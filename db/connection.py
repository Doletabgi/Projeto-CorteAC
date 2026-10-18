"""
JobManager 2000 - Camada Única de Acesso a Banco de Dados
Abstrai conexões MySQL 8.0 e SQLite, tradução de sintaxe, transações e reconexão.
Nenhum outro módulo importa sqlite3 ou pymysql diretamente.
"""
import re
import sys
import threading
import queue
from typing import Any, Dict, List, Optional, Tuple, Union
from db.config import (
    DB_BACKEND, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD,
    MYSQL_DB, MYSQL_CHARSET, MYSQL_CONNECT_TIMEOUT, SQLITE_PATH
)

class ServerUnreachableError(Exception):
    """Lançada quando o servidor MySQL central estiver inacessível."""
    def __init__(self, host: str, port: int, cause: str):
        self.host = host
        self.port = port
        self.cause = cause
        super().__init__(f"Servidor MySQL inacessível em {host}:{port} - {cause}")

class VersionConflictError(Exception):
    """Lançada quando outro operador salvou o layout concorrentemente (controle otimista)."""
    pass

class DBRow(dict):
    """
    Registro retornado por consultas: comporta-se como dicionário (row['col'])
    e permite indexação inteira (row[0], row[1]) para compatibilidade com fetchone()[0].
    """
    def __getitem__(self, item):
        if isinstance(item, int):
            return list(self.values())[item]
        return super().__getitem__(item)

    def get(self, item, default=None):
        if isinstance(item, int):
            vals = list(self.values())
            return vals[item] if 0 <= item < len(vals) else default
        return super().get(item, default)


def translate_query_for_mysql(sql: str) -> str:
    """Traduz query de SQLite para MySQL 8.0."""
    # 1. Traduz '?' para '%s' preservando strings literais
    tokens = re.split(r"('[^']*'|\"[^\"]*\")", sql)
    for i in range(0, len(tokens), 2):
        tokens[i] = tokens[i].replace("?", "%s")
    sql = "".join(tokens)

    # 2. INSERT OR IGNORE -> INSERT IGNORE
    if "INSERT OR IGNORE" in sql:
        sql = sql.replace("INSERT OR IGNORE", "INSERT IGNORE")

    # 3. INSERT OR REPLACE -> REPLACE INTO
    if "INSERT OR REPLACE" in sql:
        sql = sql.replace("INSERT OR REPLACE", "REPLACE")

    return sql


class DBCursor:
    """Cursor unificado que traduz placeholders, retorna DBRow e expõe lastrowid."""
    def __init__(self, raw_cursor, backend: str):
        self.raw = raw_cursor
        self.backend = backend

    def execute(self, query: str, params=None):
        sql = query.strip()
        if self.backend == "mysql":
            # Intercepta PRAGMA table_info(tbl) para MySQL
            m_pragma = re.match(r"PRAGMA\s+table_info\((\w+)\)", sql, re.I)
            if m_pragma:
                tbl = m_pragma.group(1)
                sql = f"SHOW COLUMNS FROM `{tbl}`"
            else:
                sql = translate_query_for_mysql(sql)

        try:
            if params is None:
                return self.raw.execute(sql)
            return self.raw.execute(sql, params)
        except Exception as e:
            raise e

    def executemany(self, query: str, seq_of_params):
        sql = query.strip()
        if self.backend == "mysql":
            sql = translate_query_for_mysql(sql)
        return self.raw.executemany(sql, seq_of_params)

    def fetchone(self) -> Optional[DBRow]:
        row = self.raw.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            # Se veio de SHOW COLUMNS, normaliza chave 'Field' como [1] para compatibilidade com pragma [cid, name, ...]
            if "Field" in row:
                return DBRow({"cid": 0, "name": row["Field"], **row})
            return DBRow(row)
        if hasattr(row, "keys"):  # sqlite3.Row
            return DBRow({k: row[k] for k in row.keys()})
        if isinstance(row, (tuple, list)):
            return DBRow({f"col_{i}": v for i, v in enumerate(row)})
        return row

    def fetchall(self) -> List[DBRow]:
        rows = self.raw.fetchall()
        result = []
        for row in rows:
            if isinstance(row, dict):
                if "Field" in row:
                    result.append(DBRow({"cid": 0, "name": row["Field"], **row}))
                else:
                    result.append(DBRow(row))
            elif hasattr(row, "keys"):
                result.append(DBRow({k: row[k] for k in row.keys()}))
            elif isinstance(row, (tuple, list)):
                result.append(DBRow({f"col_{i}": v for i, v in enumerate(row)}))
            else:
                result.append(row)
        return result

    @property
    def lastrowid(self):
        return getattr(self.raw, "lastrowid", None)

    @property
    def rowcount(self):
        return getattr(self.raw, "rowcount", -1)

    def close(self):
        try:
            self.raw.close()
        except Exception:
            pass


class DBConnection:
    """Wrapper de conexão unificado com suporte a context manager e transações explícitas."""
    def __init__(self, raw_conn, backend: str, pool=None, is_memory: bool = False):
        self.raw = raw_conn
        self.backend = backend
        self._pool = pool
        self.is_memory = is_memory
        self._in_transaction = False

    def cursor(self) -> DBCursor:
        if self.backend == "mysql":
            import pymysql.cursors
            c = self.raw.cursor(pymysql.cursors.DictCursor)
        else:
            c = self.raw.cursor()
        return DBCursor(c, self.backend)

    def commit(self):
        self.raw.commit()
        self._in_transaction = False

    def rollback(self):
        try:
            self.raw.rollback()
        except Exception:
            pass
        self._in_transaction = False

    def close(self):
        if self.is_memory:
            return  # Não fecha conexão em memória compartilhada
        if self._pool is not None and self.backend == "mysql":
            self._pool.release(self.raw)
        else:
            try:
                self.raw.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
            self.close()
            return False
        else:
            try:
                self.commit()
            except Exception:
                self.rollback()
                self.close()
                raise
            self.close()
            return True


class SimpleMySQLPool:
    """Pool simples e thread-safe de conexões MySQL com reconexão automática."""
    def __init__(self, host, port, user, password, db=None, charset=None, timeout=5, max_connections=20, database=None, pool_size=None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.db = database or db or MYSQL_DB
        self.charset = charset or MYSQL_CHARSET
        self.timeout = timeout
        self.max_connections = pool_size or max_connections
        self._pool: queue.Queue = queue.Queue(maxsize=self.max_connections)
        self._lock = threading.Lock()
        self._created_count = 0

    def _create_raw(self):
        import pymysql
        try:
            return pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.db,
                charset=self.charset,
                connect_timeout=self.timeout,
                autocommit=False
            )
        except pymysql.err.OperationalError as e:
            err_code, err_msg = e.args if len(e.args) >= 2 else (0, str(e))
            raise ServerUnreachableError(self.host, self.port, f"Erro {err_code}: {err_msg}")
        except Exception as e:
            raise ServerUnreachableError(self.host, self.port, str(e))

    def get(self):
        try:
            conn = self._pool.get_nowait()
            try:
                conn.ping()
                return conn
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                return self._create_raw()
        except queue.Empty:
            with self._lock:
                return self._create_raw()

    def release(self, conn):
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            try:
                conn.close()
            except Exception:
                pass


# Instâncias globais da camada
_mysql_pool: Optional[SimpleMySQLPool] = None
_active_backend: str = DB_BACKEND

def get_active_backend() -> str:
    global _active_backend
    return _active_backend

def set_active_backend(backend: str):
    global _active_backend
    _active_backend = backend.lower()

def get_connection(database_override: Optional[str] = None) -> DBConnection:
    """
    Retorna uma conexão encapsulada de acordo com o backend ativo ('mysql' ou 'sqlite').
    """
    global _mysql_pool, _active_backend

    if _active_backend == "mysql":
        import pymysql
        target_db = database_override or MYSQL_DB
        if database_override:
            try:
                raw = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=target_db,
                    charset=MYSQL_CHARSET,
                    connect_timeout=MYSQL_CONNECT_TIMEOUT,
                    autocommit=False
                )
                return DBConnection(raw, "mysql")
            except Exception as e:
                raise ServerUnreachableError(MYSQL_HOST, MYSQL_PORT, str(e))

        if _mysql_pool is None:
            _mysql_pool = SimpleMySQLPool(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                db=MYSQL_DB,
                charset=MYSQL_CHARSET,
                timeout=MYSQL_CONNECT_TIMEOUT
            )
        raw_conn = _mysql_pool.get()
        return DBConnection(raw_conn, "mysql", pool=_mysql_pool)
    else:
        import sqlite3
        db_path = database_override or SQLITE_PATH
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return DBConnection(conn, "sqlite")

def get_memory_connection() -> DBConnection:
    """Retorna uma conexão SQLite em memória para testes isolados."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return DBConnection(conn, "sqlite", is_memory=True)
