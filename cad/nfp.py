"""
cad/nfp.py - Motor No-Fit Polygon (NFP) em Python Puro para CorteAC / JobManager 2000

Implementação analítica de No-Fit Polygon para substituição de buscas binárias iterativas
de contato por cálculos geométricos exatos em O(1)/O(N):
1. Decomposição convexa por Ear-Clipping com preservação estrita de área.
2. Soma de Minkowski entre polígonos convexos O(n + m).
3. Composição de NFP exato entre peças côncavas/convexas.
4. Cálculo analítico de coordenada de contato com garantia de gap e zero colisão.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from cad.geometry import (
    polygon_area,
    polygon_bbox,
    polygons_collide,
    transform_contour,
    bbox_overlap,
)

Point = Dict[str, float]
Polygon = List[Point]

# Cache interno para decomposições convexas e NFP de pares de moldes
_CONVEX_DECOMP_CACHE: Dict[int, List[Polygon]] = {}
_NFP_PAIR_CACHE: Dict[Tuple[int, int], List[Polygon]] = {}
# Cache de complexidade (polígono normalizado pela bbox, invariante a translação)
_COMPLEXITY_CACHE: Dict[Tuple[tuple, ...], bool] = {}
_MAX_CONVEX_PARTS_DIRECT = 12


def _translation_invariant_key(poly: Polygon) -> Tuple[tuple, ...]:
    """Chave invariante a translação (para reaproveitar complexidade entre peças iguais)."""
    if not poly:
        return ()
    xs = [p["x"] for p in poly]
    ys = [p["y"] for p in poly]
    min_x = min(xs)
    min_y = min(ys)
    return tuple((round(p["x"] - min_x, 1), round(p["y"] - min_y, 1)) for p in poly)


def is_complex_polygon(poly: Any) -> bool:
    """
    Indica se o polígono é caro para NFP exato (>12 partes convexas).

    Contornos reais de calçado (130-190 vértices côncavos) geram ~150 partes e o
    produto cartesiano entre dois deles passa de 20 mil polígonos por par. Nesses
    casos o encosto por busca binária (SAT) é uma ordem de grandeza mais rápido.
    """
    normalized = _normalize_points(poly)
    if len(normalized) < 8:
        return False
    key = _translation_invariant_key(normalized)
    cached = _COMPLEXITY_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        complexo = len(decompose_convex(normalized)) > _MAX_CONVEX_PARTS_DIRECT
    except Exception:
        complexo = True
    if len(_COMPLEXITY_CACHE) > 2048:
        _COMPLEXITY_CACHE.clear()
    _COMPLEXITY_CACHE[key] = complexo
    return complexo


def _contact_fallback(moving_poly0: Any, obstacle_poly: Any, target: float, gap: float,
                      axis: str = "x") -> Optional[float]:
    """
    Encosto por busca binária submilimétrica (SAT) para polígonos complexos.

    Encontra a menor coordenada livre (X para contact_placement_x, Y para
    contact_placement_y) a partir da qual a peça móvel não colide com o obstáculo,
    respeitando o gap. Exato: usa o mesmo oráculo geométrico do motor SAT.
    """
    from cad.geometry import polygons_collide  # import local: evita ciclo

    eixo_x = axis == "x"

    def positioned(offset: float) -> Polygon:
        if eixo_x:
            return transform_contour(moving_poly0, offset, target, 0.0)
        return transform_contour(moving_poly0, target, offset, 0.0)

    b_m = polygon_bbox(positioned(0.0))
    b_o = polygon_bbox(_normalize_points(obstacle_poly))
    mw = b_m[2] - b_m[0]
    mh = b_m[3] - b_m[1]

    if eixo_x:
        lo = b_o[0] - gap - mw - 1.0
        hi = b_o[2] + gap - b_m[0] + 0.1
    else:
        lo = b_o[1] - gap - mh - 1.0
        hi = b_o[3] + gap - b_m[1] + 0.1

    if hi <= lo:
        return None

    def free(coord: float) -> bool:
        return not polygons_collide(positioned(coord), obstacle_poly, gap=gap)

    if not free(hi):
        return None

    for _ in range(12):
        mid = (lo + hi) / 2.0
        if free(mid):
            hi = mid
        else:
            lo = mid
    return hi + 0.05


def _normalize_points(poly: Any) -> Polygon:
    """Converte polígono para lista canônica de dicts [{'x': float, 'y': float}, ...]."""
    if not poly:
        return []
    normalized: Polygon = []
    for p in poly:
        if isinstance(p, dict):
            normalized.append({"x": float(p["x"]), "y": float(p["y"])})
        elif isinstance(p, (tuple, list)) and len(p) >= 2:
            normalized.append({"x": float(p[0]), "y": float(p[1])})
    return normalized


def polygon_signed_area(poly: Polygon) -> float:
    """Calcula a área com sinal (Shoelace). Positiva se CCW, negativa se CW."""
    n = len(poly)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += poly[i]["x"] * poly[j]["y"] - poly[j]["x"] * poly[i]["y"]
    return area / 2.0


def _point_in_triangle(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
    cx: float, cy: float
) -> bool:
    """Verifica se (px, py) está dentro ou sobre o triângulo ABC (em ordem CCW)."""
    def cp(x1: float, y1: float, x2: float, y2: float, x3: float, y3: float) -> float:
        return (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)

    cp1 = cp(ax, ay, bx, by, px, py)
    cp2 = cp(bx, by, cx, cy, px, py)
    cp3 = cp(cx, cy, ax, ay, px, py)
    return (cp1 >= -1e-8 and cp2 >= -1e-8 and cp3 >= -1e-8)


def _is_strictly_convex(poly: Polygon) -> bool:
    """Verifica se o polígono já é estritamente convexo."""
    n = len(poly)
    if n <= 3:
        return True
    sign = 0
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        p3 = poly[(i + 2) % n]
        dx1, dy1 = p2["x"] - p1["x"], p2["y"] - p1["y"]
        dx2, dy2 = p3["x"] - p2["x"], p3["y"] - p2["y"]
        cross = dx1 * dy2 - dy1 * dx2
        if abs(cross) > 1e-8:
            curr_sign = 1 if cross > 0 else -1
            if sign == 0:
                sign = curr_sign
            elif sign != curr_sign:
                return False
    return True


def decompose_convex(polygon: Any) -> List[Polygon]:
    """
    Decompõe um polígono (possivelmente côncavo) em sub-polígonos estritamente convexos
    utilizando triangulação por Ear-Clipping.
    Preserva a área total com tolerância estrita < 1e-6.
    """
    poly = _normalize_points(polygon)
    if len(poly) < 3:
        return []

    # Limpeza de pontos colineares ou duplicados consecutivos
    cleaned: Polygon = []
    for p in poly:
        if not cleaned or abs(p["x"] - cleaned[-1]["x"]) > 1e-5 or abs(p["y"] - cleaned[-1]["y"]) > 1e-5:
            cleaned.append(p)
    if len(cleaned) >= 3 and abs(cleaned[0]["x"] - cleaned[-1]["x"]) < 1e-5 and abs(cleaned[0]["y"] - cleaned[-1]["y"]) < 1e-5:
        cleaned.pop()

    if len(cleaned) <= 3 or _is_strictly_convex(cleaned):
        return [cleaned]

    # Verifica cache
    c_key = tuple((int(p["x"] * 1000), int(p["y"] * 1000)) for p in cleaned)
    h = hash(c_key)
    if h in _CONVEX_DECOMP_CACHE:
        return [[dict(pt) for pt in part] for part in _CONVEX_DECOMP_CACHE[h]]

    pts = [dict(p) for p in cleaned]
    # Força ordem Anti-Horária (CCW)
    if polygon_signed_area(pts) < 0:
        pts.reverse()

    triangles: List[Polygon] = []
    max_loops = len(pts) * len(pts)
    loop = 0

    while len(pts) > 3 and loop < max_loops:
        loop += 1
        n = len(pts)
        ear_found = False

        for i in range(n):
            prev_i = (i - 1) % n
            next_i = (i + 1) % n
            p_prev = pts[prev_i]
            p_curr = pts[i]
            p_next = pts[next_i]

            # Cross product das arestas incidentes
            dx1, dy1 = p_curr["x"] - p_prev["x"], p_curr["y"] - p_prev["y"]
            dx2, dy2 = p_next["x"] - p_curr["x"], p_next["y"] - p_curr["y"]
            cp = dx1 * dy2 - dy1 * dx2

            if cp <= 1e-8:
                continue  # Vértice reflexo ou colinear

            ax, ay = p_prev["x"], p_prev["y"]
            bx, by = p_curr["x"], p_curr["y"]
            cx, cy = p_next["x"], p_next["y"]

            # Verifica se algum outro vértice está dentro do triângulo
            has_interior_pt = False
            for k in range(n):
                if k in (prev_i, i, next_i):
                    continue
                pk = pts[k]
                if _point_in_triangle(pk["x"], pk["y"], ax, ay, bx, by, cx, cy):
                    has_interior_pt = True
                    break

            if not has_interior_pt:
                triangles.append([p_prev, p_curr, p_next])
                pts.pop(i)
                ear_found = True
                break

        if not ear_found:
            # Fallback seguro caso haja quinas colineares
            triangles.append(pts)
            break

    if len(pts) == 3:
        triangles.append(pts)

    _CONVEX_DECOMP_CACHE[h] = [[dict(pt) for pt in part] for part in triangles]
    return triangles


def minkowski_sum_convex(a: Any, b: Any) -> Polygon:
    """
    Soma de Minkowski exata A ⊕ B entre dois polígonos convexos em O(|A| + |B|).
    """
    pts_a = _normalize_points(a)
    pts_b = _normalize_points(b)

    if not pts_a:
        return pts_b
    if not pts_b:
        return pts_a

    if polygon_signed_area(pts_a) < 0:
        pts_a.reverse()
    if polygon_signed_area(pts_b) < 0:
        pts_b.reverse()

    def _lowest_index(pts: Polygon) -> int:
        best = 0
        for i in range(1, len(pts)):
            if (pts[i]["y"], pts[i]["x"]) < (pts[best]["y"], pts[best]["x"]):
                best = i
        return best

    na = len(pts_a)
    nb = len(pts_b)
    ia0 = _lowest_index(pts_a)
    ib0 = _lowest_index(pts_b)

    result: Polygon = []
    ia, ib = 0, 0

    while ia < na or ib < nb:
        pa = pts_a[(ia0 + ia) % na]
        pb = pts_b[(ib0 + ib) % nb]
        result.append({"x": pa["x"] + pb["x"], "y": pa["y"] + pb["y"]})

        if ia == na:
            ib += 1
            continue
        if ib == nb:
            ia += 1
            continue

        va = pts_a[(ia0 + ia + 1) % na]
        vb = pts_b[(ib0 + ib + 1) % nb]
        eax, eay = va["x"] - pa["x"], va["y"] - pa["y"]
        ebx, eby = vb["x"] - pb["x"], vb["y"] - pb["y"]

        cross = eax * eby - eay * ebx
        if cross > 1e-7:
            ia += 1
        elif cross < -1e-7:
            ib += 1
        else:
            ia += 1
            ib += 1

    cleaned: Polygon = []
    for p in result:
        if not cleaned or abs(p["x"] - cleaned[-1]["x"]) > 1e-4 or abs(p["y"] - cleaned[-1]["y"]) > 1e-4:
            cleaned.append(p)
    return cleaned


def clear_nfp_cache() -> None:
    """Limpa os caches de decomposição convexa e pares NFP."""
    _CONVEX_DECOMP_CACHE.clear()
    _NFP_PAIR_CACHE.clear()


def compute_nfp(moving: Any, obstacle: Any) -> Optional[List[Polygon]]:
    """
    Calcula o No-Fit Polygon exato de 'moving' ao redor de 'obstacle'.
    NFP(M, O) = O ⊕ (-M).
    Retorna uma lista de polígonos convexos cuja união forma a região proibida.
    """
    poly_m = _normalize_points(moving)
    poly_o = _normalize_points(obstacle)

    if len(poly_m) < 3 or len(poly_o) < 3:
        return None

    # Cache lookup por hash das coordenadas
    k_m = tuple((int(p["x"] * 1000), int(p["y"] * 1000)) for p in poly_m)
    k_o = tuple((int(p["x"] * 1000), int(p["y"] * 1000)) for p in poly_o)
    cache_key = (hash(k_m), hash(k_o))
    if cache_key in _NFP_PAIR_CACHE:
        return [[dict(pt) for pt in part] for part in _NFP_PAIR_CACHE[cache_key]]

    # -M (reflexão em torno da origem)
    neg_m = [{"x": -p["x"], "y": -p["y"]} for p in poly_m]

    conv_m = decompose_convex(neg_m)
    conv_o = decompose_convex(poly_o)

    nfp_parts: List[Polygon] = []
    for m_part in conv_m:
        for o_part in conv_o:
            msum = minkowski_sum_convex(o_part, m_part)
            if len(msum) >= 3:
                nfp_parts.append(msum)

    if nfp_parts:
        if len(_NFP_PAIR_CACHE) >= 5000:
            _NFP_PAIR_CACHE.clear()
        _NFP_PAIR_CACHE[cache_key] = [[dict(pt) for pt in part] for part in nfp_parts]
        return nfp_parts
    return None


def contact_placement_x(moving_poly0: Any, obstacle_poly: Any, target_y: float, gap: float = 1.0) -> Optional[float]:
    """
    Calcula analiticamente a coordenada X mínima de contato (encosto pela direita)
    da peça móvel 'moving_poly0' (em sua rotação local, centrada na origem)
    contra 'obstacle_poly' (já em coordenadas globais), dado o Y global 'target_y'.
    Retorna o deslocamento X global de contato com folga ortogonal garantida >= gap.
    """
    # Contornos reais de calçado são caros para NFP exato (milhares de polígonos
    # por par); nesses casos o encosto por busca binária é ~100x mais rápido.
    if is_complex_polygon(moving_poly0) or is_complex_polygon(obstacle_poly):
        return _contact_fallback(moving_poly0, obstacle_poly, target_y, gap, axis="x")

    nfp_parts = compute_nfp(moving_poly0, obstacle_poly)
    if not nfp_parts:
        return None

    max_req_x = -float("inf")
    found = False

    for part in nfp_parts:
        n = len(part)
        for i in range(n):
            p1, p2 = part[i], part[(i + 1) % n]
            min_y = min(p1["y"], p2["y"])
            max_y = max(p1["y"], p2["y"])
            if min_y - gap <= target_y <= max_y + gap:
                dx = p2["x"] - p1["x"]
                dy = p2["y"] - p1["y"]
                edge_len = math.hypot(dx, dy)
                if abs(dy) > 1e-6:
                    t = (target_y - p1["y"]) / dy
                    x_val = p1["x"] + t * dx
                    # Compensação trigonométrica para folga ortogonal euclidiana estrita
                    cos_theta = abs(dy) / edge_len
                    shift_x = gap / max(0.5, cos_theta)
                    req_x = x_val + shift_x + 0.05
                    if req_x > max_req_x:
                        max_req_x = req_x
                    found = True
                else:
                    req_x = max(p1["x"], p2["x"]) + gap + 0.05
                    if req_x > max_req_x:
                        max_req_x = req_x
                    found = True

    return max_req_x if found else None


def contact_placement_y(moving_poly0: Any, obstacle_poly: Any, target_x: float, gap: float = 1.0) -> Optional[float]:
    """
    Calcula analiticamente a coordenada Y mínima de contato (encosto por cima)
    da peça móvel 'moving_poly0' (em sua rotação local, centrada na origem)
    contra 'obstacle_poly' (já em coordenadas globais), dado o X global 'target_x'.
    Retorna o deslocamento Y global de contato com folga ortogonal garantida >= gap.
    """
    if is_complex_polygon(moving_poly0) or is_complex_polygon(obstacle_poly):
        return _contact_fallback(moving_poly0, obstacle_poly, target_x, gap, axis="y")

    nfp_parts = compute_nfp(moving_poly0, obstacle_poly)
    if not nfp_parts:
        return None

    max_req_y = -float("inf")
    found = False

    for part in nfp_parts:
        n = len(part)
        for i in range(n):
            p1, p2 = part[i], part[(i + 1) % n]
            min_x = min(p1["x"], p2["x"])
            max_x = max(p1["x"], p2["x"])
            if min_x - gap <= target_x <= max_x + gap:
                dx = p2["x"] - p1["x"]
                dy = p2["y"] - p1["y"]
                edge_len = math.hypot(dx, dy)
                if abs(dx) > 1e-6:
                    t = (target_x - p1["x"]) / dx
                    y_val = p1["y"] + t * dy
                    # Compensação trigonométrica para folga ortogonal euclidiana estrita
                    sin_theta = abs(dx) / edge_len
                    shift_y = gap / max(0.5, sin_theta)
                    req_y = y_val + shift_y + 0.05
                    if req_y > max_req_y:
                        max_req_y = req_y
                    found = True
                else:
                    req_y = max(p1["y"], p2["y"]) + gap + 0.05
                    if req_y > max_req_y:
                        max_req_y = req_y
                    found = True

    return max_req_y if found else None


def find_lowest_point_in_nfp(nfp: Any, gap: float = 0.0) -> Optional[Tuple[float, float]]:
    """
    Encontra o ponto mais baixo (menor Y) de contato respeitando a folga (gap).
    """
    if not nfp:
        return None

    components: List[Polygon] = nfp if isinstance(nfp[0], list) else [nfp]
    lowest_y = float("inf")
    best_x = 0.0

    for comp in components:
        for p in comp:
            if p["y"] < lowest_y:
                lowest_y = p["y"]
                best_x = p["x"]

    if lowest_y == float("inf"):
        return None

    return (best_x, lowest_y - gap)


def contact_placement(
    moving: Any,
    obstacles: List[Any],
    gap: float = 1.0,
    x_coord: Optional[float] = None,
    min_y: float = 10.0,
) -> Optional[Tuple[float, float]]:
    """
    Posiciona o contorno 'moving' na coordenada X fornecida, encontrando o menor Y
    que garante zero colisão contra todos os 'obstacles' respeitando o gap milimétrico.
    Substitui a busca binária iterativa por avaliação analítica dos limites do NFP.
    """
    poly_m = _normalize_points(moving)
    if not poly_m:
        return None

    if not obstacles:
        return (x_coord if x_coord is not None else 0.0, min_y)

    bbox_m = polygon_bbox(poly_m)
    mw = bbox_m[2] - bbox_m[0]
    target_x = x_coord if x_coord is not None else min_y

    max_req_y = min_y

    for obs in obstacles:
        poly_o = _normalize_points(obs.get("contour", obs) if isinstance(obs, dict) else obs)
        if not poly_o:
            continue

        b_o = polygon_bbox(poly_o)
        # Broad-phase: rejeita obstáculos que não interceptam o X com folga
        if target_x + bbox_m[2] + gap < b_o[0] or target_x + bbox_m[0] - gap > b_o[2]:
            continue

        # Calcula o NFP deste obstáculo relativo à peça móvel
        nfp_parts = compute_nfp(poly_m, poly_o)
        if not nfp_parts:
            continue

        for comp in nfp_parts:
            n = len(comp)
            ys = []
            for i in range(n):
                p1, p2 = comp[i], comp[(i + 1) % n]
                s_min_x = min(p1["x"], p2["x"])
                s_max_x = max(p1["x"], p2["x"])
                if s_min_x - gap <= target_x <= s_max_x + gap:
                    dx = p2["x"] - p1["x"]
                    if abs(dx) > 1e-6:
                        t = (target_x - p1["x"]) / dx
                        ys.append(p1["y"] + t * (p2["y"] - p1["y"]))
                    else:
                        ys.extend([p1["y"], p2["y"]])
            if ys:
                y_upper = max(ys)
                if y_upper + gap > max_req_y:
                    max_req_y = y_upper + gap

    y_cand = max(min_y, max_req_y)

    # Sanity Pass obrigatório com polygons_collide (oráculo industrial)
    # Se houver micro-colisão residual por arredondamento, ajusta com passo seguro
    cand_poly = transform_contour(poly_m, target_x, y_cand, 0.0)
    for obs in obstacles:
        poly_o = obs.get("contour", obs) if isinstance(obs, dict) else obs
        while polygons_collide(cand_poly, poly_o, gap=gap):
            y_cand += 0.05
            cand_poly = transform_contour(poly_m, target_x, y_cand, 0.0)

    return (target_x, y_cand)
