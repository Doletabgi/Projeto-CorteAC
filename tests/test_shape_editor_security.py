"""
tests/test_shape_editor_security.py

Testes automatizados para a Fase 6.4:
1. Modo Seguro (Trava de Geometria Lock/Unlock):
   - Inicia bloqueado por default (geometry_locked=True)
   - Clique em vértice seleciona para inspeção mas bloqueia arraste (drag_target=None)
   - Arraste com geometria bloqueada não altera coordenadas
   - Liberação de geometria (toggle_geometry_lock) permite arrastar vértices
   - Bloqueio impede adição de pontos, furos, exclusão e alteração manual por Entry
2. Rotação Interativa:
   - Ferramenta rotate ativa cursor exchange e botão sunken
   - Arraste rotaciona contorno, furos e costuras
   - Reversão (Ctrl+Z) desfaz a rotação perfeitamente em 1 passo
"""
import copy
import math
import tkinter as tk
import unittest

from ui.shape_editor_view import ShapeEditorView


class DummyEvent:
    def __init__(self, x, y, x_root=0, y_root=0, delta=0):
        self.x = x
        self.y = y
        self.x_root = x_root
        self.y_root = y_root
        self.delta = delta


class TestShapeEditorSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.geometry("1024x768")
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.test_shape = {
            "id": 99,
            "name": "Peca_Teste_Seguranca",
            "contour": [
                {"x": 10.0, "y": 10.0},
                {"x": 110.0, "y": 10.0},
                {"x": 110.0, "y": 60.0},
                {"x": 10.0, "y": 60.0}
            ],
            "holes": [
                {"x": 30.0, "y": 30.0, "r": 3.0}
            ],
            "stitching": [
                [{"x": 15.0, "y": 15.0}, {"x": 105.0, "y": 15.0}]
            ]
        }
        self.editor = ShapeEditorView(self.root, shape_data=self.test_shape)
        self.editor.pack(fill="both", expand=True)
        self.root.update()

    def tearDown(self):
        try:
            self.editor.destroy()
            self.root.update()
        except Exception:
            pass

    def test_01_geometry_locked_by_default(self):
        """Verifica se o editor inicia em Modo Seguro com a geometria travada."""
        self.assertTrue(self.editor.geometry_locked.get())
        self.assertIn("Editar Geometria", self.editor.btn_lock.cget("text"))
        self.assertEqual(self.editor.btn_lock.cget("relief"), "raised")
        self.assertIn("Modo Seguro", self.editor.lbl_sbar_status.cget("text"))

    def test_02_geometry_lock_prevents_vertex_drag(self):
        """Vértice pode ser selecionado para inspeção mas arraste é bloqueado."""
        self.assertTrue(self.editor.geometry_locked.get())
        pt0 = self.editor.shape["contour"][0]
        orig_x, orig_y = pt0["x"], pt0["y"]

        # Converte ponto 0 para coordenada de tela
        sx, sy = self.editor.world_to_screen(orig_x, orig_y)

        # Clica no vértice 0
        click_evt = DummyEvent(int(round(sx)), int(round(sy)))
        self.editor.on_canvas_click(click_evt)

        # Deve estar selecionado para inspecionar no painel lateral
        self.assertEqual(self.editor.selected_vertex_idx, 0)
        # Mas drag_target deve ser None
        self.assertIsNone(self.editor.drag_target)
        self.assertIn("Geometria bloqueada", self.editor.lbl_sbar_status.cget("text"))

        # Simula tentativa de arrastar o mouse
        drag_evt = DummyEvent(int(round(sx + 80)), int(round(sy + 80)))
        self.editor.on_canvas_drag(drag_evt)

        # Coordenadas do vértice DEVEM permanecer inalteradas
        pt0_after = self.editor.shape["contour"][0]
        self.assertEqual(pt0_after["x"], orig_x)
        self.assertEqual(pt0_after["y"], orig_y)

    def test_03_geometry_unlock_allows_vertex_drag(self):
        """Ao destravar a geometria, vértices podem ser movidos livremente."""
        # Destrava a geometria
        self.editor.toggle_geometry_lock()
        self.assertFalse(self.editor.geometry_locked.get())
        self.assertIn("Geometria Liberada", self.editor.btn_lock.cget("text"))
        self.assertEqual(self.editor.btn_lock.cget("relief"), "sunken")

        pt0 = self.editor.shape["contour"][0]
        orig_x, orig_y = pt0["x"], pt0["y"]
        sx, sy = self.editor.world_to_screen(orig_x, orig_y)

        # Clica no vértice 0
        click_evt = DummyEvent(int(round(sx)), int(round(sy)))
        self.editor.on_canvas_click(click_evt)

        # Agora drag_target deve ser ("vertex", 0)
        self.assertEqual(self.editor.drag_target, ("vertex", 0))

        # Arrasta o vértice para nova posição
        new_sx, new_sy = sx + 50, sy + 30
        drag_evt = DummyEvent(int(round(new_sx)), int(round(new_sy)))
        self.editor.on_canvas_drag(drag_evt)

        # As coordenadas do vértice no contorno devem ter mudado
        pt0_after = self.editor.shape["contour"][0]
        self.assertNotEqual(pt0_after["x"], orig_x)
        self.assertNotEqual(pt0_after["y"], orig_y)

        # Solta o mouse e garante que foi registrado no histórico
        self.editor.on_canvas_release(drag_evt)
        self.assertGreater(len(self.editor.undo_stack), 0)

        # Desfaz alteração
        self.editor.undo_or_revert()
        self.assertAlmostEqual(self.editor.shape["contour"][0]["x"], orig_x, places=1)
        self.assertAlmostEqual(self.editor.shape["contour"][0]["y"], orig_y, places=1)

    def test_04_geometry_lock_prevents_add_and_delete(self):
        """Bloqueio impede adição de pontos, furos, exclusão e alteração por campos de texto."""
        self.assertTrue(self.editor.geometry_locked.get())
        initial_verts_count = len(self.editor.shape["contour"])
        initial_holes_count = len(self.editor.shape["holes"])

        # 1. Tentativa de adicionar ponto
        self.editor.set_tool_mode("add_point")
        self.assertIn("Geometria bloqueada", self.editor.lbl_sbar_status.cget("text"))
        self.editor.on_canvas_click(DummyEvent(200, 200))
        self.assertEqual(len(self.editor.shape["contour"]), initial_verts_count)
        self.assertIn("Geometria bloqueada", self.editor.lbl_sbar_status.cget("text"))

        # 2. Tentativa de adicionar furo
        self.editor.set_tool_mode("add_hole")
        self.assertIn("Geometria bloqueada", self.editor.lbl_sbar_status.cget("text"))
        self.editor.on_canvas_click(DummyEvent(200, 200))
        self.assertEqual(len(self.editor.shape["holes"]), initial_holes_count)
        self.assertIn("Geometria bloqueada", self.editor.lbl_sbar_status.cget("text"))

        # 3. Tentativa de excluir vértice selecionado
        self.editor.set_tool_mode("select")
        self.editor.selected_vertex_idx = 1
        self.editor.delete_selected()
        self.assertEqual(len(self.editor.shape["contour"]), initial_verts_count)
        self.assertIn("Geometria bloqueada", self.editor.lbl_sbar_status.cget("text"))

        # 4. Tentativa de alterar coordenada via entry_vx/vy
        self.editor.selected_vertex_idx = 0
        orig_x = self.editor.shape["contour"][0]["x"]
        self.editor.entry_vx.delete(0, tk.END)
        self.editor.entry_vx.insert(0, "999.0")
        self.editor.on_vertex_entry_change()
        self.assertEqual(self.editor.shape["contour"][0]["x"], orig_x)
        self.assertIn("Geometria bloqueada", self.editor.lbl_sbar_status.cget("text"))

        # 5. Tentativa via menu de contexto
        self.editor.ctx_pos = (50.0, 50.0)
        self.editor.ctx_add_vertex()
        self.assertEqual(len(self.editor.shape["contour"]), initial_verts_count)
        self.editor.ctx_add_hole()
        self.assertEqual(len(self.editor.shape["holes"]), initial_holes_count)

    def test_05_rotate_tool_changes_contour_angle_and_undo(self):
        """Ferramenta de rotação gira o molde ao arrastar o mouse e suporta Ctrl+Z."""
        orig_contour = copy.deepcopy(self.editor.shape["contour"])

        # Ativa ferramenta de rotação
        self.editor.set_tool_mode("rotate")
        self.assertEqual(self.editor.canvas.cget("cursor"), "exchange")
        self.assertEqual(self.editor.btn_tool_rotate.cget("relief"), "sunken")

        # Clica para iniciar rotação
        click_evt = DummyEvent(400, 300)
        self.editor.on_canvas_click(click_evt)
        self.assertEqual(self.editor.drag_target, ("rotate", 0))

        # Arrasta o mouse gerando rotação
        drag_evt = DummyEvent(450, 400)
        self.editor.on_canvas_drag(drag_evt)

        # O contorno deve ter rotacionado
        new_contour = self.editor.shape["contour"]
        coords_changed = any(
            abs(new_contour[i]["x"] - orig_contour[i]["x"]) > 0.1 or
            abs(new_contour[i]["y"] - orig_contour[i]["y"]) > 0.1
            for i in range(len(new_contour))
        )
        self.assertTrue(coords_changed)
        self.assertIn("Rotação:", self.editor.lbl_sbar_status.cget("text"))

        # Finaliza rotação
        self.editor.on_canvas_release(drag_evt)
        self.assertIn("Rotação aplicada:", self.editor.lbl_sbar_status.cget("text"))

        # Desfaz com Ctrl+Z
        self.editor.undo_or_revert()
        reverted_contour = self.editor.shape["contour"]
        for i in range(len(reverted_contour)):
            self.assertAlmostEqual(reverted_contour[i]["x"], orig_contour[i]["x"], places=1)
            self.assertAlmostEqual(reverted_contour[i]["y"], orig_contour[i]["y"], places=1)


if __name__ == "__main__":
    unittest.main()
