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
    parse_session_params,
)
from cad.nesting_engine import (
    piece_matches_shape,
    sort_shapes_by_sequence,
    nest_multi_sheet,
    calculate_yield,
    calculate_atom_cutting_time,
)

logger = logging.getLogger("layers_split")


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
