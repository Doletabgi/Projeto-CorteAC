"""Verificações de cadastro do assistente de diagnóstico, sem alterar a sessão."""

import math


def _number(value):
    try:
        result = float(str(value).replace(",", "."))
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def check_session(context):
    """Retorna achados com orientação e destino na interface; não valida colisões."""
    checks = []

    def add(key, status, title, result, guidance, target):
        checks.append(dict(key=key, status=status, title=title, result=result,
                           guidance=guidance, target=target))

    material = context.get("material") or {}
    width = _number(material.get("width_mm"))
    height = _number(material.get("height_mm"))
    dimensions_ok = all(v is not None and 0 < v <= 10000 for v in (width, height))
    if not material:
        add("material", "attention", "Material", "Nenhum material selecionado",
            "Abra Materiais e selecione o material que será cortado.", "materials")
    elif not dimensions_ok:
        add("material", "attention", "Material", "Confira as dimensões da placa",
            "Em Materiais, informe largura e comprimento maiores que zero e de até 10 metros.", "materials")
    else:
        add("material", "ok", "Material", f"{material.get('code') or 'Selecionado'} · {width:g} × {height:g} mm",
            "Confira se essas medidas correspondem à placa que você vai utilizar.", "materials")

    shapes = context.get("shapes") or []
    pairs = [_number(shape.get("pairs")) for shape in shapes]
    invalid_pairs = any(p is None or p < 0 or not p.is_integer() for p in pairs)
    if not shapes:
        add("shapes", "attention", "Moldes e quantidades", "Nenhum molde na sessão",
            "Abra Moldes, adicione os modelos e informe a quantidade de pares.", "shapes")
    elif invalid_pairs or sum(p for p in pairs if p is not None) <= 0:
        add("shapes", "attention", "Moldes e quantidades", "Confira a quantidade de pares",
            "Informe quantidades inteiras a partir de zero. Pelo menos um molde precisa ter pares a produzir.", "shapes")
    else:
        add("shapes", "ok", "Moldes e quantidades", f"{len(shapes)} molde(s) · {int(sum(pairs))} par(es) solicitados",
            "As quantidades estão preenchidas. Confira o pedido na aba Moldes.", "shapes")

    missing = [s for s in shapes if (_number(s.get("pairs")) or 0) > 0
               and (s.get("contour_points") or 0) < 3]
    if missing:
        add("contours", "attention", "Desenhos dos moldes", f"{len(missing)} molde(s) sem contorno disponível",
            "Confira ou importe novamente os desenhos na aba Moldes antes de gerar o encaixe.", "shapes")
    elif shapes:
        add("contours", "ok", "Desenhos dos moldes", "Contornos disponíveis para os moldes solicitados",
            "Os desenhos estão carregados. A posição das peças pode ser revisada no Layout Editor.", "shapes")

    gap = _number(context.get("gap_mm"))
    margins = [_number((context.get("margins") or {}).get(side))
               for side in ("left", "right", "top", "bottom")]
    margins_ok = all(v is not None and v >= 0 for v in margins)
    if margins_ok and dimensions_ok:
        margins_ok = margins[0] + margins[1] < width and margins[2] + margins[3] < height
    if gap is None or gap < 0 or not margins_ok:
        add("spacing", "attention", "Distância e margens", "Confira os espaços de corte",
            "Na aba Geral, revise a distância entre peças e as margens. As margens precisam deixar área útil na placa.", "general")
    elif gap == 0:
        add("spacing", "info", "Distância e margens", "Distância entre peças: 0 mm",
            "As peças podem ficar encostadas. Confira se o material e a ferramenta permitem essa distância.", "general")
    else:
        add("spacing", "ok", "Distância e margens", f"Distância entre peças: {gap:g} mm",
            "Os valores estão preenchidos. Ajuste na aba Geral conforme o material e a ferramenta.", "general")

    layouts = context.get("layouts_count", 0)
    pieces = context.get("placed_count", 0)
    if not pieces:
        add("layouts", "info", "Encaixe", "Ainda não há peças posicionadas",
            "Depois de conferir material e moldes, use Gerar na aba Geral. Em seguida, revise o resultado em Layout.", "general")
    else:
        add("layouts", "ok", "Encaixe", f"{layouts} placa(s) · {pieces} posição(ões) no layout",
            "Abra Layout para revisar as posições. Esta verificação confere os dados da sessão, sem analisar colisões.", "layouts")
    return checks
