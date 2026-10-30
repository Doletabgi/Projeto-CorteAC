# FASE 6.0 — DECISÕES DE DESIGN PARA O OPERADOR HUMANO

**Projeto:** CorteAC / JobManager 2000 (Python Edition)  
**Fase:** 6.0 — Diagnóstico e Design do Shape Catalog View  
**Data:** 29/10/2026  
**Status:** Aguardando deliberação do operador  

---

## Introdução

Durante a análise diagnóstica e a engenharia reversa do catálogo de moldes inspirado no **Shape Editor Comelz** (`MA166_166_207.cmz - 22A.18-9d3a10c2`), foram mapeadas três decisões centrais de arquitetura visual e regras de negócio.

Solicitamos que o operador humano avalie as alternativas abaixo e indique sua escolha para autorizar o início da **Fase 6.1 (Implementação)**.

---

## Pergunta 1 — Marcas Magenta Internas

Na imagem de referência do Shape Editor Comelz, o interior dos contornos vetoriais apresenta marcações gráficas na cor **magenta fluorescente** (setas direcionais, linhas e símbolos). No modelo de dados e formato CAM do CorteAC/ATOM, a qual elemento essas marcações devem corresponder prioritariamente?

### Alternativas:
- **(a) Costuras (`stitching_json`)**  
  *Descrição:* As linhas e polylines internas cadastradas no banco (`stitching_json`), correspondentes aos comandos `cpoint` / `num_of_cuts` do arquivo `.die` ATOM ou às linhas de pesponto do Comelz.  
  *Vantagem:* Representa fielmente linhas de costura e divisões internas das peças de calçado.
  
- **(b) Piques de montagem e furos de alinhamento (`holes_json` com `type="PUNCH"` / `notch`)**  
  *Descrição:* Símbolos em forma de V ou setas curtas nos contornos para encaixe durante o pesponto na esteira.  
  
- **(c) Fio da pele / Direção da fibra do couro (`grain_angle` / `directionFrom` / `directionTo`)**  
  *Descrição:* Uma seta vetorial no centro do molde indicando a orientação obrigatória de corte em relação à tração do couro.

- **(d) Híbrido Completo (Costuras + Piques + Fio da Pele) [Recomendado pelo Antigravity]**  
  *Descrição:* Renderizar `stitching_json` como linha contínua magenta, os piques (`notch`/`punch`) como pequenas marcas triangulares/setas magenta, e furos normais de broca (`drill`) em amarelo/verde com cruz.

### Sua Escolha:
> `[   ]` (Preencha com a letra da sua escolha)

---

## Pergunta 2 — Significado do Badge "[2*]" no Header de Peças

No topo de cada coluna de peças no catálogo Comelz (ex: `FoCa`, `Gasp`, `Pala`, etc.), há um badge destacado exibindo **`2*`** (ou `1*`, `4*`). Qual é a regra de negócio exata que esse badge deve refletir no CorteAC?

### Alternativas:
- **(a) Camadas de corte simultâneas (Layers do Colchão)**  
  *Descrição:* Indica o número de folhas/camadas de material estendidas na mesa para corte pela navalha CNC (ex: 2 camadas cortadas de uma vez).

- **(b) Pares solicitados na ordem/sessão ativa**  
  *Descrição:* Quantidade de pares que a sessão programou para aquela peça.

- **(c) Paridade / Peças por Par (1 Normal + 1 Espelhada = 2 peças/par) [Recomendado pelo Antigravity]**  
  *Descrição:* Padrão industrial consagrado do setor coureiro-calçadista (confirmado pelo manual ATOM `bdyCatalog.htm`). Indica que cada par de calçado consome 2 peças daquele molde (pé esquerdo + pé direito espelhado). Peças ímpares (como língua ou palmilha inteira) exibem `1*`; peças duplicadas ou forros podem exibir `4*`.

- **(d) Multiplicador de corte manual configurável pelo operador**  
  *Descrição:* Campo livre editável na tabela de peças do artigo.

### Sua Escolha:
> `[   ]` (Preencha com a letra da sua escolha)

---

## Pergunta 3 — Paleta e Identidade Visual (Mockup)

Conforme a **Regra de Ouro #3** do projeto CorteAC ("*Preservação visual Win32 MDI — as cores do Comelz não podem substituir a identidade Win32 do CorteAC*"), apresentamos 3 opções de acabamento estético em `docs/FASE6_0_MOCKUP.md`:

### Alternativas:
- **(a) Fiel ao Comelz (Teal Escuro + Verde Oliva)**  
  *Descrição:* Janela e moldura inteiramente em tom teal escuro (`#13383e`), painel de botões oliva (`#4e5d43`) e grid cinza asfalto. Visual idêntico ao software Comelz original.  
  *Atenção:* Pode causar descontinuidade visual em relação às demais janelas MDI do CorteAC (`OrderView`, `LayoutEditorView`).

- **(b) Win32 Clássico Rigoroso (Cinza Windows XP / Windows 2000)**  
  *Descrição:* 100% cinza neutro Win32 (`#d4d0c8`), título azul marinho (`#0a246a`), botões clássicos 3D em relevo e células do grid em fundo branco (`#ffffff`) com borda rebaixada.  
  *Vantagem:* Integração perfeita com o tema histórico do sistema.

- **(c) Híbrido: Casca Win32 MDI + Grid CAD Técnico Escuro [Recomendado pelo Antigravity]**  
  *Descrição:* A estrutura da janela, barra de título MDI (`#0a246a`), barra de status inferior e o painel de 10 botões seguem 100% o padrão Win32 clássico. Apenas o miolo interno do Canvas onde os moldes são desenhados adota fundo escuro de alto contraste (`#1e293b`), realçando os contornos brancos, o magenta das costuras e o amarelo dos piques sem ofuscar a visão do operador de corte.

### Sua Escolha:
> `[   ]` (Preencha com a letra da sua escolha)

---

## Próximo Passo

Assim que as 3 decisões forem confirmadas pelo operador humano e validadas pelo revisor externo DeepSeek, o escopo da **Fase 6.1 (Implementação do `ShapeCatalogView`)** será formalmente autorizado para desenvolvimento.
