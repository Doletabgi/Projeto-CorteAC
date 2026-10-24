"""
JobManager 2000 (Python Edition)
Suíte de Testes Automatizados para a Dupla Saída de Layout:
- cad.czlib (Compressão e Descompressão CZLIB v1 e v2)
- cad.onx_exporter (Gerador de XML ONX Schema 1.1 e .ONX)
- cad.dual_exporter (DualLayoutExporter para ATOM .lay e Comelz .onx)
"""

import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from cad.czlib import compress_czlib, decompress_czlib, CZLIBError
from cad.onx_exporter import build_onx_xml, export_onx_from_pieces, save_onx_file
from cad.dual_exporter import DualLayoutExporter
from cad.lay_parser import parse_lay


class TestCZLIB(unittest.TestCase):
    """Validação do container de compressão CZLIB da Comelz."""

    def test_czlib_v2_roundtrip_string(self):
        sample = "Mensagem de teste de corte para máquina Comelz! 1234567890 áéíóú" * 20
        comp = compress_czlib(sample, version=2)
        self.assertTrue(comp.startswith(b"CZLIB"))
        decomp = decompress_czlib(comp).decode("utf-8")
        self.assertEqual(decomp, sample)

    def test_czlib_v1_roundtrip(self):
        sample = b"Dados legados gzip CZLIB v1" * 10
        comp = compress_czlib(sample, version=1)
        self.assertTrue(comp.startswith(b"CZLIB"))
        decomp = decompress_czlib(comp)
        self.assertEqual(decomp, sample)

    def test_czlib_invalid_magic_raises(self):
        with self.assertRaises(CZLIBError):
            decompress_czlib(b"INVALID_HEADER_DATA_12345")

    def test_czlib_with_real_as74467_file(self):
        real_file = Path("/home/dola/Documentos/clone do job/comelz/1791878926705/skins/AS74467.onx")
        if not real_file.exists():
            self.skipTest("Arquivo real AS74467.onx não encontrado")

        with open(real_file, "rb") as fp:
            orig_bytes = fp.read()

        xml_decomp = decompress_czlib(orig_bytes)
        self.assertIn(b"<onx xmlns=", xml_decomp)
        self.assertIn(b"AS74467", xml_decomp)
        self.assertIn(b"<cuttable />", xml_decomp)

        # Recomprime e verifica consistência
        recomp = compress_czlib(xml_decomp, version=2)
        self.assertEqual(len(recomp), len(orig_bytes))
        self.assertEqual(decompress_czlib(recomp), xml_decomp)


class TestONXExporter(unittest.TestCase):
    """Validação do gerador de XML e empacotamento .ONX."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.pieces = [
            {
                "id": 1,
                "name": "GASPEA_DIR",
                "size": "41",
                "x": 120.0,
                "y": 80.0,
                "rotation": 0.0,
                "is_mirrored": False,
                "contour": [{"x": 0, "y": 0}, {"x": 80, "y": 0}, {"x": 80, "y": 40}, {"x": 0, "y": 40}],
                "area": 3200.0
            },
            {
                "id": 2,
                "name": "GASPEA_ESQ",
                "size": "41",
                "x": 250.0,
                "y": 80.0,
                "rotation": 180.0,
                "is_mirrored": True,
                "contour": [{"x": 0, "y": 0}, {"x": 80, "y": 0}, {"x": 80, "y": 40}, {"x": 0, "y": 40}],
                "area": 3200.0
            }
        ]
        self.material = {
            "width_mm": 1360.0,
            "height_mm": 400.0,
            "thickness_mm": 1.2,
            "gap_mm": 2.0,
            "name": "COURO_SINTETICO",
            "id": "884412"
        }

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_build_onx_xml_schema(self):
        xml_str = build_onx_xml(self.pieces, self.material, title="LAYOUT_01")
        root = ET.fromstring(xml_str)
        self.assertEqual(root.tag, "{http://www.comelz.com/onx}onx")
        self.assertEqual(root.attrib.get("version"), "1.1")

        # Verifica tag de corte
        sec = root.find("{http://www.comelz.com/onx}security")
        self.assertIsNotNone(sec)
        self.assertIsNotNone(sec.find("{http://www.comelz.com/onx}cuttable"))

        # Verifica material e dimensões
        mat = root.find("{http://www.comelz.com/onx}material")
        self.assertIsNotNone(mat)
        self.assertEqual(mat.attrib.get("width"), "1360.00")
        self.assertEqual(mat.attrib.get("height"), "400.00")

        # Verifica peças e espelhamento
        models = root.find("{http://www.comelz.com/onx}models")
        self.assertIsNotNone(models)
        parts = models.findall(".//{http://www.comelz.com/onx}part")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0].attrib.get("mirrored"), "false")
        self.assertEqual(parts[1].attrib.get("mirrored"), "true")

    def test_save_onx_file(self):
        out_path = Path(self.tmp_dir) / "teste_corte.onx"
        saved = save_onx_file(self.pieces, self.material, out_path)
        self.assertTrue(Path(saved).exists())
        self.assertTrue(Path(saved).stat().st_size > 0)

        # Descompacta e valida conteúdo
        with open(saved, "rb") as fp:
            data = fp.read()
        decomp = decompress_czlib(data).decode("utf-8")
        self.assertIn("COURO_SINTETICO", decomp)
        self.assertIn("GASPEA_DIR", decomp)


class TestDualExporter(unittest.TestCase):
    """Validação do orquestrador de exportação dupla (ATOM + Comelz)."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.pieces = [
            {
                "id": 1,
                "name": "MOLDE_A",
                "size": "42",
                "x": 50.0,
                "y": 50.0,
                "rotation": 0.0,
                "is_mirrored": False,
                "contour": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 50}, {"x": 0, "y": 50}]
            },
            {
                "id": 2,
                "name": "MOLDE_B",
                "size": "42",
                "x": 180.0,
                "y": 50.0,
                "rotation": 90.0,
                "is_mirrored": True,
                "contour": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 50}, {"x": 0, "y": 50}]
            }
        ]
        self.material = {
            "width_mm": 1350.0,
            "height_mm": 1000.0,
            "thickness_mm": 1.0,
            "gap_mm": 1.5,
            "name": "MAT_TESTE",
            "id": "12345"
        }

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_export_dual_layout_creates_both_files(self):
        base_path = Path(self.tmp_dir) / "producao_lote_1"
        res = DualLayoutExporter.export_dual_layout(
            placed_pieces=self.pieces,
            material=self.material,
            base_path=base_path
        )

        lay_path = Path(res["lay_path"])
        onx_path = Path(res["onx_path"])

        # Ambos os arquivos devem existir
        self.assertTrue(lay_path.exists())
        self.assertTrue(onx_path.exists())
        self.assertEqual(lay_path.suffix, ".lay")
        self.assertEqual(onx_path.suffix, ".onx")
        self.assertEqual(res["total_pieces"], 2)

        # Valida arquivo ATOM .lay via parse_lay
        with open(lay_path, "r", encoding="latin1") as f:
            lay_content = f.read()
        parsed_lay = parse_lay(lay_content)
        self.assertEqual(parsed_lay.version, "$$LAYOUT.v3$$")
        self.assertEqual(len(parsed_lay.items), 2)

        # Valida arquivo Comelz .onx via decompress_czlib e XML
        with open(onx_path, "rb") as f:
            onx_bytes = f.read()
        decomp_xml = decompress_czlib(onx_bytes).decode("utf-8")
        self.assertIn("<cuttable />", decomp_xml)
        self.assertIn("MOLDE_A", decomp_xml)
        self.assertIn("MOLDE_B", decomp_xml)


if __name__ == "__main__":
    unittest.main()
