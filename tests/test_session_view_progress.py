"""
JobManager 2000 (Python Edition)
tests/test_session_view_progress.py - Suíte de Testes do Feedback Visual de Nesting (Fase 6.5)

Valida os critérios da Fase 6.5:
1. test_progress_bar_initial_state: Barra e label ocultos por padrão, botões ativos
2. test_progress_bar_appears_on_nest: Clique em [Gerar] exibe barra, anima e desabilita botões
3. test_progress_bar_hides_on_complete: hide_progress() oculta barra, restaura status e reabilita botões
4. test_double_click_prevention: Botões permanecem desabilitados durante o cálculo
5. test_custom_progress_text: show_progress aceita mensagens de status customizadas
"""

from __future__ import annotations

import tkinter as tk
import unittest
from unittest.mock import MagicMock

from database import DatabaseManager
from ui.session_view import SessionView


class TestSessionViewProgress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager()

    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            self.skipTest("Ambiente gráfico Tkinter indisponível para este teste")

        self.sess_data = {
            "id": 999,
            "name": "Sessão Teste Progresso",
            "status": "Stand by",
            "shapes": [],
            "placed_pieces": [],
            "layouts": [],
        }

    def tearDown(self):
        try:
            if hasattr(self, "root") and self.root:
                self.root.destroy()
        except Exception:
            pass

    def test_progress_bar_initial_state(self):
        """Valida que a barra de progresso inicia oculta e os botões estão em estado normal."""
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db)

        # 1. Widgets existem
        self.assertTrue(hasattr(sv, "frame_progress"), "SessionView deve possuir frame_progress")
        self.assertTrue(hasattr(sv, "progress_bar"), "SessionView deve possuir progress_bar")
        self.assertTrue(hasattr(sv, "lbl_progress"), "SessionView deve possuir lbl_progress")

        # 2. Modo indeterminate
        self.assertEqual(str(sv.progress_bar.cget("mode")), "indeterminate")

        # 3. Inicialmente oculto (sem gerenciador de geometria pack ativo)
        self.assertEqual(sv.frame_progress.winfo_manager(), "", "frame_progress deve iniciar oculto")

        # 4. Botões de ação habilitados
        self.assertEqual(sv.btn_action_nest.cget("state"), "normal")
        self.assertEqual(sv.btn_action_standby.cget("state"), "normal")
        self.assertEqual(sv.btn_action_rewind.cget("state"), "normal")

        sv.destroy()

    def test_progress_bar_appears_on_nest(self):
        """Simula o clique em Gerar e verifica se o frame de progresso ficou visível e os botões desabilitados."""
        cb_nest = MagicMock()
        sv = SessionView(self.root, session_data=self.sess_data, on_nest=cb_nest, db=self.db)

        # Clica no botão [Gerar]
        sv.btn_action_nest.invoke()

        # 1. Callback de nesting disparado
        cb_nest.assert_called_once()

        # 2. Frame de progresso agora está empacotado (visível)
        self.assertEqual(sv.frame_progress.winfo_manager(), "pack", "frame_progress deve estar visível via pack")

        # 3. Texto da label de progresso exibindo mensagem de cálculo
        self.assertIn("Calculando", sv.lbl_progress.cget("text"))

        # 4. Status da sessão alterado temporariamente
        self.assertEqual(sv.lbl_status_val.cget("text"), "Calculando...")

        # 5. Botões de ação desabilitados para prevenir concorrência / duplo clique
        self.assertEqual(sv.btn_action_nest.cget("state"), "disabled")
        self.assertEqual(sv.btn_action_standby.cget("state"), "disabled")
        self.assertEqual(sv.btn_action_rewind.cget("state"), "disabled")

        sv.destroy()

    def test_progress_bar_hides_on_complete(self):
        """Simula o final do cálculo e verifica se o frame sumiu e os botões voltaram ao normal."""
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db)

        # Inicia progresso
        sv.show_progress()
        self.assertEqual(sv.frame_progress.winfo_manager(), "pack")
        self.assertEqual(sv.btn_action_nest.cget("state"), "disabled")

        # Finaliza progresso
        sv.hide_progress()

        # 1. Frame de progresso oculto
        self.assertEqual(sv.frame_progress.winfo_manager(), "", "frame_progress deve ser ocultado")

        # 2. Botões de ação reabilitados
        self.assertEqual(sv.btn_action_nest.cget("state"), "normal")
        self.assertEqual(sv.btn_action_standby.cget("state"), "normal")
        self.assertEqual(sv.btn_action_rewind.cget("state"), "normal")

        # 3. Status restaurado para o valor prévio
        self.assertEqual(sv.lbl_status_val.cget("text"), "Stand by")

        sv.destroy()

    def test_double_click_prevention(self):
        """Verifica se os botões desabilitados impedem novos cliques concorrentes."""
        cb_nest = MagicMock()
        sv = SessionView(self.root, session_data=self.sess_data, on_nest=cb_nest, db=self.db)

        sv.show_progress()
        # Botões estão desabilitados
        self.assertEqual(sv.btn_action_nest.cget("state"), "disabled")

        sv.destroy()

    def test_custom_progress_text(self):
        """Verifica se o método show_progress aceita texto customizado."""
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db)

        custom_msg = "Otimizando percurso CAM em 3 placas..."
        sv.show_progress(custom_msg)

        self.assertEqual(sv.lbl_progress.cget("text"), custom_msg)
        sv.hide_progress()
        sv.destroy()


if __name__ == "__main__":
    unittest.main()
