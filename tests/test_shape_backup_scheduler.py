"""
Testes automatizados para o motor e interface de agendamento de backup automático de moldes.
"""

import os
import shutil
import tempfile
import unittest
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path

from database import DatabaseManager
from cad.shape_backup import create_shapes_backup
from cad.shape_backup_scheduler import (
    get_default_schedule_config,
    normalize_schedule_config,
    get_schedule_config,
    save_schedule_config,
    get_next_scheduled_run,
    is_backup_due,
    apply_retention_policy,
    list_backup_history,
    execute_scheduled_backup,
    ShapeBackupScheduler
)
from ui.shape_backup_restore_dialog import ShapeBackupRestoreDialog


class TestShapeBackupScheduler(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_corteac_sched_")
        self.db_path = Path(self.temp_dir) / "test_sched.db"
        self.db = DatabaseManager(db_path=str(self.db_path), backend="sqlite")

        # Cria moldes de teste
        fld_id = self.db.create_shape_folder("Pasta Agendada")
        self.db.create_shape(
            name="Molde_Sched_01",
            folder="Pasta Agendada",
            contour=[{"x": 0.0, "y": 0.0}, {"x": 50.0, "y": 0.0}, {"x": 50.0, "y": 50.0}, {"x": 0.0, "y": 50.0}],
            holes=[]
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_and_normalize_config(self):
        defaults = get_default_schedule_config()
        self.assertFalse(defaults["enabled"])
        self.assertEqual(defaults["mode"], "daily")
        self.assertIn("18:00", defaults["times"])
        self.assertEqual(defaults["max_retained_backups"], 10)

        # Testa normalização com dados variados
        custom = {
            "enabled": True,
            "mode": "weekly",
            "times": " 08:30 , 14:00, 99:99 ",  # 99:99 deve ser descartado
            "days_of_week": [0, 2, 4, 10],      # 10 deve ser descartado
            "interval_hours": "6",
            "max_retained_backups": "5"
        }
        normalized = normalize_schedule_config(custom)
        self.assertTrue(normalized["enabled"])
        self.assertEqual(normalized["mode"], "weekly")
        self.assertEqual(normalized["times"], ["08:30", "14:00"])
        self.assertEqual(normalized["days_of_week"], [0, 2, 4])
        self.assertEqual(normalized["interval_hours"], 6)
        self.assertEqual(normalized["max_retained_backups"], 5)

    def test_save_and_load_schedule_config(self):
        cfg = get_default_schedule_config()
        cfg["enabled"] = True
        cfg["mode"] = "daily"
        cfg["times"] = ["12:00", "18:00"]
        cfg["backup_dir"] = str(Path(self.temp_dir) / "backups")

        saved = save_schedule_config(self.db, cfg)
        loaded = get_schedule_config(self.db)

        self.assertTrue(loaded["enabled"])
        self.assertEqual(loaded["mode"], "daily")
        self.assertEqual(loaded["times"], ["12:00", "18:00"])
        self.assertEqual(loaded["backup_dir"], str(Path(self.temp_dir) / "backups"))

    def test_is_backup_due_daily(self):
        cfg = get_default_schedule_config()
        cfg["enabled"] = True
        cfg["mode"] = "daily"
        cfg["times"] = ["14:30"]

        now_match = datetime(2026, 11, 10, 14, 30, 15)
        now_mismatch = datetime(2026, 11, 10, 14, 31, 0)

        self.assertTrue(is_backup_due(cfg, now=now_match))
        self.assertFalse(is_backup_due(cfg, now=now_mismatch))

        # Se já executou no mesmo minuto, não deve disparar novamente
        cfg["last_run_timestamp"] = datetime(2026, 11, 10, 14, 30, 5).isoformat()
        self.assertFalse(is_backup_due(cfg, now=now_match))

        # Se desativado, nunca dispara
        cfg["enabled"] = False
        self.assertFalse(is_backup_due(cfg, now=now_match))

    def test_is_backup_due_weekly(self):
        cfg = get_default_schedule_config()
        cfg["enabled"] = True
        cfg["mode"] = "weekly"
        cfg["days_of_week"] = [0, 2, 4]  # Seg (0), Qua (2), Sex (4)
        cfg["times"] = ["18:00"]

        # 2026-11-09 é Segunda-feira (weekday == 0)
        segunda_1800 = datetime(2026, 11, 9, 18, 0, 0)
        # 2026-11-10 é Terça-feira (weekday == 1)
        terca_1800 = datetime(2026, 11, 10, 18, 0, 0)

        self.assertTrue(is_backup_due(cfg, now=segunda_1800))
        self.assertFalse(is_backup_due(cfg, now=terca_1800))

    def test_is_backup_due_interval(self):
        cfg = get_default_schedule_config()
        cfg["enabled"] = True
        cfg["mode"] = "interval"
        cfg["interval_hours"] = 3

        now = datetime(2026, 11, 10, 12, 0, 0)
        # Sem última execução: deve executar imediatamente
        self.assertTrue(is_backup_due(cfg, now=now))

        # Última execução há 2 horas: não deve executar
        cfg["last_run_timestamp"] = (now - timedelta(hours=2)).isoformat()
        self.assertFalse(is_backup_due(cfg, now=now))

        # Última execução há 3 horas e 5 minutos: deve executar
        cfg["last_run_timestamp"] = (now - timedelta(hours=3, minutes=5)).isoformat()
        self.assertTrue(is_backup_due(cfg, now=now))

    def test_is_backup_due_specific_datetime(self):
        cfg = get_default_schedule_config()
        cfg["enabled"] = True
        cfg["mode"] = "specific_datetime"
        cfg["specific_datetime"] = "2026-11-15 10:00"

        before = datetime(2026, 11, 15, 9, 59, 0)
        after = datetime(2026, 11, 15, 10, 0, 5)

        self.assertFalse(is_backup_due(cfg, now=before))
        self.assertTrue(is_backup_due(cfg, now=after))

        # Se já executou nessa data pontual, não repete
        cfg["last_run_timestamp"] = datetime(2026, 11, 15, 10, 0, 1).isoformat()
        self.assertFalse(is_backup_due(cfg, now=after))

    def test_get_next_scheduled_run(self):
        cfg = get_default_schedule_config()
        cfg["enabled"] = True
        cfg["mode"] = "daily"
        cfg["times"] = ["12:00", "18:00"]

        now = datetime(2026, 11, 10, 10, 0, 0)
        next_run = get_next_scheduled_run(cfg, now=now)
        self.assertEqual(next_run, datetime(2026, 11, 10, 12, 0, 0))

        now_afternoon = datetime(2026, 11, 10, 19, 0, 0)
        next_run_tomorrow = get_next_scheduled_run(cfg, now=now_afternoon)
        self.assertEqual(next_run_tomorrow, datetime(2026, 11, 11, 12, 0, 0))

    def test_apply_retention_policy_and_history(self):
        bdir = Path(self.temp_dir) / "retention_test"
        bdir.mkdir(parents=True, exist_ok=True)

        base_time = datetime(2026, 11, 10, 10, 0, 0)
        created_files = []
        for i in range(7):
            fpath = bdir / f"backup_moldes_2026-11-10_10-0{i}-00.zip"
            fpath.write_text("fake zip content", encoding="utf-8")
            mtime = (base_time + timedelta(minutes=i)).timestamp()
            os.utime(fpath, (mtime, mtime))
            created_files.append(fpath)

        self.assertEqual(len(list_backup_history(bdir)), 7)

        # Retém apenas os 4 mais recentes (deve apagar 3)
        purged = apply_retention_policy(bdir, max_keep=4)
        self.assertEqual(purged, 3)

        remaining = list_backup_history(bdir)
        self.assertEqual(len(remaining), 4)
        # O mais recente deve ser o minuto 06
        self.assertTrue(remaining[0]["filename"].endswith("10-06-00.zip"))

    def test_execute_scheduled_backup_real(self):
        bdir = Path(self.temp_dir) / "auto_backups"
        cfg = get_default_schedule_config()
        cfg["enabled"] = True
        cfg["backup_dir"] = str(bdir)
        cfg["max_retained_backups"] = 3

        res = execute_scheduled_backup(self.db, config=cfg, force=True)
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["total_shapes"], 1)
        self.assertTrue(Path(res["target_file"]).exists())

        # Verifica persistência no banco
        loaded = get_schedule_config(self.db)
        self.assertEqual(loaded["last_run_status"], "success")
        self.assertTrue(loaded["last_run_timestamp"])

    def test_scheduler_background_service(self):
        bdir = Path(self.temp_dir) / "sched_srv_test"
        cfg = get_default_schedule_config()
        cfg["enabled"] = True
        cfg["backup_dir"] = str(bdir)
        save_schedule_config(self.db, cfg)

        completed_events = []

        def _on_comp(res):
            completed_events.append(res)

        scheduler = ShapeBackupScheduler(
            db=self.db,
            on_backup_completed=_on_comp,
            check_interval_seconds=1
        )
        scheduler.start()

        # Executa uma verificação forçada
        res = scheduler.check_once(force=True)
        self.assertIsNotNone(res)
        self.assertTrue(res.get("success"))
        self.assertEqual(len(completed_events), 1)

        scheduler.stop()

    def test_ui_dialog_initial_tab_schedule(self):
        root = tk.Tk()
        root.withdraw()
        try:
            dlg = ShapeBackupRestoreDialog(root, db=self.db, initial_tab=2)
            self.assertEqual(dlg.notebook.index(dlg.notebook.select()), 2)
            self.assertIsNotNone(dlg.lbl_sched_badge)
            self.assertIsNotNone(dlg.tree_hist)
            dlg.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
