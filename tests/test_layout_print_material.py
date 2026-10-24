"""
Testes unitários para validação da sincronização e formatação automática
do Código do Material, Descrição e Camadas na tela de Impressão (LayoutPrintDialog).
"""

import unittest
import tkinter as tk
from ui.layout_print_dialog import LayoutPrintDialog
from ui.layout_editor_view import LayoutEditorView


class TestLayoutPrintMaterial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_direct_material_metadata_in_dialog(self):
        """Testa se LayoutPrintDialog formata corretamente código, descrição e camadas."""
        # 1. Caso com código, descrição e 2 camadas (padrão sessão)
        dlg1 = LayoutPrintDialog(self.root, layout_data={
            "material_code": "853412",
            "material_desc": "SINT-LOGAM-PRETO",
            "material_layers": 2
        })
        self.assertEqual(dlg1.material_name, "853412 - SINT-LOGAM-PRETO ( 2 layer(s) )")
        dlg1.destroy()

        # 2. Caso com velcro 4 camadas (conforme print do usuário)
        dlg2 = LayoutPrintDialog(self.root, layout_data={
            "material_code": "132011",
            "material_desc": "VELCRO 4'' ARGOLA - PRETO",
            "material_layers": 4
        })
        self.assertEqual(dlg2.material_name, "132011 - VELCRO 4'' ARGOLA - PRETO ( 4 layer(s) )")
        dlg2.destroy()

        # 3. Caso com dicionário de material completo
        dlg3 = LayoutPrintDialog(self.root, layout_data={
            "material": {
                "id": "885953",
                "name": "LAM 1.5 NEW LOGAN",
                "layers": 6
            }
        })
        self.assertEqual(dlg3.material_name, "885953 - LAM 1.5 NEW LOGAN ( 6 layer(s) )")
        dlg3.destroy()

        # 4. Caso onde descrição já contém o código
        dlg4 = LayoutPrintDialog(self.root, layout_data={
            "material_code": "884412",
            "material_desc": "884412 - LAM 1.5MM NEW LOGAN",
            "material_layers": 2
        })
        self.assertEqual(dlg4.material_name, "884412 - LAM 1.5MM NEW LOGAN ( 2 layer(s) )")
        dlg4.destroy()

    def test_layout_editor_passes_material_to_dialog(self):
        """Testa se LayoutEditorView.set_material propaga código, descrição e camadas para print_layout."""
        view = LayoutEditorView(self.root, layout_name="TEST_MAT.lay", load_sample=False)
        mat_sample = {
            "code": "853412",
            "name": "SINT-LOGAM-PRETO",
            "layers": 3,
            "width_mm": 1380.0,
            "height_mm": 2980.0,
            "gap": 1.5
        }
        view.set_material(mat_sample)
        self.assertEqual(view.material_id, "853412")
        self.assertEqual(view.material_name, "SINT-LOGAM-PRETO")
        self.assertEqual(view.material_layers, 3)

        # Captura instância aberta de LayoutPrintDialog interceptando sua inicialização
        captured = {}
        orig_init = LayoutPrintDialog.__init__

        def mock_init(dlg_self, parent, layout_data=None, **kwargs):
            captured["layout_data"] = layout_data
            orig_init(dlg_self, parent, layout_data=layout_data, **kwargs)

        LayoutPrintDialog.__init__ = mock_init
        try:
            view.print_layout()
            self.assertIn("layout_data", captured)
            ldata = captured["layout_data"]
            self.assertEqual(ldata["material_code"], "853412")
            self.assertEqual(ldata["material_desc"], "SINT-LOGAM-PRETO")
            self.assertEqual(ldata["material_layers"], 3)
            self.assertEqual(ldata["gap_str"], "1.50 mm")
        finally:
            LayoutPrintDialog.__init__ = orig_init
            view.destroy()


if __name__ == "__main__":
    unittest.main()
