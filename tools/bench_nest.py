#!/usr/bin/env python3
"""
tools/bench_nest.py

Benchmark automatizado dos motores de Nesting do CorteAC (JobManager Python Edition).
Executa nest_multi_sheet para os motores ('sint', 'tape_a', 'flashnestsheet', 'IA-teste')
sobre contornos reais de calçados carregados de samples/.

Uso:
    python3 tools/bench_nest.py --pieces 300 --runs 3
    python3 tools/bench_nest.py --pieces 300 --runs 3 --json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from cad.die_parser import parse_die_file  # noqa: E402
from cad.nesting_engine import nest_multi_sheet  # noqa: E402


def load_benchmark_shapes(total_pieces: int) -> list[dict]:
    """
    Carrega contornos reais de samples/ e distribui a demanda de peças
    entre os modelos disponíveis de forma balanceada.
    """
    sample_files = [
        BASE_DIR / "samples" / "Gaspea_Derby_41.die",
        BASE_DIR / "samples" / "Biqueira_Esportiva_40.die",
        BASE_DIR / "samples" / "Lateral_Sapato_42.die",
    ]

    loaded_samples = []
    for p in sample_files:
        if p.exists():
            data = parse_die_file(str(p))
            loaded_samples.append(data)

    if not loaded_samples:
        # Fallback sintético caso samples/ não esteja acessível
        synthetic_contour = [
            {"x": 0.0, "y": 0.0},
            {"x": 120.0, "y": 0.0},
            {"x": 140.0, "y": 35.0},
            {"x": 110.0, "y": 70.0},
            {"x": 0.0, "y": 60.0},
        ]
        loaded_samples.append({
            "name": "Synthetic_Piece",
            "size": "41",
            "contour": synthetic_contour,
        })

    num_samples = len(loaded_samples)
    base_qty = total_pieces // num_samples
    remainder = total_pieces % num_samples

    shapes = []
    for idx, sample in enumerate(loaded_samples):
        qty = base_qty + (1 if idx < remainder else 0)
        if qty <= 0:
            continue
        shapes.append({
            "id": idx + 1,
            "name": sample.get("name", f"Shape_{idx+1}"),
            "size": str(sample.get("size", "41")),
            "pairs": qty,  # Com layers=2, pairs = pieces
            "sequence": idx + 1,
            "contour": sample["contour"],
            "layers": 2,
        })

    return shapes


def run_benchmark(
    pieces: int = 300,
    runs: int = 3,
    engines: list[str] | None = None,
    bed_w: float = 2000.0,
    bed_h: float = 1200.0,
    gap_mm: float = 1.0,
) -> dict[str, Any]:
    if engines is None:
        engines = ["sint", "tape_a", "flashnestsheet", "IA-teste"]

    results: dict[str, Any] = {
        "pieces": pieces,
        "runs": runs,
        "bed_width_mm": bed_w,
        "bed_height_mm": bed_h,
        "gap_mm": gap_mm,
        "engines": {},
    }

    total_bench_start = time.perf_counter()

    for engine in engines:
        run_times_ms: list[float] = []
        sheets_counts: list[int] = []
        placed_counts: list[int] = []

        for _ in range(runs):
            shapes = load_benchmark_shapes(pieces)
            t0 = time.perf_counter()
            res = nest_multi_sheet(
                available_shapes=shapes,
                bed_width_mm=bed_w,
                bed_height_mm=bed_h,
                strategy=engine,
                gap_mm=gap_mm,
                layers=2,
                margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            run_times_ms.append(elapsed_ms)
            sheets_counts.append(res.get("num_sheets", 0))
            placed_counts.append(res.get("total_pieces", 0))

        run_times_ms.sort()
        p95_idx = min(len(run_times_ms) - 1, math.ceil(len(run_times_ms) * 0.95) - 1)
        p95_ms = run_times_ms[p95_idx]
        median_ms = run_times_ms[len(run_times_ms) // 2]
        avg_ms = sum(run_times_ms) / len(run_times_ms)

        results["engines"][engine] = {
            "runs_ms": [round(t, 2) for t in run_times_ms],
            "min_ms": round(run_times_ms[0], 2),
            "max_ms": round(run_times_ms[-1], 2),
            "avg_ms": round(avg_ms, 2),
            "median_ms": round(median_ms, 2),
            "p95_ms": round(p95_ms, 2),
            "sheets": sheets_counts[-1],
            "placed": placed_counts[-1],
        }

    results["total_elapsed_ms"] = round((time.perf_counter() - total_bench_start) * 1000.0, 2)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark de Nesting do CorteAC")
    parser.add_argument("--pieces", type=int, default=300, help="Quantidade total de peças a nestar (default: 300)")
    parser.add_argument("--runs", type=int, default=3, help="Número de execuções para estatística (default: 3)")
    parser.add_argument("--engines", nargs="+", default=["sint", "tape_a", "flashnestsheet", "IA-teste"], help="Motores a testar")
    parser.add_argument("--bed-w", type=float, default=2000.0, help="Largura da chapa em mm (default: 2000.0)")
    parser.add_argument("--bed-h", type=float, default=1200.0, help="Altura da chapa em mm (default: 1200.0)")
    parser.add_argument("--gap", type=float, default=1.0, help="Distância entre peças (gap) em mm (default: 1.0)")
    parser.add_argument("--backend", choices=["python", "nfp"], default="python", help="Backend de nesting a utilizar (default: python)")
    parser.add_argument("--json", action="store_true", help="Saída estrita em formato JSON")
    args = parser.parse_args()

    import os
    os.environ["CORTEAC_BACKEND"] = args.backend

    results = run_benchmark(
        pieces=args.pieces,
        runs=args.runs,
        engines=args.engines,
        bed_w=args.bed_w,
        bed_h=args.bed_h,
        gap_mm=args.gap,
    )
    results["backend"] = args.backend

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=" * 70)
        print(f"BENCHMARK DE NESTING — CORTEAC ({results['pieces']} peças, {results['runs']} rodadas)")
        print(f"Chapa: {results['bed_width_mm']}x{results['bed_height_mm']} mm | Gap: {results['gap_mm']} mm")
        print("=" * 70)
        print(f"{'Motor':<18} | {'Peças':<6} | {'Chapas':<6} | {'Média (ms)':<10} | {'Mediana (ms)':<12} | {'p95 (ms)':<10}")
        print("-" * 70)
        for engine, data in results["engines"].items():
            print(f"{engine:<18} | {data['placed']:<6} | {data['sheets']:<6} | {data['avg_ms']:<10.2f} | {data['median_ms']:<12.2f} | {data['p95_ms']:<10.2f}")
        print("=" * 70)
        print(f"Tempo total de benchmark: {results['total_elapsed_ms']:.2f} ms")

    return 0


if __name__ == "__main__":
    sys.exit(main())
