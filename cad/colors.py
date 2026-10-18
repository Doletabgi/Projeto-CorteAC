"""
JobManager 2000 (Python Edition)
Footwear CAD Color System: Mapeamento de Cores por Número / Tamanho de Molde (Grade de Calçados)
Padrão ATOM FlashCut / JobManager / Shoemaster
"""

import re

# Paleta industrial de alta visibilidade e contraste para numeração de calçados
# Paleta industrial de alta visibilidade e contraste para numeração de calçados
SIZE_COLOR_PALETTE = [
    "#ea580c",  # Laranja Intenso (36)
    "#16a34a",  # Verde Esmeralda (35)
    "#6366f1",  # Índigo / Violeta (34)
    "#eab308",  # Amarelo Dourado (33)
    "#d946ef",  # Magenta / Fúcsia (32)
    "#06b6d4",  # Ciano / Turquesa (31)
    "#dc2626",  # Vermelho Vivo (30)
    "#84cc16",  # Verde Lima (29)
    "#7c3aed",  # Roxo Real (28)
    "#f59e0b",  # Âmbar Dourado (27)
    "#ec4899",  # Rosa Pink (26)
    "#0284c7",  # Azul Céu (25)
    "#0d9488",  # Teal / Verde Água Escuro (24)
    "#92400e",  # Marrom Terracota / Bronze (23)
    "#4338ca",  # Azul Marinho Escuro (22)
    "#65a30d",  # Verde Oliva Claro
    "#059669",  # Verde Floresta
    "#0ea5e9",  # Azul Elétrico
    "#3b82f6",  # Azul Cobalto
    "#2563eb",  # Azul Real
    "#8b5cf6",  # Violeta Suave
    "#9333ea",  # Púrpura Profundo
    "#c026d3",  # Orquídea
    "#db2777",  # Rosa Magenta
    "#b91c1c",  # Vermelho Rubi
    "#4f46e5",  # Azul Noturno
    "#334155",  # Cinza Ardósia
    "#475569",  # Grafite
    "#64748b",  # Aço
    "#0891b2",  # Ciano Petróleo
    "#14b8a6",  # Turquesa Claro
    "#22c55e",  # Verde Primavera
    "#a855f7",  # Lilás Claro
]

# Tabela padrão de correspondência: Cada número / tamanho de calçado tem sua própria cor única
# Regra Estrita: Cada número tem uma cor exclusiva, NUNCA repetindo entre numerações!
STANDARD_SIZE_COLORS = {
    # Grade Infantil / Bebê (18 a 21)
    "18": "#0891b2",  # Ciano Petróleo
    "19": "#14b8a6",  # Turquesa
    "20": "#22c55e",  # Verde Primavera
    "21": "#a855f7",  # Lilás / Lavanda

    # Grade Padrão (22 a 36 - 15 numerações com cores 100% distintas e contrastantes)
    "22": "#4338ca",  # Azul Marinho Escuro
    "23": "#92400e",  # Marrom Terracota / Bronze
    "24": "#0d9488",  # Verde Petróleo / Teal
    "25": "#0284c7",  # Azul Céu
    "26": "#ec4899",  # Rosa Pink
    "27": "#f59e0b",  # Âmbar Dourado
    "28": "#7c3aed",  # Roxo Real
    "29": "#84cc16",  # Verde Lima
    "30": "#dc2626",  # Vermelho Vivo
    "31": "#06b6d4",  # Ciano Vivo
    "32": "#d946ef",  # Fúcsia / Magenta
    "33": "#eab308",  # Amarelo Ouro
    "34": "#6366f1",  # Índigo / Violeta
    "35": "#16a34a",  # Verde Esmeralda
    "36": "#ea580c",  # Laranja Intenso

    # Grade Adulto Superior (37 a 50)
    "37": "#65a30d",  # Verde Oliva Claro
    "38": "#059669",  # Verde Floresta
    "39": "#0ea5e9",  # Azul Elétrico
    "40": "#3b82f6",  # Azul Cobalto
    "41": "#2563eb",  # Azul Real
    "42": "#8b5cf6",  # Violeta Suave
    "43": "#9333ea",  # Púrpura Profundo
    "44": "#c026d3",  # Orquídea
    "45": "#db2777",  # Rosa Magenta
    "46": "#b91c1c",  # Vermelho Rubi
    "47": "#4f46e5",  # Azul Noturno
    "48": "#334155",  # Cinza Ardósia
    "49": "#475569",  # Grafite
    "50": "#64748b",  # Aço

    # Numeração sequencial 1 a 15
    "1": "#eab308",
    "2": "#f97316",
    "3": "#f43f5e",
    "4": "#ec4899",
    "5": "#16a34a",
    "6": "#06b6d4",
    "7": "#6366f1",
    "8": "#8b5cf6",
    "9": "#3b82f6",
    "10": "#d946ef",
    "11": "#0d9488",
    "12": "#ea580c",
    "13": "#7c3aed",
    "14": "#ca8a04",
    "15": "#059669",
}

# Auto-popula sufixos ('a', 'm', '.5', '_5') para que '36a', '36m', etc. tenham cores perfeitamente mapeadas
for _k in list(STANDARD_SIZE_COLORS.keys()):
    STANDARD_SIZE_COLORS[f"{_k}a"] = STANDARD_SIZE_COLORS[_k]
    STANDARD_SIZE_COLORS[f"{_k}m"] = STANDARD_SIZE_COLORS[_k]
    STANDARD_SIZE_COLORS[f"{_k}.5"] = STANDARD_SIZE_COLORS[_k]
    STANDARD_SIZE_COLORS[f"{_k}_5"] = STANDARD_SIZE_COLORS[_k]


def get_color_for_size(size_val, fallback_index=0) -> str:
    """
    Retorna uma cor hexadecimal exclusiva e distinta para o número / tamanho especificado.
    Regra estrita: Cada número tem sua própria cor única, sem repetições!
    """
    if not size_val:
        return SIZE_COLOR_PALETTE[fallback_index % len(SIZE_COLOR_PALETTE)]

    s = str(size_val).strip()
    if not s or s.lower() in ("none", "null", ""):
        return SIZE_COLOR_PALETTE[fallback_index % len(SIZE_COLOR_PALETTE)]

    s_clean = s.lower().replace(",", ".")

    # 1. Correspondência direta na tabela (ex: '36a', '22', '35m')
    if s_clean in STANDARD_SIZE_COLORS:
        return STANDARD_SIZE_COLORS[s_clean]

    # 2. Busca pelo número base extraído (ex: '323_PalAcb_36a' -> '36', 't36' -> '36')
    digits = re.findall(r"\d+", s_clean)
    if digits:
        for d in reversed(digits):
            if d in STANDARD_SIZE_COLORS:
                return STANDARD_SIZE_COLORS[d]
        try:
            num = int(digits[-1])
            return SIZE_COLOR_PALETTE[num % len(SIZE_COLOR_PALETTE)]
        except ValueError:
            pass

    # 3. Hash determinístico para formatos livres
    h = 0
    for ch in s_clean:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return SIZE_COLOR_PALETTE[h % len(SIZE_COLOR_PALETTE)]


def get_contrast_text_color(hex_color: str) -> str:
    """
    Calcula a luminância perceptual da cor de fundo (ITU-R BT.709)
    e retorna '#ffffff' para fundos escuros ou '#000000' para fundos claros.
    """
    if not hex_color or not isinstance(hex_color, str) or not hex_color.startswith("#"):
        return "#ffffff"

    c = hex_color.lstrip("#")
    if len(c) == 3:
        c = "".join([x * 2 for x in c])
    if len(c) != 6:
        return "#ffffff"

    try:
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        return "#000000" if lum > 145 else "#ffffff"
    except Exception:
        return "#ffffff"


def get_color_emoji(hex_color: str) -> str:
    """Retorna um emoji de quadrado colorido aproximado para uso em tabelas."""
    if not hex_color or not isinstance(hex_color, str):
        return "🟦"

    c = hex_color.lower()
    if any(k in c for k in ("2563eb", "3b82f6", "0284c7", "0ea5e9", "4f46e5", "4338ca")):
        return "🟦"  # Azul
    if any(k in c for k in ("16a34a", "059669", "22c55e", "10b981", "84cc16", "65a30d")):
        return "🟩"  # Verde
    if any(k in c for k in ("ea580c", "f97316", "fb923c")):
        return "🟧"  # Laranja
    if any(k in c for k in ("9333ea", "c026d3", "d946ef", "7c3aed", "8b5cf6", "a855f7")):
        return "🟪"  # Roxo / Magenta
    if any(k in c for k in ("eab308", "facc15", "ca8a04", "d97706")):
        return "🟨"  # Amarelo
    if any(k in c for k in ("e11d48", "db2777", "ec4899", "b91c1c", "f43f5e")):
        return "🟥"  # Vermelho / Rosa
    if any(k in c for k in ("0891b2", "0d9488", "14b8a6", "06b6d4")):
        return "🟦"  # Teal / Ciano

    return "🟦"
