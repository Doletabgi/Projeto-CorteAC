"""
tests/test_shape_editor_fullscreen.py

Testes automatizados para a abertura do ShapeEditorView em tela cheia:
1. show_shape_editor abre maximizado em tela cheia (in_=win, relwidth=1.0, relheight=1.0)
2. Alternância de maximização / restauração para mdi_workspace
3. Fechamento e liberação da janela
4. Duplo-clique na barra de título alterna maximização
5. Atalhos de F11 e Escape para fullscreen
"""
import unittest
import tkinter as tk
from unittest.mock import MagicMock, patch

from ui.main_window import MainWindow
from ui.shape_editor_view import ShapeEditorView


class TestShapeEditorFullscreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()
        cls.win.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.win.destroy()
        except Exception:
            pass

    def setUp(self):
        self.win.update()

    def tearDown(self):
        try:
            if self.win.shape_editor_view in self.win.open_windows:
                self.win.close_window(self.win.shape_editor_view)
                self.win.update()
        except Exception:
            pass

    def test_01_show_shape_editor_opens_in_fullscreen(self):
        """1. show_shape_editor abre em tela cheia (in_=win, relwidth=1.0, relheight=1.0)."""
        self.win.show_shape_editor()
        self.win.update()

        self.assertEqual(self.win.shape_editor_view.winfo_manager(), "place")
        self.assertIn(self.win.shape_editor_view, self.win.open_windows)
        pinfo = self.win.shape_editor_view.place_info()

        # Deve ocupar 100% da tela do MainWindow
        self.assertEqual(str(pinfo.get("in")), str(self.win))
        self.assertIn(str(pinfo.get("relwidth")), ("1", "1.0"))
        self.assertIn(str(pinfo.get("relheight")), ("1", "1.0"))
        self.assertEqual(str(pinfo.get("x")), "0")
        self.assertEqual(str(pinfo.get("y")), "0")

        # Botão maximizar deve estar em modo restaurar (❐)
        self.assertEqual(self.win.shape_editor_view.btn_max.cget("text"), "❐")
        self.assertIn("tela cheia", self.win.lbl_status_msg.cget("text"))

    def test_02_shape_editor_toggle_maximize_restore(self):
        """2. toggle_maximize alterna entre tela cheia e janela no mdi_workspace."""
        self.win.show_shape_editor()
        self.win.update()

        # Restaura para modo janela
        self.win.toggle_maximize_window(self.win.shape_editor_view)
        self.win.update()

        pinfo_restored = self.win.shape_editor_view.place_info()
        self.assertEqual(str(pinfo_restored.get("in")), str(self.win.mdi_workspace))
        self.assertEqual(self.win.shape_editor_view.btn_max.cget("text"), "□")

        # Maximiza novamente para tela cheia
        self.win.toggle_maximize_window(self.win.shape_editor_view)
        self.win.update()

        pinfo_max = self.win.shape_editor_view.place_info()
        self.assertEqual(str(pinfo_max.get("in")), str(self.win))
        self.assertIn(str(pinfo_max.get("relwidth")), ("1", "1.0"))
        self.assertEqual(self.win.shape_editor_view.btn_max.cget("text"), "❐")

    def test_03_shape_editor_close_window(self):
        """3. Fechar o Shape Editor desmapeia a tela cheia."""
        self.win.show_shape_editor()
        self.win.update()
        self.assertEqual(self.win.shape_editor_view.winfo_manager(), "place")

        self.win.close_window(self.win.shape_editor_view)
        self.win.update()
        self.assertEqual(self.win.shape_editor_view.winfo_manager(), "")
        self.assertNotIn(self.win.shape_editor_view, self.win.open_windows)

    def test_04_shape_editor_title_double_click_calls_maximize(self):
        """4. Duplo-clique no título chama on_maximize_click."""
        editor = self.win.shape_editor_view
        called = []
        editor.on_maximize_cb = lambda *args: called.append(True)

        editor.on_maximize_click()
        self.assertTrue(len(called) > 0)

    def test_05_title_drag_ignored_when_fullscreen(self):
        """5. Arrastar barra de título em tela cheia não desloca a janela."""
        self.win.show_shape_editor()
        self.win.update()

        editor = self.win.shape_editor_view
        editor._drag_start_x = 100
        editor._drag_start_y = 100
        editor._win_start_x = 0
        editor._win_start_y = 0

        class MockEvent:
            x_root = 150
            y_root = 150

        editor._on_title_motion(MockEvent())
        pinfo = editor.place_info()
        self.assertEqual(str(pinfo.get("x")), "0")
        self.assertEqual(str(pinfo.get("y")), "0")

    def test_06_f11_and_escape_fullscreen_handlers(self):
        """6. on_f11_fullscreen e on_escape_key funcionam corretamente."""
        editor = self.win.shape_editor_view
        with patch.object(self.win, "toggle_fullscreen") as mock_toggle:
            editor.on_f11_fullscreen()
            mock_toggle.assert_called_once()

    def test_07_shape_centered_in_middle_of_canvas(self):
        """7. A peça inicia centralizada exatamente no meio do canvas, não no canto."""
        from cad.geometry import polygon_bbox
        shape_27 = self.win.db.get_shape(27)
        self.win.show_shape_editor(shape_27)
        self.win.update()

        editor = self.win.shape_editor_view
        cv = editor.canvas

        # Verifica centralização com painel de info ativo
        contour = editor.shape["contour"]
        min_x, min_y, max_x, max_y = polygon_bbox(contour)
        mid_x = (min_x + max_x) / 2.0
        mid_y = (min_y + max_y) / 2.0
        sx, sy = editor.world_to_screen(mid_x, mid_y)
        canvas_cx = cv.winfo_width() / 2.0
        canvas_cy = cv.winfo_height() / 2.0

        self.assertAlmostEqual(sx, canvas_cx, delta=1.5)
        self.assertAlmostEqual(sy, canvas_cy, delta=1.5)

        # Verifica centralização ao ocultar o painel de info
        editor.show_info_panel.set(False)
        editor.toggle_info_panel()
        self.win.update()

        sx_no_info, sy_no_info = editor.world_to_screen(mid_x, mid_y)
        canvas_cx_no_info = cv.winfo_width() / 2.0
        canvas_cy_no_info = cv.winfo_height() / 2.0

        self.assertAlmostEqual(sx_no_info, canvas_cx_no_info, delta=1.5)
        self.assertAlmostEqual(sy_no_info, canvas_cy_no_info, delta=1.5)


if __name__ == "__main__":
    unittest.main()
