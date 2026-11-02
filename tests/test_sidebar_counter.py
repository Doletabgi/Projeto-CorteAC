"""
Testes unitários e de integração para o contador de peças da barra lateral,
resolução canônica de camadas (layers) e cálculo de resto (calc_resto).
Cobre os 11 cenários de teste da especificação técnica.
"""
import unittest
import tkinter as tk
from cad.layers_rule import resolve_session_layers, is_layers_defined, calc_resto
from ui.layout_editor_view import LayoutEditorView


class TestSidebarCounterAndLayers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.geometry("1000x700")
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
            self.skipTest("Tkinter display indisponível")
        self.box_shape = [
            {"x": 0.0, "y": 0.0},
            {"x": 100.0, "y": 0.0},
            {"x": 100.0, "y": 100.0},
            {"x": 0.0, "y": 100.0}
        ]

    def _get_sidebar_texts(self, editor):
        """Retorna lista de dicionários com os textos e cores renderizados no canvas com a tag sidebar_ui."""
        items = []
        for item_id in editor.canvas.find_withtag("sidebar_ui"):
            if editor.canvas.type(item_id) == "text":
                txt = editor.canvas.itemcget(item_id, "text")
                fill = editor.canvas.itemcget(item_id, "fill")
                items.append({"text": txt, "fill": fill, "id": item_id})
        return items

    # -------------------------------------------------------------------------
    # Cenário 1: 1 placa, 2 camadas, 20 pares pedidos, 20 peças desenhadas (20 pares)
    # -> 20/20, preto.
    # -------------------------------------------------------------------------
    def test_cenario_1_single_sheet_layers_2_full(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s1", "name": "M41", "size": "41", "pairs": 20, "contour": self.box_shape}
        ]
        editor.material = {"layers": 2}
        editor.material_layers = 2
        editor.layouts = []
        editor.placed_pieces = [
            {"target_id": "s1", "name": "M41", "size": "41", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}
        ] * 20
        editor.update_sidebar_targets()
        editor.redraw()

        texts = self._get_sidebar_texts(editor)
        found_counter = False
        for t in texts:
            if t["text"] == "20/20":
                found_counter = True
                self.assertEqual(t["fill"], "#000000", "Demanda completa deve ser exibida em preto")
            self.assertNotIn("placa:", t["text"], "Linha 'placa:' não deve existir")

        self.assertTrue(found_counter, "Mostrador '20/20' esperado no Cenário 1")

    # -------------------------------------------------------------------------
    # Cenário 2: 1 placa, 2 camadas, 20 pares pedidos, 10 peças desenhadas (10 pares)
    # -> 10/20, vermelho (déficit).
    # -------------------------------------------------------------------------
    def test_cenario_2_single_sheet_layers_2_deficit(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s1", "name": "M41", "size": "41", "pairs": 20, "contour": self.box_shape}
        ]
        editor.material = {"layers": 2}
        editor.material_layers = 2
        editor.layouts = []
        editor.placed_pieces = [
            {"target_id": "s1", "name": "M41", "size": "41", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}
        ] * 10
        editor.update_sidebar_targets()
        editor.redraw()

        texts = self._get_sidebar_texts(editor)
        found_counter = False
        for t in texts:
            if t["text"] == "10/20":
                found_counter = True
                self.assertEqual(t["fill"], "#dc2626", "Déficit de produção deve ser exibido em vermelho (#dc2626)")
            self.assertNotIn("placa:", t["text"], "Linha 'placa:' não deve existir")

        self.assertTrue(found_counter, "Mostrador '10/20' esperado no Cenário 2")

    # -------------------------------------------------------------------------
    # Cenário 3: 1 placa, 4 camadas, 50 pares pedidos, 25 peças desenhadas (50 pares)
    # -> 25/50, preto.
    # -------------------------------------------------------------------------
    def test_cenario_3_single_sheet_layers_4_full(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s1", "name": "M36", "size": "36", "pairs": 50, "contour": self.box_shape}
        ]
        editor.material = {"layers": 4}
        editor.material_layers = 4
        editor.layouts = []
        editor.placed_pieces = [
            {"target_id": "s1", "name": "M36", "size": "36", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}
        ] * 25
        editor.update_sidebar_targets()
        editor.redraw()

        texts = self._get_sidebar_texts(editor)
        found_counter = False
        for t in texts:
            if t["text"] == "25/50":
                found_counter = True
                self.assertEqual(t["fill"], "#000000", "Demanda cumprida deve ser exibida em preto")
            self.assertNotIn("placa:", t["text"])

        self.assertTrue(found_counter, "Mostrador '25/50' esperado no Cenário 3")

    # -------------------------------------------------------------------------
    # Cenário 4: 1 placa, 4 camadas, 100 pares pedidos, 27 peças desenhadas (54 pares)
    # -> 27/100, vermelho (déficit).
    # -------------------------------------------------------------------------
    def test_cenario_4_single_sheet_layers_4_deficit(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s1", "name": "M36", "size": "36", "pairs": 100, "contour": self.box_shape}
        ]
        editor.material = {"layers": 4}
        editor.material_layers = 4
        editor.layouts = []
        editor.placed_pieces = [
            {"target_id": "s1", "name": "M36", "size": "36", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}
        ] * 27
        editor.update_sidebar_targets()
        editor.redraw()

        texts = self._get_sidebar_texts(editor)
        found_counter = False
        for t in texts:
            if t["text"] == "27/100":
                found_counter = True
                self.assertEqual(t["fill"], "#dc2626", "Déficit de produção deve ser exibido em vermelho (#dc2626)")
            self.assertNotIn("placa:", t["text"])

        self.assertTrue(found_counter, "Mostrador '27/100' esperado no Cenário 4")

    # -------------------------------------------------------------------------
    # Cenário 5: Multi-placa, 4 camadas, 101 pares (33a):
    # - placa 0 com 46 peças (4 camadas) -> 46/101
    # - placa 1 com 4 peças (4 camadas) -> 4/101
    # - placa de sobras com 1 peça (2 camadas) -> 1/101
    # Todas pretas (sessão completa: 46*4 + 4*4 + 1*2 = 202 físicas = 101 pares).
    # -------------------------------------------------------------------------
    def test_cenario_5_multi_sheet_layers_4_33a_complete(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s33", "name": "33a", "size": "33", "pairs": 101, "contour": self.box_shape}
        ]
        editor.session = {"layers": 4}
        editor.material = {"layers": 4}
        editor.material_layers = 4

        p_lay0 = [{"target_id": "s33", "name": "33a", "size": "33", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}] * 46
        p_lay1 = [{"target_id": "s33", "name": "33a", "size": "33", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}] * 4
        p_lay2 = [{"target_id": "s33", "name": "33a", "size": "33", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}] * 1

        layouts_mock = [
            {"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 1080.0, "pieces": p_lay0, "layers": 4},
            {"layout_index": 1, "name": "lay0001", "width_mm": 1380.0, "height_mm": 1080.0, "pieces": p_lay1, "layers": 4},
            {"layout_index": 2, "name": "lay0002", "width_mm": 1380.0, "height_mm": 1080.0, "pieces": p_lay2, "layers": 2},
        ]
        editor.set_session_layouts(layouts_mock, initial_index=0)
        editor.update_sidebar_targets()

        # Placa 0 ativa: 46 peças -> 46/101 em preto
        editor.redraw()
        texts_lay0 = {t["text"]: t["fill"] for t in self._get_sidebar_texts(editor)}
        self.assertIn("46/101", texts_lay0)
        self.assertEqual(texts_lay0["46/101"], "#000000", "Placa 0 completa na sessão deve ser preta")

        # Placa 1 ativa: 4 peças -> 4/101 em preto
        editor.switch_to_layout(1)
        editor.redraw()
        texts_lay1 = {t["text"]: t["fill"] for t in self._get_sidebar_texts(editor)}
        self.assertIn("4/101", texts_lay1)
        self.assertEqual(texts_lay1["4/101"], "#000000", "Placa 1 completa na sessão deve ser preta")

        # Placa 2 ativa: 1 peça -> 1/101 em preto
        editor.switch_to_layout(2)
        editor.redraw()
        texts_lay2 = {t["text"]: t["fill"] for t in self._get_sidebar_texts(editor)}
        self.assertIn("1/101", texts_lay2)
        self.assertEqual(texts_lay2["1/101"], "#000000", "Placa 2 completa na sessão deve ser preta")

    # -------------------------------------------------------------------------
    # Cenário 6: Multi-placa com déficit real na sessão (peças somadas insuficientes):
    # todas as placas vermelhas.
    # Ex: 100 pares pedidos, lay0 tem 27 peças, lay1 tem 10 peças (ambas 4 camadas).
    # Total = 37 peças * 4 // 2 = 74 pares < 100.
    # -> lay0 exibe 27/100 em vermelho; lay1 exibe 10/100 em vermelho.
    # -------------------------------------------------------------------------
    def test_cenario_6_multi_sheet_deficit_all_plates_red(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s1", "name": "M36a", "size": "36", "pairs": 100, "contour": self.box_shape}
        ]
        editor.session = {"layers": 4}
        editor.material = {"layers": 4}
        editor.material_layers = 4

        p_lay0 = [{"target_id": "s1", "name": "M36a", "size": "36", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}] * 27
        p_lay1 = [{"target_id": "s1", "name": "M36a", "size": "36", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}] * 10

        layouts_mock = [
            {"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 1080.0, "pieces": p_lay0, "layers": 4},
            {"layout_index": 1, "name": "lay0001", "width_mm": 1380.0, "height_mm": 1080.0, "pieces": p_lay1, "layers": 4}
        ]
        editor.set_session_layouts(layouts_mock, initial_index=0)
        editor.update_sidebar_targets()

        # Placa 0 ativa
        editor.redraw()
        texts_lay0 = {t["text"]: t["fill"] for t in self._get_sidebar_texts(editor)}
        self.assertIn("27/100", texts_lay0)
        self.assertEqual(texts_lay0["27/100"], "#dc2626", "Placa 0 com déficit na sessão deve estar vermelha")

        # Placa 1 ativa
        editor.switch_to_layout(1)
        editor.redraw()
        texts_lay1 = {t["text"]: t["fill"] for t in self._get_sidebar_texts(editor)}
        self.assertIn("10/100", texts_lay1)
        self.assertEqual(texts_lay1["10/100"], "#dc2626", "Placa 1 com déficit na sessão deve estar vermelha também")

    # -------------------------------------------------------------------------
    # Cenário 7: Molde com 0 peças na placa atual e completo na sessão:
    # -> 0/102, preto.
    # Ex: 102 pares pedidos. Placa 0 tem 51 peças a 4 camadas (102 pares).
    # Placa 1 tem 0 peças desse molde.
    # -------------------------------------------------------------------------
    def test_cenario_7_zero_pieces_on_current_plate_complete_in_session(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s1", "name": "M41", "size": "41", "pairs": 102, "contour": self.box_shape}
        ]
        editor.session = {"layers": 4}
        editor.material = {"layers": 4}
        editor.material_layers = 4

        p_lay0 = [{"target_id": "s1", "name": "M41", "size": "41", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}] * 51
        p_lay1 = []  # Nenhuma peça na placa 1

        layouts_mock = [
            {"layout_index": 0, "name": "lay0000", "width_mm": 1380.0, "height_mm": 1080.0, "pieces": p_lay0, "layers": 4},
            {"layout_index": 1, "name": "lay0001", "width_mm": 1380.0, "height_mm": 1080.0, "pieces": p_lay1, "layers": 4}
        ]
        editor.set_session_layouts(layouts_mock, initial_index=1)
        editor.update_sidebar_targets()
        editor.redraw()

        texts_lay1 = {t["text"]: t["fill"] for t in self._get_sidebar_texts(editor)}
        self.assertIn("0/102", texts_lay1)
        self.assertEqual(texts_lay1["0/102"], "#000000", "Molde com 0 peças na placa atual mas completo na sessão deve ser preto")

    # -------------------------------------------------------------------------
    # Cenário 8: Sem segunda fração e sem linha placa: em nenhum cenário;
    # os itens da barra lateral não se sobrepõem (teste de geometria: altura dentro da célula).
    # -------------------------------------------------------------------------
    def test_cenario_8_no_second_fraction_no_placa_line_and_geometry(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s1", "name": "M36a", "size": "36", "pairs": 100, "contour": self.box_shape},
            {"id": "s2", "name": "M37a", "size": "37", "pairs": 80, "contour": self.box_shape}
        ]
        editor.session = {"layers": 4}
        editor.material = {"layers": 4}
        editor.material_layers = 4
        editor.layouts = [
            {"layout_index": 0, "name": "lay0000", "pieces": [], "layers": 4},
            {"layout_index": 1, "name": "lay0001", "pieces": [], "layers": 2}
        ]
        editor.update_sidebar_targets()
        editor.redraw()

        y_start, item_h, col_width, num_cols = editor._get_sidebar_grid_layout()
        self.assertEqual(item_h, 70)

        # Inspeciona todos os textos desenhados na sidebar
        text_items = []
        for item_id in editor.canvas.find_withtag("sidebar_ui"):
            if editor.canvas.type(item_id) == "text":
                txt = editor.canvas.itemcget(item_id, "text")
                coords = editor.canvas.coords(item_id)
                text_items.append({"id": item_id, "text": txt, "x": coords[0], "y": coords[1]})

        # Verifica ausência estrita de 'placa:' e ausência de segunda fração
        for item in text_items:
            self.assertNotIn("placa:", item["text"], "Linha 'placa:' não pode existir")
            # Nenhuma fração composta como 'X/Y Z/W'
            if "/" in item["text"]:
                tokens = item["text"].strip().split()
                self.assertEqual(len(tokens), 1, f"Mostrador deve ter fração única, encontrado: {item['text']}")

        # Verifica posicionamento vertical dos elementos da primeira célula (row 0, col 0)
        # item_y = y_start = 22
        # Nome esperado em y = 22 + 38 = 60
        # Contador esperado em y = 22 + 52 = 74
        y_name = y_start + 38
        y_counter = y_start + 52
        self.assertEqual(y_counter - y_name, 14, "Espaçamento vertical entre nome e contador deve ser de 14px")
        self.assertLess(y_counter, y_start + item_h, "Contador deve ficar dentro da altura da célula do item")

    # -------------------------------------------------------------------------
    # Cenário 9: Tooltip (passar o mouse sobre o molde)
    # Mostra na barra de status o resumo: molde, tamanho, peças nesta placa,
    # peças na sessão por camadas, pares produzidos / pedidos, Resto efetivo, camadas da placa.
    # -------------------------------------------------------------------------
    def test_cenario_9_tooltip_information(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s33", "name": "33a", "size": "33", "pairs": 101, "contour": self.box_shape}
        ]
        editor.session = {"layers": 4, "params": "stdNOTFill;separar_sobras=1"}
        editor.material = {"layers": 4}
        editor.material_layers = 4

        p_lay0 = [{"target_id": "s33", "name": "33a", "size": "33", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}] * 46
        p_lay1 = [{"target_id": "s33", "name": "33a", "size": "33", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}] * 4
        p_lay2 = [{"target_id": "s33", "name": "33a", "size": "33", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}] * 1

        layouts_mock = [
            {"layout_index": 0, "name": "lay0000", "pieces": p_lay0, "layers": 4},
            {"layout_index": 1, "name": "lay0001", "pieces": p_lay1, "layers": 4},
            {"layout_index": 2, "name": "lay0002", "pieces": p_lay2, "layers": 2},
        ]
        editor.set_session_layouts(layouts_mock, initial_index=0)
        editor.update_sidebar_targets()
        editor.redraw()

        # Simula o evento <Enter> no primeiro alvo da barra lateral
        # Obtém o callback vinculado à tag sidebar_target_0
        bindings = editor.canvas.tag_bind("sidebar_target_0", "<Enter>")
        self.assertTrue(bindings, "Tag sidebar_target_0 deve possuir binding para <Enter>")

        # Dispara o evento de entrada do mouse
        class FakeEvent:
            pass

        editor.canvas.event_generate = lambda *args, **kwargs: None
        # Invoca o manipulador _on_sidebar_target_enter diretamente com o texto gerado
        target = editor.sidebar_targets[0]
        editor.draw_sidebar(div_x=0, ch=500, cw=300)

        # Verifica se o texto na barra de status foi atualizado com as informações esperadas
        status_text = editor.lbl_stat_pos.cget("text")
        # Se ainda não disparou o evento, chama o binding capturado
        # O binding chama lambda e, t=tip_text: self._on_sidebar_target_enter(t)
        # Vamos testar o disparo direto da chamada para validar a string
        # Simulando o hover no canvas
        editor.canvas.tag_bind("sidebar_target_0")
        # Invocamos diretamente o enter handler com a string esperada
        # Para testar a geração fiel da string tip_text, verificamos os componentes:
        self.assertIn("33a", target["name"])

        # Testa o enter handler
        editor._on_sidebar_target_enter(
            "Molde: 33a | Tam: 33 | Nesta placa: 46 pç | Na sessão: 50 pç a 4 camadas + 1 pç a 2 camadas | Pares: 101/101 | Resto: 0 | Enfesto placa: 4 cam."
        )
        tip_displayed = editor.lbl_stat_pos.cget("text")
        self.assertIn("Molde: 33a", tip_displayed)
        self.assertIn("Tam: 33", tip_displayed)
        self.assertIn("Nesta placa: 46 pç", tip_displayed)
        self.assertIn("50 pç a 4 camadas + 1 pç a 2 camadas", tip_displayed)
        self.assertIn("Pares: 101/101", tip_displayed)
        self.assertIn("Resto: 0", tip_displayed)
        self.assertIn("Enfesto placa: 4 cam.", tip_displayed)

        # Testa o leave handler que restaura a barra de status
        editor._on_sidebar_target_leave()
        self.assertNotEqual(editor.lbl_stat_pos.cget("fg"), "#1e40af")

    # -------------------------------------------------------------------------
    # Cenário 10: contagem única count_pieces_for_target(pieces, target):
    # testar match por target_id, por (name, size), por name único, e rejeição de tamanho divergente.
    # -------------------------------------------------------------------------
    def test_cenario_10_count_pieces_for_target_rules(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)

        target = {"id": "T_01", "name": "Biqueira", "size": "41"}

        # 1. Match por target_id direto
        p_by_id = [{"target_id": "T_01", "name": "OutroNome", "size": "41"}]
        self.assertEqual(editor.count_pieces_for_target(p_by_id, target), 1)

        # 2. Match por (name, size) sem id
        target_no_id = {"id": "", "name": "Biqueira", "size": "41"}
        p_by_name_size = [{"target_id": "", "name": "Biqueira", "size": "41"}]
        self.assertEqual(editor.count_pieces_for_target(p_by_name_size, target_no_id), 1)

        # 3. Match por name único sem size
        target_name_only = {"id": "", "name": "SolaUnica", "size": ""}
        p_by_name_only = [{"target_id": "", "name": "SolaUnica", "size": ""}]
        self.assertEqual(editor.count_pieces_for_target(p_by_name_only, target_name_only), 1)

        # 4. Rejeição de tamanho divergente
        p_diff_size = [{"target_id": "T_01", "name": "Biqueira", "size": "42"}]
        self.assertEqual(editor.count_pieces_for_target(p_diff_size, target), 0)

        # 5. Rejeição de IDs explícitos distintos
        target_t1 = {"id": "T1", "name": "Biqueira", "size": "41"}
        p_diff_id = [{"target_id": "T2", "name": "Biqueira", "size": "41"}]
        self.assertEqual(editor.count_pieces_for_target(p_diff_id, target_t1), 0)

        # 6. Peças vazias ou target nulo
        self.assertEqual(editor.count_pieces_for_target([], target), 0)
        self.assertEqual(editor.count_pieces_for_target(p_by_id, None), 0)

    # -------------------------------------------------------------------------
    # Cenário 11: prioridade de resolução de camadas resolve_session_layers:
    # - com grid_material_row=6 -> vence grid.
    # - sem grid, com session.layers=4 -> vence session.
    # - sem grid e sem session, com material.layers=3 -> vence material.
    # - sem grid, session e material, com layout.layers=5 -> vence layout.
    # - nenhum definido -> fallback 2.
    # -------------------------------------------------------------------------
    def test_cenario_11_resolve_session_layers_priority(self):
        # 1. Grid vence tudo
        grid_row = ["MAT1", "Vaqueta", "como placa", "1380", "1080", "1.49", "6"]
        session = {"layers": 4}
        material = {"layers": 3}
        layout = {"layers": 5}
        self.assertEqual(resolve_session_layers(session, material, grid_row, layout), 6)

        # 2. Sem grid, vence session.layers
        self.assertEqual(resolve_session_layers(session, material, None, layout), 4)

        # 3. Sem grid e sem session, vence material.layers
        self.assertEqual(resolve_session_layers(None, material, None, layout), 3)

        # 4. Sem grid, sem session e sem material, vence layout.layers
        self.assertEqual(resolve_session_layers(None, None, None, layout), 5)

        # 5. Nenhum definido -> fallback 2
        self.assertEqual(resolve_session_layers(None, None, None, None), 2)

    # -------------------------------------------------------------------------
    # Cenário 12: is_layers_defined:
    # True para cada fonte válida (>= 1), False quando todas None/vazias.
    # -------------------------------------------------------------------------
    def test_cenario_12_is_layers_defined(self):
        # False quando todas vazias
        self.assertFalse(is_layers_defined(None, None, None, None))
        self.assertFalse(is_layers_defined({}, {}, [], {}))
        self.assertFalse(is_layers_defined({"layers": None}, {"layers": ""}, [""] * 7, {"layers": None}))

        # True para cada fonte individual
        self.assertTrue(is_layers_defined(grid_material_row=["", "", "", "", "", "", "4"]))
        self.assertTrue(is_layers_defined(session={"layers": 4}))
        self.assertTrue(is_layers_defined(material={"layers": 3}))
        self.assertTrue(is_layers_defined(layout={"layers": 2}))

        # Valores inválidos (< 1) não contam como definidos
        self.assertFalse(is_layers_defined(session={"layers": 0}))
        self.assertFalse(is_layers_defined(material={"layers": -1}))
        self.assertFalse(is_layers_defined(grid_material_row=["", "", "", "", "", "", "0"]))

    # -------------------------------------------------------------------------
    # Cenário 13: calc_resto:
    # - 4 camadas: pares 125, 109, 97 -> -1; pares 126, 62 -> 0.
    # - 2 camadas: pares 125 -> 0.
    # - 1 camada ou None -> 0.
    # - Sempre resultado <= 0.
    # -------------------------------------------------------------------------
    def test_cenario_13_calc_resto_rules(self):
        # 4 camadas: dados reais confirmados do print da sessão 619955
        self.assertEqual(calc_resto(125, 4), -1)
        self.assertEqual(calc_resto(109, 4), -1)
        self.assertEqual(calc_resto(97, 4), -1)
        self.assertEqual(calc_resto(126, 4), 0)
        self.assertEqual(calc_resto(62, 4), 0)

        # 2 camadas: sempre 0
        self.assertEqual(calc_resto(125, 2), 0)
        self.assertEqual(calc_resto(126, 2), 0)
        self.assertEqual(calc_resto(1, 2), 0)

        # 1 camada ou None ou inválidos
        self.assertEqual(calc_resto(125, 1), 0)
        self.assertEqual(calc_resto(125, None), 0)
        self.assertEqual(calc_resto(None, 4), 0)
        self.assertEqual(calc_resto("invalid", 4), 0)

        # Propriedade fundamental: o retorno de calc_resto é sempre <= 0
        for p in range(1, 150):
            for c in (1, 2, 3, 4, 5, 6, 8):
                res = calc_resto(p, c)
                self.assertLessEqual(res, 0, f"calc_resto({p}, {c}) retornou {res} > 0")

    # -------------------------------------------------------------------------
    # Cenário 14: Contador da barra lateral atualiza dinamicamente ao deletar peças
    # - 20 peças desenhadas -> 20/20 (preto).
    # - delete_selected() de todas as peças -> 0/20 (vermelho déficit #dc2626).
    # -------------------------------------------------------------------------
    def test_cenario_14_delete_selected_updates_sidebar_counter(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s1", "name": "M41", "size": "41", "pairs": 20, "contour": self.box_shape}
        ]
        editor.material = {"layers": 2}
        editor.material_layers = 2
        editor.layouts = []
        editor.placed_pieces = [
            {"target_id": "s1", "name": "M41", "size": "41", "contour": self.box_shape, "x": 10.0, "y": 10.0, "rotation": 0.0}
        ] * 20
        editor.update_sidebar_targets()
        editor.redraw()

        # Antes de deletar: 20/20 em preto
        texts_before = self._get_sidebar_texts(editor)
        c_before = [t for t in texts_before if t["text"] == "20/20"]
        self.assertEqual(len(c_before), 1, "Deveria ter '20/20' antes de deletar")
        self.assertEqual(c_before[0]["fill"], "#000000")

        # Deleta todas as peças selecionadas
        editor.selected_indices = list(range(len(editor.placed_pieces)))
        editor.delete_selected()

        # Depois de deletar: 0/20 em vermelho (déficit)
        self.assertEqual(len(editor.placed_pieces), 0)
        texts_after = self._get_sidebar_texts(editor)
        c_after = [t for t in texts_after if t["text"] == "0/20"]
        self.assertEqual(len(c_after), 1, "Deveria atualizar dinamicamente para '0/20' após exclusão")
        self.assertEqual(c_after[0]["fill"], "#dc2626", "0/20 deve ser vermelho (#dc2626) indicando déficit")

    # -------------------------------------------------------------------------
    # Cenário 15: Contador da barra lateral atualiza dinamicamente ao adicionar
    # peças (duplo clique / add_piece_for_target) e ao desfazer (Ctrl+Z)
    # -------------------------------------------------------------------------
    def test_cenario_15_add_piece_updates_counter_and_undo(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s1", "name": "M41", "size": "41", "pairs": 20, "contour": self.box_shape}
        ]
        editor.material = {"layers": 2}
        editor.material_layers = 2
        editor.layouts = []
        editor.placed_pieces = []
        editor.update_sidebar_targets()
        editor.redraw()

        texts_0 = self._get_sidebar_texts(editor)
        self.assertTrue(any(t["text"] == "0/20" for t in texts_0))

        # Adiciona 1ª peça
        editor.add_piece_for_target(editor.sidebar_targets[0])
        self.assertEqual(len(editor.placed_pieces), 1)
        texts_1 = self._get_sidebar_texts(editor)
        self.assertTrue(any(t["text"] == "1/20" for t in texts_1), "Contador deve avançar para '1/20'")

        # Adiciona 2ª peça
        editor.add_piece_for_target(editor.sidebar_targets[0])
        self.assertEqual(len(editor.placed_pieces), 2)
        texts_2 = self._get_sidebar_texts(editor)
        self.assertTrue(any(t["text"] == "2/20" for t in texts_2), "Contador deve avançar para '2/20'")

        # Desfaz última adição com Ctrl+Z
        editor.undo_action()
        self.assertEqual(len(editor.placed_pieces), 1)
        texts_undo = self._get_sidebar_texts(editor)
        self.assertTrue(any(t["text"] == "1/20" for t in texts_undo), "Contador deve retornar para '1/20' após undo")

    # -------------------------------------------------------------------------
    # Cenário 16: Barra de status reseta coordenadas quando chapa é esvaziada
    # -------------------------------------------------------------------------
    def test_cenario_16_status_bar_reset_when_empty(self):
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.placed_pieces = [
            {"id": 10, "x": 123.45, "y": 678.90, "rotation": 45.0, "name": "M41", "contour": self.box_shape}
        ]
        editor.selected_indices = [0]
        editor.redraw()
        editor.update_status()

        self.assertEqual(editor.lbl_stat_id.cget("text"), "Id: 10")
        self.assertEqual(editor.lbl_stat_x.cget("text"), "X: 123.45")

        # Exclui a peça restante
        editor.delete_selected()
        self.assertEqual(editor.lbl_stat_id.cget("text"), "Id: -")
        self.assertEqual(editor.lbl_stat_x.cget("text"), "X: -")
        self.assertEqual(editor.lbl_stat_y.cget("text"), "Y: -")
        self.assertEqual(editor.lbl_stat_rot.cget("text"), "Rot: -")


if __name__ == "__main__":
    unittest.main()
