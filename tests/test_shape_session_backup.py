"""
Testes automatizados para backup e restauração de sessões de corte e layouts
(cad/shape_backup.py e cad/shape_backup_scheduler.py).
"""

import os
import json
import zipfile
import shutil
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from cad.shape_backup import (
    create_shapes_backup,
    inspect_shapes_backup,
    restore_shapes_backup,
    BackupSummary,
    BackupInspectionResult,
    RestoreResult,
)
from cad.shape_backup_scheduler import (
    get_default_schedule_config,
    normalize_schedule_config,
    save_schedule_config,
    get_schedule_config,
    execute_scheduled_backup,
    apply_retention_policy,
)


class TestShapeSessionBackup(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_corteac_sess_bkp_")
        self.db_path = Path(self.temp_dir) / "test_session_bkp.db"
        self.db = DatabaseManager(db_path=str(self.db_path), backend="sqlite")

        # Limpa dados demo semeados para testes determinísticos
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM layout_pieces")
            cur.execute("DELETE FROM layouts")
            cur.execute("DELETE FROM sessions")
            cur.execute("DELETE FROM shapes")
            cur.execute("DELETE FROM shape_folders")
            conn.commit()

        # 1. Cria um material
        self.db.create_material(
            mat_id="MAT_TESTE",
            name="Material Couro Teste",
            type="leather"
        )

        # 2. Cria moldes de teste
        self.db.create_shape_folder("CALCADOS")
        self.shape1_id = self.db.create_shape(
            name="GASPEA_38",
            folder="CALCADOS",
            size="38",
            contour=[{"x": 0.0, "y": 0.0}, {"x": 80.0, "y": 0.0}, {"x": 80.0, "y": 60.0}, {"x": 0.0, "y": 60.0}],
            holes=[]
        )
        self.shape2_id = self.db.create_shape(
            name="TALONEIRA_38",
            folder="CALCADOS",
            size="38",
            contour=[{"x": 0.0, "y": 0.0}, {"x": 40.0, "y": 0.0}, {"x": 40.0, "y": 40.0}, {"x": 0.0, "y": 40.0}],
            holes=[]
        )

        # 3. Cria uma sessão de corte com layouts
        order_id = self.db.create_order("JOB_TEST_2026", 1)

        shapes = [
            {"id": self.shape1_id, "name": "GASPEA_38", "demand": 10, "nested": 10},
            {"id": self.shape2_id, "name": "TALONEIRA_38", "demand": 10, "nested": 10}
        ]
        placed_pieces = [
            {"shape_id": self.shape1_id, "x": 10.0, "y": 10.0, "rotation": 0.0, "piece_name": "GASPEA_38", "layer": 0},
            {"shape_id": self.shape2_id, "x": 100.0, "y": 10.0, "rotation": 90.0, "piece_name": "TALONEIRA_38", "layer": 0}
        ]

        self.db.create_session(
            session_id=101,
            material_id="MAT_TESTE",
            layers=2,
            shapes=shapes,
            placed_pieces=placed_pieces,
            order_id=order_id,
            job="JOB_TEST_2026"
        )

        # Salva layouts múltiplos para a sessão 101
        layouts = [
            {
                "layout_index": 0,
                "name": "lay0000",
                "width": 1200.0,
                "height": 800.0,
                "efficiency": 82.5,
                "pieces_count": 2,
                "pieces": placed_pieces
            },
            {
                "layout_index": 1,
                "name": "lay0001",
                "width": 1200.0,
                "height": 800.0,
                "efficiency": 78.0,
                "pieces_count": 1,
                "pieces": [placed_pieces[0]]
            }
        ]
        self.db.save_session_layouts(101, layouts)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_backup_all_scope(self):
        """Testa geração de backup completo ('all'): moldes + sessões + layouts + materiais."""
        zip_path = Path(self.temp_dir) / "backup_completo.zip"
        summary = create_shapes_backup(self.db, zip_path, backup_scope="all")

        self.assertTrue(zip_path.exists())
        self.assertEqual(summary.total_shapes, 2)
        self.assertEqual(summary.total_sessions, 1)
        self.assertEqual(summary.total_layouts, 2)
        self.assertEqual(summary.backup_type, "all")

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("manifest.json", namelist)
            self.assertIn("shapes.json", namelist)
            self.assertIn("sessions.json", namelist)
            self.assertIn("materials.json", namelist)

            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["format_version"], "2.0")
            self.assertEqual(manifest["total_shapes"], 2)
            self.assertEqual(manifest["total_sessions"], 1)
            self.assertEqual(manifest["total_layouts"], 2)

            sessions_data = json.loads(zf.read("sessions.json").decode("utf-8"))
            self.assertEqual(len(sessions_data), 1)
            s0 = sessions_data[0]
            self.assertEqual(s0["id"], 101)
            self.assertEqual(s0["job"], "JOB_TEST_2026")
            self.assertEqual(len(s0["layouts"]), 2)

    def test_backup_sessions_only_scope(self):
        """Testa backup exclusivo de sessões ('sessions_only')."""
        zip_path = Path(self.temp_dir) / "backup_sessoes.zip"
        summary = create_shapes_backup(self.db, zip_path, backup_scope="sessions_only")

        self.assertEqual(summary.total_shapes, 0)
        self.assertEqual(summary.total_sessions, 1)
        self.assertEqual(summary.total_layouts, 2)
        self.assertEqual(summary.backup_type, "sessions_only")

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("manifest.json", namelist)
            self.assertNotIn("shapes.json", namelist)
            self.assertIn("sessions.json", namelist)

    def test_backup_shapes_only_scope(self):
        """Testa backup exclusivo de moldes ('shapes_only')."""
        zip_path = Path(self.temp_dir) / "backup_moldes.zip"
        summary = create_shapes_backup(self.db, zip_path, backup_scope="shapes_only")

        self.assertEqual(summary.total_shapes, 2)
        self.assertEqual(summary.total_sessions, 0)
        self.assertEqual(summary.total_layouts, 0)
        self.assertEqual(summary.backup_type, "shapes_only")

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("shapes.json", namelist)
            self.assertNotIn("sessions.json", namelist)

    def test_inspect_shapes_and_sessions(self):
        """Testa inspeção de pacote contendo moldes e sessões."""
        zip_path = Path(self.temp_dir) / "inspect_test.zip"
        create_shapes_backup(self.db, zip_path, backup_scope="all")

        insp = inspect_shapes_backup(zip_path)
        self.assertTrue(insp.is_valid)
        self.assertTrue(insp.has_shapes)
        self.assertTrue(insp.has_sessions)
        self.assertEqual(insp.total_shapes, 2)
        self.assertEqual(insp.total_sessions, 1)
        self.assertEqual(insp.total_layouts, 2)
        self.assertEqual(len(insp.sessions), 1)
        self.assertEqual(insp.sessions[0]["id"], 101)
        self.assertEqual(insp.sessions[0]["job"], "JOB_TEST_2026")
        self.assertEqual(insp.sessions[0]["layouts_count"], 2)

    def test_restore_sessions_import_new_id(self):
        """Testa restauração com estratégia import_new_id gerando novo ID sem sobrescrever o existente."""
        zip_path = Path(self.temp_dir) / "backup_to_restore.zip"
        create_shapes_backup(self.db, zip_path, backup_scope="all")

        # Restaura na mesma base onde já existe a sessão 101
        res = restore_shapes_backup(
            self.db,
            zip_path,
            restore_shapes=False,
            restore_sessions=True,
            session_conflict_strategy="import_new_id"
        )
        self.assertEqual(res.sessions_imported, 1)
        self.assertEqual(res.sessions_updated, 0)
        self.assertEqual(res.sessions_skipped, 0)

        # Deve agora haver 2 sessões no banco
        all_sessions = self.db.get_sessions()
        self.assertEqual(len(all_sessions), 2)
        session_ids = [s["id"] for s in all_sessions]
        self.assertIn(101, session_ids)
        new_id = [sid for sid in session_ids if sid != 101][0]
        self.assertGreater(new_id, 101)

        # Verifica se os layouts da nova sessão foram gravados corretamente
        layouts_new = self.db.get_session_layouts(new_id)
        self.assertEqual(len(layouts_new), 2)
        self.assertEqual(len(layouts_new[0]["pieces"]), 2)
        self.assertEqual(len(layouts_new[1]["pieces"]), 1)

    def test_restore_sessions_overwrite(self):
        """Testa restauração com estratégia overwrite."""
        zip_path = Path(self.temp_dir) / "backup_overwrite.zip"
        create_shapes_backup(self.db, zip_path, backup_scope="sessions_only")

        # Altera layers da sessão local
        for s in self.db.get_sessions():
            if s["id"] == 101:
                # Modifica localmente recriando com layers=99
                self.db.create_session(
                    session_id=101,
                    material_id="MAT_TESTE",
                    layers=99,
                    shapes=[],
                    placed_pieces=[]
                )

        res = restore_shapes_backup(
            self.db,
            zip_path,
            restore_shapes=False,
            restore_sessions=True,
            session_conflict_strategy="overwrite"
        )
        self.assertEqual(res.sessions_updated, 1)

        # Sessão 101 deve ter voltado para layers=2 (valor do backup)
        sessions_after = self.db.get_sessions()
        s101 = next(s for s in sessions_after if s["id"] == 101)
        self.assertEqual(s101["layers"], 2)
        layouts_after = self.db.get_session_layouts(101)
        self.assertEqual(len(layouts_after), 2)

    def test_restore_sessions_skip(self):
        """Testa restauração com estratégia skip ignorando sessões existentes."""
        zip_path = Path(self.temp_dir) / "backup_skip.zip"
        create_shapes_backup(self.db, zip_path, backup_scope="sessions_only")

        res = restore_shapes_backup(
            self.db,
            zip_path,
            restore_shapes=False,
            restore_sessions=True,
            session_conflict_strategy="skip"
        )
        self.assertEqual(res.sessions_skipped, 1)
        self.assertEqual(res.sessions_imported, 0)
        self.assertEqual(res.sessions_updated, 0)

    def test_restore_sessions_with_target_job(self):
        """Testa restauração de sessão direcionada para um Job customizado."""
        zip_path = Path(self.temp_dir) / "backup_job.zip"
        create_shapes_backup(self.db, zip_path, backup_scope="sessions_only")

        res = restore_shapes_backup(
            self.db,
            zip_path,
            restore_shapes=False,
            restore_sessions=True,
            session_conflict_strategy="import_new_id",
            target_job="JOB_RESTORED_CUSTOM"
        )
        self.assertEqual(res.sessions_imported, 1)

        all_sessions = self.db.get_sessions()
        restored = next(s for s in all_sessions if s["id"] != 101)
        self.assertEqual(restored["job"], "JOB_RESTORED_CUSTOM")

    def test_restore_sessions_into_empty_db(self):
        """Testa restauração completa de moldes e sessões em um banco limpo."""
        zip_path = Path(self.temp_dir) / "clean_restore.zip"
        create_shapes_backup(self.db, zip_path, backup_scope="all")

        # Cria banco totalmente novo e limpo
        clean_db_path = Path(self.temp_dir) / "clean_target.db"
        clean_db = DatabaseManager(db_path=str(clean_db_path), backend="sqlite")
        with clean_db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM layout_pieces")
            cur.execute("DELETE FROM layouts")
            cur.execute("DELETE FROM sessions")
            cur.execute("DELETE FROM shapes")
            cur.execute("DELETE FROM shape_folders")
            conn.commit()

        self.assertEqual(len(clean_db.get_all_shapes()), 0)
        self.assertEqual(len(clean_db.get_sessions()), 0)

        res = restore_shapes_backup(clean_db, zip_path, restore_shapes=True, restore_sessions=True)
        self.assertEqual(res.imported_new, 2)
        self.assertEqual(res.sessions_imported, 1)

        # Verifica dados no banco novo
        self.assertEqual(len(clean_db.get_all_shapes()), 2)
        clean_sessions = clean_db.get_sessions()
        self.assertEqual(len(clean_sessions), 1)
        restored_id = clean_sessions[0]["id"]
        restored_lays = clean_db.get_session_layouts(restored_id)
        self.assertEqual(len(restored_lays), 2)

    def test_scheduler_execute_backup_all(self):
        """Testa execução do agendador com backup_type='all'."""
        backup_dir = Path(self.temp_dir) / "sched_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        cfg = get_default_schedule_config()
        cfg["enabled"] = True
        cfg["backup_type"] = "all"
        cfg["backup_dir"] = str(backup_dir)
        cfg["max_retained_backups"] = 5
        save_schedule_config(self.db, cfg)

        res = execute_scheduled_backup(self.db, config=cfg, force=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["total_shapes"], 2)
        self.assertEqual(res["total_sessions"], 1)
        self.assertEqual(res["total_layouts"], 2)
        self.assertTrue(Path(res["target_file"]).exists())
        self.assertTrue(Path(res["target_file"]).name.startswith("backup_corteac_"))


if __name__ == "__main__":
    unittest.main()
