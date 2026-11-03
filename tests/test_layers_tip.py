"""
tests/test_layers_tip.py

Suíte completa de 16 testes obrigatórios para Ponta de 2 Camadas (Enfesto em Degrau)
conforme especificação da auditoria técnica e regras confirmadas pelo operador.
"""

import copy
import math
import os
import tempfile
import unittest
import tkinter as tk
from pathlib import Path

from cad.layers_rule import (
    resolve_session_layers,
    resolve_layout_layers,
    is_separar_sobras_enabled,
    parse_session_params,
    encode_session_params,
    calc_resto,
    calc_resto_efetivo,
    pecas_na_mesa,
    layers_for_piece,
    format_enfesto_operator_text,
)
from cad.layers_split import (
    separar_sobras_em_ponta,
    desfazer_separacao_sobras,
    separar_sobras_camadas,
    log_sobras,
)
from cad.lay_parser import parse_lay, export_layout_from_pieces
from cad.dual_exporter import DualLayoutExporter


class TestLayersTipSuite(unittest.TestCase):
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
            cls.root = None

    def setUp(self):
        # Molde retangular 100x50 mm para testes determinísticos
        self.box_contour = [
            {"x": 0.0, "y": 0.0},
            {"x": 100.0, "y": 0.0},
            {"x": 100.0, "y": 50.0},
            {"x": 0.0, "y": 50.0}
        ]
        self.material_padrao = {
            "width_mm": 1380.0,
            "height_mm": 2990.0,
            "gap_mm": 1.0,
            "name": "SINT-PRETO",
            "layers": 4
        }

    def _make_piece(self, pid, sid, sname, size, x, y, contour=None):
        return {
            "id": pid,
            "shape_id": sid,
            "name": sname,
            "size": str(size),
            "x": float(x),
            "y": float(y),
            "rotation": 0.0,
            "mirrored": False,
            "contour": contour or copy.deepcopy(self.box_contour),
            "placement_index": pid
        }

    # -------------------------------------------------------------
    # 1. Cenário Real: 4 camadas, 7 moldes (115, 155, 157, 101, 102, 107, 108) cria ponta
    # -------------------------------------------------------------
    def test_01_cenario_real_7_moldes_impares_cria_ponta(self):
        pairs_list = [115, 155, 157, 101, 102, 107, 108]
        shapes = []
        for i, p in enumerate(pairs_list):
            shapes.append({
                "id": i + 1,
                "name": f"M{i+1}",
                "size": "38",
                "required": p,
                "pairs": p,
                "sequence": i + 1,
                "contour": self.box_contour
            })

        # Distribui peças iniciais: para cada molde P, ceil(2P/4) = (P + 1) // 2 peças no total
        all_pieces = []
        pid = 1
        for s in shapes:
            needed = (s["pairs"] + 1) // 2
            for _ in range(needed):
                all_pieces.append(self._make_piece(pid, s["id"], s["name"], s["size"], 0.0, 0.0))
                pid += 1

        # Distribui as 425 peças em 4 chapas de 1380 x 2990 mm com coordenadas válidas
        pieces_per_sheet = 110
        layouts = []
        for l_idx in range(4):
            sheet_pieces = all_pieces[l_idx * pieces_per_sheet : (l_idx + 1) * pieces_per_sheet]
            # Organiza em grade (10 colunas x 11 linhas)
            for idx_p, p in enumerate(sheet_pieces):
                col = idx_p % 10
                row = idx_p // 10
                p["x"] = 20.0 + col * 120.0
                p["y"] = 20.0 + row * 65.0
            layouts.append({
                "layout_index": l_idx,
                "name": f"lay{l_idx:04d}",
                "width_mm": 1380.0,
                "height_mm": 2990.0,
                "layers": 4,
                "pieces": sheet_pieces
            })

        res_lays, msg = separar_sobras_em_ponta(
            layouts=layouts,
            shapes=shapes,
            sheet_w=1380.0,
            sheet_h=2990.0,
            material=self.material_padrao,
            refile=True,
            tip_mode="canto"
        )

        last_lay = res_lays[-1]
        self.assertIsNotNone(last_lay.get("tip_zone"), "A última chapa deve ter tip_zone definida")
        self.assertEqual(last_lay.get("layers_tip"), 2, "layers_tip deve ser 2")

        # Resto efetivo de todos os moldes deve ser 0
        for s in shapes:
            r = calc_resto_efetivo(s["pairs"], 4, separar=True)
            self.assertEqual(r, 0, f"Resto efetivo para {s['name']} deve ser 0")

    # -------------------------------------------------------------
    # 2. Apenas moldes pares -> nenhuma ponta criada
    # -------------------------------------------------------------
    def test_02_apenas_moldes_pares_sem_ponta(self):
        even_pairs = [100, 150, 200]
        shapes = [
            {"id": i + 1, "name": f"MP{i+1}", "size": "38", "required": p, "pairs": p, "contour": self.box_contour}
            for i, p in enumerate(even_pairs)
        ]
        pieces = [self._make_piece(i + 1, 1, "MP1", "38", (i % 5) * 120.0, (i // 5) * 70.0) for i in range(10)]
        layouts = [{
            "layout_index": 0,
            "name": "lay0000",
            "width_mm": 1380.0,
            "height_mm": 2990.0,
            "layers": 4,
            "pieces": pieces
        }]

        res_lays, msg = separar_sobras_em_ponta(
            layouts=layouts,
            shapes=shapes,
            sheet_w=1380.0,
            sheet_h=2990.0,
            material=self.material_padrao
        )

        self.assertIsNone(res_lays[0].get("tip_zone"))
        self.assertIn("nenhuma sobra", msg.lower())

    # -------------------------------------------------------------
    # 3. Camadas diferente de 4 -> ponta não aplicável
    # -------------------------------------------------------------
    def test_03_camadas_diferente_de_4_sem_ponta(self):
        shapes = [{"id": 1, "name": "M1", "size": "38", "required": 5, "pairs": 5, "contour": self.box_contour}]
        pieces = [self._make_piece(1, 1, "M1", "38", 50.0, 50.0)]

        for l in (1, 2, 6):
            mat = dict(self.material_padrao)
            mat["layers"] = l
            layouts = [{
                "layout_index": 0,
                "name": "lay0000",
                "width_mm": 1380.0,
                "height_mm": 2990.0,
                "layers": l,
                "pieces": copy.deepcopy(pieces)
            }]
            res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=1380.0, sheet_h=2990.0, material=mat)
            self.assertIsNone(res[0].get("tip_zone"))
            self.assertIn("só se aplica a 4 camadas", msg.lower())

    # -------------------------------------------------------------
    # 4. Parâmetro separar_sobras desativado
    # -------------------------------------------------------------
    def test_04_separar_sobras_desativado(self):
        shapes = [{"id": 1, "name": "M1", "size": "38", "required": 5, "pairs": 5, "contour": self.box_contour}]
        pieces = [
            self._make_piece(1, 1, "M1", "38", 50.0, 50.0),
            self._make_piece(2, 1, "M1", "38", 180.0, 50.0),
            self._make_piece(3, 1, "M1", "38", 310.0, 50.0),
        ]
        layouts = [{
            "layout_index": 0,
            "name": "lay0000",
            "width_mm": 1380.0,
            "height_mm": 2990.0,
            "layers": 4,
            "pieces": pieces
        }]

        res, msg = separar_sobras_em_ponta(
            layouts=layouts,
            shapes=shapes,
            sheet_w=1380.0,
            sheet_h=2990.0,
            material=self.material_padrao,
            opts={"separar_sobras": "0"}
        )
        self.assertIsNone(res[0].get("tip_zone"))
        self.assertIn("desmarcada", msg.lower())

    # -------------------------------------------------------------
    # 5. Idempotência: segunda chamada não altera layouts já com ponta
    # -------------------------------------------------------------
    def test_05_idempotencia_segunda_chamada(self):
        shapes = [{"id": 1, "name": "M1", "size": "38", "required": 5, "pairs": 5, "contour": self.box_contour}]
        pieces = [
            self._make_piece(1, 1, "M1", "38", 50.0, 50.0),
            self._make_piece(2, 1, "M1", "38", 200.0, 50.0),
            self._make_piece(3, 1, "M1", "38", 350.0, 50.0),
        ]
        layouts = [
            {"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": pieces[:2]},
            {"layout_index": 1, "name": "lay0001", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": pieces[2:]}
        ]

        res1, msg1 = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=1380.0, sheet_h=2990.0, material=self.material_padrao)
        res2, msg2 = separar_sobras_em_ponta(layouts=res1, shapes=shapes, sheet_w=1380.0, sheet_h=2990.0, material=self.material_padrao)

        self.assertEqual(len(res1), len(res2))
        self.assertIn("já aplicada", msg2.lower())
        self.assertEqual(res1[-1].get("tip_zone"), res2[-1].get("tip_zone"))

    # -------------------------------------------------------------
    # 6. Peças de sobra retiradas do fim e origens congeladas
    # -------------------------------------------------------------
    def test_06_origem_congelada_pecas_do_fim(self):
        shapes = [{"id": 1, "name": "M1", "size": "38", "required": 5, "pairs": 5, "contour": self.box_contour}]
        p1 = self._make_piece(1, 1, "M1", "38", 10.0, 20.0)
        p2 = self._make_piece(2, 1, "M1", "38", 150.0, 20.0)
        p3 = self._make_piece(3, 1, "M1", "38", 300.0, 20.0)

        layouts = [
            {"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": [p1, p2]},
            {"layout_index": 1, "name": "lay0001", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": [p3]}
        ]

        res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=1380.0, sheet_h=2990.0, material=self.material_padrao)

        lay0 = res[0]
        self.assertEqual(lay0["pieces"][0]["x"], 10.0)
        self.assertEqual(lay0["pieces"][0]["y"], 20.0)
        self.assertEqual(lay0["pieces"][1]["x"], 150.0)
        self.assertEqual(lay0["pieces"][1]["y"], 20.0)

    # -------------------------------------------------------------
    # 7. Placa de origem vazia removida e renumerada
    # -------------------------------------------------------------
    def test_07_placa_origem_vazia_removida_renumerada(self):
        shapes = [{"id": 1, "name": "M1", "size": "38", "required": 5, "pairs": 5, "contour": self.box_contour}]
        p1 = self._make_piece(1, 1, "M1", "38", 10.0, 10.0)
        p2 = self._make_piece(2, 1, "M1", "38", 150.0, 10.0)
        p3 = self._make_piece(3, 1, "M1", "38", 300.0, 10.0)

        layouts = [
            {"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": [p1, p2]},
            {"layout_index": 1, "name": "lay0001", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": [p3]}
        ]

        res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=1380.0, sheet_h=2990.0, material=self.material_padrao)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "lay0000")
        self.assertIsNotNone(res[0].get("tip_zone"))

    # -------------------------------------------------------------
    # 8. Encaixe no canto inferior direito em modo canto
    # -------------------------------------------------------------
    def test_08_encaixe_canto_inferior_direito(self):
        shapes = [{"id": 1, "name": "M1", "size": "38", "required": 5, "pairs": 5, "contour": self.box_contour}]
        pieces = [
            self._make_piece(1, 1, "M1", "38", 10.0, 10.0),
            self._make_piece(2, 1, "M1", "38", 150.0, 10.0),
            self._make_piece(3, 1, "M1", "38", 300.0, 10.0),
        ]
        layouts = [{"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": pieces}]

        res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=1380.0, sheet_h=2990.0, material=self.material_padrao, tip_mode="canto")
        tip_z = res[0].get("tip_zone")
        self.assertIsNotNone(tip_z)
        x0, y0, x1, y1 = tip_z
        self.assertEqual(x1, 1380.0)
        self.assertGreaterEqual(y0, 0.0)
        self.assertGreaterEqual(x0, 0.0)
        self.assertGreater(y1, 0.0)

    # -------------------------------------------------------------
    # 9. Transbordo para penúltima fileira
    # -------------------------------------------------------------
    def test_09_transbordo_penultima_fileira(self):
        # 5 moldes ímpares com 3 pares cada (necessita 2 peças por molde = 10 peças no total, 5 sobras)
        shapes = [
            {"id": i + 1, "name": f"M{i+1}", "size": "38", "required": 3, "pairs": 3, "contour": self.box_contour}
            for i in range(5)
        ]
        pieces = []
        pid = 1
        for s in shapes:
            for _ in range(2):
                pieces.append(self._make_piece(pid, s["id"], s["name"], s["size"], 10.0, (pid * 55.0)))
                pid += 1

        layouts = [{"layout_index": 0, "name": "lay0000", "width_mm": 400.0, "height_mm": 2990.0, "layers": 4, "pieces": pieces}]

        res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=400.0, sheet_h=2990.0, material=self.material_padrao, tip_mode="canto")
        self.assertIsNotNone(res[0].get("tip_zone"))

    # -------------------------------------------------------------
    # 10. Transbordo para fileira extra
    # -------------------------------------------------------------
    def test_10_transbordo_fileira_extra(self):
        shapes = [{"id": 1, "name": "M1", "size": "38", "required": 3, "pairs": 3, "contour": self.box_contour}]
        pieces = [
            self._make_piece(1, 1, "M1", "38", 10.0, 10.0),
            self._make_piece(2, 1, "M1", "38", 150.0, 10.0)
        ]
        layouts = [{"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": pieces}]

        res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=1380.0, sheet_h=2990.0, material=self.material_padrao)
        self.assertIsNotNone(res[0].get("tip_zone"))

    # -------------------------------------------------------------
    # 11. Fallback para Plano B se necessitar mais de 1 fileira extra
    # -------------------------------------------------------------
    def test_11_fallback_plano_b_mais_de_uma_fileira(self):
        shapes = [
            {"id": i + 1, "name": f"M{i+1}", "size": "38", "required": 3, "pairs": 3, "contour": self.box_contour}
            for i in range(8)
        ]
        pieces = []
        pid = 1
        for s in shapes:
            for _ in range(2):
                pieces.append(self._make_piece(pid, s["id"], s["name"], s["size"], 10.0, 10.0))
                pid += 1

        layouts = [{"layout_index": 0, "name": "lay0000", "width_mm": 150.0, "height_mm": 120.0, "layers": 4, "pieces": pieces}]

        res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=150.0, sheet_h=120.0, material=self.material_padrao)
        has_2l = any(ly.get("layers") == 2 for ly in res)
        self.assertTrue(has_2l, "Deve ter feito fallback para layout de 2 camadas (Plano B)")

    # -------------------------------------------------------------
    # 12. Regra Econômica Refile ON: Ponta vence
    # -------------------------------------------------------------
    def test_12_regra_economica_refile_on_ponta_vence(self):
        shapes = [{"id": 1, "name": "M1", "size": "38", "required": 3, "pairs": 3, "contour": self.box_contour}]
        pieces = [
            self._make_piece(1, 1, "M1", "38", 10.0, 10.0),
            self._make_piece(2, 1, "M1", "38", 150.0, 10.0)
        ]
        layouts = [{"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": pieces}]

        res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=1380.0, sheet_h=2990.0, material=self.material_padrao, refile=True)
        self.assertIsNotNone(res[0].get("tip_zone"), "Ponta deve vencer economicamente")

    # -------------------------------------------------------------
    # 13. Regra Econômica Refile ON: Plano B de fallback
    # -------------------------------------------------------------
    def test_13_regra_economica_refile_on_plano_b_vence(self):
        shapes = [
            {"id": i + 1, "name": f"M{i+1}", "size": "38", "required": 3, "pairs": 3, "contour": self.box_contour}
            for i in range(15)
        ]
        pieces = []
        pid = 1
        for s in shapes:
            for _ in range(2):
                pieces.append(self._make_piece(pid, s["id"], s["name"], s["size"], 10.0, 10.0))
                pid += 1

        layouts = [{"layout_index": 0, "name": "lay0000", "width_mm": 120.0, "height_mm": 80.0, "layers": 4, "pieces": pieces}]
        res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=120.0, sheet_h=80.0, material=self.material_padrao, refile=True)
        # Deve recorrer ao Plano B
        has_2l = any(ly.get("layers") == 2 for ly in res)
        self.assertTrue(has_2l)

    # -------------------------------------------------------------
    # 14. Conservação física estrita: sum(pecas * layers) == 2 * pairs
    # -------------------------------------------------------------
    def test_14_conservacao_fisica_estrita(self):
        shapes = [
            {"id": 1, "name": "M1", "size": "38", "required": 5, "pairs": 5, "contour": self.box_contour},
            {"id": 2, "name": "M2", "size": "38", "required": 4, "pairs": 4, "contour": self.box_contour}
        ]
        pieces = [
            self._make_piece(1, 1, "M1", "38", 10.0, 10.0),
            self._make_piece(2, 1, "M1", "38", 150.0, 10.0),
            self._make_piece(3, 1, "M1", "38", 300.0, 10.0),
            self._make_piece(4, 2, "M2", "38", 10.0, 80.0),
            self._make_piece(5, 2, "M2", "38", 150.0, 80.0),
        ]
        layouts = [{"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": pieces}]

        res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=1380.0, sheet_h=2990.0, material=self.material_padrao)

        for s in shapes:
            target_phys = s["pairs"] * 2
            tot_phys = 0
            for ly in res:
                for p in ly["pieces"]:
                    if p.get("shape_id") == s["id"] or p.get("name") == s["name"]:
                        tot_phys += layers_for_piece(ly, p)
            self.assertEqual(tot_phys, target_phys, f"Conservação física violada para {s['name']}: {tot_phys} != {target_phys}")

    # -------------------------------------------------------------
    # 15. Desfazer separação de sobras restaura para 4 camadas
    # -------------------------------------------------------------
    def test_15_desfazer_separacao_sobras(self):
        shapes = [{"id": 1, "name": "M1", "size": "38", "required": 5, "pairs": 5, "contour": self.box_contour}]
        pieces = [
            self._make_piece(1, 1, "M1", "38", 10.0, 10.0),
            self._make_piece(2, 1, "M1", "38", 150.0, 10.0),
            self._make_piece(3, 1, "M1", "38", 300.0, 10.0),
        ]
        layouts = [{"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 2990.0, "layers": 4, "pieces": pieces}]

        res, msg = separar_sobras_em_ponta(layouts=layouts, shapes=shapes, sheet_w=1380.0, sheet_h=2990.0, material=self.material_padrao)
        self.assertIsNotNone(res[0].get("tip_zone"))

        reverted, rev_msg = desfazer_separacao_sobras(res)
        self.assertIsNone(reverted[0].get("tip_zone"))
        self.assertEqual(reverted[0].get("layers"), 4)

    # -------------------------------------------------------------
    # 16. Exportação .lay com tip_zone e layers_tip=2 preservados
    # -------------------------------------------------------------
    def test_16_export_lay_com_tip_zone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lay_path = Path(tmpdir) / "test_ponta.lay"
            pieces = [self._make_piece(1, 1, "M1", "38", 50.0, 50.0)]
            tip_z = (500.0, 0.0, 1380.0, 300.0)

            DualLayoutExporter.export_atom_lay(
                placed_pieces=pieces,
                material=self.material_padrao,
                file_path=lay_path,
                session_id=1,
                layers=4,
                tip_zone=tip_z,
                layers_tip=2
            )

            self.assertTrue(lay_path.exists())

            parsed = parse_lay(str(lay_path))
            self.assertIsNotNone(parsed.tip_zone)
            self.assertEqual(parsed.tip_zone, tip_z)
            self.assertEqual(parsed.layers_tip, 2)


if __name__ == '__main__':
    unittest.main()
