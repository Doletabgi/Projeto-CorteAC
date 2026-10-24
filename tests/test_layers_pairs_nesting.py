"""
Testes unitários para validação da regra de camadas (layers) no cálculo de peças
do layout e contadores da barra lateral (20/20 0/20).
"""
import math
import unittest
from unittest.mock import MagicMock
from cad.nesting_engine import auto_nest_pieces, dieproc_nest_pieces, nest_synthetic_engine


class TestLayersPairsNesting(unittest.TestCase):
    def setUp(self):
        # Retângulo simples 50x50 para testes rápidos
        self.sample_contour = [
            {"x": 0.0, "y": 0.0},
            {"x": 50.0, "y": 0.0},
            {"x": 50.0, "y": 50.0},
            {"x": 0.0, "y": 50.0}
        ]
        self.shape_20_pairs = {
            "id": 1,
            "name": "Molde_Teste_22a",
            "size": "22a",
            "pairs": 20,
            "sequence": 1,
            "contour": self.sample_contour
        }

    def test_layers_2_creates_20_pieces_for_20_pairs(self):
        """Com 2 camadas, 20 pares solicitados devem gerar 20 peças no layout."""
        layers = 2
        req_pairs = self.shape_20_pairs["pairs"]
        expected_qty = math.ceil((req_pairs * 2) / layers)
        self.assertEqual(expected_qty, 20)

        # Mesa grande o suficiente para acomodar 20 peças
        pieces = auto_nest_pieces(
            [self.shape_20_pairs],
            bed_width_mm=1000.0,
            bed_height_mm=1000.0,
            target_count=20,
            strategy="flashnestsheet",
            layers=layers
        )
        self.assertEqual(len(pieces), 20)
        self.assertTrue(all(p.get("size") == "22a" for p in pieces))

    def test_layers_1_creates_40_pieces_for_20_pairs(self):
        """Com 1 camada, 20 pares solicitados devem gerar 40 peças no layout."""
        layers = 1
        req_pairs = self.shape_20_pairs["pairs"]
        expected_qty = math.ceil((req_pairs * 2) / layers)
        self.assertEqual(expected_qty, 40)

        pieces = auto_nest_pieces(
            [self.shape_20_pairs],
            bed_width_mm=1000.0,
            bed_height_mm=1000.0,
            target_count=40,
            strategy="flashnestsheet",
            layers=layers
        )
        self.assertEqual(len(pieces), 40)

    def test_sidebar_counter_formula_layers_4(self):
        """Verifica a lógica de exibição de contadores com 4 camadas (ex: 10/20 0/20)."""
        layers = 4
        req_pairs = 20

        # Caso 1: 10 peças colocadas no layout geram 20 pares -> 10/20 0/20
        placed_pieces = 10
        placed_pairs = (placed_pieces * layers) // 2
        resto = max(0, req_pairs - placed_pairs)
        disp = f"{placed_pieces}/{req_pairs} {resto}/{req_pairs}"
        self.assertEqual(disp, "10/20 0/20")

        # Caso 2: 5 peças colocadas no layout geram 10 pares -> 5/20 10/20
        placed_pieces = 5
        placed_pairs = (placed_pieces * layers) // 2
        resto = max(0, req_pairs - placed_pairs)
        disp = f"{placed_pieces}/{req_pairs} {resto}/{req_pairs}"
        self.assertEqual(disp, "5/20 10/20")

        # Caso 3: 0 peças colocadas -> 0/20 20/20
        placed_pieces = 0
        placed_pairs = (placed_pieces * layers) // 2
        resto = max(0, req_pairs - placed_pairs)
        disp = f"{placed_pieces}/{req_pairs} {resto}/{req_pairs}"
        self.assertEqual(disp, "0/20 20/20")

    def test_sidebar_counter_formula_layers_2(self):
        """Verifica a lógica de exibição de contadores com 2 camadas (ex: 20/20 0/20)."""
        layers = 2
        req_pairs = 20

        # Caso 1: 20 peças colocadas no layout geram 20 pares -> 20/20 0/20
        placed_pieces = 20
        placed_pairs = (placed_pieces * layers) // 2
        resto = max(0, req_pairs - placed_pairs)
        disp = f"{placed_pieces}/{req_pairs} {resto}/{req_pairs}"
        self.assertEqual(disp, "20/20 0/20")

        # Caso 2: 10 peças colocadas no layout geram 10 pares -> 10/20 10/20
        placed_pieces = 10
        placed_pairs = (placed_pieces * layers) // 2
        resto = max(0, req_pairs - placed_pairs)
        disp = f"{placed_pieces}/{req_pairs} {resto}/{req_pairs}"
        self.assertEqual(disp, "10/20 10/20")

        # Caso 3: 0 peças colocadas -> 0/20 20/20
        placed_pieces = 0
        placed_pairs = (placed_pieces * layers) // 2
        resto = max(0, req_pairs - placed_pairs)
        disp = f"{placed_pieces}/{req_pairs} {resto}/{req_pairs}"
        self.assertEqual(disp, "0/20 20/20")

    def test_sidebar_counter_formula_layers_1(self):
        """Verifica a lógica de exibição de contadores com 1 camada (ex: 40/20 0/20)."""
        layers = 1
        req_pairs = 20

        # Com 1 camada, 40 peças colocadas no layout geram 20 pares -> 40/20 0/20
        placed_pieces = 40
        placed_pairs = (placed_pieces * layers) // 2
        resto = max(0, req_pairs - placed_pairs)
        disp = f"{placed_pieces}/{req_pairs} {resto}/{req_pairs}"
        self.assertEqual(disp, "40/20 0/20")


if __name__ == "__main__":
    unittest.main()
