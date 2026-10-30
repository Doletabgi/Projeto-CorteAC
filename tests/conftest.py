"""
tests/conftest.py

Configurações e fixtures globais do pytest para o JobManager 2000.
Estratégia otimizada: 'Session start + pre-concurrency' (Fase 6.2.2).
Elimina as 960 chamadas de gc.collect() da fixture autouse/teardown por teste,
executando a limpeza apenas nos momentos estritamente necessários:
1) No início da sessão (pytest_sessionstart)
2) Imediatamente antes dos testes concorrentes multithread (pytest_runtest_setup)
"""
import gc
import pytest


def pytest_sessionstart(session):
    """Purga lixo Tkinter acumulado antes da suite iniciar.

    Executado uma única vez na thread principal.
    """
    gc.collect()


def pytest_runtest_setup(item):
    """Purga lixo Tkinter ANTES de testes que criam threads secundárias.

    Só dispara para o teste de concorrência MySQL, que é o único que
    cria threads onde o GC cíclico pode invocar Variable.__del__ fora
    da thread principal.
    """
    if "test_mysql_concurrency" in item.nodeid:
        gc.collect()
