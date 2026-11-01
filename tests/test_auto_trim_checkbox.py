"""
Testes Unitários: Checkbox de Refile Automático e Recorte Pós-Nesting (test_auto_trim_checkbox.py)
"""
import copy
import os
import unittest
import tkinter as tk
from tkinter import ttk

from cad.layers_rule import (
    is_refile_auto_enabled,
    is_separar_sobras_enabled,
    parse_session_params,
    encode_session_params,
    trim_layout_dict,
    calculate_layout_trim_bounds,
)
from cad.trim_engine import calculate_layout_trim_bounds as engine_bounds, trim_layout_dict as engine_trim
from ui.session_view import SessionView


class TestAutoTrimLogic(unittest.TestCase):
    def test_is_refile_auto_enabled_defaults_to_false(self):
        """Verifica que refile_auto é False por padrão para presets normais ou None."""
        self.assertFalse(is_refile_auto_enabled(None))
        self.assertFalse(is_refile_auto_enabled(""))
        self.assertFalse(is_refile_auto_enabled("ALTERNADO"))
        self.assertFalse(is_refile_auto_enabled("stdNOTFill"))
        self.assertFalse(is_refile_auto_enabled("stdNOTFill;separar_sobras=1"))
        self.assertFalse(is_refile_auto_enabled({}))
        self.assertFalse(is_refile_auto_enabled({"params": "stdNOTFill"}))

    def test_is_refile_auto_enabled_truthy_values(self):
        """Verifica detecção de refile_auto habilitado com '1', 'true', 'yes', 'on', 'sim'."""
        for val in ("1", "true", "yes", "on", "sim", "TRUE", "Yes"):
            param_str = f"stdNOTFill;refile_auto={val}"
            self.assertTrue(is_refile_auto_enabled(param_str), f"Falha para valor {val}")
            self.assertTrue(is_refile_auto_enabled({"params": param_str}), f"Falha para dict com {val}")

    def test_is_refile_auto_enabled_falsy_values(self):
        """Verifica detecção de refile_auto desabilitado explicitamente."""
        for val in ("0", "false", "no", "off", "nao", "00"):
            param_str = f"stdNOTFill;refile_auto={val}"
            self.assertFalse(is_refile_auto_enabled(param_str), f"Falha para valor {val}")
            self.assertFalse(is_refile_auto_enabled({"params": param_str}), f"Falha para dict com {val}")

    def test_encode_and_parse_session_params_with_refile(self):
        """Verifica codificação e decodificação combinada de separar_sobras e refile_auto."""
        encoded = encode_session_params("stdNOTFill", {"separar_sobras": "1", "refile_auto": "1"})
        preset, opts = parse_session_params(encoded)
        self.assertEqual(preset, "stdNOTFill")
        self.assertEqual(opts.get("separar_sobras"), "1")
        self.assertEqual(opts.get("refile_auto"), "1")
        self.assertTrue(is_refile_auto_enabled(encoded))

    def test_calculate_layout_trim_bounds(self):
        """Calcula cotas exatas de contornos com folga/gap de 1.0 mm."""
        # Peça 1: quadrado 100x100 em (10, 20) -> max_x = 110, max_y = 120
        # Peça 2: quadrado 50x50 em (300, 400) -> max_x = 350, max_y = 450
        pieces = [
            {
                "x": 10.0,
                "y": 20.0,
                "rotation": 0.0,
                "contour": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}],
            },
            {
                "x": 300.0,
                "y": 400.0,
                "rotation": 0.0,
                "contour": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 50}, {"x": 0, "y": 50}],
            }
        ]
        w, h = calculate_layout_trim_bounds(pieces, gap_mm=1.0)
        self.assertEqual(w, 351.0)  # 350 + 1.0
        self.assertEqual(h, 451.0)  # 450 + 1.0

    def test_trim_layout_dict_updates_dimensions_and_cut_line(self):
        """Verifica que trim_layout_dict ajusta dimensões, gera trim_cut_line e recalcula rendimento."""
        layout = {
            "name": "lay0000",
            "width_mm": 1350.0,
            "height_mm": 2553.38,
            "pieces": [
                {
                    "x": 50.0,
                    "y": 100.0,
                    "rotation": 0.0,
                    "contour": [{"x": 0, "y": 0}, {"x": 200, "y": 0}, {"x": 200, "y": 300}, {"x": 0, "y": 300}],
                }
            ],
            "yield_percent": 15.0,
        }

        trimmed = trim_layout_dict(layout, original_w=1350.0, original_h=2553.38, gap_mm=1.0)

        # Cota esperada: max_x = 50 + 200 = 250 -> 251.0 mm; max_y = 100 + 300 = 400 -> 401.0 mm
        self.assertEqual(trimmed["width_mm"], 251.0)
        self.assertEqual(trimmed["height_mm"], 401.0)
        self.assertEqual(trimmed["original_sheet_width"], 1350.0)
        self.assertEqual(trimmed["original_sheet_height"], 2553.38)
        self.assertIsNotNone(trimmed.get("trim_cut_line"))
        cut = trimmed["trim_cut_line"]
        self.assertTrue(cut["enabled"])
        self.assertEqual(cut["x"], 251.0)
        self.assertEqual(cut["y"], 401.0)
        self.assertTrue(cut["has_cut_x"])
        self.assertTrue(cut["has_cut_y"])
        # Área refilada é muito menor, rendimento sobre a chapa refilada deve ser maior que 15%
        self.assertGreater(trimmed["yield_percent"], 50.0)


class TestSessionViewAutoTrimCheckbox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        self.session_data = {
            "id": 999,
            "name": "Sessão Teste Refile",
            "params": "stdNOTFill",
            "layers": 4,
            "placed_pieces": [],
            "shapes": [],
        }
        self.view = SessionView(self.root, session_data=self.session_data, db=None)

    def tearDown(self):
        if hasattr(self, "view") and self.view:
            try:
                self.view.destroy()
            except Exception:
                pass

    def test_checkbox_exists_and_side_by_side(self):
        """Verifica a existência das checkboxes de 'Separar sobras' e 'Refile automático' lado a lado."""
        self.assertTrue(hasattr(self.view, "chk_separar_sobras"))
        self.assertTrue(hasattr(self.view, "chk_refile_auto"))
        self.assertTrue(hasattr(self.view, "var_refile_auto"))

        # Ambos devem compartilhar o mesmo master (frame_checks)
        self.assertEqual(self.view.chk_separar_sobras.master, self.view.chk_refile_auto.master)
        self.assertEqual(self.view.chk_refile_auto.cget("text"), "Refile automático")

    def test_toggle_refile_auto_updates_session_params(self):
        """Ao alternar o checkbox, o campo params da sessão deve persistir refile_auto=1."""
        self.assertFalse(self.view.is_refile_auto_active())
        self.view.var_refile_auto.set(True)
        self.view.on_refile_auto_toggled()

        self.assertTrue(self.view.is_refile_auto_active())
        params_str = self.view.session_data.get("params", "")
        self.assertIn("refile_auto=1", params_str)

        # Toggle de volta para False
        self.view.var_refile_auto.set(False)
        self.view.on_refile_auto_toggled()
        self.assertFalse(self.view.is_refile_auto_active())
        params_str = self.view.session_data.get("params", "")
        self.assertIn("refile_auto=0", params_str)

    def test_load_session_syncs_checkbox(self):
        """load_session restaura o estado marcado/desmarcado a partir de session_data."""
        sess_with_refile = {
            "id": 1001,
            "name": "Sessão com Refile",
            "params": "stdNOTFill;refile_auto=1",
            "layers": 2,
            "placed_pieces": [],
            "shapes": [],
        }
        self.view.load_session(sess_with_refile)
        self.assertTrue(self.view.var_refile_auto.get())
        self.assertTrue(self.view.is_refile_auto_active())

        sess_without_refile = {
            "id": 1002,
            "name": "Sessão sem Refile",
            "params": "ALTERNADO",
            "layers": 2,
            "placed_pieces": [],
            "shapes": [],
        }
        self.view.load_session(sess_without_refile)
        self.assertFalse(self.view.var_refile_auto.get())
        self.assertFalse(self.view.is_refile_auto_active())

    def test_get_params_reflects_checkbox_state(self):
        """get_params() inclui refile_auto=1 quando marcado."""
        self.view.var_refile_auto.set(True)
        p = self.view.get_params()
        self.assertIn("refile_auto=1", p)

        self.view.var_refile_auto.set(False)
        p = self.view.get_params()
        self.assertIn("refile_auto=0", p)


class DummyWidget:
    def __init__(self):
        self.text = ""
    def config(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]
    def select(self, *args):
        pass


class TestAutoTrimMainWindowIntegration(unittest.TestCase):
    def test_auto_trim_applied_in_nesting_worker(self):
        """Simula finalização do cálculo de nesting com refile_auto=1 habilitado."""
        import queue
        from ui.main_window import MainWindow

        class FakeApp:
            def __init__(self):
                self.current_session = {
                    "id": 88,
                    "name": "Sessão Teste",
                    "params": "stdNOTFill;refile_auto=1",
                    "layers": 2,
                    "placed_pieces": [],
                    "layouts": [],
                    "material": {"width_mm": 1350.0, "height_mm": 2553.38}
                }
                self.sessions = [self.current_session]
                self.current_shapes = []
                self.canvas = type("FakeCanvas", (), {"set_pieces": lambda self, p: None})()
                self.lbl_status_msg = DummyWidget()
                self.db = type("FakeDB", (), {
                    "save_session_layouts": lambda *args: True,
                    "update_session": lambda *args, **kwargs: True,
                    "update_session_shapes": lambda *args: True,
                })()
                self.session_view = None
                self.layout_editor_view = None
                self.current_mode = "jobs"
                self.save_current_session_state = lambda: None

            def config(self, **kwargs):
                pass

            def switch_tree_mode(self, mode):
                pass

            def _poll_nest_worker(self, q, strategy, params, machine, gap=1.0, margins=None, layers=2):
                MainWindow._poll_nest_worker(self, q, strategy, params, machine, gap=gap, margins=margins, layers=layers)

        app = FakeApp()
        layout_raw = {
            "layout_index": 0,
            "name": "lay0000",
            "pieces": [
                {
                    "x": 20.0,
                    "y": 30.0,
                    "rotation": 0.0,
                    "contour": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 200}, {"x": 0, "y": 200}],
                }
            ],
            "width_mm": 1350.0,
            "height_mm": 2553.38,
            "yield_percent": 10.0,
        }

        q = queue.Queue()
        q.put(("SUCCESS", {
            "layouts": [layout_raw],
            "params": "stdNOTFill;refile_auto=1",
            "strategy": "flashnestsheet",
            "machine": "ATOM Flex",
            "gap": 1.0,
            "margins": {"left": 10, "right": 10, "top": 10, "bottom": 10},
            "layers": 2,
            "elapsed_ms": 120,
        }))


        app._poll_nest_worker(q, "flashnestsheet", "stdNOTFill;refile_auto=1", "ATOM Flex")


        # Valida que o layout foi refilado:
        # max_x = 20 + 100 = 120 -> + 1.0 = 121.0 mm
        # max_y = 30 + 200 = 230 -> + 1.0 = 231.0 mm
        first_ly = app.current_session["layouts"][0]
        self.assertEqual(first_ly["width_mm"], 121.0)
        self.assertEqual(first_ly["height_mm"], 231.0)
        self.assertEqual(app.current_session["sheet_width"], 121.0)
        self.assertEqual(app.current_session["sheet_height"], 231.0)
        self.assertIsNotNone(app.current_session.get("trim_cut_line"))
        self.assertTrue(app.current_session["trim_cut_line"]["enabled"])
        self.assertIn("✂ Refile automático", app.lbl_status_msg.text)

    def test_no_trim_when_refile_auto_disabled(self):
        """Verifica que quando refile_auto=0 o layout mantém as dimensões integrais da chapa."""
        import queue
        from ui.main_window import MainWindow

        class FakeApp:
            def __init__(self):
                self.current_session = {
                    "id": 89,
                    "name": "Sessão Sem Refile",
                    "params": "stdNOTFill",
                    "layers": 2,
                    "placed_pieces": [],
                    "layouts": [],
                    "material": {"width_mm": 1350.0, "height_mm": 2553.38}
                }
                self.sessions = [self.current_session]
                self.current_shapes = []
                self.canvas = type("FakeCanvas", (), {"set_pieces": lambda self, p: None})()
                self.lbl_status_msg = DummyWidget()
                self.db = type("FakeDB", (), {
                    "save_session_layouts": lambda *args: True,
                    "update_session": lambda *args, **kwargs: True,
                    "update_session_shapes": lambda *args: True,
                })()
                self.session_view = None
                self.layout_editor_view = None
                self.current_mode = "jobs"
                self.save_current_session_state = lambda: None

            def config(self, **kwargs):
                pass

            def switch_tree_mode(self, mode):
                pass

            def _poll_nest_worker(self, q, strategy, params, machine, gap=1.0, margins=None, layers=2):
                MainWindow._poll_nest_worker(self, q, strategy, params, machine, gap=gap, margins=margins, layers=layers)

        app = FakeApp()
        layout_raw = {
            "layout_index": 0,
            "name": "lay0000",
            "pieces": [
                {
                    "x": 20.0,
                    "y": 30.0,
                    "rotation": 0.0,
                    "contour": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 200}, {"x": 0, "y": 200}],
                }
            ],
            "width_mm": 1350.0,
            "height_mm": 2553.38,
            "yield_percent": 10.0,
        }

        q = queue.Queue()
        q.put(("SUCCESS", {
            "layouts": [layout_raw],
            "params": "stdNOTFill",
            "strategy": "flashnestsheet",
            "machine": "ATOM Flex",
            "gap": 1.0,
            "margins": {"left": 10, "right": 10, "top": 10, "bottom": 10},
            "layers": 2,
            "elapsed_ms": 120,
        }))

        app._poll_nest_worker(q, "flashnestsheet", "stdNOTFill", "ATOM Flex")

        first_ly = app.current_session["layouts"][0]
        self.assertEqual(first_ly["width_mm"], 1350.0)
        self.assertEqual(first_ly["height_mm"], 2553.38)
        self.assertIsNone(app.current_session.get("trim_cut_line"))
        self.assertNotIn("✂ Refile automático", app.lbl_status_msg.text)


if __name__ == "__main__":
    unittest.main()


