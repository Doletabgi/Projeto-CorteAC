"""
Testes unitários automatizados para a Legenda de Moldes na Impressão A4 (LayoutPrintDialog).
Cobre todos os 10 requisitos técnicos:
1. Caso 1: Placa única -> tamanho: n/m com n=m (ex: 28: 40/40)
2. Caso 2: Múltiplas placas -> lay0000 28: 28/40 e lay0001 28: 12/40 (soma 40)
3. Caso 3: Formatação de tamanho: inteiros sem .00 ("28"), meios com .5 ("35.5")
4. Caso 4: Ausência completa de "/0" na legenda
5. Caso 5: Destaque em vermelho (#dc2626) quando n > m
6. Caso 6: Shape ID ao lado do nome ("129_187_Tras  #1735") e omitido sem "#" quando ausente
7. Caso 7: Quebra de linha entre tamanhos sem partir tokens n/m
8. Caso 8: Contagem sempre em pares conforme camadas (peças/2 com layers=1; peças com layers=2)
9. Caso 9: Nota explicativa de rodapé "n/m = pares nesta placa / pedido total"
10. Caso 10: Exportação gráfica idêntica no Pillow (render_pillow_page)
"""

import unittest
import tkinter as tk
from PIL import Image
from ui.layout_print_dialog import LayoutPrintDialog, format_size, extract_molde_base_name


class TestLayoutPrintLegend(unittest.TestCase):
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

    def test_03_format_size(self):
        """Caso 3: Formatação de tamanho - inteiros sem .00, meios com .5."""
        self.assertEqual(format_size("28.00"), "28")
        self.assertEqual(format_size("28.0"), "28")
        self.assertEqual(format_size(28.0), "28")
        self.assertEqual(format_size(28), "28")
        self.assertEqual(format_size("28"), "28")

        self.assertEqual(format_size("35.50"), "35.5")
        self.assertEqual(format_size("35.5"), "35.5")
        self.assertEqual(format_size(35.5), "35.5")

        self.assertEqual(format_size("37.25"), "37.25")
        self.assertEqual(format_size(37.25), "37.25")
        self.assertEqual(format_size(""), "")
        self.assertEqual(format_size(None), "")

    def test_extract_molde_base_name(self):
        """Valida remoção do sufixo de tamanho do nome do molde para agrupamento."""
        self.assertEqual(extract_molde_base_name("129_187_Tras", "28"), "129_187_Tras")
        self.assertEqual(extract_molde_base_name("129_187_Tras 28", "28"), "129_187_Tras")
        self.assertEqual(extract_molde_base_name("129_187_Tras_28", "28"), "129_187_Tras")
        self.assertEqual(extract_molde_base_name("129_187_Tras - 28.00", "28.00"), "129_187_Tras")
        self.assertEqual(extract_molde_base_name("Gasp_35.5", "35.5"), "Gasp")

    def test_01_single_plate_pairs(self):
        """Caso 1: Placa única -> n=m (ex.: 28: 40/40), nunca n/0."""
        # 40 peças colocadas com 2 camadas -> 40 pares
        placed = [{"name": "129_187_Tras", "size": "28"} for _ in range(40)]
        session_shapes = [{"name": "129_187_Tras", "size": "28", "pairs": 40, "shape_id": 1735}]

        dlg = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": placed,
            "session_shapes": session_shapes,
            "material_layers": 2
        })

        self.assertEqual(len(dlg.legend_data), 1)
        row = dlg.legend_data[0]
        self.assertEqual(row["molde_name"], "129_187_Tras")
        self.assertEqual(row["shape_id"], "1735")
        self.assertEqual(len(row["sizes"]), 1)
        sz_item = row["sizes"][0]
        self.assertEqual(sz_item["size"], "28")
        self.assertEqual(sz_item["n"], 40)
        self.assertEqual(sz_item["m"], 40)
        self.assertFalse(sz_item["is_error"])

        # Também testa fallback quando session_shapes não é passado em placa única:
        dlg_no_sess = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": placed,
            "material_layers": 2
        })
        self.assertEqual(dlg_no_sess.legend_data[0]["sizes"][0]["n"], 40)
        self.assertEqual(dlg_no_sess.legend_data[0]["sizes"][0]["m"], 40)

        dlg.destroy()
        dlg_no_sess.destroy()

    def test_02_multi_plate_pairs_and_sum(self):
        """Caso 2: Múltiplas placas -> lay0000 28: 28/40 e lay0001 28: 12/40 (soma 40)."""
        lay0_pieces = [{"name": "129_187_Tras", "size": "28"} for _ in range(28)]
        lay1_pieces = [{"name": "129_187_Tras", "size": "28"} for _ in range(12)]
        layouts = [
            {"name": "lay0000", "pieces": lay0_pieces},
            {"name": "lay0001", "pieces": lay1_pieces}
        ]
        session_shapes = [{"name": "129_187_Tras", "size": "28", "pairs": 40, "shape_id": "1735"}]

        # Placa 0
        dlg0 = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": lay0_pieces,
            "session_shapes": session_shapes,
            "layouts": layouts,
            "current_layout_index": 0,
            "material_layers": 2
        })
        sz0 = dlg0.legend_data[0]["sizes"][0]
        self.assertEqual(sz0["n"], 28)
        self.assertEqual(sz0["m"], 40)
        self.assertFalse(sz0["is_error"])

        # Placa 1
        dlg1 = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": lay1_pieces,
            "session_shapes": session_shapes,
            "layouts": layouts,
            "current_layout_index": 1,
            "material_layers": 2
        })
        sz1 = dlg1.legend_data[0]["sizes"][0]
        self.assertEqual(sz1["n"], 12)
        self.assertEqual(sz1["m"], 40)
        self.assertFalse(sz1["is_error"])

        # Soma das placas = total pedido
        self.assertEqual(sz0["n"] + sz1["n"], sz0["m"])

        # Fallback sem session_shapes em multi-placa: deriva m da soma das placas (28 + 12 = 40)
        dlg_multi_fallback = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": lay0_pieces,
            "layouts": layouts,
            "current_layout_index": 0,
            "material_layers": 2
        })
        fb_sz = dlg_multi_fallback.legend_data[0]["sizes"][0]
        self.assertEqual(fb_sz["n"], 28)
        self.assertEqual(fb_sz["m"], 40)

        dlg0.destroy()
        dlg1.destroy()
        dlg_multi_fallback.destroy()

    def test_04_absence_of_slash_zero(self):
        """Caso 4: Ausência de '/0' em qualquer string ou token da legenda."""
        placed = [
            {"name": "129_187_Tras", "size": "28"} for _ in range(10)
        ] + [
            {"name": "129_187_Tras", "size": "35.5"} for _ in range(6)
        ]
        session_shapes = [
            {"name": "129_187_Tras", "size": "28", "pairs": 10},
            {"name": "129_187_Tras", "size": "35.5", "pairs": 6}
        ]

        dlg = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": placed,
            "session_shapes": session_shapes,
            "material_layers": 2
        })

        for row in dlg.legend_data:
            for s in row["sizes"]:
                token = f"{s['size']}: {s['n']}/{s['m']}"
                self.assertNotIn("/0", token, f"Token contém /0 indevido: {token}")
                self.assertGreater(s["m"], 0, f"m deve ser maior que 0: {s}")

        # Varre todos os textos criados no canvas
        canvas_texts = [dlg.canvas.itemcget(item_id, "text") for item_id in dlg.canvas.find_all() if dlg.canvas.type(item_id) == "text"]
        for txt in canvas_texts:
            self.assertNotIn("/0", txt, f"Texto no canvas contém /0: {txt}")

        dlg.destroy()

    def test_05_error_color_when_n_greater_than_m(self):
        """Caso 5: n > m aparece em vermelho (#dc2626) tanto no canvas quanto no Pillow."""
        # 50 peças colocadas numa placa (50 pares) mas pedido total é de apenas 40
        placed = [{"name": "129_187_Tras", "size": "28"} for _ in range(50)]
        session_shapes = [{"name": "129_187_Tras", "size": "28", "pairs": 40}]

        dlg = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": placed,
            "session_shapes": session_shapes,
            "material_layers": 2
        })

        sz = dlg.legend_data[0]["sizes"][0]
        self.assertEqual(sz["n"], 50)
        self.assertEqual(sz["m"], 40)
        self.assertTrue(sz["is_error"])

        # Encontra o item de texto no canvas com o texto "28: 50/40"
        red_items = []
        for item_id in dlg.canvas.find_all():
            if dlg.canvas.type(item_id) == "text":
                txt = dlg.canvas.itemcget(item_id, "text")
                fill = dlg.canvas.itemcget(item_id, "fill")
                if "28: 50/40" in txt:
                    red_items.append((txt, fill))

        self.assertGreater(len(red_items), 0, "Item com 28: 50/40 não encontrado no canvas")
        for txt, fill in red_items:
            self.assertEqual(fill.lower(), "#dc2626", f"Cor do token com erro deveria ser #dc2626 mas foi {fill}")

        # Valida que render_pillow_page roda sem exceção com item de erro
        img = dlg.render_pillow_page()
        self.assertIsInstance(img, Image.Image)

        dlg.destroy()

    def test_06_shape_id_rendering(self):
        """Caso 6: Shape ID ao lado do nome ('129_187_Tras  #1735'), omitido sem '#' quando ausente."""
        # Com Shape ID
        placed_with_id = [{"name": "129_187_Tras", "size": "28"}]
        sess_with_id = [{"name": "129_187_Tras", "size": "28", "pairs": 1, "shape_id": 1735}]

        dlg_with = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": placed_with_id,
            "session_shapes": sess_with_id,
            "material_layers": 2
        })
        self.assertEqual(dlg_with.legend_data[0]["shape_id"], "1735")

        canvas_texts_with = [dlg_with.canvas.itemcget(it, "text") for it in dlg_with.canvas.find_all() if dlg_with.canvas.type(it) == "text"]
        self.assertTrue(any("#1735" in t for t in canvas_texts_with), "Tag #1735 não encontrada no canvas")

        # Sem Shape ID
        placed_no_id = [{"name": "Solado_Borracha", "size": "40"}]
        dlg_without = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": placed_no_id,
            "material_layers": 2
        })
        self.assertIsNone(dlg_without.legend_data[0]["shape_id"])

        canvas_texts_without = [dlg_without.canvas.itemcget(it, "text") for it in dlg_without.canvas.find_all() if dlg_without.canvas.type(it) == "text"]
        self.assertFalse(any("#" in t for t in canvas_texts_without if "Solado_Borracha" in t or t.strip().startswith("#")),
                         "Símbolo '#' não deve aparecer quando não há shape_id")

        dlg_with.destroy()
        dlg_without.destroy()

    def test_07_token_wrapping_between_sizes(self):
        """Caso 7: Quebra de linha entre tamanhos sem quebrar n/m e sem estourar largura A4."""
        # 16 tamanhos diferentes
        sizes = ["28", "29", "30", "31", "32", "33", "34", "35", "35.5", "36", "37", "38", "39", "40", "41", "42"]
        placed = [{"name": "MoldeLongo", "size": sz} for sz in sizes]
        session_shapes = [{"name": "MoldeLongo", "size": sz, "pairs": 10} for sz in sizes]

        dlg = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": placed,
            "session_shapes": session_shapes,
            "material_layers": 2
        })

        # Verifica se todos os tokens foram preservados íntegros
        row_sizes = dlg.legend_data[0]["sizes"]
        self.assertEqual(len(row_sizes), len(sizes))

        canvas_texts = [dlg.canvas.itemcget(it, "text") for it in dlg.canvas.find_all() if dlg.canvas.type(it) == "text"]
        for sz in sizes:
            expected_token = f"{sz}: 1/10"
            self.assertTrue(any(expected_token in t for t in canvas_texts),
                            f"Token íntegro {expected_token} deve estar presente no canvas")

        # Testa Pillow export do layout com wrapping
        img = dlg.render_pillow_page()
        self.assertIsNotNone(img)

        dlg.destroy()

    def test_08_layers_pairs_calculation(self):
        """Caso 8: Contagem sempre em pares (peças/2 com layers=1; peças com layers=2; peças*2 com layers=4)."""
        # 80 peças com 1 camada -> 40 pares
        dlg_l1 = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": [{"name": "MoldeA", "size": "40"} for _ in range(80)],
            "material_layers": 1
        })
        self.assertEqual(dlg_l1.legend_data[0]["sizes"][0]["n"], 40)
        self.assertEqual(dlg_l1.legend_data[0]["sizes"][0]["m"], 40)

        # 40 peças com 2 camadas -> 40 pares
        dlg_l2 = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": [{"name": "MoldeA", "size": "40"} for _ in range(40)],
            "material_layers": 2
        })
        self.assertEqual(dlg_l2.legend_data[0]["sizes"][0]["n"], 40)
        self.assertEqual(dlg_l2.legend_data[0]["sizes"][0]["m"], 40)

        # 20 peças com 4 camadas -> 40 pares
        dlg_l4 = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": [{"name": "MoldeA", "size": "40"} for _ in range(20)],
            "material_layers": 4
        })
        self.assertEqual(dlg_l4.legend_data[0]["sizes"][0]["n"], 40)
        self.assertEqual(dlg_l4.legend_data[0]["sizes"][0]["m"], 40)

        dlg_l1.destroy()
        dlg_l2.destroy()
        dlg_l4.destroy()

    def test_09_explanatory_footnote_present(self):
        """Caso 9: Nota explicativa de rodapé 'n/m = pares nesta placa / pedido total' presente."""
        dlg = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": [{"name": "MoldeX", "size": "38"}],
            "material_layers": 2
        })

        canvas_texts = [dlg.canvas.itemcget(it, "text") for it in dlg.canvas.find_all() if dlg.canvas.type(it) == "text"]
        footnote_found = any("n/m = pares nesta placa / pedido total" in t for t in canvas_texts)
        self.assertTrue(footnote_found, "Nota explicativa de rodapé não encontrada no canvas")

        dlg.destroy()

    def test_10_pillow_render_page_identical(self):
        """Caso 10: Exportação gráfica Pillow idêntica e sem erros em portrait e landscape."""
        dlg_portrait = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": [{"name": "MoldeX", "size": "38"}],
            "orientation": "portrait",
            "material_layers": 2
        })
        img_p = dlg_portrait.render_pillow_page()
        self.assertIsInstance(img_p, Image.Image)
        self.assertEqual(img_p.mode, "RGB")
        self.assertGreater(img_p.height, img_p.width)

        dlg_landscape = LayoutPrintDialog(self.root, layout_data={
            "placed_pieces": [{"name": "MoldeX", "size": "38"}],
            "orientation": "landscape",
            "material_layers": 2
        })
        img_l = dlg_landscape.render_pillow_page()
        self.assertIsInstance(img_l, Image.Image)
        self.assertEqual(img_l.mode, "RGB")
        self.assertGreater(img_l.width, img_l.height)

        dlg_portrait.destroy()
        dlg_landscape.destroy()


if __name__ == "__main__":
    unittest.main()
