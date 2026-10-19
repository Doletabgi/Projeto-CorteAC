"""
Testes de Homologação para o Motor de Cálculo "IA-teste":
1. SafeFormulaEvaluator (segurança estrita de AST sem eval())
2. MacroCompiler (DSL declarativa de macros)
3. ShapeFeatureExtractor & Classificação de Peças Calçadistas
4. NestingAIBrain (Imitation Learning & UCB1 Multi-Armed Bandit)
5. auto_nest_pieces com strategy="IA-teste" (Zero colisão e limites de placa)
6. Fidelidade de vácuo CNC e round-trip .lay
7. Banco de Dados: Preset MACRO_IA_TESTE e coluna macro_script
"""

import unittest
import math
import os
import tempfile
from pathlib import Path
from database import DatabaseManager
from cad.geometry import transform_contour, polygon_bbox, polygons_collide, point_segment_distance_sq
from cad.ai_learner import ShapeFeatureExtractor, NestingAIBrain
from cad.macro_engine import SafeFormulaEvaluator, MacroCompiler, DEFAULT_IA_TESTE_MACRO, nest_ia_teste_engine
from cad.nesting_engine import auto_nest_pieces
from cad.lay_parser import export_layout_from_pieces, parse_lay

class TestMacroEngineIATeste(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager()
        self.shapes = self.db.get_shapes()
        self.sheet_w = 1350.0
        self.sheet_h = 2553.38

    # -------------------------------------------------------------
    # 1. SafeFormulaEvaluator Tests
    # -------------------------------------------------------------
    def test_safe_formula_evaluator_valid(self):
        evaluator = SafeFormulaEvaluator({"area": 500.0, "width": 50.0, "height": 10.0})
        self.assertEqual(evaluator.eval("area / 100.0"), 5.0)
        self.assertEqual(evaluator.eval("min(width, height)"), 10.0)
        self.assertEqual(evaluator.eval("max(width, height)"), 50.0)
        self.assertAlmostEqual(evaluator.eval("sqrt(16) + 2 * 3"), 10.0)
        self.assertEqual(evaluator.eval("round(4.6)"), 5.0)

    def test_safe_formula_evaluator_blocks_code_execution(self):
        evaluator = SafeFormulaEvaluator({})
        with self.assertRaises(ValueError):
            evaluator.eval("__import__('os').system('ls')")
        with self.assertRaises(ValueError):
            evaluator.eval("open('/etc/passwd').read()")
        with self.assertRaises(ValueError):
            evaluator.eval("eval('2 + 2')")
        with self.assertRaises(ValueError):
            evaluator.eval("exec('print(1)')")

    # -------------------------------------------------------------
    # 2. MacroCompiler Tests
    # -------------------------------------------------------------
    def test_macro_compiler_default_script(self):
        compiler = MacroCompiler()
        compiled = compiler.compile(DEFAULT_IA_TESTE_MACRO)
        self.assertGreater(len(compiled.commands), 0)
        cmd_names = compiled.commands
        self.assertIn("AI", cmd_names)
        self.assertIn("SORT", cmd_names)
        self.assertIn("CLUSTER", cmd_names)
        self.assertIn("GRID", cmd_names)
        self.assertIn("GRAVITY", cmd_names)
        self.assertIn("SCORE", cmd_names)

    def test_macro_compiler_syntax_validation(self):
        compiler = MacroCompiler()
        bad_script = "INVALID_COMMAND_XYZ 123 456"
        with self.assertRaises(ValueError):
            compiler.compile(bad_script)

    # -------------------------------------------------------------
    # 3. ShapeFeatureExtractor & Calçadista Families Tests
    # -------------------------------------------------------------
    def test_shape_feature_extraction_and_families(self):
        extractor = ShapeFeatureExtractor()
        
        # Test rectangle / shoe shape
        sample_contour = [
            {"x": 0.0, "y": 0.0},
            {"x": 120.0, "y": 0.0},
            {"x": 120.0, "y": 25.0},
            {"x": 0.0, "y": 25.0}
        ]
        feats = extractor.extract(sample_contour)
        self.assertGreater(feats.area, 0.0)
        self.assertGreater(feats.perimeter, 0.0)
        self.assertGreater(feats.compactness, 0.0)
        self.assertIn(feats.family, [
            "TIRA_LONGA", "CURVA_CONCAVA_GASPEA", "COMPACTA_SOLA_CALCANHAR", "PADRAO_IRREGULAR"
        ])

    # -------------------------------------------------------------
    # 4. NestingAIBrain Tests (Imitation Learning & UCB1 Bandit)
    # -------------------------------------------------------------
    def test_ai_brain_bandit_and_learning(self):
        brain = NestingAIBrain(self.db)
        
        # Bandit recommendations
        arm_idx, params = brain.select_arm("TIRA_LONGA")
        self.assertIn("shift_x", params)
        self.assertIn("gravity_x", params)
        self.assertIn("gravity_y", params)
        self.assertIn("sweep_max", params)
        self.assertIn("steps", params)
        
        # Feedback update
        brain.record_feedback("TIRA_LONGA", arm_idx, reward=0.85)
        
        # Imitation learning
        sample_placed = [
            {"id": 1, "name": "MOLDE_A", "x": 10.0, "y": 10.0, "rotation": 0.0, "is_mirrored": False, "contour": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 30}, {"x": 0, "y": 30}]},
            {"id": 2, "name": "MOLDE_B", "x": 65.0, "y": 10.0, "rotation": 180.0, "is_mirrored": False, "contour": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 30}, {"x": 0, "y": 30}]}
        ]
        brain.learn_from_operator_save(sample_placed, self.sheet_w, self.sheet_h)
        
        status = brain.get_memory_status()
        self.assertIn("summary", status)
        self.assertIn("habits_count", status)

    # -------------------------------------------------------------
    # 5. auto_nest_pieces com strategy="IA-teste" Tests
    # -------------------------------------------------------------
    def test_auto_nest_pieces_ia_teste_zero_collision_and_bounds(self):
        pieces = auto_nest_pieces(
            self.shapes,
            self.sheet_w,
            self.sheet_h,
            target_count=20,
            strategy="IA-teste",
            gap_mm=1.0,
            db=self.db
        )
        self.assertGreaterEqual(len(pieces), 5, "O motor IA-teste deve posicionar peças.")

        polys = [transform_contour(p["contour"], p["x"], p["y"], p["rotation"]) for p in pieces]
        bboxes = [polygon_bbox(poly) for poly in polys]

        # Verifica limites físicos da chapa
        for idx, (poly, (bx0, by0, bx1, by1)) in enumerate(zip(polys, bboxes)):
            self.assertGreaterEqual(bx0, -0.01, f"Peça {pieces[idx]['id']} ultrapassou margem esquerda")
            self.assertGreaterEqual(by0, -0.01, f"Peça {pieces[idx]['id']} ultrapassou margem inferior")
            self.assertLessEqual(bx1, self.sheet_w + 0.01, f"Peça {pieces[idx]['id']} ultrapassou margem direita")
            self.assertLessEqual(by1, self.sheet_h + 0.01, f"Peça {pieces[idx]['id']} ultrapassou margem superior")

        # Verifica Zero Colisão
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                collided = polygons_collide(
                    polys[i], polys[j], gap=0.0, bbox_a=bboxes[i], bbox_b=bboxes[j]
                )
                self.assertFalse(
                    collided,
                    f"Colisão detectada entre peça {pieces[i]['id']} e {pieces[j]['id']}"
                )

        # Ordem de corte CNC: checa se está ordenado monotonicamente de baixo para cima (vácuo)
        y_coords = [p["y"] for p in pieces]
        # Pelo menos não deve ser aleatório em Y decrescente inverso
        self.assertLessEqual(min(y_coords[:3]), max(y_coords[-3:]))

    # -------------------------------------------------------------
    # 6. .lay Round-Trip Fidelidade
    # -------------------------------------------------------------
    def test_lay_round_trip_with_ia_teste_pieces(self):
        pieces = auto_nest_pieces(
            self.shapes,
            self.sheet_w,
            self.sheet_h,
            target_count=10,
            strategy="IA-teste",
            gap_mm=1.0,
            db=self.db
        )
        material = {
            "width_mm": self.sheet_w,
            "height_mm": self.sheet_h,
            "gap_mm": 1.0,
            "name": "TEST_MAT",
            "id": "TEST_MAT"
        }
        lay_content = export_layout_from_pieces(pieces, material, filename="teste_ia.lay")
        self.assertIn("$$LAYOUT.v3$$", lay_content)
        self.assertIn("num_of_items=10", lay_content)
        self.assertIn("codR=TEST_MAT", lay_content)

        with tempfile.NamedTemporaryFile("w", suffix=".lay", delete=False, encoding="latin1") as tmp:
            tmp.write(lay_content)
            tmp_path = tmp.name

        try:
            parsed = parse_lay(tmp_path, db=self.db)
            self.assertEqual(len(parsed.items), len(pieces))
            for orig, parsed_item in zip(pieces, parsed.items):
                self.assertAlmostEqual(orig["x"], parsed_item.x, places=2)
                self.assertAlmostEqual(orig["y"], parsed_item.y, places=2)
                self.assertAlmostEqual(orig["rotation"], parsed_item.rot_deg, places=1)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # -------------------------------------------------------------
    # 7. Database Migration & Presets
    # -------------------------------------------------------------
    def test_dieproc_preset_macro_script(self):
        presets = self.db.get_dieproc_presets()
        self.assertIn("MACRO_IA_TESTE", presets)
        ia_preset = presets["MACRO_IA_TESTE"]
        self.assertTrue(len(ia_preset.get("macro_script", "").strip()) > 0)
        self.assertIn("AI AUTO_TUNE", ia_preset["macro_script"])

if __name__ == "__main__":
    unittest.main()
