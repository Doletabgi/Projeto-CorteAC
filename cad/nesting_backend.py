"""
cad/nesting_backend.py - Abstração e Gerenciamento de Backends de Nesting para CorteAC

Fornece a interface padrão NestingBackend (Protocol) e as implementações:
- PythonBackend: Motor padrão de referência (embrulha cad/nesting_engine.py).
- NfpBackend: Motor acelerado por No-Fit Polygon analítico (cad/nfp.py) com cache de contornos.

A seleção é controlada pela variável de ambiente CORTEAC_BACKEND:
- Padrão: "python" (preserva 100% da compatibilidade legado).
- Alternativo: "nfp" (ativa encosto analítico de alta performance).
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any, Dict, List, Optional, Protocol, Tuple

from cad.colors import get_color_for_size
from cad.geometry import (
    SpatialGrid,
    clear_transform_cache,
    polygon_bbox,
    polygons_collide,
    transform_contour,
)
from cad.nfp import (
    clear_nfp_cache,
    compute_nfp,
    contact_placement,
    contact_placement_x,
    contact_placement_y,
    decompose_convex,
)

logger = logging.getLogger(__name__)


class NestingBackend(Protocol):
    """Protocolo formal para motores de nesting 2D intercambiáveis."""

    def nest_sheet(
        self,
        available_shapes: list,
        bed_width_mm: float,
        bed_height_mm: float,
        target_count: int = 16,
        strategy: str = "flashnestsheet",
        params: Any = "stdNOTFill",
        gap_mm: float = 1.0,
        dieproc_params: Optional[dict] = None,
        db: Any = None,
        margins: Optional[dict] = None,
        layers: Optional[int] = None,
    ) -> list[dict[str, Any]]: ...


class PythonBackend:
    """Backend legado padrão: executa o motor clássico em cad/nesting_engine.py."""

    def nest_sheet(
        self,
        available_shapes: list,
        bed_width_mm: float,
        bed_height_mm: float,
        target_count: int = 16,
        strategy: str = "flashnestsheet",
        params: Any = "stdNOTFill",
        gap_mm: float = 1.0,
        dieproc_params: Optional[dict] = None,
        db: Any = None,
        margins: Optional[dict] = None,
        layers: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        from cad.nesting_engine import _auto_nest_pieces_core

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


class NfpBackend:
    """Backend analítico de alta performance baseado em No-Fit Polygon (NFP)."""

    def nest_sheet(
        self,
        available_shapes: list,
        bed_width_mm: float,
        bed_height_mm: float,
        target_count: int = 16,
        strategy: str = "flashnestsheet",
        params: Any = "stdNOTFill",
        gap_mm: float = 1.0,
        dieproc_params: Optional[dict] = None,
        db: Any = None,
        margins: Optional[dict] = None,
        layers: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        try:
            return self._nest_sheet_nfp(
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
        except Exception as ex:
            logger.warning(
                "Falha na execução do NfpBackend (%s). Acionando fallback automático para PythonBackend.",
                ex,
            )
            from cad.nesting_engine import _auto_nest_pieces_core

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

    def _nest_sheet_nfp(
        self,
        available_shapes: list,
        bed_width_mm: float,
        bed_height_mm: float,
        target_count: int = 16,
        strategy: str = "flashnestsheet",
        params: Any = "stdNOTFill",
        gap_mm: float = 1.0,
        dieproc_params: Optional[dict] = None,
        db: Any = None,
        margins: Optional[dict] = None,
        layers: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        # Estratégias especializadas não-chapa (IA-teste, tape_a) repassam diretamente
        strat_clean = str(strategy).lower()
        if strat_clean in ("ia-teste", "ia_teste", "iateste", "tape_a", "tape", "tiras", "fita"):
            from cad.nesting_engine import _auto_nest_pieces_core

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

        if not available_shapes:
            return []

        # Suporte a entrada simplificada (lista de contornos puros) para testes de conformidade
        if available_shapes and isinstance(available_shapes[0], (list, tuple)):
            norm_shapes = []
            for s_idx, c in enumerate(available_shapes):
                norm_shapes.append({
                    "id": s_idx + 1,
                    "name": f"Shape_{s_idx+1}",
                    "size": "41",
                    "contour": [{"x": float(p[0] if isinstance(p, (tuple, list)) else p["x"]),
                                 "y": float(p[1] if isinstance(p, (tuple, list)) else p["y"])}
                                for p in c],
                    "pairs": 1,
                    "sequence": s_idx + 1,
                })
            available_shapes = norm_shapes

        # Resolução dos parâmetros de dieproc dp98 idêntica ao motor legado
        dp_config = dict(dieproc_params) if dieproc_params else {}
        if not dp_config:
            if params == "ALTERNADO":
                dp_config = {
                    "coupling": "0/0 0/180",
                    "gap1": gap_mm,
                    "row_interlock": True,
                    "range1_from": -3.0,
                    "range1_to": 3.0,
                    "range1_step": 1.0,
                }
            elif params == "DIREITA":
                dp_config = {
                    "coupling": "0/0",
                    "gap1": gap_mm,
                    "row_interlock": True,
                    "range1_from": -3.0,
                    "range1_to": 3.0,
                    "range1_step": 1.0,
                }
            elif params == "ESQUERDA":
                dp_config = {
                    "coupling": "0/180",
                    "gap1": gap_mm,
                    "row_interlock": True,
                    "range1_from": -3.0,
                    "range1_to": 3.0,
                    "range1_step": 1.0,
                }
            elif params == "GAP 2":
                dp_config = {
                    "coupling": "0/0 0/180",
                    "gap1": 2.0,
                    "row_interlock": True,
                    "range1_from": -3.0,
                    "range1_to": 3.0,
                    "range1_step": 1.0,
                }
            elif params == "HighYield":
                dp_config = {
                    "coupling": "0/0 0/180",
                    "gap1": max(0.5, float(gap_mm) * 0.7),
                    "row_interlock": True,
                    "range1_from": -5.0,
                    "range1_to": 5.0,
                    "range1_step": 0.5,
                }
            elif params == "FastNest":
                dp_config = {
                    "coupling": "0/0 0/180",
                    "gap1": max(1.5, float(gap_mm) * 1.5),
                    "row_interlock": True,
                    "range1_from": 0.0,
                    "range1_to": 0.0,
                    "range1_step": 0.0,
                }
            else:
                dp_config = {
                    "coupling": "0/0",
                    "gap1": gap_mm,
                    "row_interlock": False,
                    "range1_from": 0.0,
                    "range1_to": 1.0,
                    "range1_step": 1.0,
                }

        if gap_mm is not None:
            dp_config["gap1"] = float(gap_mm)

        coupling = dp_config.get("coupling", "0/0 0/180")
        from cad.nesting_engine import parse_coupling_angles, sort_shapes_by_sequence

        base_angles = parse_coupling_angles(coupling)
        r1_from = float(dp_config.get("range1_from", -3.0))
        r1_to = float(dp_config.get("range1_to", 3.0))
        r1_step = float(dp_config.get("range1_step", 1.0) or 1.0)
        gap = max(0.0, float(dp_config.get("gap1", 1.0) if dp_config.get("gap1") is not None else 1.0))
        row_interlock = bool(dp_config.get("row_interlock", True))

        # Otimização fina de ângulo no Range 1
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
                    poly = transform_contour(test_shape["contour"], 0.0, 0.0, a + delta)
                    min_x, min_y, max_x, max_y = polygon_bbox(poly)
                    tot_w += (max_x - min_x)
                    tot_h = max(tot_h, max_y - min_y)
                approx_area = tot_w * tot_h
                if approx_area < best_area:
                    best_area = approx_area
                    best_delta = delta

        effective_angles = [(a + best_delta) % 360.0 for a in base_angles]

        # Resolução de margens
        m_dict = dict(margins) if margins else (dp_config.get("margins") if "margins" in dp_config else None)
        m_left = float(m_dict.get("left", 10.0)) if m_dict else 10.0
        m_right = float(m_dict.get("right", 10.0)) if m_dict else 10.0
        m_top = float(m_dict.get("top", 10.0)) if m_dict else 10.0
        m_bottom = float(m_dict.get("bottom", 10.0)) if m_dict else 10.0

        # Invalidação seletiva do cache de geometria e NFP
        clear_transform_cache()
        clear_nfp_cache()

        sorted_shapes, _ = sort_shapes_by_sequence(available_shapes)

        shape_queue = []
        for s in sorted_shapes:
            if "target_pieces" in s:
                qty = max(0, int(s["target_pieces"]))
            else:
                s_layers = layers or s.get("layers") or (dp_config.get("layers") if isinstance(dp_config, dict) else None) or 2
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

        sample_poly = transform_contour(shape_queue[0]["contour"], 0.0, 0.0, effective_angles[0])
        s_min_x, s_min_y, s_max_x, s_max_y = polygon_bbox(sample_poly)
        avg_w = max(10.0, s_max_x - s_min_x)
        avg_h = max(10.0, s_max_y - s_min_y)

        is_alternating = (len(base_angles) == 2 and abs(abs(base_angles[0] - base_angles[1]) - 180.0) < 1e-3) or coupling == "0/0 0/180"

        cur_row_y = m_bottom
        row_idx = 0
        grid = SpatialGrid(cell_size=100.0)
        rows: list[list[dict[str, Any]]] = []
        placed: list[dict[str, Any]] = []
        queue_idx = 0
        idx = 1

        sanity_enabled = os.getenv("CORTEAC_NFP_SANITY", "0").strip() == "1"

        while queue_idx < len(shape_queue) and cur_row_y < bed_height_mm - m_top and len(placed) < max_pieces:
            row_pieces: list[dict[str, Any]] = []
            is_odd_row = (row_idx % 2 == 1)

            # Preenchimento horizontal da linha com encosto milimétrico acelerado por NFP
            while queue_idx < len(shape_queue) and (len(placed) + len(row_pieces)) < max_pieces:
                shape = shape_queue[queue_idx]
                piece_in_row_idx = len(row_pieces)

                if is_alternating:
                    rot = 180.0 if ((piece_in_row_idx % 2 == 1) ^ is_odd_row) else 0.0
                else:
                    angle_idx = (piece_in_row_idx + (row_idx if row_interlock else 0)) % len(effective_angles)
                    rot = effective_angles[angle_idx]

                poly0 = transform_contour(shape["contour"], 0.0, 0.0, rot)
                min_x, min_y, max_x, max_y = polygon_bbox(poly0)
                w = max_x - min_x
                h = max_y - min_y

                if not row_pieces:
                    cand_x = m_left
                else:
                    prev = row_pieces[-1]
                    target_origin_y = cur_row_y - min_y

                    # Encosto analítico exato via NFP
                    req_x = contact_placement_x(poly0, prev["poly"], target_origin_y, gap=gap)
                    if req_x is not None:
                        cand_x = req_x + min_x
                    else:
                        cand_x = prev["bbox"][2] + gap

                    min_cand_x = max(m_left, prev["bbox"][0] - 25.0)
                    if cand_x < min_cand_x:
                        cand_x = min_cand_x

                    # Sanity pass opcional (CORTEAC_NFP_SANITY=1 para debug)
                    if sanity_enabled:
                        colliders_row = [(p["poly"], p["bbox"]) for p in row_pieces]
                        c_poly = transform_contour(shape["contour"], cand_x - min_x, cur_row_y - min_y, rot)
                        c_bbox = polygon_bbox(c_poly)
                        while any(polygons_collide(c_poly, cp, gap=gap, bbox_a=c_bbox, bbox_b=cb) for cp, cb in colliders_row):
                            cand_x += 0.05
                            c_poly = transform_contour(shape["contour"], cand_x - min_x, cur_row_y - min_y, rot)
                            c_bbox = polygon_bbox(c_poly)

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
                    "h": h,
                }
                row_pieces.append(item)
                queue_idx += 1
                idx += 1

            if not row_pieces:
                break

            # Rebaixamento da LINHA INTEIRA como corpo rígido (Row Interlock acelerado)
            if rows and row_interlock:
                prev_row = rows[-1]
                prev_max_y = max(p["bbox"][3] for p in prev_row)
                high_y = prev_max_y + gap
                low_y = prev_max_y - avg_h * 0.40

                # Interseção analítica rápida via NFP para estimar target_y
                max_req_y = low_y
                for p in row_pieces:
                    p_min_x = p["bbox"][0]
                    p_max_x = p["bbox"][2]
                    poly0_p = transform_contour(p["shape"]["contour"], 0.0, 0.0, p["rotation"])
                    for prev_p in prev_row:
                        if prev_p["bbox"][2] + gap < p_min_x or prev_p["bbox"][0] - gap > p_max_x:
                            continue
                        contact_y = contact_placement_y(poly0_p, prev_p["poly"], p["x"], gap=gap)
                        if contact_y is not None:
                            piece_req_row_y = contact_y + p["min_y"] + 0.05
                            if piece_req_row_y > max_req_y:
                                max_req_y = piece_req_row_y

                target_y = max(low_y, max_req_y)
                if target_y > high_y:
                    target_y = high_y

                # Sanity pass opcional (CORTEAC_NFP_SANITY=1 para debug)
                if sanity_enabled:
                    def row_collides_at(test_y: float) -> bool:
                        dy = test_y - cur_row_y
                        for p in row_pieces:
                            test_poly = transform_contour(p["shape"]["contour"], p["x"], p["y"] + dy, p["rotation"])
                            test_bbox = polygon_bbox(test_poly)
                            cols = grid.query_potential_colliders(test_bbox, gap=gap)
                            if any(polygons_collide(test_poly, cp, gap=gap, bbox_a=test_bbox, bbox_b=cb) for cp, cb in cols):
                                return True
                        return False

                    while row_collides_at(target_y):
                        target_y += 0.05

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
                placed.append(p)
            rows.append(row_pieces)
            row_idx += 1

        return placed


_PYTHON_BACKEND_INSTANCE = PythonBackend()
_NFP_BACKEND_INSTANCE = NfpBackend()
_NFP_NOTICE_LOGGED = False


def get_nesting_backend(backend_name: Optional[str] = None) -> NestingBackend:
    """
    Retorna a instância singleton do backend selecionado.
    Por padrão retorna NfpBackend (CORTEAC_BACKEND="nfp").
    Se CORTEAC_BACKEND="python", retorna PythonBackend para compatibilidade e fallback.
    """
    global _NFP_NOTICE_LOGGED
    name = (backend_name or os.getenv("CORTEAC_BACKEND", "nfp")).strip().lower()
    if name == "python":
        return _PYTHON_BACKEND_INSTANCE
    if not _NFP_NOTICE_LOGGED:
        logger.info("NFP backend active (default); fallback to Python if error")
        _NFP_NOTICE_LOGGED = True
    return _NFP_BACKEND_INSTANCE
