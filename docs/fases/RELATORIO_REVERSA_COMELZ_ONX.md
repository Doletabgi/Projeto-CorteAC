# Plano de Implementação: Dupla Saída de Layout (ATOM .lay + Comelz .onx)

Este documento detalha as descobertas da engenharia reversa realizada na pasta `comelz/`, a especificação técnica do formato de corte da máquina Comelz (`.onx`), e a arquitetura para implantar a **Dupla Saída de Layout** no JobManager 2000 (Python Edition), permitindo salvar encaixes para as máquinas ATOM e Comelz simultaneamente.

---

## 1. Descobertas da Engenharia Reversa (REA)

### 1.1. Ecossistema de Software Comelz
Investigamos os binários contidos no instalador `Comelz-CAM-22A.18-setup.exe` e os arquivos de corte da sessão `1791878926705/`:
- **`skins/AS74467.onx` (3.949 bytes)**: Arquivo real de produção enviado para a máquina de corte Comelz.
- **`gl.exe` (44.8 MB x86)**: Controlador CNC da máquina de corte Comelz CM44 (C++/Qt/IrrXML/czlib).
- **`NestingViewer.exe` (13 MB)**: Visualizador CAM oficial da Comelz (empacotado em PyInstaller 2.1+, Python 2.7).
- Descriptografamos os módulos Python protegidos com a chave AES-128 `mGiz44YV6O1tVQuk` encontrada no executável e descompilamos os fontes oficiais da Comelz:
  - `czlib/pysrc/czlib.py`: Código-fonte completo do container `CZLIB`.
  - `parsers/onx_parser.py`: Parser oficial do formato ONX.
  - `qa/nesting_marshaller.py` & `qa/placed_part.py`: Estruturas de dados de peças posicionadas.

### 1.2. Especificação do Formato .ONX
- **Container `CZLIB\x02`**:
  - Bytes 0 a 5: `CZLIB\x02` (`43 5A 4C 49 42 02`).
  - Bytes 6 em diante: Stream BZIP2 modificado. O algoritmo oficial da Comelz comprime os dados em BZIP2 e **remove os 10 bytes iniciais** (`BZh91AY&SY`). Na leitura, reinjeta essa assinatura de 10 bytes antes de descomprimir.
  - Teste de reversão bit a bit em Python nativo (`bz2`): **100% de correspondência** (o arquivo `AS74467.onx` de 3.949 bytes expandiu perfeitamente para 29.692 bytes de XML UTF-8 e recomprimiu para os mesmos 3.949 bytes).
- **Estrutura XML (Schema ONX v1.1)**:
  - `<security><cuttable /></security>`: Flag de autorização de corte CNC.
  - `<material id="..." type="sheet" width="1360" height="386.09" margin-top="15" margin-left="15" margin-bottom="15" margin-right="15" layers="4">`: Dimensões da chapa/pele, espessura, margens e camadas.
  - `<qualityarea layer="0" level="0"><path>15,15;15,372;1345,372;1345,15;15,15</path></qualityarea>`: Delimitação da área útil de corte em mm.
  - `<models>`: Moldes referenciados (`<model src="...">` ou `<cmzdata><![CDATA[...]]></cmzdata>`).
  - `<part name="..." size="..." mirrored="false|true" area="...">`: Peças aninhadas.
  - `<placement x="..." y="..." a="..." status="placed" sortnumber="N"/>`:
    - `x`, `y`: Posição $(X, Y)$ em milímetros.
    - `a`: Rotação angular em radianos (ex: $0$, $-\pi$).
    - `sortnumber`: Ordem sequencial de usinagem na máquina Comelz.
  - `<applications>`: Parâmetros CNC de usinagem do cabeçote Comelz (`cut_xy_vel`, `cut_xy_acc`, `cut_vel_fustelle`, `cut_order="fiep"`).

---

## 2. Matriz Comparativa: ATOM (.lay) vs Comelz (.onx)

| Parâmetro | ATOM FlashCut (`.lay`) | Comelz CNC (`.onx`) | Estratégia de Mapeamento |
| :--- | :--- | :--- | :--- |
| **Formato** | Texto plano ANSI (`\r\n`) com seções sequenciais | XML UTF-8 comprimido com `CZLIB\x02` (bzip2 customizado) | Geradores dedicados em `cad/` acionados pelo mesmo dataset |
| **Dimensões** | Linhas `ris_w <W>` e `ris_l <H>` | Atributos `<material width="W" height="H">` | Mapeamento direto de largura e comprimento |
| **Margens** | Não declaradas formalmente | Atributos `margin-top/left/bottom/right` (padrão 15mm) | Margens configuráveis com cálculo da área útil |
| **Peças / Posição** | Linha `I <idx> <tg> <id> <flags> <x> <y> <rad> ...` | `<placement x="..." y="..." a="..." status="placed"/>` | Coordenadas $(X, Y)$ em mm e ângulo em radianos |
| **Espelhamento** | Flag/tag `fn98MR` | Atributo `mirrored="true"` em `<part>` | Mapeamento do booleano `is_mirrored` |
| **Gap (Distância)** | Campo `gap <val>` | Tag `<info name="parts_distance"><val></info>` | Mapeamento do gap da chapa |
| **Ordem de Corte** | Sequência das linhas `I` (furos $\rightarrow$ piques $\rightarrow$ contorno) | Atributo `sortnumber="N"` em `<placement>` | Mesma sequência ótima Strip-TSP + 2-Opt |

---

## 3. User Review Required

> [!IMPORTANT]
> **Aprovação do Relatório e Especificação Antes de Alterações**:
> O usuário solicitou expressamente: *"mas primeiro solte um relatorio antes de implatar com todos os dados"*. 
> O relatório técnico completo está estruturado neste plano e no arquivo de documentação técnica do projeto. Aguardamos sua validação para iniciar a escrita dos códigos de produção.

> [!NOTE]
> **Pure Python 3.12**:
> Toda a implementação de compressão `CZLIB\x02` e serialização XML Comelz será feita em **Python puro**, utilizando a biblioteca padrão `bz2` e `xml.etree.ElementTree`, sem necessidade de instalar DLLs, compiladores C++ ou pacotes externos proprietários da Comelz.

---

## 4. Proposed Changes

### Módulo CAD de Baixo Nível (Compressão & Serialização)

#### [NEW] [czlib.py](file:///home/dola/Documentos/clone%20do%20job/teste_dola_win11_pendrive/app/cad/czlib.py)
- Implementação limpa do algoritmo `CZLIB` versões 1 e 2.
- `compress_czlib(data: bytes) -> bytes`: Compacta via `bz2.BZ2Compressor(9)`, suprime o header de 10 bytes (`BZh91AY&SY`) e prefixa `CZLIB\x02`.
- `decompress_czlib(data: bytes) -> bytes`: Valida a assinatura de 6 bytes, injeta `BZh91AY&SY` e descompacta via `bz2.BZ2Decompressor`.

#### [NEW] [onx_exporter.py](file:///home/dola/Documentos/clone%20do%20job/teste_dola_win11_pendrive/app/cad/onx_exporter.py)
- Construtor do documento XML Comelz ONX v1.1 (`http://www.comelz.com/onx`).
- Geração dos nós `<security><cuttable /></security>`, `<metadata>`, `<material>`, `<qualityarea>`, `<models>`, `<part>`, `<placement>` e `<applications>`.
- Função: `export_onx_from_pieces(placed_pieces, material, filename="layout.onx", margins_mm=15.0) -> bytes`.

#### [NEW] [dual_exporter.py](file:///home/dola/Documentos/clone%20do%20job/teste_dola_win11_pendrive/app/cad/dual_exporter.py)
- Orquestrador unificado para exportação singular ou dupla:
  - `export_atom_lay(...)`: Grava arquivo `.lay` padrão ATOM.
  - `export_comelz_onx(...)`: Grava arquivo `.onx` padrão Comelz.
  - `export_dual_layout(...)`: Grava simultaneamente os dois arquivos no diretório de destino (`<nome>.lay` e `<nome>.onx`).

---

### Interface Gráfica (UI)

#### [MODIFY] [layout_editor_view.py](file:///home/dola/Documentos/clone%20do%20job/teste_dola_win11_pendrive/app/ui/layout_editor_view.py)
- Atualizar `export_layout_dialog` para incluir opções de salvamento:
  1. `Dupla Saída (.lay + .onx) (*.lay;*.onx)` (Padrão)
  2. `Layout de Corte ATOM (*.lay)`
  3. `Layout de Corte Comelz (*.onx)`
- Adicionar botão rápido na barra de ferramentas ou menu de contexto: **"⚡ Dupla Saída (.lay + .onx)"**.
- Notificar na barra de status o salvamento em ambas as máquinas.

#### [MODIFY] [session_view.py](file:///home/dola/Documentos/clone%20do%20job/teste_dola_win11_pendrive/app/ui/session_view.py)
- Adicionar opção de exportação dupla nos layouts gerados pela ordem de produção.

---

### Testes Automatizados

#### [NEW] [test_dual_exporter.py](file:///home/dola/Documentos/clone%20do%20job/teste_dola_win11_pendrive/app/tests/test_dual_exporter.py)
- Testes unitários para `cad/czlib.py`:
  - Round-trip de compressão e descompressão.
  - Compatibilidade com o arquivo real `AS74467.onx`.
- Testes de integridade de `cad/onx_exporter.py`:
  - Validação da árvore XML gerada contra o schema Comelz.
  - Validação de coordenadas, rotações e contadores de peças.
- Testes de consistência de `cad/dual_exporter.py`:
  - Verificação de gravação simultânea de `.lay` e `.onx`.

---

## 5. Verification Plan

### Testes Automatizados
```bash
# Executar suíte de testes de exportação dupla
python3 -m unittest teste_dola_win11_pendrive/app/tests/test_dual_exporter.py

# Executar suíte completa de testes do sistema (garantir não-regressão)
python3 -m unittest teste_dola_win11_pendrive/app/tests/test_lay_parser.py
python3 -m unittest teste_dola_win11_pendrive/app/tests/test_layout_editor_shortcuts.py
```

### Verificação Manual
1. Abrir um layout no `LayoutEditorView`.
2. Clicar em "Exportar Layout" e selecionar "Dupla Saída (.lay + .onx)".
3. Verificar que foram gerados dois arquivos: `<arquivo>.lay` e `<arquivo>.onx`.
4. Validar o arquivo `.onx` gerado com o descompressor `czlib.py` e inspecionar a árvore XML.
5. Inspecionar o arquivo `.lay` no visualizador de layout.
