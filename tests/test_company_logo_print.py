"""
Testes Automatizados para a Remoção do Logotipo ATOM e Suporte a Logotipo Personalizado da Empresa
no Relatório de Impressão (LayoutPrintDialog) e Layout Editor.
"""

import unittest
import tempfile
import os
from pathlib import Path
import tkinter as tk
from PIL import Image

from ui.layout_print_dialog import (
    LayoutPrintDialog,
    get_company_logo_path,
    open_company_logo_dialog
)


class TestCompanyLogoPrint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_no_atom_logo_by_default(self):
        """Valida que o logotipo ATOM e o texto 'Ψ ATOM' foram completamente removidos."""
        dlg = LayoutPrintDialog(self.root, layout_data={"layout_name": "TEST_NO_ATOM.lay"})
        dlg.update()

        # Canvas items não devem conter 'Ψ ATOM' nem 'ATOM'
        canvas_texts = []
        for item in dlg.canvas.find_all():
            if dlg.canvas.type(item) == "text":
                canvas_texts.append(dlg.canvas.itemcget(item, "text"))

        for txt in canvas_texts:
            self.assertNotIn("Ψ ATOM", txt)
            self.assertNotEqual(txt.strip(), "ATOM")

        # Verifica se o método legado load_atom_logo não quebra
        self.assertTrue(callable(dlg.load_atom_logo))
        dlg.destroy()

    def test_logo_manager_toolbar_button_exists(self):
        """Valida que o botão de Logotipo da Empresa existe na barra de ferramentas."""
        dlg = LayoutPrintDialog(self.root, layout_data={"layout_name": "TEST_BTN.lay"})
        dlg.update()

        found_logo_btn = False
        for child in dlg.winfo_children():
            if isinstance(child, tk.Frame):
                for sub in child.winfo_children():
                    if isinstance(sub, tk.Button) and "Logotipo" in sub.cget("text"):
                        found_logo_btn = True
                        break
        self.assertTrue(found_logo_btn, "Botão '🏢 Logotipo...' deve estar presente na toolbar do LayoutPrintDialog.")
        dlg.destroy()

    def test_custom_company_logo_loading_and_scaling(self):
        """Valida que uma imagem personalizada da empresa é carregada, redimensionada proporcionalmente e renderizada."""
        logo_path = get_company_logo_path(create_parent=True)
        backup_bytes = None
        if logo_path.exists():
            backup_bytes = logo_path.read_bytes()

        try:
            # Cria imagem de teste representando logo da empresa (200x50)
            test_img = Image.new("RGBA", (200, 50), (37, 99, 235, 255))
            test_img.save(str(logo_path), format="PNG")

            dlg = LayoutPrintDialog(self.root, layout_data={"layout_name": "TEST_LOGO.lay"})
            dlg.update()

            self.assertIsNotNone(dlg.company_logo_raw)
            self.assertEqual(dlg.company_logo_raw.size, (200, 50))

            # Redimensionamento proporcional
            photo = dlg.get_scaled_logo_photo(100, 50)
            self.assertIsNotNone(photo)
            # Razão 200:50 = 4:1 -> em 100x50, a largura vira 100 e a altura vira 25
            self.assertEqual(photo.width(), 100)
            self.assertEqual(photo.height(), 25)

            # Valida exportação em alta resolução (PIL)
            page_img = dlg.render_pillow_page(dpi=150)
            self.assertIsNotNone(page_img)
            self.assertEqual(page_img.mode, "RGB")

            dlg.destroy()
        finally:
            # Restaura estado anterior
            if backup_bytes is not None:
                logo_path.write_bytes(backup_bytes)
            elif logo_path.exists():
                logo_path.unlink()

    def test_open_company_logo_dialog(self):
        """Valida que a janela modal de gerenciamento de logotipo abre e fecha sem erros."""
        called = [False]
        def callback():
            called[0] = True

        dlg = open_company_logo_dialog(self.root, on_update_callback=callback)
        dlg.update()
        self.assertTrue(dlg.winfo_exists())
        self.assertIn("Logotipo", dlg.title())
        dlg.destroy()


if __name__ == "__main__":
    unittest.main()
