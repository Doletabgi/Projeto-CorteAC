"""
tests/test_layout_editor_bump.py

Testes do Bump Magnético do Layout Editor (setas + bump interativo com o mouse):
- botão do meio com seleção, duplo-clique + arrasto e Ctrl+Shift + arrasto;
- direção livre (horizontal, vertical, 45° e 30°);
- linha elástica, cancelamento por Esc e arrasto curto;
- seleção múltipla em bloco, validação final e undo atômico;
- não regressão do pan com botão do meio sem seleção.
"""

import math
import tkinter as tk
import unittest

from cad.geometry import polygon_bbox, polygons_collide, transform_contour
from ui.layout_editor_view import BUMP_MIN_DRAG_PX, LayoutEditorView

SHEET_W = 1000.0
SHEET_H = 1000.0
MARGIN = 10.0
# Peça retangular simples 100 x 100 mm (contorno fechado, sentido anti-horário)
BOX = [
    {"x": 0.0, "y": 0.0},
    {"x": 100.0, "y": 0.0},
    {"x": 100.0, "y": 100.0},
    {"x": 0.0, "y": 100.0},
]
# Peça côncava em "L" (20 mm de espessura de braço), para o teste diagonal
CONCAVE = [
    {"x": 0.0, "y": 0.0},
    {"x": 120.0, "y": 0.0},
    {"x": 120.0, "y": 20.0},
    {"x": 20.0, "y": 20.0},
    {"x": 20.0, "y": 120.0},
    {"x": 0.0, "y": 120.0},
]


class DummyMouseEvent:
    def __init__(self, x=0, y=0, state=0, num=1):
        self.x = x
        self.y = y
        self.state = state
        self.num = num


class TestLayoutEditorBump(unittest.TestCase):
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
        self.view = LayoutEditorView(self.root, layout_name="[BUMP]", load_sample=False)
        self.view.pack()
        self.view.set_sheet_size(SHEET_W, SHEET_H)
        self.view.set_margins(MARGIN, MARGIN, MARGIN, MARGIN)
        self.view.gap_mm = 1.0
        self.view.zoom_factor = 1.0
        self.view.update_idletasks()
        self.view.redraw()

    def tearDown(self):
        try:
            self.view.destroy()
        except Exception:
            pass

    # ---------------- helpers ----------------
    def _piece(self, idx, x, y, contour=None, size="41"):
        return {
            "id": idx + 1,
            "name": f"P{idx}",
            "size": size,
            "color": "#3b82f6",
            "contour": [dict(p) for p in (contour or BOX)],
            "x": float(x),
            "y": float(y),
            "rotation": 0.0,
        }

    def _load(self, pieces, selected=(0,)):
        self.view.placed_pieces = pieces
        self.view.selected_indices = list(selected)
        self.view.selected_index = selected[0] if selected else None
        self.view.redraw()

    def _bbox(self, idx):
        p = self.view.placed_pieces[idx]
        return polygon_bbox(transform_contour(p["contour"], p["x"], p["y"], p.get("rotation", 0)))

    def _collisions(self):
        polys = [transform_contour(p["contour"], p["x"], p["y"], p.get("rotation", 0))
                 for p in self.view.placed_pieces]
        bbs = [polygon_bbox(p) for p in polys]
        total = 0
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                a, b = bbs[i], bbs[j]
                if a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]:
                    continue
                if polygons_collide(polys[i], polys[j], gap=0.0, bbox_a=a, bbox_b=b):
                    total += 1
        return total

    # ---------------- 1. direções ----------------
    def test_bump_horizontal_encosta_no_obstaculo(self):
        self._load([self._piece(0, 100, 100), self._piece(1, 400, 100)])
        self.view.bump_selection_vector(1, 0)
        b0, b1 = self._bbox(0), self._bbox(1)
        # encostou no obstáculo respeitando o gap de 1 mm
        self.assertAlmostEqual(b1[0] - b0[2], 1.0, delta=0.2)
        self.assertEqual(self._collisions(), 0)

    def test_bump_vertical_encosta_no_obstaculo(self):
        self._load([self._piece(0, 100, 100), self._piece(1, 100, 400)])
        self.view.bump_selection_vector(0, 1)
        b0, b1 = self._bbox(0), self._bbox(1)
        self.assertAlmostEqual(b1[1] - b0[3], 1.0, delta=0.2)
        self.assertEqual(self._collisions(), 0)

    def test_bump_diagonal_45_para_no_limite_da_placa(self):
        self._load([self._piece(0, 100, 100)])
        self.view.bump_selection_vector(1, 1)
        b0 = self._bbox(0)
        # sem obstáculos, para na margem superior/direita (a primeira que chegar)
        self.assertAlmostEqual(max(b0[2], b0[3]), SHEET_W - MARGIN, delta=0.3)
        self.assertEqual(self._collisions(), 0)

    def test_bump_30_graus_respeita_direcao(self):
        # obstáculo deslocado em 30° a partir da peça
        ang = math.radians(30.0)
        ox = 100.0 + math.cos(ang) * 300.0
        oy = 100.0 + math.sin(ang) * 300.0
        self._load([self._piece(0, 100, 100), self._piece(1, ox, oy)])
        x0, y0 = self.view.placed_pieces[0]["x"], self.view.placed_pieces[0]["y"]
        self.view.bump_selection_vector(math.cos(ang), math.sin(ang))
        x1, y1 = self.view.placed_pieces[0]["x"], self.view.placed_pieces[0]["y"]
        # o deslocamento deve ser colinear com o vetor pedido
        dx, dy = x1 - x0, y1 - y0
        self.assertGreater(math.hypot(dx, dy), 1.0)
        self.assertAlmostEqual(dy / dx, math.tan(ang), delta=0.02)
        self.assertEqual(self._collisions(), 0)

    # ---------------- 2. gatilhos de mouse ----------------
    def _trigger_middle(self, dx_px, dy_px):
        cx, cy = self.view.world_to_screen(150.0, 150.0)
        self.view.on_pan_start(DummyMouseEvent(cx, cy, num=2))
        self.view.on_pan_drag(DummyMouseEvent(cx + dx_px, cy + dy_px, num=2))
        self.view.on_pan_end(DummyMouseEvent(cx + dx_px, cy + dy_px, num=2))

    def test_tres_gatilhos_produzem_o_mesmo_resultado(self):
        resultados = []
        for gatilho in ("middle", "ctrl_shift", "double_click"):
            self._load([self._piece(0, 300, 300), self._piece(1, 700, 300)])
            cx, cy = self.view.world_to_screen(350.0, 350.0)
            ev_start = DummyMouseEvent(cx, cy)
            ev_end = DummyMouseEvent(cx + 60, cy)
            if gatilho == "middle":
                self.view.on_pan_start(DummyMouseEvent(cx, cy, num=2))
                self.view.on_pan_drag(DummyMouseEvent(cx + 60, cy, num=2))
                self.view.on_pan_end(DummyMouseEvent(cx + 60, cy, num=2))
            elif gatilho == "ctrl_shift":
                self.view.on_ctrl_shift_bump_start(ev_start)
                self.view.on_ctrl_shift_bump_drag(ev_end)
                self.view.on_ctrl_shift_bump_end(ev_end)
            else:
                # 1º clique seleciona; 2º clique (< 300 ms) arma o bump; arrasto executa
                self.view.on_canvas_click(ev_start)
                self.view.on_canvas_click(ev_start)
                self.view.on_canvas_drag(ev_end)
                self.view.on_canvas_release(ev_end)
            p = self.view.placed_pieces[0]
            resultados.append((round(p["x"], 1), round(p["y"], 1)))

        self.assertEqual(len({r for r in resultados}), 1, f"Gatilhos divergiram: {resultados}")
        self.assertGreater(resultados[0][0], 300.0)

    # ---------------- 3/4/7. arrasto curto, Esc e linha elástica ----------------
    def test_arrasto_curto_nao_move_e_nao_cria_undo(self):
        self._load([self._piece(0, 300, 300), self._piece(1, 700, 300)])
        antes = (self.view.placed_pieces[0]["x"], self.view.placed_pieces[0]["y"])
        undo_antes = len(self.view.undo_stack)
        cx, cy = self.view.world_to_screen(350.0, 350.0)
        self.view.on_ctrl_shift_bump_start(DummyMouseEvent(cx, cy))
        self.view.on_ctrl_shift_bump_drag(DummyMouseEvent(cx + BUMP_MIN_DRAG_PX - 1, cy))
        self.view.on_ctrl_shift_bump_end(DummyMouseEvent(cx + BUMP_MIN_DRAG_PX - 1, cy))
        self.assertEqual((self.view.placed_pieces[0]["x"], self.view.placed_pieces[0]["y"]), antes)
        self.assertEqual(len(self.view.undo_stack), undo_antes)

    def test_esc_cancela_bump_e_remove_linha_elastica(self):
        self._load([self._piece(0, 300, 300), self._piece(1, 700, 300)])
        antes = (self.view.placed_pieces[0]["x"], self.view.placed_pieces[0]["y"])
        cx, cy = self.view.world_to_screen(350.0, 350.0)
        self.view.on_ctrl_shift_bump_start(DummyMouseEvent(cx, cy))
        self.view.on_ctrl_shift_bump_drag(DummyMouseEvent(cx + 80, cy))
        self.assertEqual(len(self.view.canvas.find_withtag("bump_rubber")), 1)
        self.view.on_canvas_escape()
        self.assertEqual(len(self.view.canvas.find_withtag("bump_rubber")), 0)
        self.assertEqual((self.view.placed_pieces[0]["x"], self.view.placed_pieces[0]["y"]), antes)
        self.assertFalse(self.view._bump_mode)

    def test_linha_elastica_criada_e_removida_sem_vazar(self):
        self._load([self._piece(0, 300, 300)])
        cx, cy = self.view.world_to_screen(350.0, 350.0)
        self.view.on_ctrl_shift_bump_start(DummyMouseEvent(cx, cy))
        self.view.on_ctrl_shift_bump_drag(DummyMouseEvent(cx + 50, cy + 50))
        self.assertEqual(len(self.view.canvas.find_withtag("bump_rubber")), 1)
        self.view.on_ctrl_shift_bump_end(DummyMouseEvent(cx + 50, cy + 50))
        self.assertEqual(len(self.view.canvas.find_withtag("bump_rubber")), 0)
        self.assertIsNone(self.view._bump_line_id)

    # ---------------- 5. contorno côncavo na diagonal ----------------
    def test_bump_diagonal_com_contorno_concavo_nao_penetra(self):
        self._load([self._piece(0, 100, 100, contour=CONCAVE),
                    self._piece(1, 500, 500, contour=CONCAVE)])
        self.view.bump_selection_vector(1, 1)
        self.assertEqual(self._collisions(), 0)

    # ---------------- 6. seleção múltipla em bloco ----------------
    def test_bump_selecao_multipla_preserva_formacao(self):
        p0 = self._piece(0, 100, 100)
        p1 = self._piece(1, 250, 100)
        p2 = self._piece(2, 700, 100)  # obstáculo
        self._load([p0, p1, p2], selected=(0, 1))
        antes = [(self.view.placed_pieces[0]["x"], self.view.placed_pieces[0]["y"]),
                 (self.view.placed_pieces[1]["x"], self.view.placed_pieces[1]["y"])]
        self.view.bump_selection_vector(1, 0)
        depois = [(self.view.placed_pieces[0]["x"], self.view.placed_pieces[0]["y"]),
                  (self.view.placed_pieces[1]["x"], self.view.placed_pieces[1]["y"])]
        delta0 = (depois[0][0] - antes[0][0], depois[0][1] - antes[0][1])
        delta1 = (depois[1][0] - antes[1][0], depois[1][1] - antes[1][1])
        self.assertAlmostEqual(delta0[0], delta1[0], places=6)
        self.assertAlmostEqual(delta0[1], delta1[1], places=6)
        self.assertGreater(delta0[0], 1.0)
        self.assertEqual(self._collisions(), 0)

    # ---------------- 8. peça já encostada ----------------
    def test_peca_ja_encostada_nao_move(self):
        # obstáculo imediatamente à direita, respeitando exatamente o gap
        self._load([self._piece(0, 100, 100), self._piece(1, 201, 100)])
        antes = self.view.placed_pieces[0]["x"]
        undo_antes = len(self.view.undo_stack)
        self.view.bump_selection_vector(1, 0)
        self.assertAlmostEqual(self.view.placed_pieces[0]["x"], antes, delta=0.06)
        self.assertEqual(len(self.view.undo_stack), undo_antes)

    # ---------------- 9. undo atômico ----------------
    def test_undo_atomico_desfaz_o_bump(self):
        self._load([self._piece(0, 100, 100), self._piece(1, 400, 100)])
        x_antes = self.view.placed_pieces[0]["x"]
        self.view.bump_selection_vector(1, 0)
        self.assertGreater(self.view.placed_pieces[0]["x"], x_antes)
        self.view.undo_action()
        self.assertAlmostEqual(self.view.placed_pieces[0]["x"], x_antes, places=6)

    # ---------------- 10. pan sem seleção continua ----------------
    def test_pan_com_botao_do_meio_sem_selecao_continua_funcionando(self):
        self._load([self._piece(0, 300, 300)], selected=())
        self.view.selected_indices = []
        self.view.selected_index = None
        cx, cy = self.view.world_to_screen(350.0, 350.0)
        before_x = self.view.placed_pieces[0]["x"]
        self.view.on_pan_start(DummyMouseEvent(cx, cy, num=2))
        self.assertTrue(getattr(self.view, "is_panning", False))
        self.view.on_pan_drag(DummyMouseEvent(cx + 40, cy + 20, num=2))
        self.view.on_pan_end(DummyMouseEvent(cx + 40, cy + 20, num=2))
        self.assertFalse(getattr(self.view, "is_panning", False))
        self.assertEqual(self.view.placed_pieces[0]["x"], before_x)


if __name__ == "__main__":
    unittest.main()
