"""
JobManager 2000 (Python Edition)
Testes automatizados para a importação de listas de materiais:
- Detecção automática de delimitadores e codificações (UTF-8, Latin-1, CP1252)
- Parsing e mapeamento de colunas em CSV, TSV e JSON
- Conversão inteligente de unidades (metros para milímetros)
- Validação e categorização de novos vs atualizados vs erros
- Geração de modelo CSV de exemplo
- Persistência e integridade no banco de dados SQLite
- Instanciação e componentes do diálogo gráfico ImportMaterialsDialog
"""

import os
import tempfile
import unittest
import tkinter as tk
from unittest.mock import MagicMock

from cad.material_importer import (
    detect_delimiter,
    parse_material_file,
    generate_csv_template,
    _normalize_dimension,
    _parse_float
)
from database import DatabaseManager


class TestMaterialImporter(unittest.TestCase):
    def test_float_parsing(self):
        self.assertEqual(_parse_float("1,38"), 1.38)
        self.assertEqual(_parse_float("1.38"), 1.38)
        self.assertEqual(_parse_float("1.380,50"), 1380.5)
        self.assertEqual(_parse_float("1,380.50"), 1380.5)
        self.assertEqual(_parse_float("  2,5  "), 2.5)
        self.assertEqual(_parse_float("", 5.0), 5.0)
        self.assertEqual(_parse_float(None, 10.0), 10.0)

    def test_dimension_normalization(self):
        # Valores <= 25 são considerados metros e convertidos para mm (* 1000)
        self.assertEqual(_normalize_dimension(1.38), 1380.0)
        self.assertEqual(_normalize_dimension(2.98), 2980.0)
        self.assertEqual(_normalize_dimension(0.50), 500.0)
        # Valores > 25 já são milímetros
        self.assertEqual(_normalize_dimension(1380.0), 1380.0)
        self.assertEqual(_normalize_dimension(2980.0), 2980.0)
        self.assertEqual(_normalize_dimension(500.0), 500.0)

    def test_detect_delimiter(self):
        csv_semi = "cod;nome;larg;comp\nM1;Mat1;1.4;3.0\nM2;Mat2;1.5;3.2"
        self.assertEqual(detect_delimiter(csv_semi), ";")

        csv_comma = "cod,nome,larg,comp\nM1,Mat1,1.4,3.0\nM2,Mat2,1.5,3.2"
        self.assertEqual(detect_delimiter(csv_comma), ",")

        tsv = "cod\tnome\tlarg\tcomp\nM1\tMat1\t1.4\t3.0\nM2\tMat2\t1.5\t3.2"
        self.assertEqual(detect_delimiter(tsv), "\t")

    def test_parse_csv_semicolon(self):
        csv_data = (
            "codigo;descricao;definicao;largura;comprimento;camadas\n"
            "SINT-01;Sintético Preto 1.40m;como placa;1,40;3,00;2\n"
            "SINT-02;Sintético Branco 1.38m;como placa;1.38;2.98;4\n"
        )
        res = parse_material_file(csv_data)
        self.assertEqual(res["summary"]["total"], 2)
        self.assertEqual(res["summary"]["valid"], 2)
        self.assertEqual(res["summary"]["new"], 2)

        item1 = res["items"][0]
        self.assertEqual(item1["id"], "SINT-01")
        self.assertEqual(item1["name"], "Sintético Preto 1.40m")
        self.assertEqual(item1["width_mm"], 1400.0)
        self.assertEqual(item1["height_mm"], 3000.0)
        self.assertEqual(item1["layers"], 2)
        self.assertEqual(item1["status"], "new")

        item2 = res["items"][1]
        self.assertEqual(item2["id"], "SINT-02")
        self.assertEqual(item2["width_mm"], 1380.0)
        self.assertEqual(item2["height_mm"], 2980.0)
        self.assertEqual(item2["layers"], 4)

    def test_parse_csv_in_millimeters_and_aliases(self):
        csv_data = (
            "id,material,largura_mm,altura,qtd_camadas\n"
            "CHAPA-ACO,Chapa de Aço 1020,1200,2400,1\n"
        )
        res = parse_material_file(csv_data)
        self.assertEqual(res["summary"]["total"], 1)
        item = res["items"][0]
        self.assertEqual(item["id"], "CHAPA-ACO")
        self.assertEqual(item["name"], "Chapa de Aço 1020")
        self.assertEqual(item["width_mm"], 1200.0)
        self.assertEqual(item["height_mm"], 2400.0)
        self.assertEqual(item["layers"], 1)

    def test_parse_csv_latin1_encoding(self):
        raw_text = "código;descrição;largura;comprimento;camadas\nCOURO-PADRÃO;Couro Legítimo Padrão Especial;1,38;2,98;1\n"
        raw_bytes = raw_text.encode("latin-1")

        res = parse_material_file(raw_bytes)
        self.assertEqual(res["summary"]["total"], 1)
        item = res["items"][0]
        self.assertEqual(item["id"], "COURO-PADRÃO")
        self.assertEqual(item["name"], "Couro Legítimo Padrão Especial")
        self.assertEqual(item["width_mm"], 1380.0)

    def test_parse_json(self):
        json_data = """
        [
            {
                "codigo": "JSON-MAT-01",
                "descricao": "Material via JSON 1",
                "largura": 1.45,
                "comprimento": 3.10,
                "camadas": 3
            },
            {
                "id": "JSON-MAT-02",
                "name": "Material via JSON 2",
                "width": 1500,
                "height": 3000,
                "layers": 2
            }
        ]
        """
        res = parse_material_file(json_data)
        self.assertEqual(res["summary"]["total"], 2)
        self.assertEqual(res["summary"]["valid"], 2)
        self.assertEqual(res["items"][0]["id"], "JSON-MAT-01")
        self.assertEqual(res["items"][0]["width_mm"], 1450.0)
        self.assertEqual(res["items"][1]["id"], "JSON-MAT-02")
        self.assertEqual(res["items"][1]["width_mm"], 1500.0)

    def test_existing_ids_status_update(self):
        csv_data = (
            "codigo;descricao;largura;comprimento\n"
            "EXIST-01;Material Existente;1.40;3.00\n"
            "NEW-01;Material Novo;1.50;3.50\n"
        )
        existing = {"EXIST-01", "OUTRO-02"}
        res = parse_material_file(csv_data, existing_ids=existing)
        self.assertEqual(res["summary"]["total"], 2)
        self.assertEqual(res["summary"]["update"], 1)
        self.assertEqual(res["summary"]["new"], 1)
        self.assertEqual(res["items"][0]["status"], "update")
        self.assertEqual(res["items"][1]["status"], "new")

    def test_invalid_records(self):
        csv_data = (
            "codigo;descricao;largura;comprimento\n"
            ";Material Sem Codigo;1.40;3.00\n"
            "INV-01;Material Largura Invalida;0;3.00\n"
            "VALID-01;Material Valido;1.40;3.00\n"
        )
        res = parse_material_file(csv_data)
        self.assertEqual(res["summary"]["total"], 3)
        self.assertEqual(res["summary"]["invalid"], 2)
        self.assertEqual(res["summary"]["valid"], 1)
        self.assertEqual(res["items"][0]["status"], "invalid")
        self.assertEqual(res["items"][1]["status"], "invalid")
        self.assertEqual(res["items"][2]["status"], "new")

    def test_generate_template(self):
        tmpl = generate_csv_template(delimiter=";")
        self.assertIn("codigo;descricao;definicao;largura;comprimento", tmpl)
        self.assertIn("SINT-PRETO-140", tmpl)

    def test_database_bulk_import_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db_path = f.name

        try:
            db = DatabaseManager(temp_db_path)
            csv_data = (
                "codigo;descricao;definicao;largura;comprimento;camadas\n"
                "TEST-IMP-01;Material Importado 1;como placa;1,40;3,00;2\n"
                "TEST-IMP-02;Material Importado 2;como placa;1,38;2,98;3\n"
            )
            parsed = parse_material_file(csv_data)
            for it in parsed["items"]:
                db.create_material(
                    mat_id=it["id"],
                    name=it["name"],
                    type=it["type"],
                    width_mm=it["width_mm"],
                    height_mm=it["height_mm"],
                    thickness_mm=it["thickness_mm"],
                    layers=it["layers"],
                    gap_mm=it["gap_mm"]
                )

            all_mats = db.get_materials()
            mat_ids = [m["id"] for m in all_mats]
            self.assertIn("TEST-IMP-01", mat_ids)
            self.assertIn("TEST-IMP-02", mat_ids)

            m1 = db.get_material("TEST-IMP-01")
            self.assertEqual(m1["name"], "Material Importado 1")
            self.assertEqual(m1["width_mm"], 1400.0)
            self.assertEqual(m1["height_mm"], 3000.0)
            self.assertEqual(m1["layers"], 2)

            m2 = db.get_material("TEST-IMP-02")
            self.assertEqual(m2["layers"], 3)
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


class TestImportMaterialsDialogUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
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
            self.skipTest("Tkinter display not available")

    def test_dialog_creation_and_preview(self):
        from ui.import_materials_dialog import ImportMaterialsDialog

        mock_db = MagicMock()
        mock_db.get_materials.return_value = [{"id": "EXIST-01", "name": "Existente"}]

        dlg = ImportMaterialsDialog(self.root, mock_db)
        self.assertIsNotNone(dlg.tree)
        self.assertIsNotNone(dlg.btn_import)
        self.assertEqual(dlg.btn_import["state"], "disabled")

        # Testa popular a pré-visualização diretamente com resultado de parsing
        sample_result = {
            "items": [
                {
                    "id": "MAT-01",
                    "name": "Material 01",
                    "type": "como placa",
                    "width_mm": 1400.0,
                    "height_mm": 3000.0,
                    "layers": 2,
                    "status": "new",
                    "error_msg": None
                }
            ],
            "summary": {
                "total": 1,
                "valid": 1,
                "new": 1,
                "update": 0,
                "invalid": 0
            }
        }
        dlg.populate_preview(sample_result)
        self.assertEqual(dlg.btn_import["state"], "normal")
        self.assertIn("1 item(s)", dlg.lbl_summary["text"])

        dlg.destroy()


if __name__ == "__main__":
    unittest.main()
