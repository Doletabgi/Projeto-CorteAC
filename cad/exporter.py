"""
JobManager 2000 (Python Edition)
Export Engine: G-Code / ISO CNC, XML Report & DXF (Pure Python)
Trajetória CAM Otimizada: Vacuum Preservation, Midpoint Longest Edge, Strip-TSP + 2-Opt e Common-Line
"""

import datetime
import math
from pathlib import Path
from cad.geometry import transform_contour, rotate_point
from config import ATOM_MACHINE

def reorder_contour_midpoint_longest_edge(contour):
    """
    Encontra o maior segmento reto do contorno e reorganiza os pontos
    para que a lâmina oscilante inicie o corte no ponto médio (midpoint) desse segmento.
    Evita lascamento de quinas e deflexão da lâmina no plunge inicial.
    """
    if len(contour) < 3:
        return contour

    n = len(contour)
    best_seg_idx = 0
    best_len_sq = -1.0

    for i in range(n):
        p1 = contour[i]
        p2 = contour[(i + 1) % n]
        dx = p2["x"] - p1["x"]
        dy = p2["y"] - p1["y"]
        length_sq = dx * dx + dy * dy
        if length_sq > best_len_sq:
            best_len_sq = length_sq
            best_seg_idx = i

    p1 = contour[best_seg_idx]
    p2 = contour[(best_seg_idx + 1) % n]
    mid_pt = {
        "x": round((p1["x"] + p2["x"]) / 2.0, 2),
        "y": round((p1["y"] + p2["y"]) / 2.0, 2)
    }

    # Reorganiza: mid_pt -> p2 -> p3 ... -> p1 -> fecha em mid_pt
    reordered = [mid_pt]
    for k in range(1, n + 1):
        idx = (best_seg_idx + k) % n
        reordered.append(contour[idx])
    reordered.append(mid_pt)
    return reordered

def two_opt_pass(route, dist_matrix, max_iter=40):
    """
    Executa uma passagem ou conjunto de iterações do 2-Opt com avaliação delta O(1).
    Retorna (route, total_delta).
    """
    total_delta = 0.0
    improved = True
    iterations = 0
    n_pieces = len(route)

    while improved and iterations < max_iter:
        improved = False
        iterations += 1
        for i in range(n_pieces - 1):
            u = route[i]
            v = route[i + 1]
            d_uv = dist_matrix[u][v]
            for j in range(i + 2, n_pieces):
                w = route[j]
                if j == n_pieces - 1:
                    delta = dist_matrix[u][w] - d_uv
                else:
                    z = route[j + 1]
                    delta = dist_matrix[u][w] + dist_matrix[v][z] - d_uv - dist_matrix[w][z]

                if delta < -0.5:
                    route[i + 1 : j + 1] = route[i + 1 : j + 1][::-1]
                    total_delta += delta
                    improved = True
                    break
            if improved:
                break

    return route, total_delta


def or_opt(route, dist_matrix, origin_idx, max_segment=3, max_passes=50):
    """
    Otimização local Or-opt para TSP de rota aberta.

    Move segmentos de tamanho 1 a max_segment para outras posições,
    recalculando apenas as arestas afetadas (delta O(1) por tentativa).
    Retorna (nova_rota, ganho_total).
    """
    if len(route) <= 2:
        return route, 0.0

    total_gain = 0.0
    N = len(route)
    passes = 0
    improved = True

    while improved and passes < max_passes:
        improved = False
        passes += 1
        for length in range(max_segment, 0, -1):
            for i in range(N - length + 1):
                segment = route[i : i + length]
                u = origin_idx if i == 0 else route[i - 1]
                v = segment[0]
                w = segment[-1]
                x = route[i + length] if i + length < N else None

                d_remove = -dist_matrix[u][v]
                if x is not None:
                    d_remove += dist_matrix[u][x] - dist_matrix[w][x]

                # Tenta inserção em posições anteriores a i
                for j in range(0, i):
                    p = origin_idx if j == 0 else route[j - 1]
                    q = route[j]
                    delta = d_remove + dist_matrix[p][v] + dist_matrix[w][q] - dist_matrix[p][q]
                    if delta < -0.5:
                        route = route[:j] + segment + route[j:i] + route[i + length:]
                        total_gain += delta
                        improved = True
                        break
                if improved:
                    break

                # Tenta inserção em posições posteriores a i + length
                for j in range(i + length, N):
                    p = route[j]
                    q = route[j + 1] if j + 1 < N else None
                    if q is not None:
                        d_insert = dist_matrix[p][v] + dist_matrix[w][q] - dist_matrix[p][q]
                    else:
                        d_insert = dist_matrix[p][v]
                    delta = d_remove + d_insert
                    if delta < -0.5:
                        route = route[:i] + route[i + length : j + 1] + segment + route[j + 1 :]
                        total_gain += delta
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break

    return route, total_gain


def optimize_piece_cutting_order_tsp(placed_pieces, algorithm="2opt+oropt", max_iter=40):
    """
    Aplica Strip-TSP + 2-Opt + Or-opt para ordenar as peças a serem cortadas na mesa,
    minimizando o percurso em vazio (G00 rapid traverse) do cabeçote CNC.
    Otimizado para complexidade O(N^2) via matriz de distâncias pré-computada
    e avaliação delta O(1) no 2-Opt e Or-opt.
    """
    if len(placed_pieces) <= 2:
        return list(placed_pieces)

    n_pieces = len(placed_pieces)

    # Determina o ponto inicial de cada peça
    piece_entries = []
    for p in placed_pieces:
        poly = transform_contour(p["shape"]["contour"], p["x"], p["y"], p["rotation"])
        holes = p["shape"].get("holes", [])
        if holes:
            rx, ry = rotate_point(holes[0]["x"], holes[0]["y"], p["rotation"])
            entry = (p["x"] + rx, p["y"] + ry)
        else:
            reordered = reorder_contour_midpoint_longest_edge(poly)
            entry = (reordered[0]["x"], reordered[0]["y"])
        piece_entries.append(entry)

    # 1. Pré-computação da matriz de distâncias D (N+1 x N+1, onde índice n_pieces = origem (0, 0))
    # Complexidade O(N^2) executada uma única vez
    origin_idx = n_pieces
    dist_matrix = [[0.0] * (n_pieces + 1) for _ in range(n_pieces + 1)]
    for i in range(n_pieces):
        ex, ey = piece_entries[i]
        d_orig = math.hypot(ex, ey)
        dist_matrix[i][origin_idx] = d_orig
        dist_matrix[origin_idx][i] = d_orig
        for j in range(i + 1, n_pieces):
            jx, jy = piece_entries[j]
            d = math.hypot(ex - jx, ey - jy)
            dist_matrix[i][j] = d
            dist_matrix[j][i] = d

    # 2. Heurística Nearest Neighbor a partir da origem (0, 0)
    unvisited = list(range(n_pieces))
    route = []
    curr = origin_idx

    while unvisited:
        nearest_idx = -1
        min_dist = float("inf")
        for idx in unvisited:
            d = dist_matrix[curr][idx]
            if d < min_dist:
                min_dist = d
                nearest_idx = idx
        route.append(nearest_idx)
        curr = nearest_idx
        unvisited.remove(nearest_idx)

    # 3. Otimização Local
    algo_clean = str(algorithm).lower()
    eff_max_iter = 200 if algo_clean == "2opt+oropt+iter200" else max_iter

    # Fase inicial de 2-Opt
    route, _ = two_opt_pass(route, dist_matrix, max_iter=eff_max_iter)

    if algo_clean in ("2opt+oropt", "2opt+oropt+iter200", "oropt", "or-opt"):
        # Pipeline 2-Opt -> Or-opt -> 2-Opt
        or_passes = 3 if n_pieces <= 200 else 1
        for _ in range(2):
            route, delta_or = or_opt(route, dist_matrix, origin_idx, max_segment=3, max_passes=or_passes)
            if delta_or >= -0.5:
                break
            route, delta_2opt = two_opt_pass(route, dist_matrix, max_iter=eff_max_iter)
            if delta_2opt >= -0.5:
                break

    return [placed_pieces[idx] for idx in route]


def _canonical_edge(p1, p2, tol=0.2):
    """Retorna uma chave canônica normalizada para uma aresta reta."""
    x1, y1 = round(p1["x"] / tol) * tol, round(p1["y"] / tol) * tol
    x2, y2 = round(p2["x"] / tol) * tol, round(p2["y"] / tol) * tol
    if (x1, y1) > (x2, y2):
        x1, y1, x2, y2 = x2, y2, x1, y1
    return (round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1))

def export_gcode(placed_pieces, material, file_path, gap_mm=1.0):
    """
    Exporta instruções CNC no padrão G-Code / ISO para máquinas de corte ATOM.
    Aplica:
    1. Strip-TSP + 2-Opt para ordenação do percurso e redução de G00.
    2. Sequência de Preservação de Vácuo: Furações -> Piques -> Cortes Internos -> Perímetro Externo.
    3. Plunge de entrada no ponto médio da maior aresta reta.
    4. Common-Line cutting quando gap == 0 (elimina cortes duplicados em fitas).
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sorted_pieces = optimize_piece_cutting_order_tsp(placed_pieces)

    lines = [
        "; ========================================================",
        "; ATOM FlashCut CNC Program - CorteAC Win10",
        f"; Date: {now}",
        f"; Machine: {ATOM_MACHINE['model']}",
        f"; Material: {material['name']} ({material['width_mm']}x{material['height_mm']}mm, {material['thickness_mm']}mm)",
        f"; Total Pieces: {len(sorted_pieces)}",
        "; CAM Optimization: Vacuum Preservation + Strip-TSP + Midpoint Entry",
        "; ========================================================",
        "",
        "G21 ; Units in Millimeters",
        "G90 ; Absolute Coordinates",
        f"M03 S{ATOM_MACHINE['blade_frequency_rpm']} ; Start oscillating knife",
        ""
    ]

    feed_rate = ATOM_MACHINE['blade_speed_mm_s'] * 60.0
    common_line_active = (float(gap_mm or 1.0) <= 0.05)
    cut_edges = set()

    for idx, p in enumerate(sorted_pieces, start=1):
        lines.append(f"; --- Piece #{idx} (ID:{p['id']}): {p['shape']['name']} ---")

        # -------------------------------------------------------------
        # 1º e 2º PASSO: FURAÇÕES E PIQUES (VACUUM PRESERVATION)
        # Devem ser executados PRIMEIRO, enquanto o material ainda está
        # 100% selado e preso pelo vácuo da mesa.
        # -------------------------------------------------------------
        holes = p["shape"].get("holes", [])
        if holes:
            lines.append("; [Tool 1] Punches / Drills (G81 - Vacuum Safe)")
            for h in holes:
                rx, ry = rotate_point(h["x"], h["y"], p["rotation"])
                hx = p["x"] + rx
                hy = p["y"] + ry
                lines.append("G00 Z5.00")
                lines.append(f"G00 X{hx:.2f} Y{hy:.2f}")
                lines.append(f"G81 Z-{material['thickness_mm']:.2f} R2.00 F300 ; Cycle Punch")

        # -------------------------------------------------------------
        # 3º PASSO: CORTES INTERNOS / JANELAS (se existirem)
        # -------------------------------------------------------------
        internal_cuts = p["shape"].get("internal_cuts", [])
        if internal_cuts:
            lines.append("; [Tool 2] Internal Cutouts / Windows")
            for cut in internal_cuts:
                cut_poly = transform_contour(cut, p["x"], p["y"], p["rotation"])
                if cut_poly:
                    lines.append("G00 Z5.00")
                    lines.append(f"G00 X{cut_poly[0]['x']:.2f} Y{cut_poly[0]['y']:.2f}")
                    lines.append(f"G01 Z-{material['thickness_mm']:.2f} F{feed_rate:.0f}")
                    for pt in cut_poly[1:]:
                        lines.append(f"G01 X{pt['x']:.2f} Y{pt['y']:.2f}")
                    lines.append(f"G01 X{cut_poly[0]['x']:.2f} Y{cut_poly[0]['y']:.2f}")

        # -------------------------------------------------------------
        # 4º PASSO: CONTORNO EXTERNO (SEMPRE POR ÚLTIMO)
        # Entrada no ponto médio do maior segmento reto.
        # -------------------------------------------------------------
        poly = transform_contour(p["shape"]["contour"], p["x"], p["y"], p["rotation"])
        opt_poly = reorder_contour_midpoint_longest_edge(poly)

        lines.append("; [Tool 3] Outer Perimeter Cut (Oscillating Knife - Midpoint Entry)")
        lines.append("G00 Z5.00")
        lines.append(f"G00 X{opt_poly[0]['x']:.2f} Y{opt_poly[0]['y']:.2f}")
        lines.append(f"G01 Z-{material['thickness_mm']:.2f} F{feed_rate:.0f}")

        # Executa corte do contorno
        for i in range(len(opt_poly) - 1):
            p_start = opt_poly[i]
            p_end = opt_poly[i + 1]

            if common_line_active:
                edge_key = _canonical_edge(p_start, p_end)
                if edge_key in cut_edges:
                    # Aresta comum já cortada pela peça vizinha
                    lines.append(f"; Common-Line Skip -> X{p_end['x']:.2f} Y{p_end['y']:.2f}")
                    lines.append("G00 Z2.00")
                    lines.append(f"G00 X{p_end['x']:.2f} Y{p_end['y']:.2f}")
                    lines.append(f"G01 Z-{material['thickness_mm']:.2f} F{feed_rate:.0f}")
                    continue
                else:
                    cut_edges.add(edge_key)

            lines.append(f"G01 X{p_end['x']:.2f} Y{p_end['y']:.2f}")

        lines.append("")

    lines.extend([
        "G00 Z50.00 ; Retract knife to safe position",
        "M05 ; Stop blade",
        "M30 ; End of Program"
    ])

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return file_path

def export_dxf(placed_pieces, material, file_path):
    """
    Exporta o layout completo em formato DXF AutoCAD R12 (compatível com ATOM FlashCut).
    Gera camadas separadas:
    - CONTOUR: Contorno de corte da lâmina
    - PUNCHES: Furações e piques
    - SHEET: Borda da chapa/mesa de material
    """
    dxf_lines = [
        "0", "SECTION",
        "2", "HEADER",
        "9", "$ACADVER",
        "1", "AC1009",
        "0", "ENDSEC",
        "0", "SECTION",
        "2", "TABLES",
        "0", "TABLE",
        "2", "LAYER",
        "70", "3",
        "0", "LAYER", "2", "SHEET", "70", "0", "62", "7", "6", "CONTINUOUS", "0",
        "0", "LAYER", "2", "CONTOUR", "70", "0", "62", "1", "6", "CONTINUOUS", "0",
        "0", "LAYER", "2", "PUNCHES", "70", "0", "62", "3", "6", "CONTINUOUS", "0",
        "0", "ENDTAB",
        "0", "ENDSEC",
        "0", "SECTION",
        "2", "ENTITIES"
    ]

    # Contorno da chapa de material
    mw, mh = material["width_mm"], material["height_mm"]
    sheet_pts = [{"x": 0, "y": 0}, {"x": mw, "y": 0}, {"x": mw, "y": mh}, {"x": 0, "y": mh}]
    dxf_lines.extend(["0", "POLYLINE", "8", "SHEET", "66", "1", "70", "1"])
    for pt in sheet_pts:
        dxf_lines.extend(["0", "VERTEX", "8", "SHEET", "10", f"{pt['x']:.2f}", "20", f"{pt['y']:.2f}", "30", "0.0"])
    dxf_lines.extend(["0", "SEQEND"])

    # Peças
    for p in placed_pieces:
        poly = transform_contour(p["shape"]["contour"], p["x"], p["y"], p["rotation"])
        dxf_lines.extend(["0", "POLYLINE", "8", "CONTOUR", "66", "1", "70", "1"])
        for pt in poly:
            dxf_lines.extend(["0", "VERTEX", "8", "CONTOUR", "10", f"{pt['x']:.2f}", "20", f"{pt['y']:.2f}", "30", "0.0"])
        dxf_lines.extend(["0", "SEQEND"])

        # Furações como círculos DXF
        holes = p["shape"].get("holes", [])
        for h in holes:
            rx, ry = rotate_point(h["x"], h["y"], p["rotation"])
            hx = p["x"] + rx
            hy = p["y"] + ry
            dxf_lines.extend([
                "0", "CIRCLE",
                "8", "PUNCHES",
                "10", f"{hx:.2f}",
                "20", f"{hy:.2f}",
                "30", "0.0",
                "40", "1.5"  # Raio do furo 1.5mm
            ])

    dxf_lines.extend([
        "0", "ENDSEC",
        "0", "EOF"
    ])

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(dxf_lines))

    return file_path

def export_xml_report(order_name, material, placed_pieces, yield_pct, est_time_sec, file_path):
    """
    Gera um relatório de sessão em XML no formato compatível com o JobManager 2000 (Report.xsl).
    """
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<ExBlob>',
        f'  <Session Name="{order_name}" Id="Sx001" Status="Nested" Created="{now}">',
        f'    <SessionMaterial Name="{material["name"]}" GeometryType="{material["type"].capitalize()}" Width="{material["width_mm"]}" Height="{material["height_mm"]}" Thickness="{material["thickness_mm"]}"/>',
        f'    <Results Yield="{yield_pct:.1f}%" TotalPieces="{len(placed_pieces)}" EstimatedTimeSec="{est_time_sec:.1f}"/>',
        '    <Layouts>'
    ]

    for p in placed_pieces:
        xml.append(f'      <Layout DieCode="{p["shape"]["name"]}" Qty="1" X="{p["x"]:.1f}" Y="{p["y"]:.1f}" Rotation="{p["rotation"]}"/>')

    xml.extend([
        '    </Layouts>',
        '  </Session>',
        '</ExBlob>'
    ])

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(xml))

    return file_path
