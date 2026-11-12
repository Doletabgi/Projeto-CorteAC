"""Setup local/rede sem tocar na instalação ou nos bancos do operador."""
import configparser
from pathlib import Path
from unittest.mock import patch

import pytest

from db.installation_settings import configure_installation, resolve_server


@pytest.mark.parametrize('address, host, root', [
    ('SERVIDOR', 'SERVIDOR', r'\\SERVIDOR\Fabrica'),
    (' 192.168.1.100 ', '192.168.1.100', r'\\192.168.1.100\Fabrica'),
    (r'\\servidor.local\Producao', 'servidor.local', r'\\servidor.local\Producao'),
    ('\\\\SERVIDOR\\Fábrica\\OpenCorte\\', 'SERVIDOR', r'\\SERVIDOR\Fábrica\OpenCorte'),
])
def test_single_address_resolves_database_host_and_shared_root(address, host, root):
    assert resolve_server(address) == (host, root)


@pytest.mark.parametrize('address', ['', 'http://server', 'Z:\\Moldes', 'servidor\\pasta',
    '\\\\', r'\\server\\Fabrica', r'\\server\..\Fabrica', 'a"b', 'a\nb',
    '999.12.1.1', '-server', r'\\server\pasta.'])
def test_invalid_address_does_not_change_existing_configuration(tmp_path, address):
    ini = tmp_path / 'db.ini'
    ini.write_text('[database]\nbackend=sqlite\n')
    original = ini.read_bytes()
    with pytest.raises(ValueError):
        configure_installation(tmp_path, 'rede', address)
    assert ini.read_bytes() == original


def read_config(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding='utf-8')
    return parser


def test_network_configures_all_three_destinations_without_creating_data(tmp_path):
    ini = configure_installation(tmp_path, 'rede', r'\\FABRICA\Compartilhado')
    p = read_config(ini)
    assert p['database']['backend'] == 'mysql'
    assert p['database']['host'] == 'FABRICA'
    assert p['paths']['shapes_dir'] == r'\\FABRICA\Compartilhado\Moldes'
    assert p['paths']['sessions_dir'] == r'\\FABRICA\Compartilhado\Sessoes'
    assert p['installation']['server_address'] == r'\\FABRICA\Compartilhado'
    assert sorted(x.name for x in tmp_path.iterdir()) == ['db.ini']


def test_network_reconfiguration_keeps_custom_credentials_and_unrelated_options(tmp_path):
    ini = tmp_path / 'db.ini'
    ini.write_text('[database]\nbackend=mysql\nhost=antigo\nport=3310\nuser=operador\n'
                   'password=" segredo% "\npassword_format=json\ndatabase=producao\npool_size=17\n'
                   '[other]\nvalue=preservar\n', encoding='utf-8')
    configure_installation(tmp_path, 'rede', 'NOVO')
    p = read_config(ini)
    assert p['database']['host'] == 'NOVO'
    for key, value in [('port', '3310'), ('user', 'operador'), ('password', '" segredo% "'),
                       ('password_format', 'json'), ('database', 'producao'), ('pool_size', '17')]:
        assert p['database'][key] == value
    assert p['other']['value'] == 'preservar'


def test_switching_to_local_clears_both_network_paths_without_touching_data(tmp_path):
    configure_installation(tmp_path, 'rede', 'SERVIDOR')
    database = tmp_path / 'jobmanager.db'
    database.write_bytes(b'dados operacionais que nao podem ser alterados')
    configure_installation(tmp_path, 'local')
    p = read_config(tmp_path / 'db.ini')
    assert p['database']['backend'] == 'sqlite'
    assert p['sqlite']['path'] == str(database)
    assert p['paths']['shapes_dir'] == p['paths']['sessions_dir'] == ''
    assert database.read_bytes() == b'dados operacionais que nao podem ser alterados'


def test_failed_write_and_invalid_ini_preserve_original(tmp_path):
    ini = tmp_path / 'db.ini'
    ini.write_text('[database]\nbackend=sqlite\n')
    original = ini.read_bytes()
    with patch('db.installation_settings.os.replace', side_effect=PermissionError):
        with pytest.raises(PermissionError):
            configure_installation(tmp_path, 'rede', 'SERVIDOR')
    assert ini.read_bytes() == original
    assert not list(tmp_path.glob('.installation-*'))
    ini.write_text('formato invalido')
    with pytest.raises(configparser.Error):
        configure_installation(tmp_path, 'local')
    assert ini.read_text() == 'formato invalido'


def test_setup_command_uses_installation_directory_and_reports_failures(tmp_path, monkeypatch):
    import main
    from db import config
    monkeypatch.setattr(config, 'APP_DIR', tmp_path)
    monkeypatch.setattr(main.sys, 'argv', ['CorteAC.exe', '--configurar-instalacao',
                                         '--modo', 'rede', '--servidor', 'SERVIDOR'])
    with pytest.raises(SystemExit) as result:
        main.main()
    assert result.value.code == 0
    assert read_config(tmp_path / 'db.ini')['database']['host'] == 'SERVIDOR'
    original = (tmp_path / 'db.ini').read_bytes()
    error = tmp_path / 'erro.txt'
    monkeypatch.setattr(main.sys, 'argv', ['CorteAC.exe', '--configurar-instalacao',
                       '--modo', 'rede', '--servidor', 'endereco invalido', '--erro-arquivo', str(error)])
    with pytest.raises(SystemExit) as result:
        main.main()
    assert result.value.code == 1
    assert error.is_file()
    assert (tmp_path / 'db.ini').read_bytes() == original
