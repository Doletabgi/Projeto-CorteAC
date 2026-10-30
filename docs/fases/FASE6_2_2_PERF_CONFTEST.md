# RELATÓRIO TÉCNICO DE PERFORMANCE — FASE 6.2.2

**Projeto:** CorteAC / JobManager 2000 (Python Edition)  
**Missão:** Reduzir tempo da suíte de testes de 194 s para < 110 s sem reintroduzir o `PytestUnraisableExceptionWarning`  
**Fase:** 6.2.2 — Otimização do conftest.py  
**Status Oficial:** ✅ **APROVADA COM SUCESSO** (Tempo médio ~80,6 s, 0 warnings, 320 passed)  
**Revisor Externo:** DeepSeek  
**Data:** 30/10/2026  

---

## 1. Contexto e Motivação

Na Fase 6.2.1, o warning `PytestUnraisableExceptionWarning` (`RuntimeError: main thread is not in main loop`) foi neutralizado com um `tests/conftest.py` contendo uma fixture `autouse=True` e o hook `pytest_runtest_teardown`.

Apesar do sucesso técnico na eliminação do warning, a estratégia provocava:
$$\text{320 testes} \times 3 \text{ chamadas } gc.collect() = 960 \text{ coletas completas de geração 2}$$
Cada coleta em processo com objetos Tkinter e memória alocada custava ~110 ms, elevando o tempo total de execução da suíte de 85 s para **194,17 s** (aumento de 2,3×).

A Fase 6.2.2 teve como objetivo implementar a estratégia **"Session start + pre-concurrency" (Opção D)**, mantendo a purga determinística no thread principal apenas nos pontos críticos de transição, restaurando a performance da suíte para bem abaixo do limite de 110 s.

---

## 2. Baseline vs Otimizado

Execuções consecutivas com a suíte completa sob monitoramento de warnings estritos:

| Execução | Tempo Session | Tempo Real (Wall Clock) | Warnings | Passed / Skipped | Status |
|---|---:|---:|---:|---:|:---:|
| **Baseline (Fase 6.2.1)** | 194,17 s | 3m 14s | 0 | 320 / 1 | Referência |
| **Run 1 (otimizado)** | 79,29 s | 1m 20,813s (80,81 s) | 0 | 320 / 1 | ✅ Meta batida (<110 s) |
| **Run 2 (otimizado)** | 81,17 s | 1m 22,725s (82,72 s) | 0 | 320 / 1 | ✅ Meta batida (<110 s) |
| **Run 3 (otimizado)** | 81,42 s | 1m 22,952s (82,95 s) | 0 | 320 / 1 | ✅ Meta batida (<110 s) |
| **Ganho Líquido Médio** | **−113,54 s** | **−1m 52s (−58,5%)** | **0** | **Invariante** | **Excelente** |

---

## 3. Conftest.py Final

Arquivo: [tests/conftest.py](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/tests/conftest.py)

```python
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
```

---

## 4. Concurrency Isolado

Execução isolada de `tests/test_mysql_concurrency.py` com warning convertido em erro:

```bash
python3 -m pytest tests/test_mysql_concurrency.py -W error::pytest.PytestUnraisableExceptionWarning -v
```

### Output Oficial
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/dola/Documentos/clone do job/jobmanager-win10-python
collecting ... collected 2 items

tests/test_mysql_concurrency.py::TestMySQLConcurrency::test_01_intentional_concurrent_overwrite_conflict PASSED [ 50%]
tests/test_mysql_concurrency.py::TestMySQLConcurrency::test_02_load_8_clients_1000_layouts PASSED [100%]

============================== 2 passed in 15.24s ==============================
```
**Resultado:** 2 passed em 15.24s, 0 warnings.

---

## 5. Validação de ResourceWarning

Validação estrita de recursos órfãos na suíte global completa:

```bash
python3 -m pytest tests/ -W error::ResourceWarning
```

### Output Oficial
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/dola/Documentos/clone do job/jobmanager-win10-python
collecting ... collected 321 items

tests/test_company_logo_print.py ....                                    [  1%]
tests/test_db_layer.py ............                                      [  4%]
tests/test_dual_exporter.py ...s...                                      [  7%]
tests/test_exporter_tsp.py ...........                                   [ 10%]
tests/test_lay_parser.py .............                                   [ 14%]
tests/test_layers_pairs_nesting.py .....                                 [ 16%]
tests/test_layout_editor_fill.py .........................               [ 23%]
tests/test_layout_editor_shortcuts.py .................................. [ 34%]
.............................                                            [ 43%]
tests/test_layout_editor_trim.py .....                                   [ 45%]
tests/test_layout_editor_visual_regression.py .                          [ 45%]
tests/test_layout_print_legend.py ...........                            [ 48%]
tests/test_layout_print_material.py ..                                   [ 49%]
tests/test_macro_engine_ia_teste.py ............                         [ 53%]
tests/test_macro_engine_ia_teste_optimized.py .......                    [ 55%]
tests/test_material_import.py ............                               [ 59%]
tests/test_multisheet_nesting.py ...........................             [ 67%]
tests/test_mysql_concurrency.py ..                                       [ 68%]
tests/test_nesting_backend.py ........                                   [ 70%]
tests/test_nesting_contour_gap.py .......                                [ 72%]
tests/test_nesting_mode_architecture.py .........                        [ 75%]
tests/test_nfp.py ......                                                 [ 77%]
tests/test_semver.py .......                                             [ 79%]
tests/test_session_material_delete.py ......                             [ 81%]
tests/test_session_monotonic.py .......                                  [ 83%]
tests/test_shape_catalog_border_cases.py ...                             [ 84%]
tests/test_shape_catalog_polish.py ...........                           [ 88%]
tests/test_shape_catalog_view.py .........                               [ 90%]
tests/test_shape_editor_stitching.py ....                                [ 92%]
tests/test_shape_sorting.py .........                                    [ 95%]
tests/test_shapes_resto.py ..........                                    [ 98%]
tests/test_strategy_removal.py ......                                    [100%]

================== 320 passed, 1 skipped in 81.89s (0:01:21) ===================
```
**Resultado:** 100% verde, **zero ResourceWarnings**. Nenhum handle, conexão ou arquivo órfão.

---

## 6. Análise de Estabilidade e Auditoria

1. **Variação entre execuções consecutivas:**
   - Run 1: 79,29 s (real 80,81 s)
   - Run 2: 81,17 s (real 82,72 s)
   - Run 3: 81,42 s (real 82,95 s)
   - A variação máxima de tempo foi de **2,68%**, muito abaixo do teto de tolerância de 10%.
2. **Ausência absoluta de warnings:**
   - 0 warnings em todas as 3 execuções consecutivas.
   - 0 warnings na execução isolada de concorrência.
   - 0 warnings na execução com `-W error::ResourceWarning`.
3. **Preservação de Escopo e Regras de Ouro:**
   - Apenas `tests/conftest.py` foi alterado.
   - Zero linhas alteradas em `cad/*`, `ui/*`, `db/*`, `database.py`.
   - Banco de dados íntegro e backup `jobmanager.db.bak.20261030_0915` preservado.

---

## 7. Conclusão

A Fase 6.2.2 cumpriu rigorosamente todos os critérios de aceitação:
- Tempo reduzido de 194 s para **~80 s** (meta: < 110 s).
- 320 testes aprovados e 1 skipped em 3 runs consecutivas.
- Zero warnings.
- Sistema 100% estabilizado para a **Fase 6.3 (Validação em Fábrica)**.
