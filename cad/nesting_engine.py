"""
JobManager 2000 (Python Edition)
Nesting Engine & ATOM Machine Cycle Estimator (Recriação de FreeNest & AtomCuttingTimeEstimator)
"""

import math
import os
import time

from cad.geometry import (
    transform_contour, polygon_area, polygon_perimeter, polygon_bbox,
    polygons_collide, bbox_overlap, simplify_contour_for_collision, prepare_segments,
    SpatialGrid, find_contact_coordinate_binary
)
from cad.colors import get_color_for_size
from cad.macro_engine import nest_ia_teste_engine, DEFAULT_IA_TESTE_MACRO
from config import ATOM_MACHINE

def parse_sequence_num(val):
    """
    Interpreta o valor da coluna Sequência como um inteiro >= 0.
    Retorna int se válido, ou None se ausente, vazio ou inválido.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        num = float(s)
        if math.isnan(num) or math.isinf(num):
            return None
        return int(num)
    except (ValueError, TypeError):
        return None


def sort_shapes_by_sequence(shapes):
    """
    Ordena os moldes respeitando estritamente a coluna 'Sequência':
    - Menor número primeiro (1, 2, 3...)
    - Empates mantêm a ordem estável original da grade/lista
    - Valores vazios, ausentes ou inválidos vão para o final em ordem estável
    Retorna: (sorted_shapes, missing_seq_shape_names)
    """
    if not shapes:
        return [], []

    missing_names = []
    indexed = []
    for idx, s in enumerate(shapes):
        seq = parse_sequence_num(s.get("sequence"))
        if seq is None:
            name = str(s.get("name") or s.get("id") or f"Molde #{idx+1}")
            missing_names.append(name)
            key = (1, 999999999, idx)
        else:
            key = (0, seq, idx)
        indexed.append((key, s))

    indexed.sort(key=lambda item: item[0])
    sorted_shapes = [item[1] for item in indexed]
    return sorted_shapes, missing_names

_PAIRED_OFFSET_CACHE = {}

def get_paired_offset_cached(shape, gap=1.0):
    """
    Calcula e armazena em cache o deslocamento relativo ótimo (dx, dy)
    para acoplamento de par geminado (0° e 180° / macho-fêmea).
    """
    contour = shape.get("contour", [])
    if not contour:
        return (0.0, 0.0)
    shape_id = shape.get("id") or shape.get("name") or str(len(contour))
    cache_key = (shape_id, round(float(gap), 2))
    if cache_key in _PAIRED_OFFSET_CACHE:
        return _PAIRED_OFFSET_CACHE[cache_key]

    p1 = transform_contour(contour, 0, 0, 0.0)
    b1 = polygon_bbox(p1)
    p2 = transform_contour(contour, 0, 0, 180.0)
    b2 = polygon_bbox(p2)

    best_dx = b1[2] + gap - b2[0]
    best_dy = b1[1] - b2[1]

    for step_x in range(int(best_dx), int(b1[0] - (b2[2] - b2[0])), -2):
        test_p = transform_contour(contour, step_x - b2[0], best_dy - b2[1], 180.0)
        test_b = polygon_bbox(test_p)
        if not polygons_collide(p1, test_p, gap=gap, bbox_a=b1, bbox_b=test_b):
            best_dx = float(step_x)
        else:
            break

    offset = (best_dx, best_dy)
    _PAIRED_OFFSET_CACHE[cache_key] = offset
    return offset

def try_hole_filling_placement(shape, grid, bed_width, max_y, gap, rot=0.0):
    """
    Tenta posicionar um molde menor em vazios/espaços internos deixados
    nas linhas inferiores da mesa antes de avançar a altura máxima.
    """
    contour = shape.get("contour", [])
    if not contour:
        return None
    poly_0 = transform_contour(contour, 0, 0, rot)
    min_x, min_y, max_x, max_y_p = polygon_bbox(poly_0)
    w = max_x - min_x
    h = max_y_p - min_y

    step_x = max(25.0, w * 0.5)
    step_y = max(25.0, h * 0.5)

    x = 15.0
    while x + w <= bed_width - 15.0:
        y = 15.0
        while y + h <= max_y - gap:
            cand_bbox = (x, y, x + w, y + h)
            colliders = grid.query_potential_colliders(cand_bbox, gap=gap)
            cand_poly = transform_contour(contour, x - min_x, y - min_y, rot)
            if not any(polygons_collide(cand_poly, cp, gap=gap, bbox_a=cand_bbox, bbox_b=cb) for cp, cb in colliders):
                return (x - min_x, y - min_y, rot, cand_poly, cand_bbox)
            y += step_y
        x += step_x
    return None


def check_collision_against_placed(c_poly, c_bbox, placed_items, gap=0.0):
    """
    Garante que JAMAIS uma peça fique sobreposta a outra na mesa de corte.
    Verifica interseção e respeito à folga de corte (gap) contra todas as peças já posicionadas.
    """
    for p_poly, p_bbox in placed_items:
        if polygons_collide(c_poly, p_poly, gap=gap, bbox_a=c_bbox, bbox_b=p_bbox):
            return True
    return False

def calculate_yield(placed_pieces, bed_area_m2):
    """
    Calcula o rendimento (Yield) percentual da mesa de corte:
    Yield % = (Área útil das peças / Área total do material) * 100
    """
    if bed_area_m2 <= 0 or not placed_pieces:
        return 0.0, 0.0

    total_pieces_area_mm2 = 0.0
    for p in placed_pieces:
        contour = p.get("contour") or (p.get("shape", {}).get("contour") if isinstance(p.get("shape"), dict) else [])
        if not contour:
            continue
        rot = float(p.get("rotation", p.get("angle", 0.0)))
        poly = transform_contour(contour, float(p.get("x", 0.0)), float(p.get("y", 0.0)), rot)
        total_pieces_area_mm2 += polygon_area(poly)

    total_pieces_area_m2 = total_pieces_area_mm2 / 1_000_000.0
    yield_percent = (total_pieces_area_m2 / bed_area_m2) * 100.0
    return min(yield_percent, 100.0), total_pieces_area_m2

def calculate_atom_cutting_time(placed_pieces, machine=ATOM_MACHINE):
    """
    Calcula a estimativa de tempo de corte para cabeçote CNC da ATOM.
    Baseado no comprimento total de corte, velocidade nominal da lâmina (650 mm/s),
    deslocamento rápido (G00) e tempo por furação (punch delay).
    """
    if not placed_pieces:
        return 0.0, 0.0

    total_cut_length_mm = 0.0
    total_holes_count = 0

    for p in placed_pieces:
        contour = p.get("contour") or (p.get("shape", {}).get("contour") if isinstance(p.get("shape"), dict) else [])
        if not contour:
            continue
        rot = float(p.get("rotation", p.get("angle", 0.0)))
        poly = transform_contour(contour, float(p.get("x", 0.0)), float(p.get("y", 0.0)), rot)
        total_cut_length_mm += polygon_perimeter(poly)
        holes = p.get("holes") or (p.get("shape", {}).get("holes") if isinstance(p.get("shape"), dict) else []) or []
        total_holes_count += len(holes)

    cut_time_sec = total_cut_length_mm / machine["blade_speed_mm_s"]
    rapid_travel_sec = (total_cut_length_mm * 0.35) / machine["rapid_speed_mm_s"]
    punch_time_sec = total_holes_count * machine["punch_delay_s"]

    total_time_sec = cut_time_sec + rapid_travel_sec + punch_time_sec
    return total_time_sec, total_cut_length_mm

def parse_coupling_angles(coupling_str):
    """
    Interpreta a string de acoplamento angular do DieProc.
    Exemplos:
    - '0/0 0/180' -> [0.0, 180.0]
    - '0/0' -> [0.0]
    - '180/180' -> [180.0]
    - '0/90' -> [0.0, 90.0]
    - '0/0 0/90 0/180 0/270' -> [0.0, 90.0, 180.0, 270.0]
    """
    if not coupling_str:
        return [0.0, 180.0]
    tokens = str(coupling_str).strip().split()
    angles = []
    for t in tokens:
        if "/" in t:
            parts = t.split("/")
            for p in parts:
                try:
                    angles.append(float(p))
                except ValueError:
                    pass
        else:
            try:
                angles.append(float(t))
            except ValueError:
                pass
    if not angles:
        return [0.0, 180.0]
    return list(dict.fromkeys(angles))

def dieproc_nest_pieces(available_shapes, bed_width_mm, bed_height_mm, target_count=16, dieproc_params=None, is_roll=False, margins=None, layers=None):
    """
    Motor de referência para corte contínuo de sintéticos (ATOM DieProc dp98).
    Projetado para chapas e placas sintéticas (flashnestsheet).
    Aplica acoplamento de rotação (coupling), varredura de tolerância angular (range sweep),
    intertravamento entre linhas (row interlock) e controle de gap milimétrico.
    """
    placed = []
    if not available_shapes:
        return placed

    params = dieproc_params or {}
    coupling = params.get("coupling", "0/0 0/180")
    base_angles = parse_coupling_angles(coupling)
    step = float(params.get("step", 1.0) or 1.0)
    solutions = int(params.get("solutions", 30) or 30)
    r1_from = float(params.get("range1_from", -3.0))
    r1_to = float(params.get("range1_to", 3.0))
    r1_step = float(params.get("range1_step", 1.0) or 1.0)
    gap = max(0.0, float(params.get("gap1", 1.0) if params.get("gap1") is not None else 1.0))
    row_interlock = bool(params.get("row_interlock", True))
    diagonal = bool(params.get("diagonal", False))

    # Otimização fina de ângulo no Range 1 (busca de melhor tolerância)
    best_delta = 0.0
    if r1_step > 0 and r1_to >= r1_from:
        candidate_deltas = []
        d = r1_from
        while d <= r1_to + 1e-4:
            candidate_deltas.append(d)
            d += r1_step

        best_area = float("inf")
        test_shape = available_shapes[0]
        for delta in candidate_deltas:
            tot_w, tot_h = 0.0, 0.0
            for a in base_angles:
                poly = transform_contour(test_shape["contour"], 0, 0, a + delta)
                min_x, min_y, max_x, max_y = polygon_bbox(poly)
                tot_w += (max_x - min_x)
                tot_h = max(tot_h, max_y - min_y)
            approx_area = tot_w * tot_h
            if approx_area < best_area:
                best_area = approx_area
                best_delta = delta

    effective_angles = [(a + best_delta) % 360.0 for a in base_angles]

    if margins is None and params and "margins" in params:
        margins = params["margins"]
    m_left = float(margins.get("left", 10.0)) if margins else 10.0
    m_right = float(margins.get("right", 10.0)) if margins else 10.0
    m_top = float(margins.get("top", 10.0)) if margins else 10.0
    m_bottom = float(margins.get("bottom", 10.0)) if margins else 10.0

    usable_width = max(10.0, bed_width_mm - m_left - m_right)
    usable_height = max(10.0, bed_height_mm - m_bottom - m_top)

    # Ordena os moldes pela sequência de geração configurada
    sorted_shapes, _ = sort_shapes_by_sequence(available_shapes)

    # Fila de peças a cortar respeitando pares e camadas (1 par = 2 peças físicas).
    # Se o corte for realizado com múltiplas camadas (layers), cada corte na mesa gera 'layers' peças físicas.
    # Quantidade de peças necessárias no layout (.lay) = ceil((pares * 2) / layers).
    # Ex: para 2 camadas, ceil((20 * 2) / 2) = 20 peças de cada número no layout.
    shape_queue = []
    for s in sorted_shapes:
        if "target_pieces" in s:
            qty = max(0, int(s["target_pieces"]))
        else:
            s_layers = layers or s.get("layers") or (params.get("layers") if isinstance(params, dict) else None) or 2
            try:
                s_layers = max(1, int(s_layers))
            except (ValueError, TypeError):
                s_layers = 2
            qty = math.ceil((int(s.get("pairs", 24)) * 2) / s_layers)
        for _ in range(qty):
            shape_queue.append(s)

    if not shape_queue:
        shape_queue = list(sorted_shapes)

    idx = 1

    # Disposição Rolo (descontinuada - fábrica opera com chapas/placas)
    if is_roll:
        cur_x = margin
        cur_y = margin
        col_width = 0.0
        row_in_col = 0
        grid = SpatialGrid(cell_size=100.0)

        while idx <= target_count:
            shape = shape_queue[(idx - 1) % len(shape_queue)]
            rot = effective_angles[(idx - 1) % len(effective_angles)]

            poly = transform_contour(shape["contour"], 0, 0, rot)
            min_x, min_y, max_x, max_y = polygon_bbox(poly)
            w = max_x - min_x
            h = max_y - min_y

            y_offset = (h * 0.4) if (row_interlock and (row_in_col % 2 == 1)) else 0.0
            place_y = cur_y + y_offset

            if place_y + h > bed_height_mm - margin:
                cur_x += col_width + gap
                cur_y = margin
                col_width = 0.0
                row_in_col = 0
                place_y = cur_y
                if cur_x + w > bed_width_mm - margin:
                    break

            trial_x = cur_x
            trial_y = place_y
            poly_fn = lambda y, tx=trial_x: transform_contour(shape["contour"], tx - min_x, y - min_y, rot)

            query_bbox = (trial_x - gap, max(0.0, trial_y - gap * 2.0), trial_x + w + gap, bed_height_mm)
            colliders = grid.query_potential_colliders(query_bbox, gap=gap)
            if colliders:
                max_c_y = max(cb[3] for _, cb in colliders)
                start_val = max(trial_y, max_c_y + gap)
                trial_y = find_contact_coordinate_binary(poly_fn, colliders, gap, start_val, trial_y)

            c_poly = poly_fn(trial_y)
            c_bbox = polygon_bbox(c_poly)

            # Se excedeu a altura do rolo na coluna atual, tenta avançar para a próxima coluna
            if trial_y + h > bed_height_mm - margin or any(polygons_collide(c_poly, cp, gap=gap, bbox_a=c_bbox, bbox_b=cb) for cp, cb in colliders):
                cur_x += col_width + gap
                cur_y = margin
                col_width = 0.0
                row_in_col = 0
                trial_x = cur_x
                trial_y = cur_y
                if trial_x + w > bed_width_mm - margin:
                    break
                poly_fn = lambda y, tx=trial_x: transform_contour(shape["contour"], tx - min_x, y - min_y, rot)
                query_bbox = (trial_x - gap, max(0.0, trial_y - gap * 2.0), trial_x + w + gap, bed_height_mm)
                colliders = grid.query_potential_colliders(query_bbox, gap=gap)
                if colliders:
                    max_c_y = max(cb[3] for _, cb in colliders)
                    start_val = max(trial_y, max_c_y + gap)
                    trial_y = find_contact_coordinate_binary(poly_fn, colliders, gap, start_val, trial_y)
                c_poly = poly_fn(trial_y)
                c_bbox = polygon_bbox(c_poly)
                if trial_y + h > bed_height_mm - margin or any(polygons_collide(c_poly, cp, gap=gap, bbox_a=c_bbox, bbox_b=cb) for cp, cb in colliders):
                    break

            s_sz = str(shape.get("size") or shape.get("taglia") or "41")
            p_color = get_color_for_size(s_sz, idx)
            piece = {
                "id": idx,
                "shape": shape,
                "name": shape.get("name", "Molde"),
                "size": str(shape.get("size", "41")),
                "color": p_color,
                "contour": shape.get("contour", []),
                "x": trial_x - min_x,
                "y": trial_y - min_y,
                "rotation": rot
            }
            placed.append(piece)
            grid.insert(idx, c_poly, c_bbox)
            idx += 1
            row_in_col += 1

            cur_y = trial_y + h + gap
            if w > col_width:
                col_width = w

        return placed

    # Disposição 2: Chapa Retangular / Sheets (flashnestsheet & freenest)
    else:
        sample_poly = transform_contour(shape_queue[0]["contour"], 0, 0, effective_angles[0])
        s_min_x, s_min_y, s_max_x, s_max_y = polygon_bbox(sample_poly)
        avg_w = max(10.0, s_max_x - s_min_x)
        avg_h = max(10.0, s_max_y - s_min_y)

        is_alternating = (len(base_angles) == 2 and abs(abs(base_angles[0] - base_angles[1]) - 180.0) < 1e-3) or coupling == "0/0 0/180"

        cur_row_y = m_bottom
        row_idx = 0
        grid = SpatialGrid(cell_size=100.0)
        rows = []
        queue_idx = 0
        cancel_check = dieproc_params.get("cancel_check") if isinstance(dieproc_params, dict) else None
        try:
            sheet_timeout_sec = float(dieproc_params.get("sheet_timeout_sec") or 0) if isinstance(dieproc_params, dict) else 0.0
        except (TypeError, ValueError):
            sheet_timeout_sec = 0.0
        t_sheet_start = time.perf_counter()

        while queue_idx < len(shape_queue) and cur_row_y < bed_height_mm - m_top and len(placed) < target_count:
            if cancel_check is not None and cancel_check():
                break
            if sheet_timeout_sec > 0 and (time.perf_counter() - t_sheet_start) > sheet_timeout_sec:
                break
            row_pieces = []
            is_odd_row = (row_idx % 2 == 1)

            # Preenchimento horizontal da linha com encosto milimétrico contorno a contorno
            while queue_idx < len(shape_queue) and (len(placed) + len(row_pieces)) < target_count:
                if cancel_check is not None and cancel_check():
                    break
                if sheet_timeout_sec > 0 and (time.perf_counter() - t_sheet_start) > sheet_timeout_sec:
                    break
                shape = shape_queue[queue_idx]
                piece_in_row_idx = len(row_pieces)

                if is_alternating:
                    rot = 180.0 if ((piece_in_row_idx % 2 == 1) ^ is_odd_row) else 0.0
                else:
                    angle_idx = (piece_in_row_idx + (row_idx if row_interlock else 0)) % len(effective_angles)
                    rot = effective_angles[angle_idx]

                poly0 = transform_contour(shape["contour"], 0, 0, rot)
                min_x, min_y, max_x, max_y = polygon_bbox(poly0)
                w = max_x - min_x
                h = max_y - min_y

                if not row_pieces:
                    cand_x = m_left
                else:
                    prev = row_pieces[-1]
                    safe_start_x = prev["bbox"][2] + gap + 1.0
                    min_cand_x = max(m_left, prev["bbox"][0] - 25.0)
                    # Pré-filtro exato: durante a busca a peça só ocupa a janela
                    # [min_cand_x + min_x, safe_start_x + max_x]; peças da linha fora
                    # dessa janela (ou de outra faixa Y) não podem colidir.
                    win_x_min = min_cand_x + min_x
                    win_x_max = safe_start_x + max_x
                    win_y_min = cur_row_y
                    win_y_max = cur_row_y + h
                    colliders_row = [
                        (p["poly"], p["bbox"], p.get("_segs"))
                        for p in row_pieces
                        if p["bbox"][2] + gap >= win_x_min
                        and p["bbox"][0] - gap <= win_x_max
                        and p["bbox"][3] + gap >= win_y_min
                        and p["bbox"][1] - gap <= win_y_max
                    ]
                    poly_fn_x = lambda x, s=shape, mx=min_x, my=min_y, r=rot, cy=cur_row_y: transform_contour(s["contour"], x - mx, cy - my, r)
                    cand_x = find_contact_coordinate_binary(poly_fn_x, colliders_row, gap, start_val=safe_start_x, min_val=min_cand_x)

                if cand_x + w > bed_width_mm - m_right:
                    break

                c_poly = transform_contour(shape["contour"], cand_x - min_x, cur_row_y - min_y, rot)
                c_bbox = polygon_bbox(c_poly)

                size_str = str(shape.get("size") or shape.get("taglia") or "41")
                p_color = get_color_for_size(size_str, idx)
                item = {
                    "id": idx,
                    "shape": shape,
                    "name": shape.get("name", "Molde"),
                    "size": size_str,
                    "color": p_color,
                    "contour": shape.get("contour", []),
                    "x": cand_x - min_x,
                    "y": cur_row_y - min_y,
                    "rotation": rot,
                    "poly": c_poly,
                    "bbox": c_bbox,
                    "row": row_idx,
                    "min_x": min_x,
                    "min_y": min_y,
                    "w": w,
                    "h": h
                }
                item["_segs"] = prepare_segments(c_poly)
                row_pieces.append(item)
                queue_idx += 1
                idx += 1

            if not row_pieces:
                break

            # Rebaixamento da LINHA INTEIRA como corpo rígido (Row Interlock)
            if rows and row_interlock:
                prev_row = rows[-1]
                prev_max_y = max(p["bbox"][3] for p in prev_row)
                high_y = prev_max_y + gap
                low_y = prev_max_y - avg_h * 0.40

                def row_collides_at(test_y):
                    dy = test_y - cur_row_y
                    for p in row_pieces:
                        test_poly = transform_contour(p["shape"]["contour"], p["x"], p["y"] + dy, p["rotation"])
                        test_bbox = polygon_bbox(test_poly)
                        cols = grid.query_potential_colliders(test_bbox, gap=gap)
                        if any(polygons_collide(test_poly, cp, gap=gap, bbox_a=test_bbox, bbox_b=cb) for cp, cb in cols):
                            return True
                    return False

                for _ in range(10):
                    mid_y = (low_y + high_y) / 2.0
                    if row_collides_at(mid_y):
                        low_y = mid_y
                    else:
                        high_y = mid_y

                target_y = high_y + 0.05
                while row_collides_at(target_y):
                    target_y += 0.2

                delta_y = target_y - cur_row_y
                cur_row_y = target_y
                for p in row_pieces:
                    p["y"] += delta_y
                    p["poly"] = transform_contour(p["shape"]["contour"], p["x"], p["y"], p["rotation"])
                    p["bbox"] = polygon_bbox(p["poly"])
            elif rows and not row_interlock:
                prev_row = rows[-1]
                prev_max_y = max(p["bbox"][3] for p in prev_row)
                target_y = prev_max_y + gap
                delta_y = target_y - cur_row_y
                cur_row_y = target_y
                for p in row_pieces:
                    p["y"] += delta_y
                    p["poly"] = transform_contour(p["shape"]["contour"], p["x"], p["y"], p["rotation"])
                    p["bbox"] = polygon_bbox(p["poly"])

            # Verificação estrita da margem do topo da chapa
            if any(p["bbox"][3] > bed_height_mm - m_top for p in row_pieces):
                break

            for p in row_pieces:
                grid.insert(p["id"], p["poly"], p["bbox"])
                # Segmentos pré-computados servem só durante a montagem da linha;
                # removê-los evita inchar o JSON persistido no banco.
                p.pop("_segs", None)
                placed.append(p)
            rows.append(row_pieces)
            row_idx += 1

        return placed


def nest_synthetic_engine(available_shapes, bed_width_mm, bed_height_mm, target_count=16, gap_mm=1.0, is_roll=False, margins=None, layers=None):
    """
    Motor 'Sint': Otimização para corte contínuo de materiais sintéticos em rolos ou chapas.
    Características:
    - Geminação de pares (acoplamento 0° e 180° / macho-fêmea com encaixe contorno a contorno).
    - Deslocamento de contato milimétrico estrito (gap exato de 1.0mm sem desperdício de bounding box).
    - Intertravamento de colmeia com defasagem horizontal entre linhas (Row Shifting).
    - Janela de avanço contínuo respeitando largura útil e margem.
    - Zero colisão estrita e respeito ao gap milimétrico.
    """
    placed = []
    if not available_shapes:
        return placed

    sorted_shapes, _ = sort_shapes_by_sequence(available_shapes)
    shape_queue = []
    for s_item in sorted_shapes:
        if "target_pieces" in s_item:
            qty = max(0, int(s_item["target_pieces"]))
        else:
            s_layers = layers or s_item.get("layers") or 2
            try:
                s_layers = max(1, int(s_layers))
            except (ValueError, TypeError):
                s_layers = 2
            qty = math.ceil((int(s_item.get("pairs", 24)) * 2) / s_layers)
        for _ in range(qty):
            shape_queue.append(s_item)
    if not shape_queue:
        shape_queue = list(sorted_shapes)

    max_pieces = target_count if (target_count and target_count > 0) else len(shape_queue)
    m_left = float(margins.get("left", 10.0)) if margins else 10.0
    m_right = float(margins.get("right", 10.0)) if margins else 10.0
    m_top = float(margins.get("top", 10.0)) if margins else 10.0
    m_bottom = float(margins.get("bottom", 10.0)) if margins else 10.0
    gap = max(0.0, float(gap_mm))

    grid = SpatialGrid(cell_size=100.0)

    sample_poly = transform_contour(shape_queue[0]["contour"], 0, 0, 0.0)
    s_min_x, s_min_y, s_max_x, s_max_y = polygon_bbox(sample_poly)
    avg_w = max(10.0, s_max_x - s_min_x)
    avg_h = max(10.0, s_max_y - s_min_y)

    row_idx = 0
    cur_row_y = m_bottom
    idx = 1
    rows = []

    while idx <= max_pieces and (cur_row_y < bed_height_mm - m_top):
        is_odd_row = (row_idx % 2 == 1)
        interlock_offset = (avg_w * 0.40) if is_odd_row else 0.0

        row_pieces = []
        cur_x = m_left + interlock_offset

        while idx <= max_pieces:
            shape = shape_queue[(idx - 1) % len(shape_queue)]
            rot = 180.0 if ((idx % 2 == 0) ^ is_odd_row) else 0.0
            poly0 = transform_contour(shape["contour"], 0, 0, rot)
            min_x, min_y, max_x, max_y = polygon_bbox(poly0)
            w = max_x - min_x
            h = max_y - min_y

            if not row_pieces:
                cand_x = cur_x
            else:
                prev = row_pieces[-1]
                safe_x = prev["bbox"][2] + gap
                min_x_cand = max(m_left, prev["bbox"][0])
                poly_fn_x = lambda x: transform_contour(shape["contour"], x - min_x, cur_row_y - min_y, rot)
                cand_x = find_contact_coordinate_binary(poly_fn_x, [(prev["poly"], prev["bbox"])], gap, start_val=safe_x, min_val=min_x_cand)

            if cand_x + w > bed_width_mm - m_right:
                break

            c_poly = transform_contour(shape["contour"], cand_x - min_x, cur_row_y - min_y, rot)
            c_bbox = polygon_bbox(c_poly)
            p_color = get_color_for_size(shape.get("size") or shape.get("name") or "41", idx)
            item = {
                "id": idx,
                "shape": shape,
                "name": shape.get("name", "Molde"),
                "size": str(shape.get("size", "41")),
                "color": p_color,
                "contour": shape.get("contour", []),
                "x": cand_x - min_x,
                "y": cur_row_y - min_y,
                "rotation": rot,
                "poly": c_poly,
                "bbox": c_bbox,
                "row": row_idx,
                "min_x": min_x,
                "min_y": min_y,
                "w": w,
                "h": h
            }
            row_pieces.append(item)
            idx += 1

        if not row_pieces:
            break

        # Posicionamento vertical otimizado contra linhas anteriores
        if row_idx > 0:
            def row_collides(test_y):
                for p in row_pieces:
                    test_poly = transform_contour(p["shape"]["contour"], p["x"], test_y - p["min_y"], p["rotation"])
                    test_bbox = polygon_bbox(test_poly)
                    cols = grid.query_potential_colliders(test_bbox, gap=gap)
                    if any(polygons_collide(test_poly, cp, gap=gap, bbox_a=test_bbox, bbox_b=cb) for cp, cb in cols):
                        return True
                return False

            prev_row = rows[-1]
            prev_max_y = max(p["bbox"][3] for p in prev_row)
            high_y = prev_max_y + gap
            low_y = prev_max_y - avg_h * 0.35

            for _ in range(12):
                mid_y = (low_y + high_y) / 2.0
                if row_collides(mid_y):
                    low_y = mid_y
                else:
                    high_y = mid_y
            cur_row_y = high_y + 0.05
            while row_collides(cur_row_y):
                cur_row_y += 0.2

            for p in row_pieces:
                p["y"] = cur_row_y - p["min_y"]
                p["poly"] = transform_contour(p["shape"]["contour"], p["x"], p["y"], p["rotation"])
                p["bbox"] = polygon_bbox(p["poly"])

        if not is_roll and any(p["bbox"][3] > bed_height_mm - m_top for p in row_pieces):
            break

        for p in row_pieces:
            grid.insert(p["id"], p["poly"], p["bbox"])
            placed.append(p)
        rows.append(row_pieces)

        row_idx += 1
        cur_row_y += avg_h * 0.70

    return placed

def nest_tape_engine(available_shapes, bed_width_mm, bed_height_mm, target_count=16, gap_mm=1.0, margins=None, layers=None):
    """
    Motor 'Tape A': Otimização linear para fitas, tiras estreitas, debruns, vivos e correias.
    Características:
    - Alinhamento longitudinal ao longo do eixo da fita (sentido de tração mecânica).
    - Rotação fixada em 0° (ou alternância 0°/180° para tiras curvas em zigue-zague).
    - Passo linear compacto (Step packing) com corte contínuo.
    - Otimização para faixas estreitas com mínimo desperdício de aparas.
    - Zero colisão estrita.
    """
    placed = []
    if not available_shapes:
        return placed

    sorted_shapes, _ = sort_shapes_by_sequence(available_shapes)
    shape_queue = []
    for s in sorted_shapes:
        if "target_pieces" in s:
            qty = max(0, int(s["target_pieces"]))
        else:
            s_layers = layers or s.get("layers") or 2
            try:
                s_layers = max(1, int(s_layers))
            except (ValueError, TypeError):
                s_layers = 2
            qty = math.ceil((int(s.get("pairs", 24)) * 2) / s_layers)
        for _ in range(qty):
            shape_queue.append(s)
    if not shape_queue:
        shape_queue = list(sorted_shapes)

    max_pieces = target_count if (target_count and target_count > 0) else len(shape_queue)

    m_left = float(margins.get("left", 10.0)) if margins else 10.0
    m_right = float(margins.get("right", 10.0)) if margins else 10.0
    m_top = float(margins.get("top", 10.0)) if margins else 10.0
    m_bottom = float(margins.get("bottom", 10.0)) if margins else 10.0
    gap = max(0.5, float(gap_mm))

    cur_x = m_left
    row_baseline_y = m_bottom
    row_height = 0.0
    row_idx = 0
    idx = 1
    grid = SpatialGrid(cell_size=100.0)

    for i in range(max_pieces):
        shape = shape_queue[i % len(shape_queue)]

        rot = 0.0 if (i % 2 == 0) else 180.0

        poly = transform_contour(shape["contour"], 0, 0, rot)
        min_x, min_y, max_x, max_y = polygon_bbox(poly)
        w = max_x - min_x
        h = max_y - min_y

        # Se a peça estiver na vertical, gira 90° para alinhar com o comprimento da fita
        if h > w * 1.3:
            rot = (rot + 90.0) % 360.0
            poly = transform_contour(shape["contour"], 0, 0, rot)
            min_x, min_y, max_x, max_y = polygon_bbox(poly)
            w = max_x - min_x
            h = max_y - min_y

        if cur_x + w > bed_width_mm - m_right:
            row_idx += 1
            cur_x = m_left
            row_baseline_y += (row_height + gap)
            row_height = 0.0

        trial_y = max(m_bottom, row_baseline_y)
        poly_fn = lambda y, cx=cur_x: transform_contour(shape["contour"], cx - min_x, y - min_y, rot)
        query_bbox = (cur_x - gap, max(0.0, trial_y - gap * 2.0), cur_x + w + gap, bed_height_mm)
        colliders = grid.query_potential_colliders(query_bbox, gap=gap)

        if colliders:
            max_c_y = max(cb[3] for _, cb in colliders)
            start_val = max(trial_y, max_c_y + gap)
            trial_y = find_contact_coordinate_binary(poly_fn, colliders, gap, start_val, trial_y)

        c_poly = poly_fn(trial_y)
        c_bbox = polygon_bbox(c_poly)

        if trial_y + h > bed_height_mm - m_top or any(polygons_collide(c_poly, cp, gap=gap, bbox_a=c_bbox, bbox_b=cb) for cp, cb in colliders):
            break

        p_color = get_color_for_size(shape.get("size") or shape.get("name") or "41", idx)
        piece = {
            "id": idx,
            "shape": shape,
            "name": shape.get("name", "Molde"),
            "size": str(shape.get("size", "41")),
            "color": p_color,
            "contour": shape.get("contour", []),
            "x": cur_x - min_x,
            "y": trial_y - min_y,
            "rotation": rot
        }
        placed.append(piece)
        grid.insert(idx, c_poly, c_bbox)
        idx += 1


        cur_x += (w + gap)
        if (trial_y - row_baseline_y + h) > row_height:
            row_height = trial_y - row_baseline_y + h

    return placed

def auto_nest_pieces(available_shapes, bed_width_mm, bed_height_mm, target_count=16, strategy="flashnestsheet", params="stdNOTFill", gap_mm=1.0, dieproc_params=None, db=None, margins=None, layers=None):
    """
    Ponto de entrada público do aninhamento de chapa.
    Delega ao backend configurado (CORTEAC_BACKEND="python" por padrão).
    """
    import os
    if os.getenv("CORTEAC_BACKEND", "python").strip().lower() != "nfp":
        return _auto_nest_pieces_core(
            available_shapes=available_shapes,
            bed_width_mm=bed_width_mm,
            bed_height_mm=bed_height_mm,
            target_count=target_count,
            strategy=strategy,
            params=params,
            gap_mm=gap_mm,
            dieproc_params=dieproc_params,
            db=db,
            margins=margins,
            layers=layers,
        )

    from cad.nesting_backend import get_nesting_backend
    backend = get_nesting_backend("nfp")
    return backend.nest_sheet(
        available_shapes=available_shapes,
        bed_width_mm=bed_width_mm,
        bed_height_mm=bed_height_mm,
        target_count=target_count,
        strategy=strategy,
        params=params,
        gap_mm=gap_mm,
        dieproc_params=dieproc_params,
        db=db,
        margins=margins,
        layers=layers,
    )

def _auto_nest_pieces_core(available_shapes, bed_width_mm, bed_height_mm, target_count=16, strategy="flashnestsheet", params="stdNOTFill", gap_mm=1.0, dieproc_params=None, db=None, margins=None, layers=None):
    """
    Algoritmo de aninhamento automático 2D de referência (código legado padrão).
    """
    placed = []
    if not available_shapes:
        return placed

    if margins is None and dieproc_params and isinstance(dieproc_params, dict) and "margins" in dieproc_params:
        margins = dieproc_params["margins"]

    # 0. Estratégia IA-teste (Macros Declarativas + IA Local Embarcada 100% Nativa)
    if str(strategy).lower() in ("ia-teste", "ia_teste", "iateste"):
        return nest_ia_teste_engine(
            available_shapes=available_shapes,
            bed_width_mm=bed_width_mm,
            bed_height_mm=bed_height_mm,
            target_count=target_count,
            gap_mm=gap_mm,
            db=db,
            dieproc_params=dieproc_params,
            margins=margins,
            layers=layers
        )

    # 1. Estratégia Sint (Sintéticos Contínuo)
    if str(strategy).lower() in ("sint", "sintetico", "sintetico_continuo"):
        return nest_synthetic_engine(
            available_shapes,
            bed_width_mm,
            bed_height_mm,
            target_count=target_count,
            gap_mm=gap_mm,
            is_roll=False,
            margins=margins,
            layers=layers
        )

    # 2. Estratégia Tape A (Tiras e Fitas)
    if str(strategy).lower() in ("tape_a", "tape", "tiras", "fita"):
        return nest_tape_engine(
            available_shapes,
            bed_width_mm,
            bed_height_mm,
            target_count=target_count,
            gap_mm=gap_mm,
            margins=margins,
            layers=layers
        )

    # Ordena os moldes pela sequência de geração configurada
    sorted_shapes, _ = sort_shapes_by_sequence(available_shapes)

    # Fila de peças a cortar respeitando as quantidades de pares e camadas
    shape_queue = []
    for s in sorted_shapes:
        if "target_pieces" in s:
            qty = max(0, int(s["target_pieces"]))
        else:
            s_layers = layers or s.get("layers") or (dieproc_params.get("layers") if isinstance(dieproc_params, dict) else None) or 2
            try:
                s_layers = max(1, int(s_layers))
            except (ValueError, TypeError):
                s_layers = 2
            qty = math.ceil((int(s.get("pairs", 24)) * 2) / s_layers)
        for _ in range(qty):
            shape_queue.append(s)

    if not shape_queue:
        shape_queue = list(sorted_shapes)

    # Quantidade máxima a posicionar
    if params == "stdFill":
        max_pieces = 120
    else:
        max_pieces = target_count if (target_count and target_count > 0) else len(shape_queue)

    # Estratégia Couro Irregular (flashnestleather)
    if strategy == "flashnestleather":
        m_left = float(margins.get("left", 10.0)) if margins else 10.0
        m_right = float(margins.get("right", 10.0)) if margins else 10.0
        m_top = float(margins.get("top", 10.0)) if margins else 10.0
        m_bottom = float(margins.get("bottom", 10.0)) if margins else 10.0
        base_spacing = max(6.0, gap_mm * 2.0)
        angles = [0, 45, 90, 135, 180, 225, 270, 315] if params == "HighYield" else [0, 90, 180, 270]
        cur_x = m_left + 5.0
        row_baseline_y = m_bottom + 5.0
        row_height = 0.0
        idx = 1
        grid = SpatialGrid(cell_size=100.0)

        for i in range(max_pieces):
            shape = shape_queue[i % len(shape_queue)]
            rot = angles[i % len(angles)]

            poly = transform_contour(shape["contour"], 0, 0, rot)
            min_x, min_y, max_x, max_y = polygon_bbox(poly)
            w = max_x - min_x
            h = max_y - min_y

            if cur_x + w > bed_width_mm - m_right:
                cur_x = m_left + 5.0
                row_baseline_y += row_height + base_spacing
                row_height = 0.0

            trial_y = row_baseline_y
            poly_fn = lambda y, cx=cur_x: transform_contour(shape["contour"], cx - min_x, y - min_y, rot)
            query_bbox = (cur_x - base_spacing, max(0.0, trial_y - base_spacing * 2.0), cur_x + w + base_spacing, bed_height_mm)
            colliders = grid.query_potential_colliders(query_bbox, gap=base_spacing)

            if colliders:
                max_c_y = max(cb[3] for _, cb in colliders)
                start_val = max(trial_y, max_c_y + base_spacing)
                trial_y = find_contact_coordinate_binary(poly_fn, colliders, base_spacing, start_val, trial_y)

            c_poly = poly_fn(trial_y)
            c_bbox = polygon_bbox(c_poly)

            if trial_y + h > bed_height_mm - m_top or any(polygons_collide(c_poly, cp, gap=base_spacing, bbox_a=c_bbox, bbox_b=cb) for cp, cb in colliders):
                break

            s_sz = str(shape.get("size") or shape.get("taglia") or "41")
            p_color = get_color_for_size(s_sz, idx)
            piece = {
                "id": idx,
                "shape": shape,
                "name": shape.get("name", "Molde"),
                "size": s_sz,
                "color": p_color,
                "contour": shape.get("contour", []),
                "x": cur_x - min_x,
                "y": trial_y - min_y,
                "rotation": rot
            }
            placed.append(piece)
            grid.insert(idx, c_poly, c_bbox)
            idx += 1


            cur_x += w + base_spacing
            if (trial_y - row_baseline_y + h) > row_height:
                row_height = trial_y - row_baseline_y + h

        return placed

    # Estratégias de Sintéticos (DieProc dp98): flashnestsheet, freenest
    dp_config = dict(dieproc_params) if dieproc_params else {}
    # Chaves de controle do orquestrador NÃO são parâmetros de preset DieProc:
    # se só elas estiverem presentes, o preset deve ser mapeado normalmente.
    control_keys = ("cancel_check", "sheet_timeout_sec", "max_tries_per_piece", "deterministic")
    controls = {k: dp_config[k] for k in control_keys if k in dp_config}
    if not any(k not in control_keys for k in dp_config):
        # Mapeia predefinições caso não tenha sido passado objeto customizado
        if params == "ALTERNADO":
            dp_config = {"coupling": "0/0 0/180", "gap1": gap_mm, "row_interlock": True, "range1_from": -3.0, "range1_to": 3.0, "range1_step": 1.0}
        elif params == "DIREITA":
            dp_config = {"coupling": "0/0", "gap1": gap_mm, "row_interlock": True, "range1_from": -3.0, "range1_to": 3.0, "range1_step": 1.0}
        elif params == "ESQUERDA":
            dp_config = {"coupling": "0/180", "gap1": gap_mm, "row_interlock": True, "range1_from": -3.0, "range1_to": 3.0, "range1_step": 1.0}
        elif params == "GAP 2":
            dp_config = {"coupling": "0/0 0/180", "gap1": 2.0, "row_interlock": True, "range1_from": -3.0, "range1_to": 3.0, "range1_step": 1.0}
        elif params == "HighYield":
            dp_config = {"coupling": "0/0 0/180", "gap1": max(0.5, float(gap_mm) * 0.7), "row_interlock": True, "range1_from": -5.0, "range1_to": 5.0, "range1_step": 0.5}
        elif params == "FastNest":
            dp_config = {"coupling": "0/0 0/180", "gap1": max(1.5, float(gap_mm) * 1.5), "row_interlock": True, "range1_from": 0.0, "range1_to": 0.0, "range1_step": 0.0}
        else:
            dp_config = {"coupling": "0/0", "gap1": gap_mm, "row_interlock": False, "range1_from": 0.0, "range1_to": 1.0, "range1_step": 1.0}
        dp_config.update(controls)

    # Prioridade absoluta do gap oficial configurado pelo usuário na sessão
    if gap_mm is not None:
        dp_config["gap1"] = float(gap_mm)

    return dieproc_nest_pieces(
        available_shapes,
        bed_width_mm,
        bed_height_mm,
        target_count=max_pieces,
        dieproc_params=dp_config,
        is_roll=False,
        margins=margins,
        layers=layers
    )


def piece_matches_shape(piece: dict, shape: dict) -> bool:
    """
    Verifica se uma peça colocada corresponde ao molde especificado,
    respeitando a trava de compatibilidade de tamanho e a eliminação de colisão de ID.
    """
    p_shape = piece.get("shape") if isinstance(piece.get("shape"), dict) else {}
    if p_shape:
        if p_shape.get("id") is not None and shape.get("id") is not None:
            if str(p_shape.get("id")) == str(shape.get("id")):
                return True
        p_seq = parse_sequence_num(p_shape.get("sequence"))
        s_seq = parse_sequence_num(shape.get("sequence"))
        if p_seq is not None and s_seq is not None and p_seq != s_seq:
            return False

    s_id = str(shape.get("id", "")).strip()
    s_sz = str(shape.get("size", "")).strip()
    s_nm = str(shape.get("name", "")).strip()

    p_tid = str(piece.get("target_id", "")).strip()
    p_sz = str(piece.get("size", "")).strip()
    p_nm = str(piece.get("name", "")).strip()

    # Trava estrita de compatibilidade de tamanho
    if p_sz and s_sz and p_sz != s_sz:
        return False

    if p_tid and s_id and p_tid == s_id:
        return True
    if p_nm and s_nm and p_nm == s_nm:
        return True
    if p_sz and s_sz and p_sz == s_sz and (not p_nm or not s_nm or p_nm == s_nm):
        return True

    return False


def nest_multi_sheet(
    available_shapes: list,
    bed_width_mm: float,
    bed_height_mm: float,
    strategy: str = "flashnestsheet",
    params: str = "stdNOTFill",
    gap_mm: float = 1.0,
    dieproc_params: dict = None,
    db=None,
    margins: dict = None,
    layers: int = 2,
    max_sheets: int = 200,
    progress_callback=None,
    cancel_check=None,
    max_total_sec: float = None
) -> dict:
    """
    Orquestrador de Nesting em Múltiplas Placas (lay0000, lay0001, ...) até encaixar
    toda a quantidade pedida na sessão (comportamento clássico Layout.exe / JobManager).

    Regras:
    - Demanda inicial calculada via N_lay = ceil((P * 2) / L) aplicada à demanda total da sessão.
    - Loop por placas: nestar na placa k com o que falta; subtrair da demanda; abrir placa k+1.
    - Proteções: parada imediata se peça for maior que a placa útil ou se nenhuma peça couber, sem laço infinito.
    - Limite de segurança de max_sheets (padrão 200) com aviso.
    - Orçamento global de tempo de cálculo (max_total_sec, padrão 120 s ou CORTEAC_NEST_TOTAL_TIMEOUT):
      impede que sessões grandes prendam a máquina por minutos; encerra com layouts parciais.
    - Ordem de prioridade: coluna 'sequence' (# CONFIRMAR NO WINDOWS: ordem pela coluna Sequência).
    - Feedback de progresso via progress_callback(sheet_idx, total_estimado) a cada nova placa.
    - Suporte a cancelamento imediato via cancel_check() retornando layouts parciais calculados.
    - Verificação de segurança de dimensões (máximo 10 metros / 10.000 mm).
    """
    if max_total_sec is None:
        try:
            max_total_sec = float(os.getenv("CORTEAC_NEST_TOTAL_TIMEOUT", "120"))
        except (TypeError, ValueError):
            max_total_sec = 120.0
    try:
        sheet_timeout_base = float(os.getenv("CORTEAC_SHEET_TIMEOUT", "5.0"))
    except (TypeError, ValueError):
        sheet_timeout_base = 5.0
    t_nest_start = time.perf_counter()
    if bed_width_mm > 10000.0 or bed_height_mm > 10000.0:
        return {
            "success": False,
            "cancelled": False,
            "layouts": [],
            "total_pieces": 0,
            "total_pairs_cut": 0,
            "total_pairs_demanded": sum(int(x.get("pairs", 0)) for x in (available_shapes or [])),
            "yields": [],
            "unplaced_shapes": [str(s.get("name") or s.get("id") or "Molde") for s in (available_shapes or [])],
            "warning": f"Dimensões da chapa ({bed_width_mm:.1f} x {bed_height_mm:.1f} mm) excedem o limite de segurança de 10 metros (10.000 mm).",
            "missing_sequence_warning": None,
            "shape_spans": [],
            "spans_summary": "",
            "num_sheets": 0
        }

    if not available_shapes:
        return {
            "success": True,
            "cancelled": False,
            "layouts": [],
            "total_pieces": 0,
            "total_pairs_cut": 0,
            "total_pairs_demanded": 0,
            "yields": [],
            "unplaced_shapes": [],
            "warning": None,
            "missing_sequence_warning": None,
            "shape_spans": [],
            "spans_summary": "",
            "num_sheets": 0
        }

    l_val = max(1, int(layers or 2))
    m_dict = dict(margins) if margins else {"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0}
    m_left = float(m_dict.get("left", 10.0))
    m_right = float(m_dict.get("right", 10.0))
    m_top = float(m_dict.get("top", 10.0))
    m_bottom = float(m_dict.get("bottom", 10.0))

    usable_w = bed_width_mm - m_left - m_right
    usable_h = bed_height_mm - m_bottom - m_top

    # Proteção prévia: verifica se algum molde é fisicamente maior que a placa útil
    for s in available_shapes:
        c = s.get("contour", [])
        if c and len(c) >= 3:
            min_x, min_y, max_x, max_y = polygon_bbox(c)
            bw = max_x - min_x
            bh = max_y - min_y
            fits_direct = (bw <= usable_w and bh <= usable_h)
            fits_rotated = (bh <= usable_w and bw <= usable_h)
            if not (fits_direct or fits_rotated):
                shp_name = str(s.get("name") or s.get("id") or "Molde")
                return {
                    "success": False,
                    "cancelled": False,
                    "layouts": [],
                    "total_pieces": 0,
                    "total_pairs_cut": 0,
                    "total_pairs_demanded": sum(int(x.get("pairs", 0)) for x in available_shapes),
                    "yields": [],
                    "unplaced_shapes": [shp_name],
                    "warning": f"Molde '{shp_name}' ({bw:.1f}x{bh:.1f} mm) excede a área útil da placa ({usable_w:.1f}x{usable_h:.1f} mm).",
                    "missing_sequence_warning": None,
                    "shape_spans": [],
                    "spans_summary": "",
                    "num_sheets": 0
                }

    # Ordem de prioridade entre moldes
    # CONFIRMAR NO WINDOWS: ordem pela coluna Sequência (sequence) dos moldes
    sorted_shapes, missing_seq_names = sort_shapes_by_sequence(available_shapes)
    missing_seq_warn = f"Moldes sem sequência definida colocados no final: {', '.join(missing_seq_names)}" if missing_seq_names else None

    # Demanda total em peças calculada no nível da sessão: N_lay = ceil((P * 2) / L)
    demands = []
    total_pairs_demanded = 0
    total_pieces_demanded = 0
    for s in sorted_shapes:
        req_p = int(s.get("pairs", 0))
        total_pairs_demanded += req_p
        s_layers = s.get("layers") or l_val
        try:
            s_layers = max(1, int(s_layers))
        except (ValueError, TypeError):
            s_layers = l_val
        req_pieces = math.ceil((req_p * 2) / s_layers)
        total_pieces_demanded += req_pieces
        demands.append({
            "shape": s,
            "total_pieces": req_pieces,
            "remaining_pieces": req_pieces,
            "placed_pieces": 0
        })

    if total_pieces_demanded == 0:
        return {
            "success": True,
            "cancelled": False,
            "layouts": [],
            "total_pieces": 0,
            "total_pairs_cut": 0,
            "total_pairs_demanded": 0,
            "yields": [],
            "unplaced_shapes": [],
            "warning": missing_seq_warn,
            "missing_sequence_warning": missing_seq_warn,
            "shape_spans": [],
            "spans_summary": "",
            "num_sheets": 0
        }

    layouts = []
    sheet_idx = 0
    warning_msg = None
    cancelled = False

    while any(d["remaining_pieces"] > 0 for d in demands):
        if cancel_check is not None and cancel_check():
            cancelled = True
            warning_msg = "Cálculo cancelado pelo operador."
            break

        if sheet_idx >= max_sheets:
            warning_msg = f"Limite de segurança de {max_sheets} placas atingido."
            break

        elapsed_nest = time.perf_counter() - t_nest_start
        if max_total_sec and elapsed_nest > max_total_sec:
            warning_msg = (
                f"Tempo máximo de cálculo ({max_total_sec:.0f} s) atingido — "
                f"{len(layouts)} placa(s) calculada(s) preservada(s)."
            )
            break

        if progress_callback is not None:
            # Total honesto: estimativa de placas pela densidade já observada,
            # em vez de anunciar o limite de segurança de max_sheets.
            placed_so_far = sum(len(ly.get("pieces", [])) for ly in layouts)
            if layouts and placed_so_far > 0:
                avg_per_sheet = placed_so_far / len(layouts)
                total_est = max(sheet_idx + 1, int(math.ceil(total_pieces_demanded / avg_per_sheet)))
            else:
                # Ainda sem amostra de densidade: total desconhecido (0 = "chapa N...").
                total_est = 0
            try:
                progress_callback(sheet_idx, min(total_est, max_sheets))
            except Exception:
                pass

        # Monta lista de formas com demanda restante para esta rodada na ordem estrita de sequência
        round_shapes = []
        for d in demands:
            if d["remaining_pieces"] > 0:
                s_copy = dict(d["shape"])
                s_copy["target_pieces"] = d["remaining_pieces"]
                s_copy["pairs"] = math.ceil((d["remaining_pieces"] * l_val) / 2)
                round_shapes.append(s_copy)

        target_count_round = sum(d["remaining_pieces"] for d in demands)

        round_dp_params = dict(dieproc_params) if dieproc_params else {}
        if cancel_check is not None:
            round_dp_params["cancel_check"] = cancel_check
        if max_total_sec:
            # Nenhuma placa pode consumir sozinha mais que o orçamento global restante.
            remaining_budget = max(0.5, max_total_sec - elapsed_nest)
            try:
                cur_sheet_timeout = float(round_dp_params.get("sheet_timeout_sec") or sheet_timeout_base)
            except (TypeError, ValueError):
                cur_sheet_timeout = sheet_timeout_base
            round_dp_params["sheet_timeout_sec"] = min(cur_sheet_timeout, remaining_budget)

        placed_round = auto_nest_pieces(
            available_shapes=round_shapes,
            bed_width_mm=bed_width_mm,
            bed_height_mm=bed_height_mm,
            target_count=target_count_round,
            strategy=strategy,
            params=params,
            gap_mm=gap_mm,
            dieproc_params=round_dp_params,
            db=db,
            margins=m_dict,
            layers=l_val
        )

        if cancel_check is not None and cancel_check():
            cancelled = True
            warning_msg = "Cálculo cancelado pelo operador."
            break

        # Proteção contra laço infinito: se a rodada não encaixou nada
        if not placed_round:
            unplaced = [d["shape"].get("name", "Molde") for d in demands if d["remaining_pieces"] > 0]
            warning_msg = f"Não foi possível encaixar peças restantes na placa {sheet_idx}: {unplaced}"
            break

        # Prioridade Estrita [DECISÃO] (# CONFIRMAR NO WINDOWS):
        # Percorre as demandas na ordem estrita da sequência.
        # Um molde k só pode entrar se todos os moldes anteriores já tiverem sua demanda esgotada.
        # Se um molde k não esgotar sua demanda nesta placa, a placa fecha imediatamente e
        # nenhum molde posterior entra nesta placa.
        valid_placed_round = []
        can_place_next = True

        for d in demands:
            if d["remaining_pieces"] <= 0:
                continue

            if not can_place_next:
                break

            shp_pieces = [p for p in placed_round if piece_matches_shape(p, d["shape"])]
            take_cnt = min(len(shp_pieces), d["remaining_pieces"])

            if take_cnt > 0:
                valid_placed_round.extend(shp_pieces[:take_cnt])
                d["remaining_pieces"] -= take_cnt
                d["placed_pieces"] += take_cnt

            # Se este molde AINDA tem peças restantes a cortar, a fila estrita trava:
            # nenhum molde com sequência maior pode entrar nesta placa!
            if d["remaining_pieces"] > 0:
                can_place_next = False

        if not valid_placed_round:
            unplaced = [d["shape"].get("name", "Molde") for d in demands if d["remaining_pieces"] > 0]
            warning_msg = f"Peças posicionadas não correspondem à demanda restante na placa {sheet_idx}: {unplaced}"
            break

        # Normaliza e renumera peças colocadas nesta placa
        plate_pieces = []
        for p_idx, p in enumerate(valid_placed_round):
            p_clean = dict(p)
            p_clean["id"] = p_idx + 1
            plate_pieces.append(p_clean)

        # Rendimento e tempo da placa individual
        plate_area_m2 = max(1e-4, (bed_width_mm * bed_height_mm) / 1_000_000.0)
        eff_pct, used_m2 = calculate_yield(plate_pieces, plate_area_m2)
        est_time, _ = calculate_atom_cutting_time(plate_pieces)

        layout_name = f"lay{sheet_idx:04d}"
        layout_entry = {
            "layout_index": sheet_idx,
            "name": layout_name,
            "code": layout_name,
            "pieces": plate_pieces,
            "placed_pieces": plate_pieces,
            "width_mm": bed_width_mm,
            "height_mm": bed_height_mm,
            "margin_left": m_left,
            "margin_right": m_right,
            "margin_top": m_top,
            "margin_bottom": m_bottom,
            "gap_mm": gap_mm,
            "yield_percent": eff_pct,
            "yield_pct": eff_pct,
            "num_items": len(plate_pieces),
            "num_dies": len(set(p.get("name") for p in plate_pieces)),
            "used_area_m2": used_m2,
            "cutting_time_sec": est_time,
            "status": "closed"
        }
        layouts.append(layout_entry)
        sheet_idx += 1

    # Mapeamento do intervalo de placas ocupado por cada molde (shape spans)
    shape_spans = []
    for d in demands:
        shp = d["shape"]
        name = shp.get("name") or shp.get("id") or "Molde"
        seq = parse_sequence_num(shp.get("sequence"))
        seq_label = f"seq {seq}" if seq is not None else "sem seq"

        sheet_indices = [
            i for i, ly in enumerate(layouts)
            if any(piece_matches_shape(p, shp) for p in ly.get("pieces", []))
        ]
        if sheet_indices:
            start_lay = f"lay{sheet_indices[0]:04d}"
            end_lay = f"lay{sheet_indices[-1]:04d}"
            if start_lay == end_lay:
                span_str = f"Molde {name} ({seq_label}): {start_lay}"
            else:
                span_str = f"Molde {name} ({seq_label}): {start_lay} → {end_lay}"
            shape_spans.append({
                "name": name,
                "sequence": seq,
                "start_layout": start_lay,
                "end_layout": end_lay,
                "span_text": span_str,
                "sheets": sheet_indices
            })
        else:
            shape_spans.append({
                "name": name,
                "sequence": seq,
                "start_layout": None,
                "end_layout": None,
                "span_text": f"Molde {name} ({seq_label}): Não encaixado",
                "sheets": []
            })

    total_placed = sum(len(ly["pieces"]) for ly in layouts)
    total_pairs_cut = (total_placed * l_val) // 2
    yields = [ly["yield_percent"] for ly in layouts]
    unplaced_names = [d["shape"].get("name", "Molde") for d in demands if d["remaining_pieces"] > 0]
    success = (len(unplaced_names) == 0 and len(layouts) > 0 and not cancelled)

    final_warning = warning_msg
    if missing_seq_warn:
        final_warning = f"{warning_msg} ({missing_seq_warn})" if warning_msg else missing_seq_warn

    return {
        "success": success,
        "cancelled": cancelled,
        "layouts": layouts,
        "total_pieces": total_placed,
        "total_pairs_cut": total_pairs_cut,
        "total_pairs_demanded": total_pairs_demanded,
        "yields": yields,
        "unplaced_shapes": unplaced_names,
        "warning": final_warning,
        "missing_sequence_warning": missing_seq_warn,
        "shape_spans": shape_spans,
        "spans_summary": "\n".join(s["span_text"] for s in shape_spans),
        "num_sheets": len(layouts)
    }


