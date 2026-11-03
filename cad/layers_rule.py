"""
JobManager 2000 (Python Edition)
Regras de Camadas e Cálculo de Resto de Produção (layers_rule.py)
"""
import math
from typing import Any, Dict, List, Optional, Union

__all__ = [
    "resolve_session_layers",
    "resolve_layout_layers",
    "layers_for_piece",
    "format_enfesto_operator_text",
    "is_layers_defined",
    "pecas_na_mesa",
    "calc_resto",
    "calc_resto_efetivo",
    "parse_session_params",
    "encode_session_params",
    "is_separar_sobras_enabled",
    "is_refile_auto_enabled",
    "trim_layout_dict",
    "calculate_layout_trim_bounds",
]



def resolve_layout_layers(
    layout: Optional[Dict[str, Any]] = None,
    session: Optional[Dict[str, Any]] = None,
    material: Optional[Dict[str, Any]] = None,
    grid_material_row: Optional[Union[list, tuple, dict]] = None,
    default: int = 2
) -> int:
    """
    Retorna as camadas de corte de um layout específico.
    Se o layout possuir 'layers' próprio válido (>= 1), usa esse valor prioritariamente.
    Caso contrário, herda as camadas da sessão via resolve_session_layers.
    """
    if layout and isinstance(layout, dict):
        ly_val = layout.get("layers")
        if ly_val is not None:
            try:
                v = int(ly_val)
                if v >= 1:
                    return v
            except (ValueError, TypeError):
                pass
    return resolve_session_layers(
        session=session,
        material=material,
        grid_material_row=grid_material_row,
        layout=layout,
        default=default
    )


def layers_for_piece(
    layout: Optional[Union[Dict[str, Any], Any]] = None,
    piece: Optional[Union[Dict[str, Any], Any]] = None
) -> int:
    """
    Função única de resolução de camadas de corte por peça individual.
    
    Regra do enfesto em degrau com ponta de 2 camadas:
    - Se o layout possuir 'tip_zone' = (x0, y0, x1, y1) em mm no sistema da placa e o
      centro geométrico da peça estiver dentro da ponta, retorna 'layers_tip' (2).
    - Caso contrário, retorna 'layers' do layout (ex: 4).
    - Sem 'tip_zone', mantém o comportamento padrão via resolve_layout_layers.
    """
    if layout is None:
        return 4

    tip_zone = None
    layers_tip = 2
    base_layers = 4

    if isinstance(layout, dict):
        base_layers = resolve_layout_layers(layout=layout, default=4)
        tip_zone = layout.get("tip_zone")
        if layout.get("layers_tip") is not None:
            try:
                layers_tip = int(layout["layers_tip"])
            except (ValueError, TypeError):
                layers_tip = 2
    else:
        base_layers = getattr(layout, "layers", 4) or 4
        tip_zone = getattr(layout, "tip_zone", None)
        if getattr(layout, "layers_tip", None) is not None:
            try:
                layers_tip = int(getattr(layout, "layers_tip"))
            except (ValueError, TypeError):
                layers_tip = 2

    if not tip_zone or not piece:
        return base_layers

    # Extrai coordenadas e centro da peça
    if isinstance(piece, dict):
        px = float(piece.get("x", 0.0))
        py = float(piece.get("y", 0.0))
        contour = piece.get("contour") or (piece.get("shape", {}).get("contour") if isinstance(piece.get("shape"), dict) else [])
        rot = float(piece.get("rotation", piece.get("angle", piece.get("rot_deg", 0.0))))
    else:
        px = float(getattr(piece, "x", 0.0))
        py = float(getattr(piece, "y", 0.0))
        contour = getattr(piece, "contour", [])
        rot = float(getattr(piece, "rot_deg", 0.0))

    if contour and len(contour) >= 3:
        try:
            from cad.geometry import transform_contour, polygon_bbox
            poly = transform_contour(contour, px, py, rot)
            min_x, min_y, max_x, max_y = polygon_bbox(poly)
            center_x = (min_x + max_x) / 2.0
            center_y = (min_y + max_y) / 2.0
        except Exception:
            center_x, center_y = px, py
    else:
        center_x, center_y = px, py

    try:
        x0, y0, x1, y1 = tip_zone
        min_zx = min(float(x0), float(x1))
        max_zx = max(float(x0), float(x1))
        min_zy = min(float(y0), float(y1))
        max_zy = max(float(y0), float(y1))

        if (min_zx <= center_x <= max_zx) and (min_zy <= center_y <= max_zy):
            return layers_tip
    except Exception:
        pass

    return base_layers


def format_enfesto_operator_text(
    layout: Optional[Union[Dict[str, Any], Any]] = None,
    sheet_w: Optional[float] = None,
    sheet_h: Optional[float] = None,
    tip_mode: str = "canto"
) -> str:
    """
    Gera o texto oficial de instrução de enfesto para o operador no Editor e na impressão A4.
    
    Exemplo Canto:
    "Enfesto: 2 folhas longas de 299,00 × 138,00 cm + 2 folhas curtas, SEM cobrir a ponta de 50,00 × 30,00 cm no canto final"
    
    Exemplo Faixa:
    "Enfesto: 2 folhas longas de 299,00 × 138,00 cm + 2 folhas curtas de 138,00 × 269,00 cm"
    """
    tip_zone = None
    layers = 4
    if isinstance(layout, dict):
        tip_zone = layout.get("tip_zone")
        layers = int(layout.get("layers") or 4)
        if sheet_w is None:
            sheet_w = float(layout.get("width_mm") or layout.get("ris_w") or 1380.0)
        if sheet_h is None:
            sheet_h = float(layout.get("height_mm") or layout.get("ris_l") or 2990.0)
    elif layout is not None:
        tip_zone = getattr(layout, "tip_zone", None)
        layers = int(getattr(layout, "layers", 4) or 4)
        if sheet_w is None:
            sheet_w = float(getattr(layout, "ris_w", 1380.0) or 1380.0)
        if sheet_h is None:
            sheet_h = float(getattr(layout, "ris_l", 2990.0) or 2990.0)

    w_val = float(sheet_w or 1380.0)
    h_val = float(sheet_h or 2990.0)

    # NNN = comprimento/altura da placa (Y), LLL = largura da placa (X) em cm
    nnn_cm = h_val / 10.0
    lll_cm = w_val / 10.0

    if not tip_zone:
        cam_suf = "camada" if layers == 1 else "camadas"
        return f"Enfesto: {layers} {cam_suf} ({nnn_cm:.2f} × {lll_cm:.2f} cm)"

    x0, y0, x1, y1 = tip_zone
    min_x, max_x = min(x0, x1), max(x0, x1)
    min_y, max_y = min(y0, y1), max(y0, y1)

    l_ponta_cm = (max_x - min_x) / 10.0
    a_ponta_cm = (max_y - min_y) / 10.0
    x0_cm = min_x / 10.0
    y0_cm = min_y / 10.0

    # Modo faixa: x0 = 0 e a ponta cobre toda a largura
    is_faixa = (tip_mode == "faixa") or (abs(min_x) < 1.0 and abs(max_x - w_val) < 5.0)

    if is_faixa:
        return (
            f"Enfesto: 2 folhas longas de {nnn_cm:.2f} × {lll_cm:.2f} cm + "
            f"2 folhas curtas de {lll_cm:.2f} × {y0_cm:.2f} cm, SEM cobrir a ponta de {lll_cm:.2f} × {a_ponta_cm:.2f} cm"
        )
    else:
        return (
            f"Enfesto: 2 folhas longas de {nnn_cm:.2f} × {lll_cm:.2f} cm + 2 folhas curtas, "
            f"SEM cobrir a ponta de {l_ponta_cm:.2f} × {a_ponta_cm:.2f} cm no canto final"
        )



def resolve_session_layers(
    session: Optional[Dict[str, Any]] = None,
    material: Optional[Dict[str, Any]] = None,
    grid_material_row: Optional[Union[list, tuple, dict]] = None,
    layout: Optional[Dict[str, Any]] = None,
    default: int = 2
) -> int:
    """
    Fonte única de resolução de camadas de corte (layers).
    
    Prioridade estrita:
    1. grid_material_row (valor editado ao vivo na aba Materiais da sessão, coluna 6 / 'layers')
    2. session.get("layers") (valor persistido na sessão)
    3. material.get("layers") (do material da sessão ou tabela materials)
    4. layout.get("layers") (compatibilidade com Fase 6 / camadas por layout)
    5. Fallback: default (padrão 2)
    """
    # 1. Grid da aba Materiais (edição inline ou ativa)
    if grid_material_row is not None:
        if isinstance(grid_material_row, (list, tuple)) and len(grid_material_row) >= 7:
            cell_val = grid_material_row[6]
            if cell_val is not None:
                try:
                    v = int(str(cell_val).strip())
                    if v >= 1:
                        return v
                except (ValueError, TypeError):
                    pass
        elif isinstance(grid_material_row, dict):
            cell_val = grid_material_row.get("layers")
            if cell_val is not None:
                try:
                    v = int(str(cell_val).strip())
                    if v >= 1:
                        return v
                except (ValueError, TypeError):
                    pass

    # 2. Sessão persistida
    if session and isinstance(session, dict):
        sess_val = session.get("layers")
        if sess_val is not None:
            try:
                v = int(str(sess_val).strip())
                if v >= 1:
                    return v
            except (ValueError, TypeError):
                pass

    # 3. Material da sessão
    if material and isinstance(material, dict):
        mat_val = material.get("layers")
        if mat_val is not None:
            try:
                v = int(str(mat_val).strip())
                if v >= 1:
                    return v
            except (ValueError, TypeError):
                pass

    # 4. Layout (compatibilidade com Fase 6 / camadas por layout)
    if layout and isinstance(layout, dict):
        ly_val = layout.get("layers")
        if ly_val is not None:
            try:
                v = int(ly_val)
                if v >= 1:
                    return v
            except (ValueError, TypeError):
                pass

    # 5. Fallback padrão
    try:
        return max(1, int(default))
    except (ValueError, TypeError):
        return 2


def is_layers_defined(
    session: Optional[Dict[str, Any]] = None,
    material: Optional[Dict[str, Any]] = None,
    grid_material_row: Optional[Union[list, tuple, dict]] = None,
    layout: Optional[Dict[str, Any]] = None
) -> bool:
    """Verifica se alguma das fontes de camadas definiu um valor explícito e válido (>= 1)."""
    if layout and isinstance(layout, dict):
        ly_val = layout.get("layers")
        if ly_val is not None:
            try:
                if int(ly_val) >= 1:
                    return True
            except (ValueError, TypeError):
                pass

    if grid_material_row is not None:
        if isinstance(grid_material_row, (list, tuple)) and len(grid_material_row) >= 7:
            cell_val = grid_material_row[6]
            if cell_val is not None:
                try:
                    if int(str(cell_val).strip()) >= 1:
                        return True
                except (ValueError, TypeError):
                    pass
        elif isinstance(grid_material_row, dict):
            cell_val = grid_material_row.get("layers")
            if cell_val is not None:
                try:
                    if int(str(cell_val).strip()) >= 1:
                        return True
                except (ValueError, TypeError):
                    pass

    if material and isinstance(material, dict):
        mat_val = material.get("layers")
        if mat_val is not None:
            try:
                if int(str(mat_val).strip()) >= 1:
                    return True
            except (ValueError, TypeError):
                pass

    if session and isinstance(session, dict):
        sess_val = session.get("layers")
        if sess_val is not None:
            try:
                if int(str(sess_val).strip()) >= 1:
                    return True
            except (ValueError, TypeError):
                pass

    return False


def pecas_na_mesa(pares: Union[int, float, str, None], camadas: Union[int, float, str, None]) -> int:
    """Calcula a quantidade de peças desenhadas na mesa CAD / placa.
    
    Regra canônica:
    - pares <= 0 -> 0
    - camadas None ou <= 1 -> pares * 2
    - senao -> ceil((pares * 2) / camadas)
    """
    if pares is None:
        return 0
    try:
        p = int(pares)
    except (ValueError, TypeError):
        return 0
    if p <= 0:
        return 0

    if camadas is None:
        return p * 2
    try:
        c = int(camadas)
    except (ValueError, TypeError):
        return p * 2
    if c <= 1:
        return p * 2

    return math.ceil((p * 2) / c)


def calc_resto(pares: Union[int, float, str, None], camadas: Union[int, float, str, None]) -> int:
    """Resto exibido na coluna 'Resto' da grade de Moldes da SessionView.
    
    # CONFIRMAR NO WINDOWS: fórmula INFERIDA do print do Job Manager original (sessão 619955).
    Fórmula:
    desenhadas = pecas_na_mesa(pares, camadas)
    pedidas = 2 * p
    produzidas = desenhadas * c
    return -math.ceil((produzidas - pedidas) / 2)
    
    Garante sempre calc_resto <= 0 (nunca positivo, pois pecas_produzidas >= pecas_pedidas).
    """
    if pares is None:
        return 0
    try:
        p = int(pares)
    except (ValueError, TypeError):
        return 0
    if p <= 0:
        return 0

    desenhadas = pecas_na_mesa(p, camadas)
    if camadas is None:
        c = 1
    else:
        try:
            c = max(1, int(camadas))
        except (ValueError, TypeError):
            c = 1

    pedidas = 2 * p
    produzidas = desenhadas * c
    return -math.ceil((produzidas - pedidas) / 2)


def calc_resto_efetivo(
    pares: Union[int, float, str, None],
    camadas: Union[int, float, str, None],
    separar: bool = True,
    layouts_atuais: Optional[List[Dict[str, Any]]] = None
) -> int:
    """Resto efetivo considerando a separação real de sobras nos layouts.

    Se 'separar' for True e camadas == 4, verifica se algum layout realmente
    possui tip_zone ou layers=2. Se sim, o resto foi absorvido (0).
    Se não, a separação falhou e o resto real é -1.
    """
    if separar:
        try:
            c = int(camadas) if camadas is not None else 2
        except (ValueError, TypeError):
            c = 2

        if c == 4:
            if calc_resto(pares, camadas) == 0:
                return 0
            if layouts_atuais is not None:
                tem_ponta = any(
                    (ly.get("tip_zone") is not None or ly.get("layers") == 2)
                    if isinstance(ly, dict)
                    else (getattr(ly, "tip_zone", None) is not None or getattr(ly, "layers", None) == 2)
                    for ly in layouts_atuais
                )
                if tem_ponta:
                    return 0
                else:
                    return -1
            return 0

    return calc_resto(pares, camadas)


def parse_session_params(raw_params: Optional[str]) -> tuple:
    """Extrai o preset base e opções extras codificadas no campo params da sessão.

    Exemplo:
        'stdNOTFill;separar_sobras=1' -> ('stdNOTFill', {'separar_sobras': '1'})
        'ALTERNADO' -> ('ALTERNADO', {})
        None -> ('ALTERNADO', {})
    """
    if not raw_params:
        return ("ALTERNADO", {})
    parts = str(raw_params).split(";")
    preset = parts[0].strip() or "ALTERNADO"
    options = {}
    for p in parts[1:]:
        p_str = p.strip()
        if "=" in p_str:
            k, v = p_str.split("=", 1)
            options[k.strip()] = v.strip()
        elif p_str:
            options[p_str] = "1"
    return (preset, options)


def encode_session_params(preset_name: str, options_dict: Optional[Dict[str, Any]] = None) -> str:
    """Codifica o preset base e opções adicionais em uma string única para o campo params.

    Exemplo:
        encode_session_params('stdNOTFill', {'separar_sobras': '1'}) -> 'stdNOTFill;separar_sobras=1'
        encode_session_params('ALTERNADO', {}) -> 'ALTERNADO'
    """
    preset = (preset_name or "ALTERNADO").strip()
    if not options_dict:
        return preset
    pairs = []
    for k, v in options_dict.items():
        if k:
            pairs.append(f"{str(k).strip()}={str(v).strip()}")
    if pairs:
        return f"{preset};{';'.join(pairs)}"
    return preset


def is_separar_sobras_enabled(
    session_or_params: Any = None,
    default_camadas: Optional[int] = None
) -> bool:
    """Verifica se a separação de sobras em 2 camadas está habilitada.

    Regras:
    1. A separação só se aplica quando o enfesto da sessão for de 4 camadas.
    2. Com 4 camadas, o padrão é LIGADO (True), a menos que haja configuração
       explícita desligando ('separar_sobras=0' ou 'separar_sobras=false').
    """
    if session_or_params is None and default_camadas is None:
        return False

    layers = default_camadas
    raw_params = None

    if isinstance(session_or_params, dict):
        raw_params = session_or_params.get("params")
        layers = resolve_session_layers(session_or_params, default=default_camadas or 2)
    elif isinstance(session_or_params, str):
        raw_params = session_or_params

    if layers is None:
        return False
    try:
        if int(layers) != 4:
            return False
    except (ValueError, TypeError):
        return False

    _, opts = parse_session_params(raw_params)
    val = opts.get("separar_sobras")
    if val is not None:
        return str(val).strip().lower() in ("1", "true", "yes", "on", "sim")

    # Padrão: LIGADO para 4 camadas
    return True


def is_refile_auto_enabled(session_or_params: Any = None) -> bool:
    """Verifica se o refile automático de layout pós-nesting está habilitado nos parâmetros.

    Regras:
    - Lê a opção 'refile_auto' dos parâmetros da sessão ('params').
    - Retorna True se o valor for '1', 'true', 'yes', 'on', 'sim'.
    - Padrão: False (desligado).
    """
    if session_or_params is None:
        return False

    raw_params = None
    if isinstance(session_or_params, dict):
        raw_params = session_or_params.get("params")
    elif isinstance(session_or_params, str):
        raw_params = session_or_params

    if not raw_params:
        return False

    _, opts = parse_session_params(raw_params)
    val = opts.get("refile_auto")
    if val is not None:
        return str(val).strip().lower() in ("1", "true", "yes", "on", "sim")

    return False


# Reexportação utilitária de refile para conveniência
from cad.trim_engine import calculate_layout_trim_bounds, trim_layout_dict


