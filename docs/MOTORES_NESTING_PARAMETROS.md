# Manual Técnico: Motores e Perfis de Parâmetros de Nesting (JobManager / ATOM FlashCut)

Este documento descreve detalhadamente o funcionamento, a lógica matemática, a arquitetura industrial e as recomendações de uso para cada um dos motores/perfis de encaixe (*Nesting Parameters*) disponíveis no **JobManager 2000 (Python Edition)** e no ecossistema original **ATOM FlashCut / DieProc**.

---

## 1. Contexto e Localização no Sistema

Na aba **Geral** da Janela de Sessão de Produção (`SessionView`), o seletor de parâmetros de nesting permite ao operador definir a estratégia de posicionamento automático das peças sobre a chapa ou rolo:

```text
+-------------------------------------------------------------+
| Parâmetros de Nesting:                                      |
| [ FastNest             |v]  [ DieProc Cfg... ]              |
|   HighYield                                                 |
|   stdNOTFill                                                |
|   stdFill                                                   |
|   PrmSss_35                                                 |
+-------------------------------------------------------------+
```

Esses perfis controlam parâmetros fundamentais do motor de cálculo 2D:
- **Acoplamento de Rotação (*Coupling*)**: se peças adjacentes podem girar em direções opostas (0°/180°), paralelas (0°/0°) ou perpendiculares (0°/90°).
- **Varredura Angular Fina (*Range Sweep*)**: intervalo e passo de micro-rotação para encontrar o menor envelope geométrico.
- **Intertravamento entre Linhas (*Row Interlock*)**: se as curvas das peças de linhas vizinhas se entrelaçam denteadamente.
- **Preenchimento de Fim de Chapa (*Fill Layout*)**: se a máquina para ao atingir a quantidade encomendada ou preenche a chapa inteira para estoque.

---

## 2. Detalhamento de Cada Motor / Perfil

---

### 2.1. `FastNest` (Encaixe Rápido / Foco em Velocidade de Processamento)

* **Conceito Industrial**: Perfil otimizado para **velocidade máxima de cálculo**, projetado para quando a prioridade do operador é iniciar o corte imediatamente sem esperar processamento longo da CPU.
* **Comportamento Algorítmico**:
  * **Varredura Angular Desativada**: Define `range1_from = 0.0`, `range1_to = 0.0` e `range1_step = 0.0`. Não executa loops de micro-rotação angular (evita calcular centenas de trigonometrias desnecessárias).
  * **Acoplamento Padrão Direto**: Alterna diretamente entre 0° e 180° (`coupling = "0/0 0/180"`).
  * **Resolução Geométrica**: Utiliza margem de segurança ligeiramente mais ampla, reduzindo o número de iterações de busca de contato.
  * **Tempo de Cálculo**: Quase instantâneo (frações de segundo mesmo para centenas de peças).
* **Quando Utilizar**:
  * Ordens de produção volumosas com prazos de entrega imediatos.
  * Peças com formatos geométricos simples ou retangulares, onde micro-rotações não gerariam ganho significativo de área.
  * Máquinas de corte onde o operador precisa iniciar o trabalho sem filas de espera de cálculo.

---

### 2.2. `HighYield` (Alto Rendimento / Máximo Aproveitamento de Material)

* **Conceito Industrial**: Perfil voltado para a **extração máxima de área útil**, minimizando o refugo (*scrap*). Indicado quando a matéria-prima tem alto valor agregado e economizar frações percentuais representa economia financeira expressiva.
* **Comportamento Algorítmico**:
  * **Varredura Angular Submilimétrica**: Executa varredura de tolerância de $-5.0^\circ$ a $+5.0^\circ$ em passos finos de $0.5^\circ$ (`range1_from = -5.0`, `range1_to = 5.0`, `range1_step = 0.5`), testando mais de 20 rotações por par para achar o encaixe mais compacto.
  * **Intertravamento entre Linhas (*Row Interlock*)**: Ativado obrigatoriamente (`row_interlock = True`). As reentrâncias e saliências das linhas consecutivas penetram umas nas outras contorno a contorno.
  * **Otimização de Preenchimento de Vãos (*Hole-Filling*)**: Em ordens multiformas (ex: solas acompanhadas de biqueiras, saltos ou alças), peças secundárias de menor área são inseridas automaticamente dentro dos espaços ocos deixados pelas peças principais.
  * **Multidireção para Couro**: Na estratégia `flashnestleather`, testa até 8 direções simultâneas de assentamento (`[0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°]`).
* **Quando Utilizar**:
  * Couros legítimos, peles nobres e sintéticos especiais de alto custo por metro quadrado.
  * Peças com curvaturas acentuadas (solados esportivos, sapatilhas, gáspeas de botas) com grande potencial de intertravamento.

---

### 2.3. `stdNOTFill` (Standard NOT Fill / Padrão com Parada Estrita)

* **Origem ATOM**: É a predefinição padrão (*Standard*) original da ATOM onde o parâmetro **Fill Layout = None** está configurado no diálogo de parâmetros do fabricante (`dlgParamsFlashNest.gif`).
* **Conceito Industrial**: Produção sob encomenda rigorosa. A máquina de corte deve cortar **estritamente o número de pares programado na ordem**, interrompendo o cálculo assim que a meta é atingida.
* **Comportamento Algorítmico**:
  * O limite de peças (`max_pieces`) é fixado exatamente em `target_count` (quantidade de pares solicitada na ordem de produção).
  * Ao completar a quantidade programada, o motor finaliza o layout imediatamente.
  * Qualquer espaço restante no final da chapa ou do rolo é deixado em branco, podendo ser cortado posteriormente como retalho reaproveitável (*Remainder*).
* **Quando Utilizar**:
  * Produções personalizadas ou encomendas exclusivas onde peças excedentes representariam custo de material parado em estoque.
  * Produções com controle rigoroso de rastreabilidade de lote por par.

---

### 2.4. `stdFill` (Standard Fill / Padrão com Preenchimento Total da Chapa)

* **Origem ATOM**: Predefinição oficial da ATOM correspondente à opção **Fill Layout = Always / Last** documentada no manual do JobManager 2000.
* **Conceito Industrial**: Modo "Corte para Almoxarifado / Estoque". Ao alimentar uma chapa inteira na mesa de corte, o operador deseja que a área física seja **100% preenchida**, evitando sobras pequenas e inúteis que acabariam descartadas na caçamba de lixo.
* **Comportamento Algorítmico**:
  * O motor ignora a interrupção ao atingir o `target_count` inicial e continua encaixando peças adicionais (`max_pieces` expandido até o limite da placa/chapa).
  * Continua replicando os moldes do artigo até esgotar a área útil disponível na chapa.
  * O sumário da sessão aponta a quantidade de peças excedentes geradas para envio ao estoque.
* **Quando Utilizar**:
  * Chapas de EVA, recouro, microduro e borrachas prensadas onde o retalho final não teria tamanho suficiente para reaproveitamento.
  * Artigos de alto giro comercial na fábrica (peças padrão que sempre serão consumidas em lotes futuros).

---

### 2.5. `PrmSss_35` (Preset de Produção ATOM / Sintéticos e Solas com Sentido do Fio)

* **Origem ATOM**: Predefinição clássica nativa incluída de fábrica no instalador da ATOM Itália (*Prm* = Parameters, *Sss* = *Synthetic / Sole / Standard*, *_35* = espessura de 3.5 mm ou modelo de faca/matriz #35).
* **Conceito Industrial**: Projetado para materiais sintéticos com **direção de fibra, textura, estampa ou brilho orientados**, onde as peças não podem sofrer rotação transversal.
* **Comportamento Algorítmico**:
  * Configura **acoplamento paralelo unidirecional** (`coupling = "0/0"`), impedindo rotações em 90° ou 270°.
  * Mantém o alinhamento de corte rigorosamente paralelo ao sentido de laminação da bobina ou da chapa.
  * Evita que um pé do calçado fique com brilho ou tonalidade diferente do outro pé, preservando a uniformidade estética e a resistência à flexão mecânica do calçado montado.
* **Quando Utilizar**:
  * Materiais laminados sintéticos com textura direcional (imitando veio de madeira, camurça escovada, verniz refletivo ou fibra de carbono).
  * Solas de borracha ou EVA que possuem estrias ou ranhuras que precisam coincidir na direção do caminhar.

---

## 3. Tabela Comparativa Resumida

| Perfil / Motor | Rotação Permitida | Varredura Angular | Fim de Chapa (*Fill Layout*) | Velocidade | Rendimento | Foco Principal |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **`FastNest`** | 0° / 180° | Desativada ($0^\circ$) | Respeita Ordem (`None`) | ⚡ Instantâneo | Bom | Tempo mínimo de espera |
| **`HighYield`** | 0° / 180° + multiângulos | Fina ($-5^\circ$ a $+5^\circ$, passo $0.5^\circ$) | Respeita Ordem (`None`) | ⏱️ Detalhado | 🏆 Máximo | Menor refugo em materiais caros |
| **`stdNOTFill`** *(Padrão)* | Configuração padrão | Padrão | **Para estritamente** na cota | 🚀 Rápido | Equilibrado | Pedidos fechados sem sobras |
| **`stdFill`** | Configuração padrão | Padrão | **Lota a chapa inteira** | 🚀 Rápido | 🏆 Pleno | Aproveitamento total de chapas |
| **`PrmSss_35`** | Sentido Unidirecional (0°/0°) | Fio Longitudinal | Respeita Ordem (`None`) | 🚀 Rápido | Otimizado | Textura, brilho e veio direcional |

---

## 4. Guia Rápido de Escolha para o Operador

1. **"Estou cortando um pedido fechado e não posso gastar material a mais":**
   $\rightarrow$ Selecione **`stdNOTFill`**.
2. **"Coloquei uma chapa inteira e quero que corte até o final para aproveitar tudo pro almoxarifado":**
   $\rightarrow$ Selecione **`stdFill`**.
3. **"O material é caro (couro / sintético nobre) e preciso do melhor encaixe denteado possível":**
   $\rightarrow$ Selecione **`HighYield`**.
4. **"O operador está com pressa na máquina e temos 5.000 peças simples para calcular agora":**
   $\rightarrow$ Selecione **`FastNest`**.
5. **"O material tem textura/estampa com sentido marcado que não pode sair de lado":**
   $\rightarrow$ Selecione **`PrmSss_35`**.
