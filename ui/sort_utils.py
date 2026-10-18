"""
JobManager 2000 (Python Edition)
Utilitários de Ordenação Natural e por Tamanho de Calçados (sort_utils.py)
"""

import re
from typing import Any, List, Tuple


def natural_sort_key(s: Any) -> List[Tuple[int, float, str]]:
    """
    Chave de ordenação natural humana para strings alfanuméricas.
    Ex: '323_PalAcb_22a' < '323_PalAcb_36a', 'Shape #2' < 'Shape #10'.
    """
    if s is None:
        return []
    raw = str(s).strip()
    parts = re.split(r"(\d+(?:[.,]\d+)?)", raw)
    key = []
    for p in parts:
        if not p:
            continue
        try:
            num = float(p.replace(",", "."))
            key.append((0, num, p.lower()))
        except ValueError:
            key.append((1, 0.0, p.lower()))
    return key


def size_sort_key(s_size: Any, s_name: str = "") -> Tuple[int, float, str]:
    """
    Chave de ordenação especializada para tamanhos de calçado (ex: '36a', '22a', '39.5', '37 1/2', '41').
    Remove badges de cor/emojis e extrai a parte numérica decimal e sufixo.
    Se o tamanho estiver em branco, busca extrair do nome do molde.
    """
    raw = str(s_size or "").strip()
    if not raw and s_name:
        m = re.search(r"[_#\s](\d+(?:[.,]\d+)?\s*[a-zA-Z]?)$", str(s_name))
        if m:
            raw = m.group(1).strip()

    # Remove emojis e badges de cor iniciais (ex: '⬛ 36a' -> '36a')
    clean = re.sub(r"^[^\w\d.]+", "", raw).strip()

    # Tratamento para frações de ponto de calçado como '37 1/2'
    if " 1/2" in clean or "-1/2" in clean or "½" in clean:
        clean = clean.replace(" 1/2", ".5").replace("-1/2", ".5").replace("½", ".5")

    m = re.search(r"(\d+(?:[.,]\d+)?)", clean)
    if m:
        num = float(m.group(1).replace(",", "."))
        suffix = clean[m.end():].strip().lower()
        return (0, num, suffix)

    # Fallback se não tiver número
    return (1, 0.0, clean.lower())


def shape_area_sort_key(shape: dict) -> float:
    """
    Calcula a área física do contorno do molde em mm² para ordenação por dimensão geométrica.
    """
    if not isinstance(shape, dict):
        return 0.0
    contour = shape.get("contour") or []
    if not contour or len(contour) < 3:
        return 0.0
    try:
        from cad.geometry import polygon_area
        return float(polygon_area(contour))
    except Exception:
        return 0.0


def clean_session_display_name(name: Any) -> str:
    """
    Remove prefixos automáticos como '(#3)' ou '( #3 )' do nome da sessão.
    Garante que quando a sessão for renomeada (ex: para '121805'), tanto a árvore
    quanto a tabela exibam o nome limpo '121805' sem (#3), enquanto o SessId numérico
    permanece preservado intacto na coluna SessId.
    """
    if name is None:
        return ""
    s = str(name).strip()
    m = re.match(r"^\(\s*#?\d+\s*\)\s*(.+)$", s)
    if m:
        cleaned = m.group(1).strip()
        if cleaned:
            return cleaned
    return s

