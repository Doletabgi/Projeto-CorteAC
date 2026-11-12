"""Configuração do setup: modo local ou um único endereço de rede.

Não conecta a servidores, não cria compartilhamentos e não altera bancos.
"""
import argparse
import configparser
import ipaddress
import os
from pathlib import Path
import re
import tempfile


def resolve_server(address):
    """Retorna host MySQL e raiz UNC; um host isolado usa o share Fabrica."""
    value = address.strip()
    if not value or any(ord(c) < 32 or c in '/:*?"<>|' for c in value):
        raise ValueError('Informe o nome/IP do servidor ou um caminho como \\\\SERVIDOR\\Fabrica.')
    if value.startswith('\\\\'):
        parts = value[2:].rstrip('\\').split('\\')
    else:
        parts = [value]
    host = parts[0]
    if not re.fullmatch(r'[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?', host):
        raise ValueError('O endereço deve começar com um nome ou IP de servidor válido.')
    if re.fullmatch(r'[0-9.]+', host):
        try:
            ipaddress.IPv4Address(host)
        except ValueError as exc:
            raise ValueError('O endereço IP do servidor não é válido.') from exc
    if any(not p.strip() or p != p.strip() or p in ('.', '..') or p.endswith('.') for p in parts[1:]):
        raise ValueError('Informe uma pasta compartilhada válida, sem trechos vazios ou relativos.')
    root = '\\\\' + '\\'.join(parts if len(parts) > 1 else [host, 'Fabrica'])
    return host, root


def configure_installation(app_dir, mode, address=''):
    """Grava o INI atomicamente, preservando credenciais e opções não alteradas."""
    if mode not in ('local', 'rede'):
        raise ValueError('Escolha instalação local ou em rede.')
    host, root = resolve_server(address) if mode == 'rede' else ('', '')
    app_dir = Path(app_dir)
    path = app_dir / 'db.ini'
    parser = configparser.ConfigParser(interpolation=None)
    if path.exists():
        with path.open(encoding='utf-8-sig') as stream:
            parser.read_file(stream)
    for section in ('database', 'sqlite', 'paths', 'installation'):
        if not parser.has_section(section):
            parser.add_section(section)
    # A escolha local retira referências de rede, sem apagar bancos ou arquivos.
    parser.set('database', 'backend', 'mysql' if mode == 'rede' else 'sqlite')
    parser.set('paths', 'shapes_dir', root+'\\Moldes' if root else '')
    parser.set('paths', 'sessions_dir', root+'\\Sessoes' if root else '')
    parser.set('installation', 'mode', mode)
    parser.set('installation', 'server_address', root)
    if mode == 'local' or not parser.has_option('sqlite', 'path'):
        parser.set('sqlite', 'path', str(app_dir / 'jobmanager.db'))
    if mode == 'rede':
        parser.set('database', 'host', host)
        # Instalações existentes conservam porta, usuário, senha e nome do banco.
        from db import config
        for key, default in (('port', '3306'), ('user', 'jm_app'),
                             ('password', config.read_mysql_password(configparser.ConfigParser(), environ={})),
                             ('database', 'jobmanager'), ('charset', 'utf8mb4')):
            if not parser.has_option('database', key):
                parser.set('database', key, default)
                if key == 'password':
                    parser.remove_option('database', 'password_format')
    fd, temporary = tempfile.mkstemp(prefix='.installation-', suffix='.tmp', dir=app_dir)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            parser.write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def installer_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modo', choices=('local', 'rede'), required=True)
    parser.add_argument('--servidor', default='')
    parser.add_argument('--erro-arquivo')
    args = parser.parse_args(argv)
    try:
        from db.config import APP_DIR
        configure_installation(APP_DIR, args.modo, args.servidor)
        return 0
    except (OSError, ValueError, configparser.Error):
        # Não expõe credenciais ou conteúdo de um INI inválido no log do setup.
        message = ('Não foi possível salvar a configuração. Confira o endereço do servidor, '
                   'o arquivo db.ini e a permissão de gravação na pasta da instalação.')
        if args.erro_arquivo:
            Path(args.erro_arquivo).write_text(message, encoding='utf-8')
        return 1
