"""
tests/test_sobras_dobra.py

Regra da DOBRA (confirmada pelo operador): cada peça retirada das 4 camadas vira
DUAS na ponta de 2 camadas (4 físicas = 2 pares  <->  2 x 2 camadas = 4 físicas).
A divisão é escolhida automaticamente pela menor altura consumida.
"""

import unittest

from cad.layers_split import _escolher_divisao_otima, separar_sobras_em_ponta
from cad.trim_engine import calculate_layout_trim_bounds

BOX = [
    {"x": 0.0, "y": 0.0},
    {"x": 90.0, "y": 0.0},
    {"x": 90.0, "y": 200.0},
    {"x": 0.0, "y": 200.0},
]

SHEET_W, SHEET_H = 1200.0, 2400.0
MARG = {"left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0}
GAP = 1.0


def _shape(idx, pairs):
    return {
        "id": idx, "name": f"Molde_{idx}", "size": f"{30 + idx}a",
        "sequence": idx, "pairs": pairs, "contour": [dict(p) for p in BOX],
    }


def _layout(pieces_por_molde, shapes):
    pieces = []
    pid = 1
    for i, shp in enumerate(shapes):
        for c in range(pieces_por_molde):
            pieces.append({
                "id": pid, "name": shp["name"], "size": shp["size"], "color": "#3b82f6",
                "contour": [dict(p) for p in BOX], "shape": dict(shp),
                "x": 20 + (c % 6) * 95.0, "y": 20 + (c // 6) * 210.0 * 1.0 + i * 210.0,
                "rotation": 0.0,
            })
            pid += 1
    return [{
        "layout_index": 0, "name": "lay0000", "layers": 4,
        "width_mm": SHEET_W, "height_mm": SHEET_H,
        "margin_left": 10.0, "margin_right": 10.0, "margin_top": 10.0, "margin_bottom": 10.0,
        "pieces": pieces,
    }]


class TestSobrasDobra(unittest.TestCase):
    def setUp(self):
        self.session = {"id": 1, "layers": 4, "gap_mm": 1.0,
                        "params": "HighYield;separar_sobras=1;tip_mode=faixa"}
        self.material = {"layers": 4, "gap_mm": 1.0, "width_mm": SHEET_W, "height_mm": SHEET_H}

    def _run(self, k=None, pares=11, n_moldes=3, pecas=6):
        shapes = [_shape(i + 1, pares) for i in range(n_moldes)]
        layouts = _layout(pecas, shapes)
        kw = dict(session=self.session, shapes=shapes,
                  params="HighYield;separar_sobras=1;tip_mode=faixa",
                  sheet_w=SHEET_W, sheet_h=SHEET_H, material=self.material)
        if k is None:
            return separar_sobras_em_ponta(layouts, **kw)
        return separar_sobras_em_ponta(layouts, _k=k, **kw)

    def _contagens(self, layouts):
        n4 = sum(1 for ly in layouts for p in ly["pieces"] if int(p.get("layers") or 4) != 2)
        n2 = sum(1 for ly in layouts for p in ly["pieces"] if int(p.get("layers") or 4) == 2)
        fis = sum(int(p.get("layers") or 4) for ly in layouts for p in ly["pieces"])
        return n4, n2, fis

    def test_dobra_preserva_pecas_fisicas(self):
        """Qualquer k mantém 4*N4 + 2*N2 = 2P (sem cortar a mais)."""
        pares, moldes = 11, 3
        esperado = pares * 2 * moldes
        for k in (0, 1, 2):
            layouts, msg = self._run(k=k, pares=pares, n_moldes=moldes)
            n4, n2, fis = self._contagens(layouts)
            self.assertEqual(fis, esperado, f"k={k}: físicas {fis} != {esperado}")
            self.assertGreater(n4, 0)
            self.assertGreater(n2, 0)

    def test_dobra_cria_peca_duplicada_na_ponta(self):
        """k=1 remove 2 peças da base e coloca 3 na ponta (2 movidas + 1 dobrada)."""
        layouts, msg = self._run(k=1)
        n4, n2, fis = self._contagens(layouts)
        # 3 moldes: base 4 peças cada = 12; ponta 3 cada = 9
        self.assertEqual(n4, 12)
        self.assertEqual(n2, 9)
        duplicadas = sum(1 for ly in layouts for p in ly["pieces"] if p.get("is_duplicate"))
        self.assertEqual(duplicadas, 3)

    def test_divisao_automatica_escolhe_menor_altura(self):
        """A escolha automática não pode ser pior que qualquer k testado."""
        shapes = [_shape(i + 1, 11) for i in range(3)]
        layouts = _layout(6, shapes)
        kw = dict(session=self.session, shapes=shapes,
                  params="HighYield;separar_sobras=1;tip_mode=faixa",
                  sheet_w=SHEET_W, sheet_h=SHEET_H, material=self.material)

        alturas = {}
        for k in (0, 1, 2):
            res, _ = separar_sobras_em_ponta([dict(l) for l in layouts], _k=k, **kw)
            alturas[k] = sum(calculate_layout_trim_bounds(ly["pieces"], gap_mm=1.0)[1] for ly in res)

        auto, msg = _escolher_divisao_otima([dict(l) for l in layouts], **kw)
        alt_auto = sum(calculate_layout_trim_bounds(ly["pieces"], gap_mm=1.0)[1] for ly in auto)
        self.assertLessEqual(alt_auto, min(alturas.values()) + 0.5,
                             f"automático pior que o melhor k fixo: {alt_auto} vs {alturas}")

    def test_dobra_nao_penetra_contorno(self):
        """As peças dobradas respeitam o gap (sem colisão)."""
        from cad.geometry import polygon_bbox, polygons_collide, transform_contour
        layouts, msg = self._run(k=1)
        for ly in layouts:
            polys = [transform_contour(p["contour"], p["x"], p["y"], p.get("rotation", 0)) for p in ly["pieces"]]
            bbs = [polygon_bbox(q) for q in polys]
            for i in range(len(polys)):
                for j in range(i + 1, len(polys)):
                    a, b = bbs[i], bbs[j]
                    if a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]:
                        continue
                    self.assertFalse(polygons_collide(polys[i], polys[j], gap=0.0, bbox_a=a, bbox_b=b),
                                     f"colisão entre peças {i} e {j} após a dobra")



class TestRecompactacaoBase(unittest.TestCase):
    """A retirada da peça ímpar não pode deixar buraco na placa de 4 camadas."""

    @staticmethod
    def _buracos(ly, gap=1.0):
        """Conta vãos horizontais maiores que 3x o gap dentro da mesma linha."""
        from cad.geometry import polygon_bbox, transform_contour
        linhas = {}
        for p in ly["pieces"]:
            bb = polygon_bbox(transform_contour(p["contour"], p["x"], p["y"], p.get("rotation", 0)))
            linhas.setdefault(round(bb[1] / 5) * 5, []).append((bb[0], bb[2]))
        total = 0
        for v in linhas.values():
            v.sort()
            total += sum(1 for a, b in zip(v, v[1:]) if b[0] - a[1] > 3 * gap)
        return total

    def _cenario(self, pares=21, moldes=3):
        from cad.layers_split import separar_sobras_em_ponta
        from cad.nesting_engine import nest_multi_sheet

        shapes = [_shape(i + 1, pares) for i in range(moldes)]
        res = nest_multi_sheet(
            available_shapes=[dict(s) for s in shapes],
            bed_width_mm=SHEET_W, bed_height_mm=SHEET_H,
            strategy="flashnestsheet", params="HighYield;separar_sobras=1;tip_mode=faixa",
            gap_mm=GAP, margins=MARG, layers=4, max_total_sec=30,
        )
        self.assertTrue(res["success"], res.get("warning"))
        antes = [sum(1 for _ in ly["pieces"]) for ly in res["layouts"]]
        out, msg = separar_sobras_em_ponta(
            res["layouts"],
            session={"id": 1, "layers": 4, "gap_mm": GAP, "params": "HighYield;separar_sobras=1"},
            shapes=shapes, params="HighYield;separar_sobras=1",
            sheet_w=SHEET_W, sheet_h=SHEET_H,
            material={"layers": 4, "gap_mm": GAP, "width_mm": SHEET_W, "height_mm": SHEET_H},
        )
        return out, antes, pares, moldes

    def test_base_sem_buracos_apos_separar_sobras(self):
        out, antes, pares, moldes = self._cenario()
        total_buracos = sum(self._buracos(ly) for ly in out)
        self.assertEqual(total_buracos, 0, f"ficaram {total_buracos} vãos na base: {[self._buracos(l) for l in out]}")

    def test_pecas_fisicas_preservadas_apos_recompactar(self):
        out, antes, pares, moldes = self._cenario()
        fis = sum(int(p.get("layers") or 4) for ly in out for p in ly["pieces"])
        self.assertEqual(fis, 2 * pares * moldes)

    def test_altura_nao_cresce_ao_recompactar(self):
        from cad.trim_engine import calculate_layout_trim_bounds
        out, antes, pares, moldes = self._cenario()
        altura = max(calculate_layout_trim_bounds(ly["pieces"], gap_mm=GAP)[1] for ly in out)
        self.assertLessEqual(altura, SHEET_H)


if __name__ == "__main__":
    unittest.main()
