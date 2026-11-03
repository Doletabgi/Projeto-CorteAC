"""
tests/test_print_metros.py

Padronização da impressão (A4) em METROS: cabeçalho "Dimensions: W x H m" e régua
numerada em metros (0,1 / 0,2 ...), nunca em centímetros.
"""

import unittest

try:
    import tkinter as tk
    HAS_TK = True
except Exception:  # pragma: no cover
    HAS_TK = False


class TestImpressaoEmMetros(unittest.TestCase):
    def setUp(self):
        if not HAS_TK:
            self.skipTest("Tkinter indisponível")
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"sem display: {exc}")

    def tearDown(self):
        for dlg in getattr(self, "_dlgs", []):
            try:
                dlg.destroy()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _dlg(self, **extra):
        from ui.layout_print_dialog import LayoutPrintDialog

        dados = {"layout_name": "METROS.lay", "sheet_w_mm": 1380.0, "sheet_h_mm": 2980.0}
        dados.update(extra)
        dlg = LayoutPrintDialog(self.root, layout_data=dados)
        dlg.update_idletasks()
        dlg.redraw()
        self._dlgs = getattr(self, "_dlgs", [])
        self._dlgs.append(dlg)
        return dlg

    def test_regua_numerada_em_metros(self):
        dlg = self._dlg()
        labels = [dlg.canvas.itemcget(i, "text") for i in dlg.canvas.find_withtag("print_label")]
        self.assertTrue(any("," in t for t in labels), f"esperava vírgula decimal (metros): {labels[:8]}")
        self.assertIn("0,1", labels)
        self.assertIn("1,3", labels)          # 1380 mm -> última marcação antes da borda
        for texto in labels:
            self.assertNotRegex(texto, r"^\d{2,3}$", f"marcação em cm encontrada: {texto}")

    def test_cabecalho_dimensoes_em_metros(self):
        dlg = self._dlg(dimensions_str="1,38 x 2,98 m")
        textos = []
        for item in dlg.canvas.find_all():
            try:
                if dlg.canvas.type(item) == "text":
                    textos.append(dlg.canvas.itemcget(item, "text"))
            except Exception:
                continue
        cabecalho = " | ".join(textos)
        self.assertIn("1,38 x 2,98 m", cabecalho, f"cabeçalho sem dimensões em metros: {cabecalho[:200]}")
        self.assertNotIn("cm", cabecalho, "a impressão não deve mais usar centímetros")

    def test_editor_gera_dimensoes_em_metros(self):
        from ui.units import format_dim_mm
        self.assertEqual(format_dim_mm(1380.0, 2980.0), "1,38 x 2,98 m")


if __name__ == "__main__":
    unittest.main()
