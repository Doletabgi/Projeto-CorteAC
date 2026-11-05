"""
tests/test_layout_print_pagination.py

Testes automatizados da navegação de páginas de impressão (LayoutPrintDialog):
- Botões '◀ Anterior' e 'Próxima ▶' e label 'Página X de Y'
- Estado habilitado/desabilitado nas extremidades
- Alternância de metadados, contornos, legenda e título da janela
- Sincronização com o editor (master.switch_to_layout)
- Atalhos de teclado (PageDown / PageUp)
- Exportação em lote de PDF multipágina
"""

import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk

from ui.layout_print_dialog import LayoutPrintDialog


class TestLayoutPrintPagination(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception as exc:
            self.skipTest(f"Tkinter indisponível no ambiente de teste: {exc}")

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_single_page_controls_disabled(self):
        """Em placa única, botões de anterior e próxima ficam desabilitados."""
        dlg = LayoutPrintDialog(self.root, layout_data={
            "layout_name": "lay0000.lay",
            "sheet_w_mm": 1380.0,
            "sheet_h_mm": 1080.0,
            "placed_pieces": [{"name": "P1", "size": "40", "x": 10, "y": 10}],
        })
        try:
            self.assertTrue(hasattr(dlg, "btn_prev"))
            self.assertTrue(hasattr(dlg, "btn_next"))
            self.assertTrue(hasattr(dlg, "lbl_page"))

            self.assertEqual(dlg.lbl_page.cget("text"), "Página 1 de 1")
            self.assertEqual(str(dlg.btn_prev.cget("state")), "disabled")
            self.assertEqual(str(dlg.btn_next.cget("state")), "disabled")

            # Próxima e anterior não alteram nada
            self.assertEqual(dlg.next_page(), "break")
            self.assertEqual(dlg.current_layout_index, 0)
            self.assertEqual(dlg.prev_page(), "break")
            self.assertEqual(dlg.current_layout_index, 0)
        finally:
            dlg.destroy()

    def test_multi_page_navigation_flow(self):
        """Em múltiplas placas, navega sequencialmente e atualiza metadados."""
        layouts = [
            {
                "name": "lay0000",
                "width_mm": 1380.0,
                "height_mm": 1080.0,
                "pieces": [{"name": "P1", "size": "38", "x": 10, "y": 10, "contour": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 50}]}],
            },
            {
                "name": "lay0001",
                "width_mm": 1350.0,
                "height_mm": 1000.0,
                "pieces": [{"name": "P2", "size": "39", "x": 20, "y": 20, "contour": [{"x": 0, "y": 0}, {"x": 60, "y": 0}, {"x": 60, "y": 60}]}],
            },
            {
                "name": "lay0002",
                "width_mm": 1400.0,
                "height_mm": 1100.0,
                "pieces": [{"name": "P3", "size": "40", "x": 30, "y": 30, "contour": [{"x": 0, "y": 0}, {"x": 70, "y": 0}, {"x": 70, "y": 70}]}],
            },
        ]

        dlg = LayoutPrintDialog(self.root, layout_data={
            "layouts": layouts,
            "current_layout_index": 0,
            "material_name": "COUROTAN PRETO",
        })
        try:
            # Página 1
            self.assertEqual(dlg.current_layout_index, 0)
            self.assertEqual(dlg.lbl_page.cget("text"), "Página 1 de 3")
            self.assertEqual(str(dlg.btn_prev.cget("state")), "disabled")
            self.assertEqual(str(dlg.btn_next.cget("state")), "normal")
            self.assertIn("lay0000.lay", dlg.title())
            self.assertEqual(dlg.placa_n_de_m, "Placa 1 de 3")
            self.assertEqual(dlg.sheet_w_mm, 1380.0)

            # Avança para Página 2
            dlg.next_page()
            self.assertEqual(dlg.current_layout_index, 1)
            self.assertEqual(dlg.lbl_page.cget("text"), "Página 2 de 3")
            self.assertEqual(str(dlg.btn_prev.cget("state")), "normal")
            self.assertEqual(str(dlg.btn_next.cget("state")), "normal")
            self.assertIn("lay0001.lay", dlg.title())
            self.assertEqual(dlg.placa_n_de_m, "Placa 2 de 3")
            self.assertEqual(dlg.sheet_w_mm, 1350.0)

            # Avança para Página 3 (última)
            dlg.next_page()
            self.assertEqual(dlg.current_layout_index, 2)
            self.assertEqual(dlg.lbl_page.cget("text"), "Página 3 de 3")
            self.assertEqual(str(dlg.btn_prev.cget("state")), "normal")
            self.assertEqual(str(dlg.btn_next.cget("state")), "disabled")
            self.assertIn("lay0002.lay", dlg.title())
            self.assertEqual(dlg.placa_n_de_m, "Placa 3 de 3")
            self.assertEqual(dlg.sheet_w_mm, 1400.0)

            # Tenta avançar além da última -> permanece na 3
            dlg.next_page()
            self.assertEqual(dlg.current_layout_index, 2)

            # Volta para Página 2
            dlg.prev_page()
            self.assertEqual(dlg.current_layout_index, 1)
            self.assertEqual(dlg.lbl_page.cget("text"), "Página 2 de 3")
            self.assertEqual(str(dlg.btn_prev.cget("state")), "normal")
            self.assertEqual(str(dlg.btn_next.cget("state")), "normal")

            # Volta para Página 1 (primeira)
            dlg.prev_page()
            self.assertEqual(dlg.current_layout_index, 0)
            self.assertEqual(dlg.lbl_page.cget("text"), "Página 1 de 3")
            self.assertEqual(str(dlg.btn_prev.cget("state")), "disabled")
            self.assertEqual(str(dlg.btn_next.cget("state")), "normal")

            # Tenta voltar antes da primeira -> permanece na 0
            dlg.prev_page()
            self.assertEqual(dlg.current_layout_index, 0)
        finally:
            dlg.destroy()

    def test_master_editor_sync(self):
        """Ao alternar página no preview, aciona switch_to_layout no master se disponível."""
        mock_master = tk.Frame(self.root)
        mock_master.switch_to_layout = MagicMock()

        layouts = [
            {"name": "lay0000", "pieces": []},
            {"name": "lay0001", "pieces": []},
        ]
        dlg = LayoutPrintDialog(mock_master, layout_data={
            "layouts": layouts,
            "current_layout_index": 0,
        })
        try:
            dlg.next_page()
            mock_master.switch_to_layout.assert_called_with(1, save_current=True)

            dlg.prev_page()
            mock_master.switch_to_layout.assert_called_with(0, save_current=True)
        finally:
            dlg.destroy()

    def test_save_as_pdf_single_and_multi(self):
        """Verifica fluxo de exportação PDF individual e multipágina."""
        layouts = [
            {"name": "lay0000", "pieces": []},
            {"name": "lay0001", "pieces": []},
        ]
        dlg = LayoutPrintDialog(self.root, layout_data={
            "layouts": layouts,
            "current_layout_index": 0,
        })
        try:
            # 1. Cancelar confirmação
            with patch("tkinter.messagebox.askyesnocancel", return_value=None) as mock_ask:
                with patch("tkinter.filedialog.asksaveasfilename") as mock_save:
                    dlg.save_as_pdf()
                    mock_ask.assert_called_once()
                    mock_save.assert_not_called()

            # 2. Exportar página única (Não para todas)
            with patch("tkinter.messagebox.askyesnocancel", return_value=False):
                with patch("tkinter.filedialog.asksaveasfilename", return_value=""):
                    dlg.save_as_pdf()

            # 3. Exportar todas as páginas (Sim)
            with patch("tkinter.messagebox.askyesnocancel", return_value=True):
                with patch("tkinter.filedialog.asksaveasfilename", return_value="/tmp/test_export_all.pdf"):
                    with patch("tkinter.messagebox.showinfo") as mock_info:
                        dlg.save_as_pdf()
                        mock_info.assert_called_once()
                        # Deve restaurar o índice original no final
                        self.assertEqual(dlg.current_layout_index, 0)
        finally:
            dlg.destroy()


if __name__ == "__main__":
    unittest.main()
