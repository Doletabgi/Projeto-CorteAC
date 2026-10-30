# RELATÓRIO TÉCNICO — FASE 5.0b: VERIFICAÇÃO DE "FRESH LEARNING"

**Projeto:** CorteAC / JobManager 2000 (Python Edition)  
**Missão:** Determinar se o ganho de yield do motor `IA-teste` depende de aprendizado acumulado ou é intrínseco do motor  
**Fase:** 5.0b — Verificação de "Fresh Learning"  
**Data:** 29/10/2026  
**Veredito Oficial:** `MOTOR_INTRINSIC`  
**Diagnóstico da Curva de Aprendizado:** `FLAT` (constante em 69,56%)  

---

## 1. Sumário Executivo

A Fase 5.0b teve como objetivo isolar a causa do ganho de **+13,91 pontos percentuais** de rendimento (yield) obtido pelo motor `IA-teste` em comparação ao baseline analítico `flashnestsheet` (NfpBackend) no cenário industrial `mixed_300` (69,56% vs 55,65%).

A dúvida arquitetural fundamental para a Fase 5.2 era:
- **Cenário A (Motor Puro):** O algoritmo de macro declarativa com agrupamento em pares antiparalelos (`CLUSTER PAIR angles(0, 180)`), escalonamento em grade (`GRID STAGGER shift_x(0.38)`), gravidade vetorial contínua com busca binária de contato (`GRAVITY VECTOR(-0.5, -1.0)`), micro-rotações (`JIGGLE`) e preenchimento de vazios (`FILL HOLES`) entrega 69,56% de yield de forma puramente algorítmica e determinística, sem depender de histórico em banco de dados.
- **Cenário B (Aprendizado Acumulado):** O motor necessita de dados históricos gravados nas chaves de aprendizado da tabela `settings` (`ai_operator_habits`, `ai_bandit_*`) originados de `learn_from_operator_save` (Ctrl+S manual) ou calibração UCB1 para atingir alto yield, caindo para patamares próximos a 55% em uma fábrica nova com banco zerado.

### Conclusão Definitiva
Os testes executados comprovaram de forma conclusiva o **Cenário A**:
1. Em banco 100% zerado (`fresh`, sem nenhuma chave `ai_*`), o motor `IA-teste` atinge **exatamente 69,56% de yield**, consumindo **4 chapas** (contra 5 chapas do NFP).
2. Em todos os 5 estados avaliados (`fresh`, `10 ops`, `50 ops`, `100 ops` e `fully_trained`), o rendimento permaneceu rigorosamente constante em **69,56%** (curva `flat`).
3. O veredito oficial é **`MOTOR_INTRINSIC`**. Não há necessidade de fallback por falta de dados históricos nem de contadores de aquecimento na interface ("Aprendendo X/Y operações"). O Modo "Automático" da Fase 5.2 pode empregar `IA-teste` desde o Day-1.

---

## 2. Metodologia de Medição e Isolamento

Para garantir confiabilidade científica e zero impacto na produção:
1. **Backup Físico:** Realizado backup pontual do banco SQLite de produção (`jobmanager.db.bak.fresh_test.20261029_0945`).
2. **Snapshot de Configurações:** Registrado snapshot completo de todas as 28 chaves da tabela `settings` em `tools/fresh_test/settings_snapshot.json`.
3. **Identificação de Chaves de IA:** Mapeadas as chaves persistidas pelo módulo `cad/ai_learner.py`:
   - `ai_operator_habits`: Vetores espaciais e pares frequentes aprendidos no Ctrl+S pelo operador.
   - `ai_bandit_<FAMILIA>`: Estatísticas de braços do algoritmo Multi-Armed Bandit UCB1 (ex: `ai_bandit_COMPACTA_SOLA_CALCANHAR`, `ai_bandit_TIRA_LONGA`).
4. **Instrumentação Dedicada:**
   - `tools/verify_fresh_learning.py`: Mede o desempenho em DB limpo comparando contra baseline NFP e restaura o banco.
   - `tools/compare_learning_states.py`: Avalia o motor em 5 estados sintéticos de aprendizado com repetições configuráveis.
5. **Restauração e Verificação:** Ao término de todos os experimentos, o banco foi restaurado bit-a-bit do backup (`cmp` com saída 0) e a suíte completa de testes (`pytest tests/`) rodou 100% verde (277 passed, 1 skipped).

---

## 3. Seção A — Resultado Fresh vs Trained

Comparativo detalhado no cenário padrão industrial `mixed_300` (300 peças de calçado: gáspeas, biqueiras e laterais sobre chapas de 2000 x 1200 mm com gap de 1,0 mm e margens de 10,0 mm):

| Métrica | Baseline `flashnestsheet` (NFP) | `IA-teste` Fresh (DB Zerado) | `IA-teste` Fully-Trained (Produção) | Δ Fresh vs NFP | Δ Trained vs Fresh |
|---|---:|---:|---:|---:|---:|
| **Rendimento (Yield %)** | **55,65%** | **69,56%** | **69,56%** | **+13,91%** | **0,00%** |
| **Tempo de Execução** | 22,27 ms | 716,48 ms | 1006,97 ms | +694,21 ms | +290,49 ms |
| **Chapas Utilizadas** | 5 chapas | 4 chapas | 4 chapas | **-1 chapa** | 0 chapas |
| **Peças Posicionadas** | 300 / 300 | 300 / 300 | 300 / 300 | 100% | 100% |
| **Percurso Vazio G00 (mm)** | 40.025,48 mm | 41.558,03 mm | 41.936,70 mm | +1.532,55 mm | +378,67 mm |

### Veredito da Seção A
$$\Delta \text{Yield}_{\text{Fresh vs NFP}} = +13,91\% \ge +5,0\% \implies \mathbf{MOTOR\_INTRINSIC}$$

**Análise técnica:** O ganho substancial de rendimento (+13,91% de área útil aproveitada e redução de 5 para 4 chapas industriais) é integralmente gerado pela pipeline algorítmica do `OmniNestMacroEngine`. O motor limpo entrega exatamente o mesmo rendimento de uma instalação veterana.

---

## 4. Seção B — Curva de Aprendizado

Medição do rendimento em 5 estados de maturação com 3 execuções independentes por estado:

| Estado do Banco | Descrição | Yield % | Δ vs Estado Anterior | Tempo Médio (ms) | Chapas | G00 Total (mm) |
|---|---|---:|---:|---:|---:|---:|
| **1. Fresh** | Zero chaves de IA (DB limpo de fábrica nova) | 69,56% | — | 696,12 ms | 4 | 41.834,80 mm |
| **2. 10 ops** | 10 hábitos simulados + 10 trials UCB1 | 69,56% | +0,00% | 742,73 ms | 4 | 41.709,53 mm |
| **3. 50 ops** | 50 hábitos simulados + 50 trials UCB1 | 69,56% | +0,00% | 725,09 ms | 4 | 41.709,53 mm |
| **4. 100 ops** | 100 hábitos simulados + 100 trials UCB1 | 69,56% | +0,00% | 753,05 ms | 4 | 41.709,53 mm |
| **5. Fully-trained** | Banco original (28 trials acumulados) | 69,56% | +0,00% | 1006,97 ms | 4 | 41.936,70 mm |

### Gráfico Textual da Curva de Aprendizado (ASCII)

```text
Yield (%)
  75 |
     |
  70 |  69.56%    69.56%    69.56%    69.56%    69.56%
     |  [====]----[====]----[====]----[====]----[====]  <-- MOTOR_INTRINSIC (FLAT)
  65 |
     |
  60 |
     |
  55 |  55.65% (Baseline flashnestsheet NFP)
     |  ..............................................
  50 |
     +---------------------------------------------------
       Fresh     10 ops    50 ops    100 ops   Fully-Trained
```

### Diagnóstico da Curva
$$\text{Classificação: } \mathbf{FLAT}$$

**Por que a curva é flat?**
1. **Classificação Geométrica:** Todas as peças de `mixed_300` pertencem à família industrial `COMPACTA_SOLA_CALCANHAR`.
2. **Avaliação dos Braços do Bandit:** No `cad/ai_learner.py`, os 5 braços possíveis do Bandit UCB1 para essa família são:
   - Braço 0: Equilibrado Padrão (`shift_x=0.38, grav=[-0.5, -1.0], sweep=3.0, steps=[8, 4, 2, 0.5]`)
   - Braço 1: Alta Compactação Direcional (`shift_x=0.50, grav=[-0.8, -1.0], sweep=2.0, steps=[10, 5, 2, 0.5]`)
   - Braço 2: Varredura Angular Ampliada (`shift_x=0.25, grav=[-0.3, -1.0], sweep=4.0, steps=[6, 3, 1, 0.5]`)
   - Braço 3: Passo Fino Rápido (`shift_x=0.45, grav=[-1.0, -1.0], sweep=1.5, steps=[8, 4, 2, 1.0]`)
   - Braço 4: Gravidade Vertical Estrita (`shift_x=0.30, grav=[0.0, -1.0], sweep=5.0, steps=[8, 4, 2, 0.5]`)
   
   A avaliação isolada de cada um dos 5 braços sobre a geometria do `mixed_300` revelou que **todos os 5 braços produzem exatamente 69,56% de rendimento com 4 chapas**.
3. **Braço Exploratório Inicial (Fresh):** No estado `fresh` (sem histórico), o UCB1 seleciona deterministicamente o **Braço 0**, cujos parâmetros coincidem perfeitamente com os valores padrão da DSL `DEFAULT_IA_TESTE_MACRO`.
4. **Independência de Hábitos no Nesting Automático:** O método `learn_from_operator_save` persiste pares de moldes em `ai_operator_habits` para referência no CAD/LayoutEditorView, mas o motor multi-placas `OmniNestMacroEngine` guia o posicionamento estrito via heurística de empacotamento vetorial e zero colisão SAT, sem depender de memória externa de pares.

---

## 5. Seção C — Implicações para Arquitetura 4 Camadas (Fase 5.2)

O resultado `MOTOR_INTRINSIC` simplifica expressivamente o design do **Modo Automático** na Fase 5.2:

1. **Zero Período de Aquecimento (No Warm-up Period):**
   - Não é necessário implementar contadores de operações como `THRESHOLD = 50`.
   - Fábricas novas ou instalações portáteis em pendrive obtêm o benefício de +13,91% de yield imediatamente no primeiro corte.
2. **Interface Limpa:**
   - Não há necessidade de exibir mensagens transitórias como `"Aprendendo: X/Y operações — usando NFP"`.
   - A UI pode reportar diretamente: `"Modo Automático: Motor IA-teste Ativo (Alta Densidade)"`.
3. **Fallback Resiliente e Objetivo:**
   - O `NfpBackend` permanece como fallback estritamente de **segurança de runtime**: caso ocorra qualquer timeout ou exceção inesperada durante a execução da macro, o sistema transiciona de forma transparente para `flashnestsheet` (NFP).
4. **Zero Complexidade Adicional:**
   - A arquitetura dispensa lógica condicional baseada no número de registros em banco.

### Dicionário `MODES` Proposto para a Fase 5.2

```python
MODES = {
    "auto": {
        "engine": "ia_teste",
        "strategy": "flashnestsheet",
        "params": "macro_default",
        "ui_message": None,
        "description": "Otimização autônoma de máximo rendimento via motor macro vetorial (Day-1)",
    },
    "fast": {
        "engine": "nfp",
        "strategy": "flashnestsheet",
        "params": "FastNest",
        "ui_message": None,
        "description": "Cálculo instantâneo em milissegundos via No-Fit Polygon analítico",
    },
    "economic": {
        "engine": "nfp",
        "strategy": "flashnestsheet",
        "params": "HighYield",
        "ui_message": None,
        "description": "NFP analítico com refinamento de giro e contato máximo",
    },
    "tapes": {
        "engine": "nfp",
        "strategy": "tape_a",
        "params": "stdNOTFill",
        "ui_message": None,
        "description": "Alinhamento especializado em faixas e tiras contínuas",
    },
    "remnants": {
        "engine": "nfp",
        "strategy": "freenest",
        "params": "stdNOTFill",
        "ui_message": None,
        "description": "Aproveitamento livre em retalhos e áreas irregulares de couro",
    },
}
```

---

## 6. Confirmação de Integridade e Restauração do Banco

- **Snapshot de Referência:** `tools/fresh_test/settings_snapshot.json` (28 chaves conferidas).
- **Restauração Bit-a-Bit:** O arquivo `jobmanager.db` foi restaurado a partir de `jobmanager.db.bak.fresh_test.20261029_0945`.
- **Validação de Conteúdo:** O script de auditoria confirmou 0 diferenças em chaves e 0 diferenças em valores.
- **Validação Binária:** `cmp jobmanager.db jobmanager.db.bak.fresh_test.20261029_0945` retornou código de saída 0 (idêntico byte a byte).
- **Suíte de Testes de Regressão:** `python3 -m pytest tests/` executado com êxito:
  ```text
  ============ 277 passed, 1 skipped, 2 warnings in 126.05s (0:02:06) ============
  ```
- **Integridade de Produção:** Nenhuma linha de código em `cad/*.py`, `ui/*.py` ou `database.py` foi modificada.

---

## 7. Conclusão da Fase 5.0b

A missão da Fase 5.0b foi cumprida com 100% dos critérios de aceite satisfeitos. Está formalmente comprovado que o rendimento de 69,56% do motor `IA-teste` é **intrínseco ao algoritmo**.

A Fase 5.1 (Profiling e Otimização do IA-teste para atingir latência < 200 ms) e a Fase 5.2 (Implementação dos 5 Modos Industriais de Fábrica) podem prosseguir com segurança máxima.
