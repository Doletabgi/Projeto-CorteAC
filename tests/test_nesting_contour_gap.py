import unittest
import math
from database import DatabaseManager
from cad.nesting_engine import auto_nest_pieces
from cad.geometry import transform_contour, polygon_bbox, polygons_collide, point_segment_distance_sq

class TestNestingContourGap(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager()
        self.shapes = self.db.get_shapes()
        self.bed_width = 1350.0
        self.bed_height = 2553.38

    def _calc_min_dist(self, poly_a, poly_b):
        min_dist_sq = float("inf")
        len_a = len(poly_a)
        len_b = len(poly_b)
        for pt in poly_a:
            px, py = pt["x"], pt["y"]
            for j in range(len_b):
                p1 = poly_b[j]
                p2 = poly_b[(j + 1) % len_b]
                d_sq = point_segment_distance_sq(px, py, p1["x"], p1["y"], p2["x"], p2["y"])
                if d_sq < min_dist_sq:
                    min_dist_sq = d_sq
        for pt in poly_b:
            px, py = pt["x"], pt["y"]
            for i in range(len_a):
                p1 = poly_a[i]
                p2 = poly_a[(i + 1) % len_a]
                d_sq = point_segment_distance_sq(px, py, p1["x"], p1["y"], p2["x"], p2["y"])
                if d_sq < min_dist_sq:
                    min_dist_sq = d_sq
        return math.sqrt(min_dist_sq)

    def test_sint_engine_respects_gap_1mm(self):
        pieces = auto_nest_pieces(
            self.shapes, self.bed_width, self.bed_height,
            target_count=30, strategy="sint", gap_mm=1.0
        )
        self.assertGreaterEqual(len(pieces), 20)

        polys = [transform_contour(p["contour"], p["x"], p["y"], p["rotation"]) for p in pieces]
        bboxes = [polygon_bbox(p) for p in polys]

        # Verify zero collision
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                self.assertFalse(
                    polygons_collide(polys[i], polys[j], gap=0.0, bbox_a=bboxes[i], bbox_b=bboxes[j]),
                    f"Colisao detectada entre peca {pieces[i]["id"]} e {pieces[j]["id"]}"
                )

        # Verify adjacent horizontal gap is ~1.0mm (not 14.8mm)
        for i in range(min(5, len(polys) - 1)):
            if pieces[i]["y"] == pieces[i+1]["y"]:
                dist = self._calc_min_dist(polys[i], polys[i+1])
                self.assertGreaterEqual(dist, 1.0, f"Gap violado: {dist:.3f} mm < 1.0 mm")
                self.assertLess(dist, 1.3, f"Gap excessivo (sem bumping): {dist:.3f} mm >= 1.3 mm")

    def test_dieproc_engine_respects_gap_1mm(self):
        pieces = auto_nest_pieces(
            self.shapes, self.bed_width, self.bed_height,
            target_count=30, strategy="flashnestsheet", gap_mm=1.0
        )
        self.assertGreaterEqual(len(pieces), 20)

        polys = [transform_contour(p["contour"], p["x"], p["y"], p["rotation"]) for p in pieces]
        bboxes = [polygon_bbox(p) for p in polys]

        # Verify zero collision
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                self.assertFalse(
                    polygons_collide(polys[i], polys[j], gap=0.0, bbox_a=bboxes[i], bbox_b=bboxes[j]),
                    f"Colisao detectada entre peca {pieces[i]["id"]} e {pieces[j]["id"]}"
                )

        # Verify adjacent horizontal gap is ~1.0mm
        for i in range(min(5, len(polys) - 1)):
            if abs(pieces[i]["y"] - pieces[i+1]["y"]) < 5.0:
                dist = self._calc_min_dist(polys[i], polys[i+1])
                self.assertGreaterEqual(dist, 1.0, f"Gap violado: {dist:.3f} mm < 1.0 mm")
                self.assertLess(dist, 1.3, f"Gap excessivo: {dist:.3f} mm >= 1.3 mm")

    def test_session_gap_overrides_all_legacy_sources(self):
        legacy_dieproc_params = {
            "name": "TEST_LEGACY",
            "coupling": "PARALELO",
            "gap1": 0.5,
            "gap2": 0.5,
            "gap3": 0.5,
            "solutions": 10
        }
        for strat in ["sint", "flashnestsheet", "IA-teste"]:
            pieces = auto_nest_pieces(
                self.shapes, self.bed_width, self.bed_height,
                target_count=10, strategy=strat, gap_mm=2.5,
                dieproc_params=legacy_dieproc_params,
                db=self.db
            )
            self.assertGreater(len(pieces), 0, f"Nenhuma peça gerada para estratégia {strat}")
            polys = [transform_contour(p["contour"], p["x"], p["y"], p["rotation"]) for p in pieces]
            bboxes = [polygon_bbox(p) for p in polys]
            for i in range(len(polys)):
                for j in range(i + 1, len(polys)):
                    self.assertFalse(
                        polygons_collide(polys[i], polys[j], gap=0.0, bbox_a=bboxes[i], bbox_b=bboxes[j]),
                        f"Colisão detectada na estratégia {strat} entre {pieces[i]['id']} e {pieces[j]['id']}"
                    )
            # Verifica que a distância entre peças adjacentes respeita o gap_mm mestre (>= 2.5 mm)
            for i in range(min(4, len(polys) - 1)):
                for j in range(i + 1, min(len(polys), i + 3)):
                    dist = self._calc_min_dist(polys[i], polys[j])
                    self.assertGreaterEqual(dist, 2.49, f"Estratégia {strat} violou gap central de 2.5mm: {dist:.3f} mm < 2.5 mm (possível vazamento de gap1 legado de 0.5mm)")

    def test_plate_safety_margins_respected(self):
        """Valida que todos os motores respeitam rigorosamente as 4 margens da placa (Esquerda, Direita, Topo, De baixo)."""
        margins = {
            "left": 25.0,
            "right": 35.0,
            "top": 40.0,
            "bottom": 30.0
        }
        for strat in ["sint", "IA-teste"]:
            pieces = auto_nest_pieces(
                self.shapes, self.bed_width, self.bed_height,
                target_count=10, strategy=strat, gap_mm=1.0,
                margins=margins,
                db=self.db
            )
            self.assertGreater(len(pieces), 0, f"Nenhuma peça gerada para estratégia {strat}")
            for p in pieces:
                poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
                min_x, min_y, max_x, max_y = polygon_bbox(poly)
                self.assertGreaterEqual(
                    min_x, margins["left"] - 0.05,
                    f"Estratégia {strat}: Peça invadiu margem esquerda! min_x={min_x:.2f} < margin_left={margins['left']}"
                )
                self.assertLessEqual(
                    max_x, self.bed_width - margins["right"] + 0.05,
                    f"Estratégia {strat}: Peça invadiu margem direita! max_x={max_x:.2f} > limit={self.bed_width - margins['right']}"
                )
                self.assertGreaterEqual(
                    min_y, margins["bottom"] - 0.05,
                    f"Estratégia {strat}: Peça invadiu margem de baixo! min_y={min_y:.2f} < margin_bottom={margins['bottom']}"
                )
                self.assertLessEqual(
                    max_y, self.bed_height - margins["top"] + 0.05,
                    f"Estratégia {strat}: Peça invadiu margem do topo! max_y={max_y:.2f} > limit={self.bed_height - margins['top']}"
                )

        # Valida persistência das margens no banco de dados SQLite
        sess_id = self.db.create_session(
            name="Test Margins Session",
            margin_left=15.0,
            margin_right=20.0,
            margin_top=25.0,
            margin_bottom=30.0
        )
        loaded = self.db.get_session(sess_id)
        self.assertEqual(loaded["margin_left"], 15.0)
        self.assertEqual(loaded["margin_right"], 20.0)
        self.assertEqual(loaded["margin_top"], 25.0)
        self.assertEqual(loaded["margin_bottom"], 30.0)

        # Atualiza margens via update_session
        self.db.update_session(sess_id, margin_left=12.5, margin_right=18.5, margin_top=22.0, margin_bottom=28.0)
        reloaded = self.db.get_session(sess_id)
        self.assertEqual(reloaded["margin_left"], 12.5)
        self.assertEqual(reloaded["margin_right"], 18.5)
        self.assertEqual(reloaded["margin_top"], 22.0)
        self.assertEqual(reloaded["margin_bottom"], 28.0)

    def test_session_view_margin_radio_buttons(self):
        """Valida os botões de seleção de margem (10, 15, 20, 30 mm) na SessionView."""
        import tkinter as tk
        from ui.session_view import SessionView

        root = tk.Tk()
        root.withdraw()
        try:
            sess_id = self.db.create_session(name="Test Radio Session")
            sess_data = self.db.get_session(sess_id)
            view = SessionView(root, session_data=sess_data, db=self.db)

            # Padrão é 10.0 mm
            self.assertEqual(view.margin_choice_var.get(), "10.0")
            margins = view.get_margins()
            self.assertEqual(margins["left"], 10.0)
            self.assertEqual(margins["right"], 10.0)
            self.assertEqual(margins["top"], 10.0)
            self.assertEqual(margins["bottom"], 10.0)

            # Simula seleção de 15 mm
            view.margin_choice_var.set("15.0")
            view._on_margin_radio_selected()
            margins = view.get_margins()
            self.assertEqual(margins["left"], 15.0)
            self.assertEqual(margins["right"], 15.0)
            self.assertEqual(margins["top"], 15.0)
            self.assertEqual(margins["bottom"], 15.0)

            # Simula seleção de 30 mm
            view.margin_choice_var.set("30.0")
            view._on_margin_radio_selected()
            margins = view.get_margins()
            self.assertEqual(margins["left"], 30.0)
            self.assertEqual(margins["bottom"], 30.0)

            # Teste de set_margins sincronizando a variável do radio button
            view.set_margins(left=20.0, right=20.0, top=20.0, bottom=20.0)
            self.assertEqual(view.margin_choice_var.get(), "20.0")
        finally:
            root.destroy()

if __name__ == "__main__":
    unittest.main()


