"""
tests/test_shape_format_multiplier.py

Testes automatizados para a funcionalidade de Formato do Molde (1x1, 4x1, 6x1):
1. Função pura shape_multiplier:
   - "1x1" -> 1
   - "4x1" -> 2
   - "6x1" -> 3
   - Tolerância a espaços extras, maiúsculas, 'X' e '×'
   - Casos de borda: None, "", "2x1", strings arbitrárias retornando fallback 1
2. Persistência no DatabaseManager (SQLite):
   - Migração e adição de coluna shape_format
   - create_shape persistindo formato
   - get_shape e get_all_shapes retornando formato (e fallback '1x1' para legados)
   - update_shape persistindo novo formato
3. Interface ShapeEditorView:
   - Combobox 'Formato:' e Label '× N'
   - Desabilitado quando bloqueado, habilitado (readonly) quando desbloqueado
   - Alteração do formato marca dirty (*) e atualiza fator
   - Desfazer (Ctrl+Z) restaura o formato e o fator
   - Salvamento preserva shape_format e limpa o indicador dirty (*)
"""

import copy
import os
import tempfile
import unittest
from unittest.mock import patch
import tkinter as tk
from tkinter import ttk

from cad.layers_rule import shape_multiplier
from database import DatabaseManager
from ui.shape_editor_view import ShapeEditorView


class TestShapeMultiplierPureFunction(unittest.TestCase):
    def test_standard_formats(self):
        self.assertEqual(shape_multiplier("1x1"), 1)
        self.assertEqual(shape_multiplier("4x1"), 2)
        self.assertEqual(shape_multiplier("6x1"), 3)

    def test_case_and_whitespace_variations(self):
        self.assertEqual(shape_multiplier(" 1x1 "), 1)
        self.assertEqual(shape_multiplier("4X1"), 2)
        self.assertEqual(shape_multiplier(" 4 x 1 "), 2)
        self.assertEqual(shape_multiplier("6X1"), 3)
        self.assertEqual(shape_multiplier(" 6 x 1 "), 3)

    def test_unicode_multiplication_sign(self):
        self.assertEqual(shape_multiplier("4×1"), 2)
        self.assertEqual(shape_multiplier("6×1"), 3)
        self.assertEqual(shape_multiplier("1×1"), 1)

    def test_edge_cases_and_fallbacks(self):
        self.assertEqual(shape_multiplier(None), 1)
        self.assertEqual(shape_multiplier(""), 1)
        self.assertEqual(shape_multiplier("   "), 1)
        self.assertEqual(shape_multiplier("2x1"), 1)
        self.assertEqual(shape_multiplier("8x1"), 1)
        self.assertEqual(shape_multiplier("invalido"), 1)
        self.assertEqual(shape_multiplier(123), 1)


class TestShapeFormatDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_shape_format.db")
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass
        if os.path.exists(self.tmp_dir):
            try:
                os.rmdir(self.tmp_dir)
            except Exception:
                pass

    def test_create_and_get_shape_with_format(self):
        shp_id = self.db.create_shape(
            name="Palmilha_4x1",
            contour=[{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 50}],
            shape_format="4x1"
        )
        shp = self.db.get_shape(shp_id)
        self.assertIsNotNone(shp)
        self.assertEqual(shp["shape_format"], "4x1")

    def test_update_shape_format(self):
        shp_id = self.db.create_shape(
            name="Palmilha_Mod",
            contour=[{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 50}],
            shape_format="1x1"
        )
        self.assertEqual(self.db.get_shape(shp_id)["shape_format"], "1x1")

        self.db.update_shape(
            shape_id=shp_id,
            name="Palmilha_Mod_6x1",
            contour=[{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 50}],
            shape_format="6x1"
        )
        shp = self.db.get_shape(shp_id)
        self.assertEqual(shp["name"], "Palmilha_Mod_6x1")
        self.assertEqual(shp["shape_format"], "6x1")

    def test_legacy_shape_defaults_to_1x1(self):
        # 1. Molde inserido sem especificar a coluna shape_format recebe '1x1'
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO shapes (name, color, contour_json, holes_json, stitching_json, folder, size)
            VALUES ('Legado_Sem_Formato', '#000000', '[]', '[]', '[]', '', '41')
            """)
            conn.commit()
            leg_id = cursor.lastrowid

        shp = self.db.get_shape(leg_id)
        self.assertEqual(shp["shape_format"], "1x1")

        all_shapes = self.db.get_all_shapes()
        leg_in_all = next(s for s in all_shapes if s["id"] == leg_id)
        self.assertEqual(leg_in_all["shape_format"], "1x1")

        # 2. Banco pré-existente sem a coluna shape_format: valida auto-migração via init_db()
        legacy_db_path = os.path.join(self.tmp_dir, "legacy_schema.db")
        import sqlite3
        con = sqlite3.connect(legacy_db_path)
        con.execute("""
        CREATE TABLE shapes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER,
            name TEXT NOT NULL,
            color TEXT NOT NULL,
            contour_json TEXT NOT NULL,
            holes_json TEXT DEFAULT '[]',
            stitching_json TEXT DEFAULT '[]',
            folder TEXT DEFAULT '',
            size TEXT DEFAULT '41'
        )
        """)
        con.execute("""
        INSERT INTO shapes (name, color, contour_json, holes_json, stitching_json, folder, size)
        VALUES ('Molde_Antigo_Sem_Coluna', '#000000', '[]', '[]', '[]', '', '41')
        """)
        con.commit()
        con.close()

        legacy_db = DatabaseManager(db_path=legacy_db_path)
        migrated_shp = legacy_db.get_shape(1)
        self.assertIsNotNone(migrated_shp)
        self.assertEqual(migrated_shp["name"], "Molde_Antigo_Sem_Coluna")
        self.assertEqual(migrated_shp["shape_format"], "1x1")


class TestShapeEditorViewFormatUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.geometry("1024x768")
        cls.root.withdraw()
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.test_shape = {
            "id": 101,
            "name": "Gaspea_Teste",
            "size": "42",
            "shape_format": "4x1",
            "contour": [
                {"x": 0.0, "y": 0.0},
                {"x": 120.0, "y": 0.0},
                {"x": 120.0, "y": 70.0},
                {"x": 0.0, "y": 70.0}
            ],
            "holes": [],
            "stitching": []
        }
        self.saved_shapes = []

        def on_save(s):
            self.saved_shapes.append(copy.deepcopy(s))

        self.editor = ShapeEditorView(
            self.root,
            shape_data=self.test_shape,
            on_save=on_save
        )
        self.editor.pack(fill="both", expand=True)
        self.root.update()

    def tearDown(self):
        try:
            self.editor.destroy()
        except Exception:
            pass

    def test_initial_state_locked_and_format_loaded(self):
        # 1. Molde inicia com formato 4x1 e fator × 2
        self.assertEqual(self.editor.cb_shape_format.get(), "4x1")
        self.assertEqual(self.editor.lbl_format_factor.cget("text"), "× 2")

        # 2. Geometria inicia bloqueada por padrão -> combobox desabilitado
        self.assertTrue(self.editor.geometry_locked.get())
        self.assertEqual(str(self.editor.cb_shape_format.cget("state")), "disabled")

    def test_unlock_geometry_enables_combobox(self):
        # Desbloqueia geometria
        self.editor.toggle_geometry_lock()
        self.assertFalse(self.editor.geometry_locked.get())
        self.assertEqual(str(self.editor.cb_shape_format.cget("state")), "readonly")

        # Bloqueia novamente
        self.editor.toggle_geometry_lock()
        self.assertTrue(self.editor.geometry_locked.get())
        self.assertEqual(str(self.editor.cb_shape_format.cget("state")), "disabled")

    def test_change_format_marks_dirty_and_updates_factor(self):
        self.editor.toggle_geometry_lock()
        self.assertEqual(str(self.editor.cb_shape_format.cget("state")), "readonly")

        # Altera para 6x1
        self.editor.cb_shape_format.set("6x1")
        self.editor._on_shape_format_changed()

        self.assertEqual(self.editor.shape["shape_format"], "6x1")
        self.assertEqual(self.editor.lbl_format_factor.cget("text"), "× 3")
        self.assertTrue(self.editor.open_shapes[self.editor.active_shape_index]["is_dirty"])
        self.assertIn("*", self.editor.lbl_title.cget("text"))

    def test_undo_restores_previous_format(self):
        self.editor.toggle_geometry_lock()

        # Altera de 4x1 para 6x1
        self.editor.cb_shape_format.set("6x1")
        self.editor._on_shape_format_changed()
        self.assertEqual(self.editor.shape["shape_format"], "6x1")
        self.assertEqual(self.editor.lbl_format_factor.cget("text"), "× 3")
        self.assertIn("*", self.editor.lbl_title.cget("text"))

        # Executa Ctrl+Z (undo_or_revert)
        self.editor.undo_or_revert()

        # Deve restaurar o formato original 4x1 e fator × 2
        self.assertEqual(self.editor.shape["shape_format"], "4x1")
        self.assertEqual(self.editor.cb_shape_format.get(), "4x1")
        self.assertEqual(self.editor.lbl_format_factor.cget("text"), "× 2")
        self.assertNotIn("*", self.editor.lbl_title.cget("text"))

    @patch("tkinter.messagebox.showinfo")
    def test_save_persists_shape_format_and_clears_dirty(self, mock_info):
        self.editor.toggle_geometry_lock()
        self.editor.cb_shape_format.set("6x1")
        self.editor._on_shape_format_changed()

        self.assertTrue(self.editor.open_shapes[self.editor.active_shape_index]["is_dirty"])
        self.assertIn("*", self.editor.lbl_title.cget("text"))

        # Salva o molde (messagebox mockado para não bloquear a execução)
        self.editor.save_changes()

        self.assertEqual(len(self.saved_shapes), 1)
        self.assertEqual(self.saved_shapes[0]["shape_format"], "6x1")
        self.assertFalse(self.editor.open_shapes[self.editor.active_shape_index]["is_dirty"])
        self.assertNotIn("*", self.editor.lbl_title.cget("text"))

    def test_load_shape_without_format_defaults_to_1x1(self):
        shape_no_fmt = {
            "id": 102,
            "name": "Molde_Antigo",
            "size": "39",
            "contour": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 50}],
            "holes": []
        }
        self.editor.load_shape(shape_no_fmt, replace=True)
        self.root.update()

        self.assertEqual(self.editor.shape.get("shape_format"), "1x1")
        self.assertEqual(self.editor.cb_shape_format.get(), "1x1")
        self.assertEqual(self.editor.lbl_format_factor.cget("text"), "× 1")


if __name__ == "__main__":
    unittest.main()
