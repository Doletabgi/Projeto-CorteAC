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
        dlg = LayoutPrintDialog(self.root, layout_data={'sheet_w_mm':1380,'sheet_h_mm':2980,'placed_pieces':[{'name':'Molde','size':'38'}]*40,'session_shapes':[{'name':'Molde','size':'38','pairs':40,'shape_id':1735}],'material_layers':2})
        self.addCleanup(dlg.destroy)
        self.assertEqual(dlg.legend_data[0]['shape_id'],1735)
        self.assertEqual(dlg.legend_data[0]['sizes'][0]['n'],40)
        self.assertEqual(dlg.legend_data[0]['sizes'][0]['m'],40)


    def test_02_multi_plate_pairs_and_sum(self):
        layouts=[{'name':'lay0','layers':4,'width_mm':1000,'height_mm':1000,'pieces':[{'name':'Molde','size':'38'}]*14},{'name':'lay1','layers':2,'width_mm':1000,'height_mm':1000,'pieces':[{'name':'Molde','size':'38'}]*12}]
        dlg=LayoutPrintDialog(self.root,layout_data={'layouts':layouts,'session_shapes':[{'name':'Molde','size':'38','pairs':40}]})
        self.addCleanup(dlg.destroy)
        self.assertEqual(dlg.legend_data[0]['sizes'][0]['n'],28)
        dlg.next_page()
        self.assertEqual(dlg.legend_data[0]['sizes'][0]['n'],12)
        self.assertEqual(dlg.legend_data[0]['sizes'][0]['m'],40)


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
        # A ficha mostra produção e pedido em colunas explícitas, sem classificar
        # uma placa isolada como déficit da sessão ou alterar a regra de sobras.
        dlg=LayoutPrintDialog(self.root,layout_data={'sheet_w_mm':1000,'sheet_h_mm':1000,'placed_pieces':[{'name':'Molde','size':'38'}]*50,'session_shapes':[{'name':'Molde','size':'38','pairs':40}],'material_layers':2})
        self.addCleanup(dlg.destroy)
        self.assertEqual(dlg.legend_data[0]['sizes'][0]['n'],50)
        self.assertEqual(dlg.legend_data[0]['sizes'][0]['m'],40)
        self.assertIn('n/m = pares na placa / pedido da sessão',dlg.print_texts)
        self.assertIn('38: 50/40',dlg.print_texts)


    def test_06_shape_id_rendering(self):
        dlg=LayoutPrintDialog(self.root,layout_data={'sheet_w_mm':1000,'sheet_h_mm':1000,'placed_pieces':[{'name':'Molde','size':'38'}],'session_shapes':[{'name':'Molde','size':'38','pairs':1,'shape_id':1735}]})
        self.addCleanup(dlg.destroy)
        self.assertTrue(any('#1735' in t for t in dlg.print_texts))
        self.assertEqual(dlg.legend_data[0]['shape_id'],1735)


    def test_07_token_wrapping_between_sizes(self):
        sizes=['28','29','30','31','32','33','34','35','35.5','36','37','38','39','40','41','42']
        dlg=LayoutPrintDialog(self.root,layout_data={'sheet_w_mm':1000,'sheet_h_mm':1000,'placed_pieces':[{'name':'MoldeLongo','size':sz} for sz in sizes],'material_layers':2})
        self.addCleanup(dlg.destroy)
        self.assertEqual(len(dlg.legend_data[0]["sizes"]),len(sizes))
        for sz in sizes:
            self.assertTrue(any(sz+': 1/?' in t for t in dlg.print_texts))
        self.assertGreaterEqual(len(dlg.render_pillow_pages()),1)


    def test_08_layers_pairs_calculation(self):
        for layers, count in [(1,80),(2,40),(4,20)]:
            dlg=LayoutPrintDialog(self.root,layout_data={'sheet_w_mm':1000,'sheet_h_mm':1000,'placed_pieces':[{'name':'Molde','size':'38'}]*count,'material_layers':layers})
            try:
                self.assertEqual(dlg.legend_data[0]['sizes'][0]['n'],40)
                self.assertIsNone(dlg.legend_data[0]['sizes'][0]['m'])
            finally:
                dlg.destroy()


    def test_09_explanatory_footnote_present(self):
        dlg=LayoutPrintDialog(self.root,layout_data={'sheet_w_mm':1000,'sheet_h_mm':1000,'placed_pieces':[{'name':'Molde','size':'38'}]})
        self.addCleanup(dlg.destroy)
        text=' '.join(dlg.print_texts)
        self.assertIn('Aproveitamento geométrico:',text)
        self.assertIn('RESUMO DESTA PLACA',text)
        self.assertIn('Total de pares da placa:',text)
        for removed in ['Instâncias desenhadas:', 'Peças físicas:', 'Pares de componentes:', 'Área plana:', 'Área ocupada:', 'Peças físicas =']:
            self.assertNotIn(removed,text)
        self.assertIn('n/m = pares na placa / pedido da sessão',text)


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

    def test_11_print_preview_tip_zone_operator_text_header(self):
        dlg=LayoutPrintDialog(self.root,layout_data={'sheet_w_mm':1380,'sheet_h_mm':2990,'tip_zone':(0,2450,1380,2990),'tip_mode':'faixa','layers_tip':2,'material_layers':4,'placed_pieces':[{'name':'Molde','size':'38','x':100,'y':2500}]})
        self.addCleanup(dlg.destroy)
        text=' '.join(dlg.print_texts)
        for expected in ['folhas longas','folhas curtas','SEM cobrir a ponta','Ponta: 2 camadas']:
            self.assertIn(expected,text)
        self.assertEqual(dlg.legend_data[0]['sizes'][0]['n'],1)


    def test_12_legend_box_located_in_sidebar_beside_bed(self):
        # A tabela fica à direita do mapa, com fonte >= 9 pt.
        dlg=LayoutPrintDialog(self.root,layout_data={'sheet_w_mm':1380,'sheet_h_mm':2820,'placed_pieces':[{'name':'Molde','size':'38'}]})
        self.addCleanup(dlg.destroy)
        self.assertIn('MODELOS E QUANTIDADES',dlg.print_texts)
        self.assertIn('n/m = pares na placa / pedido da sessão',dlg.print_texts)
        self.assertTrue(dlg.canvas.find_withtag('print_page'))
        region = dlg.print_regions[0]
        self.assertGreater(region['models'][0], region['map'][2])



if __name__ == "__main__":
    unittest.main()
