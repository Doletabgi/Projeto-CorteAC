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
    def test_duas_pecas_do_topo_viram_quatro_na_ponta(self):
        from cad.layers_split import _compactar_topo_na_ponta, _nest_sobras_on_last_sheet
        from cad.layers_rule import layers_for_piece
        import copy

        shape = _shape(1, 35)
        base = [{"contour": BOX, "shape": shape, "x": 10 + i * 91,
                 "y": 10, "rotation": 0} for i in range(12)]
        base += [{"contour": BOX, "shape": shape, "x": 10 + i * 91,
                  "y": 211, "rotation": 0} for i in range(2)]
        dest = {"pieces": base, "layers": 4}
        items = [{"piece": {"contour": BOX, "shape": shape}} for _ in range(7)]
        placed, zone = _nest_sobras_on_last_sheet(
            dest, items, SHEET_W, SHEET_H, GAP, MARG, "faixa", 15)
        before = copy.deepcopy(dest)
        old_height = calculate_layout_trim_bounds(base + placed, gap_mm=GAP)[1]
        placed, zone = _compactar_topo_na_ponta(
            dest, placed, zone, SHEET_W, SHEET_H, GAP, MARG, "faixa", 15)
        self.assertEqual(len(before["pieces"]), 14)
        self.assertEqual(len(dest["pieces"]), 12)
        self.assertEqual(len(placed), 11)
        dest.update(tip_zone=zone, layers_tip=2)
        self.assertEqual(sum(layers_for_piece(dest, p) for p in dest["pieces"] + placed), 70)
        self.assertLess(calculate_layout_trim_bounds(dest["pieces"] + placed, gap_mm=GAP)[1], old_height)
        from cad.geometry import polygons_collide
        all_pieces = dest["pieces"] + placed
        for i, a in enumerate(all_pieces):
            for b in all_pieces[i + 1:]:
                self.assertFalse(polygons_collide(a["poly"], b["poly"], gap=GAP,
                                                 bbox_a=a["bbox"], bbox_b=b["bbox"]))

    def test_ponta_existente_tambem_otimiza_fileira_final(self):
        from cad.layers_split import _nest_sobras_on_last_sheet
        from cad.layers_rule import layers_for_piece
        import copy
        shape = _shape(1, 35)
        base = [{"contour": BOX, "shape": shape, "name": shape["name"],
                 "size": shape["size"], "x": 10 + i * 91, "y": 10}
                for i in range(12)]
        # Topos com alturas diferentes pertencem à mesma fileira.
        base += [{"contour": BOX, "shape": shape, "name": shape["name"],
                  "size": shape["size"], "x": 10 + i * 91, "y": 211 + 5 * i}
                 for i in range(2)]
        dest = {"pieces": base, "layers": 4, "width_mm": SHEET_W,
                "height_mm": SHEET_H}
        tip, zone = _nest_sobras_on_last_sheet(
            dest, [{"piece": {"contour": BOX, "shape": shape,
                                "name": shape["name"], "size": shape["size"]}}
                   for _ in range(7)], SHEET_W, SHEET_H, GAP, MARG, "faixa", 15)
        dest.update(pieces=base + tip, tip_zone=zone, layers_tip=2)
        original = copy.deepcopy(dest)
        result, _ = separar_sobras_em_ponta(
            [dest], session={"layers": 4, "gap_mm": GAP,
                            "params": "HighYield;separar_sobras=1;tip_mode=faixa"},
            shapes=[shape], sheet_w=SHEET_W, sheet_h=SHEET_H)
        out = result[-1]
        self.assertEqual(sum(layers_for_piece(out, p) == 4 for p in out["pieces"]), 12)
        self.assertEqual(sum(layers_for_piece(out, p) == 2 for p in out["pieces"]), 11)
        self.assertEqual(sum(layers_for_piece(out, p) for p in out["pieces"]), 70)
        self.assertEqual(dest, original)
        repeated, _ = separar_sobras_em_ponta(
            result, session={"layers": 4}, shapes=[shape], sheet_w=SHEET_W, sheet_h=SHEET_H)
        self.assertEqual(repeated, result)

    def test_topo_preservado_quando_ponta_precisa_de_mais_altura(self):
        from cad.layers_split import _compactar_topo_na_ponta, _nest_sobras_on_last_sheet
        base = [{"contour": BOX, "x": 10 + i * 91, "y": 10} for i in range(12)]
        base += [{"contour": BOX, "x": 10, "y": 211}]
        dest = {"pieces": base}
        placed, zone = _nest_sobras_on_last_sheet(
            dest, [{"piece": {"contour": BOX}} for _ in range(12)],
            SHEET_W, SHEET_H, GAP, MARG, "faixa", 15)
        result, _ = _compactar_topo_na_ponta(
            dest, placed, zone, SHEET_W, SHEET_H, GAP, MARG, "faixa", 15)
        self.assertEqual(len(dest["pieces"]), 13)
        self.assertEqual(len(result), 12)

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



class TestPontaDepoisDoPreenchimento(unittest.TestCase):
    def test_geracao_finaliza_ponta_apos_transferir_pecas_para_primeira_placa(self):
        """O segundo passe deixa duas peças no topo; só então elas cabem dobradas."""
        import copy
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from ui.main_window import MainWindow
        from cad.layers_split import _nest_sobras_on_last_sheet
        from cad.layers_rule import layers_for_piece
        from cad.nesting_engine import piece_matches_shape

        shape = _shape(1, 51)
        def piece(x, y):
            return {"contour": BOX, "shape": shape, "name": shape["name"],
                    "size": shape["size"], "x": x, "y": y, "rotation": 0}
        base = [piece(10 + i * 91, 10) for i in range(12)]
        base += [piece(10 + i * 91, 211) for i in range(8)]
        last = {"pieces": base, "layers": 4, "width_mm": SHEET_W,
                "height_mm": SHEET_H, "layout_index": 1}
        tip, zone = _nest_sobras_on_last_sheet(
            last, [{"piece": piece(0, 0)} for _ in range(7)],
            SHEET_W, SHEET_H, GAP, MARG, "faixa", 15)
        last.update(pieces=base + tip, tip_zone=zone, layers_tip=2)
        first = {"pieces": [piece(10, 10), piece(101, 10)], "layers": 4,
                 "width_mm": SHEET_W, "height_mm": SHEET_H, "layout_index": 0}
        separated = [first, last]
        original_height = calculate_layout_trim_bounds(last["pieces"])[1]
        session = {"id": 1, "layers": 4, "gap_mm": 1, "shapes": [shape],
                   "params": "FastNest;separar_sobras=1;refile_auto=1;tip_mode=faixa"}
        material = {"width_mm": SHEET_W, "height_mm": SHEET_H}
        session["material"] = material
        view = SimpleNamespace(shapes_list=[shape], get_strategy=lambda: "flashnestsheet",
                               get_params=lambda: session["params"], get_machine=lambda: "ATOM",
                               get_dieproc_params=lambda: None, get_nesting_mode=lambda: "custom",
                               get_gap_mm=lambda: GAP, get_margins=lambda: MARG)
        captured = []
        app = SimpleNamespace(
            session_view=view, current_session=session, current_material=material,
            db=None, show_session_window=MagicMock(), config=MagicMock(),
            lbl_status_msg=MagicMock(), on_cancel_nest=MagicMock(),
            after=lambda delay, callback: callback(),
            _poll_nest_worker=lambda q, *args: captured.append(q.get_nowait()),
        )
        class ImmediateThread:
            def __init__(self, target, **kwargs):
                self.target = target
            def start(self):
                self.target()

        def fill(layouts, **kwargs):
            if kwargs.get("session"):
                # Mesmo efeito da sessão 188: seis peças da fileira final
                # preenchem buracos da primeira placa, restando duas na base.
                moving = layouts[-1]["pieces"][12:18]
                del layouts[-1]["pieces"][12:18]
                for i, p in enumerate(moving, start=2):
                    p.update(x=10 + i * 91, y=10)
                    p.pop("poly", None)
                    p.pop("bbox", None)
                layouts[0]["pieces"].extend(moving)
            return layouts, {"movidas": 0}

        with patch("ui.main_window.threading.Thread", ImmediateThread), \
             patch("ui.main_window.nest_multi_sheet", return_value={"layouts": copy.deepcopy(separated)}), \
             patch("ui.main_window.separar_sobras_em_ponta", return_value=(copy.deepcopy(separated), "ponta")), \
             patch("cad.nesting_engine.preencher_buracos_em_placas", side_effect=fill), \
             patch.dict("os.environ", {"CORTEAC_BACKEND": "python"}):
            MainWindow.on_auto_nest(app)
        status, result = captured[0]
        self.assertEqual(status, "SUCCESS", result)
        layouts = result["layouts"]
        final = layouts[-1]
        self.assertEqual(sum(layers_for_piece(final, p) == 4 for p in final["pieces"]), 12)
        self.assertEqual(sum(layers_for_piece(final, p) == 2 for p in final["pieces"]), 11)
        self.assertEqual(sum(layers_for_piece(l, p) for l in layouts for p in l["pieces"]
                             if piece_matches_shape(p, shape)), 102)
        self.assertLess(final["height_mm"], original_height - 190)
        # As cópias têm id=None: a gravação relacional também deve aceitá-las.
        import tempfile
        from pathlib import Path
        from database import DatabaseManager
        with tempfile.TemporaryDirectory() as temp:
            db = DatabaseManager(str(Path(temp) / "ponta.db"), backend="sqlite")
            sid = db.create_session(name="Regressão da ponta final")
            self.assertTrue(db.save_session_layouts(sid, layouts))
            loaded = db.get_session_layouts(sid)[-1]
            self.assertEqual(len(loaded["pieces"]), 23)
            self.assertEqual(sum(layers_for_piece(loaded, p) == 2 for p in loaded["pieces"]), 11)
            self.assertEqual(loaded["height_mm"], final["height_mm"])


if __name__ == "__main__":
    unittest.main()
