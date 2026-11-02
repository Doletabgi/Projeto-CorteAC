"""
Testes Unitários: Criação de Sessão clicando com o botão esquerdo na pasta (duplo clique, menu, atalhos).
"""
import unittest
import tempfile
import os
import tkinter as tk
from unittest.mock import MagicMock, patch

from database import DatabaseManager
from ui.main_window import MainWindow


class TestCreateSessionLeftClick(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()
        cls.win.withdraw()
        cls.win.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.win.destroy()
        except Exception:
            pass

    def setUp(self):
        self.tmp_fd, self.tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_fd)
        self.db = DatabaseManager(self.tmp_path, backend="sqlite")
        for s in self.db.get_sessions():
            self.db.delete_session(s["id"])
        self.db.set_setting("ask_session_name", "0")
        self.win.db = self.db
        self.win.sessions = []
        self.win.current_session = None
        self.win.update()

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            try:
                os.remove(self.tmp_path)
            except Exception:
                pass

    def test_on_new_session_with_target_job(self):
        """Testa que on_new_session com target_job explícito associa a sessão à pasta informada."""
        self.win.on_new_session(target_job="PastaEspecial/Sub1")

        sessions = self.win.db.get_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["job"], "PastaEspecial/Sub1")

    def test_on_new_session_target_job_precedence_over_selection(self):
        """Testa que target_job tem precedência sobre a seleção da árvore."""
        # Simula seleção na árvore apontando para 'OutraPasta'
        item_id = self.win.tree_main.insert("", "end", text="OutraPasta", values=("job_folder", "OutraPasta"))
        self.win.tree_main.selection_set(item_id)

        # Chama com target_job='PastaPrioritaria'
        self.win.on_new_session(target_job="PastaPrioritaria")

        sessions = self.win.db.get_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["job"], "PastaPrioritaria")

    def test_double_click_on_job_folder_calls_on_new_session(self):
        """Testa que duplo clique em job_folder aciona on_new_session(target_job=folder_path)."""
        self.win.current_mode = "jobs"

        # Insere nó de pasta na árvore
        folder_item = self.win.tree_main.insert("", "end", text="ProduçãoTeste", values=("job_folder", "ProduçãoTeste"))
        self.win.tree_main.selection_set(folder_item)

        with patch.object(self.win, "on_new_session") as mock_new_sess:
            self.win.on_tree_double_click()
            mock_new_sess.assert_called_once_with(target_job="ProduçãoTeste")
            # Garante que a pasta foi aberta na árvore
            self.assertTrue(self.win.tree_main.item(folder_item, "open"))

    def test_key_return_on_tree_calls_double_click(self):
        """Testa que pressionar Enter no treeview chama on_tree_double_click."""
        with patch.object(self.win, "on_tree_double_click") as mock_dc:
            self.win.on_tree_key_return()
            mock_dc.assert_called_once()

    def test_on_tree_menu_open_job_folder(self):
        """Testa que o comando 'Abrir' no menu de contexto de uma job_folder cria a sessão."""
        folder_item = self.win.tree_main.insert("", "end", text="ProduçãoMenu", values=("job_folder", "ProduçãoMenu"))
        self.win.tree_main.selection_set(folder_item)

        with patch.object(self.win, "on_new_session") as mock_new_sess:
            self.win.on_tree_menu_open()
            mock_new_sess.assert_called_once_with(target_job="ProduçãoMenu")

    def test_dismiss_popup_menus_safeguard(self):
        """Testa que dismiss_popup_menus não fecha popups quando o evento se origina de tk.Menu."""
        dummy_menu = tk.Menu(self.win)
        fake_event = MagicMock()
        fake_event.widget = dummy_menu

        self.win._active_popup_menu = dummy_menu
        self.win.dismiss_popup_menus(fake_event)

        # Menu ativo deve ser mantido
        self.assertEqual(self.win._active_popup_menu, dummy_menu)

    def test_main_window_toolbar_and_mode_tooltips_and_hover(self):
        """Testa que os botões da toolbar e da mode bar possuem tooltips e atualizam a status bar no hover."""
        buttons = [
            self.win.btn_tb_new_session,
            self.win.btn_tb_cut,
            self.win.btn_tb_copy,
            self.win.btn_tb_paste,
            self.win.btn_tb_details,
            self.win.btn_tb_lay,
            self.win.btn_tb_shed,
            self.win.btn_shape_catalog,
            self.win.btn_tb_import_die,
            self.win.btn_tb_params,
            self.win.btn_tb_auto_nest,
            self.win.btn_tb_export_gcode,
            self.win.btn_mode_jobs,
            self.win.btn_mode_shapes,
            self.win.btn_mode_materials,
        ]
        self.win.deiconify()
        self.win.update()
        try:
            self.win.lbl_status_msg.config(text="Status Inicial")
            for btn in buttons:
                self.assertIsNotNone(btn)
                self.assertTrue(hasattr(btn, "_tooltip"))
                self.assertTrue(len(btn._tooltip.text) > 0)

                # Simula evento <Enter>
                btn.event_generate("<Enter>")
                self.win.update()
                hover_text = self.win.lbl_status_msg.cget("text")
                self.assertNotEqual(hover_text, "Status Inicial")

                # Simula evento <Leave>
                btn.event_generate("<Leave>")
                self.win.update()
                restored_text = self.win.lbl_status_msg.cget("text")
                self.assertEqual(restored_text, "Status Inicial")
        finally:
            self.win.withdraw()
            self.win.update()

    def test_status_bar_has_no_purple_leds(self):
        """Testa que os 3 LEDs ovais roxos (⬭) foram completamente removidos da barra de status."""
        for child in self.win.winfo_children():
            for sub in child.winfo_children():
                if isinstance(sub, tk.Label):
                    self.assertNotIn("⬭", sub.cget("text"))

    def test_new_session_starts_blank_without_material(self):
        """Testa que uma nova sessão criada começa completamente em branco sem material associado."""
        self.win.on_new_session(target_job="JobEmBranco")
        self.win.update()

        sessions = self.win.db.get_sessions()
        self.assertEqual(len(sessions), 1)
        sess = sessions[0]
        self.assertIsNone(sess.get("material_id"))
        self.assertIsNone(sess.get("material"))

        # Verifica na SessionView
        view = self.win.session_view
        self.assertIsNotNone(view)
        # tree_mat deve estar vazio (sem itens)
        self.assertEqual(len(view.tree_mat.get_children()), 0)
        # cb_mat_code deve estar em (unspecified)
        self.assertEqual(view.cb_mat_code.get(), "(unspecified)")


if __name__ == "__main__":
    unittest.main()

