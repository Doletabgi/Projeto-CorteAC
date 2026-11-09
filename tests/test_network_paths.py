"""
Testes unitários para carregamento e persistência de caminhos de rede
(Moldes e Sessões da fábrica)
"""
import os
import unittest
import tempfile
import configparser
from pathlib import Path

from database import DatabaseManager
import db.config as db_config


class TestNetworkPaths(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.db = DatabaseManager(":memory:", backend="sqlite")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_network_paths_fallback_in_settings(self):
        """Verifica se get_setting utiliza os caminhos de rede como fallback quando vazio."""
        orig_sessions = db_config.SESSIONS_NETWORK_DIR
        orig_shapes = db_config.SHAPES_NETWORK_DIR
        try:
            db_config.SESSIONS_NETWORK_DIR = r"\\192.168.1.100\Fabrica\Sessoes"
            db_config.SHAPES_NETWORK_DIR = r"\\192.168.1.100\Fabrica\Moldes"

            # Sem gravação prévia no banco, deve retornar os caminhos de rede configurados
            export_dir = self.db.get_setting("machine_export_dir")
            shapes_dir = self.db.get_setting("shapes_dir")

            self.assertEqual(export_dir, r"\\192.168.1.100\Fabrica\Sessoes")
            self.assertEqual(shapes_dir, r"\\192.168.1.100\Fabrica\Moldes")

            # Se o usuário definir um caminho específico no banco, este tem prioridade
            self.db.set_setting("machine_export_dir", r"C:\Custom\Sessoes")
            self.assertEqual(self.db.get_setting("machine_export_dir"), r"C:\Custom\Sessoes")
        finally:
            db_config.SESSIONS_NETWORK_DIR = orig_sessions
            db_config.SHAPES_NETWORK_DIR = orig_shapes

    def test_read_paths_from_ini(self):
        """Verifica a leitura correta da seção [paths] a partir de um arquivo ini."""
        ini_content = """[paths]
shapes_dir = \\\\SERVIDOR\\Corte\\Moldes
sessions_dir = \\\\SERVIDOR\\Corte\\Sessoes
"""
        parser = configparser.ConfigParser()
        parser.read_string(ini_content)

        self.assertTrue(parser.has_section("paths"))
        self.assertEqual(parser.get("paths", "shapes_dir"), r"\\SERVIDOR\Corte\Moldes")
        self.assertEqual(parser.get("paths", "sessions_dir"), r"\\SERVIDOR\Corte\Sessoes")


if __name__ == "__main__":
    unittest.main()
