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

import ast
import re
import math
import operator
from typing import List, Dict, Any, Optional, Tuple, Callable

from cad.geometry import (
    transform_contour, polygon_area, polygon_perimeter, polygon_bbox,
    polygons_collide, SpatialGrid, find_contact_coordinate_binary
)
from cad.colors import get_color_for_size
from cad.ai_learner import ShapeFeatureExtractor, NestingAIBrain


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
        self.sort_fields: List[Tuple[str, bool]] = [("area", True)]  # (campo, reverse)
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

    def run(
        self,
        available_shapes: List[Dict[str, Any]],
        bed_width_mm: float,
        bed_height_mm: float,
        target_count: int = 16,
        gap_mm: float = 1.0,
        macro_script: Optional[str] = None,
        dieproc_params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Executa o pipeline completo da macro sobre as peças."""
        if not available_shapes:
            return []

        config = MacroCompiler.compile(macro_script)
        # Se gap_mm explícito foi passado e difere de 1.0 mm padrão, prioriza o configurado
        if gap_mm and gap_mm > 0.0:
            config.gap = float(gap_mm)

        # 1. Análise Geométrica e Auto-Tune de IA Local
        primary_family = "COMPACTA_SOLA_CALCANHAR"
        extractor = ShapeFeatureExtractor()
        if available_shapes:
            primary_family = extractor.classify_family(available_shapes[0].get("contour", []))

        bandit_suggestion = None
        if config.ai_auto_tune:
            bandit_suggestion = self.ai_brain.suggest_optimized_macro_params(primary_family)
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

        sorted_shapes = list(available_shapes)
        for field_name, rev in reversed(config.sort_fields):
            sorted_shapes.sort(key=lambda s, fn=field_name: _get_sort_val(s, fn), reverse=rev)

        # 3. Monta a Fila de Peças a Cortar
        shape_queue = []
        for s in sorted_shapes:
            qty = int(s.get("pairs", 24)) * 2  # 1 par = 2 peças (pé esquerdo e pé direito)
            for _ in range(qty):
                shape_queue.append(s)

        if not shape_queue:
            shape_queue = list(sorted_shapes)

        max_pieces = target_count if (target_count and target_count > 0) else len(shape_queue)

        # 4. Posicionamento Base por Fileiras (Cluster + Stagger + Binary Contact)
        margin = max(8.0, config.gap * 1.5)
        gap = max(0.5, config.gap)

        placed = []
        grid = SpatialGrid(cell_size=100.0)

        cur_x = margin
        row_baseline_y = margin
        row_height = 0.0
        row_idx = 0
        idx = 1

        angles_pool = config.cluster_angles if config.cluster_angles else [0.0, 180.0]

        for i in range(max_pieces):
            shape = shape_queue[i % len(shape_queue)]
            base_rot = angles_pool[i % len(angles_pool)]

            # Testa pequena varredura angular (sweep) para melhor acomodação de base
            best_rot = base_rot
            best_trial_y = bed_height_mm * 2.0
            best_poly = None
            best_bbox = None

            sweep_angles = [base_rot]
            swp = config.sweep_from
            while swp <= config.sweep_to + 1e-4:
                ang = (base_rot + swp) % 360.0
                if ang not in sweep_angles:
                    sweep_angles.append(ang)
                swp += config.sweep_step

            # Avalia rotação que permite a coordenada Y mais compacta
            for rot_candidate in sweep_angles:
                poly0 = transform_contour(shape["contour"], 0, 0, rot_candidate)
                min_x, min_y, max_x, max_y = polygon_bbox(poly0)
                w = max_x - min_x
                h = max_y - min_y

                # Verifica quebra de linha se ultrapassar a largura da Placa
                test_cur_x = cur_x
                test_baseline_y = row_baseline_y
                if test_cur_x + w > bed_width_mm - margin:
                    test_cur_x = margin + ((row_idx + 1) % 2) * (w * config.shift_x)
                    test_baseline_y = row_baseline_y + (row_height + gap)

                trial_y = max(margin, test_baseline_y)
                poly_fn = lambda y, cx=test_cur_x, mx=min_x, my=min_y, r=rot_candidate: transform_contour(shape["contour"], cx - mx, y - my, r)
                query_bbox = (test_cur_x - gap, max(0.0, trial_y - gap * 2.0), test_cur_x + w + gap, bed_height_mm)
                colliders = grid.query_potential_colliders(query_bbox, gap=gap)

                if colliders:
                    max_c_y = max(cb[3] for _, cb in colliders)
                    start_val = max(trial_y, max_c_y + gap)
                    trial_y = find_contact_coordinate_binary(poly_fn, colliders, gap, start_val, trial_y)

                c_poly = poly_fn(trial_y)
                c_bbox = polygon_bbox(c_poly)

                if not any(polygons_collide(c_poly, cp, gap=gap, bbox_a=c_bbox, bbox_b=cb) for cp, cb in colliders):
                    if trial_y < best_trial_y:
                        best_trial_y = trial_y
                        best_rot = rot_candidate
                        best_poly = c_poly
                        best_bbox = c_bbox

            if best_poly is None:
                # Não coube sem colisão
                continue

            # Aplica a melhor rotação encontrada
            poly0 = transform_contour(shape["contour"], 0, 0, best_rot)
            min_x, min_y, max_x, max_y = polygon_bbox(poly0)
            w = max_x - min_x
            h = max_y - min_y

            if cur_x + w > bed_width_mm - margin:
                row_idx += 1
                cur_x = margin + (row_idx % 2) * (w * config.shift_x)
                row_baseline_y += (row_height + gap)
                row_height = 0.0

            trial_y = best_trial_y
            c_poly = transform_contour(shape["contour"], cur_x - min_x, trial_y - min_y, best_rot)
            c_bbox = polygon_bbox(c_poly)

            # Verifica se ultrapassa o limite físico superior da Placa
            if trial_y + h > bed_height_mm - margin:
                break

            # Zero Colisão Absoluta
            colliders = grid.query_potential_colliders(c_bbox, gap=gap)
            if any(polygons_collide(c_poly, cp, gap=gap, bbox_a=c_bbox, bbox_b=cb) for cp, cb in colliders):
                continue

            s_sz = str(shape.get("size") or shape.get("taglia") or "41")
            p_color = get_color_for_size(s_sz, idx)
            piece = {
                "id": idx,
                "shape": shape,
                "name": shape.get("name", "Molde"),
                "size": s_sz,
                "color": p_color,
                "contour": shape.get("contour", []),
                "holes": shape.get("holes", []),
                "internal_cuts": shape.get("internal_cuts", []),
                "stitching": shape.get("stitching", []),
                "x": cur_x - min_x,
                "y": trial_y - min_y,
                "rotation": best_rot,
                "poly": c_poly,
                "bbox": c_bbox
            }
            placed.append(piece)
            grid.insert(idx, c_poly, c_bbox)
            idx += 1

            cur_x += (w + gap)
            if (trial_y - row_baseline_y + h) > row_height:
                row_height = trial_y - row_baseline_y + h

        # 5. Compactação por Gravidade Vetorial Contínua (GRAVITY VECTOR)
        self._apply_vector_gravity(placed, grid, bed_width_mm, bed_height_mm, config, margin, gap)

        # 6. Micro-acomodação Angular (JIGGLE)
        self._apply_jiggle(placed, grid, bed_width_mm, bed_height_mm, config, margin, gap)

        # 7. Preenchimento de Cavidades / Vazios (FILL HOLES)
        if config.fill_holes_enabled:
            self._apply_fill_holes(placed, grid, shape_queue, bed_width_mm, bed_height_mm, config, margin, gap)

        # 8. Cálculo de Rendimento e Feedback ao Cérebro de IA
        useful_area_mm2 = sum(polygon_area(p.get("contour", [])) for p in placed)
        bed_area_m2 = (bed_width_mm * bed_height_mm) / 1_000_000.0
        yield_pct = (useful_area_mm2 / 1_000_000.0 / bed_area_m2 * 100.0) if bed_area_m2 > 0 else 0.0

        if config.ai_auto_tune and bandit_suggestion and "arm_index" in bandit_suggestion:
            self.ai_brain.record_macro_execution_feedback(
                primary_family,
                bandit_suggestion["arm_index"],
                yield_pct
            )

        # Limpa referências internas temporárias antes de retornar
        result_pieces = []
        for p in placed:
            res_item = {
                "id": p["id"],
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
        grid: SpatialGrid,
        bed_width: float,
        bed_height: float,
        config: MacroConfig,
        margin: float,
        gap: float
    ) -> None:
        """Move as peças na direção do vetor de gravidade (vx, vy) em passos decrescentes."""
        if not placed:
            return

        vx = config.gravity_vx
        vy = config.gravity_vy
        norm = math.hypot(vx, vy)
        if norm <= 0.001:
            return
        dx_dir = vx / norm
        dy_dir = vy / norm

        for step in config.gravity_steps:
            for p in placed:
                p_id = p["id"]
                c = p["contour"]
                rot = p["rotation"]
                old_x = p["x"]
                old_y = p["y"]
                old_poly = p["poly"]
                old_bbox = p["bbox"]

                # Tenta transladar no vetor de gravidade
                test_x = old_x + dx_dir * step
                test_y = old_y + dy_dir * step

                test_poly = transform_contour(c, test_x, test_y, rot)
                test_bbox = polygon_bbox(test_poly)

                # Valida limites físicos da Placa
                if (test_bbox[0] < margin or test_bbox[1] < margin or
                    test_bbox[2] > bed_width - margin or test_bbox[3] > bed_height - margin):
                    continue

                # Valida colisão contra as outras peças no grid
                colliders = [it for it in grid.query_potential_colliders(test_bbox, gap=gap) if it[0] != old_poly]
                if not any(polygons_collide(test_poly, cp, gap=gap, bbox_a=test_bbox, bbox_b=cb) for cp, cb in colliders):
                    # Aceita o deslocamento de gravidade
                    p["x"] = test_x
                    p["y"] = test_y
                    p["poly"] = test_poly
                    p["bbox"] = test_bbox
                    # Atualiza grade espacial
                    grid.insert(p_id, test_poly, test_bbox)

    def _apply_jiggle(
        self,
        placed: List[Dict[str, Any]],
        grid: SpatialGrid,
        bed_width: float,
        bed_height: float,
        config: MacroConfig,
        margin: float,
        gap: float
    ) -> None:
        """Testa micro-rotações controladas (jiggle) para compactação complementar."""
        if not placed or not config.jiggle_angles:
            return

        for p in placed:
            p_id = p["id"]
            c = p["contour"]
            cur_rot = p["rotation"]
            cur_x = p["x"]
            cur_y = p["y"]
            cur_poly = p["poly"]
            cur_bbox = p["bbox"]

            best_y = cur_bbox[1]
            best_rot = cur_rot
            best_poly = cur_poly
            best_bbox = cur_bbox

            for d_rot in config.jiggle_angles:
                if abs(d_rot) < 1e-4:
                    continue
                test_rot = (cur_rot + d_rot) % 360.0
                test_poly = transform_contour(c, cur_x, cur_y, test_rot)
                test_bbox = polygon_bbox(test_poly)

                if (test_bbox[0] < margin or test_bbox[1] < margin or
                    test_bbox[2] > bed_width - margin or test_bbox[3] > bed_height - margin):
                    continue

                colliders = [it for it in grid.query_potential_colliders(test_bbox, gap=gap) if it[0] != cur_poly]
                if not any(polygons_collide(test_poly, cp, gap=gap, bbox_a=test_bbox, bbox_b=cb) for cp, cb in colliders):
                    if test_bbox[1] < best_y:
                        best_y = test_bbox[1]
                        best_rot = test_rot
                        best_poly = test_poly
                        best_bbox = test_bbox

            if best_rot != cur_rot:
                p["rotation"] = best_rot
                p["poly"] = best_poly
                p["bbox"] = best_bbox
                grid.insert(p_id, best_poly, best_bbox)

    def _apply_fill_holes(
        self,
        placed: List[Dict[str, Any]],
        grid: SpatialGrid,
        shape_queue: List[Dict[str, Any]],
        bed_width: float,
        bed_height: float,
        config: MacroConfig,
        margin: float,
        gap: float
    ) -> None:
        """Encaixa peças pequenas em vazios existentes nas fileiras inferiores da mesa."""
        if not shape_queue or not placed:
            return

        max_placed_y = max(p["bbox"][3] for p in placed)
        next_id = max(p["id"] for p in placed) + 1

        for shape in shape_queue:
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
                cand_x = margin
                placed_in_hole = False

                while cand_x + w <= bed_width - margin:
                    cand_y = margin
                    while cand_y + h <= max_placed_y - gap:
                        test_poly = transform_contour(c, cand_x - min_x, cand_y - min_y, rot)
                        test_bbox = (cand_x, cand_y, cand_x + w, cand_y + h)

                        colliders = grid.query_potential_colliders(test_bbox, gap=gap)
                        if not any(polygons_collide(test_poly, cp, gap=gap, bbox_a=test_bbox, bbox_b=cb) for cp, cb in colliders):
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
                            grid.insert(next_id, test_poly, test_bbox)
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
    dieproc_params: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Função de entrada oficial do motor 'IA-teste'.
    Combina macros declarativas com aprendizado de máquina local e zero colisão.
    """
    # Se o script não foi passado explicitamente, busca no dieproc_params ou banco
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
        dieproc_params=dieproc_params
    )
