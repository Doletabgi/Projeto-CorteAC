#!/usr/bin/env python3
"""
tools/bench_layout_drag.py

Benchmark de arraste do Layout Editor (CorteAC), sem interacao manual.
Reproduz o caminho real de eventos: clique -> N x (Motion + B1-Motion) -> release.

Uso:
    python tools/bench_layout_drag.py --pieces 120 --events 240
    python tools/bench_layout_drag.py --pieces 120 --events 240 --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from cad.die_parser import parse_die_file  # noqa: E402
from cad.geometry import polygon_bbox, transform_contour  # noqa: E402
from ui.layout_editor_view import LayoutEditorView  # noqa: E402


def build_pieces(count: int) -> list[dict]:
    sample = parse_die_file(str(BASE_DIR / "samples" / "Gaspea_Derby_41.die"))
    contour = sample["contour"]
    pieces = []
    columns = 4
    for index in range(count):
        row, column = divmod(index, columns)
        size = str(36 + index % 16)
        pieces.append(
            {
                "name": f"Gaspea_{size}a",
                "size": size,
                "contour": contour,
                "x": 20.0 + column * 320.0,
                "y": 20.0 + row * 95.0,
                "rotation": 0,
                "target_id": f"t{size}",
                "shape": {"size": size},
            }
        )
    return pieces


def screen_of(editor: LayoutEditorView, piece: dict) -> tuple[float, float]:
    poly = transform_contour(piece["contour"], piece["x"], piece["y"], piece["rotation"])
    min_x, min_y, max_x, max_y = polygon_bbox(poly)
    wx = (min_x + max_x) / 2.0
    wy = (min_y + max_y) / 2.0
    return editor.plate_x1 + wx * editor.plate_scale, editor.plate_y2 - wy * editor.plate_scale


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pieces", type=int, default=120)
    parser.add_argument("--events", type=int, default=240)
    parser.add_argument("--interval-ms", type=float, default=4.0, help="intervalo simulado entre eventos de mouse")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = tk.Tk()
    root.geometry("1400x900+40+40")
    editor = LayoutEditorView(root, layout_name="[bench]", load_sample=False)
    editor.pack(fill="both", expand=True)
    root.update()

    editor.sheet_width = 1380.0
    editor.sheet_height = 2980.0
    editor.placed_pieces = build_pieces(args.pieces)
    editor.selected_index = -1

    started = time.perf_counter()
    editor.redraw()
    root.update()
    redraw_ms = (time.perf_counter() - started) * 1000.0

    index = min(args.pieces - 1, args.pieces // 2)
    start_x, start_y = screen_of(editor, editor.placed_pieces[index])
    click = SimpleNamespace(x=int(start_x), y=int(start_y), state=0)
    started = time.perf_counter()
    editor.on_canvas_click(click)
    root.update()
    click_ms = (time.perf_counter() - started) * 1000.0

    if not getattr(editor, "is_dragging_piece", False):
        print("ERRO: clique nao iniciou o arraste", file=sys.stderr)
        return 2

    move_times: list[float] = []
    motion_times: list[float] = []
    loop_times: list[float] = []
    for step in range(args.events):
        x = int(start_x + step * 1.5)
        y = int(start_y + step * 0.4)
        event = SimpleNamespace(x=x, y=y, state=0x0100, delta=0)
        # Tk entrega <Motion> e <B1-Motion> para o mesmo evento fisico:
        # ambos os bindings executam, entao medimos os dois.
        loop_started = time.perf_counter()
        t0 = time.perf_counter()
        editor.on_mouse_move(event)
        t1 = time.perf_counter()
        editor.on_canvas_drag(event)
        t2 = time.perf_counter()
        root.update()  # deixa o Tk pintar e rodar callbacks after() pendentes
        busy = time.perf_counter() - loop_started
        loop_times.append(busy * 1000.0)
        # pacing: mouse real nao chega mais rapido que o intervalo configurado
        remaining = args.interval_ms / 1000.0 - busy
        if remaining > 0:
            time.sleep(remaining)
        motion_times.append((t1 - t0) * 1000.0)
        move_times.append((t2 - t1) * 1000.0)

    release = SimpleNamespace(x=int(start_x + args.events * 1.5), y=int(start_y), state=0)
    started = time.perf_counter()
    editor.on_canvas_release(release)
    root.update()
    release_ms = (time.perf_counter() - started) * 1000.0

    total_ms = sum(move_times) + sum(motion_times)
    payload = {
        "pieces": args.pieces,
        "events": args.events,
        "redraw_ms": round(redraw_ms, 2),
        "click_ms": round(click_ms, 2),
        "release_ms": round(release_ms, 2),
        "drag_total_ms": round(total_ms, 2),
        "drag_avg_ms": round(total_ms / args.events, 3),
        "drag_p95_ms": round(statistics.quantiles(move_times + motion_times, n=20)[-1], 3),
        "drag_events_per_s": round(args.events / (total_ms / 1000.0), 1),
        "motion_avg_ms": round(statistics.fmean(motion_times), 3),
        "move_avg_ms": round(statistics.fmean(move_times), 3),
        "loop_avg_ms": round(statistics.fmean(loop_times), 3),
        "loop_p95_ms": round(statistics.quantiles(loop_times, n=20)[-1], 3),
        "loop_events_per_s": round(1000.0 / statistics.fmean(loop_times), 1),
        "interval_ms": args.interval_ms,
    }
    root.destroy()

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"pecas={payload['pieces']} eventos={payload['events']}")
        print(f"redraw inicial .......... {payload['redraw_ms']:>8.2f} ms")
        print(f"clique (inicio arraste) . {payload['click_ms']:>8.2f} ms")
        print(f"arraste total ........... {payload['drag_total_ms']:>8.2f} ms")
        print(f"arraste por evento ...... {payload['drag_avg_ms']:>8.3f} ms (p95 {payload['drag_p95_ms']:.3f})")
        print(f"  <Motion> (cursor/status) {payload['motion_avg_ms']:>8.3f} ms")
        print(f"  <B1-Motion> (peca) .... {payload['move_avg_ms']:>8.3f} ms")
        print(f"taxa efetiva ............ {payload['drag_events_per_s']:>8.1f} eventos/s")
        print(f"release (fim arraste) ... {payload['release_ms']:>8.2f} ms")
        print(f"intervalo simulado ....... {payload['interval_ms']:>8.2f} ms")
        print(f"laco real (evt+repintar)  {payload['loop_avg_ms']:>8.3f} ms (p95 {payload['loop_p95_ms']:.3f})")
        print(f"taxa com repintura ...... {payload['loop_events_per_s']:>8.1f} eventos/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
