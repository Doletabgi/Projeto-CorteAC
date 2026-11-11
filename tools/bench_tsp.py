#!/usr/bin/env python3
"""
tools/bench_tsp.py

Benchmark de Otimização de Sequência de Corte CNC (TSP / 2-Opt) do CorteAC.
Mede o tempo de execução e a distância total de deslocamento rápido em vazio (G00)
para diferentes quantidades de peças (N = 50, 100, 200, 500, 1000).

Uso:
    python3 tools/bench_tsp.py --points 200 --runs 3
    python3 tools/bench_tsp.py --sizes 50 100 200 500 --json
    python3 tools/bench_tsp.py --sizes 50 100 200 500 1000 --save-baseline tsp_baseline.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from cad.exporter import optimize_piece_cutting_order_tsp, reorder_contour_midpoint_longest_edge  # noqa: E402
from cad.geometry import transform_contour, rotate_point  # noqa: E402


def generate_tsp_pieces(count: int, seed: int = 42) -> list[dict]:
    """
    Gera uma lista determinística e reproduzível de peças para teste de TSP.
    """
    rng = random.Random(seed)
    box_contour = [
        {"x": 0.0, "y": 0.0},
        {"x": 100.0, "y": 0.0},
        {"x": 100.0, "y": 50.0},
        {"x": 0.0, "y": 50.0},
    ]

    pieces = []
    for i in range(count):
        pieces.append({
            "id": i + 1,
            "x": round(rng.uniform(10.0, 1900.0), 2),
            "y": round(rng.uniform(10.0, 1100.0), 2),
            "rotation": rng.choice([0, 90, 180, 270]),
            "shape": {
                "name": f"Piece_{i+1}",
                "contour": box_contour,
                "holes": [],
            },
        })
    return pieces


def calculate_tour_distance(placed_pieces: list[dict]) -> float:
    """
    Calcula a distância euclidiana total de G00 percorrida pelo cabeçote CNC
    partindo da origem (0, 0) através dos pontos de entrada de cada peça.
    """
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


def run_tsp_benchmark(
    sizes: list[int],
    runs_per_size: dict[int, int] | None = None,
    default_runs: int = 3,
    algorithm: str = "2opt",
) -> dict[str, Any]:
    if runs_per_size is None:
        runs_per_size = {}

    results: dict[str, Any] = {}
    bench_start = time.perf_counter()

    for n in sizes:
        runs = runs_per_size.get(n, default_runs)
        run_times_ms: list[float] = []
        final_dist = 0.0

        for r in range(runs):
            pieces = generate_tsp_pieces(n, seed=42 + r)
            t0 = time.perf_counter()
            try:
                ordered = optimize_piece_cutting_order_tsp(pieces, algorithm=algorithm)
            except TypeError:
                ordered = optimize_piece_cutting_order_tsp(pieces)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            run_times_ms.append(elapsed_ms)
            if r == 0:
                final_dist = calculate_tour_distance(ordered)

        run_times_ms.sort()
        median_ms = run_times_ms[len(run_times_ms) // 2]
        avg_ms = sum(run_times_ms) / len(run_times_ms)

        results[f"n{n}"] = {
            "n": n,
            "runs": runs,
            "runs_ms": [round(t, 2) for t in run_times_ms],
            "min_ms": round(run_times_ms[0], 2),
            "max_ms": round(run_times_ms[-1], 2),
            "avg_ms": round(avg_ms, 2),
            "median_ms": round(median_ms, 2),
            "tour_distance_mm": round(final_dist, 2),
        }

    results["total_bench_ms"] = round((time.perf_counter() - bench_start) * 1000.0, 2)
    results["algorithm"] = algorithm
    if len(sizes) == 1:
        s0 = sizes[0]
        results["median_ms"] = results[f"n{s0}"]["median_ms"]
        results["g00_mm"] = results[f"n{s0}"]["tour_distance_mm"]

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark de TSP do CorteAC")
    parser.add_argument("--algorithm", type=str, default="2opt", choices=["2opt", "2opt+oropt", "2opt+oropt+iter200"], help="Algoritmo de TSP a avaliar")
    parser.add_argument("--points", type=int, default=None, help="Executar apenas para N pontos")
    parser.add_argument("--sizes", nargs="+", type=int, default=[50, 100, 200, 500], help="Lista de tamanhos N")
    parser.add_argument("--runs", type=int, default=3, help="Número padrão de rodadas")
    parser.add_argument("--save-baseline", type=str, default=None, help="Salvar baseline no arquivo informado")
    parser.add_argument("--output", type=str, default=None, help="Salvar resultado JSON no arquivo informado")
    parser.add_argument("--json", action="store_true", help="Imprimir saída em formato JSON")
    args = parser.parse_args()

    sizes = [args.points] if args.points is not None else args.sizes

    # Para N grandes (ex: 500 e 1000) no baseline antigo, 1 rodada para evitar espera desnecessária
    runs_map = {50: args.runs, 100: args.runs, 200: args.runs, 500: 1, 1000: 1}

    results = run_tsp_benchmark(sizes, runs_per_size=runs_map, default_runs=args.runs, algorithm=args.algorithm)


    if args.save_baseline:
        with open(args.save_baseline, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"[OK] Baseline salvo em: {args.save_baseline}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"[OK] Resultado salvo em: {args.output}")

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=" * 70)
        print("BENCHMARK TSP — CORTEAC (Strip-TSP + 2-Opt)")
        print("=" * 70)
        print(f"{'N Pontos':<10} | {'Rodadas':<8} | {'Mediana (ms)':<14} | {'Média (ms)':<12} | {'Distância (mm)':<16}")
        print("-" * 70)
        for key, data in results.items():
            if key == "total_bench_ms":
                continue
            print(f"{data['n']:<10} | {data['runs']:<8} | {data['median_ms']:<14.2f} | {data['avg_ms']:<12.2f} | {data['tour_distance_mm']:<16.2f}")
        print("=" * 70)
        print(f"Tempo total do benchmark: {results['total_bench_ms']:.2f} ms")

    return 0


if __name__ == "__main__":
    sys.exit(main())
