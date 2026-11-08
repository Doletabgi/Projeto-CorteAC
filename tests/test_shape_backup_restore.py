"""
Testes automatizados para a ferramenta de Backup e Restauração de Moldes
(cad/shape_backup.py e ui/shape_backup_restore_dialog.py).
"""

import os
import json
import zipfile
import tempfile
import unittest
import tkinter as tk
from pathlib import Path

from cad.shape_backup import (
    create_shapes_backup,
    inspect_shapes_backup,
    restore_shapes_backup,
    BackupSummary,
    BackupInspectionResult,
    RestoreResult
)
from cad.die_parser import generate_die_content
from ui.shape_backup_restore_dialog import ShapeBackupRestoreDialog


class MockDatabase:
    """Banco de dados em memória simulado para testes isolados de moldes."""
    def __init__(self):
        self.shapes = [
            {
                "id": 1,
                "article_id": 10,
                "name": "323_PalAcb_36a",
                "size": "36",
                "color": "#000080",
                "folder": "faca",
                "shape_format": "1x1",
                "contour": [{"x": 0.0, "y": 0.0}, {"x": 50.0, "y": 0.0}, {"x": 50.0, "y": 50.0}, {"x": 0.0, "y": 50.0}],
                "holes": [],
                "stitching": []
            },
            {
                "id": 2,
                "article_id": 10,
                "name": "323_PalAcb_32a",
                "size": "32",
                "color": "#0284c7",
                "folder": "faca",
                "shape_format": "4x1",
                "contour": [{"x": 0.0, "y": 0.0}, {"x": 40.0, "y": 0.0}, {"x": 40.0, "y": 40.0}, {"x": 0.0, "y": 40.0}],
                "holes": [[{"x": 10.0, "y": 10.0}, {"x": 20.0, "y": 10.0}, {"x": 20.0, "y": 20.0}, {"x": 10.0, "y": 20.0}]],
                "stitching": []
            },
            {
                "id": 3,
                "article_id": 20,
                "name": "BOTA_CANO_DIR",
                "size": "41",
                "color": "#16a34a",
                "folder": "BOTAS/CANO",
                "shape_format": "1x1",
                "contour": [{"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 0.0}, {"x": 100.0, "y": 120.0}, {"x": 0.0, "y": 120.0}],
                "holes": [],
                "stitching": []
            }
        ]
        self.folders = ["faca", "BOTAS/CANO", "OUTROS"]
        self.orders = [{"id": 1, "name": "Pedido Teste"}]
        self.articles = [
            {"id": 10, "order_id": 1, "name": "Sapato Teste", "pairs_count": 20, "material_id": "MAT1"},
            {"id": 20, "order_id": 1, "name": "Bota Teste", "pairs_count": 10, "material_id": "MAT2"}
        ]
        self.next_shape_id = 4

    def get_all_shapes(self):
        return [dict(s) for s in self.shapes]

    def get_shape_folders(self):
        return list(self.folders)

    def create_shape_folder(self, name):
        if name and name not in self.folders:
            self.folders.append(name)
        return True

    def get_orders(self):
        return [dict(o) for o in self.orders]

    def get_articles_by_order(self, order_id):
        return [dict(a) for a in self.articles if a.get("order_id") == order_id]

    def create_shape(self, article_id=None, name="Shape", color="#000080", contour=None, holes=None, stitching=None, folder="", size="41", shape_format="1x1"):
        new_id = self.next_shape_id
        self.next_shape_id += 1
        new_shape = {
            "id": new_id,
            "article_id": article_id,
            "name": name,
            "color": color,
            "contour": contour or [],
            "holes": holes or [],
            "stitching": stitching or [],
            "folder": folder or "",
            "size": size,
            "shape_format": shape_format
        }
        self.shapes.append(new_shape)
        return new_id

    def update_shape(self, shape_id, name, contour, holes=None, stitching=None, folder=None, size=None, color=None, shape_format=None):
        for s in self.shapes:
            if s["id"] == shape_id:
                s["name"] = name
                s["contour"] = contour
                if holes is not None:
                    s["holes"] = holes
                if stitching is not None:
                    s["stitching"] = stitching
                if folder is not None:
                    s["folder"] = folder
                if size is not None:
                    s["size"] = size
                if color is not None:
                    s["color"] = color
                if shape_format is not None:
                    s["shape_format"] = shape_format
                return True
        return False


class TestShapeBackupRestore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dest_dir = Path(self.temp_dir.name)
        self.db = MockDatabase()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_shapes_backup_full(self):
        """Testa geração completa do pacote de backup com todos os moldes e pastas."""
        zip_path = self.dest_dir / "backup_completo.zip"
        summary = create_shapes_backup(self.db, zip_path, include_die_files=True)

        self.assertTrue(zip_path.exists())
        self.assertEqual(summary.total_shapes, 3)
        self.assertEqual(summary.total_folders, 3)
        self.assertTrue(summary.file_size_bytes > 0)

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("manifest.json", namelist)
            self.assertIn("shapes.json", namelist)
            self.assertIn("folders.json", namelist)
            self.assertIn("articles.json", namelist)

            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["total_shapes"], 3)
            self.assertEqual(manifest["total_folders"], 3)

            shapes_data = json.loads(zf.read("shapes.json").decode("utf-8"))
            self.assertEqual(len(shapes_data), 3)

            # Verifica presença de arquivos .die
            die_files = [n for n in namelist if n.endswith(".die")]
            self.assertEqual(len(die_files), 3)

    def test_create_shapes_backup_with_folder_filter(self):
        """Testa geração de backup filtrado por pasta específica."""
        zip_path = self.dest_dir / "backup_faca.zip"
        summary = create_shapes_backup(self.db, zip_path, folder_filter=["faca"], include_die_files=False)

        self.assertEqual(summary.total_shapes, 2)
        with zipfile.ZipFile(zip_path, "r") as zf:
            shapes_data = json.loads(zf.read("shapes.json").decode("utf-8"))
            self.assertEqual(len(shapes_data), 2)
            for s in shapes_data:
                self.assertEqual(s["folder"], "faca")
            # Sem .die
            die_files = [n for n in zf.namelist() if n.endswith(".die")]
            self.assertEqual(len(die_files), 0)

    def test_inspect_shapes_backup_valid(self):
        """Testa inspeção de arquivo de backup válido."""
        zip_path = self.dest_dir / "backup_test.zip"
        create_shapes_backup(self.db, zip_path)

        inspection = inspect_shapes_backup(zip_path)
        self.assertTrue(inspection.is_valid)
        self.assertEqual(inspection.total_shapes, 3)
        self.assertIn("faca", inspection.folders)
        self.assertIn("BOTAS/CANO", inspection.folders)
        self.assertFalse(inspection.is_legacy_die_zip)
        self.assertEqual(len(inspection.shapes), 3)

    def test_inspect_shapes_backup_invalid(self):
        """Testa inspeção em arquivo corrompido ou inexistente."""
        fake_path = self.dest_dir / "inexistente.zip"
        insp1 = inspect_shapes_backup(fake_path)
        self.assertFalse(insp1.is_valid)

        corrupted_path = self.dest_dir / "corrompido.zip"
        corrupted_path.write_bytes(b"NOT A ZIP CONTENT")
        insp2 = inspect_shapes_backup(corrupted_path)
        self.assertFalse(insp2.is_valid)

    def test_restore_shapes_backup_overwrite(self):
        """Testa restauração com estratégia 'overwrite' (atualiza existentes)."""
        zip_path = self.dest_dir / "backup_to_restore.zip"
        create_shapes_backup(self.db, zip_path)

        # Modifica o banco local para testar a atualização
        for s in self.db.shapes:
            if s["name"] == "323_PalAcb_36a":
                s["shape_format"] = "6x1"  # original no backup é 1x1

        res = restore_shapes_backup(self.db, zip_path, conflict_strategy="overwrite")
        self.assertEqual(res.total_in_backup, 3)
        self.assertEqual(res.updated_existing, 3)
        self.assertEqual(res.imported_new, 0)
        self.assertEqual(res.skipped, 0)

        # Verifica que o molde foi atualizado para o valor do backup (1x1)
        s36 = next(s for s in self.db.shapes if s["name"] == "323_PalAcb_36a")
        self.assertEqual(s36["shape_format"], "1x1")

    def test_restore_shapes_backup_skip(self):
        """Testa restauração com estratégia 'skip' (ignora existentes)."""
        zip_path = self.dest_dir / "backup_to_restore.zip"
        create_shapes_backup(self.db, zip_path)

        # Modifica o banco local
        for s in self.db.shapes:
            if s["name"] == "323_PalAcb_36a":
                s["shape_format"] = "6x1"

        res = restore_shapes_backup(self.db, zip_path, conflict_strategy="skip")
        self.assertEqual(res.skipped, 3)
        self.assertEqual(res.imported_new, 0)
        self.assertEqual(res.updated_existing, 0)

        # Permanece com a modificação local intacta
        s36 = next(s for s in self.db.shapes if s["name"] == "323_PalAcb_36a")
        self.assertEqual(s36["shape_format"], "6x1")

    def test_restore_shapes_backup_rename(self):
        """Testa restauração com estratégia 'rename' (cria cópias com sufixo)."""
        zip_path = self.dest_dir / "backup_to_restore.zip"
        create_shapes_backup(self.db, zip_path)

        initial_count = len(self.db.shapes)
        res = restore_shapes_backup(self.db, zip_path, conflict_strategy="rename")

        self.assertEqual(res.imported_new, 3)
        self.assertEqual(len(self.db.shapes), initial_count + 3)

        # Deve existir 323_PalAcb_36a_copia
        names = [s["name"] for s in self.db.shapes]
        self.assertIn("323_PalAcb_36a_copia", names)

    def test_restore_shapes_backup_from_legacy_die_zip(self):
        """Testa restauração a partir de um ZIP de arquivos .die avulsos (compatibilidade ATOM legado)."""
        zip_path = self.dest_dir / "legacy_dies.zip"
        box_shape = {
            "name": "MOLDE_LEGADO",
            "size": "42",
            "folder": "LEGADO",
            "contour": [{"x": 0.0, "y": 0.0}, {"x": 30.0, "y": 0.0}, {"x": 30.0, "y": 30.0}, {"x": 0.0, "y": 30.0}],
            "holes": [],
            "stitching": []
        }
        die_text = generate_die_content(box_shape)

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("LEGADO/MOLDE_LEGADO.die", die_text)

        inspection = inspect_shapes_backup(zip_path)
        self.assertTrue(inspection.is_valid)
        self.assertTrue(inspection.is_legacy_die_zip)
        self.assertEqual(inspection.total_shapes, 1)

        res = restore_shapes_backup(self.db, zip_path, conflict_strategy="overwrite")
        self.assertEqual(res.imported_new, 1)
        names = [s["name"] for s in self.db.shapes]
        self.assertIn("MOLDE_LEGADO", names)

    def test_ui_dialog_initialization(self):
        """Testa inicialização do diálogo modal ShapeBackupRestoreDialog."""
        try:
            root = tk.Tk()
        except Exception:
            self.skipTest("Tkinter display indisponível")

        try:
            dlg = ShapeBackupRestoreDialog(root, db=self.db)
            self.assertIsNotNone(dlg.notebook)
            self.assertEqual(len(dlg.notebook.tabs()), 3)
            self.assertTrue(dlg.btn_run_backup.winfo_exists())
            self.assertTrue(dlg.btn_run_restore.winfo_exists())
            self.assertTrue(dlg.tab_schedule.winfo_exists())
            dlg.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
