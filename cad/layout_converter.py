"""
JobManager 2000 / CorteAC (Python Edition)
CAM / CAD: Conversor Bidirecional de Arquivos de Corte (.lay ⇄ .onx)
Converte formatos entre ATOM FlashCut ($$LAYOUT.v3$$) e Comelz CNC (CZLIB v2 / ONX Schema 1.1).
"""

import os
import sys
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

from cad.lay_parser import parse_lay, generate_lay_content, LayoutData, TargetDie, PlacedItem
from cad.onx_exporter import parse_onx, save_onx_file, export_onx_from_pieces
from cad.die_parser import clean_shape_name
from cad.geometry import polygon_area


@dataclass
class ConversionResult:
    """Resultado estruturado de uma operação de conversão de layout."""
    success: bool
    source_file: str
    target_file: str
    direction: str  # "lay_to_onx" | "onx_to_lay"
    items_count: int = 0
    dies_count: int = 0
    width_mm: float = 0.0
    height_mm: float = 0.0
    gap_mm: float = 0.0
    material_code: str = ""
    error_message: Optional[str] = None


def detect_file_format(file_path: Union[str, Path]) -> str:
    """
    Detecta o formato do arquivo de corte por extensão e cabeçalho mágico.
    Retorna: 'lay', 'onx' ou 'unknown'.
    """
    p = Path(file_path)
    suffix = p.suffix.lower()

    if suffix == ".lay":
        return "lay"
    elif suffix == ".onx":
        return "onx"

    # Sondagem por conteúdo binário / texto caso a extensão seja atípica
    if p.exists() and p.is_file():
        try:
            with open(p, "rb") as fp:
                head = fp.read(64)
                if head.startswith(b"CZLIB") or b"<onx" in head:
                    return "onx"
                if head.startswith(b"$$LAYOUT"):
                    return "lay"
        except Exception:
            pass

    return "unknown"


def convert_lay_to_onx(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    margins_mm: Union[float, Tuple[float, float, float, float]] = 15.0,
    db=None
) -> ConversionResult:
    """
    Converte um arquivo ATOM FlashCut (.lay) para o formato Comelz CNC (.onx).
    Compacta com container proprietário CZLIB v2 e gera XML em conformidade com ONX Schema 1.1.
    """
    src_p = Path(input_path)
    if not src_p.exists():
        return ConversionResult(
            success=False,
            source_file=str(src_p),
            target_file=str(output_path or ""),
            direction="lay_to_onx",
            error_message=f"Arquivo de origem não encontrado: {src_p}"
        )

    dst_p = Path(output_path) if output_path else src_p.with_suffix(".onx")
    if dst_p.suffix.lower() != ".onx":
        dst_p = dst_p.with_suffix(".onx")

    try:
        layout = parse_lay(src_p, db=db)

        # Mapeia as peças posicionadas para o formato esperado pelo exportador Comelz
        pieces = []
        for it in layout.items:
            m_name = ""
            if it.target_die and it.target_die.clean_name:
                m_name = it.target_die.clean_name
            elif it.shape_name:
                m_name = clean_shape_name(it.shape_name)
            else:
                m_name = "Model"

            part_name = it.shape_name or (it.target_die.clean_name if it.target_die else f"Molde_{it.tg_idx}")
            area_val = 0.0
            if it.contour:
                area_val = abs(polygon_area(it.contour))
            if area_val <= 0.0 and layout.area > 0 and len(layout.items) > 0:
                area_val = layout.area / len(layout.items)

            pieces.append({
                "id": it.item_no,
                "name": part_name,
                "size": it.size or "41",
                "x": it.x,
                "y": it.y,
                "rotation": it.rot_deg,
                "rot_rad": it.rot_rad,
                "is_mirrored": it.is_mirrored,
                "contour": it.contour,
                "area": area_val,
                "model_name": m_name
            })

        mat = {
            "width_mm": layout.ris_w,
            "height_mm": layout.ris_l,
            "gap_mm": layout.gap,
            "id": layout.cod_r or "884412",
            "name": layout.cod_r or "SINTETICO",
            "layers": layout.layers or 1
        }

        save_onx_file(
            placed_pieces=pieces,
            material=mat,
            file_path=dst_p,
            margins_mm=margins_mm,
            options={"order_code": str(layout.session_id or 1)}
        )

        return ConversionResult(
            success=True,
            source_file=str(src_p),
            target_file=str(dst_p),
            direction="lay_to_onx",
            items_count=len(layout.items),
            dies_count=len(layout.target_dies),
            width_mm=layout.ris_w,
            height_mm=layout.ris_l,
            gap_mm=layout.gap,
            material_code=layout.cod_r
        )

    except Exception as e:
        return ConversionResult(
            success=False,
            source_file=str(src_p),
            target_file=str(dst_p),
            direction="lay_to_onx",
            error_message=str(e)
        )


def convert_onx_to_lay(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    db=None
) -> ConversionResult:
    """
    Converte um arquivo Comelz CNC (.onx) para o formato padrão ATOM FlashCut (.lay).
    Descomprime CZLIB v2/v1 e constrói arquivo $$LAYOUT.v3$$ com codificação Latin1 e CRLF.
    """
    src_p = Path(input_path)
    if not src_p.exists():
        return ConversionResult(
            success=False,
            source_file=str(src_p),
            target_file=str(output_path or ""),
            direction="onx_to_lay",
            error_message=f"Arquivo de origem não encontrado: {src_p}"
        )

    dst_p = Path(output_path) if output_path else src_p.with_suffix(".lay")
    if dst_p.suffix.lower() != ".lay":
        dst_p = dst_p.with_suffix(".lay")

    try:
        layout = parse_onx(src_p, db=db)

        # Ajusta metas de corte para cada matriz se não vierem explicitadas
        for tg in layout.target_dies:
            if tg.targ_left == 0 and tg.targ_right == 0:
                tg.targ_left = max(tg.qta_left, 1)
                tg.targ_right = tg.qta_right

        lay_content = generate_lay_content(
            layout_data=layout,
            filename_override=dst_p.name
        )

        dst_p.parent.mkdir(parents=True, exist_ok=True)
        with open(dst_p, "w", encoding="latin1", newline="") as fp:
            fp.write(lay_content)

        return ConversionResult(
            success=True,
            source_file=str(src_p),
            target_file=str(dst_p),
            direction="onx_to_lay",
            items_count=len(layout.items),
            dies_count=len(layout.target_dies),
            width_mm=layout.ris_w,
            height_mm=layout.ris_l,
            gap_mm=layout.gap,
            material_code=layout.cod_r
        )

    except Exception as e:
        return ConversionResult(
            success=False,
            source_file=str(src_p),
            target_file=str(dst_p),
            direction="onx_to_lay",
            error_message=str(e)
        )


def convert_file(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    target_format: Optional[str] = None,
    margins_mm: Union[float, Tuple[float, float, float, float]] = 15.0,
    db=None
) -> ConversionResult:
    """
    Converte um arquivo de corte automaticamente ou conforme target_format ('lay' ou 'onx').
    """
    src_fmt = detect_file_format(input_path)

    if target_format:
        tgt_fmt = target_format.lower().lstrip(".")
    else:
        if src_fmt == "lay":
            tgt_fmt = "onx"
        elif src_fmt == "onx":
            tgt_fmt = "lay"
        else:
            return ConversionResult(
                success=False,
                source_file=str(input_path),
                target_file=str(output_path or ""),
                direction="unknown",
                error_message=f"Formato de arquivo não reconhecido para '{input_path}'. Use .lay ou .onx."
            )

    if tgt_fmt == "onx":
        return convert_lay_to_onx(input_path, output_path, margins_mm=margins_mm, db=db)
    elif tgt_fmt == "lay":
        return convert_onx_to_lay(input_path, output_path, db=db)
    else:
        return ConversionResult(
            success=False,
            source_file=str(input_path),
            target_file=str(output_path or ""),
            direction="unknown",
            error_message=f"Formato de destino inválido: '{target_format}'. Deve ser 'lay' ou 'onx'."
        )


def convert_batch(
    input_paths: List[Union[str, Path]],
    output_dir: Optional[Union[str, Path]] = None,
    target_format: Optional[str] = None,
    margins_mm: Union[float, Tuple[float, float, float, float]] = 15.0,
    db=None
) -> List[ConversionResult]:
    """
    Executa a conversão em lote de múltiplos arquivos para o diretório de destino.
    """
    results = []
    out_dir_path = Path(output_dir) if output_dir else None

    if out_dir_path:
        out_dir_path.mkdir(parents=True, exist_ok=True)

    for in_p in input_paths:
        src = Path(in_p)
        if not src.is_file():
            continue

        tgt = None
        if out_dir_path:
            det_fmt = target_format or ("onx" if detect_file_format(src) == "lay" else "lay")
            tgt = out_dir_path / src.with_suffix(f".{det_fmt}").name

        res = convert_file(
            input_path=src,
            output_path=tgt,
            target_format=target_format,
            margins_mm=margins_mm,
            db=db
        )
        results.append(res)

    return results


def main():
    """Interface CLI de linha de comando para conversão rápida de arquivos."""
    parser = argparse.ArgumentParser(description="Conversor de Layouts de Corte: ATOM (.lay) ⇄ Comelz (.onx)")
    parser.add_argument("inputs", nargs="+", help="Caminho do arquivo ou arquivos para conversão")
    parser.add_argument("-o", "--output", help="Arquivo ou pasta de destino")
    parser.add_argument("-t", "--to", choices=["lay", "onx"], help="Forçar formato de destino (lay ou onx)")
    parser.add_argument("-m", "--margin", type=float, default=15.0, help="Margem para Comelz ONX em mm (padrão 15mm)")

    args = parser.parse_args()

    input_paths = [Path(p) for p in args.inputs]

    if len(input_paths) == 1 and not (args.output and Path(args.output).is_dir()):
        out_target = Path(args.output) if args.output else None
        res = convert_file(input_paths[0], out_target, target_format=args.to, margins_mm=args.margin)
        if res.success:
            print(f"✅ Sucesso: {res.source_file} -> {res.target_file}")
            print(f"   Peças: {res.items_count} | Moldes: {res.dies_count} | Dimensões: {res.width_mm:.1f} x {res.height_mm:.1f} mm")
            sys.exit(0)
        else:
            print(f"❌ Erro ao converter {res.source_file}: {res.error_message}", file=sys.stderr)
            sys.exit(1)
    else:
        results = convert_batch(input_paths, output_dir=args.output, target_format=args.to, margins_mm=args.margin)
        successes = [r for r in results if r.success]
        print(f"Total processado: {len(results)} | Sucessos: {len(successes)} | Falhas: {len(results) - len(successes)}")
        for r in results:
            if r.success:
                print(f"  [OK] {r.source_file} -> {r.target_file} ({r.items_count} peças)")
            else:
                print(f"  [ERRO] {r.source_file}: {r.error_message}")


if __name__ == "__main__":
    main()
