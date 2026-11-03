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


class TestPontaEClamp(unittest.TestCase):
    """A linha azul da ponta não pode sair da placa (caso do PDF refilado)."""

    def test_clamp_limita_a_chapa_refilada(self):
        from ui.layout_print_dialog import _clamp_tip_zone

        # ponta calculada na chapa original 1,38 x 2,98; placa refilada 1,35 x 1,13
        z = _clamp_tip_zone([0.0, 800.0, 1380.0, 2980.0], 1350.0, 1130.0)
        self.assertIsNotNone(z)
        x0, y0, x1, y1 = z
        self.assertGreaterEqual(x0, 0.0)
        self.assertGreaterEqual(y0, 0.0)
        self.assertLessEqual(x1, 1350.0)
        self.assertLessEqual(y1, 1130.0)
        self.assertAlmostEqual(y0, 800.0)
        self.assertAlmostEqual(y1, 1130.0)

    def test_clamp_descarta_ponta_cortada_pelo_refile(self):
        from ui.layout_print_dialog import _clamp_tip_zone

        # ponta inteira acima da nova altura da placa -> nada a desenhar
        self.assertIsNone(_clamp_tip_zone([0.0, 1500.0, 1380.0, 2980.0], 1350.0, 1130.0))

    def test_clamp_aceita_entradas_invalidas(self):
        from ui.layout_print_dialog import _clamp_tip_zone

        for ruim in (None, [], [1, 2, 3], "abc", [0, 0, 0, 0]):
            self.assertIsNone(_clamp_tip_zone(ruim, 1350.0, 1130.0))

    def test_texto_almoxarifado_em_metros(self):
        from cad.layers_rule import format_enfesto_operator_text

        texto = format_enfesto_operator_text(
            {"tip_zone": [0.0, 800.0, 1380.0, 2980.0], "layers": 4,
             "width_mm": 1350.0, "height_mm": 1130.0},
            tip_mode="faixa",
        )
        self.assertIn(" m", texto)
        self.assertNotIn("cm", texto)
        self.assertIn("1,35", texto)
        self.assertIn("0,33", texto)   # altura da ponta após o clamp

    def test_trim_engine_encolhe_tip_zone_no_refile(self):
        from cad.trim_engine import trim_layout_dict

        pecas = [
            {"id": 1, "name": "A", "size": "31a", "x": 10.0, "y": 10.0, "rotation": 0.0,
             "contour": [{"x": 0, "y": 0}, {"x": 200.0, "y": 0}, {"x": 200.0, "y": 900.0}, {"x": 0, "y": 900.0}]},
        ]
        layout = {"width_mm": 1380.0, "height_mm": 2980.0, "pieces": pecas,
                  "tip_zone": [0.0, 800.0, 1380.0, 2980.0], "layers_tip": 2}
        trim_layout_dict(layout, gap_mm=1.0)
        tz = layout.get("tip_zone")
        self.assertIsNotNone(tz, f"tip_zone removida; layout={ {k: layout[k] for k in ('width_mm','height_mm')} }")
        self.assertGreater(tz[3], tz[1])
        self.assertLessEqual(tz[3], layout["height_mm"] + 0.01)
        self.assertLessEqual(tz[2], layout["width_mm"] + 0.01)
