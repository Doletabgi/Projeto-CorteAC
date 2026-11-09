"""
tests/test_database_cleanup.py

Testes automatizados para a regra de higienização e limpeza de layouts de teste
pré e pós-atualização do CorteAC (JobManager 2000).
"""

import os
import tempfile
import unittest
import sqlite3
from unittest.mock import patch, MagicMock

from database import DatabaseManager
from config import APP_VERSION


class TestDatabaseCleanup(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_clean.db")
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass
        if os.path.exists(self.tmp_dir):
            try:
                os.rmdir(self.tmp_dir)
            except Exception:
                pass

    def test_clean_test_layouts_cleans_dirty_database(self):
        """Valida que clean_test_layouts purga layouts, layout_pieces, sessões de teste e reseta status."""
        # 1. Cria uma sessão real e uma sessão de teste
        sess_real_id = self.db.create_session(name="Sessão Produção Oficial", job="JOB_01")
        sess_test_id = self.db.create_session(name="Sessão Teste Autonest", job="JOB_TEST")

        # 2. Salva layouts com peças
        pieces = [
            {"id": 1, "name": "MOLDE_1", "size": "38", "x": 10.0, "y": 20.0, "rotation": 0.0},
            {"id": 2, "name": "MOLDE_2", "size": "38", "x": 50.0, "y": 60.0, "rotation": 180.0},
        ]
        self.db.save_session_layouts(sess_real_id, [{"layout_index": 0, "name": "lay0000", "pieces": pieces, "yield_pct": 78.5}])
        self.db.save_session_layouts(sess_test_id, [{"layout_index": 0, "name": "lay_test", "pieces": pieces, "yield_pct": 82.0}])

        # Verifica que o banco está "sujo" com layouts
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM layouts")
            self.assertEqual(cur.fetchone()[0], 2)
            cur.execute("SELECT count(*) FROM layout_pieces")
            self.assertGreaterEqual(cur.fetchone()[0], 2)

        # 3. Executa a limpeza
        stats = self.db.clean_test_layouts()
        self.assertEqual(stats["deleted_layouts"], 2)
        self.assertGreaterEqual(stats["deleted_pieces"], 2)
        self.assertGreaterEqual(stats["deleted_sessions"], 1)

        # 4. Verifica que o banco está 100% limpo
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            # 0 layouts e 0 peças
            cur.execute("SELECT count(*) FROM layouts")
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute("SELECT count(*) FROM layout_pieces")
            self.assertEqual(cur.fetchone()[0], 0)

            # Sessão de teste excluída
            cur.execute("SELECT count(*) FROM sessions WHERE id = ?", (sess_test_id,))
            self.assertEqual(cur.fetchone()[0], 0)

            # Sessão real preservada, mas em 'Stand by' e com placed_pieces_json = '[]'
            cur.execute("SELECT status, placed_pieces_json, yield_percent FROM sessions WHERE id = ?", (sess_real_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "Stand by")
            self.assertEqual(row[1], "[]")
            self.assertEqual(row[2], 0.0)

        # last_active_session_id aponta para a sessão real
        last_sid = self.db.get_setting("last_active_session_id")
        self.assertEqual(str(last_sid), str(sess_real_id))

    def test_post_update_preserves_layout_on_version_mismatch(self):
        """Valida que a atualização preserva o layout e grava a nova versão."""
        # Configura versão instalada como anterior
        self.db.set_setting("installed_version", "1.6.26")

        # Insere layout de teste
        sess_id = self.db.create_session(name="Sessão Operador")
        self.db.save_session_layouts(sess_id, [{"layout_index": 0, "name": "lay0000", "pieces": [{"id": 1, "name": "P1", "size": "36", "x": 0, "y": 0, "rotation": 0}], "yield_pct": 75.0}])

        # Simula MainWindow com a regra check_post_update_cleanup
        mock_win = MagicMock()
        mock_win.db = self.db
        from ui.main_window import MainWindow
        MainWindow.check_post_update_cleanup(mock_win)

        # Verifica que o layout foi preservado
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM layouts")
            self.assertEqual(cur.fetchone()[0], 1)

        # Verifica que installed_version foi atualizado para APP_VERSION atual
        self.assertEqual(self.db.get_setting("installed_version"), APP_VERSION)

    def test_post_update_cleanup_skips_when_same_version(self):
        """Valida que reinicialização na mesma versão não apaga o trabalho do operador."""
        # Configura versão instalada já igual à versão atual
        self.db.set_setting("installed_version", APP_VERSION)

        # Insere layout legítimo
        sess_id = self.db.create_session(name="Sessão Operador Legítima")
        self.db.save_session_layouts(sess_id, [{"layout_index": 0, "name": "lay_trabalho", "pieces": [{"id": 1, "name": "P1", "size": "36", "x": 0, "y": 0, "rotation": 0}], "yield_pct": 79.0}])

        # Simula MainWindow com a regra check_post_update_cleanup
        mock_win = MagicMock()
        mock_win.db = self.db
        from ui.main_window import MainWindow
        MainWindow.check_post_update_cleanup(mock_win)

        # O layout NÃO deve ser apagado
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM layouts")
            self.assertEqual(cur.fetchone()[0], 1)

    def test_tools_clean_database_script(self):
        """Valida a execução do script tools/clean_database.py em banco isolado."""
        sess_id = self.db.create_session(name="Sessão Teste Script")
        self.db.save_session_layouts(sess_id, [{"layout_index": 0, "name": "lay_scr", "pieces": [], "yield_pct": 50.0}])

        from tools.clean_database import clean_db
        res = clean_db(self.db_path, verbose=False)
        self.assertTrue(res)

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM layouts")
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute("SELECT count(*) FROM sessions WHERE id = ?", (sess_id,))
            self.assertEqual(cur.fetchone()[0], 0)

        self.assertEqual(self.db.get_setting("installed_version"), APP_VERSION)


if __name__ == "__main__":
    unittest.main()
