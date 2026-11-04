#!/usr/bin/env python3
"""
Exporta uma sessão multi-placa do CorteAC para uma pasta pronta para a máquina ATOM.

Uso típico (Windows, na pasta do CorteAC):

    python tools/export_session.py --session 282 --target "E:\\CorteAC"

Saída:

    E:\\CorteAC\\SESS-282\\
        manifest.json
        lay0000.lay
        lay0001.lay
        Shapes\\
            323_PalAcb_36a.die
            ...

O ``--cac`` é opcional e cria um ZIP com essa mesma pasta:

    python tools/export_session.py --session 282 --target "E:\\CorteAC" --cac "E:\\CorteAC\\SESS-282.cac"

Para buscar os .die originais na rede (preserva fio/qualidade):

    python tools/export_session.py --session 282 --target "E:\\CorteAC" --shapes-root "\\\\lab-inf\\NSDATAV1\\Shapes"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Permite executar como "python tools/export_session.py" a partir da raiz.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cad.project_packager import (  # noqa: E402
    MissingDiesError,
    PackagingError,
    export_session,
    pack_session_folder,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exporta uma sessão multi-placa do CorteAC para a máquina ATOM.",
    )
    parser.add_argument("--session", type=int, required=True, help="ID da sessão")
    parser.add_argument("--target", required=True, help="Pasta de destino (rede ou pendrive)")
    parser.add_argument("--cac", default="", help="Opcional: também gera um arquivo .cac (ZIP)")
    parser.add_argument("--db", default="", help="Caminho alternativo do SQLite (opcional)")
    parser.add_argument("--no-subfolder", action="store_true", help="Grava direto na pasta escolhida")
    parser.add_argument(
        "--no-copy-dies",
        action="store_true",
        help="Modo referência: não copia .die; use com --dlib apontando para a biblioteca existente",
    )
    parser.add_argument("--dlib", default="", help="dLib fixo para modo referência")
    parser.add_argument(
        "--shapes-root",
        action="append",
        default=[],
        help="Pasta para procurar .die originais por nome (pode repetir)",
    )
    parser.add_argument("--strict", action="store_true", help="Falha se algum molde estiver ausente")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    parser.add_argument("--quiet", action="store_true", help="Não imprime o resumo humano")
    return parser


def _print_summary(result, cac_path=None) -> None:
    print(f"Sessão exportada: {result.session_code} (#{result.session_id})")
    print(f"Destino: {result.session_dir}")
    print(f"Placas: {len(result.layouts)}")
    for layout in result.layouts:
        print(f"  - {layout.filename} ({layout.num_items} peças)")
    print(f"Moldes: {len(result.dies)}")
    file_count = sum(1 for d in result.dies if d.source == "file")
    db_count = sum(1 for d in result.dies if d.source == "db")
    if file_count or db_count:
        print(f"  - arquivo original: {file_count}")
        print(f"  - gerados do banco: {db_count}")
    if result.missing:
        print(f"AUSENTES: {len(result.missing)}")
        for miss in result.missing:
            print(f"  - {miss.get('name')} ({miss.get('code')}): {miss.get('reason')}")
    if result.warnings:
        print("Avisos:")
        for warning in result.warnings[:12]:
            print(f"  - {warning}")
        if len(result.warnings) > 12:
            print(f"  ... (+{len(result.warnings) - 12} avisos)")
    if cac_path:
        print(f".cac: {cac_path}")
    print(f"Tempo: {result.elapsed_sec:.2f}s")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        from database import DatabaseManager
        db = DatabaseManager(db_path=args.db) if args.db else DatabaseManager()
    except Exception as exc:
        print(f"Erro ao abrir o banco: {exc}", file=sys.stderr)
        return 1

    try:
        result = export_session(
            db,
            args.session,
            args.target,
            create_subfolder=not args.no_subfolder,
            copy_dies=not args.no_copy_dies,
            dlib_override=args.dlib or None,
            shapes_search_roots=args.shapes_root or None,
            strict=args.strict,
        )
    except MissingDiesError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": "missing_dies", "missing": exc.missing}, ensure_ascii=False, indent=2))
        else:
            print(f"ERRO: {exc}", file=sys.stderr)
            for miss in exc.missing:
                print(f"  - {miss.get('name')} ({miss.get('code')}): {miss.get('reason')}", file=sys.stderr)
        return 2
    except PackagingError as exc:
        print(f"Erro de empacotamento: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Erro inesperado: {exc}", file=sys.stderr)
        return 1

    cac_path = None
    if args.cac:
        try:
            cac_path = pack_session_folder(result.session_dir, args.cac)
            result.cac_path = cac_path
        except Exception as exc:
            print(f"Erro ao gerar .cac: {exc}", file=sys.stderr)
            return 1

    if args.json:
        payload = result.to_dict()
        payload["ok"] = result.complete
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif not args.quiet:
        _print_summary(result, cac_path)

    if result.missing:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
