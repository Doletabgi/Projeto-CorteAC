"""Abertura leve e criação/reutilização dos editores nos acessos explícitos."""
from unittest.mock import patch

import pytest

from database import DatabaseManager
from ui.main_window import MainWindow
from config import THEME
from ui.themes import CLASSIC


@pytest.fixture
def app():
    db = DatabaseManager(":memory:")
    with patch("ui.main_window.DatabaseManager", return_value=db), \
         patch("ui.main_window.ShapeBackupScheduler"):
        window = MainWindow()
        window.withdraw()
        yield window
        window.destroy()
        THEME.update(CLASSIC)


def test_startup_does_not_construct_editors_or_read_global_contours():
    db = DatabaseManager(":memory:")
    with patch("ui.main_window.DatabaseManager", return_value=db), \
         patch("ui.main_window.ShapeBackupScheduler"), \
         patch("ui.main_window.OrderView") as orders, \
         patch("ui.main_window.ShapeEditorView") as shapes, \
         patch("ui.main_window.ShapeLibraryView") as catalog, \
         patch("ui.main_window.LayoutEditorView") as layouts, \
         patch("ui.main_window.MaterialCodesView") as materials, \
         patch.object(db, "get_all_shapes", wraps=db.get_all_shapes) as read_shapes:
        window = MainWindow()
        try:
            window.update_idletasks()
            for constructor in (orders, shapes, catalog, layouts, materials, read_shapes):
                constructor.assert_not_called()
            assert window.layout_editor_view is None
            assert window.shape_editor_view is None
            assert window.current_shapes == []
        finally:
            window.destroy()
            THEME.update(CLASSIC)


@pytest.mark.parametrize("method, name, kwargs", [
    ("show_shape_editor", "shape_editor_view", {}),
    ("show_shape_catalog", "shape_catalog_view", {}),
    ("show_order_window", "order_view", {}),
    ("show_material_codes_window", "material_codes_view", {}),
    ("show_layout_editor", "layout_editor_view", {"force": True}),
])
def test_first_access_creates_and_reopening_reuses_view(app, method, name, kwargs):
    getattr(app, method)(**kwargs)
    view = getattr(app, name)
    assert view is not None
    assert app.active_child is view
    app.close_window(view)
    getattr(app, method)(**kwargs)
    assert getattr(app, name) is view
    assert app.active_child is view


def test_background_changes_do_not_create_layout_editor(app):
    app.refresh_materials_everywhere()
    app.on_apply_options(app.app_settings)
    app.update_all_metrics()
    app.handle_ctrl_s(None)
    assert app.layout_editor_view is None
    app.show_layout_editor(force=True)
    assert app.layout_editor_view.placed_pieces == []


def test_shapes_navigation_loads_global_catalog_once_on_demand(app):
    with patch.object(app.db, "get_all_shapes", wraps=app.db.get_all_shapes) as read:
        app.switch_tree_mode("shapes")
        read.assert_called_once()
        app.switch_tree_mode("jobs")
        app.switch_tree_mode("shapes")
        read.assert_called_once()


def test_first_layout_open_uses_latest_session_and_material(app):
    contour = [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 0, "y": 30}]
    piece = {"name": "Atual", "size": "41", "contour": contour,
             "x": 50.0, "y": 50.0, "rotation": 0.0}
    session = {"name": "Sessão atual", "shapes": [], "layers": 4,
               "material": {"width_mm": 1000, "height_mm": 700, "layers": 4},
               "layouts": [{"name": "lay0000", "width_mm": 1000,
                            "height_mm": 700, "layers": 4, "pieces": [piece]}]}
    app.show_layout_editor(session_data=session)
    view = app.layout_editor_view
    assert view.placed_pieces[0]["name"] == "Atual"
    assert view.placed_pieces[0]["contour"] == contour
    assert view.sheet_width == 1000
    assert view.sheet_height == 700
    assert view.material_layers == 4


def test_machine_export_can_create_layout_editor_on_first_access(app):
    app.current_session = {"name": "Exportar", "layers": 2,
                           "layouts": [{"name": "lay0000", "pieces": []}]}
    with patch("ui.main_window.LayoutEditorView.export_session_to_machine") as export:
        app.on_export_session_to_machine()
        export.assert_called_once()
        assert app.layout_editor_view is not None
