"""
Testes Unitários: Classificação e Ordenação de Moldes e Tamanhos (Maior para Menor / Menor para Maior)
"""
import unittest
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from ui.sort_utils import size_sort_key, natural_sort_key, shape_area_sort_key


class TestShapeSorting(unittest.TestCase):
    def setUp(self):
        # Dados reais extraídos da captura de tela do usuário (media_1792325929251.png)
        self.user_sample_shapes = [
            {"id": 1, "size": "36a", "name": "323_PalAcb_36a", "pairs": 16, "sequence": 1},
            {"id": 2, "size": "23a", "name": "323_PalAcb_23a", "pairs": 16, "sequence": 2},
            {"id": 3, "size": "24a", "name": "323_PalAcb_24a", "pairs": 16, "sequence": 3},
            {"id": 4, "size": "25a", "name": "323_PalAcb_25a", "pairs": 16, "sequence": 4},
            {"id": 5, "size": "26a", "name": "323_PalAcb_26a", "pairs": 16, "sequence": 5},
            {"id": 6, "size": "27a", "name": "323_PalAcb_27a", "pairs": 16, "sequence": 6},
            {"id": 7, "size": "22a", "name": "323_PalAcb_22a", "pairs": 16, "sequence": 7},  # Fora de ordem
            {"id": 8, "size": "28a", "name": "323_PalAcb_28a", "pairs": 16, "sequence": 8},
            {"id": 9, "size": "29a", "name": "323_PalAcb_29a", "pairs": 16, "sequence": 9},
            {"id": 10, "size": "30a", "name": "323_PalAcb_30a", "pairs": 16, "sequence": 10},
            {"id": 11, "size": "31a", "name": "323_PalAcb_31a", "pairs": 16, "sequence": 11},
            {"id": 12, "size": "32a", "name": "323_PalAcb_32a", "pairs": 16, "sequence": 12},
            {"id": 13, "size": "33a", "name": "323_PalAcb_33a", "pairs": 16, "sequence": 13},
            {"id": 14, "size": "34a", "name": "323_PalAcb_34a", "pairs": 16, "sequence": 14},
            {"id": 15, "size": "35a", "name": "323_PalAcb_35a", "pairs": 16, "sequence": 15},
        ]

    def test_sort_size_descending_user_screenshot(self):
        """Testa ordenação do maior para o menor nos tamanhos da captura do usuário (36a -> 22a)."""
        sorted_desc = sorted(
            self.user_sample_shapes,
            key=lambda s: size_sort_key(s["size"], s["name"]),
            reverse=True
        )
        sizes_desc = [s["size"] for s in sorted_desc]
        expected_desc = [
            "36a", "35a", "34a", "33a", "32a", "31a", "30a",
            "29a", "28a", "27a", "26a", "25a", "24a", "23a", "22a"
        ]
        self.assertEqual(sizes_desc, expected_desc, "Tamanhos devem estar ordenados estritamente do maior para o menor")

    def test_sort_size_ascending_user_screenshot(self):
        """Testa ordenação do menor para o maior nos tamanhos da captura do usuário (22a -> 36a)."""
        sorted_asc = sorted(
            self.user_sample_shapes,
            key=lambda s: size_sort_key(s["size"], s["name"]),
            reverse=False
        )
        sizes_asc = [s["size"] for s in sorted_asc]
        expected_asc = [
            "22a", "23a", "24a", "25a", "26a", "27a", "28a",
            "29a", "30a", "31a", "32a", "33a", "34a", "35a", "36a"
        ]
        self.assertEqual(sizes_asc, expected_asc, "Tamanhos devem estar ordenados estritamente do menor para o maior")

    def test_natural_sort_mold_names(self):
        """Testa ordenação alfanumérica natural dos nomes de moldes (Z->A e A->Z)."""
        sorted_names_desc = sorted(
            self.user_sample_shapes,
            key=lambda s: natural_sort_key(s["name"]),
            reverse=True
        )
        names_desc = [s["name"] for s in sorted_names_desc]
        self.assertEqual(names_desc[0], "323_PalAcb_36a")
        self.assertEqual(names_desc[-1], "323_PalAcb_22a")

    def test_size_sort_key_edge_cases(self):
        """Testa casos de borda: frações, decimais, emojis de cor e sufixos."""
        # Fração 37 1/2 vs 37 vs 38
        self.assertGreater(size_sort_key("37 1/2"), size_sort_key("37"))
        self.assertLess(size_sort_key("37 1/2"), size_sort_key("38"))
        self.assertEqual(size_sort_key("37 1/2")[1], 37.5)

        # Decimal 35.5a vs 36
        self.assertLess(size_sort_key("35.5a"), size_sort_key("36"))
        self.assertGreater(size_sort_key("35.5a"), size_sort_key("35"))

        # Emoji de cor pré-fixado (como exibido na interface: ⬛ 36a)
        k_with_emoji = size_sort_key("⬛ 36a")
        k_clean = size_sort_key("36a")
        self.assertEqual(k_with_emoji[1], k_clean[1])
        self.assertEqual(k_with_emoji[2], k_clean[2])

        # Extração de tamanho a partir do nome do molde quando size estiver vazio
        k_from_name = size_sort_key("", "Modelo_Derby_41")
        self.assertEqual(k_from_name[1], 41.0)

    def test_shape_area_sort_key(self):
        """Testa ordenação por área geométrica de contornos de moldes."""
        small_box = {"contour": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}, {"x": 0, "y": 10}]}
        large_box = {"contour": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}]}
        
        self.assertEqual(shape_area_sort_key(small_box), 100.0)
        self.assertEqual(shape_area_sort_key(large_box), 10000.0)
        self.assertGreater(shape_area_sort_key(large_box), shape_area_sort_key(small_box))


class DummyKeyEvent:
    def __init__(self, char="", keysym=""):
        self.char = char
        self.keysym = keysym


class TestSessionViewInlineArrowNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        try:
            cls.root = tk.Tk()
            cls.root.geometry("800x600")
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
        from ui.session_view import SessionView
        self.saved_sessions = []
        self.session_data = {
            "id": 42,
            "name": "Sessão Teste Digitação",
            "status": "Stand by",
            "shapes": [
                {"id": 10, "name": "Molde_36", "size": "36", "pairs": 16, "sequence": 1},
                {"id": 11, "name": "Molde_35", "size": "35", "pairs": 16, "sequence": 2},
                {"id": 12, "name": "Molde_34", "size": "34", "pairs": 16, "sequence": 3},
            ]
        }
        self.sv = SessionView(
            self.root,
            session_data=self.session_data,
            on_add_shapes=lambda sid, shapes: self.saved_sessions.append((sid, list(shapes)))
        )
        self.sv.pack()
        self.sv.load_session(self.session_data)
        self.sv.notebook.select(1)  # Aba Moldes
        self.root.update()

    def tearDown(self):
        try:
            self.sv.destroy()
        except Exception:
            pass

    def test_inline_editor_arrows_down_and_up_data_entry(self):
        """Testa digitação contínua de pares descendo e subindo pelas setas do teclado."""
        import time
        # 1. Abre inline editor na linha 0, coluna #5 (Pares...)
        self.sv.spawn_tree_inline_editor("0", "#5")
        self.root.update()
        entry = self.sv._inline_editor
        self.assertIsNotNone(entry, "Editor inline deve estar aberto")
        self.assertEqual(entry.get(), "16")

        # 2. Usuário digita 100 na primeira linha e pressiona Seta para Baixo (<Down>)
        entry.delete(0, "end")
        entry.insert(0, "100")
        entry.focus_force()
        entry.event_generate("<Down>", when="now")
        time.sleep(0.06)
        self.root.update()

        # Verifica se linha 0 salvou 100
        self.assertEqual(self.sv.shapes_list[0]["pairs"], 100)
        self.assertEqual(self.sv.tree_shapes.set("0", "pares"), "100")

        # 3. Editor agora deve estar aberto na linha 1
        entry_row1 = self.sv._inline_editor
        self.assertIsNotNone(entry_row1, "Editor inline deve ter avançado para linha 1")
        self.assertEqual(entry_row1.get(), "16")

        # Usuário digita 24 e pressiona <Return> (também desce)
        entry_row1.delete(0, "end")
        entry_row1.insert(0, "24")
        entry_row1.focus_force()
        entry_row1.event_generate("<Return>", when="now")
        time.sleep(0.06)
        self.root.update()

        # Verifica se linha 1 salvou 24
        self.assertEqual(self.sv.shapes_list[1]["pairs"], 24)
        self.assertEqual(self.sv.tree_shapes.set("1", "pares"), "24")

        # 4. Editor agora está na linha 2 (última linha)
        entry_row2 = self.sv._inline_editor
        self.assertIsNotNone(entry_row2, "Editor inline deve estar na linha 2")
        entry_row2.delete(0, "end")
        entry_row2.insert(0, "50")

        # Usuário pressiona Seta para Cima (<Up>) para voltar e corrigir a linha 1
        entry_row2.focus_force()
        entry_row2.event_generate("<Up>", when="now")
        time.sleep(0.06)
        self.root.update()

        # Verifica se linha 2 salvou 50
        self.assertEqual(self.sv.shapes_list[2]["pairs"], 50)
        self.assertEqual(self.sv.tree_shapes.set("2", "pares"), "50")

        # Editor deve ter voltado para a linha 1
        entry_back = self.sv._inline_editor
        self.assertIsNotNone(entry_back, "Editor inline deve ter retornado para a linha 1")
        self.assertEqual(entry_back.get(), "24")

        # Callback de persistência foi chamado com sucesso
        self.assertGreaterEqual(len(self.saved_sessions), 3)

    def test_treeview_direct_digit_entry(self):
        """Testa iniciar digitação imediata ao pressionar número no teclado sobre a linha selecionada."""
        self.sv.tree_shapes.selection_set("1")
        self.sv.tree_shapes.focus("1")
        self.root.update()

        # Simula usuário pressionando tecla '8'
        res = self.sv.on_tree_shape_key(DummyKeyEvent(char="8", keysym="8"))
        self.assertEqual(res, "break")
        self.root.update()

        entry = self.sv._inline_editor
        self.assertIsNotNone(entry, "Editor inline deve abrir imediatamente ao teclar número")
        self.assertEqual(entry.get(), "8", "Dígito inicial teclado deve constar no editor")

    def test_inline_editor_quick_adjust_increment(self):
        """Testa ajuste incremental rápido com Ctrl/Alt Up/Down."""
        self.sv.spawn_tree_inline_editor("0", "#5")
        self.root.update()
        entry = self.sv._inline_editor
        entry.delete(0, "end")
        entry.insert(0, "16")
        entry.focus_force()

        entry.event_generate("<Control-Up>", when="now")
        self.root.update()
        self.assertEqual(entry.get(), "17", "Control-Up deve incrementar o valor em +1")

        entry.event_generate("<Control-Down>", when="now")
        self.root.update()
        self.assertEqual(entry.get(), "16", "Control-Down deve decrementar o valor em -1")


if __name__ == "__main__":
    unittest.main()

