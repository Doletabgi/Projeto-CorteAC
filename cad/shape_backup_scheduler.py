"""
JobManager 2000 / CorteAC (Python Edition)
CAD / DB: Agendador de Backup Automático de Moldes Cadastrados
Gerenciamento de rotinas programadas (diárias, semanais, por intervalo ou data/hora pontual),
política de retenção de arquivos, verificação periódica em segundo plano e persistência.
"""

import os
import sys
import json
import time
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable, Union

from config import BASE_DIR, APP_NAME, APP_VERSION
from cad.shape_backup import create_shapes_backup, BackupSummary

# Diretório padrão de backups automáticos de moldes
DEFAULT_BACKUPS_DIR = BASE_DIR / "backups" / "shapes"
DEFAULT_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

SETTING_KEY_SCHEDULE = "shape_backup_schedule_config"


def get_default_schedule_config() -> Dict[str, Any]:
    """Retorna o dicionário padrão de configuração de agendamento de backup."""
    return {
        "enabled": False,
        "mode": "daily",                     # "daily", "weekly", "interval", "specific_datetime"
        "times": ["18:00"],                  # Lista de horários do dia no formato "HH:MM"
        "days_of_week": [0, 1, 2, 3, 4],     # 0=Segunda, 1=Terça, ..., 4=Sexta (padrão Seg a Sex)
        "interval_hours": 4,                 # Para mode == "interval"
        "specific_datetime": "",             # Para mode == "specific_datetime" ("AAAA-MM-DD HH:MM")
        "backup_dir": str(DEFAULT_BACKUPS_DIR),
        "include_dies": True,
        "folder_filter": None,               # None para todos os moldes, ou lista de nomes de pastas
        "max_retained_backups": 10,          # Quantidade máxima de backups preservados (0 = ilimitado)
        "last_run_timestamp": "",            # Data/hora ISO da última execução bem-sucedida
        "last_run_status": "",               # "success" ou "error"
        "last_run_message": "",              # Mensagem de resumo da última execução
        "last_run_file": "",                 # Caminho do último arquivo de backup gerado
        "last_checked_minute": ""            # Auxiliar para evitar dupla execução no mesmo minuto
    }


def normalize_schedule_config(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Valida e completa campos faltantes na configuração fornecida."""
    defaults = get_default_schedule_config()
    if not isinstance(cfg, dict):
        return defaults

    result = dict(defaults)
    result.update(cfg)

    # Normaliza lista de horários (pode vir como string separada por vírgulas ou lista)
    raw_times = result.get("times")
    normalized_times = []
    if isinstance(raw_times, str):
        raw_times = [t.strip() for t in raw_times.split(",") if t.strip()]
    if isinstance(raw_times, (list, tuple)):
        for t in raw_times:
            if not isinstance(t, str):
                continue
            t_clean = t.strip()
            # Valida formato HH:MM
            try:
                parts = t_clean.split(":")
                if len(parts) == 2:
                    h, m = int(parts[0]), int(parts[1])
                    if 0 <= h <= 23 and 0 <= m <= 59:
                        normalized_times.append(f"{h:02d}:{m:02d}")
            except (ValueError, TypeError):
                continue
    if not normalized_times:
        normalized_times = ["18:00"]
    result["times"] = sorted(list(set(normalized_times)))

    # Normaliza dias da semana (0..6)
    raw_dow = result.get("days_of_week")
    normalized_dow = []
    if isinstance(raw_dow, (list, tuple)):
        for d in raw_dow:
            try:
                d_int = int(d)
                if 0 <= d_int <= 6 and d_int not in normalized_dow:
                    normalized_dow.append(d_int)
            except (ValueError, TypeError):
                continue
    if not normalized_dow:
        normalized_dow = [0, 1, 2, 3, 4]
    result["days_of_week"] = sorted(normalized_dow)

    # Normaliza interval_hours
    try:
        result["interval_hours"] = max(1, int(result.get("interval_hours", 4)))
    except (ValueError, TypeError):
        result["interval_hours"] = 4

    # Normaliza max_retained_backups
    try:
        result["max_retained_backups"] = max(0, int(result.get("max_retained_backups", 10)))
    except (ValueError, TypeError):
        result["max_retained_backups"] = 10

    # Normaliza backup_dir
    b_dir = str(result.get("backup_dir") or "").strip()
    if not b_dir:
        b_dir = str(DEFAULT_BACKUPS_DIR)
    result["backup_dir"] = b_dir

    return result


def get_schedule_config(db) -> Dict[str, Any]:
    """Obtém as configurações de agendamento salvas no banco de dados (ou retorna o padrão)."""
    if db and hasattr(db, "get_setting"):
        try:
            val = db.get_setting(SETTING_KEY_SCHEDULE)
            if val:
                parsed = json.loads(val)
                return normalize_schedule_config(parsed)
        except Exception as exc:
            print(f"[AVISO] Falha ao carregar configuração de agendamento de backup: {exc}")

    return get_default_schedule_config()


def save_schedule_config(db, config: Dict[str, Any]) -> Dict[str, Any]:
    """Salva a configuração normalizada de agendamento no banco de dados."""
    normalized = normalize_schedule_config(config)
    if db and hasattr(db, "set_setting"):
        try:
            json_str = json.dumps(normalized, ensure_ascii=False, indent=2)
            db.set_setting(SETTING_KEY_SCHEDULE, json_str)
        except Exception as exc:
            print(f"[ERRO] Falha ao persistir configuração de agendamento no banco: {exc}")
    return normalized


def get_next_scheduled_run(config: Dict[str, Any], now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Calcula a data e horário da próxima execução agendada a partir do instante `now`.
    Retorna None se o agendamento estiver desativado ou se não houver execução futura prevista.
    """
    cfg = normalize_schedule_config(config)
    if not cfg.get("enabled"):
        return None

    if now is None:
        now = datetime.now()

    mode = cfg.get("mode", "daily")

    if mode == "daily":
        times = cfg.get("times", ["18:00"])
        candidates: List[datetime] = []
        for t_str in times:
            h, m = map(int, t_str.split(":"))
            today_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if today_run > now:
                candidates.append(today_run)
            else:
                tomorrow_run = today_run + timedelta(days=1)
                candidates.append(tomorrow_run)
        return min(candidates) if candidates else None

    elif mode == "weekly":
        times = cfg.get("times", ["18:00"])
        allowed_days = set(cfg.get("days_of_week", [0, 1, 2, 3, 4]))
        candidates = []
        # Avalia os próximos 8 dias para garantir que pegamos a próxima ocorrência
        for day_offset in range(8):
            day_dt = now + timedelta(days=day_offset)
            if day_dt.weekday() in allowed_days:
                for t_str in times:
                    h, m = map(int, t_str.split(":"))
                    run_dt = day_dt.replace(hour=h, minute=m, second=0, microsecond=0)
                    if run_dt > now:
                        candidates.append(run_dt)
        return min(candidates) if candidates else None

    elif mode == "interval":
        interval_hours = cfg.get("interval_hours", 4)
        last_run_str = cfg.get("last_run_timestamp", "")
        if last_run_str:
            try:
                last_dt = datetime.fromisoformat(last_run_str)
                next_dt = last_dt + timedelta(hours=interval_hours)
                if next_dt <= now:
                    return now
                return next_dt
            except (ValueError, TypeError):
                return now
        return now

    elif mode == "specific_datetime":
        dt_str = (cfg.get("specific_datetime") or "").strip()
        if not dt_str:
            return None
        # Aceita formatos: "YYYY-MM-DD HH:MM", "YYYY-MM-DD HH:MM:SS", "DD/MM/YYYY HH:MM"
        target_dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
            try:
                target_dt = datetime.strptime(dt_str, fmt)
                break
            except ValueError:
                continue
        if target_dt is None:
            return None

        # Se já executou nessa data/hora pontual, não agenda mais
        last_run_str = cfg.get("last_run_timestamp", "")
        if last_run_str:
            try:
                last_dt = datetime.fromisoformat(last_run_str)
                if last_dt >= target_dt:
                    return None
            except Exception:
                pass

        return target_dt

    return None


def is_backup_due(config: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    """
    Verifica se um backup agendado deve ser executado no instante `now`.
    Garante proteção contra disparos duplicados dentro do mesmo minuto ou intervalo.
    """
    cfg = normalize_schedule_config(config)
    if not cfg.get("enabled"):
        return False

    if now is None:
        now = datetime.now()

    curr_minute_str = now.strftime("%Y-%m-%d %H:%M")
    last_minute_checked = cfg.get("last_checked_minute", "")
    if last_minute_checked == curr_minute_str:
        return False

    mode = cfg.get("mode", "daily")
    curr_time_str = now.strftime("%H:%M")

    if mode == "daily":
        times = cfg.get("times", ["18:00"])
        if curr_time_str in times:
            last_run_str = cfg.get("last_run_timestamp", "")
            if last_run_str:
                try:
                    last_dt = datetime.fromisoformat(last_run_str)
                    if last_dt.strftime("%Y-%m-%d %H:%M") == curr_minute_str:
                        return False
                except Exception:
                    pass
            return True
        return False

    elif mode == "weekly":
        allowed_days = set(cfg.get("days_of_week", [0, 1, 2, 3, 4]))
        if now.weekday() not in allowed_days:
            return False
        times = cfg.get("times", ["18:00"])
        if curr_time_str in times:
            last_run_str = cfg.get("last_run_timestamp", "")
            if last_run_str:
                try:
                    last_dt = datetime.fromisoformat(last_run_str)
                    if last_dt.strftime("%Y-%m-%d %H:%M") == curr_minute_str:
                        return False
                except Exception:
                    pass
            return True
        return False

    elif mode == "interval":
        interval_hours = cfg.get("interval_hours", 4)
        last_run_str = cfg.get("last_run_timestamp", "")
        if not last_run_str:
            return True
        try:
            last_dt = datetime.fromisoformat(last_run_str)
            elapsed_seconds = (now - last_dt).total_seconds()
            if elapsed_seconds >= (interval_hours * 3600):
                return True
        except (ValueError, TypeError):
            return True
        return False

    elif mode == "specific_datetime":
        dt_str = (cfg.get("specific_datetime") or "").strip()
        if not dt_str:
            return False
        target_dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
            try:
                target_dt = datetime.strptime(dt_str, fmt)
                break
            except ValueError:
                continue
        if target_dt is None:
            return False

        if now >= target_dt:
            last_run_str = cfg.get("last_run_timestamp", "")
            if last_run_str:
                try:
                    last_dt = datetime.fromisoformat(last_run_str)
                    if last_dt >= target_dt:
                        return False
                except Exception:
                    pass
            return True
        return False

    return False


def apply_retention_policy(backup_dir: Union[str, Path], max_keep: int = 10) -> int:
    """
    Aplica a política de retenção no diretório de backups automáticos.
    Mantém os `max_keep` arquivos mais recentes com prefixo 'backup_moldes_' e exclui os mais antigos.
    Se max_keep <= 0, mantém todos. Retorna a contagem de arquivos excluídos.
    """
    if max_keep <= 0:
        return 0

    p_dir = Path(backup_dir)
    if not p_dir.exists() or not p_dir.is_dir():
        return 0

    backup_files = []
    for f in p_dir.iterdir():
        if f.is_file() and f.name.startswith("backup_moldes_") and (f.suffix.lower() in (".zip", ".csh")):
            try:
                backup_files.append((f.stat().st_mtime, f))
            except Exception:
                continue

    # Ordena pelo mais recente primeiro
    backup_files.sort(key=lambda x: x[0], reverse=True)

    removed_count = 0
    if len(backup_files) > max_keep:
        to_delete = backup_files[max_keep:]
        for _, f_path in to_delete:
            try:
                f_path.unlink()
                removed_count += 1
            except Exception as exc:
                print(f"[AVISO] Falha ao remover backup antigo {f_path.name}: {exc}")

    return removed_count


def list_backup_history(backup_dir: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Retorna a lista dos backups existentes no diretório informado, ordenados do mais recente ao mais antigo.
    """
    p_dir = Path(backup_dir)
    if not p_dir.exists() or not p_dir.is_dir():
        return []

    results = []
    for f in p_dir.iterdir():
        if f.is_file() and (f.suffix.lower() in (".zip", ".csh")):
            try:
                st = f.stat()
                results.append({
                    "filename": f.name,
                    "filepath": str(f.resolve()),
                    "size_bytes": st.st_size,
                    "size_display": f"{st.st_size / 1024:.1f} KB" if st.st_size < 1048576 else f"{st.st_size / (1024 * 1024):.2f} MB",
                    "mtime": st.st_mtime,
                    "date_display": datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
                })
            except Exception:
                continue

    results.sort(key=lambda x: x["mtime"], reverse=True)
    return results


def execute_scheduled_backup(
    db,
    config: Optional[Dict[str, Any]] = None,
    force: bool = False,
    on_progress: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    Executa a rotina de backup agendado.
    Gera o arquivo compactado no diretório configurado, aplica a retenção e atualiza
    as informações da última execução no banco.
    """
    if config is None:
        config = get_schedule_config(db)
    else:
        config = normalize_schedule_config(config)

    now = datetime.now()
    if not force and not is_backup_due(config, now=now):
        return {
            "success": False,
            "skipped": True,
            "message": "Nenhum backup agendado devido no momento."
        }

    backup_dir = Path(config.get("backup_dir") or DEFAULT_BACKUPS_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = now.strftime("%Y-%m-%d_%H-%M-%S")
    target_filename = f"backup_moldes_{timestamp_str}.zip"
    target_file = backup_dir / target_filename

    folder_filter = config.get("folder_filter")
    include_dies = bool(config.get("include_dies", True))

    try:
        summary: BackupSummary = create_shapes_backup(
            db=db,
            target_file=target_file,
            folder_filter=folder_filter,
            include_die_files=include_dies,
            on_progress=on_progress
        )

        # Aplica retenção
        max_keep = config.get("max_retained_backups", 10)
        purged = apply_retention_policy(backup_dir, max_keep=max_keep)

        # Atualiza status e horário na configuração
        config["last_run_timestamp"] = now.isoformat()
        config["last_run_status"] = "success"
        config["last_run_file"] = str(target_file.resolve())
        config["last_run_message"] = (
            f"Backup gerado com sucesso: {summary.total_shapes} moldes, "
            f"{summary.total_folders} pastas ({summary.file_size_bytes / 1024:.1f} KB)."
        )
        config["last_checked_minute"] = now.strftime("%Y-%m-%d %H:%M")

        save_schedule_config(db, config)

        return {
            "success": True,
            "skipped": False,
            "target_file": str(target_file.resolve()),
            "total_shapes": summary.total_shapes,
            "total_folders": summary.total_folders,
            "file_size_bytes": summary.file_size_bytes,
            "purged_old_files": purged,
            "message": config["last_run_message"]
        }

    except Exception as exc:
        err_msg = f"Erro ao executar backup agendado: {exc}"
        config["last_run_timestamp"] = now.isoformat()
        config["last_run_status"] = "error"
        config["last_run_message"] = err_msg
        config["last_checked_minute"] = now.strftime("%Y-%m-%d %H:%M")
        save_schedule_config(db, config)

        return {
            "success": False,
            "skipped": False,
            "error": err_msg,
            "message": err_msg
        }


class ShapeBackupScheduler:
    """
    Serviço em segundo plano gerenciador do agendamento de backups.
    Executa verificação periódica leve a cada `check_interval_seconds` sem onerar
    ou travar a interface gráfica do CorteAC.
    """

    def __init__(
        self,
        db,
        on_backup_completed: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_backup_error: Optional[Callable[[str], None]] = None,
        check_interval_seconds: int = 30
    ):
        self.db = db
        self.on_backup_completed = on_backup_completed
        self.on_backup_error = on_backup_error
        self.check_interval_seconds = max(5, check_interval_seconds)

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._is_running_backup = False

    def start(self):
        """Inicia o thread de monitoramento em segundo plano."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._worker_loop,
                name="CorteAC-ShapeBackupScheduler",
                daemon=True
            )
            self._thread.start()

    def stop(self, timeout: float = 2.0):
        """Sinaliza parada para o worker thread e aguarda término gracioso."""
        self._stop_event.set()
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=timeout)
                self._thread = None

    def check_once(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        Executa uma verificação pontual. Se houver backup devido (ou se force=True),
        dispara a execução. Retorna o resultado da execução ou None se ignorado.
        """
        with self._lock:
            if self._is_running_backup:
                return None
            self._is_running_backup = True

        try:
            cfg = get_schedule_config(self.db)
            if not force and not is_backup_due(cfg):
                return None

            result = execute_scheduled_backup(self.db, config=cfg, force=force)
            if result.get("success"):
                if self.on_backup_completed:
                    try:
                        self.on_backup_completed(result)
                    except Exception as cb_exc:
                        print(f"[AVISO] Falha no callback de backup concluído: {cb_exc}")
            elif not result.get("skipped"):
                if self.on_backup_error:
                    try:
                        self.on_backup_error(result.get("error", "Erro desconhecido"))
                    except Exception as cb_exc:
                        print(f"[AVISO] Falha no callback de erro de backup: {cb_exc}")
            return result
        finally:
            with self._lock:
                self._is_running_backup = False

    def _worker_loop(self):
        """Loop contínuo de monitoramento em segundo plano."""
        while not self._stop_event.is_set():
            try:
                self.check_once(force=False)
            except Exception as exc:
                print(f"[AVISO] Exceção no ciclo do agendador de backup de moldes: {exc}")

            # Aguarda o intervalo ou interrupção de término
            self._stop_event.wait(self.check_interval_seconds)
