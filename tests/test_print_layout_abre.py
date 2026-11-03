"""
tests/test_print_layout_abre.py

Regressão: Ctrl+P / botão Imprimir do Layout Editor não abria a impressão.
O código lia o contorno como tupla (cntr[i][0]) mas o editor usa {"x","y"},
o que levantava KeyError dentro do callback do Tk — a exceção era engolida e
o operador via apenas "nada acontece".
"""

import unittest
from types import MethodType

try:
    import tkinter as tk
    HAS_TK = True
except Exception:  # pragma: no cover
    HAS_TK = False

from ui.layout_editor_view import _contour_area_mm2

CONTOUR_DICT = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 250}, {"x": 0, "y": 250}]
CONTOUR_TUPLE = [(0, 0), (100, 0), (100, 250), (0, 250)]


class TestContourArea(unittest.TestCase):
    def test_aceita_dict_e_tupla(self):
        self.assertAlmostEqual(_contour_area_mm2(CONTOUR_DICT), 25000.0)
        self.assertAlmostEqual(_contour_area_mm2(CONTOUR_TUPLE), 25000.0)

    def test_contorno_invalido_devolve_zero(self):
        for ruim in ([], None, [{"x": 0, "y": 0}], "abc", [1, 2, 3]):
            self.assertEqual(_contour_area_mm2(ruim), 0.0)


class TestPrintLayoutAbre(unittest.TestCase):
    def setUp(self):
        if not HAS_TK:
            self.skipTest("Tkinter indisponível")
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"sem display para Tk: {exc}")

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _editor(self, contour, n=4):
        from ui.layout_editor_view import LayoutEditorView

        f = tk.Frame(self.root)
        f.sheet_width, f.sheet_height = 1380.0, 2980.0
        f.placed_pieces = [
            {"id": i, "name": "323_PalAcb_31a", "size": "31a", "x": 10.0 * i, "y": 10.0,
             "rotation": 0.0, "contour": contour}
            for i in range(1, n + 1)
        ]
        f.shapes = []
        f.material = {"code": "115001", "name": "Raspa Natural", "layers": 4, "gap": 1.0}
        f.material_id, f.material_name, f.material_layers = "115001", "Raspa Natural", 4
        f.material_cod_r = None
        f.current_layout_index = 0
        f.layouts = [{"layers": 4, "pieces": f.placed_pieces}]
        f.layout_name = "10001.lay"
        f.session = {"id": 282, "layers": 4}
        f.session_shapes = []
        f.trim_cut_line = None
        f.tip_zone = None
        f.layers_tip = None
        f.tip_mode = "canto"
        return f, MethodType(LayoutEditorView.print_layout, f)

    def _capturar_dialogo(self):
        import ui.layout_editor_view as LEV
        capturado = {}

        class FakeDialog:
            def __init__(self, parent, layout_data=None):
                capturado.update(layout_data or {})

            def focus_set(self):
                pass

        original = LEV.LayoutPrintDialog
        LEV.LayoutPrintDialog = FakeDialog
        self.addCleanup(lambda: setattr(LEV, "LayoutPrintDialog", original))
        return capturado

    def test_print_layout_abre_com_contorno_dict(self):
        capturado = self._capturar_dialogo()
        f, acao = self._editor(CONTOUR_DICT)
        acao()  # não pode levantar exceção
        self.assertTrue(capturado, "o diálogo de impressão não foi aberto")
        self.assertEqual(capturado.get("instances_count"), 4)
        # 4 x 25.000 mm² em 1,38 x 2,98 m => ~2,43% (nunca o antigo 83.02 falso)
        self.assertAlmostEqual(float(capturado.get("yield_pct")), 2.43, places=1)
        self.assertNotAlmostEqual(float(capturado.get("yield_pct")), 83.02, places=2)
        # Padronização: dimensões sempre em metros
        self.assertEqual(capturado.get("dimensions_str"), "1,38 x 2,98 m")

    def test_print_layout_abre_com_contorno_tupla(self):
        capturado = self._capturar_dialogo()
        f, acao = self._editor(CONTOUR_TUPLE)
        acao()
        self.assertTrue(capturado)
        self.assertAlmostEqual(float(capturado.get("yield_pct")), 2.43, places=1)

    def test_print_layout_sem_pecas_nao_inventa_rendimento(self):
        capturado = self._capturar_dialogo()
        f, acao = self._editor(CONTOUR_DICT, n=0)
        acao()
        self.assertTrue(capturado)
        self.assertEqual(float(capturado.get("yield_pct")), 0.0)


if __name__ == "__main__":
    unittest.main()
