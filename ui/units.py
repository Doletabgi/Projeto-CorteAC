"""
ui/units.py - Formatação e leitura de medidas em METROS para o operador.

Regra do projeto: as dimensões de placa/material são digitadas e exibidas em metros
com vírgula decimal (ex: 1,38), independentemente de o banco armazenar milímetros.
"""

from __future__ import annotations

DECIMAL_COMMA = ","


def format_m(mm: float, decimals: int = 2) -> str:
    """Converte milímetros para texto em metros com vírgula: 1380 -> '1,38'."""
    try:
        texto = f"{float(mm) / 1000.0:.{decimals}f}"
    except (TypeError, ValueError):
        return ""
    return texto.replace(".", DECIMAL_COMMA)


def format_dim_mm(width_mm: float, height_mm: float, decimals: int = 2) -> str:
    """Dimensões em metros no formato do operador: '1,38 x 2,99 m' (largura x comprimento)."""
    return f"{format_m(width_mm, decimals)} x {format_m(height_mm, decimals)} m"


def format_dim_m(width_m: float, height_m: float, decimals: int = 2) -> str:
    """Idem, para valores já em metros."""
    try:
        w = f"{float(width_m):.{decimals}f}".replace(".", DECIMAL_COMMA)
        h = f"{float(height_m):.{decimals}f}".replace(".", DECIMAL_COMMA)
    except (TypeError, ValueError):
        return ""
    return f"{w} x {h} m"


def parse_m(texto: str) -> float:
    """
    Lê uma medida digitada em metros ('1,38', '1.38', ' 2,99 m') e devolve metros.

    Levanta ValueError quando o texto não é um número válido.
    """
    if texto is None:
        raise ValueError("medida vazia")
    limpo = str(texto).strip().lower().replace("metros", "").replace("metro", "")
    limpo = limpo.replace("m", "").replace(DECIMAL_COMMA, ".").strip()
    if not limpo:
        raise ValueError("medida vazia")
    valor = float(limpo)
    if valor < 0:
        raise ValueError("medida negativa")
    return valor


def parse_m_to_mm(texto: str) -> float:
    """Lê metros digitados pelo operador e devolve milímetros (unidade do banco)."""
    return round(parse_m(texto) * 1000.0, 3)
