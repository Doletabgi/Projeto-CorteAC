"""
JobManager 2000 (Python Edition)
cad/fill_engine.py - Motor Geométrico de Preenchimento Regular (Fill Row / Alternate / Column)

Implementa a cinemática industrial de repetição de moldes conforme Layout.exe original:
- Fill Row (ID 52103): Repetição horizontal contorno a contorno até a margem direita.
- Fill Row Alternate (ID 52104): Repetição horizontal alternando rotação 0° / 180° (acoplamento bico-calcanhar).
- Fill Column (ID 50007): Repetição vertical (+Y) contorno a contorno até a margem superior.

Respeita rigidamente as margens úteis da chapa e a folga mínima (gap_mm) via busca binária
submilimétrica contorno a contorno (SAT / Shapely), garantindo zero sobreposição.
"""

import copy
import math
from typing import List, Dict, Any, Tuple, Union

from cad.geometry import (
    rotate_point,
    transform_contour,
    polygon_bbox,
    polygons_collide,
    find_contact_coordinate_binary,
)
from cad.macro_engine import check_collision_against_placed


def rotate_piece_in_place_math(piece: Dict[str, Any], delta_deg: float) -> Dict[str, Any]:
    """
    Rotaciona a peça em torno do centro do bounding box do seu contorno base original,
    garantindo invariância total do centro na chapa:
      C_placa = (X, Y) + rotate_point(cx0, cy0, rot_old)
      (X_new, Y_new) = C_placa - rotate_point(cx0, cy0, rot_new)
    """
    contour = piece.get("contour")
    if not contour:
        piece["rotation"] = round((float(piece.get("rotation", 0.0)) + delta_deg) % 360.0, 6)
        return piece

    min_x, min_y, max_x, max_y = polygon_bbox(contour)
    cx0 = (min_x + max_x) / 2.0
    cy0 = (min_y + max_y) / 2.0

    current_rot = float(piece.get("rotation", 0.0))
    cx_old, cy_old = rotate_point(cx0, cy0, current_rot)
    c_plate_x = float(piece.get("x", 0.0)) + cx_old
    c_plate_y = float(piece.get("y", 0.0)) + cy_old

    new_rot = (current_rot + delta_deg) % 360.0
    if abs(new_rot - round(new_rot)) < 1e-9:
        new_rot = float(round(new_rot))
    else:
        new_rot = round(new_rot, 6)

    cx_new, cy_new = rotate_point(cx0, cy0, new_rot)
    new_x = c_plate_x - cx_new
    new_y = c_plate_y - cy_new

    if abs(new_x - round(new_x)) < 1e-9:
        new_x = float(round(new_x))
    if abs(new_y - round(new_y)) < 1e-9:
        new_y = float(round(new_y))

    piece["x"] = new_x
    piece["y"] = new_y
    piece["rotation"] = new_rot
    if "rotation_rad" in piece:
        piece["rotation_rad"] = math.radians(new_rot)
    return piece


def _parse_margins(margins: Union[Tuple[float, float, float, float], List[float], Dict[str, float]]) -> Tuple[float, float, float, float]:
    """Extrai (m_left, m_right, m_top, m_bottom)."""
    if isinstance(margins, dict):
        return (
            float(margins.get("left", 10.0)),
            float(margins.get("right", 10.0)),
            float(margins.get("top", 10.0)),
            float(margins.get("bottom", 10.0)),
        )
    if isinstance(margins, (tuple, list)) and len(margins) >= 4:
        return (float(margins[0]), float(margins[1]), float(margins[2]), float(margins[3]))
    return (10.0, 10.0, 10.0, 10.0)


def fill_row_pieces(
    target_piece: Dict[str, Any],
    placed_pieces: List[Dict[str, Any]],
    sheet_width: float,
    sheet_height: float,
    margins: Union[Tuple[float, float, float, float], List[float], Dict[str, float]] = (10.0, 10.0, 10.0, 10.0),
    gap_mm: float = 1.0,
    max_pieces: int = 300
) -> List[Dict[str, Any]]:
    """
    Clona a peça horizontalmente da sua posição em direção à margem direita da chapa (Win32 ID 52103).
    # CONFIRMAR NO WINDOWS: preenchimento a partir da peça-alvo em direção à margem direita.
    """
    contour = target_piece.get("contour", [])
    if not contour:
        return []

    m_left, m_right, m_top, m_bottom = _parse_margins(margins)
    gap = max(0.0, float(gap_mm))

    poly0 = transform_contour(
        contour,
        float(target_piece.get("x", 0.0)),
        float(target_piece.get("y", 0.0)),
        float(target_piece.get("rotation", 0.0))
    )
    bbox0 = polygon_bbox(poly0)

    target_rot = float(target_piece.get("rotation", 0.0))
    target_y = float(target_piece.get("y", 0.0))

    poly_base = transform_contour(contour, 0.0, target_y, target_rot)
    base_min_x, base_min_y, base_max_x, base_max_y = polygon_bbox(poly_base)
    cand_w = base_max_x - base_min_x

    new_pieces = []
    prev_poly = poly0
    prev_bbox = bbox0

    for _ in range(max_pieces):
        safe_start_x = prev_bbox[2] + gap + 2.0 - base_min_x
        min_cand_x = prev_bbox[0] - base_min_x

        def poly_cand_fn(x, cy=target_y, rot=target_rot):
            return transform_contour(contour, x, cy, rot)

        # Garante que na posição inicial de penetração haja colisão
        shift_count = 0
        while not polygons_collide(poly_cand_fn(min_cand_x), prev_poly, gap=gap) and shift_count < 20:
            min_cand_x -= 10.0
            shift_count += 1

        contact_x = find_contact_coordinate_binary(
            poly_cand_fn,
            [(prev_poly, prev_bbox)],
            gap=gap,
            start_val=safe_start_x,
            min_val=min_cand_x,
            iterations=14
        )

        # Valida se encontrou encosto numérico válido
        if contact_x is None:
            break

        cand_poly = poly_cand_fn(contact_x)
        cand_bbox = polygon_bbox(cand_poly)

        # Garante avanço real no eixo horizontal (+X)
        if cand_bbox[0] <= prev_bbox[0] + 0.001:
            break

        # 1. Verifica limites úteis da chapa
        if cand_bbox[2] > sheet_width - m_right:
            break
        if cand_bbox[0] < m_left or cand_bbox[1] < m_bottom or cand_bbox[3] > sheet_height - m_top:
            break

        # 2. Valida contra o vizinho anterior (garante zero colisão/sobreposição de encosto)
        if polygons_collide(cand_poly, prev_poly, gap=0.0, bbox_a=cand_bbox, bbox_b=prev_bbox):
            break

        # 3. Validação estrita de colisão com peças existentes ou já colocadas
        all_obstacles = placed_pieces + new_pieces
        if check_collision_against_placed(cand_poly, cand_bbox, all_obstacles, gap=gap):
            break

        # Instancia cópia com metadados preservados
        p_copy = dict(target_piece)
        p_copy["x"] = contact_x
        p_copy["y"] = target_y
        p_copy["rotation"] = target_rot
        p_copy["contour"] = copy.deepcopy(contour)
        for k in ("holes", "internal_cuts", "stitching"):
            if k in target_piece:
                p_copy[k] = copy.deepcopy(target_piece[k])

        new_pieces.append(p_copy)
        prev_poly = cand_poly
        prev_bbox = cand_bbox

    return new_pieces


def fill_row_alternate_pieces(
    target_piece: Dict[str, Any],
    placed_pieces: List[Dict[str, Any]],
    sheet_width: float,
    sheet_height: float,
    margins: Union[Tuple[float, float, float, float], List[float], Dict[str, float]] = (10.0, 10.0, 10.0, 10.0),
    gap_mm: float = 1.0,
    max_pieces: int = 300
) -> List[Dict[str, Any]]:
    """
    Clona a peça horizontalmente alternando rotações 0° / 180° (Win32 ID 52104).
    As cópias ímpares recebem +180° em relação à peça-alvo em torno do centro do molde,
    permitindo acoplamento milimétrico perfeito (bico com calcanhar).
    # CONFIRMAR NO WINDOWS: preenchimento a partir da peça-alvo em direção à margem direita.
    """
    contour = target_piece.get("contour", [])
    if not contour:
        return []

    m_left, m_right, m_top, m_bottom = _parse_margins(margins)
    gap = max(0.0, float(gap_mm))

    poly0 = transform_contour(
        contour,
        float(target_piece.get("x", 0.0)),
        float(target_piece.get("y", 0.0)),
        float(target_piece.get("rotation", 0.0))
    )
    bbox0 = polygon_bbox(poly0)

    # Configurações par (orientação original)
    target_rot = float(target_piece.get("rotation", 0.0))
    target_y = float(target_piece.get("y", 0.0))

    # Configurações ímpar (rotacionado 180° em torno do centro de massa/bbox)
    temp_alt = dict(target_piece)
    rotate_piece_in_place_math(temp_alt, 180.0)
    alt_y = float(temp_alt.get("y", target_y))
    alt_rot = float(temp_alt.get("rotation", (target_rot + 180.0) % 360.0))

    new_pieces = []
    prev_poly = poly0
    prev_bbox = bbox0

    for step_idx in range(1, max_pieces + 1):
        is_odd = (step_idx % 2 == 1)
        cur_y = alt_y if is_odd else target_y
        cur_rot = alt_rot if is_odd else target_rot

        poly_base = transform_contour(contour, 0.0, cur_y, cur_rot)
        base_min_x, base_min_y, base_max_x, base_max_y = polygon_bbox(poly_base)
        cand_w = base_max_x - base_min_x

        safe_start_x = prev_bbox[2] + gap + 2.0 - base_min_x
        min_cand_x = prev_bbox[0] - base_min_x

        def poly_cand_fn(x, cy=cur_y, rot=cur_rot):
            return transform_contour(contour, x, cy, rot)

        shift_count = 0
        while not polygons_collide(poly_cand_fn(min_cand_x), prev_poly, gap=gap) and shift_count < 20:
            min_cand_x -= 10.0
            shift_count += 1

        contact_x = find_contact_coordinate_binary(
            poly_cand_fn,
            [(prev_poly, prev_bbox)],
            gap=gap,
            start_val=safe_start_x,
            min_val=min_cand_x,
            iterations=14
        )

        # Valida se encontrou encosto numérico válido
        if contact_x is None:
            break

        cand_poly = poly_cand_fn(contact_x)
        cand_bbox = polygon_bbox(cand_poly)

        # Garante avanço real no eixo horizontal (+X)
        if cand_bbox[0] <= prev_bbox[0] + 0.001:
            break

        # 1. Limites úteis da chapa
        if cand_bbox[2] > sheet_width - m_right:
            break
        if cand_bbox[0] < m_left or cand_bbox[1] < m_bottom or cand_bbox[3] > sheet_height - m_top:
            break

        # 2. Valida contra o vizinho anterior (garante zero colisão/sobreposição de encosto)
        if polygons_collide(cand_poly, prev_poly, gap=0.0, bbox_a=cand_bbox, bbox_b=prev_bbox):
            break

        # 3. Verificação de colisão contra todas as peças na mesa e novas cópias
        all_obstacles = placed_pieces + new_pieces
        if check_collision_against_placed(cand_poly, cand_bbox, all_obstacles, gap=gap):
            break

        # Instancia cópia com rotação alternada
        p_copy = dict(target_piece)
        p_copy["x"] = contact_x
        p_copy["y"] = cur_y
        p_copy["rotation"] = cur_rot
        p_copy["contour"] = copy.deepcopy(contour)
        for k in ("holes", "internal_cuts", "stitching"):
            if k in target_piece:
                p_copy[k] = copy.deepcopy(target_piece[k])

        new_pieces.append(p_copy)
        prev_poly = cand_poly
        prev_bbox = cand_bbox

    return new_pieces


def fill_column_pieces(
    target_piece: Dict[str, Any],
    placed_pieces: List[Dict[str, Any]],
    sheet_width: float,
    sheet_height: float,
    margins: Union[Tuple[float, float, float, float], List[float], Dict[str, float]] = (10.0, 10.0, 10.0, 10.0),
    gap_mm: float = 1.0,
    max_pieces: int = 300
) -> List[Dict[str, Any]]:
    """
    Clona a peça verticalmente da sua posição em direção à margem superior da chapa (Win32 ID 50007).
    No plano cartesiano industrial (SetYCartesian TRUE), +Y aponta para cima.
    # CONFIRMAR NO WINDOWS: preenchimento a partir da peça-alvo em direção à margem superior (+Y).
    """
    contour = target_piece.get("contour", [])
    if not contour:
        return []

    m_left, m_right, m_top, m_bottom = _parse_margins(margins)
    gap = max(0.0, float(gap_mm))

    poly0 = transform_contour(
        contour,
        float(target_piece.get("x", 0.0)),
        float(target_piece.get("y", 0.0)),
        float(target_piece.get("rotation", 0.0))
    )
    bbox0 = polygon_bbox(poly0)

    target_rot = float(target_piece.get("rotation", 0.0))
    target_x = float(target_piece.get("x", 0.0))

    poly_base = transform_contour(contour, target_x, 0.0, target_rot)
    base_min_x, base_min_y, base_max_x, base_max_y = polygon_bbox(poly_base)
    cand_h = base_max_y - base_min_y

    new_pieces = []
    prev_poly = poly0
    prev_bbox = bbox0

    for _ in range(max_pieces):
        safe_start_y = prev_bbox[3] + gap + 2.0 - base_min_y
        min_cand_y = prev_bbox[1] - base_min_y

        def poly_cand_fn(y, cx=target_x, rot=target_rot):
            return transform_contour(contour, cx, y, rot)

        shift_count = 0
        while not polygons_collide(poly_cand_fn(min_cand_y), prev_poly, gap=gap) and shift_count < 20:
            min_cand_y -= 10.0
            shift_count += 1

        contact_y = find_contact_coordinate_binary(
            poly_cand_fn,
            [(prev_poly, prev_bbox)],
            gap=gap,
            start_val=safe_start_y,
            min_val=min_cand_y,
            iterations=14
        )

        # Valida se encontrou encosto numérico válido
        if contact_y is None:
            break

        cand_poly = poly_cand_fn(contact_y)
        cand_bbox = polygon_bbox(cand_poly)

        # Garante avanço real no eixo vertical (+Y)
        if cand_bbox[1] <= prev_bbox[1] + 0.001:
            break

        # 1. Limites úteis da chapa (margem superior e laterais)
        if cand_bbox[3] > sheet_height - m_top:
            break
        if cand_bbox[1] < m_bottom or cand_bbox[0] < m_left or cand_bbox[2] > sheet_width - m_right:
            break

        # 2. Valida contra o vizinho anterior (garante zero colisão/sobreposição de encosto)
        if polygons_collide(cand_poly, prev_poly, gap=0.0, bbox_a=cand_bbox, bbox_b=prev_bbox):
            break

        # 3. Verificação de colisão contra todas as peças na mesa e novas cópias
        all_obstacles = placed_pieces + new_pieces
        if check_collision_against_placed(cand_poly, cand_bbox, all_obstacles, gap=gap):
            break

        # Instancia cópia com metadados
        p_copy = dict(target_piece)
        p_copy["x"] = target_x
        p_copy["y"] = contact_y
        p_copy["rotation"] = target_rot
        p_copy["contour"] = copy.deepcopy(contour)
        for k in ("holes", "internal_cuts", "stitching"):
            if k in target_piece:
                p_copy[k] = copy.deepcopy(target_piece[k])

        new_pieces.append(p_copy)
        prev_poly = cand_poly
        prev_bbox = cand_bbox

    return new_pieces


def find_piece_vertical_contact_y(
    contour: List[Dict[str, float]],
    x: float,
    rot: float,
    colliders: List[Tuple[Any, Tuple[float, float, float, float]]],
    gap: float,
    min_y_limit: float
) -> float:
    """
    Encontra a coordenada Y onde a peça em (x, rot) encosta contorno a contorno
    sobre os colisores existentes sem sobreposição.
    """
    poly_base = transform_contour(contour, x, 0.0, rot)
    bmin_x, bmin_y, bmax_x, bmax_y = polygon_bbox(poly_base)
    cand_h = bmax_y - bmin_y

    relevant = [
        (c_poly, c_bbox) for c_poly, c_bbox in colliders
        if not (c_bbox[2] < bmin_x - gap or c_bbox[0] > bmax_x + gap)
    ]
    if not relevant:
        return min_y_limit - bmin_y

    max_top = max(c[1][3] for c in relevant)
    safe_start_y = max_top + gap + 5.0 - bmin_y

    def poly_cand_fn(y):
        return transform_contour(contour, x, y, rot)

    # Posição penetrante: afunda na linha inferior para garantir colisão inicial
    penetrating_y = max_top - bmin_y - min(5.0, max(1.0, cand_h / 4.0))

    shift_count = 0
    cand_poly_pen = poly_cand_fn(penetrating_y)
    cand_bbox_pen = polygon_bbox(cand_poly_pen)
    while not any(polygons_collide(cand_poly_pen, c_poly, gap=gap, bbox_a=cand_bbox_pen, bbox_b=c_bbox) for c_poly, c_bbox in relevant) and shift_count < 20:
        penetrating_y -= 5.0
        if penetrating_y < min_y_limit - bmin_y:
            penetrating_y = min_y_limit - bmin_y
            break
        cand_poly_pen = poly_cand_fn(penetrating_y)
        cand_bbox_pen = polygon_bbox(cand_poly_pen)
        shift_count += 1

    contact_y = find_contact_coordinate_binary(
        poly_cand_fn,
        relevant,
        gap=gap,
        start_val=safe_start_y,
        min_val=penetrating_y,
        iterations=14
    )
    if contact_y is None:
        contact_y = safe_start_y

    return max(contact_y, min_y_limit - bmin_y)


def find_row_vertical_contact_y(
    contour: List[Dict[str, float]],
    rot: float,
    x_positions: List[float],
    colliders: List[Tuple[Any, Tuple[float, float, float, float]]],
    gap: float,
    min_y_limit: float
) -> float:
    """
    Calcula a coordenada Y de uma nova linha horizontal calculando o encosto vertical
    contorno a contorno contra os colisores da linha inferior.
    Retorna o max(Y) necessário para que nenhuma peça da linha colida.
    """
    poly_base = transform_contour(contour, 0.0, 0.0, rot)
    bmin_x, bmin_y, bmax_x, bmax_y = polygon_bbox(poly_base)
    base_min_offset = min_y_limit - bmin_y

    if not colliders or not x_positions:
        return base_min_offset

    max_y = base_min_offset
    for x in x_positions:
        cy = find_piece_vertical_contact_y(contour, x, rot, colliders, gap, min_y_limit)
        if cy > max_y:
            max_y = cy

    return max(max_y, base_min_offset)


def fill_sheet_pieces(
    target_piece: Dict[str, Any],
    placed_pieces: List[Dict[str, Any]],
    sheet_width: float,
    sheet_height: float,
    margins: Union[Tuple[float, float, float, float], List[float], Dict[str, float]] = (10.0, 10.0, 10.0, 10.0),
    gap_mm: float = 1.0,
    max_pieces: int = 1000
) -> List[Dict[str, Any]]:
    """
    Preenche a área restante da chapa em linhas sucessivas a partir da peça-alvo (Win32 ID 52105).
    - Linha 0 (base): preenchimento horizontal a partir da peça-alvo até a margem direita.
    - Linhas subsequentes (Linha 1, 2, ...): iniciam na margem esquerda útil e são empilhadas
      verticalmente (+Y) contorno a contorno sobre a linha anterior sem colisões.
    # CONFIRMAR NO WINDOWS: preenchimento em varredura por linhas a partir da base.
    """
    contour = target_piece.get("contour", [])
    if not contour or max_pieces <= 0:
        return []

    m_left, m_right, m_top, m_bottom = _parse_margins(margins)
    gap = max(0.0, float(gap_mm))

    new_pieces: List[Dict[str, Any]] = []

    # 1. Preenche a Linha 0 à direita da peça-alvo
    row0_copies = fill_row_pieces(
        target_piece=target_piece,
        placed_pieces=placed_pieces,
        sheet_width=sheet_width,
        sheet_height=sheet_height,
        margins=margins,
        gap_mm=gap,
        max_pieces=max_pieces
    )
    new_pieces.extend(row0_copies)
    if len(new_pieces) >= max_pieces:
        return new_pieces[:max_pieces]

    target_rot = float(target_piece.get("rotation", 0.0))
    poly_base = transform_contour(contour, 0.0, 0.0, target_rot)
    base_min_x, base_min_y, base_max_x, base_max_y = polygon_bbox(poly_base)
    cand_w = base_max_x - base_min_x
    cand_h = base_max_y - base_min_y

    current_row_pieces = [target_piece] + row0_copies

    # 2. Gera linhas subsequentes empilhadas para cima (+Y)
    max_rows = 200  # Limite de segurança de linhas
    for _ in range(max_rows):
        if len(new_pieces) >= max_pieces:
            break

        all_obstacles = placed_pieces + new_pieces
        row_colliders = [
            (
                transform_contour(p.get("contour", contour), float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("rotation", 0.0))),
                polygon_bbox(transform_contour(p.get("contour", contour), float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("rotation", 0.0))))
            )
            for p in current_row_pieces
        ]

        seed_x = m_left - base_min_x
        sample_x_positions = [seed_x]
        for p in current_row_pieces:
            sample_x_positions.append(float(p.get("x", seed_x)))
        sx = seed_x
        step_sample = max(15.0, cand_w / 2.0)
        while sx < sheet_width - m_right:
            sample_x_positions.append(sx)
            sx += step_sample

        row_y = find_row_vertical_contact_y(
            contour=contour,
            rot=target_rot,
            x_positions=sample_x_positions,
            colliders=row_colliders,
            gap=gap,
            min_y_limit=m_bottom
        )

        seed_poly = transform_contour(contour, seed_x, row_y, target_rot)
        seed_bbox = polygon_bbox(seed_poly)

        if seed_bbox[3] > sheet_height - m_top:
            break

        # Se houver obstáculo no ponto inicial da margem esquerda, tenta avançar
        shift_tries = 0
        while check_collision_against_placed(seed_poly, seed_bbox, all_obstacles, gap=gap) and shift_tries < 50:
            seed_x += 10.0
            seed_poly = transform_contour(contour, seed_x, row_y, target_rot)
            seed_bbox = polygon_bbox(seed_poly)
            shift_tries += 1

        if seed_bbox[2] > sheet_width - m_right or seed_bbox[3] > sheet_height - m_top:
            break

        if check_collision_against_placed(seed_poly, seed_bbox, all_obstacles, gap=gap):
            break

        p_row_seed = dict(target_piece)
        p_row_seed["x"] = seed_x
        p_row_seed["y"] = row_y
        p_row_seed["rotation"] = target_rot
        p_row_seed["contour"] = copy.deepcopy(contour)
        for k in ("holes", "internal_cuts", "stitching"):
            if k in target_piece:
                p_row_seed[k] = copy.deepcopy(target_piece[k])

        new_pieces.append(p_row_seed)
        row_new_pieces = [p_row_seed]

        remaining_quota = max_pieces - len(new_pieces)
        if remaining_quota > 0:
            row_tail = fill_row_pieces(
                target_piece=p_row_seed,
                placed_pieces=placed_pieces + new_pieces,
                sheet_width=sheet_width,
                sheet_height=sheet_height,
                margins=margins,
                gap_mm=gap,
                max_pieces=remaining_quota
            )
            new_pieces.extend(row_tail)
            row_new_pieces.extend(row_tail)

        current_row_pieces = row_new_pieces

    return new_pieces[:max_pieces]


def fill_sheet_alternate_pieces(
    target_piece: Dict[str, Any],
    placed_pieces: List[Dict[str, Any]],
    sheet_width: float,
    sheet_height: float,
    margins: Union[Tuple[float, float, float, float], List[float], Dict[str, float]] = (10.0, 10.0, 10.0, 10.0),
    gap_mm: float = 1.0,
    max_pieces: int = 1000,
    row_phase_shift: int = 0
) -> List[Dict[str, Any]]:
    """
    Preenche toda a chapa com padrão alternado 0° / 180° por linha (Win32 ID 52106).
    Acoplamento contorno a contorno (bico-calcanhar).
    # CONFIRMAR NO WINDOWS: row_phase_shift=0 define que cada nova linha inicia com a
    # rotação idêntica à peça-alvo; se row_phase_shift=1, inverte a rotação inicial em linhas ímpares.
    """
    contour = target_piece.get("contour", [])
    if not contour or max_pieces <= 0:
        return []

    m_left, m_right, m_top, m_bottom = _parse_margins(margins)
    gap = max(0.0, float(gap_mm))

    new_pieces: List[Dict[str, Any]] = []

    # 1. Preenche a Linha 0 alternando à direita da peça-alvo
    row0_copies = fill_row_alternate_pieces(
        target_piece=target_piece,
        placed_pieces=placed_pieces,
        sheet_width=sheet_width,
        sheet_height=sheet_height,
        margins=margins,
        gap_mm=gap,
        max_pieces=max_pieces
    )
    new_pieces.extend(row0_copies)
    if len(new_pieces) >= max_pieces:
        return new_pieces[:max_pieces]

    target_rot = float(target_piece.get("rotation", 0.0))
    target_y = float(target_piece.get("y", 0.0))

    temp_alt = dict(target_piece)
    rotate_piece_in_place_math(temp_alt, 180.0)
    alt_y = float(temp_alt.get("y", target_y))
    alt_rot = float(temp_alt.get("rotation", (target_rot + 180.0) % 360.0))

    current_row_pieces = [target_piece] + row0_copies

    max_rows = 200
    for row_idx in range(1, max_rows + 1):
        if len(new_pieces) >= max_pieces:
            break

        all_obstacles = placed_pieces + new_pieces
        row_colliders = [
            (
                transform_contour(p.get("contour", contour), float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("rotation", 0.0))),
                polygon_bbox(transform_contour(p.get("contour", contour), float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("rotation", 0.0))))
            )
            for p in current_row_pieces
        ]

        # Determina a rotação inicial desta linha de acordo com row_phase_shift
        is_row_inverted = (row_phase_shift == 1 and row_idx % 2 == 1)
        cur_start_rot = alt_rot if is_row_inverted else target_rot

        poly_base = transform_contour(contour, 0.0, 0.0, cur_start_rot)
        base_min_x, base_min_y, base_max_x, base_max_y = polygon_bbox(poly_base)
        cand_w = base_max_x - base_min_x

        seed_x = m_left - base_min_x
        sample_x_positions = [seed_x]
        for p in current_row_pieces:
            sample_x_positions.append(float(p.get("x", seed_x)))
        sx = seed_x
        step_sample = max(15.0, cand_w / 2.0)
        while sx < sheet_width - m_right:
            sample_x_positions.append(sx)
            sx += step_sample

        row_y = find_row_vertical_contact_y(
            contour=contour,
            rot=cur_start_rot,
            x_positions=sample_x_positions,
            colliders=row_colliders,
            gap=gap,
            min_y_limit=m_bottom
        )

        seed_poly = transform_contour(contour, seed_x, row_y, cur_start_rot)
        seed_bbox = polygon_bbox(seed_poly)

        if seed_bbox[3] > sheet_height - m_top:
            break

        shift_tries = 0
        while check_collision_against_placed(seed_poly, seed_bbox, all_obstacles, gap=gap) and shift_tries < 50:
            seed_x += 10.0
            seed_poly = transform_contour(contour, seed_x, row_y, cur_start_rot)
            seed_bbox = polygon_bbox(seed_poly)
            shift_tries += 1

        if seed_bbox[2] > sheet_width - m_right or seed_bbox[3] > sheet_height - m_top:
            break

        if check_collision_against_placed(seed_poly, seed_bbox, all_obstacles, gap=gap):
            break

        p_row_seed = dict(target_piece)
        p_row_seed["x"] = seed_x
        p_row_seed["y"] = row_y
        p_row_seed["rotation"] = cur_start_rot
        p_row_seed["contour"] = copy.deepcopy(contour)
        for k in ("holes", "internal_cuts", "stitching"):
            if k in target_piece:
                p_row_seed[k] = copy.deepcopy(target_piece[k])

        new_pieces.append(p_row_seed)
        row_new_pieces = [p_row_seed]

        remaining_quota = max_pieces - len(new_pieces)
        if remaining_quota > 0:
            row_tail = fill_row_alternate_pieces(
                target_piece=p_row_seed,
                placed_pieces=placed_pieces + new_pieces,
                sheet_width=sheet_width,
                sheet_height=sheet_height,
                margins=margins,
                gap_mm=gap,
                max_pieces=remaining_quota
            )
            new_pieces.extend(row_tail)
            row_new_pieces.extend(row_tail)

        current_row_pieces = row_new_pieces

    return new_pieces[:max_pieces]


def fill_user_pieces(
    target_piece: Dict[str, Any],
    placed_pieces: List[Dict[str, Any]],
    sheet_width: float,
    sheet_height: float,
    constraints: Any,
    margins: Union[Tuple[float, float, float, float], List[float], Dict[str, float]] = (10.0, 10.0, 10.0, 10.0),
    base_gap_mm: float = 1.0,
    max_safety_limit: int = 1000
) -> List[Dict[str, Any]]:
    """
    Preenchimento com parâmetros e restrições customizadas do usuário (Dialog 159, Win32 ID 50003).
    Suporta passo milimétrico fixo (step_x, step_y) ou encosto automático contorno a contorno (step=0),
    limite de cópias, folga extra, alternância angular e preenchimento de chapa inteira.
    # CONFIRMAR NO WINDOWS: implementação inferida dos controles do Dialog 159.
    """
    contour = target_piece.get("contour", [])
    if not contour or max_safety_limit <= 0:
        return []

    m_left, m_right, m_top, m_bottom = _parse_margins(margins)

    extra_gap = float(getattr(constraints, "extra_gap_mm", 0.0) or 0.0)
    effective_gap = max(0.0, float(base_gap_mm) + extra_gap)

    c_max = int(getattr(constraints, "max_copies", 0) or 0)
    limit = c_max if c_max > 0 else max_safety_limit
    limit = min(limit, max_safety_limit)

    step_x = max(0.0, float(getattr(constraints, "step_x_mm", 0.0) or 0.0))
    step_y = max(0.0, float(getattr(constraints, "step_y_mm", 0.0) or 0.0))
    direction = str(getattr(constraints, "direction", "row")).lower().strip()
    alternate = bool(getattr(constraints, "alternate_rot", False))
    fill_sheet = bool(getattr(constraints, "fill_sheet", False))

    target_rot = float(target_piece.get("rotation", 0.0))
    target_x = float(target_piece.get("x", 0.0))
    target_y = float(target_piece.get("y", 0.0))

    poly_base = transform_contour(contour, 0.0, 0.0, target_rot)
    base_min_x, base_min_y, base_max_x, base_max_y = polygon_bbox(poly_base)
    cand_w = base_max_x - base_min_x
    cand_h = base_max_y - base_min_y

    # Caso 1: Preencher chapa inteira
    if fill_sheet:
        if step_x == 0.0 and step_y == 0.0:
            if alternate:
                return fill_sheet_alternate_pieces(
                    target_piece=target_piece,
                    placed_pieces=placed_pieces,
                    sheet_width=sheet_width,
                    sheet_height=sheet_height,
                    margins=margins,
                    gap_mm=effective_gap,
                    max_pieces=limit
                )
            else:
                return fill_sheet_pieces(
                    target_piece=target_piece,
                    placed_pieces=placed_pieces,
                    sheet_width=sheet_width,
                    sheet_height=sheet_height,
                    margins=margins,
                    gap_mm=effective_gap,
                    max_pieces=limit
                )
        else:
            # Preenchimento em grade com passos fixos fornecidos pelo operador
            sx = step_x if step_x > 0.0 else (cand_w + effective_gap)
            sy = step_y if step_y > 0.0 else (cand_h + effective_gap)

            new_pieces = []
            cur_y = target_y
            row_idx = 0

            temp_alt = dict(target_piece)
            rotate_piece_in_place_math(temp_alt, 180.0)
            alt_rot = float(temp_alt.get("rotation", (target_rot + 180.0) % 360.0))
            delta_y_rot = float(temp_alt.get("y", target_y)) - target_y

            while cur_y + base_max_y <= sheet_height - m_top and len(new_pieces) < limit:
                cur_x = target_x
                col_idx = 0
                while cur_x + base_max_x <= sheet_width - m_right and len(new_pieces) < limit:
                    # Não duplica a peça original
                    if row_idx != 0 or col_idx != 0:
                        is_alt = alternate and ((row_idx + col_idx) % 2 == 1)
                        p_rot = alt_rot if is_alt else target_rot
                        p_y = cur_y + (delta_y_rot if is_alt else 0.0)

                        cand_poly = transform_contour(contour, cur_x, p_y, p_rot)
                        cand_bbox = polygon_bbox(cand_poly)

                        if (cand_bbox[0] >= m_left and cand_bbox[2] <= sheet_width - m_right and
                            cand_bbox[1] >= m_bottom and cand_bbox[3] <= sheet_height - m_top):
                            all_obstacles = placed_pieces + new_pieces
                            if not check_collision_against_placed(cand_poly, cand_bbox, all_obstacles, gap=effective_gap):
                                p_copy = dict(target_piece)
                                p_copy["x"] = cur_x
                                p_copy["y"] = p_y
                                p_copy["rotation"] = p_rot
                                p_copy["contour"] = copy.deepcopy(contour)
                                for k in ("holes", "internal_cuts", "stitching"):
                                    if k in target_piece:
                                        p_copy[k] = copy.deepcopy(target_piece[k])
                                new_pieces.append(p_copy)

                    cur_x += sx
                    col_idx += 1
                cur_y += sy
                row_idx += 1
            return new_pieces[:limit]

    # Caso 2: Linha única (Row ou Column)
    if direction == "row":
        if step_x == 0.0 and step_y == 0.0:
            if alternate:
                return fill_row_alternate_pieces(
                    target_piece=target_piece,
                    placed_pieces=placed_pieces,
                    sheet_width=sheet_width,
                    sheet_height=sheet_height,
                    margins=margins,
                    gap_mm=effective_gap,
                    max_pieces=limit
                )
            else:
                return fill_row_pieces(
                    target_piece=target_piece,
                    placed_pieces=placed_pieces,
                    sheet_width=sheet_width,
                    sheet_height=sheet_height,
                    margins=margins,
                    gap_mm=effective_gap,
                    max_pieces=limit
                )
        else:
            # Passo fixo horizontal
            sx = step_x if step_x > 0.0 else (cand_w + effective_gap)
            sy = step_y

            new_pieces = []
            cur_x = target_x
            cur_y = target_y

            temp_alt = dict(target_piece)
            rotate_piece_in_place_math(temp_alt, 180.0)
            alt_rot = float(temp_alt.get("rotation", (target_rot + 180.0) % 360.0))
            delta_y_rot = float(temp_alt.get("y", target_y)) - target_y

            for step_idx in range(1, limit + 1):
                cur_x += sx
                cur_y += sy
                is_odd = (step_idx % 2 == 1)
                p_rot = alt_rot if (alternate and is_odd) else target_rot
                p_y = cur_y + (delta_y_rot if (alternate and is_odd) else 0.0)

                cand_poly = transform_contour(contour, cur_x, p_y, p_rot)
                cand_bbox = polygon_bbox(cand_poly)

                if (cand_bbox[2] > sheet_width - m_right or cand_bbox[0] < m_left or
                    cand_bbox[3] > sheet_height - m_top or cand_bbox[1] < m_bottom):
                    break

                all_obstacles = placed_pieces + new_pieces
                if check_collision_against_placed(cand_poly, cand_bbox, all_obstacles, gap=effective_gap):
                    break

                p_copy = dict(target_piece)
                p_copy["x"] = cur_x
                p_copy["y"] = p_y
                p_copy["rotation"] = p_rot
                p_copy["contour"] = copy.deepcopy(contour)
                for k in ("holes", "internal_cuts", "stitching"):
                    if k in target_piece:
                        p_copy[k] = copy.deepcopy(target_piece[k])
                new_pieces.append(p_copy)

            return new_pieces

    else:  # direction == "column"
        if step_x == 0.0 and step_y == 0.0 and not alternate:
            return fill_column_pieces(
                target_piece=target_piece,
                placed_pieces=placed_pieces,
                sheet_width=sheet_width,
                sheet_height=sheet_height,
                margins=margins,
                gap_mm=effective_gap,
                max_pieces=limit
            )
        else:
            # Passo fixo vertical
            sy = step_y if step_y > 0.0 else (cand_h + effective_gap)
            sx = step_x

            new_pieces = []
            cur_x = target_x
            cur_y = target_y

            temp_alt = dict(target_piece)
            rotate_piece_in_place_math(temp_alt, 180.0)
            alt_rot = float(temp_alt.get("rotation", (target_rot + 180.0) % 360.0))
            delta_y_rot = float(temp_alt.get("y", target_y)) - target_y

            for step_idx in range(1, limit + 1):
                cur_x += sx
                cur_y += sy
                is_odd = (step_idx % 2 == 1)
                p_rot = alt_rot if (alternate and is_odd) else target_rot
                p_y = cur_y + (delta_y_rot if (alternate and is_odd) else 0.0)

                cand_poly = transform_contour(contour, cur_x, p_y, p_rot)
                cand_bbox = polygon_bbox(cand_poly)

                if (cand_bbox[3] > sheet_height - m_top or cand_bbox[1] < m_bottom or
                    cand_bbox[2] > sheet_width - m_right or cand_bbox[0] < m_left):
                    break

                all_obstacles = placed_pieces + new_pieces
                if check_collision_against_placed(cand_poly, cand_bbox, all_obstacles, gap=effective_gap):
                    break

                p_copy = dict(target_piece)
                p_copy["x"] = cur_x
                p_copy["y"] = p_y
                p_copy["rotation"] = p_rot
                p_copy["contour"] = copy.deepcopy(contour)
                for k in ("holes", "internal_cuts", "stitching"):
                    if k in target_piece:
                        p_copy[k] = copy.deepcopy(target_piece[k])
                new_pieces.append(p_copy)

            return new_pieces

