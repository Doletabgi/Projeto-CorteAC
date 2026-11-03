"""
tests/test_nesting_compactness.py

Regressão do "encaixe com vãos" (Prompt 14): o motor de nesting recebia o campo
`params` composto da sessão (ex.: 'HighYield;separar_sobras=1;tip_mode=canto') e
comparava com o preset puro ('HighYield'), caindo no preset padrão e deixando
espaços enormes entre as peças. Também garante que `tip_zone`/`folga_ponta`
residuais de uma execução anterior não contaminem o novo encaixe.
"""

import math
import unittest

from cad.layers_split import separar_sobras_em_ponta
from cad.nesting_engine import auto_nest_pieces, nest_multi_sheet
from cad.geometry import polygon_bbox, transform_contour

GAP = 1.0
SHEET_W = 1000.0
SHEET_H = 2000.0
MARGINS = {"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0}

BOX = [
    {"x": 0.0, "y": 0.0},
    {"x": 80.0, "y": 0.0},
    {"x": 80.0, "y": 120.0},
    {"x": 0.0, "y": 120.0},
]


def _shape(idx, size, pairs):
    return {
        "id": idx,
        "name": f"MOLDE_{size}",
        "size": size,
        "sequence": idx,
        "pairs": pairs,
        "contour": [dict(p) for p in BOX],
    }


def _poly(p):
    return transform_contour(p["contour"], p["x"], p["y"], p.get("rotation", 0))


def _min_gap(pieces):
    """Menor distância contorno-a-contorno entre duas peças da placa (mm)."""
    if len(pieces) < 2:
        return float("inf")
    polys = [_poly(p) for p in pieces]
    bbs = [polygon_bbox(q) for q in polys]
    melhor = float("inf")
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            a, b = bbs[i], bbs[j]
            if a[2] + 50 < b[0] or b[2] + 50 < a[0] or a[3] + 50 < b[1] or b[3] + 50 < a[1]:
                continue
            for pt in polys[i]:
                for k in range(len(polys[j])):
                    q1, q2 = polys[j][k], polys[j][(k + 1) % len(polys[j])]
                    dx, dy = q2["x"] - q1["x"], q2["y"] - q1["y"]
                    if dx == 0 and dy == 0:
                        d = math.hypot(pt["x"] - q1["x"], pt["y"] - q1["y"])
                    else:
                        t = ((pt["x"] - q1["x"]) * dx + (pt["y"] - q1["y"]) * dy) / (dx * dx + dy * dy)
                        t = max(0.0, min(1.0, t))
                        d = math.hypot(pt["x"] - (q1["x"] + t * dx), pt["y"] - (q1["y"] + t * dy))
                    if d < melhor:
                        melhor = d
    return melhor


class TestNestingCompactness(unittest.TestCase):
    def test_params_compostos_produzem_o_mesmo_encaixe_do_preset_puro(self):
        """'HighYield;separar_sobras=1;tip_mode=canto' deve encaixar como 'HighYield'."""
        shapes = [_shape(i + 1, f"{30 + i}a", 20) for i in range(3)]

        def run(params):
            return auto_nest_pieces(
                available_shapes=[dict(s) for s in shapes],
                bed_width_mm=SHEET_W, bed_height_mm=SHEET_H, target_count=30,
                strategy="flashnestsheet", params=params, gap_mm=GAP,
                margins=MARGINS, layers=4,
            )

        puro = run("HighYield")
        composto = run("HighYield;separar_sobras=1;tip_mode=canto;folga_ponta=15")

        self.assertEqual(len(puro), len(composto))
        self.assertGreater(len(composto), 0)
        # O bug antigo caía no preset padrão e deixava vãos grandes; ambos devem
        # ficar compactos (encostados no gap de 1 mm)
        self.assertLessEqual(_min_gap(puro), GAP * 1.5)
        self.assertLessEqual(_min_gap(composto), GAP * 1.5)

    def test_tip_zone_nos_shapes_nao_altera_o_encaixe(self):
        """Zonas de ponta residuais nos moldes não podem virar margem do encaixe."""
        limpos = [_shape(i + 1, f"{30 + i}a", 12) for i in range(3)]
        sujos = []
        for s in limpos:
            d = dict(s)
            d["tip_zone"] = [0.0, 1500.0, SHEET_W, SHEET_H]
            d["layers_tip"] = 2
            d["target_pieces"] = 1
            sujos.append(d)

        def run(shapes):
            r = nest_multi_sheet(
                available_shapes=[dict(s) for s in shapes],
                bed_width_mm=SHEET_W, bed_height_mm=SHEET_H,
                strategy="flashnestsheet", params="HighYield;separar_sobras=1",
                gap_mm=GAP, margins=MARGINS, layers=4, max_total_sec=20,
            )
            return r

        a = run(limpos)
        b = run(sujos)
        self.assertEqual(a["total_pieces"], b["total_pieces"])
        self.assertEqual(a["num_sheets"], b["num_sheets"])
        for ly_a, ly_b in zip(a["layouts"], b["layouts"]):
            pos_a = [(round(p["x"], 1), round(p["y"], 1)) for p in ly_a["pieces"]]
            pos_b = [(round(p["x"], 1), round(p["y"], 1)) for p in ly_b["pieces"]]
            self.assertEqual(pos_a, pos_b, "tip_zone nos moldes alterou o encaixe")

    def test_sobras_na_ponta_mantem_base_compacta(self):
        """Após mover as sobras para a ponta, a base continua sem vãos colossais."""
        shapes = [_shape(i + 1, f"{30 + i}a", 11) for i in range(3)]  # 11 pares (ímpar)
        res = nest_multi_sheet(
            available_shapes=[dict(s) for s in shapes],
            bed_width_mm=SHEET_W, bed_height_mm=SHEET_H,
            strategy="flashnestsheet", params="HighYield;separar_sobras=1;tip_mode=faixa",
            gap_mm=GAP, margins=MARGINS, layers=4, max_total_sec=30,
        )
        self.assertTrue(res["success"], res.get("warning"))

        layouts, msg = separar_sobras_em_ponta(
            res["layouts"],
            session={"id": 1, "layers": 4, "params": "HighYield;separar_sobras=1"},
            shapes=[dict(s) for s in shapes],
            params="HighYield;separar_sobras=1;tip_mode=faixa",
            sheet_w=SHEET_W, sheet_h=SHEET_H,
            material={"layers": 4, "gap_mm": GAP, "width_mm": SHEET_W, "height_mm": SHEET_H},
        )
        self.assertTrue(any(ly.get("tip_zone") for ly in layouts), f"sem ponta: {msg}")

        for ly in layouts:
            pieces = ly.get("pieces") or []
            if len(pieces) < 2:
                continue
            # base (4 camadas) e ponta (2 camadas) ficam na mesma placa; separadas
            # pelo tip_zone, então medimos por grupo
            base = [p for p in pieces if not _inside_tip(p, ly)]
            ponta = [p for p in pieces if _inside_tip(p, ly)]
            if len(base) >= 2:
                self.assertLessEqual(_min_gap(base), GAP * 2.0,
                                     "base ficou com vão entre peças após a separação")
            if len(ponta) >= 2:
                self.assertLessEqual(_min_gap(ponta), GAP * 2.0,
                                     "ponta ficou com vão entre peças")

    def test_rodar_novamente_nao_degrada_o_encaixe(self):
        """Gerar duas vezes (como 'Gerar' + 'Refazer') não pode abrir vãos na segunda."""
        shapes = [_shape(i + 1, f"{30 + i}a", 20) for i in range(3)]

        def run():
            return nest_multi_sheet(
                available_shapes=[dict(s) for s in shapes],
                bed_width_mm=SHEET_W, bed_height_mm=SHEET_H,
                strategy="flashnestsheet", params="HighYield;separar_sobras=1",
                gap_mm=GAP, margins=MARGINS, layers=4, max_total_sec=20,
            )

        a, b = run(), run()
        self.assertEqual(a["total_pieces"], b["total_pieces"])
        self.assertAlmostEqual(
            sum(a["yields"]) / max(1, len(a["yields"])),
            sum(b["yields"]) / max(1, len(b["yields"])),
            places=6,
            msg="segundo cálculo mudou o rendimento (vazamento de estado)",
        )
        for ly in b["layouts"]:
            if len(ly["pieces"]) >= 2:
                self.assertLessEqual(_min_gap(ly["pieces"]), GAP * 1.5)


def _inside_tip(piece, layout):
    tz = layout.get("tip_zone")
    if not tz:
        return False
    x0, y0, x1, y1 = tz
    bb = polygon_bbox(_poly(piece))
    cx = (bb[0] + bb[2]) / 2.0
    cy = (bb[1] + bb[3]) / 2.0
    return min(x0, x1) <= cx <= max(x0, x1) and min(y0, y1) <= cy <= max(y0, y1)


if __name__ == "__main__":
    unittest.main()
