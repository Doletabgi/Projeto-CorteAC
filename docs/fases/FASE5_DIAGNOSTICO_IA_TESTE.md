# RELATÓRIO TÉCNICO DE DIAGNÓSTICO: MOTOR IA-TESTE (FASE 5.0)

**Projeto:** CorteAC / JobManager 2000 (Python Edition)  
**Missão:** Investigação Empírica de Gargalo e Viabilidade do Motor `IA-teste`  
**Fase:** Fase 5.0 — Diagnóstico Estrutural e Análise de Rendimento  
**Status da Fase:** Concluída com Sucesso (Zero alteração em código de produção)  
**Revisor Externo:** DeepSeek  
**Operador Humano:** Dola  
**Data da Avaliação:** 28/10/2026  

---

## 1. Sumário Executivo

O motor experimental `IA-teste` (`cad/macro_engine.py` / `OmniNestMacroEngine`) foi diagnosticado detalhadamente através de instrumentação analítica com `cProfile`, pstats e testes comparativos em 3 cenários industriais contra a referência de produção `flashnestsheet` (com `NfpBackend`).

### Principais Conclusões:
1. **Onde o tempo é gasto:** **74,8% do tempo exclusivo (tottime)** é consumido no cálculo de colisão SAT (`polygons_collide` e operações vetoriais built-in). Na hierarquia cumulativa, **77,9% do tempo (cumtime)** provém de `find_contact_coordinate_binary`, que realiza busca binária iterativa de contato horizontal testando SAT repetidamente contra a grade espacial (`SpatialGrid`). A inteligência artificial local (UCB1 Multi-Armed Bandit e AST SafeFormula) consome menos de **0,02 ms (< 0,01%)**, sendo completamente desprezível no tempo total.
2. **O que IA-teste entrega:** No cenário padrão industrial (`mixed_300`), o motor `IA-teste` atinge **69,56% de rendimento de área contra 55,65% do `flashnestsheet`**, um ganho massivo de **+13,91% de Yield** (superando com folga o gatilho contratual de +5%). Esse ganho empacotou 300 peças em **4 chapas em vez de 5 chapas**, economizando **1 chapa física inteira (20% de economia direta de matéria-prima)**.
3. **Comportamento em geometrias de alta densidade:** Em peças de calçados reais com >150 vértices (`small_shoes_50`), o `IA-teste` foi **1,96× MAIS RÁPIDO** que o `flashnestsheet` (6,76s vs 12,81s), pois evita a explosão combinatória da decomposição convexa da soma de Minkowski do NFP. Em peças grandes (`large_pieces_100`), foi **2,20× MAIS RÁPIDO** (243 ms vs 535 ms).
4. **Recomendação Técnica:** Aplicação estrita da **Opção C — Autorizar Fase 5.1 (Otimização do IA-teste)**, substituindo a busca binária SAT pelo algoritmo analítico NFP em contato horizontal e incorporando cache de transformações.

---

## 2. Comparativo Global dos 4 Motores (300 Peças, Samples Reais)

Executado via `tools/bench_ia_teste.py --pieces 300 --runs 3 --json`:

| Motor | Backend | Tempo Médio (ms) | Tempo Mediano (ms) | Chapas | Peças | Yield (%) | G00 Total (mm) | Status |
|---|---|---:|---:|:---:|:---:|---:|---:|:---:|
| `flashnestsheet` | `python` | 77,87 | 77,87 | 5 | 300 | 55,65% | 39.333,19 | Fallback Fase 0 |
| `flashnestsheet` | `nfp` | **16,81** | **16,81** | 5 | 300 | 55,65% | 40.025,48 | **Referência Produção** |
| `tape_a` | `nfp` | 28,46 | 28,46 | 5 | 300 | 55,65% | 40.890,75 | Fitas especializadas |
| **`IA-teste`** | `nfp` | **735,47** | **735,47** | **4** | **300** | **69,56%** | **41.558,03** | **+13,91% Yield (-1 chapa)** |

---

## 3. SEÇÃO A — Onde o Tempo é Gasto (Diagnóstico de Gargalo)

Perfilamento analítico executado com `tools/profile_ia_teste.py` sobre o `OmniNestMacroEngine` executando 300 peças (`samples/` reais).

### 3.1 Breakdown de Tempo Exclusivo (Tottime) — Soma 100,0%

| Componente Funcional | Arquivo / Módulo Principal | Chamadas | Tottime (ms) | % Tottime | Papel no Gargalo |
|---|---|---:|---:|---:|---|
| **SAT Colisão de Polígonos** | `cad/geometry.py:polygons_collide` + min/max/abs built-in | 267.432 | **1.095,96** | **74,8%** | **Gargalo Primário (> 30%)** |
| **Transformação de Contornos** | `cad/geometry.py:transform_contour` + rotação | 196.484 | **161,24** | **11,0%** | Re-cálculo trigonométrico sem cache |
| **Outros / Overhead Estrutural** | Dicts, lists, lookups internos do Python | Diversos | **106,98** | **7,3%** | Não-classificado (< 10%) |
| **Busca de Contato Horizontal** | `cad/geometry.py:find_contact_coordinate_binary` | 4.812 | **41,33** | **2,8%** | Loop de bisseção (overhead local) |
| **Grade Espacial (SpatialGrid)** | `cad/geometry.py:SpatialGrid` (insert / query_items) | 6.540 | **35,58** | **2,4%** | Indexação espacial O(1) |
| **Orquestração e Loop de Linhas** | `cad/macro_engine.py:run` + `nest_multi_sheet` | 15 | **17,34** | **1,2%** | Loop gerencial de chapas |
| **Gravidade Vetorial Contínua** | `cad/macro_engine.py:_apply_vector_gravity` | 300 | **3,70** | **0,3%** | Vetor de atração (-0.5, -1.0) |
| **Interlock Vertical de Linhas** | `cad/macro_engine.py:row_collides` | 148 | **2,64** | **0,2%** | Encaixe de dentes entre faixas |
| **IA Local / UCB1 Bandit / AST** | `cad/ai_learner.py` + `SafeFormulaEvaluator` | 12 | **0,02** | **0,0%** | Desprezível (< 0,01%) |
| **TOTAL** | — | — | **1.464,79** | **100,0%** | Perfilamento completo |

> **Gargalo Primário Identificado:** O teste de colisão SAT (`polygons_collide` e projeção de eixos) responde isoladamente por **74,8%** do processamento exclusivo do motor.

### 3.2 Hierarquia Cumulativa de Chamadas (Cumtime)

Analisando a árvore de chamadas (quem chama quem e acumula tempo):

```text
OmniNestMacroEngine.run (1.465 ms)
  │
  ├── nest_multi_sheet (1.465 ms)
  │     │
  │     ├── _apply_vector_gravity (166 ms - 11,3%)
  │     │     └── check_collision_against_placed -> polygons_collide
  │     │
  │     ├── row_collides (89 ms - 6,1%)
  │     │     └── polygons_collide
  │     │
  │     └── find_contact_coordinate_binary (1.141 ms - 77,9% do tempo total!)
  │           │
  │           └── check_collision_against_placed (1.099 ms)
  │                 │
  │                 └── polygons_collide (1.004 ms - 68,5% cumtime)
  │                       ├── builtins.min / builtins.max / builtins.abs
  │                       └── projeção vetorial nos eixos normais
  │
  └── transform_contour (189 ms - 12,9% cumtime)
        └── rotate_point (sin / cos trigonométrico)
```

### 3.3 Diagnóstico Físico do Porquê o IA-teste Gasta 735 ms
1. **Busca Binária vs Bump Analítico:** O `flashnestsheet` com NFP calcula diretamente o deslocamento $X$ onde a peça encosta na peça anterior via geometria analítica da soma de Minkowski ($O(1)$ após o polígono NFP estar construído). O `IA-teste`, por sua vez, usa uma busca binária numérica (`find_contact_coordinate_binary`), realizando de 10 a 16 iterações de bisseção por peça.
2. **Multiplicação Algébrica de SAT:** Cada iteração da busca binária invoca `check_collision_against_placed`, que consulta a grade espacial e dispara o Teorema dos Eixos Separadores (SAT) para 2 a 6 vizinhos. Para 300 peças, são **267.432 execuções de SAT completo**.
3. **Ausência de Cache de Rotação de Contornos:** O `IA-teste` recalcula `transform_contour` 196.484 vezes porque aplica micro-rotações (`JIGGLE` de -2° a +2°) sem armazenar o contorno transformado em cache memoizado.

---

## 4. SEÇÃO B — O Que o IA-teste Entrega de Melhor (Análise de Rendimento)

Resultados rigorosos obtidos com a ferramenta automatizada `tools/compare_ia_teste_yield.py` (`ia_teste_yield_comparison.json`):

### 4.1 Tabela Comparativa em 3 Cenários Industriais

| Cenário | Motor | Tempo (ms) | Chapas | Peças | Yield (%) | Delta Yield | G00 (mm) | Delta G00 | Veredito Yield ≥ +5% |
|---|---|---:|:---:|:---:|---:|:---:|---:|:---:|:---:|
| **`mixed_300`** | `flashnestsheet` (NFP)<br>**`IA-teste`** | 21,79<br>**735,06** | 5<br>**4** | 300<br>300 | 55,65%<br>**69,56%** | **+13,91%** | 40.025,48<br>41.558,03 | +3,83% | **SIM (+13,91%)**<br>*(1 chapa salva!)* |
| **`small_shoes_50`** | `flashnestsheet` (NFP)<br>**`IA-teste`** | 12.814,63<br>**6.765,66** | 1<br>1 | 50<br>50 | 16,04%<br>16,04% | 0,00% | 3.859,12<br>5.234,81 | +35,65% | NÃO (0,00%)<br>*(Ambos cabem em 1 chapa)* |
| **`large_pieces_100`** | `flashnestsheet` (NFP)<br>**`IA-teste`** | 535,17<br>**243,12** | 2<br>2 | 100<br>100 | 57,85%<br>57,85% | 0,00% | 15.187,62<br>16.022,65 | +5,50% | NÃO (0,00%)<br>*(Ambos cabem em 2 chapas)* |

### 4.2 Análise das Vitórias do IA-teste

#### 1. Economia Real de 1 Chapa Inteira em `mixed_300` (+13,91% de Yield)
- O `flashnestsheet` distribui as peças em faixas retilíneas com bounding boxes isoladas. Com 300 peças mistas (Gáspea, Biqueira e Lateral), o `flashnestsheet` consumiu **5 chapas completas** (12,0 m² de material) com Yield de **55,65%**.
- O `IA-teste`, através do escalonamento de grade (`GRID STAGGER shift_x=0.38`), gravidade vetorial 2D (`GRAVITY VECTOR(-0.5, -1.0)`) e encaixe fino (`JIGGLE` micro-ângulos), conseguiu entrelaçar as curvas côncavas e convexas dos cabedais.
- O resultado foi o empacotamento das 300 peças em apenas **4 chapas** (9,6 m² de material) com Yield de **69,56%**.
- **Impacto Financeiro na Fábrica:** Economia de **20% de couro/sintético** na ordem de corte. Em uma fábrica que corta 1.000 chapas/mês, isso representa 200 chapas economizadas.

#### 2. Vantagem Inesperada em Contornos Complexos (`small_shoes_50` e `large_pieces_100`)
- No cenário `small_shoes_50`, os contornos reais do banco de dados (`323_PalAcb_22a` a `25a`) possuem entre **150 e 185 vértices** por peça.
- O algoritmo NFP Minkowski entra em explosão de complexidade combinatorial durante a decomposição convexa do polígono em dezenas de triângulos/trapézios ($O(V^2)$ a $O(V^3)$), demorando **12,81 segundos**.
- O `IA-teste` executou o mesmo cenário em **6,76 segundos (1,96× mais rápido que o NFP)**, demonstrando que a grade espacial `SpatialGrid` combinada com SAT tem excelente resiliência contra saturação de vértices.
- Em `large_pieces_100`, o `IA-teste` concluiu em **243 ms**, sendo **2,20× mais rápido** que o `flashnestsheet` NFP (535 ms).

---

## 5. SEÇÃO C — Recomendação Técnica e Resposta aos Riscos

### 5.1 Decisão Formal: OPÇÃO C (Autorizar Fase 5.1 — Otimização)

Conforme os critérios estabelecidos pelo Revisor Externo DeepSeek na Seção 6 do Kickoff:
- *Critério 1:* "Se o ganho de Yield do IA-teste for ≥ 5% em qualquer cenário real -> Opção C: Autorizar Fase 5.1 (otimização)".
- **Evidência Comprovada:** O ganho no cenário padrão `mixed_300` foi de **+13,91% de Yield** (69,56% vs 55,65%), com eliminação de 1 chapa inteira (4 chapas vs 5 chapas).
- **Veredito:** O motor `IA-teste` possui valor de negócio industrial extraordinário e seu único impeditivo é a lentidão da busca binária SAT (735 ms). Deve ser otimizado na Fase 5.1.

---

### 5.2 Resposta aos 4 Riscos de Otimização

#### Risco 1: Determinismo do UCB1 Bandit
- **Auditoria do Código (`cad/ai_learner.py:suggest_optimized_macro_params`):**
  A fórmula implementada é estritamente matemática:
  $$\text{Score} = \bar{R}_i + c \sqrt{\frac{\ln(N)}{n_i}} \quad (c = 1.414)$$
- **Não há uso de números pseudo-aleatórios (`random` ou `random.choice`)**: A busca pelo melhor braço é puramente determinística sobre os registros da tabela `settings`.
- **Mitigação para Fase 5.1:** Para garantir determinismo reprodutível em testes e benchmarks, o seletor aceitará um flag `deterministic=True` ou congelará os braços do bandit quando executado em modo de teste automatizado.

#### Risco 2: Avaliação de AST / SafeFormula
- **Auditoria de Custo:** A avaliação de expressões AST consome **0,02 ms (0,00% do tottime)** em 300 peças. O avaliador `SafeFormulaEvaluator` já compila a AST via `ast.parse` previamente.
- **Conclusão:** Não requer otimização. Está seguro, isolado e com custo residual irrisório.

#### Risco 3: Necessidade de Sanity Pass Pós-Nesting
- Assim como adotado na promoção do `NfpBackend` na Fase 4, caso o `IA-teste` utilize bumping NFP analítico para acelerar o contato horizontal, um **Sanity Pass** de colisão zero ($O(N)$ via `SpatialGrid`) deve ser mantido como gate de segurança final.
- **Custo medido do Sanity Pass:** 0,08 ms para 300 peças. Risco zero de impacto no tempo total.

#### Risco 4: Trade-off de Complexidade e Manutenibilidade
- A otimização não exigirá reescrever a orquestração de macros nem a DSL.
- Bastará substituir o método interno `_find_best_horizontal_slot` / `find_contact_coordinate_binary` pela projeção analítica já existente em `cad/nfp.py:get_nfp_sliding_distance` ou contato direto via cache NFP.
- Adição de decimação de polígonos por Ramer-Douglas-Peucker (RDP) para peças com >50 vértices no NFP, resolvendo o gargalo de peças de alta densidade como o `small_shoes_50`.

---

## 6. Arquitetura Proposta para a Fase 5.1 (Alvo: < 30 ms com Yield 69,5%)

Para levar o `IA-teste` de 735 ms para **< 30 ms** mantendo o yield de 69,56%:

1. **Substituição da Busca Binária por NFP Bumping:** Eliminar as 267.000 chamadas a `polygons_collide` dentro de `find_contact_coordinate_binary`. O NFP analítico calcula a posição $X$ de contato em uma única operação geométrica.
2. **Cache de Contornos Rotacionados:** Memoizar rotações dos ângulos de macro (`angles(0, 180)` e jiggle `[-2, 2]`), eliminando 161 ms de `transform_contour`.
3. **Decimação RDP para Contornos Densos:** Reduzir contornos com >100 vértices para uma representação simplificada de ~30 vértices para cálculo de contato sem perder a precisão do corte final.

---

**Assinatura Técnica:**  
*Antigravity Agent (Implementador)*  
*Validação Externa: DeepSeek*  
*Data: 28/10/2026*
