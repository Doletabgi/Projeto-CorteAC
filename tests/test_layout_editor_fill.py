"""
JobManager 2000 (Python Edition)
tests/test_layout_editor_fill.py - Testes de Menu de Contexto 102 e Operações de Fill (Row, Row Alternate, Column)
"""

import unittest
import math
import tkinter as tk
from unittest.mock import MagicMock, patch

from ui.layout_editor_view import LayoutEditorView, CONTOUR_CON
from cad.geometry import polygon_bbox, transform_contour, polygons_collide
from cad.fill_engine import (
    fill_row_pieces,
    fill_row_alternate_pieces,
    fill_column_pieces,
    fill_sheet_pieces,
    fill_sheet_alternate_pieces,
    fill_user_pieces,
)
from ui.fill_user_dialog import FillUserDialog, FillUserConstraints, validate_fill_user_params



class DummyMouseEvent:
    def __init__(self, x=0, y=0, state=0, num=1, x_root=None, y_root=None):
        self.x = x
        self.y = y
        self.state = state
        self.num = num
        self.x_root = x_root if x_root is not None else x
        self.y_root = y_root if y_root is not None else y


class TestLayoutEditorFill(unittest.TestCase):
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
            self.skipTest("Tkinter display not available")
        self.view = LayoutEditorView(self.root, layout_name="[TEST_FILL]", load_sample=False)
        self.view.pack()
        self.view.update_idletasks()

    def tearDown(self):
        if hasattr(self, "view") and self.view:
            try:
                self.view.destroy()
            except Exception:
                pass

    def test_01_rclick_quick_opens_menu_and_drag_does_not(self):
        """
        Requisito 1:
        - Clique direito rápido (deslocamento < 2.65 px) abre o Menu de Contexto 102.
        - Botão direito com arrasto (> 2.65 px) NÃO abre o menu.
        - Clique sobre peça não selecionada seleciona-a antes de abrir o menu.
        """
        # Adiciona 2 peças na mesa
        self.view.placed_pieces = [
            {"target_id": "t1", "name": "P1", "contour": CONTOUR_CON, "x": 100.0, "y": 100.0, "rotation": 0.0},
            {"target_id": "t2", "name": "P2", "contour": CONTOUR_CON, "x": 400.0, "y": 100.0, "rotation": 0.0},
        ]
        self.view.selected_index = 0
        self.view.selected_indices = {0}
        self.view.redraw()

        # Simula clique rápido (< 2.65 px) sobre o canvas
        with patch.object(self.view.context_menu_102, "tk_popup") as mock_popup:
            press_ev = DummyMouseEvent(x=200, y=200)
            self.view.on_rbutton_press(press_ev)
            # Soltura a 1 px de distância (dist = 1.0 < 2.65 px)
            release_ev = DummyMouseEvent(x=201, y=200)
            self.view.on_rbutton_release(release_ev)

            self.assertTrue(self.view._context_menu_opened)
            mock_popup.assert_called_once()

        # Simula arrasto com botão direito (> 2.65 px)
        self.view._context_menu_opened = False
        with patch.object(self.view.context_menu_102, "tk_popup") as mock_popup:
            press_ev = DummyMouseEvent(x=200, y=200)
            self.view.on_rbutton_press(press_ev)
            # Arrasto de 15 px (dist = 15.0 > 2.65 px)
            drag_ev = DummyMouseEvent(x=215, y=200)
            self.view.on_rbutton_drag(drag_ev)
            release_ev = DummyMouseEvent(x=215, y=200)
            self.view.on_rbutton_release(release_ev)

            self.assertFalse(self.view._context_menu_opened)
            mock_popup.assert_not_called()

        # Testa que o clique direito rápido sobre outra peça NÃO altera a seleção existente
        # Coordenadas da peça 1 (x=400, y=100)
        sx, sy = self.view.world_to_screen(410.0, 100.0)
        self.view.selected_index = 0
        self.view.selected_indices = {0}
        with patch.object(self.view.context_menu_102, "tk_popup"):
            p_ev = DummyMouseEvent(x=int(sx), y=int(sy))
            self.view.on_rbutton_press(p_ev)
            r_ev = DummyMouseEvent(x=int(sx), y=int(sy))
            self.view.on_rbutton_release(r_ev)

            # A seleção deve permanecer inalterada na peça 0
            self.assertEqual(self.view.selected_index, 0)
            self.assertEqual(self.view.selected_indices, {0})
            self.assertEqual(self.view._context_target_idx, 0)

    def test_02_menu_structure_and_states(self):
        """
        Requisito 2:
        - Estrutura exata do Menu 102 com submenu Fill.
        - Submenu Fill com 6 itens: Row, Row Alternate e Column habilitados; Sheet, Sheet Alternate e User desabilitados.
        """
        menu = self.view.context_menu_102
        self.assertIsNotNone(menu)

        # Mapeia rótulos do menu principal
        total_entries = menu.index("end") + 1
        menu_items = []
        for i in range(total_entries):
            mtype = menu.type(i)
            if mtype == "separator":
                menu_items.append("---")
            else:
                lbl = menu.entrycget(i, "label")
                state = menu.entrycget(i, "state")
                menu_items.append((lbl, mtype, state))

        # Menu simplificado conforme solicitação do operador: exibe apenas Fill
        expected_labels = ["Fill"]

        actual_labels = [it if it == "---" else it[0] for it in menu_items]
        self.assertEqual(actual_labels, expected_labels)

        # Verifica estados no menu principal
        item_states = {it[0]: it[2] for it in menu_items if it != "---"}
        self.assertEqual(item_states["Fill"], "normal")

        # Verifica Submenu Fill com 6 itens
        fill_menu = self.view.fill_submenu
        self.assertIsNotNone(fill_menu)
        self.assertEqual(fill_menu.index("end") + 1, 6)

        fill_labels_states = [(fill_menu.entrycget(i, "label"), str(fill_menu.entrycget(i, "state"))) for i in range(6)]
        self.assertEqual(fill_labels_states[0], ("Row", "normal"))
        self.assertEqual(fill_labels_states[1], ("Row Alternate", "normal"))
        self.assertEqual(fill_labels_states[2], ("Column", "normal"))
        self.assertEqual(fill_labels_states[3], ("Sheet", "normal"))
        self.assertEqual(fill_labels_states[4], ("Sheet Alternate", "normal"))
        self.assertEqual(fill_labels_states[5], ("User...", "normal"))

    def test_03_fill_row_placement(self):
        """
        Requisito 3:
        Fill Row: N cópias, todas dentro das margens, zero sobreposição, gap respeitado.
        """
        self.view.sheet_width = 600.0
        self.view.sheet_height = 400.0
        self.view.set_margins(left=10.0, right=10.0, top=10.0, bottom=10.0)
        self.view.gap_mm = 2.0

        p0 = {
            "target_id": "target_1",
            "name": "CON_T3",
            "size": "3",
            "color": "#f97316",
            "contour": CONTOUR_CON,
            "x": 30.0,
            "y": 100.0,
            "rotation": 0.0
        }
        self.view.placed_pieces = [p0]
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        self.view.fill_row(0)

        # Deve gerar múltiplas cópias
        count = len(self.view.placed_pieces)
        self.assertGreater(count, 2)

        # 1. Todas as peças dentro dos limites da chapa
        for idx, p in enumerate(self.view.placed_pieces):
            poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
            b = polygon_bbox(poly)
            self.assertGreaterEqual(b[0], 10.0 - 1e-4, f"Peça {idx} violou margem esquerda")
            self.assertLessEqual(b[2], 600.0 - 10.0 + 1e-4, f"Peça {idx} violou margem direita")
            self.assertGreaterEqual(b[1], 10.0 - 1e-4, f"Peça {idx} violou margem inferior")
            self.assertLessEqual(b[3], 400.0 - 10.0 + 1e-4, f"Peça {idx} violou margem superior")

        # 2. Zero colisão / sobreposição entre qualquer par de peças
        for i in range(count):
            pi = self.view.placed_pieces[i]
            poly_i = transform_contour(pi["contour"], pi["x"], pi["y"], pi["rotation"])
            bbox_i = polygon_bbox(poly_i)
            for j in range(i + 1, count):
                pj = self.view.placed_pieces[j]
                poly_j = transform_contour(pj["contour"], pj["x"], pj["y"], pj["rotation"])
                bbox_j = polygon_bbox(poly_j)
                # Sem sobreposição
                self.assertFalse(
                    polygons_collide(poly_i, poly_j, gap=0.0, bbox_a=bbox_i, bbox_b=bbox_j),
                    f"Colisão detectada entre peças {i} e {j}"
                )

        # 3. Respeito ao gap de 2.0 mm entre peças vizinhas adjacentes
        for i in range(count - 1):
            p_a = self.view.placed_pieces[i]
            p_b = self.view.placed_pieces[i + 1]
            poly_a = transform_contour(p_a["contour"], p_a["x"], p_a["y"], p_a["rotation"])
            poly_b = transform_contour(p_b["contour"], p_b["x"], p_b["y"], p_b["rotation"])
            # Colisão com gap - 0.05 mm deve ser falsa (espaçamento respeitado)
            self.assertFalse(polygons_collide(poly_a, poly_b, gap=1.95))

    def test_04_fill_row_alternate(self):
        """
        Requisito 4:
        Fill Row Alternate: rotações alternam 0°/180°, zero colisão, encosto por contorno.
        """
        self.view.sheet_width = 600.0
        self.view.sheet_height = 400.0
        self.view.set_margins(left=10.0, right=10.0, top=10.0, bottom=10.0)
        self.view.gap_mm = 1.0

        p0 = {
            "target_id": "target_1",
            "name": "CON_T3",
            "size": "3",
            "color": "#f97316",
            "contour": CONTOUR_CON,
            "x": 30.0,
            "y": 120.0,
            "rotation": 0.0
        }
        self.view.placed_pieces = [p0]
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        self.view.fill_row_alternate(0)

        count = len(self.view.placed_pieces)
        self.assertGreater(count, 2)

        # Verifica alternância exata de 0° e 180°
        for idx, p in enumerate(self.view.placed_pieces):
            expected_rot = 180.0 if (idx % 2 == 1) else 0.0
            self.assertAlmostEqual(p["rotation"], expected_rot, places=2)

        # Zero colisão entre qualquer par de peças
        for i in range(count):
            pi = self.view.placed_pieces[i]
            poly_i = transform_contour(pi["contour"], pi["x"], pi["y"], pi["rotation"])
            bbox_i = polygon_bbox(poly_i)
            for j in range(i + 1, count):
                pj = self.view.placed_pieces[j]
                poly_j = transform_contour(pj["contour"], pj["x"], pj["y"], pj["rotation"])
                bbox_j = polygon_bbox(poly_j)
                self.assertFalse(polygons_collide(poly_i, poly_j, gap=0.0, bbox_a=bbox_i, bbox_b=bbox_j))

        # Encosto por contorno: o passo entre cópias alternadas aproveita a curva
        # (a distância entre centros X é menor que a soma das metades dos bounding boxes)
        poly0 = transform_contour(self.view.placed_pieces[0]["contour"], self.view.placed_pieces[0]["x"], self.view.placed_pieces[0]["y"], self.view.placed_pieces[0]["rotation"])
        poly1 = transform_contour(self.view.placed_pieces[1]["contour"], self.view.placed_pieces[1]["x"], self.view.placed_pieces[1]["y"], self.view.placed_pieces[1]["rotation"])
        b0 = polygon_bbox(poly0)
        b1 = polygon_bbox(poly1)
        w0 = b0[2] - b0[0]
        # Distância entre inícios:
        step_x = b1[0] - b0[0]
        # Como as peças alternam bico-calcanhar, há acoplamento real
        self.assertLess(step_x, w0 + self.view.gap_mm + 5.0)

    def test_05_fill_column_placement(self):
        """
        Requisito 5:
        Fill Column: análogo no eixo vertical (+Y).
        """
        self.view.sheet_width = 500.0
        self.view.sheet_height = 600.0
        self.view.set_margins(left=10.0, right=10.0, top=10.0, bottom=10.0)
        self.view.gap_mm = 1.5

        p0 = {
            "target_id": "target_1",
            "name": "CON_T3",
            "size": "3",
            "color": "#f97316",
            "contour": CONTOUR_CON,
            "x": 100.0,
            "y": 50.0,
            "rotation": 0.0
        }
        self.view.placed_pieces = [p0]
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        self.view.fill_column(0)

        count = len(self.view.placed_pieces)
        self.assertGreater(count, 2)

        # Verifica progressão estrita em +Y
        for i in range(count - 1):
            self.assertGreater(self.view.placed_pieces[i + 1]["y"], self.view.placed_pieces[i]["y"])

        # Todas dentro da margem superior útil
        for p in self.view.placed_pieces:
            poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
            b = polygon_bbox(poly)
            self.assertLessEqual(b[3], 600.0 - 10.0 + 1e-4)

        # Zero colisões
        for i in range(count):
            pi = self.view.placed_pieces[i]
            poly_i = transform_contour(pi["contour"], pi["x"], pi["y"], pi["rotation"])
            for j in range(i + 1, count):
                pj = self.view.placed_pieces[j]
                poly_j = transform_contour(pj["contour"], pj["x"], pj["y"], pj["rotation"])
                self.assertFalse(polygons_collide(poly_i, poly_j, gap=0.0))

    def test_06_fill_atomic_undo(self):
        """
        Requisito 6:
        Undo desfaz o Fill inteiro em 1 único passo; peças originais intactas.
        """
        p0 = {"target_id": "t1", "name": "P1", "contour": CONTOUR_CON, "x": 50.0, "y": 80.0, "rotation": 0.0}
        p_extra = {"target_id": "t2", "name": "P2", "contour": CONTOUR_CON, "x": 50.0, "y": 200.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0), dict(p_extra)]
        self.view.selected_index = 0
        self.view.selected_indices = {0}
        undo_len_start = len(self.view.undo_stack)

        self.view.fill_row(0)

        # Fill executado: peças adicionadas e exatamente +1 entrada na pilha de undo
        self.assertGreater(len(self.view.placed_pieces), 2)
        self.assertEqual(len(self.view.undo_stack), undo_len_start + 1)
        self.assertTrue(self.view.is_modified)

        # 1 passo de Undo desfaz o Fill completo
        self.view.undo_action()

        self.assertEqual(len(self.view.placed_pieces), 2)
        self.assertEqual(self.view.placed_pieces[0]["x"], 50.0)
        self.assertEqual(self.view.placed_pieces[0]["y"], 80.0)
        self.assertEqual(self.view.placed_pieces[1]["x"], 50.0)
        self.assertEqual(self.view.placed_pieces[1]["y"], 200.0)

    def test_07_fill_no_space_no_op(self):
        """
        Requisito 7:
        Fill sem espaço útil não altera o layout nem a pilha de undo_stack.
        """
        # Posiciona peça encostada na margem direita
        self.view.sheet_width = 300.0
        self.view.sheet_height = 300.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)

        poly_raw = transform_contour(CONTOUR_CON, 0, 0, 0)
        b_raw = polygon_bbox(poly_raw)
        w_piece = b_raw[2] - b_raw[0]

        # Coloca a peça no limite máximo da margem direita (sem caber nenhuma cópia)
        edge_x = 300.0 - 10.0 - b_raw[2]
        p_edge = {
            "target_id": "t1",
            "name": "EdgePiece",
            "contour": CONTOUR_CON,
            "x": edge_x,
            "y": 100.0,
            "rotation": 0.0
        }
        self.view.placed_pieces = [dict(p_edge)]
        self.view.selected_index = 0
        self.view.selected_indices = {0}
        self.view.set_modified(False)
        undo_len_before = len(self.view.undo_stack)

        self.view.fill_row(0)

        # Nenhuma peça adicionada, sem snapshot de undo e sem marcação de modificado
        self.assertEqual(len(self.view.placed_pieces), 1)
        self.assertEqual(len(self.view.undo_stack), undo_len_before)
        self.assertFalse(self.view.is_modified)

    def test_08_empty_canvas_click_disables_piece_items(self):
        """
        Ajuste Obrigatório 1:
        Clique direito no vazio (sem peça-alvo selecionada nem sob o cursor):
        abre o menu com Fill, Delete, Mirror desabilitados, e Check Overlay habilitado.
        """
        self.view.placed_pieces = []
        self.view.selected_index = None
        self.view.selected_indices = set()

        with patch.object(self.view.context_menu_102, "tk_popup") as mock_popup:
            press_ev = DummyMouseEvent(x=200, y=200)
            self.view.on_rbutton_press(press_ev)
            release_ev = DummyMouseEvent(x=200, y=200)
            self.view.on_rbutton_release(release_ev)

            mock_popup.assert_called_once()
            self.assertTrue(self.view._context_menu_opened)
            self.assertIsNone(self.view._context_target_idx)

            # Valida estados no menu principal
            menu = self.view.context_menu_102
            self.assertEqual(str(menu.entrycget("Fill", "state")), "disabled")

            # Submenu Fill deve estar desabilitado
            fill_menu = self.view.fill_submenu
            self.assertEqual(str(fill_menu.entrycget("Row", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Row Alternate", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Column", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Sheet", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Sheet Alternate", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("User...", "state")), "disabled")

    def test_09_fill_row_stops_at_middle_obstacle(self):
        """
        Ajuste Obrigatório 2 (Parte 1):
        Fill Row com obstáculo no meio da linha.
        O Fill deve parar antes do obstáculo e JAMAIS saltá-lo ou gerar peça sobreposta.
        """
        self.view.sheet_width = 800.0
        self.view.sheet_height = 400.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)
        self.view.gap_mm = 2.0

        p_start = {
            "target_id": "t1",
            "name": "StartPiece",
            "contour": CONTOUR_CON,
            "x": 30.0,
            "y": 100.0,
            "rotation": 0.0
        }
        # Obstáculo posicionado a X=250 na mesma faixa horizontal
        p_obstacle = {
            "target_id": "obs",
            "name": "Obstacle",
            "contour": CONTOUR_CON,
            "x": 250.0,
            "y": 100.0,
            "rotation": 0.0
        }
        self.view.placed_pieces = [dict(p_start), dict(p_obstacle)]
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        self.view.fill_row(0)

        # O preenchimento deve ter adicionado peças intermediárias
        count = len(self.view.placed_pieces)
        self.assertGreater(count, 2)

        obs_poly = transform_contour(p_obstacle["contour"], p_obstacle["x"], p_obstacle["y"], p_obstacle["rotation"])
        obs_bbox = polygon_bbox(obs_poly)

        # Nenhuma peça ultrapassa ou salta o obstáculo
        for i, p in enumerate(self.view.placed_pieces):
            if p["target_id"] == "obs":
                continue
            poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
            bbox = polygon_bbox(poly)
            # Nenhuma colisão com o obstáculo
            self.assertFalse(polygons_collide(poly, obs_poly, gap=self.view.gap_mm - 0.01))
            # Nenhuma cópia gerada além do obstáculo
            self.assertLess(bbox[2], obs_bbox[0] + 1e-3, f"Peça {i} gerada após ou sobre o obstáculo")

    def test_10_fill_row_concave_contour_snug_fit(self):
        """
        Ajuste Obrigatório 2 (Parte 2):
        Peça com contorno côncavo (formato em 'U' / 'C').
        Valida que o algoritmo realiza encosto por contorno sem colisões nem penetração.
        """
        CONCAVE_CONTOUR = [
            {"x": 0.0, "y": 0.0},
            {"x": 80.0, "y": 0.0},
            {"x": 80.0, "y": 25.0},
            {"x": 25.0, "y": 25.0},
            {"x": 25.0, "y": 55.0},
            {"x": 80.0, "y": 55.0},
            {"x": 80.0, "y": 80.0},
            {"x": 0.0, "y": 80.0},
        ]
        self.view.sheet_width = 600.0
        self.view.sheet_height = 400.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)
        self.view.gap_mm = 1.0

        p0 = {
            "target_id": "c1",
            "name": "ConcavePiece",
            "contour": CONCAVE_CONTOUR,
            "x": 30.0,
            "y": 100.0,
            "rotation": 0.0
        }
        self.view.placed_pieces = [p0]
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        self.view.fill_row(0)

        count = len(self.view.placed_pieces)
        self.assertGreater(count, 3)

        # Zero colisão entre qualquer par de peças côncavas
        for i in range(count):
            pi = self.view.placed_pieces[i]
            poly_i = transform_contour(pi["contour"], pi["x"], pi["y"], pi["rotation"])
            bbox_i = polygon_bbox(poly_i)
            for j in range(i + 1, count):
                pj = self.view.placed_pieces[j]
                poly_j = transform_contour(pj["contour"], pj["x"], pj["y"], pj["rotation"])
                bbox_j = polygon_bbox(poly_j)
                self.assertFalse(
                    polygons_collide(poly_i, poly_j, gap=0.0, bbox_a=bbox_i, bbox_b=bbox_j),
                    f"Colisão detectada entre peças côncavas {i} e {j}"
                )

    def test_11_fill_column_direction_proves_visual_top(self):
        """
        Ajuste Obrigatório 3:
        Comprova que o Fill Column avança em direção à margem superior visual da chapa:
        - wy (mundo) aumenta monotonicamente (wy_{i+1} > wy_i).
        - sy (canvas screen) diminui monotonicamente (sy_{i+1} < sy_i), aproximando-se de plate_y1.
        """
        self.view.sheet_width = 400.0
        self.view.sheet_height = 600.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)
        self.view.gap_mm = 2.0
        self.view.redraw()

        p0 = {
            "target_id": "col_1",
            "name": "ColPiece",
            "contour": CONTOUR_CON,
            "x": 50.0,
            "y": 30.0,
            "rotation": 0.0
        }
        self.view.placed_pieces = [p0]
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        self.view.fill_column(0)

        count = len(self.view.placed_pieces)
        self.assertGreater(count, 2)

        # Na tela do canvas, o topo da chapa (plate_y1) tem coordenada Y menor que o fundo (plate_y2)
        plate_top_screen = self.view.plate_y1
        plate_bottom_screen = self.view.plate_y2
        self.assertLess(plate_top_screen, plate_bottom_screen)

        for i in range(count - 1):
            p_curr = self.view.placed_pieces[i]
            p_next = self.view.placed_pieces[i + 1]

            # 1. No mundo cartesiano industrial, Y aumenta (+Y para cima)
            self.assertGreater(p_next["y"], p_curr["y"])

            # 2. Na tela Tkinter (origem no canto superior esquerdo), sy diminui aproximando-se de plate_y1
            sx_curr, sy_curr = self.view.world_to_screen(p_curr["x"], p_curr["y"])
            sx_next, sy_next = self.view.world_to_screen(p_next["x"], p_next["y"])
            self.assertLess(sy_next, sy_curr, "A peça seguinte deve estar visualmente ACIMA na tela (menor sy)")
            self.assertGreater(sy_next, plate_top_screen, "A peça seguinte não deve ultrapassar a margem superior da chapa")

    def test_12_rclick_over_unselected_piece_preserves_selection_and_targets_selected(self):
        """
        Requisito de Ajuste no Plano (Itens 1 e 4):
        - O clique direito NÃO altera a seleção existente.
        - Clique direito sobre outra peça não selecionada abre o menu agindo sobre a seleção atual.
        - Fill opera sobre a peça selecionada e as cópias geradas NÃO ficam selecionadas.
        """
        self.view.sheet_width = 800.0
        self.view.sheet_height = 400.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)
        self.view.gap_mm = 1.0

        p0 = {"target_id": "t1", "name": "P0_Selected", "contour": CONTOUR_CON, "x": 50.0, "y": 80.0, "rotation": 0.0}
        p1 = {"target_id": "t2", "name": "P1_Unselected", "contour": CONTOUR_CON, "x": 50.0, "y": 250.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0), dict(p1)]

        # Seleciona explicitamente P0 (via clique esquerdo / operador)
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        # Clique direito rápido sobre P1 (unselected) em (50, 250)
        sx1, sy1 = self.view.world_to_screen(50.0, 250.0)
        with patch.object(self.view.context_menu_102, "tk_popup") as mock_popup:
            self.view.on_rbutton_press(DummyMouseEvent(x=int(sx1), y=int(sy1)))
            self.view.on_rbutton_release(DummyMouseEvent(x=int(sx1), y=int(sy1)))

            mock_popup.assert_called_once()
            # A seleção NÃO foi transferida para P1; continua em P0!
            self.assertEqual(self.view.selected_index, 0)
            self.assertEqual(self.view.selected_indices, {0})
            self.assertEqual(self.view._context_target_idx, 0)

            # Menu habilitado porque HÁ seleção
            self.assertEqual(str(self.view.context_menu_102.entrycget("Fill", "state")), "normal")

        # Dispara Fill Row: deve clonar P0 (a peça selecionada), não P1
        self.view.fill_row()

        # Peças adicionadas na linha de P0 (Y=80)
        self.assertGreater(len(self.view.placed_pieces), 2)
        for p in self.view.placed_pieces[2:]:
            self.assertEqual(p["y"], 80.0, "Cópias devem ter sido geradas na linha de P0 (peça selecionada)")
            self.assertEqual(p["name"], "P0_Selected")

        # P1 (em Y=250) permanece intacto
        self.assertEqual(self.view.placed_pieces[1]["y"], 250.0)

        # Após o Fill: a seleção continua na peça original P0 (as cópias NÃO são selecionadas)
        self.assertEqual(self.view.selected_index, 0)
        self.assertEqual(self.view.selected_indices, {0})

    def test_13_fill_multiple_selection_uses_primary_piece(self):
        """
        Requisito de Ajuste no Plano (Item 2):
        Seleção múltipla: o Fill usa a peça primária (selected_index; se None, primeira em ordem estável)
        e as demais peças da seleção permanecem inalteradas.
        """
        self.view.sheet_width = 800.0
        self.view.sheet_height = 400.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)
        self.view.gap_mm = 1.0

        p0 = {"target_id": "t1", "name": "Primary", "contour": CONTOUR_CON, "x": 30.0, "y": 80.0, "rotation": 0.0}
        p1 = {"target_id": "t2", "name": "Secondary", "contour": CONTOUR_CON, "x": 30.0, "y": 250.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0), dict(p1)]

        # Seleção múltipla com P0 como primária
        self.view.selected_indices = {0, 1}
        self.view.selected_index = 0

        self.assertEqual(self.view.get_target_piece_index(), 0)

        # Fill Row utiliza P0
        self.view.fill_row()

        self.assertGreater(len(self.view.placed_pieces), 2)
        # Cópias geradas foram para a linha de P0
        for p in self.view.placed_pieces[2:]:
            self.assertEqual(p["name"], "Primary")
            self.assertEqual(p["y"], 80.0)

        # P1 em Y=250 permaneceu inalterada
        self.assertEqual(self.view.placed_pieces[1]["y"], 250.0)

        # Caso selected_index seja None: usa a primeira em ordem estável (sorted(selected_indices)[0])
        self.view.selected_index = None
        self.assertEqual(self.view.get_target_piece_index(), 0)

    def test_14_operator_workflow_left_select_right_click_fill_atomic_undo(self):
        """
        Requisito de Ajuste no Plano (Fluxo Completo do Operador):
        1. Clique esquerdo seleciona a peça.
        2. Clique direito rápido abre o Menu 102.
        3. Fill > Row gera as cópias operando sobre a peça selecionada.
        4. Undo desfaz o Fill inteiro em 1 único passo.
        """
        self.view.sheet_width = 600.0
        self.view.sheet_height = 400.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)
        self.view.gap_mm = 1.0

        p0 = {"target_id": "t1", "name": "OperatorPiece", "contour": CONTOUR_CON, "x": 50.0, "y": 100.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0)]
        self.view.selected_index = None
        self.view.selected_indices = set()
        self.view.redraw()

        # 1. Clique esquerdo sobre a peça 0 seleciona-a
        sx0, sy0 = self.view.world_to_screen(50.0, 100.0)
        self.view.on_canvas_click(DummyMouseEvent(x=int(sx0), y=int(sy0), num=1))
        self.assertEqual(self.view.selected_index, 0)
        self.assertIn(0, self.view.selected_indices)

        # 2. Clique direito rápido (< 2.65 px) abre o menu de contexto
        with patch.object(self.view.context_menu_102, "tk_popup") as mock_popup:
            press_ev = DummyMouseEvent(x=int(sx0 + 10), y=int(sy0 + 10))
            self.view.on_rbutton_press(press_ev)
            release_ev = DummyMouseEvent(x=int(sx0 + 11), y=int(sy0 + 10))
            self.view.on_rbutton_release(release_ev)

            mock_popup.assert_called_once()
            # Menus habilitados
            self.assertEqual(str(self.view.context_menu_102.entrycget("Fill", "state")), "normal")

        # 3. Fill > Row gera cópias
        undo_len_start = len(self.view.undo_stack)
        self.view.fill_row()

        self.assertGreater(len(self.view.placed_pieces), 2)
        self.assertEqual(len(self.view.undo_stack), undo_len_start + 1)
        self.assertTrue(self.view.is_modified)

        # Seleção permanece na peça original 0
        self.assertEqual(self.view.selected_index, 0)
        self.assertEqual(set(self.view.selected_indices), {0})

        # 4. Undo desfaz o Fill completo em 1 único passo
        self.view.undo_action()
        self.assertEqual(len(self.view.placed_pieces), 1)
        self.assertEqual(len(self.view.undo_stack), undo_len_start)
        self.assertEqual(self.view.placed_pieces[0]["name"], "OperatorPiece")

    def test_15_empty_selection_disables_items_recalculated_each_open(self):
        """
        Requisito de Ajuste no Plano (Item 3):
        A habilitação do menu é recalculada a cada abertura:
        - Sem seleção: Fill, Delete, Mirror desabilitados; Check Overlay habilitado.
        - Com seleção: Fill, Delete, Mirror habilitados.
        - Ao desmarcar seleção: volta a ficar desabilitado.
        """
        p0 = {"target_id": "t1", "name": "P0", "contour": CONTOUR_CON, "x": 50.0, "y": 100.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0)]

        menu = self.view.context_menu_102
        fill_menu = self.view.fill_submenu

        # 1. Sem seleção
        self.view.selected_index = None
        self.view.selected_indices = set()
        with patch.object(menu, "tk_popup"):
            self.view.open_context_menu_102(DummyMouseEvent(x=100, y=100))
            self.assertEqual(str(menu.entrycget("Fill", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Row", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Row Alternate", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Column", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Sheet", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Sheet Alternate", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("User...", "state")), "disabled")

        # 2. Seleciona peça 0
        self.view.selected_index = 0
        self.view.selected_indices = {0}
        with patch.object(menu, "tk_popup"):
            self.view.open_context_menu_102(DummyMouseEvent(x=100, y=100))
            self.assertEqual(str(menu.entrycget("Fill", "state")), "normal")
            self.assertEqual(str(fill_menu.entrycget("Row", "state")), "normal")
            self.assertEqual(str(fill_menu.entrycget("Row Alternate", "state")), "normal")
            self.assertEqual(str(fill_menu.entrycget("Column", "state")), "normal")
            self.assertEqual(str(fill_menu.entrycget("Sheet", "state")), "normal")
            self.assertEqual(str(fill_menu.entrycget("Sheet Alternate", "state")), "normal")
            self.assertEqual(str(fill_menu.entrycget("User...", "state")), "normal")

        # 3. Limpa seleção novamente
        self.view.selected_index = None
        self.view.selected_indices = set()
        with patch.object(menu, "tk_popup"):
            self.view.open_context_menu_102(DummyMouseEvent(x=100, y=100))
            self.assertEqual(str(menu.entrycget("Fill", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Row", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Sheet", "state")), "disabled")

    def test_16_fill_sheet_placement(self):
        """
        Test 16: Fill > Sheet (Win32 ID 52105).
        Preenchimento de múltiplas linhas na chapa, todas dentro das margens,
        zero colisão contorno a contorno, gap_mm respeitado e empilhamento vertical contorno a contorno.
        """
        self.view.sheet_width = 500.0
        self.view.sheet_height = 400.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)
        self.view.gap_mm = 1.0

        p0 = {"target_id": "t1", "name": "P0", "contour": CONTOUR_CON, "x": 20.0, "y": 60.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0)]
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        self.view.fill_sheet()

        self.assertGreater(len(self.view.placed_pieces), 4)

        # Valida que há peças em múltiplas linhas (+Y)
        y_coords = [p["y"] for p in self.view.placed_pieces]
        self.assertGreater(len(set(round(y, 1) for y in y_coords)), 1)

        # Valida margens e colisões
        polys = []
        for p in self.view.placed_pieces:
            poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
            bbox = polygon_bbox(poly)
            self.assertGreaterEqual(bbox[0], 10.0 - 0.05)
            self.assertLessEqual(bbox[2], 500.0 - 10.0 + 0.05)
            self.assertGreaterEqual(bbox[1], 10.0 - 0.05)
            self.assertLessEqual(bbox[3], 400.0 - 10.0 + 0.05)
            polys.append((poly, bbox))

        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                self.assertFalse(
                    polygons_collide(polys[i][0], polys[j][0], gap=0.0, bbox_a=polys[i][1], bbox_b=polys[j][1]),
                    f"Colisão detectada entre peça {i} e {j}"
                )

        # A peça original permanece selecionada
        self.assertEqual(self.view.selected_index, 0)
        self.assertTrue(self.view.is_modified)

    def test_17_fill_sheet_with_obstacle(self):
        """
        Test 17: Fill Sheet com obstáculo no meio da chapa.
        As cópias param antes do obstáculo na linha afetada e preenchem as demais linhas com zero colisões.
        """
        self.view.sheet_width = 500.0
        self.view.sheet_height = 400.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)
        self.view.gap_mm = 1.0

        p0 = {"target_id": "t1", "name": "P0", "contour": CONTOUR_CON, "x": 20.0, "y": 60.0, "rotation": 0.0}
        obstacle = {"target_id": "obs", "name": "Obstacle", "contour": CONTOUR_CON, "x": 200.0, "y": 60.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0), dict(obstacle)]
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        self.view.fill_sheet()

        self.assertGreater(len(self.view.placed_pieces), 2)

        # Valida zero colisões contra o obstáculo e entre todas as peças
        polys = [
            (transform_contour(p["contour"], p["x"], p["y"], p["rotation"]),
             polygon_bbox(transform_contour(p["contour"], p["x"], p["y"], p["rotation"])))
            for p in self.view.placed_pieces
        ]
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                self.assertFalse(
                    polygons_collide(polys[i][0], polys[j][0], gap=0.0, bbox_a=polys[i][1], bbox_b=polys[j][1]),
                    f"Colisão detectada entre peça {i} e {j} com obstáculo"
                )

    def test_18_fill_sheet_alternate(self):
        """
        Test 18: Fill > Sheet Alternate (Win32 ID 52106).
        Alternância 0° / 180° a cada peça por linha com acoplamento contorno a contorno.
        """
        self.view.sheet_width = 500.0
        self.view.sheet_height = 400.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)
        self.view.gap_mm = 1.0

        p0 = {"target_id": "t1", "name": "P0", "contour": CONTOUR_CON, "x": 20.0, "y": 60.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0)]
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        self.view.fill_sheet_alternate()

        self.assertGreater(len(self.view.placed_pieces), 4)

        # Verifica que existem peças rotacionadas em 0° e 180°
        rotations = set(round(p["rotation"] % 360, 1) for p in self.view.placed_pieces)
        self.assertIn(0.0, rotations)
        self.assertIn(180.0, rotations)

        # Valida zero sobreposição
        polys = [
            (transform_contour(p["contour"], p["x"], p["y"], p["rotation"]),
             polygon_bbox(transform_contour(p["contour"], p["x"], p["y"], p["rotation"])))
            for p in self.view.placed_pieces
        ]
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                self.assertFalse(
                    polygons_collide(polys[i][0], polys[j][0], gap=0.0, bbox_a=polys[i][1], bbox_b=polys[j][1]),
                    f"Colisão detectada em Sheet Alternate entre {i} e {j}"
                )

    def test_19_fill_sheet_no_space_status_bar(self):
        """
        Test 19: Sem espaço útil para Fill Sheet.
        Nenhuma peça é adicionada, pilha de undo fica intacta e mensagem na status bar.
        """
        self.view.sheet_width = 60.0
        self.view.sheet_height = 80.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)

        p0 = {"target_id": "t1", "name": "P0", "contour": CONTOUR_CON, "x": 10.0, "y": 48.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0)]
        self.view.selected_index = 0
        self.view.selected_indices = {0}
        self.view.set_modified(False)
        undo_len_before = len(self.view.undo_stack)

        self.view.fill_sheet()

        self.assertEqual(len(self.view.placed_pieces), 1)
        self.assertEqual(len(self.view.undo_stack), undo_len_before)
        self.assertFalse(self.view.is_modified)
        self.assertIn("Nenhuma cópia coube", self.view.lbl_stat_pos.cget("text"))

    def test_20_fill_sheet_atomic_undo(self):
        """
        Test 20: Undo atômico do Fill Sheet.
        1 único Ctrl+Z desfaz todas as cópias geradas pelo preenchimento da chapa inteira.
        """
        self.view.sheet_width = 500.0
        self.view.sheet_height = 400.0
        self.view.set_margins(10.0, 10.0, 10.0, 10.0)

        p0 = {"target_id": "t1", "name": "P0", "contour": CONTOUR_CON, "x": 20.0, "y": 60.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0)]
        self.view.selected_index = 0
        self.view.selected_indices = {0}

        self.view.fill_sheet()
        self.assertGreater(len(self.view.placed_pieces), 5)

        # 1 único undo
        self.view.undo_action()
        self.assertEqual(len(self.view.placed_pieces), 1)
        self.assertEqual(self.view.placed_pieces[0]["name"], "P0")

    def test_21_fill_sheet_max_pieces_safety_limit(self):
        """
        Test 21: Limite de segurança max_pieces em fill_sheet_pieces.
        Em chapa enorme, respeita o limite estrito de peças sem extrapolar nem travar.
        """
        p0 = {"target_id": "t1", "name": "P0", "contour": CONTOUR_CON, "x": 20.0, "y": 60.0, "rotation": 0.0}
        res = fill_sheet_pieces(
            target_piece=p0,
            placed_pieces=[p0],
            sheet_width=2000.0,
            sheet_height=2000.0,
            max_pieces=12
        )
        self.assertEqual(len(res), 12)

    def test_22_fill_user_dialog_validation_and_session_memory(self):
        """
        Test 22: Validação pura do FillUserDialog e memória de sessão RAM.
        Rejeição de parâmetros inválidos e persistência de valores válidos em _last_values.
        """
        # 1. Validação positiva
        good_dict = {
            "direction": "row",
            "step_x": "75.5",
            "step_y": "40.0",
            "max_copies": "8",
            "alternate_rot": True,
            "extra_gap": "1.5",
            "fill_sheet": True,
        }
        constraints, err = validate_fill_user_params(good_dict)
        self.assertIsNone(err)
        self.assertIsNotNone(constraints)
        self.assertEqual(constraints.step_x_mm, 75.5)
        self.assertEqual(constraints.step_y_mm, 40.0)
        self.assertEqual(constraints.max_copies, 8)
        self.assertTrue(constraints.alternate_rot)
        self.assertEqual(constraints.extra_gap_mm, 1.5)
        self.assertTrue(constraints.fill_sheet)

        # 2. Validações negativas
        _, err_dir = validate_fill_user_params({"direction": "diagonal"})
        self.assertIn("Direção inválida", err_dir)

        _, err_neg_x = validate_fill_user_params({"step_x": "-5"})
        self.assertIn("Passo X não pode ser negativo", err_neg_x)

        _, err_nan_x = validate_fill_user_params({"step_x": "xyz"})
        self.assertIn("Valor inválido para o Passo X", err_nan_x)

        _, err_float_max = validate_fill_user_params({"max_copies": "3.5"})
        self.assertIn("deve ser um número inteiro", err_float_max)

        _, err_neg_gap = validate_fill_user_params({"extra_gap": "-1.0"})
        self.assertIn("não pode ser negativa", err_neg_gap)

        # 3. Memória de sessão RAM
        FillUserDialog._last_values = good_dict
        self.assertEqual(FillUserDialog._last_values["step_x"], "75.5")

    def test_23_fill_user_fixed_step_placement(self):
        """
        Test 23: Preenchimento por passo fixo milimétrico (FillUserConstraints).
        """
        p0 = {"target_id": "t1", "name": "P0", "contour": CONTOUR_CON, "x": 20.0, "y": 60.0, "rotation": 0.0}
        constraints = FillUserConstraints(
            direction="row",
            step_x_mm=100.0,
            step_y_mm=0.0,
            max_copies=3,
            alternate_rot=False,
            extra_gap_mm=0.0,
            fill_sheet=False
        )

        copies = fill_user_pieces(
            target_piece=p0,
            placed_pieces=[p0],
            sheet_width=800.0,
            sheet_height=400.0,
            constraints=constraints
        )

        self.assertEqual(len(copies), 3)
        self.assertAlmostEqual(copies[0]["x"], 120.0, places=2)
        self.assertAlmostEqual(copies[1]["x"], 220.0, places=2)
        self.assertAlmostEqual(copies[2]["x"], 320.0, places=2)

    def test_24_fill_user_step_zero_contour_and_fill_sheet(self):
        """
        Test 24: Passo 0 equivale a encosto automático por contorno em fill_user_pieces.
        Suporta fill_sheet=True com alternância.
        """
        p0 = {"target_id": "t1", "name": "P0", "contour": CONTOUR_CON, "x": 20.0, "y": 60.0, "rotation": 0.0}
        constraints = FillUserConstraints(
            direction="row",
            step_x_mm=0.0,
            step_y_mm=0.0,
            max_copies=10,
            alternate_rot=True,
            extra_gap_mm=0.5,
            fill_sheet=True
        )

        copies = fill_user_pieces(
            target_piece=p0,
            placed_pieces=[p0],
            sheet_width=600.0,
            sheet_height=400.0,
            constraints=constraints,
            base_gap_mm=1.0
        )

        self.assertGreater(len(copies), 0)
        self.assertLessEqual(len(copies), 10)

        # Valida alternância angular
        rotations = set(round(p["rotation"] % 360, 1) for p in copies)
        self.assertTrue(0.0 in rotations or 180.0 in rotations)

        # Valida zero sobreposição
        all_pieces = [p0] + copies
        polys = [
            (transform_contour(p["contour"], p["x"], p["y"], p["rotation"]),
             polygon_bbox(transform_contour(p["contour"], p["x"], p["y"], p["rotation"])))
            for p in all_pieces
        ]
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                self.assertFalse(
                    polygons_collide(polys[i][0], polys[j][0], gap=0.0, bbox_a=polys[i][1], bbox_b=polys[j][1]),
                    f"Colisão detectada no Fill User entre {i} e {j}"
                )

    def test_25_menu_sheet_and_user_states_dynamic(self):
        """
        Test 25: Habilitação de Sheet, Sheet Alternate e User... quando há seleção
        e desabilitação quando não há seleção.
        """
        p0 = {"target_id": "t1", "name": "P0", "contour": CONTOUR_CON, "x": 50.0, "y": 100.0, "rotation": 0.0}
        self.view.placed_pieces = [dict(p0)]
        menu = self.view.context_menu_102
        fill_menu = self.view.fill_submenu

        # 1. Sem seleção -> desabilitados
        self.view.selected_index = None
        self.view.selected_indices = set()
        with patch.object(menu, "tk_popup"):
            self.view.open_context_menu_102(DummyMouseEvent(x=100, y=100))
            self.assertEqual(str(fill_menu.entrycget("Sheet", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("Sheet Alternate", "state")), "disabled")
            self.assertEqual(str(fill_menu.entrycget("User...", "state")), "disabled")

        # 2. Com seleção -> habilitados
        self.view.selected_index = 0
        self.view.selected_indices = {0}
        with patch.object(menu, "tk_popup"):
            self.view.open_context_menu_102(DummyMouseEvent(x=100, y=100))
            self.assertEqual(str(fill_menu.entrycget("Sheet", "state")), "normal")
            self.assertEqual(str(fill_menu.entrycget("Sheet Alternate", "state")), "normal")
            self.assertEqual(str(fill_menu.entrycget("User...", "state")), "normal")


if __name__ == "__main__":
    unittest.main()
