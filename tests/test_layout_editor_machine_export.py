"""Teste headless do botão 'Salvar Sessão para Máquina' do LayoutEditorView."""

from __future__ import annotations

import copy
from unittest.mock import patch

from ui.layout_editor_view import LayoutEditorView


CONTOUR = [
    {"x": 0.0, "y": 0.0},
    {"x": 100.0, "y": 0.0},
    {"x": 100.0, "y": 50.0},
    {"x": 0.0, "y": 50.0},
]


class _DB:
    def __init__(self, session, shapes):
        self.session = session
        self.shapes = shapes
        self.saved_layouts = None
        self.settings = {}

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = str(value)

    def save_session_layouts(self, session_id, layouts):
        self.saved_layouts = copy.deepcopy(layouts)
        self.session["layouts"] = copy.deepcopy(layouts)
        return True

    def get_session(self, session_id):
        return self.session if int(session_id) == int(self.session["id"]) else None

    def get_all_shapes(self):
        return list(self.shapes)


def _piece(name, target_id, x):
    return {
        "id": target_id,
        "target_id": target_id,
        "name": name,
        "size": "41",
        "x": x,
        "y": 10.0,
        "rotation": 0.0,
        "is_mirrored": False,
        "contour": list(CONTOUR),
        "holes": [],
        "stitching": [],
    }


def test_layout_editor_export_session_to_machine(tmp_path):
    shape = {
        "id": 1,
        "name": "Gaspea_41",
        "size": "41",
        "contour": list(CONTOUR),
        "holes": [],
        "stitching": [],
    }
    layouts = [
        {
            "layout_index": 0,
            "code": "lay0000",
            "name": "lay0000",
            "width_mm": 1000.0,
            "height_mm": 500.0,
            "gap_mm": 1.0,
            "layers": 2,
            "pieces": [_piece("Gaspea_41", 1, 10.0)],
        },
        {
            "layout_index": 1,
            "code": "lay0001",
            "name": "lay0001",
            "width_mm": 900.0,
            "height_mm": 500.0,
            "gap_mm": 1.0,
            "layers": 2,
            "pieces": [_piece("Gaspea_41", 1, 50.0)],
        },
    ]
    session = {
        "id": 77,
        "code": "SESS-77",
        "name": "Sessão 77",
        "job": "JOB",
        "material_id": "884412",
        "shapes": [shape],
        "layouts": copy.deepcopy(layouts),
    }
    db = _DB(session, [shape])

    editor = object.__new__(LayoutEditorView)
    editor.db = db
    editor.session = session
    editor.session_id = 77
    editor.layouts = copy.deepcopy(layouts)
    editor.current_layout_index = 0
    editor.placed_pieces = copy.deepcopy(layouts[0]["pieces"])
    editor.layout_name = "lay0000"
    editor.sheet_width = 1000.0
    editor.sheet_height = 500.0
    editor.material_layers = 2
    editor.tip_zone = None
    editor.layers_tip = None
    editor.trim_cut_line = None
    editor.material_id = "884412"
    editor.material_name = "MAT"
    editor.material = {"gap_mm": 1.0}

    target = tmp_path / "saida"
    target.mkdir()
    with patch("ui.layout_editor_view.filedialog.askdirectory", return_value=str(target)), \
         patch("ui.layout_editor_view.messagebox.showinfo") as info, \
         patch("ui.layout_editor_view.messagebox.showwarning") as warning, \
         patch("ui.layout_editor_view.messagebox.showerror") as error:
        editor.export_session_to_machine()

    assert not error.called
    assert info.called or warning.called
    assert db.saved_layouts is not None
    assert len(db.saved_layouts) == 2
    session_dir = target / "SESS-77"
    assert (session_dir / "lay0000.lay").is_file()
    assert (session_dir / "lay0001.lay").is_file()
    assert (session_dir / "Shapes" / "Gaspea_41.die").is_file()
    assert (session_dir / "manifest.json").is_file()
    assert db.settings.get("machine_export_dir") == str(target)
