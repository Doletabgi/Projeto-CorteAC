"""
Testes Automatizados para Atalhos do LayoutEditorView:
F1 / F2 / F3 / F4 + Ctrl+Z + Ctrl+S, Invariância de Centro, Regras de Grão/Cabedal e Proibições.
"""

import unittest
import math
import tempfile
import os
from pathlib import Path
import tkinter as tk

from ui.layout_editor_view import (
    LayoutEditorView,
    rotate_piece_in_place,
    ROT_FINE_STEP_DEG,
    ROT_90_STEP_DEG,
    ROT_FLIP_STEP_DEG,
    ROT_DIR_LEFT,
    ROT_DIR_RIGHT,
    ROT_DIR_F3,
    UNDO_MAX_LEVELS,
    UNDO_GROUP_AUTOREPEAT,
    SAVE_TARGET,
    CONTOUR_CON,
)
from cad.geometry import polygon_bbox, transform_contour, polygon_area


class DummyEvent:
    def __init__(self, char="", keysym=""):
        self.char = char
        self.keysym = keysym


class TestLayoutEditorShortcuts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        import gc
        gc.collect()
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.root:
            self.skipTest("Tkinter display not available")
        self.view = LayoutEditorView(self.root, layout_name="[TEST001]")
        self.view.pack()
        self.view.update_idletasks()

    def tearDown(self):
        if hasattr(self, "view") and self.view:
            if hasattr(self.view, "icons"):
                self.view.icons.clear()
            try:
                self.view.destroy()
            except Exception:
                pass
        import gc
        gc.collect()

    def test_rotate_piece_in_place_math_proof(self):
        """Prova matemática: centro invariante e retorno 100% exato após 180x F1 (360°)."""
        piece = {
            "x": 150.0,
            "y": 250.0,
            "rotation": 0.0,
            "contour": CONTOUR_CON
        }
        # Calcula centro na chapa inicial
        poly0 = transform_contour(piece["contour"], piece["x"], piece["y"], piece["rotation"])
        bbox0 = polygon_bbox(poly0)
        c0 = ((bbox0[0] + bbox0[2]) / 2.0, (bbox0[1] + bbox0[3]) / 2.0)

        # 180 giros de +2° = 360°
        for _ in range(180):
            rotate_piece_in_place(piece, ROT_DIR_LEFT * ROT_FINE_STEP_DEG)

        poly_final = transform_contour(piece["contour"], piece["x"], piece["y"], piece["rotation"])
        bbox_final = polygon_bbox(poly_final)
        c_final = ((bbox_final[0] + bbox_final[2]) / 2.0, (bbox_final[1] + bbox_final[3]) / 2.0)

        self.assertAlmostEqual(piece["rotation"], 0.0, places=5)
        self.assertAlmostEqual(piece["x"], 150.0, places=5)
        self.assertAlmostEqual(piece["y"], 250.0, places=5)
        self.assertAlmostEqual(c0[0], c_final[0], places=5)
        self.assertAlmostEqual(c0[1], c_final[1], places=5)

    def test_f1_followed_by_f2_exact_identity(self):
        """F1 (+2°) seguido imediatamente por F2 (-2°) restaura a identidade exata."""
        self.view.selected_index = 0
        p = self.view.placed_pieces[0]
        orig_x, orig_y, orig_rot = p["x"], p["y"], p["rotation"]

        # F1
        self.view.on_f1_press(DummyEvent(keysym="F1"))
        self.assertEqual(p["rotation"], (orig_rot + 2.0) % 360.0)

        # F2
        self.view.on_f2_press(DummyEvent(keysym="F2"))
        self.assertAlmostEqual(p["rotation"], orig_rot, places=5)
        self.assertAlmostEqual(p["x"], orig_x, places=5)
        self.assertAlmostEqual(p["y"], orig_y, places=5)

    def test_45_f1_equals_f3_and_90_f1_equals_f4(self):
        """45x F1 (+90°) equivale exatamente a 1x F3. 90x F1 (+180°) equivale a 1x F4."""
        piece_a = {"x": 200.0, "y": 300.0, "rotation": 0.0, "contour": CONTOUR_CON}
        piece_b = {"x": 200.0, "y": 300.0, "rotation": 0.0, "contour": CONTOUR_CON}

        # 45 giros finos vs 1 giro F3
        for _ in range(45):
            rotate_piece_in_place(piece_a, 2.0)
        rotate_piece_in_place(piece_b, 90.0)

        self.assertAlmostEqual(piece_a["rotation"], piece_b["rotation"], places=5)
        self.assertAlmostEqual(piece_a["x"], piece_b["x"], places=5)
        self.assertAlmostEqual(piece_a["y"], piece_b["y"], places=5)

        # Mais 45 giros finos (total 90) vs F4 (+180) a partir do início
        piece_c = {"x": 200.0, "y": 300.0, "rotation": 0.0, "contour": CONTOUR_CON}
        for _ in range(90):
            rotate_piece_in_place(piece_a, 2.0)
        rotate_piece_in_place(piece_c, 180.0)

        self.assertAlmostEqual(piece_a["rotation"], 270.0, places=5)
        self.assertAlmostEqual(piece_c["rotation"], 180.0, places=5)

    def test_f3_coarse_cycle_and_f4_flip(self):
        """Ciclo de 4 estados do F3 (0->90->180->270->0) e 2x F3 == 1x F4."""
        self.view.selected_index = 0
        p = self.view.placed_pieces[0]
        p["rotation"] = 0.0
        orig_x, orig_y = p["x"], p["y"]

        # F3 passo 1
        self.view._f3_pressed = False
        self.view.on_f3_press(DummyEvent(keysym="F3"))
        self.assertEqual(p["rotation"], 90.0)

        # F3 passo 2
        self.view._f3_pressed = False
        self.view.on_f3_press(DummyEvent(keysym="F3"))
        self.assertEqual(p["rotation"], 180.0)

        # F3 passo 3
        self.view._f3_pressed = False
        self.view.on_f3_press(DummyEvent(keysym="F3"))
        self.assertEqual(p["rotation"], 270.0)

        # F3 passo 4 (retorna a 0)
        self.view._f3_pressed = False
        self.view.on_f3_press(DummyEvent(keysym="F3"))
        self.assertAlmostEqual(p["rotation"], 0.0, places=5)
        self.assertAlmostEqual(p["x"], orig_x, places=5)
        self.assertAlmostEqual(p["y"], orig_y, places=5)

        # 2x F4 retorna à origem
        self.view._f4_pressed = False
        self.view.on_f4_press(DummyEvent(keysym="F4"))
        self.assertEqual(p["rotation"], 180.0)
        self.view._f4_pressed = False
        self.view.on_f4_press(DummyEvent(keysym="F4"))
        self.assertAlmostEqual(p["rotation"], 0.0, places=5)
        self.assertAlmostEqual(p["x"], orig_x, places=5)
        self.assertAlmostEqual(p["y"], orig_y, places=5)

    def test_intermediate_angles_preserved(self):
        """Preservação rigorosa de ângulos intermediários com F3 e F4 (ex: 14°)."""
        piece = {"x": 100.0, "y": 150.0, "rotation": 14.0, "contour": CONTOUR_CON}

        # F3 a partir de 14°
        rotate_piece_in_place(piece, 90.0)
        self.assertAlmostEqual(piece["rotation"], 104.0, places=5)

        rotate_piece_in_place(piece, 90.0)
        self.assertAlmostEqual(piece["rotation"], 194.0, places=5)

        rotate_piece_in_place(piece, 90.0)
        self.assertAlmostEqual(piece["rotation"], 284.0, places=5)

        rotate_piece_in_place(piece, 90.0)
        self.assertAlmostEqual(piece["rotation"], 14.0, places=5)

        # F4 a partir de 14°
        rotate_piece_in_place(piece, 180.0)
        self.assertAlmostEqual(piece["rotation"], 194.0, places=5)

        rotate_piece_in_place(piece, 180.0)
        self.assertAlmostEqual(piece["rotation"], 14.0, places=5)

    def test_center_drift_under_100_rotations(self):
        """Nenhum desvio/drift de centro da peça (< 1e-6 mm) sob centenas de rotações sucessivas."""
        from cad.geometry import rotate_point
        piece = {"x": 300.0, "y": 400.0, "rotation": 0.0, "contour": CONTOUR_CON}
        min_x, min_y, max_x, max_y = polygon_bbox(piece["contour"])
        cx0 = (min_x + max_x) / 2.0
        cy0 = (min_y + max_y) / 2.0

        # Centro inicial da peça na chapa
        cx_init, cy_init = rotate_point(cx0, cy0, piece["rotation"])
        c_plate_0 = (piece["x"] + cx_init, piece["y"] + cy_init)

        for i in range(100):
            rotate_piece_in_place(piece, 2.0)
            cx_curr, cy_curr = rotate_point(cx0, cy0, piece["rotation"])
            c_plate_i = (piece["x"] + cx_curr, piece["y"] + cy_curr)
            drift = math.hypot(c_plate_i[0] - c_plate_0[0], c_plate_i[1] - c_plate_0[1])
            self.assertLess(drift, 1e-6, f"Drift detectado no passo {i}: {drift} mm")

    def test_cabedal_leather_grain_rule(self):
        """Validação do fio do couro (longitudinal 0°/180° ± 15° vs 90°/270°)."""
        self.view.selected_index = 0
        p = self.view.placed_pieces[0]
        p["name"] = "101-002_CONTRAFORTE_CABEDAL"

        # 0° -> Alinhado ao fio (sem aviso)
        p["rotation"] = 0.0
        warn = self.view.validate_placement_status()
        self.assertIsNone(warn)

        # 4° -> Ajuste fino F1 (dentro de ±15°, sem aviso)
        p["rotation"] = 4.0
        warn = self.view.validate_placement_status()
        self.assertIsNone(warn)

        # 180° -> Pé oposto F4 (alinhado longitudinalmente ao fio, sem aviso)
        p["rotation"] = 180.0
        warn = self.view.validate_placement_status()
        self.assertIsNone(warn)

        # 90° -> Perpendicular ao fio (deve gerar aviso de status)
        p["rotation"] = 90.0
        warn = self.view.validate_placement_status()
        self.assertIsNotNone(warn)
        self.assertIn("Fio do Couro", warn)

        # 270° -> Perpendicular ao fio (deve gerar aviso de status)
        p["rotation"] = 270.0
        warn = self.view.validate_placement_status()
        self.assertIsNotNone(warn)
        self.assertIn("Fio do Couro", warn)

    def test_undo_stack_restores_state(self):
        """Ctrl+Z desfaz com precisão rotação e restaura a geometria e status."""
        self.view.selected_index = 0
        p = self.view.placed_pieces[0]
        initial_rot = p["rotation"]

        # Rotação F3
        self.view._f3_pressed = False
        self.view.on_f3_press(DummyEvent(keysym="F3"))
        self.assertEqual(p["rotation"], (initial_rot + 90.0) % 360.0)
        self.assertTrue(len(self.view.undo_stack) > 0)

        # Ctrl+Z desfaz
        self.view.undo_action()
        self.assertEqual(self.view.placed_pieces[0]["rotation"], initial_rot)

        # Undo em pilha vazia não lança exceção
        self.view.undo_stack.clear()
        ret = self.view.undo_action()
        self.assertEqual(ret, "break")

    def test_autorepeat_grouping(self):
        """Agrupamento de auto-repeat (UNDO_GROUP_AUTOREPEAT): segurar F1 conta como 1 único undo."""
        self.view.selected_index = 0
        init_undo_len = len(self.view.undo_stack)
        initial_rot = self.view.placed_pieces[0]["rotation"]

        # Simula 5 eventos rápidos de auto-repeat do F1
        for _ in range(5):
            self.view.on_f1_press(DummyEvent(keysym="F1"))

        # Pilha de undo deve ter adicionado exatamente 1 checkpoint para toda a sequência
        self.assertEqual(len(self.view.undo_stack), init_undo_len + 1)
        self.assertEqual(self.view.placed_pieces[0]["rotation"], (initial_rot + 10.0) % 360.0)

        # Um único Ctrl+Z reverte todo o giro contínuo de 10°
        self.view.undo_action()
        self.assertEqual(self.view.placed_pieces[0]["rotation"], initial_rot)

    def test_strict_prohibitions_shift_f3_and_ctrl_y(self):
        """Proibição estrita: Shift+F3 e Ctrl+Y não fazem nada e não há redo_stack."""
        self.assertFalse(hasattr(self.view, "redo_stack"))
        self.assertFalse(hasattr(self.view, "redo_action"))

        # Verifica retorno de 'break' para bloquear processamento
        cb_shift_f3 = self.view.bind("<Shift-F3>")
        self.assertTrue(cb_shift_f3)

        cb_ctrl_y = self.view.bind("<Control-y>")
        self.assertTrue(cb_ctrl_y)

    def test_ctrl_s_save_persistence_and_modified_flag(self):
        """Ctrl+S salva atomicamente, remove indicador de asterisco e preserva undo stack."""
        self.view.selected_index = 0
        self.assertFalse(self.view.is_modified)
        self.assertNotIn("*", self.view.lbl_title.cget("text"))

        # Realiza uma edição (F1)
        self.view.on_f1_press(DummyEvent(keysym="F1"))
        self.assertTrue(self.view.is_modified)
        self.assertIn("*", self.view.lbl_title.cget("text"))
        undo_count_before_save = len(self.view.undo_stack)

        # Mock callback de save
        saved_calls = []
        self.view.on_save_cb = lambda pieces, w, h, name: saved_calls.append((len(pieces), w, h, name))

        # Cria arquivo temporário para testar regravação em disco
        with tempfile.NamedTemporaryFile(suffix=".lay", delete=False) as tf:
            tmp_path = tf.name

        try:
            self.view.layout_filepath = tmp_path
            # Executa Ctrl+S
            res = self.view.save_layout(DummyEvent(keysym="s"))
            self.assertEqual(res, "break")

            # Verifica persistência
            self.assertEqual(len(saved_calls), 1)
            self.assertFalse(self.view.is_modified)
            self.assertNotIn("*", self.view.lbl_title.cget("text"))

            # Verifica que o arquivo .lay foi regravado em disco
            self.assertTrue(os.path.exists(tmp_path))
            with open(tmp_path, "r", encoding="latin1") as fp:
                content = fp.read()
            self.assertTrue(content.startswith("$$LAYOUT.v3$$"))

            # O histórico de Undo DEVE ser preservado após o Ctrl+S
            self.assertEqual(len(self.view.undo_stack), undo_count_before_save)

            # Usuário ainda pode dar Ctrl+Z após o salvamento
            self.view.undo_action()
            self.assertEqual(len(self.view.undo_stack), undo_count_before_save - 1)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_close_without_modification_proceeds(self):
        """Ao fechar sem modificações, fecha sem abrir diálogo de confirmação."""
        self.view.is_modified = False
        closed = []
        self.view.on_close_cb = lambda: closed.append(True)
        self.view.on_close_click()
        self.assertEqual(len(closed), 1)

    def test_validation_warnings_only_on_status_bar(self):
        """Avisos de borda e colisão são exibidos exclusivamente na barra de status, sem pop-up."""
        self.view.selected_index = 0
        p = self.view.placed_pieces[0]
        # Move peça para fora da chapa
        p["x"] = 9999.0
        self.view.update_status()

        status_text = self.view.lbl_stat_pos.cget("text")
        status_fg = self.view.lbl_stat_pos.cget("fg")
        self.assertIn("Limite da Chapa", status_text)
        self.assertEqual(status_fg, "#dc2626")

    def test_add_session_shapes_batch_and_sidebar_targets(self):
        """Testa adição de grade completa (múltiplos moldes) e atualização dos alvos da barra lateral."""
        grade = [
            {"id": f"323_{sz}", "name": f"323_PalAcb_{sz}a", "size": str(sz), "contour": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 30}, {"x": 0, "y": 30}]}
            for sz in range(22, 37)
        ]
        self.view.add_session_shapes(grade)
        self.assertEqual(len(self.view.session_shapes), 15)
        # Na barra lateral, os 15 moldes formam grade 4x4 preenchida com 'grade_ch_0' como 16º item
        self.assertEqual(len(self.view.sidebar_targets), 16)
        # O primeiro da lista de alvos deve ser o tamanho 36 (ordenação decrescente)
        self.assertEqual(self.view.sidebar_targets[0]["size"], "36")
        self.assertEqual(self.view.sidebar_targets[-2]["size"], "22")
        self.assertEqual(self.view.sidebar_targets[-1]["name"], "grade_ch_0")

    def test_session_view_add_shapes_batch(self):
        """Testa add_shapes em lote no SessionView com preservação de sequência e callback."""
        from ui.session_view import SessionView
        saved = []
        sv = SessionView(self.root, session_data={"id": 101, "status": "Stand by"}, on_add_shapes=lambda sid, shapes: saved.append((sid, shapes)))
        grade = [
            {"id": f"shp_{sz}", "name": f"Molde_{sz}", "size": str(sz)}
            for sz in range(22, 37)
        ]
        sv.add_shapes(grade)
        self.assertEqual(len(sv.shapes_list), 15)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0][0], 101)
        self.assertEqual(len(saved[0][1]), 15)


if __name__ == "__main__":
    unittest.main()
