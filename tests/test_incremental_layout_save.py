import copy
from unittest.mock import patch

import pytest

from database import DatabaseManager
from db.connection import DBCursor


def layouts(count=3):
    return [{"layout_index": i, "name": f"lay{i:04d}", "layers": 4,
             "pieces": [{"id": 1, "name": "Molde", "size": "41", "x": 10.0,
                         "y": 20.0, "rotation": 0.0,
                         "contour": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 0, "y": 30}]}]}
            for i in range(count)]


@pytest.fixture
def saved(tmp_path):
    db = DatabaseManager(tmp_path / "incremental.db")
    sid = db.create_session(name="Incremental")
    data = layouts()
    db.save_session_layouts(sid, data)
    return db, sid, data


def snapshot(db, sid):
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM layouts WHERE session_id = ? ORDER BY layout_index", (sid,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM layout_pieces ORDER BY id")
        return rows, [dict(r) for r in cur.fetchall()]


def test_unchanged_save_performs_no_writes_even_with_different_json_key_order(saved):
    db, sid, data = saved
    before = snapshot(db, sid)
    data[1]["pieces"][0] = dict(reversed(list(data[1]["pieces"][0].items())))
    with patch.object(DBCursor, "execute", autospec=True, side_effect=DBCursor.execute) as execute:
        db.save_session_layouts(sid, data)
        writes = [call.args[1] for call in execute.call_args_list
                  if call.args[1].lstrip().upper().startswith(("UPDATE ", "INSERT ", "DELETE "))]
        assert writes == []
    assert snapshot(db, sid) == before


def test_only_edited_sheet_and_its_pieces_change(saved):
    db, sid, data = saved
    before, old_pieces = snapshot(db, sid)
    data[1]["pieces"][0]["x"] = 123.0
    db.save_session_layouts(sid, data)
    after, new_pieces = snapshot(db, sid)
    assert [r["id"] for r in after] == [r["id"] for r in before]
    assert after[0] == before[0] and after[2] == before[2]
    assert after[1]["version"] == before[1]["version"] + 1
    for index in (0, 2):
        lid = before[index]["id"]
        assert [p for p in old_pieces if p["layout_id"] == lid] == [p for p in new_pieces if p["layout_id"] == lid]
    assert db.get_session_layouts(sid)[1]["pieces"][0]["x"] == 123.0
    assert data[1]["version"] == after[1]["version"]


def test_metadata_changes_preserve_relational_pieces_and_production_owner(saved):
    db, sid, data = saved
    before, pieces = snapshot(db, sid)
    db.add_user("Novo operador", set_active=True)
    data[1].update(height_mm=500, layers=2, layers_tip=1,
                   tip_zone=[0, 0, 20, 20], trim_cut_line={"y": 500})
    db.save_session_layouts(sid, data)
    after, changed_pieces = snapshot(db, sid)
    assert changed_pieces == pieces
    assert after[1]["height_mm"] == 500
    assert after[1]["layers"] == 2
    assert after[1]["production_user"] == before[1]["production_user"]
    assert after[1]["updated_by"] == "Novo operador"


def test_insert_and_remove_only_requested_sheets(saved):
    db, sid, data = saved
    before, _ = snapshot(db, sid)
    data = [data[0], data[2], layouts(4)[3]]
    db.save_session_layouts(sid, data)
    after, pieces = snapshot(db, sid)
    assert [r["layout_index"] for r in after] == [0, 2, 3]
    assert after[0] == before[0] and after[1] == before[2]
    assert all(p["layout_id"] != before[1]["id"] for p in pieces)


def test_failure_rolls_back_deletions_and_updates_without_mutating_input(saved):
    db, sid, data = saved
    before = snapshot(db, sid)
    changed = copy.deepcopy(data[:2])
    changed[0]["pieces"][0]["x"] = 90
    input_before = copy.deepcopy(changed)
    with patch.object(DBCursor, "executemany", side_effect=RuntimeError("Falha simulada")):
        with pytest.raises(RuntimeError, match="Falha simulada"):
            db.save_session_layouts(sid, changed)
    assert snapshot(db, sid) == before
    assert changed == input_before


def test_parent_session_remains_synchronized(saved):
    db, sid, data = saved
    data[0]["pieces"][0]["rotation"] = 45
    data[0]["yield_percent"] = 60
    db.save_session_layouts(sid, data)
    session = db.get_session(sid)
    assert session["placed_pieces"][0]["rotation"] == 45
    assert session["yield_percent"] == 20


def test_duplicate_indices_rejected_without_changes(saved):
    db, sid, data = saved
    before = snapshot(db, sid)
    with pytest.raises(ValueError, match="duplicados"):
        db.save_session_layouts(sid, [data[0], data[0]])
    assert snapshot(db, sid) == before


def test_nested_geometry_edit_is_detected_with_serialization_cache(saved):
    db, sid, data = saved
    data[1]["pieces"][0]["contour"][0]["x"] = 99
    db.save_session_layouts(sid, data)
    assert db.get_session_layouts(sid)[1]["pieces"][0]["contour"][0]["x"] == 99


def test_fresh_database_instance_without_cache_saves_unchanged_plates_without_writes(saved):
    db, sid, data = saved
    before = snapshot(db, sid)
    fresh = DatabaseManager(db.db_path)
    fresh.save_session_layouts(sid, data)
    assert snapshot(db, sid) == before
