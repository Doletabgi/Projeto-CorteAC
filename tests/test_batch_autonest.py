"""
JobManager 2000 (Python Edition)
tests/test_batch_autonest.py - Testes Unitários de Seleção em Massa e Batch Auto-Nest
"""

import os
import copy
import queue
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import tkinter as tk
from tkinter import ttk

from database import DatabaseManager
from ui.main_window import MainWindow
from ui.batch_nest_dialog import BatchAutoNestDialog, BatchProgressDialog
from cad.layers_rule import is_refile_auto_enabled, is_separar_sobras_enabled


class FakeBatchWindow:
    """Mock leve de MainWindow contendo todos os componentes e métodos de batch."""
    def __init__(self, root, db_path):
        self.root = root
        self.tree_main = ttk.Treeview(root, show="tree", selectmode="extended")
        self.grid_lower = ttk.Treeview(root, show="headings", selectmode="extended")
        self.current_mode = "jobs"
        self.icons = {}
        self.db = DatabaseManager(db_path, backend="sqlite")

        # Pastas e sessões de teste
        self.db.create_job_folder("ProduçãoNova")
        self.db.create_job_folder("ProduçãoUrgente")

        # Material padrão
        self.materials = self.db.get_materials()
        self.current_material = self.materials[0] if self.materials else None

        self.orders = []
        self.current_order = None
        self.sessions = []
        self.current_session = None

        # Botões e barra de status dummy
        self.btn_mode_jobs = MagicMock()
        self.btn_mode_shapes = MagicMock()
        self.btn_mode_materials = MagicMock()
        self.btn_tb_auto_nest = tk.Button(root, text="⚡ Auto-Nest")
        self.lbl_status_msg = tk.Label(root, text="")
        self.sort_grid_lower = lambda col: None
        self.tree_menu = tk.Menu(root, tearoff=0)
        self.after = root.after

        # Batch bar
        self.batch_bar = tk.Frame(root)
        self.batch_bar.pack(fill="x", side="top")
        self.lbl_batch_status = tk.Label(self.batch_bar, text="☐ 0 marcadas")
        self.lbl_batch_status.pack(side="left")
        self.btn_batch_none = tk.Button(self.batch_bar, text="Desmarcar")
        self.btn_batch_none.pack(side="right")
        self.btn_batch_all = tk.Button(self.batch_bar, text="Marcar Todas")
        self.btn_batch_all.pack(side="right")

        self.tree_main.pack(fill="both", expand=True)

        # Estados de batch
        self.batch_checked_sessions = set()
        self._batch_in_progress = False
        self._cancel_batch = False

        # Canvas e SessionView mocks
        self.canvas = MagicMock()
        self.session_view = MagicMock()

        # Stubs para comandos de menu da árvore
        self.on_tree_menu_open = lambda: None
        self.on_create_job_subfolder = lambda *a: None
        self.on_create_production = lambda *a: None
        self.on_new_session = lambda *a: None
        self.on_create_order = lambda *a: None
        self.on_rename_tree_item = lambda *a: None
        self.on_delete_tree_item = lambda *a: None
        self.on_publish = lambda *a: None
        self.on_export_xml = lambda *a: None
        self.on_import_xml = lambda *a: None
        self.on_import_die = lambda *a: None
        self.show_layout_editor = lambda *a: None
        self.on_move_session_to_job_folder = lambda *a: None
        self.on_create_job_subfolder_menu_action = lambda *a: None

    # Liga os métodos reais de MainWindow na instância de teste
    switch_tree_mode = MainWindow.switch_tree_mode
    on_tree_click_checkbox = MainWindow.on_tree_click_checkbox
    on_tree_space_toggle = MainWindow.on_tree_space_toggle
    _get_tree_session_ids = MainWindow._get_tree_session_ids
    _find_tree_node_by_value = MainWindow._find_tree_node_by_value
    toggle_batch_node = MainWindow.toggle_batch_node
    toggle_session_batch_selection = MainWindow.toggle_session_batch_selection
    set_folder_batch_selection = MainWindow.set_folder_batch_selection
    select_all_batch_sessions = MainWindow.select_all_batch_sessions
    deselect_all_batch_sessions = MainWindow.deselect_all_batch_sessions
    update_batch_tree_visuals = MainWindow.update_batch_tree_visuals
    show_tree_context_menu = MainWindow.show_tree_context_menu
    dismiss_popup_menus = lambda self, event=None: None
    show_popup_menu = lambda self, menu, x, y: None
    on_auto_nest = MainWindow.on_auto_nest
    open_batch_auto_nest_dialog = MainWindow.open_batch_auto_nest_dialog
    run_batch_auto_nest = MainWindow.run_batch_auto_nest
    on_cancel_batch = MainWindow.on_cancel_batch
    _batch_nest_worker = MainWindow._batch_nest_worker
    _poll_batch_worker = MainWindow._poll_batch_worker


class TestBatchAutoNest(unittest.TestCase):
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
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()

        self.app = FakeBatchWindow(self.root, self.db_path)

        # Cria 3 sessões no banco para os testes
        id1 = self.app.db.create_session(session_id=101, name="Sessão #101", job="ProduçãoNova")
        id2 = self.app.db.create_session(session_id=102, name="Sessão #102", job="ProduçãoNova")
        id3 = self.app.db.create_session(session_id=201, name="Sessão #201", job="ProduçãoUrgente")

        s1 = self.app.db.get_session(id1)
        s2 = self.app.db.get_session(id2)
        s3 = self.app.db.get_session(id3)

        self.app.sessions = [s1, s2, s3]
        self.app.current_session = s1
        self.app.switch_tree_mode("jobs")

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_single_session_checkbox_toggle(self):
        """Testa alternância de checkbox em uma única sessão e atualização da barra."""
        # Inicialmente 0 marcadas
        self.assertEqual(len(self.app.batch_checked_sessions), 0)
        self.assertIn("0 marcadas", self.app.lbl_batch_status.cget("text"))
        self.assertEqual(self.app.btn_tb_auto_nest.cget("text"), "⚡ Auto-Nest")

        # Marca sessão 101
        self.app.toggle_session_batch_selection(101)
        self.assertIn(101, self.app.batch_checked_sessions)
        self.assertEqual(len(self.app.batch_checked_sessions), 1)

        # Verifica textos atualizados
        self.assertIn("1 marcada(s)", self.app.lbl_batch_status.cget("text"))
        self.assertEqual(self.app.btn_tb_auto_nest.cget("text"), "⚡ Auto-Nest (1)")

        # Desmarca sessão 101
        self.app.toggle_session_batch_selection(101)
        self.assertNotIn(101, self.app.batch_checked_sessions)
        self.assertEqual(len(self.app.batch_checked_sessions), 0)
        self.assertIn("0 marcadas", self.app.lbl_batch_status.cget("text"))
        self.assertEqual(self.app.btn_tb_auto_nest.cget("text"), "⚡ Auto-Nest")

    def test_folder_checkbox_toggle_and_tristate(self):
        """Testa marcar e desmarcar pasta de produção e estado tri-state (☐, ▣, ☑)."""
        # Localiza o nó da pasta 'ProduçãoNova' na árvore
        folder_nodes = self.app._find_tree_node_by_value(self.app.tree_main.get_children("")[0], "job_folder", "ProduçãoNova")
        self.assertTrue(len(folder_nodes) > 0)
        fn_id = folder_nodes[0]

        # 1. Nenhuma sessão marcada -> pasta exibe '☐'
        self.app.update_batch_tree_visuals()
        txt = self.app.tree_main.item(fn_id, "text")
        self.assertTrue(txt.strip().startswith("☐"))

        # 2. Marca 1 de 2 sessões da pasta (101) -> pasta exibe '▣' (parcial)
        self.app.toggle_session_batch_selection(101)
        txt = self.app.tree_main.item(fn_id, "text")
        self.assertTrue(txt.strip().startswith("▣"))

        # 3. Clica na pasta -> como está parcial, deve marcar todas as sessões da pasta -> '☑'
        self.app.toggle_batch_node(fn_id)
        self.assertIn(101, self.app.batch_checked_sessions)
        self.assertIn(102, self.app.batch_checked_sessions)
        self.assertNotIn(201, self.app.batch_checked_sessions)  # da outra pasta
        txt = self.app.tree_main.item(fn_id, "text")
        self.assertTrue(txt.strip().startswith("☑"))

        # 4. Clica na pasta novamente -> desmarca todas as sessões da pasta -> '☐'
        self.app.toggle_batch_node(fn_id)
        self.assertNotIn(101, self.app.batch_checked_sessions)
        self.assertNotIn(102, self.app.batch_checked_sessions)
        txt = self.app.tree_main.item(fn_id, "text")
        self.assertTrue(txt.strip().startswith("☐"))

    def test_select_all_and_deselect_all(self):
        """Testa os botões 'Marcar Todas' e 'Desmarcar'."""
        self.app.select_all_batch_sessions()
        self.assertEqual(len(self.app.batch_checked_sessions), 3)
        self.assertIn("3 marcada(s)", self.app.lbl_batch_status.cget("text"))
        self.assertEqual(self.app.btn_tb_auto_nest.cget("text"), "⚡ Auto-Nest (3)")

        # Verifica pastas com '☑'
        f1 = self.app._find_tree_node_by_value(self.app.tree_main.get_children("")[0], "job_folder", "ProduçãoNova")[0]
        f2 = self.app._find_tree_node_by_value(self.app.tree_main.get_children("")[0], "job_folder", "ProduçãoUrgente")[0]
        self.assertTrue(self.app.tree_main.item(f1, "text").strip().startswith("☑"))
        self.assertTrue(self.app.tree_main.item(f2, "text").strip().startswith("☑"))

        # Desmarcar todas
        self.app.deselect_all_batch_sessions()
        self.assertEqual(len(self.app.batch_checked_sessions), 0)
        self.assertIn("0 marcadas", self.app.lbl_batch_status.cget("text"))
        self.assertEqual(self.app.btn_tb_auto_nest.cget("text"), "⚡ Auto-Nest")
        self.assertTrue(self.app.tree_main.item(f1, "text").strip().startswith("☐"))
        self.assertTrue(self.app.tree_main.item(f2, "text").strip().startswith("☐"))

    def test_set_folder_batch_selection(self):
        """Testa método set_folder_batch_selection(folder, is_checked)."""
        self.app.set_folder_batch_selection("ProduçãoNova", True)
        self.assertIn(101, self.app.batch_checked_sessions)
        self.assertIn(102, self.app.batch_checked_sessions)
        self.assertNotIn(201, self.app.batch_checked_sessions)

        self.app.set_folder_batch_selection("ProduçãoNova", False)
        self.assertNotIn(101, self.app.batch_checked_sessions)
        self.assertNotIn(102, self.app.batch_checked_sessions)

    def test_context_menu_options(self):
        """Verifica se o menu de contexto inclui as opções de marcar/desmarcar."""
        folder_nodes = self.app._find_tree_node_by_value(self.app.tree_main.get_children("")[0], "job_folder", "ProduçãoNova")
        fn_id = folder_nodes[0]
        self.app.tree_main.selection_set(fn_id)

        # Dispara evento simulado
        event = MagicMock()
        event.x = 10
        event.y = 10
        event.x_root = 100
        event.y_root = 100

        with patch.object(self.app.tree_main, "identify_row", return_value=fn_id):
            self.app.show_tree_context_menu(event)

        labels = [
            self.app.tree_menu.entrycget(i, "label")
            for i in range(self.app.tree_menu.index("end") + 1)
            if self.app.tree_menu.type(i) != "separator"
        ]
        self.assertIn("☑ Marcar todas da pasta", labels)
        self.assertIn("☐ Desmarcar todas da pasta", labels)

    def test_batch_dialog_confirm_configuration(self):
        """Testa a abertura do diálogo BatchAutoNestDialog e a geração de configurações."""
        sessions_to_nest = [
            {"id": 101, "name": "Sessão #101", "job": "ProduçãoNova", "shapes": [{"id": 1, "pairs": 10}]},
            {"id": 102, "name": "Sessão #102", "job": "ProduçãoNova", "shapes": [{"id": 2, "pairs": 5}]}
        ]

        received_batch = []
        def on_start(sess_list, cfg):
            received_batch.append((sess_list, cfg))

        dlg = BatchAutoNestDialog(
            parent=self.root,
            selected_sessions=sessions_to_nest,
            initial_config={"gap_mm": 1.2, "margin_mm": 15.0, "nesting_mode": "auto"},
            on_start_batch=on_start
        )

        # Ajusta parâmetros no diálogo
        dlg.var_mode.set("economic")
        dlg.var_strat.set("flashnestsheet")
        dlg.var_params.set("HighYield")
        dlg.var_gap.set("1.5")
        dlg.var_margin.set("12.0")
        dlg.var_refile.set(True)
        dlg.var_sobras.set(True)
        dlg.var_save_db.set(True)

        dlg.on_confirm()

        self.assertTrue(dlg.confirmed)
        self.assertEqual(len(received_batch), 1)
        sess_out, cfg_out = received_batch[0]
        self.assertEqual(len(sess_out), 2)
        self.assertEqual(cfg_out["nesting_mode"], "economic")
        self.assertEqual(cfg_out["gap_mm"], 1.5)
        self.assertEqual(cfg_out["margin_mm"], 12.0)
        self.assertTrue(cfg_out["refile_auto"])
        self.assertTrue(cfg_out["separar_sobras"])
        self.assertTrue(cfg_out["save_to_db"])
        self.assertTrue(is_refile_auto_enabled(cfg_out["params"]))
        self.assertTrue(is_separar_sobras_enabled(cfg_out["params"], default_camadas=4))

    def test_batch_worker_and_polling_execution(self):
        """Testa o processamento do worker e o polling de persistência em lote."""
        # Cadastra moldes na sessão 101 e 102
        contour_rect = [{"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 0.0}, {"x": 100.0, "y": 80.0}, {"x": 0.0, "y": 80.0}]
        shape1 = {
            "name": "Biqueira", "size": "41", "pairs": 4, "contour": contour_rect,
            "area_mm2": 8000.0, "sequence": 1
        }
        shape2 = {
            "name": "Calcanhar", "size": "41", "pairs": 4, "contour": contour_rect,
            "area_mm2": 8000.0, "sequence": 2
        }

        self.app.db.update_session_shapes(101, [shape1])
        self.app.db.update_session_shapes(102, [shape2])

        sessions_to_run = [
            copy.deepcopy(next(s for s in self.app.sessions if s["id"] == 101)),
            copy.deepcopy(next(s for s in self.app.sessions if s["id"] == 102))
        ]

        # Configuração de nesting rápido para teste
        config = {
            "strategy": "flashnestsheet",
            "params": "FastNest",
            "machine": "ATOM FlashCut Flex 3020",
            "nesting_mode": "fast",
            "gap_mm": 1.0,
            "margin_mm": 10.0,
            "margins": {"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            "refile_auto": True,
            "separar_sobras": True,
            "save_to_db": True
        }

        q = queue.Queue()
        # Executa o worker síncronamente no teste
        self.app._batch_nest_worker(sessions_to_run, config, q)

        # Mock do diálogo de progresso
        progress_dlg = MagicMock()
        progress_dlg.winfo_exists.return_value = True

        # Processa todas as mensagens geradas na fila pelo worker
        self.app._poll_batch_worker(q, progress_dlg, config)

        # Verifica se as duas sessões foram calculadas e salvas como 'Nested' no banco
        db_s1 = self.app.db.get_session(101)
        db_s2 = self.app.db.get_session(102)

        self.assertEqual(db_s1["status"], "Nested")
        self.assertEqual(db_s2["status"], "Nested")
        self.assertGreater(db_s1.get("yield_percent", 0), 0)
        self.assertGreater(db_s2.get("yield_percent", 0), 0)

        # Verifica layouts salvos
        ly1 = self.app.db.get_session_layouts(101)
        ly2 = self.app.db.get_session_layouts(102)
        self.assertTrue(len(ly1) >= 1)
        self.assertTrue(len(ly2) >= 1)

        # Verifica se o progresso chamou mark_completed
        progress_dlg.mark_completed.assert_called_once()

    def test_batch_worker_cancellation(self):
        """Testa o cancelamento gracioso do cálculo do lote."""
        sessions_to_run = [
            copy.deepcopy(next(s for s in self.app.sessions if s["id"] == 101)),
            copy.deepcopy(next(s for s in self.app.sessions if s["id"] == 102))
        ]

        config = {
            "strategy": "flashnestsheet",
            "params": "FastNest",
            "machine": "ATOM FlashCut Flex 3020",
            "nesting_mode": "fast",
            "gap_mm": 1.0,
            "refile_auto": True,
            "separar_sobras": True,
            "save_to_db": True
        }

        # Simula cancelamento prévio
        self.app._cancel_batch = True
        q = queue.Queue()
        self.app._batch_nest_worker(sessions_to_run, config, q)

        # Deve enviar BATCH_CANCELLED imediatamente
        msg = q.get_nowait()
        self.assertEqual(msg[0], "BATCH_CANCELLED")
        self.assertEqual(msg[1], 0)  # 0 concluídas


if __name__ == "__main__":
    unittest.main()
