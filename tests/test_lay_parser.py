"""
Testes Unitários para o Parser e Gerador de Arquivos .lay (ATOM $$LAYOUT.v3$$)
Compatível com fn98.exe, dp98.exe e mesas CNC ATOM.
"""

import os
import sys
import unittest
import tempfile
import math

# Adiciona o diretório raiz ao sys.path para importação
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from cad.lay_parser import (
    parse_lay,
    generate_lay_content,
    export_layout_from_pieces,
    validate_layout_placement,
    LayoutData,
    TargetDie,
    PlacedItem,
    QualityZone
)
from cad.die_parser import parse_die_file
from database import DatabaseManager

SAMPLES_DIR = os.path.join(PROJECT_ROOT, "samples", "lay")


class TestLayParser(unittest.TestCase):

    def setUp(self):
        self.sample_files = [
            os.path.join(SAMPLES_DIR, f) for f in os.listdir(SAMPLES_DIR) if f.endswith(".lay")
        ]
        self.sample_files.sort()

    def test_samples_exist(self):
        """Verifica se as amostras reais foram encontradas."""
        self.assertGreaterEqual(len(self.sample_files), 5, "Devem existir ao menos 5 amostras .lay em samples/lay")

    def test_parse_real_samples(self):
        """Testa o parsing em todas as amostras reais de produção ATOM."""
        for s_path in self.sample_files:
            with self.subTest(sample=os.path.basename(s_path)):
                lay = parse_lay(s_path)
                self.assertEqual(lay.version, "$$LAYOUT.v3$$", f"Versão incorreta em {s_path}")
                self.assertGreater(lay.ris_w, 0.0, "Largura da chapa deve ser maior que zero")
                self.assertGreater(lay.ris_l, 0.0, "Comprimento da chapa deve ser maior que zero")
                self.assertEqual(len(lay.target_dies), lay.no_dies, "Contagem de matrizes (TG) deve bater com no_dies")
                self.assertEqual(len(lay.items), lay.num_of_items, "Contagem de itens (I) deve bater com num_of_items")
                self.assertGreater(len(lay.items), 0, "Layout de amostra deve conter peças posicionadas")

                # Verifica se cada peça tem dados válidos
                for it in lay.items:
                    self.assertGreater(it.item_no, 0)
                    self.assertGreaterEqual(it.tg_idx, 0)
                    self.assertLess(it.tg_idx, len(lay.target_dies))
                    self.assertIsInstance(it.x, float)
                    self.assertIsInstance(it.y, float)
                    self.assertIsInstance(it.rot_deg, float)
                    self.assertTrue(it.shape_name, "Nome do molde não pode ser vazio")

    def test_round_trip_byte_exact(self):
        """
        Testa a fidelidade byte-a-byte do ciclo parse -> generate -> comparar com arquivo original.
        Garante que o gerador não perde nenhum dado e preserva rigorosamente a formatação original.
        """
        for s_path in self.sample_files:
            with self.subTest(sample=os.path.basename(s_path)):
                with open(s_path, "rb") as fp:
                    orig_bytes = fp.read()

                lay = parse_lay(s_path)
                gen_text = generate_lay_content(lay)
                gen_bytes = gen_text.encode("latin1")

                self.assertEqual(
                    len(gen_bytes),
                    len(orig_bytes),
                    f"Tamanho em bytes difere em {os.path.basename(s_path)}"
                )
                self.assertEqual(
                    gen_bytes,
                    orig_bytes,
                    f"Conteúdo binário não é idêntico byte-a-byte em {os.path.basename(s_path)}"
                )

    def test_edge_case_empty_source(self):
        """Verifica se string ou arquivo vazio lança ValueError claro."""
        with self.assertRaises(ValueError):
            parse_lay("")

        with tempfile.NamedTemporaryFile("w", suffix=".lay", delete=False) as tf:
            tf.write("")
            tmp_name = tf.name

        try:
            with self.assertRaises(ValueError):
                parse_lay(tmp_name)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    def test_edge_case_truncated_source(self):
        """Verifica se layout com cabeçalho incompleto é tratado sem travar."""
        truncated_header = "$$LAYOUT.v3$$\n\\\\SERVER\\NSDATA\\test.lay\ndesc=Teste"
        lay = parse_lay(truncated_header)
        self.assertEqual(lay.version, "$$LAYOUT.v3$$")
        self.assertEqual(len(lay.items), 0)

    def test_edge_case_encodings(self):
        """Verifica parsing com acentuação e caracteres em latin1, utf-8 e cp1252."""
        text_with_accents = (
            "$$LAYOUT.v3$$\r\n"
            "C:\\Jobs\\Layout_Padrão.lay\r\n"
            "desc=Amostra com Acentuação Órgão e Padrão\r\n"
            "gap=1.000000\r\n"
            "codR=884412 Couro Bovino Estampado\r\n"
            "risW=1350.000000\r\n"
            "risL=2000.000000\r\n"
            "area=0.000000\r\n"
            "no_dies=1\r\n"
            "TG 1\r\n"
            "dLib=\\\\server\\shapes\r\n"
            "dCode=Gaspea_41.die\r\n"
            "dId=1\r\n"
            "dQta=1, 0\r\n"
            "dSingle=0, 0\r\n"
            "dIsFiller=0\r\n"
            "dTarg=1, 0\r\n"
            "num_of_items=1\r\n"
            "I 1 0 0 0 100.000000 150.000000 0.000000 -65536 Pasted\r\n"
        )
        for enc in ("latin1", "utf-8", "cp1252"):
            encoded = text_with_accents.encode(enc)
            lay = parse_lay(encoded)
            self.assertEqual(lay.version, "$$LAYOUT.v3$$")
            self.assertEqual(len(lay.items), 1)
            self.assertEqual(lay.items[0].x, 100.0)
            self.assertEqual(lay.items[0].y, 150.0)

    def test_edge_case_comma_decimal(self):
        """Verifica tolerância a vírgulas decimais europeias (ex: 1350,500000)."""
        comma_text = (
            "$$LAYOUT.v3$$\r\n"
            "C:\\Jobs\\test.lay\r\n"
            "desc=Teste Virgula\r\n"
            "gap=1,250000\r\n"
            "codR=884412\r\n"
            "risW=1340,500000\r\n"
            "risL=2500,750000\r\n"
            "area=12345,670000\r\n"
            "no_dies=1\r\n"
            "TG 1\r\n"
            "dLib=C:\\Shapes\r\n"
            "dCode=Peca.die\r\n"
            "dId=5\r\n"
            "dQta=1, 0\r\n"
            "dSingle=0, 0\r\n"
            "dIsFiller=0\r\n"
            "dTarg=1, 0\r\n"
            "num_of_items=1\r\n"
            "I 1 0 0 0 120,500000 45,250000 1,570796 -65536 Pasted\r\n"
        )
        lay = parse_lay(comma_text)
        self.assertAlmostEqual(lay.gap, 1.25)
        self.assertAlmostEqual(lay.ris_w, 1340.5)
        self.assertAlmostEqual(lay.ris_l, 2500.75)
        self.assertAlmostEqual(lay.area, 12345.67)
        self.assertEqual(len(lay.items), 1)
        self.assertAlmostEqual(lay.items[0].x, 120.5)
        self.assertAlmostEqual(lay.items[0].y, 45.25)
        self.assertAlmostEqual(lay.items[0].rot_deg, 90.0, places=1)

    def test_edge_case_missing_mold_in_db(self):
        """Verifica que peças com moldes não cadastrados no banco criam PlacedItem com fallback seguro."""
        db = DatabaseManager(":memory:")
        s_path = self.sample_files[0]
        lay = parse_lay(s_path, db=db)
        self.assertGreater(len(lay.items), 0)
        for it in lay.items:
            self.assertFalse(it.matched_in_db)
            self.assertTrue(len(it.contour) > 0, "Deve atribuir contorno padrão de fallback")

    def test_validation_warnings(self):
        """Testa regras de validação geométrica e regras de corte em pele/couro."""
        lay = LayoutData(
            ris_w=1000.0,
            ris_l=1000.0,
            items=[
                # Peça 1: Coordenada negativa
                PlacedItem(item_no=1, shape_name="peça_neg", x=-10.0, y=50.0, rot_deg=0.0),
                # Peça 2: Excede largura
                PlacedItem(item_no=2, shape_name="peça_fora", x=1050.0, y=50.0, rot_deg=0.0),
                # Peça 3: Cabedal girado a 90°
                PlacedItem(item_no=3, shape_name="gaspea_34", x=200.0, y=200.0, rot_deg=90.0),
            ]
        )
        warnings = validate_layout_placement(lay)
        self.assertTrue(any("coordenadas negativas" in w for w in warnings))
        self.assertTrue(any("excede a largura" in w for w in warnings))
        self.assertTrue(any("linha de tração/fio da pele" in w for w in warnings))

    def test_defect_zone_quality_validation(self):
        """Testa violação de zona de defeito: L_def <= Q_req."""
        qz = QualityZone(
            name="Cicatriz Severa",
            level=3,  # Nível 3 (Defeito severo)
            polygon=[
                {"x": 100.0, "y": 100.0},
                {"x": 200.0, "y": 100.0},
                {"x": 200.0, "y": 200.0},
                {"x": 100.0, "y": 200.0}
            ]
        )
        # Peça requer qualidade alta Q1 (1), sobreposta na cicatriz de nível 3 -> Regra L_def <= Q_req violada (3 > 1)
        item = PlacedItem(
            item_no=1,
            shape_name="gaspea_derby",
            quality_zone=1,
            x=150.0,
            y=150.0,
            rot_deg=0.0,
            contour=[
                {"x": -20.0, "y": -20.0},
                {"x": 20.0, "y": -20.0},
                {"x": 20.0, "y": 20.0},
                {"x": -20.0, "y": 20.0}
            ]
        )
        lay = LayoutData(
            ris_w=1000.0,
            ris_l=1000.0,
            items=[item],
            quality_zones=[qz]
        )
        warnings = validate_layout_placement(lay)
        self.assertTrue(any("Alerta de Qualidade" in w for w in warnings))

    def test_export_layout_from_pieces(self):
        """Testa geração de .lay a partir de lista de peças do editor com ordenação de vácuo."""
        pieces = [
            {
                "id": 1,
                "name": "Gaspea_Derby_41",
                "x": 100.0,
                "y": 200.0,
                "rotation": 45.0,
                "is_mirrored": False,
                "color": "#2563eb",
                "contour": [{"x": 0.0, "y": 0.0}, {"x": 50.0, "y": 0.0}, {"x": 50.0, "y": 50.0}, {"x": 0.0, "y": 50.0}],
                "holes": [{"x": 25.0, "y": 25.0, "radius": 1.5}],
                "stitching": [],
                "internal_cuts": []
            },
            {
                "id": 2,
                "name": "Gaspea_Derby_41",
                "x": 200.0,
                "y": 200.0,
                "rotation": 0.0,
                "is_mirrored": True,
                "color": "#2563eb",
                "contour": [{"x": 0.0, "y": 0.0}, {"x": 50.0, "y": 0.0}, {"x": 50.0, "y": 50.0}, {"x": 0.0, "y": 50.0}],
                "holes": [],
                "stitching": [],
                "internal_cuts": []
            }
        ]
        mat = {
            "id": "MAT_01",
            "name": "Couro 1.4mm",
            "width_mm": 1350.0,
            "height_mm": 2000.0,
            "gap_mm": 1.5
        }
        content = export_layout_from_pieces(pieces, mat, filename="teste_export.lay")
        self.assertTrue(content.startswith("$$LAYOUT.v3$$\r\n"))
        self.assertIn("num_of_items=2\r\n", content)
        self.assertIn("TG 1\r\n", content)
        self.assertIn("dQta=1, 1\r\n", content)
        self.assertIn("fn98MR", content)  # Peça espelhada

    def test_database_persistence(self):
        """Testa gravação, consulta e exclusão de layout no banco de dados SQLite."""
        db = DatabaseManager(":memory:")
        s_path = self.sample_files[0]
        lay = parse_lay(s_path, db=db)

        # Salva o layout na sessão 1
        layout_id = db.save_layout(session_id=1, layout_data=lay)
        self.assertIsNotNone(layout_id)
        self.assertGreater(layout_id, 0)

        # Consulta lista de layouts
        layouts = db.get_layouts(session_id=1)
        self.assertEqual(len(layouts), 1)
        self.assertEqual(layouts[0]["id"], layout_id)
        self.assertEqual(layouts[0]["num_items"], lay.num_of_items)

        # Consulta layout por ID com suas peças
        full_lay = db.get_layout_by_id(layout_id)
        self.assertIsNotNone(full_lay)
        self.assertEqual(len(full_lay["pieces"]), lay.num_of_items)

        # Deleta layout
        deleted = db.delete_layout(layout_id)
        self.assertTrue(deleted)
        self.assertEqual(len(db.get_layouts(session_id=1)), 0)

    def test_die_parser_regression(self):
        """Garante que o parser .die continua funcionando com 100% de estabilidade (zero regressão)."""
        die_path = os.path.join(PROJECT_ROOT, "samples", "Gaspea_Derby_41.die")
        if os.path.exists(die_path):
            data = parse_die_file(die_path)
            self.assertIn("contour", data)
            self.assertGreater(len(data["contour"]), 0)


if __name__ == "__main__":
    unittest.main()
