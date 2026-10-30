"""
tools/bench_real_shapes.py - Benchmark de motores de nesting com CONTORNOS REAIS.

Os benchmarks antigos (bench_multi_sheet.py / bench_10k_pieces.py) usam
samples/Gaspea_Derby_41.die, cujo contorno tem 7 vertices (1 parte convexa), e por
isso nunca exercitam a decomposicao convexa que domina o custo em moldes reais.

Este benchmark carrega os moldes reais de uma sessao do banco (jobmanager.db) e mede,
por estrategia: tempo, pecas encaixadas, colisoes e rendimento.

Uso:
    python3 tools/bench_real_shapes.py --session 156
    python3 tools/bench_real_shapes.py --session 156 --strategies flashnestsheet,ia-teste
    python3 tools/bench_real_shapes.py --session 156 --pieces 120 --json
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from cad.geometry import polygon_bbox, polygons_collide, transform_contour  # noqa: E402
from cad.nesting_engine import auto_nest_pieces  # noqa: E402

ALL_STRATEGIES = ["flashnestsheet", "sint", "tape_a", "freenest", "ia-teste"]


def load_session_shapes(db_path: Path, session_id: int) -> tuple[list[dict], dict, int]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    sess = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if sess is None:
        raise SystemExit(f"Sessao {session_id} nao encontrada em {db_path}")
    sess = dict(sess)
    shapes = json.loads(sess.get("shapes_json") or "[]")
    for s in shapes:
        if not s.get("contour") and s.get("contour_json"):
            s["contour"] = json.loads(s["contour_json"])
    material = {}
    if sess.get("material_id"):
        row = conn.execute("SELECT * FROM materials WHERE id = ?", (sess["material_id"],)).fetchone()
        if row:
            material = dict(row)
    conn.close()
    layers = int(material.get("layers") or 2)
    return shapes, material, layers


def count_collisions(pieces: list[dict], gap: float = 0.0) -> int:
    polys, boxes = [], []
    for p in pieces:
        poly = transform_contour(p["shape"]["contour"], p["x"], p["y"], p.get("rotation", 0))
        polys.append(poly)
        boxes.append(polygon_bbox(poly))
    total = 0
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            a, b = boxes[i], boxes[j]
            if a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]:
                continue
            if polygons_collide(polys[i], polys[j], gap=gap, bbox_a=a, bbox_b=b):
                total += 1
    return total


def run_strategy(shapes, material, layers, strategy, params, piece_cap, timeout, backend=None):
    if backend:
        os.environ["CORTEAC_BACKEND"] = backend
    bed_w = float(material.get("width_mm") or 1380.0)
    bed_h = float(material.get("height_mm") or 2980.0)
    queue = []
    remaining = piece_cap
    for s in shapes:
        if remaining <= 0:
            break
        take = min(remaining, max(1, -(-(int(s.get("pairs", 0)) * 2) // layers)))
        queue.append(dict(s, target_pieces=take))
        remaining -= take

    started = time.perf_counter()
    try:
        placed = auto_nest_pieces(
            available_shapes=queue,
            bed_width_mm=bed_w,
            bed_height_mm=bed_h,
            target_count=max(1, piece_cap - remaining),
            strategy=strategy,
            params=params,
            gap_mm=1.0,
            dieproc_params={"coupling": "0/0 0/180", "row_interlock": True, "sheet_timeout_sec": timeout},
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            layers=layers,
        )
        error = None
    except Exception as exc:  # noqa: BLE001
        placed, error = [], f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started

    collisions = count_collisions(placed)
    return {
        "strategy": strategy,
        "params": params,
        "pieces": len(placed),
        "seconds": round(elapsed, 3),
        "ms_per_piece": round(elapsed * 1000.0 / len(placed), 2) if placed else None,
        "collisions": collisions,
        "error": error,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark de nesting com contornos reais")
    parser.add_argument("--db", default=str(BASE_DIR / "jobmanager.db"))
    parser.add_argument("--session", type=int, default=156)
    parser.add_argument("--strategies", default=",".join(ALL_STRATEGIES))
    parser.add_argument("--pieces", type=int, default=60, help="Teto de pecas por medicao (padrao 60)")
    parser.add_argument("--timeout", type=float, default=20.0, help="Timeout por placa em segundos")
    parser.add_argument("--params", default="FastNest")
    parser.add_argument("--backend", default=None, help="python | nfp (padrao: o do ambiente)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    shapes, material, layers = load_session_shapes(Path(args.db), args.session)
    verts = [len(s.get("contour") or []) for s in shapes]
    print(
        f"Sessao {args.session}: {len(shapes)} moldes, {sum(int(s.get('pairs', 0)) for s in shapes)} pares, "
        f"vertices/ molde min={min(verts)} max={max(verts)}, placa {material.get('width_mm')}x{material.get('height_mm')} mm, "
        f"camadas={layers}",
        flush=True,
    )

    results = []
    for strategy in [s.strip() for s in args.strategies.split(",") if s.strip()]:
        row = run_strategy(
            shapes, material, layers, strategy, args.params, args.pieces, args.timeout, args.backend
        )
        results.append(row)
        if not args.json:
            status = row["error"] or f"{row['pieces']} pecas, {row['collisions']} colisoes"
            print(f"  {strategy:14s} {row['seconds']:7.3f}s  {status}", flush=True)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
