# FASE 6.0 — MOCKUPS VISUAIS DO SHAPE CATALOG VIEW (GRID VIEW)

**Projeto:** CorteAC / JobManager 2000 (Python Edition)  
**Módulo:** `ui/shape_catalog_view.py`  
**Referência:** Shape Editor Comelz (`MA166_166_207.cmz - 22A.18-9d3a10c2`)  
**Data:** 29/10/2026  
**Status:** Diagnóstico e Especificação de Design  

---

## 1. Visão Geral da Arquitetura Visual

O **Shape Catalog View** (ou Catálogo de Moldes em Grid) tem como propósito exibir a coleção completa de moldes de um Artigo estruturada em uma **matriz bidimensional de Peças (Colunas) × Tamanhos (Linhas)**.

### Estrutura Geral do Layout
- **Barra Superior MDI:** Barra de título clássica com controles de janela (`_`, `□`, `✕`).
- **Header de Colunas (Peças):** Exibe o Badge de paridade/corte (`[2*]`) e o nome mnemônico da peça (`FoCa`, `Gasp`, `Pala`, etc.).
- **Sidebar Esquerda (Tamanhos):** Lista vertical dos tamanhos (`17.00`, `18.00`, `19.00`, ..., `22.00` ou `22a` a `36a`).
- **Área Central (Grid de Células):** Matriz de $N \times M$ células vetoriais em alta fidelidade com contorno do molde, marcações de costura e piques/furos.
- **Painel Lateral Direito (10 Botões de Ação):**
  1. `[Reimportar]`
  2. `[Mesclar arq.]`
  3. `[Organizar peças]`
  4. `[Espelhar]`
  5. `[Apagar peça]`
  6. `[Desfazer]` (Ctrl+Z)
  7. `[Editar peça]` (Abre `ShapeEditorView`)
  8. `[Salvar como]`
  9. `[Salvar]`
  10. `[Esc]` (Fechar)
- **Barra de Status Inferior:** Informações de peça selecionada, tamanho, dimensões (mm), total de peças e estado operacional.

---

## 2. Mockup A — Fiel ao Comelz (Teal Escuro + Oliva)

### 2.1 Descrição Estética
Inspirado 1:1 na identidade visual do software Comelz Calzature:
- Fundo da janela principal em tom **teal escuro** (`#13383e`).
- Fundo do grid e das células em **cinza asfalto escuro** (`#2b3035`).
- Headers de coluna e botões do painel direito em **verde oliva suave** (`#556345` / `#62724e`).
- Contornos vetoriais das peças em **branco/marfim** (`#f0f3f4`).
- Marcações internas (costuras/sentido de montagem) em **magenta fluorescente** (`#ff00ff`).
- Piques e furações em **amarelo limão** (`#eab308`).
- Célula ativa destacada com borda **laranja/dourada Comelz** (`#f59e0b`).

### 2.2 Diagrama ASCII Art (Mockup A)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ 📐 [MA166_166_207.cmz - 22A.18]                                                  [_] [□] [×]│
├──────────────────────────────────────────────────────────────────────────────┬──────────────┤
│ TAM  │  [2*]   [2*]   [2*]     [2*]       [2*]     [2*]   [2*]    [2*]       │ [Reimportar] │
│      │  FoCa   Gasp   Pala   Palmilha   Palmlhdo   RGas   RfQu    FoPal      │ [Mesclar arq]│
├──────┼───────────────────────────────────────────────────────────────────────┼──────────────┤
│17.00 │ ┌─────┐ ┌────┐ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ┌────────┐  │ [Organizar]  │
│      │ │ ⟍ ⟋ │ │╭──╮│ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ │ ╭────╮ │  │ [Espelhar]   │
│      │ │  •  │ ││->││ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ │ │ -> │ │  │ [Apagar peça]│
│      │ └─────┘ └────┘ └────┘ └────────┘ └────────┘ └────┘ └────┘ └────────┘  │ [Desfazer]   │
├──────┼───────────────────────────────────────────────────────────────────────┤ [Editar peça]│
│18.00 │ ┌─────┐ ┌────┐ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ┌────────┐  │ [Salvar como]│
│      │ │ ⟍ ⟋ │ │╭──╮│ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ │ ╭────╮ │  │ [Salvar]     │
│      │ │  •  │ ││->││ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ │ │ -> │ │  │ [Esc]        │
│      │ └─────┘ └────┘ └────┘ └────────┘ └────────┘ └────┘ └────┘ └────────┘  ├──────────────┤
├──────┼───────────────────────────────────────────────────────────────────────┤ Mini-Info:   │
│19.00 │ ┌─────┐ ┌────┐ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ┌────────┐  │ Gasp @ 20.00 │
│      │ │ ⟍ ⟋ │ │╭──╮│ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ │ ╭────╮ │  │ 210 x 125 mm │
│      │ │  •  │ ││->││ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ │ │ -> │ │  │ Par: 2 peças │
│      │ └─────┘ └────┘ └────┘ └────────┘ └────────┘ └────┘ └────┘ └────────┘  │ Costura: 2   │
├──────┼───────────────────────────────────────────────────────────────────────┤ Furos: 4     │
│20.00 │ ┌─────┐ ╔════╗ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ┌────────┐  │              │
│      │ │ ⟍ ⟋ │ ║╭──╮║ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ │ ╭────╮ │  │              │
│      │ │  •  │ ║│->║║ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ │ │ -> │ │  │              │
│      │ └─────┘ ╚════╝ └────┘ └────────┘ └────────┘ └────┘ └────┘ └────────┘  │              │
├──────┼───────────────────────────────────────────────────────────────────────┤              │
│21.00 │ ┌─────┐ ┌────┐ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ┌────────┐  │              │
│      │ │ ⟍ ⟋ │ │╭──╮│ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ │ ╭────╮ │  │              │
│      │ │  •  │ ││->││ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ │ │ -> │ │  │              │
│      │ └─────┘ └────┘ └────┘ └────────┘ └────────┘ └────┘ └────┘ └────────┘  │              │
├──────┼───────────────────────────────────────────────────────────────────────┤              │
│22.00 │ ┌─────┐ ┌────┐ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ┌────────┐  │              │
│      │ │ ⟍ ⟋ │ │╭──╮│ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ │ ╭────╮ │  │              │
│      │ │  •  │ ││->││ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ │ │ -> │ │  │              │
│      │ └─────┘ └────┘ └────┘ └────────┘ └────────┘ └────┘ └────┘ └────────┘  │              │
├──────┴───────────────────────────────────────────────────────────────────────┴──────────────┤
│ [Gasp] Tam: 20.00 | W: 210.4 mm | H: 125.1 mm | Área: 2.15 dm² | 48 células carregadas (8x6)│
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Tabela de Cores (Mockup A)
| Componente | Cor Hex | Descrição |
|---|---|---|
| Fundo da Janela | `#13383e` | Teal escuro profundo Comelz |
| Fundo do Grid | `#232a2f` | Cinza escuro técnico |
| Fundo das Células | `#2d353b` | Célula vetorial com borda fina |
| Seleção Ativa | `#f59e0b` | Dourado/laranja com moldura dupla |
| Headers & Ações | `#4e5d43` | Verde oliva clássico Comelz |
| Texto dos Botões | `#ffffff` | Branco com boa legibilidade |
| Contorno Vetorial | `#ffffff` | Polígono da peça em linha sólida de 1.5px |
| Marcações Internas | `#ff00ff` | Costura / piques em magenta fluorescente |
| Furos / Brocas | `#eab308` | Círculo amarelo limão com cruz |

---

## 3. Mockup B — Win32 Clássico (Cinza Padrão Windows XP/2000)

### 3.1 Descrição Estética
100% aderente às diretrizes de interface do JobManager 2000 e do tema Win32 MDI (Regra de Ouro #3):
- Barra de título MDI em azul clássico (`#0a246a`) com texto branco em negrito.
- Janela, molduras e painéis em **cinza Win32** (`#d4d0c8` / `#ece9d8`).
- Botões em relevo clássico 3D (`relief="raised"`, `bd=2`).
- Células do grid em **branco** (`#ffffff`) ou cinza suave (`#f5f5f5`) com borda rebaixada (`relief="sunken"`, `bd=1`).
- Contornos vetoriais em **azul escuro industrial** (`#0a246a`) com preenchimento cinza claro translúcido (`#e8edf2`).
- Marcações de costura em **magenta clássico** (`#cc00cc`).
- Furos de broca em **verde floresta** (`#16a34a`) com ponto central.
- Headers com aparência de botões de tabela Win32 clássicos.

### 3.2 Diagrama ASCII Art (Mockup B)

```
╔═════════════════════════════════════════════════════════════════════════════╗
║ 📐 Catálogo de Moldes - [Artigo: MA166_166_207]                   [_] [□] [✕]║
╠══════════════════════════════════════════════════════════════════╦══════════╣
║ Tamanho│ [2*]    [2*]    [2*]    [2*]    [2*]    [2*]    [2*]    ║[Reimport]║
║        │ FoCa    Gasp    Pala    Palm   Plhdo    RGas    RfQu    ║[Mesclar] ║
╠════════╪═════════════════════════════════════════════════════════╬══════════╣
║ 17.00  │┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐ ║[Organizar]║
║        ││ ⟍  ⟋ ││ ╭──╮ ││  ╱╲  ││╭────╮││╭────╮││  ╱╲  ││ ⟍  ⟋ │ ║[Espelhar] ║
║        ││  ••  ││ │->│ ││  ••  │││ -> ││││ -> │││  ••  ││  ••  │ ║[Excluir] ║
║        │└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘ ║[Desfazer] ║
╠────────┼─────────────────────────────────────────────────────────╢[Editar...]║
║ 18.00  │┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐ ║[Salvar C.]║
║        ││ ⟍  ⟋ ││ ╭──╮ ││  ╱╲  ││╭────╮││╭────╮││  ╱╲  ││ ⟍  ⟋ │ ║[Salvar]   ║
║        ││  ••  ││ │->│ ││  ••  │││ -> ││││ -> │││  ••  ││  ••  │ ║[Fechar]   ║
║        │└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘ ╠══════════╣
╠────────┼─────────────────────────────────────────────────────────╢Detalhes: ║
║ 19.00  │┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐ ║Molde:     ║
║        ││ ⟍  ⟋ ││ ╭──╮ ││  ╱╲  ││╭────╮││╭────╮││  ╱╲  ││ ⟍  ⟋ │ ║ Gasp     ║
║        ││  ••  ││ │->│ ││  ••  │││ -> ││││ -> │││  ••  ││  ••  │ ║Tam: 20.00 ║
║        │└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘ ║          ║
╠────────┼─────────────────────────────────────────────────────────╢Larg: 210mm║
║ 20.00  │┌──────┐╔══════╗┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐ ║Alt:  125mm║
║        ││ ⟍  ⟋ │║ ╭──╮ ║│  ╱╲  ││╭────╮││╭────╮││  ╱╲  ││ ⟍  ⟋ │ ║Área:     ║
║        ││  ••  │║ │->│ ║│  ••  │││ -> ││││ -> │││  ••  ││  ••  │ ║ 2.15 dm² ║
║        │└──────┘╚══════╝└──────┘└──────┘└──────┘└──────┘└──────┘ ║Par: 2 pçs║
╠────────┼─────────────────────────────────────────────────────────╢          ║
║ 21.00  │┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐ ║Status:   ║
║        ││ ⟍  ⟋ ││ ╭──╮ ││  ╱╲  ││╭────╮││╭────╮││  ╱╲  ││ ⟍  ⟋ │ ║Aprovado  ║
║        ││  ••  ││ │->│ ││  ••  │││ -> ││││ -> │││  ••  ││  ••  │ ║          ║
║        │└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘ ║          ║
╠────────┼─────────────────────────────────────────────────────────╢          ║
║ 22.00  │┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐ ║          ║
║        ││ ⟍  ⟋ ││ ╭──╮ ││  ╱╲  ││╭────╮││╭────╮││  ╱╲  ││ ⟍  ⟋ │ ║          ║
║        ││  ••  ││ │->│ ││  ••  │││ -> ││││ -> │││  ••  ││  ••  │ ║          ║
║        │└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘ ║          ║
╠════════╧═════════════════════════════════════════════════════════╩══════════╣
║ [Gasp / 20.00] Pronto | 48 moldes indexados | Dois cliques para abrir no CAD║
╚═════════════════════════════════════════════════════════════════════════════╝
```

### 3.3 Tabela de Cores (Mockup B)
| Componente | Cor Hex | Descrição |
|---|---|---|
| Barra de Título | `#0a246a` | Azul marinho WinXP com texto branco |
| Fundo da Janela / Painéis | `#d4d0c8` / `#ece9d8` | Cinza neutro Win32 clássico |
| Botões de Ação | `#d4d0c8` | Cinza com borda 3D `raised` (bd=2) |
| Célula Vetorial | `#ffffff` | Branco puro com relevo `sunken` (bd=1) |
| Célula Ativa / Foco | `#0a246a` | Moldura azul 2px sólida com fundo azul claro (`#e0edff`) |
| Headers Peças / Tamanhos | `#d4d0c8` | Botões em relevo com fonte Segoe UI 8 bold |
| Contorno da Peça | `#0a246a` | Azul escuro nítido (1.5px) com preenchimento `#f0f4f8` |
| Marcações Internas | `#cc00cc` | Magenta Win32 |
| Furos de Broca | `#16a34a` | Verde floresta com cruz interna |

---

## 4. Mockup C — Híbrido (Win32 MDI + Acentos Comelz) ★ RECOMENDADO

### 4.1 Descrição Estética e Racional Técnico
O **Mockup C** resolve com perfeição o dilema entre a **Regra de Ouro #3 (Preservação Win32)** e a **ergonomia visual dos softwares modernos de corte CAM/CAD**:
1. **Estrutura Externa 100% Win32:** A moldura MDI, barra de título (`#0a246a`), barra de status e contornos de janelas respeitam rigorosamente a identidade do CorteAC / JobManager 2000.
2. **Área Interna Técnica de Alto Contraste:** A grade de células do Canvas utiliza fundo técnico escuro (`#262626` / `#1e293b`), permitindo que as linhas vetoriais brancas (`#ffffff`), as costuras em magenta vibrante (`#ff00ff`) e os piques/furos amarelos (`#facc15`) tenham visibilidade imediata sem cansaço visual.
3. **Sidebar de Tamanhos com Acento Ciano:** Destaca os números dos tamanhos com fundo suave (`#e2e8f0` ou ciano sutil `#0891b2` com texto legível).
4. **Painel de Ações Rebaixado / Win32 Organizado:** Mantém os 10 botões clássicos Win32 com ícones e agrupamentos lógicos.

### 4.2 Diagrama ASCII Art (Mockup C)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║ 📐 Catálogo de Moldes (Grid View) - [MA166_166_207.cmz]           [_] [□] [✕]║
╠═══════════════════════════════════════════════════════════════════╦══════════╣
║ TAM   │  [2*]    [2*]    [2*]     [2*]       [2*]     [2*]   [2*] ║[Reimport]║
║       │  FoCa    Gasp    Pala   Palmilha   Palmlhdo   RGas   RfQu ║[Mesclar] ║
╠═══════╪═══════════════════════════════════════════════════════════╬══════════╣
║ 17.00 │ ┌─────┐ ┌────┐ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ║[Organizar]║
║       │ │ ⟍ ⟋ │ │╭──╮│ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ ║[Espelhar] ║
║       │ │  •  │ ││->││ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ ║[Apagar]   ║
║       │ └─────┘ └────┘ └────┘ └────────┘ └────────┘ └────┘ └────┘ ║[Desfazer] ║
╠───────┼───────────────────────────────────────────────────────────╢[Editar ✏️]║
║ 18.00 │ ┌─────┐ ┌────┐ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ║[Salvar C.]║
║       │ │ ⟍ ⟋ │ │╭──╮│ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ ║[Salvar 💾]║
║       │ │  •  │ ││->││ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ ║[Esc ↩]   ║
║       │ └─────┘ └────┘ └────┘ └────────┘ └────────┘ └────┘ └────┘ ╠══════════╣
╠───────┼───────────────────────────────────────────────────────────╢Painel Info║
║ 19.00 │ ┌─────┐ ┌────┐ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ║Peça: Gasp ║
║       │ │ ⟍ ⟋ │ │╭──╮│ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ ║Tam: 20.00 ║
║       │ │  •  │ ││->││ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ ║Dimensões: ║
║       │ └─────┘ └────┘ └────┘ └────────┘ └────────┘ └────┘ └────┘ ║210x125 mm ║
╠───────┼───────────────────────────────────────────────────────────╢Área Bruta:║
║ 20.00 │ ┌─────┐ ╔════╗ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ║ 2.15 dm²  ║
║       │ │ ⟍ ⟋ │ ║╭──╮║ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ ║Paridade:  ║
║       │ │  •  │ ║│->║║ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ ║ 2 por par ║
║       │ └─────┘ ╚════╝ └────┘ └────────┘ └────────┘ └────┘ └────┘ ║Costura: Sim║
╠───────┼───────────────────────────────────────────────────────────╢Furos: 4    ║
║ 21.00 │ ┌─────┐ ┌────┐ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ║          ║
║       │ │ ⟍ ⟋ │ │╭──╮│ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ ║          ║
║       │ │  •  │ ││->││ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ ║          ║
║       │ └─────┘ └────┘ └────┘ └────────┘ └────────┘ └────┘ └────┘ ║          ║
╠───────┼───────────────────────────────────────────────────────────╢          ║
║ 22.00 │ ┌─────┐ ┌────┐ ┌────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────┐ ║          ║
║       │ │ ⟍ ⟋ │ │╭──╮│ │ ╱╲ │ │ ╭────╮ │ │ ╭────╮ │ │ ╱╲ │ │ ⟍ ⟋│ ║          ║
║       │ │  •  │ ││->││ │ │• │ │ │ -> │ │ │ │ -> │ │ │ │• │ │  • │ ║          ║
║       │ └─────┘ └────┘ └────┘ └────────┘ └────────┘ └────┘ └────┘ ║          ║
╠═══════╧═══════════════════════════════════════════════════════════╩══════════╣
║ [Gasp @ 20.00] Selecionado | 48 células (8x6) | Pressione [Enter] ou 2-cliques║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 4.3 Tabela de Cores (Mockup C)
| Componente | Cor Hex | Descrição |
|---|---|---|
| Casca Externa / Janela | `#d4d0c8` | Cinza clássico Win32 / WinXP |
| Barra de Título MDI | `#0a246a` | Azul XP com texto branco `#ffffff` |
| Headers de Peças (Colunas) | `#e2e8f0` | Fundo claro com borda 3D suave, texto bold `#0f172a` |
| Badges de Paridade `[2*]` | `#0284c7` | Azul ciano suave com texto `#ffffff` bold |
| Sidebar de Tamanhos (Linhas) | `#0f766e` / `#e2e8f0` | Destacado com numeração limpa |
| Fundo do Canvas Central | `#1e293b` | Azulardósia escuro de alto contraste |
| Fundo de Célula Normal | `#2b3442` | Célula vetorial com contorno fino cinza |
| Célula Ativa / Selecionada | `#f59e0b` / `#38bdf8` | Moldura destacada em dourado/ciano (2px) |
| Contorno Vetorial da Peça | `#ffffff` | Linha sólida branca 1.5px (máxima nitidez) |
| Marcações Internas (Costuras) | `#ff00ff` | Linha magenta fluorescente |
| Furos e Piques | `#facc15` | Círculo amarelo limão com ponto central |
| Botões do Painel Lateral | `#d4d0c8` | Estilo Win32 com texto escuro e relevo `raised` |

---

## 5. Especificações Técnicas de Interação dos Mockups

### 5.1 Navegação por Mouse e Teclado
- **Clique Simples no Grid (`<Button-1>`):** Seleciona a célula `(peça, tamanho)`. Atualiza o painel de informações lateral com métricas da peça e destaca a célula com borda brilhante.
- **Duplo Clique no Grid (`<Double-1>`):** Dispara `on_edit_shape()` abrindo a peça instantaneamente no `ShapeEditorView` completo para edição profunda de vértices.
- **Teclas de Seta (`Up`, `Down`, `Left`, `Right`):** Navega pela matriz de células sem necessidade de mouse.
- **Tecla Enter / Barra de Espaço:** Confirma seleção ou abre edição.
- **Atalho Teclado `Ctrl+Z`:** Dispara a função do botão `[Desfazer]`.
- **Tecla `Escape`:** Dispara a função do botão `[Esc]` (minimiza ou fecha o catálogo retornando à visão principal).

### 5.2 Mapeamento dos 10 Botões do Painel Direito
1. **`[Reimportar]`:** Recarrega o arquivo original de moldes (`.cmz`, `.die`, `.d`) do disco, descartando alterações locais não salvas.
2. **`[Mesclar arq.]`:** Abre diálogo de importação para mesclar novos moldes ou peças adicionais ao catálogo do artigo ativo.
3. **`[Organizar peças]`:** Reorganiza a matriz de colunas e linhas por tamanho crescente/decrescente ou agrupamento de tipo de material.
4. **`[Espelhar]`:** Aplica inversão horizontal (espelhamento esquerdo/direito) na peça selecionada.
5. **`[Apagar peça]`:** Remove a peça selecionada do artigo com confirmação de segurança.
6. **`[Desfazer]`:** Reverte a última ação de manipulação de peças.
7. **`[Editar peça]`:** Abre o editor vetorial detalhado (`ShapeEditorView`).
8. **`[Salvar como]`:** Exporta o conjunto de moldes do catálogo para um novo arquivo de molde ou pasta.
9. **`[Salvar]`:** Grava as alterações de contornos, piques e metadados no banco de dados (`jobmanager.db`).
10. **`[Esc]`:** Fecha o catálogo de moldes.
