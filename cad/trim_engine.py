"""
JobManager 2000 (Python Edition)
Motor de Refile Automático de Layouts (trim_engine.py)

Calcula as dimensões úteis ocupadas pelas peças encaixadas somando folga de segurança (gap_mm),
gera as linhas de corte transversal/longitudinal CAM (guilhotina) e recalcula
a eficiência de aproveitamento (Yield %) e área útil do layout.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from cad.geometry import polygon_area, polygon_bbox, transform_contour


def calculate_layout_trim_bounds(pieces: List[Dict[str, Any]], gap_mm: float = 1.0) -> Tuple[float, float]:
    """
    Calcula as dimensões mínimas necessárias (largura_x, altura_y) em milímetros
    para acomodar todas as peças posicionadas no layout respeitando a geometria
    poligonal rotacionada e somando a folga de segurança (gap_mm, padrão 1.0 mm).
    """
    if not pieces:
        return 0.0, 0.0

    max_x = 0.0
    max_y = 0.0

    for p in pieces:
        contour = p.get("contour") or (p.get("shape", {}).get("contour") if isinstance(p.get("shape"), dict) else [])
        px = float(p.get("x", 0.0))
        py = float(p.get("y", 0.0))
        rot = float(p.get("rotation", p.get("angle", p.get("rotation_deg", 0.0))))

        if contour and len(contour) >= 3:
            poly = transform_contour(contour, px, py, rot)
            _, _, p_max_x, p_max_y = polygon_bbox(poly)
            if p_max_x > max_x:
                max_x = p_max_x
            if p_max_y > max_y:
                max_y = p_max_y
        else:
            if px > max_x:
                max_x = px
            if py > max_y:
                max_y = py

    if max_x <= 0.0 and pieces:
        max_x = max(float(p.get("x", 0.0)) for p in pieces)
    if max_y <= 0.0 and pieces:
        max_y = max(float(p.get("y", 0.0)) for p in pieces)

    target_w_mm = round(max_x + float(gap_mm), 2)
    target_h_mm = round(max_y + float(gap_mm), 2)
    return target_w_mm, target_h_mm


def trim_layout_dict(
    layout_dict: Dict[str, Any],
    original_w: Optional[float] = None,
    original_h: Optional[float] = None,
    gap_mm: float = 1.0
) -> Dict[str, Any]:
    """
    Aplica o refile automático em um dicionário de layout gerado.

    - Calcula a cota máxima ocupada pelas peças + gap_mm (padrão 1.0 mm).
    - Limita as novas dimensões às dimensões originais da chapa (não expande).
    - Preserva original_sheet_width e original_sheet_height.
    - Atualiza width_mm, height_mm, ris_w, ris_l, sheet_width_mm, sheet_height_mm e area_mm2.
    - Recalcula yield_percent, yield_pct e used_area_m2 com base na nova área da chapa.
    - Gera ou atualiza o dicionário trim_cut_line com as cotas CAM de guilhotina.
    """
    if not isinstance(layout_dict, dict):
        return layout_dict

    pieces = layout_dict.get("pieces") or layout_dict.get("placed_pieces") or []
    if not pieces:
        return layout_dict

    curr_w = float(layout_dict.get("width_mm") or layout_dict.get("ris_w") or original_w or 1380.0)
    curr_h = float(layout_dict.get("height_mm") or layout_dict.get("ris_l") or original_h or 2990.0)
    orig_w = float(original_w or layout_dict.get("original_sheet_width") or curr_w)
    orig_h = float(original_h or layout_dict.get("original_sheet_height") or curr_h)

    target_w, target_h = calculate_layout_trim_bounds(pieces, gap_mm=gap_mm)
    if target_w <= 0.0 or target_h <= 0.0:
        return layout_dict

    # Não expande além da chapa original
    target_w = min(orig_w, target_w)
    target_h = min(orig_h, target_h)

    # Armazena dimensões originais para histórico e cálculo de economia
    layout_dict["original_sheet_width"] = orig_w
    layout_dict["original_sheet_height"] = orig_h

    # Atualiza dimensões úteis refiladas
    layout_dict["width_mm"] = target_w
    layout_dict["height_mm"] = target_h
    layout_dict["ris_w"] = target_w
    layout_dict["ris_l"] = target_h
    layout_dict["sheet_width_mm"] = target_w
    layout_dict["sheet_height_mm"] = target_h

    # A ponta de 2 camadas foi calculada sobre a chapa ORIGINAL; após o refile a placa
    # encolhe, e um tip_zone maior que a chapa desenhava a linha azul fora do contorno
    # (e gerava texto de almoxarifado com metragem impossível).
    if layout_dict.get("tip_zone"):
        from cad.layers_rule import clamp_tip_zone

        zona = clamp_tip_zone(layout_dict.get("tip_zone"), target_w, target_h)
        if zona:
            layout_dict["tip_zone"] = [round(v, 2) for v in zona]
        else:
            # A ponta foi totalmente cortada pelo refile: não há mais área de 2 camadas
            layout_dict.pop("tip_zone", None)
            layout_dict.pop("layers_tip", None)

    plate_area_m2 = max(1e-4, (target_w * target_h) / 1_000_000.0)
    layout_dict["area_mm2"] = round(target_w * target_h, 2)

    # Recalcula a área útil real e rendimento (Yield %) com base na nova área refilada
    total_pieces_area_mm2 = 0.0
    for p in pieces:
        contour = p.get("contour") or (p.get("shape", {}).get("contour") if isinstance(p.get("shape"), dict) else [])
        if not contour:
            continue
        px = float(p.get("x", 0.0))
        py = float(p.get("y", 0.0))
        rot = float(p.get("rotation", p.get("angle", p.get("rotation_deg", 0.0))))
        poly = transform_contour(contour, px, py, rot)
        total_pieces_area_mm2 += polygon_area(poly)

    used_m2 = total_pieces_area_mm2 / 1_000_000.0
    eff_pct = min(100.0, round((used_m2 / plate_area_m2) * 100.0, 2)) if plate_area_m2 > 0 else 0.0

    layout_dict["yield_percent"] = eff_pct
    layout_dict["yield_pct"] = eff_pct
    layout_dict["used_area_m2"] = round(used_m2, 4)

    # Gera a linha de corte CAM de acabamento (guilhotina)
    layout_dict["trim_cut_line"] = {
        "y": float(target_h),
        "x": float(target_w),
        "orig_w": float(orig_w),
        "orig_h": float(orig_h),
        "has_cut_y": (orig_h - target_h > 0.5),
        "has_cut_x": (orig_w - target_w > 0.5),
        "enabled": True,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return layout_dict
