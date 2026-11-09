"""Regressões da comparação diagnóstica de nesting."""
import copy
import sqlite3
import pytest

from tools.comparar_nesting import analyze_demand, analyze_trim, compare_case, load_sqlite_session, validate_layouts


def square(x=0, y=0, size=10, shape_id=1):
    contour = [{'x': 0, 'y': 0}, {'x': size, 'y': 0},
               {'x': size, 'y': size}, {'x': 0, 'y': size}]
    shape = {'id': shape_id, 'name': str(shape_id), 'size': '40', 'contour': contour,
             'pairs': 1, 'sequence': shape_id}
    return shape, {'shape': shape, 'contour': contour, 'x': x, 'y': y, 'rotation': 0}


def test_rejects_wrong_shape_and_ambiguous_matches():
    shape, piece = square()
    other, _ = square(shape_id=2)
    assert not analyze_demand([shape, other], [{'pieces': [piece, piece]}], 2)['atendida']
    result = analyze_demand([shape, dict(shape)], [{'pieces': [piece]}], 2)
    assert result['pecas_ambiguas'] == 1
    assert not result['atendida']


def test_check_detects_gap_violation_and_margin_excess():
    _, a = square(0, 0)
    _, b = square(10.5, 0, shape_id=2)
    result = validate_layouts([{'pieces': [a, b]}], 100, 100,
                              dict(left=1, right=1, top=1, bottom=1), 1)
    assert result['pares_em_conflito'] == 1
    assert result['fora_das_margens'] == 2
    assert result['maior_excesso_margem_mm'] == 1


def test_trim_does_not_mutate_layout_and_reports_area_per_layer():
    _, p = square(5, 5)
    layout = {'pieces': [p], 'width_mm': 100, 'height_mm': 100}
    before = copy.deepcopy(layout)
    result = analyze_trim([layout], 100, 100, 1)
    assert layout == before
    assert result['area_original_m2'] == 0.01
    assert result['area_apos_refile_m2'] == 0.0003
    assert result['area_recortada_m2'] == 0.0097


def test_missing_session_does_not_create_sqlite(tmp_path):
    db = tmp_path / 'ausente.db'
    with pytest.raises(sqlite3.OperationalError):
        load_sqlite_session(db, 1)
    assert not db.exists()


def test_complete_sample_does_not_change_input_or_environment(monkeypatch):
    shape, _ = square()
    before = copy.deepcopy(shape)
    monkeypatch.setenv('CORTEAC_BACKEND', 'nfp')
    result = compare_case([shape], 100, 100, 2, dict(left=1, right=1, top=1, bottom=1), 1,
                          'flashnestsheet', 'python', 5)
    assert result['resultado_completo']
    assert result['demanda_por_molde']['atendida']
    assert shape == before
    import os
    assert os.environ['CORTEAC_BACKEND'] == 'nfp'


def test_load_session_preserves_specific_layers_and_parameters(tmp_path):
    import json
    db = tmp_path / 'sessao.db'
    shape, _ = square()
    conn = sqlite3.connect(str(db))
    conn.execute('create table sessions (id integer, material_id text, shapes_json text, layers integer, gap_mm real, params text, margin_left real, margin_right real, margin_top real, margin_bottom real)')
    conn.execute('create table materials (id text, width_mm real, height_mm real, layers integer)')
    conn.execute('insert into materials values (?, ?, ?, ?)', ('a', 100, 200, 2))
    conn.execute('insert into sessions values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (7, 'a', json.dumps([shape]), 4, 2, 'FastNest', 3, 4, 5, 6))
    conn.commit()
    conn.close()
    before = db.read_bytes()
    result = load_sqlite_session(db, 7)
    assert result['layers'] == 4
    assert result['params'] == 'FastNest'
    assert result['gap_mm'] == 2
    assert result['margins'] == {'left': 3, 'right': 4, 'top': 5, 'bottom': 6}
    assert db.read_bytes() == before


def test_fill_preview_works_on_copy(monkeypatch):
    import tools.comparar_nesting as comparison
    shape, _ = square()
    original = copy.deepcopy(shape)
    calls = []
    def fake_fill(layouts, **kwargs):
        calls.append(True)
        return layouts, {'movidas': 0, 'placas_removidas': 0}
    monkeypatch.setattr(comparison.nesting_engine, 'preencher_buracos_em_placas', fake_fill)
    result = compare_case([shape], 100, 100, 2, dict(left=1, right=1, top=1, bottom=1),
                          1, 'flashnestsheet', 'python', 5, fill_holes=True)
    assert calls and result['preenchimento_simulado']['demanda_por_molde']['atendida']
    assert shape == original
