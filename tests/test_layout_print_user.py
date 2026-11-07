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
            self.skipTest("Ambiente sem display Tkinter")

        db = DatabaseManager(":memory:")
        db.add_user("Lucas")
        db.set_user_print_prefix("Usuário")

        dlg = LayoutPrintDialog(self.root, layout_data={
            "db": db,
            "active_user": "Lucas",
            "user_print_prefix": "Usuário",
            "layout_name": "lay0000.lay",
            "sheet_w_mm": 1380.0,
            "sheet_h_mm": 1080.0,
        })
        dlg.update()

        # Verifica tag do usuário
        user_items = dlg.canvas.find_withtag("print_user_name")
        self.assertEqual(len(user_items), 1, "Tag print_user_name deve existir no Canvas")

        user_text = dlg.canvas.itemcget(user_items[0], "text")
        self.assertEqual(user_text, "Usuário: Lucas")

        # Verifica coordenadas verticais: deve estar abaixo do título
        u_box = dlg.canvas.bbox(user_items[0])
        # Posição Y do topo do nome de usuário
        user_top_y = u_box[1]

        # Busca texto do título (deve exibir 'lay0000 (Placa ...)' sem '.lay')
        all_texts = [dlg.canvas.itemcget(item, "text") for item in dlg.canvas.find_all() if dlg.canvas.type(item) == "text"]
        self.assertTrue(any("lay0000 (" in t for t in all_texts), f"Esperava encontrar 'lay0000 (' nos textos: {all_texts}")
        self.assertFalse(any("lay0000.lay (" in t for t in all_texts), f"Não deve conter 'lay0000.lay (' nos textos: {all_texts}")

        # O nome do usuário deve estar acima do bloco de metadados ("Layout: ...")
        layout_items = [i for i in dlg.canvas.find_all() if dlg.canvas.type(i) == "text" and "Layout:" in dlg.canvas.itemcget(i, "text")]
        if layout_items:
            meta_box = dlg.canvas.bbox(layout_items[0])
            self.assertLess(u_box[3], meta_box[1], "O nome de usuário deve estar ACIMA do bloco de metadados Layout:")

        dlg.destroy()

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
