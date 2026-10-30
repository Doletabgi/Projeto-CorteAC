# ANÁLISE DE WARNING DO PYTEST — FASE 6.2

**Projeto:** CorteAC / JobManager 2000 (Python Edition)  
**Documento:** Análise e Diagnóstico de Warning Persistente  
**Data:** 30/10/2026  
**Revisor Externo:** DeepSeek  

---

## 1. Identificação do Warning

Nas Fases 6.0, 6.1 e 6.1.1, a execução global de `pytest tests/` reportou consistentemente `1 warning`:

```text
=============================== warnings summary ===============================
tests/test_mysql_concurrency.py::TestMySQLConcurrency::test_02_load_8_clients_1000_layouts
  /home/dola/.local/lib/python3.12/site-packages/_pytest/unraisableexception.py:63: PytestUnraisableExceptionWarning: Exception ignored in: <function Variable.__del__ at 0x7f4ac9ecb4c0>
  
  Traceback (most recent call last):
    File "/usr/lib/python3.12/tkinter/__init__.py", line 410, in __del__
      if self._tk.getboolean(self._tk.call("info", "exists", self._name)):
                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  RuntimeError: main thread is not in main loop
```

---

## 2. Diagnóstico Detalhado

### 2.1 Categoria do Warning
- **Categoria:** `PytestUnraisableExceptionWarning` (captura exceções ignoradas pelo interpretador Python dentro de métodos `__del__`).
- **NÃO é `ResourceWarning`:** O teste de execução estrita com `pytest -W error::ResourceWarning` passou com $100\%$ de sucesso (nenhum descritor de arquivo, conexão de banco ou socket órfão).
- **NÃO é `DeprecationWarning`:** Nenhuma API obsoleta do Python ou Tkinter foi utilizada.

### 2.2 Teste que Dispara
- **Arquivo:** `tests/test_mysql_concurrency.py`
- **Método:** `TestMySQLConcurrency.test_02_load_8_clients_1000_layouts`
- **Fato Notável:** Quando `test_mysql_concurrency.py` é executado **isoladamente** (`pytest tests/test_mysql_concurrency.py`), **zero warnings** são emitidos (`2 passed in 13.04s`). O warning só ocorre quando a suíte completa é executada sequencialmente.

### 2.3 Causa Raiz
1. Testes de interface gráfica executados anteriormente na suíte (`test_layout_editor_*.py`) instanciam controles Tkinter que utilizam `tk.BooleanVar` e `tk.StringVar`.
2. Ao finalizar os testes de UI, alguns objetos `tk.Variable` permanecem em memória aguardando o ciclo do coletor de lixo (*cyclic garbage collector* do CPython).
3. Quando `test_02_load_8_clients_1000_layouts` inicia, ele dispara 8 threads simultâneas para simular 8 terminais de corte gerando 1.000 requisições concorrentes no MySQL/SQLite.
4. O interpretador Python aciona uma rodada de garbage collection durante a execução de uma das **threads secundárias** (não a thread principal).
5. O coletor de lixo invoca `Variable.__del__` do Tkinter a partir dessa thread de trabalho.
6. Como o Tkinter/Tcl é *single-threaded*, `self._tk.call("info", "exists", self._name)` rejeita chamadas de fora da thread da UI com `RuntimeError: main thread is not in main loop`.
7. O interpretador ignora a exceção porque ocorreu dentro de `__del__`, e o Pytest a intercepta como `PytestUnraisableExceptionWarning`.

---

## 3. Impacto Operacional e Risco

- **Impacto em Produção (Jornada de 8h):** **NULO (Zero risco)**.
  - Em produção real, o aplicativo roda em loop de eventos da thread principal (`mainloop`). As threads secundárias (ex: nesting ou consultas pesadas de banco) não instanciam nem desalocam widgets Tkinter.
  - A concorrência em produção opera sobre conexões de banco (`DatabaseManager`) desacopladas da interface gráfica.
- **Vazamento de Recursos:** Não há retenção contínua de memória; os objetos são devidamente liberados pelo GC logo em seguida.

---

## 4. Ação Tomada

- **Classificação:** Warning inofensivo de finalização de thread em ambiente de testes unitários sintéticos.
- **Resolução:** 
  - Adicionado `gc.collect()` no ciclo de limpeza da suíte para que a coleta de variáveis Tkinter ocorra deterministicamente na thread principal antes do teste de estresse de 8 threads.
  - Status: **Identificado, diagnosticado e documentado** sem necessidade de alterar o núcleo do sistema CAD ou de banco de dados.
