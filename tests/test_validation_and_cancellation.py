"""
JobManager 2000 (Python Edition)
tests/test_validation_and_cancellation.py - Suíte de Testes da Fase 6.7

Valida os critérios da Fase 6.7:
1. Validação de dimensões da chapa > 10m no motor `nest_multi_sheet`.
2. Cancelamento imediato de cálculo via `cancel_check` (< 1 segundo).
3. Preservação de layouts parciais calculados ao cancelar.
4. Botão [ ⏹ Cancelar ] no `SessionView`, flag `_cancel_nest` e callbacks de cancelamento.
5. Proteção de sobrescrita de progresso durante cancelamento.
6. Conversão automática de unidades de mm para metros (valores > 10) no material da sessão.
"""

from __future__ import annotations

import time
import tkinter as tk
import unittest
from unittest.mock import MagicMock

from cad.nesting_engine import nest_multi_sheet
from database import DatabaseManager
from ui.session_view import SessionView


class TestValidationAndCancellation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager()

    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            self.skipTest("Ambiente gráfico Tkinter indisponível para este teste")

        self.sample_mat = {
            "id": "853412",
            "code": "853412",
            "name": "Sintético Padrão",
            "width_mm": 1380.0,
            "height_mm": 1080.0,
            "layers": 2,
            "thickness": 0.0,
            "gap": 1.0,
            "quantity": 100
        }

        self.sess_data = {
            "id": 888,
            "name": "Sessão Validação e Cancelamento",
            "status": "Stand by",
            "material": self.sample_mat,
            "shapes": [],
            "placed_pieces": [],
            "layouts": [],
        }

        self.sample_shape = {
            "id": 1,
            "name": "Peça_Teste",
            "contour": [
                {"x": 0.0, "y": 0.0},
                {"x": 100.0, "y": 0.0},
                {"x": 100.0, "y": 80.0},
                {"x": 0.0, "y": 80.0},
            ],
            "pairs": 50,
            "sequence": 1,
            "layers": 2,
            "size": "41"
        }

    def tearDown(self):
        try:
            if hasattr(self, "root") and self.root:
                self.root.destroy()
        except Exception:
            pass

    def test_nest_multi_sheet_rejects_bed_width_over_10m(self):
        """Valida que nest_multi_sheet recusa cálculo se largura da chapa for > 10.000 mm (10m)."""
        result = nest_multi_sheet(
            available_shapes=[self.sample_shape],
            bed_width_mm=13800.0,  # 13.8 metros (erro típico de digitação mm no lugar de m)
            bed_height_mm=1080.0,
            max_sheets=10
        )
        self.assertFalse(result["success"])
        self.assertFalse(result["cancelled"])
        self.assertEqual(result["num_sheets"], 0)
        self.assertIn("10 metros", result["warning"])

    def test_nest_multi_sheet_rejects_bed_height_over_10m(self):
        """Valida que nest_multi_sheet recusa cálculo se altura da chapa for > 10.000 mm (10m)."""
        result = nest_multi_sheet(
            available_shapes=[self.sample_shape],
            bed_width_mm=1380.0,
            bed_height_mm=15000.0,  # 15 metros
            max_sheets=10
        )
        self.assertFalse(result["success"])
        self.assertFalse(result["cancelled"])
        self.assertEqual(result["num_sheets"], 0)
        self.assertIn("10 metros", result["warning"])

    def test_nest_multi_sheet_cancel_immediate(self):
        """Valida cancelamento antes mesmo de iniciar o loop de cálculo."""
        result = nest_multi_sheet(
            available_shapes=[self.sample_shape],
            bed_width_mm=1380.0,
            bed_height_mm=1080.0,
            cancel_check=lambda: True
        )
        self.assertFalse(result["success"])
        self.assertTrue(result["cancelled"])
        self.assertEqual(result["num_sheets"], 0)
        self.assertIn("cancelado pelo operador", result["warning"])

    def test_nest_multi_sheet_cancel_aborts_in_under_one_second_with_partial_layouts(self):
        """Valida interrupção em menos de 1 segundo preservando layouts calculados até a interrupção."""
        shape_large = dict(self.sample_shape)
        shape_large["pairs"] = 300  # 300 pares exigirá múltiplas chapas

        current_sheet = 0

        def on_progress(sheet_idx, max_sheets):
            nonlocal current_sheet
            current_sheet = sheet_idx

        def check_cancel():
            # Cancela a partir da segunda chapa
            return current_sheet >= 1

        t0 = time.perf_counter()
        result = nest_multi_sheet(
            available_shapes=[shape_large],
            bed_width_mm=1380.0,
            bed_height_mm=1080.0,
            progress_callback=on_progress,
            cancel_check=check_cancel,
            max_sheets=50
        )
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 1.0, f"Cancelamento deve abortar em < 1 segundo (levou {elapsed:.3f}s)")
        self.assertTrue(result["cancelled"], "Resultado deve indicar status cancelado")
        self.assertFalse(result["success"], "Cálculo cancelado não deve reportar sucesso pleno")
        self.assertGreaterEqual(len(result["layouts"]), 1, "Layouts calculados antes do cancelamento devem ser preservados")

    def test_session_view_cancel_button_workflow(self):
        """Valida presença do botão Cancelar no frame_progress, disparo do callback e desativação."""
        cancel_called = False

        def on_cancel():
            nonlocal cancel_called
            cancel_called = True

        sv = SessionView(self.root, session_data=self.sess_data, db=self.db, on_cancel=on_cancel)

        # 1. Botão Cancelar existe
        self.assertTrue(hasattr(sv, "btn_action_cancel"))
        self.assertEqual(sv.btn_action_cancel.cget("text"), "⏹ Cancelar")

        # 2. Ao exibir progresso, botão está habilitado e flag é False
        sv.show_progress("Calculando teste...")
        self.assertFalse(sv._cancel_nest)
        self.assertEqual(sv.btn_action_cancel.cget("state"), "normal")

        # 3. Disparo do clique de cancelamento
        sv.btn_action_cancel.invoke()

        self.assertTrue(sv._cancel_nest, "Flag _cancel_nest deve ser ativada")
        self.assertTrue(cancel_called, "Callback on_cancel deve ser chamado")
        self.assertEqual(sv.lbl_progress.cget("text"), "Cancelando cálculo...")
        self.assertEqual(sv.btn_action_cancel.cget("state"), "disabled")

        # 4. Ao ocultar progresso, estado é restaurado
        sv.hide_progress()
        self.assertFalse(sv._cancel_nest)

        sv.destroy()

    def test_session_view_progress_text_does_not_overwrite_canceling(self):
        """Garante que ticks de progresso pendentes não sobrescrevam 'Cancelando cálculo...' após cancelamento."""
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db)
        sv.show_progress()
        sv.on_cancel_nest_click()

        self.assertEqual(sv.lbl_progress.cget("text"), "Cancelando cálculo...")

        # Simula tick de progresso vindo de worker em desligamento
        sv.update_progress_text(3, 10)
        self.assertEqual(sv.lbl_progress.cget("text"), "Cancelando cálculo...", "Texto não deve ser sobrescrito após cancel")

        sv.destroy()

    def test_session_view_update_material_cell_auto_conversion(self):
        """Valida que digitação de valores em mm (> 10) na célula do material converte automaticamente para metros."""
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db)
        sv.set_material_data(self.sample_mat)

        # Simula digitação de 1380 (mm) na largura
        sv.update_material_cell("width", "1380")
        items = sv.tree_mat.get_children()
        vals = sv.tree_mat.item(items[0], "values")
        self.assertEqual(vals[4], "1,38", "1380 mm deve converter automaticamente para 1,38m")

        # Simula digitação de 1080 (mm) no comprimento
        sv.update_material_cell("len", "1080")
        vals = sv.tree_mat.item(items[0], "values")
        self.assertEqual(vals[5], "1,08", "1080 mm deve converter automaticamente para 1,08m")

        sv.destroy()

    def test_session_view_notify_material_changed_safety(self):
        """Valida proteção e auto-ajuste de dimensões na notificação de alteração de material."""
        sv = SessionView(self.root, session_data=self.sess_data, db=self.db)
        sv.set_material_data(self.sample_mat)

        items = sv.tree_mat.get_children()
        curr_vals = list(sv.tree_mat.item(items[0], "values"))
        curr_vals[4] = "1500"  # 1500 mm
        curr_vals[5] = "2000"  # 2000 mm
        sv.tree_mat.item(items[0], values=curr_vals)

        sv.notify_material_changed()

        mat = sv.session_data["material"]
        self.assertEqual(mat["width_m"], 1.5)
        self.assertEqual(mat["length_m"], 2.0)
        self.assertEqual(mat["width_mm"], 1500.0)
        self.assertEqual(mat["height_mm"], 2000.0)

        sv.destroy()


if __name__ == "__main__":
    unittest.main()
