"""
JobManager 2000 - Configuração de Banco de Dados Central
Carrega parâmetros de conexão do arquivo db.ini e/ou variáveis de ambiente.
"""
import os
import sys
import configparser
import json
from pathlib import Path

# Localiza diretório base da aplicação (compatível com PyInstaller frozen)
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

INI_FILE = APP_DIR / "db.ini"

# Lê arquivo db.ini se existir
_parser = configparser.ConfigParser(interpolation=None)
if INI_FILE.exists():
    _parser.read(str(INI_FILE), encoding="utf-8")

def _get_val(section: str, key: str, env_var: str, default: str) -> str:
    env_val = os.getenv(env_var)
    if env_val is not None:
        return env_val
    if _parser.has_section(section) and _parser.has_option(section, key):
        return _parser.get(section, key)
    return default

def _get_int(section: str, key: str, env_var: str, default: int) -> int:
    val = _get_val(section, key, env_var, str(default))
    try:
        return int(val)
    except ValueError:
        return default


def read_mysql_password(parser, environ=None, default="jm_factory_2026"):
    """Lê também senhas com espaços nas extremidades, preservadas pela tela."""
    environ = os.environ if environ is None else environ
    if "MYSQL_PASSWORD" in environ:
        return environ["MYSQL_PASSWORD"]
    value = parser.get("database", "password", fallback=default)
    if parser.get("database", "password_format", fallback="plain") == "json":
        value = json.loads(value)
        if not isinstance(value, str):
            raise ValueError("Formato de senha inválido")
    return value

# Configurações globais:
# Se existir db.ini configurado ou variável de ambiente, usa o valor indicado.
# Se NÃO existir db.ini (ex: máquina de testes, VM ou cliente avulso), o padrão seguro é 'sqlite'
default_backend = "mysql" if (INI_FILE.exists() and _parser.has_section("database")) else "sqlite"
DB_BACKEND = _get_val("database", "backend", "DB_BACKEND", default_backend).lower()

# Parâmetros MySQL 8.0 Central
MYSQL_HOST = _get_val("database", "host", "MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = _get_int("database", "port", "MYSQL_PORT", 3306)
MYSQL_USER = _get_val("database", "user", "MYSQL_USER", "jm_app")
MYSQL_PASSWORD = read_mysql_password(_parser)
MYSQL_DB = _get_val("database", "database", "MYSQL_DB", "jobmanager")
MYSQL_CHARSET = _get_val("database", "charset", "MYSQL_CHARSET", "utf8mb4")
MYSQL_CONNECT_TIMEOUT = _get_int("database", "connect_timeout", "MYSQL_CONNECT_TIMEOUT", 5)

# Parâmetros SQLite Reserva
SQLITE_PATH = _get_val("sqlite", "path", "SQLITE_PATH", str(APP_DIR / "jobmanager.db"))
# O banco acompanha a instalação, mesmo quando o atalho inicia em outra pasta.
if SQLITE_PATH != ":memory:":
    _sqlite_file = Path(SQLITE_PATH).expanduser()
    if not _sqlite_file.is_absolute():
        _sqlite_file = APP_DIR / _sqlite_file
    SQLITE_PATH = str(_sqlite_file.resolve())

# Parâmetros de Pastas de Rede (Moldes e Sessões da Fábrica)
SHAPES_NETWORK_DIR = _get_val("paths", "shapes_dir", "CORTEAC_SHAPES_DIR", "").strip()
SESSIONS_NETWORK_DIR = _get_val("paths", "sessions_dir", "CORTEAC_SESSIONS_DIR", "").strip()

