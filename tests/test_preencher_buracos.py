"""
tests/test_preencher_buracos.py

Regressão do "buraco" nas placas: peças da última placa devem ocupar os vãos
das anteriores em vez de virar desperdício de material.
"""

import unittest

from cad.nesting_engine import preencher_buracos_em_placas

QUADRADO = [
    {"x": 0.0, "y": 0.0},
    {"x": 100.0, "y": 0.0},
    {"x": 100.0, "y": 200.0},
    {"x": 0.0, "y": 200.0},
]


def _peca(pid, x, y, nome="M1", size="38"):
    return {"id": pid, "name": nome, "size": size, "x": float(x), "y": float(y),
            "rotation": 0.0, "contour": [dict(p) for p in QUADRADO], "layers": 4}


class TestPreencherBuracos(unittest.TestCase):
    def test_move_peca_da_ultima_placa_para_o_vao(self):
        # placa 0 com 2 peças no canto inferior e um vão acima
        lay0 = {"name": "lay0000", "width_mm": 400.0, "height_mm": 600.0, "layers": 4,
                "pieces": [_peca(1, 10, 10), _peca(2, 10, 220)]}
        # última placa com uma peça que cabe no vão (10..110, 430..630 não cabe; usa 10..110, 310..510)
        lay1 = {"name": "lay0001", "width_mm": 400.0, "height_mm": 600.0, "layers": 4,
                "pieces": [_peca(3, 10, 10, nome="M2")]}

        layouts, info = preencher_buracos_em_placas([lay0, lay1], gap_mm=1.0, time_budget_s=2.0)
        self.assertEqual(info["movidas"], 1)
        self.assertEqual(len(layouts), 1, "placa final vazia deveria ser removida")
        self.assertEqual(len(layouts[0]["pieces"]), 3)

    def test_nao_move_peca_de_2_camadas(self):
        lay0 = {"name": "lay0000", "width_mm": 400.0, "height_mm": 600.0, "layers": 4,
                "pieces": [_peca(1, 10, 10)]}
        peca_tip = _peca(2, 10, 10, nome="M2")
        peca_tip["layers"] = 2
        lay1 = {"name": "lay0001", "width_mm": 400.0, "height_mm": 600.0, "layers": 4,
                "layers_tip": 2, "pieces": [peca_tip]}

        layouts, info = preencher_buracos_em_placas([lay0, lay1], gap_mm=1.0, time_budget_s=1.0)
        self.assertEqual(info["movidas"], 0)
        self.assertEqual(len(layouts), 2)

    def test_sem_colisao_apos_preencher(self):
        from cad.geometry import polygons_collide, transform_contour

        lay0 = {"name": "lay0000", "width_mm": 400.0, "height_mm": 600.0, "layers": 4,
                "pieces": [_peca(1, 10, 10), _peca(2, 10, 220)]}
        lay1 = {"name": "lay0001", "width_mm": 400.0, "height_mm": 600.0, "layers": 4,
                "pieces": [_peca(3, 10, 10, nome="M2")]}
        layouts, info = preencher_buracos_em_placas([lay0, lay1], gap_mm=1.0, time_budget_s=2.0)

        polys = [transform_contour(p["contour"], p["x"], p["y"], p.get("rotation", 0)) for p in layouts[0]["pieces"]]
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                self.assertFalse(polygons_collide(polys[i], polys[j], gap=0.0),
                                 f"peças {i} e {j} colidem após o preenchimento")

    def test_uma_placa_so_nao_faz_nada(self):
        lay0 = {"name": "lay0000", "width_mm": 400.0, "height_mm": 600.0, "layers": 4,
                "pieces": [_peca(1, 10, 10)]}
        layouts, info = preencher_buracos_em_placas([lay0])
        self.assertEqual(info["movidas"], 0)
        self.assertEqual(len(layouts), 1)


if __name__ == "__main__":
    unittest.main()


class TestNuncaDeitarPeca(unittest.TestCase):
    """Regra do operador: peça nunca é deitada (90°/270°) — só 0°/180°."""

    def test_rotacoes_permitidas_sao_0_e_180(self):
        import inspect
        from cad.nesting_engine import preencher_buracos_em_placas

        assinatura = inspect.signature(preencher_buracos_em_placas)
        self.assertEqual(tuple(assinatura.parameters["rotacoes"].default), (0.0, 180.0))

    def test_peca_movida_nao_e_deitada(self):
        cont = [
            {"x": 0.0, "y": 0.0}, {"x": 60.0, "y": 0.0},
            {"x": 60.0, "y": 200.0}, {"x": 0.0, "y": 200.0},
        ]
        def peca(pid, x, y):
            return {"id": pid, "name": "M1", "size": "38", "x": float(x), "y": float(y),
                    "rotation": 0.0, "contour": [dict(p) for p in cont], "layers": 4}

        # vão estreito: só caberia deitando a peça — portanto NÃO deve ser movida
        lay0 = {"name": "lay0000", "width_mm": 200.0, "height_mm": 600.0, "layers": 4,
                "pieces": [peca(1, 10, 10), peca(2, 10, 220), peca(3, 10, 430)]}
        lay1 = {"name": "lay0001", "width_mm": 200.0, "height_mm": 600.0, "layers": 4,
                "pieces": [peca(4, 10, 10)]}

        layouts, info = preencher_buracos_em_placas([lay0, lay1], gap_mm=1.0, time_budget_s=2.0)
        for ly in layouts:
            for p in ly["pieces"]:
                self.assertIn(round(float(p.get("rotation", 0.0))) % 360, (0, 180),
                              f"peça deitada: rotação {p.get('rotation')}")
