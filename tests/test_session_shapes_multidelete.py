"""
JobManager 2000 (Python Edition)
tests/test_session_shapes_multidelete.py - Testes de Exclusão Múltipla de Moldes na SessionView

Valida:
1. test_delete_single_shape_confirmed: Exclusão de 1 molde com confirmação
2. test_delete_multiple_shapes_confirmed: Exclusão em lote com tecla Delete / método delete_selected_shape
3. test_delete_multiple_shapes_cancelled: Cancelamento mantém todos os moldes na sessão
4. test_delete_key_returns_break: Evento <Delete> consome o evento retornando 'break'
5. test_context_menu_preserves_multiselection: Clique com botão direito não colapsa a múltipla seleção existente
"""

from __future__ import annotations

import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from database import DatabaseManager
from ui.session_view import SessionView


class TestSessionShapesMultiDelete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager()

    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            self.skipTest("Ambiente gráfico Tkinter indisponível para este teste")

        self.sample_shapes = [
            {"id": 30, "name": "323_PalAcb_25a", "size": "25a", "pairs": 16, "sequence": 1},
            {"id": 31, "name": "323_PalAcb_26a", "size": "26a", "pairs": 16, "sequence": 2},
            {"id": 32, "name": "323_PalAcb_27a", "size": "27a", "pairs": 16, "sequence": 3},
            {"id": 33, "name": "323_PalAcb_28a", "size": "28a", "pairs": 16, "sequence": 4},
            {"id": 34, "name": "323_PalAcb_29a", "size": "29a", "pairs": 16, "sequence": 5},
        ]
        self.sess_data = {
            "id": 156,
            "name": "Session #156",
            "status": "Stand by",
            "shapes": list(self.sample_shapes),
            "placed_pieces": [],
            "layouts": [],
        }

    def tearDown(self):
        try:
            if hasattr(self, "root") and self.root:
                self.root.destroy()
        except Exception:
            pass

    @patch("tkinter.messagebox.askyesno", return_value=True)
    def test_delete_single_shape_confirmed(self, mock_ask):
        """Verifica exclusão de um único molde selecionado com confirmação."""
        cb_save = MagicMock()
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db, on_add_shapes=cb_save)
        sv.set_shapes_data(self.sample_shapes)

        # Seleciona apenas o item índice 1 (323_PalAcb_26a)
        sv.tree_shapes.selection_set("1")
        sv.delete_selected_shape()

        # Modal confirmação foi exibido com nome do molde
        mock_ask.assert_called_once()
        args, kwargs = mock_ask.call_args
        self.assertEqual(args[0], "Remover Molde da Sessão")
        self.assertIn("323_PalAcb_26a", args[1])

        # Restaram 4 moldes na sessão
        self.assertEqual(len(sv.shapes_list), 4)
        remaining_names = [s["name"] for s in sv.shapes_list]
        self.assertNotIn("323_PalAcb_26a", remaining_names)
        self.assertIn("323_PalAcb_25a", remaining_names)
        self.assertIn("323_PalAcb_27a", remaining_names)

        # Sequências reatribuídas 1..4
        self.assertEqual([s["sequence"] for s in sv.shapes_list], [1, 2, 3, 4])

        # Callback de persistência disparado
        cb_save.assert_called_once()
        sv.destroy()

    @patch("tkinter.messagebox.askyesno", return_value=True)
    def test_delete_multiple_shapes_confirmed(self, mock_ask):
        """Verifica a exclusão em lote de múltiplos moldes selecionados simultaneamente."""
        cb_save = MagicMock()
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db, on_add_shapes=cb_save)
        sv.set_shapes_data(self.sample_shapes)

        # Seleciona múltiplos itens: índices 1, 2 e 4
        sv.tree_shapes.selection_set(["1", "2", "4"])
        sv.delete_selected_shape()

        mock_ask.assert_called_once()
        args, kwargs = mock_ask.call_args
        self.assertEqual(args[0], "Remover Moldes da Sessão")
        self.assertIn("3 moldes selecionados", args[1])

        # Restaram 2 moldes (índices 0 e 3 originais: 25a e 28a)
        self.assertEqual(len(sv.shapes_list), 2)
        remaining_names = [s["name"] for s in sv.shapes_list]
        self.assertEqual(remaining_names, ["323_PalAcb_25a", "323_PalAcb_28a"])

        # Sequências reatribuídas 1..2
        self.assertEqual([s["sequence"] for s in sv.shapes_list], [1, 2])

        # Callback chamado
        cb_save.assert_called_once()
        sv.destroy()

    @patch("tkinter.messagebox.askyesno", return_value=False)
    def test_delete_multiple_shapes_cancelled(self, mock_ask):
        """Verifica que cancelar a caixa de diálogo não remove nenhum molde."""
        cb_save = MagicMock()
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db, on_add_shapes=cb_save)
        sv.set_shapes_data(self.sample_shapes)

        # Seleciona todos os 5 moldes
        sv.tree_shapes.selection_set(["0", "1", "2", "3", "4"])
        sv.delete_selected_shape()

        # Nada foi removido
        self.assertEqual(len(sv.shapes_list), 5)
        cb_save.assert_not_called()
        sv.destroy()

    @patch("tkinter.messagebox.askyesno", return_value=True)
    def test_delete_key_returns_break(self, mock_ask):
        """Verifica que a função de atalho _on_tree_shapes_delete retorna 'break' consumindo o evento."""
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db)
        sv.set_shapes_data(self.sample_shapes)
        sv.tree_shapes.selection_set("0")

        res = sv._on_tree_shapes_delete()
        self.assertEqual(res, "break", "_on_tree_shapes_delete deve retornar 'break'")
        self.assertEqual(len(sv.shapes_list), 4)
        sv.destroy()

    def test_context_menu_preserves_multiselection(self):
        """Verifica que clicar com botão direito em um item da seleção múltipla não destrói a seleção."""
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db)
        sv.set_shapes_data(self.sample_shapes)

        # Usuário seleciona múltiplos moldes
        sv.tree_shapes.selection_set(["0", "1", "2"])
        initial_sel = sv.tree_shapes.selection()
        self.assertEqual(len(initial_sel), 3)

        # Simula evento de clique direito em cima da linha "1" (que já faz parte da seleção)
        event = MagicMock()
        event.widget = sv.tree_shapes
        event.y = 10
        event.x_root = 100
        event.y_root = 100

        with patch.object(sv.tree_shapes, "identify_row", return_value="1"), \
             patch("tkinter.Menu.tk_popup") as mock_popup:
            sv.show_shapes_context_menu(event)

            # A seleção múltipla continua intacta com 3 itens
            current_sel = sv.tree_shapes.selection()
            self.assertEqual(len(current_sel), 3)
            self.assertEqual(set(current_sel), {"0", "1", "2"})

        sv.destroy()


if __name__ == "__main__":
    unittest.main()
