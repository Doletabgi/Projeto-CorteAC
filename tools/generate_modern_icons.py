#!/usr/bin/env python3
"""
tools/generate_modern_icons.py
Gera ícones modernos, nítidos, anti-aliased (RGBA 32-bit com transparência)
para substituir os ícones retrô da interface do CorteAC.

Usa super-sampling (desenho em 4x e redução via Lanczos) para garantir
acabamento vetorial perfeito e zero serrilhamento.
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter


def create_supersampled(target_size: int, scale: int = 4):
    """Cria uma imagem RGBA vazia com resolução multiplicada por `scale`."""
    size = target_size * scale
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    return img, draw, scale


def finish_icon(img: Image.Image, target_size: int) -> Image.Image:
    """Reduz a imagem para o tamanho final usando filtro Lanczos de alta qualidade."""
    return img.resize((target_size, target_size), Image.Resampling.LANCZOS)


# =========================================================================
# 1. TOOLBAR: Cut (Tesoura Moderna)
# =========================================================================
def make_cut_icon(target_size=16) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    # Dimensões 64x64
    blade_color = (203, 213, 225, 255)   # Prata claro #cbd5e1
    blade_edge = (148, 163, 184, 255)    # Prata escuro #94a3b8
    blade_shine = (248, 250, 252, 255)   # Brilho branco #f8fafc
    handle_color = (37, 99, 235, 255)    # Azul royal #2563eb
    handle_inner = (29, 78, 216, 255)    # Azul escuro #1d4ed8
    screw_color = (71, 85, 105, 255)     # Parafuso cinza #475569

    # Lâmina 1: de (30, 30) para superior direito (54, 10)
    blade1 = [(30*s//4, 30*s//4), (54*s//4, 10*s//4), (50*s//4, 8*s//4), (28*s//4, 26*s//4)]
    draw.polygon(blade1, fill=blade_color, outline=blade_edge)
    draw.line([(31*s//4, 29*s//4), (52*s//4, 9*s//4)], fill=blade_shine, width=max(1, s//4))

    # Lâmina 2: de (34, 30) para superior esquerdo (10, 10)
    blade2 = [(34*s//4, 30*s//4), (10*s//4, 10*s//4), (14*s//4, 8*s//4), (36*s//4, 26*s//4)]
    draw.polygon(blade2, fill=blade_color, outline=blade_edge)
    draw.line([(33*s//4, 29*s//4), (12*s//4, 9*s//4)], fill=blade_shine, width=max(1, s//4))

    # Hastes dos pegadores
    draw.line([(28*s//4, 34*s//4), (18*s//4, 46*s//4)], fill=handle_inner, width=4*s//4)
    draw.line([(36*s//4, 34*s//4), (46*s//4, 46*s//4)], fill=handle_inner, width=4*s//4)

    # Pegador 1 (inferior esquerdo)
    box1 = [8*s//4, 42*s//4, 24*s//4, 58*s//4]
    draw.ellipse(box1, outline=handle_color, width=4*s//4)

    # Pegador 2 (inferior direito)
    box2 = [40*s//4, 42*s//4, 56*s//4, 58*s//4]
    draw.ellipse(box2, outline=handle_color, width=4*s//4)

    # Parafuso central
    screw_box = [30*s//4, 28*s//4, 34*s//4, 32*s//4]
    draw.ellipse(screw_box, fill=screw_color)

    return finish_icon(img, target_size)


# =========================================================================
# 2. TOOLBAR: Copy (Dois Documentos Sobrepostos)
# =========================================================================
def make_copy_icon(target_size=16) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    # Folha de trás (offset para cima e esquerda)
    bg_border = (148, 163, 184, 255)
    bg_fill = (241, 245, 249, 255)
    draw.rounded_rectangle([10*s//4, 6*s//4, 44*s//4, 48*s//4], radius=3*s//4, fill=bg_fill, outline=bg_border, width=2*s//4)

    # Folha da frente (offset para baixo e direita)
    fg_border = (37, 99, 235, 255)       # Azul elegante
    fg_fill = (255, 255, 255, 255)
    draw.rounded_rectangle([20*s//4, 16*s//4, 54*s//4, 58*s//4], radius=3*s//4, fill=fg_fill, outline=fg_border, width=2*s//4)

    # Canto dobrado na folha da frente
    fold_pts = [(44*s//4, 16*s//4), (54*s//4, 26*s//4), (44*s//4, 26*s//4)]
    draw.polygon(fold_pts, fill=(219, 234, 254, 255), outline=fg_border)

    # Linhas de texto modernas na folha da frente
    line_color = (148, 163, 184, 255)
    draw.line([(26*s//4, 32*s//4), (48*s//4, 32*s//4)], fill=line_color, width=2*s//4)
    draw.line([(26*s//4, 40*s//4), (48*s//4, 40*s//4)], fill=line_color, width=2*s//4)
    draw.line([(26*s//4, 48*s//4), (40*s//4, 48*s//4)], fill=line_color, width=2*s//4)

    return finish_icon(img, target_size)


# =========================================================================
# 3. TOOLBAR: Paste (Prancheta com Papel)
# =========================================================================
def make_paste_icon(target_size=16) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    # Prancheta (fundo marrom/grafite moderno)
    board_fill = (71, 85, 105, 255)      # Slate escuro elegante #475569
    board_border = (51, 65, 85, 255)
    draw.rounded_rectangle([10*s//4, 12*s//4, 54*s//4, 60*s//4], radius=4*s//4, fill=board_fill, outline=board_border, width=2*s//4)

    # Folha de papel branca na prancheta
    paper_fill = (255, 255, 255, 255)
    paper_border = (148, 163, 184, 255)
    draw.rounded_rectangle([16*s//4, 18*s//4, 48*s//4, 54*s//4], radius=2*s//4, fill=paper_fill, outline=paper_border, width=2*s//4)

    # Linhas de texto azuis suaves
    draw.line([(22*s//4, 28*s//4), (42*s//4, 28*s//4)], fill=(59, 130, 246, 255), width=2*s//4)
    draw.line([(22*s//4, 36*s//4), (42*s//4, 36*s//4)], fill=(148, 163, 184, 255), width=2*s//4)
    draw.line([(22*s//4, 44*s//4), (36*s//4, 44*s//4)], fill=(148, 163, 184, 255), width=2*s//4)

    # Clipe metálico no topo
    clip_fill = (226, 232, 240, 255)
    clip_border = (100, 116, 139, 255)
    draw.rounded_rectangle([24*s//4, 6*s//4, 40*s//4, 16*s//4], radius=3*s//4, fill=clip_fill, outline=clip_border, width=2*s//4)
    draw.ellipse([30*s//4, 9*s//4, 34*s//4, 13*s//4], fill=(71, 85, 105, 255))

    return finish_icon(img, target_size)


# =========================================================================
# 4. TOOLBAR: Details (Detalhes / Propriedades)
# =========================================================================
def make_details_icon(target_size=18) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    # Folha de relatório técnico
    draw.rounded_rectangle([8*s//4, 8*s//4, 56*s//4, 58*s//4], radius=4*s//4, fill=(255, 255, 255, 255), outline=(148, 163, 184, 255), width=2*s//4)

    # Cabeçalho da tabela (azul profissional)
    draw.rounded_rectangle([12*s//4, 12*s//4, 52*s//4, 22*s//4], radius=2*s//4, fill=(37, 99, 235, 255))

    # Linhas de dados (tabela limpa)
    draw.line([(14*s//4, 30*s//4), (50*s//4, 30*s//4)], fill=(203, 213, 225, 255), width=2*s//4)
    draw.line([(14*s//4, 38*s//4), (50*s//4, 38*s//4)], fill=(203, 213, 225, 255), width=2*s//4)
    draw.line([(14*s//4, 46*s//4), (50*s//4, 46*s//4)], fill=(203, 213, 225, 255), width=2*s//4)

    # Checkmarks ou indicadores verdes e azuis
    draw.ellipse([14*s//4, 28*s//4, 18*s//4, 32*s//4], fill=(16, 185, 129, 255))
    draw.ellipse([14*s//4, 36*s//4, 18*s//4, 40*s//4], fill=(59, 130, 246, 255))
    draw.ellipse([14*s//4, 44*s//4, 18*s//4, 48*s//4], fill=(245, 158, 11, 255))

    # Lápis / marcador em diagonal no canto inferior direito
    pencil_pts = [(42*s//4, 48*s//4), (58*s//4, 32*s//4), (62*s//4, 36*s//4), (46*s//4, 52*s//4)]
    draw.polygon(pencil_pts, fill=(245, 158, 11, 255), outline=(180, 83, 9, 255))
    tip_pts = [(42*s//4, 48*s//4), (46*s//4, 52*s//4), (38*s//4, 56*s//4)]
    draw.polygon(tip_pts, fill=(30, 41, 59, 255))

    return finish_icon(img, target_size)


# =========================================================================
# 5. TOOLBAR: Layout Editor (Mosaico CAM Nesting)
# =========================================================================
def make_layout_icon(target_size=18) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    # Borda da chapa de corte (retângulo arredondado cinza escuro)
    draw.rounded_rectangle([4*s//4, 4*s//4, 60*s//4, 60*s//4], radius=6*s//4, fill=(248, 250, 252, 255), outline=(71, 85, 105, 255), width=3*s//4)

    # Peça 1: Molde azul no canto superior esquerdo
    p1 = [(10*s//4, 12*s//4), (34*s//4, 12*s//4), (28*s//4, 32*s//4), (10*s//4, 28*s//4)]
    draw.polygon(p1, fill=(37, 99, 235, 255), outline=(29, 78, 216, 255))

    # Peça 2: Molde verde esmeralda no topo direito
    p2 = [(38*s//4, 12*s//4), (54*s//4, 12*s//4), (54*s//4, 38*s//4), (32*s//4, 36*s//4)]
    draw.polygon(p2, fill=(16, 185, 129, 255), outline=(5, 150, 105, 255))

    # Peça 3: Molde âmbar na base esquerda
    p3 = [(10*s//4, 34*s//4), (28*s//4, 38*s//4), (32*s//4, 54*s//4), (10*s//4, 54*s//4)]
    draw.polygon(p3, fill=(245, 158, 11, 255), outline=(217, 119, 6, 255))

    # Peça 4: Molde ciano na base direita
    p4 = [(36*s//4, 42*s//4), (54*s//4, 42*s//4), (54*s//4, 54*s//4), (36*s//4, 54*s//4)]
    draw.polygon(p4, fill=(6, 182, 212, 255), outline=(8, 145, 178, 255))

    return finish_icon(img, target_size)


# =========================================================================
# 6. TOOLBAR: Shape Editor (Moldes / Vetor CAD)
# =========================================================================
def make_shed_icon(target_size=20) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    # Molde curvo moderno de calçado
    shoe_pts = [
        (10*s//4, 44*s//4),
        (12*s//4, 32*s//4),
        (22*s//4, 18*s//4),
        (38*s//4, 16*s//4),
        (54*s//4, 26*s//4),
        (56*s//4, 42*s//4),
        (46*s//4, 48*s//4),
        (28*s//4, 46*s//4),
    ]
    draw.polygon(shoe_pts, fill=(59, 130, 246, 220), outline=(29, 78, 216, 255))

    # Linha de cota / régua técnica
    draw.line([(8*s//4, 54*s//4), (56*s//4, 54*s//4)], fill=(148, 163, 184, 255), width=2*s//4)
    for x in [8, 16, 24, 32, 40, 48, 56]:
        h = 6 if x in (8, 32, 56) else 3
        draw.line([(x*s//4, 54*s//4), (x*s//4, (54 - h)*s//4)], fill=(100, 116, 139, 255), width=2*s//4)

    # Caneta de vetor / nó de âncora CAD no topo
    anchor = [36*s//4, 14*s//4, 40*s//4, 18*s//4]
    draw.rectangle(anchor, fill=(245, 158, 11, 255), outline=(180, 83, 9, 255))

    return finish_icon(img, target_size)


# =========================================================================
# 7. MODE BAR: Produção (Monitor Widescreen Moderno)
# =========================================================================
def make_mode_prod_icon(target_size=20) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    # Monitor ultrafino widescreen
    draw.rounded_rectangle([4*s//4, 8*s//4, 60*s//4, 46*s//4], radius=4*s//4, fill=(15, 23, 42, 255), outline=(51, 65, 85, 255), width=2*s//4)
    draw.rounded_rectangle([7*s//4, 11*s//4, 57*s//4, 43*s//4], radius=2*s//4, fill=(30, 41, 59, 255))

    # Barras de status
    draw.rounded_rectangle([12*s//4, 26*s//4, 18*s//4, 38*s//4], radius=1*s//4, fill=(59, 130, 246, 255))
    draw.rounded_rectangle([22*s//4, 20*s//4, 28*s//4, 38*s//4], radius=1*s//4, fill=(16, 185, 129, 255))
    draw.rounded_rectangle([32*s//4, 28*s//4, 38*s//4, 38*s//4], radius=1*s//4, fill=(245, 158, 11, 255))
    draw.rounded_rectangle([42*s//4, 16*s//4, 48*s//4, 38*s//4], radius=1*s//4, fill=(14, 165, 233, 255))

    # Linha de tendência
    draw.line([(15*s//4, 24*s//4), (25*s//4, 18*s//4), (35*s//4, 26*s//4), (45*s//4, 14*s//4)], fill=(248, 250, 252, 255), width=2*s//4)

    # Suporte / haste do monitor
    draw.rectangle([28*s//4, 46*s//4, 36*s//4, 54*s//4], fill=(148, 163, 184, 255))
    draw.rounded_rectangle([20*s//4, 54*s//4, 44*s//4, 58*s//4], radius=2*s//4, fill=(100, 116, 139, 255))

    return finish_icon(img, target_size)


# =========================================================================
# 8. MODE BAR: Moldes (Molde Vetorial Verde Esmeralda)
# =========================================================================
def make_mode_moldes_icon(target_size=20) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    pts = [
        (8*s//4, 48*s//4),
        (12*s//4, 32*s//4),
        (26*s//4, 16*s//4),
        (46*s//4, 14*s//4),
        (58*s//4, 24*s//4),
        (56*s//4, 44*s//4),
        (44*s//4, 52*s//4),
        (24*s//4, 50*s//4),
    ]
    draw.polygon(pts, fill=(16, 185, 129, 255), outline=(5, 150, 105, 255))

    inner_pts = [
        (16*s//4, 42*s//4),
        (18*s//4, 34*s//4),
        (28*s//4, 24*s//4),
        (42*s//4, 22*s//4),
        (50*s//4, 28*s//4),
    ]
    draw.line(inner_pts, fill=(110, 231, 183, 255), width=2*s//4)

    for p in [(26*s//4, 16*s//4), (58*s//4, 24*s//4), (44*s//4, 52*s//4)]:
        draw.rectangle([p[0]-2*s//4, p[1]-2*s//4, p[0]+2*s//4, p[1]+2*s//4], fill=(255, 255, 255, 255), outline=(4, 120, 87, 255))

    return finish_icon(img, target_size)


# =========================================================================
# 9. MODE BAR: Materiais (Camadas 3D de Material de Corte)
# =========================================================================
def make_mode_mat_icon(target_size=20) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    # Três camadas modernas empilhadas
    draw.rounded_rectangle([6*s//4, 38*s//4, 58*s//4, 54*s//4], radius=4*s//4, fill=(71, 85, 105, 255), outline=(51, 65, 85, 255))
    draw.rounded_rectangle([6*s//4, 24*s//4, 58*s//4, 40*s//4], radius=4*s//4, fill=(14, 165, 233, 255), outline=(2, 132, 199, 255))
    draw.rounded_rectangle([6*s//4, 10*s//4, 58*s//4, 26*s//4], radius=4*s//4, fill=(245, 158, 11, 255), outline=(217, 119, 6, 255))

    draw.line([(14*s//4, 18*s//4), (44*s//4, 18*s//4)], fill=(254, 243, 199, 255), width=2*s//4)
    draw.line([(14*s//4, 32*s//4), (40*s//4, 32*s//4)], fill=(224, 242, 254, 255), width=2*s//4)

    return finish_icon(img, target_size)


# =========================================================================
# 10. TREEVIEW: Raiz Produção (iconJobNodeBase 16x16)
# =========================================================================
def make_tree_prod_node_icon(target_size=16) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    draw.rounded_rectangle([4*s//4, 6*s//4, 60*s//4, 46*s//4], radius=3*s//4, fill=(30, 41, 59, 255), outline=(71, 85, 105, 255), width=2*s//4)
    draw.rounded_rectangle([8*s//4, 10*s//4, 56*s//4, 42*s//4], radius=1*s//4, fill=(14, 165, 233, 255))

    draw.ellipse([26*s//4, 20*s//4, 38*s//4, 32*s//4], fill=(255, 255, 255, 255))
    draw.ellipse([29*s//4, 23*s//4, 35*s//4, 29*s//4], fill=(14, 165, 233, 255))

    draw.rectangle([28*s//4, 46*s//4, 36*s//4, 52*s//4], fill=(100, 116, 139, 255))
    draw.rounded_rectangle([20*s//4, 52*s//4, 44*s//4, 56*s//4], radius=2*s//4, fill=(71, 85, 105, 255))

    return finish_icon(img, target_size)


# =========================================================================
# 11. TREEVIEW: Pasta de Produção (iconJobJobFolder 16x16)
# =========================================================================
def make_tree_folder_icon(target_size=16) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    folder_back = (217, 119, 6, 255)
    folder_front = (245, 158, 11, 255)
    folder_tab = (251, 191, 36, 255)

    tab_pts = [(6*s//4, 14*s//4), (24*s//4, 14*s//4), (30*s//4, 22*s//4), (58*s//4, 22*s//4), (58*s//4, 54*s//4), (6*s//4, 54*s//4)]
    draw.polygon(tab_pts, fill=folder_back)

    draw.rounded_rectangle([12*s//4, 18*s//4, 52*s//4, 34*s//4], radius=2*s//4, fill=(255, 255, 255, 255))

    draw.rounded_rectangle([4*s//4, 24*s//4, 60*s//4, 56*s//4], radius=3*s//4, fill=folder_front, outline=folder_back, width=1*s//4)
    draw.line([(8*s//4, 26*s//4), (56*s//4, 26*s//4)], fill=folder_tab, width=2*s//4)

    return finish_icon(img, target_size)


# =========================================================================
# 12. TREEVIEW: Pedido / Artigo (iconJobOrder 16x16)
# =========================================================================
def make_tree_order_icon(target_size=16) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    tag_bg = (37, 99, 235, 255)
    tag_border = (29, 78, 216, 255)

    pts = [
        (6*s//4, 32*s//4),
        (18*s//4, 14*s//4),
        (58*s//4, 14*s//4),
        (58*s//4, 50*s//4),
        (18*s//4, 50*s//4),
    ]
    draw.polygon(pts, fill=tag_bg, outline=tag_border)

    draw.ellipse([14*s//4, 28*s//4, 22*s//4, 36*s//4], fill=(255, 255, 255, 255), outline=tag_border)
    draw.line([(28*s//4, 24*s//4), (52*s//4, 24*s//4)], fill=(255, 255, 255, 255), width=2*s//4)
    draw.line([(28*s//4, 32*s//4), (48*s//4, 32*s//4)], fill=(251, 191, 36, 255), width=2*s//4)
    draw.line([(28*s//4, 40*s//4), (44*s//4, 40*s//4)], fill=(191, 219, 254, 255), width=2*s//4)

    return finish_icon(img, target_size)


# =========================================================================
# 13. TREEVIEW: Sessão de Corte (iconJobSession 16x16)
# =========================================================================
def make_tree_session_icon(target_size=16) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    draw.rounded_rectangle([6*s//4, 8*s//4, 58*s//4, 56*s//4], radius=3*s//4, fill=(241, 245, 249, 255), outline=(100, 116, 139, 255), width=2*s//4)

    draw.rounded_rectangle([12*s//4, 14*s//4, 32*s//4, 30*s//4], radius=2*s//4, fill=(37, 99, 235, 255))
    draw.rounded_rectangle([36*s//4, 14*s//4, 52*s//4, 30*s//4], radius=2*s//4, fill=(245, 158, 11, 255))
    draw.rounded_rectangle([12*s//4, 34*s//4, 40*s//4, 48*s//4], radius=2*s//4, fill=(16, 185, 129, 255))

    draw.ellipse([44*s//4, 40*s//4, 56*s//4, 52*s//4], fill=(34, 197, 94, 255), outline=(255, 255, 255, 255), width=2*s//4)

    return finish_icon(img, target_size)


# =========================================================================
# 14. TREEVIEW: Moldes Raiz e Artigo (iconShpShpBase / iconShpArticle 16x16)
# =========================================================================
def make_tree_shp_icon(target_size=16) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    pts = [
        (8*s//4, 46*s//4),
        (12*s//4, 28*s//4),
        (26*s//4, 14*s//4),
        (46*s//4, 12*s//4),
        (56*s//4, 24*s//4),
        (54*s//4, 44*s//4),
        (40*s//4, 52*s//4),
        (20*s//4, 50*s//4),
    ]
    draw.polygon(pts, fill=(16, 185, 129, 255), outline=(5, 150, 105, 255))
    draw.ellipse([26*s//4, 24*s//4, 34*s//4, 32*s//4], fill=(255, 255, 255, 255))
    return finish_icon(img, target_size)


# =========================================================================
# 15. TREEVIEW: Materiais Raiz (iconMatBase 16x16)
# =========================================================================
def make_tree_mat_icon(target_size=16) -> Image.Image:
    img, draw, s = create_supersampled(target_size, scale=4)
    draw.rounded_rectangle([6*s//4, 34*s//4, 58*s//4, 50*s//4], radius=2*s//4, fill=(71, 85, 105, 255))
    draw.rounded_rectangle([6*s//4, 22*s//4, 58*s//4, 38*s//4], radius=2*s//4, fill=(14, 165, 233, 255))
    draw.rounded_rectangle([6*s//4, 10*s//4, 58*s//4, 26*s//4], radius=2*s//4, fill=(245, 158, 11, 255))
    return finish_icon(img, target_size)


def generate_all_icons(assets_dir: Path):
    """Gera e salva todos os novos ícones modernos em assets/."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    layout_dir = assets_dir / "layout"
    layout_dir.mkdir(parents=True, exist_ok=True)

    icons_map = {
        # Toolbar
        assets_dir / "tlbCut.png": make_cut_icon(16),
        assets_dir / "tlbCopy.png": make_copy_icon(16),
        assets_dir / "tlbPaste.png": make_paste_icon(16),
        assets_dir / "tlbDetails.png": make_details_icon(18),
        layout_dir / "layout_icon.png": make_layout_icon(18),
        layout_dir / "layout_icon_16.png": make_layout_icon(16),
        layout_dir / "layout_icon_32.png": make_layout_icon(32),
        assets_dir / "iconShed.png": make_shed_icon(20),

        # Mode Bar
        assets_dir / "btn_prod.png": make_mode_prod_icon(20),
        assets_dir / "btn_moldes.png": make_mode_moldes_icon(20),
        assets_dir / "btn_mat.png": make_mode_mat_icon(20),
        assets_dir / "mode_job.png": make_mode_prod_icon(20),
        assets_dir / "mode_shp.png": make_mode_moldes_icon(20),
        assets_dir / "mode_mat.png": make_mode_mat_icon(20),

        # Treeview
        assets_dir / "iconJobNodeBase.png": make_tree_prod_node_icon(16),
        assets_dir / "iconJobJobFolder.png": make_tree_folder_icon(16),
        assets_dir / "iconJobOrder.png": make_tree_order_icon(16),
        assets_dir / "iconJobSession.png": make_tree_session_icon(16),
        assets_dir / "iconShpShpBase.png": make_tree_shp_icon(16),
        assets_dir / "iconShpArticle.png": make_tree_shp_icon(16),
        assets_dir / "iconMatBase.png": make_tree_mat_icon(16),
    }

    for path, img in icons_map.items():
        img.save(path, "PNG")
        print(f"Salvo: {path.name} (tamanho: {img.size}, modo: {img.mode})")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    assets_path = repo_root / "assets"
    print(f"Gerando ícones modernos em: {assets_path}")
    generate_all_icons(assets_path)
    print("Todos os ícones modernos gerados com sucesso!")
