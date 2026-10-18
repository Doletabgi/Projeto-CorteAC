"""
Camada de Acesso a Dados do JobManager (MySQL 8.0 / SQLite Reserva)
"""
from db.connection import (
    get_connection,
    get_memory_connection,
    DBConnection,
    DBCursor,
    DBRow,
    ServerUnreachableError,
    VersionConflictError,
    get_active_backend,
    set_active_backend
)
from db.config import (
    DB_BACKEND,
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_DB,
    SQLITE_PATH
)

__all__ = [
    "get_connection",
    "DBConnection",
    "DBCursor",
    "DBRow",
    "ServerUnreachableError",
    "VersionConflictError",
    "get_active_backend",
    "set_active_backend",
    "DB_BACKEND",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_DB",
    "SQLITE_PATH",
]
