"""
tests/test_layout_editor_sidebar_selection.py

Clique na miniatura do molde na barra lateral deve selecionar TODAS as peças
daquele número presentes na placa atual (antes selecionava apenas a primeira).
"""

import tkinter as tk
import unittest

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

    # ---------------- testes ----------------
    def test_clique_seleciona_todas_as_pecas_do_molde(self):
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
        self._click_target(idx_41)

        self.assertEqual(sorted(self.view.selected_indices), [0, 1, 2])
        self.assertEqual(self.view.selected_index, 0)
        self.assertEqual(self.view.active_target_index, idx_41)

    def test_clique_em_outro_molde_troca_a_selecao(self):
        self._setup_targets(["41", "42"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 200, 100),
            self._piece(2, "42", 100, 300),
        ]
        self.view.redraw()

        idx_42 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "42")
        self._click_target(idx_42)
        self.assertEqual(self.view.selected_indices, [2])

        idx_41 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "41")
        self._click_target(idx_41)
        self.assertEqual(sorted(self.view.selected_indices), [0, 1])

    def test_molde_sem_pecas_na_placa_nao_quebra(self):
        self._setup_targets(["41", "42"])
        self.view.placed_pieces = [self._piece(0, "41", 100, 100)]
        self.view.redraw()

        idx_42 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "42")
        self._click_target(idx_42)
        self.assertEqual(self.view.selected_indices, [])
        self.assertIsNone(self.view.selected_index)
        self.assertIn("nenhuma peça", self.view.lbl_stat_pos.cget("text").lower())

    def test_mensagem_de_status_informa_quantidade(self):
        self._setup_targets(["41"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 200, 100),
        ]
        self.view.redraw()
        self._click_target(0)
        txt = self.view.lbl_stat_pos.cget("text")
        self.assertIn("2", txt)
        self.assertIn("selecionadas", txt)

    def test_selecao_do_molde_permite_bump(self):
        self._setup_targets(["41", "42"])
        self.view.placed_pieces = [
            self._piece(0, "41", 100, 100),
            self._piece(1, "41", 200, 100),
            self._piece(2, "42", 900, 100),  # obstáculo à direita
        ]
        self.view.redraw()
        idx_41 = next(i for i, t in enumerate(self.view.sidebar_targets) if t["size"] == "41")
        self._click_target(idx_41)
        antes = [self.view.placed_pieces[i]["x"] for i in (0, 1)]
        moveu = self.view.bump_selection_vector(1, 0)
        depois = [self.view.placed_pieces[i]["x"] for i in (0, 1)]
        self.assertTrue(moveu)
        self.assertGreater(depois[0], antes[0])
        # formação relativa preservada
        self.assertAlmostEqual(depois[0] - antes[0], depois[1] - antes[1], places=6)


if __name__ == "__main__":
    unittest.main()
