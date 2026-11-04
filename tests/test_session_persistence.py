"""
tests/test_session_persistence.py

Testes automatizados para a persistência da última sessão ativa,
protocolo de fechamento seguro (WM_DELETE_WINDOW / on_app_close)
e substituição atômica de layouts ao importar .lay.
"""

import unittest
from unittest.mock import MagicMock, patch
import json


class TestSessionPersistence(unittest.TestCase):

    def test_settings_last_active_session_id(self):
        """Verifica se get_setting e set_setting persistem last_active_session_id corretamente."""
        from database import DatabaseManager
        db = DatabaseManager(":memory:")
        self.assertIsNone(db.get_setting("last_active_session_id"))

        db.set_setting("last_active_session_id", 188)
        self.assertEqual(db.get_setting("last_active_session_id"), "188")

        db.set_setting("last_active_session_id", 189)
        self.assertEqual(db.get_setting("last_active_session_id"), "189")

    def test_load_initial_data_restores_last_active_session(self):
        """MainWindow.load_initial_data deve restaurar a sessão gravada em last_active_session_id."""
        from database import DatabaseManager
        db = DatabaseManager(":memory:")
        id1 = db.create_session(name="Sessão Antiga")
        id2 = db.create_session(name="Sessão Recente")

        # Define que a última sessão ativa era a id2
        db.set_setting("last_active_session_id", id2)

        sessions = db.get_sessions()
        last_sid_str = db.get_setting("last_active_session_id")
        last_sid = int(last_sid_str) if last_sid_str else None
        target = next((s for s in sessions if s["id"] == last_sid), None)

        self.assertIsNotNone(target)
        self.assertEqual(target["id"], id2)
        self.assertEqual(target["name"], "Sessão Recente")

    def test_on_app_close_saves_current_session_state(self):
        """on_app_close deve salvar a sessão ativa e gravar last_active_session_id."""
        from ui.main_window import MainWindow

        mock_win = MagicMock(spec=MainWindow)
        mock_win.current_session = {"id": 188, "name": "Sessão #188"}
        mock_win.db = MagicMock()
        mock_win.save_current_session_state = MagicMock()
        mock_win.destroy = MagicMock()

        # Executa o método unbound on_app_close
        MainWindow.on_app_close(mock_win)

        mock_win.save_current_session_state.assert_called_once()
        mock_win.db.set_setting.assert_called_once_with("last_active_session_id", 188)
        mock_win.destroy.assert_called_once()

    def test_import_lay_file_replaces_session_layouts_atomically(self):
        """import_lay_file deve substituir session_data['layouts'] e persistir via save_session_layouts."""
        from ui.session_view import SessionView

        mock_sv = MagicMock(spec=SessionView)
        mock_sv.session_data = {
            "id": 188,
            "name": "Sessão #188",
            "layouts": [{"layout_index": 0, "name": "lay_antigo", "pieces": []}],
            "placed_pieces": [],
            "yield_percent": 0.0
        }
        mock_sv.db = MagicMock()
        mock_sv.load_session = MagicMock()

        # Mock de lay retornado por parse_lay
        mock_lay = MagicMock()
        mock_lay.filename = "lay0000.lay"
        mock_lay.ris_w = 1360.0
        mock_lay.ris_l = 2860.0
        mock_lay.cod_r = "0001 - Couro"
        mock_lay.gap = 1.0
        mock_lay.layers = 4
        mock_lay.calculate_yield.return_value = 75.5
        mock_lay.items = [
            MagicMock(item_no=1, tg_idx=0, shape_name="323_PalAcb_30a", size="41", color="#2563eb",
                      contour=[(0, 0), (10, 0), (10, 10)], holes=[], stitching=[], internal_cuts=[],
                      x=100.0, y=200.0, rot_deg=0.0, is_mirrored=False, tag=None, quality_zone=1)
        ]

        with patch("ui.session_view.filedialog.askopenfilename", return_value="/tmp/lay0000.lay"), \
             patch("ui.session_view.parse_lay", return_value=mock_lay), \
             patch("ui.session_view.validate_layout_placement", return_value=[]), \
             patch("ui.session_view.messagebox.showinfo"):
            SessionView.import_lay_file(mock_sv)

        # Verifica se session_data["layouts"] foi atualizado com o layout importado
        self.assertEqual(len(mock_sv.session_data["layouts"]), 1)
        imported = mock_sv.session_data["layouts"][0]
        self.assertEqual(imported["name"], "lay0000.lay")
        self.assertEqual(imported["width_mm"], 1360.0)
        self.assertEqual(imported["height_mm"], 2860.0)
        self.assertEqual(imported["yield_percent"], 75.5)
        self.assertEqual(len(imported["pieces"]), 1)

        # Verifica chamada atômica save_session_layouts
        mock_sv.db.save_session_layouts.assert_called_once_with(188, [imported])


if __name__ == "__main__":
    unittest.main()
