"""Fluxos do catálogo visual usando um banco temporário de verdade."""
import copy
import time
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from cad.shape_library import AdditionResult
from database import DatabaseManager
from tests.test_shape_library import library_db
from ui.main_window import MainWindow
from ui.session_view import SessionView
from ui.shape_library_view import ShapeLibraryView


@pytest.fixture
def view(library_db):
    db, ids, sid = library_db
    root = tk.Tk()
    root.geometry('1280x800+40+40')
    window = ShapeLibraryView(root, db)
    window.pack(fill='both', expand=True)
    window.set_session_context(db.get_catalog_sessions(), sid)
    root.update()
    yield window, db, ids, sid
    window.destroy()
    root.destroy()


def wait_for_addition(view):
    deadline = time.monotonic()+4
    while view._adding and time.monotonic() < deadline:
        view.update()
        time.sleep(.01)
    assert not view._adding


def test_library_loads_global_catalog_and_defaults_to_active_session(view):
    window, db, ids, sid = view
    assert len(window.shapes_list) == len(db.get_all_shapes())
    active = db.get_catalog_sessions()[-1]['id']
    window.set_session_context(db.get_catalog_sessions(), active)
    assert window.destination_id == active
    assert str(active) in window.active_badge.cget('text')
    assert window.cards_canvas.find_all()


def test_filters_keep_selection_and_edited_pairs(view):
    window, db, ids, sid = view
    key = str(ids[0])
    window.toggle_shape(key)
    window._pair_vars[key].set('27')
    window.query.set('outro')
    window.apply_filters()
    assert [shape['id'] for shape in window.filtered_shapes] == [ids[4]]
    assert window.selected_pairs[key] == '27'
    window.clear_filters()
    assert key in window.selected_pairs
    assert window.selected_pairs[key] == '27'


def test_select_all_uses_filtered_results_only_and_preserves_prior_quantities(view):
    window, db, ids, sid = view
    window.toggle_shape(ids[4])
    window.query.set('gaspea 323')
    window.apply_filters()
    window.select_all_var.set(True)
    window.toggle_all_visible()
    assert set(window.selected_pairs) == {str(ids[0]), str(ids[1]), str(ids[4])}
    window.default_pairs.set('30')
    window.select_all_var.set(True)
    window.toggle_all_visible()
    assert all(value == '12' for value in window.selected_pairs.values())


def test_invalid_quantity_does_not_write_and_selection_remains(view):
    window, db, ids, sid = view
    window.toggle_shape(ids[0])
    window._pair_vars[str(ids[0])].set('0')
    window.add_to_session()
    assert not window._adding
    assert 'entre 1 e 9999' in window.status.get()
    assert db.get_session_shapes(sid) == []
    assert str(ids[0]) in window.selected_pairs


def test_add_persists_pairs_does_not_duplicate_and_updates_callback(view):
    window, db, ids, sid = view
    callback = MagicMock()
    window.on_session_updated_cb = callback
    window.toggle_shape(ids[0])
    window.toggle_shape(ids[1])
    window.default_pairs.set('24')
    window.apply_pairs()
    window.add_to_session()
    assert window.add_button.cget('state') == 'disabled'
    window.add_to_session()  # Proteção contra duplo clique.
    wait_for_addition(window)
    saved = db.get_session_shapes(sid)
    assert {shape['id'] for shape in saved} == set(ids[:2])
    assert all(shape['pairs'] == 24 for shape in saved)
    callback.assert_called_once()
    assert callback.call_args.args[0] == sid
    assert str(ids[0]) in window.existing_ids
    assert window.add_button.cget('state') == 'disabled'
    assert '2 molde(s) adicionado(s)' in window.status.get()


def test_destination_choice_is_preserved_and_selection_can_be_reused(view):
    window, db, ids, sid = view
    window.toggle_shape(ids[0])
    window.add_to_session()
    wait_for_addition(window)
    other = next(item['id'] for item in db.get_catalog_sessions() if item['id'] != sid)
    window.select_destination(other)
    assert str(ids[0]) in window.selected_pairs
    assert window.add_button.cget('state') == 'normal'
    window.set_session_context(db.get_catalog_sessions(), sid)
    assert window.destination_id == other
    window.add_to_session()
    wait_for_addition(window)
    assert len(db.get_session_shapes(sid)) == 1
    assert len(db.get_session_shapes(other)) == 1


def test_already_present_shapes_are_identified_and_not_selected(view):
    window, db, ids, sid = view
    shape = db.get_shape(ids[0]);shape.update(pairs=77, sequence=8)
    db.update_session_shapes(sid, [shape])
    window.reload_data()
    window.toggle_shape(ids[0])
    assert str(ids[0]) not in window.selected_pairs
    assert 'já está na sessão' in window.status.get()
    window.select_all_var.set(True)
    window.toggle_all_visible()
    assert str(ids[0]) not in window.selected_pairs
    assert db.get_session_shapes(sid)[0]['pairs'] == 77


def test_corrupt_preview_and_empty_results_are_handled(view):
    window, db, ids, sid = view
    invalid = db.create_shape(name='Sem desenho', contour=[])
    window.reload_data()
    window.toggle_shape(invalid)
    assert str(invalid) not in window.selected_pairs
    assert 'contorno válido' in window.status.get()
    window.query.set('não existe nada com este nome')
    window.apply_filters()
    window.update()
    assert window.filtered_shapes == []
    assert any('Nenhum molde encontrado' in window.cards_canvas.itemcget(item, 'text')
               for item in window.cards_canvas.find_all() if window.cards_canvas.type(item) == 'text')


def test_edit_opens_focused_shape_and_disables_for_hidden_focus(view):
    window, db, ids, sid = view
    callback = MagicMock()
    window.on_edit_shape_cb = callback
    window.toggle_shape(ids[0])
    window.edit_focused()
    callback.assert_called_once_with(ids[0])
    window.query.set('outro')
    window.apply_filters()
    window.edit_focused()
    callback.assert_called_once()
    assert window.edit_button.cget('state') == 'disabled'


def test_small_window_keeps_filters_and_add_button_accessible(view):
    window, db, ids, sid = view
    root = window.master
    root.geometry('780x650')
    root.update()
    assert not window.left_panel.winfo_ismapped()
    assert window.compact_filters.winfo_ismapped()
    assert window.add_button.winfo_ismapped()
    assert window.add_button.winfo_rooty()+window.add_button.winfo_height() < root.winfo_rooty()+root.winfo_height()
    root.geometry('1280x800')
    root.update()
    assert window.left_panel.winfo_ismapped()


def test_large_catalog_only_draws_visible_cards_and_paginates_selection(view):
    window, db, ids, sid = view
    sample = copy.deepcopy(window.shapes_list[0])
    shapes = [dict(sample, id=10000+index, name=f'Molde {index}') for index in range(2000)]
    window.shapes_list = shapes
    window.shapes_by_id = {str(shape['id']): shape for shape in shapes}
    window._valid_ids = set(window.shapes_by_id)
    window.apply_filters()
    window.update()
    assert len(window.cards_canvas.find_all()) < 1500
    window.select_all_var.set(True)
    window.toggle_all_visible()
    assert len(window.selected_pairs) == 2000
    assert len(window._pair_vars) == 12
    assert window.page_next.cget('state') == 'normal'
    window._change_page(1)
    assert len(window._pair_vars) == 12
    assert '13–24' in window.page_label.cget('text')


def test_deleted_destination_and_database_errors_keep_selection(view):
    window, db, ids, sid = view
    window.toggle_shape(ids[0])
    db.delete_session(sid)
    window.add_to_session()
    wait_for_addition(window)
    assert 'não existe mais' in window.status.get()
    assert str(ids[0]) in window.selected_pairs
    with patch.object(db, 'get_all_shapes', side_effect=RuntimeError('offline')):
        window.reload_data()
    assert 'Não foi possível carregar' in window.status.get()
    assert window.add_button.cget('state') == 'disabled'


def test_empty_database_and_no_session_have_clear_disabled_state(view):
    window, db, ids, sid = view
    for session in db.get_catalog_sessions():
        db.delete_session(session['id'])
    with db.get_connection() as conn:
        conn.cursor().execute('DELETE FROM shapes')
    window.reload_data()
    window.update()
    assert not window.filtered_shapes
    assert window.destination_id is None
    assert str(window.session_combo.cget('state')) == 'disabled'
    assert window.add_button.cget('state') == 'disabled'


def test_main_window_sync_updates_only_target_session():
    fake = object.__new__(MainWindow)
    source = {'id': 1, 'shapes': [{'id': 100}]}
    target = {'id': 2, 'shapes': []}
    fake.sessions = [source, target]
    fake.current_session = source
    fake.open_sessions = {1: MagicMock(session_data=source), 2: MagicMock(session_data=target)}
    fake.layout_editor_view = MagicMock(session_id=1)
    fake.lbl_status_msg = MagicMock()
    result = AdditionResult([{'id': 99, 'pairs': 12}], 1, 0)
    MainWindow.on_catalog_session_updated(fake, 2, result)
    assert source['shapes'] == [{'id': 100}]
    assert target['shapes'] == result.shapes
    fake.open_sessions[1].set_shapes_data.assert_not_called()
    fake.open_sessions[2].set_shapes_data.assert_called_once()
    fake.layout_editor_view.set_session_shapes.assert_not_called()


def test_session_add_button_routes_to_catalog_for_its_own_session():
    fake = object.__new__(SessionView)
    fake.on_open_catalog_cb = MagicMock()
    fake.session_data = {'id': 71}
    SessionView.on_add_shape_click(fake)
    fake.on_open_catalog_cb.assert_called_once_with(71)


def test_main_window_catalog_add_updates_session_view_and_survives_reopen(library_db):
    db, ids, sid = library_db
    with patch('ui.main_window.DatabaseManager', return_value=db), patch('ui.main_window.ShapeBackupScheduler'):
        app = MainWindow()
        app.withdraw()
        try:
            app.show_shape_catalog()
            catalog = app.shape_catalog_view
            active_id = app.current_session['id']
            assert catalog.destination_id == active_id
            catalog.toggle_shape(ids[0])
            catalog.default_pairs.set('18')
            catalog.apply_pairs()
            catalog.add_to_session()
            wait_for_addition(catalog)
            assert '1 molde(s) adicionado(s)' in catalog.status.get()
            assert app.current_session['shapes'][0]['pairs'] == 18
            assert app.open_sessions[active_id].shapes_list[0]['id'] == ids[0]
            app.show_shape_catalog()
            assert str(ids[0]) in catalog.existing_ids
            assert db.get_session_shapes(active_id)[0]['pairs'] == 18
            app.open_sessions[active_id].on_add_shape_click()
            assert app.active_child is catalog
            assert catalog.destination_id == active_id
        finally:
            app.destroy()
