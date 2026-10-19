"""
Testes automatizados para remoção de material na sessão via tecla Delete / botão / menu:
- Remoção liberada quando layout NÃO está calculado
- Bloqueio estrito quando layout ESTÁ calculado
- Desbloqueio para troca após limpar/refazer o layout ("refazer aí sim libera")
- Prevenção de troca via combobox ou arrastar e soltar com layout calculado
"""

import unittest
from unittest.mock import patch, MagicMock
import tkinter as tk

from ui.session_view import SessionView
from database import DatabaseManager


class TestSessionMaterialDelete(unittest.TestCase):
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
        self.mock_db = MagicMock(spec=DatabaseManager)
        self.mock_material_cb = MagicMock()

        self.sample_material = {
            "id": 1,
            "name": "SINT-LOGAM 1.4 PRETO",
            "code": "SINT-LOGAM 1.4 PRETO",
            "width_mm": 1380.0,
            "height_mm": 2990.0,
            "layers": 2,
            "thickness": 0.0,
            "gap": 1.0,
            "quantity": 0,
            "type": "como placa"
        }

        self.session_dict = {
            "id": 10,
            "name": "Sessão #10",
            "status": "Open",
            "material_id": 1,
            "material": dict(self.sample_material),
            "placed_pieces": [],
            "yield_percent": 0.0,
            "cutting_time_sec": 0.0,
            "shapes": []
        }

        self.view = SessionView(
            self.root,
            session_data=self.session_dict,
            db=self.mock_db,
            on_material_change=self.mock_material_cb
        )
        self.view.set_materials_list([self.sample_material, {"id": 2, "name": "COURO-BOVINO"}])
        self.view.set_material_data(self.sample_material)

    def tearDown(self):
        if hasattr(self, "view") and self.view:
            try:
                self.view.destroy()
            except Exception:
                pass

    def test_initial_material_displayed_in_tree_mat(self):
        """Verifica se o material da sessão é exibido corretamente na tabela tree_mat."""
        items = self.view.tree_mat.get_children()
        self.assertEqual(len(items), 1)
        vals = self.view.tree_mat.item(items[0], "values")
        self.assertEqual(vals[1], "como placa")
        self.assertEqual(vals[2], "SINT-LOGAM 1.4 PRETO")
        self.assertEqual(vals[3], "1,38")
        self.assertEqual(vals[4], "2,99")

    @patch("tkinter.messagebox.askyesno", return_value=True)
    def test_remove_material_when_layout_not_calculated(self, mock_ask):
        """Valida que o material é removido com sucesso via remove_session_material quando não há layout calculado."""
        self.assertFalse(self.view.has_calculated_layout())

        # Executa remoção (mesma ação disparada pela tecla Delete)
        res = self.view.remove_session_material()
        self.assertEqual(res, "break")

        # Confirma que a caixa de confirmação foi exibida
        mock_ask.assert_called_once()

        # Material na sessão foi limpo
        self.assertIsNone(self.view.session_data.get("material"))
        self.assertIsNone(self.view.session_data.get("material_id"))

        # tree_mat ficou vazia
        self.assertEqual(len(self.view.tree_mat.get_children()), 0)

        # Combobox foi resetado para (unspecified)
        self.assertEqual(self.view.cb_mat_code.get(), "(unspecified)")

        # Persistência no banco foi chamada com clear_material=True
        self.mock_db.update_session.assert_called_with(10, material_id=None, clear_material=True)

        # Callback para a MainWindow foi acionado com None
        self.mock_material_cb.assert_called_with(None)

    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.askyesno")
    def test_cannot_remove_material_when_layout_is_calculated(self, mock_ask, mock_warn):
        """Valida que a remoção do material é terminantemente bloqueada se o layout estiver calculado."""
        # Configura layout calculado com peças posicionadas
        self.view.session_data["placed_pieces"] = [{"id": 1, "name": "Sola_41", "x": 100, "y": 200}]
        self.assertTrue(self.view.has_calculated_layout())

        # Tenta remover o material
        res = self.view.remove_session_material()
        self.assertEqual(res, "break")

        # Alerta exibido ao operador informando o bloqueio
        mock_warn.assert_called_once()
        self.assertIn("Material Bloqueado", mock_warn.call_args[0][0])

        # Confirmação de exclusão NUNCA deve ser chamada
        mock_ask.assert_not_called()

        # Material e tabela permanecem intactos
        self.assertIsNotNone(self.view.session_data.get("material"))
        self.assertEqual(len(self.view.tree_mat.get_children()), 1)

    @patch("tkinter.messagebox.showwarning")
    def test_cannot_change_material_combobox_when_layout_is_calculated(self, mock_warn):
        """Valida que trocar o material na combobox é bloqueado e revertido se o layout estiver calculado."""
        self.view.session_data["placed_pieces"] = [{"id": 1, "name": "Sola_41"}]
        self.assertTrue(self.view.has_calculated_layout())

        # Tenta alterar a combobox para outro material
        self.view.cb_mat_code.set("2 - COURO-BOVINO")
        self.view.on_material_code_selected()

        # Alerta exibido e combobox revertida
        mock_warn.assert_called_once()
        self.assertEqual(self.view.cb_mat_code.get(), "1 - SINT-LOGAM 1.4 PRETO")
        self.mock_material_cb.assert_not_called()

    @patch("tkinter.messagebox.askyesno", return_value=True)
    @patch("tkinter.messagebox.showwarning")
    def test_clearing_layout_unlocks_material_removal_and_change(self, mock_warn, mock_ask):
        """
        Valida o fluxo completo descrito pelo usuário:
        1. Com layout calculado, remoção é bloqueada
        2. Limpa o layout ('refazer')
        3. Agora 'aí sim libera' a remoção do material via Delete
        """
        # 1. Layout calculado -> Bloqueado
        self.view.session_data["placed_pieces"] = [{"id": 1, "name": "Sola_41"}]
        self.view.remove_session_material()
        mock_warn.assert_called_once()
        self.assertIsNotNone(self.view.session_data.get("material"))

        # 2. Usuário limpa o layout (refazer)
        self.view.clear_current_layout()
        self.assertEqual(self.view.session_data["placed_pieces"], [])
        self.assertFalse(self.view.has_calculated_layout())

        # 3. Aí sim libera a remoção com o Delete
        self.view.remove_session_material()
        self.assertIsNone(self.view.session_data.get("material"))
        self.assertEqual(len(self.view.tree_mat.get_children()), 0)
        self.assertEqual(self.view.cb_mat_code.get(), "(unspecified)")

    @patch("tkinter.messagebox.askyesno", return_value=True)
    def test_delete_key_event_on_tree_mat_triggers_removal(self, mock_ask):
        """Valida que o evento de teclado <Delete> no tree_mat dispara a remoção do material."""
        self.assertFalse(self.view.has_calculated_layout())

        try:
            self.root.deiconify()
            self.view.pack(fill="both", expand=True)
            self.root.update()
            # Seleciona a aba Materiais para que tree_mat esteja visível e receba eventos de foco
            self.view.notebook.select(self.view.tab_mat)
            self.root.update()
            self.view.tree_mat.focus_set()
            self.root.update()

            # Dispara tecla Delete no tree_mat
            self.view.tree_mat.event_generate("<Delete>")
            self.root.update()

            self.assertIsNone(self.view.session_data.get("material"))
            self.assertEqual(len(self.view.tree_mat.get_children()), 0)
        finally:
            self.root.withdraw()


if __name__ == "__main__":
    unittest.main()
