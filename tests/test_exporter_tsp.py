"""
tests/test_exporter_tsp.py

Suíte de testes de validação matemática, estabilidade e fuzzing para
a otimização Strip-TSP + 2-Opt em cad/exporter.py.
"""

import math
import random
import unittest
from cad.exporter import (
    optimize_piece_cutting_order_tsp,
    reorder_contour_midpoint_longest_edge,
)
from cad.geometry import transform_contour, rotate_point


def calculate_tour_distance(placed_pieces: list[dict]) -> float:
    """Calcula a distância euclidiana total de G00 partindo de (0, 0)."""
    if not placed_pieces:
        return 0.0
    total_dist = 0.0
    curr_x, curr_y = 0.0, 0.0
    for p in placed_pieces:
        poly = transform_contour(p["shape"]["contour"], p["x"], p["y"], p["rotation"])
        holes = p["shape"].get("holes", [])
        if holes:
            rx, ry = rotate_point(holes[0]["x"], holes[0]["y"], p["rotation"])
            entry_x, entry_y = p["x"] + rx, p["y"] + ry
        else:
            reordered = reorder_contour_midpoint_longest_edge(poly)
            entry_x, entry_y = reordered[0]["x"], reordered[0]["y"]
        total_dist += math.hypot(entry_x - curr_x, entry_y - curr_y)
        curr_x, curr_y = entry_x, entry_y
    return total_dist


class TestExporterTSP(unittest.TestCase):
    def setUp(self):
        self.box_contour = [
            {"x": 0.0, "y": 0.0},
            {"x": 100.0, "y": 0.0},
            {"x": 100.0, "y": 50.0},
            {"x": 0.0, "y": 50.0},
        ]

    def _make_pieces(self, coords: list[tuple[float, float]]) -> list[dict]:
        return [
            {
                "id": i + 1,
                "x": float(x),
                "y": float(y),
                "rotation": 0,
                "shape": {"name": f"P{i+1}", "contour": self.box_contour, "holes": []},
            }
            for i, (x, y) in enumerate(coords)
        ]

    def test_01_empty_and_trivial_piece_lists(self):
        """Listas com 0, 1 ou 2 peças não devem sofrer alteração ou erro."""
        self.assertEqual(optimize_piece_cutting_order_tsp([]), [])

        p1 = self._make_pieces([(100.0, 100.0)])
        res1 = optimize_piece_cutting_order_tsp(p1)
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0]["id"], 1)

        p2 = self._make_pieces([(100.0, 100.0), (300.0, 300.0)])
        res2 = optimize_piece_cutting_order_tsp(p2)
        self.assertEqual(len(res2), 2)
        self.assertEqual([p["id"] for p in res2], [1, 2])

    def test_02_preserves_all_pieces_and_integrity(self):
        """Garante que para N=50, 100, 200 nenhuma peça é perdida ou duplicada."""
        for n in [10, 50, 100, 200]:
            rng = random.Random(n)
            coords = [(rng.uniform(10, 1900), rng.uniform(10, 1100)) for _ in range(n)]
            pieces = self._make_pieces(coords)
            optimized = optimize_piece_cutting_order_tsp(pieces)

            self.assertEqual(len(optimized), n, f"Tamanho incorreto para N={n}")
            input_ids = {p["id"] for p in pieces}
            output_ids = {p["id"] for p in optimized}
            self.assertEqual(input_ids, output_ids, f"Conjunto de IDs divergente para N={n}")

    def test_03_straight_line_route_not_degraded(self):
        """Uma rota perfeitamente linear e ordenada não deve ser degradada."""
        coords = [(100.0 + i * 80.0, 200.0) for i in range(15)]
        pieces = self._make_pieces(coords)
        dist_before = calculate_tour_distance(pieces)

        optimized = optimize_piece_cutting_order_tsp(pieces)
        dist_after = calculate_tour_distance(optimized)

        self.assertLessEqual(dist_after, dist_before + 1e-4)
        # Deve manter a sequência natural crescente
        self.assertEqual([p["id"] for p in optimized], list(range(1, 16)))

    def test_04_reversed_route_is_improved(self):
        """Uma rota propositalmente invertida (pior caso) deve ser otimizada."""
        # Peças alinhadas mas ordenadas da mais distante para a mais próxima de (0, 0)
        coords = [(100.0 + (14 - i) * 80.0, 200.0) for i in range(15)]
        pieces = self._make_pieces(coords)
        dist_before = calculate_tour_distance(pieces)

        optimized = optimize_piece_cutting_order_tsp(pieces)
        dist_after = calculate_tour_distance(optimized)

        self.assertLess(dist_after, dist_before)
        # Otimizador deve reorganizar a partir de (0, 0)
        self.assertEqual([p["id"] for p in optimized], list(reversed(range(1, 16))))

    def test_05_deterministic_output(self):
        """Execuções consecutivas sobre os mesmos dados produzem ordem idêntica."""
        rng = random.Random(999)
        coords = [(rng.uniform(0, 2000), rng.uniform(0, 1200)) for _ in range(50)]
        pieces = self._make_pieces(coords)

        res_a = optimize_piece_cutting_order_tsp(pieces)
        res_b = optimize_piece_cutting_order_tsp(pieces)

        self.assertEqual([p["id"] for p in res_a], [p["id"] for p in res_b])

    def test_06_fuzz_10000_routes(self):
        """
        Fuzz test com 10.000 rotas aleatórias (N=10 a 50):
        - 100% das rotas mantêm integridade de IDs (zero perda/duplicação).
        - 100% das rotas resultam em distância menor ou igual à rota não otimizada.
        """
        rng = random.Random(42)
        total_fuzz = 10000

        for idx in range(total_fuzz):
            n = 10 + (idx % 41)  # Varia N entre 10 e 50
            coords = [
                (round(rng.uniform(10.0, 1900.0), 1), round(rng.uniform(10.0, 1100.0), 1))
                for _ in range(n)
            ]
            pieces = self._make_pieces(coords)
            raw_dist = calculate_tour_distance(pieces)

            optimized = optimize_piece_cutting_order_tsp(pieces)

            self.assertEqual(len(optimized), n)
            self.assertEqual(len({p["id"] for p in optimized}), n)

            opt_dist = calculate_tour_distance(optimized)
            self.assertLessEqual(
                opt_dist,
                raw_dist + 1e-4,
                f"Degradação encontrada no caso fuzz {idx}: opt={opt_dist:.2f} > raw={raw_dist:.2f}"
            )

    def test_07_or_opt_reduces_distance_or_equal(self):
        """Or-opt deve reduzir ou igualar a distância em relação à rota inicial (nunca piorar)."""
        rng = random.Random(77)
        for n in [20, 50, 100]:
            coords = [(rng.uniform(10, 1900), rng.uniform(10, 1100)) for _ in range(n)]
            pieces = self._make_pieces(coords)
            res_2opt = optimize_piece_cutting_order_tsp(pieces, algorithm="2opt")
            res_pipe = optimize_piece_cutting_order_tsp(pieces, algorithm="2opt+oropt")

            d_2opt = calculate_tour_distance(res_2opt)
            d_pipe = calculate_tour_distance(res_pipe)
            self.assertLessEqual(
                d_pipe,
                d_2opt + 1e-4,
                f"Pipeline piorou a rota para N={n}: pipe={d_pipe:.2f} > 2opt={d_2opt:.2f}"
            )

    def test_08_or_opt_preserves_all_pieces(self):
        """Nenhuma peça deve ser perdida ou duplicada com Or-opt em qualquer tamanho."""
        for n in [15, 60, 120]:
            rng = random.Random(100 + n)
            coords = [(rng.uniform(10, 1900), rng.uniform(10, 1100)) for _ in range(n)]
            pieces = self._make_pieces(coords)
            res = optimize_piece_cutting_order_tsp(pieces, algorithm="2opt+oropt")

            self.assertEqual(len(res), n)
            self.assertEqual({p["id"] for p in res}, {p["id"] for p in pieces})

    def test_09_or_opt_preserves_linear_route(self):
        """Rota em linha reta não deve sofrer degradação com Or-opt."""
        coords = [(100.0 + i * 50.0, 300.0) for i in range(25)]
        pieces = self._make_pieces(coords)
        dist_before = calculate_tour_distance(pieces)

        res = optimize_piece_cutting_order_tsp(pieces, algorithm="2opt+oropt")
        dist_after = calculate_tour_distance(res)

        self.assertLessEqual(dist_after, dist_before + 1e-4)
        self.assertEqual([p["id"] for p in res], list(range(1, 26)))

    def test_10_or_opt_deterministic(self):
        """10 execuções idênticas com Or-opt devem gerar exatamente a mesma sequência."""
        rng = random.Random(555)
        coords = [(rng.uniform(0, 2000), rng.uniform(0, 1200)) for _ in range(40)]
        pieces = self._make_pieces(coords)

        first_run = optimize_piece_cutting_order_tsp(pieces, algorithm="2opt+oropt")
        first_ids = [p["id"] for p in first_run]

        for _ in range(9):
            subsequent = optimize_piece_cutting_order_tsp(pieces, algorithm="2opt+oropt")
            self.assertEqual([p["id"] for p in subsequent], first_ids)

    def test_11_pipeline_2opt_or_opt_beats_2opt_only(self):
        """Pipeline 2-Opt + Or-opt deve ser estritamente superior ou igual ao 2-Opt puro."""
        from tools.bench_tsp import generate_tsp_pieces
        pieces = generate_tsp_pieces(200, seed=42)
        res_2opt = optimize_piece_cutting_order_tsp(pieces, algorithm="2opt")
        res_pipe = optimize_piece_cutting_order_tsp(pieces, algorithm="2opt+oropt")

        d_2opt = calculate_tour_distance(res_2opt)
        d_pipe = calculate_tour_distance(res_pipe)

        self.assertLess(d_pipe, d_2opt, f"Pipeline deveria superar 2-Opt puro: {d_pipe:.2f} vs {d_2opt:.2f}")
        # Ganho esperado no caso canônico de seed=42 é de pelo menos 5%
        gain_pct = (d_2opt - d_pipe) / d_2opt * 100.0
        self.assertGreater(gain_pct, 5.0, f"Ganho de G00 foi de apenas {gain_pct:.2f}% (esperado > 5%)")


if __name__ == "__main__":
    unittest.main()

