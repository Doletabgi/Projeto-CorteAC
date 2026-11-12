"""Configuração e teste independente da conexão em uso pelo aplicativo."""
from dataclasses import dataclass, field, replace
import configparser
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from db import config


class SettingsError(ValueError):
    def __init__(self, message, field_name=None):
        super().__init__(message)
        self.field_name = field_name


@dataclass(frozen=True)
class ConnectionSettings:
    backend: str = 'sqlite'
    host: str = '127.0.0.1'
    port: int = 3306
    database: str = 'jobmanager'
    user: str = 'jm_app'
    password: str = field(default='', repr=False)
    sqlite_path: str = ''
    charset: str = 'utf8mb4'
    connect_timeout: int = 5


ENV_FIELDS = {
    'backend': 'DB_BACKEND', 'host': 'MYSQL_HOST', 'port': 'MYSQL_PORT',
    'database': 'MYSQL_DB', 'user': 'MYSQL_USER', 'password': 'MYSQL_PASSWORD',
    'sqlite_path': 'SQLITE_PATH', 'charset': 'MYSQL_CHARSET',
    'connect_timeout': 'MYSQL_CONNECT_TIMEOUT',
}


def _read_ini(path):
    parser = configparser.ConfigParser(interpolation=None)
    if path.exists():
        try:
            with path.open(encoding='utf-8') as stream:
                parser.read_file(stream)
        except (OSError, UnicodeError, configparser.Error) as exc:
            raise SettingsError('Não foi possível ler a configuração atual. Peça ajuda ao responsável pelo sistema.') from exc
    return parser


def _absolute_sqlite_path(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = config.APP_DIR / path
    return str(path.resolve())


def load_settings(path=None, environ=None):
    path = Path(path) if path is not None else config.INI_FILE
    environ = os.environ if environ is None else environ
    parser = _read_ini(path)
    defaults = ConnectionSettings(sqlite_path=str(config.APP_DIR / 'jobmanager.db'))
    values = {}
    for name, env_key in ENV_FIELDS.items():
        section, key = ('sqlite', 'path') if name == 'sqlite_path' else ('database', name)
        default = getattr(defaults, name)
        if name == 'backend' and parser.has_section('database'):
            default = 'mysql'
        values[name] = environ.get(env_key, parser.get(section, key, fallback=default))
    for name, default in (('port', 3306), ('connect_timeout', 5)):
        try:
            values[name] = int(values[name])
        except (ValueError, TypeError):
            raise SettingsError(f'A configuração de {"porta" if name == "port" else "tempo de conexão"} é inválida.', name)
    values['backend'] = str(values['backend']).lower()
    try:
        values['password'] = config.read_mysql_password(parser, environ, default='')
    except ValueError as exc:
        raise SettingsError('Não foi possível ler a senha salva. Peça ajuda ao responsável pelo sistema.', 'password') from exc
    values['sqlite_path'] = _absolute_sqlite_path(values['sqlite_path'])
    return ConnectionSettings(**values)


def validate_settings(settings):
    if settings.backend not in ('sqlite', 'mysql'):
        raise SettingsError('Escolha onde os dados serão guardados.', 'backend')
    if settings.backend == 'sqlite':
        if not settings.sqlite_path.strip():
            raise SettingsError('Escolha o arquivo do banco local.', 'sqlite_path')
        return replace(settings, sqlite_path=_absolute_sqlite_path(settings.sqlite_path.strip()))
    for name, label in (('host', 'o endereço do servidor'), ('database', 'o nome do banco'), ('user', 'o usuário')):
        if not getattr(settings, name).strip():
            raise SettingsError(f'Preencha {label}. Se não souber, peça esse dado ao responsável pela rede.', name)
    if not isinstance(settings.port, int) or not 1 <= settings.port <= 65535:
        raise SettingsError('A porta deve ser um número entre 1 e 65535. Normalmente é 3306.', 'port')
    return replace(settings, host=settings.host.strip(), database=settings.database.strip(), user=settings.user.strip())


def save_settings(settings, path=None):
    """Grava atomicamente, preservando pastas de rede e demais opções do INI."""
    settings = validate_settings(settings)
    path = Path(path) if path is not None else config.INI_FILE
    parser = _read_ini(path)
    if not parser.has_section('database'):
        parser.add_section('database')
    if not parser.has_section('sqlite'):
        parser.add_section('sqlite')
    for name in ('backend', 'host', 'port', 'database', 'user', 'password', 'charset', 'connect_timeout'):
        parser.set('database', name, str(getattr(settings, name)))
    # O INI remove espaços externos e quebras de linha. Preserva esses casos
    # com uma string JSON, mantendo compatibilidade com os arquivos antigos.
    if settings.password != settings.password.strip() or '\n' in settings.password or '\r' in settings.password:
        parser.set('database', 'password', json.dumps(settings.password, ensure_ascii=False))
        parser.set('database', 'password_format', 'json')
    else:
        parser.remove_option('database', 'password_format')
    parser.set('sqlite', 'path', settings.sqlite_path)
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix='.db-config-', suffix='.tmp', dir=path.parent)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            parser.write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise SettingsError('Não foi possível salvar. Verifique se você pode gravar na pasta do CorteAC.') from exc
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def probe_connection(settings):
    """Somente leitura: não muda o backend ativo, não cria banco nem tabelas."""
    settings = validate_settings(settings)
    if settings.backend == 'sqlite':
        path = Path(settings.sqlite_path)
        if not path.is_file():
            raise SettingsError('Arquivo não encontrado. Clique em Escolher arquivo e selecione o banco local.', 'sqlite_path')
        if not os.access(path, os.W_OK) or not os.access(path.parent, os.W_OK):
            raise SettingsError('O arquivo e sua pasta precisam permitir gravação para salvar seu trabalho.', 'sqlite_path')
        try:
            connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
            try:
                connection.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone()
            finally:
                connection.close()
        except sqlite3.Error as exc:
            raise SettingsError('Não foi possível abrir esse banco. Escolha um arquivo SQLite válido do CorteAC.', 'sqlite_path') from exc
        return 'Tudo certo! O banco local está acessível.'
    try:
        import pymysql
    except ImportError as exc:
        raise SettingsError('Esta instalação precisa do suporte a MySQL. Peça ao responsável para atualizar o CorteAC.') from exc
    connection = None
    try:
        connection = pymysql.connect(
            host=settings.host, port=settings.port, user=settings.user,
            password=settings.password, database=settings.database,
            charset=settings.charset, connect_timeout=5, read_timeout=5,
            write_timeout=5, autocommit=False,
        )
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception as exc:
        code = exc.args[0] if exc.args else None
        if code == 1045:
            message = 'Usuário ou senha não aceitos. Confira os dados com o responsável pelo banco.'
        elif code == 1049:
            message = 'O servidor respondeu, mas esse banco não foi encontrado. Confira o nome do banco.'
        elif code == 1044:
            message = 'Esse usuário não tem acesso ao banco. Peça ao responsável para liberar o acesso.'
        elif code in (2002, 2003, 2005, 2006, 2013) or isinstance(exc, OSError):
            message = 'Não foi possível alcançar o servidor. Confira o endereço, a porta e se este computador está conectado à rede.'
        else:
            message = 'Não foi possível concluir o teste. Confira os dados ou peça ajuda ao responsável pelo banco.'
        raise SettingsError(message) from exc
    finally:
        if connection is not None:
            connection.close()
    return 'Conexão realizada! O servidor respondeu corretamente.'
