"""
Testes automatizados para a identificação da(s) placa(s) em que cada molde/número está alocado
na barra lateral do Layout Editor (LayoutEditorView).
"""

import unittest
import tkinter as tk

from ui.layout_editor_view import LayoutEditorView


class TestSidebarPlatesIdentification(unittest.TestCase):
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
            {"x": 50.0, "y": 0.0},
            {"x": 50.0, "y": 50.0},
            {"x": 0.0, "y": 50.0}
        ]

    def _get_sidebar_texts(self, editor):
        items = []
        for item_id in editor.canvas.find_withtag("sidebar_ui"):
            if editor.canvas.type(item_id) == "text":
                txt = editor.canvas.itemcget(item_id, "text")
                fill = editor.canvas.itemcget(item_id, "fill")
                items.append({"text": txt, "fill": fill, "id": item_id})
        return items

    def test_multi_sheet_plates_identification_on_sidebar(self):
        """
        Cenário fiel ao screenshot do usuário:
        Sessão com 2 placas.
        Placa 1 contém 36a (51 pç) e 32a (20 pç).
        Placa 2 contém 32a (31 pç), 31a (51 pç) e 30a (51 pç).
        Molde 29a não possui peças alocadas.
        """
        editor = LayoutEditorView(self.root, is_subwindow=True)
        editor.session_shapes = [
            {"id": "s36", "name": "323_PalAcb_36a", "size": "36", "pairs": 101, "contour": self.box_shape},
            {"id": "s32", "name": "323_PalAcb_32a", "size": "32", "pairs": 101, "contour": self.box_shape},
            {"id": "s31", "name": "323_PalAcb_31a", "size": "31", "pairs": 101, "contour": self.box_shape},
            {"id": "s30", "name": "323_PalAcb_30a", "size": "30", "pairs": 101, "contour": self.box_shape},
            {"id": "s29", "name": "323_PalAcb_29a", "size": "29", "pairs": 101, "contour": self.box_shape},
        ]
        editor.session = {"layers": 4}
        editor.material = {"layers": 4}
        editor.material_layers = 4

        p1_pieces = (
            [{"target_id": "s36", "name": "323_PalAcb_36a", "size": "36", "contour": self.box_shape, "x": float(100 + i * 60), "y": 100.0, "rotation": 0.0} for i in range(51)] +
            [{"target_id": "s32", "name": "323_PalAcb_32a", "size": "32", "contour": self.box_shape, "x": float(100 + i * 60), "y": 200.0, "rotation": 0.0} for i in range(20)]
        )
        p2_pieces = (
            [{"target_id": "s32", "name": "323_PalAcb_32a", "size": "32", "contour": self.box_shape, "x": float(100 + i * 60), "y": 100.0, "rotation": 0.0} for i in range(31)] +
            [{"target_id": "s31", "name": "323_PalAcb_31a", "size": "31", "contour": self.box_shape, "x": float(100 + i * 60), "y": 200.0, "rotation": 0.0} for i in range(51)] +
            [{"target_id": "s30", "name": "323_PalAcb_30a", "size": "30", "contour": self.box_shape, "x": float(100 + i * 60), "y": 300.0, "rotation": 0.0} for i in range(51)]
        )

        layouts_mock = [
            {"layout_index": 0, "name": "lay0000", "pieces": p1_pieces, "layers": 4},
            {"layout_index": 1, "name": "lay0001", "pieces": p2_pieces, "layers": 4},
        ]

        editor.set_session_layouts(layouts_mock, initial_index=0)
        editor.update_sidebar_targets()

        # 1. Validação direta do helper get_plates_for_target
        t36 = editor.sidebar_targets[0]
        t32 = editor.sidebar_targets[1]
        t31 = editor.sidebar_targets[2]
        t30 = editor.sidebar_targets[3]
        t29 = editor.sidebar_targets[4]

        self.assertEqual(editor.get_plates_for_target(t36), [1])
        self.assertEqual(editor.get_plates_for_target(t32), [1, 2])
        self.assertEqual(editor.get_plates_for_target(t31), [2])
        self.assertEqual(editor.get_plates_for_target(t30), [2])
        self.assertEqual(editor.get_plates_for_target(t29), [])

        # 2. Validação da renderização na Placa 1
        editor.draw_sidebar(div_x=0, ch=500, cw=350)
        texts_p1 = [t["text"] for t in self._get_sidebar_texts(editor)]

        self.assertIn("Placa 1", texts_p1)
        self.assertIn("Placa 1, 2", texts_p1)
        self.assertIn("Placa 2", texts_p1)
        self.assertIn("Sem placa", texts_p1)

        # 3. Validação ao mudar para a Placa 2
        editor.switch_to_layout(1, save_current=True)
        editor.draw_sidebar(div_x=0, ch=500, cw=350)
        texts_p2 = [t["text"] for t in self._get_sidebar_texts(editor)]

        self.assertIn("Placa 1", texts_p2)
        self.assertIn("Placa 1, 2", texts_p2)
        self.assertIn("Placa 2", texts_p2)
        self.assertIn("Sem placa", texts_p2)

        # 4. Validação da mensagem de clique quando o molde não está na placa atual
        editor.switch_to_layout(0, save_current=True) # volta para Placa 1
        # Simula clique no molde 31a (índice 2) que está apenas na Placa 2
        y_start, item_h, col_width, num_cols = editor._get_sidebar_grid_layout()
        col = 2 % num_cols
        row = 2 // num_cols
        class MockEvent:
            x = editor.sidebar_div_x + 15 + col * col_width + col_width // 2
            y = y_start + row * item_h + item_h // 2
        editor.on_sidebar_click(MockEvent())

        status_text = editor.lbl_stat_pos.cget("text")
        self.assertIn("presente na Placa 2", status_text)


if __name__ == "__main__":
    unittest.main()
