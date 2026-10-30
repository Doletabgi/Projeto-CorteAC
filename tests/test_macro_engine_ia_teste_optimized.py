"""
JobManager 2000 (Python Edition)
tests/test_macro_engine_ia_teste_optimized.py

Suíte Oficial de Homologação da Fase 5.1 — Otimização do Motor IA-teste:
1. test_ia_teste_optimized_preserves_yield_mixed_300: Yield em mixed_300 >= 65.0% (mantendo ganho vs baseline 69.56%)
2. test_ia_teste_optimized_zero_collisions_mixed_300: 0 colisões em mixed_300 (auditado O(N²) com SAT e gap estrito)
3. test_ia_teste_optimized_time_under_100ms: mixed_300 executa em tempo mediano < 100 ms
4. test_ia_teste_optimized_small_shoes_under_500ms: small_shoes_50 < 500 ms com zero colisões
5. test_ia_teste_optimized_large_pieces_under_100ms: large_pieces_100 < 100 ms com zero colisões
6. test_ia_teste_deterministic_flag: com flag deterministic=True, 3 execuções geram saída 100% idêntica
7. test_nfp_loop_convergence_handles_concave: loop de convergência NFP lida com múltiplos obstáculos côncavos sem colisão
"""

import json
import math
import os
import time
import unittest
from pathlib import Path

from cad.geometry import (
    transform_contour,
    polygon_bbox,
    polygon_area,
    polygons_collide,
    bbox_overlap,
    find_contact_coordinate_binary,
)
from cad.macro_engine import (
    nest_ia_teste_engine,
    ramer_douglas_peucker,
    clear_macro_caches,
    OmniNestMacroEngine,
    _find_best_horizontal_slot_nfp,
)
from cad.nesting_engine import nest_multi_sheet
from cad.nfp import contact_placement_x
from tools.bench_nest import load_benchmark_shapes


BASELINE_PATH = Path(__file__).resolve().parent / "fixtures" / "ia_teste_baseline.json"


class TestMacroEngineIATesteOptimized(unittest.TestCase):
    def setUp(self):
        clear_macro_caches()

    def tearDown(self):
        clear_macro_caches()

    def test_01_ia_teste_optimized_preserves_yield_mixed_300(self):
        """
        1. test_ia_teste_optimized_preserves_yield_mixed_300:
        Yield em mixed_300 deve ser >= 65.0% (baseline: 69.56%).
        Garante que a otimização preservou o ganho de chapas (4 chapas).
        """
        shapes = load_benchmark_shapes(300)
        res = nest_multi_sheet(
            available_shapes=shapes,
            bed_width_mm=2000.0,
            bed_height_mm=1200.0,
            strategy="IA-teste",
            gap_mm=1.0,
            layers=2,
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
        )
        layouts = res.get("layouts", [])
        num_sheets = max(1, res.get("num_sheets", len(layouts)))
        useful_area_m2 = sum(
            polygon_area(p["shape"]["contour"] if ("shape" in p and "contour" in p["shape"]) else p.get("contour", []))
            for lay in layouts
            for p in lay.get("pieces", [])
        ) / 1_000_000.0
        total_bed_m2 = num_sheets * 2.4
        yield_pct = (useful_area_m2 / total_bed_m2 * 100.0) if total_bed_m2 > 0 else 0.0

        self.assertEqual(num_sheets, 4, f"Deve utilizar exatamente 4 chapas, utilizou: {num_sheets}")
        self.assertGreaterEqual(yield_pct, 65.0, f"Yield ({yield_pct:.2f}%) deve ser >= 65.00%")

        # Validação contra baseline gravado
        if BASELINE_PATH.exists():
            with open(BASELINE_PATH, "r", encoding="utf-8") as f:
                b_data = json.load(f)
            b_yield = b_data.get("engines", {}).get("IA-teste", {}).get("yield_pct", 69.56)
            diff_pp = abs(yield_pct - b_yield)
            self.assertLess(diff_pp, 4.56, f"Perda de yield ({diff_pp:.2f} p.p.) não pode exceder 4.56 p.p.")

    def test_02_ia_teste_optimized_zero_collisions_mixed_300(self):
        """
        2. test_ia_teste_optimized_zero_collisions_mixed_300:
        0 colisões em mixed_300 verificado via SAT O(N²) com gap milimétrico estrito.
        """
        shapes = load_benchmark_shapes(300)
        res = nest_multi_sheet(
            available_shapes=shapes,
            bed_width_mm=2000.0,
            bed_height_mm=1200.0,
            strategy="IA-teste",
            gap_mm=1.0,
            layers=2,
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
        )
        layouts = res.get("layouts", [])
        self.assertTrue(len(layouts) >= 4)

        audit_gap = 0.98
        total_collisions = 0
        for sheet_idx, lay in enumerate(layouts, start=1):
            pcs = lay.get("pieces", [])
            for i in range(len(pcs)):
                poly_i = transform_contour(pcs[i]["contour"], pcs[i]["x"], pcs[i]["y"], pcs[i]["rotation"])
                bbox_i = polygon_bbox(poly_i)
                for j in range(i + 1, len(pcs)):
                    poly_j = transform_contour(pcs[j]["contour"], pcs[j]["x"], pcs[j]["y"], pcs[j]["rotation"])
                    bbox_j = polygon_bbox(poly_j)
                    if bbox_overlap(bbox_i, bbox_j, audit_gap):
                        if polygons_collide(poly_i, poly_j, gap=audit_gap):
                            total_collisions += 1

        self.assertEqual(total_collisions, 0, f"Deve haver 0 colisões em mixed_300, encontradas: {total_collisions}")

    def test_03_ia_teste_optimized_time_under_100ms(self):
        """
        3. test_ia_teste_optimized_time_under_100ms:
        Tempo de execução em mixed_300 deve ser < 100.0 ms (mediana de 5 runs warm).
        """
        shapes = load_benchmark_shapes(300)

        # Warm-up run
        nest_multi_sheet(
            available_shapes=shapes,
            bed_width_mm=2000.0,
            bed_height_mm=1200.0,
            strategy="IA-teste",
            gap_mm=1.0,
            layers=2,
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
        )

        times_ms = []
        for _ in range(5):
            t0 = time.perf_counter()
            nest_multi_sheet(
                available_shapes=shapes,
                bed_width_mm=2000.0,
                bed_height_mm=1200.0,
                strategy="IA-teste",
                gap_mm=1.0,
                layers=2,
                margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            )
            times_ms.append((time.perf_counter() - t0) * 1000.0)

        median_time = sorted(times_ms)[len(times_ms) // 2]
        self.assertLess(
            median_time,
            100.0,
            f"Tempo mediano ({median_time:.2f} ms) deve ser < 100.0 ms! Runs: {[round(t, 2) for t in times_ms]}"
        )

    def test_04_ia_teste_optimized_small_shoes_under_500ms(self):
        """
        4. test_ia_teste_optimized_small_shoes_under_500ms:
        small_shoes_50 (peças densas de calçado) deve executar em < 500 ms com zero colisões.
        """
        shapes = load_benchmark_shapes(50)
        t0 = time.perf_counter()
        res = nest_multi_sheet(
            available_shapes=shapes,
            bed_width_mm=2000.0,
            bed_height_mm=1200.0,
            strategy="IA-teste",
            gap_mm=1.0,
            layers=2,
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertLess(elapsed_ms, 500.0, f"small_shoes_50 demorou {elapsed_ms:.2f} ms, esperado < 500 ms")

        # Zero colisões
        for lay in res.get("layouts", []):
            pcs = lay.get("pieces", [])
            for i in range(len(pcs)):
                poly_i = transform_contour(pcs[i]["contour"], pcs[i]["x"], pcs[i]["y"], pcs[i]["rotation"])
                bbox_i = polygon_bbox(poly_i)
                for j in range(i + 1, len(pcs)):
                    poly_j = transform_contour(pcs[j]["contour"], pcs[j]["x"], pcs[j]["y"], pcs[j]["rotation"])
                    bbox_j = polygon_bbox(poly_j)
                    if bbox_overlap(bbox_i, bbox_j, 0.98):
                        self.assertFalse(polygons_collide(poly_i, poly_j, gap=0.98), "Colisão em small_shoes_50")

    def test_05_ia_teste_optimized_large_pieces_under_100ms(self):
        """
        5. test_ia_teste_optimized_large_pieces_under_100ms:
        large_pieces_100 deve executar em < 100 ms com zero colisões.
        """
        shapes = load_benchmark_shapes(100)
        t0 = time.perf_counter()
        res = nest_multi_sheet(
            available_shapes=shapes,
            bed_width_mm=2000.0,
            bed_height_mm=1200.0,
            strategy="IA-teste",
            gap_mm=1.0,
            layers=2,
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertLess(elapsed_ms, 100.0, f"large_pieces_100 demorou {elapsed_ms:.2f} ms, esperado < 100 ms")

        # Zero colisões
        for lay in res.get("layouts", []):
            pcs = lay.get("pieces", [])
            for i in range(len(pcs)):
                poly_i = transform_contour(pcs[i]["contour"], pcs[i]["x"], pcs[i]["y"], pcs[i]["rotation"])
                bbox_i = polygon_bbox(poly_i)
                for j in range(i + 1, len(pcs)):
                    poly_j = transform_contour(pcs[j]["contour"], pcs[j]["x"], pcs[j]["y"], pcs[j]["rotation"])
                    bbox_j = polygon_bbox(poly_j)
                    if bbox_overlap(bbox_i, bbox_j, 0.98):
                        self.assertFalse(polygons_collide(poly_i, poly_j, gap=0.98), "Colisão em large_pieces_100")

    def test_06_ia_teste_deterministic_flag(self):
        """
        6. test_ia_teste_deterministic_flag:
        Com flag deterministic=True, 3 execuções consecutivas produzem layouts 100% idênticos.
        """
        shapes = load_benchmark_shapes(300)
        res1 = nest_ia_teste_engine(shapes, 2000.0, 1200.0, gap_mm=1.0, layers=2, deterministic=True)
        res2 = nest_ia_teste_engine(shapes, 2000.0, 1200.0, gap_mm=1.0, layers=2, deterministic=True)
        res3 = nest_ia_teste_engine(shapes, 2000.0, 1200.0, gap_mm=1.0, layers=2, deterministic=True)

        self.assertEqual(len(res1), len(res2))
        self.assertEqual(len(res2), len(res3))
        for p1, p2, p3 in zip(res1, res2, res3):
            self.assertEqual(p1["id"], p2["id"])
            self.assertEqual(p1["x"], p2["x"])
            self.assertEqual(p1["y"], p2["y"])
            self.assertEqual(p1["rotation"], p2["rotation"])
            self.assertEqual(p2["x"], p3["x"])
            self.assertEqual(p2["y"], p3["y"])
            self.assertEqual(p2["rotation"], p3["rotation"])

    def test_07_nfp_loop_convergence_handles_concave(self):
        """
        7. test_nfp_loop_convergence_handles_concave:
        Valida que o loop de convergência NFP trata múltiplos obstáculos côncavos
        garantindo zero colisão e sem travamento (deadlock).
        """
        # Obstáculo côncavo em U
        u_shape = [
            {"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 0.0}, {"x": 100.0, "y": 60.0},
            {"x": 80.0, "y": 60.0}, {"x": 80.0, "y": 20.0}, {"x": 20.0, "y": 20.0},
            {"x": 20.0, "y": 60.0}, {"x": 0.0, "y": 60.0}
        ]
        u_obs1 = [{"x": p["x"] + 10.0, "y": p["y"] + 10.0} for p in u_shape]
        u_obs2 = [{"x": p["x"] + 120.0, "y": p["y"] + 10.0} for p in u_shape]
        moving_piece = [
            {"x": 0.0, "y": 10.0}, {"x": 30.0, "y": 10.0},
            {"x": 30.0, "y": 40.0}, {"x": 0.0, "y": 40.0}
        ]

        cand_x = _find_best_horizontal_slot_nfp(moving_piece, [u_obs1, u_obs2], gap=1.0)
        self.assertTrue(math.isfinite(cand_x))
        self.assertGreater(cand_x, 0.0)

        placed_m = [{"x": p["x"] + cand_x, "y": p["y"]} for p in moving_piece]
        cand_bbox = polygon_bbox(placed_m)
        for obs in [u_obs1, u_obs2]:
            o_bbox = polygon_bbox(obs)
            self.assertFalse(
                polygons_collide(placed_m, obs, gap=0.98, bbox_a=cand_bbox, bbox_b=o_bbox),
                "Colisão detectada em obstáculo côncavo após loop de convergência"
            )


if __name__ == "__main__":
    unittest.main()
