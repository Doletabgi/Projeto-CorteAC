"""
tests/test_shape_editor_multishape.py

Testes automatizados para a seleção e abertura de múltiplos moldes no Shape Editor:
1. Carga de múltiplos moldes em abas no ShapeEditorView
2. Alternância entre abas de moldes e sincronização de dados/título
3. Isolamento de modificações e pilhas de Undo/Redo entre abas
4. Fechamento de abas individuais
5. Modo de sobreposição (Sobrepor Todos / Grade de Tamanhos)
6. Abertura múltipla via seleção em grid_lower no MainWindow
7. Navegação cíclica via next_shape e prev_shape (Ctrl+Tab)
"""
import copy
import tkinter as tk
import unittest

from ui.main_window import MainWindow
from ui.shape_editor_view import ShapeEditorView


class TestShapeEditorMultiShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = MainWindow()
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.shape_a = {
            "id": 101,
            "name": "Peça_22a",
            "size": "22a",
            "contour": [
                {"x": 0.0, "y": 0.0},
                {"x": 100.0, "y": 0.0},
                {"x": 100.0, "y": 50.0},
                {"x": 0.0, "y": 50.0}
            ],
            "holes": [{"x": 20.0, "y": 20.0, "r": 3.0}],
            "stitching": []
        }
        self.shape_b = {
            "id": 102,
            "name": "Peça_23a",
            "size": "23a",
            "contour": [
                {"x": 0.0, "y": 0.0},
                {"x": 105.0, "y": 0.0},
                {"x": 105.0, "y": 52.0},
                {"x": 0.0, "y": 52.0}
            ],
            "holes": [{"x": 21.0, "y": 21.0, "r": 3.0}],
            "stitching": []
        }
        self.shape_c = {
            "id": 103,
            "name": "Peça_24a",
            "size": "24a",
            "contour": [
                {"x": 0.0, "y": 0.0},
                {"x": 110.0, "y": 0.0},
                {"x": 110.0, "y": 55.0},
                {"x": 0.0, "y": 55.0}
            ],
            "holes": [{"x": 22.0, "y": 22.0, "r": 3.0}],
            "stitching": []
        }

    def test_01_load_multiple_shapes_creates_tabs(self):
        """1. Carga de múltiplos moldes gera a lista de abas e define o molde inicial."""
        editor = self.root.shape_editor_view
        editor.load_shapes([self.shape_a, self.shape_b, self.shape_c])
        self.root.update()

        self.assertEqual(len(editor.open_shapes), 3)
        self.assertEqual(editor.active_shape_index, 0)
        self.assertEqual(editor.shape["id"], 101)
        self.assertEqual(editor.shape["name"], "Peça_22a")
        self.assertIn("Peça_22a", editor.lbl_title.cget("text"))
        self.assertIn("1 de 3", editor.lbl_title.cget("text"))

    def test_02_switch_to_shape_tab(self):
        """2. switch_to_shape alterna corretamente o molde ativo no canvas e título."""
        editor = self.root.shape_editor_view
        editor.load_shapes([self.shape_a, self.shape_b, self.shape_c])
        self.root.update()

        editor.switch_to_shape(1)
        self.root.update()

        self.assertEqual(editor.active_shape_index, 1)
        self.assertEqual(editor.shape["id"], 102)
        self.assertEqual(editor.shape["name"], "Peça_23a")
        self.assertIn("Peça_23a", editor.lbl_title.cget("text"))
        self.assertIn("2 de 3", editor.lbl_title.cget("text"))

    def test_03_isolated_undo_and_modifications_across_tabs(self):
        """3. Alterações e histórico de desfazer (Ctrl+Z) em uma aba são preservados e isolados das demais."""
        editor = self.root.shape_editor_view
        editor.load_shapes([self.shape_a, self.shape_b])
        self.root.update()

        # Altera molde A
        editor.push_undo()
        editor.shape["contour"][1]["x"] = 150.0

        # Alterna para molde B
        editor.switch_to_shape(1)
        self.root.update()
        self.assertEqual(editor.shape["contour"][1]["x"], 105.0)
        self.assertEqual(len(editor.undo_stack), 0)

        # Volta para molde A
        editor.switch_to_shape(0)
        self.root.update()
        self.assertEqual(editor.shape["contour"][1]["x"], 150.0)
        self.assertEqual(len(editor.undo_stack), 1)

        # Desfaz alteração
        editor.undo_or_revert()
        self.assertEqual(editor.shape["contour"][1]["x"], 100.0)

    def test_04_close_tab(self):
        """4. close_shape_tab remove a aba selecionada e foca no molde adjacente."""
        editor = self.root.shape_editor_view
        editor.load_shapes([self.shape_a, self.shape_b, self.shape_c])
        self.root.update()

        # Fecha a segunda aba (Peça_23a)
        editor.close_shape_tab(1)
        self.root.update()

        self.assertEqual(len(editor.open_shapes), 2)
        self.assertEqual(editor.open_shapes[0]["shape"]["id"], 101)
        self.assertEqual(editor.open_shapes[1]["shape"]["id"], 103)

    def test_05_overlay_all_shapes_mode(self):
        """5. Modo sobrepor todos (var_overlay_all) desenha os contornos secundários no canvas."""
        editor = self.root.shape_editor_view
        editor.load_shapes([self.shape_a, self.shape_b, self.shape_c])
        editor.var_overlay_all.set(True)
        self.root.update()

        editor.redraw()
        tags = editor.canvas.find_withtag("overlay_shapes")
        self.assertTrue(len(tags) > 0)

    def test_06_navigation_next_prev_shape(self):
        """6. next_shape e prev_shape ciclam pelos moldes abertos."""
        editor = self.root.shape_editor_view
        editor.load_shapes([self.shape_a, self.shape_b, self.shape_c])

        editor.next_shape()
        self.assertEqual(editor.active_shape_index, 1)

        editor.next_shape()
        self.assertEqual(editor.active_shape_index, 2)

        # Volta ao início
        editor.next_shape()
        self.assertEqual(editor.active_shape_index, 0)

        # Navega para trás
        editor.prev_shape()
        self.assertEqual(editor.active_shape_index, 2)

    def test_07_main_window_show_shape_editor_with_list(self):
        """7. MainWindow.show_shape_editor aceita lista de moldes e os carrega simultaneamente."""
        self.root.show_shape_editor([self.shape_a, self.shape_b])
        self.root.update()

        editor = self.root.shape_editor_view
        self.assertEqual(len(editor.open_shapes), 2)
        self.assertIn("2 moldes abertos", self.root.lbl_status_msg.cget("text"))

    def test_08_rotate_tool_drags_all_open_shapes(self):
        """8. Ferramenta Girar (rotate) com arrasto do mouse rotaciona todos os moldes abertos simultaneamente."""
        editor = self.root.shape_editor_view
        editor.load_shapes([self.shape_a, self.shape_b])
        self.root.update()

        editor.set_tool_mode("rotate")
        self.assertEqual(editor.tool_mode, "rotate")
        self.assertIn("Girar todos os 2 moldes", editor.lbl_sbar_status.cget("text"))

        class MockEvent:
            def __init__(self, x, y):
                self.x = int(round(x))
                self.y = int(round(y))

        # Centro do molde A é (50.0, 25.0)
        # Ponto inicial do clique: (150, 25) no mundo -> ângulo 0.0°
        press_sx, press_sy = editor.world_to_screen(150.0, 25.0)
        editor.on_canvas_click(MockEvent(press_sx, press_sy))
        self.assertEqual(editor.drag_target, ("rotate", 0))
        self.assertIn("Girando todos os 2 moldes", editor.lbl_sbar_status.cget("text"))

        # Arrasto para cima: (50, 125) no mundo -> ângulo 90.0°
        drag_sx, drag_sy = editor.world_to_screen(50.0, 125.0)
        editor.on_canvas_drag(MockEvent(drag_sx, drag_sy))
        status = editor.lbl_sbar_status.cget("text")
        self.assertIn("Girando todos os 2 moldes:", status)
        # Eventos usam pixels inteiros; a escala da área útil afeta o arredondamento.
        angle = float(status.rsplit(":", 1)[1].rstrip("°"))
        self.assertAlmostEqual(angle, 90.0, delta=0.2)

        # Verifica se ambos os moldes foram modificados
        shape_0 = editor.open_shapes[0]["shape"]
        shape_1 = editor.open_shapes[1]["shape"]

        # Molde A contorno ponto 0 era (0, 0), agora em torno de (50, 25) rotacionado 90° deve ir para (75, -25)
        self.assertAlmostEqual(shape_0["contour"][0]["x"], 75.0, places=0)
        self.assertAlmostEqual(shape_0["contour"][0]["y"], -25.0, places=0)

        # Molde B contorno ponto 0 era (0, 0), rotacionado pelo mesmo ângulo e centro
        self.assertAlmostEqual(shape_1["contour"][0]["x"], 75.0, places=0)
        self.assertAlmostEqual(shape_1["contour"][0]["y"], -25.0, places=0)

        # Libera o clique do mouse
        editor.on_canvas_release(MockEvent(drag_sx, drag_sy))
        self.assertIn("Rotação aplicada em todos os 2 moldes", editor.lbl_sbar_status.cget("text"))
        self.assertIsNone(editor.drag_target)

    def test_09_rotate_shape_method_all_shapes(self):
        """9. Método rotate_shape(angle, all_shapes=True) rotaciona todos os moldes abertos."""
        editor = self.root.shape_editor_view
        editor.load_shapes([self.shape_a, self.shape_b])
        self.root.update()

        orig_a_x0 = editor.open_shapes[0]["shape"]["contour"][0]["x"]
        orig_b_x0 = editor.open_shapes[1]["shape"]["contour"][0]["x"]

        editor.rotate_shape(180.0, all_shapes=True)

        new_a_x0 = editor.open_shapes[0]["shape"]["contour"][0]["x"]
        new_b_x0 = editor.open_shapes[1]["shape"]["contour"][0]["x"]

        self.assertNotEqual(orig_a_x0, new_a_x0)
        self.assertNotEqual(orig_b_x0, new_b_x0)
        self.assertIn("Todos os 2 moldes rotacionados", editor.lbl_sbar_status.cget("text"))

    def test_10_rotate_all_undo_reverts_all_shapes(self):
        """10. Ctrl+Z após rotação multi-molde desfaz a alteração em todos os moldes abertos simultaneamente."""
        editor = self.root.shape_editor_view
        editor.load_shapes([self.shape_a, self.shape_b])
        self.root.update()

        copy_a = copy.deepcopy(editor.open_shapes[0]["shape"])
        copy_b = copy.deepcopy(editor.open_shapes[1]["shape"])

        editor.rotate_shape(90.0, all_shapes=True)
        self.assertNotEqual(editor.open_shapes[0]["shape"]["contour"], copy_a["contour"])
        self.assertNotEqual(editor.open_shapes[1]["shape"]["contour"], copy_b["contour"])

        # Desfaz com undo_or_revert
        editor.undo_or_revert()
        self.assertEqual(editor.open_shapes[0]["shape"]["contour"], copy_a["contour"])
        self.assertEqual(editor.open_shapes[1]["shape"]["contour"], copy_b["contour"])
        self.assertIn("Alteração desfeita em todos os 2 moldes", editor.lbl_sbar_status.cget("text"))

    def test_11_rotate_single_when_var_rotate_all_false(self):
        """11. Quando var_rotate_all é falso, a rotação altera apenas o molde ativo."""
        editor = self.root.shape_editor_view
        editor.load_shapes([self.shape_a, self.shape_b])
        editor.var_rotate_all.set(False)
        self.root.update()

        copy_b = copy.deepcopy(editor.open_shapes[1]["shape"])

        editor.rotate_shape(90.0)
        # Molde A foi rotacionado
        self.assertNotEqual(editor.open_shapes[0]["shape"]["contour"][0]["x"], 0.0)
        # Molde B permaneceu intacto
        self.assertEqual(editor.open_shapes[1]["shape"]["contour"], copy_b["contour"])


if __name__ == "__main__":
    unittest.main()
