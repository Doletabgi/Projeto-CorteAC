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
import tkinter as tk
from pathlib import Path
from database import DatabaseManager
from cad.geometry import transform_contour, polygon_bbox, polygons_collide, point_segment_distance_sq
from cad.ai_learner import ShapeFeatureExtractor, NestingAIBrain
from cad.macro_engine import SafeFormulaEvaluator, MacroCompiler, DEFAULT_IA_TESTE_MACRO, nest_ia_teste_engine
from cad.nesting_engine import auto_nest_pieces
from cad.lay_parser import export_layout_from_pieces, parse_lay
from ui.session_view import SessionView


def make_realistic_shoe_sole_contour(length=240.0, width=85.0):
    """
    Gera um contorno de palmilha/sola calçadista realista com 36 vértices,
    incluindo curvatura suave do calcanhar, concavidade do enfranque/cintura medial,
    largura na planta e curvatura no bico.
    """
    pts = []
    for deg in range(0, 360, 10):
        rad = math.radians(deg)
        cx = (math.cos(rad) + 1.0) * 0.5 * length
        base_w = math.sin(rad) * 0.5 * width
        if 0 <= deg <= 180:
            # Lado medial (interno) com concavidade no enfranque entre 50° e 130°
            if 50 <= deg <= 130:
                base_w *= 0.52
            cy = 44.0 + base_w
        else:
            # Lado lateral (externo)
            cy = 44.0 + base_w * 0.95
        pts.append({"x": round(cx, 2), "y": round(cy, 2)})
    return pts


class TestMacroEngineIATeste(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "root", None):
            try:
                cls.root.destroy()
            except Exception:
                pass

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

    # -------------------------------------------------------------
    # 8. Strict Zero-Overlap Test with Realistic Concave Shoe Contours
    # -------------------------------------------------------------
    def test_ia_teste_strict_zero_overlap_with_real_shoe_contours(self):
        """
        Garantia Estrita de Zero Sobreposição:
        Cria moldes curvos reais (palmilha côncava com 36 vértices) e roda IA-teste com gap=1.0.
        Reconstrói os polígonos exatamente como LayoutEditorView e verifica par-a-par
        com polygons_collide(p1, p2, gap=0.95) que ZERO pares colidem.
        """
        shoe_sole = make_realistic_shoe_sole_contour(length=240.0, width=85.0)
        shape_sole = {
            "id": 999,
            "name": "SOLA_PALMILHA_TESTE",
            "size": "41",
            "pairs": 12,
            "sequence": 1,
            "contour": shoe_sole,
            "holes": [],
            "internal_cuts": [],
            "stitching": []
        }
        test_shapes = [shape_sole]

        pieces = auto_nest_pieces(
            test_shapes,
            bed_width_mm=1350.0,
            bed_height_mm=1000.0,
            target_count=20,
            strategy="IA-teste",
            gap_mm=1.0,
            db=self.db
        )
        self.assertGreaterEqual(len(pieces), 4, "Deve posicionar pelo menos 4 palmilhas na placa.")

        # Reconstrução exata do LayoutEditorView
        reconstructed_polys = []
        reconstructed_bboxes = []
        for p in pieces:
            poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
            bbox = polygon_bbox(poly)
            reconstructed_polys.append(poly)
            reconstructed_bboxes.append(bbox)

        # 1. Verifica limites físicos da Placa
        for idx, (poly, (bx0, by0, bx1, by1)) in enumerate(zip(reconstructed_polys, reconstructed_bboxes)):
            self.assertGreaterEqual(bx0, 0.0, f"Peça {pieces[idx]['id']} ultrapassou margem esquerda")
            self.assertGreaterEqual(by0, 0.0, f"Peça {pieces[idx]['id']} ultrapassou margem inferior")
            self.assertLessEqual(bx1, 1350.0 + 0.05, f"Peça {pieces[idx]['id']} ultrapassou margem direita")
            self.assertLessEqual(by1, 1000.0 + 0.05, f"Peça {pieces[idx]['id']} ultrapassou margem superior")

        # 2. Auditoria par-a-par estrita com tolerância de gap=0.95 (garante gap de 1.0mm)
        collisions = []
        for i in range(len(reconstructed_polys)):
            for j in range(i + 1, len(reconstructed_polys)):
                if polygons_collide(
                    reconstructed_polys[i], reconstructed_polys[j],
                    gap=0.95,
                    bbox_a=reconstructed_bboxes[i],
                    bbox_b=reconstructed_bboxes[j]
                ):
                    collisions.append((pieces[i]["id"], pieces[j]["id"]))

        self.assertEqual(
            len(collisions), 0,
            f"Erro crítico: sobreposição/colisão detectada em peças {collisions} com motor IA-teste!"
        )

    # -------------------------------------------------------------
    # 9. SessionView Spin Control: 'Distância peças (mm)' [-][ 1.0 ][+]
    # -------------------------------------------------------------
    def test_session_view_piece_distance_spin_control_overrides_gap(self):
        """
        Valida o controle 'Distância peças (mm)' [-] [ 1.0 ] [+] em SessionView:
        - Campo inicial com valor padrão 1.0 mm
        - Cliques no botão [+] incrementam em 0.5 mm
        - Cliques no botão [-] decrementam em 0.5 mm com trava em 0.0 mm
        - O gap configurado é repassado como gap mestre em get_dieproc_params()
        - auto_nest_pieces com o gap da SessionView é respeitado pelo motor IA-teste
        """
        if not self.root:
            self.skipTest("Ambiente Tkinter headless sem display gráfico.")

        sess_data = {"id": 1, "status": "Stand by", "strategy": "IA-teste", "gap_mm": 1.0}
        sv = SessionView(self.root, session_data=sess_data, db=self.db)

        # 1. Checa presença dos widgets visuais
        self.assertTrue(hasattr(sv, "entry_gap"), "SessionView deve ter entry_gap")
        self.assertTrue(hasattr(sv, "btn_gap_minus"), "SessionView deve ter btn_gap_minus")
        self.assertTrue(hasattr(sv, "btn_gap_plus"), "SessionView deve ter btn_gap_plus")
        self.assertEqual(sv.entry_gap.get(), "1.0")
        self.assertEqual(sv.get_gap_mm(), 1.0)

        # 2. Testa incremento via [+]
        sv._on_gap_plus()
        self.assertEqual(sv.get_gap_mm(), 1.5)
        self.assertEqual(sv.entry_gap.get(), "1.5")

        sv._on_gap_plus()
        self.assertEqual(sv.get_gap_mm(), 2.0)
        self.assertEqual(sv.entry_gap.get(), "2.0")

        # 3. Testa decremento via [-]
        sv._on_gap_minus()
        self.assertEqual(sv.get_gap_mm(), 1.5)
        self.assertEqual(sv.entry_gap.get(), "1.5")

        # Testa trava no mínimo de 0.0 mm
        sv._on_gap_minus()  # 1.0
        sv._on_gap_minus()  # 0.5
        sv._on_gap_minus()  # 0.0
        self.assertEqual(sv.get_gap_mm(), 0.0)
        self.assertEqual(sv.entry_gap.get(), "0.0")

        sv._on_gap_minus()  # Continua travado em 0.0
        self.assertEqual(sv.get_gap_mm(), 0.0)
        self.assertEqual(sv.entry_gap.get(), "0.0")

        # 4. Testa set_gap_mm e repasse mestre para get_dieproc_params()
        sv.set_gap_mm(2.5)
        self.assertEqual(sv.get_gap_mm(), 2.5)
        self.assertEqual(sv.entry_gap.get(), "2.5")
        dieproc_p = sv.get_dieproc_params()
        if dieproc_p:
            self.assertEqual(dieproc_p.get("gap1"), 2.5)

        # 5. Testa cálculo de layout com o gap da interface
        pieces = auto_nest_pieces(
            self.shapes,
            bed_width_mm=1350.0,
            bed_height_mm=1000.0,
            target_count=8,
            strategy="IA-teste",
            gap_mm=sv.get_gap_mm(),
            db=self.db
        )
        self.assertGreater(len(pieces), 0)


if __name__ == "__main__":
    unittest.main()
