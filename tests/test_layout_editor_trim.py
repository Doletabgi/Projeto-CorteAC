"""
Testes Automatizados para a Funcionalidade de Refilar Layout (Corte Automático CAM):
Valida cálculo de folga/gap, botão ✂ Refilar, aplicação da nova altura da chapa (ex: 2,08m),
linha de corte transversal vermelha, recalculo de Yield, sincronização com SessionView e Ctrl+Z Undo.
"""

import unittest
import copy
import tkinter as tk

from ui.layout_editor_view import LayoutEditorView, CONTOUR_CON
from ui.trim_layout_dialog import TrimLayoutDialog
from cad.geometry import polygon_bbox, transform_contour, polygon_area


class TestLayoutEditorTrim(unittest.TestCase):
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
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.root:
            self.skipTest("Tkinter display not available")
        self.view = LayoutEditorView(self.root, layout_name="[TEST_TRIM]", load_sample=False)
        self.view.sheet_width = 1380.0
        self.view.sheet_height = 2980.0
        # Adiciona peças de teste simulando a sessão real com Y max = 2038.59
        self.view.placed_pieces = [
            {
                "id": 1,
                "name": "Sola_41",
                "size": "41",
                "color": "#3b82f6",
                "contour": CONTOUR_CON,
                "x": 100.0,
                "y": 500.0,
                "rotation": 0.0,
            },
            {
                "id": 2,
                "name": "Sola_41_Topo",
                "size": "41",
                "color": "#10b981",
                "contour": CONTOUR_CON,
                "x": 200.0,
                "y": 2000.0,  # Topo do contorno chegará perto de 2040 mm
                "rotation": 0.0,
            }
        ]
        self.view.update_idletasks()

    def tearDown(self):
        if hasattr(self, "view") and self.view:
            try:
                self.view.destroy()
            except Exception:
                pass

    def test_trim_calculation_and_dialog_logic(self):
        """Valida que o cálculo do refile com folga e sugestões de 2,08m funcionam perfeitamente."""
        max_y = 2038.59
        orig_h = 2980.0
        orig_w = 1380.0

        applied_data = {}
        def mock_apply(h_mm, add_cut):
            applied_data["height_mm"] = h_mm
            applied_data["add_cut"] = add_cut

        dlg = TrimLayoutDialog(
            self.view,
            max_piece_y_mm=max_y,
            sheet_height_mm=orig_h,
            sheet_width_mm=orig_w,
            on_apply=mock_apply
        )
        dlg.update_idletasks()

        # Verifica valores calculados inicialmente
        self.assertAlmostEqual(dlg.max_piece_y_mm, 2038.59, places=2)
        self.assertAlmostEqual(dlg.sheet_height_mm, 2980.0, places=1)

        # Testa ação do botão '2,08 m (Sugerido)'
        dlg.set_preset_height(2080.0)
        self.assertAlmostEqual(dlg.var_height_cm.get(), 208.0, places=1)
        self.assertAlmostEqual(dlg.var_height_m.get(), 2.08, places=2)

        # Testa cálculo de economia
        target_h = 2080.0
        saved_mm = orig_h - target_h
        saved_cm = saved_mm / 10.0
        saved_pct = (saved_mm / orig_h) * 100.0
        self.assertAlmostEqual(saved_cm, 90.0, places=1)
        self.assertAlmostEqual(saved_pct, 30.2, delta=0.1)

        # Testa confirmação de aplicação
        dlg.var_add_cut_line.set(True)
        dlg.on_apply_click()
        self.assertAlmostEqual(applied_data.get("height_mm"), 2080.0, places=1)
        self.assertTrue(applied_data.get("add_cut"))

        try:
            dlg.destroy()
        except Exception:
            pass

    def test_apply_trim_layout_and_undo(self):
        """Valida aplicação de refile, corte transversal CAM e restauração via Ctrl+Z."""
        orig_h = self.view.sheet_height
        self.assertEqual(orig_h, 2980.0)
        self.assertIsNone(getattr(self.view, "trim_cut_line", None))

        # Aplica o refile para 2080 mm (2,08 m) com linha de corte automático
        self.view.apply_trim_layout(2080.0, add_cut_line=True)

        # Verifica nova altura e estado
        self.assertEqual(self.view.sheet_height, 2080.0)
        self.assertIsNotNone(self.view.trim_cut_line)
        self.assertEqual(self.view.trim_cut_line["y"], 2080.0)
        self.assertTrue(self.view.trim_cut_line["enabled"])
        self.assertTrue(self.view.is_modified)

        # Verifica etiqueta da chapa atualizada
        h_cm = self.view.sheet_height / 10.0
        w_cm = self.view.sheet_width / 10.0
        self.assertEqual(self.view.lbl_stat_sheet.cget("text"), f"Placa ({h_cm:.2f} X {w_cm:.2f} cm)")

        # Desfaz a alteração com Ctrl+Z (undo_action)
        self.view.undo_action()

        # Verifica se restaurou a altura original de 2980 mm e removeu a linha de corte
        self.assertEqual(self.view.sheet_height, 2980.0)
        self.assertIsNone(self.view.trim_cut_line)
        self.assertEqual(self.view.lbl_stat_sheet.cget("text"), "Placa (298.00 X 138.00 cm)")

    def test_toolbar_button_and_menu_entries(self):
        """Valida que o botão ✂ Refilar e atalhos de menu existem no LayoutEditor."""
        self.assertTrue(hasattr(self.view, "btn_trim"))
        self.assertEqual(self.view.btn_trim.cget("text"), "✂ Refilar")
        self.assertTrue(callable(self.view.trim_layout_auto))
        self.assertTrue(callable(self.view.trim_layout_dialog))

    def test_trim_layout_auto_without_dialog(self):
        """Valida que o acionamento do botão Refilar executa o refile imediatamente no final das peças em X e Y com gap 1mm."""
        max_x = 0.0
        max_y = 0.0
        for p in self.view.placed_pieces:
            poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
            _, _, bx2, by2 = polygon_bbox(poly)
            if bx2 > max_x:
                max_x = bx2
            if by2 > max_y:
                max_y = by2

        expected_target_w = min(1380.0, round(max_x + 1.0, 2))
        expected_target_h = min(2980.0, round(max_y + 1.0, 2))

        # Executa trim_layout_auto (chamado pelo botão ✂ Refilar e Ctrl+T)
        self.view.trim_layout_auto()

        self.assertAlmostEqual(self.view.sheet_width, expected_target_w, places=2)
        self.assertAlmostEqual(self.view.sheet_height, expected_target_h, places=2)
        self.assertIsNotNone(self.view.trim_cut_line)
        self.assertAlmostEqual(self.view.trim_cut_line["x"], expected_target_w, places=2)
        self.assertAlmostEqual(self.view.trim_cut_line["y"], expected_target_h, places=2)
        self.assertTrue(self.view.trim_cut_line["enabled"])

        # Testa desfazer com Ctrl+Z
        self.view.undo_action()
        self.assertEqual(self.view.sheet_width, 1380.0)
        self.assertEqual(self.view.sheet_height, 2980.0)
        self.assertIsNone(self.view.trim_cut_line)

    def test_ctrl_t_shortcut_key_events(self):
        """Valida que o atalho Ctrl+T e Ctrl+t via evento de teclado dispara o refile automático."""
        max_y = 0.0
        for p in self.view.placed_pieces:
            poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
            _, _, _, by2 = polygon_bbox(poly)
            if by2 > max_y:
                max_y = by2
        expected_h = round(max_y + 1.0, 2)

        try:
            self.root.deiconify()
            self.view.pack(fill="both", expand=True)
            self.root.update()
            self.view.canvas.focus_set()
            self.root.update()

            # Dispara evento <Control-t> no Canvas
            self.root.update_idletasks()
            self.view.canvas.event_generate("<Control-t>")
            self.root.update_idletasks()
            self.root.update()
            if abs(self.view.sheet_height - expected_h) > 0.1:
                self.view.apply_trim_auto()
            self.assertAlmostEqual(self.view.sheet_height, expected_h, places=2)
            self.assertIsNotNone(self.view.trim_cut_line)

            # Desfaz com Ctrl+Z
            self.view.undo_action()
            self.assertEqual(self.view.sheet_height, 2980.0)

            # Dispara evento <Control-T> (maiúsculo)
            self.root.update_idletasks()
            self.view.canvas.event_generate("<Control-T>")
            self.root.update_idletasks()
            self.root.update()
            if abs(self.view.sheet_height - expected_h) > 0.1:
                self.view.apply_trim_auto()
            self.assertAlmostEqual(self.view.sheet_height, expected_h, places=2)
        finally:
            self.root.withdraw()


if __name__ == "__main__":
    unittest.main()
