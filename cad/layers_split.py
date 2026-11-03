"""
JobManager 2000 (Python Edition)
Módulo de Separação Automática de Sobras de Camadas (layers_split.py)

Regra de negócio confirmada pelo operador:
- Com 4 camadas e demandas com pares ÍMPARES (P), a última peça desenhada na mesa
  geraria 4 peças físicas quando apenas 2 são necessárias (sobra de 1 par).
- No fim da geração do layout (e antes de exportar), a peça excedente de cada molde ímpar
  é retirada da placa de 4 camadas e colocada em layout(s) extra(s) de 2 CAMADAS (layers = 2).
- Exemplo: 125 pares -> placa de 4 camadas com 62 peças (248 físicas) + layout de 2 camadas
  com 1 peça (2 físicas) = 250 físicas exatas = 125 pares exatos. Resto efetivo = 0.
- Conservação de peças: o sistema apenas MOVE peças entre layouts; nunca cria nem apaga peças.
- Idempotência: se o estado desejado já existir, não altera nada e preserva ajustes manuais.
- Integridade física estrita: sum(peças * layers) = 2P por molde. Se divergir, rollback atômico.
"""

import copy
import logging
from typing import Any, Dict, List, Optional, Tuple

from cad.layers_rule import (
    resolve_session_layers,
    resolve_layout_layers,
    is_separar_sobras_enabled,
    is_refile_auto_enabled,
    parse_session_params,
    encode_session_params,
    layers_for_piece,
    format_enfesto_operator_text,
)
from cad.geometry import (
    transform_contour,
    polygon_bbox,
    polygon_area,
    polygons_collide,
)
from cad.trim_engine import (
    calculate_layout_trim_bounds,
    trim_layout_dict,
)
from cad.nesting_engine import (
    piece_matches_shape,
    sort_shapes_by_sequence,
    nest_multi_sheet,
    auto_nest_pieces,
    calculate_yield,
    calculate_atom_cutting_time,
)

logger = logging.getLogger("layers_split")


def log_sobras(msg: str):
    """Emite log formatado com tag [SOBRAS] para rastreabilidade de nesting e auditoria."""
    logger.info("[SOBRAS] %s", msg)


def _recompact_plate(
    plate: Dict[str, Any],
    strategy: str = "flashnestsheet",
    params: str = "HighYield",
    layers: int = 4,
    gap_mm: Optional[float] = None,
) -> bool:
    """
    Reencaixa as peças restantes de uma placa que cedeu sobras, fechando os buracos.

    Ao mover a peça ímpar para a ponta de 2 camadas, a placa de 4 camadas ficava com a
    vaga vazia (o operador via um "buraco" no encaixe). Aqui as peças restantes são
    reencaixadas compactamente, preservando exatamente as contagens por molde. Qualquer
    divergência mantém a placa original (rollback local).
    """
    pieces = plate.get("pieces") or []
    if len(pieces) < 2:
        return False

    bed_w = float(plate.get("width_mm") or plate.get("sheet_width_mm") or 1380.0)
    bed_h = float(plate.get("height_mm") or plate.get("sheet_height_mm") or 2990.0)
    margins = {
        "left": float(plate.get("margin_left", 10.0)),
        "right": float(plate.get("margin_right", 10.0)),
        "top": float(plate.get("margin_top", 10.0)),
        "bottom": float(plate.get("margin_bottom", 10.0)),
    }
    gap = float(gap_mm if gap_mm is not None else (plate.get("gap_mm", 1.0) or 1.0))

    grupos: Dict[Any, Dict[str, Any]] = {}
    for p in pieces:
        shp = p.get("shape") if isinstance(p.get("shape"), dict) else {}
        nome = p.get("name") or shp.get("name") or "Molde"
        size = str(p.get("size") or shp.get("size") or "")
        chave = (str(nome), size)
        if chave not in grupos:
            cntr = p.get("contour") or shp.get("contour") or []
            if not cntr:
                return False
            base_shp = dict(shp) if shp else {}
            base_shp.update({
                "name": nome,
                "size": size,
                "contour": [dict(q) for q in cntr],
                "pairs": 0,          # pares zerados: a demanda vem de target_pieces
                "layers": layers,
                "sequence": len(grupos) + 1,
            })
            grupos[chave] = {"shape": base_shp, "count": 0}
        grupos[chave]["count"] += 1

    shapes_in = []
    for info in grupos.values():
        shp = dict(info["shape"])
        shp["target_pieces"] = info["count"]
        shapes_in.append(shp)

    total = len(pieces)
    try:
        novos = auto_nest_pieces(
            available_shapes=shapes_in,
            bed_width_mm=bed_w,
            bed_height_mm=bed_h,
            target_count=total,
            strategy=strategy,
            params=params,
            gap_mm=gap,
            margins=margins,
            layers=layers,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[SOBRAS] Recompactação falhou (%s); mantendo placa original.", exc)
        return False

    if not novos or len(novos) != total:
        logger.info("[SOBRAS] Recompactação não fechou a contagem (%s/%s); mantendo placa original.",
                    len(novos or []), total)
        return False

    # Mantém os dicionários ORIGINAIS (identidade do molde intacta) e copia só a posição.
    # Substituir as peças quebrava `piece_matches_shape` quando dois moldes têm o mesmo
    # contorno/tamanho, fazendo a verificação física acusar divergência e reverter tudo.
    def _chave(item: Dict[str, Any]) -> Any:
        shp = item.get("shape") if isinstance(item.get("shape"), dict) else {}
        return (str(item.get("name") or shp.get("name") or ""),
                str(item.get("size") or shp.get("size") or ""))

    originais: Dict[Any, List[Dict[str, Any]]] = {}
    for item in pieces:
        originais.setdefault(_chave(item), []).append(item)

    novos_por_grupo: Dict[Any, List[Dict[str, Any]]] = {}
    for item in novos:
        novos_por_grupo.setdefault(_chave(item), []).append(item)

    for chave, lista in originais.items():
        candidatos = novos_por_grupo.get(chave, [])
        if len(candidatos) != len(lista):
            logger.info("[SOBRAS] Recompactação divergiu no molde %s (%s/%s); mantendo placa original.",
                        chave[0], len(candidatos), len(lista))
            return False
        for original, novo in zip(lista, candidatos):
            original["x"] = float(novo.get("x", original.get("x", 0.0)))
            original["y"] = float(novo.get("y", original.get("y", 0.0)))
            original["rotation"] = float(novo.get("rotation", original.get("rotation", 0.0)))
            for campo in ("poly", "bbox", "_segs"):
                original.pop(campo, None)

    plate["num_items"] = len(pieces)
    logger.info("[SOBRAS] Placa recompactada: %d peças reencaixadas sem buraco.", len(pieces))
    return True


def separar_sobras_camadas(
    layouts: List[Dict[str, Any]],
    session: Optional[Dict[str, Any]] = None,
    shapes: Optional[List[Dict[str, Any]]] = None,
    params: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Separa automaticamente peças de sobra de 4 camadas em layout(s) extra(s) de 2 camadas.

    Retorna:
        (new_layouts, summary_msg)
        Se nenhuma separação for necessária ou possível, retorna (layouts, None).
    """
    if not layouts:
        return layouts, None

    # 1. Validação de pré-requisitos: enfesto base deve ser 4 camadas
    sess_layers = resolve_session_layers(session, default=4)
    if sess_layers != 4:
        return layouts, None

    # 2. Validação do parâmetro da sessão
    session_params = params if params is not None else (session.get("params") if session else None)
    if not is_separar_sobras_enabled(session_params, default_camadas=4):
        return layouts, None

    if not shapes:
        return layouts, None

    # 3. Ordenação estrita pela coluna Sequência
    sorted_shapes, _ = sort_shapes_by_sequence(shapes)

    # 4. Estado Desejado por molde
    # Para cada molde com P pares e base 4 camadas:
    #   target_4 = P // 2
    #   target_2 = P % 2 (1 se ímpar, 0 se par)
    desired: Dict[Any, Dict[str, Any]] = {}
    has_any_odd = False
    for s in sorted_shapes:
        p = max(0, int(s.get("pairs", 0)))
        t_4 = p // 2
        t_2 = p % 2
        if t_2 > 0:
            has_any_odd = True
        s_key = s.get("id") or s.get("name")
        desired[s_key] = {
            "shape": s,
            "pairs": p,
            "target_4": t_4,
            "target_2": t_2,
        }

    if not has_any_odd:
        # Nenhum molde tem pares ímpares: nada a separar
        return layouts, None

    # Preserva cópia íntegra para rollback atômico em caso de qualquer divergência
    original_layouts = copy.deepcopy(layouts)

    # 5. Separação dos layouts atuais entre placas de 4 camadas e placas de 2 camadas
    layouts_4: List[Dict[str, Any]] = []
    layouts_2: List[Dict[str, Any]] = []

    for ly in layouts:
        ly_l = resolve_layout_layers(ly, session=session, default=4)
        ly_copy = copy.deepcopy(ly)
        if ly_l == 2:
            layouts_2.append(ly_copy)
        else:
            ly_copy["layers"] = 4
            layouts_4.append(ly_copy)

    # Contagem atual de peças por molde nas placas de 4 e 2 camadas
    curr_counts_4: Dict[Any, int] = {k: 0 for k in desired}
    curr_counts_2: Dict[Any, int] = {k: 0 for k in desired}

    for ly in layouts_4:
        for p in ly.get("pieces", []):
            for k, info in desired.items():
                if piece_matches_shape(p, info["shape"]):
                    curr_counts_4[k] += 1
                    break

    for ly in layouts_2:
        for p in ly.get("pieces", []):
            for k, info in desired.items():
                if piece_matches_shape(p, info["shape"]):
                    curr_counts_2[k] += 1
                    break

    # 6. Verificação de IDEMPOTÊNCIA:
    # Se já existem placas de 2 camadas E as contagens em 4 e 2 batem perfeitamente com o estado desejado,
    # não fazemos nada (preserva ajustes finos manuais do operador na placa de sobras).
    is_already_separated = (
        bool(layouts_2) and
        all(curr_counts_4[k] == desired[k]["target_4"] for k in desired) and
        all(curr_counts_2[k] == desired[k]["target_2"] for k in desired)
    )
    if is_already_separated:
        return layouts, None

    # 7. Identificação de déficits manuais e retirada de peças excedentes das placas de 4 camadas
    manual_deficits: Dict[Any, int] = {}
    removed_pieces_map: Dict[Any, List[Dict[str, Any]]] = {k: [] for k in desired}
    affected_plates: set = set()

    for k, info in desired.items():
        shp = info["shape"]
        t_4 = info["target_4"]
        c_4 = curr_counts_4[k]

        if c_4 < t_4:
            # Operador apagou peças manualmente: não inventa peças
            deficit = t_4 - c_4
            manual_deficits[k] = deficit
            logger.info("Molde %s com déficit manual de %d peça(s) em 4 camadas", shp.get("name"), deficit)
        elif c_4 > t_4:
            # Excedente a retirar: exatamente c_4 - t_4 peças
            excess_to_remove = c_4 - t_4

            # Retira a peça onde o molde termina (ordem da Sequência), selecionando a de maior placement_index
            # Percorre os layouts de 4 camadas do último para o primeiro
            for ly in reversed(layouts_4):
                if excess_to_remove <= 0:
                    break
                ly_pieces = ly.get("pieces", [])
                matching_indices = [
                    idx for idx, p in enumerate(ly_pieces)
                    if piece_matches_shape(p, shp)
                ]
                if not matching_indices:
                    continue

                # Ordena pelo placement_index decrescente (fallback: índice original na lista de peças)
                # CONFIRMAR NO WINDOWS: fallback do índice de posicionamento
                matching_indices.sort(
                    key=lambda idx: (
                        ly_pieces[idx].get("placement_index") if ly_pieces[idx].get("placement_index") is not None else idx
                    ),
                    reverse=True
                )

                take = min(excess_to_remove, len(matching_indices))
                indices_to_pop = sorted(matching_indices[:take], reverse=True)
                for idx in indices_to_pop:
                    p_removed = ly_pieces.pop(idx)
                    removed_pieces_map[k].append(p_removed)
                    excess_to_remove -= 1
                    curr_counts_4[k] -= 1
                affected_plates.add(id(ly))

    # 7.1 Recompacta as placas que cederam peças: fecha o "buraco" deixado pela retirada
    if affected_plates:
        _strat = (session.get("strategy") if isinstance(session, dict) else None) or "flashnestsheet"
        _clean, _ = parse_session_params(session_params)
        _gap = float(session.get("gap_mm", 1.0)) if isinstance(session, dict) and session.get("gap_mm") is not None else None
        for ly in layouts_4:
            if id(ly) in affected_plates and ly.get("pieces"):
                _recompact_plate(ly, strategy=_strat, params=_clean or "HighYield", layers=4, gap_mm=_gap)

    # 8. Remoção de layouts de 4 camadas vazios (que só continham peças de sobra)
    layouts_4 = [ly for ly in layouts_4 if len(ly.get("pieces", [])) > 0]

    # 9. Monta a demanda a reencaixar nas placas de 2 camadas
    shapes_for_2: List[Dict[str, Any]] = []
    total_sobras_pieces = 0

    for k, info in desired.items():
        shp = info["shape"]
        t_2 = info["target_2"]
        if t_2 > 0:
            shp_2 = dict(shp)
            shp_2["target_pieces"] = t_2
            shp_2["pairs"] = t_2
            shp_2["layers"] = 2
            shapes_for_2.append(shp_2)
            total_sobras_pieces += t_2

    if total_sobras_pieces == 0:
        # Nenhuma sobra a reencaixar; se layouts_4 mudou, renumera e retorna
        for idx, ly in enumerate(layouts_4):
            ly["layout_index"] = idx
            ly["name"] = f"lay{idx:04d}"
            ly["code"] = f"lay{idx:04d}"
        return layouts_4, None

    # Dimensões da chapa para o reencaixe
    mat = (session.get("material") if isinstance(session, dict) and isinstance(session.get("material"), dict) else {})
    bed_w = float(mat.get("width_mm") or (layouts[0].get("sheet_width_mm") if layouts else 1350.0) or 1350.0)
    bed_h = float(mat.get("height_mm") or (layouts[0].get("sheet_height_mm") if layouts else 2553.38) or 2553.38)
    if bed_w <= 0:
        bed_w = 1350.0
    if bed_h <= 0:
        bed_h = 2553.38

    # Margens e espaçamento
    m_left = float(session.get("margin_left", 10.0)) if isinstance(session, dict) else 10.0
    m_right = float(session.get("margin_right", 10.0)) if isinstance(session, dict) else 10.0
    m_top = float(session.get("margin_top", 10.0)) if isinstance(session, dict) else 10.0
    m_bottom = float(session.get("margin_bottom", 10.0)) if isinstance(session, dict) else 10.0
    margins = {"left": m_left, "right": m_right, "top": m_top, "bottom": m_bottom}

    gap = float(session.get("gap_mm", 1.0)) if isinstance(session, dict) else 1.0
    strategy = session.get("strategy") or "flashnestsheet" if isinstance(session, dict) else "flashnestsheet"
    clean_params, _ = parse_session_params(session_params)

    # 10. Reencaixe das sobras do zero a 2 camadas (layers = 2)
    nest_res = nest_multi_sheet(
        available_shapes=shapes_for_2,
        bed_width_mm=bed_w,
        bed_height_mm=bed_h,
        strategy=strategy,
        params=clean_params,
        gap_mm=gap,
        margins=margins,
        layers=2,
        max_sheets=50
    )

    new_layouts_2 = nest_res.get("layouts", [])
    if not new_layouts_2:
        # Falha no reencaixe das sobras: rollback atômico
        logger.warning("Falha ao reencaixar sobras em 2 camadas: desfazendo separação")
        return original_layouts, None

    # Garante layers = 2 e is_sobras = True em todas as placas de sobras geradas
    for ly in new_layouts_2:
        ly["layers"] = 2
        ly["is_sobras"] = True
        ly["sheet_width_mm"] = bed_w
        ly["sheet_height_mm"] = bed_h

    # 11. Consolidação e Renumeração Contínua (lay0000, lay0001, ...)
    combined_layouts = layouts_4 + new_layouts_2
    plate_area_m2 = max(1e-4, (bed_w * bed_h) / 1_000_000.0)

    for idx, ly in enumerate(combined_layouts):
        ly["layout_index"] = idx
        name = f"lay{idx:04d}"
        ly["name"] = name
        ly["code"] = name
        pieces = ly.get("pieces", [])
        eff_pct, used_m2 = calculate_yield(pieces, plate_area_m2)
        est_time, _ = calculate_atom_cutting_time(pieces)
        ly["yield_percent"] = eff_pct
        ly["yield_pct"] = eff_pct
        ly["cutting_time_sec"] = est_time
        ly["used_area_m2"] = used_m2

    # 12. VERIFICAÇÃO FÍSICA ESTRITA POR MOLDE:
    # sum(peças_do_molde * layers_do_layout) deve fechar a produção esperada exata
    for k, info in desired.items():
        shp = info["shape"]
        req_p = info["pairs"]
        expected_phys = 2 * req_p - manual_deficits.get(k, 0) * 4

        actual_phys = 0
        for ly in combined_layouts:
            ly_l = ly.get("layers", 4)
            cnt = sum(1 for p in ly.get("pieces", []) if piece_matches_shape(p, shp))
            actual_phys += cnt * ly_l

        if actual_phys != expected_phys:
            # Divergência detectada: ROLLBACK ATÔMICO imediato
            logger.error(
                "Divergência física no molde '%s': esperado %d peças físicas, obtido %d. Revertendo separação.",
                shp.get("name"), expected_phys, actual_phys
            )
            return original_layouts, None

    # 13. Resumo informativo para a barra de status e log da sessão
    n_moldes = sum(1 for k in desired if desired[k]["target_2"] > 0)
    n_pares_evitados = n_moldes
    extra_names = ", ".join(ly["name"] for ly in new_layouts_2)
    n_pecas_sobras = sum(len(ly.get("pieces", [])) for ly in new_layouts_2)

    summary_msg = (
        f"Sobras separadas: {n_moldes} molde(s), {n_pares_evitados} par(es) evitado(s). "
        f"Layout extra: {extra_names} (2 camadas, {n_pecas_sobras} peça(s))"
    )

    return combined_layouts, summary_msg


def _cluster_pieces_by_y(pieces: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Agrupa peças da chapa em linhas/faixas horizontais de Y (do fundo ao topo)."""
    if not pieces:
        return []

    valid = []
    for p in pieces:
        if not p.get("bbox"):
            cntr = p.get("contour") or (p.get("shape", {}).get("contour") if isinstance(p.get("shape"), dict) else [])
            px = float(p.get("x", 0.0))
            py = float(p.get("y", 0.0))
            rot = float(p.get("rotation", p.get("angle", p.get("rot_deg", 0.0))))
            if cntr and len(cntr) >= 3:
                poly = transform_contour(cntr, px, py, rot)
                p["poly"] = poly
                p["bbox"] = polygon_bbox(poly)
            else:
                p["bbox"] = (px, py, px + 50.0, py + 50.0)
        valid.append(p)

    sorted_p = sorted(valid, key=lambda x: x["bbox"][1])
    rows: List[List[Dict[str, Any]]] = []
    for p in sorted_p:
        pb = p["bbox"]
        assigned = False
        for r in rows:
            r_min_y = min(it["bbox"][1] for it in r)
            r_max_y = max(it["bbox"][3] for it in r)
            ov_y = max(0.0, min(pb[3], r_max_y) - max(pb[1], r_min_y))
            p_h = max(1.0, pb[3] - pb[1])
            if ov_y / p_h >= 0.35:
                r.append(p)
                assigned = True
                break
        if not assigned:
            rows.append([p])

    rows.sort(key=lambda r: min(it["bbox"][1] for it in r))
    return rows


def _place_sobra_piece(
    piece_dict: Dict[str, Any],
    cand_x: float,
    cand_y: float,
    rot: float,
    bed_w: float,
    bed_h: float,
    margins: Dict[str, float],
    gap: float,
    existing_items: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Tenta posicionar uma peça de sobra nas coordenadas candidatas sem colisão e dentro dos limites."""
    cntr = piece_dict.get("contour") or (piece_dict.get("shape", {}).get("contour") if isinstance(piece_dict.get("shape"), dict) else [])
    if not cntr:
        return None

    poly0 = transform_contour(cntr, 0, 0, rot)
    min_x, min_y, max_x, max_y = polygon_bbox(poly0)
    w = max_x - min_x
    h = max_y - min_y

    px = cand_x - min_x
    py = cand_y - min_y

    c_poly = transform_contour(cntr, px, py, rot)
    c_bbox = polygon_bbox(c_poly)

    # Verifica limites da chapa com margens
    if (c_bbox[0] < margins["left"] - 0.01 or
        c_bbox[2] > bed_w - margins["right"] + 0.01 or
        c_bbox[1] < margins["bottom"] - 0.01 or
        c_bbox[3] > bed_h - margins["top"] + 0.01):
        return None

    # Verifica colisões com peças existentes
    for other in existing_items:
        o_poly = other.get("poly")
        o_bbox = other.get("bbox")
        if not o_poly:
            o_cntr = other.get("contour") or (other.get("shape", {}).get("contour") if isinstance(other.get("shape"), dict) else [])
            ox = float(other.get("x", 0.0))
            oy = float(other.get("y", 0.0))
            orot = float(other.get("rotation", other.get("angle", 0.0)))
            o_poly = transform_contour(o_cntr, ox, oy, orot)
            o_bbox = polygon_bbox(o_poly)
            other["poly"] = o_poly
            other["bbox"] = o_bbox

        if polygons_collide(c_poly, o_poly, gap=gap, bbox_a=c_bbox, bbox_b=o_bbox):
            return None

    new_p = copy.deepcopy(piece_dict)
    new_p["x"] = px
    new_p["y"] = py
    new_p["rotation"] = rot
    new_p["poly"] = c_poly
    new_p["bbox"] = c_bbox
    new_p["is_tip"] = True
    new_p["layers"] = 2
    return new_p


def _nest_sobras_on_last_sheet(
    dest_layout: Dict[str, Any],
    sobras_to_place: List[Dict[str, Any]],
    bed_w: float,
    bed_h: float,
    gap_mm: float,
    margins: Dict[str, float],
    tip_mode: str = "canto",
    folga_ponta: float = 15.0
) -> Optional[Tuple[List[Dict[str, Any]], List[float]]]:
    """
    Posiciona as sobras no topo (maior Y) da última placa de 4 camadas (enfesto em degrau).
    Garante o posicionamento no final da placa de forma forçada e robusta.
    """
    existing_pieces = dest_layout.get("pieces", [])
    if not sobras_to_place:
        return None

    # 1. Calcula os polígonos de todas as peças existentes (4 camadas)
    for p in existing_pieces:
        if not p.get("poly") or not p.get("bbox"):
            cntr = p.get("contour") or (p.get("shape", {}).get("contour") if isinstance(p.get("shape"), dict) else [])
            px = float(p.get("x", 0.0))
            py = float(p.get("y", 0.0))
            rot = float(p.get("rotation", p.get("angle", 0.0)))
            if cntr:
                poly = transform_contour(cntr, px, py, rot)
                p["poly"] = poly
                p["bbox"] = polygon_bbox(poly)
            else:
                p["bbox"] = (px, py, px + 10, py + 10)

    # 2. Acha o maior Y ocupado pelas peças de 4 camadas (o topo do enfesto)
    max_y_4 = max((p["bbox"][3] for p in existing_pieces if p.get("bbox")), default=margins.get("bottom", 10.0))

    # 3. Define o Y inicial da ponta: logo acima da última peça + folga da ponta
    start_y = max_y_4 + folga_ponta

    # Se o start_y já passou do limite da placa, tenta colocar na mesma linha (mais à direita)
    if start_y > bed_h - margins.get("top", 10.0):
        start_y = max_y_4  # Tenta alinhar com o topo da última linha

    placed_sobras = []
    current_x = margins.get("left", 10.0)

    # 4. Posiciona as peças da esquerda para a direita, formando a faixa da ponta
    for item in sobras_to_place:
        p_dict = item["piece"]
        orig_rot = float(p_dict.get("rotation", p_dict.get("angle", 0.0)))

        placed = None
        # Tenta rotações para caber melhor
        for rot in [orig_rot, 0.0, 180.0]:
            test_x = current_x

            cntr = p_dict.get("contour", []) or (p_dict.get("shape", {}).get("contour") if isinstance(p_dict.get("shape"), dict) else [])
            if not cntr:
                continue
            poly0 = transform_contour(cntr, 0, 0, rot)
            bbox0 = polygon_bbox(poly0)
            w_piece = bbox0[2] - bbox0[0]

            if test_x + w_piece > bed_w - margins.get("right", 10.0):
                continue  # Não cabe nesta linha

            res = _place_sobra_piece(
                p_dict, test_x, start_y, rot,
                bed_w, bed_h, margins, gap_mm, existing_pieces + placed_sobras
            )
            if res:
                placed = res
                current_x = res["bbox"][2] + gap_mm  # Avança o X
                break

        if not placed and placed_sobras:
            # Se não coube na linha atual por largura, tenta nova linha acima no topo
            row_max_y = max(p["bbox"][3] for p in placed_sobras)
            next_row_y = row_max_y + gap_mm
            test_x = margins.get("left", 10.0)
            for rot in [orig_rot, 0.0, 180.0]:
                res = _place_sobra_piece(
                    p_dict, test_x, next_row_y, rot,
                    bed_w, bed_h, margins, gap_mm, existing_pieces + placed_sobras
                )
                if res:
                    placed = res
                    start_y = next_row_y
                    current_x = res["bbox"][2] + gap_mm
                    break

        if not placed:
            # Se não coube na linha nova (Y alto), tenta colocar no final da linha anterior (4 camadas)
            max_x_4 = max((p["bbox"][2] for p in existing_pieces if p.get("bbox")), default=margins.get("left", 10.0))
            test_x = max_x_4 + folga_ponta

            for rot in [orig_rot, 0.0, 180.0]:
                res = _place_sobra_piece(
                    p_dict, test_x, max_y_4, rot,
                    bed_w, bed_h, margins, gap_mm, existing_pieces + placed_sobras
                )
                if res:
                    placed = res
                    break

        if placed:
            placed_sobras.append(placed)
        else:
            logger.error("[SOBRAS] Impossível posicionar a peça de sobra '%s'. Abortando ponta.", item.get("shape", {}).get("name"))
            return None

    if not placed_sobras:
        return None

    # 5. Calcula a tip_zone (área da ponta)
    sobras_min_x = min(p["bbox"][0] for p in placed_sobras)
    sobras_min_y = min(p["bbox"][1] for p in placed_sobras)

    if tip_mode == "faixa":
        x0 = 0.0
        x1 = bed_w
    else:
        x0 = max(0.0, sobras_min_x - 10.0)
        x1 = bed_w

    y0 = max(0.0, sobras_min_y - gap_mm)
    y1 = bed_h

    tip_zone = [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]
    return placed_sobras, tip_zone


def _escolher_divisao_otima(
    layouts, session=None, shapes=None, params=None,
    sheet_w=None, sheet_h=None, material=None, refile=None, tip_mode=None, opts=None,
    max_k: int = 3,
):
    """
    Escolhe a divisão 4 camadas / 2 camadas que fecha a placa com MENOS sobra.

    Para cada k (dobras), a divisão de cada molde vira:
        peças_4 = P//2 - k      peças_2 = (P%2) + 2k
    mantendo sempre 4*peças_4 + 2*peças_2 = 2P (pares exatos, sem cortar a mais).
    A melhor opção é a que resulta na menor altura total utilizada (refile menor).
    """
    pares = [max(0, int(s.get("pairs", 0) or 0)) for s in (shapes or [])]
    p_max = max(pares) if pares else 0
    limite = max(0, min(int(max_k), p_max // 2))

    melhor = None
    for k in range(0, limite + 1):
        try:
            res = separar_sobras_em_ponta(
                layouts, session=session, shapes=shapes, params=params,
                sheet_w=sheet_w, sheet_h=sheet_h, material=material,
                refile=refile, tip_mode=tip_mode, opts=opts, _k=k,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[SOBRAS] Divisão com k=%d falhou: %s", k, exc)
            continue
        if not res or not res[0] or not res[1]:
            continue
        resultado, msg = res
        if not any(ly.get("tip_zone") for ly in resultado):
            continue
        altura_total = 0.0
        for ly in resultado:
            try:
                _, th = calculate_layout_trim_bounds(ly.get("pieces") or [], gap_mm=1.0)
            except Exception:
                th = float(ly.get("height_mm") or 0.0)
            altura_total += float(th or 0.0)
        logger.info("[SOBRAS] k=%d -> altura total utilizada %.1f mm", k, altura_total)
        if melhor is None or altura_total < melhor[0] - 5.0:
            melhor = (altura_total, res)

    if melhor is None:
        # Mantém o comportamento/mensagem originais (ex.: "todos os moldes têm pares pares")
        logger.info("[SOBRAS] Nenhuma divisão viável; mantendo enfesto padrão.")
        return separar_sobras_em_ponta(
            layouts, session=session, shapes=shapes, params=params,
            sheet_w=sheet_w, sheet_h=sheet_h, material=material,
            refile=refile, tip_mode=tip_mode, opts=opts, _k=0,
        )
    return melhor[1]


def separar_sobras_em_ponta(
    layouts: List[Dict[str, Any]],
    session: Optional[Dict[str, Any]] = None,
    shapes: Optional[List[Dict[str, Any]]] = None,
    params: Optional[str] = None,
    sheet_w: Optional[float] = None,
    sheet_h: Optional[float] = None,
    material: Optional[Dict[str, Any]] = None,
    refile: Optional[bool] = None,
    tip_mode: Optional[str] = None,
    opts: Optional[Dict[str, Any]] = None,
    _k: Optional[int] = None,
    **kwargs
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Separa automaticamente sobras de 4 camadas em PONTA DE 2 CAMADAS no final da sessão (enfesto em degrau).

    Regras do operador:
    1. Enfesto em degrau: 2 folhas longas (placa inteira) + 2 folhas curtas (exceto a ponta).
    2. Sobras de moldes ímpares (P % 2 == 1, 1 peça por molde) retiradas de onde o molde termina pela Sequência.
    3. Placas de origem congeladas (não renestam; placas vazias são descartadas e reindexadas).
    4. Destino: última placa de 4 camadas, aninhadas à direita da última linha ou penúltima linha ou 1 linha extra max.
    5. Geometria da ponta: modo canto [x0, y0, x1, y1] ou modo faixa, com folga_ponta configurável.
    6. Regra econômica: compara consumo Ponta vs Plano B. Se Ponta consome mais ou não cabe, recorre ao Plano B.
    7. Integridade física estrita: sum(peças * layers_for_piece) = 2P. Rollback atômico em divergência.
    8. Idempotência estrita: se já aplicada e consistente, preserva ajustes manuais.
    """
    if not layouts:
        logger.info("[SOBRAS] Nenhum layout na sessão para separar sobras.")
        return layouts, "[SOBRAS] Nenhum layout na sessão para separar sobras."

    # Sem `_k` explícito: escolhe automaticamente a divisão que fecha a placa melhor
    if _k is None:
        return _escolher_divisao_otima(
            layouts, session=session, shapes=shapes, params=params,
            sheet_w=sheet_w, sheet_h=sheet_h, material=material,
            refile=refile, tip_mode=tip_mode, opts=opts,
        )

    # 1. Validação de pré-requisitos: enfesto base deve ser 4 camadas
    sess_layers = resolve_session_layers(session, material=material, default=4)
    if sess_layers != 4:
        msg = f"[SOBRAS] Sessão com {sess_layers} camadas: ponta de 2 camadas só se aplica a 4 camadas."
        logger.info(msg)
        return layouts, msg

    # 2. Validação do parâmetro da sessão
    session_params = params if params is not None else (session.get("params") if session else None)
    if opts and "separar_sobras" in opts:
        is_sep = str(opts["separar_sobras"]) in ("1", "true", "True")
    else:
        is_sep = is_separar_sobras_enabled(session_params, default_camadas=4)
    if not is_sep:
        msg = "[SOBRAS] Separação de sobras desmarcada nos parâmetros da sessão."
        logger.info(msg)
        return layouts, msg

    if not shapes:
        logger.info("[SOBRAS] Nenhum molde na sessão para separar sobras.")
        return layouts, "[SOBRAS] Nenhum molde na sessão para separar sobras."

    # 3. Ordenação estrita pela coluna Sequência
    sorted_shapes, _ = sort_shapes_by_sequence(shapes)

    # 4. Estado Desejado por molde
    # Regra da dobra (confirmada pelo operador): cada peça retirada das 4 camadas vira
    # DUAS na ponta de 2 camadas, pois 4 físicas = 2 pares <-> 2 peças x 2 camadas = 2 pares.
    #   peças_4 = P//2 - k      peças_2 = (P%2) + 2k      (k = número de dobras)
    desired: Dict[Any, Dict[str, Any]] = {}
    has_any_odd = False
    k_div = max(0, int(_k or 0))
    for s in sorted_shapes:
        p = max(0, int(s.get("pairs", 0)))
        t_4 = max(0, p // 2 - min(k_div, p // 2))
        t_2 = (p % 2) + 2 * min(k_div, p // 2)
        if t_2 > 0:
            has_any_odd = True
        s_key = s.get("id") or s.get("name")
        desired[s_key] = {
            "shape": s,
            "pairs": p,
            "target_4": t_4,
            "target_2": t_2,
        }

    if not has_any_odd:
        msg = "[SOBRAS] Todos os moldes têm pares pares (resto = 0). Nenhuma sobra a separar."
        logger.info(msg)
        return layouts, msg

    # Preserva cópia íntegra para rollback atômico
    original_layouts = copy.deepcopy(layouts)

    # 5. Verifica se já está separado em ponta de forma consistente (idempotência)
    last_ly = layouts[-1]
    if last_ly.get("tip_zone") and last_ly.get("layers_tip") == 2:
        counts_match = True
        for k, info in desired.items():
            shp = info["shape"]
            req_p = info["pairs"]
            expected_phys = 2 * req_p
            actual_phys = sum(layers_for_piece(ly, p) for ly in layouts for p in ly.get("pieces", []) if piece_matches_shape(p, shp))
            if actual_phys != expected_phys:
                counts_match = False
                break
        if counts_match:
            logger.info("[SOBRAS] Ponta de 2 camadas já aplicada e consistente. Layout preservado.")
            return layouts, "[SOBRAS] Ponta de 2 camadas já aplicada e consistente."

    # 6. Agrupamento de layouts: reverte eventual separação prévia para base 4 camadas limpa
    clean_layouts = copy.deepcopy(layouts)
    clean_layouts, _ = desfazer_separacao_sobras(clean_layouts, session=session, shapes=shapes)

    layouts_4 = clean_layouts

    # Contagem de peças por molde
    curr_counts_4: Dict[Any, int] = {k: 0 for k in desired}
    for ly in layouts_4:
        for p in ly.get("pieces", []):
            for k, info in desired.items():
                if piece_matches_shape(p, info["shape"]):
                    curr_counts_4[k] += 1
                    break

    # 7. Identificação de déficits manuais e coleta de sobras
    manual_deficits: Dict[Any, int] = {}
    sobras_to_place: List[Dict[str, Any]] = []
    affected_plates: set = set()

    for k, info in desired.items():
        shp = info["shape"]
        t_4 = info["target_4"]
        c_4 = curr_counts_4[k]

        if c_4 < t_4:
            deficit = t_4 - c_4
            manual_deficits[k] = deficit
            logger.info("Molde %s com déficit manual de %d peça(s) em 4 camadas", shp.get("name"), deficit)
        elif c_4 > t_4:
            excess = c_4 - t_4
            for ly in reversed(layouts_4):
                if excess <= 0:
                    break
                ly_pieces = ly.get("pieces", [])
                matching_indices = [
                    idx for idx, p in enumerate(ly_pieces)
                    if piece_matches_shape(p, shp)
                ]
                if not matching_indices:
                    continue

                matching_indices.sort(
                    key=lambda idx: (
                        ly_pieces[idx].get("placement_index") if ly_pieces[idx].get("placement_index") is not None else idx
                    ),
                    reverse=True
                )

                take = min(excess, len(matching_indices))
                indices_to_pop = sorted(matching_indices[:take], reverse=True)
                for idx in indices_to_pop:
                    p_removed = ly_pieces.pop(idx)
                    sobras_to_place.append({
                        "shape_key": k,
                        "piece": p_removed,
                        "shape": shp
                    })
                    excess -= 1
                    curr_counts_4[k] -= 1
                affected_plates.add(id(ly))

    # 7.2 DOBRA: cada peça retirada das 4 camadas vira DUAS na ponta de 2 camadas.
    #     A cópia é um desenho novo da MESMA peça cortada a 2 camadas: 2 desenhos x 2
    #     camadas = 4 físicas = 2 pares, exatamente o que a peça representava em 4 camadas.
    #     Assim 4*N4 + 2*N2 = 2P continua valendo (nenhuma peça física a mais).
    por_molde: Dict[Any, List[Dict[str, Any]]] = {}
    for item in sobras_to_place:
        por_molde.setdefault(item["shape_key"], []).append(item)

    for k, info in desired.items():
        alvo = int(info["target_2"])
        atuais = por_molde.get(k, [])
        faltam = alvo - len(atuais)
        if faltam <= 0 or not atuais:
            continue
        for i in range(faltam):
            base = atuais[i % len(atuais)]
            copia = copy.deepcopy(base["piece"])
            copia["id"] = None
            copia["is_duplicate"] = True
            copia["is_tip"] = True
            sobras_to_place.append({"shape_key": k, "piece": copia, "shape": info["shape"]})
        logger.info("[SOBRAS] Molde %s: %d dobra(s) na ponta de 2 camadas.",
                    info["shape"].get("name"), faltam)

    # 7.1 Recompacta as placas que cederam peças: fecha o "buraco" deixado pela retirada
    if affected_plates:
        _strat = (session.get("strategy") if isinstance(session, dict) else None) or "flashnestsheet"
        _clean, _ = parse_session_params(session_params)
        _gap = float(session.get("gap_mm", 1.0)) if isinstance(session, dict) and session.get("gap_mm") is not None else None
        for ly in layouts_4:
            if id(ly) in affected_plates and ly.get("pieces"):
                _recompact_plate(ly, strategy=_strat, params=_clean or "HighYield", layers=4, gap_mm=_gap)

    # 8. Elimina placas de 4 camadas vazias
    layouts_4 = [ly for ly in layouts_4 if len(ly.get("pieces", [])) > 0]
    if not layouts_4:
        logger.info("[SOBRAS] Nenhuma placa de 4 camadas para receber a ponta. Recorrendo ao Plano B.")
        return separar_sobras_camadas(original_layouts, session, shapes, params)

    dest_layout = layouts_4[-1]

    # Dimensões e parâmetros
    mat = material if material is not None else (session.get("material") if isinstance(session, dict) and isinstance(session.get("material"), dict) else {})
    bed_w = float(sheet_w or dest_layout.get("width_mm") or dest_layout.get("sheet_width_mm") or (mat.get("width_mm") if mat else 1350.0) or 1350.0)
    bed_h = float(sheet_h or dest_layout.get("height_mm") or dest_layout.get("sheet_height_mm") or (mat.get("height_mm") if mat else 2553.38) or 2553.38)
    if bed_w <= 0:
        bed_w = 1350.0
    if bed_h <= 0:
        bed_h = 2553.38

    m_left = float(session.get("margin_left", 10.0)) if isinstance(session, dict) else 10.0
    m_right = float(session.get("margin_right", 10.0)) if isinstance(session, dict) else 10.0
    m_top = float(session.get("margin_top", 10.0)) if isinstance(session, dict) else 10.0
    m_bottom = float(session.get("margin_bottom", 10.0)) if isinstance(session, dict) else 10.0
    margins = {"left": m_left, "right": m_right, "top": m_top, "bottom": m_bottom}
    gap = float(session.get("gap_mm", 1.0)) if isinstance(session, dict) else 1.0

    _, parsed_opts = parse_session_params(session_params)
    effective_opts = dict(parsed_opts)
    if opts:
        effective_opts.update(opts)
    effective_tip_mode = str(tip_mode or effective_opts.get("tip_mode", "canto")).strip().lower()
    if effective_tip_mode not in ("canto", "faixa"):
        effective_tip_mode = "canto"
    try:
        folga_ponta = float(effective_opts.get("folga_ponta", 15.0))
    except (ValueError, TypeError):
        folga_ponta = 15.0

    # 9. Tenta posicionar as sobras na última placa
    nest_res = _nest_sobras_on_last_sheet(
        dest_layout, sobras_to_place, bed_w, bed_h, gap, margins,
        tip_mode=effective_tip_mode, folga_ponta=folga_ponta
    )

    if not nest_res:
        logger.info("[SOBRAS] Não foi possível posicionar sobras na ponta da última placa. Recorrendo ao Plano B.")
        return separar_sobras_camadas(original_layouts, session, shapes, params)

    placed_sobras, tip_zone = nest_res

    # 10. Regra de Decisão Econômica (consumo de chapa / folha)
    is_refile = refile if refile is not None else (
        is_refile_auto_enabled(session_params) or
        (isinstance(session, dict) and is_refile_auto_enabled(session))
    )
    if is_refile:
        tw_ponta, th_ponta = calculate_layout_trim_bounds(dest_layout["pieces"] + placed_sobras, gap_mm=gap)
        a_placa = (min(bed_w, tw_ponta) * min(bed_h, th_ponta)) / 1e6
        x0, y0, x1, y1 = tip_zone
        a_ponta = ((x1 - x0) * (y1 - y0)) / 1e6
        c_ponta = 2.0 * a_placa + 2.0 * max(0.0, a_placa - a_ponta)

        tw_4, th_4 = calculate_layout_trim_bounds(dest_layout["pieces"], gap_mm=gap)
        a_placa4 = (min(bed_w, tw_4) * min(bed_h, th_4)) / 1e6
        sobras_geom_area = sum(polygon_area(p["poly"]) for p in placed_sobras) / 1e6
        a_placa2 = max(0.05, sobras_geom_area / 0.70)
        c_planoB = 4.0 * a_placa4 + 2.0 * a_placa2

        if c_ponta > c_planoB + 1e-4:
            logger.info(
                "[SOBRAS] Ponta consome mais material (%.4f m2) que Plano B (%.4f m2). Recorrendo ao Plano B.",
                c_ponta, c_planoB
            )
            return separar_sobras_camadas(original_layouts, session, shapes, params)

    # 11. Aplicação da Ponta no Destino
    dest_layout["pieces"] = dest_layout["pieces"] + placed_sobras
    dest_layout["tip_zone"] = tip_zone
    dest_layout["layers_tip"] = 2
    dest_layout["tip_mode"] = tip_mode

    for p in dest_layout["pieces"]:
        p_l = layers_for_piece(dest_layout, p)
        p["layers"] = p_l
        p["is_tip"] = (p_l == 2)

    # 12. VERIFICAÇÃO FÍSICA ESTRITA POR MOLDE:
    for k, info in desired.items():
        shp = info["shape"]
        req_p = info["pairs"]
        expected_phys = 2 * req_p - manual_deficits.get(k, 0) * 4

        actual_phys = 0
        for ly in layouts_4:
            for p in ly.get("pieces", []):
                if piece_matches_shape(p, shp):
                    actual_phys += layers_for_piece(ly, p)

        if actual_phys != expected_phys:
            logger.error(
                "[SOBRAS] Divergência física no molde '%s': esperado %d peças físicas, obtido %d. Revertendo separação.",
                shp.get("name"), expected_phys, actual_phys
            )
            return original_layouts, "[SOBRAS] Erro de conservação física: separação revertida."

    # 13. Renumeração e Recálculo de Rendimento
    plate_area_m2 = max(1e-4, (bed_w * bed_h) / 1e6)
    for idx, ly in enumerate(layouts_4):
        ly["layout_index"] = idx
        name = f"lay{idx:04d}"
        ly["name"] = name
        ly["code"] = name
        pieces = ly.get("pieces", [])
        eff_pct, used_m2 = calculate_yield(pieces, plate_area_m2)
        est_time, _ = calculate_atom_cutting_time(pieces)
        ly["yield_percent"] = eff_pct
        ly["yield_pct"] = eff_pct
        ly["cutting_time_sec"] = est_time
        ly["used_area_m2"] = used_m2

    n_moldes_sobras = sum(1 for k in desired if desired[k]["target_2"] > 0)
    dest_name = dest_layout.get("name", "lay0000")
    mode_label = "canto" if tip_mode == "canto" else "faixa"
    summary_msg = (
        f"Ponta de 2 camadas aplicada na {dest_name} ({mode_label}): "
        f"{n_moldes_sobras} molde(s) com sobras ({len(placed_sobras)} peça(s) a 2 camadas). "
        f"Enfesto em degrau configurado."
    )
    logger.info("[SOBRAS] %s", summary_msg)
    return layouts_4, summary_msg


def desfazer_separacao_sobras(
    layouts: List[Dict[str, Any]],
    session: Optional[Dict[str, Any]] = None,
    shapes: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Reverte a separação de sobras (tanto ponta de 2 camadas quanto layouts extras de 2 camadas),
    restaurando a sessão para o enfesto padrão de 4 camadas.
    """
    if not layouts:
        return layouts, "[SOBRAS] Nenhum layout para reverter."

    updated = copy.deepcopy(layouts)

    # 1. Remove ponta de 2 camadas de qualquer layout
    for ly in updated:
        if ly.get("tip_zone") is not None or ly.get("layers_tip") is not None:
            ly.pop("tip_zone", None)
            ly.pop("layers_tip", None)
            ly.pop("tip_mode", None)
            ly["layers"] = 4
            for p in ly.get("pieces", []):
                p.pop("is_tip", None)
                p["layers"] = 4

    # 2. Reverte layouts extras de 2 camadas (Plano B)
    lays_4 = [ly for ly in updated if ly.get("layers") != 2 and not ly.get("is_sobras")]
    lays_2 = [ly for ly in updated if ly.get("layers") == 2 or ly.get("is_sobras")]

    if lays_2:
        if lays_4:
            dest = lays_4[-1]
            dest_pieces = dest.setdefault("pieces", [])
            for ly2 in lays_2:
                for p in ly2.get("pieces", []):
                    p["layers"] = 4
                    p.pop("is_sobras", None)
                    p.pop("is_tip", None)
                    dest_pieces.append(p)
        updated = lays_4

    if not updated:
        updated = copy.deepcopy(layouts)

    # 3. Renumera e recalcula
    plate_w = float(updated[0].get("sheet_width_mm") or 1350.0)
    plate_h = float(updated[0].get("sheet_height_mm") or 2553.38)
    plate_area = max(1e-4, (plate_w * plate_h) / 1e6)

    for idx, ly in enumerate(updated):
        ly["layout_index"] = idx
        ly["name"] = f"lay{idx:04d}"
        ly["code"] = f"lay{idx:04d}"
        ly["layers"] = 4
        pieces = ly.get("pieces", [])
        for p in pieces:
            p["layers"] = 4
            p.pop("is_tip", None)
            p.pop("is_sobras", None)
        eff_pct, used_m2 = calculate_yield(pieces, plate_area)
        est_time, _ = calculate_atom_cutting_time(pieces)
        ly["yield_percent"] = eff_pct
        ly["yield_pct"] = eff_pct
        ly["cutting_time_sec"] = est_time
        ly["used_area_m2"] = used_m2

    msg = "[SOBRAS] Separação de sobras revertida. Layouts restaurados para enfesto padrão de 4 camadas."
    logger.info(msg)
    return updated, msg

