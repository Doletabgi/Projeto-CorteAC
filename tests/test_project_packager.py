"""Testes do empacotador de sessão multi-placa (cad/project_packager.py)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from cad.die_parser import parse_die_file
from cad.project_packager import (
    CAC_FORMAT,
    MANIFEST_NAME,
    SHAPES_DIRNAME,
    DieSourceIndex,
    MissingDiesError,
    PackagingError,
    export_session,
    export_session_cac,
    pack_session_folder,
)


CONTOUR_A = [
    {"x": 0.0, "y": 0.0},
    {"x": 100.0, "y": 0.0},
    {"x": 100.0, "y": 50.0},
    {"x": 0.0, "y": 50.0},
]
CONTOUR_B = [
    {"x": 0.0, "y": 0.0},
    {"x": 80.0, "y": 0.0},
    {"x": 80.0, "y": 40.0},
    {"x": 0.0, "y": 40.0},
]


class FakeDB:
    """Banco mínimo, com a mesma interface usada pelo packager."""

    def __init__(self, session=None, shapes=None):
        self.session = session
        self.shapes = list(shapes or [])
        self.calls = {"get_all_shapes": 0, "get_session": 0}

    def get_session(self, session_id):
        self.calls["get_session"] += 1
        if self.session and int(self.session.get("id")) == int(session_id):
            return self.session
        return None

    def get_session_shapes(self, session_id):
        return self.session.get("shapes", []) if self.session else []

    def get_all_shapes(self):
        self.calls["get_all_shapes"] += 1
        return list(self.shapes)


def _piece(name, target_id, x=0.0, y=0.0, contour=None, size="41", **extra):
    piece = {
        "id": target_id,
        "target_id": target_id,
        "name": name,
        "size": size,
        "x": x,
        "y": y,
        "rotation": 0.0,
        "is_mirrored": False,
        "contour": list(CONTOUR_A if contour is None else contour),
        "holes": [],
        "stitching": [],
    }
    piece.update(extra)
    return piece


def _session(layouts=None, shapes=None):
    if layouts is None:
        layouts = [
            {
                "layout_index": 0,
                "code": "lay0000",
                "name": "lay0000",
                "width_mm": 1000.0,
                "height_mm": 500.0,
                "gap_mm": 1.0,
                "layers": 2,
                "pieces": [
                    _piece("Gaspea_41", 1, 10.0, 20.0),
                    _piece("Biqueira_40", 2, 200.0, 20.0, contour=CONTOUR_B),
                ],
            },
            {
                "layout_index": 1,
                "code": "lay0001",
                "name": "lay0001",
                "width_mm": 900.0,
                "height_mm": 500.0,
                "gap_mm": 1.0,
                "layers": 2,
                "pieces": [
                    _piece("Gaspea_41", 1, 50.0, 50.0),
                ],
            },
        ]
    if shapes is None:
        shapes = [
            {
                "id": 1,
                "name": "Gaspea_41",
                "size": "41",
                "contour": list(CONTOUR_A),
                "holes": [{"x": 50.0, "y": 25.0, "r": 2.0}],
                "stitching": [],
            },
            {
                "id": 2,
                "name": "Biqueira_40",
                "size": "40",
                "contour": list(CONTOUR_B),
                "holes": [],
                "stitching": [],
            },
        ]
    return {
        "id": 42,
        "code": "SESS-42",
        "name": "Sessão de Teste",
        "job": "JOB-TESTE",
        "material_id": "884412",
        "shapes": list(shapes),
        "layouts": list(layouts),
    }


def _read_lay(path: Path) -> list[str]:
    return path.read_text(encoding="latin1").splitlines()


def _lay_value(lines: list[str], key: str) -> list[str]:
    return [line.split("=", 1)[1].strip() for line in lines if line.startswith(f"{key}=")]


def test_export_all_layouts_and_only_referenced_dies(tmp_path):
    db = FakeDB(_session())
    result = export_session(db, 42, tmp_path)

    assert result.complete
    assert result.success
    assert result.session_code == "SESS-42"
    assert result.session_dir == tmp_path / "SESS-42"
    assert [l.filename for l in result.layouts] == ["lay0000.lay", "lay0001.lay"]

    # As duas placas foram gravadas.
    assert (result.session_dir / "lay0000.lay").is_file()
    assert (result.session_dir / "lay0001.lay").is_file()

    # Apenas os dois moldes usados, e apenas uma vez cada.
    shape_files = sorted(p.name for p in (result.session_dir / SHAPES_DIRNAME).iterdir())
    assert shape_files == ["Biqueira_40.die", "Gaspea_41.die"]
    assert len(result.dies) == 2
    assert db.calls["get_all_shapes"] == 1

    manifest = json.loads((result.session_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["format"] == CAC_FORMAT
    assert manifest["session"]["id"] == 42
    assert manifest["complete"] is True
    assert len(manifest["layouts"]) == 2
    assert {d["name"] for d in manifest["dies"]} == {"Gaspea_41", "Biqueira_40"}


def test_lay_line2_and_dlib_point_to_export_folder(tmp_path):
    target = tmp_path / "pasta com espaço"
    db = FakeDB(_session())
    result = export_session(db, 42, target)

    lines = _read_lay(result.session_dir / "lay0000.lay")
    assert lines[0] == "$$LAYOUT.v3$$"
    assert lines[1] == f"{result.session_dir} lay0000.lay"

    dlibs = _lay_value(lines, "dLib")
    assert dlibs
    assert all(value == str(result.shapes_dir) for value in dlibs)

    codes = _lay_value(lines, "dCode")
    assert set(codes) == {"Gaspea_41.die", "Biqueira_40.die"}


def test_generated_die_is_valid_fustella(tmp_path):
    db = FakeDB(_session())
    result = export_session(db, 42, tmp_path)

    die_path = result.shapes_dir / "Gaspea_41.die"
    content = die_path.read_text(encoding="latin1")
    assert content.startswith("$$FUSTELLA.v3$$")
    parsed = parse_die_file(str(die_path))
    assert parsed["name"] == "Gaspea_41"
    assert len(parsed["contour"]) >= 4
    assert len(parsed["holes"]) == 1

    manifest = json.loads((result.session_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    die_entry = next(d for d in manifest["dies"] if d["name"] == "Gaspea_41")
    assert die_entry["source"] == "db"
    assert die_entry["warning"]


def test_original_die_is_copied_byte_for_byte(tmp_path):
    source = tmp_path / "origem" / "Gaspea_41.die"
    source.parent.mkdir(parents=True)
    original_bytes = b"$$FUSTELLA.v3$$\nname_of_die = MODEL Gaspea_41\npoint=0 0\npoint=10 0\npoint=10 10\n"
    source.write_bytes(original_bytes)

    shapes = [
        {
            "id": 1,
            "name": "Gaspea_41",
            "size": "41",
            "contour": list(CONTOUR_A),
            "holes": [],
            "stitching": [],
            "source_path": str(source),
        }
    ]
    session = _session(shapes=shapes, layouts=[
        {
            "layout_index": 0,
            "code": "lay0000",
            "width_mm": 1000.0,
            "height_mm": 500.0,
            "gap_mm": 1.0,
            "pieces": [_piece("Gaspea_41", 1)],
        }
    ])
    result = export_session(FakeDB(session, shapes=shapes), 42, tmp_path)

    exported = result.shapes_dir / "Gaspea_41.die"
    assert exported.read_bytes() == original_bytes
    manifest = json.loads((result.session_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    entry = manifest["dies"][0]
    assert entry["source"] == "file"
    assert entry["original_path"].endswith("Gaspea_41.die")
    assert entry["warning"] == ""


def test_shapes_search_root_finds_nested_original(tmp_path):
    root = tmp_path / "biblioteca"
    nested = root / "151" / "060" / "pacote" / "884412"
    nested.mkdir(parents=True)
    original = nested / "Gaspea_41.die"
    original.write_bytes(b"$$FUSTELLA.v3$$\nfio original\n")

    session = _session(layouts=[
        {
            "layout_index": 0,
            "code": "lay0000",
            "width_mm": 1000.0,
            "height_mm": 500.0,
            "gap_mm": 1.0,
            "pieces": [_piece("Gaspea_41", 1)],
        }
    ])
    result = export_session(
        FakeDB(session),
        42,
        tmp_path / "destino",
        shapes_search_roots=[str(root)],
    )

    exported = result.shapes_dir / "Gaspea_41.die"
    assert exported.read_bytes() == original.read_bytes()
    assert result.dies[0].source == "file"


def test_missing_die_is_reported_and_can_be_strict(tmp_path):
    session = _session(layouts=[
        {
            "layout_index": 0,
            "code": "lay0000",
            "width_mm": 1000.0,
            "height_mm": 500.0,
            "gap_mm": 1.0,
            "pieces": [_piece("Fantasma", 99, contour=[])],
        }
    ])
    session["shapes"] = []
    db = FakeDB(session, shapes=[])

    result = export_session(db, 42, tmp_path)
    assert result.missing
    assert result.missing[0]["name"] == "Fantasma"
    assert result.complete is False
    # O layout sai mesmo assim; o operador vê a lista de ausentes no manifesto.
    assert (result.session_dir / "lay0000.lay").is_file()
    manifest = json.loads((result.session_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["missing"]

    with pytest.raises(MissingDiesError) as exc_info:
        export_session(db, 42, tmp_path / "strict", strict=True)
    assert exc_info.value.missing[0]["name"] == "Fantasma"


def test_same_die_in_two_layouts_is_deduplicated(tmp_path):
    db = FakeDB(_session())
    result = export_session(db, 42, tmp_path)
    assert len([d for d in result.dies if d.name == "Gaspea_41"]) == 1
    assert len(list((result.session_dir / SHAPES_DIRNAME).glob("Gaspea_41*.die"))) == 1


def test_no_subfolder_writes_directly_to_target(tmp_path):
    db = FakeDB(_session())
    result = export_session(db, 42, tmp_path, create_subfolder=False)
    assert result.session_dir == tmp_path.resolve()
    assert (tmp_path / "lay0000.lay").is_file()
    assert (tmp_path / MANIFEST_NAME).is_file()
    lines = _read_lay(tmp_path / "lay0000.lay")
    assert lines[1] == f"{tmp_path.resolve()} lay0000.lay"


def test_reference_mode_does_not_copy_dies_and_uses_dlib_override(tmp_path):
    db = FakeDB(_session())
    result = export_session(
        db,
        42,
        tmp_path,
        copy_dies=False,
        dlib_override=r"\\lab-inf\NSDATAV1\Shapes",
    )
    assert result.shapes_dir is None
    assert not (result.session_dir / SHAPES_DIRNAME).exists()
    lines = _read_lay(result.session_dir / "lay0000.lay")
    assert all(v == r"\\lab-inf\NSDATAV1\Shapes" for v in _lay_value(lines, "dLib"))
    # Em modo referência o dCode original é preservado.
    assert "Gaspea_41.die" in _lay_value(lines, "dCode")
    manifest = json.loads((result.session_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert all(d["file"] is None for d in manifest["dies"])


def test_pack_session_folder_creates_zip_with_relative_names(tmp_path):
    db = FakeDB(_session())
    result = export_session(db, 42, tmp_path / "saida")
    cac = pack_session_folder(result.session_dir, tmp_path / "SESS-42.cac")

    assert cac.is_file()
    with zipfile.ZipFile(cac) as zf:
        names = zf.namelist()
    assert MANIFEST_NAME in names
    assert "lay0000.lay" in names
    assert "lay0001.lay" in names
    assert "Shapes/Gaspea_41.die" in names
    assert all(not n.startswith("/") and ".." not in n.split("/") for n in names)


def test_export_session_cac_returns_cac_and_cleans_temp(tmp_path):
    db = FakeDB(_session())
    cac_path = tmp_path / "projeto.cac"
    result = export_session_cac(db, 42, cac_path)
    assert result.cac_path == cac_path
    assert cac_path.is_file()
    assert result.layouts
    with zipfile.ZipFile(cac_path) as zf:
        assert MANIFEST_NAME in zf.namelist()


def test_invalid_session_and_empty_session_raise(tmp_path):
    with pytest.raises(PackagingError):
        export_session(FakeDB(_session()), 999, tmp_path)

    empty = _session(layouts=[])
    with pytest.raises(PackagingError):
        export_session(FakeDB(empty), 42, tmp_path)


def test_die_source_index_ignores_non_die_and_finds_sidecar(tmp_path):
    root = tmp_path / "shapes"
    root.mkdir()
    (root / "foo.txt").write_text("x")
    (root / "Gaspea_41.die").write_bytes(b"x")
    index = DieSourceIndex([str(root)])
    assert index.find("Gaspea_41.die") is not None
    assert index.find("foo.txt") is None
    assert index.find("inexistente.die") is None


def test_flat_piece_geometry_generates_die_without_db_shape(tmp_path):
    """Layouts antigos trazem contour no nível da peça, sem shape aninhado."""
    session = _session(shapes=[])
    db = FakeDB(session, shapes=[])
    result = export_session(db, 42, tmp_path)
    assert result.complete
    assert (result.shapes_dir / "Gaspea_41.die").is_file()
    assert result.dies[0].source == "db"


def test_die_filename_is_sanitized_and_lay_code_matches(tmp_path):
    session = _session(shapes=[], layouts=[
        {
            "layout_index": 0,
            "code": "lay0000",
            "width_mm": 1000.0,
            "height_mm": 500.0,
            "gap_mm": 1.0,
            "pieces": [_piece("Gaspea/41", 1)],
        }
    ])
    result = export_session(FakeDB(session, shapes=[]), 42, tmp_path)

    assert result.dies[0].filename == "41.die"
    assert (result.shapes_dir / "41.die").is_file()
    lines = _read_lay(result.session_dir / "lay0000.lay")
    assert _lay_value(lines, "dCode") == ["41.die"]
    # Nenhum diretório extra criado dentro de Shapes.
    assert all(p.is_file() for p in (result.session_dir / SHAPES_DIRNAME).iterdir())


def test_reexport_removes_stale_layouts_only_when_manifest_exists(tmp_path):
    db = FakeDB(_session())
    export_session(db, 42, tmp_path)
    assert (tmp_path / "SESS-42" / "lay0001.lay").is_file()

    one_layout = _session(layouts=[
        {
            "layout_index": 0,
            "code": "lay0000",
            "width_mm": 1000.0,
            "height_mm": 500.0,
            "gap_mm": 1.0,
            "pieces": [_piece("Gaspea_41", 1)],
        }
    ])
    export_session(FakeDB(one_layout), 42, tmp_path)
    assert (tmp_path / "SESS-42" / "lay0000.lay").is_file()
    assert not (tmp_path / "SESS-42" / "lay0001.lay").exists()


def test_no_manifest_does_not_delete_unrelated_lay(tmp_path):
    target = tmp_path / "destino"
    target.mkdir()
    keep = target / "keep.lay"
    keep.write_text("nao apagar", encoding="latin1")

    db = FakeDB(_session())
    export_session(db, 42, target, create_subfolder=False)
    assert keep.read_text(encoding="latin1") == "nao apagar"


def test_reuses_shape_catalog_and_die_index(tmp_path):
    root = tmp_path / "biblioteca"
    root.mkdir()
    source = root / "Gaspea_41.die"
    source.write_bytes(b"$$FUSTELLA.v3$$\noriginal\n")
    index = DieSourceIndex([str(root)])

    session = _session(layouts=[
        {
            "layout_index": 0,
            "code": "lay0000",
            "width_mm": 1000.0,
            "height_mm": 500.0,
            "gap_mm": 1.0,
            "pieces": [_piece("Gaspea_41", 1)],
        }
    ])
    db = FakeDB(session)
    result = export_session(
        db,
        42,
        tmp_path / "destino",
        shape_catalog=session["shapes"],
        die_index=index,
    )
    assert db.calls["get_all_shapes"] == 0
    assert (result.shapes_dir / "Gaspea_41.die").read_bytes() == source.read_bytes()


def test_nested_shape_geometry_from_batch_layout(tmp_path):
    """Layouts do batch trazem shape.contour_json aninhado, sem contour no topo."""
    nested_piece = {
        "id": 1,
        "target_id": 1,
        "name": "Gaspea_41",
        "size": "41",
        "x": 10.0,
        "y": 20.0,
        "rotation": 0.0,
        "shape": {
            "id": 1,
            "name": "Gaspea_41",
            "contour_json": json.dumps(CONTOUR_A),
            "holes_json": "[]",
            "stitching_json": "[]",
        },
    }
    session = _session(shapes=[], layouts=[
        {
            "layout_index": 0,
            "code": "lay0000",
            "width_mm": 1000.0,
            "height_mm": 500.0,
            "gap_mm": 1.0,
            "pieces": [nested_piece],
        }
    ])
    result = export_session(FakeDB(session, shapes=[]), 42, tmp_path)
    assert result.complete
    assert (result.shapes_dir / "Gaspea_41.die").is_file()
