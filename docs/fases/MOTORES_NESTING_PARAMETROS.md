# Manual Técnico: Estratégias de Corte e Motores de Parâmetros de Nesting (JobManager / ATOM FlashCut)

Este documento descreve detalhadamente o funcionamento, a lógica matemática, a arquitetura industrial e as recomendações de uso para todas as **Estratégias de Nesting** e todos os **Motores / Perfis de Parâmetros** disponíveis no **JobManager 2000 (Python Edition)** e no ecossistema original **ATOM FlashCut / DieProc dp98**.

---

## 1. Visão Geral da Aba Geral da Sessão

Na interface de produção (`SessionView`), o operador dispõe de dois seletores interdependentes fundamentais:

```text
+-------------------------------------------------------------------------+
| Estratégia:                                                             |
| [ sint                 |v]                                              |
|   tape_a                                                                |
|   flashnestsheet                                                        |
|   freenest                                                              |
|                                                                         |
| Parâmetros:                                                             |
| [ FastNest             |v]  [ DieProc Cfg... ]                          |
|   HighYield                                                             |
|   stdNOTFill                                                            |
|   stdFill                                                               |
|   PrmSss_35                                                             |
+-------------------------------------------------------------------------+
```

### Qual a diferença entre Estratégia e Parâmetros?
* **A Estratégia** define o **tipo de material e a geometria física da mesa de corte**: se é chapa fechada, placa retangular, fitas lineares estreitas ou encaixe livre em retalhos (a fábrica opera 100% com chapas/placas).
* **Os Parâmetros (Motores)** definem a **agressividade do cálculo e a regra de produção**: se o algoritmo deve calcular instantaneamente, se deve buscar o aproveitamento máximo no milímetro, se deve parar na quantidade exata pedida ou se deve lotar a chapa inteira para estoque.

---

## 2. As Estratégias de Nesting

---

### 2.1. `sint` (Sintéticos em Chapas e Placas com Linhas Uniformes)

* **Conceito Industrial**: Motor de corte contínuo desenvolvido especificamente para materiais sintéticos regulares (laminados, PVC, PU, sintéticos expandidos, palmilhas e solados).
* **Como Funciona**:
  * **Organização em Fileiras Retilíneas**: Todas as peças de uma mesma linha compartilham uma linha de base comum perfeitamente alinhada e nivelada. Isso é essencial para que o cabeçote de corte da máquina ATOM trabalhe em velocidade contínua linear, sem movimentos em vazio no ar.
  * **Geminação 0° / 180°**: Alterna as peças adjacentes invertidas a 180° para que as curvas do calcanhar e da ponta se encaixem perfeitamente.
  * **Contour Bumping Exato de 1.0 mm**: Utiliza busca binária submilimétrica para encostar as peças contorno a contorno com folga estrita de $1.0\text{ mm}$ (sem folgas exageradas de bounding box e com zero colisões).
  * **Intertravamento Vertical de Linhas**: A aproximação entre linhas inteiras penetra nas curvas das peças da linha anterior.
* **Quando Utilizar**:
  * Solados, palmilhas e cortes de calçados em chapas sintéticas ou placas onde se exige corte veloz, organizado em fileiras limpas e sem desvios.

---

### 2.2. `tape_a` (Tiras, Debruns, Fitas e Correias Estreitas)

* **Conceito Industrial**: Motor linear especializado para peças extremamente compridas e estreitas (*Tapes & Ribbons*), como tiras de sandálias, debruns, vivos, passadores, correias e tirantes.
* **Como Funciona**:
  * **Alinhamento Unidirecional Fixo**: Trava a rotação das tiras em ângulo fixo (geralmente paralelo ao eixo da chapa).
  * **Passo Linear Constante**: Avança as tiras lado a lado com espaçamento estritamente uniforme.
  * **Prevenção de Distorção por Arrasto**: Ao cortar peças compridas e finas, rotações variadas ou curvas inclinadas fariam a lâmina vibrar ou puxar o material, gerando variação de largura na ponta da tira. O alinhamento paralelo linear elimina esse problema.
* **Quando Utilizar**:
  * Tiras finas, debruns, atacadores planos, correias e tirantes onde a largura precisa ser 100% calibrada e idêntica de ponta a ponta.

---

### 2.3. `flashnestsheet` (Chapas Retangulares com Tecnologia DieProc dp98)

* **Conceito Industrial**: A estratégia clássica da ATOM para chapas e placas regulares (*Sheets*) com dimensões físicas fechadas (ex: placas de borracha 1000x1000 mm, chapas de microduro 1200x900 mm ou EVA 1500x1000 mm).
* **Como Funciona**:
  * **Integração com DieProc**: Aplica as matrizes de acoplamento (*Coupling*), varredura angular (*Range*) e tolerâncias configuradas na tela oficial `DieProc configuration`.
  * **Limites de Mesa (X e Y Fechados)**: Respeita as margens de borda da placa e calcula quantas peças cabem exatamente na área retangular física.
  * **Preenchimento de Cavidades (*Hole-Filling*)**: Se a chapa contiver peças grandes com espaços ocos (como moldes em formato de "C" ou "U"), a estratégia identifica esses espaços e encaixa moldes menores lá dentro.
* **Quando Utilizar**:
  * Qualquer corte em placas ou chapas soltas de sintético, borracha, EVA, recouro ou cartão de palmilha.

---

### 2.4. `freenest` (Nesting Livre / Geometria Orgânica e Retalhos)

* **Conceito Industrial**: Motor de encaixe livre baseado em heurística poligonal e gravidade geométrica bidimensional, sem a rigidez de matrizes ou linhas fixas.
* **Como Funciona**:
  * **Atratores de Espaço Livre (*Bottom-Left Placement*)**: Cada nova peça é lançada na chapa buscando o menor ponto de gravidade livre (canto inferior esquerdo) e girando em busca do melhor contato de superfície.
  * **Multipeças Heterogêneas**: Excelente quando há mistura de múltiplos moldes completamente diferentes em tamanho e formato (ex: 10 solas, 20 tiras pequenas, 15 calcanhares e 8 biqueiras na mesma sessão).
  * **Reaproveitamento de Sobras (*Remainder Nest*)**: Ideal para cortar em cima de retalhos irregulares que sobraram de produções anteriores.
* **Quando Utilizar**:
  * Prototipagem rápida, corte de coleções com muitas peças mistas de tamanhos diferentes, ou quando o material possui formato irregular / retalhos.

> [!NOTE]
> **Nota sobre Bobinas Contínuas (`flashnestroll`)**: A estratégia para bobinas contínuas com esteira rolante foi removida do sistema, uma vez que a fábrica opera exclusivamente com corte em chapas e placas sintéticas.

---

### Resumo Comparativo das Estratégias

| Estratégia | Tipo de Material / Suporte | Disposição no Layout | Comportamento do Cabeçote | Melhor Aplicação |
|---|---|---|---|---|
| **`sint`** | Chapas e Placas Sintéticas | Fileiras retilíneas geminadas (0°/180°) | Trajetória linear contínua | Solados, palmilhas e calçados em geral |
| **`tape_a`** | Fitas e Tiras em Chapa/Placa | Tiras paralelas lineares em passo fixo | Trajetória paralela uniforme | Debruns, vivos, correias e tirantes |
| **`flashnestsheet`** | Placas e Chapas Fechadas | Grade DieProc com *Hole-Filling* | Otimizado para área retangular | Chapas de borracha, EVA, recouro e PVC |
| **`freenest`** | Chapas, Retalhos e Peças Mistas | Orgânico livre (busca de espaços vazios) | Gravidade espacial e atratores | Protótipos, peças sortidas e retalhos |

---

## 3. Os Motores de Parâmetros de Nesting

Os motores de parâmetros atuam sobre a estratégia escolhida, determinando as regras de busca matemática e o destino das peças.

---

### 3.1. `FastNest` (Encaixe Rápido / Foco em Velocidade de Processamento)

* **Conceito**: Velocidade máxima de cálculo para início imediato do corte.
* **Lógica Técnica**:
  * Desativa a varredura angular fina (`range1_from = 0.0, range1_to = 0.0, range1_step = 0.0`).
  * Utiliza ângulos base fixos diretos (0° e 180° alternados).
  * Margem de segurança rápida, reduzindo ciclos de colisão.
* **Aplicação**: Ordens com milhares de peças onde o operador não pode esperar cálculo demorado na máquina.

---

### 3.2. `HighYield` (Alto Rendimento / Máximo Aproveitamento)

* **Conceito**: Extrair o menor refugo possível (*scrap* mínimo), economizando cada milímetro de material nobre.
* **Lógica Técnica**:
  * Executa varredura fina de tolerância angular de $-5.0^\circ$ a $+5.0^\circ$ em passos de $0.5^\circ$.
  * Ativa obrigatoriamente o intertravamento entre linhas (*Row Interlock*).
  * Em couro irregular (`flashnestleather`), testa até 8 direções de corte simultâneas (0°, 45°, 90°, 135°, 180°, etc.).
* **Aplicação**: Materiais de alto custo por metro quadrado (couros caros, sintéticos nobres, borrachas especiais).

---

### 3.3. `stdNOTFill` (Standard NOT Fill / Padrão com Parada Estrita)

* **Conceito**: Parada estrita ao atingir a quantidade exata do pedido (*Fill Layout = None* na ATOM).
* **Lógica Técnica**:
  * Limita as peças posicionadas rigorosamente ao `target_count` solicitado na ordem de produção.
  * Interrompe o cálculo imediatamente, deixando qualquer sobra de chapa em branco para reaproveitamento posterior.
* **Aplicação**: Pedidos fechados e personalizados sob encomenda, sem sobras para estoque.

---

### 3.4. `stdFill` (Standard Fill / Padrão com Preenchimento Total da Chapa)

* **Conceito**: Modo almoxarifado/estoque (*Fill Layout = Always/Last* na ATOM).
* **Lógica Técnica**:
  * Ao atingir a cota da ordem, continua encaixando peças extras até esgotar toda a área útil física da chapa.
* **Aplicação**: Placas onde a sobra seria jogada no lixo; as peças extras são estocadas para pedidos futuros.

---

### 3.5. `PrmSss_35` (Preset ATOM / Sintéticos e Solas com Fio Direcional)

* **Conceito**: Preset clássico de fábrica ATOM (*Synthetic / Sole / Standard 3.5mm*).
* **Lógica Técnica**:
  * Trava o acoplamento em sentido paralelo unidirecional (`coupling = "0/0"`).
  * Garante que todas as peças respeitem o sentido da trama, textura, estampa ou brilho do material sintético.
* **Aplicação**: Materiais laminados com textura orientada (camurça sintética, estampa direcional, verniz).

---

## 4. Matriz de Combinações Recomendadas

| Se o seu objetivo na fábrica for... | Escolha esta Estratégia | E escolha este Parâmetro |
|---|---|---|
| **Corte padrão de solados em chapa sintética com pedido exato** | **`sint`** | **`stdNOTFill`** |
| **Corte de solas aproveitando 100% da chapa para estoque** | **`sint`** | **`stdFill`** |
| **Corte de tiras finas, debruns ou correias** | **`tape_a`** | **`stdNOTFill`** |
| **Material com textura/brilho que não pode girar** | **`sint`** ou **`flashnestsheet`** | **`PrmSss_35`** |
| **Aproveitar sobras e retalhos com peças sortidas** | **`freenest`** | **`stdNOTFill`** |
