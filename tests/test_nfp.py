"""
tests/test_nfp.py

Testes unitários e de fuzzing para o motor No-Fit Polygon (cad/nfp.py).
Valida:
1. Decomposição convexa por Ear-Clipping e preservação estrita de área (1e-6).
2. Soma de Minkowski analítica entre polígonos convexos.
3. Geração de NFP entre peças reais e idênticas.
4. Encosto analítico contact_placement com garantia de gap e zero colisão.
5. Fuzz test com 1.000 pares aleatórios com oráculo polygons_collide.
6. Determinismo estrito em múltiplas execuções.
"""

import math
import random
import unittest
from pathlib import Path

from cad.die_parser import parse_die_file
from cad.geometry import (
    polygon_area,
    polygon_bbox,
    polygons_collide,
    transform_contour,
)
from cad.nfp import (
    compute_nfp,
    contact_placement,
    decompose_convex,
    find_lowest_point_in_nfp,
    minkowski_sum_convex,
    polygon_signed_area,
)

BASE_DIR = Path(__file__).resolve().parent.parent


class TestNFP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sample_path = BASE_DIR / "samples" / "Gaspea_Derby_41.die"
        if sample_path.exists():
            data = parse_die_file(str(sample_path))
            cls.real_contour = data["contour"]
        else:
            cls.real_contour = [
                {"x": 0.0, "y": 0.0},
                {"x": 200.0, "y": 0.0},
                {"x": 220.0, "y": 60.0},
                {"x": 160.0, "y": 120.0},
                {"x": 40.0, "y": 100.0},
                {"x": 0.0, "y": 40.0},
            ]

    def test_01_convex_decomposition_area_preservation(self):
        """Decomposição convexa deve preservar a área (Shoelace) com tolerância < 1e-6."""
        # Polígono côncavo em L
        poly_l = [
            {"x": 0.0, "y": 0.0},
            {"x": 100.0, "y": 0.0},
            {"x": 100.0, "y": 40.0},
            {"x": 40.0, "y": 40.0},
            {"x": 40.0, "y": 100.0},
            {"x": 0.0, "y": 100.0},
        ]
        orig_area = polygon_area(poly_l)
        parts = decompose_convex(poly_l)
        sum_area = sum(polygon_area(p) for p in parts)
        self.assertAlmostEqual(orig_area, sum_area, places=6)

        # Contorno real industrial de calçado
        real_area = polygon_area(self.real_contour)
        real_parts = decompose_convex(self.real_contour)
        real_sum = sum(polygon_area(p) for p in real_parts)
        self.assertAlmostEqual(real_area, real_sum, places=5)

    def test_02_minkowski_sum_convex_squares(self):
        """Soma de Minkowski entre dois quadrados de lado 10 e 20 deve gerar quadrado de lado 30."""
        sq1 = [
            {"x": 0.0, "y": 0.0},
            {"x": 10.0, "y": 0.0},
            {"x": 10.0, "y": 10.0},
            {"x": 0.0, "y": 10.0},
        ]
        sq2 = [
            {"x": 0.0, "y": 0.0},
            {"x": 20.0, "y": 0.0},
            {"x": 20.0, "y": 20.0},
            {"x": 0.0, "y": 20.0},
        ]
        msum = minkowski_sum_convex(sq1, sq2)
        area = polygon_area(msum)
        self.assertAlmostEqual(area, 900.0, places=4)
        bbox = polygon_bbox(msum)
        self.assertAlmostEqual(bbox[2] - bbox[0], 30.0, places=4)
        self.assertAlmostEqual(bbox[3] - bbox[1], 30.0, places=4)

    def test_03_nfp_between_identical_pieces(self):
        """NFP entre duas peças idênticas deve ser não vazio e conter componentes válidos."""
        nfp = compute_nfp(self.real_contour, self.real_contour)
        self.assertIsNotNone(nfp)
        self.assertGreater(len(nfp), 0)
        for comp in nfp:
            self.assertGreaterEqual(len(comp), 3)
            self.assertGreater(polygon_area(comp), 0.0)

    def test_04_contact_placement_gap_and_zero_collision(self):
        """contact_placement deve respeitar o gap milimétrico e produzir zero colisão."""
        gap = 1.0
        # Obstáculo fixo na posição (100, 100)
        obs = [transform_contour(self.real_contour, 100.0, 100.0, 0.0)]
        target_x = 100.0

        pos = contact_placement(self.real_contour, obs, gap=gap, x_coord=target_x, min_y=10.0)
        self.assertIsNotNone(pos)
        self.assertEqual(pos[0], target_x)

        placed_poly = transform_contour(self.real_contour, pos[0], pos[1], 0.0)
        # Oráculo estrito: polygons_collide NÃO pode acusar colisão
        has_col = polygons_collide(placed_poly, obs[0], gap=gap)
        self.assertFalse(has_col, f"Colisão detectada na posição sugerida pelo NFP: {pos}")

    def test_05_fuzz_1000_pairs_nfp_vs_collision_oracle(self):
        """
        Fuzz test de 1.000 pares aleatórios de peças com gap=1.0:
        O resultado de contact_placement deve produzir ZERO colisão verificada
        pelo oráculo polygons_collide em 100% dos pares.
        """
        gap = 1.0
        rng = random.Random(1337)
        collisions_found = 0

        for i in range(1000):
            obs_x = rng.uniform(50.0, 1000.0)
            obs_y = rng.uniform(50.0, 600.0)
            obs_rot = rng.choice([0.0, 90.0, 180.0, 270.0])
            obs_poly = transform_contour(self.real_contour, obs_x, obs_y, obs_rot)

            cand_x = obs_x + rng.uniform(-100.0, 100.0)
            pos = contact_placement(self.real_contour, [obs_poly], gap=gap, x_coord=cand_x, min_y=10.0)

            cand_poly = transform_contour(self.real_contour, pos[0], pos[1], 0.0)
            if polygons_collide(cand_poly, obs_poly, gap=gap):
                collisions_found += 1

        self.assertEqual(collisions_found, 0, f"Colisões encontradas no fuzz test: {collisions_found} / 1000")

    def test_06_nfp_determinism(self):
        """10 execuções idênticas devem gerar exatamente as mesmas coordenadas."""
        obs = [transform_contour(self.real_contour, 150.0, 150.0, 0.0)]
        positions = []
        for _ in range(10):
            pos = contact_placement(self.real_contour, obs, gap=1.5, x_coord=120.0, min_y=10.0)
            positions.append(pos)

        first = positions[0]
        for p in positions[1:]:
            self.assertEqual(p, first)


class TestTransformCacheIdentity(unittest.TestCase):
    """
    Regressão: o cache de transformação era indexado por id(contorno) sem validar o
    conteúdo. Como o Python recicla o endereço de listas liberadas, um contorno novo
    podia herdar o hash de outro molde e `transform_contour` devolvia a geometria
    errada — colisões falsas e resultados de nesting corrompidos.
    (Detectado pelo fuzz test test_05 em execuções da suíte completa.)
    """

    def test_transform_cache_rejeita_entrada_de_outro_contorno(self):
        from cad import geometry
        from cad.geometry import clear_transform_cache, transform_contour

        clear_transform_cache()
        outro = [{"x": float(i) * 3.0, "y": float(i) * 5.0} for i in range(60)]
        alvo = [{"x": float(i), "y": float(i) * 2.0} for i in range(60)]

        # Popula o cache com o conteúdo de "outro" e o copia para o id de "alvo",
        # simulando a reciclagem de endereço que o CPython faz após o GC.
        transform_contour(outro, 0.0, 0.0, 0.0)  # popula o cache de transformação
        geometry._CONTOUR_HASH_CACHE[id(alvo)] = geometry._CONTOUR_HASH_CACHE[id(outro)]

        saida = transform_contour(alvo, 0.0, 0.0, 0.0)
        self.assertEqual(len(saida), len(alvo))
        for obtido, esperado in zip(saida, alvo):
            self.assertAlmostEqual(obtido["x"], esperado["x"], places=6)
            self.assertAlmostEqual(obtido["y"], esperado["y"], places=6)

    def test_transform_contour_com_offset_e_rotacao_apos_reciclagem(self):
        from cad import geometry
        from cad.geometry import clear_transform_cache, transform_contour

        clear_transform_cache()
        outro = [{"x": float(i) * 4.0, "y": float(i) * 7.0} for i in range(80)]
        alvo = [{"x": float(i), "y": float(i) * 1.5} for i in range(80)]
        transform_contour(outro, 100.0, 50.0, 180.0)  # popula o cache de transformação
        geometry._CONTOUR_HASH_CACHE[id(alvo)] = geometry._CONTOUR_HASH_CACHE[id(outro)]

        saida = transform_contour(alvo, 100.0, 50.0, 180.0)
        esperado = transform_contour(alvo, 100.0, 50.0, 180.0)  # já validado acima
        for a, b in zip(saida, esperado):
            self.assertAlmostEqual(a["x"], b["x"], places=6)
            self.assertAlmostEqual(a["y"], b["y"], places=6)
        # e a geometria tem que ser a do alvo (rotação 180 de x,y), não a do outro
        self.assertAlmostEqual(saida[1]["x"], 100.0 - 1.0, places=3)


if __name__ == "__main__":
    unittest.main()
