"""
JobManager 2000 (Python Edition)
Nesting Engine & ATOM Machine Cycle Estimator (Recriação de FreeNest & AtomCuttingTimeEstimator)
"""

from cad.geometry import (
    transform_contour, polygon_area, polygon_perimeter, polygon_bbox,
    polygons_collide, bbox_overlap, simplify_contour_for_collision,
    SpatialGrid, find_contact_coordinate_binary
)
from cad.colors import get_color_for_size
from config import ATOM_MACHINE

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
        holes = p.get("holes") or (p.get("shape", {}).get("holes") if isinstance(p.get("shape"), dict) else [])
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

def dieproc_nest_pieces(available_shapes, bed_width_mm, bed_height_mm, target_count=16, dieproc_params=None, is_roll=False):
    """
    Motor de referência para corte contínuo de sintéticos (ATOM DieProc dp98).
    Projetado para rolos e chapas sintéticas (flashnestsheet / flashnestroll).
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
    gap = max(0.5, float(params.get("gap1", 1.0) or 1.0))
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

    margin = max(15.0, gap * 2.5)
    usable_width = bed_width_mm - margin * 2.0
    usable_height = bed_height_mm - margin * 2.0

    # Ordena os moldes pela sequência de geração configurada
    sorted_shapes = sorted(available_shapes, key=lambda s: int(s.get("sequence", 999)))

    # Fila de peças a cortar respeitando as quantidades de pares e sequência (1 par = 2 peças)
    shape_queue = []
    for s in sorted_shapes:
        qty = int(s.get("pairs", 24)) * 2
        for _ in range(qty):
            shape_queue.append(s)

    if not shape_queue:
        shape_queue = list(sorted_shapes)

    idx = 1

    # Disposição 1: Rolo Contínuo (flashnestroll)
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
        cur_x = margin
        row_baseline_y = margin
        row_height = 0.0
        row_idx = 0
        grid = SpatialGrid(cell_size=100.0)

        sample_poly = transform_contour(shape_queue[0]["contour"], 0, 0, effective_angles[0])
        s_min_x, s_min_y, s_max_x, s_max_y = polygon_bbox(sample_poly)
        avg_w = s_max_x - s_min_x
        avg_h = s_max_y - s_min_y

        avg_area = sum(polygon_area(s.get("contour", [])) for s in available_shapes) / len(available_shapes)

        while idx <= target_count:
            shape = shape_queue[(idx - 1) % len(shape_queue)]
            angle_idx = (idx - 1 + (row_idx if row_interlock else 0)) % len(effective_angles)
            rot = effective_angles[angle_idx]

            # Otimização de Hole-Filling: Se a peça for menor e existirem linhas já preenchidas
            if len(available_shapes) > 1 and row_baseline_y > margin + 60.0:
                s_area = polygon_area(shape.get("contour", []))
                if s_area > 0 and s_area < avg_area * 0.6:
                    hole_pos = try_hole_filling_placement(shape, grid, bed_width_mm, row_baseline_y, gap, rot)
                    if hole_pos:
                        hx, hy, hrot, hc_poly, hc_bbox = hole_pos
                        s_sz = str(shape.get("size") or shape.get("taglia") or "41")
                        p_color = get_color_for_size(s_sz, idx)
                        piece = {
                            "id": idx,
                            "shape": shape,
                            "name": shape.get("name", "Molde"),
                            "size": s_sz,
                            "color": p_color,
                            "contour": shape.get("contour", []),
                            "x": hx,
                            "y": hy,
                            "rotation": hrot
                        }
                        placed.append(piece)
                        grid.insert(idx, hc_poly, hc_bbox)
                        idx += 1
                        continue

            poly = transform_contour(shape["contour"], 0, 0, rot)
            min_x, min_y, max_x, max_y = polygon_bbox(poly)
            w = max_x - min_x
            h = max_y - min_y

            # Mudança de linha ao atingir limite da largura da chapa
            if cur_x + w > bed_width_mm - margin:

                row_idx += 1
                if row_interlock:
                    interlock_x_offset = (avg_w * 0.45) if (row_idx % 2 == 1) else 0.0
                    cur_x = margin + interlock_x_offset
                    row_baseline_y += (row_height * 0.70 + gap)
                else:
                    cur_x = margin
                    row_baseline_y += (row_height + gap)

                if diagonal:
                    cur_x += (row_idx * (avg_w * 0.25)) % (usable_width * 0.5)

                row_height = 0.0

            trial_y = max(margin, row_baseline_y)
            poly_fn = lambda y, cx=cur_x: transform_contour(shape["contour"], cx - min_x, y - min_y, rot)
            query_bbox = (cur_x - gap, max(0.0, trial_y - gap * 2.0), cur_x + w + gap, bed_height_mm)
            colliders_all = grid.query_potential_colliders(query_bbox, gap=gap)
            colliders = [(cp, cb) for cp, cb in colliders_all if cb[1] < trial_y + h * 0.15]

            if colliders:
                max_c_y = max(cb[3] for _, cb in colliders)
                start_val = max(trial_y, max_c_y + gap)
                trial_y = find_contact_coordinate_binary(poly_fn, colliders, gap, start_val, trial_y)

            c_poly = poly_fn(trial_y)
            c_bbox = polygon_bbox(c_poly)

            if trial_y + h > bed_height_mm - margin:
                break

            # Verificação estrita contra todos os potenciais obstáculos com micro-ajuste de segurança
            all_cols = grid.query_potential_colliders(c_bbox, gap=gap)
            shifts = 0
            while any(polygons_collide(c_poly, cp, gap=gap, bbox_a=c_bbox, bbox_b=cb) for cp, cb in all_cols) and shifts < 50:
                cur_x += 0.2
                c_poly = transform_contour(shape["contour"], cur_x - min_x, trial_y - min_y, rot)
                c_bbox = polygon_bbox(c_poly)
                all_cols = grid.query_potential_colliders(c_bbox, gap=gap)
                shifts += 1

            if trial_y + h > bed_height_mm - margin or any(polygons_collide(c_poly, cp, gap=gap, bbox_a=c_bbox, bbox_b=cb) for cp, cb in all_cols):
                cur_x += (w * 0.25 + gap)
                if cur_x + w > bed_width_mm - margin:
                    row_idx += 1
                    cur_x = margin
                    row_baseline_y += (row_height + gap)
                    row_height = 0.0
                continue

            size_str = str(shape.get("size") or shape.get("taglia") or "41")
            p_color = get_color_for_size(size_str, idx)
            piece = {
                "id": idx,
                "shape": shape,
                "name": shape.get("name", "Molde"),
                "size": size_str,
                "color": p_color,
                "contour": shape.get("contour", []),
                "x": cur_x - min_x,
                "y": trial_y - min_y,
                "rotation": rot
            }
            placed.append(piece)
            grid.insert(idx, c_poly, c_bbox)
            idx += 1

            if (trial_y - row_baseline_y + h) > row_height:
                row_height = trial_y - row_baseline_y + h

            # Deslocamento por aproximação de contorno (bumping contorno a contorno para gap exato)
            if idx <= target_count:
                next_shape = shape_queue[(idx - 1) % len(shape_queue)]
                next_angle_idx = (idx - 1 + (row_idx if row_interlock else 0)) % len(effective_angles)
                next_rot = effective_angles[next_angle_idx]
                n_poly0 = transform_contour(next_shape["contour"], 0, 0, next_rot)
                n_min_x, n_min_y, n_max_x, n_max_y = polygon_bbox(n_poly0)

                safe_start_x = c_bbox[2] + gap
                min_cand_x = max(margin, c_bbox[0])

                poly_fn_x = lambda x: transform_contour(next_shape["contour"], x - n_min_x, trial_y - n_min_y, next_rot)
                cur_x = find_contact_coordinate_binary(poly_fn_x, [(c_poly, c_bbox)], gap, start_val=safe_start_x, min_val=min_cand_x)
            else:
                cur_x += (w + gap)

        return placed


def nest_synthetic_engine(available_shapes, bed_width_mm, bed_height_mm, target_count=16, gap_mm=1.0, is_roll=False):
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

    sorted_shapes = sorted(available_shapes, key=lambda s: int(s.get("sequence", 999)))
    shape_queue = []
    for s_item in sorted_shapes:
        qty = int(s_item.get("pairs", 24)) * 2
        for _ in range(qty):
            shape_queue.append(s_item)
    if not shape_queue:
        shape_queue = list(sorted_shapes)

    max_pieces = target_count if (target_count and target_count > 0) else len(shape_queue)
    margin = max(10.0, gap_mm * 2.0)
    gap = max(0.5, float(gap_mm))

    grid = SpatialGrid(cell_size=100.0)

    sample_poly = transform_contour(shape_queue[0]["contour"], 0, 0, 0.0)
    s_min_x, s_min_y, s_max_x, s_max_y = polygon_bbox(sample_poly)
    avg_w = max(10.0, s_max_x - s_min_x)
    avg_h = max(10.0, s_max_y - s_min_y)

    row_idx = 0
    cur_row_y = margin
    idx = 1
    rows = []

    while idx <= max_pieces and (cur_row_y < bed_height_mm - margin):
        is_odd_row = (row_idx % 2 == 1)
        interlock_offset = (avg_w * 0.40) if is_odd_row else 0.0

        row_pieces = []
        cur_x = margin + interlock_offset

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
                min_x_cand = max(margin, prev["bbox"][0])
                poly_fn_x = lambda x: transform_contour(shape["contour"], x - min_x, cur_row_y - min_y, rot)
                cand_x = find_contact_coordinate_binary(poly_fn_x, [(prev["poly"], prev["bbox"])], gap, start_val=safe_x, min_val=min_x_cand)

            if cand_x + w > bed_width_mm - margin:
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

        if not is_roll and any(p["bbox"][3] > bed_height_mm - margin for p in row_pieces):
            break

        for p in row_pieces:
            grid.insert(p["id"], p["poly"], p["bbox"])
            placed.append(p)
        rows.append(row_pieces)

        row_idx += 1
        cur_row_y += avg_h * 0.70

    return placed

def nest_tape_engine(available_shapes, bed_width_mm, bed_height_mm, target_count=16, gap_mm=1.0):
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

    sorted_shapes = sorted(available_shapes, key=lambda s: int(s.get("sequence", 999)))
    shape_queue = []
    for s in sorted_shapes:
        qty = int(s.get("pairs", 24))
        for _ in range(qty):
            shape_queue.append(s)
    if not shape_queue:
        shape_queue = list(sorted_shapes)

    max_pieces = target_count if (target_count and target_count > 0) else len(shape_queue)

    margin = max(8.0, gap_mm * 1.5)
    gap = max(0.5, float(gap_mm))

    cur_x = margin
    row_baseline_y = margin
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

        if cur_x + w > bed_width_mm - margin:
            row_idx += 1
            cur_x = margin
            row_baseline_y += (row_height + gap)
            row_height = 0.0

        trial_y = max(margin, row_baseline_y)
        poly_fn = lambda y, cx=cur_x: transform_contour(shape["contour"], cx - min_x, y - min_y, rot)
        query_bbox = (cur_x - gap, max(0.0, trial_y - gap * 2.0), cur_x + w + gap, bed_height_mm)
        colliders = grid.query_potential_colliders(query_bbox, gap=gap)

        if colliders:
            max_c_y = max(cb[3] for _, cb in colliders)
            start_val = max(trial_y, max_c_y + gap)
            trial_y = find_contact_coordinate_binary(poly_fn, colliders, gap, start_val, trial_y)

        c_poly = poly_fn(trial_y)
        c_bbox = polygon_bbox(c_poly)

        if trial_y + h > bed_height_mm - margin or any(polygons_collide(c_poly, cp, gap=gap, bbox_a=c_bbox, bbox_b=cb) for cp, cb in colliders):
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

def auto_nest_pieces(available_shapes, bed_width_mm, bed_height_mm, target_count=16, strategy="flashnestsheet", params="stdNOTFill", gap_mm=1.0, dieproc_params=None):
    """
    Algoritmo de aninhamento automático 2D com suporte a múltiplas estratégias:
    - sint: Motor de corte contínuo para rolos e chapas sintéticas (geminação 0°/180° e colmeia).
    - tape_a: Motor linear para fitas estreitas, tiras, debruns e correias (passo linear compacto).
    - flashnestsheet: Nesting contínuo em chapas sintéticas (DieProc dp98 com Row interlock e Coupling).
    - flashnestroll: Nesting contínuo em rolos/bobinas sintéticas.
    - flashnestleather: Nesting em couro / peles irregulares (busca multi-angular).
    - freenest: Heurística livre para máxima compactação geométrica.
    """
    placed = []
    if not available_shapes:
        return placed

    # 1. Estratégia Sint (Sintéticos Contínuo)
    if str(strategy).lower() in ("sint", "sintetico", "sintetico_continuo"):
        return nest_synthetic_engine(
            available_shapes,
            bed_width_mm,
            bed_height_mm,
            target_count=target_count,
            gap_mm=gap_mm,
            is_roll=False
        )

    # 2. Estratégia Tape A (Tiras e Fitas)
    if str(strategy).lower() in ("tape_a", "tape", "tiras", "fita"):
        return nest_tape_engine(
            available_shapes,
            bed_width_mm,
            bed_height_mm,
            target_count=target_count,
            gap_mm=gap_mm
        )

    # Ordena os moldes pela sequência de geração configurada
    sorted_shapes = sorted(available_shapes, key=lambda s: int(s.get("sequence", 999)))

    # Fila de peças a cortar respeitando as quantidades de pares e sequência
    shape_queue = []
    for s in sorted_shapes:
        qty = int(s.get("pairs", 24))
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
        margin = max(40.0, gap_mm * 10.0)
        base_spacing = max(6.0, gap_mm * 2.0)
        angles = [0, 45, 90, 135, 180, 225, 270, 315] if params == "HighYield" else [0, 90, 180, 270]
        cur_x = margin + 15.0
        row_baseline_y = margin + 15.0
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

            if cur_x + w > bed_width_mm - margin - 20.0:
                cur_x = margin + 15.0
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

            if trial_y + h > bed_height_mm - margin - 20.0 or any(polygons_collide(c_poly, cp, gap=base_spacing, bbox_a=c_bbox, bbox_b=cb) for cp, cb in colliders):
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

    # Estratégias de Sintéticos (DieProc dp98): flashnestsheet, flashnestroll, freenest
    dp_config = dict(dieproc_params) if dieproc_params else {}
    if not dp_config:
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
            dp_config = {"coupling": "0/0 0/180", "gap1": max(0.5, gap_mm * 0.7), "row_interlock": True, "range1_from": -5.0, "range1_to": 5.0, "range1_step": 0.5}
        elif params == "FastNest":
            dp_config = {"coupling": "0/0 0/180", "gap1": max(1.5, gap_mm * 1.5), "row_interlock": True, "range1_from": 0.0, "range1_to": 0.0, "range1_step": 0.0}
        else:
            dp_config = {"coupling": "0/0", "gap1": gap_mm, "row_interlock": False, "range1_from": 0.0, "range1_to": 1.0, "range1_step": 1.0}

    is_roll = (strategy == "flashnestroll")
    return dieproc_nest_pieces(
        available_shapes,
        bed_width_mm,
        bed_height_mm,
        target_count=max_pieces,
        dieproc_params=dp_config,
        is_roll=is_roll
    )

