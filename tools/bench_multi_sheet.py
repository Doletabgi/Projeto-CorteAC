#!/usr/bin/env python3
"""
tools/bench_multi_sheet.py

Benchmark automatizado para validação de performance em Nesting de Múltiplas Chapas (Fase 6.6).
Mede o tempo total para aninhamento de 1600 peças (100 pares x 16 tamanhos graduados)
utilizando a estratégia flashnestsheet no motor acelerado NfpBackend (FastNest).

Meta de Aceite:
- Tempo total < 10.0 s (ideal < 3.0 s)
- 1600 peças encaixadas
- Verificação do callback de progresso determinado
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from cad.die_parser import parse_die_file  # noqa: E402
from cad.nesting_engine import nest_multi_sheet  # noqa: E402


def generate_benchmark_shapes(total_pieces: int = 1600, num_sizes: int = 16) -> list[dict]:
    """
    Gera conjunto de moldes com num_sizes tamanhos graduados,
    totalizando exatamente total_pieces com camadas=2.
    """
    die_path = BASE_DIR / "samples" / "Gaspea_Derby_41.die"
    if die_path.exists():
        sample = parse_die_file(str(die_path))
        base_contour = sample["contour"]
    else:
        base_contour = [
            {"x": 0.0, "y": 0.0},
            {"x": 180.0, "y": 0.0},
            {"x": 220.0, "y": 50.0},
            {"x": 190.0, "y": 100.0},
            {"x": 40.0, "y": 90.0},
            {"x": 0.0, "y": 45.0},
        ]

    pieces_per_size = total_pieces // num_sizes
    remainder = total_pieces % num_sizes

    shapes = []
    base_size = 33
    for i in range(num_sizes):
        size_num = base_size + i
        scale = 0.90 + (i * 0.015)
        scaled_contour = [
            {"x": round(p["x"] * scale, 3), "y": round(p["y"] * scale, 3)}
            for p in base_contour
        ]
        qty = pieces_per_size + (1 if i < remainder else 0)
        shapes.append({
            "id": i + 1,
            "name": f"Gaspea_{size_num}",
            "size": str(size_num),
            "sequence": i + 1,
            "pairs": qty,
            "layers": 2,
            "contour": scaled_contour,
        })

    return shapes


def run_benchmark(
    pieces: int = 1600,
    num_sizes: int = 16,
    backend: str = "nfp",
    strategy: str = "flashnestsheet",
    params: str = "FastNest",
    bed_w: float = 2000.0,
    bed_h: float = 1200.0,
    gap_mm: float = 1.0,
) -> dict:
    os.environ["CORTEAC_BACKEND"] = backend

    shapes = generate_benchmark_shapes(total_pieces=pieces, num_sizes=num_sizes)
    progress_calls = []

    def _progress(cur: int, tot: int):
        progress_calls.append((cur, tot))

    t_start = time.perf_counter()
    result = nest_multi_sheet(
        available_shapes=shapes,
        bed_width_mm=bed_w,
        bed_height_mm=bed_h,
        strategy=strategy,
        params=params,
        gap_mm=gap_mm,
        layers=2,
        margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
        progress_callback=_progress,
    )
    elapsed_sec = time.perf_counter() - t_start

    num_sheets = result.get("num_sheets", 0)
    placed_pieces = result.get("total_pieces", 0)
    target_met = (elapsed_sec < 10.0) and (placed_pieces == pieces)

    return {
        "success": result.get("success", False),
        "target_met": target_met,
        "elapsed_sec": round(elapsed_sec, 4),
        "elapsed_ms": round(elapsed_sec * 1000.0, 2),
        "total_pieces_demanded": pieces,
        "total_pieces_placed": placed_pieces,
        "num_sheets": num_sheets,
        "num_sizes": num_sizes,
        "backend": backend,
        "strategy": strategy,
        "params": params,
        "progress_calls_count": len(progress_calls),
        "first_progress": progress_calls[0] if progress_calls else None,
        "last_progress": progress_calls[-1] if progress_calls else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Multi-Sheet Nesting (1600 peças)")
    parser.add_argument("--pieces", type=int, default=1600, help="Total de peças a aninhar (default: 1600)")
    parser.add_argument("--sizes", type=int, default=16, help="Número de tamanhos graduados (default: 16)")
    parser.add_argument("--backend", default="nfp", choices=["nfp", "python"], help="Motor de nesting (default: nfp)")
    parser.add_argument("--strategy", default="flashnestsheet", help="Estratégia (default: flashnestsheet)")
    parser.add_argument("--params", default="FastNest", help="Preset (default: FastNest)")
    parser.add_argument("--bed-w", type=float, default=2000.0, help="Largura da mesa em mm (default: 2000.0)")
    parser.add_argument("--bed-h", type=float, default=1200.0, help="Altura da mesa em mm (default: 1200.0)")
    parser.add_argument("--gap", type=float, default=1.0, help="Gap em mm (default: 1.0)")
    parser.add_argument("--json", action="store_true", help="Saída estrita em JSON")
    args = parser.parse_args()

    bench = run_benchmark(
        pieces=args.pieces,
        num_sizes=args.sizes,
        backend=args.backend,
        strategy=args.strategy,
        params=args.params,
        bed_w=args.bed_w,
        bed_h=args.bed_h,
        gap_mm=args.gap,
    )

    if args.json:
        print(json.dumps(bench, indent=2))
    else:
        print("=" * 72)
        print("BENCHMARK MULTI-SHEET NESTING — CORTEAC (FASE 6.6)")
        print(f"Demanda: {bench['total_pieces_demanded']} peças ({bench['num_sizes']} tamanhos graduados)")
        print(f"Mesa: {args.bed_w}x{args.bed_h} mm | Gap: {args.gap} mm | Motor: {bench['backend']} ({bench['params']})")
        print("=" * 72)
        print(f"Tempo decorrido:         {bench['elapsed_sec']:.3f} s ({bench['elapsed_ms']:.1f} ms)")
        print(f"Peças aninhadas:         {bench['total_pieces_placed']} / {bench['total_pieces_demanded']}")
        print(f"Chapas geradas:          {bench['num_sheets']}")
        print(f"Notificações progresso:  {bench['progress_calls_count']} chamadas (Primeira: {bench['first_progress']}, Última: {bench['last_progress']})")
        print(f"Status da meta (< 10 s): {'✅ APROVADO' if bench['target_met'] else '❌ REPROVADO'}")
        print("=" * 72)

    return 0 if bench["target_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
