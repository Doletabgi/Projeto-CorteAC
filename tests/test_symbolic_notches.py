import copy
import math
import tkinter as tk
from types import SimpleNamespace

import pytest

from cad.symbolic_notches import SYMBOL_TYPES, insert_symbol, symbol_pattern
from cad.geometry import polygon_area
from cad.die_parser import generate_die_content, parse_die_file


SMALL, LARGE, DOUBLE, SIZE = SYMBOL_TYPES
RECT = [{"x": 0., "y": 0.}, {"x": 100., "y": 0.},
        {"x": 100., "y": 50.}, {"x": 0., "y": 50.}]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("edge,click", [(0, (50, 0)), (1, (100, 25)), (2, (50, 50)), (3, (0, 25))])
def test_notch_is_inward_on_each_edge_and_winding(reverse, edge, click):
    contour = list(reversed(RECT)) if reverse else RECT
    before = copy.deepcopy(contour)
    result, added = insert_symbol(contour, *click, SMALL)
    assert contour == before
    assert len(result) == 7
    assert len(added) == 3
    assert polygon_area(result) == pytest.approx(polygon_area(contour)-2.25)
    assert all(0 <= p['x'] <= 100 and 0 <= p['y'] <= 50 for p in added)


def test_duplicate_closing_point_and_double_notch():
    result, added = insert_symbol(RECT+[RECT[0].copy()], 50, 0, DOUBLE)
    assert result[0] == result[-1]
    assert len(added) == 6
    assert polygon_area(result) == pytest.approx(4995.5)


def test_size_rules_use_last_digit_and_reject_ambiguous_sizes():
    assert symbol_pattern(SIZE, '40') == [(7, 2), (7, 2)]
    assert symbol_pattern(SIZE, '41') == [(4.5, 1)]
    assert symbol_pattern(SIZE, '45') == [(7, 2)]
    assert symbol_pattern(SIZE, '49') == [(7, 2)] + [(4.5, 1)]*4
    for size in ('41.5', '41a', '', None):
        with pytest.raises(ValueError):
            symbol_pattern(SIZE, size)


@pytest.mark.parametrize("click", [(0, 0), (50, 25), (500, 0), (math.nan, 0)])
def test_invalid_placement_is_rejected_without_mutating(click):
    original = copy.deepcopy(RECT)
    with pytest.raises(ValueError):
        insert_symbol(RECT, *click, SMALL)
    assert RECT == original


def test_thin_piece_rejects_cut_through_opposite_edge():
    thin = [{"x": 0, "y": 0}, {"x": 100, "y": 0},
            {"x": 100, "y": .5}, {"x": 0, "y": .5}]
    with pytest.raises(ValueError, match="cruzaria"):
        insert_symbol(thin, 50, 0, SMALL)


def test_die_roundtrip_preserves_notch(tmp_path):
    contour, _ = insert_symbol(RECT, 50, 0, SMALL)
    path = tmp_path/'notched.die'
    path.write_text(generate_die_content({'name': 'Peca', 'contour': contour}), encoding='latin1')
    parsed = parse_die_file(str(path))
    assert parsed['contour'] == [{"x": p['x'], "y": p['y']} for p in contour]
    assert parsed['holes'] == []  # pique não vira furo de broca


@pytest.fixture
def editor():
    from ui.shape_editor_view import ShapeEditorView
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Display Tk indisponível')
    root.withdraw()
    shape = {'id': 77, 'name': 'Teste', 'size': '41', 'contour': copy.deepcopy(RECT),
             'holes': [], 'stitching': []}
    view = ShapeEditorView(root, shape_data=shape)
    view.pack()
    root.update_idletasks()
    yield view
    root.destroy()


def test_editor_lock_click_dirty_undo_and_escape(editor):
    assert editor.geometry_locked.get()
    assert len(editor.undo_stack) == 0
    editor.set_tool_mode('symbolic')
    sx, sy = editor.world_to_screen(50, 0)
    editor.on_canvas_click(SimpleNamespace(x=sx, y=sy))
    assert len(editor.shape['contour']) == 7
    assert editor.open_shapes[0]['is_dirty']
    assert editor.tool_mode == 'symbolic'
    assert editor.geometry_locked.get()  # a ferramenta não libera o arraste de vértices
    assert len(editor.undo_stack) == 1
    editor.undo_or_revert()
    assert editor.shape['contour'] == RECT
    assert editor.on_escape_key() == 'break'
    assert editor.tool_mode == 'select'


def test_failed_editor_click_creates_no_undo(editor):
    editor.geometry_locked.set(False)
    assert not editor.add_symbolic_at(0, 0)
    assert editor.shape['contour'] == RECT
    assert not editor.undo_stack


def test_database_and_package_keep_manual_symbols_over_old_library(tmp_path):
    from database import DatabaseManager
    from cad.project_packager import _normalize_shape, _resolve_die
    db = DatabaseManager(db_path=str(tmp_path/'symbols.db'))
    contour, _ = insert_symbol(RECT, 50, 0, SMALL)
    shape_id = db.create_shape(name='Simbolica', contour=contour, size='41')
    saved = db.get_shape(shape_id)
    assert saved['contour'] == contour
    original = tmp_path/'old.die'
    original.write_text(generate_die_content({'name': 'Simbolica', 'contour': RECT}), encoding='latin1')
    saved['source_path'] = str(original)
    asset, missing = _resolve_die('Simbolica', 'Simbolica.die', _normalize_shape(saved, 'Simbolica'), None, set())
    assert missing is None
    assert asset.source == 'db'
    new = tmp_path/'new.die'
    new.write_bytes(asset.data)
    assert len(parse_die_file(str(new))['contour']) == 7
    assert len(parse_die_file(str(original))['contour']) == 4


def test_dialog_accept_and_cancel(editor):
    from ui.symbolic_dialog import SymbolicDialog
    def accept():
        dialog = next(w for w in editor.winfo_children() if isinstance(w, SymbolicDialog))
        dialog.kind.set(DOUBLE)
        dialog._preview()
        dialog._accept()
    editor.after(10, accept)
    editor.choose_symbolic()
    assert editor.geometry_locked.get()  # escolher simbólica funciona com a trava ativa
    assert editor.symbolic_kind == DOUBLE
    assert editor.tool_mode == 'symbolic'
    editor.set_tool_mode('select')
    def cancel():
        next(w for w in editor.winfo_children() if isinstance(w, SymbolicDialog)).destroy()
    editor.after(10, cancel)
    editor.choose_symbolic()
    assert editor.tool_mode == 'select'


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("closed", [False, True])
@pytest.mark.parametrize("kind", [SMALL, DOUBLE, SIZE])
def test_dense_contour_accepts_notch_across_several_segments(reverse, closed, kind):
    dense = ([{"x": float(x), "y": 0., "original": x} for x in range(101)] +
             [{"x": 100., "y": 50.}, {"x": 0., "y": 50.}])
    if reverse:
        dense.reverse()
    if closed:
        dense.append(dense[0].copy())
    original = copy.deepcopy(dense)
    result, added = insert_symbol(dense, 50, 0, kind, size='49')
    expected_area = 5000-sum(w*d/2 for w, d in symbol_pattern(kind, '49'))
    assert polygon_area(result) == pytest.approx(expected_area)
    assert dense == original
    assert len(added) == 3*len(symbol_pattern(kind, '49'))
    assert any(p.get('original') == 10 for p in result)
    assert (result[0] == result[-1]) == closed


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("angle", [0, 0.7, 2.5])
def test_curved_contour_and_wraparound_keep_valid_notch(reverse, angle):
    contour = [{"x": 50*math.cos(i*2*math.pi/360),
                "y": 50*math.sin(i*2*math.pi/360)} for i in range(360)]
    if reverse:
        contour.reverse()
    result, added = insert_symbol(contour, 50*math.cos(angle), 50*math.sin(angle), DOUBLE)
    assert polygon_area(result) < polygon_area(contour)
    assert len(added) == 6
    assert all(math.hypot(p['x'], p['y']) <= 50+1e-8 for p in added)
    assert all(math.dist((a['x'], a['y']), (b['x'], b['y'])) > 1e-8
               for a, b in zip(result, result[1:]+result[:1]))


def test_toolbar_click_on_dense_piece_and_save_with_lock(editor, monkeypatch):
    import ui.shape_editor_view as module
    dense = ([{"x": float(x), "y": 0.} for x in range(101)] +
             [{"x": 100., "y": 50.}, {"x": 0., "y": 50.}])
    editor.shape['contour'] = copy.deepcopy(dense)
    editor.original_shape = copy.deepcopy(editor.shape)
    saved = []
    editor.on_save_cb = lambda shape: saved.append(copy.deepcopy(shape))
    monkeypatch.setattr(module, 'SymbolicDialog', lambda *a, **kw: SimpleNamespace(result=SMALL))
    monkeypatch.setattr(module.messagebox, 'showinfo', lambda *a, **kw: None)
    assert editor.geometry_locked.get()
    editor.btn_tool_symbolic.invoke()
    sx, sy = editor.world_to_screen(50, 0)
    editor.on_canvas_click(SimpleNamespace(x=sx, y=sy))
    assert editor.open_shapes[0]['is_dirty']
    assert editor.geometry_locked.get()
    assert sum(bool(p.get('symbolic_notch')) for p in editor.shape['contour']) == 3
    assert polygon_area(editor.shape['contour']) == pytest.approx(4997.75)
    editor.save_changes()
    assert saved[0]['contour'] == editor.shape['contour']
    assert not editor.open_shapes[0]['is_dirty']
