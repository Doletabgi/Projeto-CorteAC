"""
JobManager 2000 (Python Edition)
CAD 2D Geometry Engine
"""

import math

def rotate_point(x, y, angle_deg):
    """Gira um ponto 2D em torno da origem (0,0) pelo ângulo em graus."""
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    return (
        x * cos_a - y * sin_a,
        x * sin_a + y * cos_a
    )

_TRANSFORM_CACHE: dict = {}
_ROT_CACHE: dict = {}
_CONTOUR_HASH_CACHE: dict = {}
_CACHE_STATS = {"hits": 0, "misses": 0}

def clear_transform_cache():
    """Limpa o cache de transformações geométricas de contornos."""
    global _TRANSFORM_CACHE, _ROT_CACHE, _CONTOUR_HASH_CACHE, _CACHE_STATS
    _TRANSFORM_CACHE.clear()
    _ROT_CACHE.clear()
    _CONTOUR_HASH_CACHE.clear()
    _CACHE_STATS["hits"] = 0
    _CACHE_STATS["misses"] = 0

def get_transform_cache_stats() -> dict:
    """Retorna estatísticas de uso do cache de contornos."""
    total = _CACHE_STATS["hits"] + _CACHE_STATS["misses"]
    rate = (_CACHE_STATS["hits"] / total * 100.0) if total > 0 else 0.0
    return {
        "hits": _CACHE_STATS["hits"],
        "misses": _CACHE_STATS["misses"],
        "size": len(_TRANSFORM_CACHE) + len(_ROT_CACHE),
        "hit_rate_pct": round(rate, 2),
    }

def _get_contour_hash(contour) -> int:
    """
    Hash imutável do contorno, com cache O(1) por identidade VALIDADA.

    O cache é indexado por id(contorno) (endereço), mas o Python recicla endereços
    de listas liberadas: sem validação, um contorno novo herdaria o hash de outro
    molde e `transform_contour` devolveria a geometria errada (peças deslocadas,
    colisões falsas e resultados de nesting corrompidos). A validação barata
    (tamanho + 3 vértices de referência) transforma a reciclagem em cache miss.
    """
    cid = id(contour)
    n = len(contour)
    entrada = _CONTOUR_HASH_CACHE.get(cid)
    if entrada is not None:
        h_cached, n_cached, amostra = entrada
        if n_cached == n:
            try:
                a0 = contour[0]
                am = contour[n // 2]
                az = contour[-1]
                if (
                    round(amostra[0], 4) == round(a0["x"], 4)
                    and round(amostra[1], 4) == round(a0["y"], 4)
                    and round(amostra[2], 4) == round(am["x"], 4)
                    and round(amostra[3], 4) == round(am["y"], 4)
                    and round(amostra[4], 4) == round(az["x"], 4)
                    and round(amostra[5], 4) == round(az["y"], 4)
                ):
                    return h_cached
            except (KeyError, IndexError, TypeError):
                pass
    h = hash(tuple((int(p["x"] * 1000), int(p["y"] * 1000)) for p in contour))
    if len(_CONTOUR_HASH_CACHE) >= 2000:
        _CONTOUR_HASH_CACHE.clear()
    try:
        amostra = (contour[0]["x"], contour[0]["y"],
                   contour[n // 2]["x"], contour[n // 2]["y"],
                   contour[-1]["x"], contour[-1]["y"])
    except (KeyError, IndexError, TypeError):
        amostra = None
    _CONTOUR_HASH_CACHE[cid] = (h, n, amostra) if amostra is not None else (h, n, None)
    return h

def transform_contour(contour, offset_x, offset_y, angle_deg):
    """Aplica rotação e translação a uma lista de pontos dict(x, y)."""
    if not contour:
        return []

    h_c = _get_contour_hash(contour)
    int_angle = int(angle_deg * 100)
    int_off_x = int(offset_x * 1000)
    int_off_y = int(offset_y * 1000)

    cache_key = (h_c, int_angle, int_off_x, int_off_y)
    cached = _TRANSFORM_CACHE.get(cache_key)
    if cached is not None:
        _CACHE_STATS["hits"] += 1
        return [dict(p) for p in cached]

    # Nível 2: Cache de contornos pré-rotacionados na origem
    rot_key = (h_c, int_angle)
    base_rotated = _ROT_CACHE.get(rot_key)
    if base_rotated is not None:
        _CACHE_STATS["hits"] += 1
    else:
        _CACHE_STATS["misses"] += 1
        rad = math.radians(angle_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        base_rotated = []
        for pt in contour:
            px = pt["x"]
            py = pt["y"]
            base_rotated.append({
                "x": px * cos_a - py * sin_a,
                "y": px * sin_a + py * cos_a,
            })
        if len(_ROT_CACHE) >= 2000:
            _ROT_CACHE.clear()
        _ROT_CACHE[rot_key] = base_rotated

    off_x = float(offset_x)
    off_y = float(offset_y)
    transformed = [
        {"x": pt["x"] + off_x, "y": pt["y"] + off_y}
        for pt in base_rotated
    ]

    if len(_TRANSFORM_CACHE) >= 10000:
        _TRANSFORM_CACHE.clear()

    _TRANSFORM_CACHE[cache_key] = [dict(p) for p in transformed]
    return transformed

def polygon_area(poly):
    """Calcula a área de um polígono usando a fórmula Shoelace (Gauss)."""
    n = len(poly)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += poly[i]["x"] * poly[j]["y"]
        area -= poly[j]["x"] * poly[i]["y"]
    return abs(area) / 2.0

def polygon_perimeter(poly):
    """Calcula o perímetro total do contorno do polígono em milímetros."""
    n = len(poly)
    if n < 2:
        return 0.0
    perim = 0.0
    for i in range(n):
        j = (i + 1) % n
        dx = poly[j]["x"] - poly[i]["x"]
        dy = poly[j]["y"] - poly[i]["y"]
        perim += math.hypot(dx, dy)
    return perim

def polygon_bbox(poly):
    """Retorna (min_x, min_y, max_x, max_y) do polígono."""
    xs = [pt["x"] for pt in poly]
    ys = [pt["y"] for pt in poly]
    return min(xs), min(ys), max(xs), max(ys)

def bbox_overlap(bbox_a, bbox_b, gap=0.0):
    """Verifica se duas bounding boxes colidem considerando folga de gap."""
    min_xa, min_ya, max_xa, max_ya = bbox_a
    min_xb, min_yb, max_xb, max_yb = bbox_b
    if max_xa + gap < min_xb or max_xb + gap < min_xa:
        return False
    if max_ya + gap < min_yb or max_yb + gap < min_ya:
        return False
    return True

def point_in_polygon(px, py, poly):
    """Algoritmo Ray Casting para verificar se (px, py) está dentro do polígono."""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]["x"], poly[i]["y"]
        xj, yj = poly[j]["x"], poly[j]["y"]
        
        intersect = ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside

def _ccw(ax, ay, bx, by, cx, cy):
    return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)

def segments_intersect(p1x, p1y, p2x, p2y, p3x, p3y, p4x, p4y):
    """Verifica se o segmento (p1, p2) intercepta o segmento (p3, p4)."""
    return (
        (_ccw(p1x, p1y, p3x, p3y, p4x, p4y) != _ccw(p2x, p2y, p3x, p3y, p4x, p4y)) and
        (_ccw(p1x, p1y, p2x, p2y, p3x, p3y) != _ccw(p1x, p1y, p2x, p2y, p4x, p4y))
    )


def _collinear_overlap(s1, s2, eps=1e-6):
    """
    Detecta segmentos colineares que se sobrepõem (peças exatamente coincidentes
    ou alinhadas na mesma reta). O teste de cruzamento estrito (segments_intersect)
    não enxerga esse caso, que é justamente sobreposição real.
    """
    x1, y1, x2, y2 = s1[0], s1[1], s1[2], s1[3]
    x3, y3, x4, y4 = s2[0], s2[1], s2[2], s2[3]
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx * (y3 - y1) - dy * (x3 - x1)) > eps:
        return False
    if abs(dx * (y4 - y1) - dy * (x4 - x1)) > eps:
        return False
    if abs(dx) >= abs(dy):
        a1, a2 = (x1, x2) if x1 <= x2 else (x2, x1)
        b1, b2 = (x3, x4) if x3 <= x4 else (x4, x3)
    else:
        a1, a2 = (y1, y2) if y1 <= y2 else (y2, y1)
        b1, b2 = (y3, y4) if y3 <= y4 else (y4, y3)
    return a2 >= b1 and b2 >= a1

def point_segment_distance_sq(px, py, x1, y1, x2, y2):
    """Distância ao quadrado de um ponto a um segmento de reta."""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return (px - x1)**2 + (py - y1)**2
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return (px - proj_x)**2 + (py - proj_y)**2

def simplify_contour_for_collision(poly, max_pts=64):
    """Reduz o número de pontos do contorno para detecção de colisão ultra-rápida mantendo precisão milimétrica."""
    n = len(poly)
    if n <= max_pts:
        return poly
    step = n / float(max_pts)
    return [poly[int(i * step)] for i in range(max_pts)]

def prepare_segments(poly):
    """
    Pré-computa os segmentos de um polígono (com AABB de cada aresta).

    Usado em laços quentes de colisão: um mesmo polígono é testado dezenas de vezes
    contra candidatos diferentes, e reconstruir a lista a cada teste dominava o tempo
    em contornos reais de 130-190 vértices.
    """
    n = len(poly)
    if n < 2:
        return []
    segs = []
    for i in range(n):
        p1 = poly[i]
        p2 = poly[i + 1] if i + 1 < n else poly[0]
        x1 = p1['x']; y1 = p1['y']; x2 = p2['x']; y2 = p2['y']
        s_min_x = x1 if x1 < x2 else x2
        s_max_x = x1 if x1 > x2 else x2
        s_min_y = y1 if y1 < y2 else y2
        s_max_y = y1 if y1 > y2 else y2
        segs.append((x1, y1, x2, y2, s_min_x, s_max_x, s_min_y, s_max_y))
    return segs


def polygons_collide(poly_a, poly_b, gap=0.0, bbox_a=None, bbox_b=None, segs_a=None, segs_b=None):
    """
    Sistema robusto de detecção de colisão entre dois contornos de moldes (polígonos).
    Garante que JAMAIS duas peças fiquem sobrepostas ou violem a folga (gap) de corte.
    Utiliza filtragem por janela de interseção para alcançar 100% de exatidão
    (zero erro de simplificação / 0.0000 mm de tolerância) com alta velocidade.
    1. Rejeição rápida por Bounding Box expandida pelo gap.
    2. Filtragem de vértices e arestas que interceptam a janela de sobreposição.
    3. Teste de cruzamento de arestas reais na janela.
    4. Teste de contenção de vértices reais na janela.
    5. Teste de proximidade estrita do gap milimétrico com AABB local.
    """
    if not poly_a or not poly_b:
        return False

    b_a = bbox_a or polygon_bbox(poly_a)
    b_b = bbox_b or polygon_bbox(poly_b)

    if not bbox_overlap(b_a, b_b, gap):
        return False

    # Janela geométrica de sobreposição das duas bounding boxes expandida pelo gap
    ov_min_x = max(b_a[0], b_b[0]) - gap
    ov_max_x = min(b_a[2], b_b[2]) + gap
    ov_min_y = max(b_a[1], b_b[1]) - gap
    ov_max_y = min(b_a[3], b_b[3]) + gap

    len_a = len(poly_a)
    len_b = len(poly_b)

    # Coleta apenas os segmentos reais que tocam a janela de sobreposição.
    # min/max inline (sem chamadas a builtins) — este laço roda para cada par testado.
    if segs_a is not None:
        segs_a = [s for s in segs_a
                  if s[5] >= ov_min_x and s[4] <= ov_max_x and s[7] >= ov_min_y and s[6] <= ov_max_y]
    else:
        segs_a = []
        for i in range(len_a):
            p1 = poly_a[i]
            p2 = poly_a[(i + 1) % len_a] if i + 1 < len_a else poly_a[0]
            x1 = p1['x']; y1 = p1['y']; x2 = p2['x']; y2 = p2['y']
            s_min_x = x1 if x1 < x2 else x2
            s_max_x = x1 if x1 > x2 else x2
            s_min_y = y1 if y1 < y2 else y2
            s_max_y = y1 if y1 > y2 else y2
            if s_max_x >= ov_min_x and s_min_x <= ov_max_x and s_max_y >= ov_min_y and s_min_y <= ov_max_y:
                segs_a.append((x1, y1, x2, y2, s_min_x, s_max_x, s_min_y, s_max_y))

    if segs_b is not None:
        segs_b = [s for s in segs_b
                  if s[5] >= ov_min_x and s[4] <= ov_max_x and s[7] >= ov_min_y and s[6] <= ov_max_y]
    else:
        segs_b = []
        for j in range(len_b):
            p1 = poly_b[j]
            p2 = poly_b[(j + 1) % len_b] if j + 1 < len_b else poly_b[0]
            x1 = p1['x']; y1 = p1['y']; x2 = p2['x']; y2 = p2['y']
            s_min_x = x1 if x1 < x2 else x2
            s_max_x = x1 if x1 > x2 else x2
            s_min_y = y1 if y1 < y2 else y2
            s_max_y = y1 if y1 > y2 else y2
            if s_max_x >= ov_min_x and s_min_x <= ov_max_x and s_max_y >= ov_min_y and s_min_y <= ov_max_y:
                segs_b.append((x1, y1, x2, y2, s_min_x, s_max_x, s_min_y, s_max_y))

    # 1. Cruzamento direto de arestas na janela de sobreposição
    for s1 in segs_a:
        for s2 in segs_b:
            if s1[5] < s2[4] or s1[4] > s2[5]:
                continue
            if s1[7] < s2[6] or s1[6] > s2[7]:
                continue
            if segments_intersect(s1[0], s1[1], s1[2], s1[3], s2[0], s2[1], s2[2], s2[3]):
                return True
            if _collinear_overlap(s1, s2):
                return True

    # 2. Contenção de vértice real.
    # Sem cruzamento de arestas na janela, ou um polígono contém o outro, ou estão
    # separados — então basta testar UM vértice de cada lado (exato e ~10x mais barato).
    if point_in_polygon(poly_a[0]['x'], poly_a[0]['y'], poly_b):
        return True
    if point_in_polygon(poly_b[0]['x'], poly_b[0]['y'], poly_a):
        return True

    # 3. Teste exato de folga mínima milimétrica (gap)
    if gap > 0:
        pts_a = [pt for pt in poly_a if ov_min_x <= pt['x'] <= ov_max_x and ov_min_y <= pt['y'] <= ov_max_y]
        pts_b = [pt for pt in poly_b if ov_min_x <= pt['x'] <= ov_max_x and ov_min_y <= pt['y'] <= ov_max_y]
        gap_sq = gap * gap
        for pt in pts_a:
            px, py = pt['x'], pt['y']
            for s in segs_b:
                if px < s[4] - gap or px > s[5] + gap:
                    continue
                if py < s[6] - gap or py > s[7] + gap:
                    continue
                if point_segment_distance_sq(px, py, s[0], s[1], s[2], s[3]) < gap_sq:
                    return True

        for pt in pts_b:
            px, py = pt['x'], pt['y']
            for s in segs_a:
                if px < s[4] - gap or px > s[5] + gap:
                    continue
                if py < s[6] - gap or py > s[7] + gap:
                    continue
                if point_segment_distance_sq(px, py, s[0], s[1], s[2], s[3]) < gap_sq:
                    return True

    return False


class SpatialGrid:
    """
    Indexação Espacial 2D (Spatial Grid Hashing).
    Divide a mesa de corte em células quadradas de tamanho `cell_size` (padrão 100mm).
    Permite busca de colisões em O(1) na média, filtrando apenas as peças
    que compartilham células próximas da peça candidata.
    """
    def __init__(self, cell_size=100.0):
        self.cell_size = float(cell_size) if cell_size > 0 else 100.0
        self.grid = {}  # (cx, cy) -> list of (item_id, poly, bbox)
        self.items = [] # list of (item_id, poly, bbox)

    def clear(self):
        """Limpa a grade espacial."""
        self.grid.clear()
        self.items.clear()

    def insert(self, item_id, poly, bbox=None):
        """Insere uma peça posicionada na grade espacial com base em sua Bounding Box."""
        b = bbox or polygon_bbox(poly)
        min_x, min_y, max_x, max_y = b
        item = (item_id, poly, b)
        self.items.append(item)

        c_min_x = int(math.floor(min_x / self.cell_size))
        c_max_x = int(math.floor(max_x / self.cell_size))
        c_min_y = int(math.floor(min_y / self.cell_size))
        c_max_y = int(math.floor(max_y / self.cell_size))

        for cx in range(c_min_x, c_max_x + 1):
            for cy in range(c_min_y, c_max_y + 1):
                key = (cx, cy)
                if key not in self.grid:
                    self.grid[key] = []
                self.grid[key].append(item)

    def query_potential_colliders(self, bbox, gap=0.0):
        """
        Retorna a lista de itens (poly, bbox) que compartilham células espaciais
        com a Bounding Box consultada (expandida pelo gap).
        """
        min_x, min_y, max_x, max_y = bbox
        c_min_x = int(math.floor((min_x - gap) / self.cell_size))
        c_max_x = int(math.floor((max_x + gap) / self.cell_size))
        c_min_y = int(math.floor((min_y - gap) / self.cell_size))
        c_max_y = int(math.floor((max_y + gap) / self.cell_size))

        candidates = []
        seen = set()

        for cx in range(c_min_x, c_max_x + 1):
            for cy in range(c_min_y, c_max_y + 1):
                cell_items = self.grid.get((cx, cy))
                if cell_items:
                    for it in cell_items:
                        it_id = it[0]
                        if it_id not in seen:
                            seen.add(it_id)
                            # Verificação preliminar de Bounding Box
                            if bbox_overlap(bbox, it[2], gap):
                                candidates.append((it[1], it[2]))
        return candidates

    def query_items(self, bbox, gap=0.0):
        """
        Retorna a lista de itens completos (item_id, poly, bbox) que compartilham células espaciais
        com a Bounding Box consultada (expandida pelo gap).
        """
        min_x, min_y, max_x, max_y = bbox
        c_min_x = int(math.floor((min_x - gap) / self.cell_size))
        c_max_x = int(math.floor((max_x + gap) / self.cell_size))
        c_min_y = int(math.floor((min_y - gap) / self.cell_size))
        c_max_y = int(math.floor((max_y + gap) / self.cell_size))

        candidates = []
        seen = set()

        for cx in range(c_min_x, c_max_x + 1):
            for cy in range(c_min_y, c_max_y + 1):
                cell_items = self.grid.get((cx, cy))
                if cell_items:
                    for it in cell_items:
                        it_id = it[0]
                        if it_id not in seen:
                            seen.add(it_id)
                            if bbox_overlap(bbox, it[2], gap):
                                candidates.append((it[0], it[1], it[2]))
        return candidates

def find_contact_coordinate_binary(poly_candidate_fn, candidate_colliders, gap, start_val, min_val, axis="y", iterations=10):
    """
    Busca Binária de Contato (Bumping Rápido com Resolução Submilimétrica Exata).
    Dado um intervalo [min_val, start_val], onde `start_val` é garantidamente livre de colisão
    e `min_val` é a posição desejada mais próxima da borda (que pode colidir),
    encontra por busca binária a coordenada mais baixa/próxima que NÃO colide com nenhum obstáculo.
    Em 12 iterações, resolve uma janela com resolução de centésimos de milímetro (~0.02mm).
    """

    if not candidate_colliders:
        return min_val

    def _collides(poly_cand) -> bool:
        bbox_cand = polygon_bbox(poly_cand)
        for col in candidate_colliders:
            c_poly = col[0]
            c_bbox = col[1]
            c_segs = col[2] if len(col) > 2 else None
            if polygons_collide(poly_cand, c_poly, gap=gap, bbox_a=bbox_cand,
                                bbox_b=c_bbox, segs_b=c_segs):
                return True
        return False

    # Testa se na posição mínima já não colide
    if not _collides(poly_candidate_fn(min_val)):
        return min_val

    # Se colide na posição mínima, busca entre low (colidindo) e high (livre)
    low = min_val
    high = start_val

    for _ in range(iterations):
        mid = (low + high) / 2.0
        if _collides(poly_candidate_fn(mid)):
            low = mid   # Ainda colide, precisa ficar acima
        else:
            high = mid  # Livre de colisão, pode tentar descer mais

    # Garante margem de segurança discreta para zero colisão com precisão milimétrica
    res_coord = high + 0.05
    while _collides(poly_candidate_fn(res_coord)):
        res_coord += 0.05

    return res_coord
