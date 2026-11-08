"""
Testes Automatizados para validação dos itens do menu Ferramentas na MainWindow.
Garante que opções obsoletas ou indesejadas não estejam presentes no menu Ferramentas.
"""

import unittest
from ui.main_window import MainWindow


class TestToolsMenuItems(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = MainWindow()
            cls.root.update()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def test_tools_menu_does_not_contain_production_or_folder_creation(self):
        """Verifica que o menu Ferramentas não contém 'Criar Produção', 'Criar Pasta de Moldes' ou 'Criar Subpasta de Moldes'."""
        if not self.root:
            self.skipTest("MainWindow indisponível no ambiente de teste")

        tools_menu = self.root.tools_menu
        num_items = tools_menu.index("end")
        labels = []
        for i in range(num_items + 1):
            try:
                if tools_menu.type(i) == "command":
                    labels.append(tools_menu.entrycget(i, "label"))
            except Exception:
                pass

        # Não deve conter opções de criar produção ou pastas de moldes
        for forbidden in ["Criar Produção", "Criar Pasta de Moldes", "Criar Subpasta de Moldes"]:
            self.assertFalse(
                any(forbidden in lbl for lbl in labels),
                f"'{forbidden}' não deve estar presente no menu Ferramentas. Itens encontrados: {labels}"
            )

        # Deve conter opções válidas mantidas
        self.assertTrue(any("Layout Editor" in lbl for lbl in labels))
        self.assertTrue(any("Shape Editor" in lbl for lbl in labels))
        self.assertTrue(any("Conversor de Arquivos" in lbl for lbl in labels))
        self.assertTrue(any("Importar Shape (.die)" in lbl for lbl in labels))
        self.assertTrue(any("Exportar G-Code" in lbl for lbl in labels), f"'Exportar G-Code' deve estar presente no menu Ferramentas: {labels}")
        self.assertTrue(any("Backup e Restauração de Moldes" in lbl for lbl in labels), f"'Backup e Restauração de Moldes' deve estar presente no menu Ferramentas: {labels}")

    def test_export_gcode_removed_from_toolbar(self):
        """Garante que o botão Exportar G-Code não está mais presente na barra de ferramentas da MainWindow."""
        if not self.root:
            self.skipTest("MainWindow indisponível no ambiente de teste")

        self.assertIsNone(self.root.btn_tb_export_gcode)


if __name__ == "__main__":
    unittest.main()
