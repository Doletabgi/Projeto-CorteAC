"""
tests/test_shape_catalog_border_cases.py

Testes de casos de borda dos botões complexos do ShapeCatalogView (Fase 6.2 - Tarefa 4):
1. test_merge_file_duplicate_name_appends_suffix
2. test_save_as_preserves_stitching_holes_grain_angle
3. test_save_syncs_with_editor_view
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
import tkinter as tk

import database as db_mod
from cad.die_parser import parse_die_file, save_die_file
from ui.shape_catalog_view import ShapeCatalogView


class TestShapeCatalogBorderCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.geometry("1000x700")
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

    def test_merge_file_duplicate_name_appends_suffix(self):
        """
        Tarefa 4.1:
        Mesclar arquivo com nome existente ("teste2") deve duplicar com sufixo numérico ("teste2 (2)", "teste2 (3)").
        """
        shape_data = {
            "name": "teste2",
            "contour": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 50}, {"x": 0, "y": 50}],
            "holes": [],
            "stitching": [],
            "size": "41"
        }

        new_ids = []
        try:
            # 1ª mesclagem: já existe "teste2" no artigo 1
            new_id_1 = self.catalog.merge_shape_data(shape_data)
            new_ids.append(new_id_1)
            self.assertIsNotNone(new_id_1)
            created_shape_1 = self.db.get_shape(new_id_1)
            self.assertEqual(created_shape_1["name"], "teste2 (2)", "Primeira duplicata deve receber sufixo (2)")

            # 2ª mesclagem: agora já existe "teste2" e "teste2 (2)"
            new_id_2 = self.catalog.merge_shape_data(shape_data)
            new_ids.append(new_id_2)
            self.assertIsNotNone(new_id_2)
            created_shape_2 = self.db.get_shape(new_id_2)
            self.assertEqual(created_shape_2["name"], "teste2 (3)", "Segunda duplicata deve receber sufixo (3)")
        finally:
            # Limpeza do banco de dados para os registros temporários
            if new_ids:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"DELETE FROM shapes WHERE id IN ({','.join(['?']*len(new_ids))})", tuple(new_ids))
                    conn.commit()

    def test_save_as_preserves_stitching_holes_grain_angle(self):
        """
        Tarefa 4.2:
        Exportar para .die e reimportar (round-trip) deve preservar contorno, furos, costuras e grain_angle.
        """
        sample_shape = {
            "id": 9999,
            "name": "RoundTrip_Test_Piece",
            "contour": [
                {"x": 0.0, "y": 0.0},
                {"x": 120.0, "y": 0.0},
                {"x": 150.0, "y": 60.0},
                {"x": 60.0, "y": 80.0},
                {"x": 0.0, "y": 30.0}
            ],
            "holes": [
                {"x": 30.0, "y": 25.0, "r": 3.0},
                {"x": 90.0, "y": 25.0, "r": 2.5}
            ],
            "stitching": [
                [{"x": 15.0, "y": 15.0}, {"x": 60.0, "y": 20.0}, {"x": 105.0, "y": 15.0}],
                [{"x": 20.0, "y": 50.0}, {"x": 80.0, "y": 50.0}]
            ],
            "size": "42",
            "metadata": {
                "grain_angle_deg": 0.0
            }
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "test_roundtrip.die"
            save_die_file(sample_shape, str(file_path))
            self.assertTrue(file_path.exists(), "Arquivo .die deve ser gerado no disco.")

            reimported = parse_die_file(str(file_path))

            # Verifica contorno
            self.assertEqual(len(reimported["contour"]), len(sample_shape["contour"]), "Contorno deve ter mesma quantidade de pontos.")
            for pt_orig, pt_reimp in zip(sample_shape["contour"], reimported["contour"]):
                self.assertAlmostEqual(pt_orig["x"], pt_reimp["x"], places=1)
                self.assertAlmostEqual(pt_orig["y"], pt_reimp["y"], places=1)

            # Verifica furos
            self.assertEqual(len(reimported["holes"]), len(sample_shape["holes"]), "Furos devem ser preservados.")
            for h_orig, h_reimp in zip(sample_shape["holes"], reimported["holes"]):
                self.assertAlmostEqual(h_orig["x"], h_reimp["x"], places=1)
                self.assertAlmostEqual(h_orig["y"], h_reimp["y"], places=1)

            # Verifica costuras (stitching)
            self.assertEqual(len(reimported["stitching"]), len(sample_shape["stitching"]), "Costuras devem ter mesma quantidade de polylines.")
            for poly_orig, poly_reimp in zip(sample_shape["stitching"], reimported["stitching"]):
                self.assertEqual(len(poly_orig), len(poly_reimp), "Cada polyline de costura deve preservar seus pontos.")
                for pt_orig, pt_reimp in zip(poly_orig, poly_reimp):
                    self.assertAlmostEqual(pt_orig["x"], pt_reimp["x"], places=1)
                    self.assertAlmostEqual(pt_orig["y"], pt_reimp["y"], places=1)

            # Verifica grain_angle
            grain = reimported.get("metadata", {}).get("grain_angle_deg")
            self.assertIsNotNone(grain, "Grain angle deve estar presente nos metadados.")
            self.assertAlmostEqual(grain, 0.0, places=1)

    def test_save_syncs_with_editor_view(self):
        """
        Tarefa 4.3:
        Verifica que action_save() sincroniza e invalida cache do catálogo quando dados são alterados externamente (ex: no editor).
        """
        # Encontra um molde existente no artigo 1
        shapes = self.db.get_shapes_by_article(1)
        self.assertGreater(len(shapes), 0)
        target = shapes[0]
        orig_contour = copy.deepcopy(target["contour"])

        # Simula alteração externa feita pelo ShapeEditorView no banco
        modified_contour = copy.deepcopy(orig_contour)
        modified_contour[0]["x"] = modified_contour[0]["x"] + 15.0

        self.db.update_shape(
            shape_id=target["id"],
            name=target["name"],
            contour=modified_contour,
            holes=target.get("holes", []),
            stitching=target.get("stitching", []),
            folder=target.get("folder"),
            size=target.get("size")
        )

        try:
            # Invoca ação de salvar/sincronizar no catálogo
            self.catalog.action_save()

            # Encontra o molde atualizado na matriz do catálogo
            base_p = target["name"]
            size = str(target.get("size") or "41")
            cached_shape = None
            for s in self.catalog.shapes_list:
                if s["id"] == target["id"]:
                    cached_shape = s
                    break

            self.assertIsNotNone(cached_shape, "Molde deve existir no catálogo após sincronização.")
            self.assertEqual(
                cached_shape["contour"][0]["x"],
                modified_contour[0]["x"],
                "Catálogo deve refletir imediatamente o contorno modificado pelo editor."
            )
        finally:
            # Restaura contorno original no banco
            self.db.update_shape(
                shape_id=target["id"],
                name=target["name"],
                contour=orig_contour,
                holes=target.get("holes", []),
                stitching=target.get("stitching", []),
                folder=target.get("folder"),
                size=target.get("size")
            )


if __name__ == "__main__":
    unittest.main()
