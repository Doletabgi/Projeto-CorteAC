# Relatório Técnico Completo da Arquitetura, Motores e Código do Sistema

> **Projeto**: JobManager 2000 (Python Edition) / *teste_dola*  
> **Finalidade**: Sistema CAD/CAM de Gestão, Aninhamento Automático 2D (Nesting) e Controle de Corte CNC para Calçados e Artefatos (Compatível com fluxos ATOM FlashCut/DieProc e Comelz CAM).  
> **Linguagem**: Python 3.12 (Tkinter nativo, SQLite3, Pillow, PyInstaller).  
> **Volume de Código**: 13.422 linhas de código em 21 módulos estruturados.  
> **Destinatário da Análise**: Assistente Argon Gemini (Revisão Técnica e Propostas de Melhoria).

---

## 1. Visão Geral e Objetivo do Sistema

O sistema é uma recriação moderna, estável e independente dos softwares industriais clássicos **JobManager 2000**, **ATOM LayoutNT (`Layout.exe`)**, **ATOM FlashCut / DieProc (`dp98`)** e estratégias de corte contínuo estilo **Comelz CAM**.

### Principais Capacidades:
1. **Importação e Engenharia de Moldes (`.die`, `.dxf`, `.hps`)**: Decodificação vetorial direta de arquivos de matrizes de corte, com identificação de contornos de corte, furações, marcações internas, chanfros e extração automática de numeração (*taglia*).
2. **Gerenciamento de Ordens e Sessões de Produção**: Controle estruturado de modelos, pares por tamanho, sequência de corte, ficha técnica e alocação de matérias-primas (chapas e bobinas).
3. **Motores de Cálculo de Layout (Nesting 2D)**:
   - **`sint` (Sintético Contínuo)**: Geminação de pares $0^\circ/180^\circ$, defasagem horizontal em colmeia e avanço contínuo.
   - **`tape_a` (Tiras & Fitas)**: Alinhamento longitudinal estrito para faixas estreitas com passo compacto.
   - **`flashnestsheet` (ATOM DieProc dp98)**: Otimização bidimensional com tolerância angular fina (*range sweep*) e acoplamento de rotação.
   - **`flashnestroll`**: Otimização contínua minimizando comprimento desenrolado de bobinas.
   - **`flashnestleather`**: Varredura multi-angular adaptativa para peles irregulares de couro.
   - **`freenest`**: Heurística livre para máxima compactação percentual.
4. **Sistema de Detecção de Colisão Zero**: Bloqueio estrito de sobreposições com verificação geométrica poligonal (SAT / interseção de arestas) e respeito ao gap milimétrico.
5. **Layout Editor com Interface Autêntica MDI**: Reprodução fiel do visual Win32 clássico, contendo mesa CAD estática com grade milimétrica, barra lateral com miniaturas vetoriais preenchidas na cor do número, contadores de produção (`3/3 0/3`, `16/32 16/32`), suporte a `Ctrl+Z`, manipulação livre e seletor de paleta de cores.
6. **Estimador de Tempo de Máquina CNC & Exportadores**: Estimativa precisa de ciclo para cabeçotes ATOM (velocidade de lâmina 650 mm/s, translação rápida G00, tempo de punção) e geração de G-Code (ISO 6983) e DXF R12.

---

## 2. Mapa Estrutural do Código-Fonte

```
jobmanager-win10-python/
│
├── main.py                     # [36 LOC] Ponto de entrada, High-DPI Windows, inicialização
├── config.py                   # [124 LOC] Paleta Win32, temas visuais, parâmetros ATOM
├── database.py                 # [858 LOC] Camada SQLite, migrações, CRUD e serialização JSON
│
├── cad/                        # NÚCLEO MATEMÁTICO E GEOMÉTRICO
│   ├── geometry.py             # [200 LOC] Algoritmos 2D: Shoelace, SAT, Ray-casting, BBox, Colisões
│   ├── colors.py               # [195 LOC] Sistema de cores por número (grade 18 a 48, alto contraste)
│   ├── die_parser.py           # [525 LOC] Parser binário e ASCII de arquivos .die (ATOM/Caligola/Comelz)
│   ├── nesting_engine.py       # [653 LOC] Motores de nesting (Sint, Tape A, DieProc, Leather, Yield, Time)
│   └── exporter.py             # [100 LOC] Geradores de G-Code (ISO 6983 CNC) e DXF R12
│
├── ui/                         # INTERFACE GRÁFICA (TKINTER MDI INDUSTRIAL)
│   ├── main_window.py          # [3.190 LOC] Janela MDI principal, árvore de navegação, status bar, menus
│   ├── session_view.py         # [1.810 LOC] Visão da Sessão: Abas Geral, Moldes, Materiais, Layout, Resumo
│   ├── layout_editor_view.py   # [1.268 LOC] Layout Editor [I0000]: Mesa CAD estática, barra lateral, miniaturas
│   ├── shape_editor_view.py    # [1.082 LOC] Editor de contornos vetoriais e piques
│   ├── layout_print_dialog.py  # [615 LOC] Relatório de impressão vetorial de ficha técnica de corte
│   ├── options_dialog.py       # [584 LOC] Janela de opções globais (Ferramentas -> Opções)
│   ├── material_codes_view.py  # [511 LOC] Listagem e cadastro de códigos de materiais
│   ├── dieproc_dialog.py       # [452 LOC] Configuração de parâmetros DieProc dp98 (coupling, ranges, gaps)
│   ├── cad_canvas.py           # [410 LOC] Canvas 2D interativo com zoom, pan e seleção
│   ├── add_shapes_dialog.py    # [299 LOC] Diálogo de importação e adição de moldes à sessão
│   ├── order_view.py           # [207 LOC] Gestão de pedidos e clientes
│   ├── edit_shape_in_session_dialog.py # [185 LOC] Configuração de pares, sequência e cor por número
│   └── params_dialog.py        # [118 LOC] Configuração rápida de gap e preenchimento
│
├── assets/                     # Ícones originais Win32 e gráficos 16x16 / 24x20 / 32x32
├── samples/                    # Moldes de teste (.die)
└── jobmanager.db               # Banco de dados SQLite de produção
```

---

## 3. Detalhamento dos Módulos Principais

### 3.1. Núcleo Matemático e Algorítmico (`cad/`)

#### A. Geometria Computacional ([`cad/geometry.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/cad/geometry.py))
- **`polygon_area(poly)`**: Cálculo exato da área de polígonos irregulares via Fórmula do Cadarço (Shoelace / Teorema de Green).
- **`polygon_perimeter(poly)`**: Comprimento perimetral contínuo para estimativa de corte de lâmina.
- **`transform_contour(contour, dx, dy, angle_deg)`**: Rotação e translação euclidiana bidimensional com matriz de rotação trigonométrica:
  $$\begin{bmatrix} x' \\ y' \end{bmatrix} = \begin{bmatrix} \cos\theta & -\sin\theta \\ \sin\theta & \cos\theta \end{bmatrix} \begin{bmatrix} x \\ y \end{bmatrix} + \begin{bmatrix} dx \\ dy \end{bmatrix}$$
- **`polygons_collide(poly_a, poly_b, gap)`**: Teste de não-sobreposição em duas etapas:
  1. *Filtro Rápido (Broad-Phase)*: Verificação de sobreposição de Bounding Boxes expandidas pelo `gap`.
  2. *Filtro Estrito (Narrow-Phase)*: Detecção de interseção de segmentos de reta entre arestas e teste de ponto interior (Ray-Casting Algorithm) para capturar peças contidas dentro de outras.

#### B. Motores de Aninhamento 2D ([`cad/nesting_engine.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/cad/nesting_engine.py))
Contém a suíte completa de motores de encaixe industrial:

1. **Motor `nest_synthetic_engine` (`strategy="sint"`)**:
   - Desenvolvido para materiais sintéticos em bobina e chapa (homogêneos, sem defeitos naturais).
   - **Geminação de Pares**: Alterna peças em $0^\circ$ e $180^\circ$ (macho/fêmea ou par casado) para reduzir a área vazia entre pés.
   - **Intertravamento em Colmeia (Row Shifting)**: Aplica defasagem de linha horizontal ($\Delta x = W_{peça} \times 0.40$), permitindo que o rebaixo de uma linha abrace o relevo da linha adjacente.
   - **Ajuste Fino de Linha**: Varre milimetricamente a elevação vertical $\Delta y$ para eliminar 100% de colisões respeitando o gap.

2. **Motor `nest_tape_engine` (`strategy="tape_a"`)**:
   - Desenvolvido para peças lineares, fitas, tiras estreitas, debruns, correias e vivos.
   - **Alinhamento Longitudinal Estrito**: Trava o eixo maior das peças no sentido do comprimento da fita/bobina (eixo X) para garantir resistência à tração do tecido/fita.
   - **Passo Linear Compacto (Step Packing)**: Espaçamento equidistante contínuo ao longo da faixa. Peças curvas são alternadas em zigue-zague $0^\circ/180^\circ$.

3. **Motor `dieproc_nest_pieces` (`strategy="flashnestsheet" / "flashnestroll"`)**:
   - Reimplementação do motor clássico **ATOM DieProc dp98**.
   - Lê os pares de acoplamento angular (`coupling`, ex: `"0/0 0/180"`).
   - Executa a micro-varredura angular de tolerância (*range sweep* de $-3^\circ$ a $+3^\circ$) para encontrar a rotação ótima que minimiza o retângulo envolvente combinado.
   - Suporta escalonamento diagonal (*diagonal stepping*).

4. **Motor `flashnestleather`**:
   - Nesting adaptativo para peles irregulares de couro, operando com varredura multi-angular livre ($0^\circ, 45^\circ, 90^\circ, \dots, 315^\circ$) e maior margem de segurança de borda.

5. **Estimadores de Desempenho**:
   - `calculate_yield(...)`: Rendimento percentual ($\text{Yield} = \frac{\text{Área Útil}}{\text{Área Chapa}} \times 100$).
   - `calculate_atom_cutting_time(...)`: Ciclo total de máquina:
     $$T_{\text{ciclo}} = \frac{L_{\text{corte}}}{V_{\text{lâmina}}} + \frac{L_{\text{translação}} \times 0.35}{V_{\text{rápido}}} + N_{\text{furos}} \times T_{\text{punção}}$$

#### C. Sistema de Cores por Número ([`cad/colors.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/cad/colors.py))
- Elimina completamente o problema de peças ficarem pretas por padrão (`fill=None`).
- Mapeia toda a grade de calçados (infantil 18–32, adulto 33–48, e tamanhos especiais como `25a`, `23_5a`):
  - Ex: **Nº 25a** $\rightarrow$ Magenta Choque `#d946ef` | **Nº 41** $\rightarrow$ Azul Royal `#2563eb` | **Nº 38** $\rightarrow$ Verde `#16a34a`.
- `get_contrast_text_color`: Define texto em preto ou branco por luminância relativa ($L = 0.299R + 0.587G + 0.114B$).

#### D. Analisador de Arquivos `.die` ([`cad/die_parser.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/cad/die_parser.py))
- Suporta matrizes de calçados de sistemas ATOM, Caligola e Comelz.
- Identifica cabeçalhos binários e ASCII, blocos de coordenadas, piques de referência (*notches*), furações e campos de identificação de artigo e tamanho.

---

### 3.2. Interface Gráfica e Visual Industrial (`ui/`)

#### A. Janela Principal MDI ([`ui/main_window.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/ui/main_window.py))
- **Design Industrial Win32**: Janelas internas arrastáveis com barra de título rebaixada, botões Minimizar/Maximizar/Fechar, docking na barra de tarefas inferior e cascateamento.
- **Barra de Navegação em 3 Modos**:
  - `Produção`: Árvore hierárquica `Ordens -> Sessões -> Moldes`.
  - `Materiais`: Catálogo de matérias-primas e estoques.
  - `Moldes`: Artigos e geometrias catalogadas.
- **Barra de Ferramentas de Dois Níveis**: Acesso rápido a Novo, Abrir, Salvar, Cortar, Copiar, Colar, Importar .die, Parâmetros, Auto-Nest, Simulação e Exportar G-Code.

#### B. Layout Editor Autêntico ([`ui/layout_editor_view.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/ui/layout_editor_view.py))
- **Fidelidade Total ao ATOM LayoutNT (`Layout.exe`)**:
  - Viewport estático proporcional à chapa (sem perda de referência no zoom da roda).
  - Mesa cinza industrial com grade milimétrica de 100mm.
  - Divisória vertical 3D rebaixada separando a chapa da barra lateral.
- **Barra Lateral de Moldes (Miniaturas, Nomes e Numeração)**:
  - Miniatura do contorno vetorial preenchida com a cor do número e borda preta nítida de 1px.
  - Linha 1: Nome do molde (com truncamento inteligente `...`).
  - Linha 2: Tamanho e relação de produção (`3/3 0/3`, `Nº 25a 16/32 16/32`).
  - Interação: Clique simples seleciona a peça na mesa; duplo clique insere peça na mesa em posição livre de colisão; botão `+` adiciona peça do molde ativo.
- **Mecanismos de Segurança de Edição**:
  - **Bloqueio de Colisão por Drag & Drop**: Se o operador soltar uma peça sobreposta a outra, a peça é revertida para a posição anterior com alerta sonoro/visual.
  - **Histórico Undo (`Ctrl+Z`)**: Até 50 níveis de desfeitas.
  - **Rótulo Central na Peça**: Indica visualmente na mesa o número do calçado (`Nº 25a`, `Nº 41`).

#### C. Sessão de Corte ([`ui/session_view.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/ui/session_view.py))
- Caderno de abas:
  - **Geral**: Seletor de estratégia (`sint`, `tape_a`, `flashnestsheet`, etc.), presets de parâmetros e descrição técnica em tempo real.
  - **Moldes**: Tabela com badges de cores, pares requeridos, sequência de corte, área em $dm^2$, botão de troca de cor com color picker do sistema e pré-visualização vetorial colorida do molde.
  - **Materiais / Layout / Resumo**: Indicadores de eficiência, tempo de corte e instâncias.

---

### 3.3. Banco de Dados e Persistência ([`database.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/database.py))

Estrutura relacional SQLite em [`jobmanager.db`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/jobmanager.db):
- **`orders`**: Ordens de corte com código, cliente, status e prazos.
- **`sessions`**: Sessões ativas de aninhamento com vínculo de material, máquina, estratégia, parâmetros e campo JSON `placed_pieces` persistindo posições $(x, y, \theta)$ e cores.
- **`shapes`**: Moldes importados associados à sessão com pares, sequência, tamanho, contorno vetorial JSON, furações e cor atribuída.
- **`materials`**: Catálogo com dimensões (largura, altura/comprimento em mm), espessura, custo $/m^2$ e folga de segurança (*gap*).
- **`dieproc_presets`**: Predefinições de acoplamento e tolerância angular (ex: `ALTERNADO`, `DIREITA`, `ESQUERDA`, `GAP 2`, `HighYield`, `FastNest`).
- **`settings`**: Configurações de sistema e máquina.

---

## 4. Fluxo de Execução Ponta a Ponta (End-to-End)

```mermaid
graph TD
    A[Arquivo .die / .dxf / .hps] -->|Parser Geométrico| B(cad/die_parser.py)
    B -->|Cadastro de Molde & Grade| C[Tabela de Moldes da Sessão]
    C -->|Atribuição de Cor por Número| D(cad/colors.py)
    D -->|Definição de Pares & Sequência| E[Sessão de Corte / ui/session_view.py]
    E -->|Seleção de Estratégia: Sint / Tape A / DieProc| F{cad/nesting_engine.py}
    F -->|Motor Sint| G[Geminação 0/180 & Colmeia]
    F -->|Motor Tape A| H[Alinhamento Linear Longitudinal]
    F -->|Motor DieProc dp98| I[Coupling & Range Sweep]
    G --> J[Validação de Colisão Zero / cad/geometry.py]
    H --> J
    I --> J
    J -->|Persistência SQLite| K[(jobmanager.db)]
    K -->|Visualização & Interatividade| L[Layout Editor [I0000] / ui/layout_editor_view.py]
    L -->|Ajuste Manual / Bump / Ctrl+Z| L
    L -->|Exportação| M[G-Code CNC ISO 6983]
    L -->|Relatório| N[Ficha Técnica Vetorial / ui/layout_print_dialog.py]
```

---

## 5. Pontos Fortes do Sistema Atual

1. **Autonomia e Portabilidade Total**:
   - Zero dependências de frameworks pesados de terceiros (não requer C++ runtime externo, Qt ou bibliotecas pesadas). Compila para um binário executável único via PyInstaller (`dist/teste_dola`) que roda direto do pendrive em Linux e Windows 10/11.
2. **Conformidade Industrial Rígida**:
   - **Zero Colisão**: Regra estrita respeitada em todos os motores matemáticos e no drag & drop manual.
   - **Cores por Grade**: Eliminação de ambiguidade visual na fábrica — cada número de calçado possui cor exclusiva e rótulo central de alto contraste.
   - **Fidelidade Visual ATOM**: Layout Editor recria pixel a pixel a barra de ferramentas, miniaturas, contadores e atalhos clássicos do ATOM LayoutNT.
3. **Multi-Estratégia Especializada**:
   - Suporte tanto a corte contínuo de rolos sintéticos (`sint`), tiras estreitas (`tape_a`), chapas ATOM (`flashnestsheet`) e peles irregulares (`flashnestleather`).

---

## 6. Oportunidades de Melhoria para Avaliação do Assistente Argon Gemini

Para a análise de evolução do sistema pelo assistente **Argon Gemini**, destacam-se os seguintes tópicos de aprimoramento recomendados:

### A. Algoritmos de Nesting e Pesquisa Operacional
1. **No-Fit Polygon (NFP) Completo com Soma de Minkowski**:
   - Atualmente, a detecção de colisão faz varredura milimétrica direta. A implementação de NFP analítico exato entre polígonos côncavos permitiria deslizamento contínuo em $O(1)$ após o pré-cálculo do NFP, acelerando o aninhamento de centenas de peças.
2. **Meta-Heurísticas de Otimização Global**:
   - Adição de algoritmo genético (GA) ou *Simulated Annealing* sobre a ordem da fila de peças e rotações para buscar o rendimento teórico máximo ($\text{Yield} > 85\%$).
3. **Common-Line Cutting Real (Corte em Linha Compartilhada)**:
   - Para a estratégia `tape_a`, gerar trajetórias de G-Code onde a aresta divisória comum entre duas peças consecutivas é percorrida uma única vez pela lâmina CNC (corte guilhotina em passagem única).

### B. Otimização de Trajetória da Lâmina CNC (Cálculo de Percurso)
1. **Resolução do Problema do Caixeiro Viajante (TSP) para Deslocamentos Rápidos (G00)**:
   - Ordenar a sequência de corte dos moldes na mesa de modo a minimizar o percurso aéreo da faca entre o término de uma peça e o início da próxima.
2. **Compensação Dinâmica de Raio de Lâmina e Tangencialidade**:
   - Inserção de comandos de controle do eixo C tangencial (rotação da faca oscilante) nas curvas fechadas de calçados para evitar mastigamento de material.

### C. Arquitetura de Software e Responsividade da UI
1. **Processamento Assíncrono / Multiprocessamento no Cálculo de Layout**:
   - Executar os cálculos pesados de `auto_nest_pieces` em um `ProcessPoolExecutor` ou `threading.Thread` com barra de progresso, evitando qualquer congelamento temporário da interface Tkinter durante cálculos com 200+ peças.
2. **Modularização do `ui/main_window.py`**:
   - Com 3.190 linhas, o arquivo concentra controle de janelas, sincronização de menus e chamadas de banco de dados. Pode ser desmembrado em um *WindowManager* e *ActionController* dedicados.

---

## 7. Instruções para o Assistente Argon Gemini

Ao analisar este projeto, sugere-se focar nas seguintes questões:
1. **Otimização dos algoritmos de geometria e colisão** (`cad/geometry.py` e `cad/nesting_engine.py`) para maior velocidade de processamento.
2. **Estratégias adicionais de aproveitamento de material** para bobinas contínuas e couro.
3. **Padrões de design de código** para facilitar a manutenção contínua e extensibilidade dos módulos CAD/CAM.
