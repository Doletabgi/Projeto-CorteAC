"""
JobManager 2000 (Python Edition)
Regras de Camadas e Cálculo de Resto de Produção (layers_rule.py)
"""
from typing import Optional, Union


def calc_resto(pares: Union[int, float, str, None], camadas: Union[int, float, str, None]) -> int:
    """Resto exibido na coluna 'Resto' da grade de Moldes da SessionView.
    
    # CONFIRMAR NO WINDOWS: fórmula INFERIDA do print do Job Manager original (sessão 619955).
    Fórmula:
    - pecas = 2 * pares
    - sobra_pecas = pecas % camadas (camadas <= 1 ou indefinido: retorna 0)
    - resto = -(sobra_pecas // 2) (sobra em pares com sinal negativo)
    
    Exemplos com 4 camadas:
    - 125, 109 e 97 pares -> -1
    - 126 e 62 pares -> 0
    Com 2 camadas:
    - sempre 0
    Com camadas <= 1 ou None:
    - 0
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
        return 0
    try:
        c = int(camadas)
    except (ValueError, TypeError):
        return 0
    if c <= 1:
        return 0

    pecas = 2 * p
    sobra_pecas = pecas % c
    resto = -(sobra_pecas // 2)
    return resto
