#!/usr/bin/env python3
"""
tools/capture_layout_screenshots.py

Captura e compara screenshots do LayoutEditorView para prevenir regressões visuais
durante as otimizações de performance (LOD, cache de contorno e redraw incremental).

Uso:
    # Capturar baseline imutável
    python3 tools/capture_layout_screenshots.py --output-dir tests/fixtures/layout_screenshots/

    # Comparar contra o baseline
    python3 tools/capture_layout_screenshots.py --compare tests/fixtures/layout_screenshots/
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import tkinter as tk
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageChops

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from cad.die_parser import parse_die_file  # noqa: E402
from ui.layout_editor_view import LayoutEditorView  # noqa: E402


def build_test_pieces(count: int = 100) -> list[dict]:
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


def render_scenario(scenario_name: str, count: int = 100) -> Image.Image:
    root = tk.Tk()
    root.geometry("1400x900+40+40")
    editor = LayoutEditorView(root, layout_name="[visual_bench]", load_sample=False)
    editor.pack(fill="both", expand=True)
    root.update()

    editor.sheet_width = 1380.0
    editor.sheet_height = 2980.0
    editor.placed_pieces = build_test_pieces(count)
    editor.selected_indices = []
    editor.selected_index = None

    if scenario_name == "01_initial":
        editor.zoom_factor = 1.0
        editor.pan_offset_x = 0.0
        editor.pan_offset_y = 0.0
        editor.redraw()
    elif scenario_name == "02_zoom_in":
        editor.zoom_factor = 1.3
        editor.pan_offset_x = 0.0
        editor.pan_offset_y = 0.0
        editor.redraw()
    elif scenario_name == "03_zoom_out":
        editor.zoom_factor = 0.7
        editor.pan_offset_x = 0.0
        editor.pan_offset_y = 0.0
        editor.redraw()
    elif scenario_name == "04_pan":
        editor.zoom_factor = 1.0
        editor.pan_offset_x = 50.0
        editor.pan_offset_y = -35.0
        editor.redraw()
    elif scenario_name == "05_selection":
        editor.zoom_factor = 1.0
        editor.pan_offset_x = 0.0
        editor.pan_offset_y = 0.0
        editor.selected_indices = [3, 7, 15]
        editor.selected_index = 15
        editor.redraw()
    elif scenario_name == "06_after_drag":
        editor.zoom_factor = 1.0
        editor.pan_offset_x = 0.0
        editor.pan_offset_y = 0.0
        editor.selected_indices = [5]
        editor.selected_index = 5
        # Move peça 5 30mm em X e 20mm em Y
        editor.placed_pieces[5]["x"] += 30.0
        editor.placed_pieces[5]["y"] += 20.0
        editor.redraw()
    else:
        editor.redraw()

    root.update()
    ps = editor.canvas.postscript(colormode="color")
    img = Image.open(io.BytesIO(ps.encode("utf-8")))
    root.destroy()
    return img.convert("RGB")


def run_scenarios(output_dir: Path | None = None, compare_dir: Path | None = None) -> bool:
    scenarios = [
        "01_initial",
        "02_zoom_in",
        "03_zoom_out",
        "04_pan",
        "05_selection",
        "06_after_drag",
    ]

    all_passed = True

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        for sc in scenarios:
            img = render_scenario(sc)
            dest = output_dir / f"{sc}.png"
            img.save(dest)
            print(f"[OK] Salvo: {dest}")

    if compare_dir:
        print("\n" + "=" * 70)
        print("COMPARAÇÃO DE REGRESSÃO VISUAL (Tolerância estrita: 0 px)")
        print("=" * 70)
        for sc in scenarios:
            base_file = compare_dir / f"{sc}.png"
            if not base_file.exists():
                print(f"[ERRO] Baseline ausente para {sc}: {base_file}")
                all_passed = False
                continue

            current_img = render_scenario(sc)
            base_img = Image.open(base_file).convert("RGB")

            if current_img.size != base_img.size:
                print(f"[FALHA] {sc}: Tamanho divergente {current_img.size} vs {base_img.size}")
                all_passed = False
                continue

            diff = ImageChops.difference(current_img, base_img)
            bbox = diff.getbbox()
            if bbox is not None:
                diff_pixels = sum(1 for px in diff.getdata() if any(c > 0 for c in px))
                print(f"[FALHA] {sc}: Divergência visual encontrada! {diff_pixels} pixels diferentes no bbox {bbox}")
                all_passed = False
            else:
                print(f"[PASS]  {sc}: 0 px de diferença (fidelidade visual 100.0%)")

        print("=" * 70)
        if all_passed:
            print("[SUCESSO] Todos os 6 cenários validados com 0 px de divergência!")
        else:
            print("[ERRO] Regressão visual detectada!")

    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Captura e Verificação de Regressão Visual no LayoutEditorView")
    parser.add_argument("--output-dir", type=str, default=None, help="Diretório onde salvar os screenshots gerados")
    parser.add_argument("--compare", type=str, default=None, help="Diretório com baseline para comparação de diferença")
    args = parser.parse_args()

    out_p = Path(args.output_dir) if args.output_dir else None
    cmp_p = Path(args.compare) if args.compare else None

    if not out_p and not cmp_p:
        out_p = BASE_DIR / "tests" / "fixtures" / "layout_screenshots"

    success = run_scenarios(output_dir=out_p, compare_dir=cmp_p)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
