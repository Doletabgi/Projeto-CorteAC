"""
JobManager 2000 (Python Edition)
Regras de Camadas e Cálculo de Resto de Produção (layers_rule.py)
"""
import math
from typing import Any, Dict, Optional, Union

__all__ = [
    "resolve_session_layers",
    "resolve_layout_layers",
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
    separar: bool = True
) -> int:
    """Resto efetivo considerando a separação automática de sobras de 4 camadas em 2 camadas.

    Regra de negócio confirmada:
    - Se separar for True e camadas == 4:
      A peça de sobra de cada molde com pares ímpares é transferida para uma placa
      extra de 2 camadas, absorvendo a sobra com precisão de pares (Resto = 0).
    - Caso contrário (separar False, ou camadas != 4):
      Retorna o calc_resto(pares, camadas) normal (-1 informativo para ímpar a 4 camadas).
    """
    if separar:
        try:
            c = int(camadas) if camadas is not None else 2
        except (ValueError, TypeError):
            c = 2
        if c == 4:
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


