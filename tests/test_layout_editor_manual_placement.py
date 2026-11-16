"""Inclusão pela miniatura acompanha o mouse até o clique de posicionamento."""

import copy
import tkinter as tk
import unittest
from types import SimpleNamespace

from cad.geometry import polygon_bbox, transform_contour
from ui.layout_editor_view import LayoutEditorView


SHAPE = {
    "id": "manual-41",
    "name": "Molde manual",
    "size": "41",
    "pairs": 10,
    # Contorno fora da origem para detectar deslocamentos indevidos do ponteiro.
    "contour": [
        {"x": -20.0, "y": 10.0}, {"x": 40.0, "y": 10.0},
        {"x": 40.0, "y": 50.0}, {"x": -20.0, "y": 50.0},
    ],
    "holes": [[{"x": 0.0, "y": 20.0}, {"x": 10.0, "y": 20.0}, {"x": 5.0, "y": 30.0}]],
    "stitching": [[{"x": -10.0, "y": 15.0}, {"x": 30.0, "y": 15.0}]],
    "internal_cuts": [[{"x": 0.0, "y": 35.0}, {"x": 10.0, "y": 35.0}]],
}


def event(x, y, state=0):
    return SimpleNamespace(x=x, y=y, state=state)


class TestManualPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("Tkinter display not available")
        cls.root.geometry("1100x750+5000+5000")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.view = LayoutEditorView(self.root, layout_name="[MANUAL]", load_sample=False)
        self.view.pack(fill="both", expand=True)
        self.view.set_sheet_size(1200.0, 1000.0)
        self.view.session_shapes = [copy.deepcopy(SHAPE)]
        self.view.update_sidebar_targets()
        self.root.update()
        self.view.redraw()
        self.view.layouts = [{"pieces": [], "placed_pieces": []}]

    def tearDown(self):
        self.view.destroy()

    def _sidebar_event(self):
        y_start, item_h, col_width, _ = self.view._get_sidebar_grid_layout()
        return event(self.view.sidebar_div_x + 15 + col_width // 2, y_start + item_h // 2)

    def _start(self):
        click = self._sidebar_event()
        self.view.on_canvas_click(click)
        self.view.on_canvas_release(click)
        self.view.on_canvas_double_click(click)
        self.view.on_canvas_release(click)

    def _table_event(self, wx=400.0, wy=450.0):
        x, y = self.view.world_to_screen(wx, wy)
        return event(round(x), round(y))

    def _assert_center_at_pointer(self, piece, pointer):
        poly = transform_contour(piece["contour"], piece["x"], piece["y"], piece["rotation"])
        x0, y0, x1, y1 = polygon_bbox(poly)
        sx, sy = self.view.world_to_screen((x0 + x1) / 2, (y0 + y1) / 2)
        self.assertAlmostEqual(sx, pointer.x, places=5)
        self.assertAlmostEqual(sy, pointer.y, places=5)

    def test_double_click_attaches_piece_and_motion_without_button_follows_pointer(self):
        self._start()
        self.assertIsNotNone(self.view._manual_piece)
        self._assert_center_at_pointer(self.view._manual_piece, self._sidebar_event())

        pointer = self._table_event()
        self.view.on_mouse_move(pointer)
        self._assert_center_at_pointer(self.view._manual_piece, pointer)
        self.assertTrue(self.view.canvas.find_withtag("manual_piece_preview"))
        coords = self.view.canvas.coords("manual_piece_preview")
        self.assertAlmostEqual((min(coords[::2]) + max(coords[::2])) / 2, pointer.x)
        self.assertAlmostEqual((min(coords[1::2]) + max(coords[1::2])) / 2, pointer.y)
        self.assertEqual(self.view.placed_pieces, [])
        self.assertEqual(self.view.layouts[0]["pieces"], [])
        self.assertEqual(self.view.undo_stack, [])
        self.assertFalse(self.view.is_modified)

    def test_click_commits_at_pointer_preserves_shape_and_undo_removes_piece(self):
        self._start()
        # Confirma na posição do clique, mesmo sem um Motion anterior nessa posição.
        click = self._table_event(550.0, 350.0)
        self.view.on_canvas_click(click)
        self.view.on_canvas_release(click)
        self.assertIsNone(self.view._manual_piece)
        self.assertFalse(self.view.canvas.find_withtag("manual_piece_preview"))
        self.assertEqual(len(self.view.placed_pieces), 1)
        piece = self.view.placed_pieces[0]
        self._assert_center_at_pointer(piece, click)
        for key in ("contour", "holes", "stitching", "internal_cuts"):
            self.assertEqual(piece[key], SHAPE[key])
            self.assertIsNot(piece[key], SHAPE[key])
        self.assertEqual(piece["target_id"], SHAPE["id"])
        self.assertEqual(self.view.selected_indices, [0])
        self.assertEqual(self.view.layouts[0]["pieces"], [piece])
        self.assertTrue(self.view.is_modified)
        self.assertEqual(len(self.view.undo_stack), 1)
        self.view.undo_action()
        self.assertEqual(self.view.placed_pieces, [])
        self.assertEqual(self.view.layouts[0]["pieces"], [])

    def test_preview_stays_at_pointer_with_zoom_pan_and_redraw(self):
        self._start()
        for zoom, pan_x, pan_y in ((0.7, 35.0, -25.0), (1.4, -40.0, 30.0)):
            with self.subTest(zoom=zoom):
                self.view.zoom_factor = zoom
                self.view.pan_offset_x = pan_x
                self.view.pan_offset_y = pan_y
                self.view.redraw()
                pointer = self._table_event()
                self.view.on_mouse_move(pointer)
                self._assert_center_at_pointer(self.view._manual_piece, pointer)
                self.view.redraw()
                self._assert_center_at_pointer(self.view._manual_piece, pointer)
                self.assertTrue(self.view.canvas.find_withtag("manual_piece_preview"))

    def test_collision_and_sheet_bounds_keep_piece_on_pointer_until_valid_click(self):
        obstacle = self.view._build_piece_for_target(SHAPE, 390.0, 420.0)
        self.view.set_pieces([obstacle])
        self._start()
        for click in (self._table_event(), self._table_event(5.0, 450.0)):
            with self.subTest(click=click):
                self.view.on_canvas_click(click)
                self.view.on_canvas_release(click)
                self.assertEqual(len(self.view.placed_pieces), 1)
                self.assertIsNotNone(self.view._manual_piece)
                self.assertEqual(self.view.undo_stack, [])
                self._assert_center_at_pointer(self.view._manual_piece, click)

        click = self._table_event(600.0, 450.0)
        self.view.on_canvas_click(click)
        self.assertEqual(len(self.view.placed_pieces), 2)
        self.assertIsNone(self.view._manual_piece)

    def test_escape_discards_preview_without_changing_layout_or_undo(self):
        self._start()
        self.view.on_canvas_drag(self._table_event())
        self.view.cancel_drag()
        self.assertIsNone(self.view._manual_piece)
        self.assertEqual(self.view.placed_pieces, [])
        self.assertEqual(self.view.undo_stack, [])
        self.assertFalse(self.view.is_modified)
        self.assertFalse(self.view.canvas.find_withtag("manual_piece_preview"))

    def test_undo_cancels_preview_and_preserves_previous_edit(self):
        self.view.add_piece_for_target(SHAPE)
        before = copy.deepcopy(self.view.placed_pieces)
        self._start()
        self.view.undo_action()
        self.assertIsNone(self.view._manual_piece)
        self.assertEqual(self.view.placed_pieces, before)
        self.assertEqual(len(self.view.undo_stack), 1)

    def test_switching_sheet_cancels_preview_without_inserting_piece(self):
        self.view.layouts.append({"name": "lay0001", "pieces": [], "placed_pieces": []})
        self._start()
        self.assertTrue(self.view.switch_to_layout(1))
        self.assertIsNone(self.view._manual_piece)
        self.assertFalse(self.view.canvas.find_withtag("manual_piece_preview"))
        self.assertEqual(self.view.layouts[0]["pieces"], [])
        self.assertEqual(self.view.placed_pieces, [])

    def test_tk_bindings_double_click_move_and_place(self):
        canvas = self.view.canvas
        sidebar = self._sidebar_event()
        for sequence, timestamp in (("<ButtonPress-1>", 1000), ("<ButtonRelease-1>", 1010),
                                    ("<ButtonPress-1>", 1100), ("<ButtonRelease-1>", 1110)):
            canvas.event_generate(sequence, x=sidebar.x, y=sidebar.y, time=timestamp)
        self.assertIsNotNone(self.view._manual_piece)
        pointer = self._table_event()
        canvas.event_generate("<Motion>", x=pointer.x, y=pointer.y, state=0)
        self._assert_center_at_pointer(self.view._manual_piece, pointer)
        canvas.event_generate("<ButtonPress-1>", x=pointer.x, y=pointer.y, time=2000)
        canvas.event_generate("<ButtonRelease-1>", x=pointer.x, y=pointer.y, time=2010)
        self.assertEqual(len(self.view.placed_pieces), 1)
        self._assert_center_at_pointer(self.view.placed_pieces[0], pointer)


if __name__ == "__main__":
    unittest.main()
