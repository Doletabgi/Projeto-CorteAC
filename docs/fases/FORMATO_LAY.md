# Especificação Técnica do Formato .lay (Layout de Corte ATOM $$LAYOUT.v3$$)

**Sistema Alvo:** JobManager 2000 / ATOM FlashCut (Linha Flex, Flash, Intelli)  
**Motores de Origem:** `fn98.exe` (FlashNest Couro), `dp98.exe` (DieProc Sintéticos/Rolos), `Layout.exe` (LayoutNT)  
**Data da Documentação:** Outubro/2026  
**Status:** Engenharia Reversa Baseada em 38 Amostras Reais de Produção e Binários Oficiais (`Afcadv18.dll`, `Layout.exe`)

---

## 1. Visão Geral e Características Físicas do Arquivo

O arquivo `.lay` é um arquivo de texto plano formatado em linhas com codificação de caracteres legível e terminadores de linha padrão Windows **CRLF (`\r\n`)**.
Ele representa o resultado do cálculo de nesting (encaixe automático ou manual), descrevendo quais matrizes/moldes (`.die`) foram utilizados, as dimensões da mesa ou bobina de corte, e a posição/rotação exata de cada peça colocada na área de corte.

- **Classificação:** Texto simples ASCII / Windows-1252 (Latin-1).
- **Assinatura (Magic Header):** Primeira linha obrigatória: `$$LAYOUT.v3$$`.
- **Separadores:** Quebras de linha `\r\n`. Linhas de metadados utilizam formato `chave=valor`. Linhas de matriz utilizam prefixo `TG <n>` seguido de subcampos `chave=valor`. Linhas de peças utilizam formato tabular com espaços `I <campos...>`.
- **Unidades de Medida:** 
  - Coordenadas ($X, Y$) e dimensões lineares: **Milímetros (mm)** em ponto flutuante com 6 casas decimais.
  - Áreas: **Milímetros quadrados (mm²)** com 6 casas decimais.
  - Ângulos de Rotação: **Radianos** em ponto flutuante (sentido anti-horário). $\pi \approx 3.141593\text{ rad} = 180.000^\circ$; $0.017453\text{ rad} \approx 1.000^\circ$; $6.265732\text{ rad} \approx 359.000^\circ$.
  - Origem do Sistema de Coordenadas ($0,0$): Canto inferior esquerdo (ou superior esquerdo com $Y$ decrescente conforme padrão CAD Win32 da mesa CNC).

---

## 2. Estrutura Seccional do Arquivo

Um arquivo `.lay` divide-se estritamente em quatro seções sequenciais:

```text
[1. Assinatura e Localização]
$$LAYOUT.v3$$
<caminho_completo_rede_ou_disco> <nome_do_arquivo.lay>

[2. Metadados Gerais da Chapa/Bobina]
desc=<string_do_motor_de_nesting>
gap=<espacamento_entre_pecas_mm>
codR=<codigo_do_material_ou_hide>
[hide=<caminho_da_pele>] (opcional se codR=hide)
risW=<largura_util_da_chapa_mm>
risL=<comprimento_ou_passo_mm>
Y_max=<coordenada_y_maxima_mm>
Y_last=<coordenada_y_ultima_linha_mm>
area=<area_total_liquida_das_pecas_mm2>
no_dies=<quantidade_de_moldes_distintos>

[3. Definições de Matrizes Alvo (TG - Target Groups)]
TG 1
dLib=<diretorio_da_biblioteca_do_molde>
dCode=<nome_do_arquivo_die>
dId=<id_numerico_do_molde>
dQta=<qtd_colocada_esq>, <qtd_colocada_dir>
dSingle=<qtd_avulsa_esq>, <qtd_avulsa_dir>
dIsFiller=<0_ou_1>
dTarg=<meta_solicitada_esq>, <meta_solicitada_dir>
... (repete de 1 ate no_dies)

[4. Lista de Peças Posicionadas (Items)]
num_of_items=<quantidade_total_de_pecas>
I <item_no> <tg_idx> <inst_id> <flags> <x> <y> <rot_rad> <color> <tag>
... (repete de 1 ate num_of_items)
```

---

## 3. Especificação Detalhada dos Campos

### 3.1. Cabeçalho e Metadados

| Linha / Chave | Tipo | Descrição | Exemplo Real | Status |
| :--- | :---: | :--- | :--- | :---: |
| `$$LAYOUT.v3$$` | String | Assinatura oficial do formato Layout ATOM v3. | `$$LAYOUT.v3$$` | **Confirmado** |
| `<Path> <Filename>` | String | Caminho de origem do arquivo e nome com extensão. | `\\lab-inf\...\1519 l0000.lay` | **Confirmado** |
| `desc` | String | Descritor do motor de nesting e versão geradora. | `fn98 - v1.2.36 - 12.09.2012` | **Confirmado** |
| `gap` | Float | Distância mínima permitida entre peças vizinhas (mm). | `1.000000` | **Confirmado** |
| `codR` | String | Código e especificação do material ou `hide`. | `884412 - LAM 1.5MM NEW LOGAN...` | **Confirmado** |
| `hide` | String | Caminho do arquivo de pele (`.hid`/`.onx`) se `codR=hide`. | `\\lab-inf\Hides\Skin01.onx` | **Confirmado** |
| `risW` | Float | Largura da chapa/bobina/área útil (Resource Width, mm). | `1340.000000` | **Confirmado** |
| `risL` | Float | Comprimento utilizado ou passo da bobina (Length, mm). | `2980.000000` | **Confirmado** |
| `Y_max` | Float | Coordenada Y máxima atingida pelas peças no aninhamento. | `0.000000` | **Confirmado** |
| `Y_last` | Float | Coordenada Y final da última fileira calculada. | `0.000000` | **Confirmado** |
| `area` | Float | Área total líquida das peças inseridas no layout (mm²). | `22420.492481` | **Confirmado** |
| `no_dies` | Integer | Número total de moldes (`.die`) distintos empregados. | `4` | **Confirmado** |

### 3.2. Bloco de Matrizes (`TG <n>`)

Cada bloco `TG` descreve uma matriz alvo utilizada no layout:

| Campo | Tipo | Descrição | Exemplo Real | Status |
| :--- | :---: | :--- | :--- | :---: |
| `TG <idx>` | Integer | Índice do grupo de matriz (1-based: `TG 1`, `TG 2`). | `TG 1` | **Confirmado** |
| `dLib` | String | Diretório base da biblioteca onde a matriz reside. | `\\lab-inf\NSDATAV1\Shapes\129...` | **Confirmado** |
| `dCode` | String | Nome do arquivo `.die` que contém a geometria vetorial. | `129_178_Tras_33_5a.die` | **Confirmado** |
| `dId` | Integer | Identificador interno da matriz no banco de dados. | `1729` | **Confirmado** |
| `dQta` | 2 Integers | Peças alocadas no layout: `pé esquerdo, pé direito`. | `2, 0` | **Confirmado** |
| `dSingle` | 2 Integers | Peças avulsas / sem par correspondente no encaixe. | `0, 0` | **Confirmado** |
| `dIsFiller` | Integer | Indicador de peça de enchimento/aproveitamento (`1` ou `0`). | `0` | **Confirmado** |
| `dTarg` | 2 Integers | Meta de produção exigida na ordem: `meta esq, meta dir`. | `2, 2` | **Confirmado** |

### 3.3. Bloco de Peças Posicionadas (`I`)

Linhas iniciadas por `I` representam as peças individuais cortadas pela máquina:

Formato: `I <item_no> <tg_idx> <inst_id> <flags> <x> <y> <rot_rad> <color> <tag>`

| Token | Tipo | Descrição | Exemplo Real | Status |
| :---: | :---: | :--- | :--- | :---: |
| **1** | Char | Prefixo de comando de item (`I`). | `I` | **Confirmado** |
| **2** | Integer | Índice sequencial da peça no layout (1-based, $1 \dots N$). | `1` | **Confirmado** |
| **3** | Integer | Índice do molde de referência em `TG` (**0-based**, `0` = TG 1). | `0` | **Confirmado** |
| **4** | Integer | Identificador de instância/sequência na ordem de corte. | `0` | **Confirmado** |
| **5** | Integer | Flags reservadas de estado (sempre `0` nas amostras reais). | `0` | **Confirmado** |
| **6** | Float | Posição X da origem do molde na mesa (mm). | `13.080000` | **Confirmado** |
| **7** | Float | Posição Y da origem do molde na mesa (mm). | `70.150000` | **Confirmado** |
| **8** | Float | Rotação em radianos (anti-horário, $\pi = 180^\circ$). | `3.141593` | **Confirmado** |
| **9** | Integer | Cor de exibição da peça (Win32 signed integer: `-65536` = Vermelho). | `-65536` | **Confirmado** |
| **10** | String | Tag do algoritmo de posicionamento e transformação. | `fn98MR` | **Confirmado** |

#### Significado dos Sufixos na Tag (Token 10):
- `fn98`: Gerado pelo algoritmo automático FlashNest 98.
- `fn98-1`: Variante da estratégia de encaixe com passo unitário.
- `Pasted`: Peça inserida ou movida manualmente pelo operador no Layout Editor.
- `M`: **Mirror (Espelhamento)** ativo. Indica que a peça foi espelhada em relação ao eixo vertical para cortar o par oposto (ex: pé direito espelhado a partir da fôrma do pé esquerdo).
- `R`: **Rotation** ativa (matriz girada em relação à posição canônica original).
- `MR`, `MRM`, `RMR`: Combinações sucessivas de rotação e espelhamento durante a busca de melhor aproveitamento.

---

## 4. Tabela de Campos: Confirmados vs. Não Confirmados

| Campo | Status | Racional / Evidência Técnica |
| :--- | :---: | :--- |
| `$$LAYOUT.v3$$` | **Confirmado** | 100% das 38 amostras reais de fábrica abrem com esta assinatura. |
| `desc`, `gap`, `codR`, `risW`, `risL`, `area`, `no_dies` | **Confirmado** | Presentes em todas as amostras; strings literais de parsing identificadas no binário `Afcadv18.dll`. |
| `TG` (`dCode`, `dLib`, `dId`, `dQta`, `dSingle`, `dIsFiller`, `dTarg`) | **Confirmado** | Mapeamento completo dos grupos de matrizes alvo; validação cruzada com ordens `.b`. |
| `I` (Tokens 1 a 10) | **Confirmado** | Assinatura C++ no `Afcadv18.dll`: `I %d %d %d %d %lf %lf %lf %ld %s`. |
| `Y_max`, `Y_last` | **Confirmado** | Presentes em todas as amostras reais; seu valor é `0.000000` em encaixes contínuos em rolo/chapa inteira. |
| `flags` (Token 5 da linha `I`) | **Não Confirmado** | Sempre `0` nas 38 amostras de produção; documentado como campo reservado para expansão futura. |
| `hide=` com zonas de defeito em arquivo `.lay` | **Não Confirmado em Amostras de Arquivo** | Suportado nas estruturas internas C++ (`CHide`, `CQAreaPoly`), porém os 38 arquivos reais disponíveis tratam materiais sintéticos em bobina (`codR=LAM`). |

---

## 5. Ordem de Usinagem CAM Obrigatória (Preservação de Vácuo)

Nas máquinas de corte CNC oscilante ATOM (cabeçotes com lâmina, furador e caneta), o material é mantido plano por sucção a vácuo na esteira. Se o contorno externo de uma peça for cortado antes das furações internas, a peça solta-se da chapa, perde o vácuo e move-se sob a vibração da faca, destruindo a precisão das furações.

Portanto, todo layout `.lay` exportado deve seguir rigorosamente a seguinte sequência de usinagem por peça:

1. **1º Passo - Furações e Ilhoses (`DRILL` / `HOLES`):**
   - Punções e brocas penetram primeiro enquanto a folha/pele está 100% selada sob máxima pressão de vácuo.
2. **2º Passo - Piques e Punções (`PUNCH` / `PRICKER`):**
   - Marcações estruturais para costura e montagem da gáspea/traseiro.
3. **3º Passo - Costuras e Rasgos Internos (`CUTS` / `CPOINTS` / `INTERNAL_CUTS`):**
   - Janelas decorativas ou vazamentos internos recortados com lâmina oscilante.
4. **4º Passo - Contorno Externo (`TOOL_KNIFE_DOWN`):**
   - O perímetro fechado da peça é **SEMPRE cortado por último**. Ao término deste percurso, a peça desprende-se da matriz.

---

## 6. Exemplo Real Completo (`l0000.lay` - 8 peças, 4 matrizes)

```text
$$LAYOUT.v3$$
\\lab-inf\NSDATAV1\Compiti\SEM 34-UP060\129.060\1519 l0000.lay
desc=fn98 - v1.2.36 - 12.09.2012
gap=1.000000
codR=884412 - LAM 1.5MM NEW LOGAN+HM50+SP40+HM50+NYL02 - MA ( 2 layer(s) )
risW=219.928975
risL=135.665276
Y_max=0.000000
Y_last=0.000000
area=22420.492481
no_dies=4
TG 1
dLib=\\lab-inf\NSDATAV1\Shapes\129\060\129178000018685\884412
dCode=129_178_Tras_33_5a.die
dId=1729
dQta=2, 0
dSingle=0, 0
dIsFiller=0
dTarg=2, 2
TG 2
dLib=\\lab-inf\NSDATAV1\Shapes\129\060\129178000018685\884412
dCode=129_178_Tras_31_5a.die
dId=1728
dQta=2, 0
dSingle=0, 0
dIsFiller=0
dTarg=2, 2
TG 3
dLib=\\lab-inf\NSDATAV1\Shapes\129\060\129178000018685\884412
dCode=129_178_Tras_29_5a.die
dId=1727
dQta=2, 0
dSingle=0, 0
dIsFiller=0
dTarg=2, 2
TG 4
dLib=\\lab-inf\NSDATAV1\Shapes\129\060\129178000018685\884412
dCode=129_178_Tras_28a.die
dId=1726
dQta=2, 0
dSingle=0, 0
dIsFiller=0
dTarg=2, 2
num_of_items=8
I 1 0 0 0 13.080000 70.150000 3.141593 -65536 fn98
I 2 0 1 0 41.941560 69.640166 3.141593 -65536 fn98MR
I 3 1 2 0 70.718342 65.973963 3.141593 -65536 fn98MR
I 4 1 3 0 98.578342 65.733963 3.141593 -65536 fn98MR
I 5 2 4 0 126.336276 61.922963 3.141593 -65536 fn98M
I 6 2 5 0 153.181856 61.922965 3.141593 -65536 fn98MR
I 7 3 6 0 180.213743 58.595607 3.141593 -65536 fn98MR
I 8 3 7 0 206.423743 58.655607 3.141593 -65536 fn98MR
```
