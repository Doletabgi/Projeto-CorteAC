"""
tests/conftest.py

Configurações e fixtures globais do pytest para o JobManager 2000 / CorteAC.
Estratégia otimizada: 'Session start + pre-concurrency' (Fase 6.2.2) + Isolamento de Banco.
- Purga lixo Tkinter nos momentos estritamente necessários.
- Isola o banco de dados jobmanager.db durante a execução dos testes via backup e restauração automática,
  garantindo que execuções de testes nunca deixem poluição de layouts ou sessões no ambiente de produção.
"""
import gc
import os
import shutil
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "jobmanager.db"
BACKUP_PATH = ROOT_DIR / "jobmanager.db.pytest_backup"
_DB_EXISTED_AT_START = False


def pytest_sessionstart(session):
    """Purga lixo Tkinter e realiza backup de segurança do banco antes de iniciar a suite."""
    global _DB_EXISTED_AT_START
    gc.collect()

    if DB_PATH.exists():
        _DB_EXISTED_AT_START = True
        try:
            shutil.copy2(DB_PATH, BACKUP_PATH)
        except Exception as exc:
            print(f"[AVISO pytest] Falha ao criar backup de jobmanager.db: {exc}")
    else:
        _DB_EXISTED_AT_START = False


def pytest_runtest_setup(item):
    """Purga lixo Tkinter ANTES de testes que criam threads secundárias.

    Só dispara para o teste de concorrência MySQL, que é o único que
    cria threads onde o GC cíclico pode invocar Variable.__del__ fora
    da thread principal.
    """
    if "test_mysql_concurrency" in item.nodeid:
        gc.collect()


def pytest_sessionfinish(session, exitstatus):
    """Restaura o banco de dados ao estado original limpo e remove arquivos residuais de teste."""
    gc.collect()

    if _DB_EXISTED_AT_START and BACKUP_PATH.exists():
        try:
            shutil.copy2(BACKUP_PATH, DB_PATH)
            BACKUP_PATH.unlink(missing_ok=True)
        except Exception as exc:
            print(f"[AVISO pytest] Falha ao restaurar backup de jobmanager.db: {exc}")
    elif not _DB_EXISTED_AT_START and DB_PATH.exists():
        DB_PATH.unlink(missing_ok=True)

    # Limpa arquivos temporários test_*.db criados eventualmente por testes
    for tmp_file in ROOT_DIR.glob("test_*.db*"):
        try:
            tmp_file.unlink(missing_ok=True)
        except Exception:
            pass
