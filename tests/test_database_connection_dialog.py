"""Fluxos reais da tela, com arquivos temporários e teste MySQL simulado."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import threading
import time
import tkinter as tk
from unittest.mock import patch

import pytest

from db.connection_settings import ConnectionSettings, SettingsError, load_settings, save_settings
from ui.database_connection_dialog import DatabaseConnectionDialog


@pytest.fixture
def dialog(tmp_path):
    root = tk.Tk()
    root.withdraw()
    path = tmp_path / 'local.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE sample (value TEXT)')
    config_path = tmp_path / 'db.ini'
    save_settings(ConnectionSettings(sqlite_path=str(path)), config_path)
    window = DatabaseConnectionDialog(root, config_path=config_path, environ={})
    yield window
    if window.winfo_exists():
        window.destroy()
    root.destroy()


def wait_for_test(window):
    deadline = time.monotonic() + 3
    while window._busy and time.monotonic() < deadline:
        window.update()
        time.sleep(.01)
    assert not window._busy


def use_mysql(window):
    window.backend.set('mysql')
    window._mode_changed()
    window.host.set('192.0.2.20')
    window.database.set('jobmanager')
    window.user.set('operador')
    window.password.set('senha%123')


def test_mode_selection_and_password_visibility(dialog):
    dialog.update()
    assert dialog.local_frame.winfo_ismapped()
    assert not dialog.server_frame.winfo_ismapped()
    use_mysql(dialog)
    dialog.update()
    assert dialog.server_frame.winfo_ismapped()
    assert not dialog.local_frame.winfo_ismapped()
    assert dialog.fields['password'].cget('show')
    dialog.show_password.set(True)
    dialog._toggle_password()
    assert dialog.fields['password'].cget('show') == ''


def test_validation_focuses_missing_field_and_shows_invalid_port(dialog):
    use_mysql(dialog)
    dialog.host.set('')
    dialog.save_configuration()
    assert 'endereço do servidor' in dialog.status.get()
    assert not dialog._busy
    dialog.host.set('server')
    dialog.port.set('abc')
    dialog.save_configuration()
    assert 'porta' in dialog.status.get()
    assert dialog.show_port.get()


def test_local_save_tests_read_only_then_saves_for_next_start(dialog):
    original_db = Path(dialog.sqlite_path.get()).read_bytes()
    dialog.save_configuration()
    wait_for_test(dialog)
    assert 'Configuração salva' in dialog.status.get()
    assert 'Feche e abra' in dialog.status.get()
    assert load_settings(dialog.config_path, {}).backend == 'sqlite'
    assert Path(dialog.sqlite_path.get()).read_bytes() == original_db


def test_failed_mysql_test_never_saves_or_changes_file(dialog):
    original = dialog.config_path.read_bytes()
    use_mysql(dialog)
    with patch('ui.database_connection_dialog.probe_connection', side_effect=SettingsError('Confira o usuário ou a senha.')):
        dialog.save_configuration()
        wait_for_test(dialog)
    assert 'senha' in dialog.status.get()
    assert dialog.config_path.read_bytes() == original
    assert dialog.save_button.cget('state') == 'normal'


def test_success_is_invalidated_if_form_changes_before_save(dialog):
    use_mysql(dialog)
    with patch('ui.database_connection_dialog.probe_connection', return_value='Conectado.') as probe:
        dialog.test_connection()
        wait_for_test(dialog)
        assert load_settings(dialog.config_path, {}).backend == 'sqlite'
        dialog.host.set('outro-servidor')
        dialog.save_configuration()
        wait_for_test(dialog)
    assert probe.call_count == 2
    saved = load_settings(dialog.config_path, {})
    assert saved.backend == 'mysql'
    assert saved.host == 'outro-servidor'
    assert saved.password == 'senha%123'


def test_verified_settings_save_without_repeating_test(dialog):
    use_mysql(dialog)
    with patch('ui.database_connection_dialog.probe_connection', return_value='Conectado.') as probe:
        dialog.test_connection()
        wait_for_test(dialog)
        dialog.save_configuration()
    assert probe.call_count == 1
    assert load_settings(dialog.config_path, {}).backend == 'mysql'


def test_close_while_testing_does_not_write_or_call_tk_from_worker(dialog):
    entered, release = threading.Event(), threading.Event()
    original = dialog.config_path.read_bytes()
    path = dialog.config_path
    def slow_probe(settings):
        entered.set()
        release.wait(timeout=2)
        return 'Conectado.'
    with patch('ui.database_connection_dialog.probe_connection', side_effect=slow_probe):
        dialog.save_configuration()
        assert entered.wait(timeout=1)
        assert dialog.save_button.cget('state') == 'disabled'
        dialog.destroy()
        release.set()
    assert path.read_bytes() == original


def test_external_configuration_does_not_claim_to_save_ineffective_changes(dialog):
    other = DatabaseConnectionDialog(dialog.master, config_path=dialog.config_path,
                                      environ={'DB_BACKEND': 'sqlite'})
    try:
        assert other.save_button.cget('state') == 'disabled'
        assert 'configurações externas' in other.status.get()
    finally:
        other.destroy()
