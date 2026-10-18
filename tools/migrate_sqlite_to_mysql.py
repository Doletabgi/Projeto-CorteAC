#!/usr/bin/env python3
"""
tools/migrate_sqlite_to_mysql.py - Migra jobmanager.db (SQLite) para MySQL 8.0 Central.

Características:
- Modo --dry-run para simulação segura.
- Backup automático de jobmanager.db -> jobmanager.db.bak antes de iniciar.
- Execução transacional e idempotente (INSERT ... ON DUPLICATE KEY UPDATE / INSERT IGNORE).
- Verificação e exibição da contagem de linhas linha-a-linha no final.
"""

import sys
import os
import shutil
import sqlite3
import argparse
from pathlib import Path

# Adiciona raiz do projeto ao sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import db
from db.config import SQLITE_PATH, MYSQL_HOST, MYSQL_PORT, MYSQL_DB, MYSQL_USER

TABLES_ORDER = [
    "materials",
    "orders",
    "articles",
    "shape_folders",
    "shapes",
    "sessions",
    "settings",
    "dieproc_presets",
    "layouts",
    "layout_pieces"
]

def make_backup(sqlite_file: Path) -> Path:
    backup_file = sqlite_file.with_name(sqlite_file.name + ".bak")
    shutil.copy2(sqlite_file, backup_file)
    return backup_file

def migrate(sqlite_file: Path, dry_run: bool = False, target_db: str = None) -> bool:
    if not sqlite_file.exists():
        print(f"ERRO: Banco SQLite não encontrado em {sqlite_file}", file=sys.stderr)
        return False

    print(f"=================================================================")
    print(f" MIGRAÇÃO: SQLite -> MySQL 8.0 Central")
    print(f" Origem:  {sqlite_file} ({sqlite_file.stat().st_size} bytes)")
    print(f" Destino: MySQL {MYSQL_HOST}:{MYSQL_PORT} / {target_db or MYSQL_DB}")
    print(f" Modo:    {'DRY-RUN (Simulação - nenhuma gravação)' if dry_run else 'PRODUÇÃO (Gravação Transacional)'}")
    print(f"=================================================================\n")

    if not dry_run:
        bak = make_backup(sqlite_file)
        print(f"[1/4] Backup de segurança criado: {bak}")
    else:
        print("[1/4] Modo dry-run: backup ignorado.")

    # Conecta ao SQLite
    sq_conn = sqlite3.connect(str(sqlite_file))
    sq_conn.row_factory = sqlite3.Row

    # Conecta ao MySQL
    try:
        my_conn = db.get_connection(database_override=target_db)
    except Exception as e:
        print(f"ERRO ao conectar ao MySQL: {e}", file=sys.stderr)
        return False

    print(f"[2/4] Conexão MySQL estabelecida com sucesso.")

    counts_sqlite = {}
    counts_mysql_before = {}
    counts_mysql_after = {}

    my_cur = my_conn.cursor()

    # Contagem inicial
    for tbl in TABLES_ORDER:
        try:
            sq_cur = sq_conn.cursor()
            sq_cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            counts_sqlite[tbl] = sq_cur.fetchone()[0]
        except Exception:
            counts_sqlite[tbl] = 0

        try:
            my_cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            counts_mysql_before[tbl] = my_cur.fetchone()[0]
        except Exception:
            counts_mysql_before[tbl] = 0

    print("[3/4] Migrando tabelas...")

    try:
        # Desativa foreign key checks temporariamente para inserção rápida em lote
        if not dry_run:
            my_cur.execute("SET FOREIGN_KEY_CHECKS = 0")

        for tbl in TABLES_ORDER:
            sq_cur = sq_conn.cursor()
            try:
                sq_cur.execute(f"SELECT * FROM {tbl}")
                rows = sq_cur.fetchall()
            except Exception as e:
                print(f"  - {tbl}: tabela inexistente no SQLite ({e}), pulando.")
                continue

            if not rows:
                print(f"  - {tbl}: 0 registros no SQLite.")
                continue

            cols = list(rows[0].keys())
            placeholders = ", ".join(["%s"] * len(cols))
            
            # Ajuste de escape para colunas reservadas (ex: `key`, `desc`)
            def esc(c):
                return f"`{c}`" if c.lower() in ("key", "desc", "order", "status") else c

            col_names = ", ".join(esc(c) for c in cols)

            if tbl == "materials":
                update_clause = "name=VALUES(name), type=VALUES(type), width_mm=VALUES(width_mm), height_mm=VALUES(height_mm), area_m2=VALUES(area_m2), thickness_mm=VALUES(thickness_mm), layers=VALUES(layers), gap_mm=VALUES(gap_mm)"
                sql = f"INSERT INTO materials ({col_names}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"
            elif tbl == "settings":
                sql = f"INSERT INTO settings ({col_names}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE `value`=VALUES(`value`)"
            elif tbl == "dieproc_presets":
                sql = f"INSERT INTO dieproc_presets ({col_names}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE coupling=VALUES(coupling), step=VALUES(step)"
            elif tbl == "shape_folders":
                sql = f"INSERT IGNORE INTO shape_folders ({col_names}) VALUES ({placeholders})"
            elif tbl == "layouts":
                # Mapeia colunas existentes e inclui defaults para colunas novas da Etapa 2
                sql = f"INSERT IGNORE INTO layouts ({col_names}) VALUES ({placeholders})"
            elif tbl == "layout_pieces":
                cols_to_use = list(cols)
                if "mold_id" not in cols_to_use and "shape_id" in cols_to_use:
                    cols_to_use.append("mold_id")
                if "mirrored" not in cols_to_use and "is_mirrored" in cols_to_use:
                    cols_to_use.append("mirrored")
                placeholders = ", ".join(["%s"] * len(cols_to_use))
                col_names = ", ".join(esc(c) for c in cols_to_use)
                sql = f"INSERT IGNORE INTO layout_pieces ({col_names}) VALUES ({placeholders})"
            else:
                sql = f"INSERT IGNORE INTO {tbl} ({col_names}) VALUES ({placeholders})"

            data = []
            for r in rows:
                row_vals = [r[c] for c in cols]
                if tbl == "layout_pieces":
                    if "mold_id" not in cols and "shape_id" in cols:
                        row_vals.append(r["shape_id"])
                    if "mirrored" not in cols and "is_mirrored" in cols:
                        row_vals.append(r["is_mirrored"])
                data.append(tuple(row_vals))

            if dry_run:
                print(f"  [DRY-RUN] {tbl}: {len(data)} registros seriam migrados.")
            else:
                my_cur.executemany(sql, data)
                print(f"  [OK] {tbl}: {len(data)} registros inseridos/sincronizados.")

        if not dry_run:
            my_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            my_conn.commit()
            print("\n[4/4] Transação confirmada (COMMIT).")
        else:
            print("\n[4/4] Modo dry-run finalizado sem alterações.")

    except Exception as e:
        if not dry_run:
            my_conn.rollback()
            print(f"\nERRO durante a migração. ROLLBACK executado: {e}", file=sys.stderr)
        raise e
    finally:
        my_conn.close()
        sq_conn.close()

    # Contagem final de validação
    print("\n=================================================================")
    print(" RELATÓRIO DE CONCILIAÇÃO DE DADOS (CONTAGEM DE REGISTROS)")
    print("=================================================================")
    print(f"{'Tabela':<20} | {'SQLite Original':<15} | {'MySQL Final':<15} | {'Status':<10}")
    print("-" * 68)

    check_conn = db.get_connection(database_override=target_db)
    check_cur = check_conn.cursor()
    all_equal = True

    for tbl in TABLES_ORDER:
        check_cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        final_count = check_cur.fetchone()[0]
        orig_count = counts_sqlite.get(tbl, 0)
        status = "IGUAL" if (dry_run or final_count == orig_count) else "DIVERGENTE"
        if not (dry_run or final_count == orig_count):
            all_equal = False
        print(f"{tbl:<20} | {orig_count:<15} | {final_count:<15} | {status:<10}")

    check_conn.close()
    print("=================================================================\n")
    return all_equal

def main():
    parser = argparse.ArgumentParser(description="Migra jobmanager.db para MySQL 8.0 Central.")
    parser.add_argument("--sqlite", default=SQLITE_PATH, help=f"Caminho do arquivo SQLite (padrão: {SQLITE_PATH})")
    parser.add_argument("--dry-run", action="store_true", help="Simula a migração sem gravar no MySQL.")
    parser.add_argument("--target-db", default=None, help="Nome do banco de destino (padrão: configurado no db.ini / env)")
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite).resolve()
    success = migrate(sqlite_path, dry_run=args.dry_run, target_db=args.target_db)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
