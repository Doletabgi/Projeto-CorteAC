"""
JobManager 2000 / CorteAC (Python Edition)
Suíte de Testes Automatizados para o Conversor de Arquivos (.lay ⇄ .onx):
- cad.layout_converter (Funções de conversão bidirecional e em lote)
- Testes com arquivos sintéticos e arquivos reais de produção
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cad.layout_converter import (
    convert_lay_to_onx,
    convert_onx_to_lay,
    convert_file,
    convert_batch,
    detect_file_format,
    ConversionResult
)
from cad.lay_parser import parse_lay
from cad.onx_exporter import parse_onx
from cad.czlib import decompress_czlib


class TestLayoutConverter(unittest.TestCase):
    """Testes de conversão entre ATOM FlashCut (.lay) e Comelz CNC (.onx)."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_converter_"))

        # Cria um arquivo .lay de teste sintético com padrão oficial $$LAYOUT.v3$$
        self.sample_lay_path = self.tmp_dir / "sample.lay"
        lay_content = (
            "$$LAYOUT.v3$$\r\n"
            "\\\\lab-inf\\NSDATAV1\\Compiti\\JobManager sample.lay\r\n"
            "desc=CorteAC Test\r\n"
            "gap=1.500000\r\n"
            "codR=MAT_SYNTH_01\r\n"
            "risW=1350.000000\r\n"
            "risL=2000.000000\r\n"
            "Y_max=0.000000\r\n"
            "Y_last=0.000000\r\n"
            "area=50000.000000\r\n"
            "no_dies=2\r\n"
            "TG 1\r\n"
            "dLib=\\\\lab-inf\\NSDATAV1\\Shapes\r\n"
            "dCode=Gaspea.die\r\n"
            "dId=1\r\n"
            "dQta=2, 0\r\n"
            "dSingle=0, 0\r\n"
            "dIsFiller=0\r\n"
            "dTarg=2, 0\r\n"
            "TG 2\r\n"
            "dLib=\\\\lab-inf\\NSDATAV1\\Shapes\r\n"
            "dCode=Taloeira.die\r\n"
            "dId=2\r\n"
            "dQta=0, 2\r\n"
            "dSingle=0, 0\r\n"
            "dIsFiller=0\r\n"
            "dTarg=0, 2\r\n"
            "num_of_items=4\r\n"
            "I 1 0 0 0 100.000000 150.000000 0.000000 -65536 Pasted\r\n"
            "I 2 0 1 0 250.000000 150.000000 0.000000 -65536 Pasted\r\n"
            "I 3 1 2 0 100.000000 350.000000 3.141593 -65536 fn98MR\r\n"
            "I 4 1 3 0 250.000000 350.000000 3.141593 -65536 fn98MR\r\n"
        )
        with open(self.sample_lay_path, "wb") as f:
            f.write(lay_content.encode("latin1"))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_detect_file_format(self):
        self.assertEqual(detect_file_format("arquivo.lay"), "lay")
        self.assertEqual(detect_file_format("arquivo.onx"), "onx")
        self.assertEqual(detect_file_format(self.sample_lay_path), "lay")

    def test_convert_lay_to_onx(self):
        target_onx = self.tmp_dir / "converted.onx"
        res = convert_lay_to_onx(self.sample_lay_path, target_onx)

        self.assertTrue(res.success, msg=f"Falha na conversão: {res.error_message}")
        self.assertEqual(res.direction, "lay_to_onx")
        self.assertEqual(res.items_count, 4)
        self.assertEqual(res.dies_count, 2)
        self.assertEqual(res.width_mm, 1350.0)
        self.assertEqual(res.height_mm, 2000.0)
        self.assertTrue(target_onx.exists())

        # Valida que o ONX gerado tem assinatura CZLIB e XML válido
        with open(target_onx, "rb") as fp:
            onx_bytes = fp.read()
        self.assertTrue(onx_bytes.startswith(b"CZLIB"))
        xml_decomp = decompress_czlib(onx_bytes).decode("utf-8")
        self.assertIn("<onx xmlns=\"http://www.comelz.com/onx\"", xml_decomp)
        self.assertIn("Gaspea", xml_decomp)
        self.assertIn("Taloeira", xml_decomp)
        self.assertIn("width=\"1350.00\"", xml_decomp)

    def test_convert_onx_to_lay(self):
        # 1. Primeiro gera um ONX
        target_onx = self.tmp_dir / "temp.onx"
        res_onx = convert_lay_to_onx(self.sample_lay_path, target_onx)
        self.assertTrue(res_onx.success)

        # 2. Converte de volta para .lay
        target_lay = self.tmp_dir / "converted_back.lay"
        res_lay = convert_onx_to_lay(target_onx, target_lay)

        self.assertTrue(res_lay.success, msg=f"Falha na conversão: {res_lay.error_message}")
        self.assertEqual(res_lay.direction, "onx_to_lay")
        self.assertEqual(res_lay.items_count, 4)
        self.assertEqual(res_lay.dies_count, 2)
        self.assertEqual(res_lay.width_mm, 1350.0)
        self.assertEqual(res_lay.height_mm, 2000.0)
        self.assertTrue(target_lay.exists())

        # 3. Lê com o parser oficial de .lay
        parsed = parse_lay(target_lay)
        self.assertEqual(len(parsed.items), 4)
        self.assertEqual(len(parsed.target_dies), 2)
        self.assertEqual(parsed.ris_w, 1350.0)
        self.assertEqual(parsed.ris_l, 2000.0)

    def test_convert_file_auto_detection(self):
        # Converte .lay sem especificar destino -> gera .onx
        res1 = convert_file(self.sample_lay_path)
        self.assertTrue(res1.success)
        expected_onx = self.sample_lay_path.with_suffix(".onx")
        self.assertTrue(expected_onx.exists())

        # Converte o .onx gerado de volta para outra pasta
        out_lay = self.tmp_dir / "auto_test.lay"
        res2 = convert_file(expected_onx, out_lay)
        self.assertTrue(res2.success)
        self.assertTrue(out_lay.exists())

    def test_convert_batch(self):
        # Prepara 3 arquivos .lay na pasta de teste
        file1 = self.tmp_dir / "lay01.lay"
        file2 = self.tmp_dir / "lay02.lay"
        shutil.copy(self.sample_lay_path, file1)
        shutil.copy(self.sample_lay_path, file2)

        batch_out = self.tmp_dir / "batch_output"
        results = convert_batch([file1, file2], output_dir=batch_out, target_format="onx")

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertTrue(r.success)
            self.assertTrue(Path(r.target_file).exists())
            self.assertEqual(Path(r.target_file).suffix, ".onx")

    def test_real_sess188_lay_file(self):
        real_lay = Path("/home/dola/Documentos/clone do job/SESS-188/lay0000.lay")
        if not real_lay.exists():
            self.skipTest("Arquivo SESS-188/lay0000.lay não encontrado")

        out_onx = self.tmp_dir / "sess188.onx"
        res = convert_lay_to_onx(real_lay, out_onx)
        self.assertTrue(res.success)
        self.assertEqual(res.items_count, 226)
        self.assertEqual(res.dies_count, 6)
        self.assertTrue(out_onx.exists())

        # Converte de volta para .lay e confere integridade
        out_lay = self.tmp_dir / "sess188_back.lay"
        res_back = convert_onx_to_lay(out_onx, out_lay)
        self.assertTrue(res_back.success)
        self.assertEqual(res_back.items_count, 226)

    def test_real_comelz_as74467_file(self):
        real_onx = Path("/home/dola/Documentos/clone do job/sistemas/comelz/1791878926705/skins/AS74467.onx")
        if not real_onx.exists():
            self.skipTest("Arquivo real AS74467.onx não encontrado")

        out_lay = self.tmp_dir / "AS74467.lay"
        res = convert_onx_to_lay(real_onx, out_lay)
        self.assertTrue(res.success)
        self.assertEqual(res.items_count, 28)
        self.assertEqual(res.dies_count, 4)
        self.assertTrue(out_lay.exists())

        # Converte de volta para ONX
        out_onx = self.tmp_dir / "AS74467_back.onx"
        res_back = convert_lay_to_onx(out_lay, out_onx)
        self.assertTrue(res_back.success)
        self.assertEqual(res_back.items_count, 28)

    def test_error_handling_nonexistent_file(self):
        bogus_file = self.tmp_dir / "nonexistent.lay"
        res = convert_file(bogus_file)
        self.assertFalse(res.success)
        self.assertIn("não encontrado", res.error_message)


if __name__ == "__main__":
    unittest.main()
