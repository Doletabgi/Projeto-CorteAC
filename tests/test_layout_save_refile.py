"""
tests/test_layout_save_refile.py

Regressão: "refilei, salvei o layout e não salvou — continua igual ao estado anterior".

Duas falhas cobertas:
1. `LayoutEditorView.save_layout` precisa persistir as dimensões REFILADAS (e a ponta).
2. `MainWindow.on_layout_editor_save` precisa sincronizar a lista `layouts` da sessão em
   memória; sem isso uma gravação posterior sobrescrevia o banco com as dimensões antigas.
"""

import copy
import os
import tempfile
import unittest

try:
    import tkinter as tk
    HAS_TK = True
except Exception:  # pragma: no cover
    HAS_TK = False

CONTOUR = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 250}, {"x": 0, "y": 250}]


def _pecas(n=3):
    return [
        {"id": i, "name": "M1", "size": "38", "x": 10.0 + (i - 1) * 110.0, "y": 10.0,
         "rotation": 0.0, "contour": copy.deepcopy(CONTOUR), "color": "#3b82f6"}
        for i in range(1, n + 1)
    ]


class _DummyLabel:
    def config(self, **kwargs):
        self.last = kwargs


class TestSalvarRefile(unittest.TestCase):
    def setUp(self):
        if not HAS_TK:
            self.skipTest("Tkinter indisponível")
        from database import DatabaseManager

        self.tmp = tempfile.mkdtemp(prefix="corteac_save_")
        self.db = DatabaseManager(db_path=os.path.join(self.tmp, "s.db"))
        self.sid = self.db.create_session(name="TESTE_SALVAR_REFILE")
        self.layout_original = {
            "layout_index": 0, "name": "lay0000", "layers": 4,
            "width_mm": 1380.0, "height_mm": 2980.0,
            "pieces": _pecas(),
        }
        self.db.save_session_layouts(self.sid, [copy.deepcopy(self.layout_original)])

        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"sem display: {exc}")

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    # ---------------------------------------------------------------- editor
    def _editor(self):
        from types import MethodType
        from ui.layout_editor_view import LayoutEditorView

        f = tk.Frame(self.root)
        f.db = self.db
        f.session_id = self.sid
        f.layout_id = None
        f.layout_version = 1
        f.layouts = [copy.deepcopy(self.layout_original)]
        f.current_layout_index = 0
        f.placed_pieces = _pecas()
        f.layout_name = "lay0000"
        # Estado REFILADO (o que o botão ✂ Refilar deixa no editor)
        f.sheet_width = 345.0
        f.sheet_height = 265.0
        f.trim_cut_line = {"y": 265.0, "x": 345.0, "orig_w": 1380.0, "orig_h": 2980.0,
                           "has_cut_y": True, "has_cut_x": True, "enabled": True}
        f.tip_zone = [0.0, 200.0, 345.0, 265.0]
        f.layers_tip = 2
        f.tip_mode = "faixa"
        f.material_layers = 4
        f.material_name, f.material_id = "Raspa", "115001"
        f.undo_stack = []
        f.on_save_cb = None
        f.layout_filepath = None
        f.set_modified = lambda v: None
        f.lbl_stat_pos = _DummyLabel()
        f.save_layout = MethodType(LayoutEditorView.save_layout, f)
        return f

    def test_editor_persiste_dimensoes_refiladas(self):
        f = self._editor()
        f.save_layout()

        recarregado = self.db.get_session_layouts(self.sid)
        self.assertEqual(len(recarregado), 1)
        ly = recarregado[0]
        self.assertAlmostEqual(float(ly["width_mm"]), 345.0, places=1)
        self.assertAlmostEqual(float(ly["height_mm"]), 265.0, places=1)
        self.assertTrue(ly.get("trim_cut_line"), "o refile (corte CAM) não foi salvo")
        self.assertEqual(ly.get("layers_tip"), 2)

    # ------------------------------------------------------------ main window
    def _main_window(self, editor):
        from types import MethodType
        from ui.main_window import MainWindow

        class SessView:
            def __init__(self):
                self.session_data = {"id": self_sid, "layouts": [], "placed_pieces": []}
                self.refresh_chamado = 0

            def refresh_layout_tab(self, session_data=None):
                self.refresh_chamado += 1

            def update_summary_text(self, *a, **k):
                pass

            def draw_mini_layout_preview(self):
                pass

        self_sid = self.sid
        mw = type("MW", (), {})()
        mw.current_session = {"id": self.sid, "layouts": [copy.deepcopy(self.layout_original)],
                              "placed_pieces": []}
        mw.sessions = [mw.current_session]
        mw.layout_editor_view = editor
        mw.db = self.db
        sv = SessView()
        mw.open_sessions = {self.sid: sv}
        mw.lbl_status_msg = _DummyLabel()
        mw.on_layout_editor_save = MethodType(MainWindow.on_layout_editor_save, mw)
        return mw, sv

    def test_main_window_sincroniza_layouts_refilados(self):
        f = self._editor()
        f.save_layout()  # editor já persistiu

        mw, sv = self._main_window(f)
        ok = mw.on_layout_editor_save(f.placed_pieces, f.sheet_width, f.sheet_height, "lay0000")
        self.assertTrue(ok)

        # Sessão em memória precisa refletir o refile (antes ficava com 1380 x 2980)
        ly_mem = mw.current_session["layouts"][0]
        self.assertAlmostEqual(float(ly_mem["width_mm"]), 345.0, places=1)
        self.assertAlmostEqual(float(ly_mem["height_mm"]), 265.0, places=1)

        # E o banco continua correto depois disso
        ly_db = self.db.get_session_layouts(self.sid)[0]
        self.assertAlmostEqual(float(ly_db["width_mm"]), 345.0, places=1)
        self.assertAlmostEqual(float(ly_db["height_mm"]), 265.0, places=1)

        # A aba Layout foi atualizada (todas as placas, não uma linha só)
        self.assertEqual(sv.refresh_chamado, 1)


if __name__ == "__main__":
    unittest.main()
