"""
Testes unitários automatizados para a Impressão em Massa (Batch Print) de Sessões.
Valida:
1. Coleta e enriquecimento de layouts de sessões com metadados e contornos (_collect_session_layouts_for_print).
2. Agregação multi-sessão e abertura do LayoutPrintDialog (on_batch_print_sessions e on_print_session).
3. Navegação entre páginas de diferentes sessões com materiais e moldes distintos.
4. Exportação multi-página PDF consolidada de todas as sessões do lote.
5. Presença dos comandos de impressão em massa nos menus de contexto da árvore.
"""

import os
import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
from tkinter import ttk

from ui.layout_print_dialog import LayoutPrintDialog
from ui.main_window import MainWindow


class TestBatchPrintSessions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_collect_session_layouts_for_print_enrichment(self):
        """Valida que _collect_session_layouts_for_print enriquece os layouts com contornos, material e título."""
        win = MagicMock(spec=MainWindow)
        win.current_session = None
        win.shapes = []

        dummy_shapes = [
            {"id": "shape_1", "name": "Biqueira", "size": "41", "contour": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 50}, {"x": 0, "y": 50}]},
            {"id": "shape_2", "name": "Taloneira", "size": "41", "contour": [{"x": 0, "y": 0}, {"x": 80, "y": 0}, {"x": 80, "y": 40}, {"x": 0, "y": 40}]},
        ]
        dummy_layouts = [
            {
                "id": 1,
                "name": "lay0000.lay",
                "width_mm": 1380.0,
                "height_mm": 1080.0,
                "pieces": [
                    {"name": "Biqueira", "shape_id": "shape_1", "size": "41", "x": 10.0, "y": 20.0},
                    {"name": "Taloneira", "shape_id": "shape_2", "size": "41", "x": 120.0, "y": 20.0},
                ],
                "layers": 2,
            },
            {
                "id": 2,
                "name": "lay0001.lay",
                "width_mm": 1380.0,
                "height_mm": 500.0,
                "pieces": [
                    {"name": "Biqueira", "shape_id": "shape_1", "size": "41", "x": 10.0, "y": 10.0},
                ],
                "layers": 2,
            }
        ]
        dummy_mat = {
            "code": "853412",
            "name": "COURO-VAQUETA",
            "layers": 2,
            "width_mm": 1380.0,
            "height_mm": 1080.0,
        }

        mock_db = MagicMock()
        mock_db.get_session.return_value = {
            "id": 188,
            "name": "Sessão Teste 188",
            "job": "ProducaoNova",
            "shapes": dummy_shapes,
            "material": dummy_mat,
            "layouts": dummy_layouts,
        }
        mock_db.get_session_shapes.return_value = dummy_shapes
        mock_db.get_session_layouts.return_value = dummy_layouts
        win.db = mock_db
        win.sessions = []

        # Executa método real vinculado
        enriched = MainWindow._collect_session_layouts_for_print(win, 188)

        self.assertEqual(len(enriched), 2)
        # Layout 0
        ly0 = enriched[0]
        self.assertEqual(ly0["session_id"], 188)
        self.assertEqual(ly0["session_title"], "Sessão #188")
        self.assertEqual(ly0["material_code"], "853412")
        self.assertEqual(ly0["material_desc"], "COURO-VAQUETA")
        self.assertEqual(len(ly0["pieces"]), 2)
        # Contornos foram preenchidos a partir de session_shapes
        self.assertIsNotNone(ly0["pieces"][0].get("contour"))
        self.assertEqual(len(ly0["pieces"][0]["contour"]), 4)

        # Layout 1
        ly1 = enriched[1]
        self.assertEqual(ly1["session_id"], 188)
        self.assertEqual(ly1["session_title"], "Sessão #188")
        self.assertEqual(len(ly1["pieces"]), 1)
        self.assertIsNotNone(ly1["pieces"][0].get("contour"))

    def test_batch_print_dialog_multi_session_navigation(self):
        """Valida que o LayoutPrintDialog exibe metadados de sessões diferentes ao navegar pelas placas."""
        batch_layouts = [
            {
                "name": "lay0000.lay",
                "session_id": 101,
                "session_title": "Sessão #101",
                "width_mm": 1400.0,
                "height_mm": 1000.0,
                "material_code": "MAT-A",
                "material_desc": "Sintético Azul",
                "material_layers": 4,
                "pieces": [
                    {"name": "PecaA", "size": "38", "x": 50, "y": 50, "contour": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 50}, {"x": 0, "y": 50}]}
                ],
                "session_shapes": [
                    {"name": "PecaA", "size": "38", "shape_id": "1", "pairs": 5}
                ]
            },
            {
                "name": "lay0000.lay",
                "session_id": 102,
                "session_title": "Sessão #102",
                "width_mm": 1200.0,
                "height_mm": 800.0,
                "material_code": "MAT-B",
                "material_desc": "Couro Marrom",
                "material_layers": 2,
                "pieces": [
                    {"name": "PecaB", "size": "42", "x": 60, "y": 60, "contour": [{"x": 0, "y": 0}, {"x": 60, "y": 0}, {"x": 60, "y": 40}, {"x": 0, "y": 40}]}
                ],
                "session_shapes": [
                    {"name": "PecaB", "size": "42", "shape_id": "2", "pairs": 10}
                ]
            }
        ]

        dlg = LayoutPrintDialog(self.root, layout_data={
            "layouts": batch_layouts,
            "current_layout_index": 0,
        })
        try:
            # Página 1 (Sessão 101)
            self.assertEqual(dlg.current_layout_index, 0)
            self.assertIn("Sessão #101", dlg.placa_n_de_m)
            self.assertIn("MAT-A", dlg.material_name)
            self.assertEqual(dlg.layout_layers, 4)
            self.assertEqual(len(dlg.placed_pieces), 1)

            # Avança para Página 2 (Sessão 102)
            dlg.next_page()
            self.assertEqual(dlg.current_layout_index, 1)
            self.assertIn("Sessão #102", dlg.placa_n_de_m)
            self.assertIn("MAT-B", dlg.material_name)
            self.assertEqual(dlg.layout_layers, 2)
            self.assertEqual(len(dlg.placed_pieces), 1)

            # Retorna para Página 1
            dlg.prev_page()
            self.assertEqual(dlg.current_layout_index, 0)
            self.assertIn("Sessão #101", dlg.placa_n_de_m)
        finally:
            dlg.destroy()

    def test_on_batch_print_sessions_no_selection_shows_info(self):
        """Valida que on_batch_print_sessions exibe mensagem amigável quando nenhuma sessão está marcada."""
        win = MagicMock(spec=MainWindow)
        win.batch_checked_sessions = set()
        mock_tree = MagicMock()
        mock_tree.selection.return_value = ()
        win.tree_main = mock_tree

        with patch("tkinter.messagebox.showinfo") as mock_info:
            MainWindow.on_batch_print_sessions(win)
            mock_info.assert_called_once()
            args, _ = mock_info.call_args
            self.assertEqual(args[0], "Imprimir em Massa")
            self.assertIn("Nenhuma sessão marcada", args[1])

    def test_batch_print_save_all_pdf(self):
        """Valida a renderização e exportação de todas as páginas em PDF para múltiplas sessões."""
        batch_layouts = [
            {
                "name": "lay0000.lay",
                "session_title": "Sessão #200",
                "width_mm": 1000.0,
                "height_mm": 500.0,
                "material_desc": "EVA Preto",
                "pieces": [{"name": "P1", "size": "40", "x": 10, "y": 10, "contour": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 30}, {"x": 0, "y": 30}]}],
            },
            {
                "name": "lay0000.lay",
                "session_title": "Sessão #201",
                "width_mm": 1000.0,
                "height_mm": 500.0,
                "material_desc": "Tecido Branco",
                "pieces": [{"name": "P2", "size": "41", "x": 20, "y": 20, "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 20}, {"x": 0, "y": 20}]}],
            }
        ]

        dlg = LayoutPrintDialog(self.root, layout_data={"layouts": batch_layouts})
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
                tmp_pdf = tf.name

            try:
                with patch("tkinter.messagebox.askyesnocancel", return_value=True), \
                     patch("tkinter.filedialog.asksaveasfilename", return_value=tmp_pdf), \
                     patch("tkinter.messagebox.showinfo") as mock_info:
                    dlg.save_as_pdf()
                    mock_info.assert_called_once()
                    self.assertTrue(os.path.exists(tmp_pdf))
                    self.assertGreater(os.path.getsize(tmp_pdf), 100)
            finally:
                if os.path.exists(tmp_pdf):
                    os.remove(tmp_pdf)
        finally:
            dlg.destroy()

    def test_on_print_job_folder_sessions(self):
        """Valida que on_print_job_folder_sessions localiza sessões da pasta e chama on_batch_print_sessions."""
        win = MagicMock(spec=MainWindow)
        win.sessions = [
            {"id": 10, "job": "PastaA/Sub1"},
            {"id": 20, "job": "PastaA/Sub2"},
            {"id": 30, "job": "OutraPasta"},
        ]
        MainWindow.on_print_job_folder_sessions(win, "PastaA")
        win.on_batch_print_sessions.assert_called_once()
        _, kwargs = win.on_batch_print_sessions.call_args
        self.assertEqual(kwargs.get("session_ids"), [10, 20])
        self.assertIn("PastaA", kwargs.get("title_context", ""))

    def test_tree_context_menu_contains_print_options(self):
        """Valida que show_tree_context_menu adiciona opções de impressão de sessão e em massa."""
        win = MagicMock(spec=MainWindow)
        win.current_mode = "jobs"
        win.batch_checked_sessions = {188, 189}
        tree_menu = tk.Menu(self.root)
        win.tree_menu = tree_menu
        mock_tree = MagicMock()
        mock_tree.identify_row.return_value = "item_sess"
        mock_tree.selection.return_value = ("item_sess",)
        mock_tree.item.side_effect = lambda it, opt=None: ("session", 188) if opt == "values" else {"values": ("session", 188)}
        win.tree_main = mock_tree
        win.show_popup_menu = MagicMock()

        dummy_event = MagicMock()
        dummy_event.x_root = 100
        dummy_event.y_root = 100
        dummy_event.y = 50

        MainWindow.show_tree_context_menu(win, dummy_event)

        # Inspeciona comandos do menu criado
        labels = [tree_menu.entrycget(i, "label") for i in range(tree_menu.index("end") + 1) if tree_menu.type(i) == "command"]
        self.assertTrue(any("Imprimir Sessão" in lbl for lbl in labels), f"Labels encontrados: {labels}")
        self.assertTrue(any("Imprimir em Massa" in lbl for lbl in labels), f"Labels encontrados: {labels}")


if __name__ == "__main__":
    unittest.main()
