import unittest
import tkinter as tk
from ui.shape_editor_view import ShapeEditorView


class TestShapeEditorStitching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.geometry("800x600")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.view = ShapeEditorView(self.root)
        self.view.pack(fill="both", expand=True)
        self.root.update_idletasks()

    def tearDown(self):
        self.view.destroy()

    def test_editor_renders_stitching_empty(self):
        """Verifica que shape sem stitching não causa erro e não gera itens."""
        shape = {
            "id": 101,
            "name": "Test_Empty_Stitching",
            "contour": [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100},
                {"x": 0, "y": 100}
            ],
            "holes": [],
            "stitching": []
        }
        self.view.load_shape(shape)
        self.view.redraw()
        items = self.view.canvas.find_withtag("stitching")
        self.assertEqual(len(items), 0)

    def test_editor_renders_stitching_with_data(self):
        """Verifica que shape com polylines gera itens de stitching no canvas."""
        shape = {
            "id": 102,
            "name": "Test_With_Stitching",
            "contour": [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100},
                {"x": 0, "y": 100}
            ],
            "holes": [],
            "stitching": [
                [{"x": 10, "y": 10}, {"x": 50, "y": 10}, {"x": 90, "y": 10}],
                [{"x": 10, "y": 50}, {"x": 50, "y": 50}],
                [{"x": 20, "y": 80}, {"x": 80, "y": 80}]
            ]
        }
        self.view.load_shape(shape)
        self.view.redraw()
        items = self.view.canvas.find_withtag("stitching")
        self.assertEqual(len(items), 3)

    def test_editor_stitching_color_is_magenta(self):
        """Verifica que a cor de preenchimento (fill) das costuras é magenta #ff00ff."""
        shape = {
            "id": 103,
            "name": "Test_Stitching_Color",
            "contour": [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100},
                {"x": 0, "y": 100}
            ],
            "holes": [],
            "stitching": [
                [{"x": 10, "y": 10}, {"x": 90, "y": 10}]
            ]
        }
        self.view.load_shape(shape)
        self.view.redraw()
        items = self.view.canvas.find_withtag("stitching")
        self.assertGreaterEqual(len(items), 1)
        fill_color = self.view.canvas.itemcget(items[0], "fill")
        self.assertEqual(fill_color.lower(), "#ff00ff")

    def test_editor_stitching_z_order_behind_vertices(self):
        """Verifica que stitching é desenhado antes dos vértices (z-order inferior)."""
        shape = {
            "id": 104,
            "name": "Test_Stitching_ZOrder",
            "contour": [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100},
                {"x": 0, "y": 100}
            ],
            "holes": [],
            "stitching": [
                [{"x": 10, "y": 10}, {"x": 90, "y": 10}],
                [{"x": 10, "y": 50}, {"x": 90, "y": 50}]
            ]
        }
        self.view.load_shape(shape)
        self.view.redraw()
        items_stitching = self.view.canvas.find_withtag("stitching")
        items_vertices = self.view.canvas.find_withtag("vertices")
        self.assertGreater(len(items_stitching), 0)
        self.assertGreater(len(items_vertices), 0)
        max_stitching_id = max(items_stitching)
        min_vertex_id = min(items_vertices)
        self.assertLess(max_stitching_id, min_vertex_id)

    def test_editor_rotate_tool_activation_and_ui(self):
        """Verifica presença do botão Girar, ativação do modo rotate e cursor exchange."""
        self.assertTrue(hasattr(self.view, "btn_tool_rotate"))
        self.assertEqual(self.view.btn_tool_rotate.cget("text"), "🔄 Girar")

        self.view.set_tool_mode("rotate")
        self.assertEqual(self.view.tool_mode, "rotate")
        self.assertEqual(self.view.btn_tool_rotate.cget("relief"), "sunken")
        self.assertEqual(self.view.canvas.cget("cursor"), "exchange")
        self.assertIn("Girar", self.view.lbl_sbar_status.cget("text"))

    def test_editor_interactive_rotation(self):
        """
        Tarefa 4 (Fase 6.4): Simula rotação interativa com mouse drag no ShapeEditorView.
        Valida que contorno, furos e stitching rotacionam em tempo real, o status bar
        exibe o ângulo, e um único Ctrl+Z desfaz a operação inteira.
        """
        shape = {
            "id": 201,
            "name": "Test_Rotate_Shape",
            "contour": [
                {"x": 0.0, "y": 0.0},
                {"x": 100.0, "y": 0.0},
                {"x": 100.0, "y": 100.0},
                {"x": 0.0, "y": 100.0}
            ],
            "holes": [
                {"x": 50.0, "y": 20.0, "r": 3.0}
            ],
            "stitching": [
                [{"x": 20.0, "y": 50.0}, {"x": 80.0, "y": 50.0}]
            ]
        }
        self.view.load_shape(shape)
        self.view.redraw()

        # Centro do molde (0..100, 0..100) é (50, 50)
        center_w = (50.0, 50.0)
        center_sx, center_sy = self.view.world_to_screen(50.0, 50.0)

        # 1. Ativa ferramenta Girar
        self.view.set_tool_mode("rotate")

        # 2. Simula ButtonPress-1 à direita do centro (ângulo 0 rad = 0°)
        # Ponto em mundo: (150, 50) -> ângulo inicial 0°
        press_sx, press_sy = self.view.world_to_screen(150.0, 50.0)

        class MockMouseEvent:
            def __init__(self, x, y):
                self.x = int(round(x))
                self.y = int(round(y))

        self.view.on_canvas_click(MockMouseEvent(press_sx, press_sy))
        self.assertEqual(self.view.drag_target, ("rotate", 0))
        self.assertEqual(self.view.lbl_sbar_status.cget("text"), "Rotação: 0.0°")

        # 3. Simula B1-Motion diretamente acima do centro (ângulo 90° no mundo)
        # Ponto em mundo: (50, 150) -> ângulo pi/2 rad = 90°
        drag_sx, drag_sy = self.view.world_to_screen(50.0, 150.0)
        self.view.on_canvas_drag(MockMouseEvent(drag_sx, drag_sy))

        # Status bar durante arrasto
        self.assertIn("Rotação: 90.0°", self.view.lbl_sbar_status.cget("text"))

        # Ponto (100, 50) inicial rotacionado em 90° em torno de (50, 50) deve ir para (50, 100)
        # O furo em (50, 20) deve ir para (50 - (20-50)*0, 50 + (20-50)*1) = (80, 50)
        # Verificamos que os pontos realmente mudaram
        cur_contour = self.view.shape["contour"]
        self.assertNotEqual(cur_contour[0]["x"], 0.0)

        # 4. Simula ButtonRelease-1
        self.view.on_canvas_release(MockMouseEvent(drag_sx, drag_sy))
        self.assertIn("Rotação aplicada: 90.0°", self.view.lbl_sbar_status.cget("text"))
        self.assertIsNone(self.view.drag_target)

        # Furo e stitching devem ter sido rotacionados
        rotated_hole = self.view.shape["holes"][0]
        self.assertAlmostEqual(rotated_hole["x"], 80.0, delta=0.5)
        self.assertAlmostEqual(rotated_hole["y"], 50.0, delta=0.5)

        rotated_stitch = self.view.shape["stitching"][0]
        # Ponto de costura (20, 50) -> rotacionado 90° em torno de (50, 50) -> (50, 20)
        self.assertAlmostEqual(rotated_stitch[0]["x"], 50.0, delta=0.5)
        self.assertAlmostEqual(rotated_stitch[0]["y"], 20.0, delta=0.5)

        # 5. Validação de Undo (Ctrl+Z): reverte toda a rotação em 1 único passo
        self.assertEqual(len(self.view.undo_stack), 1)
        self.view.undo_or_revert()

        # Molde restaurado ao original exato
        restored_contour = self.view.shape["contour"]
        self.assertEqual(restored_contour[0], {"x": 0.0, "y": 0.0})
        self.assertEqual(restored_contour[1], {"x": 100.0, "y": 0.0})
        self.assertEqual(self.view.shape["holes"][0], {"x": 50.0, "y": 20.0, "r": 3.0})
        self.assertEqual(self.view.shape["stitching"][0][0], {"x": 20.0, "y": 50.0})
        self.assertIn("Alteração desfeita", self.view.lbl_sbar_status.cget("text"))

    def test_editor_programmatic_rotate_shape(self):
        """Valida que o método rotate_shape rotaciona contorno, furos e costuras e suporta undo."""
        shape = {
            "id": 202,
            "name": "Test_Rotate_Method",
            "contour": [
                {"x": 0.0, "y": 0.0},
                {"x": 200.0, "y": 0.0},
                {"x": 200.0, "y": 100.0},
                {"x": 0.0, "y": 100.0}
            ],
            "holes": [
                {"x": 100.0, "y": 50.0, "r": 2.5}
            ],
            "stitching": [
                [{"x": 50.0, "y": 50.0}, {"x": 150.0, "y": 50.0}]
            ]
        }
        self.view.load_shape(shape)
        # Centro é (100, 50). Rotaciona 180°
        self.view.rotate_shape(180.0)

        # O furo no centro (100, 50) deve permanecer em (100, 50)
        self.assertAlmostEqual(self.view.shape["holes"][0]["x"], 100.0, delta=0.5)
        self.assertAlmostEqual(self.view.shape["holes"][0]["y"], 50.0, delta=0.5)

        # Contorno rotacionado 180°: (0, 0) em torno de (100, 50) vai para (200, 100)
        self.assertAlmostEqual(self.view.shape["contour"][0]["x"], 200.0, delta=0.5)
        self.assertAlmostEqual(self.view.shape["contour"][0]["y"], 100.0, delta=0.5)

        # Undo desfaz
        self.view.undo_or_revert()
        self.assertEqual(self.view.shape["contour"][0]["x"], 0.0)
        self.assertEqual(self.view.shape["contour"][0]["y"], 0.0)


if __name__ == "__main__":
    unittest.main()
