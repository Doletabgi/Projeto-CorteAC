#!/usr/bin/env python3
"""Gera toda a família de ícones: python3 tools/generate_modern_icons.py."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ui.icon_art import ICON_NAMES, render_icon
from ui.icons import LEGACY_ICONS


def generate_all_icons(assets_dir):
    assets_dir = Path(assets_dir)
    icons_dir = assets_dir / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)
    for name in ICON_NAMES:
        render_icon(name, 96).save(icons_dir / f"{name}.png")
    # Caminhos usados pelas árvores, versões anteriores e atalhos.
    for alias, name in LEGACY_ICONS.items():
        is_layout = (alias.startswith("btn_") and alias not in ("btn_prod", "btn_moldes", "btn_mat")) or alias == "layout_icon"
        folder = assets_dir / "layout" if is_layout else assets_dir
        folder.mkdir(parents=True, exist_ok=True)
        render_icon(name, 20 if is_layout or alias.startswith("btn_") else 18).save(folder / f"{alias}.png")
    for size in (16, 32):
        render_icon("layout", size).save(assets_dir / "layout" / f"layout_icon_{size}.png")
    for size in (16, 24, 32, 48, 64, 128):
        render_icon("app", size).save(assets_dir / f"app_icon_{size}.png")
    app = render_icon("app", 256)
    app.save(assets_dir / "app_icon.png")
    app.save(assets_dir / "app_icon.ico", sizes=[(s,s) for s in (16,24,32,48,64,128,256)])


if __name__ == "__main__":
    generate_all_icons(ROOT / "assets")
    print(f"{len(ICON_NAMES)} ícones gerados em assets/icons e caminhos compatíveis.")
