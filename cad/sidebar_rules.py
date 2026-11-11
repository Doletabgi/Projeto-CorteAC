"""Regras de correspondência e contagem da barra lateral, sem dependência de UI.

Preserva a prioridade de IDs e tamanho e o fallback legado por nome/prefixo.
As quantidades retornadas são peças na mesa; conversões de camadas e pares
continuam em cad.layers_rule.
"""

def piece_matches_target(piece, target) -> bool:
    """
    Regra única de correspondência peça <-> molde da barra lateral.

    Usada tanto pelos CONTADORES quanto pela SELEÇÃO por clique na miniatura,
    para que o número exibido e as peças selecionadas nunca divirjam.
    """
    if not piece or not target:
        return False

    t_id = str(target.get("id") or "").strip()
    t_sz = str(target.get("size") or "").strip()
    t_nm = str(target.get("name") or "").strip()

    shp = piece.get("shape") if isinstance(piece.get("shape"), dict) else {}
    p_tid = str(piece.get("target_id") or piece.get("shape_id") or shp.get("id") or "").strip()
    p_sz = str(piece.get("size") or shp.get("size") or "").strip()
    p_nm = str(piece.get("name") or shp.get("name") or "").strip()

    # Rejeição imediata se tamanhos divergirem
    if p_sz and t_sz and p_sz != t_sz:
        return False

    # Correspondência por ID do molde
    if p_tid and t_id and p_tid == t_id:
        return True

    # Se ambos possuem ID explícito diferente, não correspondem
    if p_tid and t_id and p_tid != t_id:
        return False

    # Correspondência por nome idêntico ou prefixo (ex.: sufixos de tamanho ou truncamento)
    if p_nm and t_nm:
        if p_nm == t_nm:
            return True
        p_clean = p_nm.rstrip(".").lower()
        t_clean = t_nm.rstrip(".").lower()
        if p_clean == t_clean or p_clean.startswith(t_clean) or t_clean.startswith(p_clean):
            return True

    # Correspondência por tamanho idêntico
    if p_sz and t_sz and p_sz == t_sz and (not p_nm or not t_nm or p_nm == t_nm):
        return True

    return False


def count_pieces_for_target(pieces, target) -> int:
    """Conta peças físicas que correspondem ao molde/tamanho solicitado."""
    if not pieces or not target:
        return 0
    return sum(1 for piece in pieces if piece_matches_target(piece, target))


def get_plates_for_target(layouts, current_layout_index, placed_pieces, target) -> list:
    """Placas em ordem (base 1), usando a edição atual em vez da cópia salva."""
    if not target:
        return []
    if not layouts:
        return [1] if count_pieces_for_target(placed_pieces, target) else []
    plates = []
    for index, layout in enumerate(layouts):
        pieces = (placed_pieces if index == current_layout_index else
                  layout.get("pieces") or layout.get("placed_pieces") or [])
        if count_pieces_for_target(pieces, target):
            plates.append(index + 1)
    return plates
