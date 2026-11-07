"""
tests/test_layout_editor_add_shape.py

Testes automatizados para a funcionalidade do botão (+) no Layout Editor:
- Diálogo AddShapesDialog para selecionar pasta no catálogo ou importar .die do disco
- Inclusão do molde fora do layout em session_shapes, sidebar_targets e placed_pieces
- Preservação de contorno, furos (holes), costuras (stitching) e recortes internos (internal_cuts)
- Menu de contexto com botão direito no (+)
"""

import os
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from ui.layout_editor_view import LayoutEditorView
from ui.add_shapes_dialog import AddShapesDialog


SAMPLE_CONTOUR = [
    {"x": 0.0, "y": 0.0},
    {"x": 60.0, "y": 0.0},
    {"x": 60.0, "y": 40.0},
    {"x": 0.0, "y": 40.0},
]

SAMPLE_HOLES = [
    [{"x": 10.0, "y": 10.0}, {"x": 15.0, "y": 10.0}, {"x": 15.0, "y": 15.0}, {"x": 10.0, "y": 15.0}]
]

SAMPLE_STITCHING = [
    [{"x": 5.0, "y": 5.0}, {"x": 55.0, "y": 5.0}]
]


class TestLayoutEditorAddShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.has_display = True
        except tk.TclError:
            cls.root = None
            cls.has_display = False

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.has_display:
            self.skipTest("Tkinter display not available")
        self.view = LayoutEditorView(self.root, layout_name="[TEST_ADD_SHAPE]", load_sample=False)
        self.view.pack()
        self.view.set_sheet_size(1200.0, 1000.0)
        self.view.update_idletasks()

    def tearDown(self):
        try:
            self.view.destroy()
        except Exception:
            pass

    def test_01_btn_add_configuration(self):
        """Verifica se o botão btn_add foi criado e configurado para abrir o diálogo de seleção de pasta."""
        self.assertTrue(hasattr(self.view, "btn_add_shape"))
        self.assertIsNotNone(self.view.btn_add_shape)
        cmd_str = str(self.view.btn_add_shape.cget("command"))
        self.assertIn("open_add_shape_dialog", cmd_str)

    def test_02_get_all_catalog_shapes_with_db(self):
        """Verifica se _get_all_catalog_shapes busca moldes do banco de dados quando disponível."""
        mock_db = MagicMock()
        mock_db.get_shapes.return_value = [
            {"id": "s1", "name": "Biqueira", "size": "40", "folder": "faca", "contour": SAMPLE_CONTOUR},
            {"id": "s2", "name": "Traseiro", "size": "41", "folder": "807266", "contour": SAMPLE_CONTOUR},
        ]
        self.view.db = mock_db
        shapes = self.view._get_all_catalog_shapes()
        self.assertEqual(len(shapes), 2)
        self.assertEqual(shapes[0]["folder"], "faca")
        self.assertEqual(shapes[1]["folder"], "807266")

    def test_03_on_shapes_added_to_layout_places_pieces_and_updates_targets(self):
        """Ao confirmar a adição de moldes, eles devem ser adicionados a session_shapes, sidebar_targets e placed_pieces."""
        initial_pieces = len(self.view.placed_pieces)
        new_shape = {
            "id": "ext_shape_99",
            "name": "Molde Externo",
            "size": "42",
            "folder": "pasta_especial",
            "contour": SAMPLE_CONTOUR,
            "holes": SAMPLE_HOLES,
            "stitching": SAMPLE_STITCHING,
            "internal_cuts": [],
            "pairs": 5,
            "resto": 0,
        }

        self.view._on_shapes_added_to_layout([new_shape])

        # session_shapes atualizado
        self.assertTrue(any(s.get("id") == "ext_shape_99" for s in self.view.session_shapes))

        # sidebar_targets atualizado com holes e stitching
        tgt = next((t for t in self.view.sidebar_targets if t.get("id") == "ext_shape_99"), None)
        self.assertIsNotNone(tgt)
        self.assertEqual(tgt["name"], "Molde Externo")
        self.assertEqual(len(tgt.get("holes", [])), 1)
        self.assertEqual(len(tgt.get("stitching", [])), 1)

        # placed_pieces atualizado com nova peça
        self.assertEqual(len(self.view.placed_pieces), initial_pieces + 1)
        placed = self.view.placed_pieces[-1]
        self.assertEqual(placed["target_id"], "ext_shape_99")
        self.assertEqual(placed["name"], "Molde Externo")
        self.assertEqual(len(placed.get("holes", [])), 1)
        self.assertEqual(len(placed.get("stitching", [])), 1)
        self.assertEqual(self.view.selected_index, len(self.view.placed_pieces) - 1)

    def test_04_open_add_shape_dialog_instantiation(self):
        """Verifica se open_add_shape_dialog abre o AddShapesDialog com os parâmetros corretos."""
        with patch("ui.layout_editor_view.AddShapesDialog") as mock_dialog:
            self.view.open_add_shape_dialog()
            mock_dialog.assert_called_once()
            _, kwargs = mock_dialog.call_args
            self.assertEqual(kwargs.get("title_text"), "Adicionar Shape ao Layout")
            self.assertEqual(kwargs.get("action_button_text"), "➕ Adicionar ao Layout")
            self.assertIn("escolha a pasta abaixo", kwargs.get("header_instruction", ""))

    def test_05_open_add_shape_file_dialog_import_die(self):
        """Verifica se open_add_shape_file_dialog importa arquivos .die e os coloca na mesa de corte."""
        # Cria arquivo .die temporário com conteúdo DXF/DIE simulado
        die_content = "0\nSECTION\n2\nENTITIES\n0\nLINE\n10\n0.0\n20\n0.0\n11\n50.0\n21\n0.0\n0\nENDSEC\n0\nEOF\n"
        with tempfile.NamedTemporaryFile(suffix=".die", mode="w", delete=False) as f:
            f.write(die_content)
            temp_path = f.name

        try:
            with patch("tkinter.filedialog.askopenfilenames", return_value=[temp_path]):
                with patch("ui.layout_editor_view.parse_die_file", return_value={
                    "name": "DieTestShape",
                    "contour": SAMPLE_CONTOUR,
                    "holes": [],
                    "stitching": [],
                    "size": "41"
                }):
                    initial_count = len(self.view.placed_pieces)
                    self.view.open_add_shape_file_dialog()
                    self.assertEqual(len(self.view.placed_pieces), initial_count + 1)
                    last_piece = self.view.placed_pieces[-1]
                    self.assertEqual(last_piece["name"], "DieTestShape")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_06_add_shapes_dialog_import_die_button(self):
        """Verifica se AddShapesDialog possui o botão de importar do disco e atualiza a pasta."""
        shapes_sample = [
            {"id": "c1", "name": "Shape 1", "folder": "faca", "contour": SAMPLE_CONTOUR},
            {"id": "c2", "name": "Shape 2", "folder": "807266", "contour": SAMPLE_CONTOUR},
        ]
        dialog = AddShapesDialog(
            self.view,
            all_shapes=shapes_sample,
            current_session_shapes=[],
            on_add_callback=lambda s: None,
            title_text="Teste AddShapesDialog"
        )
        self.view.update_idletasks()

        # O botão do disco deve existir no filter_bar
        self.assertTrue(hasattr(dialog, "btn_import_disk"))
        # As pastas iniciais no combo devem conter (Todas as Pastas), faca, 807266
        values = dialog.cb_folder["values"]
        self.assertIn("(Todas as Pastas)", values)
        self.assertIn("faca", values)
        self.assertIn("807266", values)

        dialog.destroy()

    def test_07_right_click_context_menu(self):
        """Verifica se o clique com botão direito no botão (+) aciona o menu popup com opções."""
        dummy_event = MagicMock()
        dummy_event.x_root = 100
        dummy_event.y_root = 100
        with patch("tkinter.Menu.tk_popup") as mock_popup:
            self.view.show_add_shape_context_menu(dummy_event)
            mock_popup.assert_called_once_with(100, 100)

    def test_08_folder_filtering_in_dialog(self):
        """Verifica se a seleção de pasta no combobox filtra os moldes exibidos na árvore."""
        shapes_sample = [
            {"id": "c1", "name": "Shape Faca 1", "folder": "faca", "contour": SAMPLE_CONTOUR},
            {"id": "c2", "name": "Shape Faca 2", "folder": "faca", "contour": SAMPLE_CONTOUR},
            {"id": "c3", "name": "Shape 807266", "folder": "807266", "contour": SAMPLE_CONTOUR},
        ]
        dialog = AddShapesDialog(
            self.view,
            all_shapes=shapes_sample,
            current_session_shapes=[],
            on_add_callback=lambda s: None
        )
        self.view.update_idletasks()

        # Filtrar por '807266'
        dialog.cb_folder.set("807266")
        dialog.filter_tree()
        children = dialog.tree.get_children()
        self.assertEqual(len(children), 1)
        item_vals = dialog.tree.item(children[0], "values")
        self.assertEqual(item_vals[1], "c3")

        # Filtrar por '(Todas as Pastas)'
        dialog.cb_folder.set("(Todas as Pastas)")
        dialog.filter_tree()
        self.assertEqual(len(dialog.tree.get_children()), 3)

        dialog.destroy()

    def test_09_dialog_import_die_files_updates_folder(self):
        """Verifica se import_die_files no AddShapesDialog adiciona a nova pasta no combobox e seleciona os moldes importados."""
        shapes_sample = [
            {"id": "c1", "name": "Shape 1", "folder": "faca", "contour": SAMPLE_CONTOUR},
        ]
        dialog = AddShapesDialog(
            self.view,
            all_shapes=shapes_sample,
            current_session_shapes=[],
            on_add_callback=lambda s: None
        )
        self.view.update_idletasks()

        with tempfile.TemporaryDirectory() as tmp_dir:
            die_file = Path(tmp_dir) / "novo_molde.die"
            die_file.write_text("0\nSECTION\n0\nEOF\n")
            folder_name = Path(tmp_dir).name

            with patch("tkinter.filedialog.askopenfilenames", return_value=[str(die_file)]):
                with patch("ui.add_shapes_dialog.parse_die_file", return_value={
                    "name": "novo_molde",
                    "contour": SAMPLE_CONTOUR,
                    "holes": [],
                    "stitching": [],
                    "size": "41"
                }):
                    dialog.import_die_files()
                    # A nova pasta deve estar no cb_folder
                    self.assertIn(folder_name, dialog.cb_folder["values"])
                    # O novo molde deve estar na lista all_shapes
                    self.assertTrue(any(s.get("name") == "novo_molde" for s in dialog.all_shapes))
                    # O novo molde deve estar marcado como selecionado
                    new_item = next(s for s in dialog.all_shapes if s.get("name") == "novo_molde")
                    self.assertTrue(dialog.selected_map.get(new_item["id"]))

        dialog.destroy()


if __name__ == "__main__":
    unittest.main()
