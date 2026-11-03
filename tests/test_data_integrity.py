"""
tests/test_data_integrity.py

Testes de integridade de dados e blindagem de persistência das sessões.
Garante que:
1. SessionView.load_session NUNCA dispara UPDATE no banco de dados.
2. O worker de nesting (_poll_nest_worker) e o reset (clear_session_nesting) operam
   estritamente sobre os moldes da sessão, isolando-se do catálogo global (current_shapes).
3. DatabaseManager sanitiza e preserva metadados essenciais (pairs, sequence, rest).
4. Moldes fantasmas sem correspondência nas peças do layout são filtrados.
5. O utilitário de higienização (scrub_all_sessions_shapes) corrige inconsistências.
"""

import os
import json
import copy
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

from database import DatabaseManager
from ui.session_view import SessionView
from tools.scrub_all_sessions_shapes import scrub_sessions


@pytest.fixture
def temp_db(tmp_path):
    """Cria um banco SQLite temporário isolado para testes."""
    db_file = str(tmp_path / "test_integrity.db")
    db = DatabaseManager(db_path=db_file)
    db.init_db()
    return db, db_file


class TestDataIntegrity:

    def test_load_session_never_updates_db(self):
        """Garante que abrir/carregar uma sessão no SessionView é 100% somente-leitura."""
        mock_db = MagicMock()
        mock_parent = MagicMock()

        # Instancia SessionView sem inicializar widgets reais do Tkinter caso não haja display
        with patch.object(SessionView, "__init__", lambda self, *args, **kwargs: None):
            view = SessionView()
            view.db = mock_db
            view.lbl_title = MagicMock()
            view.entry_sname = MagicMock()
            view.cb_strategy = MagicMock()
            view.cb_params = MagicMock()
            view.cb_params.__getitem__.return_value = ["stdNOTFill", "ALTERNADO"]
            view.refresh_params_list = MagicMock()
            view.update_strategy_description = MagicMock()
            view.highlight_guide_matching = MagicMock()
            view._refresh_layer_2_widgets = MagicMock()
            view.update_summary_text = MagicMock()
            view.set_shapes_data = MagicMock()

            # Sessão com parâmetro desconhecido ou legado
            sess_data = {
                "id": 100,
                "name": "Sessao Teste ReadOnly",
                "params": "PARAM_INEXISTENTE;separar_sobras=1",
                "status": "Stand by",
                "shapes": [{"id": 1, "name": "M1", "size": "41", "pairs": 11}],
                "layouts": []
            }

            view.load_session(sess_data)

            # Verifica que NENHUM método de escrita foi chamado no mock_db
            assert mock_db.update_session.call_count == 0
            assert mock_db.update_session_shapes.call_count == 0
            assert mock_db.save_session_layouts.call_count == 0

    def test_database_preserves_pairs_and_sequence_on_update(self, temp_db):
        """Garante que update_session_shapes preserva pairs e sequence existentes se novos vierem None."""
        db, db_file = temp_db

        # Cria sessão com moldes tendo pares e sequência definidos
        sid = db.create_session(name="Sessao Integridade")
        initial_shapes = [
            {"id": 10, "name": "Molde1", "size": "40", "pairs": 11, "sequence": 1, "rest": 11},
            {"id": 20, "name": "Molde2", "size": "41", "pairs": 15, "sequence": 2, "rest": 15}
        ]
        db.update_session_shapes(sid, initial_shapes)

        # Simula tentativa de sobrescrita com lista incompleta (pairs=None, sequence=None)
        incomplete_shapes = [
            {"id": 10, "name": "Molde1", "size": "40", "pairs": None, "sequence": None},
            {"id": 20, "name": "Molde2", "size": "41", "pairs": None, "sequence": None}
        ]
        db.update_session_shapes(sid, incomplete_shapes)

        saved = db.get_session_shapes(sid)
        assert len(saved) == 2
        # Pares e sequências foram protegidos e preservados!
        assert saved[0]["pairs"] == 11
        assert saved[0]["sequence"] == 1
        assert saved[1]["pairs"] == 15
        assert saved[1]["sequence"] == 2

    def test_poll_nest_worker_does_not_contaminate_with_catalog_shapes(self):
        """Valida que o retorno do nesting atualiza os moldes da sessão e não do catálogo global."""
        from ui.main_window import MainWindow

        win = MagicMock()
        win.db = MagicMock()
        win.lbl_status_msg = MagicMock()
        win.canvas = MagicMock()
        win.sessions = []
        win.save_current_session_state = MagicMock()
        win.layout_editor_view = None
        win._nest_progress = None
        win._nesting_in_progress = True

        # Catálogo global com 5 moldes
        win.current_shapes = [
            {"id": 1, "name": "Cat1", "size": "38", "pairs": None},
            {"id": 2, "name": "Cat2", "size": "39", "pairs": None},
            {"id": 3, "name": "Cat3", "size": "40", "pairs": None},
            {"id": 4, "name": "Cat4", "size": "41", "pairs": None},
            {"id": 5, "name": "Cat5", "size": "42", "pairs": None},
        ]

        # Sessão ativa tem apenas 2 moldes legítimos
        sess_shapes = [
            {"id": 10, "name": "SessMolde1", "size": "40", "pairs": 12, "sequence": 1},
            {"id": 20, "name": "SessMolde2", "size": "41", "pairs": 12, "sequence": 2}
        ]
        win.current_session = {
            "id": 777,
            "shapes": sess_shapes,
            "layers": 4
        }

        # Mock da session_view
        mock_sv = MagicMock()
        mock_sv.shapes_list = sess_shapes
        mock_sv.is_refile_auto_active.return_value = False
        win.session_view = mock_sv

        # Mock queue com resultado de sucesso
        mock_q = MagicMock()
        nest_res = {
            "layouts": [
                {
                    "layout_index": 0,
                    "layers": 4,
                    "pieces": [
                        {"shape": {"id": 10, "name": "SessMolde1", "size": "40"}},
                        {"shape": {"id": 20, "name": "SessMolde2", "size": "41"}}
                    ]
                }
            ]
        }
        mock_q.get_nowait.return_value = ("SUCCESS", nest_res)

        MainWindow._poll_nest_worker(win, mock_q, strategy="flashnestsheet", params="stdNOTFill", machine="Flex", layers=4)

        # Verifica que update_session_shapes foi chamado com os 2 moldes da sessão, NUNCA com os 5 do catálogo!
        win.db.update_session_shapes.assert_called_once()
        call_args = win.db.update_session_shapes.call_args[0]
        assert call_args[0] == 777
        updated_shapes = call_args[1]
        assert len(updated_shapes) == 2
        assert updated_shapes[0]["id"] == 10
        assert updated_shapes[1]["id"] == 20

    def test_load_session_filters_ghost_shapes_when_layouts_present(self):
        """Garante que moldes fantasmas sem correspondência nas peças são podados em load_session."""
        with patch.object(SessionView, "__init__", lambda self, *args, **kwargs: None):
            view = SessionView()
            view.db = None
            view.lbl_title = MagicMock()
            view.entry_sname = MagicMock()
            view.cb_strategy = MagicMock()
            view.cb_params = MagicMock()
            view.cb_params.__getitem__.return_value = ["stdNOTFill"]
            view.refresh_params_list = MagicMock()
            view.update_strategy_description = MagicMock()
            view.highlight_guide_matching = MagicMock()
            view._refresh_layer_2_widgets = MagicMock()
            view.update_summary_text = MagicMock()
            view.set_shapes_data = MagicMock()

            # Sessão com layout calculado de 1 peça (MoldeReal) e 1 molde fantasma (MoldeFantasma)
            session_data = {
                "id": 999,
                "name": "Sessao com Fantasma",
                "status": "Nested",
                "layouts": [
                    {
                        "layout_index": 0,
                        "pieces": [
                            {"name": "MoldeReal", "size": "41", "shape": {"id": 1, "name": "MoldeReal", "size": "41"}}
                        ]
                    }
                ],
                "shapes": [
                    {"id": 1, "name": "MoldeReal", "size": "41", "pairs": 10},
                    {"id": 99, "name": "MoldeFantasma", "size": "35", "pairs": 5}
                ]
            }

            view.load_session(session_data)

            # set_shapes_data deve ter recebido apenas o MoldeReal
            view.set_shapes_data.assert_called_once()
            passed_shapes = view.set_shapes_data.call_args[0][0]
            assert len(passed_shapes) == 1
            assert passed_shapes[0]["name"] == "MoldeReal"

    def test_scrubber_tool_removes_ghosts_and_restores_metadata(self, temp_db):
        """Testa o utilitário tools/scrub_all_sessions_shapes.py em banco real."""
        db, db_file = temp_db

        # Cria sessão 100 com layout de 2 peças legítimas
        sid = db.create_session(session_id=100, name="Sessao Corrompida", layers=4)

        legit_shape_in_piece = {
            "id": 10,
            "name": "MoldeBom",
            "size": "41",
            "pairs": 14,
            "sequence": 1,
            "target_pieces": 7,
            "folder": "pasta_a"
        }
        layout_pieces = [
            {"shape": legit_shape_in_piece, "name": "MoldeBom", "size": "41"},
            {"shape": legit_shape_in_piece, "name": "MoldeBom", "size": "41"}
        ]
        db.save_session_layouts(sid, [{"layout_index": 0, "layers": 4, "pieces": layout_pieces}])

        # Simula shapes_json corrompido: MoldeBom perdeu pairs/sequence (veio None) e foi adicionado MoldeFantasma
        corrupted_shapes = [
            {"id": 10, "name": "MoldeBom", "size": "41", "pairs": None, "sequence": None, "folder": "pasta_a"},
            {"id": 99, "name": "MoldeFantasma", "size": "33", "pairs": None, "sequence": None, "folder": "pasta_faca"}
        ]
        db.update_session_shapes(sid, corrupted_shapes)

        # Executa scrubber
        reports = scrub_sessions(db_path=db_file, dry_run=False, target_session_id=sid)

        assert len(reports) == 1
        rep = reports[0]
        assert rep["shapes_before"] == 2
        assert rep["shapes_after"] == 1
        assert "MoldeFantasma" in rep["ghosts_removed"]

        # Verifica banco após scrub
        cleaned = db.get_session_shapes(sid)
        assert len(cleaned) == 1
        assert cleaned[0]["name"] == "MoldeBom"
        assert cleaned[0]["pairs"] == 14
        assert cleaned[0]["sequence"] == 1
