"""Temas da interface: preserva widgets, geometria e estado das sessões."""
import tkinter as tk
from tkinter import ttk
from config import THEME

CLASSIC = dict(THEME)
THEMES = {
    "classic": ("Clássico", {}),
    "blue": ("Azul claro", dict(bg_main="#f3f5f8", bg_surface="#f3f5f8", bg_card="#f3f5f8", bg_input="#ffffff", bg_workspace="#dce3ed", canvas_bg="#dce3ed", bg_hover="#e2eafa", border="#cbd5e1", border_dark="#94a3b8", border_light="#ffffff", text_main="#172033", text_muted="#526176", title_bar_bg="#203b65", select_bg="#2563eb", accent_blue="#2563eb")),
    "graphite": ("Grafite", dict(bg_main="#20262e", bg_surface="#282f39", bg_card="#282f39", bg_input="#343d49", bg_workspace="#1b2129", canvas_bg="#1b2129", bg_hover="#3c4857", border="#495462", border_dark="#495462", border_light="#495462", text_main="#e6ebf2", text_muted="#aab5c2", title_bar_bg="#141b23", select_bg="#008f85", accent_blue="#18b6a4", accent_green="#8bd450")),
    "petroleum": ("Verde-petróleo", dict(bg_main="#f5f5f1", bg_surface="#f5f5f1", bg_card="#f5f5f1", bg_input="#fefefc", bg_workspace="#dce5e0", canvas_bg="#dce5e0", bg_hover="#e6ece8", border="#d2d8d4", border_dark="#94aaa3", border_light="#fefefc", text_main="#263330", text_muted="#596b64", title_bar_bg="#20535a", select_bg="#287f78", accent_blue="#287f78")),
}

class ThemeManager:
    def __init__(self, root, name="classic"):
        self.root = root
        self.name = name if name in THEMES else "classic"
        self.pending = None
        self.set_palette()
        root.bind_all("<Map>", self.on_map, add="+")

    def set_palette(self):
        THEME.update(CLASSIC)
        THEME.update(THEMES[self.name][1])
        self.root._icon_theme = self.name

    def on_map(self, event):
        if self.pending is None:
            self.pending = self.root.after_idle(self.refresh)

    def apply(self, name):
        if name not in THEMES:
            raise ValueError(name)
        # Capture the previous palette before updating the shared dictionary.
        old = dict(THEME)
        self.name = name
        self.set_palette()
        self.refresh(old)

    def refresh(self, old=None):
        self.pending = None
        old = old or dict(THEME)
        palette = dict(THEME)
        def visit(widget):
            try:
                options = widget.keys()
                changes = {}
                for key in ("background", "foreground", "activebackground", "activeforeground", "selectbackground", "selectforeground", "selectcolor", "insertbackground", "disabledforeground", "disabledbackground", "highlightbackground"):
                    if key in options:
                        saved = getattr(widget, "_theme_colors", {})
                        if key not in saved:
                            value = str(widget.cget(key)).lower()
                            if value and not value.startswith("#"):
                                try:
                                    value = "#%02x%02x%02x" % tuple(c // 257 for c in widget.winfo_rgb(value))
                                except tk.TclError:
                                    pass
                            priorities = (["text_main", "text_muted", "accent_green", "title_bar_fg", "select_fg"] if "foreground" in key or key == "insertbackground" else ["bg_input", "title_bar_bg", "bg_surface", "bg_workspace", "bg_hover", "border", "border_dark", "border_light", "select_bg"])
                            role = next((k for k in priorities if str(old.get(k, "")).lower() == value), None)
                            if role is None:
                                role = next((k for k in priorities if str(CLASSIC.get(k, "")).lower() == value), None)
                            if role is None and value in ("#d9d9d9", "#d4d0c8"):
                                role = "bg_surface"
                            if role is None and value in ("#006400", "green"):
                                role = "accent_green"
                            saved[key] = (role, widget.cget(key))
                            widget._theme_colors = saved
                        role, original = saved[key]
                        if role:
                            changes[key] = palette[role]
                if "relief" in options:
                    original = getattr(widget, "_theme_relief", None)
                    if original is None:
                        widget._theme_relief = original = widget.cget("relief")
                    changes["relief"] = original if self.name == "classic" else "flat"
                if getattr(widget, "_theme_primary", False):
                    changes.update(background=palette["bg_surface"] if self.name == "classic" else palette["select_bg"], foreground=palette["text_main"] if self.name == "classic" else palette["select_fg"])
                if changes:
                    widget.configure(**changes)
                if isinstance(widget, ttk.Treeview):
                    style_name = widget.cget("style") or "Treeview"
                    self.style.configure(style_name, background=palette["bg_input"], fieldbackground=palette["bg_input"], foreground=palette["text_main"])
                    self.style.map(style_name, background=[("selected",palette["select_bg"])], foreground=[("selected",palette["select_fg"])])
                for child in widget.winfo_children():
                    visit(child)
            except tk.TclError:
                pass
        self.style = ttk.Style(self.root)
        if self.style.theme_use() != "clam":
            self.style.theme_use("clam")
        self.style.configure(".", background=palette["bg_surface"], foreground=palette["text_main"], bordercolor=palette["border"], lightcolor=palette["border_light"], darkcolor=palette["border_dark"], troughcolor=palette["bg_main"], selectbackground=palette["select_bg"], selectforeground=palette["select_fg"])
        for name in ("TEntry", "TCombobox", "TSpinbox"):
            self.style.configure(name, fieldbackground=palette["bg_input"], foreground=palette["text_main"], insertcolor=palette["text_main"], arrowcolor=palette["text_main"])
            self.style.map(name, fieldbackground=[("readonly",palette["bg_input"]),("disabled",palette["bg_surface"])], foreground=[("disabled",palette["text_muted"]),("readonly",palette["text_main"])])
        for name in ("TNotebook", "WinClassic.TNotebook"):
            self.style.configure(name, background=palette["bg_surface"])
            self.style.configure(name+".Tab", background=palette["bg_card"], foreground=palette["text_main"])
            self.style.map(name+".Tab", background=[("selected",palette["bg_surface"])], foreground=[("selected",palette["accent_blue"])])
        self.style.configure("Treeview.Heading", background=palette["bg_surface"], foreground=palette["text_main"])
        visit(self.root)
        from ui.icons import refresh_icons
        refresh_icons(self.root)
