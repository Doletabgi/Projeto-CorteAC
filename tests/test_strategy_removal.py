"""
Testes automatizados para validação da remoção da estratégia flashnestroll (bobinas contínuas):
- flashnestroll removida das opções de SessionView (cb_strategy)
- flashnestroll removida das opções de OptionsDialog (cb_strategy)
- Normalização transparente de flashnestroll -> flashnestsheet ao carregar sessão legada
- Normalização transparente de flashnestroll -> flashnestsheet no OptionsDialog
- Comportamento de nesting_engine operando 100% em chapas/placas (is_roll=False)
"""

import unittest
from unittest.mock import MagicMock
import tkinter as tk

from ui.session_view import SessionView
from ui.options_dialog import OptionsDialog
from cad.nesting_engine import auto_nest_pieces


class TestStrategyRemoval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.root:
            self.skipTest("Tkinter display not available")

    def test_session_view_strategies_excludes_flashnestroll(self):
        """Verifica que SessionView não oferece flashnestroll e inclui apenas estratégias de chapas/fitas/retalhos."""
        mock_db = MagicMock()
        session_dict = {
            "id": 1,
            "name": "Teste Sessao",
            "status": "Open",
            "strategy": "sint",
            "shapes": [],
            "placed_pieces": []
        }
        sv = SessionView(self.root, session_dict, db=mock_db)
        values = list(sv.cb_strategy["values"])
        self.assertNotIn("flashnestroll", values)
        self.assertEqual(values, ["sint", "tape_a", "flashnestsheet", "freenest", "IA-teste"])
        sv.destroy()

    def test_session_view_normalizes_legacy_flashnestroll(self):
        """Sessão legada gravada como flashnestroll deve normalizar automaticamente para flashnestsheet."""
        mock_db = MagicMock()
        session_dict = {
            "id": 2,
            "name": "Sessao Legada Rolo",
            "status": "Open",
            "strategy": "flashnestroll",
            "shapes": [],
            "placed_pieces": []
        }
        sv = SessionView(self.root, session_dict, db=mock_db)
        self.assertEqual(sv.cb_strategy.get(), "flashnestsheet")
        self.assertEqual(sv.session_data.get("strategy"), "flashnestsheet")

        # Testa também ao chamar load_session diretamente
        sv.load_session({"id": 3, "strategy": "flashnestroll", "shapes": [], "placed_pieces": []})
        self.assertEqual(sv.cb_strategy.get(), "flashnestsheet")
        self.assertEqual(sv.session_data.get("strategy"), "flashnestsheet")
        sv.destroy()

    def test_options_dialog_excludes_flashnestroll(self):
        """Verifica que OptionsDialog não oferece flashnestroll no combobox de estratégia padrão."""
        mock_db = MagicMock()
        mock_db.get_all_settings.return_value = {"default_strategy": "flashnestroll"}
        dlg = OptionsDialog(self.root, db=mock_db)
        values = list(dlg.cb_strategy["values"])
        self.assertNotIn("flashnestroll", values)
        self.assertEqual(values, ["sint", "tape_a", "flashnestsheet", "std"])
        # Normalização de settings legados
        self.assertEqual(dlg.cb_strategy.get(), "flashnestsheet")
        dlg.destroy()

    def test_nesting_engine_operates_on_sheet(self):
        """Garante que auto_nest_pieces calcula corretamente em chapas sem depender de flashnestroll."""
        sample_shape = {
            "id": 1,
            "name": "Sola",
            "contour": [{"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 0.0}, {"x": 100.0, "y": 50.0}, {"x": 0.0, "y": 50.0}],
            "sequence": 1,
            "pairs": 5
        }
        placed = auto_nest_pieces(
            [sample_shape],
            bed_width_mm=500.0,
            bed_height_mm=400.0,
            target_count=6,
            strategy="flashnestsheet",
            params="ALTERNADO"
        )
        self.assertTrue(len(placed) > 0)
        for p in placed:
            self.assertIn("x", p)
            self.assertIn("y", p)

    def test_session_view_has_recommended_combinations_table(self):
        """Valida que o Guia de Combinações Recomendadas foi removido da tela do SessionView a pedido da fábrica."""
        mock_db = MagicMock()
        session_dict = {
            "id": 1,
            "name": "Teste Sessao Guia",
            "status": "Open",
            "strategy": "sint",
            "params": "stdNOTFill",
            "shapes": [],
            "placed_pieces": []
        }
        sv = SessionView(self.root, session_dict, db=mock_db)
        self.assertFalse(hasattr(sv, "tree_guide"))
        sv.destroy()

    def test_strategy_label_and_descriptions(self):
        """Valida que o label de estratégia e as descrições definem a geometria física do corte e do material."""
        mock_db = MagicMock()
        session_dict = {
            "id": 1,
            "name": "Teste Sessao",
            "status": "Open",
            "strategy": "freenest",
            "shapes": [],
            "placed_pieces": []
        }
        sv = SessionView(self.root, session_dict, db=mock_db)

        # Encontra o label acima do combobox cb_strategy
        parent = sv.cb_strategy.master
        labels = [w for w in parent.winfo_children() if isinstance(w, tk.Label)]
        label_texts = [lbl.cget("text") for lbl in labels]
        self.assertIn("A Estratégia define a geometria física do corte e do material:", label_texts)

        # Encontra o label de parâmetros dentro de params_header
        hdr_labels = []
        for w in parent.winfo_children():
            if isinstance(w, tk.Frame):
                hdr_labels.extend([subw.cget("text") for subw in w.winfo_children() if isinstance(subw, tk.Label)])
        self.assertIn("O Parâmetro define o comportamento das rotações, folgas e preenchimento da chapa:", hdr_labels)

        # Verifica descrição dinâmica
        self.assertIn("A Estratégia define a geometria física do corte e do material", sv.lbl_strategy_desc.cget("text"))

        sv.destroy()


if __name__ == "__main__":
    unittest.main()

