"""
JobManager 2000 (Python Edition)
cad/macro_engine.py - Motor de Cálculo por Macros Declarativas & IA Local Embarcada "IA-teste"

Componentes:
1. SafeFormulaEvaluator: Avaliador seguro de fórmulas via ast puro (sem eval inseguro).
2. MacroCompiler: Parser da DSL declarativa de macros de nesting.
3. OmniNestMacroEngine: Motor de execução de macros com compactação vetorial contínua,
   micro-rotações (Jiggle), preenchimento de vazios e auto-calibração por IA Local (NestingAIBrain).
4. nest_ia_teste_engine: Ponto de entrada padrão para a estratégia "IA-teste".
"""

import os
import ast
import re
import math
import operator
from typing import List, Dict, Any, Optional, Tuple, Callable, Union

from cad.geometry import (
    rotate_point, transform_contour, polygon_area, polygon_perimeter, polygon_bbox,
    bbox_overlap, polygons_collide, SpatialGrid, find_contact_coordinate_binary
)
from cad.nfp import contact_placement_x
from cad.colors import get_color_for_size
from cad.ai_learner import ShapeFeatureExtractor, NestingAIBrain


_DX_SEP_CACHE: Dict[Tuple[int, float, int, float, float], float] = {}
_POLY0_CACHE: Dict[Tuple[int, float], Any] = {}


def clear_macro_caches() -> None:
    """Limpa os caches de NFP analítico horizontal e contornos base pré-calculados."""
    _DX_SEP_CACHE.clear()
    _POLY0_CACHE.clear()


def ramer_douglas_peucker(points: List[Any], epsilon: float = 0.2) -> List[Any]:
    """
    Simplifica contorno poligonal usando o algoritmo Ramer-Douglas-Peucker (RDP).
    Aplicado apenas em contornos complexos (> 50 vértices) durante cálculo de contato e NFP.
    Preserva o contorno original intacto para renderização e exportação .lay.
    """
    if os.getenv("CORTEAC_RDP_DISABLED", "0") == "1" or len(points) <= 3:
        return points

    def perpendicular_distance(pt, line_start, line_end):
        x0 = pt["x"] if isinstance(pt, dict) else pt[0]
        y0 = pt["y"] if isinstance(pt, dict) else pt[1]
        x1 = line_start["x"] if isinstance(line_start, dict) else line_start[0]
        y1 = line_start["y"] if isinstance(line_start, dict) else line_start[1]
        x2 = line_end["x"] if isinstance(line_end, dict) else line_end[0]
        y2 = line_end["y"] if isinstance(line_end, dict) else line_end[1]
        dx = x2 - x1
        dy = y2 - y1
        mag_sq = dx * dx + dy * dy
        if mag_sq < 1e-12:
            return math.hypot(x0 - x1, y0 - y1)
        return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / math.sqrt(mag_sq)

    def _rdp(pts):
        if len(pts) <= 2:
            return pts
        dmax = 0.0
        index = 0
        for i in range(1, len(pts) - 1):
            d = perpendicular_distance(pts[i], pts[0], pts[-1])
            if d > dmax:
                index = i
                dmax = d
        if dmax > epsilon:
            rec1 = _rdp(pts[:index + 1])
            rec2 = _rdp(pts[index:])
            return rec1[:-1] + rec2
        else:
            return [pts[0], pts[-1]]

    pt0 = points[0]
    pt_last = points[-1]
    x0 = pt0["x"] if isinstance(pt0, dict) else pt0[0]
    y0 = pt0["y"] if isinstance(pt0, dict) else pt0[1]
    xl = pt_last["x"] if isinstance(pt_last, dict) else pt_last[0]
    yl = pt_last["y"] if isinstance(pt_last, dict) else pt_last[1]
    is_closed = math.hypot(x0 - xl, y0 - yl) < 1e-5

    if is_closed and len(points) > 4:
        pts = points[:-1] if is_closed else points
        half = len(pts) // 2
        p1 = _rdp(pts[:half + 1])
        p2 = _rdp(pts[half:] + [pts[0]])
        return p1[:-1] + p2
    return _rdp(points)


def _find_best_horizontal_slot_nfp(piece: Any, row_obstacles: List[Any], gap: float = 1.0) -> float:
    """
    Encontra X onde a peça móvel encosta na fileira de obstáculos.
    Usa NFP analítico como chute inicial + loop de convergência via SAT (máximo 20 iterações)
    para garantir zero colisão em contornos côncavos, com fallback seguro para find_contact_coordinate_binary.
    """
    if not row_obstacles:
        return 0.0

    if isinstance(piece, dict):
        piece_poly = piece.get("poly") or piece.get("contour", [])
    else:
        piece_poly = piece

    if not piece_poly:
        return 0.0

    b_m = polygon_bbox(piece_poly)
    w_m = b_m[2] - b_m[0]
    h_m = b_m[3] - b_m[1]
    m_norm = [{"x": p["x"] - b_m[0], "y": p["y"] - b_m[1]} for p in piece_poly]

    norm_obs = []
    for obs in row_obstacles:
        if isinstance(obs, dict):
            p = obs.get("poly") or obs.get("contour", [])
            b = obs.get("bbox") or polygon_bbox(p)
            norm_obs.append((p, b))
        elif isinstance(obs, (tuple, list)) and len(obs) == 2 and isinstance(obs[1], (tuple, list)):
            norm_obs.append((obs[0], obs[1]))
        else:
            norm_obs.append((obs, polygon_bbox(obs)))

    # Passo 1: chute inicial = max dos encostos individuais via NFP
    cand_x = 0.0
    for o_poly, o_bbox in norm_obs:
        cx = contact_placement_x(m_norm, o_poly, 0.0, gap)
        if cx is not None and cx <= (o_bbox[2] + gap + 5.0) and cx >= -25.0:
            cand_x = max(cand_x, cx)

    if cand_x <= 0.0:
        cand_x = max(ob[2] + gap for _, ob in norm_obs)

    # Passo 2: LOOP DE CONVERGÊNCIA — se colidir com algum obstáculo, empurra mais à direita e re-testa (máx 20 iterações)
    for _ in range(20):
        piece_at_cand = [{"x": p["x"] + cand_x, "y": p["y"]} for p in m_norm]
        cand_bbox = (cand_x, 0.0, cand_x + w_m, h_m)
        collisions = [(op, ob) for op, ob in norm_obs if polygons_collide(piece_at_cand, op, gap=gap, bbox_a=cand_bbox, bbox_b=ob)]

        if not collisions:
            return cand_x

        new_cand = cand_x
        for op, ob in collisions:
            cx = contact_placement_x(m_norm, op, 0.0, gap)
            if cx is not None and cx <= (ob[2] + gap + 5.0) and cx > new_cand:
                new_cand = cx

        # Se não avançou (deadlock por concavidade complexa) -> fallback seguro
        if new_cand <= cand_x + 1e-4:
            poly_fn = lambda x: [{"x": p["x"] + x, "y": p["y"]} for p in m_norm]
            safe_start = max(ob[2] for _, ob in norm_obs) + gap + 1.0
            return find_contact_coordinate_binary(poly_fn, norm_obs, gap, start_val=safe_start, min_val=cand_x)

        cand_x = new_cand

    poly_fn = lambda x: [{"x": p["x"] + x, "y": p["y"]} for p in m_norm]
    safe_start = max(ob[2] for _, ob in norm_obs) + gap + 1.0
    return find_contact_coordinate_binary(poly_fn, norm_obs, gap, start_val=safe_start, min_val=cand_x)



def check_collision_against_placed(cand_poly, cand_bbox, placed_pieces, gap=1.0, exclude_id=None, grid=None):
    """
    Verifica colisão do polígono candidato contra peças já posicionadas.
    Filtra primeiro por Bounding Box expandido pelo gap e aplica o Teorema dos Eixos Separadores (SAT).
    Se grid (SpatialGrid) for fornecido, realiza consulta espacial O(1).
    """
    effective_gap = max(0.0, float(gap))
    if grid is not None:
        near_colliders = grid.query_items(cand_bbox, gap=effective_gap)
        for it_id, p_poly, p_bbox in near_colliders:
            if exclude_id is not None and it_id == exclude_id:
                continue
            if polygons_collide(cand_poly, p_poly, gap=effective_gap, bbox_a=cand_bbox, bbox_b=p_bbox):
                return True
        return False

    for p in placed_pieces:
        if exclude_id is not None and p.get("id") == exclude_id:
            continue
        p_bbox = p.get("bbox")
        if p_bbox and not bbox_overlap(cand_bbox, p_bbox, effective_gap):
            continue
        p_poly = p.get("poly")
        if p_poly is None:
            p_poly = transform_contour(p.get("contour", []), p.get("x", 0.0), p.get("y", 0.0), p.get("rotation", 0.0))
        if polygons_collide(cand_poly, p_poly, gap=effective_gap, bbox_a=cand_bbox, bbox_b=p_bbox):
            return True
    return False


DEFAULT_IA_TESTE_MACRO = """# Macro Padrão do Motor 'IA-teste' com IA Local Auto-Tune
AI AUTO_TUNE
SORT BY area DESC
CLUSTER PAIR angles(0, 180) sweep(-3, 3, 1.0)
GRID STAGGER shift_x(0.38) gap(1.0)
GRAVITY VECTOR(-0.5, -1.0) steps(8, 4, 2, 0.5)
JIGGLE angles(-2, 2, 0.5)
FILL HOLES WHERE area < 4500 ANGLES(0, 90, 180, 270)
SCORE "used_height * 1.0 - yield_pct * 10.0"
"""


# ---------------------------------------------------------------------------
# 1. Avaliador Seguro de Fórmulas Matemáticas (SafeFormulaEvaluator)
# ---------------------------------------------------------------------------

class SafeFormulaEvaluator:
    """
    Avaliador de expressões matemáticas e lógicas estritamente seguro.
    Utiliza AST (Abstract Syntax Tree) do Python 3.12, rejeitando qualquer tentativa
    de acesso a atributos, importações, chamadas de sistema ou execução arbitrária.
    """

    ALLOWED_FUNCS: Dict[str, Callable] = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "sqrt": math.sqrt,
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "floor": math.floor,
        "ceil": math.ceil,
        "radians": math.radians,
        "degrees": math.degrees,
        "hypot": math.hypot,
        "pow": pow,
    }

    ALLOWED_CONSTANTS: Dict[str, Any] = {
        "pi": math.pi,
        "e": math.e,
        "True": True,
        "False": False,
        "None": None,
    }

    BINARY_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    UNARY_OPS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
        ast.Not: operator.not_,
    }

    COMPARE_OPS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }

    def __init__(self, context: Optional[Dict[str, Any]] = None):
        self.context = dict(context or {})

    def eval(self, expression: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Avalia a expressão permitindo contexto local e levantando ValueError se violar segurança."""
        if not expression or not expression.strip():
            return 0.0
        ctx = dict(self.context)
        if context:
            ctx.update(context)
        tree = ast.parse(expression.strip(), mode="eval")
        return self._eval_node(tree.body, ctx)

    @classmethod
    def evaluate(cls, expression: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Avalia com segurança uma expressão matemática / condicional dentro de um contexto."""
        if not expression or not expression.strip():
            return 0.0

        ctx = dict(context or {})
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            return cls._eval_node(tree.body, ctx)
        except Exception:
            return 0.0

    @classmethod
    def _eval_node(cls, node: ast.AST, ctx: Dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in ctx:
                return ctx[node.id]
            if node.id in cls.ALLOWED_CONSTANTS:
                return cls.ALLOWED_CONSTANTS[node.id]
            raise ValueError(f"Variável não permitida ou não definida no contexto: '{node.id}'")

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in cls.BINARY_OPS:
                raise ValueError(f"Operador binário não permitido: {op_type.__name__}")
            left = cls._eval_node(node.left, ctx)
            right = cls._eval_node(node.right, ctx)
            return cls.BINARY_OPS[op_type](left, right)

        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in cls.UNARY_OPS:
                raise ValueError(f"Operador unário não permitido: {op_type.__name__}")
            operand = cls._eval_node(node.operand, ctx)
            return cls.UNARY_OPS[op_type](operand)

        if isinstance(node, ast.Compare):
            left = cls._eval_node(node.left, ctx)
            for op, comp in zip(node.ops, node.comparators):
                op_type = type(op)
                if op_type not in cls.COMPARE_OPS:
                    raise ValueError(f"Operador de comparação não permitido: {op_type.__name__}")
                right = cls._eval_node(comp, ctx)
                if not cls.COMPARE_OPS[op_type](left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(cls._eval_node(val, ctx) for val in node.values)
            if isinstance(node.op, ast.Or):
                return any(cls._eval_node(val, ctx) for val in node.values)
            raise ValueError("Operador booleano desconhecido")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in cls.ALLOWED_FUNCS:
                func_name = node.func.id if isinstance(node.func, ast.Name) else "<complex>"
                raise ValueError(f"Função não permitida: '{func_name}'")
            func = cls.ALLOWED_FUNCS[node.func.id]
            args = [cls._eval_node(arg, ctx) for arg in node.args]
            return func(*args)

        raise ValueError(f"Nó de AST proibido por segurança: {type(node).__name__}")


# ---------------------------------------------------------------------------
# 2. Compilador da DSL de Macros (MacroCompiler)
# ---------------------------------------------------------------------------

class MacroConfig:
    """Configuração intermediária resultante da compilação de uma macro."""
    def __init__(self):
        self.commands: List[str] = []
        self.ai_auto_tune: bool = False
        self.sort_fields: List[Tuple[str, bool]] = [("sequence", False)]  # (campo, reverse)
        self.cluster_angles: List[float] = [0.0, 180.0]
        self.sweep_from: float = -3.0
        self.sweep_to: float = 3.0
        self.sweep_step: float = 1.0
        self.shift_x: float = 0.38
        self.gap: float = 1.0
        self.gravity_vx: float = -0.5
        self.gravity_vy: float = -1.0
        self.gravity_steps: List[float] = [8.0, 4.0, 2.0, 0.5]
        self.jiggle_angles: List[float] = [-2.0, -1.0, 0.0, 1.0, 2.0]
        self.fill_holes_enabled: bool = False
        self.fill_holes_where: str = "area < 4500"
        self.fill_holes_angles: List[float] = [0.0, 90.0, 180.0, 270.0]
        self.score_formula: str = "used_height * 1.0 - yield_pct * 10.0"


class MacroCompiler:
    """Compila o texto da macro declarativa em um objeto MacroConfig executável."""

    @classmethod
    def compile(cls, script_text: Optional[str]) -> MacroConfig:
        config = MacroConfig()
        if not script_text or not script_text.strip():
            script_text = DEFAULT_IA_TESTE_MACRO

        for raw_line in script_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # 1. AI AUTO_TUNE
            if re.match(r"^AI\s+AUTO_TUNE", line, re.IGNORECASE):
                config.ai_auto_tune = True
                config.commands.append("AI")
                continue

            # 2. SORT BY <campo> [ASC|DESC], ...
            m_sort = re.match(r"^SORT\s+BY\s+(.+)$", line, re.IGNORECASE)
            if m_sort:
                fields_str = m_sort.group(1)
                sort_rules = []
                for chunk in fields_str.split(","):
                    parts = chunk.strip().split()
                    if not parts:
                        continue
                    fname = parts[0].lower()
                    rev = True if (len(parts) > 1 and parts[1].upper() == "DESC") else False
                    if len(parts) == 1:
                        rev = True  # Padrão de sort no nesting industrial é DESC (maior para menor)
                    sort_rules.append((fname, rev))
                if sort_rules:
                    config.sort_fields = sort_rules
                config.commands.append("SORT")
                continue

            # 3. CLUSTER PAIR angles(a1, a2) sweep(from, to, step)
            m_cluster = re.match(r"^CLUSTER\s+PAIR\s+angles\s*\(([^)]+)\)\s*(?:sweep\s*\(([^)]+)\))?", line, re.IGNORECASE)
            if m_cluster:
                ang_str = m_cluster.group(1)
                try:
                    config.cluster_angles = [float(x.strip()) for x in ang_str.split(",") if x.strip()]
                except Exception:
                    pass
                if m_cluster.group(2):
                    swp_parts = [float(x.strip()) for x in m_cluster.group(2).split(",") if x.strip()]
                    if len(swp_parts) >= 3:
                        config.sweep_from = swp_parts[0]
                        config.sweep_to = swp_parts[1]
                        config.sweep_step = max(0.1, swp_parts[2])
                config.commands.append("CLUSTER")
                continue

            # 4. GRID STAGGER shift_x(ratio) gap(mm)
            m_grid = re.match(r"^GRID\s+STAGGER", line, re.IGNORECASE)
            if m_grid:
                m_shift = re.search(r"shift_x\s*\(\s*([\d\.-]+)\s*\)", line, re.IGNORECASE)
                if m_shift:
                    config.shift_x = float(m_shift.group(1))
                m_gap = re.search(r"gap\s*\(\s*([\d\.-]+)\s*\)", line, re.IGNORECASE)
                if m_gap:
                    config.gap = max(0.1, float(m_gap.group(1)))
                config.commands.append("GRID")
                continue

            # 5. GRAVITY VECTOR(vx, vy) steps(s1, s2, ...)
            m_grav = re.match(r"^GRAVITY\s+VECTOR\s*\(\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*\)(?:\s*steps\s*\(([^)]+)\))?", line, re.IGNORECASE)
            if m_grav:
                config.gravity_vx = float(m_grav.group(1))
                config.gravity_vy = float(m_grav.group(2))
                if m_grav.group(3):
                    steps_list = [float(x.strip()) for x in m_grav.group(3).split(",") if x.strip()]
                    if steps_list:
                        config.gravity_steps = steps_list
                config.commands.append("GRAVITY")
                continue

            # 6. JIGGLE angles(from, to, step)
            m_jiggle = re.match(r"^JIGGLE\s+angles\s*\(\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*\)", line, re.IGNORECASE)
            if m_jiggle:
                j_from = float(m_jiggle.group(1))
                j_to = float(m_jiggle.group(2))
                j_step = max(0.1, float(m_jiggle.group(3)))
                angles = []
                cur = j_from
                while cur <= j_to + 1e-4:
                    angles.append(round(cur, 2))
                    cur += j_step
                if angles:
                    config.jiggle_angles = angles
                config.commands.append("JIGGLE")
                continue

            # 7. FILL HOLES WHERE <condição> ANGLES(a1, a2, ...)
            m_fill = re.match(r"^FILL\s+HOLES\s+WHERE\s+(.+?)(?:\s+ANGLES\s*\(([^)]+)\))?$", line, re.IGNORECASE)
            if m_fill:
                config.fill_holes_enabled = True
                config.fill_holes_where = m_fill.group(1).strip()
                if m_fill.group(2):
                    ang_parts = [float(x.strip()) for x in m_fill.group(2).split(",") if x.strip()]
                    if ang_parts:
                        config.fill_holes_angles = ang_parts
                config.commands.append("FILL_HOLES")
                continue

            # 8. SCORE "<fórmula>"
            m_score = re.match(r'^SCORE\s+["\'](.+?)["\']', line, re.IGNORECASE)
            if m_score:
                config.score_formula = m_score.group(1).strip()
                config.commands.append("SCORE")
                continue

            raise ValueError(f"Comando de macro inválido ou não reconhecido: '{line}'")

        return config


# ---------------------------------------------------------------------------
# 3. Motor de Execução de Macros (OmniNestMacroEngine)
# ---------------------------------------------------------------------------

class OmniNestMacroEngine:
    """
    Executa a macro declarativa sobre a geometria real dos moldes,
    respeitando limites físicos da Placa, gap milimétrico estrito e zero colisão.
    """

    def __init__(self, db=None):
        self.db = db
        self.ai_brain = NestingAIBrain(db=db)

    def _get_poly0_info(self, shape: Dict[str, Any], rot: float) -> Tuple[Any, float, float, float, float, List[Dict[str, float]]]:
        """Calcula ou recupera do cache o contorno transformado poly0, bbox e forma normalizada."""
        c = shape.get("contour", [])
        c_id = id(c)
        r_key = round(float(rot), 2)
        key = (c_id, r_key)
        if key in _POLY0_CACHE:
            return _POLY0_CACHE[key]

        poly0 = transform_contour(c, 0.0, 0.0, r_key)
        min_x, min_y, max_x, max_y = polygon_bbox(poly0)
        w = max_x - min_x
        h = max_y - min_y
        poly_norm = [{"x": p["x"] - min_x, "y": p["y"] - min_y} for p in poly0]
        info = (poly0, min_x, min_y, w, h, poly_norm)
        if len(_POLY0_CACHE) >= 5000:
            _POLY0_CACHE.clear()
        _POLY0_CACHE[key] = info
        return info

    def _get_dx_sep(self, s_m: Dict[str, Any], rot_m: float, s_o: Dict[str, Any], rot_o: float, gap_val: float) -> float:
        """Calcula ou recupera do cache a distância de contato horizontal analítica via NFP com Loop de Convergência."""
        c_m = s_m.get("contour", [])
        c_o = s_o.get("contour", [])
        key = (id(c_m), round(float(rot_m), 2), id(c_o), round(float(rot_o), 2), round(float(gap_val), 2))
        if key in _DX_SEP_CACHE:
            return _DX_SEP_CACHE[key]

        info_m = self._get_poly0_info(s_m, rot_m)
        info_o = self._get_poly0_info(s_o, rot_o)
        m_norm = info_m[5]
        o_norm = info_o[5]

        dx = _find_best_horizontal_slot_nfp(m_norm, [o_norm], gap=gap_val)

        if len(_DX_SEP_CACHE) >= 5000:
            _DX_SEP_CACHE.clear()
        _DX_SEP_CACHE[key] = dx
        return dx

    def run(
        self,
        available_shapes: List[Dict[str, Any]],
        bed_width_mm: float,
        bed_height_mm: float,
        target_count: int = 16,
        gap_mm: float = 1.0,
        macro_script: Optional[str] = None,
        dieproc_params: Optional[Dict[str, Any]] = None,
        margins: Optional[Dict[str, float]] = None,
        layers: Optional[int] = None,
        deterministic: bool = False
    ) -> List[Dict[str, Any]]:
        """Executa o pipeline completo da macro sobre as peças com otimizações NFP analíticas e zero colisão."""
        if not available_shapes:
            return []

        config = MacroCompiler.compile(macro_script)
        # Se gap_mm explícito foi passado, prioriza o valor mestre
        if gap_mm is not None and gap_mm >= 0.0:
            config.gap = float(gap_mm)

        # Se parâmetros DieProc (coupling, ranges) foram informados, aplica no config
        if dieproc_params and isinstance(dieproc_params, dict):
            c_str = str(dieproc_params.get("coupling", "")).strip()
            if c_str == "0/0":
                config.cluster_angles = [0.0]
                config.shift_x = 0.0
                config.jiggle_angles = []
            elif c_str == "180/180":
                config.cluster_angles = [180.0]
                config.shift_x = 0.0
                config.jiggle_angles = []
            elif "0/180" in c_str or "180" in c_str:
                config.cluster_angles = [0.0, 180.0]
            if "range1_from" in dieproc_params:
                config.sweep_from = float(dieproc_params["range1_from"])
            if "range1_to" in dieproc_params:
                config.sweep_to = float(dieproc_params["range1_to"])
            if "range1_step" in dieproc_params and float(dieproc_params["range1_step"]) > 0:
                config.sweep_step = max(0.1, float(dieproc_params["range1_step"]))

        if margins is None and dieproc_params and isinstance(dieproc_params, dict) and "margins" in dieproc_params:
            margins = dieproc_params["margins"]
        m_left = float(margins.get("left", 10.0)) if margins else 10.0
        m_right = float(margins.get("right", 10.0)) if margins else 10.0
        m_top = float(margins.get("top", 10.0)) if margins else 10.0
        m_bottom = float(margins.get("bottom", 10.0)) if margins else 10.0
        margins_dict = {"left": m_left, "right": m_right, "top": m_top, "bottom": m_bottom}

        # 1. Análise Geométrica e Auto-Tune de IA Local
        primary_family = "COMPACTA_SOLA_CALCANHAR"
        extractor = ShapeFeatureExtractor()
        if available_shapes:
            primary_family = extractor.classify_family(available_shapes[0].get("contour", []))

        bandit_suggestion = None
        if config.ai_auto_tune:
            bandit_suggestion = self.ai_brain.suggest_optimized_macro_params(primary_family, deterministic=deterministic)
            if bandit_suggestion:
                config.shift_x = float(bandit_suggestion.get("shift_x", config.shift_x))
                config.gravity_vx = float(bandit_suggestion.get("gravity_x", config.gravity_vx))
                config.gravity_vy = float(bandit_suggestion.get("gravity_y", config.gravity_vy))
                swp_max = float(bandit_suggestion.get("sweep_max", config.sweep_to))
                config.sweep_from = -swp_max
                config.sweep_to = swp_max
                if "steps" in bandit_suggestion and isinstance(bandit_suggestion["steps"], list):
                    config.gravity_steps = bandit_suggestion["steps"]

        # 2. Ordenação dos Moldes conforme regras SORT BY
        def _get_sort_val(s: Dict[str, Any], field_name: str) -> float:
            c = s.get("contour", [])
            f_name = field_name.lower()
            if f_name == "area":
                return polygon_area(c) if c else 0.0
            if f_name == "perimeter":
                return polygon_perimeter(c) if c else 0.0
            if f_name in ("width", "w"):
                if not c:
                    return 0.0
                b = polygon_bbox(c)
                return b[2] - b[0]
            if f_name in ("height", "h"):
                if not c:
                    return 0.0
                b = polygon_bbox(c)
                return b[3] - b[1]
            if f_name in ("size", "taglia"):
                try:
                    return float(re.sub(r"[^\d.]", "", str(s.get("size", "0"))))
                except Exception:
                    return 0.0
            if f_name == "sequence":
                try:
                    return float(s.get("sequence", 999))
                except Exception:
                    return 999.0
            return 0.0

        # Neutraliza qualquer ordenação interna por área/tamanho em favor da sequência estrita (# CONFIRMAR NO WINDOWS)
        from cad.nesting_engine import sort_shapes_by_sequence
        sorted_shapes, _ = sort_shapes_by_sequence(available_shapes)

        # 3. Monta a Fila de Peças a Cortar considerando pares e camadas
        shape_queue = []
        for s in sorted_shapes:
            if "target_pieces" in s:
                qty = max(0, int(s["target_pieces"]))
            else:
                l_val = layers or s.get("layers") or (dieproc_params.get("layers") if isinstance(dieproc_params, dict) else None) or 2
                try:
                    l_val = max(1, int(l_val))
                except (ValueError, TypeError):
                    l_val = 2
                qty = math.ceil((int(s.get("pairs", 24)) * 2) / l_val)
            for _ in range(qty):
                shape_queue.append(s)

        if not shape_queue:
            shape_queue = list(sorted_shapes)

        max_pieces = target_count if (target_count and target_count > 0) else len(shape_queue)

        # 4. Posicionamento Base por Fileiras Unificadas (Row Interlock + Contour Bumping)
        gap = max(0.0, config.gap)

        placed = []
        rows = []
        cur_row_y = m_bottom
        row_idx = 0
        grid = SpatialGrid(cell_size=150.0)
        queue_idx = 0
        idx = 1

        angles_pool = config.cluster_angles if config.cluster_angles else [0.0, 180.0]
        is_alternating = len(angles_pool) > 1 and (0.0 in angles_pool and 180.0 in angles_pool)

        while queue_idx < max_pieces and cur_row_y < bed_height_mm - m_top:
            row_pieces = []
            is_odd_row = (row_idx % 2 == 1)

            # 1. Preenche a fileira horizontalmente (eixo X) com bumping contorno a contorno analítico
            while queue_idx < max_pieces:
                shape = shape_queue[queue_idx % len(shape_queue)]
                piece_in_row_idx = len(row_pieces)

                if is_alternating:
                    base_rot = 180.0 if ((piece_in_row_idx % 2 == 1) ^ is_odd_row) else 0.0
                else:
                    base_rot = angles_pool[piece_in_row_idx % len(angles_pool)]

                if not row_pieces:
                    poly0, min_x, min_y, w, h, poly_norm = self._get_poly0_info(shape, base_rot)
                    cand_x = m_left
                    cand_bbox = (cand_x, cur_row_y, cand_x + w, cur_row_y + h)
                    best_cand = None
                    if cand_bbox[2] <= bed_width_mm - m_right:
                        best_cand = {
                            "cand_x": cand_x,
                            "rot": base_rot,
                            "min_x": min_x,
                            "min_y": min_y,
                            "w": w,
                            "h": h,
                            "poly_norm": poly_norm
                        }
                else:
                    sweep_angles = [base_rot]
                    swp = config.sweep_from
                    while swp <= config.sweep_to + 1e-4:
                        ang = (base_rot + swp) % 360.0
                        if ang not in sweep_angles:
                            sweep_angles.append(ang)
                        swp += config.sweep_step

                    best_cand = None
                    best_x = float("inf")

                    for rot_candidate in sweep_angles:
                        poly0, min_x, min_y, w, h, poly_norm = self._get_poly0_info(shape, rot_candidate)
                        prev_piece = row_pieces[-1]
                        sep_x = self._get_dx_sep(shape, rot_candidate, prev_piece["shape"], prev_piece["rot"], gap)
                        cand_x = prev_piece["cand_x"] + sep_x

                        cand_bbox = (cand_x, cur_row_y, cand_x + w, cur_row_y + h)
                        if cand_bbox[2] <= bed_width_mm - m_right:
                            if cand_x < best_x:
                                best_x = cand_x
                                best_cand = {
                                    "cand_x": cand_x,
                                    "rot": rot_candidate,
                                    "min_x": min_x,
                                    "min_y": min_y,
                                    "w": w,
                                    "h": h,
                                    "poly_norm": poly_norm
                                }

                if best_cand is None:
                    # Largura útil da chapa atingida para esta fileira
                    break

                s_sz = str(shape.get("size") or shape.get("taglia") or "41")
                p_color = get_color_for_size(s_sz, idx)
                cand_x = best_cand["cand_x"]
                min_x = best_cand["min_x"]
                min_y = best_cand["min_y"]
                w = best_cand["w"]
                h = best_cand["h"]
                rot = best_cand["rot"]
                poly_norm = best_cand["poly_norm"]

                # Translação vetorial pura sem recalculação trigonométrica
                cand_poly = [{"x": p["x"] + cand_x, "y": p["y"] + cur_row_y} for p in poly_norm]
                cand_bbox = (cand_x, cur_row_y, cand_x + w, cur_row_y + h)

                item = {
                    "id": idx,
                    "shape": shape,
                    "name": shape.get("name", "Molde"),
                    "size": s_sz,
                    "color": p_color,
                    "contour": shape.get("contour", []),
                    "holes": shape.get("holes", []),
                    "internal_cuts": shape.get("internal_cuts", []),
                    "stitching": shape.get("stitching", []),
                    "cand_x": cand_x,
                    "rot": rot,
                    "x": cand_x - min_x,
                    "y": cur_row_y - min_y,
                    "rotation": rot,
                    "poly": cand_poly,
                    "bbox": cand_bbox,
                    "min_x": min_x,
                    "min_y": min_y,
                    "w": w,
                    "h": h
                }
                row_pieces.append(item)
                queue_idx += 1
                idx += 1

            if not row_pieces:
                break

            # 2. Encaixe vertical contorno a contorno da fileira inteira como bloco rígido (Row Interlock)
            if row_idx > 0:
                prev_row = rows[-1]
                prev_max_y = max(p["bbox"][3] for p in prev_row)
                last_hit_idx = [0]

                def row_collides(test_row_y):
                    dy = test_row_y - cur_row_y
                    n_rp = len(row_pieces)
                    order = [last_hit_idx[0]] + [i for i in range(n_rp) if i != last_hit_idx[0]]
                    for i in order:
                        p = row_pieces[i]
                        test_p_bbox = (p["bbox"][0], p["bbox"][1] + dy, p["bbox"][2], p["bbox"][3] + dy)
                        if test_p_bbox[1] - gap > prev_max_y:
                            continue
                        near_c = grid.query_items(test_p_bbox, gap=gap)
                        if not near_c:
                            continue
                        test_p_poly = [{"x": pt["x"], "y": pt["y"] + dy} for pt in p["poly"]]
                        for it_id, p_poly, p_bbox in near_c:
                            if polygons_collide(test_p_poly, p_poly, gap=gap, bbox_a=test_p_bbox, bbox_b=p_bbox):
                                last_hit_idx[0] = i
                                return True
                    return False

                high_y = prev_max_y + gap + 5.0
                low_y = prev_max_y - 80.0

                for _ in range(8):
                    mid_y = (low_y + high_y) / 2.0
                    if row_collides(mid_y):
                        low_y = mid_y
                    else:
                        high_y = mid_y
                final_row_y = high_y + 0.05
                while row_collides(final_row_y):
                    final_row_y += 0.1

                dy_final = final_row_y - cur_row_y
                cur_row_y = final_row_y
                for p in row_pieces:
                    p["y"] += dy_final
                    p["bbox"] = (p["bbox"][0], p["bbox"][1] + dy_final, p["bbox"][2], p["bbox"][3] + dy_final)
                    p["poly"] = [{"x": pt["x"], "y": pt["y"] + dy_final} for pt in p["poly"]]

            # 3. Interrompe se a fileira ultrapassar a margem do topo da placa
            if any(p["bbox"][3] > bed_height_mm - m_top for p in row_pieces):
                break

            for p in row_pieces:
                grid.insert(p["id"], p["poly"], p["bbox"])
                placed.append(p)
            rows.append(row_pieces)
            row_idx += 1
            cur_row_y += 100.0

        # 5. Compactação por Gravidade Vetorial Contínua
        if config.gravity_vx != 0:
            self._apply_vector_gravity(placed, bed_width_mm, bed_height_mm, config, margins_dict, gap)

        # 8. Trava Final Inviolável de Sanity Pass Pós-Processamento com SpatialGrid
        audit_gap = max(0.0, gap - 0.02)
        for _ in range(12):
            conflict_found = False
            audit_grid = SpatialGrid(cell_size=150.0)
            for p in placed:
                audit_grid.insert(p["id"], p["poly"], p["bbox"])
            for pi in placed:
                near = audit_grid.query_items(pi["bbox"], gap=audit_gap)
                for pj_id, pj_poly, pj_bbox in near:
                    if pj_id <= pi["id"]:
                        continue
                    if polygons_collide(pi["poly"], pj_poly, gap=audit_gap, bbox_a=pi["bbox"], bbox_b=pj_bbox):
                        conflict_found = True
                        pj = next(p for p in placed if p["id"] == pj_id)
                        p_upper = pi if pi["bbox"][1] >= pj["bbox"][1] else pj
                        p_other = pj if p_upper is pi else pi

                        # Empurra a peça superior para cima em passos de 0.2mm até descolidir
                        while polygons_collide(p_upper["poly"], p_other["poly"], gap=audit_gap, bbox_a=p_upper["bbox"], bbox_b=p_other["bbox"]):
                            p_upper["y"] += 0.2
                            p_upper["poly"] = [{"x": pt["x"], "y": pt["y"] + 0.2} for pt in p_upper["poly"]]
                            p_upper["bbox"] = (p_upper["bbox"][0], p_upper["bbox"][1] + 0.2, p_upper["bbox"][2], p_upper["bbox"][3] + 0.2)
                            if p_upper["bbox"][3] > bed_height_mm - m_top:
                                break
            if not conflict_found:
                break

        # Remove qualquer peça que após o empurrão tenha saído dos limites da placa
        placed = [p for p in placed if p["bbox"][0] >= m_left - 0.05 and p["bbox"][1] >= m_bottom - 0.05 and p["bbox"][2] <= bed_width_mm - m_right + 0.05 and p["bbox"][3] <= bed_height_mm - m_top + 0.05]

        # 9. Cálculo de Rendimento e Feedback ao Cérebro de IA
        useful_area_mm2 = sum(polygon_area(p.get("contour", [])) for p in placed)
        bed_area_m2 = (bed_width_mm * bed_height_mm) / 1_000_000.0
        yield_pct = (useful_area_mm2 / 1_000_000.0 / bed_area_m2 * 100.0) if bed_area_m2 > 0 else 0.0

        if config.ai_auto_tune and bandit_suggestion and "arm_index" in bandit_suggestion and not deterministic:
            self.ai_brain.record_macro_execution_feedback(
                primary_family,
                bandit_suggestion["arm_index"],
                yield_pct
            )

        # 10. Ordenação de Vácuo CNC e Retorno das Peças
        placed.sort(key=lambda p: (round(p["y"], 1), round(p["x"], 1)))
        result_pieces = []
        for new_idx, p in enumerate(placed, start=1):
            res_item = {
                "id": new_idx,
                "shape": p.get("shape", {}),
                "name": p.get("name", "Molde"),
                "size": str(p.get("size", "41")),
                "color": p.get("color", "#2563eb"),
                "contour": p.get("contour", []),
                "holes": p.get("holes", []),
                "internal_cuts": p.get("internal_cuts", []),
                "stitching": p.get("stitching", []),
                "x": round(float(p["x"]), 3),
                "y": round(float(p["y"]), 3),
                "rotation": round(float(p["rotation"]), 3)
            }
            result_pieces.append(res_item)

        return result_pieces

    # -----------------------------------------------------------------------
    # Métodos Auxiliares de Otimização Física
    # -----------------------------------------------------------------------

    def _apply_vector_gravity(
        self,
        placed: List[Dict[str, Any]],
        bed_width: float,
        bed_height: float,
        config: MacroConfig,
        margins: Union[float, Dict[str, float], None],
        gap: float
    ) -> None:
        """Move as peças na direção do vetor de gravidade (vx, vy) em passos decrescentes usando translações vetoriais diretas."""
        if not placed:
            return

        if isinstance(margins, dict):
            m_left = float(margins.get("left", 10.0))
            m_right = float(margins.get("right", 10.0))
            m_top = float(margins.get("top", 10.0))
            m_bottom = float(margins.get("bottom", 10.0))
        elif isinstance(margins, (int, float)):
            m_left = m_right = m_top = m_bottom = float(margins)
        else:
            m_left = m_right = m_top = m_bottom = 10.0

        vx = config.gravity_vx
        vy = config.gravity_vy
        norm = math.hypot(vx, vy)
        if norm <= 0.001:
            return
        dx_dir = vx / norm
        dy_dir = vy / norm

        grid_g = SpatialGrid(cell_size=150.0)
        for item in placed:
            grid_g.insert(item["id"], item["poly"], item["bbox"])

        for step in config.gravity_steps:
            # 1. Puxada vertical em Y (para baixo)
            if abs(dy_dir) > 0.01:
                step_y = dy_dir * step
                order_y = sorted(placed, key=lambda p: p["bbox"][1] if dy_dir < 0 else -p["bbox"][3])
                moved_y = False
                for p in order_y:
                    p_id = p["id"]
                    old_bbox = p["bbox"]
                    if dy_dir < 0 and old_bbox[1] <= m_bottom + 0.05:
                        continue
                    test_bbox = (old_bbox[0], old_bbox[1] + step_y, old_bbox[2], old_bbox[3] + step_y)
                    if test_bbox[1] < m_bottom or test_bbox[3] > bed_height - m_top:
                        continue
                    near_c = grid_g.query_items(test_bbox, gap=gap)
                    colliders = [it for it in near_c if it[0] != p_id]
                    if not colliders:
                        p["y"] += step_y
                        p["poly"] = [{"x": pt["x"], "y": pt["y"] + step_y} for pt in p["poly"]]
                        p["bbox"] = test_bbox
                        moved_y = True
                        continue
                    # Prioriza o último obstáculo que colidiu com esta peça
                    last_c = p.get("_lc_y")
                    if last_c is not None:
                        for c_i, it in enumerate(colliders):
                            if it[0] == last_c:
                                colliders.insert(0, colliders.pop(c_i))
                                break
                    test_poly = [{"x": pt["x"], "y": pt["y"] + step_y} for pt in p["poly"]]
                    collides = False
                    for it_id, o_poly, o_bbox in colliders:
                        if polygons_collide(test_poly, o_poly, gap=gap, bbox_a=test_bbox, bbox_b=o_bbox):
                            collides = True
                            p["_lc_y"] = it_id
                            break
                    if not collides:
                        p["y"] += step_y
                        p["poly"] = test_poly
                        p["bbox"] = test_bbox
                        moved_y = True
                if moved_y:
                    grid_g = SpatialGrid(cell_size=150.0)
                    for item in placed:
                        grid_g.insert(item["id"], item["poly"], item["bbox"])

            # 2. Puxada horizontal em X (para a esquerda)
            if abs(dx_dir) > 0.01:
                step_x = dx_dir * step
                order_x = sorted(placed, key=lambda p: p["bbox"][0] if dx_dir < 0 else -p["bbox"][2])
                moved_x = False
                for p in order_x:
                    p_id = p["id"]
                    old_bbox = p["bbox"]
                    if dx_dir < 0 and old_bbox[0] <= m_left + 0.05:
                        continue
                    test_bbox = (old_bbox[0] + step_x, old_bbox[1], old_bbox[2] + step_x, old_bbox[3])
                    if test_bbox[0] < m_left or test_bbox[2] > bed_width - m_right:
                        continue
                    near_c = grid_g.query_items(test_bbox, gap=gap)
                    colliders = [it for it in near_c if it[0] != p_id]
                    if not colliders:
                        p["x"] += step_x
                        p["poly"] = [{"x": pt["x"] + step_x, "y": pt["y"]} for pt in p["poly"]]
                        p["bbox"] = test_bbox
                        moved_x = True
                        continue
                    last_c = p.get("_lc_x")
                    if last_c is not None:
                        for c_i, it in enumerate(colliders):
                            if it[0] == last_c:
                                colliders.insert(0, colliders.pop(c_i))
                                break
                    test_poly = [{"x": pt["x"] + step_x, "y": pt["y"]} for pt in p["poly"]]
                    collides = False
                    for it_id, o_poly, o_bbox in colliders:
                        if polygons_collide(test_poly, o_poly, gap=gap, bbox_a=test_bbox, bbox_b=o_bbox):
                            collides = True
                            p["_lc_x"] = it_id
                            break
                    if not collides:
                        p["x"] += step_x
                        p["poly"] = test_poly
                        p["bbox"] = test_bbox
                        moved_x = True
                if moved_x:
                    grid_g = SpatialGrid(cell_size=150.0)
                    for item in placed:
                        grid_g.insert(item["id"], item["poly"], item["bbox"])

    def _apply_jiggle(
        self,
        placed: List[Dict[str, Any]],
        bed_width: float,
        bed_height: float,
        config: MacroConfig,
        margins: Union[float, Dict[str, float], None],
        gap: float
    ) -> None:
        """Testa micro-rotações controladas (jiggle) para compactação complementar em torno do centro."""
        if not placed or not config.jiggle_angles:
            return

        if isinstance(margins, dict):
            m_left = float(margins.get("left", 10.0))
            m_right = float(margins.get("right", 10.0))
            m_top = float(margins.get("top", 10.0))
            m_bottom = float(margins.get("bottom", 10.0))
        elif isinstance(margins, (int, float)):
            m_left = m_right = m_top = m_bottom = float(margins)
        else:
            m_left = m_right = m_top = m_bottom = 10.0

        grid_j = SpatialGrid(cell_size=100.0)
        for item in placed:
            grid_j.insert(item["id"], item["poly"], item["bbox"])

        for p in placed:
            p_id = p["id"]
            c = p["contour"]
            cur_rot = p["rotation"]
            cur_x = p["x"]
            cur_y = p["y"]
            cur_poly = p["poly"]
            cur_bbox = p["bbox"]

            min_x0, min_y0, max_x0, max_y0 = polygon_bbox(c)
            cx0 = (min_x0 + max_x0) / 2.0
            cy0 = (min_y0 + max_y0) / 2.0

            cx_old, cy_old = rotate_point(cx0, cy0, cur_rot)
            c_plate_x = cur_x + cx_old
            c_plate_y = cur_y + cy_old

            best_y = cur_bbox[1]
            best_rot = cur_rot
            best_x = cur_x
            best_y_coord = cur_y
            best_poly = cur_poly
            best_bbox = cur_bbox

            for d_rot in config.jiggle_angles:
                if abs(d_rot) < 1e-4:
                    continue
                test_rot = (cur_rot + d_rot) % 360.0
                cx_new, cy_new = rotate_point(cx0, cy0, test_rot)
                test_x = c_plate_x - cx_new
                test_y = c_plate_y - cy_new

                test_poly = transform_contour(c, test_x, test_y, test_rot)
                test_bbox = polygon_bbox(test_poly)

                if (test_bbox[0] < m_left or test_bbox[1] < m_bottom or
                    test_bbox[2] > bed_width - m_right or test_bbox[3] > bed_height - m_top):
                    continue

                if not check_collision_against_placed(test_poly, test_bbox, placed, gap=gap, exclude_id=p_id, grid=grid_j):
                    if test_bbox[1] < best_y:
                        best_y = test_bbox[1]
                        best_rot = test_rot
                        best_x = test_x
                        best_y_coord = test_y
                        best_poly = test_poly
                        best_bbox = test_bbox

            if best_rot != cur_rot:
                p["rotation"] = best_rot
                p["x"] = best_x
                p["y"] = best_y_coord
                p["poly"] = best_poly
                p["bbox"] = best_bbox

    def _apply_fill_holes(
        self,
        placed: List[Dict[str, Any]],
        shape_queue: List[Dict[str, Any]],
        bed_width: float,
        bed_height: float,
        config: MacroConfig,
        margins: Union[float, Dict[str, float], None],
        gap: float
    ) -> None:
        """Encaixa peças pequenas em vazios existentes nas fileiras inferiores da mesa."""
        if not shape_queue or not placed:
            return

        if isinstance(margins, dict):
            m_left = float(margins.get("left", 10.0))
            m_right = float(margins.get("right", 10.0))
            m_top = float(margins.get("top", 10.0))
            m_bottom = float(margins.get("bottom", 10.0))
        elif isinstance(margins, (int, float)):
            m_left = m_right = m_top = m_bottom = float(margins)
        else:
            m_left = m_right = m_top = m_bottom = 10.0

        max_placed_y = max(p["bbox"][3] for p in placed)
        next_id = max(p["id"] for p in placed) + 1

        for shape in shape_queue:
            # Trava inviolável de prioridade estrita: nunca fura fila com moldes de sequência futura
            if placed:
                from cad.nesting_engine import parse_sequence_num
                placed_seqs = [parse_sequence_num(p.get("shape", {}).get("sequence")) for p in placed]
                valid_seqs = [s for s in placed_seqs if s is not None]
                s_seq = parse_sequence_num(shape.get("sequence"))
                if s_seq is not None and valid_seqs and s_seq > max(valid_seqs):
                    continue

            c = shape.get("contour", [])
            if not c:
                continue
            f = ShapeFeatureExtractor.extract_features(c)

            # Avalia a condição declarada no FILL HOLES WHERE ...
            is_candidate = SafeFormulaEvaluator.evaluate(config.fill_holes_where, f)
            if not is_candidate:
                continue

            for rot in config.fill_holes_angles:
                poly0 = transform_contour(c, 0, 0, rot)
                min_x, min_y, max_x, max_y = polygon_bbox(poly0)
                w = max_x - min_x
                h = max_y - min_y

                # Varredura em grade fina nos vazios inferiores
                step_grid = max(30.0, w * 0.6)
                cand_x = m_left
                placed_in_hole = False

                while cand_x + w <= bed_width - m_right:
                    cand_y = m_bottom
                    while cand_y + h <= max_placed_y - gap:
                        test_poly = transform_contour(c, cand_x - min_x, cand_y - min_y, rot)
                        test_bbox = (cand_x, cand_y, cand_x + w, cand_y + h)

                        if not check_collision_against_placed(test_poly, test_bbox, placed, gap=gap):
                            s_sz = str(shape.get("size") or shape.get("taglia") or "41")
                            p_color = get_color_for_size(s_sz, next_id)
                            piece = {
                                "id": next_id,
                                "shape": shape,
                                "name": shape.get("name", "Molde"),
                                "size": s_sz,
                                "color": p_color,
                                "contour": c,
                                "holes": shape.get("holes", []),
                                "internal_cuts": shape.get("internal_cuts", []),
                                "stitching": shape.get("stitching", []),
                                "x": cand_x - min_x,
                                "y": cand_y - min_y,
                                "rotation": rot,
                                "poly": test_poly,
                                "bbox": test_bbox
                            }
                            placed.append(piece)
                            next_id += 1
                            placed_in_hole = True
                            break
                        cand_y += step_grid
                    if placed_in_hole:
                        break
                    cand_x += step_grid


# ---------------------------------------------------------------------------
# 4. Função Pública do Motor "IA-teste"
# ---------------------------------------------------------------------------

def nest_ia_teste_engine(
    available_shapes: List[Dict[str, Any]],
    bed_width_mm: float,
    bed_height_mm: float,
    target_count: int = 16,
    gap_mm: float = 1.0,
    macro_script: Optional[str] = None,
    db=None,
    dieproc_params: Optional[Dict[str, Any]] = None,
    margins: Optional[Dict[str, float]] = None,
    layers: Optional[int] = None,
    deterministic: bool = False
) -> List[Dict[str, Any]]:
    """
    Função de entrada oficial do motor 'IA-teste'.
    Combina macros declarativas com aprendizado de máquina local e zero colisão.
    """
    # Se o script não foi passado explicitamente, busca no dieproc_params ou banco
    if not deterministic and dieproc_params and isinstance(dieproc_params, dict):
        deterministic = bool(dieproc_params.get("deterministic", False))

    script = macro_script
    if not script and dieproc_params and isinstance(dieproc_params, dict):
        script = dieproc_params.get("macro_script")

    if not script and db:
        try:
            # Tenta buscar preset padrão de macro ou configuração salva
            preset = db.get_dieproc_preset("MACRO_IA_TESTE")
            if preset and preset.get("macro_script"):
                script = preset.get("macro_script")
        except Exception:
            pass

    if not script:
        script = DEFAULT_IA_TESTE_MACRO

    engine = OmniNestMacroEngine(db=db)
    return engine.run(
        available_shapes=available_shapes,
        bed_width_mm=bed_width_mm,
        bed_height_mm=bed_height_mm,
        target_count=target_count,
        gap_mm=gap_mm,
        macro_script=script,
        dieproc_params=dieproc_params,
        margins=margins,
        layers=layers,
        deterministic=deterministic
    )

