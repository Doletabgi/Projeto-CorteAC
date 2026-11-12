"""Trocas de apresentação mantêm os moldes, filtros e quantidades do operador."""
import copy
from types import SimpleNamespace

import pytest

from tests.test_shape_library import library_db
from tests.test_shape_library_view import view, wait_for_addition
from ui.library_presentations import DETAIL_COLUMNS, VIEW_MODES, shape_metrics


def visible_text(window):
    cv = window.cards_canvas
    return [cv.itemcget(item, 'text') for item in cv.find_all() if cv.type(item) == 'text']


@pytest.mark.parametrize('mode', VIEW_MODES)
def test_switch_preserves_filters_selection_pairs_and_destination(view, mode):
    window, db, ids, sid = view
    window.toggle_shape(ids[0])
    window._pair_vars[str(ids[0])].set('27')
    window.query.set('323')
    window.size_filter.set('22a')
    window.apply_filters()
    filtered = [shape['id'] for shape in window.filtered_shapes]
    window.set_view_mode(mode)
    window.update()
    assert window.selected_pairs == {str(ids[0]): '27'}
    assert window.query.get() == '323'
    assert window.size_filter.get() == '22a'
    assert window.destination_id == sid
    assert [shape['id'] for shape in window.filtered_shapes] == filtered
    assert window.cards_canvas.find_all()
    assert db.get_session_shapes(sid) == []


@pytest.mark.parametrize('mode', VIEW_MODES)
def test_click_selects_correct_shape_and_adds_to_session(view, mode):
    window, db, ids, sid = view
    window.query.set('gaspea 323 22a')
    window.apply_filters()
    window.set_view_mode(mode)
    window.update()
    # Um clique na primeira linha/cartão deve continuar representando o mesmo ID.
    columns, width, height, gap = window._card_layout()
    window._card_clicked(SimpleNamespace(x=gap+20, y=gap+height/2))
    assert set(window.selected_pairs) == {str(ids[0])}
    window.default_pairs.set('19')
    window.apply_pairs()
    window.add_to_session()
    wait_for_addition(window)
    saved = db.get_session_shapes(sid)
    assert len(saved) == 1
    assert saved[0]['id'] == ids[0]
    assert saved[0]['pairs'] == 19
    window.update()
    assert 'Já na sessão' in visible_text(window)


def test_compact_cards_show_more_columns_than_large_cards(view):
    window, db, ids, sid = view
    large = window._card_layout()
    window.set_view_mode('compact')
    window.update()
    compact = window._card_layout()
    assert compact[0] > large[0]
    assert compact[2] < large[2]


def test_details_show_real_measurements_and_sort_numerically(view):
    window, db, ids, sid = view
    box = [{'x': 0, 'y': 0}, {'x': 20, 'y': 0}, {'x': 20, 'y': 10}, {'x': 0, 'y': 10}]
    tiny = db.create_shape(name='Teste pequeno', contour=box, folder='Medidas', size='2')
    wide = db.create_shape(name='Teste grande', contour=[dict(p, x=p['x']*5) for p in box], folder='Medidas', size='10')
    window.reload_data()
    window.query.set('Medidas')
    window.apply_filters()
    window.set_view_mode('details')
    window.sort_details('width')
    window.update()
    assert [shape['id'] for shape in window.filtered_shapes] == [tiny, wide]
    texts = visible_text(window)
    assert '20,0' in texts and '100,0' in texts
    assert '2,00' in texts and '10,00' in texts  # cm², sem confundir com mm².
    window.sort_details('width')
    window.update()
    assert [shape['id'] for shape in window.filtered_shapes] == [wide, tiny]
    window.sort_details('size')
    assert [shape['id'] for shape in window.filtered_shapes] == [tiny, wide]


def test_details_horizontal_scroll_and_header_stay_aligned(view):
    window, db, ids, sid = view
    window.master.geometry('780x650')
    window.set_view_mode('details')
    window.update()
    assert window.details_header.winfo_ismapped()
    assert window.horizontal_scroll.winfo_ismapped()
    window._scroll_horizontal('moveto', .4)
    window.update()
    assert window.cards_canvas.xview()[0] > 0
    assert abs(window.cards_canvas.xview()[0]-window.details_header.xview()[0]) < .01
    # Clicar no cabeçalho depois de rolar ainda ordena a coluna indicada.
    key, title, left, width, anchor = window._detail_columns()[3]
    x = left-window.details_header.canvasx(0)+15
    window._header_clicked(SimpleNamespace(x=x))
    assert window._sort_column == key
    window.set_view_mode('cards')
    window.update()
    assert not window.details_header.winfo_ismapped()
    assert not window.horizontal_scroll.winfo_ismapped()
    assert window.cards_canvas.xview()[0] == 0


@pytest.mark.parametrize('mode', VIEW_MODES)
def test_empty_results_and_invalid_shapes_are_safe_in_every_mode(view, mode):
    window, db, ids, sid = view
    invalid = db.create_shape(name='Molde vazio', contour=[])
    window.reload_data()
    window.query.set('Molde vazio')
    window.apply_filters()
    window.set_view_mode(mode)
    window.update()
    window.toggle_shape(invalid)
    assert str(invalid) not in window.selected_pairs
    window.query.set('sem-resultados-999999')
    window.apply_filters()
    window.update()
    assert any('Nenhum molde encontrado' in text for text in visible_text(window))


@pytest.mark.parametrize('mode', VIEW_MODES)
def test_large_results_render_only_visible_items(view, mode):
    window, db, ids, sid = view
    source = copy.deepcopy(window.shapes_list[0])
    window.shapes_list = [dict(source, id=20000+index, name=f'Molde {index}') for index in range(3000)]
    window.shapes_by_id = {str(shape['id']): shape for shape in window.shapes_list}
    window._valid_ids = set(window.shapes_by_id)
    window.apply_filters()
    window.set_view_mode(mode)
    window.update()
    assert len(window.cards_canvas.find_all()) < 2000
    window._scroll_cards('moveto', 1)
    window.update()
    assert any('Molde 2999' in text for text in visible_text(window))
    assert len(window.cards_canvas.find_all()) < 2000


def test_keyboard_moves_one_row_in_list_and_details(view):
    window, db, ids, sid = view
    for mode in ('list', 'details'):
        window.set_view_mode(mode)
        window.update()
        window.focused_id = str(window.filtered_shapes[0]['id'])
        window._navigate(0, 1)
        assert window.focused_id == str(window.filtered_shapes[1]['id'])


def test_mode_survives_refresh_and_invalid_mode_does_not_change_it(view):
    window, db, ids, sid = view
    window.set_view_mode('list')
    window.reload_data()
    assert window.view_mode == 'list'
    assert window.view_choice.get() == VIEW_MODES['list']
    with pytest.raises(ValueError):
        window.set_view_mode('unknown')
    assert window.view_mode == 'list'


def test_metrics_do_not_mutate_geometry_and_invalid_contour_has_no_measurements():
    shape = {'contour': [{'x': 0, 'y': 0}, {'x': 120, 'y': 0}, {'x': 120, 'y': 80}, {'x': 0, 'y': 80}]}
    original = copy.deepcopy(shape)
    assert shape_metrics(shape) == (120, 80, 96)
    assert shape == original
    assert shape_metrics({'contour': []}) is None


def test_visualization_selector_opens_the_requested_presentation(view):
    window, db, ids, sid = view
    window.view_choice.set(VIEW_MODES['details'])
    window.view_combo.event_generate('<<ComboboxSelected>>')
    window.update()
    assert window.view_mode == 'details'
    assert window.details_header.winfo_ismapped()
    texts = [window.details_header.itemcget(item, 'text') for item in window.details_header.find_all()
             if window.details_header.type(item) == 'text']
    assert 'Largura\n(mm)' in texts
    assert 'Área externa\n(cm²)' in texts
