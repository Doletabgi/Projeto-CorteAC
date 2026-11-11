import unittest
import tkinter as tk
from database import DatabaseManager
from ui.layout_print_dialog import LayoutPrintDialog


class TestLayoutPrintUser(unittest.TestCase):
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

    def test_01_no_user_renders_cleanly(self):
        if not self.root:
            self.skipTest("Ambiente sem display Tkinter")

        db = DatabaseManager(":memory:")
        dlg = LayoutPrintDialog(self.root, layout_data={
            "db": db,
            "active_user": "",
            "layout_name": "lay0000.lay",
            "sheet_w_mm": 1380.0,
            "sheet_h_mm": 1080.0,
        })
        dlg.update()

        items = dlg.canvas.find_withtag("print_user_name")
        self.assertEqual(len(items), 0, "Sem usuário ativo, a tag print_user_name não deve existir")

        img = dlg.render_pillow_page(dpi=72)
        self.assertIsNotNone(img)
        dlg.destroy()

    def test_02_canvas_renders_user_below_title(self):
        if not self.root:
            self.skipTest('Ambiente sem display Tkinter')
        db=DatabaseManager(':memory:')
        dlg=LayoutPrintDialog(self.root,layout_data={'db':db,'active_user':'Lucas','sheet_w_mm':1380,'sheet_h_mm':1080})
        self.addCleanup(dlg.destroy)
        text=' '.join(dlg.print_texts)
        self.assertIn('Operador (usuário ativo): Lucas',text)
        self.assertLess(text.index('FICHA DE PRODUÇÃO'),text.index('Operador (usuário ativo): Lucas'))
        self.assertLess(text.index('Operador (usuário ativo): Lucas'),text.index('PREPARAÇÃO DO MATERIAL'))


    def test_03_pillow_renders_user_text(self):
        if not self.root:
            self.skipTest("Ambiente sem display Tkinter")

        db = DatabaseManager(":memory:")
        db.add_user("Dola")
        db.set_user_print_prefix("Operador")

        dlg = LayoutPrintDialog(self.root, layout_data={
            "db": db,
            "active_user": "Dola",
            "user_print_prefix": "Operador",
            "layout_name": "lay0000.lay",
            "sheet_w_mm": 1380.0,
            "sheet_h_mm": 1080.0,
        })
        dlg.update()

        self.assertEqual(dlg.get_user_display_text(), "Operador: Dola")

        img = dlg.render_pillow_page(dpi=150)
        self.assertIsNotNone(img)
        self.assertGreater(img.size[0], 500)
        self.assertGreater(img.size[1], 500)

        dlg.destroy()

    def test_04_user_prefix_options(self):
        if not self.root:
            self.skipTest("Ambiente sem display Tkinter")

        db = DatabaseManager(":memory:")

        # Prefixo customizado
        dlg1 = LayoutPrintDialog(self.root, layout_data={
            "db": db, "active_user": "Roberto", "user_print_prefix": "Operador"
        })
        self.assertEqual(dlg1.get_user_display_text(), "Operador: Roberto")
        dlg1.destroy()

        # Sem prefixo
        dlg2 = LayoutPrintDialog(self.root, layout_data={
            "db": db, "active_user": "Roberto", "user_print_prefix": ""
        })
        self.assertEqual(dlg2.get_user_display_text(), "Roberto")
        dlg2.destroy()

        # Não duplica prefixo se já contiver
        dlg3 = LayoutPrintDialog(self.root, layout_data={
            "db": db, "active_user": "Operador: Roberto", "user_print_prefix": "Operador"
        })
        self.assertEqual(dlg3.get_user_display_text(), "Operador: Roberto")
        dlg3.destroy()


if __name__ == "__main__":
    unittest.main()
