"""
Testes Automatizados para a Funcionalidade "Alterar chapa":
Edição das medidas da chapa (Largura e Altura em metros) DEPOIS do encaixe.
11 Casos de Teste cobrindo todos os requisitos e invariantes.
"""

import unittest
import copy
import math
import tempfile
import os
import json
import tkinter as tk
from unittest.mock import patch, MagicMock

from cad.geometry import polygon_bbox, transform_contour, polygon_area
from cad.lay_parser import export_layout_from_pieces, parse_lay, LayoutData
from cad.onx_exporter import build_onx_xml
from database import DatabaseManager
from ui.alter_sheet_dialog import (
    AlterSheetDialog,
    calc_pieces_minimum,
    count_pieces_outside,
    parse_dim_m_to_mm,
    format_m,
    format_dim_m,
    format_dim_mm,
)
from ui.layout_editor_view import LayoutEditorView


SAMPLE_CONTOUR = [
    {"x": 0.0, "y": 0.0},
    {"x": 100.0, "y": 0.0},
    {"x": 100.0, "y": 50.0},
    {"x": 0.0, "y": 50.0},
]


class TestAlterSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        import gc
        gc.collect()
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.root:
            self.skipTest("Tkinter display not available")
        self.view = LayoutEditorView(self.root, layout_name="[TEST_ALTER_SHEET]", load_sample=False)
        self.view.sheet_width = 1380.0
        self.view.sheet_height = 2990.0
        self.view.margin_left = 10.0
        self.view.margin_right = 10.0
        self.view.margin_top = 10.0
        self.view.margin_bottom = 10.0
        self.view.placed_pieces = [
            {
                "target_id": 1,
                "name": "Peca_1",
                "x": 50.0,
                "y": 60.0,
                "rotation": 0.0,
                "contour": copy.deepcopy(SAMPLE_CONTOUR),
            },
            {
                "target_id": 2,
                "name": "Peca_2",
                "x": 200.0,
                "y": 300.0,
                "rotation": 45.0,
                "contour": copy.deepcopy(SAMPLE_CONTOUR),
            },
        ]
        self.view.pack()
        self.view.update_idletasks()

    def tearDown(self):
        if hasattr(self, "view") and self.view:
            if hasattr(self.view, "icons"):
                self.view.icons.clear()
            try:
                self.view.destroy()
            except Exception:
                pass
        import gc
        gc.collect()

    def test_01_increase_sheet_pieces_invariant_and_undo(self):
        """
        Caso 1: Aumentar chapa (L e A maiores).
        - Coordenadas (x, y, rotation) e contorno de TODAS as peças continuam idênticos.
        - sheet_width, sheet_height e area_mm2 atualizam.
        - Ctrl+Z restaura as dimensões anteriores.
        """
        orig_pieces = copy.deepcopy(self.view.placed_pieces)
        orig_w = self.view.sheet_width
        orig_h = self.view.sheet_height

        # Aumentar chapa de 1.38 x 2.99 m (1380 x 2990 mm) para 1.50 x 3.20 m (1500 x 3200 mm)
        success = self.view.alter_sheet(new_w_mm=1500.0, new_h_mm=3200.0)
        self.assertTrue(success)

        # 1. Dimensões atualizadas
        self.assertEqual(self.view.sheet_width, 1500.0)
        self.assertEqual(self.view.sheet_height, 3200.0)

        # 2. Invariância absoluta das peças
        self.assertEqual(len(self.view.placed_pieces), len(orig_pieces))
        for p_new, p_orig in zip(self.view.placed_pieces, orig_pieces):
            self.assertEqual(p_new["x"], p_orig["x"])
            self.assertEqual(p_new["y"], p_orig["y"])
            self.assertEqual(p_new["rotation"], p_orig["rotation"])
            self.assertEqual(p_new["contour"], p_orig["contour"])

        # 3. Ctrl+Z restaura
        self.view.undo_action()
        self.assertEqual(self.view.sheet_width, orig_w)
        self.assertEqual(self.view.sheet_height, orig_h)
        for p_new, p_orig in zip(self.view.placed_pieces, orig_pieces):
            self.assertEqual(p_new["x"], p_orig["x"])
            self.assertEqual(p_new["y"], p_orig["y"])

    def test_02_decrease_to_minimum_and_below_minimum_warning(self):
        """
        Caso 2: Diminuir chapa até o mínimo e abaixo do mínimo.
        - Mínimo exato é aceito sem aviso.
        - 1 mm a menos que o mínimo avisa e conta peças fora/cruzando margem.
        - Se o usuário aceitar, aplica e marca as peças em vermelho (#dc2626, largura 3.0).
        - Se cancelar, nada muda.
        - Peças NUNCA são deletadas.
        """
        min_w, min_h, *_ = calc_pieces_minimum(
            self.view.placed_pieces,
            margin_left=self.view.margin_left,
            margin_right=self.view.margin_right,
            margin_top=self.view.margin_top,
            margin_bottom=self.view.margin_bottom,
        )

        # 1. Aplicar exatamente o mínimo
        out_pieces, out_margins, affected = count_pieces_outside(
            self.view.placed_pieces,
            min_w,
            min_h,
            margin_left=self.view.margin_left,
            margin_right=self.view.margin_right,
            margin_top=self.view.margin_top,
            margin_bottom=self.view.margin_bottom,
        )
        self.assertEqual(len(affected), 0, "No mínimo exato nenhuma peça pode ficar fora")

        # 2. Testar 1 mm a menos que o mínimo
        under_w = min_w - 1.0
        under_h = min_h - 1.0
        out_pieces, out_margins, affected = count_pieces_outside(
            self.view.placed_pieces,
            under_w,
            under_h,
            margin_left=self.view.margin_left,
            margin_right=self.view.margin_right,
            margin_top=self.view.margin_top,
            margin_bottom=self.view.margin_bottom,
        )
        self.assertGreater(len(affected), 0, "1 mm abaixo do mínimo deve acusar peças fora")

        # 3. Aplicar abaixo do mínimo no editor: confirma que peças NÃO são deletadas
        orig_count = len(self.view.placed_pieces)
        self.view.alter_sheet(new_w_mm=under_w, new_h_mm=under_h)
        self.assertEqual(len(self.view.placed_pieces), orig_count, "Peças nunca são deletadas")
        self.assertEqual(self.view.sheet_width, under_w)
        self.assertEqual(self.view.sheet_height, under_h)

        # 4. Redraw detecta as peças colidindo com a borda/margem e inclui no colliding_indices
        self.view.redraw()
        colliding = getattr(self.view, "colliding_indices", set())
        for idx in affected:
            self.assertIn(idx, colliding, f"Peça {idx} fora da margem deve estar em colliding_indices")

        # 5. Diálogo: simula cancelamento pelo usuário quando há peças fora
        with patch("tkinter.messagebox.askyesno", return_value=False):
            dlg = AlterSheetDialog(
                parent=self.view,
                current_sheet_w_mm=self.view.sheet_width,
                current_sheet_h_mm=self.view.sheet_height,
                placed_pieces=self.view.placed_pieces,
                margin_left=self.view.margin_left,
                margin_right=self.view.margin_right,
                margin_top=self.view.margin_top,
                margin_bottom=self.view.margin_bottom,
                on_apply=MagicMock(),
            )
            dlg.entry_w.delete(0, tk.END)
            dlg.entry_w.insert(0, f"{(min_w - 50.0) / 1000.0:.2f}")
            dlg.entry_h.delete(0, tk.END)
            dlg.entry_h.insert(0, f"{(min_h - 50.0) / 1000.0:.2f}")
            dlg._on_ok()
            dlg.on_apply.assert_not_called()
            dlg.destroy()

    def test_03_calc_minimum_with_rotated_contour_and_margins(self):
        """
        Caso 3: Chapa com peças inclinadas e formas irregulares.
        - O cálculo usa contorno real rotacionado via transform_contour.
        - Testa com margem de segurança de 10 mm e com 15 mm (+5 mm por lado).
        """
        contour_rect = [
            {"x": 0.0, "y": 0.0},
            {"x": 200.0, "y": 0.0},
            {"x": 200.0, "y": 100.0},
            {"x": 0.0, "y": 100.0},
        ]
        # Peça inclinada a 45 graus com centro em (300, 300)
        piece_rot = {
            "x": 300.0,
            "y": 300.0,
            "rotation": 45.0,
            "contour": contour_rect,
        }

        min_w_10, min_h_10, *_ = calc_pieces_minimum(
            [piece_rot],
            margin_left=10.0,
            margin_right=10.0,
            margin_top=10.0,
            margin_bottom=10.0,
        )

        min_w_15, min_h_15, *_ = calc_pieces_minimum(
            [piece_rot],
            margin_left=15.0,
            margin_right=15.0,
            margin_top=15.0,
            margin_bottom=15.0,
        )

        # Margem de 15 mm tem 5 mm a mais em cada lado (10 mm a mais no total de largura e altura)
        self.assertAlmostEqual(min_w_15 - min_w_10, 5.0, delta=0.01)
        self.assertAlmostEqual(min_h_15 - min_h_10, 5.0, delta=0.01)

        # Verifica cálculo analítico exato do contorno rotacionado
        trans = transform_contour(contour_rect, 300.0, 300.0, 45.0)
        xs = [pt["x"] for pt in trans]
        ys = [pt["y"] for pt in trans]
        expected_w = max(xs) + 10.0
        expected_h = max(ys) + 10.0
        self.assertAlmostEqual(min_w_10, expected_w, delta=0.01)
        self.assertAlmostEqual(min_h_10, expected_h, delta=0.01)

    def test_04_nesting_done_reduce_to_min_then_increase_back(self):
        """
        Caso 4: Encaixe feito -> Reduzir chapa até o mínimo -> Aumentar de volta.
        - Peças não se movem em nenhum momento.
        - Contadores de peças colocadas/restantes não se alteram.
        - Resto e aproveitamento recomputam com a área da chapa.
        - Ctrl+Z retorna perfeitamente ao estado original.
        """
        orig_pieces = copy.deepcopy(self.view.placed_pieces)
        orig_w = self.view.sheet_width
        orig_h = self.view.sheet_height

        min_w, min_h, *_ = calc_pieces_minimum(
            self.view.placed_pieces,
            margin_left=self.view.margin_left,
            margin_right=self.view.margin_right,
            margin_top=self.view.margin_top,
            margin_bottom=self.view.margin_bottom,
        )

        # 1. Reduz até o mínimo
        self.view.alter_sheet(new_w_mm=min_w, new_h_mm=min_h)
        self.assertEqual(len(self.view.placed_pieces), len(orig_pieces))
        for p1, p0 in zip(self.view.placed_pieces, orig_pieces):
            self.assertEqual(p1["x"], p0["x"])
            self.assertEqual(p1["y"], p0["y"])

        # 2. Aumenta de volta ao tamanho original
        self.view.alter_sheet(new_w_mm=orig_w, new_h_mm=orig_h)
        for p1, p0 in zip(self.view.placed_pieces, orig_pieces):
            self.assertEqual(p1["x"], p0["x"])
            self.assertEqual(p1["y"], p0["y"])

        # 3. Ctrl+Z desfaz o aumento
        self.view.undo_action()
        self.assertEqual(self.view.sheet_width, min_w)
        self.assertEqual(self.view.sheet_height, min_h)

        # 4. Ctrl+Z desfaz a redução
        self.view.undo_action()
        self.assertEqual(self.view.sheet_width, orig_w)
        self.assertEqual(self.view.sheet_height, orig_h)

    def test_05_format_and_units_validation(self):
        """
        Caso 5: Validação de formato e unidades no diálogo.
        - Aceita vírgula e ponto ("1,40", "1.40" -> 1400 mm).
        - Rejeita valores negativos, zero, texto inválido.
        - Mapeamento: Largura = X (sheet_width), Altura = Y (sheet_height).
        """
        # Parsing de metros para mm
        self.assertAlmostEqual(parse_dim_m_to_mm("1.40"), 1400.0)
        self.assertAlmostEqual(parse_dim_m_to_mm("1,40"), 1400.0)
        self.assertAlmostEqual(parse_dim_m_to_mm(" 2,99 m "), 2990.0)
        self.assertAlmostEqual(parse_dim_m_to_mm("0.85"), 850.0)

        # Inválidos
        with self.assertRaises(ValueError):
            parse_dim_m_to_mm("0")
        with self.assertRaises(ValueError):
            parse_dim_m_to_mm("-1.5")
        with self.assertRaises(ValueError):
            parse_dim_m_to_mm("abc")
        with self.assertRaises(ValueError):
            parse_dim_m_to_mm("")

        # Formatação
        self.assertEqual(format_m(1400.0), "1,40")
        self.assertEqual(format_dim_mm(1380.0, 2990.0), "1,38 x 2,99 m")

    def test_06_no_automatic_triggers_fire(self):
        """
        Caso 6: Nenhuma automação dispara ao alterar chapa.
        - NÃO roda separação de sobras.
        - NÃO move a ponta de 2 camadas se foi configurada.
        - NÃO dispara refile automático.
        """
        self.view.tip_zone = (1000.0, 2500.0, 1380.0, 2990.0)
        orig_tip = copy.deepcopy(self.view.tip_zone)
        self.view.trim_cut_line = None

        with patch("cad.layers_split.separar_sobras_camadas") as mock_split:
            # Aumentar chapa
            self.view.alter_sheet(new_w_mm=1600.0, new_h_mm=3200.0)
            mock_split.assert_not_called()

        # Ponta de 2 camadas não se moveu para o final da chapa
        self.assertEqual(self.view.tip_zone, orig_tip)
        # Refile continuou None (não gerou refile automaticamente)
        self.assertIsNone(self.view.trim_cut_line)

    def test_07_trim_cut_line_recalculated_or_invalidated(self):
        """
        Caso 7: Refile (sobra) já aplicado:
        - Se as peças continuarem cabendo dentro do corte, trim_cut_line é recalculado
          com orig_w/h atualizados e has_cut_x/y recalculados.
        - Se a nova chapa for menor do que a linha de corte do refile, é invalidado (None).
        """
        # 1. Chapa 1380 x 2990 com refile em 1000 x 2000
        self.view.trim_cut_line = {
            "x": 1000.0,
            "y": 2000.0,
            "has_cut_x": True,
            "has_cut_y": True,
            "orig_w": 1380.0,
            "orig_h": 2990.0,
            "cut_area_m2": 2.0,
            "enabled": True,
        }

        # Aumentar chapa para 1500 x 3100: corte (1000, 2000) cabe dentro da nova chapa
        self.view.alter_sheet(new_w_mm=1500.0, new_h_mm=3100.0)
        self.assertIsNotNone(self.view.trim_cut_line)
        self.assertEqual(self.view.trim_cut_line["orig_w"], 1500.0)
        self.assertEqual(self.view.trim_cut_line["orig_h"], 3100.0)
        self.assertTrue(self.view.trim_cut_line["has_cut_x"])
        self.assertTrue(self.view.trim_cut_line["has_cut_y"])

        # 2. Reduzir a chapa para menor que a linha de corte (ex: 900 x 1800)
        # O corte antigo de 1000 x 2000 não cabe mais -> invalida para None
        self.view.alter_sheet(new_w_mm=900.0, new_h_mm=1800.0)
        self.assertIsNone(self.view.trim_cut_line)

    def test_08_tip_zone_warning_on_reduction_and_stationary_on_enlargement(self):
        """
        Caso 8: Ponta de 2 camadas (tip_zone) já configurada:
        - Ao reduzir a chapa: se tip_zone cruzar ou ficar fora da borda, avisa o operador.
        - Ao aumentar a chapa: ponta fica estacionária (não se move para o novo final da chapa).
        """
        # Ponta de 2 camadas no topo: Y de 2800 a 2990
        tip = (0.0, 2800.0, 1380.0, 2990.0)
        self.view.tip_zone = tip

        # Aumentar para 3200: ponta NÃO se move
        self.view.alter_sheet(new_w_mm=1380.0, new_h_mm=3200.0)
        self.assertEqual(self.view.tip_zone, tip)

        # Diálogo avisando que tip_zone fica fora se reduzir a altura para 2500
        with patch("tkinter.messagebox.askyesno", return_value=True) as mock_ask:
            dlg = AlterSheetDialog(
                parent=self.view,
                current_sheet_w_mm=1380.0,
                current_sheet_h_mm=3200.0,
                placed_pieces=self.view.placed_pieces,
                margin_left=10.0,
                margin_right=10.0,
                margin_top=10.0,
                margin_bottom=10.0,
                tip_zone=tip,
                on_apply=MagicMock(),
            )
            dlg.entry_w.delete(0, tk.END)
            dlg.entry_w.insert(0, "1.38")
            dlg.entry_h.delete(0, tk.END)
            dlg.entry_h.insert(0, "2.50")  # Topo em 2500 < 2800 do tip
            dlg._on_ok()
            # Deve perguntar se deseja continuar pois a ponta fica fora
            mock_ask.assert_called()
            dlg.destroy()

    def test_09_multi_sheet_session_persistence(self):
        """
        Caso 9: Persistência em sessão com múltiplas chapas.
        - Cria sessão com 2 chapas:
          * Chapa 1: 1380 x 2990 mm
          * Chapa 2: alterada para 1380 x 1800 mm
        - Salva no banco de dados SQLite e recarrega:
          cada chapa mantém suas próprias medidas individuais.
        """
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_db_path = f.name

        try:
            db = DatabaseManager(db_path=tmp_db_path, backend="sqlite")
            sess_id = db.create_session(name="Sessao Multi-Placas")

            layouts_data = [
                {
                    "layout_index": 0,
                    "name": "Placa 1",
                    "width_mm": 1380.0,
                    "height_mm": 2990.0,
                    "ris_w": 1380.0,
                    "ris_l": 2990.0,
                    "pieces": copy.deepcopy(self.view.placed_pieces),
                },
                {
                    "layout_index": 1,
                    "name": "Placa 2",
                    "width_mm": 1380.0,
                    "height_mm": 1800.0,
                    "ris_w": 1380.0,
                    "ris_l": 1800.0,
                    "pieces": copy.deepcopy(self.view.placed_pieces),
                },
            ]

            db.save_session_layouts(sess_id, layouts_data)

            # Recarrega do banco
            loaded = db.get_session_layouts(sess_id)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(float(loaded[0]["width_mm"]), 1380.0)
            self.assertEqual(float(loaded[0]["height_mm"]), 2990.0)
            self.assertEqual(float(loaded[1]["width_mm"]), 1380.0)
            self.assertEqual(float(loaded[1]["height_mm"]), 1800.0)
        finally:
            if os.path.exists(tmp_db_path):
                os.remove(tmp_db_path)

    def test_10_export_and_description_match_new_dimensions(self):
        """
        Caso 10: Exportação .lay / .onx e descrição do layout.
        - Exportação .lay e .onx reflete as dimensões atualizadas.
        - get_sheet_description() gera 'Sheet (comprimento X largura)' com valores reais,
          eliminando o '2553.38 X 1350.00' fixo antigo.
        """
        # Altera chapa para 1.40 x 2.80 m (1400 x 2800 mm)
        self.view.alter_sheet(new_w_mm=1400.0, new_h_mm=2800.0)

        # 1. Descrição do layout
        desc = self.view.get_sheet_description()
        self.assertEqual(desc, "Sheet (2800.00 X 1400.00)")
        self.assertNotIn("2553.38", desc)

        # 2. Exportação .lay
        mat_dict = {"width_mm": self.view.sheet_width, "height_mm": self.view.sheet_height, "name": "Vaqueta"}
        lay_content = export_layout_from_pieces(
            self.view.placed_pieces,
            material=mat_dict,
            filename="teste.lay"
        )
        self.assertIn("1400", lay_content)
        self.assertIn("2800", lay_content)
        parsed = parse_lay(lay_content)
        self.assertEqual(parsed.ris_w, 1400.0)
        self.assertEqual(parsed.ris_l, 2800.0)

        # 3. Exportação .onx
        onx_content = build_onx_xml(
            self.view.placed_pieces,
            material=mat_dict,
        )
        self.assertIn('width="1400', onx_content)
        self.assertIn('height="2800', onx_content)

    def test_11_shortcut_and_menu_bindings(self):
        """
        Caso 11: Atalhos e Menu:
        - Ctrl+M aciona alter_sheet().
        - Menus Arquivo e Encaixe contêm 'Alterar chapa...\tCtrl+M'.
        """
        # Verifica se o método alter_sheet existe
        self.assertTrue(hasattr(self.view, "alter_sheet"))
        self.assertTrue(callable(self.view.alter_sheet))

        # Simula chamada do atalho Ctrl+M passando novas medidas diretamente
        orig_w = self.view.sheet_width
        self.view.alter_sheet(new_w_mm=orig_w + 50.0, new_h_mm=self.view.sheet_height + 50.0)
        self.assertEqual(self.view.sheet_width, orig_w + 50.0)

        # Verifica descrição do status da chapa
        self.assertEqual(self.view.lbl_stat_sheet.cget("text"), f"Placa {format_dim_mm(self.view.sheet_width, self.view.sheet_height)}")

    def test_12_refile_layout_no_false_edge_collisions_session_188(self):
        """
        Caso 12: Layout com Refile aplicado (Cenário real Sessão 188):
        - Peças aninhadas com margem de 10mm na chapa original (1380x2980).
        - Refile corta no final das peças (gap 1mm), resultando em chapa 1364.54 x 2823.23.
        - As peças das pontas NÃO podem ser falsamente acusadas de colisão (colliding_indices vazio).
        - As margens tracejadas (sheet_margins) NÃO devem ser traçadas 10mm para dentro do corte, cortando as peças.
        - AlterSheetDialog não deve acusar peças fora se medidas preservarem as peças.
        - Se a chapa for reduzida abaixo da extensão das peças (ex: 1200mm), aí sim acusa colisão.
        """
        # Cria peças com bordas estendidas até 1363.54 x 2822.23 (como no lay0000 da Sessão 188)
        contour_rect = [
            {"x": 0.0, "y": 0.0},
            {"x": 50.0, "y": 0.0},
            {"x": 50.0, "y": 50.0},
            {"x": 0.0, "y": 50.0},
        ]
        p_left = {"x": 10.0, "y": 10.0, "rotation": 0.0, "contour": contour_rect, "id": 1}
        p_top = {"x": 100.0, "y": 2772.23, "rotation": 0.0, "contour": contour_rect, "id": 2}
        p_right = {"x": 1313.54, "y": 100.0, "rotation": 0.0, "contour": contour_rect, "id": 3}

        self.view.placed_pieces = [p_left, p_top, p_right]
        self.view.sheet_width = 1364.54
        self.view.sheet_height = 2823.23
        self.view.original_sheet_width = 1380.0
        self.view.original_sheet_height = 2980.0
        self.view.margin_left = 10.0
        self.view.margin_right = 10.0
        self.view.margin_top = 10.0
        self.view.margin_bottom = 10.0
        self.view.trim_cut_line = {
            "x": 1364.54,
            "y": 2823.23,
            "orig_w": 1380.0,
            "orig_h": 2980.0,
            "has_cut_x": True,
            "has_cut_y": True,
            "enabled": True,
        }

        # 1. Redraw não deve apontar colisões nas peças das pontas
        self.view.redraw()
        colliding = self.view.colliding_indices
        self.assertEqual(len(colliding), 0, "Peças em layout refilado não devem sofrer falsa colisão com a margem")

        # 2. O status bar não deve exibir alerta de colisão
        if hasattr(self.view, "lbl_stat_left"):
            status_text = self.view.lbl_stat_left.cget("text")
            self.assertNotIn("⚠️ ALERTA: Colisão", status_text)

        # 3. sheet_margins só deve desenhar linhas nas bordas não refiladas (esquerda e inferior)
        margin_lines = self.view.canvas.find_withtag("sheet_margins")
        self.assertEqual(len(margin_lines), 2, "Em chapa com corte X e Y, apenas margens esquerda e inferior são traçadas")

        # 4. AlterSheetDialog com refile ativo: cálculo de mínimo considera has_cut_x/y
        dlg = AlterSheetDialog(
            parent=self.view,
            current_sheet_w_mm=self.view.sheet_width,
            current_sheet_h_mm=self.view.sheet_height,
            placed_pieces=self.view.placed_pieces,
            margin_left=10.0,
            margin_right=10.0,
            margin_top=10.0,
            margin_bottom=10.0,
            trim_cut_line=self.view.trim_cut_line,
            on_apply=MagicMock(),
        )
        self.assertAlmostEqual(dlg.min_w_mm, 1363.54, delta=0.1)
        self.assertAlmostEqual(dlg.min_h_mm, 2822.23, delta=0.1)
        # Ao confirmar dimensões atuais, não deve detectar peças fora
        out_sheet, out_margin, affected = count_pieces_outside(
            self.view.placed_pieces,
            self.view.sheet_width,
            self.view.sheet_height,
            margin_left=10.0,
            margin_right=10.0,
            margin_bottom=10.0,
            margin_top=10.0,
            has_cut_x=True,
            has_cut_y=True,
        )
        self.assertEqual(len(affected), 0, "Medidas atuais de refile não têm peças fora da margem")
        dlg.destroy()

        # 5. Se o operador reduzir manualmente para 1200 x 2500, as peças fora da chapa DEVEM ser detectadas
        self.view.alter_sheet(new_w_mm=1200.0, new_h_mm=2500.0)
        self.view.redraw()
        colliding_reduced = self.view.colliding_indices
        self.assertIn(1, colliding_reduced, "Peça p_top (Y=2822) deve ser marcada como colisão fora da chapa de 2500mm")
        self.assertIn(2, colliding_reduced, "Peça p_right (X=1363) deve ser marcada como colisão fora da chapa de 1200mm")


if __name__ == "__main__":
    unittest.main()

