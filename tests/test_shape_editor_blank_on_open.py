"""
tests/test_shape_editor_blank_on_open.py

Validação da inicialização do Shape Editor:
1. Ao abrir sem argumentos (menu Ferramentas, Janela, atalho da toolbar), abre 100% em branco:
   - Contorno vazio (contour = [])
   - Nome vazio ("") e campo de texto vazio
   - Título exibe [Novo Molde]
   - Geometria destravada para desenho
   - Métricas zeradas (0.0 mm, 0.00 dm²)
2. Ao abrir com ID ou molde específico, carrega normalmente a peça.
3. Método load_empty_shape limpa o canvas e reseta estado.
4. Salvar uma peça criada a partir da tela em branco cria o molde no banco de dados.
"""
import unittest
import tkinter as tk
from unittest.mock import MagicMock, patch

from ui.main_window import MainWindow
from ui.shape_editor_view import ShapeEditorView


class TestShapeEditorBlankOnOpen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()
        cls.win.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.win.destroy()
        except Exception:
            pass

    def setUp(self):
        self.win.update()

    def tearDown(self):
        try:
            if self.win.shape_editor_view in self.win.open_windows:
                self.win.close_window(self.win.shape_editor_view)
                self.win.update()
        except Exception:
            pass

    def test_01_show_shape_editor_no_args_opens_blank(self):
        """1. show_shape_editor() sem argumentos abre completamente em branco sem peças pré-carregadas."""
        self.win.show_shape_editor()
        self.win.update()

        editor = self.win.shape_editor_view
        self.assertEqual(len(editor.shape.get("contour", [])), 0)
        self.assertEqual(editor.shape.get("name", ""), "")
        self.assertEqual(editor.entry_name.get(), "")
        self.assertIn("Novo Molde", editor.lbl_title.cget("text"))
        self.assertFalse(editor.geometry_locked.get())
        self.assertIn("Novo molde em branco", self.win.lbl_status_msg.cget("text"))

        # Métricas devem estar zeradas
        self.assertIn("0.0 mm", editor.lbl_dim_w.cget("text"))
        self.assertIn("0.0 mm", editor.lbl_dim_h.cget("text"))
        self.assertIn("0.00 dm²", editor.lbl_area_gross.cget("text"))
        self.assertIn("Vértices: 0", editor.lbl_counts.cget("text"))

    def test_02_show_shape_editor_with_specific_shape_loads_normally(self):
        """2. show_shape_editor com ID específico carrega a peça normalmente."""
        shape_27 = self.win.db.get_shape(27)
        self.assertIsNotNone(shape_27)
        self.win.show_shape_editor(shape_27["id"])
        self.win.update()

        editor = self.win.shape_editor_view
        self.assertGreater(len(editor.shape.get("contour", [])), 0)
        self.assertEqual(editor.shape.get("name"), shape_27["name"])
        self.assertEqual(editor.entry_name.get(), shape_27["name"])
        self.assertIn(shape_27["name"], editor.lbl_title.cget("text"))

    def test_03_load_empty_shape_resets_canvas(self):
        """3. load_empty_shape() reseta o editor com prancheta em branco."""
        # Carrega primeiro uma peça existente
        shape_27 = self.win.db.get_shape(27)
        editor = self.win.shape_editor_view
        editor.load_shape(shape_27)
        self.win.update()
        self.assertGreater(len(editor.shape.get("contour", [])), 0)

        # Chama load_empty_shape
        editor.load_empty_shape()
        self.win.update()

        self.assertEqual(len(editor.shape.get("contour", [])), 0)
        self.assertEqual(editor.shape.get("name", ""), "")
        self.assertEqual(editor.entry_name.get(), "")
        self.assertIn("Novo Molde", editor.lbl_title.cget("text"))
        self.assertFalse(editor.geometry_locked.get())
        self.assertIn("0.0 mm", editor.lbl_dim_w.cget("text"))

    def test_04_save_new_shape_persists_in_database(self):
        """4. Desenhar e salvar uma peça no editor em branco cria o molde no banco."""
        self.win.show_shape_editor()
        self.win.update()

        editor = self.win.shape_editor_view
        test_name = "Molde_Teste_Novo_Auto"

        # Simula desenho de 4 pontos
        editor.shape["contour"] = [
            {"x": 0.0, "y": 0.0},
            {"x": 100.0, "y": 0.0},
            {"x": 100.0, "y": 80.0},
            {"x": 0.0, "y": 80.0}
        ]
        editor.entry_name.delete(0, tk.END)
        editor.entry_name.insert(0, test_name)

        # Salva
        with patch("tkinter.messagebox.showinfo"):
            editor.save_changes()

        created_id = editor.shape.get("id")
        self.assertIsNotNone(created_id)
        saved_db = self.win.db.get_shape(created_id)
        self.assertIsNotNone(saved_db)
        self.assertEqual(saved_db["name"], test_name)
        self.assertEqual(len(saved_db["contour"]), 4)


if __name__ == "__main__":
    unittest.main()
