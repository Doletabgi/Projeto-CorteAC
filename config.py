"""
CorteAC (Python Edition)
Configuration & Machine Presets
"""

import sys
import os
import shutil
from pathlib import Path

# Paths: No executável standalone PyInstaller, BASE_DIR é o diretório do executável
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR

DATABASE_PATH = BASE_DIR / "jobmanager.db"

# Se o banco persistente no diretório do executável não existir ou estiver vazio (0 bytes),
# inicializa copiando o banco empacotado para garantir que os dados persistam permanentemente
if getattr(sys, "frozen", False):
    bundled_db = BUNDLE_DIR / "jobmanager.db"
    if (not DATABASE_PATH.exists() or DATABASE_PATH.stat().st_size == 0) and bundled_db.exists() and bundled_db.stat().st_size > 0:
        try:
            shutil.copy2(bundled_db, DATABASE_PATH)
        except Exception:
            pass

EXPORTS_DIR = BASE_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

from cad.semver import SemVer

# Application Metadata
APP_NAME = "CorteAC"
APP_VERSION = "1.5.0"

# UI Classic Windows XP Theme Palette (Amostrado exatamente dos prints do usuário)
THEME = {
    "bg_main": "#ece9d8",          # Cinza/bege 3D clássico do Windows XP
    "bg_surface": "#ece9d8",       # Fundo de formulários e caixas
    "bg_card": "#ece9d8",          # Fundo de abas e painéis
    "bg_workspace": "#808080",     # Fundo MDI do desktop (#808080 exato do print)
    "bg_input": "#ffffff",         # Fundo branco puro de inputs, tabelas e árvores
    "bg_hover": "#d8d4c0",         # Hover em controles 3D
    "border": "#aca899",           # Borda de sombra 3D (cinza médio do WinXP)
    "border_dark": "#716f64",      # Borda externa escura
    "border_light": "#ffffff",     # Borda de luz 3D (branco)
    "text_main": "#000000",        # Texto preto clássico
    "text_muted": "#404040",       # Texto secundário/cinza
    "title_bar_bg": "#0a246a",     # Azul marinho clássico de títulos de janela ativa
    "title_bar_fg": "#ffffff",     # Texto branco da barra de título
    "title_inactive_bg": "#808080", # Título de janela inativa
    "select_bg": "#0a246a",        # Fundo azul de seleção
    "select_fg": "#ffffff",        # Texto branco de seleção
    "preview_bg": "#ffc9b1",       # Preenchimento salmão autêntico do molde CAD (conforme media_1792070997258.jpg)
    "preview_border": "#c2410c",   # Borda de contorno do preview
    "accent_cyan": "#008080",      # Cyan clássico / Teal
    "accent_blue": "#0a246a",      # Azul clássico
    "accent_green": "#008000",     # Verde clássico
    "accent_rose": "#c00000",      # Vermelho clássico
    "accent_amber": "#b45309",     # Âmbar clássico
    "canvas_bg": "#808080",        # Fundo neutro do espaço de trabalho CAD
    "canvas_bed": "#f5f3ee",       # Superfície da mesa de corte (chapa/couro)
    "canvas_grid": "#b8b4aa",      # Linhas da grade milimétrica
}

# Machine Specifications (ATOM FlashCut Flex Series)
ATOM_MACHINE = {
    "model": "ATOM FlashCut Flex 3020",
    "max_width_mm": 3050,
    "max_height_mm": 2050,
    "blade_speed_mm_s": 650.0,      # Velocidade nominal de corte da lâmina oscilante
    "rapid_speed_mm_s": 1200.0,     # Deslocamento rápido sem corte (G00)
    "punch_delay_s": 0.12,          # Tempo por furação/picote
    "blade_frequency_rpm": 12000,   # Rotação da lâmina pneumática/elétrica
}

# Material Presets autênticos conforme media_1792065351450.jpg
AUTHENTIC_MATERIALS = [
    {"id": "0", "name": "0 - Chapa Padrão", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.0, "layers": 2},
    {"id": "0001", "name": "0001 - Couro Vaqueta", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.4, "layers": 2},
    {"id": "1000", "name": "1000 - Sintético Liso", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.0, "layers": 2},
    {"id": "10000", "name": "10000 - Tecido Dublado", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "114971", "name": "114971 - Tecido Forro", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 0.8, "layers": 2},
    {"id": "114998", "name": "114998 - Camurça Bovina", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115001", "name": "115001 - Raspa Natural", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.6, "layers": 2},
    {"id": "115015", "name": "115015 - Sintético PU", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.0, "layers": 2},
    {"id": "115334", "name": "115334 - Nylon Especial", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.0, "layers": 2},
    {"id": "115340", "name": "115340 - Tecido Sarja", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.0, "layers": 2},
    {"id": "115400", "name": "115400 - Tecido Microfibra", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.0, "layers": 2},
    {"id": "115401", "name": "TEC F. NYL. 02 +ESP20/JR - PRETO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115402", "name": "TEC F. NYL. 02 +ESP20/JR - GELO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115403", "name": "TEC F. NYL. 02 +ESP20/JR - GRAFITE", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115406", "name": "TEC F. NYL. 02 +ESP20/JR - MARINHO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115408", "name": "TEC F. NYL. 02 +ESP20/JR - VERMELHO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115411", "name": "TEC F. NYL. 02 +ESP20/JR - ROSA", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115412", "name": "TEC F. NYL. 02 +ESP20/JR - ROSA CLARO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115413", "name": "TEC F.NYL.02+ESP20/JR-PINK", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115415", "name": "TEC F. NYL. 02 +ESP20/JR - ORQUIDEA", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115418", "name": "TEC F. NYL. 02 +ESP20/JR - LARANJA", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115419", "name": "TEC F. NYL. 02 +ESP20/JR - AMARELO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115422", "name": "TEC F.NYL.02+ESP20/JR - CHAMPAGNE", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115423", "name": "TEC F. NYL. 02 +ESP20/JR - CAFE", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115433", "name": "TEC F. NYL. 02 +ESP20/JR - CORAL", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115434", "name": "TEC F. NYL. 02 +ESP20/JR - PINK NEW", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115436", "name": "TEC F. NYL. 02 +ESP20/JR - AZUL ROYAL", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115437", "name": "TEC F.NYL.02+ESP20/JR-VERMELHO VIVO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115438", "name": "TEC F.NYL.02+ESP20/JR LARANJA ESCURO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115441", "name": "TEC F. NYL. 02 +ESP20/JR - AMARELO CANARIO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115442", "name": "TEC F. NYL. 02 +ESP20/JR - PINK ESCURO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115444", "name": "TEC F. NYL. 02 +ESP20/JR - AZUL INDIGO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115445", "name": "TEC F. NYL. 02 +ESP20/JR - VERDE VIVO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115446", "name": "TEC F. NYL. 02 +ESP20/JR - AZUL NIKE", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115447", "name": "TEC F. NYL. 02 +ESP20/JR - AMARELO VIVO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115448", "name": "TEC F. NYL. 02 +ESP20/JR - VINHO ESCURO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115449", "name": "TEC F. NYL. 02 +ESP20/JR - VERDE 2017", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115800", "name": "TEC LONA ALGODAO LISA - ROSA BB", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.0, "layers": 2},
    {"id": "115805", "name": "TEC LONA ALGODAO LISA - BEGE", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.0, "layers": 2},
    {"id": "115987", "name": "TEC MALHA SUED +ESP20/JR-BCO", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
    {"id": "115988", "name": "TEC MALHA SUED. +ESP20/JR - CINZA", "type": "como placa", "width_mm": 1380.0, "height_mm": 2980.0, "area_m2": 4.1124, "thickness_mm": 1.2, "layers": 2},
]

DEFAULT_MATERIALS = AUTHENTIC_MATERIALS
