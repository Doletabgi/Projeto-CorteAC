"""
Testes automatizados completos para Nesting em Múltiplas Placas (Multi-Sheet Nesting).
Cobre:
1. Demanda em 1 placa (regressão) -> lay0000 único.
2. Demanda multi-placa (ex: 200 pares em chapa finita) -> N layouts (lay0000, lay0001, ...).
3. Placas intermediárias preenchidas e última placa com resíduo.
4. Molde oversized / não encaixável -> parada imediata e segura sem laço infinito.
5. Limite de segurança max_sheets atingido.
6. Regra de camadas N_lay = ceil((P * 2) / L) aplicada à demanda total da sessão.
7. Persistência de layouts múltiplos no SQLite e compatibilidade com sessões legadas.
8. Navegação no LayoutEditorView (Ctrl+L, Ctrl+Shift+L, isolamento de undo, foco em Entry).
9. Contadores da barra lateral no LayoutEditorView ({cnt} placa | {tot}/{req}).
10. Exportação dual (export_multi_sheet_dual) gerando lay0000.lay, lay0001.lay etc. válidos para parse_lay.
"""

import unittest
import math
import tempfile
import os
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from cad.nesting_engine import (
    nest_multi_sheet,
    auto_nest_pieces,
    piece_matches_shape,
    polygon_bbox,
    sort_shapes_by_sequence,
    parse_sequence_num,
)
from cad.dual_exporter import export_multi_sheet_dual
from cad.lay_parser import parse_lay
from unittest.mock import patch, MagicMock
from database import DatabaseManager
from ui.layout_editor_view import (
    LayoutEditorView,
    rotate_piece_in_place,
)
from ui.session_view import SessionView


class DummyEvent:
    def __init__(self, char="", keysym=""):
        self.char = char
        self.keysym = keysym


class TestMultiSheetNesting(unittest.TestCase):
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
        # Molde retangular padrão 100x100 mm
        self.box_100 = [
            {"x": 0.0, "y": 0.0},
            {"x": 100.0, "y": 0.0},
            {"x": 100.0, "y": 100.0},
            {"x": 0.0, "y": 100.0}
        ]
        self.shape_item = {
            "id": 1,
            "name": "Box100",
            "size": "41",
            "pairs": 10,
            "sequence": 1,
            "contour": self.box_100
        }

    # =========================================================================
    # 1. Regressão: Demanda pequena que cabe em 1 placa única (lay0000)
    # =========================================================================
    def test_single_sheet_demand_creates_only_lay0000(self):
        # Chapa 1000x1000 mm cabe facilmente 10 peças (10 pares com 2 camadas = 10 peças)
        res = nest_multi_sheet(
            available_shapes=[self.shape_item],
            bed_width_mm=1000.0,
            bed_height_mm=1000.0,
            strategy="flashnestsheet",
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            layers=2
        )
        self.assertTrue(res["success"])
        self.assertEqual(len(res["layouts"]), 1)
        self.assertEqual(res["num_sheets"], 1)
        self.assertEqual(res["layouts"][0]["name"], "lay0000")
        self.assertEqual(res["layouts"][0]["layout_index"], 0)
        self.assertEqual(res["total_pieces"], 10)
        self.assertEqual(res["total_pairs_cut"], 10)
        self.assertEqual(len(res["unplaced_shapes"]), 0)

    # =========================================================================
    # 2. Demanda multi-placa: 200 pares em chapa finita gerando N > 1 placas
    # =========================================================================
    def test_multi_sheet_large_demand_sequential_naming_and_margins(self):
        # Chapa 250x250 mm com margens de 10 mm -> área útil 230x230 mm.
        # Cabe no máximo 4 caixas de 100x100 mm por chapa.
        # Pedido de 12 pares (layers=2 -> 12 peças necessárias).
        # Precisará de pelo menos 3 placas de 4 peças.
        shape_12p = dict(self.shape_item)
        shape_12p["pairs"] = 12

        res = nest_multi_sheet(
            available_shapes=[shape_12p],
            bed_width_mm=250.0,
            bed_height_mm=250.0,
            strategy="flashnestsheet",
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            layers=2
        )
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["num_sheets"], 3)
        self.assertEqual(res["total_pieces"], 12)
        self.assertEqual(res["total_pairs_cut"], 12)

        # Verifica nomes sequenciais lay0000, lay0001, lay0002...
        for idx, ly in enumerate(res["layouts"]):
            expected_name = f"lay{idx:04d}"
            self.assertEqual(ly["name"], expected_name)
            self.assertEqual(ly["layout_index"], idx)
            # Verifica que todas as peças respeitam as margens da chapa
            for p in ly["pieces"]:
                px, py = p["x"], p["y"]
                self.assertGreaterEqual(px, 10.0 - 1e-3)
                self.assertGreaterEqual(py, 10.0 - 1e-3)
                # bounding box da peça não pode ultrapassar bed - margem
                self.assertLessEqual(px + 100.0, 240.0 + 1e-3)
                self.assertLessEqual(py + 100.0, 240.0 + 1e-3)

    # =========================================================================
    # 3. Placas intermediárias preenchidas e última placa com resíduo
    # =========================================================================
    def test_intermediate_sheets_full_and_last_sheet_has_remainder(self):
        # Chapa 250x250 mm cabe 4 peças. Demanda de 10 peças (10 pares / 2 camadas = 10 peças)
        # Placa 0: 4 peças (cheia)
        # Placa 1: 4 peças (cheia)
        # Placa 2: 2 peças (resíduo final)
        shape_10p = dict(self.shape_item)
        shape_10p["pairs"] = 10

        res = nest_multi_sheet(
            available_shapes=[shape_10p],
            bed_width_mm=250.0,
            bed_height_mm=250.0,
            strategy="flashnestsheet",
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            layers=2
        )
        self.assertTrue(res["success"])
        self.assertEqual(len(res["layouts"]), 3)
        self.assertEqual(len(res["layouts"][0]["pieces"]), 4)
        self.assertEqual(len(res["layouts"][1]["pieces"]), 4)
        self.assertEqual(len(res["layouts"][2]["pieces"]), 2)
        self.assertEqual(res["total_pieces"], 10)

    # =========================================================================
    # 4. Molde oversized / impossível de encaixar: parada imediata sem loop infinito
    # =========================================================================
    def test_oversized_shape_terminates_immediately_without_infinite_loop(self):
        # Chapa de 100x100 com margens de 10 -> útil 80x80 mm.
        # Molde de 100x100 mm não cabe!
        res = nest_multi_sheet(
            available_shapes=[self.shape_item],
            bed_width_mm=100.0,
            bed_height_mm=100.0,
            strategy="flashnestsheet",
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            layers=2
        )
        self.assertFalse(res["success"])
        self.assertEqual(len(res["layouts"]), 0)
        self.assertIn("Box100", res["unplaced_shapes"])
        self.assertIsNotNone(res["warning"])
        self.assertIn("excede a área útil", res["warning"])

    # =========================================================================
    # 5. Limite de segurança max_sheets atingido
    # =========================================================================
    def test_max_sheets_safety_limit(self):
        # Chapa cabe 4 peças. Demanda de 20 peças precisaria de 5 chapas.
        # Mas configuramos max_sheets=2.
        shape_20p = dict(self.shape_item)
        shape_20p["pairs"] = 20

        res = nest_multi_sheet(
            available_shapes=[shape_20p],
            bed_width_mm=250.0,
            bed_height_mm=250.0,
            strategy="flashnestsheet",
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            layers=2,
            max_sheets=2
        )
        self.assertFalse(res["success"])
        self.assertEqual(len(res["layouts"]), 2)
        self.assertEqual(res["num_sheets"], 2)
        self.assertIsNotNone(res["warning"])
        self.assertIn("Limite de segurança de 2 placas atingido", res["warning"])
        self.assertIn("Box100", res["unplaced_shapes"])

    # =========================================================================
    # 6. Regra de camadas N_lay = ceil((P * 2) / L) aplicada à demanda total
    # =========================================================================
    def test_layer_formula_total_demand(self):
        # 15 pares com 1 camada -> ceil((15 * 2) / 1) = 30 peças
        # Chapa 500x500 mm cabe 16 peças (4x4 caixas de 100x100)
        # Placa 0: 16 peças
        # Placa 1: 14 peças
        # Total: 30 peças
        shape_15p = dict(self.shape_item)
        shape_15p["pairs"] = 15

        res = nest_multi_sheet(
            available_shapes=[shape_15p],
            bed_width_mm=500.0,
            bed_height_mm=500.0,
            strategy="flashnestsheet",
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            layers=1
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["total_pieces"], 30)
        self.assertEqual(res["total_pairs_cut"], 15)
        self.assertEqual(len(res["layouts"]), 2)
        self.assertEqual(len(res["layouts"][0]["pieces"]), 16)
        self.assertEqual(len(res["layouts"][1]["pieces"]), 14)

    # =========================================================================
    # 7. Persistência de layouts múltiplos no Banco de Dados SQLite & Legado
    # =========================================================================
    def test_db_persistence_and_backward_compatibility(self):
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_jobmanager.db")
        try:
            db = DatabaseManager(db_path=db_path, backend="sqlite")
            sess_id = db.create_session(name="Sessao 1", job="JOB_MULTI", material_id="COURO", machine="Flex 3020")

            # Salva 3 layouts
            layouts_to_save = [
                {"layout_index": 0, "name": "lay0000", "pieces": [{"id": 1, "size": "41"}], "yield_pct": 85.0},
                {"layout_index": 1, "name": "lay0001", "pieces": [{"id": 2, "size": "41"}], "yield_pct": 82.0},
                {"layout_index": 2, "name": "lay0002", "pieces": [{"id": 3, "size": "41"}], "yield_pct": 40.0},
            ]
            ok = db.save_session_layouts(sess_id, layouts_to_save)
            self.assertTrue(ok)

            loaded = db.get_session_layouts(sess_id)
            self.assertEqual(len(loaded), 3)
            self.assertEqual([ly["name"] for ly in loaded], ["lay0000", "lay0001", "lay0002"])
            self.assertEqual(len(loaded[0]["pieces"]), 1)
            self.assertEqual(loaded[0]["pieces"][0]["id"], 1)
            self.assertEqual(len(loaded[2]["pieces"]), 1)

            # Teste de compatibilidade com sessão legada (sem registros na tabela layouts)
            sess_legacy_id = db.create_session(name="Sessao Legada", job="JOB_MULTI", material_id="COURO", machine="Flex 3020")
            # Simula sessão legada onde placed_pieces_json foi gravado diretamente em sessions
            legacy_pieces = [{"id": 10, "size": "38", "name": "Gaspea"}]
            db.update_session(sess_legacy_id, placed_pieces=legacy_pieces, yield_pct=75.0)

            # Ao chamar get_session_layouts para sessão legada, deve sintetizar lay0000
            legacy_lays = db.get_session_layouts(sess_legacy_id)
            self.assertEqual(len(legacy_lays), 1)
            self.assertEqual(legacy_lays[0]["name"], "lay0000")
            self.assertEqual(legacy_lays[0]["layout_index"], 0)
            self.assertEqual(len(legacy_lays[0]["pieces"]), 1)
            self.assertEqual(legacy_lays[0]["pieces"][0]["size"], "38")
            self.assertEqual(legacy_lays[0]["yield_percent"], 75.0)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # =========================================================================
    # 8. Navegação no LayoutEditorView (Ctrl+L, Ctrl+Shift+L, isolamento de undo)
    # =========================================================================
    def test_layout_editor_navigation_and_undo_isolation(self):
        if not self.root:
            self.skipTest("Tkinter display indisponível")

        editor = LayoutEditorView(self.root, is_subwindow=True)

        layouts_mock = [
            {
                "layout_index": 0,
                "name": "lay0000",
                "width_mm": 1000.0,
                "height_mm": 1000.0,
                "margin_left": 10.0,
                "margin_right": 10.0,
                "margin_top": 10.0,
                "margin_bottom": 10.0,
                "pieces": [{"id": 1, "x": 50.0, "y": 50.0, "rot": 0.0, "contour": self.box_100, "size": "41"}]
            },
            {
                "layout_index": 1,
                "name": "lay0001",
                "width_mm": 1000.0,
                "height_mm": 1000.0,
                "margin_left": 10.0,
                "margin_right": 10.0,
                "margin_top": 10.0,
                "margin_bottom": 10.0,
                "pieces": [
                    {"id": 2, "x": 60.0, "y": 60.0, "rot": 0.0, "contour": self.box_100, "size": "41"},
                    {"id": 3, "x": 200.0, "y": 200.0, "rot": 0.0, "contour": self.box_100, "size": "41"}
                ]
            }
        ]

        editor.set_session_layouts(layouts_mock, initial_index=0)
        self.assertEqual(editor.current_layout_index, 0)
        self.assertEqual(len(editor.placed_pieces), 1)
        self.assertIn("lay0000", editor.lbl_stat_doc.cget("text"))

        # Modifica a peça na placa 0 e empilha no undo
        editor.push_undo()
        editor.placed_pieces[0]["x"] = 99.0
        self.assertGreater(len(editor.undo_stack), 0)

        # Avança para a placa 1 com Ctrl+L
        editor._on_ctrl_l(DummyEvent(keysym="l"))
        self.assertEqual(editor.current_layout_index, 1)
        self.assertEqual(len(editor.placed_pieces), 2)
        self.assertIn("lay0001", editor.lbl_stat_doc.cget("text"))
        # A pilha de undo da placa 1 deve estar vazia (isolada da placa 0)
        self.assertEqual(len(editor.undo_stack), 0)

        # Volta para a placa 0 com Ctrl+Shift+L
        editor._on_ctrl_shift_l(DummyEvent(keysym="L"))
        self.assertEqual(editor.current_layout_index, 0)
        self.assertEqual(len(editor.placed_pieces), 1)
        # Pilha de undo da placa 0 foi restaurada
        self.assertGreater(len(editor.undo_stack), 0)

        # Testa trava de foco em widget Entry: atalho não deve navegar
        entry = ttk.Entry(editor)
        entry.focus_set()
        dummy_event_with_widget = DummyEvent(keysym="l")
        dummy_event_with_widget.widget = entry
        editor._on_ctrl_l(dummy_event_with_widget)
        # Deve permanecer no layout 0
        self.assertEqual(editor.current_layout_index, 0)

    # =========================================================================
    # 9. Contadores da barra lateral no LayoutEditorView ({cnt} placa | {tot}/{req})
    # =========================================================================
    def test_layout_editor_sidebar_counters(self):
        if not self.root:
            self.skipTest("Tkinter display indisponível")

        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": 1, "name": "Box100", "size": "41", "pairs": 6, "contour": self.box_100}
        ]
        editor.material_layers = 2  # 6 pares -> 6 peças exigidas no total

        layouts_mock = [
            {
                "layout_index": 0,
                "name": "lay0000",
                "width_mm": 1000.0,
                "height_mm": 1000.0,
                "pieces": [{"id": 1, "size": "41", "name": "Box100", "contour": self.box_100, "x": 50.0, "y": 50.0, "rotation": 0.0}] * 6
            },
            {
                "layout_index": 1,
                "name": "lay0001",
                "width_mm": 1000.0,
                "height_mm": 1000.0,
                "pieces": []
            }
        ]
        editor.set_session_layouts(layouts_mock, initial_index=0)
        editor.update_sidebar_targets()
        editor.redraw()

        # Verifica widgets/textos criados no sidebar do canvas
        # Em modo multi-placa, a palavra 'placa' (ex: '0 placa', '16 placa') foi completamente removida,
        # exibindo diretamente a relação limpa '6/6' (total da sessão / pedido total).
        found_clean_text = False
        for item in editor.canvas.find_withtag("sidebar_ui"):
            if editor.canvas.type(item) == "text":
                txt = editor.canvas.itemcget(item, "text")
                self.assertNotIn("placa", txt.lower(), f"A palavra 'placa' não deve aparecer nos contadores dos moldes: {txt}")
                if txt == "6/6":
                    found_clean_text = True
        self.assertTrue(found_clean_text, "Contador limpo '6/6' não encontrado na barra lateral")

        # Alterna para Placa 1 (0 peças nesta placa, mas total da sessão segue 6/6)
        editor.switch_to_layout(1)
        editor.redraw()

        found_clean_lay1 = False
        for item in editor.canvas.find_withtag("sidebar_ui"):
            if editor.canvas.type(item) == "text":
                txt = editor.canvas.itemcget(item, "text")
                self.assertNotIn("placa", txt.lower(), f"A palavra 'placa' não deve aparecer na placa 1: {txt}")
                if txt == "6/6":
                    found_clean_lay1 = True
        self.assertTrue(found_clean_lay1, "Contador limpo '6/6' não encontrado na Placa 1")

    # =========================================================================
    # 10. Exportação Dual (export_multi_sheet_dual) gerando N .lay e .onx
    # =========================================================================
    def test_export_multi_sheet_dual_generates_valid_files(self):
        temp_dir = tempfile.mkdtemp()
        try:
            layouts_mock = [
                {
                    "layout_index": 0,
                    "name": "lay0000",
                    "width_mm": 1000.0,
                    "height_mm": 1000.0,
                    "margin_left": 10.0,
                    "margin_right": 10.0,
                    "margin_top": 10.0,
                    "margin_bottom": 10.0,
                    "gap_mm": 1.0,
                    "pieces": [{"id": 1, "x": 50.0, "y": 50.0, "rot": 0.0, "contour": self.box_100, "size": "41"}]
                },
                {
                    "layout_index": 1,
                    "name": "lay0001",
                    "width_mm": 1000.0,
                    "height_mm": 1000.0,
                    "margin_left": 10.0,
                    "margin_right": 10.0,
                    "margin_top": 10.0,
                    "margin_bottom": 10.0,
                    "gap_mm": 1.0,
                    "pieces": [{"id": 2, "x": 60.0, "y": 60.0, "rot": 0.0, "contour": self.box_100, "size": "41"}]
                }
            ]

            material = {
                "name": "COURO_SINTETICO",
                "width_mm": 1000.0,
                "height_mm": 1000.0,
                "gap_mm": 1.0,
                "layers": 2
            }

            exported = export_multi_sheet_dual(
                layouts=layouts_mock,
                material=material,
                base_dir=temp_dir,
                stem_prefix="lay",
                session_id=1
            )

            self.assertEqual(len(exported), 2)
            self.assertEqual(exported[0]["name"], "lay0000")
            self.assertEqual(exported[1]["name"], "lay0001")

            lay0_path = exported[0]["lay_path"]
            onx0_path = exported[0]["onx_path"]
            lay1_path = exported[1]["lay_path"]
            onx1_path = exported[1]["onx_path"]

            self.assertTrue(os.path.exists(lay0_path))
            self.assertTrue(os.path.exists(onx0_path))
            self.assertTrue(os.path.exists(lay1_path))
            self.assertTrue(os.path.exists(onx1_path))

            # Valida com parse_lay round-trip
            parsed_lay0 = parse_lay(lay0_path)
            self.assertEqual(len(parsed_lay0.items), 1)
            self.assertEqual(parsed_lay0.ris_w, 1000.0)

            parsed_lay1 = parse_lay(lay1_path)
            self.assertEqual(len(parsed_lay1.items), 1)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # =========================================================================
    # 11. Ordem de Encaixe por Sequência: Out-of-order sequences (3, 1, 2)
    # =========================================================================
    def test_out_of_order_sequences_nested_strictly_1_2_3(self):
        """Demanda com sequências [3, 1, 2] deve ser encaixada na ordem estrita 1, 2, 3."""
        s3 = {"id": 101, "name": "MoldeSeq3", "size": "43", "pairs": 3, "sequence": 3, "contour": self.box_100}
        s1 = {"id": 102, "name": "MoldeSeq1", "size": "41", "pairs": 3, "sequence": 1, "contour": self.box_100}
        s2 = {"id": 103, "name": "MoldeSeq2", "size": "42", "pairs": 3, "sequence": 2, "contour": self.box_100}

        res = nest_multi_sheet(
            available_shapes=[s3, s1, s2],
            bed_width_mm=1000.0,
            bed_height_mm=1000.0,
            strategy="flashnestsheet",
            layers=2
        )
        self.assertTrue(res["success"])
        pieces = res["layouts"][0]["pieces"]
        # Total: 3 peças de cada (pairs 3 com layers 2 = 3 peças)
        self.assertEqual(len(pieces), 9)

        # As 3 primeiras devem ser do MoldeSeq1 (seq 1)
        for p in pieces[0:3]:
            self.assertEqual(p["name"], "MoldeSeq1")
        # As 3 seguintes devem ser do MoldeSeq2 (seq 2)
        for p in pieces[3:6]:
            self.assertEqual(p["name"], "MoldeSeq2")
        # As 3 últimas devem ser do MoldeSeq3 (seq 3)
        for p in pieces[6:9]:
            self.assertEqual(p["name"], "MoldeSeq3")

    # =========================================================================
    # 12. Prioridade Estrita [DECISÃO] (# CONFIRMAR NO WINDOWS): Não furar fila
    # =========================================================================
    def test_strict_priority_no_higher_sequence_before_lower_exhausted(self):
        """Molde de maior sequência JAMAIS entra na placa enquanto o de menor sequência tiver demanda pendente."""
        # Chapa 250x250 mm com margem 10 mm = área útil 230x230 mm.
        # Molde 100x100 mm com gap 1.0 mm -> cabem exatamente 4 peças por placa (2x2).
        s1 = {"id": 201, "name": "Seq1_Demand", "size": "41", "pairs": 6, "sequence": 1, "contour": self.box_100}
        s2 = {"id": 202, "name": "Seq2_Waiting", "size": "42", "pairs": 4, "sequence": 2, "contour": self.box_100}

        res = nest_multi_sheet(
            available_shapes=[s1, s2],
            bed_width_mm=250.0,
            bed_height_mm=250.0,
            strategy="flashnestsheet",
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            gap_mm=1.0,
            layers=2
        )
        self.assertTrue(res["success"])
        layouts = res["layouts"]
        # s1 precisa de 6 peças. Placa 0 cabe 4 peças de s1 (sobrando 2 peças de s1).
        # Na placa 0, NÃO pode haver NENHUMA peça de s2!
        lay0_pieces = layouts[0]["pieces"]
        self.assertEqual(len(lay0_pieces), 4)
        for p in lay0_pieces:
            self.assertEqual(p["name"], "Seq1_Demand", "Placa 0 não pode conter peças de sequência 2!")

        # Placa 1: recebe as 2 restantes de s1, esgotando s1. Em seguida recebe 2 de s2.
        lay1_pieces = layouts[1]["pieces"]
        self.assertEqual(len(lay1_pieces), 4)
        self.assertEqual(sum(1 for p in lay1_pieces if p["name"] == "Seq1_Demand"), 2)
        self.assertEqual(sum(1 for p in lay1_pieces if p["name"] == "Seq2_Waiting"), 2)

        # Placa 2: recebe as 2 restantes de s2.
        lay2_pieces = layouts[2]["pieces"]
        self.assertEqual(len(lay2_pieces), 2)
        for p in lay2_pieces:
            self.assertEqual(p["name"], "Seq2_Waiting")

    # =========================================================================
    # 13. Continuidade Multi-Placa e Rastreamento de Spans
    # =========================================================================
    def test_mold_spanning_multiple_sheets_continuity_and_count(self):
        """Molde seq 2 inicia em lay0000 e termina em lay0001, com contagem exata e spans."""
        # Chapa 250x250 mm -> 4 peças por placa
        # s1: 2 peças (esgota em lay0000)
        # s2: 5 peças (2 entram em lay0000, 3 entram em lay0001)
        s1 = {"id": 301, "name": "MoldeA", "size": "41", "pairs": 2, "sequence": 1, "contour": self.box_100}
        s2 = {"id": 302, "name": "MoldeB", "size": "42", "pairs": 5, "sequence": 2, "contour": self.box_100}

        res = nest_multi_sheet(
            available_shapes=[s1, s2],
            bed_width_mm=250.0,
            bed_height_mm=250.0,
            strategy="flashnestsheet",
            margins={"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0},
            gap_mm=1.0,
            layers=2
        )
        self.assertTrue(res["success"])
        self.assertEqual(len(res["layouts"]), 2)
        self.assertEqual(res["total_pieces"], 7)

        # Verifica rastreamento de spans retornado
        spans = {s["name"]: s for s in res["shape_spans"]}
        self.assertIn("MoldeA", spans)
        self.assertIn("MoldeB", spans)

        self.assertEqual(spans["MoldeA"]["start_layout"], "lay0000")
        self.assertEqual(spans["MoldeA"]["end_layout"], "lay0000")
        self.assertEqual(spans["MoldeB"]["start_layout"], "lay0000")
        self.assertEqual(spans["MoldeB"]["end_layout"], "lay0001")
        self.assertIn("lay0000 → lay0001", spans["MoldeB"]["span_text"])

    # =========================================================================
    # 14. Empates de Sequência mantêm Ordem Estável da Grade
    # =========================================================================
    def test_sequence_ties_preserve_stable_grid_row_order(self):
        """Empates na coluna Sequência mantêm rigorosamente a ordem estável de entrada da grade."""
        sA = {"id": 401, "name": "First_Tie", "size": "41", "pairs": 2, "sequence": 2, "contour": self.box_100}
        sB = {"id": 402, "name": "Second_Tie", "size": "42", "pairs": 2, "sequence": 2, "contour": self.box_100}
        sC = {"id": 403, "name": "Third_Tie", "size": "43", "pairs": 2, "sequence": 2, "contour": self.box_100}

        res = nest_multi_sheet(
            available_shapes=[sA, sB, sC],
            bed_width_mm=1000.0,
            bed_height_mm=1000.0,
            strategy="flashnestsheet",
            layers=2
        )
        self.assertTrue(res["success"])
        pieces = res["layouts"][0]["pieces"]
        self.assertEqual(len(pieces), 6)
        self.assertEqual([p["name"] for p in pieces], [
            "First_Tie", "First_Tie",
            "Second_Tie", "Second_Tie",
            "Third_Tie", "Third_Tie"
        ])

    # =========================================================================
    # 15. Sequência Ausente / Vazia / Inválida vai para o Final com Aviso
    # =========================================================================
    def test_missing_or_invalid_sequence_placed_at_end_with_warning(self):
        """Sequências vazias (''), None ou alfanuméricas inválidas vão para o fim da fila em ordem estável com aviso."""
        s_valid = {"id": 501, "name": "ValidSeq", "size": "40", "pairs": 2, "sequence": 1, "contour": self.box_100}
        s_empty = {"id": 502, "name": "EmptySeq", "size": "41", "pairs": 2, "sequence": "", "contour": self.box_100}
        s_none = {"id": 503, "name": "NoneSeq", "size": "42", "pairs": 2, "sequence": None, "contour": self.box_100}
        s_invalid = {"id": 504, "name": "InvalidSeq", "size": "43", "pairs": 2, "sequence": "xyz", "contour": self.box_100}

        res = nest_multi_sheet(
            available_shapes=[s_empty, s_none, s_valid, s_invalid],
            bed_width_mm=1000.0,
            bed_height_mm=1000.0,
            strategy="flashnestsheet",
            layers=2
        )
        self.assertTrue(res["success"])
        self.assertIsNotNone(res["missing_sequence_warning"])
        self.assertIn("EmptySeq", res["missing_sequence_warning"])
        self.assertIn("NoneSeq", res["missing_sequence_warning"])
        self.assertIn("InvalidSeq", res["missing_sequence_warning"])

        pieces = res["layouts"][0]["pieces"]
        # ValidSeq deve ser a primeira a ser colocada
        self.assertEqual(pieces[0]["name"], "ValidSeq")
        self.assertEqual(pieces[1]["name"], "ValidSeq")

        # Em seguida as sem sequência na ordem relativa original
        self.assertEqual(pieces[2]["name"], "EmptySeq")
        self.assertEqual(pieces[3]["name"], "EmptySeq")
        self.assertEqual(pieces[4]["name"], "NoneSeq")
        self.assertEqual(pieces[5]["name"], "NoneSeq")
        self.assertEqual(pieces[6]["name"], "InvalidSeq")
        self.assertEqual(pieces[7]["name"], "InvalidSeq")

    # =========================================================================
    # 16. Edição Pós-Cálculo da Coluna Sequência Não Altera Layouts Já Gerados
    # =========================================================================
    def test_sequence_change_after_nesting_does_not_alter_existing_layouts(self):
        """Alterar o valor da coluna Sequência na grade após o cálculo não modifica retroativamente os layouts persistidos."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_seq_edit.db")
        try:
            db = DatabaseManager(db_path=db_path)
            sess_id = db.create_session(name="SeqJob", job="TestJob")

            s1 = {"id": 601, "name": "Molde1", "size": "41", "pairs": 2, "sequence": 1, "contour": self.box_100}
            s2 = {"id": 602, "name": "Molde2", "size": "42", "pairs": 2, "sequence": 2, "contour": self.box_100}
            db.update_session_shapes(sess_id, [s1, s2])

            res = nest_multi_sheet(
                available_shapes=[s1, s2],
                bed_width_mm=1000.0,
                bed_height_mm=1000.0,
                strategy="flashnestsheet",
                layers=2
            )
            db.save_session_layouts(sess_id, res["layouts"])

            # Usuário edita a sequência no grid: inverte para s1=99 e s2=1
            s1_edited = dict(s1)
            s1_edited["sequence"] = 99
            s2_edited = dict(s2)
            s2_edited["sequence"] = 1
            db.update_session_shapes(sess_id, [s1_edited, s2_edited])

            # Carrega layouts do DB: devem permanecer idênticos ao cálculo original (s1 primeiro)
            saved_lays = db.get_session_layouts(sess_id)
            self.assertEqual(len(saved_lays), 1)
            lay_pieces = saved_lays[0]["pieces"]
            self.assertEqual(lay_pieces[0]["name"], "Molde1")
            self.assertEqual(lay_pieces[1]["name"], "Molde1")
            self.assertEqual(lay_pieces[2]["name"], "Molde2")
            self.assertEqual(lay_pieces[3]["name"], "Molde2")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # =========================================================================
    # 17. Neutralização de Ordenação por Área/Tamanho em Favor da Sequência
    # =========================================================================
    def test_nesting_engine_does_not_reorder_by_area_over_sequence(self):
        """Molde menor com seq 1 e molde maior com seq 2 -> molde menor com seq 1 deve vir antes."""
        small_box = [
            {"x": 0.0, "y": 0.0},
            {"x": 40.0, "y": 0.0},
            {"x": 40.0, "y": 40.0},
            {"x": 0.0, "y": 40.0}
        ]
        large_box = [
            {"x": 0.0, "y": 0.0},
            {"x": 120.0, "y": 0.0},
            {"x": 120.0, "y": 120.0},
            {"x": 0.0, "y": 120.0}
        ]
        s_small = {"id": 701, "name": "SmallMold", "size": "34", "pairs": 2, "sequence": 1, "contour": small_box}
        s_large = {"id": 702, "name": "LargeMold", "size": "44", "pairs": 2, "sequence": 2, "contour": large_box}

        res = nest_multi_sheet(
            available_shapes=[s_large, s_small],
            bed_width_mm=1000.0,
            bed_height_mm=1000.0,
            strategy="flashnestsheet",
            layers=2
        )
        self.assertTrue(res["success"])
        pieces = res["layouts"][0]["pieces"]
        self.assertEqual(pieces[0]["name"], "SmallMold", "Molde com seq 1 deve vir antes mesmo tendo área menor!")
        self.assertEqual(pieces[1]["name"], "SmallMold")
        self.assertEqual(pieces[2]["name"], "LargeMold")
        self.assertEqual(pieces[3]["name"], "LargeMold")

    # =========================================================================
    # 18. Seleção de Linhas de Layout na SessionView e Atualização do Preview
    # =========================================================================
    def test_session_view_layout_selection_updates_preview_and_indicator(self):
        """Selecionar a linha lay_1 deve atualizar o indicador ▶ e desenhar as peças da placa 1."""
        if not self.root:
            self.skipTest("Tkinter indisponível em ambiente headless")

        from ui.session_view import SessionView

        box = [{"x": 0.0, "y": 0.0}, {"x": 50.0, "y": 0.0}, {"x": 50.0, "y": 30.0}, {"x": 0.0, "y": 30.0}]
        sess_data = {
            "id": 991,
            "name": "MultiSheetViewTest",
            "status": "Nested",
            "sheet_width": 1000.0,
            "sheet_height": 800.0,
            "layouts": [
                {
                    "layout_index": 0,
                    "name": "lay0000",
                    "pieces": [{"name": "P0", "x": 10.0, "y": 10.0, "contour": box, "rotation": 0.0}],
                    "yield_percent": 60.0
                },
                {
                    "layout_index": 1,
                    "name": "lay0001",
                    "pieces": [
                        {"name": "P1_a", "x": 20.0, "y": 20.0, "contour": box, "rotation": 0.0},
                        {"name": "P1_b", "x": 80.0, "y": 20.0, "contour": box, "rotation": 0.0}
                    ],
                    "yield_percent": 80.0
                }
            ]
        }

        view = SessionView(self.root, session_data=sess_data)
        view.load_session(sess_data)

        # Inicialmente lay_0 está selecionado com indicador ▶
        row0_vals = view.tree_lays.item("lay_0", "values")
        self.assertEqual(row0_vals[0], "▶")

        # Seleciona lay_1
        view.tree_lays.selection_set("lay_1")
        view.on_layout_selected()

        # Indicador ▶ deve ter mudado para lay_1 e sumido de lay_0
        row0_vals = view.tree_lays.item("lay_0", "values")
        row1_vals = view.tree_lays.item("lay_1", "values")
        self.assertEqual(row0_vals[0], "")
        self.assertEqual(row1_vals[0], "▶")

        # Verifica que botões do editor e preview estão habilitados
        self.assertEqual(view.btn_open_editor.cget("state"), "normal")
        self.assertEqual(view.btn_print_layout.cget("state"), "normal")
        self.assertEqual(view.btn_preview_open_editor.cget("state"), "normal")

        view.destroy()

    # =========================================================================
    # 19. Duplo Clique em Linha de Layout Aciona Callback com Nome da Placa
    # =========================================================================
    def test_session_view_double_click_opens_selected_layout(self):
        """Duplo clique na placa selecionada deve disparar callback on_open_layout_editor com o nome correto."""
        if not self.root:
            self.skipTest("Tkinter indisponível em ambiente headless")

        from ui.session_view import SessionView

        opened_calls = []
        def mock_open_editor(name):
            opened_calls.append(name)

        sess_data = {
            "id": 992,
            "name": "DoubleClickTest",
            "layouts": [
                {"layout_index": 0, "name": "lay0000", "pieces": []},
                {"layout_index": 1, "name": "lay0001", "pieces": []},
                {"layout_index": 2, "name": "lay0002", "pieces": []}
            ]
        }

        view = SessionView(self.root, session_data=sess_data, on_open_layout_editor=mock_open_editor)
        view.load_session(sess_data)

        # Seleciona lay_2 e aciona duplo clique
        view.tree_lays.selection_set("lay_2")
        view.on_layout_row_double_click()

        self.assertEqual(len(opened_calls), 1)
        self.assertEqual(opened_calls[0], "lay0002")

        view.destroy()

    # =========================================================================
    # 20. Resolução Dinâmica de Contornos Ausentes nas Peças
    # =========================================================================
    def test_contour_resolution_for_pieces_without_inline_contour(self):
        """Peças de layouts sem 'contour' embutido devem ter contorno resolvido por target_id/nome."""
        if not self.root:
            self.skipTest("Tkinter indisponível em ambiente headless")

        from ui.session_view import SessionView

        custom_contour = [{"x": 0.0, "y": 0.0}, {"x": 90.0, "y": 0.0}, {"x": 90.0, "y": 40.0}, {"x": 0.0, "y": 40.0}]
        sess_data = {
            "id": 993,
            "name": "ContourResolutionTest",
            "shapes": [
                {"id": 888, "name": "Gaspia", "size": "41", "contour": custom_contour}
            ],
            "layouts": [
                {
                    "layout_index": 0,
                    "name": "lay0000",
                    "pieces": [
                        {"target_id": 888, "name": "Gaspia", "size": "41", "x": 10.0, "y": 10.0, "rotation": 0.0}
                    ]
                }
            ]
        }

        view = SessionView(self.root, session_data=sess_data)
        piece = sess_data["layouts"][0]["pieces"][0]
        resolved = view._resolve_piece_contour(piece)
        self.assertEqual(resolved, custom_contour)

        # Teste também com LayoutEditorView
        editor = LayoutEditorView(self.root, load_sample=False)
        editor.set_session_shapes(sess_data["shapes"])
        editor.set_session_layouts(sess_data["layouts"], initial_index=0)
        self.assertEqual(len(editor.placed_pieces), 1)
        self.assertEqual(editor.placed_pieces[0]["contour"], custom_contour)

        view.destroy()
        editor.destroy()

    # =========================================================================
    # 21. MainWindow.show_layout_editor Suporta Sessão Multi-Placa sem Bloqueio
    # =========================================================================
    def test_main_window_show_layout_editor_with_multisheet_layouts(self):
        """MainWindow.show_layout_editor abre corretamente quando placed_pieces está vazio mas layouts existe."""
        from unittest.mock import MagicMock, patch
        from ui.main_window import MainWindow

        class DummyWin:
            def __init__(self):
                self.minimized_windows = []
                self.sessions = [{
                    "id": 994,
                    "placed_pieces": [],
                    "shapes": [],
                    "layouts": [
                        {"layout_index": 0, "name": "lay0000", "pieces": [{"name": "P0"}]},
                        {"layout_index": 1, "name": "lay0001", "pieces": [{"name": "P1"}]},
                        {"layout_index": 2, "name": "lay0002", "pieces": [{"name": "P2"}]}
                    ]
                }]
                self.current_session = self.sessions[0]
                self.current_material = None
                self.layout_editor_view = MagicMock()
                self.lbl_status_msg = MagicMock()
                self.maximize_window = MagicMock()
                self.restore_window = MagicMock()

        win = DummyWin()
        with patch("tkinter.messagebox.showwarning") as mock_warn:
            # Pede para abrir a placa lay0002
            MainWindow.show_layout_editor(win, layout_name="lay0002")
            mock_warn.assert_not_called()
            win.maximize_window.assert_called_once_with(win.layout_editor_view)
            # Verifica que set_session_layouts foi chamado com initial_index=2
            win.layout_editor_view.set_session_layouts.assert_called_once_with(
                win.current_session["layouts"],
                initial_index=2
            )
            # placed_pieces da sessão foi sincronizado
            self.assertEqual(win.current_session["placed_pieces"], [{"name": "P0"}])

    # =========================================================================
    # 22. Placa 0 exibe quantidade correta de instâncias (não exibe 0)
    # =========================================================================
    def test_plate_0_instances_count_and_fallback(self):
        """Verifica que a Placa 0 na grade tree_lays exibe sua quantidade correta de instâncias."""
        if not self.root:
            self.skipTest("Tkinter display indisponível")

        view = SessionView(self.root, db=None)

        # Caso A: Placa 0 com pieces vazio, mas session_data com placed_pieces (155 peças)
        session_mock = {
            "id": 881,
            "name": "Sessão Teste 155",
            "placed_pieces": [{"id": i, "name": "P1", "contour": self.box_100} for i in range(155)],
            "layouts": [
                {
                    "layout_index": 0,
                    "name": "lay0000",
                    "pieces": [],
                    "yield_percent": 74.22,
                    "cutting_time_sec": 132.0,
                    "num_items": 155
                },
                {
                    "layout_index": 1,
                    "name": "lay0001",
                    "pieces": [{"id": i, "name": "P2", "contour": self.box_100} for i in range(155)],
                    "yield_percent": 64.14,
                    "cutting_time_sec": 130.0,
                    "num_items": 155
                }
            ]
        }
        view.load_session(session_mock)

        # Inspeciona valores inseridos no tree_lays
        items = view.tree_lays.get_children()
        self.assertEqual(len(items), 2)

        # Placa 0: values = (indicator, N., Eficiência, Cortes_executar, Cortes_executados, Tempo, Instâncias, Área)
        vals_0 = view.tree_lays.item("lay_0", "values")
        self.assertEqual(vals_0[1], "0")          # N. 0
        self.assertEqual(vals_0[2], "74,22%")     # Eficiência 74,22%
        self.assertEqual(vals_0[6], "155")        # Instâncias NÃO É 0! É 155!

        # Placa 1:
        vals_1 = view.tree_lays.item("lay_1", "values")
        self.assertEqual(vals_1[1], "1")          # N. 1
        self.assertEqual(vals_1[2], "64,14%")     # Eficiência 64,14%
        self.assertEqual(vals_1[6], "155")        # Instâncias = 155

        # Caso B: pieces vazio e sem session placed_pieces, mas com num_items = 42
        session_mock_b = {
            "id": 882,
            "name": "Sessão Fallback num_items",
            "placed_pieces": [],
            "layouts": [
                {
                    "layout_index": 0,
                    "name": "lay0000",
                    "pieces": [],
                    "num_items": 42,
                    "yield_percent": 80.0
                }
            ]
        }
        view.load_session(session_mock_b)
        vals_b = view.tree_lays.item("lay_0", "values")
        self.assertEqual(vals_b[6], "42")         # Exibe 42 usando fallback de num_items

        view.destroy()

    # =========================================================================
    # 23. get_session_layouts com placed_pieces_json vazio recupera layout_pieces
    # =========================================================================
    def test_get_session_layouts_empty_json_fallback(self):
        """get_session_layouts recupera registros de layout_pieces mesmo com placed_pieces_json='[]'."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_empty_json.db")
        try:
            with patch("db.config.SQLITE_PATH", db_path), \
                 patch("db.config.DB_BACKEND", "sqlite"):
                db = DatabaseManager()
                sess_id = db.create_session(name="Sessao Empty JSON", job="JOB_T", material_id="MAT_T", machine="Flex")

                # Salva layout com 5 peças
                five_pieces = [{"id": i, "name": f"P{i}", "size": "41", "x": 10.0 * i, "y": 20.0, "rotation": 0.0} for i in range(1, 6)]
                db.save_session_layouts(sess_id, [{"layout_index": 0, "name": "lay0000", "pieces": five_pieces, "yield_pct": 77.0}])

                # Força placed_pieces_json para '[]' simulando banco antigo/legado
                with db.get_connection() as conn:
                    c = conn.cursor()
                    c.execute("UPDATE layouts SET placed_pieces_json = '[]' WHERE session_id = ?", (sess_id,))
                    conn.commit()

                # get_session_layouts deve cair no fallback e carregar as 5 peças de layout_pieces
                lays = db.get_session_layouts(sess_id)
                self.assertEqual(len(lays), 1)
                self.assertEqual(lays[0]["num_items"], 5)
                self.assertEqual(len(lays[0]["pieces"]), 5)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # =========================================================================
    # 24. DatabaseManager.delete_session_layouts
    # =========================================================================
    def test_database_delete_session_layouts(self):
        """delete_session_layouts remove layouts, peças e atualiza status da sessão para Stand by."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_del_lays.db")
        try:
            with patch("db.config.SQLITE_PATH", db_path), \
                 patch("db.config.DB_BACKEND", "sqlite"):
                db = DatabaseManager()
                sess_id = db.create_session(name="Sessao Exclusao", job="JOB_DEL", material_id="MAT_1", machine="Flex")

                # Salva 3 layouts com peças
                l_list = []
                for idx in range(3):
                    pcs = [{"id": i, "name": f"P{idx}_{i}", "size": "40", "x": 10.0 * i, "y": 20.0, "rotation": 0.0} for i in range(1, 5)]
                    l_list.append({"layout_index": idx, "name": f"lay000{idx}", "pieces": pcs, "yield_pct": 82.5})
                db.save_session_layouts(sess_id, l_list)

                saved_lays = db.get_session_layouts(sess_id)
                self.assertEqual(len(saved_lays), 3)
                saved_lay_ids = [l["id"] for l in saved_lays]

                # Executa delete_session_layouts
                res = db.delete_session_layouts(sess_id)
                self.assertTrue(res)

                # Verifica que get_session_layouts agora retorna lista vazia
                self.assertEqual(db.get_session_layouts(sess_id), [])

                # Verifica diretamente nas tabelas
                with db.get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT count(*) FROM layouts WHERE session_id = ?", (sess_id,))
                    self.assertEqual(c.fetchone()[0], 0)
                    placeholders = ",".join("?" for _ in saved_lay_ids)
                    c.execute(f"SELECT count(*) FROM layout_pieces WHERE layout_id IN ({placeholders})", tuple(saved_lay_ids))
                    self.assertEqual(c.fetchone()[0], 0)
                    c.execute("SELECT placed_pieces_json, yield_percent, status FROM sessions WHERE id = ?", (sess_id,))
                    row = c.fetchone()
                    self.assertEqual(row["placed_pieces_json"], "[]")
                    self.assertEqual(float(row["yield_percent"]), 0.0)
                    self.assertEqual(row["status"], "Stand by")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # =========================================================================
    # 25. Botão Refazer (on_clear_bed) começa do zero e restaura demanda dos moldes
    # =========================================================================
    def test_on_clear_bed_refazer_starts_from_zero_and_resets_demand(self):
        """Ao acionar on_clear_bed (Refazer), o layout da sessão é reiniciado do zero e demandas restauradas."""
        if not self.root:
            self.skipTest("Tkinter root indisponível")

        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_refazer.db")
        try:
            with patch("db.config.SQLITE_PATH", db_path), \
                 patch("db.config.DB_BACKEND", "sqlite"):
                db = DatabaseManager()
                sess_id = db.create_session(name="Sessao Refazer", job="JOB_R", material_id="MAT_1", machine="Flex")

                # Salva 2 layouts
                pcs = [{"id": 1, "name": "M1", "size": "40", "x": 10.0, "y": 20.0, "rotation": 0.0}]
                db.save_session_layouts(sess_id, [
                    {"layout_index": 0, "name": "lay0000", "pieces": pcs, "yield_pct": 75.0},
                    {"layout_index": 1, "name": "lay0001", "pieces": pcs, "yield_pct": 75.0}
                ])

                # Monta estado simulando MainWindow
                class MockMainWindow:
                    def __init__(self, database):
                        self.db = database
                        self.canvas = MagicMock()
                        self.lbl_status_msg = MagicMock()
                        self.current_mode = "jobs"
                        self.layout_editor_view = MagicMock()
                        self.current_shapes = [
                            {"id": 101, "name": "Gáspea", "pairs": 125, "rest": 0, "resto": 0, "layers": 2},
                            {"id": 102, "name": "Biqueira", "pairs": 109, "rest": 20, "resto": -1, "layers": 4}
                        ]
                        self.current_session = {
                            "id": sess_id,
                            "name": "Sessao Refazer",
                            "placed_pieces": pcs,
                            "layouts": [{"layout_index": 0}, {"layout_index": 1}],
                            "yield_percent": 75.0,
                            "cutting_time_sec": 120.0,
                            "used_area_m2": 0.8,
                            "status": "Nested",
                            "layers": 2,
                            "shapes": list(self.current_shapes)
                        }
                        self.sessions = [self.current_session]
                        self.open_sessions = {}
                        self.session_view = None

                    def switch_tree_mode(self, mode):
                        pass

                from ui.main_window import MainWindow
                win = MockMainWindow(db)
                sv = SessionView(self.root, session_data=win.current_session, db=db)
                win.session_view = sv

                # Executa on_clear_bed (método do MainWindow)
                MainWindow.on_clear_bed(win)

                # Verifica limpeza completa em memória
                self.assertEqual(win.current_session["placed_pieces"], [])
                self.assertEqual(win.current_session["layouts"], [])
                self.assertEqual(win.current_session["yield_percent"], 0.0)
                self.assertEqual(win.current_session["cutting_time_sec"], 0.0)
                self.assertEqual(win.current_session["used_area_m2"], 0.0)
                self.assertEqual(win.current_session["status"], "Stand by")

                # Verifica restauração das demandas nos moldes
                shp1 = next(s for s in win.current_shapes if s["id"] == 101)
                shp2 = next(s for s in win.current_shapes if s["id"] == 102)
                self.assertEqual(shp1["rest"], 125)
                self.assertEqual(shp1["resto"], 0)
                self.assertEqual(shp2["rest"], 109)
                self.assertEqual(shp2["resto"], 0)

                # Verifica que a grade tree_lays na SessionView ficou em branco
                self.assertEqual(len(sv.tree_lays.get_children()), 0)

                # Verifica que no banco os layouts foram removidos
                self.assertEqual(db.get_session_layouts(sess_id), [])

                sv.destroy()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # =========================================================================
    # 26. SessionView.clear_current_layout limpa multi-placas
    # =========================================================================
    def test_session_view_clear_current_layout(self):
        """clear_current_layout zera layouts e placed_pieces na SessionView."""
        if not self.root:
            self.skipTest("Tkinter root indisponível")

        mock_db = MagicMock()
        mock_db.delete_session_layouts.return_value = True

        sess_data = {
            "id": 999,
            "name": "Sessão Teste Limpar",
            "placed_pieces": [{"id": 1, "name": "P1", "contour": [(0, 0), (10, 0), (10, 10)]}],
            "layouts": [{"layout_index": 0, "name": "lay0000", "pieces": []}],
            "yield_percent": 85.0,
            "cutting_time_sec": 45.0,
            "status": "Nested",
            "layers": 2,
            "shapes": [{"id": 501, "name": "Talão", "pairs": 50, "rest": 0, "resto": 0}]
        }

        sv = SessionView(self.root, session_data=sess_data, db=mock_db)
        self.assertTrue(sv.has_calculated_layout())

        # Executa clear_current_layout sem prompt modal
        sv.clear_current_layout(ask_confirm=False)

        self.assertEqual(sess_data["placed_pieces"], [])
        self.assertEqual(sess_data["layouts"], [])
        self.assertEqual(sess_data["status"], "Stand by")
        self.assertEqual(sess_data["shapes"][0]["rest"], 50)
        self.assertFalse(sv.has_calculated_layout())
        self.assertEqual(len(sv.tree_lays.get_children()), 0)
        mock_db.delete_session_layouts.assert_called_once_with(999)

        sv.destroy()

    # =========================================================================
    # 27. LayoutEditorView.set_session_layouts com lista vazia reseta o editor
    # =========================================================================
    def test_layout_editor_set_session_layouts_empty_clears_editor(self):
        """set_session_layouts com lista vazia limpa layouts e peças do LayoutEditorView."""
        if not self.root:
            self.skipTest("Tkinter root indisponível")

        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.set_session_layouts([
            {"layout_index": 0, "name": "lay0000", "pieces": [{"id": 1, "contour": self.box_100}]},
            {"layout_index": 1, "name": "lay0001", "pieces": [{"id": 2, "contour": self.box_100}]}
        ], initial_index=0)
        self.assertEqual(len(editor.layouts), 2)

        # Chama com lista vazia
        editor.set_session_layouts([])
        self.assertEqual(editor.layouts, [])
        self.assertEqual(editor.placed_pieces, [])

        editor.destroy()


if __name__ == "__main__":
    unittest.main()

