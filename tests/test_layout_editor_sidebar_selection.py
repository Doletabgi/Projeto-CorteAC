"""
tests/test_layout_editor_sidebar_selection.py

Clique simples ativa a miniatura; menu Select seleciona as instâncias do molde.
"""

import tkinter as tk
import unittest
from unittest.mock import patch

from ui.layout_editor_view import LayoutEditorView

BOX = [
    {"x": 0.0, "y": 0.0},
    {"x": 50.0, "y": 0.0},
    {"x": 50.0, "y": 80.0},
    {"x": 0.0, "y": 80.0},
]


class DummyMouseEvent:
    def __init__(self, x=0, y=0, state=0, num=1):
        self.x = x
        self.y = y
        self.state = state
        self.num = num


class TestSidebarSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.has_display = True
        except tk.TclError:
            cls.root = None
            cls.has_display = False

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.has_display:
            self.skipTest("Tkinter display not available")
        self.view = LayoutEditorView(self.root, layout_name="[SIDEBAR]", load_sample=False)
        self.view.pack()
        self.view.set_sheet_size(1200.0, 2400.0)
        self.view.update_idletasks()
        self.view.redraw()

    def tearDown(self):
        try:
            self.view.destroy()
        except Exception:
            pass

    # ---------------- helpers ----------------
    def _piece(self, idx, size, x, y, name=None):
        return {
            "id": idx + 1,
            "name": name or f"323_PalAcb_{size}",
            "size": size,
            "color": "#3b82f6",
            "contour": [dict(p) for p in BOX],
            "x": float(x),
            "y": float(y),
            "rotation": 0.0,
        }

    def _click_target(self, target_index):
        """Simula o clique na célula da grade onde o molde é desenhado."""
        y_start, item_h, col_width, num_cols = self.view._get_sidebar_grid_layout()
        col = target_index % num_cols
        row = target_index // num_cols
        x = self.view.sidebar_div_x + 15 + col * col_width + col_width // 2
        y = y_start + row * item_h + item_h // 2
        self.view.on_sidebar_click(DummyMouseEvent(x, y))

    def _setup_targets(self, sizes):
        self.view.session_shapes = [
            {"id": s, "name": f"323_PalAcb_{s}", "size": s, "pairs": 10, "contour": [dict(p) for p in BOX]}
            for s in sizes
        ]
        self.view.update_sidebar_targets()

    def _select_target(self, target_index):
        self._click_target(target_index)
        self.view.select_active_target_pieces()

    # ---------------- testes ----------------
    def test_select_seleciona_todas_as_pecas_do_molde(self):
        self._setup_targets(["41", "42"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 200, 100),
            self._piece(2, "41", 300, 100),
            self._piece(3, "42", 100, 300),
            self._piece(4, "42", 200, 300),
        ]
        self.view.redraw()

        idx_41 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "41")
        self._select_target(idx_41)

        self.assertEqual(sorted(self.view.selected_indices), [0, 1, 2])
        self.assertEqual(self.view.selected_index, 0)
        self.assertEqual(self.view.active_target_index, idx_41)

    def test_select_em_outro_molde_acrescenta_instancias_como_original(self):
        self._setup_targets(["41", "42"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 200, 100),
            self._piece(2, "42", 100, 300),
        ]
        self.view.redraw()

        idx_42 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "42")
        self._select_target(idx_42)
        self.assertEqual(self.view.selected_indices, [2])

        idx_41 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "41")
        self._select_target(idx_41)
        self.assertEqual(sorted(self.view.selected_indices), [0, 1, 2])

    def test_molde_sem_pecas_na_placa_nao_quebra(self):
        self._setup_targets(["41", "42"])
        self.view.placed_pieces = [self._piece(0, "41", 100, 100)]
        self.view.redraw()

        idx_42 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "42")
        self._click_target(idx_42)
        self.assertEqual(self.view.selected_indices, [])
        self.assertEqual(self.view.selected_index, -1)
        self.assertIn("nenhuma peça", self.view.lbl_stat_pos.cget("text").lower())

    def test_mensagem_de_status_informa_quantidade(self):
        self._setup_targets(["41"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 200, 100),
        ]
        self.view.redraw()
        self._select_target(0)
        txt = self.view.lbl_stat_pos.cget("text")
        self.assertIn("2", txt)
        self.assertIn("selecionadas", txt)

    def _screen_center(self, idx):
        from cad.geometry import polygon_bbox, transform_contour
        p = self.view.placed_pieces[idx]
        bb = polygon_bbox(transform_contour(p["contour"], p["x"], p["y"], p.get("rotation", 0)))
        return self.view.world_to_screen((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)

    def test_shift_clique_adiciona_e_remove_pecas_da_selecao(self):
        self._setup_targets(["41"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 300, 100),
            self._piece(2, "41", 500, 100),
        ]
        self.view.redraw()
        self.view.selected_indices = []
        self.view.update_status()
        self.assertIn("Sel: 0", self.view.lbl_stat_sel.cget("text"))

        # Shift+clique adiciona
        x0, y0 = self._screen_center(0)
        self.view.on_canvas_click(DummyMouseEvent(int(x0), int(y0), state=1))
        self.assertEqual(self.view.selected_indices, [0])
        self.assertIn("Sel: 1", self.view.lbl_stat_sel.cget("text"))

        x1, y1 = self._screen_center(1)
        self.view.on_canvas_click(DummyMouseEvent(int(x1), int(y1), state=1))
        self.assertEqual(sorted(self.view.selected_indices), [0, 1])
        self.assertIn("Sel: 2", self.view.lbl_stat_sel.cget("text"))

        # Shift+clique na peça já selecionada remove
        self.view.on_canvas_click(DummyMouseEvent(int(x0), int(y0), state=1))
        self.assertEqual(self.view.selected_indices, [1])
        self.assertIn("Sel: 1", self.view.lbl_stat_sel.cget("text"))

    def test_ctrl_clique_faz_zoom_e_preserva_selecao(self):
        self._setup_targets(["41"])
        self.view.placed_pieces = [self._piece(0, "41", 100, 100)]
        self.view.redraw()
        self.view.selected_indices = [0]
        self.view.update_status()
        zoom_antes = self.view.zoom_factor
        # ponto na mesa CAD aplica zoom in e preserva seleção
        self.view.on_ctrl_canvas_click(DummyMouseEvent(60, 40, state=4))
        self.assertEqual(self.view.selected_indices, [0])
        self.assertAlmostEqual(self.view.zoom_factor, zoom_antes * 1.20, places=4)

    def test_painel_sel_reflete_comando_select(self):
        self._setup_targets(["41", "42"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 200, 100),
            self._piece(2, "41", 300, 100),
            self._piece(3, "42", 100, 300),
        ]
        self.view.redraw()
        idx_41 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "41")
        self._select_target(idx_41)
        self.assertIn("Sel: 3", self.view.lbl_stat_sel.cget("text"))

        idx_42 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "42")
        self._select_target(idx_42)
        self.assertIn("Sel: 4", self.view.lbl_stat_sel.cget("text"))

    def test_selecao_do_molde_permite_bump(self):
        self._setup_targets(["41", "42"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 200, 100),
            self._piece(2, "42", 900, 100),  # obstáculo à direita
        ]
        self.view.redraw()
        idx_41 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "41")
        self._select_target(idx_41)
        antes = [self.view.placed_pieces[i]["x"] for i in (0, 1)]
        moveu = self.view.bump_selection_vector(1, 0)
        depois = [self.view.placed_pieces[i]["x"] for i in (0, 1)]
        self.assertTrue(moveu)
        self.assertGreater(depois[0], antes[0])
        # formação relativa preservada
        self.assertAlmostEqual(depois[0] - antes[0], depois[1] - antes[1], places=6)

    def test_clique_na_miniatura_preserva_selecao_da_mesa(self):
        self._setup_targets(["41", "42"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 200, 100),
            self._piece(2, "42", 100, 300),
        ]
        for selection in ([], [2]):
            with self.subTest(selection=selection):
                self.view.selected_indices = list(selection)
                self.view.selected_index = selection[0] if selection else None
                self._click_target(0)
                self.assertEqual(self.view.selected_indices, selection)
                self.assertEqual(self.view.selected_index, selection[0] if selection else None)
                self.assertEqual(self.view.active_target_index, 0)

    def test_menu_select_da_miniatura_nao_inicia_rotacao(self):
        self._setup_targets(["41", "42"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 200, 100),
            self._piece(2, "42", 100, 300),
        ]
        self.view.selected_indices = [2]
        self.view.selected_index = 2
        idx = next(i for i, target in enumerate(self.view.sidebar_targets) if target["size"] == "41")
        y, h, width, cols = self.view._get_sidebar_grid_layout()
        row, col = divmod(idx, cols)
        ev = DummyMouseEvent(self.view.sidebar_div_x + 15 + col * width + width // 2,
                             y + row * h + h // 2, num=3)
        with patch.object(self.view.sidebar_context_menu, "tk_popup") as popup, \
             patch.object(self.view.context_menu_102, "tk_popup") as canvas_popup:
            self.view.on_rbutton_press(ev)
            self.assertFalse(self.view._rdrag_active)
            self.view.on_rbutton_drag(DummyMouseEvent(ev.x + 40, ev.y + 40, num=3))
            self.view.on_rbutton_release(ev)
            popup.assert_called_once()
            canvas_popup.assert_not_called()
        self.assertEqual(self.view.selected_indices, [2])
        self.assertTrue(all(p["rotation"] == 0 for p in self.view.placed_pieces))
        self.view.sidebar_context_menu.invoke("Select")
        self.assertEqual(sorted(self.view.selected_indices), [0, 1, 2])
        self.assertEqual(self.view.undo_stack, [])
        self.assertFalse(self.view.is_modified)


if __name__ == "__main__":
    unittest.main()
