"""Regressões das regras da barra lateral, executáveis sem servidor gráfico."""
from copy import deepcopy

import pytest

from cad.sidebar_rules import (
    count_pieces_for_target,
    get_plates_for_target,
    piece_matches_target,
)


@pytest.mark.parametrize("piece,target,expected", [
    (None, {"id": "1"}, False),
    ({"id": "1"}, None, False),
    ({"target_id": 1, "size": "41"}, {"id": " 1 ", "size": "41"}, True),
    ({"target_id": "1", "size": "42"}, {"id": "1", "size": "41"}, False),
    ({"target_id": "2", "name": "Gaspea"}, {"id": "1", "name": "Gaspea"}, False),
    ({"shape_id": "1"}, {"id": "1"}, True),
    ({"shape": {"id": "1", "size": "41"}}, {"id": "1", "size": "41"}, True),
    # ID de destino e tamanho explícitos têm precedência sobre shape aninhado.
    ({"target_id": "2", "shape_id": "1"}, {"id": "1"}, False),
    ({"size": "42", "shape": {"size": "41"}}, {"size": "41"}, False),
    ({"name": " GASPEA... "}, {"name": "Gaspea"}, True),
    ({"name": "Gaspea_41a"}, {"name": "Gaspea"}, True),
    ({"name": "Gaspea"}, {"name": "Gaspea_41a"}, True),
    ({"name": "Gaspea", "size": "41"}, {"name": "Forro", "size": "41"}, False),
    ({"size": "41"}, {"name": "Gaspea", "size": "41"}, True),
    ({"shape": "arquivo.die", "size": "41"}, {"size": "41"}, True),
    ({"x": 10}, {"id": "1"}, False),
])
def test_matching_preserves_legacy_identity_rules(piece, target, expected):
    assert piece_matches_target(piece, target) is expected


def test_counts_and_plates_use_unsaved_current_layout_without_mutation():
    target = {"id": "32", "name": "323_PalAcb_32a", "size": "32"}
    piece = {"target_id": "32", "size": "32"}
    other = {"target_id": "36", "size": "36"}
    layouts = [
        {"pieces": [other], "layers": 4},
        {"placed_pieces": [piece] * 31, "layers": 2},
        {"pieces": [other]},
    ]
    current = [piece] * 20
    snapshot = deepcopy((layouts, current, target))
    assert count_pieces_for_target(current, target) == 20
    assert get_plates_for_target(layouts, 0, current, target) == [1, 2]
    # Remover todas as peças da placa atual não recupera a cópia salva.
    assert get_plates_for_target(layouts, 1, [], target) == []
    assert (layouts, current, target) == snapshot


@pytest.mark.parametrize("layouts", [None, []])
def test_single_plate_without_session_layouts(layouts):
    target = {"id": "1"}
    assert get_plates_for_target(layouts, 0, [{"shape_id": "1"}], target) == [1]
    assert get_plates_for_target(layouts, 0, [], target) == []
    assert count_pieces_for_target(None, target) == 0
    assert count_pieces_for_target([{"shape_id": "1"}], None) == 0


def test_editor_delegates_rules_without_creating_tk_window():
    from ui.layout_editor_view import LayoutEditorView

    # Exercita a integração real com os métodos do editor sem inicializar Tk.
    view = LayoutEditorView.__new__(LayoutEditorView)
    view.layouts = [{"pieces": [], "layers": 4}, {"pieces": [], "layers": 2}]
    view.current_layout_index = 1
    view.placed_pieces = [{"shape": {"id": "1", "size": "41"}}] * 3
    target = {"id": "1", "size": "41"}
    assert view._piece_matches_target(view.placed_pieces[0], target)
    assert view.count_pieces_for_target(view.placed_pieces, target) == 3
    assert view.get_plates_for_target(target) == [2]
