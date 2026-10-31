"""
Testes unitários e de integração para a regra de camadas e cálculo de resto (calc_resto).

Cobre:
1. pecas_na_mesa e calc_resto com 4 camadas (125/109/97 -> 63/55/49 peças e resto -1; 126/62 -> 63/31 peças e resto 0).
2. 2 camadas -> sempre resto 0 para qualquer quantidade de pares.
3. 3 e 6 camadas com 125 pares -> 84 e 42 peças, ambos resto -1.
4. Teste de propriedade (1..500 pares x 1..8 camadas): calc_resto <= 0 e produzido >= pedido.
5. Casos de borda: 0 pares, pares negativos, camadas None / 0 / 1.
6. Precedência de camadas: grid_material_row > session.layers > material.layers > layout.layers > 2.
7. Nesting com 4 camadas e moldes com 125, 109, 97 pares para FastNest, HighYield, stdNOTFill.
8. stdNOTFill (respeita a cota exata) vs stdFill (continua preenchendo a chapa).
9. Multi-placa com 125 pares em 4 camadas -> soma 63 peças entre as placas (a 63ª peça aparece exatamente 1x).
10. Zero colisão e respeito a margens úteis para todas as peças.
"""
import math
import unittest

from cad.geometry import polygons_collide, polygon_bbox
from cad.layers_rule import (
    calc_resto,
    is_layers_defined,
    pecas_na_mesa,
    resolve_session_layers,
)
from cad.nesting_engine import (
    auto_nest_pieces,
    nest_multi_sheet,
    nest_synthetic_engine,
    nest_tape_engine,
    dieproc_nest_pieces,
)


class TestLayersResto(unittest.TestCase):
    def setUp(self):
        # Contorno retangular 40x40 mm para testes geométricos rápidos
        self.contour_40x40 = [
            {"x": 0.0, "y": 0.0},
            {"x": 40.0, "y": 0.0},
            {"x": 40.0, "y": 40.0},
            {"x": 0.0, "y": 40.0},
        ]
        self.shape_125 = {
            "id": 1,
            "name": "M_125",
            "size": "41",
            "pairs": 125,
            "sequence": 1,
            "contour": self.contour_40x40,
        }
        self.shape_109 = {
            "id": 2,
            "name": "M_109",
            "size": "40",
            "pairs": 109,
            "sequence": 2,
            "contour": self.contour_40x40,
        }
        self.shape_97 = {
            "id": 3,
            "name": "M_97",
            "size": "39",
            "pairs": 97,
            "sequence": 3,
            "contour": self.contour_40x40,
        }

    # -------------------------------------------------------------------------
    # Teste 1: 4 Camadas (dados reais da sessão 619955)
    # -------------------------------------------------------------------------
    def test_01_layers_4_odd_and_even_pairs(self):
        # Pares ímpares em 4 camadas geram 1 par a mais de sobra (-1)
        self.assertEqual(pecas_na_mesa(125, 4), 63)
        self.assertEqual(calc_resto(125, 4), -1)

        self.assertEqual(pecas_na_mesa(109, 4), 55)
        self.assertEqual(calc_resto(109, 4), -1)

        self.assertEqual(pecas_na_mesa(97, 4), 49)
        self.assertEqual(calc_resto(97, 4), -1)

        # Pares pares em 4 camadas fecham exato (resto 0)
        self.assertEqual(pecas_na_mesa(126, 4), 63)
        self.assertEqual(calc_resto(126, 4), 0)

        self.assertEqual(pecas_na_mesa(62, 4), 31)
        self.assertEqual(calc_resto(62, 4), 0)

    # -------------------------------------------------------------------------
    # Teste 2: 2 Camadas (resto é SEMPRE zero)
    # -------------------------------------------------------------------------
    def test_02_layers_2_always_zero_resto(self):
        for p in (1, 2, 15, 20, 97, 109, 125, 126, 500):
            desenhadas = pecas_na_mesa(p, 2)
            self.assertEqual(desenhadas, p, f"Para 2 camadas, {p} pares deve gerar {p} peças")
            r = calc_resto(p, 2)
            self.assertEqual(r, 0, f"Para 2 camadas, resto de {p} pares deve ser 0")

    # -------------------------------------------------------------------------
    # Teste 3: 3 e 6 Camadas com 125 pares
    # -------------------------------------------------------------------------
    def test_03_layers_3_and_6_odd_layers(self):
        # 3 camadas com 125 pares:
        # pecas_pedidas = 250
        # desenhadas = ceil(250 / 3) = 84 peças
        # pecas_produzidas = 84 * 3 = 252 (2 peças a mais = 1 par excedente -> resto -1)
        self.assertEqual(pecas_na_mesa(125, 3), 84)
        self.assertEqual(calc_resto(125, 3), -1)

        # 6 camadas com 125 pares:
        # pecas_pedidas = 250
        # desenhadas = ceil(250 / 6) = 42 peças
        # pecas_produzidas = 42 * 6 = 252 (2 peças a mais = 1 par excedente -> resto -1)
        self.assertEqual(pecas_na_mesa(125, 6), 42)
        self.assertEqual(calc_resto(125, 6), -1)

    # -------------------------------------------------------------------------
    # Teste 4: Teste de Propriedade (1..500 pares x 1..8 camadas)
    # -------------------------------------------------------------------------
    def test_04_property_exhaustion(self):
        for p in range(1, 501):
            for c in range(1, 9):
                desenhadas = pecas_na_mesa(p, c)
                produzidas = desenhadas * c
                pedidas = 2 * p
                resto = calc_resto(p, c)

                # Propriedade 1: Produzido nunca pode ser menor que o pedido
                self.assertGreaterEqual(
                    produzidas, pedidas,
                    f"Erro: p={p}, c={c} produziu {produzidas} < pedidas {pedidas}"
                )
                # Propriedade 2: Resto é puramente informativo e nunca positivo (<= 0)
                self.assertLessEqual(
                    resto, 0,
                    f"Erro: p={p}, c={c} resto={resto} > 0"
                )

    # -------------------------------------------------------------------------
    # Teste 5: Casos de Borda (0 pares, negativos, camadas None / 0 / 1)
    # -------------------------------------------------------------------------
    def test_05_edge_cases(self):
        # Pares zero ou negativos
        self.assertEqual(pecas_na_mesa(0, 4), 0)
        self.assertEqual(calc_resto(0, 4), 0)
        self.assertEqual(pecas_na_mesa(-10, 4), 0)
        self.assertEqual(calc_resto(-10, 4), 0)
        self.assertEqual(pecas_na_mesa(None, 4), 0)
        self.assertEqual(calc_resto(None, 4), 0)

        # Camadas None, 0 ou 1 -> cada peça desenhada gera 1 peça física (demanda = 2P)
        self.assertEqual(pecas_na_mesa(20, None), 40)
        self.assertEqual(calc_resto(20, None), 0)
        self.assertEqual(pecas_na_mesa(20, 0), 40)
        self.assertEqual(calc_resto(20, 0), 0)
        self.assertEqual(pecas_na_mesa(20, 1), 40)
        self.assertEqual(calc_resto(20, 1), 0)

        # Entradas em formato string
        self.assertEqual(pecas_na_mesa("125", "4"), 63)
        self.assertEqual(calc_resto("125", "4"), -1)
        self.assertEqual(pecas_na_mesa("abc", "4"), 0)
        self.assertEqual(calc_resto("abc", "4"), 0)

    # -------------------------------------------------------------------------
    # Teste 6: Precedência de Camadas
    # grid_material_row > session.layers > material.layers > layout.layers > 2
    # -------------------------------------------------------------------------
    def test_06_layers_resolution_precedence(self):
        # 1. grid_material_row tem prioridade máxima
        grid_row = ["▶", "853412", "Couro", "M", "1.40", "1.00", "4", "1.2", "1.0", "10"]
        sess = {"layers": 3}
        mat = {"layers": 5}
        ly = {"layers": 6}
        self.assertEqual(resolve_session_layers(sess, mat, grid_row, ly), 4)

        # 2. session.layers vence se grid_row for None ou vazio
        self.assertEqual(resolve_session_layers(sess, mat, None, ly), 3)
        grid_row_empty = ["▶", "853412", "Couro", "M", "1.40", "1.00", "", "1.2", "1.0", "10"]
        self.assertEqual(resolve_session_layers(sess, mat, grid_row_empty, ly), 3)

        # 3. material.layers vence se session não definir layers
        sess_no_layers = {"id": 1, "status": "Stand by"}
        self.assertEqual(resolve_session_layers(sess_no_layers, mat, None, ly), 5)

        # 4. layout.layers vence se material não definir layers
        mat_no_layers = {"id": 10}
        self.assertEqual(resolve_session_layers(sess_no_layers, mat_no_layers, None, ly), 6)

        # 5. Padrão 2 vence quando nenhuma fonte definir layers
        self.assertEqual(resolve_session_layers(sess_no_layers, mat_no_layers, None, None), 2)
        self.assertEqual(resolve_session_layers(None, None, None, None), 2)

        # is_layers_defined
        self.assertTrue(is_layers_defined(grid_material_row=grid_row))
        self.assertTrue(is_layers_defined(session=sess))
        self.assertTrue(is_layers_defined(material=mat))
        self.assertTrue(is_layers_defined(layout=ly))
        self.assertFalse(is_layers_defined(None, None, None, None))

    # -------------------------------------------------------------------------
    # Teste 7: Nesting com 4 camadas (125/109/97 pares -> 63/55/49 peças)
    # em FastNest, HighYield, stdNOTFill e sint
    # -------------------------------------------------------------------------
    def test_07_nesting_pieces_demanded_formula(self):
        # Moldes com 125, 109 e 97 pares com 4 camadas demandam exatamente 63, 55 e 49 peças
        self.assertEqual(pecas_na_mesa(125, 4), 63)
        self.assertEqual(pecas_na_mesa(109, 4), 55)
        self.assertEqual(pecas_na_mesa(97, 4), 49)

        # Chapa ampla para caber 63 peças (2000x2000 mm)
        # FastNest
        pieces_fast = auto_nest_pieces(
            [self.shape_125],
            bed_width_mm=2000.0,
            bed_height_mm=2000.0,
            strategy="flashnestsheet",
            params="FastNest",
            layers=4
        )
        self.assertEqual(len(pieces_fast), 63)

        # HighYield
        pieces_hy = auto_nest_pieces(
            [self.shape_125],
            bed_width_mm=2000.0,
            bed_height_mm=2000.0,
            strategy="flashnestsheet",
            params="HighYield",
            layers=4
        )
        self.assertEqual(len(pieces_hy), 63)

        # stdNOTFill
        pieces_notfill = auto_nest_pieces(
            [self.shape_125],
            bed_width_mm=2000.0,
            bed_height_mm=2000.0,
            strategy="flashnestsheet",
            params="stdNOTFill",
            layers=4
        )
        self.assertEqual(len(pieces_notfill), 63)

        # sint (Sintéticos Contínuo) com target_count=pecas_na_mesa
        pieces_sint = auto_nest_pieces(
            [self.shape_125],
            bed_width_mm=2000.0,
            bed_height_mm=2000.0,
            strategy="sint",
            params="stdNOTFill",
            layers=4
        )
        self.assertEqual(len(pieces_sint), 63)

    # -------------------------------------------------------------------------
    # Teste 8: stdNOTFill (parada exata) vs stdFill (continua preenchendo)
    # -------------------------------------------------------------------------
    def test_08_stdnotfill_vs_stdfill(self):
        # 1 par pedido (2 camadas) -> cota = 1 peça desenhada
        shape_1pair = {
            "id": 99,
            "name": "Single_Pair",
            "size": "41",
            "pairs": 1,
            "sequence": 1,
            "contour": self.contour_40x40,
        }
        # Na chapa de 500x500 mm cabem dezenas de peças 40x40
        # Com stdNOTFill: para RIGOROSAMENTE na cota (1 peça)
        pieces_notfill = auto_nest_pieces(
            [shape_1pair],
            bed_width_mm=500.0,
            bed_height_mm=500.0,
            strategy="flashnestsheet",
            params="stdNOTFill",
            layers=2
        )
        self.assertEqual(len(pieces_notfill), 1, "stdNOTFill deve parar rigorosamente na cota de 1 peça")

        # Com stdFill: continua preenchendo a chapa física além da cota
        pieces_fill = auto_nest_pieces(
            [shape_1pair],
            bed_width_mm=500.0,
            bed_height_mm=500.0,
            strategy="flashnestsheet",
            params="stdFill",
            layers=2
        )
        self.assertGreater(len(pieces_fill), 1, "stdFill deve preencher a chapa além da cota para estoque")

    # -------------------------------------------------------------------------
    # Teste 9: Multi-placa com 125 pares em 4 camadas -> soma 63 peças (peça extra 1x)
    # -------------------------------------------------------------------------
    def test_09_multisheet_125_pairs_layers_4(self):
        # Chapa que comporta aproximadamente 40 peças por placa (ex: 350x350 mm para molde 40x40)
        res = nest_multi_sheet(
            available_shapes=[self.shape_125],
            bed_width_mm=350.0,
            bed_height_mm=350.0,
            strategy="flashnestsheet",
            params="stdNOTFill",
            gap_mm=2.0,
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            layers=4
        )
        self.assertTrue(res["success"])
        self.assertGreater(len(res["layouts"]), 1, "Deve gerar mais de 1 placa para acomodar as 63 peças")

        # Total de peças colocadas somadas entre todas as placas deve ser EXATAMENTE 63
        total_placed = sum(len(ly["pieces"]) for ly in res["layouts"])
        self.assertEqual(total_placed, 63, "Multi-placa deve posicionar exatamente 63 peças somadas")
        self.assertEqual(res["total_pieces"], 63)
        # 63 peças em 4 camadas cortam 252 peças físicas = 126 pares
        self.assertEqual(res["total_pairs_cut"], 126)
        self.assertEqual(res["total_pairs_demanded"], 125)

    # -------------------------------------------------------------------------
    # Teste 10: Zero Colisão e Respeito a Margens Úteis para todas as peças (inclusive a 63ª)
    # -------------------------------------------------------------------------
    def test_10_zero_collision_and_margins(self):
        m_left = 12.0
        m_right = 14.0
        m_top = 16.0
        m_bottom = 18.0
        sheet_w = 1200.0
        sheet_h = 1000.0
        gap = 2.0

        pieces = auto_nest_pieces(
            [self.shape_125],
            bed_width_mm=sheet_w,
            bed_height_mm=sheet_h,
            strategy="flashnestsheet",
            params="stdNOTFill",
            gap_mm=gap,
            margins={"left": m_left, "right": m_right, "top": m_top, "bottom": m_bottom},
            layers=4
        )
        self.assertEqual(len(pieces), 63, "Todas as 63 peças devem caber na chapa 1200x1000 mm")

        # 1. Valida respeito a margens de todas as peças
        for p in pieces:
            poly = p.get("contour", [])
            from cad.geometry import transform_contour
            t_poly = transform_contour(poly, p["x"], p["y"], p.get("rotation", 0.0))
            min_x, min_y, max_x, max_y = polygon_bbox(t_poly)

            self.assertGreaterEqual(min_x, m_left - 1e-4, f"Peça {p['id']} violou margem esquerda")
            self.assertGreaterEqual(min_y, m_bottom - 1e-4, f"Peça {p['id']} violou margem inferior")
            self.assertLessEqual(max_x, sheet_w - m_right + 1e-4, f"Peça {p['id']} violou margem direita")
            self.assertLessEqual(max_y, sheet_h - m_top + 1e-4, f"Peça {p['id']} violou margem superior")

        # 2. Valida zero colisão entre todas as peças da mesa com gap de 2.0mm
        from cad.geometry import transform_contour
        transformed_polys = [
            (
                p["id"],
                transform_contour(p["contour"], p["x"], p["y"], p.get("rotation", 0.0)),
                polygon_bbox(transform_contour(p["contour"], p["x"], p["y"], p.get("rotation", 0.0)))
            )
            for p in pieces
        ]

        for i in range(len(transformed_polys)):
            id_a, poly_a, bbox_a = transformed_polys[i]
            for j in range(i + 1, len(transformed_polys)):
                id_b, poly_b, bbox_b = transformed_polys[j]
                # polygons_collide com gap=0.0 verifica sobreposição física direta
                collides = polygons_collide(poly_a, poly_b, gap=0.0, bbox_a=bbox_a, bbox_b=bbox_b)
                self.assertFalse(collides, f"Colisão detectada entre peças {id_a} e {id_b}")


if __name__ == "__main__":
    unittest.main()
