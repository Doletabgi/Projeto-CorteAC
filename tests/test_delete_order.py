import os
import unittest
import sqlite3
import tempfile
from unittest.mock import patch
import tkinter as tk
from tkinter import ttk

from database import DatabaseManager
from ui.main_window import MainWindow

class DummyBtn:
    def config(self, **kwargs):
        pass

class FakeMain:
    def __init__(self, root, db_path):
        self.root = root
        self.tree_main = ttk.Treeview(root)
        self.grid_lower = ttk.Treeview(root)
        self.current_mode = "jobs"
        self.icons = {}
        self.db = DatabaseManager(db_path, backend="sqlite")
        self.orders = [{"id": 1, "name": "Derby Masculino #41"}]
        self.sessions = [{"id": 91, "name": "Sessão 91", "order_id": 1, "job": "ProduçãoNova"}]
        self.current_session = self.sessions[0]
        self.current_order = self.orders[0]
        self.btn_mode_jobs = DummyBtn()
        self.btn_mode_shapes = DummyBtn()
        self.btn_mode_materials = DummyBtn()
        self.sort_grid_lower = lambda col: None
        self.lbl_status_msg = DummyBtn()
        self.active_child = None
        self.order_view = None
        self.tree_menu = tk.Menu(root, tearoff=0)

    def switch_tree_mode(self, mode="jobs"):
        MainWindow.switch_tree_mode(self, mode=mode)

    def on_delete_tree_item(self):
        MainWindow.on_delete_tree_item(self)

    def show_tree_context_menu(self, event):
        MainWindow.show_tree_context_menu(self, event)

    def show_popup_menu(self, menu, x, y):
        pass

    def on_tree_menu_open(self):
        pass

    def on_rename_tree_item(self):
        pass


class TestDeleteOrderAndArticle(unittest.TestCase):
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

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_sqlite_migration_removes_not_null(self):
        """Testa se init_db() migra automaticamente tabelas legadas com NOT NULL em order_id e article_id."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            customer TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pendente'
        )
        """)
        c.execute("""
        CREATE TABLE materials (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            width_mm REAL NOT NULL,
            height_mm REAL NOT NULL,
            area_m2 REAL NOT NULL,
            thickness_mm REAL NOT NULL
        )
        """)
        c.execute("""
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            pairs_count INTEGER NOT NULL DEFAULT 1,
            material_id TEXT NOT NULL
        )
        """)
        c.execute("""
        CREATE TABLE shapes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            color TEXT NOT NULL,
            contour_json TEXT NOT NULL
        )
        """)
        c.execute("""
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            order_id INTEGER NOT NULL,
            material_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Planejado'
        )
        """)
        conn.commit()
        conn.close()

        # Ao instanciar DatabaseManager, init_db deve migrar e remover NOT NULL
        mgr = DatabaseManager(self.db_path, backend="sqlite")

        with mgr.get_connection() as c_conn:
            cursor = c_conn.cursor()
            cursor.execute("PRAGMA table_info(sessions)")
            s_map = {r[1]: r[3] for r in cursor.fetchall()}
            self.assertEqual(s_map["order_id"], 0, "sessions.order_id deve permitir NULL após migração")
            self.assertEqual(s_map["material_id"], 0, "sessions.material_id deve permitir NULL após migração")

            cursor.execute("PRAGMA table_info(shapes)")
            sh_map = {r[1]: r[3] for r in cursor.fetchall()}
            self.assertEqual(sh_map["article_id"], 0, "shapes.article_id deve permitir NULL após migração")

            cursor.execute("PRAGMA table_info(articles)")
            art_map = {r[1]: r[3] for r in cursor.fetchall()}
            self.assertEqual(art_map["material_id"], 0, "articles.material_id deve permitir NULL após migração")

    def test_delete_order_preserves_sessions_and_shapes(self):
        """Testa se delete_order exclui o pedido mas preserva e desacopla sessões e moldes."""
        mgr = DatabaseManager(self.db_path, backend="sqlite")

        # Insere dados vinculados
        with mgr.get_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO orders (id, code, name, customer) VALUES (10, 'ORD-010', 'Artigo Teste', 'Cliente A')")
            c.execute("INSERT INTO articles (id, order_id, name) VALUES (20, 10, 'Artigo Teste Art')")
            c.execute("""
            INSERT INTO shapes (id, article_id, name, color, contour_json)
            VALUES (30, 20, 'Gáspea Teste', '#ff0000', '[{\"x\":0,\"y\":0}]')
            """)
            c.execute("""
            INSERT INTO sessions (id, code, order_id, material_id, name)
            VALUES (40, 'SESS-040', 10, 'MAT_VAQ_01', 'Sessão 40')
            """)
            conn.commit()

        # Executa delete_order
        mgr.delete_order(10)

        # Valida que pedido e artigo foram excluídos
        self.assertFalse(any(o["id"] == 10 for o in mgr.get_orders()))
        self.assertEqual(len(mgr.get_articles_by_order(10)), 0)

        # Valida que o molde existe e teve article_id alterado para None
        shp = mgr.get_shape(30)
        self.assertIsNotNone(shp, "Molde não deve ser excluído")
        self.assertIsNone(shp["article_id"], "Molde deve ter article_id desacoplado (None)")

        # Valida que a sessão existe e teve order_id alterado para None
        sess = mgr.get_session(40)
        self.assertIsNotNone(sess, "Sessão não deve ser excluída")
        self.assertIsNone(sess["order_id"], "Sessão deve ter order_id desacoplado (None)")

    def test_context_menu_no_duplicate_excluir(self):
        """Valida que o menu de contexto do nó 'order' possui apenas 'Excluir Artigo' sem duplicatas."""
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        class DummyEvent:
            x_root = 100
            y_root = 100
            y = 10

        fm = FakeMain(self.root, self.db_path)
        fm.tree_menu.delete(0, "end")

        # Insere nó de pedido real na árvore
        root_node = fm.tree_main.insert("", "end", text=" Produção", values=("root_production", ""))
        order_node = fm.tree_main.insert(root_node, "end", text=" Derby Masculino #41", values=("order", 1))
        fm.tree_main.selection_set(order_node)

        with patch.object(fm.tree_main, "identify_row", return_value=order_node):
            fm.show_tree_context_menu(DummyEvent())
            labels = []
            for i in range(fm.tree_menu.index("end") + 1):
                try:
                    labels.append(fm.tree_menu.entrycget(i, "label"))
                except Exception:
                    pass
            self.assertIn("Excluir Artigo", labels)
            self.assertNotIn("Excluir", labels, "Não deve conter a opção duplicada 'Excluir'")

    def test_delete_order_via_ui_tree_action(self):
        """Valida que a exclusão pela árvore remove o artigo e atualiza a interface."""
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        fm = FakeMain(self.root, self.db_path)

        # Adiciona item na árvore
        root_prod = fm.tree_main.insert("", "end", text=" Produção", values=("root_production", ""))
        order_item = fm.tree_main.insert(root_prod, "end", text=" Derby Masculino #41", values=("order", 1))
        fm.tree_main.selection_set(order_item)

        with patch("tkinter.messagebox.askyesno", return_value=True):
            with patch.object(fm.db, "delete_order") as mock_delete:
                fm.on_delete_tree_item()
                mock_delete.assert_called_once_with(1)

        self.assertEqual(len(fm.orders), 0)
        self.assertIsNone(fm.current_order)
        self.assertIsNone(fm.sessions[0]["order_id"], "order_id da sessão em memória deve ser None")


if __name__ == "__main__":
    unittest.main()
