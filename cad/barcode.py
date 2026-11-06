"""
CorteAC - Barcode Engine (Code 128 Subset B)
Geração nativa de código de barras padrão industrial Code 128 em Python puro.
Suporta renderização vetorial precisa em Tkinter Canvas e exportação de alta resolução em Pillow.
"""

from typing import List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

# Tabela oficial de 107 padrões Code 128 (ISO/IEC 15417)
# Cada símbolo tem 11 módulos (Stop tem 13 módulos: 11 do padrão + 2 da barra de terminação '11')
CODE128_PATTERNS: Tuple[str, ...] = (
    "11011001100",  # 0
    "11001101100",  # 1
    "11001100110",  # 2
    "10010011000",  # 3
    "10010001100",  # 4
    "10001001100",  # 5
    "10011001000",  # 6
    "10011000100",  # 7
    "10001100100",  # 8
    "11001001000",  # 9
    "11001000100",  # 10
    "11000100100",  # 11
    "10110011100",  # 12
    "10011011100",  # 13
    "10011001110",  # 14
    "10111001100",  # 15
    "10011101100",  # 16
    "10011100110",  # 17
    "11001110010",  # 18
    "11001011100",  # 19
    "11001001110",  # 20
    "11011100100",  # 21
    "11001110100",  # 22
    "11101101110",  # 23
    "11101001100",  # 24
    "11100101100",  # 25
    "11100100110",  # 26
    "11101100100",  # 27
    "11100110100",  # 28
    "11100110010",  # 29
    "11011011000",  # 30
    "11011000110",  # 31
    "11000110110",  # 32
    "10100011000",  # 33
    "10001011000",  # 34
    "10001000110",  # 35
    "10110001000",  # 36
    "10001101000",  # 37
    "10001100010",  # 38
    "11010001000",  # 39
    "11000101000",  # 40
    "11000100010",  # 41
    "10110111000",  # 42
    "10110001110",  # 43
    "10001101110",  # 44
    "10111011000",  # 45
    "10111000110",  # 46
    "10001110110",  # 47
    "11101110110",  # 48
    "11010001110",  # 49
    "11000101110",  # 50
    "11011101000",  # 51
    "11011100010",  # 52
    "11011101110",  # 53
    "11101011000",  # 54
    "11101000110",  # 55
    "11100010110",  # 56
    "11101101000",  # 57
    "11101100010",  # 58
    "11100011010",  # 59
    "11101111010",  # 60
    "11001000010",  # 61
    "11110001010",  # 62
    "10100110000",  # 63
    "10100001100",  # 64
    "10010110000",  # 65
    "10010000110",  # 66
    "10000101100",  # 67
    "10000100110",  # 68
    "10110010000",  # 69
    "10110000100",  # 70
    "10011010000",  # 71
    "10011000010",  # 72
    "10000110100",  # 73
    "10000110010",  # 74
    "11000010010",  # 75
    "11001010000",  # 76
    "11110111010",  # 77
    "11000010100",  # 78
    "10001111010",  # 79
    "10100111100",  # 80
    "10010111100",  # 81
    "10010011110",  # 82
    "10111100100",  # 83
    "10011110100",  # 84
    "10011110010",  # 85
    "11110100100",  # 86
    "11110010100",  # 87
    "11110010010",  # 88
    "11011011110",  # 89
    "11011110110",  # 90
    "11110110110",  # 91
    "10101111000",  # 92
    "10100011110",  # 93
    "10001011110",  # 94
    "10111101000",  # 95
    "10111100010",  # 96
    "11110101000",  # 97
    "11110100010",  # 98
    "10111011110",  # 99
    "10111101110",  # 100
    "11101011110",  # 101
    "11110101110",  # 102
    "11010000100",  # 103 (Start A)
    "11010010000",  # 104 (Start B)
    "11010011100",  # 105 (Start C)
    "11000111010",  # 106 (Stop pattern base)
)

START_B_CODE = 104
STOP_CODE = 106
STOP_TERMINATION_BAR = "11"


def sanitize_code128_b_text(text: str) -> str:
    """Filtra o texto garantindo caracteres ASCII imprimíveis suportados pelo Subset B (32 a 126)."""
    if not text:
        return ""
    clean_chars: List[str] = []
    for ch in str(text):
        o = ord(ch)
        if 32 <= o <= 126:
            clean_chars.append(ch)
        else:
            clean_chars.append("?")
    return "".join(clean_chars)


def encode_code128_b(text: str, quiet_zone_modules: int = 10) -> str:
    """
    Codifica a string em uma sequência binária de '1's (barra) e '0's (espaço)
    utilizando a tabela oficial do Code 128 (Subset B) com dígito verificador.
    """
    clean_text = sanitize_code128_b_text(text)
    if not clean_text:
        clean_text = "0"

    # Mapeia cada caractere ASCII para o valor correspondente (ASCII - 32)
    values = [ord(ch) - 32 for ch in clean_text]

    # Cálculo do dígito verificador módulo 103:
    # Checksum = (Start_Code + sum(pos * val for pos, val in enumerate(values, 1))) % 103
    chk = (START_B_CODE + sum(pos * val for pos, val in enumerate(values, start=1))) % 103

    # Monta a cadeia binária completa
    bits_list: List[str] = []

    # Zona de silêncio inicial
    if quiet_zone_modules > 0:
        bits_list.append("0" * quiet_zone_modules)

    # Start Code B
    bits_list.append(CODE128_PATTERNS[START_B_CODE])

    # Símbolos de dados
    for val in values:
        bits_list.append(CODE128_PATTERNS[val])

    # Símbolo verificador
    bits_list.append(CODE128_PATTERNS[chk])

    # Símbolo Stop + Barra de terminação de 2 módulos
    bits_list.append(CODE128_PATTERNS[STOP_CODE] + STOP_TERMINATION_BAR)

    # Zona de silêncio final
    if quiet_zone_modules > 0:
        bits_list.append("0" * quiet_zone_modules)

    return "".join(bits_list)


def draw_code128_canvas(
    canvas,
    x: float,
    y: float,
    text: str,
    height: float = 30.0,
    module_width: float = 1.0,
    show_text: bool = True,
    label: Optional[str] = None,
    tags: str = "barcode",
    fill: str = "#000000",
    font: Tuple[str, int] = ("Courier", 7),
) -> Tuple[float, float, float, float]:
    """
    Desenha o código de barras Code 128 diretamente em um Canvas Tkinter.
    Agrupa módulos pretos consecutivos em retângulos individuais para máxima nitidez e velocidade.
    Retorna o bounding box (x0, y0, x1, y1).
    """
    bits = encode_code128_b(text, quiet_zone_modules=10)
    cur_x = float(x)
    total_w = len(bits) * module_width
    bar_h = float(height)

    # Desenha barras
    i = 0
    n = len(bits)
    while i < n:
        if bits[i] == "1":
            start_i = i
            while i < n and bits[i] == "1":
                i += 1
            bx0 = cur_x + start_i * module_width
            bx1 = cur_x + i * module_width
            canvas.create_rectangle(
                bx0, y, bx1, y + bar_h,
                fill=fill, outline="", width=0,
                tags=(tags, f"{tags}_bar")
            )
        else:
            i += 1

    total_h = bar_h

    # Texto legível para operadores humanos
    if show_text:
        display_str = label if label is not None else text
        text_y = y + bar_h + 4.0
        canvas.create_text(
            cur_x + total_w / 2.0, text_y,
            text=display_str,
            font=font,
            fill=fill,
            anchor="n",
            tags=(tags, f"{tags}_text")
        )
        total_h += 14.0

    return (cur_x, float(y), cur_x + total_w, float(y) + total_h)


def generate_code128_pillow(
    text: str,
    height: int = 36,
    module_width: int = 2,
    show_text: bool = True,
    label: Optional[str] = None,
    quiet_zone_modules: int = 10,
    bg_color: str = "white",
    fg_color: str = "black",
) -> Optional["Image.Image"]:
    """
    Gera uma imagem Pillow (PIL) de alta resolução do código de barras Code 128.
    Utilizada para exportação fiel em PDF e impressoras térmicas/jato de tinta.
    """
    if Image is None or ImageDraw is None:
        return None

    bits = encode_code128_b(text, quiet_zone_modules=quiet_zone_modules)
    total_w = len(bits) * module_width
    text_space = 14 if show_text else 0
    total_h = height + text_space

    im = Image.new("RGB", (total_w, total_h), color=bg_color)
    draw = ImageDraw.Draw(im)

    # Desenha barras
    i = 0
    n = len(bits)
    while i < n:
        if bits[i] == "1":
            start_i = i
            while i < n and bits[i] == "1":
                i += 1
            bx0 = start_i * module_width
            bx1 = i * module_width - 1
            draw.rectangle([bx0, 0, bx1, height - 1], fill=fg_color)
        else:
            i += 1

    # Legenda textual humana
    if show_text:
        display_str = label if label is not None else text
        try:
            # Tenta carregar fonte padrão ou proporcional
            f = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), display_str, font=f)
            tw = bbox[2] - bbox[0]
            tx = max(0, (total_w - tw) // 2)
            draw.text((tx, height + 4), display_str, fill=fg_color, font=f)
        except Exception:
            pass

    return im
