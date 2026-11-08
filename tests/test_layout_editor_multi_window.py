import copy
import pytest
import tkinter as tk
from unittest.mock import MagicMock

from ui.layout_editor_view import LayoutEditorView, LayoutSubWindow


@pytest.fixture
def tk_root():
    """Cria uma raiz Tkinter invisível para os testes de interface."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def sample_layouts():
    """Retorna dados de 2 placas (layouts) de uma sessão de corte."""
    contour_rect = [
        {"x": 0.0, "y": 0.0},
        {"x": 100.0, "y": 0.0},
        {"x": 100.0, "y": 80.0},
        {"x": 0.0, "y": 80.0},
    ]
    lay0 = {
        "name": "lay0000",
        "width_mm": 1380.0,
        "height_mm": 2000.0,
        "layers": 4,
        "yield_percent": 75.5,
        "pieces": [
            {"id": "p1", "name": "Biqueira_41", "size": "41", "x": 50.0, "y": 50.0, "rotation": 0.0, "contour": contour_rect},
            {"id": "p2", "name": "Biqueira_41", "size": "41", "x": 200.0, "y": 50.0, "rotation": 0.0, "contour": contour_rect},
        ],
    }
    lay1 = {
        "name": "lay0001",
        "width_mm": 1380.0,
        "height_mm": 1500.0,
        "layers": 2,
        "yield_percent": 42.0,
        "pieces": [
            {"id": "p3", "name": "Contraforte_41", "size": "41", "x": 80.0, "y": 80.0, "rotation": 90.0, "contour": contour_rect},
        ],
    }
    return [lay0, lay1]


def test_cascade_layouts_creates_subwindows(tk_root, sample_layouts):
    """Verifica se cascade_layouts cria subjanelas MDI dispostas em cascata diagonal."""
    editor = LayoutEditorView(tk_root, load_sample=False)
    editor.set_session_layouts(sample_layouts, initial_index=0)
    editor.update_idletasks()

    editor.cascade_layouts()

    assert editor.layout_view_mode == "cascade"
    assert len(editor.sub_windows) == 2
    sw0 = editor.sub_windows[0]
    sw1 = editor.sub_windows[1]
    assert isinstance(sw0, LayoutSubWindow)
    assert isinstance(sw1, LayoutSubWindow)

    # Subjanelas possuem títulos corretos
    assert "lay0000" in sw0.lbl_title.cget("text")
    assert "lay0001" in sw1.lbl_title.cget("text")
    assert "Placa 1 de 2" in sw0.lbl_title.cget("text")
    assert "Placa 2 de 2" in sw1.lbl_title.cget("text")

    # Layout ativo tem destaque na barra de título
    assert sw0.is_active is True
    assert sw1.is_active is False

    # Cascata aplica deslocamento progressivo
    editor.update_idletasks()
    info0 = sw0.place_info()
    info1 = sw1.place_info()
    assert int(info0.get("x", 0)) < int(info1.get("x", 0))
    assert int(info0.get("y", 0)) < int(info1.get("y", 0))


def test_tile_layouts_horizontal_splits_width(tk_root, sample_layouts):
    """Verifica se tile_layouts_horizontal divide a largura disponível entre os layouts."""
    editor = LayoutEditorView(tk_root, load_sample=False)
    editor.set_session_layouts(sample_layouts, initial_index=0)
    editor.update_idletasks()

    editor.tile_layouts_horizontal()

    assert editor.layout_view_mode == "tile_h"
    assert len(editor.sub_windows) == 2

    info0 = editor.sub_windows[0].place_info()
    info1 = editor.sub_windows[1].place_info()

    # Coluna 0 começa em x=0, Coluna 1 começa após x=0
    assert int(info0.get("x", 0)) == 0
    assert int(info1.get("x", 0)) > 0
    assert int(info0.get("y", 0)) == 0
    assert int(info1.get("y", 0)) == 0


def test_tile_layouts_vertical_splits_height(tk_root, sample_layouts):
    """Verifica se tile_layouts_vertical empilha as subjanelas verticalmente."""
    editor = LayoutEditorView(tk_root, load_sample=False)
    editor.set_session_layouts(sample_layouts, initial_index=0)
    editor.update_idletasks()

    editor.tile_layouts_vertical()

    assert editor.layout_view_mode == "tile_v"
    assert len(editor.sub_windows) == 2

    info0 = editor.sub_windows[0].place_info()
    info1 = editor.sub_windows[1].place_info()

    # Linha 0 começa em y=0, Linha 1 começa após y=0
    assert int(info0.get("y", 0)) == 0
    assert int(info1.get("y", 0)) > 0
    assert int(info0.get("x", 0)) == 0
    assert int(info1.get("x", 0)) == 0


def test_subwindow_selection_and_maximize(tk_root, sample_layouts):
    """Verifica seleção de subjanela e retorno ao modo de edição completa com duplo-clique/maximizar."""
    editor = LayoutEditorView(tk_root, load_sample=False)
    editor.set_session_layouts(sample_layouts, initial_index=0)
    editor.cascade_layouts()

    # Clica na Placa 2
    editor._on_subwindow_selected(1)
    assert editor.current_layout_index == 1
    assert editor.sub_windows[1].is_active is True
    assert editor.sub_windows[0].is_active is False
    assert editor.layout_name == "lay0001"

    # Maximiza para edição de tela cheia
    editor.maximize_current_layout(1)
    assert editor.layout_view_mode == "single"
    assert editor.current_layout_index == 1
    assert editor.layout_name == "lay0001"
    # Canvas principal está visível
    assert bool(editor.canvas.winfo_ismapped() or editor.canvas.winfo_manager() == "pack")


def test_window_menu_dynamic_layout_list(tk_root, sample_layouts):
    """Verifica se o menu Janela é populado com as opções de layout e indicação da placa ativa."""
    editor = LayoutEditorView(tk_root, load_sample=False)
    editor.set_session_layouts(sample_layouts, initial_index=1)

    menu = tk.Menu(editor, tearoff=0)
    editor._refresh_window_menu(menu)

    labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1) if menu.type(i) != "separator"]
    assert "Em cascata" in labels
    assert "Lado a lado horizontal" in labels
    assert "Lado a lado vertical" in labels
    assert "Maximizar (Layout Único)" in labels

    # A placa 2 (índice 1) deve conter o checkmark de ativa
    check_item = [lbl for lbl in labels if "lay0001" in lbl]
    assert len(check_item) == 1
    assert "✓" in check_item[0]


def test_main_window_delegation_to_layout_editor():
    """Verifica se MainWindow delega cascade_windows e tile_horizontal para o LayoutEditorView quando ativo."""
    from ui.main_window import MainWindow
    mw = object.__new__(MainWindow)
    mw.open_windows = []

    mock_editor = MagicMock(spec=LayoutEditorView)
    mock_editor.winfo_ismapped.return_value = True
    mock_editor.layouts = [{"name": "lay0000"}, {"name": "lay0001"}]
    mw.layout_editor_view = mock_editor
    mw.open_windows.append(mock_editor)
    mw.active_child = mock_editor

    MainWindow.cascade_windows(mw)
    mock_editor.cascade_layouts.assert_called_once()

    MainWindow.tile_horizontal(mw)
    mock_editor.tile_layouts_horizontal.assert_called_once()

    MainWindow.tile_vertical(mw)
    mock_editor.tile_layouts_vertical.assert_called_once()

