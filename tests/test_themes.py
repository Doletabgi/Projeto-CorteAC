"""Troca real de temas sem perder estado, imagens ou preferências."""
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
import pytest
from config import THEME
from database import DatabaseManager
from ui.themes import CLASSIC, THEMES, ThemeManager
from ui.icons import get_icon

@pytest.fixture
def themed_root():
    root = tk.Tk()
    root.withdraw()
    manager = ThemeManager(root)
    yield root, manager
    root.destroy()
    THEME.update(CLASSIC)

def test_cycle_preserves_controls_values_selection_and_icon_references(themed_root):
    root, manager = themed_root
    entry = tk.Entry(root, bg=CLASSIC["bg_input"], fg=CLASSIC["text_main"])
    entry.insert(0, "Sessão #188")
    tree = ttk.Treeview(root)
    tree.insert("", "end", iid="188", text="Sessão #188")
    tree.selection_set("188")
    calls = []
    image = get_icon(root, "production")
    button = tk.Button(root, image=image, command=lambda: calls.append(1), relief="raised", width=22)
    manager.refresh()
    pixels = set()
    for name in THEMES:
        manager.apply(name)
        assert entry.get() == "Sessão #188"
        assert tree.selection() == ("188",)
        assert button.cget("image") == str(image)
        assert int(button.cget("width")) == 22
        assert entry.cget("bg") == THEME["bg_input"]
        pixels.add(str(root.tk.call(image.name, "data", "-format", "png")))
    assert len(pixels) == 4
    manager.apply("classic")
    assert entry.cget("bg") == CLASSIC["bg_input"]
    assert button.cget("relief") == "raised"
    button.invoke()
    assert calls == [1]

def test_new_controls_in_dark_theme_and_disabled_state(themed_root):
    root, manager = themed_root
    manager.apply("graphite")
    entry = tk.Entry(root, bg="white", fg="black", state="disabled")
    manager.refresh()
    assert entry.cget("state") == "disabled"
    assert entry.cget("bg") == THEME["bg_input"]
    assert entry.cget("fg") == THEME["text_main"]

def test_tools_menu_and_saved_theme_on_restart():
    from ui.main_window import MainWindow
    database = DatabaseManager(":memory:")
    with patch("ui.main_window.DatabaseManager", return_value=database):
        app = MainWindow()
        app.withdraw()
        try:
            assert [app.themes_menu.entrycget(i, "label") for i in range(4)] == [v[0] for v in THEMES.values()]
            app.themes_menu.invoke(2)
            assert app.theme_manager.name == "graphite"
            assert database.get_setting("ui_theme") == "graphite"
        finally:
            app.destroy()
        app = MainWindow()
        app.withdraw()
        try:
            assert app.theme_manager.name == "graphite"
            assert app.theme_var.get() == "graphite"
        finally:
            app.destroy()
            THEME.update(CLASSIC)
