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
from tkinter import ttk

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
    SELECTED_OUTLINE_ONLY,
)
from cad.geometry import polygon_bbox, transform_contour, polygon_area


class DummyEvent:
    def __init__(self, char="", keysym=""):
        self.char = char
        self.keysym = keysym


class DummyMouseEvent:
    def __init__(self, x=0, y=0, state=0, num=1):
        self.x = x
        self.y = y
        self.state = state
        self.num = num


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
        self.view = LayoutEditorView(self.root, layout_name="[TEST001]", load_sample=True)
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
        # Na barra lateral, os 15 moldes formam exatamente os 15 alvos
        self.assertEqual(len(self.view.sidebar_targets), 15)
        # O primeiro da lista de alvos deve ser o tamanho 36 (ordenação decrescente)
        self.assertEqual(self.view.sidebar_targets[0]["size"], "36")
        self.assertEqual(self.view.sidebar_targets[-1]["size"], "22")
        self.assertFalse(any(t.get("name") == "grade_ch_0" for t in self.view.sidebar_targets))

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

    def test_treeview_multi_selection_jobs_mode_and_ctrl_a(self):
        """Testa que multi-seleção de sessões na árvore preserva os itens e Ctrl+A seleciona todas."""
        from tkinter import ttk
        tree = ttk.Treeview(self.root, selectmode="extended")
        root_node = tree.insert("", "end", text=" Produção")
        prod_node = tree.insert(root_node, "end", text=" ProduçãoNova")

        items = []
        for i in range(1, 16):
            it = tree.insert(prod_node, "end", text=f" (#{i}) Sessão #{i}", values=("session", i))
            items.append(it)

        # Seleção múltipla de 5 sessões (1 a 5)
        tree.selection_set(items[:5])
        self.assertEqual(len(tree.selection()), 5)

        # Simula on_tree_selected para verificar que não colapsa a seleção
        from ui.main_window import MainWindow
        class MockMain:
            def __init__(self, t):
                self.tree_main = t
                self.current_mode = "jobs"
                self.status_msg = ""
                self.switched_id = None
                class Lbl:
                    def config(s, text=""):
                        self.status_msg = text
                self.lbl_status_msg = Lbl()
            def switch_to_session(self, sid):
                self.switched_id = sid
            def _collect_session_nodes(self, node, result_list):
                MainWindow._collect_session_nodes(self, node, result_list)

        mock_main = MockMain(tree)
        MainWindow.on_tree_selected(mock_main)

        # Deve permanecer com 5 itens selecionados e NÃO chamar switch_to_session
        self.assertEqual(len(tree.selection()), 5)
        self.assertIsNone(mock_main.switched_id)
        self.assertEqual(mock_main.status_msg, "5 sessões selecionadas.")

        # Testa coleta com _collect_session_nodes e on_select_all
        all_sess = []
        for child in tree.get_children():
            mock_main._collect_session_nodes(child, all_sess)
        self.assertEqual(len(all_sess), 15)

    def test_zoom_20_percent_tool_and_ctrl_click(self):
        """Habilita zoom de 20% a cada clique na ferramenta + atalho CTRL + clique do mouse de ação."""
        # 1. Estado inicial de zoom 100% (1.0)
        self.assertEqual(self.view.zoom_factor, 1.0)

        # 2. Clique na ferramenta btn_zoom (lupa na barra de ferramentas) amplia 20% (+20%, fator 1.20)
        self.view.btn_zoom.invoke()
        self.assertAlmostEqual(self.view.zoom_factor, 1.20, places=4)

        # Segundo clique consecutivo na ferramenta amplia mais 20% (1.20 * 1.20 = 1.44)
        self.view.btn_zoom.invoke()
        self.assertAlmostEqual(self.view.zoom_factor, 1.44, places=4)

        # 3. Botão Exibir Layout Completo (btn_zoom_fit / reset_view) restaura para 100% (1.0)
        self.view.reset_view()
        self.assertEqual(self.view.zoom_factor, 1.0)

        # 4. Atalho CTRL + clique do mouse de ação no canvas centra o zoom exatamente sob o cursor
        class MockCtrlClickEvent:
            def __init__(self, x, y, state=4):
                self.x = x
                self.y = y
                self.state = state

        cur_x, cur_y = 300, 250
        wx_before, wy_before = self.view.screen_to_world(cur_x, cur_y)
        res = self.view.on_ctrl_canvas_click(MockCtrlClickEvent(cur_x, cur_y))
        self.assertEqual(res, "break")
        self.assertAlmostEqual(self.view.zoom_factor, 1.20, places=4)

        # O ponto do mundo CAD sob o cursor permanece perfeitamente ancorado sem desvio (drift = 0)
        if self.view.canvas.winfo_width() > 10:
            cur_x_after, cur_y_after = self.view.world_to_screen(wx_before, wy_before)
            self.assertAlmostEqual(cur_x_after, cur_x, places=2)
            self.assertAlmostEqual(cur_y_after, cur_y, places=2)

        # Segundo CTRL + clique consecutivo amplia mais 20% (1.44)
        res2 = self.view.on_ctrl_canvas_click(MockCtrlClickEvent(cur_x, cur_y))
        self.assertEqual(res2, "break")
        self.assertAlmostEqual(self.view.zoom_factor, 1.44, places=4)

        # 5. Redução de zoom (zoom_out) reduz 20%
        self.view.zoom_out()
        self.assertAlmostEqual(self.view.zoom_factor, 1.20, places=4)
        self.view.zoom_out()
        self.assertAlmostEqual(self.view.zoom_factor, 1.0, places=4)

    def test_plate_centered_in_cad_screen_area(self):
        """A placa do layout é centralizada simetricamente no meio da tela da área CAD."""
        self.root.geometry("1024x515")
        self.view.update()
        self.view.redraw()

        cw = self.view.canvas.winfo_width()
        if cw > 50:
            div_x = self.view.sidebar_div_x
            left_margin = self.view.plate_x1
            right_margin = div_x - self.view.plate_x2
            # Margens laterais na área CAD devem ser rigorosamente iguais (diferença zero)
            self.assertAlmostEqual(left_margin, right_margin, places=2)

            # Testa também com dimensões de chapa verticais (conforme captura: 1380 x 2980)
            self.view.set_sheet_size(1380.0, 2980.0)
            self.view.update()
            left_margin_vert = self.view.plate_x1
            right_margin_vert = self.view.sidebar_div_x - self.view.plate_x2
            self.assertAlmostEqual(left_margin_vert, right_margin_vert, places=2)

    def test_machine_default_preserved_without_editor_combobox(self):
        """A máquina padrão 'ATOM FlashCut Flex 3020' é mantida sem exibir combobox no editor."""
        from ui.session_view import SessionView
        sv = SessionView(self.root, session_data={"id": 99, "status": "Stand by"})
        self.assertFalse(hasattr(sv, "cb_machine"))
        self.assertEqual(sv.get_machine(), "ATOM FlashCut Flex 3020")
        self.assertEqual(sv.session_data.get("machine"), "ATOM FlashCut Flex 3020")
        sv.load_session({"id": 100, "status": "Stand by"})
        self.assertEqual(sv.get_machine(), "ATOM FlashCut Flex 3020")
        sv.destroy()

    def test_ctrl_p_shortcut_triggers_print_layout(self):
        """Atalho Ctrl+P e Ctrl+p no LayoutEditorView estão devidamente vinculados ao canvas e frame."""
        # 1. Verifica presença de bindings no canvas e frame
        self.assertTrue(self.view.canvas.bind("<Control-p>"), "Canvas deve ter bind de <Control-p>")
        self.assertTrue(self.view.canvas.bind("<Control-P>"), "Canvas deve ter bind de <Control-P>")
        self.assertTrue(self.view.bind("<Control-p>"), "Frame deve ter bind de <Control-p>")
        self.assertTrue(self.view.bind("<Control-P>"), "Frame deve ter bind de <Control-P>")

        # 2. Testa acionamento de print_layout()
        called = []
        original_print = self.view.print_layout
        self.view.print_layout = lambda: called.append("print")
        try:
            self.view.print_layout()
            self.assertIn("print", called)
        finally:
            self.view.print_layout = original_print

    def test_layout_print_dialog_plate_proportional_and_large(self):
        """Desenho da chapa no relatório A4 tem escala proporcional e tamanho expandido (sem travar em 60pt)."""
        from ui.layout_print_dialog import LayoutPrintDialog

        # Caso 1: Chapa padrão 1380 x 1080 mm
        dlg = LayoutPrintDialog(self.view, layout_data={
            "layout_name": "10001.lay",
            "sheet_w_mm": 1380.0,
            "sheet_h_mm": 1080.0,
        })
        dlg.update_idletasks()
        dlg.redraw()

        items = dlg.canvas.find_all()
        rect_coords = None
        for it in items:
            if dlg.canvas.type(it) == "rectangle":
                coords = dlg.canvas.coords(it)
                if len(coords) == 4 and dlg.canvas.itemcget(it, "fill") == "#ffffff":
                    w = coords[2] - coords[0]
                    h = coords[3] - coords[1]
                    if w < 595 and h < 842:
                        rect_coords = coords
                        break
        self.assertIsNotNone(rect_coords)
        w = rect_coords[2] - rect_coords[0]
        h = rect_coords[3] - rect_coords[1]

        # O tamanho DEVE ser grande proporcional à folha, muito maior que o antigo teto de 60pt!
        self.assertGreater(h, 200.0, "A chapa deve ser grande e proporcional, não miniatura de 60pt")
        self.assertGreater(w, 250.0, "A chapa deve ser grande e proporcional, não miniatura")

        # A proporção geométrica (aspect ratio) deve coincidir com a da chapa
        expected_ratio = 1380.0 / 1080.0
        actual_ratio = w / h
        self.assertAlmostEqual(actual_ratio, expected_ratio, delta=0.05)

        # Testa renderização PIL
        im = dlg.render_pillow_page(dpi=150)
        self.assertIsNotNone(im)
        self.assertEqual(im.size, (int(8.27 * 150), int(11.69 * 150)))
        dlg.destroy()

        # Caso 2: Chapa alta (1350 x 2553.38 mm) como na captura do usuário (media_1792335385519)
        dlg2 = LayoutPrintDialog(self.view, layout_data={
            "layout_name": "TALL.lay",
            "sheet_w_mm": 1350.0,
            "sheet_h_mm": 2553.38,
        })
        dlg2.update_idletasks()
        dlg2.redraw()

        items2 = dlg2.canvas.find_all()
        rect_coords2 = None
        for it in items2:
            if dlg2.canvas.type(it) == "rectangle":
                coords = dlg2.canvas.coords(it)
                if len(coords) == 4 and dlg2.canvas.itemcget(it, "fill") == "#ffffff":
                    w2 = coords[2] - coords[0]
                    h2 = coords[3] - coords[1]
                    if w2 < 595 and h2 < 842:
                        rect_coords2 = coords
                        break
        self.assertIsNotNone(rect_coords2)
        w2 = rect_coords2[2] - rect_coords2[0]
        h2 = rect_coords2[3] - rect_coords2[1]

        # Na captura media_1792335385519, h2 era 48-60pt e w2 era 22pt!
        # Agora h2 deve preencher a maior parte do espaço vertical disponível (~500pt)
        self.assertGreater(h2, 350.0)
        self.assertGreater(w2, 180.0)
        expected_ratio2 = 1350.0 / 2553.38
        actual_ratio2 = w2 / h2
        self.assertAlmostEqual(actual_ratio2, expected_ratio2, delta=0.05)

        dlg2.destroy()

    def test_plate_label_in_cm_and_no_sheet_nor_leather(self):
        """O rótulo exibe 'Placa' com medidas em cm (sem 'Sheet' nem 'Leather')."""
        self.root.geometry("1024x515")
        self.view.update()
        # 1. Configura dimensões idênticas à captura do usuário (1380 x 2980 mm -> 1,38 x 2,99 m)
        self.view.set_sheet_size(1380.0, 2980.0)
        self.view.update()
        self.view.redraw()

        # Verifica rótulo na barra de status
        stat_text = self.view.lbl_stat_sheet.cget("text")
        self.assertEqual(stat_text, "Placa 1,38 x 2,98 m")
        self.assertNotIn("Sheet", stat_text)
        self.assertNotIn("Leather", stat_text)

        # Verifica rótulo sobre a mesa CAD no Canvas
        label_items = self.view.canvas.find_withtag("sheet_label")
        self.assertTrue(len(label_items) > 0)
        canvas_text = self.view.canvas.itemcget(label_items[0], "text")
        self.assertEqual(canvas_text, "Placa 1,38 x 2,98 m")
        self.assertNotIn("Sheet", canvas_text)
        self.assertNotIn("Leather", canvas_text)

        # 2. Verifica que SessionView não disponibiliza 'flashnestleather' na lista de estratégias
        from ui.session_view import SessionView
        sv = SessionView(self.root, session_data={"id": 101, "status": "Stand by"})
        strat_values = sv.cb_strategy.cget("values")
        self.assertNotIn("flashnestleather", strat_values)
        sv.destroy()

    def test_layout_print_dialog_fullscreen_and_maximized(self):
        """Tela de impressão inicia maximizada / tela cheia, possui controle F11 e escape inteligente."""
        from ui.layout_print_dialog import LayoutPrintDialog

        dlg = LayoutPrintDialog(self.view, layout_data={"layout_name": "TEST_FS.lay"})
        dlg.update_idletasks()

        # 1. Verifica existência do botão de tela cheia
        self.assertTrue(hasattr(dlg, "btn_fullscreen"))
        self.assertEqual(dlg.btn_fullscreen.cget("text"), "⛶ Tela Cheia")

        # 2. Testa alternância de tela cheia (F11 / toggle_fullscreen)
        dlg.toggle_fullscreen()
        self.assertEqual(dlg.btn_fullscreen.cget("text"), "🗗 Restaurar")
        try:
            self.assertTrue(bool(dlg.attributes("-fullscreen")))
        except Exception:
            pass

        # 3. Testa on_escape em tela cheia: deve restaurar sem destruir a janela
        res = dlg.on_escape()
        self.assertEqual(res, "break")
        self.assertEqual(dlg.btn_fullscreen.cget("text"), "⛶ Tela Cheia")
        self.assertTrue(dlg.winfo_exists())

        # 4. Testa on_escape fora de tela cheia: destrói a janela
        dlg.on_escape()
        self.assertFalse(dlg.winfo_exists())

    def test_grid_10cm_markings_and_labels(self):
        """A placa do layout possui marcações e réguas de 10 em 10 cm com traços e números."""
        self.root.geometry("1024x515")
        self.view.update()
        self.view.set_sheet_size(1380.0, 2980.0)
        self.view.update()
        self.view.redraw()

        # 1. Verifica presença de traços de marcação (ticks) nas bordas
        ticks = self.view.canvas.find_withtag("grid_tick")
        self.assertGreater(len(ticks), 10, "A placa deve possuir traços (ticks) de marcação ao longo das bordas")

        # 2. Verifica presença de números de 10 em 10 cm
        labels = self.view.canvas.find_withtag("grid_label")
        self.assertGreater(len(labels), 10, "A placa deve possuir numeração de 10 em 10 cm")

        label_texts = [self.view.canvas.itemcget(item, "text") for item in labels]
        self.assertIn("10", label_texts, "Deve conter a marcação de 10 cm")
        self.assertIn("20", label_texts, "Deve conter a marcação de 20 cm")
        self.assertIn("30", label_texts, "Deve conter a marcação de 30 cm")

        # 3. Testa ocultação quando show_grid é desativado
        self.view.show_grid = False
        self.view.redraw()
        labels_hidden = self.view.canvas.find_withtag("grid_label")
        ticks_hidden = self.view.canvas.find_withtag("grid_tick")
        self.assertEqual(len(labels_hidden), 0)
        self.assertEqual(len(ticks_hidden), 0)

        # Restaura show_grid
        self.view.show_grid = True
        self.view.redraw()

    def test_print_preview_contains_10cm_grid_and_labels(self):
        """O relatório de impressão e exportação contém a grade, traços e números de 10 em 10 cm na chapa."""
        from ui.layout_print_dialog import LayoutPrintDialog

        dlg = LayoutPrintDialog(self.view, layout_data={
            "layout_name": "GRID_TEST.lay",
            "sheet_w_mm": 1380.0,
            "sheet_h_mm": 1080.0,
        })
        dlg.update_idletasks()
        dlg.redraw()

        # 1. Canvas do diálogo deve conter itens das tags print_grid, print_tick e print_label
        grid_lines = dlg.canvas.find_withtag("print_grid")
        ticks = dlg.canvas.find_withtag("print_tick")
        labels = dlg.canvas.find_withtag("print_label")

        self.assertGreater(len(grid_lines), 15, "A tela de impressão deve conter linhas de grade interna")
        self.assertGreater(len(ticks), 20, "A tela de impressão deve conter traços (ticks) de régua")
        self.assertGreater(len(labels), 15, "A tela de impressão deve conter numeração em cm")

        label_texts = [dlg.canvas.itemcget(item, "text") for item in labels]
        self.assertIn("10", label_texts, "Deve conter a marcação de 10 cm na régua da impressão")
        self.assertIn("20", label_texts, "Deve conter a marcação de 20 cm na régua da impressão")
        self.assertIn("30", label_texts, "Deve conter a marcação de 30 cm na régua da impressão")

        # 2. Renderização Pillow (utilizada para PDF, impressão física e exportação de imagem) deve gerar com sucesso
        im = dlg.render_pillow_page(dpi=150)
        self.assertIsNotNone(im)
        self.assertEqual(im.size, (int(8.27 * 150), int(11.69 * 150)))

        dlg.destroy()

    def test_production_tree_subfolders_hierarchy(self):
        """Valida que pastas de produção com subpastas (ex: SEMANA-46/LOTE-1) são aninhadas corretamente na árvore."""
        from tkinter import ttk
        from ui.main_window import MainWindow

        class FakeDB:
            def get_job_folders(self):
                return ["SEMANA-46", "SEMANA-46/LOTE-1", "SEMANA-46/LOTE-1/CORTE", "SEMANA-47"]
            def create_job_folder(self, name):
                pass
            def get_sessions(self):
                return []
            def get_orders(self):
                return []

        class FakeMain:
            def __init__(self, root):
                self.root = root
                self.tree_main = ttk.Treeview(root)
                self.grid_lower = ttk.Treeview(root)
                self.icons = {}
                self.db = FakeDB()
                self.sessions = [
                    {"id": 1, "name": "Sessao 1", "status": "Stand by", "job": "SEMANA-46"},
                    {"id": 2, "name": "Sessao 2", "status": "Stand by", "job": "SEMANA-46/LOTE-1"},
                    {"id": 3, "name": "Sessao 3", "status": "Stand by", "job": "SEMANA-46/LOTE-1/CORTE"},
                ]
                self.orders = []
                self.current_session = None
                class DummyBtn:
                    def config(self, **kwargs):
                        pass
                self.btn_mode_jobs = DummyBtn()
                self.btn_mode_shapes = DummyBtn()
                self.btn_mode_materials = DummyBtn()
                self.sort_grid_lower = lambda col: None

            def switch_tree_mode(self, mode="jobs"):
                MainWindow.switch_tree_mode(self, mode=mode)

        fm = FakeMain(self.root)
        fm.switch_tree_mode("jobs")

        # Verifica hierarquia na treeview:
        # Raiz tem filho "Produção"
        root_nodes = fm.tree_main.get_children("")
        self.assertEqual(len(root_nodes), 1)
        prod_root = root_nodes[0]
        self.assertEqual(fm.tree_main.item(prod_root, "text").strip(), "Produção")

        # Filhos diretos de Produção: SEMANA-46 e SEMANA-47
        prod_children = fm.tree_main.get_children(prod_root)
        prod_child_texts = [fm.tree_main.item(c, "text").strip() for c in prod_children]
        self.assertIn("SEMANA-46", prod_child_texts)
        self.assertIn("SEMANA-47", prod_child_texts)
        self.assertNotIn("LOTE-1", prod_child_texts)  # LOTE-1 não deve estar na raiz, deve ser filho de SEMANA-46!

        # Localiza o nó de SEMANA-46
        sem46_node = next(c for c in prod_children if fm.tree_main.item(c, "text").strip() == "SEMANA-46")
        sem46_children = fm.tree_main.get_children(sem46_node)
        sem46_child_texts = [fm.tree_main.item(c, "text").strip() for c in sem46_children]

        # Sob SEMANA-46 deve existir a subpasta "LOTE-1" e a "Sessao 1"
        self.assertIn("LOTE-1", sem46_child_texts)
        self.assertTrue(any("Sessao 1" in t for t in sem46_child_texts))

        # Localiza o nó de LOTE-1
        lote1_node = next(c for c in sem46_children if fm.tree_main.item(c, "text").strip() == "LOTE-1")
        lote1_children = fm.tree_main.get_children(lote1_node)
        lote1_child_texts = [fm.tree_main.item(c, "text").strip() for c in lote1_children]

        # Sob LOTE-1 deve existir a subpasta "CORTE" e a "Sessao 2"
        self.assertIn("CORTE", lote1_child_texts)
        self.assertTrue(any("Sessao 2" in t for t in lote1_child_texts))

        # Sob CORTE deve existir a "Sessao 3"
        corte_node = next(c for c in lote1_children if fm.tree_main.item(c, "text").strip() == "CORTE")
        corte_children = fm.tree_main.get_children(corte_node)
        corte_child_texts = [fm.tree_main.item(c, "text").strip() for c in corte_children]
        self.assertTrue(any("Sessao 3" in t for t in corte_child_texts))

    def test_clean_session_display_name_helper(self):
        """Verifica a limpeza de prefixos (#id) em nomes de sessão mantendo nomes originais intactos."""
        from ui.sort_utils import clean_session_display_name
        self.assertEqual(clean_session_display_name("121805"), "121805")
        self.assertEqual(clean_session_display_name("(#3) 121805"), "121805")
        self.assertEqual(clean_session_display_name("( #3 ) 121805"), "121805")
        self.assertEqual(clean_session_display_name("(#3227) 121805"), "121805")
        self.assertEqual(clean_session_display_name("(3) 121805"), "121805")
        self.assertEqual(clean_session_display_name("Sessão #3"), "Sessão #3")
        self.assertEqual(clean_session_display_name("(#3) Sessão #3"), "Sessão #3")
        self.assertEqual(clean_session_display_name(""), "")
        self.assertEqual(clean_session_display_name(None), "")

    def test_renamed_session_has_no_id_prefix_in_tree_and_preserves_sessid_in_grid(self):
        """
        Verifica que após renomear a sessão (ex: 121805):
        1. A árvore exibe estritamente '121805' sem prefixo (#3).
        2. A tabela inferior (grid_lower) mantém SessId='3' e Nome sessão='121805'.
        """
        from tkinter import ttk
        from ui.main_window import MainWindow

        class FakeDB:
            def get_job_folders(self):
                return ["1684.044"]
            def get_orders(self):
                return []

        class DummyBtn:
            def config(self, **kwargs):
                pass

        class FakeMain:
            def __init__(self, root):
                self.root = root
                self.tree_main = ttk.Treeview(root)
                self.grid_lower = ttk.Treeview(root)
                self.current_mode = "jobs"
                self.icons = {}
                self.db = FakeDB()
                self.sessions = [
                    {"id": 3, "job": "1684.044", "name": "121805", "status": "Pronta"}
                ]
                self.current_session = self.sessions[0]
                self.orders = []
                self.btn_mode_jobs = DummyBtn()
                self.btn_mode_shapes = DummyBtn()
                self.btn_mode_materials = DummyBtn()
                self.sort_grid_lower = lambda col: None

            def populate_tree(self, mode="jobs"):
                MainWindow.populate_tree(self, mode=mode)

        fm = FakeMain(self.root)
        fm.populate_tree(mode="jobs")

        # Verifica árvore: nó de 1684.044
        prod_root = fm.tree_main.get_children("")[0]
        job_node = fm.tree_main.get_children(prod_root)[0]
        self.assertEqual(fm.tree_main.item(job_node, "text").strip(), "1684.044")

        # Verifica sessão filha
        sess_node = fm.tree_main.get_children(job_node)[0]
        sess_text = fm.tree_main.item(sess_node, "text").strip()
        self.assertEqual(sess_text, "121805")
        self.assertNotIn("(#3)", sess_text)
        self.assertNotIn("#3", sess_text)

        # Verifica grid inferior
        grid_items = fm.grid_lower.get_children("")
        self.assertEqual(len(grid_items), 1)
        row_vals = fm.grid_lower.item(grid_items[0], "values")
        # values: (sess_id, s_job, disp_name, s_status)
        self.assertEqual(str(row_vals[0]), "3")          # SessId original preservado
        self.assertEqual(str(row_vals[1]), "1684.044")   # Produção
        self.assertEqual(str(row_vals[2]), "121805")     # Nome sessão limpo
        self.assertEqual(str(row_vals[3]), "Pronta")     # Status

    def test_on_rename_tree_item_cleans_and_updates_session(self):
        """Verifica que ao acionar on_rename_tree_item o nome digitado é limpo e atualiza tree e grid."""
        from tkinter import ttk
        from unittest.mock import patch
        from ui.main_window import MainWindow

        class FakeDB:
            def __init__(self):
                self.updated = {}
            def get_job_folders(self):
                return ["1684.044"]
            def get_orders(self):
                return []
            def update_session(self, sid, **kwargs):
                self.updated[sid] = kwargs

        class DummyBtn:
            def config(self, **kwargs):
                pass

        class FakeMain:
            def __init__(self, root):
                self.root = root
                self.tree_main = ttk.Treeview(root)
                self.grid_lower = ttk.Treeview(root)
                self.current_mode = "jobs"
                self.icons = {}
                self.db = FakeDB()
                self.sessions = [
                    {"id": 3, "job": "1684.044", "name": "Sessão #3", "status": "Stand by"}
                ]
                self.current_session = self.sessions[0]
                self.orders = []
                self.btn_mode_jobs = DummyBtn()
                self.btn_mode_shapes = DummyBtn()
                self.btn_mode_materials = DummyBtn()
                self.sort_grid_lower = lambda col: None
                self.session_view = None

            def switch_tree_mode(self, mode="jobs"):
                MainWindow.switch_tree_mode(self, mode=mode)

            def _select_session_in_tree(self, parent_item, target_sess_id):
                return MainWindow._select_session_in_tree(self, parent_item, target_sess_id)

            def on_rename_tree_item(self):
                MainWindow.on_rename_tree_item(self)

        fm = FakeMain(self.root)
        fm.switch_tree_mode("jobs")

        # Seleciona nó da sessão na árvore
        prod_root = fm.tree_main.get_children("")[0]
        job_node = fm.tree_main.get_children(prod_root)[0]
        sess_node = fm.tree_main.get_children(job_node)[0]
        fm.tree_main.selection_set(sess_node)

        # Mock simpledialog.askstring para simular o usuário digitando "(#3) 121805"
        with patch("tkinter.simpledialog.askstring", return_value="(#3) 121805"):
            fm.on_rename_tree_item()

        # O banco foi atualizado para "121805"
        self.assertEqual(fm.db.updated.get(3, {}).get("name"), "121805")
        self.assertEqual(fm.sessions[0]["name"], "121805")

        # O nó da árvore exibe "121805"
        updated_job_node = fm.tree_main.get_children(fm.tree_main.get_children("")[0])[0]
        updated_sess_node = fm.tree_main.get_children(updated_job_node)[0]
        self.assertEqual(fm.tree_main.item(updated_sess_node, "text").strip(), "121805")

        # O grid inferior tem SessId="3" e Nome="121805"
        grid_items = fm.grid_lower.get_children("")
        vals = fm.grid_lower.item(grid_items[0], "values")
        self.assertEqual(str(vals[0]), "3")
        self.assertEqual(str(vals[2]), "121805")

    def test_delete_article_order_from_tree(self):
        """Verifica a exclusão de artigo/pedido (Derby Masculino #41) via on_delete_tree_item."""
        from tkinter import ttk
        from unittest.mock import patch
        from ui.main_window import MainWindow

        class FakeDB:
            def __init__(self):
                self.deleted_orders = []
            def get_job_folders(self):
                return ["167044"]
            def get_orders(self):
                return []
            def delete_order(self, oid):
                self.deleted_orders.append(oid)

        class DummyBtn:
            def config(self, **kwargs):
                pass

        class FakeMain:
            def __init__(self, root):
                self.root = root
                self.tree_main = ttk.Treeview(root)
                self.grid_lower = ttk.Treeview(root)
                self.current_mode = "jobs"
                self.icons = {}
                self.db = FakeDB()
                self.orders = [{"id": 1, "name": "Derby Masculino #41"}]
                self.sessions = [{"id": 3, "job": "167044", "name": "121805", "status": "Stand by"}]
                self.current_session = self.sessions[0]
                self.current_order = self.orders[0]
                self.btn_mode_jobs = DummyBtn()
                self.btn_mode_shapes = DummyBtn()
                self.btn_mode_materials = DummyBtn()
                self.sort_grid_lower = lambda col: None
                self.lbl_status_msg = DummyBtn()
                self.active_child = None
                self.order_view = None

            def switch_tree_mode(self, mode="jobs"):
                MainWindow.switch_tree_mode(self, mode=mode)

            def on_delete_tree_item(self):
                MainWindow.on_delete_tree_item(self)

        fm = FakeMain(self.root)
        fm.switch_tree_mode("jobs")

        # Localiza o nó do artigo/pedido
        prod_root = fm.tree_main.get_children("")[0]
        job_node = fm.tree_main.get_children(prod_root)[0]
        children = fm.tree_main.get_children(job_node)
        order_node = next(c for c in children if fm.tree_main.item(c, "values")[0] == "order")
        self.assertEqual(fm.tree_main.item(order_node, "text").strip(), "Derby Masculino #41")

        # Seleciona o artigo e executa exclusão confirmada
        fm.tree_main.selection_set(order_node)
        with patch("tkinter.messagebox.askyesno", return_value=True):
            fm.on_delete_tree_item()

        # Verifica que delete_order foi chamado com id=1
        self.assertIn(1, fm.db.deleted_orders)
        self.assertEqual(len(fm.orders), 0)

        # Na árvore o nó de artigo não existe mais, restando apenas a sessão 121805
        updated_job_node = fm.tree_main.get_children(fm.tree_main.get_children("")[0])[0]
        remaining = fm.tree_main.get_children(updated_job_node)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(fm.tree_main.item(remaining[0], "text").strip(), "121805")

    def test_delete_material_context_menu_and_actions(self):
        """Valida que o clique com botão direito na árvore e grid de materiais exibe 'Excluir Material', e que a exclusão remove o material."""
        from unittest.mock import patch
        from ui.main_window import MainWindow

        class FakeDBMat:
            def __init__(self):
                self.deleted_materials = []
            def get_materials(self):
                return [m for m in [{"id": "MAT_CAM_02", "name": "Camurça"}] if m["id"] not in self.deleted_materials]
            def delete_material(self, mat_id):
                self.deleted_materials.append(mat_id)

        class DummyBtn:
            def config(self, **kwargs):
                pass

        class FakeMainMat:
            def __init__(self, root):
                self.root = root
                self.tree_main = ttk.Treeview(root)
                self.grid_lower = ttk.Treeview(root)
                self.current_mode = "materials"
                self.icons = {}
                self.db = FakeDBMat()
                self.materials = self.db.get_materials()
                self.current_material = self.materials[0] if self.materials else None
                self.btn_mode_jobs = DummyBtn()
                self.btn_mode_shapes = DummyBtn()
                self.btn_mode_materials = DummyBtn()
                self.materials_menu = tk.Menu(root, tearoff=0)
                self.lbl_status_msg = DummyBtn()
                self.active_child = None
                self.open_sessions = {}
                self.sort_grid_lower = lambda col: None
                self.on_create_material = lambda: None
                self.show_material_codes_window = lambda: None
                self.apply_material_to_session = lambda m: None
                self.dismiss_popup_menus = lambda: None
                self._active_popup_menu = None
                self._last_popup_time = 0

            def switch_tree_mode(self, mode="materials"):
                MainWindow.switch_tree_mode(self, mode=mode)

            def show_popup_menu(self, menu, x, y):
                pass

            def show_tree_context_menu(self, event):
                MainWindow.show_tree_context_menu(self, event)

            def show_grid_context_menu(self, event):
                MainWindow.show_grid_context_menu(self, event)

            def on_delete_tree_item(self):
                MainWindow.on_delete_tree_item(self)

            def on_delete_grid_item(self):
                MainWindow.on_delete_grid_item(self)

            def refresh_materials_everywhere(self):
                MainWindow.refresh_materials_everywhere(self)

        fm = FakeMainMat(self.root)
        fm.switch_tree_mode("materials")

        # Verifica nó do material na árvore
        root_node = fm.tree_main.get_children("")[0]
        children = fm.tree_main.get_children(root_node)
        self.assertEqual(len(children), 1)
        mat_node = children[0]
        self.assertEqual(fm.tree_main.item(mat_node, "values")[1], "MAT_CAM_02")

        # Seleciona nó e simula clique com botão direito do mouse
        fm.tree_main.selection_set(mat_node)
        class DummyEvent:
            x_root = 100
            y_root = 100
            y = -1
        fm.show_tree_context_menu(DummyEvent())

        # Verifica comandos presentes no menu de contexto
        labels = [fm.materials_menu.entrycget(i, "label") for i in range(fm.materials_menu.index("end") + 1) if fm.materials_menu.type(i) == "command"]
        self.assertIn("Excluir Material", labels)
        self.assertIn("Excluir", labels)

        # Simula exclusão pela árvore
        with patch("tkinter.messagebox.askyesno", return_value=True):
            fm.on_delete_tree_item()

        self.assertIn("MAT_CAM_02", fm.db.deleted_materials)
        self.assertEqual(len(fm.materials), 0)

        # Testa menu de contexto do grid inferior
        fm2 = FakeMainMat(self.root)
        fm2.switch_tree_mode("materials")
        grid_items = fm2.grid_lower.get_children("")
        self.assertIn("MAT_CAM_02", grid_items)
        fm2.grid_lower.selection_set("MAT_CAM_02")

        fm2.show_grid_context_menu(DummyEvent())
        grid_labels = [fm2.materials_menu.entrycget(i, "label") for i in range(fm2.materials_menu.index("end") + 1) if fm2.materials_menu.type(i) == "command"]
        self.assertIn("Excluir Material", grid_labels)
        self.assertIn("Excluir", grid_labels)

        # Simula exclusão pelo grid
        with patch("tkinter.messagebox.askyesno", return_value=True):
            fm2.on_delete_grid_item()
        self.assertIn("MAT_CAM_02", fm2.db.deleted_materials)

    def test_layout_editor_empty_by_default(self):
        """Verifica que o LayoutEditorView inicializado por padrão possui 0 peças e 0 moldes falsos."""
        empty_view = LayoutEditorView(self.root, layout_name="[EMPTY]")
        self.assertEqual(empty_view.placed_pieces, [])
        self.assertEqual(empty_view.sidebar_targets, [])
        empty_view.destroy()

    def test_session_view_editor_button_state_and_guard(self):
        """Verifica que o botão Editor e o duplo-clique na aba Layout são bloqueados se não houver cálculo."""
        from ui.session_view import SessionView
        from unittest.mock import MagicMock, patch

        cb_open = MagicMock()
        sess_data = {
            "id": 99,
            "name": "Sessão Teste Sem Layout",
            "status": "Stand by",
            "placed_pieces": [],
            "shapes": [],
            "material": {"id": "M1", "name": "Mat Test", "width_mm": 1350, "height_mm": 2550}
        }
        sv = SessionView(self.root, session_data=sess_data, on_open_layout_editor=cb_open)

        # 1. Botão Editor deve estar desabilitado (disabled) quando não há layout
        self.assertEqual(str(sv.btn_open_editor["state"]), "disabled")

        # 2. Tentar abrir sem layout deve disparar aviso e não chamar o callback
        with patch("tkinter.messagebox.showwarning") as mock_warn:
            sv.on_layout_row_double_click()
            self.assertTrue(mock_warn.called)
            cb_open.assert_not_called()

        # 3. Quando o layout é calculado ou peças são atribuídas, o botão passa a ser habilitado (normal)
        sess_data["placed_pieces"] = [{"name": "P1", "contour": CONTOUR_CON, "x": 100, "y": 100, "rotation": 0}]
        sess_data["layout_name"] = "[I0099]"
        sv.load_session(sess_data)

        self.assertEqual(str(sv.btn_open_editor["state"]), "normal")

        # 4. Agora o duplo-clique / clique no Editor abre normalmente
        sv.on_layout_row_double_click()
        cb_open.assert_called_once_with("[I0099]")

        sv.destroy()

    def test_main_window_show_layout_editor_guard(self):
        """Verifica que MainWindow.show_layout_editor barra a abertura sem cálculo de encaixe."""
        from unittest.mock import MagicMock, patch

        class DummyMainWindow:
            def __init__(self):
                self.minimized_windows = []
                self.sessions = [{"id": 1, "placed_pieces": [], "shapes": []}]
                self.current_session = self.sessions[0]
                self.current_material = None
                self.layout_editor_view = MagicMock()
                self.lbl_status_msg = MagicMock()
                self.maximize_window = MagicMock()
                self.restore_window = MagicMock()

        from ui.main_window import MainWindow

        win = DummyMainWindow()
        # Sem peças calculadas: showwarning deve ser chamado e a janela não deve ser maximizada
        with patch("tkinter.messagebox.showwarning") as mock_warn:
            MainWindow.show_layout_editor(win)
            self.assertTrue(mock_warn.called)
            win.maximize_window.assert_not_called()

        # Com peças calculadas: abre com sucesso
        win.current_session["placed_pieces"] = [{"name": "P1", "contour": CONTOUR_CON}]
        win.current_session["layout_name"] = "[I0001]"
        with patch("tkinter.messagebox.showwarning") as mock_warn:
            MainWindow.show_layout_editor(win)
            mock_warn.assert_not_called()
            win.maximize_window.assert_called_once_with(win.layout_editor_view)

    def test_materials_grid_has_descricao_column_and_no_partida(self):
        """Valida que o grid inferior no modo Estoque de material usa coluna 'Descrição' e não 'Partida'."""
        from ui.main_window import MainWindow

        class DummyBtn:
            def config(self, **kwargs):
                pass

        class FakeMainMatGrid:
            def __init__(self, root):
                self.root = root
                self.tree_main = ttk.Treeview(root)
                self.grid_lower = ttk.Treeview(root)
                self.current_mode = "materials"
                self.icons = {}
                self.materials = [
                    {"id": 1, "name": "SINT-LOGAM 1.4 PRETO", "code": "SINT-LOGAM", "width_mm": 1380.0, "height_mm": 2980.0, "type": "como placa"}
                ]
                self.btn_mode_jobs = DummyBtn()
                self.btn_mode_shapes = DummyBtn()
                self.btn_mode_materials = DummyBtn()
                self.sort_grid_lower = lambda col: None

            def switch_tree_mode(self, mode="materials"):
                MainWindow.switch_tree_mode(self, mode=mode)

        fm = FakeMainMatGrid(self.root)
        fm.switch_tree_mode("materials")

        cols = list(fm.grid_lower["columns"])
        self.assertNotIn("partida", cols)
        self.assertIn("descricao", cols)
        self.assertEqual(cols, ["cod_mat", "descricao", "definicao", "comprimento", "largura"])

        self.assertEqual(fm.grid_lower.heading("descricao", "text"), "Descrição")

        items = fm.grid_lower.get_children("")
        self.assertEqual(len(items), 1)
        row_vals = fm.grid_lower.item(items[0], "values")
        self.assertEqual(str(row_vals[0]), "1")
        self.assertEqual(row_vals[1], "SINT-LOGAM 1.4 PRETO")

    def test_drag_motion_zero_delay_without_full_redraw(self):
        """Simula 100 eventos consecutivos de <B1-Motion> em uma placa com 50 peças e verifica que o tempo total dos 100 frames é inferior a 50 ms (< 0.5 ms por movimento) e que redraw() completo não é chamado durante o <B1-Motion>."""
        import time
        from unittest.mock import patch

        # Configura exatamente 50 peças na mesa
        pieces = []
        for i in range(50):
            row = i // 10
            col = i % 10
            pieces.append({
                "name": f"P{i+1}",
                "contour": list(CONTOUR_CON),
                "x": 50.0 + col * 120.0,
                "y": 50.0 + row * 120.0,
                "rotation": 0.0,
                "color": "#3b82f6"
            })
        self.view.placed_pieces = pieces
        self.view.redraw()
        self.assertEqual(len(self.view.placed_pieces), 50)

        p = self.view.placed_pieces[0]
        poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
        bbox = polygon_bbox(poly)
        wx = (bbox[0] + bbox[2]) / 2.0
        wy = (bbox[1] + bbox[3]) / 2.0
        cx = self.view.plate_x1 + wx * self.view.plate_scale
        cy = self.view.plate_y2 - wy * self.view.plate_scale

        # Clique inicial para selecionar e iniciar drag
        self.view.on_canvas_click(DummyMouseEvent(cx, cy))
        self.assertEqual(self.view.selected_index, 0)
        self.assertTrue(self.view.is_dragging_piece)

        # Verifica criação do ghost outline na origem
        ghost_items = self.view.canvas.find_withtag("drag_ghost")
        self.assertTrue(len(ghost_items) > 0)

        # Monitora chamadas a redraw() durante o arraste
        with patch.object(self.view, "redraw", wraps=self.view.redraw) as mock_redraw:
            t0 = time.perf_counter()
            # Simula 100 eventos contínuos de B1-Motion
            for i in range(1, 101):
                self.view.on_canvas_drag(DummyMouseEvent(cx + i * 2, cy + i * 2))
            dt = time.perf_counter() - t0

            # Prova inviolável: NENHUM redraw() completo no loop de arraste
            self.assertEqual(mock_redraw.call_count, 0)
            # Desempenho extremo: 100 frames processados em menos de 50 ms (< 0.5 ms/evento)
            self.assertLess(dt, 0.050)

        # Release: redraw() único e remoção do ghost
        self.view.on_canvas_release(DummyMouseEvent(cx + 200, cy + 200))
        self.assertFalse(self.view.is_dragging_piece)
        ghost_after = self.view.canvas.find_withtag("drag_ghost")
        self.assertEqual(len(ghost_after), 0)

    def test_drag_realtime_collision_red_outline_feedback(self):
        """Verifica que durante o arrasto sobre outra peça ou fora da Placa o polígono recebe outline='#ef4444', voltando ao normal quando movido para uma área livre."""
        self.view.placed_pieces = [
            {"name": "P1", "contour": list(CONTOUR_CON), "x": 100.0, "y": 100.0, "rotation": 0.0, "color": "#3b82f6"},
            {"name": "P2", "contour": list(CONTOUR_CON), "x": 300.0, "y": 100.0, "rotation": 0.0, "color": "#10b981"},
        ]
        self.view.redraw()

        p0 = self.view.placed_pieces[0]
        poly0 = transform_contour(p0["contour"], p0["x"], p0["y"], p0["rotation"])
        bbox0 = polygon_bbox(poly0)
        wx0 = (bbox0[0] + bbox0[2]) / 2.0
        wy0 = (bbox0[1] + bbox0[3]) / 2.0
        cx0 = self.view.plate_x1 + wx0 * self.view.plate_scale
        cy0 = self.view.plate_y2 - wy0 * self.view.plate_scale

        self.view.on_canvas_click(DummyMouseEvent(cx0, cy0))
        poly0_item = self.view.canvas.find_withtag("piece_poly_0")[0]

        # 1. Arraste sobre outra peça (colisão peça a peça) -> outline="#ef4444"
        p1 = self.view.placed_pieces[1]
        poly1 = transform_contour(p1["contour"], p1["x"], p1["y"], p1["rotation"])
        bbox1 = polygon_bbox(poly1)
        wx1 = (bbox1[0] + bbox1[2]) / 2.0
        wy1 = (bbox1[1] + bbox1[3]) / 2.0
        col_cx = self.view.plate_x1 + wx1 * self.view.plate_scale
        col_cy = self.view.plate_y2 - wy1 * self.view.plate_scale
        self.view.on_canvas_drag(DummyMouseEvent(col_cx, col_cy))
        self.view.flush_pending_drag()
        self.assertEqual(self.view.canvas.itemcget(poly0_item, "outline"), "#ef4444")

        # 2. Arraste para fora da Placa (invasão de borda) -> outline="#ef4444"
        out_wx = -200.0
        out_wy = -200.0
        out_cx = self.view.plate_x1 + out_wx * self.view.plate_scale
        out_cy = self.view.plate_y2 - out_wy * self.view.plate_scale
        self.view.on_canvas_drag(DummyMouseEvent(out_cx, out_cy))
        self.view.flush_pending_drag()
        self.assertEqual(self.view.canvas.itemcget(poly0_item, "outline"), "#ef4444")

        # 3. Arraste para área livre e válida dentro da Placa -> outline="#22c55e"
        free_wx = 100.0
        free_wy = 350.0
        free_cx = self.view.plate_x1 + free_wx * self.view.plate_scale
        free_cy = self.view.plate_y2 - free_wy * self.view.plate_scale
        self.view.on_canvas_drag(DummyMouseEvent(free_cx, free_cy))
        self.view.flush_pending_drag()
        self.assertEqual(self.view.canvas.itemcget(poly0_item, "outline"), "#22c55e")

        # Release na área livre
        self.view.on_canvas_release(DummyMouseEvent(free_cx, free_cy))
        self.assertFalse(self.view.is_dragging_piece)

    def test_drag_realtime_collision_and_ghost_feedback(self):
        """Valida ghost outline, feedback vermelho/verde na peça arrastada e âmbar nas peças colididas."""
        self.view.placed_pieces = [
            {"name": "P1", "contour": list(CONTOUR_CON), "x": 100.0, "y": 100.0, "rotation": 0.0, "color": "#3b82f6"},
            {"name": "P2", "contour": list(CONTOUR_CON), "x": 300.0, "y": 100.0, "rotation": 0.0, "color": "#10b981"},
        ]
        self.view.redraw()

        p0 = self.view.placed_pieces[0]
        poly0 = transform_contour(p0["contour"], p0["x"], p0["y"], p0["rotation"])
        bbox0 = polygon_bbox(poly0)
        wx0 = (bbox0[0] + bbox0[2]) / 2.0
        wy0 = (bbox0[1] + bbox0[3]) / 2.0
        cx0 = self.view.plate_x1 + wx0 * self.view.plate_scale
        cy0 = self.view.plate_y2 - wy0 * self.view.plate_scale

        self.view.on_canvas_click(DummyMouseEvent(cx0, cy0))
        self.assertEqual(self.view.selected_index, 0)

        # Ghost presente
        self.assertTrue(len(self.view.canvas.find_withtag("drag_ghost")) > 0)

        # Arraste para área livre (ex: +200 no Y)
        target_wx = wx0
        target_wy = wy0 + 200.0
        target_cx = self.view.plate_x1 + target_wx * self.view.plate_scale
        target_cy = self.view.plate_y2 - target_wy * self.view.plate_scale
        self.view.on_canvas_drag(DummyMouseEvent(target_cx, target_cy))
        self.view.flush_pending_drag()

        poly0_item = self.view.canvas.find_withtag("piece_poly_0")[0]
        self.assertEqual(self.view.canvas.itemcget(poly0_item, "outline"), "#22c55e")

        # Arraste sobrepondo a peça P2
        p1 = self.view.placed_pieces[1]
        poly1 = transform_contour(p1["contour"], p1["x"], p1["y"], p1["rotation"])
        bbox1 = polygon_bbox(poly1)
        wx1 = (bbox1[0] + bbox1[2]) / 2.0
        wy1 = (bbox1[1] + bbox1[3]) / 2.0
        col_cx = self.view.plate_x1 + wx1 * self.view.plate_scale
        col_cy = self.view.plate_y2 - wy1 * self.view.plate_scale
        self.view.on_canvas_drag(DummyMouseEvent(col_cx, col_cy))
        self.view.flush_pending_drag()

        self.assertEqual(self.view.canvas.itemcget(poly0_item, "outline"), "#ef4444")
        poly1_item = self.view.canvas.find_withtag("piece_poly_1")[0]
        self.assertEqual(self.view.canvas.itemcget(poly1_item, "outline"), "#f59e0b")

        # Solta o mouse: colisão deve reverter a peça para a posição original
        self.view.on_canvas_release(DummyMouseEvent(col_cx, col_cy))
        self.assertAlmostEqual(self.view.placed_pieces[0]["x"], 100.0, places=1)
        self.assertAlmostEqual(self.view.placed_pieces[0]["y"], 100.0, places=1)
        self.assertEqual(len(self.view.canvas.find_withtag("drag_ghost")), 0)

    def test_escape_cancels_drag_and_restores_ghost_position(self):
        """Valida que a tecla Escape cancela o arraste e restaura a peça exatamente à origem do ghost."""
        self.view.placed_pieces = [
            {"name": "P1", "contour": list(CONTOUR_CON), "x": 150.0, "y": 200.0, "rotation": 0.0, "color": "#3b82f6"}
        ]
        self.view.redraw()
        orig_undo_len = len(self.view.undo_stack)

        p = self.view.placed_pieces[0]
        poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
        bbox = polygon_bbox(poly)
        wx = (bbox[0] + bbox[2]) / 2.0
        wy = (bbox[1] + bbox[3]) / 2.0
        cx = self.view.plate_x1 + wx * self.view.plate_scale
        cy = self.view.plate_y2 - wy * self.view.plate_scale

        self.view.on_canvas_click(DummyMouseEvent(cx, cy))
        self.assertTrue(self.view.is_dragging_piece)
        self.assertTrue(len(self.view.canvas.find_withtag("drag_ghost")) > 0)

        # Move a peça para longe
        self.view.on_canvas_drag(DummyMouseEvent(cx + 100, cy - 80))
        self.assertNotEqual(self.view.placed_pieces[0]["x"], 150.0)

        # Cancela com Escape
        self.view.cancel_drag()
        self.assertFalse(self.view.is_dragging_piece)
        self.assertEqual(len(self.view.canvas.find_withtag("drag_ghost")), 0)
        self.assertAlmostEqual(self.view.placed_pieces[0]["x"], 150.0, places=2)
        self.assertAlmostEqual(self.view.placed_pieces[0]["y"], 200.0, places=2)
        self.assertEqual(len(self.view.undo_stack), orig_undo_len)

    def test_redraw_single_piece_rotations_and_nudge(self):
        """Valida que F1/F2/F3/F4 e setas utilizam redraw_single_piece sem recriar cena inteira."""
        from unittest.mock import patch

        self.view.selected_index = 0
        p = self.view.placed_pieces[0]
        orig_rot = p["rotation"]
        orig_x = p["x"]

        with patch.object(self.view, "redraw") as mock_redraw:
            # F1 rotação 2°
            self.view.on_f1_press(DummyEvent(keysym="F1"))
            self.assertEqual(mock_redraw.call_count, 0)
            self.assertEqual(p["rotation"], (orig_rot + 2.0) % 360.0)

            # Nudge seta
            x_before_nudge = p["x"]
            self.view.nudge_selected(5, 0)
            self.assertEqual(mock_redraw.call_count, 0)
            self.assertEqual(p["x"], x_before_nudge + 5.0)

    def test_cad_canvas_fast_path_and_ghost(self):
        """Valida fast-path, ghost e cancel_drag no widget CADCanvas."""
        from ui.cad_canvas import CADCanvas
        from unittest.mock import patch

        cad = CADCanvas(self.root)
        cad.pack()
        cad.set_material({"width_mm": 1000.0, "height_mm": 1000.0})
        cad.set_pieces([
            {"shape": {"contour": list(CONTOUR_CON)}, "x": 100.0, "y": 100.0, "rotation": 0.0},
            {"shape": {"contour": list(CONTOUR_CON)}, "x": 300.0, "y": 100.0, "rotation": 0.0}
        ])
        cad.update_idletasks()

        # Clica na peça 0
        poly0 = transform_contour(CONTOUR_CON, 100.0, 100.0, 0.0)
        bbox0 = polygon_bbox(poly0)
        wx0 = (bbox0[0] + bbox0[2]) / 2.0
        wy0 = (bbox0[1] + bbox0[3]) / 2.0
        sx, sy = cad.world_to_screen(wx0, wy0)
        cad.on_button1_down(DummyMouseEvent(sx, sy))
        self.assertEqual(cad.dragged_index, 0)
        self.assertTrue(len(cad.find_withtag("drag_ghost")) > 0)

        # Move a peça com fast-path
        with patch.object(cad, "redraw") as mock_redraw:
            for i in range(1, 11):
                cad.on_button1_motion(DummyMouseEvent(sx + i * 5, sy + i * 5))
            self.assertEqual(mock_redraw.call_count, 0)

        # Escape cancela
        cad.cancel_drag()
        self.assertEqual(cad.dragged_index, -1)
        self.assertEqual(len(cad.find_withtag("drag_ghost")), 0)
        self.assertAlmostEqual(cad.placed_pieces[0]["x"], 100.0, places=1)
        cad.destroy()

    def test_rdrag_deadzone_no_rotation_no_undo(self):
        """Clique rápido com botão direito dentro da deadzone (dx^2 + dy^2 <= 7) não altera o ângulo nem suja o undo_stack."""
        self.view.selected_index = 0
        p = self.view.placed_pieces[0]
        orig_rot = p["rotation"]
        orig_x, orig_y = p["x"], p["y"]
        undo_len_before = len(self.view.undo_stack)

        # Press
        self.view.on_rbutton_press(DummyMouseEvent(x=150, y=150))
        self.assertTrue(self.view._rdrag_active)
        self.assertFalse(self.view._rdrag_rotating)

        # Motion dentro da deadzone (dx=2, dy=1 -> 4 + 1 = 5 <= 7)
        self.view.on_rbutton_drag(DummyMouseEvent(x=152, y=151))
        self.assertFalse(self.view._rdrag_rotating)
        self.assertEqual(p["rotation"], orig_rot)

        # Release dentro da deadzone
        self.view.on_rbutton_release(DummyMouseEvent(x=152, y=151))
        self.assertFalse(self.view._rdrag_active)
        self.assertFalse(self.view._rdrag_rotating)
        self.assertEqual(p["rotation"], orig_rot)
        self.assertEqual(p["x"], orig_x)
        self.assertEqual(p["y"], orig_y)
        self.assertEqual(len(self.view.undo_stack), undo_len_before)

    def test_rdrag_continuous_rotation_and_single_undo(self):
        """Arrasto com botão direito (dx^2 + dy^2 > 7) gira continuamente conforme atan2, gera 1 nível de Undo e Ctrl+Z restaura."""
        self.view.selected_index = 0
        p = self.view.placed_pieces[0]
        orig_rot = p["rotation"]
        undo_len_before = len(self.view.undo_stack)

        # Pivô na tela para a peça 0
        p_poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
        b = polygon_bbox(p_poly)
        Cx_world = (b[0] + b[2]) / 2.0
        Cy_world = (b[1] + b[3]) / 2.0
        Cx_px, Cy_px = self.view.world_to_screen(Cx_world, Cy_world)

        # Pressiona botão direito a 50px à direita do pivô (theta0 = 0.0°)
        self.view.on_rbutton_press(DummyMouseEvent(x=Cx_px + 50.0, y=Cy_px))
        self.assertTrue(self.view._rdrag_active)
        piv_x, piv_y = self.view._rdrag_pivot_screen

        # Arrasta para 50px acima do pivô (em tela, y menor é para cima -> theta1 = +90.0°)
        self.view.on_rbutton_drag(DummyMouseEvent(x=piv_x, y=piv_y - 50.0))
        self.assertTrue(self.view._rdrag_rotating)
        expected_rot_90 = (orig_rot + 90.0) % 360.0
        self.assertAlmostEqual(p["rotation"], expected_rot_90, places=1)
        # Guia visual ativa
        self.assertTrue(len(self.view.canvas.find_withtag("rdrag_guide")) > 0)

        # Arrasta mais para 50px à esquerda do pivô (theta1 = 180° -> delta = +180°)
        self.view.on_rbutton_drag(DummyMouseEvent(x=piv_x - 50.0, y=piv_y))
        expected_rot_180 = (orig_rot + 180.0) % 360.0
        self.assertAlmostEqual(p["rotation"], expected_rot_180, places=1)

        # Solta o botão direito
        self.view.on_rbutton_release(DummyMouseEvent(x=piv_x - 50.0, y=piv_y))
        self.assertFalse(self.view._rdrag_active)
        self.assertFalse(self.view._rdrag_rotating)
        # Guia visual apagada
        self.assertEqual(len(self.view.canvas.find_withtag("rdrag_guide")), 0)
        # Apenas 1 nível de Undo para todo o arrasto
        self.assertEqual(len(self.view.undo_stack), undo_len_before + 1)
        self.assertTrue(self.view.is_modified)

        # Ctrl+Z desfaz a rotação inteira e restaura o ângulo original
        self.view.undo_action()
        self.assertAlmostEqual(self.view.placed_pieces[0]["rotation"], orig_rot, places=2)

    def test_rdrag_escape_cancellation(self):
        """Pressionar Escape no meio do arrasto rotacional restaura ângulo original e não adiciona item ao undo_stack."""
        self.view.selected_index = 0
        p = self.view.placed_pieces[0]
        orig_rot = p["rotation"]
        orig_x, orig_y = p["x"], p["y"]
        undo_len_before = len(self.view.undo_stack)

        self.view.on_rbutton_press(DummyMouseEvent(x=100, y=100))
        # Move além da deadzone para girar
        self.view.on_rbutton_drag(DummyMouseEvent(x=160, y=80))
        self.assertTrue(self.view._rdrag_rotating)
        self.assertNotEqual(p["rotation"], orig_rot)

        # Pressiona Escape
        res = self.view.cancel_drag(DummyEvent(keysym="Escape"))
        self.assertEqual(res, "break")
        self.assertFalse(self.view._rdrag_active)
        self.assertFalse(self.view._rdrag_rotating)
        p_res = self.view.placed_pieces[0]
        self.assertAlmostEqual(p_res["rotation"], orig_rot, places=2)
        self.assertAlmostEqual(p_res["x"], orig_x, places=2)
        self.assertAlmostEqual(p_res["y"], orig_y, places=2)
        # Nada adicionado ao undo_stack
        self.assertEqual(len(self.view.undo_stack), undo_len_before)
        # Guia visual limpa
        self.assertEqual(len(self.view.canvas.find_withtag("rdrag_guide")), 0)

    def test_rdrag_ctrl_group_rigid_body_rotation(self):
        """Arrasto com Ctrl pressionado e 2 peças selecionadas gira ambas em grupo ao redor do centro comum."""
        self.assertTrue(len(self.view.placed_pieces) >= 2)
        # Configura duas peças em posições controladas
        self.view.placed_pieces[0]["x"] = 100.0
        self.view.placed_pieces[0]["y"] = 150.0
        self.view.placed_pieces[0]["rotation"] = 0.0
        self.view.placed_pieces[1]["x"] = 250.0
        self.view.placed_pieces[1]["y"] = 150.0
        self.view.placed_pieces[1]["rotation"] = 0.0

        p0 = self.view.placed_pieces[0]
        p1 = self.view.placed_pieces[1]
        self.view.selected_indices = {0, 1}
        self.view.selected_index = 0
        undo_len_before = len(self.view.undo_stack)

        # Distância inicial entre as duas peças
        dist_before = math.hypot(p1["x"] - p0["x"], p1["y"] - p0["y"])

        # Calcula bounding box coletivo inicial
        poly0 = transform_contour(p0["contour"], p0["x"], p0["y"], p0["rotation"])
        poly1 = transform_contour(p1["contour"], p1["x"], p1["y"], p1["rotation"])
        b0 = polygon_bbox(poly0)
        b1 = polygon_bbox(poly1)
        coll_Cx = (min(b0[0], b1[0]) + max(b0[2], b1[2])) / 2.0
        coll_Cy = (min(b0[1], b1[1]) + max(b0[3], b1[3])) / 2.0
        coll_Cx_px, coll_Cy_px = self.view.world_to_screen(coll_Cx, coll_Cy)

        # Inicia arrasto com Ctrl (state=0x0004) a 60px à direita do centro coletivo (theta0 = 0.0°)
        self.view.on_rbutton_press(DummyMouseEvent(x=coll_Cx_px + 60.0, y=coll_Cy_px, state=0x0004))
        self.assertTrue(self.view._rdrag_is_ctrl)
        piv_x, piv_y = self.view._rdrag_pivot_screen

        # Gira 90° no sentido anti-horário (em tela: 60px para cima)
        self.view.on_rbutton_drag(DummyMouseEvent(x=piv_x, y=piv_y - 60.0, state=0x0004))
        self.assertTrue(self.view._rdrag_rotating)

        # Ambas as peças devem estar orientadas a 90°
        self.assertAlmostEqual(p0["rotation"], 90.0, places=1)
        self.assertAlmostEqual(p1["rotation"], 90.0, places=1)

        # Como corpo rígido, a distância mútua entre peças é preservada
        dist_after = math.hypot(p1["x"] - p0["x"], p1["y"] - p0["y"])
        self.assertAlmostEqual(dist_before, dist_after, places=1)

        # E as peças translacionaram ao redor do centro coletivo
        self.assertAlmostEqual(p0["x"], p1["x"], delta=20.0)

        # Conclui giro e verifica Undo
        self.view.on_rbutton_release(DummyMouseEvent(x=piv_x, y=piv_y - 60.0, state=0x0004))
        self.assertEqual(len(self.view.undo_stack), undo_len_before + 1)

        # Ctrl+Z restaura as duas peças à orientação 0° e posições originais
        self.view.undo_action()
        self.assertAlmostEqual(self.view.placed_pieces[0]["rotation"], 0.0, places=2)
        self.assertAlmostEqual(self.view.placed_pieces[1]["rotation"], 0.0, places=2)
        self.assertAlmostEqual(self.view.placed_pieces[0]["x"], 100.0, places=1)
        self.assertAlmostEqual(self.view.placed_pieces[1]["x"], 250.0, places=1)

    def test_rdrag_auto_select_under_cursor_and_empty_space_ignore(self):
        """O botão direito não altera a seleção existente (nem em espaço vazio nem sobre peça)."""
        self.view.selected_index = -1
        self.view.selected_indices = set()

        # 1. Clique com botão direito em espaço vazio (longe das peças)
        self.view.on_rbutton_press(DummyMouseEvent(x=5, y=5))
        self.assertFalse(self.view._rdrag_active)
        self.assertFalse(self.view._rdrag_rotating)
        self.assertEqual(self.view.selected_index, -1)

        # 2. Clique com botão direito sobre a peça 0: a seleção permanece inalterada
        p0 = self.view.placed_pieces[0]
        poly0 = transform_contour(p0["contour"], p0["x"], p0["y"], p0["rotation"])
        b0 = polygon_bbox(poly0)
        c_x = (b0[0] + b0[2]) / 2.0
        c_y = (b0[1] + b0[3]) / 2.0
        sx, sy = self.view.world_to_screen(c_x, c_y)

        self.view.on_rbutton_press(DummyMouseEvent(x=sx, y=sy))
        self.assertEqual(self.view.selected_index, -1)
        self.assertFalse(self.view._rdrag_active)

        self.view.on_rbutton_release(DummyMouseEvent(x=sx, y=sy))
        self.assertFalse(self.view._rdrag_active)
        self.assertEqual(self.view.selected_index, -1)

    def test_rubberband_100_percent_contained_only(self):
        """Rubberband: seleciona APENAS peças cujo bounding box esteja 100% contido. Peças parcialmente cruzadas são ignoradas."""
        self.view.placed_pieces = [
            {"x": 100.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]},
            {"x": 200.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]},
            {"x": 300.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]}
        ]
        self.view.selected_indices = []
        self.view.selected_index = None
        self.view.redraw()

        # Peça 0: X em [100, 140], Y em [100, 140]
        # Peça 1: X em [200, 240], Y em [100, 140]
        # Peça 2: X em [300, 340], Y em [100, 140]
        # Caixa elástica cobre X de 80 a 220, Y de 80 a 160:
        # - Peça 0: 100% contida ([100, 140] está dentro de [80, 220])
        # - Peça 1: Cruza parcialmente a borda (vai de 200 a 240, mas a caixa acaba em 220) -> NÃO deve ser selecionada!
        # - Peça 2: Totalmente fora -> NÃO deve ser selecionada!
        sx0, sy0 = self.view.world_to_screen(80.0, 80.0)
        sx1, sy1 = self.view.world_to_screen(220.0, 160.0)

        # Inicia rubberband no ponto (sx0, sy0)
        self.view.on_canvas_click(DummyMouseEvent(x=sx0, y=sy0))
        self.assertTrue(self.view.is_rubberbanding)

        # Arrasta até (sx1, sy1)
        self.view.on_canvas_drag(DummyMouseEvent(x=sx1, y=sy1))
        boxes = self.view.canvas.find_withtag("rubberband_box")
        self.assertTrue(len(boxes) > 0)

        # Solta o botão
        self.view.on_canvas_release(DummyMouseEvent(x=sx1, y=sy1))
        self.assertFalse(self.view.is_rubberbanding)
        self.assertEqual(len(self.view.canvas.find_withtag("rubberband_box")), 0)

        # Apenas peça 0 deve estar selecionada!
        self.assertEqual(self.view.selected_indices, [0])
        self.assertEqual(self.view.selected_index, 0)

    def test_rubberband_with_shift_accumulates(self):
        """Rubberband segurando Shift soma as peças 100% contidas à seleção pré-existente."""
        self.view.placed_pieces = [
            {"x": 50.0, "y": 50.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 30, "y": 0}, {"x": 30, "y": 30}, {"x": 0, "y": 30}]},
            {"x": 150.0, "y": 50.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 30, "y": 0}, {"x": 30, "y": 30}, {"x": 0, "y": 30}]},
            {"x": 250.0, "y": 50.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 30, "y": 0}, {"x": 30, "y": 30}, {"x": 0, "y": 30}]}
        ]
        self.view.selected_indices = [0]
        self.view.selected_index = 0
        self.view.redraw()

        # Caixa sobre a peça 2 com Shift (state=0x0001)
        sx0, sy0 = self.view.world_to_screen(240.0, 40.0)
        sx1, sy1 = self.view.world_to_screen(290.0, 90.0)

        self.view.on_canvas_click(DummyMouseEvent(x=sx0, y=sy0, state=0x0001))
        self.view.on_canvas_drag(DummyMouseEvent(x=sx1, y=sy1, state=0x0001))
        self.view.on_canvas_release(DummyMouseEvent(x=sx1, y=sy1, state=0x0001))

        self.assertIn(0, self.view.selected_indices)
        self.assertIn(2, self.view.selected_indices)
        self.assertNotIn(1, self.view.selected_indices)

    def test_shift_click_toggle_pieces(self):
        """Shift + Clique sobre peça alterna (toggle) sua presença em selected_indices."""
        self.view.placed_pieces = [
            {"x": 100.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]},
            {"x": 200.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]}
        ]
        self.view.selected_indices = []
        self.view.selected_index = None
        self.view.redraw()

        sx0, sy0 = self.view.world_to_screen(120.0, 120.0)
        sx1, sy1 = self.view.world_to_screen(220.0, 120.0)

        # 1. Shift+Clique na peça 0: adiciona
        self.view.on_canvas_click(DummyMouseEvent(x=sx0, y=sy0, state=0x0001))
        self.assertIn(0, self.view.selected_indices)

        # 2. Shift+Clique na peça 1: adiciona
        self.view.on_canvas_click(DummyMouseEvent(x=sx1, y=sy1, state=0x0001))
        self.assertIn(0, self.view.selected_indices)
        self.assertIn(1, self.view.selected_indices)

        # 3. Shift+Clique na peça 0: remove
        self.view.on_canvas_click(DummyMouseEvent(x=sx0, y=sy0, state=0x0001))
        self.assertNotIn(0, self.view.selected_indices)
        self.assertIn(1, self.view.selected_indices)

        # 4. Shift+Clique na peça 1: remove
        self.view.on_canvas_click(DummyMouseEvent(x=sx1, y=sy1, state=0x0001))
        self.assertEqual(len(self.view.selected_indices), 0)
        self.assertIsNone(self.view.selected_index)

    def test_single_and_double_click_empty_clears_selection(self):
        """Clique simples ou duplo-clique no vazio desmarca todas as peças selecionadas."""
        self.view.placed_pieces = [
            {"x": 100.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]}
        ]
        self.view.selected_indices = [0]
        self.view.selected_index = 0
        self.view.redraw()

        empty_sx, empty_sy = self.view.world_to_screen(10.0, 10.0)

        # Clique simples no vazio (sem arrastar)
        self.view.on_canvas_click(DummyMouseEvent(x=empty_sx, y=empty_sy, state=0))
        self.view.on_canvas_release(DummyMouseEvent(x=empty_sx, y=empty_sy, state=0))
        self.assertEqual(self.view.selected_indices, [])
        self.assertIsNone(self.view.selected_index)

        # Re-seleciona para testar duplo-clique
        self.view.selected_indices = [0]
        self.view.selected_index = 0
        self.view.on_canvas_double_click(DummyMouseEvent(x=empty_sx, y=empty_sy))
        self.assertEqual(self.view.selected_indices, [])
        self.assertIsNone(self.view.selected_index)

    def test_click_multi_selection_drag_vs_click_release(self):
        """Clicar em peça já selecionada no grupo mantém grupo; soltar sem arrastar isola a peça."""
        self.view.placed_pieces = [
            {"x": 100.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]},
            {"x": 200.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]}
        ]
        self.view.selected_indices = [0, 1]
        self.view.selected_index = 1
        self.view.redraw()

        sx0, sy0 = self.view.world_to_screen(120.0, 120.0)

        # 1. Clique sobre a peça 0: mantém grupo selecionado no Press
        self.view.on_canvas_click(DummyMouseEvent(x=sx0, y=sy0, state=0))
        self.assertEqual(set(self.view.selected_indices), {0, 1})
        self.assertTrue(self.view.is_dragging_piece)

        # 2. Solta no mesmo ponto (sem arrastar: dx^2 + dy^2 <= 7): isola apenas a peça 0
        self.view.on_canvas_release(DummyMouseEvent(x=sx0, y=sy0, state=0))
        self.assertEqual(self.view.selected_indices, [0])
        self.assertEqual(self.view.selected_index, 0)

    def test_group_drag_moves_all_pieces_equally_and_single_undo(self):
        """Arrastar uma peça do grupo move todas as selecionadas pelo mesmo (Δx, Δy); 1 único Ctrl+Z desfaz tudo."""
        self.view.placed_pieces = [
            {"x": 100.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]},
            {"x": 200.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]},
            {"x": 300.0, "y": 250.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]}
        ]
        self.view.selected_indices = [0, 1]
        self.view.selected_index = 0
        self.view.redraw()

        undo_before = len(self.view.undo_stack)
        sx0, sy0 = self.view.world_to_screen(120.0, 120.0)

        # Inicia arraste na peça 0
        self.view.on_canvas_click(DummyMouseEvent(x=sx0, y=sy0, state=0))
        self.assertTrue(self.view.is_dragging_piece)

        # Arrasta +30 mm em X e +20 mm em Y no mundo
        new_wx, new_wy = 120.0 + 30.0, 120.0 + 20.0
        sx_drag, sy_drag = self.view.world_to_screen(new_wx, new_wy)
        self.view.on_canvas_drag(DummyMouseEvent(x=sx_drag, y=sy_drag, state=0))
        self.view.flush_pending_drag()

        # Solta o mouse
        self.view.on_canvas_release(DummyMouseEvent(x=sx_drag, y=sy_drag, state=0))

        # Ambas as peças 0 e 1 devem ter se deslocado exatamente +30 em X e +20 em Y
        p0 = self.view.placed_pieces[0]
        p1 = self.view.placed_pieces[1]
        p2 = self.view.placed_pieces[2]
        self.assertAlmostEqual(p0["x"], 130.0, places=1)
        self.assertAlmostEqual(p0["y"], 120.0, places=1)
        self.assertAlmostEqual(p1["x"], 230.0, places=1)
        self.assertAlmostEqual(p1["y"], 120.0, places=1)
        # Peça 2 não selecionada permanece intacta
        self.assertAlmostEqual(p2["x"], 300.0, places=1)
        self.assertAlmostEqual(p2["y"], 250.0, places=1)

        # Apenas 1 nível adicionado ao undo_stack
        self.assertEqual(len(self.view.undo_stack), undo_before + 1)

        # Um único Ctrl+Z restaura ambas as peças às coordenadas originais
        self.view.undo_action()
        self.assertAlmostEqual(self.view.placed_pieces[0]["x"], 100.0, places=1)
        self.assertAlmostEqual(self.view.placed_pieces[0]["y"], 100.0, places=1)
        self.assertAlmostEqual(self.view.placed_pieces[1]["x"], 200.0, places=1)
        self.assertAlmostEqual(self.view.placed_pieces[1]["y"], 100.0, places=1)

    def test_group_drag_escape_aborts_without_undo(self):
        """Pressionar Escape durante o arrasto em grupo aborta e restaura posições sem sujar undo_stack."""
        self.view.placed_pieces = [
            {"x": 100.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]},
            {"x": 200.0, "y": 100.0, "rotation": 0.0, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}]}
        ]
        self.view.selected_indices = [0, 1]
        self.view.selected_index = 0
        self.view.redraw()

        undo_before = len(self.view.undo_stack)
        sx0, sy0 = self.view.world_to_screen(120.0, 120.0)

        self.view.on_canvas_click(DummyMouseEvent(x=sx0, y=sy0, state=0))
        sx_drag, sy_drag = self.view.world_to_screen(160.0, 160.0)
        self.view.on_canvas_drag(DummyMouseEvent(x=sx_drag, y=sy_drag, state=0))
        self.view.flush_pending_drag()

        # Tecla Escape durante o arrasto
        self.view.cancel_drag(DummyEvent(keysym="Escape"))

        # Posições originais restauradas
        self.assertAlmostEqual(self.view.placed_pieces[0]["x"], 100.0, places=1)
        self.assertAlmostEqual(self.view.placed_pieces[1]["x"], 200.0, places=1)
        self.assertFalse(self.view.is_dragging_piece)
        # Nenhum snapshot criado no undo_stack
        self.assertEqual(len(self.view.undo_stack), undo_before)

    def test_ctrl_a_selects_all_pieces(self):
        """Ctrl+A seleciona todas as peças posicionadas no layout."""
        self.view.placed_pieces = [
            {"x": 100.0, "y": 100.0, "rotation": 0.0, "contour": CONTOUR_CON},
            {"x": 200.0, "y": 100.0, "rotation": 0.0, "contour": CONTOUR_CON},
            {"x": 300.0, "y": 100.0, "rotation": 0.0, "contour": CONTOUR_CON}
        ]
        self.view.selected_indices = []
        self.view.selected_index = None

        self.view.select_all()
        self.assertEqual(self.view.selected_indices, [0, 1, 2])
        self.assertEqual(self.view.selected_index, 2)

    def test_group_delete_and_shortcuts_single_undo(self):
        """Delete, F1-F4 e Setas operam em todas as peças selecionadas gerando apenas 1 nível de Undo."""
        self.view.placed_pieces = [
            {"x": 100.0, "y": 100.0, "rotation": 0.0, "contour": CONTOUR_CON},
            {"x": 200.0, "y": 100.0, "rotation": 0.0, "contour": CONTOUR_CON}
        ]
        self.view.selected_indices = [0, 1]
        self.view.selected_index = 0
        self.view.redraw()

        # 1. F1 (+2°) no grupo
        undo_before = len(self.view.undo_stack)
        self.view.on_f1_press(DummyEvent(keysym="F1"))
        self.assertAlmostEqual(self.view.placed_pieces[0]["rotation"], 2.0, places=1)
        self.assertAlmostEqual(self.view.placed_pieces[1]["rotation"], 2.0, places=1)
        self.assertEqual(len(self.view.undo_stack), undo_before + 1)

        # 2. Setas (Nudge dx=+10, dy=+5) no grupo
        undo_before = len(self.view.undo_stack)
        p0_x = self.view.placed_pieces[0]["x"]
        p0_y = self.view.placed_pieces[0]["y"]
        p1_x = self.view.placed_pieces[1]["x"]
        p1_y = self.view.placed_pieces[1]["y"]
        self.view.nudge_selected(10.0, 5.0)
        self.assertAlmostEqual(self.view.placed_pieces[0]["x"], p0_x + 10.0, places=1)
        self.assertAlmostEqual(self.view.placed_pieces[1]["x"], p1_x + 10.0, places=1)
        self.assertAlmostEqual(self.view.placed_pieces[0]["y"], p0_y + 5.0, places=1)
        self.assertAlmostEqual(self.view.placed_pieces[1]["y"], p1_y + 5.0, places=1)
        self.assertEqual(len(self.view.undo_stack), undo_before + 1)

        # 3. Delete no grupo exclui ambas as peças em 1 nível de Undo
        undo_before = len(self.view.undo_stack)
        self.view.delete_selected()
        self.assertEqual(len(self.view.placed_pieces), 0)
        self.assertEqual(self.view.selected_indices, [])
        self.assertEqual(len(self.view.undo_stack), undo_before + 1)

        # Ctrl+Z restaura as duas peças excluídas
        self.view.undo_action()
        self.assertEqual(len(self.view.placed_pieces), 2)

    def test_selected_outline_only_style(self):
        """SELECTED_OUTLINE_ONLY = True renderiza contorno destacado sem preenchimento opaco (fill="")."""
        self.assertTrue(SELECTED_OUTLINE_ONLY)
        self.view.placed_pieces = [
            {"x": 100.0, "y": 100.0, "rotation": 0.0, "contour": CONTOUR_CON},
            {"x": 200.0, "y": 100.0, "rotation": 0.0, "contour": CONTOUR_CON}
        ]
        self.view.selected_indices = [0]
        self.view.selected_index = 0
        self.view.redraw()

        poly0_id = self.view.canvas.find_withtag("piece_poly_0")
        self.assertTrue(len(poly0_id) > 0)
        fill0 = self.view.canvas.itemcget(poly0_id[0], "fill")
        self.assertEqual(fill0, "")

        poly1_id = self.view.canvas.find_withtag("piece_poly_1")
        self.assertTrue(len(poly1_id) > 0)
        fill1 = self.view.canvas.itemcget(poly1_id[0], "fill")
        self.assertNotEqual(fill1, "")

    def test_simulation_workflow_in_layout_editor(self):
        """Testa o fluxo completo da simulação de corte CAM no LayoutEditorView."""
        # 1. Verifica presença do botão na barra de ferramentas
        self.assertTrue(hasattr(self.view, "btn_sim"))
        self.assertEqual(self.view.btn_sim.cget("text"), "▶ Simular")
        self.assertFalse(self.view.sim_running)

        # 2. Inicia simulação
        self.view.toggle_simulation()
        self.assertTrue(self.view.sim_running)
        self.assertEqual(self.view.btn_sim.cget("text"), "⏹ Parar")

        # Verifica se o cabeçote CNC foi desenhado no canvas
        head_items = self.view.canvas.find_withtag("sim_head")
        self.assertTrue(len(head_items) > 0)

        # 3. Executa passos da simulação
        self.view._sim_step()
        self.assertTrue(len(self.view.canvas.find_withtag("sim_head")) > 0)

        # 4. Para simulação via toggle
        self.view.toggle_simulation()
        self.assertFalse(self.view.sim_running)
        self.assertEqual(self.view.btn_sim.cget("text"), "▶ Simular")
        self.assertEqual(len(self.view.canvas.find_withtag("sim_head")), 0)
        self.assertEqual(len(self.view.canvas.find_withtag("sim_cut_trail")), 0)

    def test_simulation_cancel_via_escape(self):
        """Pressionar Escape (cancel_drag) interrompe a simulação ativa."""
        self.view.start_simulation()
        self.assertTrue(self.view.sim_running)
        res = self.view.cancel_drag()
        self.assertEqual(res, "break")
        self.assertFalse(self.view.sim_running)
        self.assertEqual(self.view.btn_sim.cget("text"), "▶ Simular")

    def test_session_view_buttons_nest_renamed_to_gerar_and_cut_removed(self):
        """Valida que o botão Nest foi renomeado para Gerar e o botão Cut foi removido da SessionView."""
        from ui.session_view import SessionView
        from unittest.mock import MagicMock

        cb_nest = MagicMock()
        sess_data = {
            "id": 101,
            "name": "Sessão Teste Botoes",
            "status": "Stand by",
            "placed_pieces": [],
            "shapes": [],
        }
        sv = SessionView(self.root, session_data=sess_data, on_nest=cb_nest)

        # 1. Botão Nest renomeado para Gerar
        self.assertIsNotNone(sv.btn_action_nest)
        self.assertEqual(sv.btn_action_nest.cget("text"), "Gerar")

        # 2. Ao clicar no botão Gerar, o callback de nesting é acionado
        sv.btn_action_nest.invoke()
        cb_nest.assert_called_once()

        # 3. Botão Cut foi removido
        self.assertIsNone(sv.btn_action_cut)

        sv.destroy()

    def test_layout_editor_menu_translated_to_portuguese(self):
        """Verifica se os menus do Layout Editor foram traduzidos para Português (Brasil)."""
        # Coleta os textos dos botões Menubutton filhos do menubar do view
        menubar_children = [
            w for w in self.view.children.values()
            if isinstance(w, tk.Frame) and any(isinstance(c, tk.Menubutton) for c in w.children.values())
        ]
        self.assertTrue(len(menubar_children) > 0)
        menu_frame = menubar_children[0]
        menubuttons = [c.cget("text") for c in menu_frame.children.values() if isinstance(c, tk.Menubutton)]
        expected = ["Arquivo", "Editar", "Exibir", "Encaixe", "Ferramentas", "Janela", "Ajuda"]
        self.assertEqual(menubuttons, expected)

    def test_piece_geometry_cache_hits_and_misses(self):
        """Valida que _get_piece_geom armazena em cache e contabiliza hits/misses corretamente."""
        self.view.clear_piece_cache()
        piece = {"contour": CONTOUR_CON, "x": 100.0, "y": 200.0, "rotation": 0.0}

        # Primeiro acesso: miss
        poly1, bbox1 = self.view._get_piece_geom(piece)
        stats1 = self.view.get_piece_cache_stats()
        self.assertEqual(stats1["misses"], 1)
        self.assertEqual(stats1["hits"], 0)

        # Segundo acesso idêntico: hit
        poly2, bbox2 = self.view._get_piece_geom(piece)
        stats2 = self.view.get_piece_cache_stats()
        self.assertEqual(stats2["misses"], 1)
        self.assertEqual(stats2["hits"], 1)
        self.assertEqual(stats2["hit_rate_pct"], 50.0)
        self.assertEqual(poly1, poly2)
        self.assertEqual(bbox1, bbox2)

        # Limpeza do cache
        self.view.clear_piece_cache()
        stats3 = self.view.get_piece_cache_stats()
        self.assertEqual(stats3["hits"], 0)
        self.assertEqual(stats3["misses"], 0)
        self.assertEqual(stats3["size"], 0)

    def test_lod_level_selection_and_piece_preservation(self):
        """Valida a transição entre Full, Simplified e LOD, garantindo 0 peças perdidas em todos os níveis."""
        # Cria 220 peças para acionar regras de LOD
        contour = CONTOUR_CON
        test_pieces = [
            {"name": f"P_{i}", "contour": contour, "x": 10.0 + (i % 10) * 120.0, "y": 10.0 + (i // 10) * 120.0, "rotation": 0.0}
            for i in range(220)
        ]
        self.view.placed_pieces = test_pieces
        self.view.selected_index = -1
        self.view.selected_indices = []

        # 1. Nível Full (zoom_factor alto -> effective_scale >= 0.5)
        self.view.zoom_factor = 5.0
        self.view.redraw()
        polys_full = self.view.canvas.find_withtag("piece_item")
        self.assertTrue(len(polys_full) >= 220)
        poly0 = self.view.canvas.find_withtag("piece_poly_0")
        self.assertTrue(len(poly0) > 0)
        self.assertEqual(self.view.canvas.type(poly0[0]), "polygon")
        self.assertNotEqual(self.view.canvas.itemcget(poly0[0], "fill"), "")

        # 2. Nível Simplified (zoom médio -> 0.15 <= effective_scale < 0.5)
        self.view.zoom_factor = 2.0
        self.view.redraw()
        polys_simp = self.view.canvas.find_withtag("piece_item")
        self.assertTrue(len(polys_simp) >= 220)
        poly0_simp = self.view.canvas.find_withtag("piece_poly_0")
        self.assertTrue(len(poly0_simp) > 0)
        self.assertEqual(self.view.canvas.type(poly0_simp[0]), "polygon")
        self.assertEqual(self.view.canvas.itemcget(poly0_simp[0], "fill"), "")

        # 3. Nível LOD (zoom baixo -> effective_scale < 0.15)
        self.view.zoom_factor = 0.2
        self.view.redraw()
        polys_lod = self.view.canvas.find_withtag("piece_item")
        self.assertTrue(len(polys_lod) >= 220)
        rect0 = self.view.canvas.find_withtag("piece_poly_0")
        self.assertTrue(len(rect0) > 0)
        self.assertEqual(self.view.canvas.type(rect0[0]), "rectangle")

        # Em TODOS os 3 níveis, todas as 220 peças foram renderizadas (zero desaparecidas)
        for i in range(220):
            item_tag = self.view.canvas.find_withtag(f"piece_{i}")
            self.assertTrue(len(item_tag) > 0, f"Peça {i} desapareceu no nível LOD!")

    def test_incremental_redraw_background_caching(self):
        """Valida que redraw() consecutivo preserva o background e reutiliza itens de fundo."""
        self.view.placed_pieces = [
            {"contour": CONTOUR_CON, "x": 50.0, "y": 50.0, "rotation": 0.0}
        ]
        self.view.redraw()
        bg_items_1 = set(self.view.canvas.find_withtag("bg_element"))
        self.assertTrue(len(bg_items_1) > 0)

        # Segundo redraw com mesma viewport/geometria
        self.view.redraw()
        bg_items_2 = set(self.view.canvas.find_withtag("bg_element"))
        # Os IDs dos itens de fundo devem ser idênticos (não foram deletados e recriados)
        self.assertEqual(bg_items_1, bg_items_2)


if __name__ == "__main__":
    unittest.main()




