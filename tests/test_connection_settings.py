"""Configuração e sondagens sem usar o banco do operador ou um servidor real."""
from dataclasses import replace
import configparser
import os
from pathlib import Path
import runpy
import sqlite3
import sys
from unittest.mock import MagicMock, patch

import pytest

from db import config
from db.connection import get_active_backend
from db.connection_settings import ConnectionSettings, SettingsError, load_settings, probe_connection, save_settings


@pytest.fixture
def settings(tmp_path):
    return ConnectionSettings(backend='mysql', host='192.0.2.10', password='p%#@;123',
                              sqlite_path=str(tmp_path / 'local.db'))


def test_missing_file_defaults_to_local_beside_application(tmp_path):
    loaded = load_settings(tmp_path / 'db.ini', {})
    assert loaded.backend == 'sqlite'
    assert loaded.sqlite_path == str(config.APP_DIR / 'jobmanager.db')
    assert loaded.password == ''


def test_roundtrip_preserves_password_and_other_sections(tmp_path, settings):
    path = tmp_path / 'db.ini'
    path.write_text('[database]\npool_size = 17\n[paths]\nshapes_dir = \\\\SERVIDOR\\Moldes\n', encoding='utf-8')
    save_settings(settings, path)
    assert load_settings(path, {}) == settings
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path)
    assert parser.get('paths', 'shapes_dir') == r'\\SERVIDOR\Moldes'
    assert parser.get('database', 'pool_size') == '17'
    assert settings.password not in repr(settings)
    if os.name != 'nt':
        assert path.stat().st_mode & 0o777 == 0o600


def test_environment_precedence_and_legacy_relative_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'APP_DIR', tmp_path)
    path = tmp_path / 'db.ini'
    path.write_text('[database]\nhost = old\n[sqlite]\npath = local.db\n')
    loaded = load_settings(path, {'MYSQL_HOST': 'server', 'MYSQL_PASSWORD': ' secret% '})
    assert loaded.backend == 'mysql'
    assert loaded.host == 'server'
    assert loaded.password == ' secret% '
    assert loaded.sqlite_path == str(tmp_path / 'local.db')


def test_config_reader_accepts_literal_percent_password_and_relative_path(tmp_path, settings, monkeypatch):
    path = tmp_path / 'db.ini'
    save_settings(replace(settings, sqlite_path='local.db'), path)
    # Faz o leitor de inicialização enxergar uma instalação temporária.
    with monkeypatch.context() as scoped:
        for key in ('MYSQL_PASSWORD', 'SQLITE_PATH', 'DB_BACKEND'):
            scoped.delenv(key, raising=False)
        scoped.setattr(sys, 'frozen', True, raising=False)
        scoped.setattr(sys, 'executable', str(tmp_path / 'CorteAC'))
        state = runpy.run_path(str(Path(config.__file__)))
    assert state['MYSQL_PASSWORD'] == settings.password
    assert state['DB_BACKEND'] == 'mysql'


def test_invalid_settings_and_failed_write_leave_existing_file_untouched(tmp_path, settings):
    path = tmp_path / 'db.ini'
    path.write_text('[database]\nbackend = sqlite\n')
    original = path.read_bytes()
    with pytest.raises(SettingsError, match='porta'):
        save_settings(replace(settings, port=0), path)
    assert path.read_bytes() == original
    with patch('db.connection_settings.os.replace', side_effect=PermissionError()):
        with pytest.raises(SettingsError, match='salvar'):
            save_settings(settings, path)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob('.db-config-*'))


def test_malformed_file_is_not_overwritten(tmp_path, settings):
    path = tmp_path / 'db.ini'
    path.write_text('configuração inválida')
    with pytest.raises(SettingsError):
        save_settings(settings, path)
    assert path.read_text() == 'configuração inválida'


def test_sqlite_probe_reads_real_database_without_modification(tmp_path):
    path = tmp_path / 'local.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE sample (value TEXT)')
        connection.execute("INSERT INTO sample VALUES ('preservar')")
    original = path.read_bytes()
    backend = get_active_backend()
    assert 'Tudo certo' in probe_connection(ConnectionSettings(sqlite_path=str(path)))
    assert path.read_bytes() == original
    assert get_active_backend() == backend


def test_sqlite_probe_does_not_create_missing_file_or_accept_wrong_format(tmp_path):
    path = tmp_path / 'missing.db'
    with pytest.raises(SettingsError, match='não encontrado'):
        probe_connection(ConnectionSettings(sqlite_path=str(path)))
    assert not path.exists()
    path.write_text('Este arquivo não é um banco SQLite')
    with pytest.raises(SettingsError, match='SQLite válido'):
        probe_connection(ConnectionSettings(sqlite_path=str(path)))


def test_mysql_probe_uses_entered_settings_and_only_selects(settings):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    backend = get_active_backend()
    with patch('pymysql.connect', return_value=connection) as connect:
        assert 'Conexão realizada' in probe_connection(settings)
    assert connect.call_args.kwargs['host'] == settings.host
    assert connect.call_args.kwargs['password'] == settings.password
    assert connect.call_args.kwargs['database'] == settings.database
    cursor.execute.assert_called_once_with('SELECT 1')
    connection.commit.assert_not_called()
    connection.close.assert_called_once()
    assert get_active_backend() == backend


@pytest.mark.parametrize('code, expected', [(1045, 'Usuário ou senha'), (1049, 'não foi encontrado'),
                                           (1044, 'não tem acesso'), (2003, 'alcançar o servidor'),
                                           (2005, 'alcançar o servidor'), (9999, 'concluir o teste')])
def test_mysql_errors_are_actionable_and_do_not_expose_password(settings, code, expected):
    with patch('pymysql.connect', side_effect=Exception(code, settings.password)):
        with pytest.raises(SettingsError) as error:
            probe_connection(settings)
    assert expected in str(error.value)
    assert settings.password not in str(error.value)


@pytest.mark.parametrize('password', ['  senha% com espaços  ', 'linha1\nlinha2', 'senha#;\\á%', ''])
def test_password_survives_save_and_startup_reader(tmp_path, settings, password):
    path = tmp_path / 'db.ini'
    save_settings(replace(settings, password=password), path)
    assert load_settings(path, {}).password == password
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path)
    assert config.read_mysql_password(parser, {}, default='') == password
    # Retirar a codificação especial ao salvar uma senha normal também funciona.
    save_settings(replace(settings, password='normal%123'), path)
    assert load_settings(path, {}).password == 'normal%123'
