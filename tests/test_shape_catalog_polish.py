"""
tests/test_shape_catalog_polish.py

Testes de polimento do ShapeCatalogView (Fase 6.2):
- Validação de fallback headless (Tarefa 3)
- Zoom e Pan no Grid Canvas (Tarefa 5)
- Filtros por tamanho e peça (Tarefa 6)
"""
import copy
import unittest
from unittest.mock import patch
import tkinter as tk

import database as db_mod
from ui.shape_catalog_view import ShapeCatalogView
from ui.shape_editor_view import ShapeEditorView


class TestShapeCatalogPolish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.geometry("1100x700")
        cls.root.withdraw()
        cls.db = db_mod.DatabaseManager()
        cls.db.init_db()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.catalog = ShapeCatalogView(self.root, article_id=1, db=self.db)
        self.catalog._suppress_dialogs = True
        self.catalog.pack(fill="both", expand=True)

    def tearDown(self):
        try:
            self.catalog.destroy()
        except Exception:
            pass

    # =========================================================================
    # Tarefa 3 / GATE C: Fallback Headless
    # =========================================================================
    def test_editor_dimensions_fallback_only_when_headless(self):
        """
        Tarefa 3 / GATE C:
        - winfo_width() == 800 (tela real) -> fallback NÃO ativa (_used_headless_fallback is False)
        - winfo_width() == 0 (headless) -> fallback ativa (_used_headless_fallback is True)
        """
        view = ShapeEditorView(self.root)
        view.pack(fill="both", expand=True)

        # 1. Simula tela real com dimensões 800x600
        with patch.object(view.canvas, "winfo_width", return_value=800), \
             patch.object(view.canvas, "winfo_height", return_value=600):
            view.redraw()
            self.assertFalse(view._used_headless_fallback, "Em tela real (800x600), o fallback NÃO deve ativar.")

        # 2. Simula ambiente headless ou janela não mapeada (0x0)
        with patch.object(view.canvas, "winfo_width", return_value=0), \
             patch.object(view.canvas, "winfo_height", return_value=0):
            view.redraw()
            self.assertTrue(view._used_headless_fallback, "Em ambiente headless (0x0), o fallback DEVE ativar.")

        view.destroy()

    # =========================================================================
    # Tarefa 5 / GATE E: Zoom e Pan
    # =========================================================================
    def test_zoom_in_increases_scale_by_20_percent(self):
        """Verifica que zoom in aumenta a escala em 20% (fator 1.2x)."""
        self.assertEqual(self.catalog.zoom_factor, 1.0)
        self.assertEqual(self.catalog.cell_w, 110)

        self.catalog.zoom_step(1.2)
        self.assertAlmostEqual(self.catalog.zoom_factor, 1.2, places=2)
        self.assertEqual(self.catalog.cell_w, int(110 * 1.2))
        self.assertEqual(self.catalog.cell_h, int(75 * 1.2))

    def test_zoom_reset_returns_to_100_percent(self):
        """Verifica que reset_zoom restaura a escala para 100% (1.0x)."""
        self.catalog.zoom_step(1.2)
        self.catalog.zoom_step(1.2)
        self.assertGreater(self.catalog.zoom_factor, 1.2)

        self.catalog.reset_zoom()
        self.assertEqual(self.catalog.zoom_factor, 1.0)
        self.assertEqual(self.catalog.cell_w, 110)
        self.assertEqual(self.catalog.cell_h, 75)

    def test_zoom_limits_respected(self):
        """Verifica que os limites de zoom (0.5x mínimo e 4.0x máximo) são estritamente respeitados."""
        # Tenta zoom out excessivo
        for _ in range(10):
            self.catalog.zoom_step(0.5)
        self.assertGreaterEqual(self.catalog.zoom_factor, 0.5)
        self.assertEqual(self.catalog.zoom_factor, 0.5)

        # Tenta zoom in excessivo
        for _ in range(15):
            self.catalog.zoom_step(1.5)
        self.assertLessEqual(self.catalog.zoom_factor, 4.0)
        self.assertEqual(self.catalog.zoom_factor, 4.0)

    def test_pan_moves_viewport_without_affecting_data(self):
        """Verifica que a ação de pan move a visualização sem alterar os dados do catálogo ou do banco."""
        shapes_before = copy.deepcopy(self.catalog.shapes_list)
        matrix_before = copy.deepcopy(self.catalog.grid_matrix)

        # Executa pan simulado via scan_mark e scan_dragto
        class DummyEvent:
            x = 100
            y = 100

        ev_start = DummyEvent()
        self.catalog.on_pan_start(ev_start)

        ev_move = DummyEvent()
        ev_move.x = 250
        ev_move.y = 180
        self.catalog.on_pan_motion(ev_move)
        self.catalog.on_pan_end(ev_move)

        # Confirma que os dados permaneceram 100% íntegros
        self.assertEqual(len(self.catalog.shapes_list), len(shapes_before))
        self.assertEqual(len(self.catalog.grid_matrix), len(matrix_before))
        for key in matrix_before:
            self.assertEqual(
                self.catalog.grid_matrix[key]["contour"],
                matrix_before[key]["contour"],
                "Coordenadas dos moldes não devem ser alteradas por pan."
            )

    # =========================================================================
    # Tarefa 6 / GATE F: Filtros por Tamanho e Peça
    # =========================================================================
    def test_filter_by_size_shows_only_matching_row(self):
        """Verifica que filtrar por tamanho exibe apenas a linha daquele tamanho."""
        self.assertGreater(len(self.catalog.all_sizes_list), 1)

        # Aplica filtro pelo tamanho "41"
        self.catalog.filter_size = "41"
        self.catalog.apply_filters()

        self.assertEqual(len(self.catalog.sizes_list), 1)
        self.assertEqual(self.catalog.sizes_list[0], "41")
        # Colunas devem permanecer todas
        self.assertEqual(len(self.catalog.piece_names), len(self.catalog.all_piece_names))

    def test_filter_by_shape_shows_only_matching_column(self):
        """Verifica que filtrar por peça exibe apenas a coluna daquela peça."""
        self.assertGreater(len(self.catalog.all_piece_names), 1)

        target_piece = self.catalog.all_piece_names[0]
        self.catalog.filter_piece = target_piece
        self.catalog.apply_filters()

        self.assertEqual(len(self.catalog.piece_names), 1)
        self.assertEqual(self.catalog.piece_names[0], target_piece)
        # Linhas devem permanecer todas
        self.assertEqual(len(self.catalog.sizes_list), len(self.catalog.all_sizes_list))

    def test_filter_reset_shows_all_cells(self):
        """Verifica que reset_filters restaura a visualização de todas as células."""
        # Aplica filtros
        self.catalog.filter_size = "41"
        self.catalog.filter_piece = self.catalog.all_piece_names[0]
        self.catalog.apply_filters()
        self.assertEqual(len(self.catalog.sizes_list), 1)
        self.assertEqual(len(self.catalog.piece_names), 1)

        # Restaura tudo
        self.catalog.reset_filters()
        self.assertEqual(self.catalog.filter_size, "Todos")
        self.assertEqual(self.catalog.filter_piece, "Todas")
        self.assertEqual(len(self.catalog.sizes_list), len(self.catalog.all_sizes_list))
        self.assertEqual(len(self.catalog.piece_names), len(self.catalog.all_piece_names))

    def test_filter_combined_size_and_shape(self):
        """Verifica combinação simultânea de filtro de tamanho e peça."""
        target_size = "41"
        target_piece = "teste2"

        self.catalog.filter_size = target_size
        self.catalog.filter_piece = target_piece
        self.catalog.apply_filters()

        self.assertEqual(self.catalog.sizes_list, [target_size])
        self.assertEqual(self.catalog.piece_names, [target_piece])

        # Se existir molde nessa interseção, ele deve estar acessível
        shape = self.catalog.get_selected_shape()
        if (target_piece, target_size) in self.catalog.grid_matrix:
            self.assertIsNotNone(shape)
            self.assertEqual(shape.get("size"), target_size)

    def test_filters_do_not_persist_on_reload(self):
        """Verifica que ao recarregar ou abrir o catálogo, os filtros voltam ao padrão ('Todos', 'Todas') e zoom 100%."""
        self.catalog.filter_size = "41"
        self.catalog.filter_piece = "teste2"
        self.catalog.zoom_step(1.5)
        self.catalog.apply_filters()

        # Cria nova instância do catálogo (simulando reabertura pelo operador)
        new_catalog = ShapeCatalogView(self.root, article_id=1, db=self.db)
        new_catalog._suppress_dialogs = True
        try:
            self.assertEqual(new_catalog.zoom_factor, 1.0, "Zoom inicial deve ser 100% (1.0x).")
            self.assertEqual(new_catalog.filter_size, "Todos", "Filtro de tamanho inicial deve ser 'Todos'.")
            self.assertEqual(new_catalog.filter_piece, "Todas", "Filtro de peça inicial deve ser 'Todas'.")
            self.assertEqual(len(new_catalog.piece_names), len(new_catalog.all_piece_names))
            self.assertEqual(len(new_catalog.sizes_list), len(new_catalog.all_sizes_list))
        finally:
            new_catalog.destroy()

    def test_filter_then_zoom_keeps_filtered_cell_visible(self):
        """
        Tarefa 3 (Fase 6.2.1): Teste de interação Filtro + Zoom.
        Valida que ao filtrar por tamanho/peça e aplicar zoom in, as células
        filtradas permanecem corretamente identificadas e visíveis no viewport.
        """
        # 1. Filtra por um tamanho existente no artigo 1
        self.assertTrue(len(self.catalog.all_sizes_list) > 0, "Catálogo deve possuir tamanhos carregados.")
        target_size = self.catalog.all_sizes_list[0]

        self.catalog.filter_size = target_size
        self.catalog.apply_filters()
        self.catalog.redraw_grid()

        # 2. Obtém as células visíveis filtradas
        visible_cells = self.catalog.get_visible_cells()
        self.assertGreater(len(visible_cells), 0, f"Deve haver pelo menos uma célula visível para o tamanho {target_size}.")
        for piece, size in visible_cells:
            self.assertEqual(size, target_size, f"Célula visível deve pertencer ao tamanho filtrado {target_size}.")

        # 3. Aplica zoom in de 1.5x
        self.catalog.zoom_step(1.5)
        self.assertEqual(self.catalog.zoom_factor, 1.5)
        self.assertEqual(self.catalog.cell_w, int(self.catalog.base_cell_w * 1.5))
        self.assertEqual(self.catalog.cell_h, int(self.catalog.base_cell_h * 1.5))

        # 4. Verifica visibilidade no viewport para a primeira célula filtrada (col 0, row 0)
        self.assertTrue(
            self.catalog.is_cell_in_viewport(0, 0),
            "Célula filtrada (0, 0) deve estar visível no viewport após zoom.",
        )
        # Índice fora dos limites deve retornar False
        self.assertFalse(self.catalog.is_cell_in_viewport(999, 999))

        # 5. Restaura zoom e filtros
        self.catalog.reset_zoom()
        self.catalog.reset_filters()
        self.assertEqual(self.catalog.zoom_factor, 1.0)
        self.assertEqual(len(self.catalog.sizes_list), len(self.catalog.all_sizes_list))


if __name__ == "__main__":
    unittest.main()
