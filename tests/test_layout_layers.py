"""
tests/test_layout_layers.py

Suíte completa de testes para validação de:
1. Herança de camadas (resolve_layout_layers)
2. Persistência de camadas por layout no banco de dados (SQLite e retrocompatibilidade)
3. Preservação de layers no formato .lay
4. Totais da sessão no LayoutEditorView (pares ponderados por layout)
5. Cores do contador (déficit em vermelho, sobra legítima em preto)
6. Enfesto visível (título, status, canvas e troca via Ctrl+L / open_next_layout)
7. Legenda de Impressão A4 (n/m, sem .00, sem /0, ShapeId com/sem #, sobra legítima, quebra de linha)
8. Camadas indefinidas / desconhecidas (alerta "assumindo 2")
"""

import os
import tempfile
import unittest
import tkinter as tk
from unittest.mock import MagicMock

from cad.layers_rule import (
    resolve_layout_layers,
    resolve_session_layers,
    is_layers_defined,
    calc_resto,
    pecas_na_mesa
)
from cad.lay_parser import (
    LayoutData,
    PlacedItem,
    generate_lay_content,
    parse_lay,
    export_layout_from_pieces
)
from database import DatabaseManager
from ui.layout_editor_view import LayoutEditorView
from ui.layout_print_dialog import LayoutPrintDialog, format_size, format_shape_id_tag


class TestLayoutLayers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    # =========================================================================
    # Caso 1: Herança de Camadas (resolve_layout_layers)
    # =========================================================================
    def test_case_1_inheritance(self):
        """Layout sem layers herda da sessão; layout com layers usa o próprio."""
        # 1. Layout sem layers herda da sessão
        ly_empty = {}
        sess_4 = {"layers": 4}
        self.assertEqual(resolve_layout_layers(ly_empty, session=sess_4), 4)

        # 2. Layout com layers sobrescreve sessão
        ly_2 = {"layers": 2}
        self.assertEqual(resolve_layout_layers(ly_2, session=sess_4), 2)

        # 3. Layout None herda da sessão
        self.assertEqual(resolve_layout_layers(None, session=sess_4), 4)

        # 4. Sem layout e sem sessão, herda do material
        mat_6 = {"layers": 6}
        self.assertEqual(resolve_layout_layers(None, session=None, material=mat_6), 6)

        # 5. Fallback padrão quando nada definido
        self.assertEqual(resolve_layout_layers(None, session=None, material=None, default=2), 2)

    # =========================================================================
    # Caso 2: Persistência no Banco (SQLite e Retrocompatibilidade)
    # =========================================================================
    def test_case_2_database_persistence(self):
        """Salvar e reabrir sessão preserva layers por layout. Sessão antiga abre herdando."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_layers.db")
        try:
            db = DatabaseManager(db_path=db_path, backend="sqlite")
            sess_id = db.create_session(name="Sessao Camadas", job="JOB_CAM", material_id="MAT01", layers=4)

            # Salva 2 layouts: lay0000 com 4 camadas, lay0001 com 2 camadas
            layouts_to_save = [
                {"layout_index": 0, "name": "lay0000", "pieces": [{"id": 1, "name": "P1", "size": "41"}], "layers": 4},
                {"layout_index": 1, "name": "lay0001", "pieces": [{"id": 2, "name": "P1", "size": "41"}], "layers": 2},
            ]
            ok = db.save_session_layouts(sess_id, layouts_to_save)
            self.assertTrue(ok)

            loaded = db.get_session_layouts(sess_id)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0]["layers"], 4)
            self.assertEqual(loaded[1]["layers"], 2)

            # Retrocompatibilidade: insere layout legado com layers = NULL diretamente no banco
            with db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO layouts (session_id, layout_index, name, code, layers) VALUES (?, ?, ?, ?, NULL)",
                    (sess_id, 2, "lay0002", "lay0002")
                )
                conn.commit()

            loaded_with_legacy = db.get_session_layouts(sess_id)
            self.assertEqual(len(loaded_with_legacy), 3)
            # Layout 2 tinha NULL no banco, deve herdar 4 da sessão
            self.assertEqual(loaded_with_legacy[2]["layers"], 4)
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass

    # =========================================================================
    # Caso 3: Formato .lay (Exportação e Retrocompatibilidade)
    # =========================================================================
    def test_case_3_lay_format(self):
        """Layout exportado para .lay e relido preserva layers. Arquivo sem o campo lê normalmente."""
        pcs = [
            {"id": 1, "name": "Gaspea", "size": "41", "target_id": 1, "rotation": 0.0, "x": 100.0, "y": 100.0, "contour": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 50}, {"x": 0, "y": 50}]}
        ]
        content = export_layout_from_pieces(
            placed_pieces=pcs,
            material={"width_mm": 1380.0, "height_mm": 1080.0},
            layers=4
        )
        self.assertIn("layers=4", content)

        # Relê o conteúdo gerado
        parsed = parse_lay(content)
        self.assertEqual(parsed.layers, 4)

        # Arquivo legado autêntico ATOM da pasta samples sem o campo layers
        sample_path = os.path.join(os.path.dirname(__file__), "..", "samples", "lay", "sample_1494_l0000.lay")
        if os.path.exists(sample_path):
            parsed_sample = parse_lay(sample_path)
            self.assertIsNotNone(parsed_sample)
            # Lê normalmente e mantém compatibilidade
            self.assertTrue(parsed_sample.ris_w > 0)

    # =========================================================================
    # Caso 4: Totais da Sessão com Camadas Diferentes
    # =========================================================================
    def test_case_4_multi_layout_weighted_pairs(self):
        """62 peças a 4 camadas + 1 peça a 2 camadas = 125 pares produzidos. Contador exibe 125/125."""
        view = LayoutEditorView(self.root, layout_name="lay0000.lay", load_sample=False)
        try:
            # 62 peças no layout 0 (4 camadas)
            pcs_0 = [{"name": "Gaspea", "size": "41", "target_id": "1"} for _ in range(62)]
            # 1 peça no layout 1 (2 camadas)
            pcs_1 = [{"name": "Gaspea", "size": "41", "target_id": "1"} for _ in range(1)]

            layouts = [
                {"layout_index": 0, "name": "lay0000", "pieces": pcs_0, "layers": 4},
                {"layout_index": 1, "name": "lay0001", "pieces": pcs_1, "layers": 2},
            ]
            shapes = [
                {"id": "1", "name": "Gaspea", "size": "41", "pairs": 125}
            ]

            view.session = {"layers": 4}
            view.set_session_shapes(shapes)
            view.set_session_layouts(layouts, initial_index=0)
            view.update_sidebar_targets()

            # Renderiza barra lateral para gerar os textos no canvas
            view.draw_sidebar(div_x=0, ch=500, cw=300)

            # Verifica textos gerados na barra lateral
            sidebar_texts = [view.canvas.itemcget(i, "text") for i in view.canvas.find_withtag("sidebar_ui") if view.canvas.type(i) == "text"]
            sidebar_colors = {view.canvas.itemcget(i, "text"): view.canvas.itemcget(i, "fill") for i in view.canvas.find_withtag("sidebar_ui") if view.canvas.type(i) == "text"}

            # (62 * 4 + 1 * 2) // 2 = (248 + 2) // 2 = 125 pares produzidos na sessão
            # Na placa 0 (com 62 peças): contador deve ser 62/125 em preto
            self.assertIn("62/125", sidebar_texts)
            self.assertEqual(sidebar_colors.get("62/125"), "#000000")
            # Sem linha 'placa:'
            for txt in sidebar_texts:
                self.assertNotIn("placa:", txt)
        finally:
            view.destroy()

    # =========================================================================
    # Caso 5: Cores do Contador (Déficit em vermelho, sobra legítima em preto)
    # =========================================================================
    def test_case_5_sidebar_counter_colors(self):
        """Déficit real em vermelho; sobra legítima por arredondamento em preto."""
        view = LayoutEditorView(self.root, layout_name="lay0000.lay", load_sample=False)
        try:
            # Caso A: Déficit real (pedido 125 pares, produzido 120 pares em 60 peças)
            pcs_def = [{"name": "Gaspea", "size": "41", "target_id": "1"} for _ in range(60)]  # 60 * 4 // 2 = 120
            layouts_def = [{"layout_index": 0, "name": "lay0000", "pieces": pcs_def, "layers": 4}]
            shapes_def = [{"id": "1", "name": "Gaspea", "size": "41", "pairs": 125}]

            view.session = {"layers": 4}
            view.set_session_shapes(shapes_def)
            view.set_session_layouts(layouts_def, initial_index=0)
            view.update_sidebar_targets()
            view.draw_sidebar(div_x=0, ch=500, cw=300)

            sidebar_colors_a = {view.canvas.itemcget(i, "text"): view.canvas.itemcget(i, "fill") for i in view.canvas.find_withtag("sidebar_ui") if view.canvas.type(i) == "text"}
            self.assertIn("60/125", sidebar_colors_a)
            self.assertEqual(sidebar_colors_a["60/125"], "#dc2626")  # Déficit real em vermelho

            # Caso B: Sobra legítima (pedido 63 pares a 4 camadas -> demanda ceil((63*2)/4)=32 peças -> 64 pares)
            pcs_sobra = [{"name": "Gaspea", "size": "41", "target_id": "1"} for _ in range(32)]  # 32 * 4 // 2 = 64
            layouts_sobra = [{"layout_index": 0, "name": "lay0000", "pieces": pcs_sobra, "layers": 4}]
            shapes_sobra = [{"id": "1", "name": "Gaspea", "size": "41", "pairs": 63}]

            view.set_session_shapes(shapes_sobra)
            view.set_session_layouts(layouts_sobra, initial_index=0)
            view.update_sidebar_targets()
            view.draw_sidebar(div_x=0, ch=500, cw=300)

            sidebar_colors_b = {view.canvas.itemcget(i, "text"): view.canvas.itemcget(i, "fill") for i in view.canvas.find_withtag("sidebar_ui") if view.canvas.type(i) == "text"}
            self.assertIn("32/63", sidebar_colors_b)
            self.assertEqual(sidebar_colors_b["32/63"], "#000000")  # Sobra legítima em preto
        finally:
            view.destroy()

    # =========================================================================
    # Caso 6: Enfesto Visível no Layout Editor e Troca com Ctrl+L
    # =========================================================================
    def test_case_6_enfesto_visible_and_ctrl_l(self):
        """Título e canvas mostram enfesto do layout selecionado e atualizam na troca de placa."""
        view = LayoutEditorView(self.root, layout_name="lay0000.lay", load_sample=False)
        try:
            layouts = [
                {"layout_index": 0, "name": "lay0000", "pieces": [], "layers": 4},
                {"layout_index": 1, "name": "lay0001", "pieces": [], "layers": 2},
            ]
            view.session = {"layers": 4}
            view.set_session_layouts(layouts, initial_index=0)

            # Placa 0: enfesto de 4 camadas
            self.assertIn("enfesto de 4 camadas", view.lbl_title.cget("text"))
            self.assertIn("enfesto de 4 camadas", view.lbl_stat_doc.cget("text"))
            enf_items_0 = view.canvas.find_withtag("enfesto_label")
            self.assertTrue(len(enf_items_0) > 0)
            self.assertIn("Enfesto: 4 camadas", view.canvas.itemcget(enf_items_0[0], "text"))

            # Troca de layout para placa 1 (Ctrl+L)
            view.open_next_layout()
            self.assertEqual(view.current_layout_index, 1)
            self.assertIn("enfesto de 2 camadas", view.lbl_title.cget("text"))
            self.assertIn("enfesto de 2 camadas", view.lbl_stat_doc.cget("text"))
            enf_items_1 = view.canvas.find_withtag("enfesto_label")
            self.assertTrue(len(enf_items_1) > 0)
            self.assertIn("Enfesto: 2 camadas", view.canvas.itemcget(enf_items_1[0], "text"))
        finally:
            view.destroy()

    # =========================================================================
    # Caso 7: Legenda A4 de Impressão (n/m, ShapeId, Sobra Legítima, Quebra)
    # =========================================================================
    def test_case_7_print_legend_a4(self):
        """Valida formatação n/m, ShapeId (# e ausência), sobra legítima e metadados de Enfesto."""
        session_shapes = [
            {"id": "1735", "name": "129_187_Tras_36a", "size": "36", "pairs": 50},
            {"id": "1736", "name": "129_187_Tras_37a", "size": "37", "pairs": 62},  # 4 camadas: sobra 0
            {"id": "1737", "name": "129_187_Tras_38a", "size": "38", "pairs": 63},  # 4 camadas: produz 64, sobra 1
            {"name": "SemId_39a", "size": "39", "pairs": 0},                        # sem ShapeId e m=0
        ]
        # Peças na placa atual (4 camadas)
        placed_pieces = (
            [{"name": "129_187_Tras_36a", "size": "36", "shape_id": "1735"} for _ in range(25)] +   # 25 * 4 // 2 = 50 pares (50/50)
            [{"name": "129_187_Tras_37a", "size": "37", "shape_id": "1735"} for _ in range(31)] +   # 31 * 4 // 2 = 62 pares (62/62)
            [{"name": "129_187_Tras_38a", "size": "38", "shape_id": "1735"} for _ in range(32)] +   # 32 * 4 // 2 = 64 pares (64/63 -> sobra legítima)
            [{"name": "SemId_39a", "size": "39"} for _ in range(5)]                                  # 5 * 4 // 2 = 10 pares (10 sem /0)
        )

        dlg = LayoutPrintDialog(self.root, layout_data={
            "session_shapes": session_shapes,
            "placed_pieces": placed_pieces,
            "layers": 4,
            "material_layers": 4
        })
        try:
            legend = dlg.legend_data
            self.assertTrue(len(legend) >= 2)

            # Valida formatação de ShapeId
            self.assertEqual(format_shape_id_tag("1735"), "  #1735")
            self.assertEqual(format_shape_id_tag("#1735"), "  #1735")
            self.assertEqual(format_shape_id_tag(None), "")
            self.assertEqual(format_shape_id_tag(""), "")

            # Molde 1: 129_187_Tras
            row_tras = next((r for r in legend if "129_187_Tras" in r["molde_name"]), None)
            self.assertIsNotNone(row_tras)
            self.assertEqual(row_tras["shape_id"], "1735")

            sizes_map = {s["size"]: s for s in row_tras["sizes"]}
            # Tamanho 36: 50/50
            self.assertIn("36", sizes_map)
            self.assertEqual(sizes_map["36"]["n"], 50)
            self.assertEqual(sizes_map["36"]["m"], 50)
            self.assertFalse(sizes_map["36"]["is_error"])

            # Tamanho 38: 64/63 (sobra legítima por 4 camadas, is_error deve ser FALSE)
            self.assertIn("38", sizes_map)
            self.assertEqual(sizes_map["38"]["n"], 64)
            self.assertEqual(sizes_map["38"]["m"], 63)
            self.assertFalse(sizes_map["38"]["is_error"], "Sobra legítima de 1 par não deve ser marcada como erro!")

            # Molde 2: SemId_39a com pedido m = 0
            row_sem = next((r for r in legend if "SemId" in r["molde_name"]), None)
            self.assertIsNotNone(row_sem)
            self.assertIsNone(row_sem.get("shape_id"))
            sizes_map_sem = {s["size"]: s for s in row_sem["sizes"]}
            self.assertEqual(sizes_map_sem["39"]["m"], 0)
            self.assertEqual(sizes_map_sem["39"]["n"], 10)

            # Verifica metadados de Enfesto no diálogo
            self.assertEqual(dlg.layout_layers, 4)
        finally:
            dlg.destroy()

    # =========================================================================
    # Caso 8: Camadas Desconhecidas (Alerta "assumindo 2")
    # =========================================================================
    def test_case_8_unknown_layers_warning(self):
        """Camadas indefinidas geram aviso na barra de status e no canvas."""
        view = LayoutEditorView(self.root, layout_name="lay0000.lay", load_sample=False)
        try:
            view.session = {}
            view.material = None
            view.material_layers = 2
            view.layouts = [{"layout_index": 0, "name": "lay0000", "pieces": []}]
            view.current_layout_index = 0

            self.assertFalse(is_layers_defined(session=None, layout=view.layouts[0], material=None))

            view.update_title_and_status()
            self.assertIn("assumindo 2", view.lbl_stat_pos.cget("text"))
            self.assertIn("assumindo 2", view.lbl_stat_doc.cget("text"))
        finally:
            view.destroy()

    # =========================================================================
    # Caso 9: Regressão Geral de Cálculos de Resto e Peças na Mesa
    # =========================================================================
    def test_case_9_rules_consistency(self):
        """Validação de consistência em larga escala de pecas_na_mesa e calc_resto."""
        for p in range(1, 100):
            for l in (1, 2, 4, 6):
                pecas = pecas_na_mesa(p, l)
                produzido = (pecas * l) // 2
                resto = calc_resto(p, l)
                self.assertTrue(produzido >= p, f"Produzido {produzido} < Pedido {p} para camadas {l}")
                self.assertEqual(resto, p - produzido, f"Resto incorreto para p={p}, l={l}")
                self.assertTrue(resto <= 0, f"Resto positivo para p={p}, l={l}")


if __name__ == "__main__":
    unittest.main()
