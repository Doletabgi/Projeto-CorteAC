from datetime import date
import json
import sqlite3
from analytics.production_dashboard import fetch_data, summarize


def test_weighted_yield_and_session_date_filters():
    sessions = [
        {'id': 1, 'order_id': 9, 'material_id': 'A', 'material_name': 'Couro', 'created_at': '2026-01-01 10:00:00', 'shapes_json': json.dumps([{'pairs': 20}])},
        {'id': 2, 'order_id': 9, 'material_id': 'B', 'material_name': 'Lona', 'created_at': '2026-01-02 10:00:00', 'shapes_json': json.dumps([{'pairs': 5}])},
    ]
    layouts = [{'session_id': 1, 'width_mm': 1000, 'height_mm': 1000, 'yield_percent': 50},
               {'session_id': 1, 'width_mm': 2000, 'height_mm': 1000, 'yield_percent': 80},
               {'session_id': 2, 'width_mm': 1000, 'height_mm': 1000, 'yield_percent': 90}]
    data = summarize(sessions, layouts, date(2026, 1, 1), date(2026, 1, 1), 'A')
    assert data['orders'] == 1 and data['sessions'] == 1 and data['pairs_planned'] == 20
    assert data['layouts'] == 2 and data['area_m2_per_layer'] == 3
    assert abs(data['yield_pct'] - 70) < 1e-9
    assert abs(data['unoccupied_m2_per_layer'] - .9) < 1e-9


def test_missing_invalid_and_empty_data_are_not_presented_as_measured():
    sessions = [{'id': 1, 'order_id': None, 'material_id': None, 'created_at': None, 'shapes_json': '[]'},
                {'id': 2, 'created_at': '2026-01-01', 'shapes_json': 'not json'}]
    layouts = [{'session_id': 1, 'width_mm': 1000, 'height_mm': 1000, 'yield_percent': 0},
               {'session_id': 2, 'width_mm': 0, 'height_mm': 1000, 'yield_percent': 80}]
    data = summarize(sessions, layouts)
    assert data['sessions_missing_pairs'] == 2
    assert data['invalid_layouts'] == 2 and data['yield_pct'] is None
    assert data['undated_sessions'] == 1
    assert summarize(sessions, layouts, start=date(2026, 1, 1))['sessions'] == 1


def test_fetch_data_reads_persisted_rows_without_inventing_layouts(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    c = sqlite3.connect(db_path)
    c.executescript('create table materials (id text, name text); create table sessions (id integer, order_id integer, material_id text, created_at text, shapes_json text); create table layouts (session_id integer, width_mm real, height_mm real, yield_percent real, yield_pct real);')
    c.execute("insert into sessions values (1, null, null, '2026-01-01', '[]')")
    c.commit()
    c.close()
    class DB:
        def get_connection(self):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn
    sessions, layouts = fetch_data(DB())
    assert len(sessions) == 1 and layouts == []
    assert summarize(sessions, layouts)['layouts'] == 0


def test_dashboard_window_shows_unavailable_and_filters():
    import tkinter as tk
    import pytest
    from ui.production_dashboard import ProductionDashboard
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Interface gráfica não disponível')
    class FakeDB:
        def get_connection(self):
            c = sqlite3.connect(':memory:')
            c.row_factory = sqlite3.Row
            c.executescript('create table materials (id text, name text); create table sessions (id integer, order_id integer, material_id text, created_at text, shapes_json text); create table layouts (session_id integer, width_mm real, height_mm real, yield_percent real, yield_pct real);')
            return c
    root.withdraw()
    try:
        panel = ProductionDashboard(root, FakeDB())
        root.update_idletasks()
        assert 'Indisponível' in panel.summary.get()
        assert str(panel.material_box.cget('state')) == 'readonly'
        panel.destroy()
    finally:
        root.destroy()


def test_legacy_yield_pct_is_used_when_primary_is_empty():
    sessions = [{'id': 1, 'created_at': '2026-01-01', 'shapes_json': '[{"pairs": 1}]'}]
    layouts = [{'session_id': 1, 'width_mm': 1000, 'height_mm': 1000, 'yield_percent': 0, 'yield_pct': 75}]
    assert summarize(sessions, layouts)['yield_pct'] == 75
