"""
JobManager 2000 (Python Edition)
cad/ai_learner.py - IA Local Embarcada 100% Nativa (Pure Python 3.12)

Módulo de Inteligência Artificial Local para Nesting Industrial:
1. ShapeFeatureExtractor: Assinatura geométrica e classificação de moldes em famílias.
2. NestingAIBrain:
   - Aprendizado por Imitação (learn_from_operator_save): captura padrões e vetores relativos no Ctrl+S.
   - Aprendizado por Reforço UCB1 (suggest_optimized_macro_params / record_macro_execution_feedback):
     calibração dinâmica dos hiperparâmetros de nesting por família geométrica.
   - Persistência idempotente via tabela `settings` (MySQL 8.0 e SQLite).
"""

import math
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

from cad.geometry import polygon_area, polygon_perimeter, polygon_bbox
from cad.die_parser import clean_shape_name


@dataclass
class ShapeFeatures:
    area: float
    perimeter: float
    width: float
    height: float
    bbox_area: float
    rectangularity: float
    compactness: float
    aspect_ratio: float
    family: str

    def get(self, key, default=None):
        return getattr(self, key, default)


# ---------------------------------------------------------------------------
# 1. Extrator de Características Geométricas
# ---------------------------------------------------------------------------

class ShapeFeatureExtractor:
    """
    Extrai características geométricas normalizadas e invariantes a escala/rotação
    de contornos 2D para classificação em famílias industriais de calçados.
    """

    @classmethod
    def extract(cls, contour: List[Dict[str, float]]) -> ShapeFeatures:
        """Extrai características e classifica o contorno diretamente."""
        d = cls.extract_features(contour)
        fam = cls.classify_family(d)
        return ShapeFeatures(
            area=d["area"],
            perimeter=d["perimeter"],
            width=d["width"],
            height=d["height"],
            bbox_area=d["bbox_area"],
            rectangularity=d["rectangularity"],
            compactness=d["compactness"],
            aspect_ratio=d["aspect_ratio"],
            family=fam
        )

    @staticmethod
    def extract_features(contour: List[Dict[str, float]]) -> Dict[str, float]:
        """Calcula métricas geométricas fundamentais do contorno."""
        if not contour or len(contour) < 3:
            return {
                "area": 0.0,
                "perimeter": 0.0,
                "width": 0.0,
                "height": 0.0,
                "bbox_area": 0.001,
                "rectangularity": 0.0,
                "compactness": 0.0,
                "aspect_ratio": 1.0,
            }

        area = polygon_area(contour)
        perimeter = polygon_perimeter(contour)
        min_x, min_y, max_x, max_y = polygon_bbox(contour)
        w = max(0.001, max_x - min_x)
        h = max(0.001, max_y - min_y)
        bbox_area = max(0.001, w * h)

        rectangularity = min(1.0, max(0.0, area / bbox_area))
        compactness = (4.0 * math.pi * area) / (perimeter ** 2) if perimeter > 0.001 else 0.0
        compactness = min(1.0, max(0.0, compactness))
        aspect_ratio = max(w, h) / max(min(w, h), 0.001)

        return {
            "area": round(area, 2),
            "perimeter": round(perimeter, 2),
            "width": round(w, 2),
            "height": round(h, 2),
            "bbox_area": round(bbox_area, 2),
            "rectangularity": round(rectangularity, 4),
            "compactness": round(compactness, 4),
            "aspect_ratio": round(aspect_ratio, 3),
        }

    @classmethod
    def classify_family(cls, contour_or_features) -> str:
        """
        Classifica o molde em uma de 4 famílias geométricas da indústria de calçado:
        - TIRA_LONGA: faixas, correias, debruns, atacadores.
        - CURVA_CONCAVA_GASPEA: gáspeas, biqueiras, tiras curvas em zigue-zague.
        - COMPACTA_SOLA_CALCANHAR: solados, palmilhas, calcanheiras, contrafortes.
        - PADRAO_IRREGULAR: moldes assimétricos e peças sortidas.
        """
        if isinstance(contour_or_features, list):
            f = cls.extract_features(contour_or_features)
        elif isinstance(contour_or_features, dict):
            if "rectangularity" in contour_or_features:
                f = contour_or_features
            else:
                f = cls.extract_features(contour_or_features.get("contour", []))
        else:
            return "PADRAO_IRREGULAR"

        aspect_ratio = f.get("aspect_ratio", 1.0)
        compactness = f.get("compactness", 0.0)
        rectangularity = f.get("rectangularity", 0.0)

        if aspect_ratio >= 3.0 or compactness < 0.15:
            return "TIRA_LONGA"
        if compactness < 0.35 and rectangularity < 0.65:
            return "CURVA_CONCAVA_GASPEA"
        if rectangularity >= 0.65 or compactness >= 0.50:
            return "COMPACTA_SOLA_CALCANHAR"
        return "PADRAO_IRREGULAR"


# ---------------------------------------------------------------------------
# 2. Cérebro Local de IA (NestingAIBrain)
# ---------------------------------------------------------------------------

BANDIT_ARMS = [
    {
        "id": 0,
        "name": "Equilibrado Padrão",
        "shift_x": 0.38,
        "gravity_x": -0.5,
        "gravity_y": -1.0,
        "sweep_max": 3.0,
        "steps": [8.0, 4.0, 2.0, 0.5]
    },
    {
        "id": 1,
        "name": "Alta Compactação Direcional",
        "shift_x": 0.50,
        "gravity_x": -0.8,
        "gravity_y": -1.0,
        "sweep_max": 2.0,
        "steps": [10.0, 5.0, 2.0, 0.5]
    },
    {
        "id": 2,
        "name": "Varredura Angular Ampliada",
        "shift_x": 0.25,
        "gravity_x": -0.3,
        "gravity_y": -1.0,
        "sweep_max": 4.0,
        "steps": [6.0, 3.0, 1.0, 0.5]
    },
    {
        "id": 3,
        "name": "Passo Fino Rápido",
        "shift_x": 0.45,
        "gravity_x": -1.0,
        "gravity_y": -1.0,
        "sweep_max": 1.5,
        "steps": [8.0, 4.0, 2.0, 1.0]
    },
    {
        "id": 4,
        "name": "Gravidade Vertical Estrita",
        "shift_x": 0.30,
        "gravity_x": 0.0,
        "gravity_y": -1.0,
        "sweep_max": 5.0,
        "steps": [8.0, 4.0, 2.0, 0.5]
    }
]


class NestingAIBrain:
    """
    Cérebro de Inteligência Artificial Local Embarcada.
    - Não requer internet nem bibliotecas externas.
    - Executa aprendizado por imitação com base nos salvamentos manuais dos operadores (Ctrl+S).
    - Executa calibração contínua de hiperparâmetros por UCB1 Multi-Armed Bandit.
    """

    def __init__(self, db=None):
        self.db = db

    # -----------------------------------------------------------------------
    # Aprendizado por Imitação (Ctrl+S do Operador)
    # -----------------------------------------------------------------------

    def learn_from_operator_save(
        self,
        placed_pieces: List[Dict[str, Any]],
        sheet_w: float,
        sheet_h: float
    ) -> int:
        """
        Extrai relações e vetores espaciais relativos aprendidos entre pares de peças
        que o operador organizou e salvou no LayoutEditorView (Ctrl+S).
        Retorna o número de novos hábitos registrados.
        """
        if not placed_pieces or len(placed_pieces) < 2:
            return 0

        learned_pairs = []
        n = len(placed_pieces)
        extractor = ShapeFeatureExtractor()

        for i in range(n):
            p1 = placed_pieces[i]
            c1 = p1.get("contour", [])
            x1 = float(p1.get("x", 0.0))
            y1 = float(p1.get("y", 0.0))
            rot1 = float(p1.get("rotation", 0.0))
            name1 = clean_shape_name(str(p1.get("name", "M1")))
            fam1 = extractor.classify_family(c1)

            # Centro aproximado
            if c1:
                b1 = polygon_bbox(c1)
                cx1 = x1 + (b1[0] + b1[2]) / 2.0
                cy1 = y1 + (b1[1] + b1[3]) / 2.0
            else:
                cx1, cy1 = x1, y1

            for j in range(i + 1, min(i + 8, n)):
                p2 = placed_pieces[j]
                c2 = p2.get("contour", [])
                x2 = float(p2.get("x", 0.0))
                y2 = float(p2.get("y", 0.0))
                rot2 = float(p2.get("rotation", 0.0))
                name2 = clean_shape_name(str(p2.get("name", "M2")))
                fam2 = extractor.classify_family(c2)

                if c2:
                    b2 = polygon_bbox(c2)
                    cx2 = x2 + (b2[0] + b2[2]) / 2.0
                    cy2 = y2 + (b2[1] + b2[3]) / 2.0
                else:
                    cx2, cy2 = x2, y2

                dist = math.hypot(cx2 - cx1, cy2 - cy1)
                # Analisa pares vizinhos próximos na mesa de corte
                if 5.0 <= dist <= 180.0:
                    dx = cx2 - cx1
                    dy = cy2 - cy1
                    delta_angle = (rot2 - rot1) % 360.0
                    pair_key = f"{name1}::{name2}" if name1 <= name2 else f"{name2}::{name1}"
                    fam_pair_key = f"{fam1}::{fam2}" if fam1 <= fam2 else f"{fam2}::{fam1}"

                    learned_pairs.append({
                        "pair_key": pair_key,
                        "fam_pair_key": fam_pair_key,
                        "dx": round(dx, 2),
                        "dy": round(dy, 2),
                        "delta_angle": round(delta_angle, 1),
                        "dist": round(dist, 2),
                        "rot1": round(rot1, 1),
                        "rot2": round(rot2, 1)
                    })

        if not learned_pairs or not self.db:
            return 0

        # Carrega hábitos existentes da tabela settings
        existing_habits = []
        try:
            raw = self.db.get_setting("ai_operator_habits", "[]")
            existing_habits = json.loads(raw) if raw else []
            if not isinstance(existing_habits, list):
                existing_habits = []
        except Exception:
            existing_habits = []

        # Mescla com hábitos já aprendidos, priorizando novas evidências
        habits_map = {}
        for h in existing_habits:
            k = (h.get("pair_key"), round(h.get("delta_angle", 0.0), 0))
            habits_map[k] = h

        for lp in learned_pairs:
            k = (lp["pair_key"], round(lp["delta_angle"], 0))
            if k in habits_map:
                habits_map[k]["count"] = habits_map[k].get("count", 1) + 1
                # Média ponderada do deslocamento
                c = habits_map[k]["count"]
                habits_map[k]["dx"] = round((habits_map[k]["dx"] * (c - 1) + lp["dx"]) / c, 2)
                habits_map[k]["dy"] = round((habits_map[k]["dy"] * (c - 1) + lp["dy"]) / c, 2)
            else:
                lp["count"] = 1
                habits_map[k] = lp

        # Ranqueia os melhores 200 padrões da fábrica (por frequência de uso e compacidade)
        sorted_habits = sorted(
            habits_map.values(),
            key=lambda x: (x.get("count", 1), -x.get("dist", 999)),
            reverse=True
        )[:200]

        try:
            self.db.set_setting("ai_operator_habits", json.dumps(sorted_habits))
        except Exception as e:
            print(f"[NestingAIBrain] Erro ao persistir hábitos no banco: {e}")

        return len(learned_pairs)

    def get_learned_habits(self, fam_pair_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna os hábitos aprendidos armazenados no banco de dados."""
        if not self.db:
            return []
        try:
            raw = self.db.get_setting("ai_operator_habits", "[]")
            habits = json.loads(raw) if raw else []
            if not isinstance(habits, list):
                return []
            if fam_pair_key:
                return [h for h in habits if h.get("fam_pair_key") == fam_pair_key]
            return habits
        except Exception:
            return []

    # -----------------------------------------------------------------------
    # Aprendizado por Reforço (UCB1 Multi-Armed Bandit por Família)
    # -----------------------------------------------------------------------

    def suggest_optimized_macro_params(self, family_name: str = "COMPACTA_SOLA_CALCANHAR", deterministic: bool = False) -> Dict[str, Any]:
        """
        Seleciona o melhor braço de hiperparâmetros usando o algoritmo UCB1:
        UCB_i = avg_reward_i + c * sqrt(ln(N) / n_i)
        Garante equilíbrio entre explorar novos passos e explorar os melhores resultados.
        Se deterministic=True, congela exploração aleatória e seleciona estritamente por melhor recompensa média ou braço 0 padrão.
        """
        setting_key = f"ai_bandit_{family_name}"
        bandit_data = {}

        if self.db:
            try:
                raw = self.db.get_setting(setting_key, "{}")
                bandit_data = json.loads(raw) if raw else {}
            except Exception:
                bandit_data = {}

        arms_stats = bandit_data.get("arms", {})

        if deterministic:
            # Seleção puramente determinística para testes e reproducibilidade exata
            if not arms_stats:
                return {
                    **BANDIT_ARMS[0],
                    "arm_index": 0,
                    "family": family_name,
                    "reason": "Exploração Determinística (Braço 0 Padrão)"
                }
            best_arm = BANDIT_ARMS[0]
            best_reward = -float("inf")
            for arm in BANDIT_ARMS:
                arm_id = str(arm["id"])
                stats = arms_stats.get(arm_id, {})
                avg_r = stats.get("avg_reward", 0.0)
                if avg_r > best_reward:
                    best_reward = avg_r
                    best_arm = arm
            return {
                **best_arm,
                "arm_index": best_arm["id"],
                "family": family_name,
                "reason": f"Aproveitamento Determinístico Puro (reward={round(best_reward, 2)})"
            }

        total_trials = int(bandit_data.get("total_trials", 0))

        # 1. Se algum braço nunca foi testado, seleciona-o para exploração inicial
        for arm in BANDIT_ARMS:
            arm_id = str(arm["id"])
            if arm_id not in arms_stats or arms_stats[arm_id].get("count", 0) == 0:
                return {
                    **arm,
                    "arm_index": arm["id"],
                    "family": family_name,
                    "reason": "Exploração Inicial (UCB1 n_i=0)"
                }

        # 2. Se todos os braços já foram testados, calcula UCB1
        c = 1.414  # Constante de exploração sqrt(2)
        best_score = -float("inf")
        best_arm = BANDIT_ARMS[0]

        log_total = math.log(max(1, total_trials))

        for arm in BANDIT_ARMS:
            arm_id = str(arm["id"])
            stats = arms_stats[arm_id]
            count = stats.get("count", 1)
            avg_reward = stats.get("avg_reward", 0.0)

            exploration_bonus = c * math.sqrt(log_total / count)
            ucb_score = avg_reward + exploration_bonus

            if ucb_score > best_score:
                best_score = ucb_score
                best_arm = arm

        return {
            **best_arm,
            "arm_index": best_arm["id"],
            "family": family_name,
            "reason": f"Aproveitamento Otimizado UCB1 (score={round(best_score, 2)})"
        }

    def record_macro_execution_feedback(
        self,
        family_name: str,
        arm_index: int,
        achieved_yield: float
    ) -> None:
        """
        Registra a recompensa obtida (rendimento percentual do layout gerado)
        para atualizar a média e contagem do braço no UCB1 Bandit.
        """
        if not self.db or achieved_yield <= 0.0:
            return

        setting_key = f"ai_bandit_{family_name}"
        bandit_data = {}

        try:
            raw = self.db.get_setting(setting_key, "{}")
            bandit_data = json.loads(raw) if raw else {}
        except Exception:
            bandit_data = {}

        total_trials = int(bandit_data.get("total_trials", 0)) + 1
        arms_stats = bandit_data.get("arms", {})

        arm_id = str(arm_index)
        cur_stats = arms_stats.get(arm_id, {"count": 0, "total_reward": 0.0, "avg_reward": 0.0})

        new_count = cur_stats.get("count", 0) + 1
        new_total_reward = cur_stats.get("total_reward", 0.0) + achieved_yield
        new_avg_reward = new_total_reward / new_count

        arms_stats[arm_id] = {
            "count": new_count,
            "total_reward": round(new_total_reward, 2),
            "avg_reward": round(new_avg_reward, 2)
        }

        bandit_data["total_trials"] = total_trials
        bandit_data["arms"] = arms_stats

        try:
            self.db.set_setting(setting_key, json.dumps(bandit_data))
        except Exception as e:
            print(f"[NestingAIBrain] Erro ao gravar feedback bandit no banco: {e}")

    def select_arm(self, family_name: str = "COMPACTA_SOLA_CALCANHAR") -> Tuple[int, Dict[str, Any]]:
        """Alias para suggest_optimized_macro_params retornando (arm_index, params)."""
        res = self.suggest_optimized_macro_params(family_name)
        return res["arm_index"], res

    def record_feedback(self, family_name: str, arm_index: int, reward: float) -> None:
        """Alias para record_macro_execution_feedback."""
        self.record_macro_execution_feedback(family_name, arm_index, reward)

    # -----------------------------------------------------------------------
    # Informações de Status da Memória da IA Local
    # -----------------------------------------------------------------------

    def get_memory_status(self) -> Dict[str, Any]:
        """Retorna um sumário do estado atual de aprendizado da IA Local."""
        habits = self.get_learned_habits()
        families_tuned = 0
        total_runs = 0

        if self.db:
            for fam in ["TIRA_LONGA", "CURVA_CONCAVA_GASPEA", "COMPACTA_SOLA_CALCANHAR", "PADRAO_IRREGULAR"]:
                raw = self.db.get_setting(f"ai_bandit_{fam}")
                if raw:
                    try:
                        d = json.loads(raw)
                        trials = d.get("total_trials", 0)
                        if trials > 0:
                            families_tuned += 1
                            total_runs += trials
                    except Exception:
                        pass

        status_text = "Ativo" if (habits or families_tuned > 0 or self.db is not None) else "Stand by"
        summary = (
            f"IA Local Ativa — {len(habits)} hábitos aprendidos (Ctrl+S), "
            f"{families_tuned} famílias calibradas por UCB1 ({total_runs} execuções)"
        )

        return {
            "status": status_text,
            "habits_count": len(habits),
            "families_tuned": families_tuned,
            "total_runs": total_runs,
            "summary": summary
        }
