"""
JobManager 2000 - Configuração de Banco de Dados Central
Carrega parâmetros de conexão do arquivo db.ini e/ou variáveis de ambiente.
"""
import os
import sys
import configparser
from pathlib import Path

# Localiza diretório base da aplicação (compatível com PyInstaller frozen)
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

INI_FILE = APP_DIR / "db.ini"

# Lê arquivo db.ini se existir
_parser = configparser.ConfigParser()
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

# Configurações globais
DB_BACKEND = _get_val("database", "backend", "DB_BACKEND", "mysql").lower()

# Parâmetros MySQL 8.0 Central
MYSQL_HOST = _get_val("database", "host", "MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = _get_int("database", "port", "MYSQL_PORT", 3306)
MYSQL_USER = _get_val("database", "user", "MYSQL_USER", "jm_app")
MYSQL_PASSWORD = _get_val("database", "password", "MYSQL_PASSWORD", "jm_factory_2026")
MYSQL_DB = _get_val("database", "database", "MYSQL_DB", "jobmanager")
MYSQL_CHARSET = _get_val("database", "charset", "MYSQL_CHARSET", "utf8mb4")
MYSQL_CONNECT_TIMEOUT = _get_int("database", "connect_timeout", "MYSQL_CONNECT_TIMEOUT", 5)

# Parâmetros SQLite Reserva
SQLITE_PATH = _get_val("sqlite", "path", "SQLITE_PATH", str(APP_DIR / "jobmanager.db"))
