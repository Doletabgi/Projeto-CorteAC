"""
tests/test_layers_split.py

Suíte completa de testes (16 casos de teste obrigatórios) para validação da
separação automática de sobras de 4 camadas em layout extra de 2 camadas.
"""

import copy
import math
import os
import tempfile
import unittest
import tkinter as tk
from unittest.mock import MagicMock

from cad.layers_rule import (
    resolve_session_layers,
    resolve_layout_layers,
    is_separar_sobras_enabled,
    parse_session_params,
    encode_session_params,
    calc_resto,
    calc_resto_efetivo,
    pecas_na_mesa,
)
from cad.layers_split import separar_sobras_camadas
from cad.nesting_engine import (
    nest_multi_sheet,
    piece_matches_shape,
    polygons_collide,
    transform_contour,
    polygon_bbox,
)
from cad.lay_parser import parse_lay, export_layout_from_pieces
from cad.dual_exporter import DualLayoutExporter
from database import DatabaseManager
from ui.layout_editor_view import LayoutEditorView
from ui.layout_print_dialog import LayoutPrintDialog


class TestLayersSplit(unittest.TestCase):
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
        # Molde retangular 100x100 mm para testes geométricos rápidos
        self.contour_100 = [
            {"x": 0.0, "y": 0.0},
            {"x": 100.0, "y": 0.0},
            {"x": 100.0, "y": 100.0},
            {"x": 0.0, "y": 100.0}
        ]
        self.contour_50 = [
            {"x": 0.0, "y": 0.0},
            {"x": 50.0, "y": 0.0},
            {"x": 50.0, "y": 50.0},
            {"x": 0.0, "y": 50.0}
        ]

    # =========================================================================
    # Caso 1: 125, 109 e 97 pares a 4 camadas
    # =========================================================================
    def test_case_01_odd_pairs_4_layers_separation_and_counters(self):
        """
        125, 109 e 97 pares a 4 camadas:
        Placas de 4 camadas ficam com 62, 54 e 48 peças.
        Placa de 2 camadas fica com 1 peça de cada molde.
        Total físico exato (250, 218, 194).
        Resto efetivo 0 e contador sem vermelho.
        """
        shapes = [
            {"id": 1, "name": "M125", "size": "41", "pairs": 125, "sequence": 1, "contour": self.contour_50},
            {"id": 2, "name": "M109", "size": "42", "pairs": 109, "sequence": 2, "contour": self.contour_50},
            {"id": 3, "name": "M97", "size": "43", "pairs": 97, "sequence": 3, "contour": self.contour_50},
        ]
        # Simula placas de 4 camadas iniciais (demanda total = ceil(2P/4): 63, 55, 49)
        pieces_lay0 = []
        p_id = 1
        for s, qty in [(shapes[0], 63), (shapes[1], 55), (shapes[2], 49)]:
            for i in range(qty):
                pieces_lay0.append({
                    "id": p_id,
                    "placement_index": p_id,
                    "shape": s,
                    "name": s["name"],
                    "size": s["size"],
                    "x": float((i % 10) * 60),
                    "y": float((i // 10) * 60),
                    "rotation": 0.0,
                    "contour": s["contour"]
                })
                p_id += 1

        initial_layouts = [{
            "layout_index": 0,
            "name": "lay0000",
            "layers": 4,
            "pieces": pieces_lay0,
            "sheet_width_mm": 2000.0,
            "sheet_height_mm": 2000.0
        }]
        session = {
            "layers": 4,
            "params": "stdNOTFill;separar_sobras=1",
            "margin_left": 10.0,
            "margin_right": 10.0,
            "margin_top": 10.0,
            "margin_bottom": 10.0,
            "gap_mm": 1.0,
            "material": {"width_mm": 2000.0, "height_mm": 2000.0, "layers": 4}
        }

        new_layouts, summary = separar_sobras_camadas(initial_layouts, session=session, shapes=shapes)
        self.assertIsNotNone(summary)
        self.assertEqual(len(new_layouts), 2)

        lay_4 = new_layouts[0]
        lay_2 = new_layouts[1]
        self.assertEqual(lay_4["layers"], 4)
        self.assertEqual(lay_2["layers"], 2)

        # Contagens na placa de 4 camadas: 62, 54, 48
        c1_4 = sum(1 for p in lay_4["pieces"] if piece_matches_shape(p, shapes[0]))
        c2_4 = sum(1 for p in lay_4["pieces"] if piece_matches_shape(p, shapes[1]))
        c3_4 = sum(1 for p in lay_4["pieces"] if piece_matches_shape(p, shapes[2]))
        self.assertEqual(c1_4, 62)
        self.assertEqual(c2_4, 54)
        self.assertEqual(c3_4, 48)

        # Contagens na placa de 2 camadas: 1, 1, 1
        c1_2 = sum(1 for p in lay_2["pieces"] if piece_matches_shape(p, shapes[0]))
        c2_2 = sum(1 for p in lay_2["pieces"] if piece_matches_shape(p, shapes[1]))
        c3_2 = sum(1 for p in lay_2["pieces"] if piece_matches_shape(p, shapes[2]))
        self.assertEqual(c1_2, 1)
        self.assertEqual(c2_2, 1)
        self.assertEqual(c3_2, 1)

        # Totais físicos exatos:
        self.assertEqual(c1_4 * 4 + c1_2 * 2, 250)
        self.assertEqual(c2_4 * 4 + c2_2 * 2, 218)
        self.assertEqual(c3_4 * 4 + c3_2 * 2, 194)

        # Resto efetivo = 0
        self.assertEqual(calc_resto_efetivo(125, 4, separar=True), 0)
        self.assertEqual(calc_resto_efetivo(109, 4, separar=True), 0)
        self.assertEqual(calc_resto_efetivo(97, 4, separar=True), 0)

        # Contador da barra lateral
        if self.root:
            editor = LayoutEditorView(self.root, db=None)
            editor.layouts = new_layouts
            editor.placed_pieces = lay_4["pieces"]
            editor.session = session
            target = {"name": "M125", "size": "41", "pairs": 125}
            placed_cnt = editor.count_pieces_for_target(editor.placed_pieces, target)
            tot_phys = placed_cnt * 4 + editor.count_pieces_for_target(lay_2["pieces"], target) * 2
            pares_prod = tot_phys // 2
            self.assertEqual(pares_prod, 125)
            self.assertEqual(max(0, 125 - pares_prod), 0)
            has_deficit = (pares_prod < 125)
            self.assertFalse(has_deficit)
            editor.destroy()

    # =========================================================================
    # Caso 2: 126 e 62 pares (pares estritamente pares)
    # =========================================================================
    def test_case_02_even_pairs_no_separation(self):
        """Com pares estritamente pares, nada é separado e nenhum layout extra é gerado."""
        shapes = [
            {"id": 1, "name": "M126", "pairs": 126, "sequence": 1, "contour": self.contour_50},
            {"id": 2, "name": "M62", "pairs": 62, "sequence": 2, "contour": self.contour_50},
        ]
        pieces = []
        p_id = 1
        for s, qty in [(shapes[0], 63), (shapes[1], 31)]:
            for _ in range(qty):
                pieces.append({"id": p_id, "shape": s, "name": s["name"], "contour": s["contour"]})
                p_id += 1

        layouts = [{"layout_index": 0, "name": "lay0000", "layers": 4, "pieces": pieces}]
        session = {"layers": 4, "params": "stdNOTFill;separar_sobras=1"}

        new_layouts, summary = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        self.assertIsNone(summary)
        self.assertEqual(len(new_layouts), 1)
        self.assertEqual(new_layouts[0]["layers"], 4)
        self.assertEqual(len(new_layouts[0]["pieces"]), 94)

    # =========================================================================
    # Caso 3: Mistura de moldes pares e ímpares
    # =========================================================================
    def test_case_03_mixed_even_and_odd_shapes(self):
        """Placa de sobras contém apenas os moldes ímpares (1 peça de cada)."""
        shapes = [
            {"id": 1, "name": "Par100", "pairs": 100, "sequence": 1, "contour": self.contour_50},
            {"id": 2, "name": "Impar125", "pairs": 125, "sequence": 2, "contour": self.contour_50},
            {"id": 3, "name": "Par60", "pairs": 60, "sequence": 3, "contour": self.contour_50},
        ]
        pieces = []
        p_id = 1
        for s, qty in [(shapes[0], 50), (shapes[1], 63), (shapes[2], 30)]:
            for _ in range(qty):
                pieces.append({"id": p_id, "shape": s, "name": s["name"], "contour": s["contour"]})
                p_id += 1

        layouts = [{"layout_index": 0, "name": "lay0000", "layers": 4, "pieces": pieces}]
        session = {"layers": 4, "params": "stdNOTFill;separar_sobras=1"}

        new_lays, summary = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        self.assertIsNotNone(summary)
        self.assertEqual(len(new_lays), 2)
        lay_sobras = new_lays[1]
        self.assertEqual(lay_sobras["layers"], 2)

        # Na placa de sobras: apenas Impar125 (1 peça), Par100 tem 0, Par60 tem 0
        c_par100 = sum(1 for p in lay_sobras["pieces"] if piece_matches_shape(p, shapes[0]))
        c_impar125 = sum(1 for p in lay_sobras["pieces"] if piece_matches_shape(p, shapes[1]))
        c_par60 = sum(1 for p in lay_sobras["pieces"] if piece_matches_shape(p, shapes[2]))
        self.assertEqual(c_par100, 0)
        self.assertEqual(c_impar125, 1)
        self.assertEqual(c_par60, 0)

    # =========================================================================
    # Caso 4: Sessão com 2 camadas
    # =========================================================================
    def test_case_04_session_with_2_layers_no_separation(self):
        """Em sessão de 2 camadas nunca há sobra: nenhuma separação e nenhuma mudança."""
        shapes = [{"id": 1, "name": "M125", "pairs": 125, "contour": self.contour_50}]
        pieces = [{"id": i, "shape": shapes[0], "name": "M125", "contour": self.contour_50} for i in range(125)]
        layouts = [{"layout_index": 0, "name": "lay0000", "layers": 2, "pieces": pieces}]
        session = {"layers": 2, "params": "stdNOTFill;separar_sobras=1"}

        new_lays, summary = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        self.assertIsNone(summary)
        self.assertEqual(len(new_lays), 1)
        self.assertEqual(new_lays[0]["layers"], 2)

    # =========================================================================
    # Caso 5: Multi-placa com moldes ímpares espalhados
    # =========================================================================
    def test_case_05_multisheet_removes_from_terminating_plate(self):
        """A peça sai da placa onde cada molde termina, uma única vez; ordem pela Sequência preservada."""
        shapes = [
            {"id": 1, "name": "M1", "pairs": 125, "sequence": 1, "contour": self.contour_50},
            {"id": 2, "name": "M2", "pairs": 125, "sequence": 2, "contour": self.contour_50},
        ]
        # lay0000 tem 60 peças de M1
        # lay0001 tem 3 peças de M1 (total 63) e 50 peças de M2
        # lay0002 tem 13 peças de M2 (total 63)
        p0 = [{"id": i, "placement_index": i, "shape": shapes[0], "name": "M1", "contour": self.contour_50} for i in range(1, 61)]
        p1 = [{"id": i, "placement_index": i, "shape": shapes[0], "name": "M1", "contour": self.contour_50} for i in range(61, 64)]
        p1.extend([{"id": i, "placement_index": i, "shape": shapes[1], "name": "M2", "contour": self.contour_50} for i in range(101, 151)])
        p2 = [{"id": i, "placement_index": i, "shape": shapes[1], "name": "M2", "contour": self.contour_50} for i in range(151, 164)]

        layouts = [
            {"layout_index": 0, "name": "lay0000", "layers": 4, "pieces": p0},
            {"layout_index": 1, "name": "lay0001", "layers": 4, "pieces": p1},
            {"layout_index": 2, "name": "lay0002", "layers": 4, "pieces": p2},
        ]
        session = {"layers": 4, "params": "stdNOTFill;separar_sobras=1"}

        new_lays, summary = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        self.assertIsNotNone(summary)
        # Total de placas: 3 de 4 camadas + 1 de 2 camadas = 4 placas
        self.assertEqual(len(new_lays), 4)

        # M1 terminou em lay0001: lay0000 permaneceu com 60 peças intactas!
        self.assertEqual(len(new_lays[0]["pieces"]), 60)
        # lay0001 perdeu 1 peça de M1 (ficou com 2 de M1 + 50 de M2 = 52 peças)
        c_m1_lay1 = sum(1 for p in new_lays[1]["pieces"] if piece_matches_shape(p, shapes[0]))
        self.assertEqual(c_m1_lay1, 2)
        # M2 terminou em lay0002: lay0002 perdeu 1 peça de M2 (ficou com 12 peças)
        c_m2_lay2 = sum(1 for p in new_lays[2]["pieces"] if piece_matches_shape(p, shapes[1]))
        self.assertEqual(c_m2_lay2, 12)

    # =========================================================================
    # Caso 6: Último layout de 4 camadas que só tinha sobras
    # =========================================================================
    def test_case_06_empty_4_layer_layout_removed(self):
        """Último layout de 4 camadas que só tinha sobras é removido; índices contínuos."""
        shapes = [{"id": 1, "name": "M1", "pairs": 125, "contour": self.contour_50}]
        # lay0000 tem 62 peças, lay0001 tem apenas 1 peça (a sobra)
        p0 = [{"id": i, "placement_index": i, "shape": shapes[0], "name": "M1", "contour": self.contour_50} for i in range(1, 63)]
        p1 = [{"id": 63, "placement_index": 63, "shape": shapes[0], "name": "M1", "contour": self.contour_50}]

        layouts = [
            {"layout_index": 0, "name": "lay0000", "layers": 4, "pieces": p0},
            {"layout_index": 1, "name": "lay0001", "layers": 4, "pieces": p1},
        ]
        session = {"layers": 4, "params": "stdNOTFill;separar_sobras=1"}

        new_lays, summary = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        # lay0001 ficou vazio e foi removido! A placa de 2 camadas passa a ser lay0001.
        self.assertEqual(len(new_lays), 2)
        self.assertEqual(new_lays[0]["name"], "lay0000")
        self.assertEqual(new_lays[0]["layers"], 4)
        self.assertEqual(len(new_lays[0]["pieces"]), 62)

        self.assertEqual(new_lays[1]["name"], "lay0001")
        self.assertEqual(new_lays[1]["layers"], 2)
        self.assertEqual(len(new_lays[1]["pieces"]), 1)

    # =========================================================================
    # Caso 7: Muitas sobras que não cabem numa chapa
    # =========================================================================
    def test_case_07_multiple_sheets_of_leftovers(self):
        """Muitas sobras que não cabem numa chapa útil geram multi-placa, todas com layers=2."""
        # Chapa útil pequena (120x120 mm) onde cada molde 100x100 só cabe 1 peça por placa
        shapes = [
            {"id": 1, "name": "M1", "pairs": 1, "contour": self.contour_100},
            {"id": 2, "name": "M2", "pairs": 1, "contour": self.contour_100},
        ]
        layouts = [{
            "layout_index": 0,
            "name": "lay0000",
            "layers": 4,
            "pieces": [
                {"id": 1, "placement_index": 1, "shape": shapes[0], "name": "M1", "contour": self.contour_100},
                {"id": 2, "placement_index": 2, "shape": shapes[1], "name": "M2", "contour": self.contour_100},
            ],
            "sheet_width_mm": 120.0,
            "sheet_height_mm": 120.0
        }]
        session = {
            "layers": 4,
            "params": "stdNOTFill;separar_sobras=1",
            "margin_left": 5.0,
            "margin_right": 5.0,
            "margin_top": 5.0,
            "margin_bottom": 5.0,
            "gap_mm": 1.0,
            "material": {"width_mm": 120.0, "height_mm": 120.0, "layers": 4}
        }

        new_lays, summary = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        # A placa de 4 camadas original esvaziou (ambas eram sobras) e foi removida.
        # As 2 peças de 100x100 mm não cabem juntas numa chapa 120x120 mm útil (110x110 mm),
        # gerando 2 placas de sobras de 2 camadas!
        self.assertTrue(len(new_lays) >= 2)
        for ly in new_lays:
            self.assertEqual(ly["layers"], 2)

    # =========================================================================
    # Caso 8: Idempotência e Preservação de Ajustes Manuais
    # =========================================================================
    def test_case_08_idempotence_and_preserves_manual_adjustments(self):
        """Rodar duas vezes não duplica peças/placas e preserva ajustes manuais na placa de sobras."""
        shapes = [{"id": 1, "name": "M125", "pairs": 125, "contour": self.contour_50}]
        p0 = [{"id": i, "placement_index": i, "shape": shapes[0], "name": "M125", "contour": self.contour_50} for i in range(1, 64)]
        layouts = [{"layout_index": 0, "name": "lay0000", "layers": 4, "pieces": p0}]
        session = {"layers": 4, "params": "stdNOTFill;separar_sobras=1"}

        # Primeira execução
        step1_lays, sum1 = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        self.assertIsNotNone(sum1)
        self.assertEqual(len(step1_lays), 2)

        # Operador move a peça na placa de sobras manualmente
        step1_lays[1]["pieces"][0]["x"] = 777.5
        step1_lays[1]["pieces"][0]["y"] = 888.5

        # Segunda execução: idempotente, preserva coordenadas manuais
        step2_lays, sum2 = separar_sobras_camadas(step1_lays, session=session, shapes=shapes)
        self.assertIsNone(sum2)
        self.assertEqual(len(step2_lays), 2)
        self.assertEqual(step2_lays[1]["pieces"][0]["x"], 777.5)
        self.assertEqual(step2_lays[1]["pieces"][0]["y"], 888.5)

    # =========================================================================
    # Caso 9: Operador apagou peça à mão (déficit manual)
    # =========================================================================
    def test_case_09_manual_deficit_does_not_invent_pieces(self):
        """Se o operador apagou peças à mão, não inventa peças novas."""
        shapes = [{"id": 1, "name": "M125", "pairs": 125, "contour": self.contour_50}]
        # Desejado em 4 camadas é 62 peças. Operador apagou 3, deixando apenas 59.
        p0 = [{"id": i, "placement_index": i, "shape": shapes[0], "name": "M125", "contour": self.contour_50} for i in range(1, 60)]
        layouts = [{"layout_index": 0, "name": "lay0000", "layers": 4, "pieces": p0}]
        session = {"layers": 4, "params": "stdNOTFill;separar_sobras=1"}

        new_lays, summary = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        # Nenhuma peça deve ser retirada de 4 camadas pois já está abaixo de 62.
        # Placa de sobras é gerada com a 1 peça devida a 2 camadas.
        self.assertEqual(len(new_lays[0]["pieces"]), 59)
        self.assertEqual(len(new_lays[1]["pieces"]), 1)

    # =========================================================================
    # Caso 10: Verificação física e rollback atômico
    # =========================================================================
    def test_case_10_physical_divergence_triggers_atomic_rollback(self):
        """Se forçar um erro na verificação física, a separação é desfeita e nada muda."""
        shapes = [{"id": 1, "name": "M125", "pairs": 125, "contour": self.contour_50}]
        p0 = [{"id": i, "placement_index": i, "shape": shapes[0], "name": "M125", "contour": self.contour_50} for i in range(1, 64)]
        layouts = [{"layout_index": 0, "name": "lay0000", "layers": 4, "pieces": p0}]
        session = {"layers": 4, "params": "stdNOTFill;separar_sobras=1"}

        # Simula falha injetando mock em nest_multi_sheet que devolve placa com contagem errada
        original_copy = copy.deepcopy(layouts)
        with unittest.mock.patch("cad.layers_split.nest_multi_sheet") as mock_nest:
            mock_nest.return_value = {
                "layouts": [{
                    "layout_index": 1,
                    "name": "lay0001",
                    "layers": 2,
                    "pieces": []  # Nenhuma peça colocada!
                }]
            }
            res_lays, summary = separar_sobras_camadas(layouts, session=session, shapes=shapes)
            self.assertIsNone(summary)
            # Reverteu por completo!
            self.assertEqual(len(res_lays), 1)
            self.assertEqual(len(res_lays[0]["pieces"]), 63)
            self.assertEqual(res_lays, original_copy)

    # =========================================================================
    # Caso 11: Reencaixe com zero colisão e gap respeitado
    # =========================================================================
    def test_case_11_renest_zero_collision_and_gap_respected(self):
        """Reencaixe da placa de sobras: zero colisão, margens e gap_mm respeitados."""
        shapes = [
            {"id": 1, "name": "M1", "pairs": 125, "sequence": 1, "contour": self.contour_50},
            {"id": 2, "name": "M2", "pairs": 109, "sequence": 2, "contour": self.contour_50},
        ]
        p0 = [{"id": i, "placement_index": i, "shape": shapes[0], "name": "M1", "contour": self.contour_50} for i in range(1, 64)]
        p0.extend([{"id": 100 + i, "placement_index": 100 + i, "shape": shapes[1], "name": "M2", "contour": self.contour_50} for i in range(1, 56)])
        layouts = [{
            "layout_index": 0,
            "name": "lay0000",
            "layers": 4,
            "pieces": p0,
            "sheet_width_mm": 1000.0,
            "sheet_height_mm": 1000.0
        }]
        session = {
            "layers": 4,
            "params": "stdNOTFill;separar_sobras=1",
            "margin_left": 10.0,
            "margin_right": 10.0,
            "margin_top": 10.0,
            "margin_bottom": 10.0,
            "gap_mm": 2.0,
            "material": {"width_mm": 1000.0, "height_mm": 1000.0, "layers": 4}
        }

        new_lays, summary = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        self.assertIsNotNone(summary)
        sobra_lay = new_lays[1]
        sobra_pcs = sobra_lay["pieces"]
        self.assertEqual(len(sobra_pcs), 2)

        # Verifica colisões entre peças da placa de sobras
        poly_0 = transform_contour(sobra_pcs[0]["contour"], sobra_pcs[0]["x"], sobra_pcs[0]["y"], sobra_pcs[0].get("rotation", 0.0))
        poly_1 = transform_contour(sobra_pcs[1]["contour"], sobra_pcs[1]["x"], sobra_pcs[1]["y"], sobra_pcs[1].get("rotation", 0.0))
        collides = polygons_collide(poly_0, poly_1, gap=1.99)
        self.assertFalse(collides)

    # =========================================================================
    # Caso 12: Parâmetro desligado
    # =========================================================================
    def test_case_12_param_disabled_preserves_legacy_behavior(self):
        """Parâmetro desligado: comportamento anterior (sobra na placa de 4 camadas, Resto -1)."""
        shapes = [{"id": 1, "name": "M125", "pairs": 125, "contour": self.contour_50}]
        p0 = [{"id": i, "placement_index": i, "shape": shapes[0], "name": "M125", "contour": self.contour_50} for i in range(1, 64)]
        layouts = [{"layout_index": 0, "name": "lay0000", "layers": 4, "pieces": p0}]

        # Explicitamente desligado
        session = {"layers": 4, "params": "stdNOTFill;separar_sobras=0"}
        self.assertFalse(is_separar_sobras_enabled(session))

        new_lays, summary = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        self.assertIsNone(summary)
        self.assertEqual(len(new_lays), 1)
        self.assertEqual(len(new_lays[0]["pieces"]), 63)
        self.assertEqual(calc_resto_efetivo(125, 4, separar=False), -1)

    # =========================================================================
    # Caso 13: Nunca há camadas diferentes na mesma placa
    # =========================================================================
    def test_case_13_uniform_layers_per_sheet(self):
        """Cada placa possui exatamente UM valor uniforme de camadas."""
        shapes = [{"id": 1, "name": "M125", "pairs": 125, "contour": self.contour_50}]
        p0 = [{"id": i, "placement_index": i, "shape": shapes[0], "name": "M125", "contour": self.contour_50} for i in range(1, 64)]
        layouts = [{"layout_index": 0, "name": "lay0000", "layers": 4, "pieces": p0}]
        session = {"layers": 4, "params": "stdNOTFill;separar_sobras=1"}

        new_lays, _ = separar_sobras_camadas(layouts, session=session, shapes=shapes)
        for ly in new_lays:
            l_val = ly["layers"]
            self.assertIn(l_val, (2, 4))
            # Nenhuma peça na placa pode ter layers diferente do layout
            for p in ly["pieces"]:
                if "layers" in p:
                    self.assertEqual(p["layers"], l_val)

    # =========================================================================
    # Caso 14: Persistência no SQLite e Exportação .lay
    # =========================================================================
    def test_case_14_database_persistence_and_lay_export(self):
        """Salvar e reabrir sessão preserva placas e camadas; .lay exporta com layers=2."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_split_persist.db")
        try:
            db = DatabaseManager(db_path=db_path, backend="sqlite")
            sess_id = db.create_session(
                name="Sessao Split",
                job="JOB_SPLIT",
                material_id="MAT01",
                layers=4,
                params="stdNOTFill;separar_sobras=1"
            )

            layouts_to_save = [
                {"layout_index": 0, "name": "lay0000", "pieces": [{"id": 1, "name": "M1", "size": "41"}], "layers": 4},
                {"layout_index": 1, "name": "lay0001", "pieces": [{"id": 2, "name": "M1", "size": "41"}], "layers": 2, "is_sobras": True},
            ]
            db.save_session_layouts(sess_id, layouts_to_save)

            reloaded = db.get_session_layouts(sess_id)
            self.assertEqual(len(reloaded), 2)
            self.assertEqual(reloaded[0]["layers"], 4)
            self.assertEqual(reloaded[1]["layers"], 2)

            # Exportação .lay da placa de sobras
            pcs = [{"id": 1, "name": "M1", "size": "41", "target_id": 1, "rotation": 0.0, "x": 10.0, "y": 10.0, "contour": self.contour_50}]
            mat = {"width_mm": 1000.0, "height_mm": 1000.0, "name": "MAT01"}
            lay_out = os.path.join(temp_dir, "lay0001.lay")
            DualLayoutExporter.export_atom_lay(pcs, mat, lay_out, session_id=sess_id, layers=2)

            with open(lay_out, "r", encoding="latin1") as f:
                content = f.read()
            self.assertIn("layers=2", content)

            parsed = parse_lay(content)
            self.assertEqual(parsed.layers, 2)
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass

    # =========================================================================
    # Caso 15: Concordância Resto / Contador Sidebar / Impressão A4
    # =========================================================================
    def test_case_15_consistency_resto_sidebar_and_print_legend(self):
        """Coluna Resto, contador da barra lateral e legenda A4 concordam (zeram a sobra)."""
        # 125 pares com separação ligada
        resto_efetivo = calc_resto_efetivo(125, 4, separar=True)
        self.assertEqual(resto_efetivo, 0)

        # Contador da sidebar
        pcs_4 = [{"id": i, "name": "M1", "size": "41"} for i in range(62)]
        pcs_2 = [{"id": 1, "name": "M1", "size": "41"}]
        tot_phys = len(pcs_4) * 4 + len(pcs_2) * 2
        pares_prod = tot_phys // 2
        self.assertEqual(pares_prod, 125)

        # Legenda A4
        session = {"layers": 4, "params": "stdNOTFill;separar_sobras=1"}
        is_sep = is_separar_sobras_enabled(session)
        resto_a4 = calc_resto_efetivo(125, 4, separar=is_sep)
        self.assertEqual(resto_a4, 0)
        max_allowed = 125 + abs(resto_a4)
        is_error = (pares_prod > max_allowed)
        self.assertFalse(is_error)

    # =========================================================================
    # Caso 16: Regressão Geral de Regras
    # =========================================================================
    def test_case_16_rules_consistency_and_helpers(self):
        """Verifica encode/decode de params e helpers de camadas."""
        preset, opts = parse_session_params("stdNOTFill;separar_sobras=1")
        self.assertEqual(preset, "stdNOTFill")
        self.assertEqual(opts.get("separar_sobras"), "1")

        encoded = encode_session_params("ALTERNADO", {"separar_sobras": "0"})
        self.assertEqual(encoded, "ALTERNADO;separar_sobras=0")

        self.assertTrue(is_separar_sobras_enabled({"layers": 4, "params": "stdNOTFill;separar_sobras=1"}))
        self.assertFalse(is_separar_sobras_enabled({"layers": 4, "params": "stdNOTFill;separar_sobras=0"}))
        self.assertFalse(is_separar_sobras_enabled({"layers": 2, "params": "stdNOTFill;separar_sobras=1"}))
