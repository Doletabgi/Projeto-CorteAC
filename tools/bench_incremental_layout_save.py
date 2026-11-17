"""Compara salvamento antigo/incremental em SQLite temporário, sem banco operacional.

Uso: python3 tools/bench_incremental_layout_save.py --output /tmp/save-benchmark.json
"""
import argparse
import ast
import copy
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import types

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import database


def old_save(ref):
    source = subprocess.check_output(["git", "show", f"{ref}:database.py"], cwd=ROOT, text=True)
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DatabaseManager")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "save_session_layouts")
    scope = dict(vars(database))
    exec(compile(ast.Module(body=[method], type_ignores=[]), "<baseline-save>", "exec"), scope)
    return scope[method.name]


def make_layouts(count, pieces_per_sheet):
    contour = [{"x": round(20 + 20 * math.cos(i * math.pi / 10), 4),
                "y": round(15 + 15 * math.sin(i * math.pi / 10), 4)} for i in range(20)]
    pieces = [{"id": i + 1, "name": "Molde benchmark", "size": "41", "x": (i % 10) * 50,
               "y": (i // 10) * 40, "rotation": 0.0, "contour": contour}
              for i in range(pieces_per_sheet)]
    return [{"layout_index": i, "name": f"lay{i:04d}", "layers": 4,
             "width_mm": 1380, "height_mm": 2980, "yield_percent": 65,
             "pieces": copy.deepcopy(pieces)} for i in range(count)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="v1.8.27")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--pieces", type=int, default=100)
    parser.add_argument("--sheets", type=int, nargs="+", default=[10, 50, 100])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 2 or args.pieces < 1 or any(n < 1 for n in args.sheets):
        parser.error("Use ao menos duas repetições e quantidades positivas.")
    baseline = old_save(args.baseline)
    results = []
    with tempfile.TemporaryDirectory(prefix="opencorte-save-bench-") as temporary:
        for sheets in args.sheets:
            for scenario in ("one_sheet", "one_sheet_cold", "unchanged", "all_sheets"):
                row = {"sheets": sheets, "pieces_per_sheet": args.pieces, "scenario": scenario}
                for name, method in (("before", baseline), ("after", database.DatabaseManager.save_session_layouts)):
                    db = database.DatabaseManager(Path(temporary) / f"{sheets}-{scenario}-{name}.db")
                    sid = db.create_session(name="Benchmark temporário")
                    save = types.MethodType(method, db)
                    data = make_layouts(sheets, args.pieces)
                    save(sid, data)
                    samples = []
                    for iteration in range(args.repeats + 2):
                        if scenario != "unchanged":
                            indices = [sheets // 2] if scenario.startswith("one_sheet") else range(sheets)
                            for i in indices:
                                data[i]["pieces"][0]["x"] += 1.0
                        if scenario == "one_sheet_cold":
                            db._layout_serialization_cache = {}
                        start = time.perf_counter()
                        save(sid, data)
                        elapsed = (time.perf_counter() - start) * 1000
                        if iteration >= 2:
                            samples.append(elapsed)
                    row[name] = {"mean_ms": statistics.mean(samples), "median_ms": statistics.median(samples),
                                 "stdev_ms": statistics.stdev(samples), "samples_ms": samples}
                row["time_reduction_percent"] = 100 * (1 - row["after"]["mean_ms"] / row["before"]["mean_ms"])
                results.append(row)
                print(f"{sheets:3} placas | {scenario:10} | {row['before']['mean_ms']:.1f} → "
                      f"{row['after']['mean_ms']:.1f} ms | redução {row['time_reduction_percent']:.1f}%", flush=True)
    result = {"environment": platform.platform(), "python": platform.python_version(),
              "storage": "SQLite em arquivos temporários locais; sem latência de rede simulada",
              "baseline": args.baseline, "repeats": args.repeats, "warmups": 2, "results": results}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
