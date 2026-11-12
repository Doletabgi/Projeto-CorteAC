"""Testes para a opção 'Salvar Sessão para Máquina' no menu de contexto da sessão."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
from tkinter import ttk

from ui.main_window import MainWindow
from ui.session_view import SessionView


class DummyBtn:
    def config(self, **kwargs):
        pass


class FakeEvent:
    def __init__(self, x=10, y=10, x_root=100, y_root=100):
        self.x = x
        self.y = y
        self.x_root = x_root
        self.y_root = y_root


class TestSessionContextMenuExport(unittest.TestCase):
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
            self.skipTest("Tkinter indisponível em ambiente headless")

    def test_tree_menu_contains_export_session_to_machine(self):
        """Verifica que o menu de contexto do nó 'session' possui a opção 'Salvar Sessão para Máquina'."""
        fake = object.__new__(MainWindow)
        fake.current_mode = "jobs"
        fake.tree_main = ttk.Treeview(self.root)
        fake.tree_menu = tk.Menu(self.root, tearoff=0)
        fake.batch_checked_sessions = set()
        fake.show_popup_menu = MagicMock()
        fake.on_tree_menu_open = MagicMock()
        fake.on_new_session = MagicMock()
        fake.on_create_order = MagicMock()
        fake.on_create_production = MagicMock()
        fake.on_create_job_subfolder_menu_action = MagicMock()
        fake.on_move_session_to_job_folder = MagicMock()
        fake.on_rename_tree_item = MagicMock()
        fake.on_delete_tree_item = MagicMock()
        fake.on_publish = MagicMock()
        fake.on_export_xml = MagicMock()
        fake.on_import_xml = MagicMock()
        fake.on_import_die = MagicMock()
        fake.show_layout_editor = MagicMock()
        fake.on_export_session_to_machine = MagicMock()

        # Insere nó de sessão
        item_id = fake.tree_main.insert("", "end", text="Sessão #100", values=("session", "100"))
        fake.tree_main.selection_set(item_id)

        # Dispara menu de contexto
        MainWindow.show_tree_context_menu(fake, FakeEvent())

        # Procura o comando "📤 Salvar Sessão para Máquina..." no menu
        menu_labels = []
        num_items = fake.tree_menu.index("end")
        if num_items is not None:
            for idx in range(num_items + 1):
                try:
                    menu_labels.append(fake.tree_menu.entrycget(idx, "label"))
                except Exception:
                    pass

        self.assertIn("📤 Salvar Sessão para Máquina...", menu_labels)
        idx = menu_labels.index("📤 Salvar Sessão para Máquina...")
        # Deve estar logo abaixo de 'Abrir'
        self.assertEqual(menu_labels[idx - 1], "Abrir")

        # Invoca o comando e verifica se repassa sess_id = 100
        fake.tree_menu.invoke(idx)
        fake.on_export_session_to_machine.assert_called_once_with(100)

    def test_on_export_session_to_machine_switches_session(self):
        """Verifica que on_export_session_to_machine alterna de sessão se session_id for especificado."""
        fake = object.__new__(MainWindow)
        fake.sessions = [
            {"id": 10, "name": "Sessão 10", "layouts": []},
            {"id": 20, "name": "Sessão 20", "layouts": [{"pieces": [1]}], "placed_pieces": [1]},
        ]
        fake.current_session = fake.sessions[0]
        fake.switch_to_session = MagicMock()
        fake.layout_editor_view = MagicMock()
        fake.show_layout_editor = MagicMock()
        fake.db = None

        # Simula que switch_to_session atualiza current_session
        def do_switch(sid):
            fake.current_session = next(s for s in fake.sessions if s["id"] == sid)
        fake.switch_to_session.side_effect = do_switch

        MainWindow.on_export_session_to_machine(fake, session_id=20)

        fake.switch_to_session.assert_called_once_with(20)
        fake.show_layout_editor.assert_called_once()
        fake.layout_editor_view.export_session_to_machine.assert_called_once()

    def test_on_export_session_to_machine_warns_no_layouts(self):
        """Verifica aviso se a sessão não tiver layouts."""
        fake = object.__new__(MainWindow)
        fake.sessions = [{"id": 30, "name": "Sessão 30", "layouts": [], "placed_pieces": []}]
        fake.current_session = fake.sessions[0]
        fake.layout_editor_view = MagicMock()
        fake.db = None

        with patch("ui.main_window.messagebox.showwarning") as warn_mock:
            MainWindow.on_export_session_to_machine(fake, session_id=30)
            warn_mock.assert_called_once()
            self.assertIn("não tem layout", warn_mock.call_args[0][1].lower())

        fake.layout_editor_view.export_session_to_machine.assert_not_called()

    def test_session_view_lay_menu_and_export_method(self):
        """Verifica comando 'Salvar Sessão para Máquina' na tabela de layouts da SessionView."""
        exported_sids = []
        sv = SessionView(
            self.root,
            session_data={"id": 88, "status": "Stand by"},
            on_export_machine=lambda sid: exported_sids.append(sid),
        )

        menu_labels = []
        num_items = sv.lay_menu.index("end")
        if num_items is not None:
            for idx in range(num_items + 1):
                try:
                    menu_labels.append(sv.lay_menu.entrycget(idx, "label"))
                except Exception:
                    pass

        self.assertIn("Salvar Sessão para Máquina...", menu_labels)
        idx = menu_labels.index("Salvar Sessão para Máquina...")

        self.assertTrue(sv.lay_menu.entrycget(idx, "image"))

        # Dispara via invoke
        sv.lay_menu.invoke(idx)
        self.assertEqual(exported_sids, [88])

        sv.destroy()

    def test_job_folder_menu_contains_export_folder_to_machine(self):
        """Verifica que o menu de contexto de job_folder possui a opção 'Salvar Pasta ... para Máquina'."""
        fake = object.__new__(MainWindow)
        fake.current_mode = "jobs"
        fake.tree_main = ttk.Treeview(self.root)
        fake.tree_menu = tk.Menu(self.root, tearoff=0)
        fake.show_popup_menu = MagicMock()
        fake.on_tree_menu_open = MagicMock()
        fake.on_create_job_subfolder = MagicMock()
        fake.on_create_production = MagicMock()
        fake.on_new_session = MagicMock()
        fake.on_create_order = MagicMock()
        fake.on_rename_tree_item = MagicMock()
        fake.on_delete_tree_item = MagicMock()
        fake.on_publish = MagicMock()
        fake.on_export_xml = MagicMock()
        fake.on_import_xml = MagicMock()
        fake.on_import_die = MagicMock()
        fake.show_layout_editor = MagicMock()
        fake.set_folder_batch_selection = MagicMock()
        fake.on_export_job_folder_to_machine = MagicMock()

        item_id = fake.tree_main.insert("", "end", text="Pasta A", values=("job_folder", "ProducaoA"))
        fake.tree_main.selection_set(item_id)

        MainWindow.show_tree_context_menu(fake, FakeEvent())

        menu_labels = []
        num_items = fake.tree_menu.index("end")
        if num_items is not None:
            for idx in range(num_items + 1):
                try:
                    menu_labels.append(fake.tree_menu.entrycget(idx, "label"))
                except Exception:
                    pass

        expected_label = "📤 Salvar Pasta 'ProducaoA' para Máquina..."
        self.assertIn(expected_label, menu_labels)
        idx = menu_labels.index(expected_label)
        self.assertEqual(menu_labels[idx - 1], "Abrir")

        fake.tree_menu.invoke(idx)
        fake.on_export_job_folder_to_machine.assert_called_once_with("ProducaoA")

    def test_on_export_job_folder_to_machine_flow(self):
        """Verifica fluxo completo de exportação de pasta com múltiplas sessões."""
        from cad.project_packager import ExportResult
        fake = object.__new__(MainWindow)
        fake.sessions = [
            {"id": 1, "job": "Lote_1", "layouts": [{"name": "lay0000"}]},
            {"id": 2, "job": "Lote_1", "layouts": [{"name": "lay0000"}, {"name": "lay0001"}]},
            {"id": 3, "job": "Lote_1", "layouts": []},  # Sem layout, deve ser ignorada
            {"id": 4, "job": "Outro_Lote", "layouts": [{"name": "lay0000"}]},  # Outro lote
        ]
        fake.db = MagicMock()
        fake.db.get_setting.return_value = "/tmp"
        fake.db.get_session_layouts.return_value = []
        fake.save_current_session_state = MagicMock()
        fake._machine_shapes_roots = MagicMock(return_value=[])
        fake.lbl_status_msg = DummyBtn()

        res1 = MagicMock(session_id=1, session_code="SESS-1", session_dir="/tmp/SESS-1", layouts=["lay0000"], dies=[], missing=[])
        res2 = MagicMock(session_id=2, session_code="SESS-2", session_dir="/tmp/SESS-2", layouts=["lay0000", "lay0001"], dies=[], missing=[])

        with patch("ui.main_window.filedialog.askdirectory", return_value="/tmp/export_target"), \
             patch("ui.main_window.export_session", side_effect=[res1, res2]) as mock_export, \
             patch("ui.main_window.messagebox.showwarning") as mock_warn, \
             patch("ui.main_window.messagebox.showerror") as mock_err, \
             patch("ui.main_window.messagebox.showinfo") as mock_info:
            MainWindow.on_export_job_folder_to_machine(fake, "Lote_1")

            self.assertEqual(mock_export.call_count, 2)
            mock_info.assert_called_once()
            dialog_msg = mock_info.call_args[0][1]
            self.assertIn("Sessões exportadas: 2 de 2", dialog_msg)
            self.assertIn("Placas (.lay) salvas: 3", dialog_msg)

    def test_on_export_job_folder_warns_empty_folder(self):
        """Verifica aviso quando a pasta não tem nenhuma sessão."""
        fake = object.__new__(MainWindow)
        fake.sessions = []
        with patch("ui.main_window.messagebox.showinfo") as mock_info:
            MainWindow.on_export_job_folder_to_machine(fake, "Vazia")
            mock_info.assert_called_once()
            self.assertIn("Nenhuma sessão encontrada", mock_info.call_args[0][1])

    def test_on_export_job_folder_warns_no_layouts(self):
        """Verifica aviso quando as sessões da pasta não possuem layouts."""
        fake = object.__new__(MainWindow)
        fake.sessions = [{"id": 1, "job": "Sem_Layout", "layouts": []}]
        fake.db = MagicMock()
        fake.db.get_session_layouts.return_value = []
        with patch("ui.main_window.messagebox.showwarning") as mock_warn:
            MainWindow.on_export_job_folder_to_machine(fake, "Sem_Layout")
            mock_warn.assert_called_once()
            self.assertIn("possui layout calculado", mock_warn.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
