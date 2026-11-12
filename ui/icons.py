"""Carregamento compartilhado de ícones, com cache por interpretador Tcl."""
import sys
import io
import tkinter as tk
from pathlib import Path
from PIL import Image

ASSETS_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets"

LEGACY_ICONS = {
    "tlbCut": "cut", "tlbCopy": "copy", "tlbPaste": "paste",
    "tlbDetails": "details", "btn_prod": "production", "mode_job": "production",
    "btn_moldes": "shape", "mode_shp": "shape", "btn_mat": "materials",
    "mode_mat": "materials", "iconJobNodeBase": "production",
    "iconJobJobFolder": "folder", "iconJobOrder": "order", "iconJobSession": "session",
    "iconShpShpBase": "catalog", "iconShpArticle": "shape", "iconShed": "shape",
    "iconMatBase": "materials", "layout_icon": "layout", "tbShowIndex": "number",
    "tbShowPoints": "hole", "btn_outline": "palette", "btn_zoom_fit": "fit",
    "btn_bump_left": "left", "btn_bump_right": "right", "btn_bump_up": "up",
    "btn_bump_down": "down", "btn_trim": "cut", "btn_play": "play",
}
for _name in ("new", "open", "save", "dual", "cut", "copy", "paste", "print",
              "zoom", "add", "move", "grid"):
    LEGACY_ICONS[f"btn_{_name}"] = _name

# Símbolos dos rótulos legados viram imagens reais, independentes de fontes.
GLYPH_ICONS = {
    "📂": "open", "📁": "folder", "🗂": "materials", "💾": "save",
    "✂": "cut", "📄": "new", "📑": "materials", "📋": "details",
    "📐": "shape", "📏": "ruler", "🧩": "layout", "▦": "catalog",
    "📊": "production", "🖨": "print", "📤": "export", "📥": "import",
    "🎨": "palette", "🔍": "zoom", "➕": "add", "➖": "remove",
    "⬆": "up", "⬇": "down", "◀": "left", "▶": "play", "⏹": "stop",
    "🗑": "delete", "✏": "edit", "✎": "edit", "📝": "edit",
    "🔄": "refresh", "↻": "refresh", "⚙": "settings", "⚡": "auto",
    "👤": "user", "📦": "backup", "⏰": "clock", "⏳": "clock",
    "🧹": "clean", "📟": "barcode", "☑": "check", "✅": "check",
    "✓": "check", "✔": "check", "☐": "uncheck", "⬜": "uncheck",
    "❌": "close", "✕": "close", "×": "close", "□": "maximize",
    "🗖": "restore", "🗗": "restore", "❐": "restore", "⛶": "fullscreen", "↖": "select",
    "⭕": "hole", "🔒": "lock", "🔓": "unlock", "👁": "eye",
    "↔": "mirror_x", "↕": "mirror_y", "🎯": "target", "⚠": "warning",
    "💡": "tip", "🖼": "image", "🏢": "company", "🔽": "sort",
    "🔼": "up", "🔢": "number", "🖥": "production", "📚": "materials",
    "🟩": "shape", "🔵": "export", "🟠": "import",
}


def icon_size(widget, size=18):
    """Tk scaling é pixels por ponto; 4/3 corresponde a 100% (96 dpi)."""
    factor = float(widget.tk.call("tk", "scaling")) / (96 / 72)
    return max(12, round(size * max(1.0, factor)))


def get_icon(widget, name, size=18, color=None):
    """Mantém referências vivas no root correto, inclusive com vários Tk()."""
    name = LEGACY_ICONS.get(name, name)
    pixels = icon_size(widget, size)
    root = widget._root()
    cache = getattr(root, "_modern_icon_cache", None)
    if cache is None:
        cache = root._modern_icon_cache = {}
    key = (name, pixels, color)
    if key not in cache:
        path = ASSETS_DIR / "icons" / f"{name}.png"
        with Image.open(path) as source:
            bitmap = source.convert("RGBA").resize((pixels, pixels), Image.Resampling.LANCZOS)
        if color:
            tinted = Image.new('RGBA', bitmap.size, color)
            tinted.putalpha(bitmap.getchannel('A'))
            bitmap = tinted
        buffer = io.BytesIO()
        bitmap.save(buffer, format="PNG")
        cache[key] = tk.PhotoImage(data=buffer.getvalue(), master=root)
    return cache[key]


def split_icon_text(text):
    """Retira apenas um símbolo inicial ou a seta de navegação final."""
    if not isinstance(text, str):
        return None, text
    stripped = text.strip()
    if stripped == "_":
        return "minimize", ""
    if stripped and stripped[0] in GLYPH_ICONS:
        return GLYPH_ICONS[stripped[0]], stripped[1:].lstrip("\ufe0f ")
    if stripped.endswith(" ▶"):
        return "right", stripped[:-2].rstrip()
    return None, text
