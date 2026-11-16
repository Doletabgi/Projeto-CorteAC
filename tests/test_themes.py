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


def test_new_window_does_not_repaint_existing_controls_or_icons(themed_root):
    root, manager = themed_root
    manager.apply("graphite")
    root.geometry("800x500+5000+5000")
    existing = tk.Frame(root, bg=CLASSIC["bg_surface"])
    existing.pack(fill="both", expand=True)
    ttk.Treeview(existing).pack()
    hook_calls = []
    existing.apply_theme_layout = lambda name: hook_calls.append(name)
    root.deiconify()
    root.update()
    hook_calls.clear()

    with patch.object(existing, "configure", wraps=existing.configure) as configure, \
         patch("ui.icons.refresh_icons") as icons, \
         patch.object(manager.style, "configure", wraps=manager.style.configure) as styles:
        dialog = tk.Toplevel(root)
        entry = tk.Entry(dialog, bg="white", fg="black")
        entry.pack()
        ttk.Treeview(dialog).pack()
        root.update()
        assert entry.cget("bg") == THEME["bg_input"]
        assert entry.cget("fg") == THEME["text_main"]
        configure.assert_not_called()
        icons.assert_not_called()
        assert hook_calls == []
        styles.assert_not_called()
        # Reabrir a mesma janela não deve reaplicar tema nem agendar refresh.
        for _ in range(3):
            dialog.withdraw()
            root.update()
            dialog.deiconify()
            root.update()
        assert manager.pending is None
        configure.assert_not_called()
        icons.assert_not_called()
        assert hook_calls == []
        dialog.destroy()


def test_idle_after_opening_layout_stops_redrawing(themed_root):
    from ui.layout_editor_view import LayoutEditorView
    root, manager = themed_root
    root.geometry("1100x750+5000+5000")
    view = LayoutEditorView(root, load_sample=False)
    view.pack(fill="both", expand=True)
    root.deiconify()
    root.update()
    with patch.object(view, "redraw", wraps=view.redraw) as redraw, \
         patch.object(view.canvas, "configure", wraps=view.canvas.configure) as configure, \
         patch("ui.icons.refresh_icons") as icons:
        dialog = tk.Toplevel(root)
        tk.Label(dialog, text="Janela de teste").pack()
        root.update()
        root.after(250, root.quit)
        root.mainloop()
        redraw.assert_not_called()
        configure.assert_not_called()
        icons.assert_not_called()
        assert manager.pending is None
        dialog.destroy()

def test_tools_menu_and_saved_theme_on_restart():
    from ui.main_window import MainWindow
    database = DatabaseManager(":memory:")
    with patch("ui.main_window.DatabaseManager", return_value=database):
        app = MainWindow()
        app.withdraw()
        try:
            assert [app.themes_menu.entrycget(i, "label") for i in range(len(THEMES))] == [v[0] for v in THEMES.values()]
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


def test_layouts_reuse_widgets_and_restore_classic(themed_root):
    from ui.session_view import SessionView
    root, manager = themed_root
    root.theme_manager = manager
    root.geometry("1600x950")
    database = DatabaseManager(":memory:")
    view = SessionView(root, db=database, session_data={"id": 188, "name": "Sessão #188", "status": "Stand by", "shapes": []})
    view.pack(fill="both", expand=True)
    view.entry_sname.delete(0, 'end')
    view.entry_sname.insert(0, 'Nome ainda não salvo')
    original = view.cb_params
    value = original.get()
    checked = view.var_refile_auto.get()
    for name in ("modern", "technical", "compact", "classic", "technical", "blue", "compact", "classic"):
        manager.apply(name)
        root.update_idletasks()
        assert view.entry_sname.get() == "Nome ainda não salvo"
        assert view.cb_params is original
        assert original.get() == value
        assert view.var_refile_auto.get() == checked
        assert view.btn_action_nest.cget('state') == 'normal'
        if name == 'technical':
            assert view.box_advanced.pack_info()['in'] == view.theme_layout.inspector
        elif name in ('modern', 'compact'):
            assert view.box_advanced.winfo_manager() == 'grid'
        else:
            assert view.box_advanced.winfo_manager() == 'pack'
            assert view.material_controls.pack_info()['in'] == view.grid_params
    assert view.mode_widget.winfo_manager() == 'pack'
    assert view.macro_panel.winfo_manager() == 'pack'


@pytest.mark.parametrize('name', ['modern', 'technical', 'compact'])
def test_saved_layout_and_navigation_on_startup(name):
    from ui.main_window import MainWindow
    database = DatabaseManager(":memory:")
    database.set_setting('ui_theme', name)
    with patch('ui.main_window.DatabaseManager', return_value=database):
        app = MainWindow()
        app.withdraw()
        try:
            assert app.theme_manager.name == name
            assert str(app.main_paned.cget('orient')) == ('vertical' if name == 'compact' else 'horizontal')
            app.change_theme('classic')
            assert str(app.main_paned.cget('orient')) == 'horizontal'
        finally:
            app.destroy()
            THEME.update(CLASSIC)


def test_preview_draws_real_pieces_without_changing_session(themed_root):
    import copy
    from ui.session_view import SessionView
    root, manager = themed_root
    data = {'id': 188, 'name': 'Teste', 'shapes': [], 'placed_pieces': [
        {'x': 10, 'y': 15, 'rotation': 30, 'color': '#ff0000', 'contour': [
            {'x': 0, 'y': 0}, {'x': 100, 'y': 0}, {'x': 0, 'y': 100}]}]}
    view = SessionView(root, session_data=data, db=DatabaseManager(':memory:'))
    snapshot = copy.deepcopy(view.session_data)
    manager.apply('technical')
    canvas = view.theme_layout.preview
    view.draw_mini_layout_preview(canvas)
    polygons = [i for i in canvas.find_all() if canvas.type(i) == 'polygon']
    assert len(polygons) == 1
    assert canvas.itemcget(polygons[0], 'fill') == '#ff0000'
    assert view.session_data == snapshot


@pytest.mark.parametrize('name', ['modern', 'compact'])
def test_short_window_can_scroll_to_actions(themed_root, name):
    from ui.session_view import SessionView
    root, manager = themed_root
    root.geometry('1000x580+50+50')
    view = SessionView(root, db=DatabaseManager(':memory:'),
                       session_data={'id': 188, 'name': 'Teste', 'shapes': []})
    view.pack(fill='both', expand=True)
    root.deiconify()
    manager.apply(name)
    root.update()
    layout = view.theme_layout
    layout.viewport.yview_moveto(1)
    root.update()
    assert view.btn_action_nest.winfo_ismapped()
    assert view.btn_action_nest.winfo_rooty() + view.btn_action_nest.winfo_height() <= root.winfo_rooty() + root.winfo_height()
