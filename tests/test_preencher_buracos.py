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


class TestSegundoPassePosSobras(unittest.TestCase):
    """
    Cenário real 6 moldes x 101 pares, chapa 1,37 x 2,82 m, 4 camadas (§8.48):
    O 2º passe de preenchimento roda após separar_sobras_em_ponta e fecha o buraco
    de 4 peças no canto superior direito da placa 0 (220 -> 224 peças).
    """

    def test_cenario_6_moldes_101_pares_fecha_buraco(self):
        import os
        from database import DatabaseManager
        from cad.nesting_engine import nest_multi_sheet, preencher_buracos_em_placas
        from cad.layers_split import separar_sobras_em_ponta
        from cad.geometry import polygons_collide, transform_contour, polygon_bbox
        from cad.layers_rule import layers_for_piece

        db_path = "jobmanager.db"
        if not os.path.exists(db_path):
            self.skipTest("jobmanager.db não encontrado para teste de cenário real")

        db = DatabaseManager(db_path)
        sess = db.get_session(282)
        if not sess or not sess.get("shapes"):
            self.skipTest("Sessão #282 não encontrada no jobmanager.db")

        mat = sess.get("material") or {}
        shapes = sess.get("shapes", [])
        gap = float(sess.get("gap_mm", 1.0) or 1.0)
        margins = {
            "left": float(sess.get("margin_left", 10.0)),
            "right": float(sess.get("margin_right", 10.0)),
            "top": float(sess.get("margin_top", 10.0)),
            "bottom": float(sess.get("margin_bottom", 10.0)),
        }

        # 1. Encaixe multi-placa original
        nest_res = nest_multi_sheet(
            available_shapes=shapes,
            bed_width_mm=float(mat.get("width_mm", 1380.0)),
            bed_height_mm=float(mat.get("height_mm", 2980.0)),
            strategy=sess.get("strategy") or "flashnestsheet",
            params=sess.get("params") or "FastNest",
            gap_mm=gap,
            margins=margins,
            layers=4,
            max_total_sec=60,
        )
        self.assertTrue(nest_res.get("success"), nest_res.get("warning"))
        layouts = nest_res["layouts"]

        # 2. 1º passe de vãos (placa cheia, 0 movidas)
        layouts, _ = preencher_buracos_em_placas(layouts, gap_mm=gap, time_budget_s=4.0)

        # 3. Separação de sobras em ponta (cria ponta de 2c na última placa e retira 4 peças da placa 0)
        layouts, _ = separar_sobras_em_ponta(
            layouts=layouts,
            session=sess,
            shapes=shapes,
            params=sess.get("params"),
        )
        self.assertEqual(len(layouts[0]["pieces"]), 220, "Placa 0 pós-separação deve ter 220 peças")

        # 4. 2º passe de vãos: fecha o buraco com grade fina (célula 20 mm, passo 5 mm, 4 s)
        layouts, info2 = preencher_buracos_em_placas(
            layouts,
            gap_mm=gap,
            cell_mm=20.0,
            step_mm=5.0,
            time_budget_s=4.0,
            session=sess,
            shapes=shapes,
        )

        self.assertEqual(info2["movidas"], 4, "Devem ser movidas exatamente 4 peças para fechar o vão")
        self.assertEqual(len(layouts[0]["pieces"]), 224, "Placa 0 deve voltar a ter 224 peças")

        # 5. Verificação física estrita por molde: sum(peças * layers) = 2P
        for shp in shapes:
            req_p = int(shp["pairs"])
            expected = 2 * req_p
            actual = sum(
                layers_for_piece(ly, p)
                for ly in layouts
                for p in ly["pieces"]
                if (p.get("size") or p.get("name")) == (shp.get("size") or shp.get("name"))
            )
            self.assertEqual(actual, expected, f"Molde {shp.get('size')}: esperado {expected}, obtido {actual}")

        # 6. Sem colisão entre peças
        for idx, ly in enumerate(layouts):
            polys = [transform_contour(p["contour"], p["x"], p["y"], p.get("rotation", 0)) for p in ly["pieces"]]
            bbs = [polygon_bbox(q) for q in polys]
            for i in range(len(polys)):
                for j in range(i + 1, len(polys)):
                    a, b = bbs[i], bbs[j]
                    if a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]:
                        continue
                    self.assertFalse(
                        polygons_collide(polys[i], polys[j], gap=0.0, bbox_a=a, bbox_b=b),
                        f"Colisão na placa {idx} entre peças {i} e {j}",
                    )

        # 7. Apenas rotações 0° e 180°
        for ly in layouts:
            for p in ly["pieces"]:
                rot = round(float(p.get("rotation", 0.0))) % 360
                self.assertIn(rot, (0, 180), f"Peça deitada com rotação {p.get('rotation')}")

        # 8. Ponta da última placa intacta (6 peças a 2 camadas)
        tip_pieces = [
            p for p in layouts[-1]["pieces"]
            if p.get("is_tip") or layers_for_piece(layouts[-1], p) == 2
        ]
        self.assertEqual(len(tip_pieces), 6, "Ponta da última placa deve conter exatamente 6 peças de 2c")

