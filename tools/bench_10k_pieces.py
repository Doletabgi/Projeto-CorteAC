#!/usr/bin/env python3
"""
tools/bench_10k_pieces.py

Benchmark extremo de estresse para validação de estabilidade de memória e tempo
com carga máxima de produção: 10.000 peças (Fase 6.6.1).

Cenário:
- 10.000 peças (500 pares x 20 tamanhos graduados com contornos reais de calçados).
- Mesa padrão: 2000 x 1200 mm | Gap: 1.0 mm | Camadas: 2.
- Motor: flashnestsheet no modo acelerado NfpBackend (FastNest).
- Telemetria de progresso determinado via progress_callback.

Critérios de Aceite:
- Tempo total: < 60.0 s (ideal < 10.0 s)
- Consumo máximo de RAM: < 2.0 GB (2048 MB)
- Ocorrência de MemoryError: Zero
- UI/Thread responsiva via progress_callback: Sim
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from cad.die_parser import parse_die_file  # noqa: E402
from cad.nesting_engine import nest_multi_sheet  # noqa: E402


def get_current_rss_mb() -> float:
    """Retorna o uso atual de memória RSS do processo em MB."""
    if psutil is not None:
        return psutil.Process().memory_info().rss / (1024.0 * 1024.0)
    # Fallback via resource (Linux ru_maxrss é em KiB)
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def get_peak_rss_mb() -> float:
    """Retorna o pico histórico de memória RSS do processo em MB."""
    # No Linux, ru_maxrss é reportado em KiB
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def generate_10k_shapes(total_pieces: int = 10000, num_sizes: int = 20) -> list[dict]:
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
    base_size = 30
    for i in range(num_sizes):
        size_num = base_size + i
        scale = 0.85 + (i * 0.015)
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


def run_stress_test(
    pieces: int = 10000,
    num_sizes: int = 20,
    backend: str = "nfp",
    strategy: str = "flashnestsheet",
    params: str = "FastNest",
    bed_w: float = 2000.0,
    bed_h: float = 1200.0,
    gap_mm: float = 1.0,
    max_sheets: int = 500,
) -> dict:
    os.environ["CORTEAC_BACKEND"] = backend

    shapes = generate_10k_shapes(total_pieces=pieces, num_sizes=num_sizes)

    mem_before_mb = get_current_rss_mb()
    progress_samples = []
    memory_samples_mb = [mem_before_mb]

    def _progress(cur: int, tot: int):
        progress_samples.append((cur, tot))
        # Amostragem periódica de memória a cada 10 chapas
        if len(progress_samples) % 10 == 0:
            memory_samples_mb.append(get_current_rss_mb())

    has_memory_error = False
    error_msg = None
    t_start = time.perf_counter()

    try:
        result = nest_multi_sheet(
            available_shapes=shapes,
            bed_width_mm=bed_w,
            bed_height_mm=bed_h,
            strategy=strategy,
            params=params,
            gap_mm=gap_mm,
            layers=2,
            max_sheets=max_sheets,
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            progress_callback=_progress,
        )
    except MemoryError as me:
        has_memory_error = True
        error_msg = f"MemoryError capturado: {me}"
        result = {"success": False, "total_pieces": 0, "num_sheets": 0}
    except Exception as ex:
        error_msg = f"Erro na execução: {ex}"
        result = {"success": False, "total_pieces": 0, "num_sheets": 0}

    elapsed_sec = time.perf_counter() - t_start
    mem_after_mb = get_current_rss_mb()
    peak_rss_mb = get_peak_rss_mb()

    placed_pieces = result.get("total_pieces", 0)
    num_sheets = result.get("num_sheets", 0)

    time_target_met = (elapsed_sec < 60.0)
    ideal_time_met = (elapsed_sec < 10.0)
    ram_target_met = (peak_rss_mb < 2048.0)
    pieces_complete = (placed_pieces == pieces)

    all_targets_ok = (
        time_target_met
        and ram_target_met
        and (not has_memory_error)
        and pieces_complete
        and result.get("success", False)
    )

    return {
        "success": result.get("success", False),
        "all_targets_met": all_targets_ok,
        "elapsed_sec": round(elapsed_sec, 4),
        "elapsed_ms": round(elapsed_sec * 1000.0, 2),
        "time_target_met (< 60s)": time_target_met,
        "ideal_time_met (< 10s)": ideal_time_met,
        "mem_initial_mb": round(mem_before_mb, 2),
        "mem_final_mb": round(mem_after_mb, 2),
        "peak_ram_mb": round(peak_rss_mb, 2),
        "ram_target_met (< 2GB)": ram_target_met,
        "memory_error": has_memory_error,
        "error_message": error_msg,
        "total_pieces_demanded": pieces,
        "total_pieces_placed": placed_pieces,
        "num_sheets": num_sheets,
        "num_sizes": num_sizes,
        "backend": backend,
        "strategy": strategy,
        "params": params,
        "progress_calls_count": len(progress_samples),
        "first_progress": progress_samples[0] if progress_samples else None,
        "last_progress": progress_samples[-1] if progress_samples else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress Test Multi-Sheet Nesting (10.000 peças)")
    parser.add_argument("--pieces", type=int, default=10000, help="Quantidade de peças (default: 10000)")
    parser.add_argument("--sizes", type=int, default=20, help="Quantidade de tamanhos (default: 20)")
    parser.add_argument("--backend", default="nfp", choices=["nfp", "python"], help="Motor de nesting (default: nfp)")
    parser.add_argument("--strategy", default="flashnestsheet", help="Estratégia (default: flashnestsheet)")
    parser.add_argument("--params", default="FastNest", help="Preset (default: FastNest)")
    parser.add_argument("--max-sheets", type=int, default=500, help="Limite de chapas (default: 500)")
    parser.add_argument("--bed-w", type=float, default=2000.0, help="Largura da mesa em mm (default: 2000.0)")
    parser.add_argument("--bed-h", type=float, default=1200.0, help="Altura da mesa em mm (default: 1200.0)")
    parser.add_argument("--gap", type=float, default=1.0, help="Gap em mm (default: 1.0)")
    parser.add_argument("--json", action="store_true", help="Saída estrita em JSON")
    args = parser.parse_args()

    bench = run_stress_test(
        pieces=args.pieces,
        num_sizes=args.sizes,
        backend=args.backend,
        strategy=args.strategy,
        params=args.params,
        bed_w=args.bed_w,
        bed_h=args.bed_h,
        gap_mm=args.gap,
        max_sheets=args.max_sheets,
    )

    if args.json:
        print(json.dumps(bench, indent=2))
    else:
        print("=" * 76)
        print("TESTE DE ESTRESSE 10K PEÇAS — NESTING MULTI-SHEET (FASE 6.6.1)")
        print(f"Demanda: {bench['total_pieces_demanded']} peças ({bench['num_sizes']} tamanhos graduados)")
        print(f"Mesa: {args.bed_w}x{args.bed_h} mm | Gap: {args.gap} mm | Motor: {bench['backend']} ({bench['params']})")
        print("=" * 76)
        print(f"Tempo total:             {bench['elapsed_sec']:.3f} s ({bench['elapsed_ms']:.1f} ms)")
        print(f"Meta de tempo (< 60s):   {'✅ APROVADO' if bench['time_target_met (< 60s)'] else '❌ REPROVADO'} (Ideal < 10s: {'✅ SIM' if bench['ideal_time_met (< 10s)'] else '⚠️ NÃO'})")
        print(f"Peças aninhadas:         {bench['total_pieces_placed']} / {bench['total_pieces_demanded']}")
        print(f"Chapas geradas:          {bench['num_sheets']}")
        print(f"Memória Inicial (RSS):   {bench['mem_initial_mb']:.2f} MB")
        print(f"Memória Final (RSS):     {bench['mem_final_mb']:.2f} MB")
        print(f"Pico de Memória RAM:     {bench['peak_ram_mb']:.2f} MB")
        print(f"Meta de RAM (< 2048 MB): {'✅ APROVADO' if bench['ram_target_met (< 2GB)'] else '❌ REPROVADO'}")
        print(f"Ocorrência MemoryError:  {'❌ SIM' if bench['memory_error'] else '✅ ZERO'}")
        print(f"Progresso (chamadas):    {bench['progress_calls_count']} eventos (Primeiro: {bench['first_progress']}, Último: {bench['last_progress']})")
        print("=" * 76)
        print(f"STATUS FINAL:            {'✅ APROVADO EM TODOS OS CRITÉRIOS' if bench['all_targets_met'] else '❌ REPROVADO'}")
        print("=" * 76)

    return 0 if bench["all_targets_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
