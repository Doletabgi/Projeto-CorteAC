import os
import unittest
import tkinter as tk
from database import DatabaseManager
from ui.user_dialog import UserManagementDialog, open_user_management_dialog


class TestUserManagement(unittest.TestCase):
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
            cls.root.destroy()

    def setUp(self):
        # Banco isolado em memória
        self.db = DatabaseManager(":memory:")

    def test_01_initial_users_empty(self):
        users = self.db.get_users()
        self.assertEqual(users, [])
        self.assertEqual(self.db.get_active_user(), "")
        self.assertEqual(self.db.get_user_print_prefix(), "Usuário")

    def test_02_add_first_user_becomes_active(self):
        ok = self.db.add_user("Lucas")
        self.assertTrue(ok)
        users = self.db.get_users()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["name"], "Lucas")
        self.assertEqual(self.db.get_active_user(), "Lucas")

    def test_03_add_multiple_users_and_set_active(self):
        self.db.add_user("Lucas")
        self.db.add_user("Dola")
        self.db.add_user("Operador 3")

        users = self.db.get_users()
        names = [u["name"] for u in users]
        self.assertIn("Lucas", names)
        self.assertIn("Dola", names)
        self.assertIn("Operador 3", names)

        # Lucas foi o primeiro, então é o ativo
        self.assertEqual(self.db.get_active_user(), "Lucas")

        # Muda o ativo para Dola
        self.db.set_active_user("Dola")
        self.assertEqual(self.db.get_active_user(), "Dola")

    def test_04_delete_user(self):
        self.db.add_user("UserA")
        self.db.add_user("UserB")
        self.db.set_active_user("UserA")

        self.db.delete_user("UserA")
        users = self.db.get_users()
        names = [u["name"] for u in users]
        self.assertNotIn("UserA", names)
        self.assertIn("UserB", names)
        # O ativo deve ter mudado para UserB
        self.assertEqual(self.db.get_active_user(), "UserB")

    def test_05_prefix_configuration(self):
        self.assertEqual(self.db.get_user_print_prefix(), "Usuário")
        self.db.set_user_print_prefix("Operador")
        self.assertEqual(self.db.get_user_print_prefix(), "Operador")
        self.db.set_user_print_prefix("")
        self.assertEqual(self.db.get_user_print_prefix(), "")

    def test_06_dialog_ui_add_and_set_active(self):
        if not self.root:
            self.skipTest("Ambiente sem display Tkinter")

        callback_called = [False]
        def on_update():
            callback_called[0] = True

        dlg = open_user_management_dialog(self.root, db=self.db, on_update_callback=on_update)
        dlg.update()

        # Adiciona usuário via interface
        dlg.entry_name.insert(0, "Carlos Silva")
        dlg.on_add_user()
        dlg.update()

        self.assertTrue(callback_called[0])
        self.assertEqual(self.db.get_active_user(), "Carlos Silva")

        # Muda prefixo via interface
        dlg.prefix_var.set("Operador")
        dlg._on_prefix_changed()
        dlg.update()
        self.assertEqual(self.db.get_user_print_prefix(), "Operador")
        self.assertIn("Operador: Carlos Silva", dlg.lbl_prev_user.cget("text"))

        dlg.destroy()


if __name__ == "__main__":
    unittest.main()
