"""Piques manuais incorporados ao contorno, em milímetros.

Equivalente funcional da ferramenta de simbólica; não interpreta comandos .smb.
As proporções de referência vêm de conf/_standard_.smk da Comelz.
"""
import copy
import math
import re


SYMBOL_TYPES = {
    "Pique pequeno (4,5 × 1 mm)": [(4.5, 1.0)],
    "Pique grande (7 × 2 mm)": [(7.0, 2.0)],
    "Duplo pequeno": [(4.5, 1.0), (4.5, 1.0)],
    "Por tamanho (último dígito)": None,
}


def symbol_pattern(kind, size=""):
    if kind not in SYMBOL_TYPES:
        raise ValueError("Selecione um tipo de simbólica.")
    pattern = SYMBOL_TYPES[kind]
    if pattern is not None:
        return list(pattern)
    text = str(size).strip()
    if not re.fullmatch(r"\d+", text):
        raise ValueError("Simbólica por tamanho requer tamanho inteiro. Escolha um pique manual para outros tamanhos.")
    digit = int(text[-1])
    small, large = (4.5, 1.0), (7.0, 2.0)
    return [large, large] if digit == 0 else ([large] if digit >= 5 else []) + [small] * (digit % 5)


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def _intersects(a, b, c, d):
    """Inclui contato e sobreposição de segmentos não adjacentes."""
    eps = 1e-8
    if max(a[0], b[0]) < min(c[0], d[0])-eps or max(c[0], d[0]) < min(a[0], b[0])-eps:
        return False
    if max(a[1], b[1]) < min(c[1], d[1])-eps or max(c[1], d[1]) < min(a[1], b[1])-eps:
        return False
    ab_c, ab_d, cd_a, cd_b = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    return ((ab_c <= eps and ab_d >= -eps) or (ab_d <= eps and ab_c >= -eps)) and ((cd_a <= eps and cd_b >= -eps) or (cd_b <= eps and cd_a >= -eps))


def insert_symbol(contour, x, y, kind, size="", max_distance=8.0):
    """Retorna novo contorno e os pontos inseridos; nunca altera a entrada.

    Projeta o clique na aresta mais próxima, orienta os V para dentro e rejeita
    cantos sem espaço e interseções. O grupo inteiro é uma única operação.
    """
    pattern = symbol_pattern(kind, size)
    try:
        pts = [(float(p["x"]), float(p["y"])) for p in contour]
        x, y, max_distance = float(x), float(y), float(max_distance)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Contorno ou posição inválidos.") from exc
    if not all(math.isfinite(v) for p in pts for v in p) or not all(math.isfinite(v) for v in (x, y, max_distance)) or max_distance <= 0:
        raise ValueError("Coordenadas e tolerância devem ser finitas e válidas.")
    closed = len(pts) > 1 and pts[0] == pts[-1]
    if closed:
        pts.pop()
    n = len(pts)
    if n < 3:
        raise ValueError("É necessário um contorno com pelo menos três vértices.")
    area2 = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(pts, pts[1:]+pts[:1]))
    if abs(area2) < 1e-8:
        raise ValueError("O contorno não possui área válida.")
    best = None
    for i, (a, b) in enumerate(zip(pts, pts[1:]+pts[:1])):
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = math.hypot(dx, dy)
        if length < 1e-8:
            continue
        t = min(1.0, max(0.0, ((x-a[0])*dx+(y-a[1])*dy)/(length*length)))
        qx, qy = a[0]+t*dx, a[1]+t*dy
        candidate = (math.hypot(x-qx, y-qy), i, t*length, length, dx/length, dy/length)
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best is None or best[0] > max_distance:
        raise ValueError("Clique próximo à borda da peça para adicionar a simbólica.")
    _, edge, center, length, ux, uy = best
    spacing = 1.0
    width = sum(w for w, _ in pattern) + spacing*(len(pattern)-1)
    start = center-width/2
    if start <= 1e-6 or start+width >= length-1e-6:
        raise ValueError("A simbólica não cabe nesta aresta. Clique mais longe do canto ou escolha um pique menor.")
    sign = 1 if area2 > 0 else -1
    nx, ny = -uy*sign, ux*sign
    ax, ay = pts[edge]
    added = []
    for w, depth in pattern:
        for along, inward in ((start, 0), (start+w/2, depth), (start+w, 0)):
            added.append({"x": ax+along*ux+inward*nx, "y": ay+along*uy+inward*ny,
                          "symbolic_notch": True})
        start += w+spacing
    raw = copy.deepcopy(list(contour[:-1] if closed else contour))
    result = raw[:edge+1] + added + raw[edge+1:]
    xy = [(p["x"], p["y"]) for p in result]
    m = len(xy)
    for i in range(m):
        for j in range(i+2, m):
            if i == 0 and j == m-1:
                continue
            if _intersects(xy[i], xy[(i+1)%m], xy[j], xy[(j+1)%m]):
                raise ValueError("A simbólica cruzaria outro trecho do contorno. Escolha outra posição.")
    if closed:
        result.append(copy.deepcopy(result[0]))
    return result, added
