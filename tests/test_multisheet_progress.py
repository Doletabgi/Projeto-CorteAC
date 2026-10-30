"""
tests/test_multisheet_progress.py - Suíte de testes para a Fase 6.6 (Multi-sheet e Progresso Determinado)
"""

import os
import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk

from database import DatabaseManager
from cad.nesting_engine import nest_multi_sheet
from cad.nesting_backend import NfpBackend, get_nesting_backend
from ui.session_view import SessionView


class TestMultiSheetProgress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None
        cls.db = DatabaseManager()

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass
            cls.root = None

    def setUp(self):
        # Molde retangular 100x100 mm
        self.box_100 = [
            {"x": 0.0, "y": 0.0},
            {"x": 100.0, "y": 0.0},
            {"x": 100.0, "y": 100.0},
            {"x": 0.0, "y": 100.0},
        ]
        self.shape_item = {
            "id": 1,
            "name": "Box100",
            "size": "41",
            "pairs": 50,  # 50 pares = 50 peças em 2 camadas
            "sequence": 1,
            "contour": self.box_100,
        }

    def test_nest_multi_sheet_progress_callback_called(self):
        """Valida que o progress_callback é chamado a cada placa gerada."""
        calls = []

        def callback(cur, tot):
            calls.append((cur, tot))

        res = nest_multi_sheet(
            available_shapes=[self.shape_item],
            bed_width_mm=300.0,
            bed_height_mm=300.0,
            strategy="flashnestsheet",
            params="FastNest",
            gap_mm=1.0,
            layers=2,
            max_sheets=50,
            progress_callback=callback,
        )

        self.assertTrue(res["success"])
        self.assertGreater(len(calls), 1, "Deve gerar múltiplas placas e chamar o callback")
        self.assertEqual(len(calls), res["num_sheets"])
        # Primeira chamada inicia no índice 0
        self.assertEqual(calls[0], (0, 50))
        # Chamadas consecutivas incrementam sheet_idx
        for idx, call in enumerate(calls):
            self.assertEqual(call[0], idx)
            self.assertEqual(call[1], 50)

    def test_nest_multi_sheet_progress_callback_exception_handling(self):
        """Valida que exceção levantada dentro do callback não interrompe o nesting."""
        def buggy_callback(cur, tot):
            raise RuntimeError("Erro intencional no callback")

        res = nest_multi_sheet(
            available_shapes=[self.shape_item],
            bed_width_mm=1000.0,
            bed_height_mm=1000.0,
            strategy="flashnestsheet",
            params="FastNest",
            gap_mm=1.0,
            layers=2,
            progress_callback=buggy_callback,
        )

        self.assertTrue(res["success"])
        self.assertGreater(res["total_pieces"], 0)

    def test_session_view_update_progress_text(self):
        """Valida método update_progress_text da SessionView e exibição 'chapa X de Y'."""
        if not self.root:
            self.skipTest("Ambiente gráfico Tkinter indisponível")

        sess_data = {
            "id": 888,
            "name": "Sessão Teste Progresso Determinado",
            "status": "Stand by",
            "shapes": [],
            "placed_pieces": [],
            "layouts": [],
        }
        sv = SessionView(self.root, session_data=sess_data, db=self.db)

        # Chama com valores determinados
        sv.update_progress_text(3, 25)
        self.assertEqual(sv.lbl_progress.cget("text"), "Calculando chapa 3 de 25...")
        self.assertEqual(sv.frame_progress.winfo_manager(), "pack")

        # Chama com 0 (0-indexed) e valida normalização para 1
        sv.update_progress_text(0, 20)
        self.assertEqual(sv.lbl_progress.cget("text"), "Calculando chapa 1 de 20...")

        sv.destroy()

    def test_nfp_backend_constants_and_timeout(self):
        """Valida as constantes de segurança e timeout no NfpBackend."""
        backend = NfpBackend()
        self.assertEqual(backend.MAX_TRIES_PER_PIECE, 30)
        self.assertEqual(backend.FASTNEST_MAX_TRIES_PER_PIECE, 50)
        self.assertEqual(backend.SHEET_TIMEOUT_SEC, 5.0)

        # Simula timeout de chapa extremamente curto (0.0001s)
        shapes = [dict(self.shape_item) for _ in range(5)]
        dieproc_params = {"sheet_timeout_sec": 0.00001}
        placed = backend.nest_sheet(
            available_shapes=shapes,
            bed_width_mm=1000.0,
            bed_height_mm=1000.0,
            target_count=50,
            strategy="flashnestsheet",
            params="FastNest",
            dieproc_params=dieproc_params,
        )
        # Timeout deve retornar com segurança uma lista (possivelmente parcial ou vazia) sem lançar erro
        self.assertIsInstance(placed, list)


if __name__ == "__main__":
    unittest.main()
