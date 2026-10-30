"""
Testes Unitários: ShapeCatalogView (Catálogo de Moldes - Grid View Matrix)
Fase 6.1 — 9 Testes Obrigatórios
"""

import sys
import unittest
from pathlib import Path
import tkinter as tk

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import database as db
from ui.shape_catalog_view import ShapeCatalogView, extract_piece_base_name


class TestShapeCatalogView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()
        cls.db_manager = db.DatabaseManager()
        cls.db_manager.init_db()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.editor_opened_with = None

        def mock_edit_shape(shape_id):
            self.editor_opened_with = shape_id

        self.closed_called = False

        def mock_close():
            self.closed_called = True

        self.view = ShapeCatalogView(
            self.root,
            article_id=1,
            article_name="Artigo Teste",
            db=self.db_manager,
            on_edit_shape=mock_edit_shape,
            on_close=mock_close,
        )

    def tearDown(self):
        try:
            self.view.destroy()
        except Exception:
            pass

    def test_01_catalog_loads_article_with_17_shapes(self):
        """1. test_catalog_loads_article_with_17_shapes — artigo 1 carrega sem erro e com 17 shapes."""
        self.assertEqual(len(self.view.shapes_list), 17)
        self.assertGreater(len(self.view.grid_matrix), 0)

    def test_02_catalog_matrix_dimensions(self):
        """2. test_catalog_matrix_dimensions — colunas = nomes únicos, linhas = tamanhos únicos."""
        # Artigo 1 possui 3 peças bases ('323_PalAcb', 'PALM_CAVA', 'teste2') e 16 tamanhos distintos
        self.assertEqual(len(self.view.piece_names), 3)
        self.assertIn("323_PalAcb", self.view.piece_names)
        self.assertIn("PALM_CAVA", self.view.piece_names)
        self.assertIn("teste2", self.view.piece_names)
        self.assertEqual(len(self.view.sizes_list), 16)
        total_cells = len(self.view.piece_names) * len(self.view.sizes_list)
        self.assertEqual(total_cells, 48)

    def test_03_catalog_sparse_cells_marked_empty(self):
        """3. test_catalog_sparse_cells_marked_empty — 31 células vazias exibem [-]."""
        total_cells = len(self.view.piece_names) * len(self.view.sizes_list)
        filled_count = len(self.view.grid_matrix)
        empty_count = total_cells - filled_count
        self.assertEqual(filled_count, 17)
        self.assertEqual(empty_count, 31)

        # Procura uma coordenada vazia (ex: 'PALM_CAVA' no tamanho '22a')
        empty_coords = None
        for r_idx, sz in enumerate(self.view.sizes_list):
            for c_idx, p in enumerate(self.view.piece_names):
                if (p, sz) not in self.view.grid_matrix:
                    empty_coords = (c_idx, r_idx)
                    break
            if empty_coords:
                break

        self.assertIsNotNone(empty_coords)
        self.view.selected_coords = empty_coords
        self.view.update_info_panel()
        shape = self.view.get_selected_shape()
        self.assertIsNone(shape)
        self.assertIn("Vazio", self.view.lbl_det_status.cget("text"))

    def test_04_catalog_single_click_selects_cell(self):
        """4. test_catalog_single_click_selects_cell — clique atualiza painel info."""
        # Procura coordenada preenchida
        filled_coords = None
        for r_idx, sz in enumerate(self.view.sizes_list):
            for c_idx, p in enumerate(self.view.piece_names):
                if (p, sz) in self.view.grid_matrix:
                    filled_coords = (c_idx, r_idx)
                    break
            if filled_coords:
                break

        self.assertIsNotNone(filled_coords)
        c_idx, r_idx = filled_coords

        # Simula evento de clique
        click_x = self.view.sidebar_w + c_idx * self.view.cell_w + 10
        click_y = self.view.header_h + r_idx * self.view.cell_h + 10

        class MockEvent:
            pass

        event = MockEvent()
        event.x = click_x
        event.y = click_y

        self.view.on_canvas_click(event)
        self.assertEqual(self.view.selected_coords, (c_idx, r_idx))
        selected_shape = self.view.get_selected_shape()
        self.assertIsNotNone(selected_shape)
        self.assertIn(selected_shape["name"], self.view.lbl_det_piece.cget("text"))
        self.assertIn("Pronto", self.view.lbl_det_status.cget("text"))

    def test_05_catalog_double_click_opens_editor(self):
        """5. test_catalog_double_click_opens_editor — duplo-clique chama show_shape_editor."""
        filled_coords = None
        for r_idx, sz in enumerate(self.view.sizes_list):
            for c_idx, p in enumerate(self.view.piece_names):
                if (p, sz) in self.view.grid_matrix:
                    filled_coords = (c_idx, r_idx)
                    break
            if filled_coords:
                break

        c_idx, r_idx = filled_coords
        click_x = self.view.sidebar_w + c_idx * self.view.cell_w + 10
        click_y = self.view.header_h + r_idx * self.view.cell_h + 10

        class MockEvent:
            pass

        event = MockEvent()
        event.x = click_x
        event.y = click_y

        self.view.on_canvas_double_click(event)
        self.assertIsNotNone(self.editor_opened_with)
        shape = self.view.get_selected_shape()
        self.assertEqual(self.editor_opened_with, shape["id"])

    def test_06_catalog_keyboard_navigation(self):
        """6. test_catalog_keyboard_navigation — setas + Enter funcionam."""
        self.view.selected_coords = (0, 0)
        self.view.navigate_selection(1, 0)
        self.assertEqual(self.view.selected_coords, (1, 0))

        self.view.navigate_selection(0, 2)
        self.assertEqual(self.view.selected_coords, (1, 2))

        # Enter abre peça selecionada se preenchida
        # Encontra preenchida
        for r in range(len(self.view.sizes_list)):
            for c in range(len(self.view.piece_names)):
                p = self.view.piece_names[c]
                s = self.view.sizes_list[r]
                if (p, s) in self.view.grid_matrix:
                    self.view.selected_coords = (c, r)
                    break
            if self.view.get_selected_shape():
                break

        self.editor_opened_with = None
        self.view.open_selected_shape()
        self.assertIsNotNone(self.editor_opened_with)

    def test_07_catalog_escape_closes(self):
        """7. test_catalog_escape_closes — Esc fecha sem erro."""
        self.closed_called = False
        self.view.on_close_click()
        self.assertTrue(self.closed_called)

    def test_08_catalog_persists_index_creation(self):
        """8. test_catalog_persists_index_creation — índice SQL existe após init_db()."""
        with self.db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("PRAGMA index_list(shapes)")
            indexes = [r["name"] if hasattr(r, "__getitem__") and "name" in r else r[1] for r in c.fetchall()]
            self.assertIn("idx_shapes_article_size_name", indexes)

            # Valida EXPLAIN QUERY PLAN utilizando o índice
            c.execute(
                "EXPLAIN QUERY PLAN SELECT id, name, size FROM shapes WHERE article_id = ? ORDER BY size, name",
                (1,),
            )
            plan = [str(dict(r) if hasattr(r, "keys") else r) for r in c.fetchall()]
            self.assertTrue(any("idx_shapes_article_size_name" in p for p in plan))

    def test_09_catalog_badge_parity_default_2(self):
        """9. test_catalog_badge_parity_default_2 — [2*] hardcoded aparece."""
        # Verifica se o badge de paridade padrão aparece no painel ou molde
        catalog_data = self.db_manager.get_article_shape_catalog(1)
        for s in catalog_data:
            self.assertEqual(s.get("pairs_per_shape", 2), 2)

        # Atualiza painel e verifica se o rótulo de paridade exibe [2*]
        for r_idx, sz in enumerate(self.view.sizes_list):
            for c_idx, p in enumerate(self.view.piece_names):
                if (p, sz) in self.view.grid_matrix:
                    self.view.selected_coords = (c_idx, r_idx)
                    break
            if self.view.get_selected_shape():
                break

        self.view.update_info_panel()
        self.assertIn("[2*]", self.view.lbl_det_parity.cget("text"))


if __name__ == "__main__":
    unittest.main()
