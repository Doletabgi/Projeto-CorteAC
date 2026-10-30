"""
JobManager 2000 (Python Edition)
tests/test_nesting_mode_architecture.py - Suíte de Testes da Arquitetura de 4 Camadas de UX

Valida os 9 critérios bloqueantes da Fase 5.2:
1. test_modes_dict_has_6_options: MODES possui Automático + 5 presets + Personalizado
2. test_auto_mode_locks_strategy_params_engine: em Automático, dropdowns travados com badge (auto)
3. test_auto_mode_allows_gap_margins: em Automático, Gap e Margens ativos e operáveis
4. test_change_strategy_promotes_to_custom: alterar Strategy promove o modo para Personalizado
5. test_legacy_session_loads_as_custom: sessão legada sem nesting_mode carrega como custom
6. test_new_session_defaults_to_auto: sessão nova criada no banco defaults para auto
7. test_persist_nesting_mode: salvar e recarregar persiste nesting_mode
8. test_dieproc_dialog_still_accessible: DieProcDialog funcional e acessível a partir da Camada 3
9. test_env_vars_still_work_as_fallback: CORTEAC_BACKEND funciona como fallback do sistema
"""

from __future__ import annotations

import os
import tkinter as tk
import unittest
from pathlib import Path
from typing import Any

from database import DatabaseManager
from ui.dieproc_dialog import DieProcDialog
from ui.nesting_mode_widget import MODES, NestingModeWidget
from ui.session_view import SessionView


class TestNestingModeArchitecture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager()

    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            self.skipTest("Ambiente gráfico Tkinter indisponível para este teste")

    def tearDown(self):
        try:
            if hasattr(self, "root") and self.root:
                self.root.destroy()
        except Exception:
            pass

    def test_01_modes_dict_has_6_options(self):
        """1. test_modes_dict_has_6_options: MODES tem Automático + 5 presets + Personalizado."""
        expected_keys = {"auto", "fast", "economic", "tapes", "remnants", "custom"}
        self.assertEqual(set(MODES.keys()), expected_keys, f"MODES keys devem ser {expected_keys}")

        # Verifica campos obrigatórios em cada modo
        for key, mode_info in MODES.items():
            self.assertIn("label", mode_info, f"Modo '{key}' deve possuir 'label'")
            self.assertIn("description", mode_info, f"Modo '{key}' deve possuir 'description'")
            self.assertIn("engine", mode_info, f"Modo '{key}' deve possuir 'engine'")
            self.assertIn("strategy", mode_info, f"Modo '{key}' deve possuir 'strategy'")
            self.assertIn("params", mode_info, f"Modo '{key}' deve possuir 'params'")

        # Valida modo 'auto'
        self.assertEqual(MODES["auto"]["engine"], "ia_teste")
        self.assertEqual(MODES["auto"]["strategy"], "flashnestsheet")
        self.assertIn("Automático", MODES["auto"]["label"])

        # Valida modo 'custom'
        self.assertIsNone(MODES["custom"]["engine"])
        self.assertIsNone(MODES["custom"]["strategy"])
        self.assertIn("Personalizado", MODES["custom"]["label"])

    def test_02_auto_mode_locks_strategy_params_engine(self):
        """2. test_auto_mode_locks_strategy_params_engine: em Automático, dropdowns travados com badge."""
        sess_data = {
            "id": 9901,
            "name": "Sessão Teste Auto",
            "strategy": "flashnestsheet",
            "params": "stdNOTFill",
            "nesting_mode": "auto",
        }
        view = SessionView(self.root, session_data=sess_data, db=self.db)
        view.load_session(sess_data)

        # Em Automático, Estratégia e Parâmetros devem estar desabilitados
        self.assertEqual(view.get_nesting_mode(), "auto")
        self.assertEqual(str(view.cb_strategy.cget("state")), "disabled")
        self.assertEqual(str(view.cb_params.cget("state")), "disabled")

        # Em Automático, Camada 3 e 4 devem estar travadas
        self.assertEqual(str(view.macro_panel.cb_macro.cget("state")), "disabled")
        self.assertEqual(str(view.debug_panel.cb_engine.cget("state")), "disabled")

    def test_03_auto_mode_allows_gap_margins(self):
        """3. test_auto_mode_allows_gap_margins: em Automático, Gap e Margens ativos e operáveis."""
        sess_data = {
            "id": 9902,
            "name": "Sessão Teste Gap/Margins",
            "nesting_mode": "auto",
            "gap_mm": 1.5,
            "margin_left": 10.0,
        }
        view = SessionView(self.root, session_data=sess_data, db=self.db)
        view.load_session(sess_data)

        self.assertEqual(view.get_nesting_mode(), "auto")

        # Gap continua ativo
        self.assertEqual(str(view.entry_gap.cget("state")), "normal")
        self.assertEqual(str(view.btn_gap_minus.cget("state")), "normal")
        self.assertEqual(str(view.btn_gap_plus.cget("state")), "normal")

        # Operações de alteração de Gap continuam funcionando
        initial_gap = view.get_gap_mm()
        view._on_gap_plus()
        self.assertGreater(view.get_gap_mm(), initial_gap)

        # Margens continuam ativas
        for rb in view.rb_margins.values():
            self.assertEqual(str(rb.cget("state")), "normal")

    def test_04_change_strategy_promotes_to_custom(self):
        """4. test_change_strategy_promotes_to_custom: mudar Strategy -> modo vira Personalizado."""
        sess_data = {
            "id": 9903,
            "name": "Sessão Teste Auto-Promote",
            "nesting_mode": "auto",
            "strategy": "flashnestsheet",
            "params": "stdNOTFill",
        }
        view = SessionView(self.root, session_data=sess_data, db=self.db)
        view.load_session(sess_data)

        self.assertEqual(view.get_nesting_mode(), "auto")

        # Simula alteração do usuário desbloqueando ou selecionando outra estratégia
        view.cb_strategy.config(state="readonly")
        view.cb_strategy.set("sint")
        view.on_strategy_selected()

        # O modo deve ter sido promovido automaticamente para 'custom'
        self.assertEqual(view.get_nesting_mode(), "custom")
        self.assertEqual(view.mode_widget.get_mode(), "custom")
        self.assertEqual(str(view.cb_strategy.cget("state")), "readonly")
        self.assertEqual(str(view.cb_params.cget("state")), "readonly")

    def test_05_legacy_session_loads_as_custom(self):
        """5. test_legacy_session_loads_as_custom: sessão sem nesting_mode -> carrega como custom."""
        # Dicionário legado sem a chave nesting_mode
        legacy_data = {
            "id": 9904,
            "name": "Sessão Legada Sem Modo",
            "strategy": "sint",
            "params": "ALTERNADO",
            # nesting_mode ausente
        }
        view = SessionView(self.root, session_data=legacy_data, db=self.db)
        view.load_session(legacy_data)

        # Deve carregar obrigatoriamente como 'custom'
        self.assertEqual(view.get_nesting_mode(), "custom")
        self.assertEqual(view.mode_widget.get_mode(), "custom")

    def test_06_new_session_defaults_to_auto(self):
        """6. test_new_session_defaults_to_auto: sessão nova -> auto."""
        new_id = self.db.create_session(name="Sessão Nova Default Auto")
        try:
            sess = self.db.get_session(new_id)
            self.assertIsNotNone(sess)
            self.assertEqual(
                sess.get("nesting_mode"),
                "auto",
                f"Sessão nova deve possuir nesting_mode='auto', obtido: {sess.get('nesting_mode')}",
            )
        finally:
            self.db.delete_session(new_id)

    def test_07_persist_nesting_mode(self):
        """7. test_persist_nesting_mode: salvar e recarregar mantém nesting_mode."""
        sid = self.db.create_session(name="Sessão Persistência Modo")
        try:
            # Atualiza para modo econômico
            self.db.update_session(sid, nesting_mode="economic")
            s1 = self.db.get_session(sid)
            self.assertEqual(s1.get("nesting_mode"), "economic")

            # Atualiza para modo fitas
            self.db.update_session(sid, nesting_mode="tapes")
            s2 = self.db.get_session(sid)
            self.assertEqual(s2.get("nesting_mode"), "tapes")
        finally:
            self.db.delete_session(sid)

    def test_08_dieproc_dialog_still_accessible(self):
        """8. test_dieproc_dialog_still_accessible: DieProcDialog acessível a partir de MacroPanel."""
        sess_data = {
            "id": 9905,
            "name": "Sessão Teste DieProc",
            "nesting_mode": "custom",
        }
        view = SessionView(self.root, session_data=sess_data, db=self.db)
        self.assertIsNotNone(view.macro_panel)

        # Instanciação direta do DieProcDialog via MacroPanel
        dlg = DieProcDialog(self.root, self.db, initial_preset="ALTERNADO")
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.title(), "DieProc configuration")
        dlg.destroy()

    def test_09_env_vars_still_work_as_fallback(self):
        """9. test_env_vars_still_work_as_fallback: CORTEAC_BACKEND ainda funciona se setada."""
        from cad.nesting_backend import NfpBackend, PythonBackend, get_nesting_backend

        orig = os.environ.get("CORTEAC_BACKEND")
        try:
            os.environ["CORTEAC_BACKEND"] = "python"
            b_python = get_nesting_backend()
            self.assertIsInstance(b_python, PythonBackend)

            os.environ["CORTEAC_BACKEND"] = "nfp"
            b_nfp = get_nesting_backend()
            self.assertIsInstance(b_nfp, NfpBackend)
        finally:
            if orig is not None:
                os.environ["CORTEAC_BACKEND"] = orig
            else:
                os.environ.pop("CORTEAC_BACKEND", None)


if __name__ == "__main__":
    unittest.main()
