"""Busca global, quantidades e inclusão transacional do catálogo."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from database import DatabaseManager
from cad.shape_library import add_shapes_to_session, contour_points, filter_shapes, validate_pairs

BOX = [{'x': 0, 'y': 0}, {'x': 120, 'y': 0}, {'x': 120, 'y': 80}, {'x': 0, 'y': 80}]


@pytest.fixture
def library_db(tmp_path):
    db = DatabaseManager(str(tmp_path/'catalog.db'), backend='sqlite')
    for session in db.get_sessions():
        db.update_session_shapes(session['id'], [])
    ids = []
    for name, size, folder in [('Gáspea_22a', '22a', 'Modelo 323'), ('Gáspea_23a', '23a', 'Modelo 323'),
                                ('Forro_22a', '22a', 'Modelo 323/Forros'), ('Palmilha_22a', '22a', ''),
                                ('Outro_25a', '25a', 'Modelo 415')]:
        ids.append(db.create_shape(name=name, contour=BOX, size=size, folder=folder))
    with db.get_connection() as connection:
        connection.cursor().execute('UPDATE shapes SET article_id = NULL WHERE id = ?', (ids[0],))
    return db, ids, db.get_sessions()[0]['id']


def test_global_search_includes_unassigned_shapes_and_ignores_accents(library_db):
    db, ids, sid = library_db
    result = filter_shapes(db.get_all_shapes(), query='gaspea 323 22a')
    assert [shape['id'] for shape in result] == [ids[0]]
    assert result[0]['article_id'] is None


def test_folder_hierarchy_root_size_and_article_filters(library_db):
    db, ids, sid = library_db
    all_shapes = db.get_all_shapes()
    assert {shape['id'] for shape in filter_shapes(all_shapes, folder='Modelo 323')} == set(ids[:3])
    assert [shape['id'] for shape in filter_shapes(all_shapes, folder='Modelo 323/Forros')] == [ids[2]]
    assert ids[3] in {shape['id'] for shape in filter_shapes(all_shapes, folder='')}
    assert [shape['id'] for shape in filter_shapes(all_shapes, folder='Modelo 323', size='23a')] == [ids[1]]
    assert not filter_shapes(all_shapes, article_id=99999)


@pytest.mark.parametrize('value', ['', 0, -1, '1.5', 10000, 'abc', True, '9'*5000])
def test_pairs_reject_invalid_quantities(value):
    with pytest.raises(ValueError, match='entre 1 e 9999'):
        validate_pairs(value)


def test_contour_validation_handles_corrupt_empty_and_collinear_shapes():
    for points in ([], [{'x': 0}], [{'x': float('nan'), 'y': 1}]*3, [(0, 0), (1, 1), (2, 2)]):
        assert contour_points({'contour': points}) == []
    assert len(contour_points({'contour': BOX})) == 4


def test_add_keeps_existing_pairs_sequence_geometry_and_layouts(library_db):
    db, ids, sid = library_db
    original = db.get_shape(ids[0])
    original.update(pairs=77, sequence=9, rest=3, target_pieces=12)
    db.update_session_shapes(sid, [original])
    before = db.get_session(sid)
    result = add_shapes_to_session(db, sid, [{'id': str(ids[0]), 'pairs': 1}, {'id': ids[1], 'pairs': 24}])
    assert (result.added, result.skipped) == (1, 1)
    saved = db.get_session_shapes(sid)
    assert saved[0] == original
    assert saved[1]['pairs'] == 24
    assert saved[1]['sequence'] == 10
    assert saved[1]['contour'] == BOX
    assert saved[1]['shape_format'] == '1x1'
    after = db.get_session(sid)
    for key in ('layouts', 'placed_pieces', 'material_id', 'status'):
        assert after[key] == before[key]
    other = next(item for item in db.get_sessions() if item['id'] != sid)
    assert other['shapes'] == []
    assert db.get_shape(ids[1]).get('pairs') is None


def test_repeat_add_is_idempotent_and_preserves_first_quantity(library_db):
    db, ids, sid = library_db
    add_shapes_to_session(db, sid, [{'id': ids[0], 'pairs': 7}])
    result = add_shapes_to_session(db, sid, [{'id': ids[0], 'pairs': 99}])
    assert (result.added, result.skipped) == (0, 1)
    assert db.get_session_shapes(sid)[0]['pairs'] == 7


def test_invalid_selection_missing_shape_or_deleted_session_never_partially_writes(library_db):
    db, ids, sid = library_db
    for selection in ([], [{'id': ids[0], 'pairs': 0}], [{'id': ids[0], 'pairs': 5}, {'id': 999999, 'pairs': 8}]):
        with pytest.raises(ValueError):
            add_shapes_to_session(db, sid, selection)
        assert db.get_session_shapes(sid) == []
    with pytest.raises(ValueError, match='sessão escolhida'):
        add_shapes_to_session(db, 999999, [{'id': ids[0], 'pairs': 5}])


def test_corrupt_existing_session_is_not_overwritten(library_db):
    db, ids, sid = library_db
    with db.get_connection() as conn:
        conn.cursor().execute('UPDATE sessions SET shapes_json = ? WHERE id = ?', ('corrompido', sid))
    with pytest.raises(ValueError, match='sessão não foi alterada'):
        add_shapes_to_session(db, sid, [{'id': ids[0], 'pairs': 5}])
    with db.get_connection() as conn:
        cur = conn.cursor();cur.execute('SELECT shapes_json FROM sessions WHERE id = ?', (sid,))
        assert cur.fetchone()[0] == 'corrompido'


def test_reads_current_geometry_instead_of_old_preview(library_db):
    db, ids, sid = library_db
    changed = copy.deepcopy(BOX)
    changed[1]['x'] = 140
    db.update_shape(ids[0], 'Novo nome', changed)
    add_shapes_to_session(db, sid, [{'id': ids[0], 'pairs': 8}])
    shape = db.get_session_shapes(sid)[0]
    assert shape['name'] == 'Novo nome'
    assert shape['contour'] == changed


def test_concurrent_additions_are_merged_without_losing_either_selection(library_db):
    db, ids, sid = library_db
    barrier = threading.Barrier(2)
    def add(shape_id):
        barrier.wait()
        return add_shapes_to_session(db, sid, [{'id': shape_id, 'pairs': 12}])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(add, ids[:2]))
    assert all(result.added == 1 for result in results)
    saved = db.get_session_shapes(sid)
    assert {shape['id'] for shape in saved} == set(ids[:2])
    assert len({shape['sequence'] for shape in saved}) == 2


def test_large_selection_reads_sources_in_batches(library_db):
    db, ids, sid = library_db
    bulk_ids = list(range(10000, 10506))
    with db.get_connection() as conn:
        conn.cursor().executemany(
            'INSERT INTO shapes (id, name, color, contour_json, holes_json, stitching_json, folder, size, shape_format) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [(key, f'Molde {key}', '#2563eb', json.dumps(BOX), '[]', '[]', 'Lote', '22a', '1x1') for key in bulk_ids])
    result = add_shapes_to_session(db, sid, [{'id': key, 'pairs': 1} for key in bulk_ids])
    assert result.added == 506
    assert len(db.get_session_shapes(sid)) == 506


def test_mysql_branch_locks_destination_before_reading_and_updating(library_db):
    from unittest.mock import MagicMock
    db, ids, sid = library_db
    source = db.get_shape(ids[0])
    fake = MagicMock()
    connection = fake.get_connection.return_value.__enter__.return_value
    connection.backend = 'mysql'
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {'id': sid, 'shapes_json': '[]'}
    cursor.fetchall.return_value = [source]
    result = add_shapes_to_session(fake, sid, [{'id': ids[0], 'pairs': 12}])
    assert result.added == 1
    first_query = cursor.execute.call_args_list[0].args[0]
    assert first_query.endswith('FOR UPDATE')
    assert not any('BEGIN IMMEDIATE' in call.args[0] for call in cursor.execute.call_args_list)
