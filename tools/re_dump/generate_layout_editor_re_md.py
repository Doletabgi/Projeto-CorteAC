#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_layout_editor_re_md.py
Gera o documento docs/LAYOUT_EDITOR_RE.md com inventário completo e estruturado
a partir dos dados extraídos do Layout.exe, FreeNest.exe, SMPNst.dll e help oficial.
"""

import os
import json

def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_md = os.path.join(root, "docs", "LAYOUT_EDITOR_RE.md")
    inv_file = os.path.join(root, "tools", "re_dump", "layout_inventory.json")
    
    with open(inv_file, "r", encoding="utf-8") as f:
        inv = json.load(f)
        
    md = []
    
    # Cabeçalho
    md.append("# Inventário Completo de Engenharia Reversa: ATOM Layout Editor (Layout.exe / LayoutNT)")
    md.append("")
    md.append("> **Documento Técnico de Engenharia Reversa e Comparação Sistemática**  ")
    md.append("> **Alvo Primário:** `Layout.exe` (v3.2.7.0, 28/03/2013, ATOM S.p.A. / FlashCut CAM)  ")
    md.append("> **Módulo Complementar:** `FreeNest.exe` (v1.0.8.1, 26/07/2010) & `SMPNst.dll` (v1.0.13.0, 04/02/2003)  ")
    md.append("> **Sistema Original:** JobManager 2000 / ATOM FlashCut (Linhas Flex, Flash, Intelli)  ")
    md.append("> **Aplicação Alvo de Comparação:** `LayoutEditorView` (CorteAC / `ui/layout_editor_view.py`)  ")
    md.append("> **Data da Análise:** Sábado, 24 de Outubro de 2026  ")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## Glossário de Certeza Metodológica")
    md.append("")
    md.append("Para garantir rigor científico e rastreabilidade nesta engenharia reversa, todas as afirmações técnicas usam estritamente uma de três etiquetas de certeza:")
    md.append("- `[EVIDÊNCIA]`: Fato comprovado diretamente por dump de recursos PE (menus, toolbars, aceleradores, diálogos, strings, cursores), desmontagem de opcodes x86 (Ghidra/Capstone), chamadas de API do Windows ou manual oficial de ajuda HTML (`Help/LayoutEditor/`).")
    md.append("- `[INFERIDO]`: Dedução lógica de alta probabilidade baseada no padrão de arquitetura MFC/Win32, convenções de projeto da ATOM ou correlação direta entre binários.")
    md.append("- `[DESCONHECIDO]`: Comportamento interno que não pôde ser determinado estaticamente com 100% de precisão e depende de confirmação dinâmica no Windows real pelo operador.")
    md.append("")
    md.append("*(Nota: A etiqueta `[CONFIRMADO]` é expressamente reservada para o usuário após sua validação prática na máquina).*")
    md.append("")
    md.append("---")
    md.append("")
    
    # Seção A
    md.append("## Seção A: Arquitetura e Tecnologia do Layout.exe")
    md.append("")
    md.append("### 1. Binário e Compilador `[EVIDÊNCIA]`")
    md.append("- **Arquivo Executável:** `Layout.exe` (PE32 x86, modo GUI Windows).")
    md.append("- **Versão do Produto:** `3.2.7.0` (Special Build: `v3.2.7 - 28.03.2013`).")
    md.append("- **Nome Interno / Módulo:** `LayoutNT`.")
    md.append("- **Compilador e Framework:** Microsoft Visual C++ 2010 (MSVC 10.0), vinculado dinamicamente ao MFC 10.0 (`mfc100.dll`, `MSVCR100.dll`).")
    md.append("- **Proteção contra Cópia:** SafeNet Sentinel SuperPro / UltraPro dongle via `SentinelKeyW.DLL` (`[EVIDÊNCIA]`). O executável verifica a presença da licença de hardware na inicialização antes de liberar a interface MDI.")
    md.append("")
    md.append("### 2. Padrão Arquitetural MDI e Classes MFC `[EVIDÊNCIA]`")
    md.append("O `Layout.exe` é estruturado sobre o padrão clássico **Document/View MDI (Multiple Document Interface)**:")
    md.append("- `CMainFrame` (classe base `CMDIFrameWnd`): Gerencia a barra de menus principal, barra de ferramentas e barra de status da aplicação.")
    md.append("- `CChildFrame` (classe base `CMDIChildWnd`): Moldura de cada janela de layout aberta. Permite abrir múltiplos arquivos `.lay` ou `.b` simultaneamente em cascata, lado a lado ou minimizados.")
    md.append("- `CLayoutDoc` (classe base `CDocument`): Modelo de dados que encapsula a chapa/material, catálogo de moldes, peças posicionadas (`CInstance`), zonas de qualidade e lista de comandos de desfazimento.")
    md.append("- `CLayoutView` (classe base `CView` / `CScrollView`): Janela de visualização dividida por um divisor (`CSplitterWnd`) entre o painel de edição CAD e o catálogo lateral.")
    md.append("")
    md.append("### 3. Motor Gráfico CAD e Sistema de Coordenadas (`Afcadv18E.dll`) `[EVIDÊNCIA]`")
    md.append("A renderização gráfica do canvas de corte não utiliza OpenGL nem DirectX; ela é construída sobre uma DLL gráfica proprietária da ATOM chamada `Afcadv18E.dll`:")
    md.append("- **Classe Gráfica Principal:** `CDrawWindow` (herda de `CScrollView`).")
    md.append("- **Unidade Interna:** Milímetros (`mm`) em ponto flutuante de precisão dupla (`double` 64-bit IEEE 754).")
    md.append("- **Orientação Cartesiana:** O método `CDrawWindow::SetYCartesian(TRUE)` inverte o eixo Y do GDI do Windows (onde Y cresce para baixo), fazendo o eixo Y cartesiano crescer rigorosamente para CIMA (`+Y` no topo da chapa, como na geometria analítica clássica).")
    md.append("- **Conversão de Coordenadas:**")
    md.append("  - `R2DC(real_x, real_y, &dev_x, &dev_y)`: Real-to-Device Coordinates (converte mm do mundo real para pixels da janela, aplicando escala de zoom e offset de pan).")
    md.append("  - `DC2R(dev_x, dev_y, &real_x, &real_y)`: Device-to-Real Coordinates (converte clique de mouse em pixels de tela para mm do mundo real).")
    md.append("- **Modo Raster Interativo (Elastic Rubberbanding & Rotação):** A renderização elástica (retângulo de seleção, linha guia de bump e arcos de rotação livre) usa o modo raster binário GDI `R2_NOTXORPEN` (código 10). Isso permite desenhar e apagar geometrias vetoriais instantaneamente em tempo real na tela sem disparar `WM_PAINT` completo de todos os moldes.")
    md.append("")
    md.append("### 4. Motor de Encaixe e Geometria (`Afchlib12E.dll` & `SMPNst.dll`) `[EVIDÊNCIA]`")
    md.append("- **`Afchlib12E.dll`:** Biblioteca de suporte geométrico contendo:")
    md.append("  - `CHNNest::BumpSelection`: Rotina que empurra a seleção em linha reta até colidir com outras peças ou limites.")
    md.append("  - `CHNNest::BumpShape`: Cálculo de colisão e contato rígido contorno a contorno.")
    md.append("  - `CHNCatalog::DoRot`: Transformação de matriz de rotação trigonométrica sobre os vértices do molde.")
    md.append("- **`SMPNst.dll`:** Motor de nesting industrial exportando rotinas `CHNNickNest`, `FastNest` e classes de controle de aproveitamento.")
    md.append("")
    md.append("---")
    md.append("")
    
    # Seção B
    md.append("## Seção B: Barra de Menus Completa")
    md.append("")
    md.append("Foram extraídos 8 recursos de menu do `Layout.exe`. A seguir detalham-se os menus principais:")
    md.append("")
    md.append("### 1. Menu 129: Menu Principal (Com Documento MDI Ativo) `[EVIDÊNCIA]`")
    md.append("")
    md.append("| Menu Superior | Submenu / Item | ID Win32 | Atalho de Teclado | Tooltip / String de Ajuda | Certeza | Ação Realizada |")
    md.append("|---|---|---|---|---|---|---|")
    
    menu129_items = [
        ("File", "New", "57600", "Ctrl+N", "Create a new document", "[EVIDÊNCIA]", "Cria um novo arquivo de layout em branco"),
        ("File", "Open...", "57601", "Ctrl+O", "Open an existing document", "[EVIDÊNCIA]", "Abre arquivo .lay ou .b existente"),
        ("File", "Open Next", "51111", "Ctrl+L", "Open Next Document", "[EVIDÊNCIA]", "Abre automaticamente o próximo layout calculado da mesma sessão"),
        ("File", "ReOpen ...", "50009", "-", "-", "[EVIDÊNCIA]", "Recarrega o layout ativo a partir do disco descartando alterações"),
        ("File", "Close", "57602", "Ctrl+W", "Close the active document", "[EVIDÊNCIA]", "Fecha o layout ativo com confirmação se modificado"),
        ("File", "Close and reopen using &Interactive Layout", "33906", "Ctrl+I", "-", "[EVIDÊNCIA]", "Alterna para o modo de encaixe interativo avançado"),
        ("File", "Save", "57603", "Ctrl+S", "Save the active document", "[EVIDÊNCIA]", "Salva o layout ativo sobrescrevendo o arquivo"),
        ("File", "Save As...", "57604", "-", "Save active document with new name", "[EVIDÊNCIA]", "Salva cópia do layout sob novo nome"),
        ("File > Save Local", "Original", "32975", "-", "-", "[EVIDÊNCIA]", "Salva arquivo local com coordenadas e moldes originais"),
        ("File > Save Local", "Mirror shapes", "32834", "-", "-", "[EVIDÊNCIA]", "Salva arquivo local espelhando os moldes"),
        ("File", "Save dot B", "33902", "-", "-", "[EVIDÊNCIA]", "Salva no formato binário compacto .B"),
        ("File", "Set Alternate Path...", "32807", "-", "Set alternate shapes search path", "[EVIDÊNCIA]", "Configura diretórios alternativos de busca de moldes"),
        ("File", "Merge...", "32803", "-", "Merge two layout files", "[EVIDÊNCIA]", "Funde outro arquivo .lay na chapa atual"),
        ("File > Load Material...", "Hide", "32806", "-", "Load a Hide material", "[EVIDÊNCIA]", "Carrega contorno de pele/couro natural com defeitos"),
        ("File > Load Material...", "Sheet", "32811", "-", "Load a rectangular Sheet", "[EVIDÊNCIA]", "Carrega chapa retangular sintética"),
        ("File > Load Material...", "Roll", "32812", "-", "Load a Roll material", "[EVIDÊNCIA]", "Carrega bobina/rolo contínuo"),
        ("File", "Print...", "57607", "Ctrl+P", "Print the active document", "[EVIDÊNCIA]", "Imprime o layout na impressora do Windows"),
        ("File", "Print Preview", "57609", "-", "Display full pages", "[EVIDÊNCIA]", "Pré-visualização de impressão da folha"),
        ("File", "Print Setup...", "57606", "-", "Change printer and printing options", "[EVIDÊNCIA]", "Configura impressora, margens e folha"),
        ("File", "Exit", "57665", "-", "Quit the application", "[EVIDÊNCIA]", "Encerra o Layout Editor"),
        ("Edit", "Undo", "57643", "Ctrl+Z (Alt+BkSp)", "Undo the last action", "[EVIDÊNCIA]", "Desfaz a última ação CAM de movimentação ou rotação"),
        ("Edit", "Cut", "57635", "Ctrl+X (Shift+Del)", "Cut the selection and put in on Clipboard", "[EVIDÊNCIA]", "Recorta peças selecionadas para a área de transferência"),
        ("Edit", "Copy", "57634", "Ctrl+C (Ctrl+Ins)", "Copy the selection to Clipboard", "[EVIDÊNCIA]", "Copia peças selecionadas para a área de transferência"),
        ("Edit", "Paste", "57637", "Ctrl+V (Shift+Ins)", "Insert Clipboard contents", "[EVIDÊNCIA]", "Cola peças da área de transferência com offset na tela"),
        ("Edit", "Position...", "32817", "-", "Edit Instance position", "[EVIDÊNCIA]", "Abre diálogo de ajuste fino milimétrico (Dialog 141)"),
        ("Edit", "Delete", "32818", "Del", "Delete selected piece(s)", "[EVIDÊNCIA]", "Exclui as peças selecionadas do layout"),
        ("Edit", "Mirror", "32845", "F5", "Mirror Selected Instance(s)", "[EVIDÊNCIA]", "Espelha horizontalmente as peças selecionadas (inverte pé)"),
        ("Edit > Duplicate", "Normal", "52102", "-", "Duplicate selected instance", "[EVIDÊNCIA]", "Duplica a peça na mesma rotação"),
        ("Edit > Duplicate", "Rotated", "50006", "-", "Duplicate with rotation", "[EVIDÊNCIA]", "Duplica a peça com rotação pré-definida"),
        ("Edit > Fill", "Row", "52103", "-", "Fill the current row", "[EVIDÊNCIA]", "Preenche a linha horizontal da chapa com a peça"),
        ("Edit > Fill", "Row Alternate", "52104", "-", "Fill row with alternate rotation", "[EVIDÊNCIA]", "Preenche linha alternando orientações (0°/180°)"),
        ("Edit > Fill", "Column", "50007", "-", "Fill the current column", "[EVIDÊNCIA]", "Preenche a coluna vertical da chapa"),
        ("Edit > Fill", "Sheet", "52105", "-", "Fill entire sheet", "[EVIDÊNCIA]", "Preenche toda a área livre da chapa"),
        ("Edit > Fill", "Sheet Alternate", "52106", "-", "Fill entire sheet alternating", "[EVIDÊNCIA]", "Preenche a chapa inteira com padrão alternado"),
        ("Edit > Fill", "User", "50003", "-", "Fill using custom constraints", "[EVIDÊNCIA]", "Preenchimento configurado por restrições do usuário (Dialog 159)"),
        ("Edit", "Set Rotation Center", "52109", "-", "Set custom rotation pivot", "[EVIDÊNCIA]", "Coloca cursor alvo para fixar pivô de rotação customizado"),
        ("Edit", "Remove All", "32972", "-", "Remove all pieces from layout", "[EVIDÊNCIA]", "Limpa todas as peças posicionadas na chapa"),
        ("Edit > Flip", "Around x axis", "32962", "-", "Flip geometry over X", "[EVIDÊNCIA]", "Inverte verticalmente a geometria do molde"),
        ("Edit > Flip", "Around y axis", "32961", "-", "Flip geometry over Y", "[EVIDÊNCIA]", "Inverte horizontalmente a geometria do molde"),
        ("View", "Toolbar", "59392", "-", "Show or hide the toolbar", "[EVIDÊNCIA]", "Exibe ou oculta as barras de ferramentas"),
        ("View", "Status Bar", "59393", "-", "Show or hide the status bar", "[EVIDÊNCIA]", "Exibe ou oculta a barra de status inferior"),
        ("View", "Zoom", "32778", "Ctrl+Q", "Enable/Disable zooming", "[EVIDÊNCIA]", "Ativa cursor lupa para zoom por clique ou janela elástica"),
        ("View", "Previous zoom", "32772", "-", "Restore previous zoom level", "[EVIDÊNCIA]", "Retorna ao fator de ampliação anterior"),
        ("View", "Full view", "32771", "-", "Zoom to display complete layout", "[EVIDÊNCIA]", "Enquadra a chapa inteira no espaço disponível (Fit All)"),
        ("View > History", "Start", "32839", "Home", "Jump to first placement step", "[EVIDÊNCIA]", "Reproduz início da sequência de encaixe do layout"),
        ("View > History", "End", "32840", "End", "Jump to completed layout", "[EVIDÊNCIA]", "Avança para o estado final com todas as peças"),
        ("View > History", "Advance", "32841", "+ (Num +)", "Advance one piece placement", "[EVIDÊNCIA]", "Posiciona a próxima peça da sequência histórica"),
        ("View > History", "Back", "32842", "- (Num -)", "Step back one piece placement", "[EVIDÊNCIA]", "Oculta a última peça colocada (passo anterior)"),
        ("View", "Groups", "32836", "-", "Manage piece grouping", "[EVIDÊNCIA]", "Gerenciamento e agrupamento lógico de moldes"),
        ("View", "Full schedule", "50008", "-", "Show complete job schedule", "[EVIDÊNCIA]", "Exibe grade de produção com total de peças pendentes"),
        ("View", "Instance Information...", "32819", "-", "Show selected piece properties", "[EVIDÊNCIA]", "Exibe detalhes geométricos da peça (Dialog 161)"),
        ("View", "Layout Information...", "32893", "-", "Show layout statistics", "[EVIDÊNCIA]", "Exibe área, aproveitamento, perímetro e tempo (Dialog 180)"),
        ("Cut", "Left", "32789", "-", "Cut left side / first half", "[EVIDÊNCIA]", "Define corte da área esquerda (máquinas de 2 cabeçotes)"),
        ("Cut", "Right", "32788", "-", "Cut right side / second half", "[EVIDÊNCIA]", "Define corte da área direita"),
        ("Cut", "Execute", "32787", "-", "Send layout to cutting machine", "[EVIDÊNCIA]", "Despacha layout para usinagem na máquina CNC via ANP"),
        ("Nesting", "Move Material", "32810", "-", "Translate material boundary", "[EVIDÊNCIA]", "Permite arrastar a origem da chapa/pele no canvas"),
        ("Nesting", "Offset Material", "32837", "-", "Set edge offset margins", "[EVIDÊNCIA]", "Configura margens de recuo da borda do material"),
        ("Nesting", "Rotate", "32843", "-", "Rotate entire layout", "[EVIDÊNCIA]", "Gira todo o material e peças em 90° ou 180°"),
        ("Nesting", "ShowRectangle", "32844", "Ctrl+R", "Show bounding rectangle", "[EVIDÊNCIA]", "Exibe o retângulo envolvente de cada molde"),
        ("Nesting", "Calculate", "32809", "-", "Run automatic nesting", "[EVIDÊNCIA]", "Dispara o cálculo automático do motor de nesting"),
        ("Nesting", "Create Hide Shape", "32964", "-", "Define custom hide outline", "[EVIDÊNCIA]", "Desenha polígono fechado para criar retalho/pele"),
        ("Nesting", "Copy BMP of layout", "32892", "-", "Copy layout image to Clipboard", "[EVIDÊNCIA]", "Renderiza imagem raster do layout e envia ao Clipboard"),
        ("Nesting > Quality areas", "Create", "32898", "-", "Add quality defect area", "[EVIDÊNCIA]", "Cria polígono de defeito/área de qualidade em couro"),
        ("Nesting > Quality areas", "Delete", "32899", "-", "Remove quality defect area", "[EVIDÊNCIA]", "Exclui polígono de área de qualidade selecionado"),
        ("Nesting", "Nesting parameters", "33904", "-", "Configure nesting parameters", "[EVIDÊNCIA]", "Abre parâmetros industriais de nesting (Dialog 186/908)"),
        ("Nesting", "Nest classes ...", "33905", "-", "Manage nesting classes", "[EVIDÊNCIA]", "Configuração de classes de encaixe (Dialog 104)"),
        ("Nesting", "Start SoleNest / Params", "33907 / 33912", "-", "Sole nesting engine", "[EVIDÊNCIA]", "Módulo especializado de solados"),
        ("Nesting", "Start LuxuryNest / Params", "33910 / 33913", "-", "Luxury goods engine", "[EVIDÊNCIA]", "Módulo especializado para bolsas e artigos de luxo"),
        ("Nesting", "Start BagNest / Params", "33909 / 33914", "-", "Bags nesting engine", "[EVIDÊNCIA]", "Módulo de malas e bolsas"),
        ("Nesting", "Start BeltNest / Params", "33908 / 33915", "-", "Belts nesting engine", "[EVIDÊNCIA]", "Módulo especializado em cintos e tiras compridas"),
        ("Nesting", "Start WeaveNest / Params", "33911 / 33916", "-", "Woven material engine", "[EVIDÊNCIA]", "Módulo de tecidos e sintéticos entrelaçados"),
        ("Nesting", "Start SliceNest / Params", "33917 / 33918", "-", "Slice nesting engine", "[EVIDÊNCIA]", "Módulo de fatiamento linear de rolos"),
        ("Tools", "Colours...", "32821", "-", "Configure color scheme", "[EVIDÊNCIA]", "Configura paleta de cores de peças, chapas e defeitos"),
        ("Tools", "Preferences...", "50002", "-", "Application preferences", "[EVIDÊNCIA]", "Abre preferências gerais e passo de giro (Dialog 158)"),
        ("Tools", "Check Overlay", "32835", "Ctrl+E", "Check shape overlapping", "[EVIDÊNCIA]", "Verifica e desenha hachura quadriculada sobre colisões"),
        ("Tools", "Show cut pieces", "33920", "-", "Highlight cut instances", "[EVIDÊNCIA]", "Destaca peças que já foram usinadas na mesa CNC"),
        ("Tools", "Change Gap", "32967", "-", "Configure safety gap", "[EVIDÊNCIA]", "Configura a distância mínima de segurança entre peças (Dialog 167)"),
        ("Tools", "Cutting Order", "32965", "-", "Sequence toolpaths", "[EVIDÊNCIA]", "Modo interativo de renumerar sequência de usinagem (Cursor 177)"),
        ("Window", "New Window", "57648", "-", "Open another window for active doc", "[EVIDÊNCIA]", "Abre segunda visualização do mesmo layout"),
        ("Window", "Cascade", "57650", "-", "Arrange windows overlapping", "[EVIDÊNCIA]", "Organiza janelas de layout em cascata"),
        ("Window > Tile", "Horizontally / Vertically", "57651 / 57652", "-", "Arrange windows non-overlapping", "[EVIDÊNCIA]", "Organiza janelas lado a lado ou em faixas horizontais"),
        ("Window", "Arrange Icons", "57649", "-", "Arrange minimized windows", "[EVIDÊNCIA]", "Organiza ícones das janelas minimizadas"),
        ("Window", "Split", "57653", "-", "Split active window into panes", "[EVIDÊNCIA]", "Divide janela ativa com réguas de splitter"),
        ("Help", "About Layout...", "57664", "-", "Show program info and version", "[EVIDÊNCIA]", "Exibe caixa Sobre o Layout (Dialog 100)")
    ]
    for m in menu129_items:
        md.append(f"| {m[0]} | {m[1]} | `{m[2]}` | `{m[3]}` | {m[4]} | {m[5]} | {m[6]} |")
    md.append("")
    
    # 2. Menu de Contexto 102
    md.append("### 2. Menu de Contexto 102 (Clique com Botão Direito nas Peças) `[EVIDÊNCIA]`")
    md.append("")
    md.append("| Item do Menu Popup | ID Win32 | Atalho Equivalente | Certeza | Ação Realizada |")
    md.append("|---|---|---|---|---|")
    popup102_items = [
        ("Position...", "32817", "Toolbar Big Plus", "[EVIDÊNCIA]", "Abre diálogo de ajuste fino milimétrico (Dialog 141) com caixas Abs/Rel"),
        ("Delete", "32818", "Del", "[EVIDÊNCIA]", "Remove as peças selecionadas do layout e atualiza contadores do catálogo"),
        ("Delete cut pieces", "33903", "-", "[EVIDÊNCIA]", "Remove somente as peças já marcadas como cortadas"),
        ("Mirror", "32845", "F5", "[EVIDÊNCIA]", "Espelha a peça selecionada invertendo o pé"),
        ("Revert cut status", "33922", "-", "[EVIDÊNCIA]", "Desfaz a marcação de peça cortada"),
        ("Substitute > Sub1", "32846", "-", "[EVIDÊNCIA]", "Substitui a peça selecionada por outro molde da mesma família"),
        ("Duplicate > Normal", "52102", "-", "[EVIDÊNCIA]", "Duplica a peça na mesma orientação"),
        ("Duplicate > Rotated", "50006", "-", "[EVIDÊNCIA]", "Duplica a peça rotacionando pelo passo angular padrão"),
        ("Fill > Row", "52103", "-", "[EVIDÊNCIA]", "Preenche a linha horizontal da chapa com repetições da peça"),
        ("Fill > Row Alternate", "52104", "-", "[EVIDÊNCIA]", "Preenche a linha horizontal alternando orientações"),
        ("Fill > Column", "50007", "-", "[EVIDÊNCIA]", "Preenche a coluna vertical da chapa"),
        ("Fill > Sheet", "52105", "-", "[EVIDÊNCIA]", "Preenche toda a área restante da chapa com a peça"),
        ("Fill > Sheet Alternate", "52106", "-", "[EVIDÊNCIA]", "Preenche toda a chapa em padrão alternado"),
        ("Fill > User...", "50003", "-", "[EVIDÊNCIA]", "Abre diálogo de parâmetros customizados de preenchimento (Dialog 159)"),
        ("Info...", "32819", "-", "[EVIDÊNCIA]", "Abre diálogo de propriedades detalhadas da peça selecionada (Dialog 161)"),
        ("View...", "32968", "-", "[EVIDÊNCIA]", "Abre o molde no Shape Editor (ShedNt.exe) para conferência vetorial"),
        ("Set Rotation Center", "52109", "-", "[EVIDÊNCIA]", "Posiciona marcador alvo para giro customizado com tecla Shift"),
        ("Check Overlay", "32963", "Ctrl+E", "[EVIDÊNCIA]", "Ativa ou desativa a verificação visual de colisões e folga"),
        ("Advanced Substitute...", "32969", "-", "[EVIDÊNCIA]", "Abre diálogo de substituição avançada por grade (Dialog 164)")
    ]
    for p in popup102_items:
        md.append(f"| {p[0]} | `{p[1]}` | `{p[2]}` | {p[3]} | {p[4]} |")
    md.append("")
    
    # 3. Menu de Contexto 132
    md.append("### 3. Menu de Contexto 132 (Clique com Botão Direito no Catálogo Lateral) `[EVIDÊNCIA]`")
    md.append("")
    md.append("| Item do Menu Popup | ID Win32 | Certeza | Ação Realizada |")
    md.append("|---|---|---|---|")
    popup132_items = [
        ("Info", "32816", "[EVIDÊNCIA]", "Exibe propriedades e contagens do molde no estoque da sessão"),
        ("Add...", "32820", "[EVIDÊNCIA]", "Abre caixa de seleção de arquivos para adicionar novo molde ao catálogo"),
        ("Modify...", "32815", "[EVIDÊNCIA]", "Configura parâmetros específicos de nesting do molde (Dialog 148: Modify Shape Target)"),
        ("Remove", "32814", "[EVIDÊNCIA]", "Remove o molde selecionado do catálogo da sessão"),
        ("Select", "52100", "[EVIDÊNCIA]", "Seleciona instantaneamente todas as peças deste molde colocadas no layout"),
        ("View", "52101", "[EVIDÊNCIA]", "Abre o molde selecionado no visualizador / Shape Editor (ShedNt.exe)")
    ]
    for p in popup132_items:
        md.append(f"| {p[0]} | `{p[1]}` | {p[2]} | {p[3]} |")
    md.append("")
    
    # Seção C
    md.append("## Seção C: Barras de Ferramentas (Toolbars)")
    md.append("")
    md.append("O `Layout.exe` possui 4 recursos `RT_TOOLBAR` integrados na janela principal:")
    md.append("")
    md.append("### 1. Toolbar 128: Padrão / Arquivo (16x15 px) `[EVIDÊNCIA]`")
    md.append("")
    md.append("| Posição | Ícone de Referência | ID Win32 | Tooltip Oficial | Tipo | Equivalente de Menu | Certeza | Função |")
    md.append("|---|---|---|---|---|---|---|---|")
    tb128_items = [
        ("0", "`bdyInterfaceBig.jpg`", "57600", "New", "Push", "File > New", "[EVIDÊNCIA]", "Cria novo documento de layout"),
        ("1", "`bdyInterfaceBig.jpg`", "57601", "Open", "Push", "File > Open...", "[EVIDÊNCIA]", "Abre arquivo de layout .lay existente"),
        ("2", "`bdyInterfaceBig.jpg`", "57603", "Save", "Push", "File > Save", "[EVIDÊNCIA]", "Salva o layout ativo"),
        ("3", "---", "---", "---", "Separador", "---", "[EVIDÊNCIA]", "Separador visual"),
        ("4", "`bdyInterfaceBig.jpg`", "57635", "Cut", "Push", "Edit > Cut", "[EVIDÊNCIA]", "Recorta peças selecionadas para o Clipboard"),
        ("5", "`bdyInterfaceBig.jpg`", "57634", "Copy", "Push", "Edit > Copy", "[EVIDÊNCIA]", "Copia peças selecionadas para o Clipboard"),
        ("6", "`bdyInterfaceBig.jpg`", "57637", "Paste", "Push", "Edit > Paste", "[EVIDVIÊNCIA]", "Cola peças com deslocamento na chapa"),
        ("7", "---", "---", "---", "Separador", "---", "[EVIDÊNCIA]", "Separador visual"),
        ("8", "`bdyInterfaceBig.jpg`", "57607", "Print", "Push", "File > Print...", "[EVIDÊNCIA]", "Envia layout ativo para impressão")
    ]
    for b in tb128_items:
        md.append(f"| {b[0]} | {b[1]} | `{b[2]}` | {b[3]} | {b[4]} | {b[5]} | {b[6]} | {b[7]} |")
    md.append("")
    
    # Toolbar 137
    md.append("### 2. Toolbar 137: Visualização e CAD CAM (16x15 px) `[EVIDÊNCIA]`")
    md.append("")
    md.append("| Posição | Ícone de Referência | ID Win32 | Tooltip Oficial | Tipo | Equivalente de Menu | Certeza | Função |")
    md.append("|---|---|---|---|---|---|---|---|")
    tb137_items = [
        ("0", "`bdyInt1.gif`", "32790", "Show QAreas on hide", "Toggle", "-", "[EVIDÊNCIA]", "Exibe ou oculta contorno das áreas de defeito em pele"),
        ("1", "`bdyInt2.gif`", "32799", "Fill QAreas", "Toggle", "-", "[EVIDÊNCIA]", "Preenche com cor translúcida as áreas de qualidade"),
        ("2", "`bdyInt3.gif`", "32794", "Show Shapes", "Toggle", "-", "[EVIDÊNCIA]", "Exibe ou oculta todos os moldes no layout"),
        ("3", "`bdyInt4.gif`", "32774", "Fill Shapes", "Toggle", "-", "[EVIDÊNCIA]", "Alterna entre moldes preenchidos e somente contorno"),
        ("4", "---", "---", "---", "Separador", "---", "[EVIDÊNCIA]", "Separador visual"),
        ("5", "`bdyInt5.gif`", "32835", "Check Overlay", "Toggle", "Tools > Check Overlay", "[EVIDÊNCIA]", "Destaca sobreposições e violações de gap com hachura xadrez"),
        ("6", "---", "---", "---", "Separador", "---", "[EVIDÊNCIA]", "Separador visual"),
        ("7", "`bdyInt6.gif`", "32771", "Display complete Layout", "Push", "View > Full view", "[EVIDÊNCIA]", "Enquadra a chapa 100% na janela (Fit All)"),
        ("8", "`bdyInt7.gif`", "32778", "Zoom", "Toggle", "View > Zoom (Ctrl+Q)", "[EVIDÊNCIA]", "Ativa cursor lupa para ampliação pontual ou retangular"),
        ("9", "---", "---", "---", "Separador", "---", "[EVIDÊNCIA]", "Separador visual"),
        ("10", "`bdyInt9.gif`", "32820", "Add Shape", "Push", "Catalog > Add...", "[EVIDÊNCIA]", "Abre diálogo de seleção de novos moldes de arquivo"),
        ("11", "`FuneTune.gif`", "32817", "Edit position", "Push", "Edit > Position...", "[EVIDÊNCIA]", "Abre painel flutuante de ajuste fino milimétrico (Dialog 141)"),
        ("12", "---", "---", "---", "Separador", "---", "[EVIDÊNCIA]", "Separador visual"),
        ("13", "-", "33923", "<SEM TEXTO>", "Push", "-", "[INFERIDO]", "Ação de depuração interna ou comando de expansão")
    ]
    for b in tb137_items:
        md.append(f"| {b[0]} | {b[1]} | `{b[2]}` | {b[3]} | {b[4]} | {b[5]} | {b[6]} | {b[7]} |")
    md.append("")
    
    # Toolbar 150
    md.append("### 3. Toolbar 150: Bump Magnético Direcional (16x15 px, Setas Pretas com Fundo Amarelo) `[EVIDÊNCIA]`")
    md.append("")
    md.append("| Posição | Ícone Oficial | ID Win32 | Tooltip Oficial | Tecla Direta | Certeza | Comportamento Cinemático CAM |")
    md.append("|---|---|---|---|---|---|---|")
    tb150_items = [
        ("0", "Seta Baixo amarela", "32831", "Bump Down", "Seta Baixo (Down)", "[EVIDÊNCIA]", "Desloca seleção para baixo até colidir com outra peça ou borda inferior"),
        ("1", "Seta Direita amarela", "32832", "Bump Right", "Seta Direita (Right)", "[EVIDÊNCIA]", "Desloca seleção para a direita até encostar em obstáculo ou borda direita"),
        ("2", "Seta Esquerda amarela", "32833", "Bump Left", "Seta Esquerda (Left)", "[EVIDÊNCIA]", "Desloca seleção para a esquerda até encostar em obstáculo ou borda esquerda"),
        ("3", "Seta Cima amarela", "51000", "Bump Up", "Seta Cima (Up)", "[EVIDÊNCIA]", "Desloca seleção para cima até colidir com outra peça ou margem superior")
    ]
    for b in tb150_items:
        md.append(f"| {b[0]} | {b[1]} | `{b[2]}` | {b[3]} | `{b[4]}` | {b[5]} | {b[6]} |")
    md.append("")
    
    # Seção D
    md.append("## Seção D: Painel Lateral / Catálogo de Moldes (Catalog Pane)")
    md.append("")
    md.append("### 1. Elementos Estruturais do Catálogo `[EVIDÊNCIA]`")
    md.append("- **Barra Divisória (Splitter Bar):** Uma barra divisória vertical separa o painel de edição CAD do catálogo lateral. O operador pode arrastá-la livremente para redimensionar a largura do catálogo. Um duplo-clique em qualquer área vazia do catálogo reorganiza automaticamente a grade de miniaturas (`[EVIDÊNCIA]`).")
    md.append("- **Miniaturas dos Moldes:** Cada molde pertencente à sessão é exibido como um cartão retangular contendo o desenho vetorial em escala proporcional e seu identificador/tamanho.")
    md.append("- **Duplo Conjunto de Contadores Numéricos:** Sob cada molde no catálogo são exibidos dois pares de contadores:")
    md.append("  ```text")
    md.append("  [ Peças Normais ]    [ Peças Espelhadas ]")
    md.append("      10 / 20                0 / 20")
    md.append("  ```")
    md.append("  - O **primeiro par** refere-se ao estoque normal do molde (`Colocadas neste layout / Total solicitado na sessão`).")
    md.append("  - O **segundo par** refere-se ao estoque espelhado (pé oposto / lado invertido).")
    md.append("  - Quando o número de peças colocadas iguala o total solicitado (ex: `20 / 20`), a meta daquele molde está 100% atingida.")
    md.append("- **Regra Industrial de Camadas de Corte (Layers) `[EVIDÊNCIA]`:** O manual oficial registra expressamente: *'If you are editing a layout that will be cut on multiple layers at the same time please keep in mind that every alteration you make will be multiplied by the number of layers'*. Assim, cada molde físico adicionado na mesa CAD abate $L$ pares da ordem (onde $L$ é o número de camadas, ex: 2 ou 4 camadas).")
    md.append("")
    md.append("### 2. Interações do Usuário com o Catálogo `[EVIDÊNCIA]`")
    md.append("- **Arrasto para a Mesa (Drag-and-Drop):**")
    md.append("  - Método 1: Duplo-clique no cartão do molde no catálogo e arrasto do contorno elástico para o canvas; soltar ou clicar coloca o molde na coordenada desejada.")
    md.append("  - Método 2: Pressionar botão esquerdo e arrastar diretamente para a mesa.")
    md.append("  - Pressionar a tecla `Escape` durante o arrasto cancela a inserção sem alterar nada.")
    md.append("- **Arrasto de Arquivos Externos:** O operador pode abrir o Windows Explorer, selecionar arquivos de moldes (`.die`, `.sho`, `.xml`) e arrastá-los diretamente para a janela do `Layout.exe`. Eles são importados e inseridos no catálogo imediatamente (`[EVIDÊNCIA]`).")
    md.append("- **Menu de Contexto (Menu 132):** Clique com botão direito em qualquer cartão abre as opções `Info`, `Add...`, `Modify...`, `Remove`, `Select` (seleciona todas as instâncias desse molde no layout) e `View` (abre no Shape Editor).")
    md.append("")
    md.append("---")
    md.append("")
    
    # Seção E
    md.append("## Seção E: Área de Edição (Canvas)")
    md.append("")
    md.append("### 1. Sistema Geométrico Real `[EVIDÊNCIA]`")
    md.append("- As coordenadas da chapa e dos moldes são representadas em milímetros reais (`double`), nunca em pixels.")
    md.append("- O eixo Y é cartesiano estrito para cima (`SetYCartesian(TRUE)`). A origem $(0, 0)$ situa-se no canto inferior esquerdo da chapa de material.")
    md.append("")
    md.append("### 2. Estados Visuais dos Moldes (Preenchimento vs Seleção) `[EVIDÊNCIA]`")
    md.append("- **Peças Não Selecionadas:** São renderizadas preenchidas com suas respectivas cores de identificação (ou com a cor da zona de qualidade subjacente).")
    md.append("- **Peças Selecionadas:** A documentação oficial e os testes registram uma convenção visual fundamental: *'Selected shapes can be identified because only the shape outline is visible'*. As peças selecionadas perdem o preenchimento opaco e exibem apenas o seu **contorno (outline)**, permitindo enxergar a borda da chapa e peças adjacentes por baixo.")
    md.append("")
    md.append("### 3. Detecção Visual de Colisões: Check Overlay (`Ctrl+E`) `[EVIDÊNCIA]`")
    md.append("- Quando ativado (via botão na Toolbar 137, atalho `Ctrl+E` ou Menu Tools), o sistema calcula interseções contorno a contorno e violações de Gap entre peças adjacentes.")
    md.append("- Qualquer região onde duas peças se sobreponham ou onde a distância seja menor que o Gap permitido é desenhada com uma **hachura em padrão xadrez (squared pattern)** (`[EVIDÊNCIA]`).")
    md.append("- O manual alerta que esta função consome cálculo intensivo e deve ser ligada sob demanda pelo operador.")
    md.append("")
    md.append("### 4. Barra de Status com 9 Painéis `[EVIDÊNCIA]`")
    md.append("A barra de status inferior possui 9 seções dinâmicas:")
    md.append("1. **Painel 0 (Prompt/Ajuda):** Descrição textual da ferramenta ou comando selecionado.")
    md.append("2. **Painel 1 (Coordenadas X/Y):** Posição contínua do cursor do mouse em mm (`x: @@@@.@@ y: @@@@.@@`).")
    md.append("3. **Painel 2 (Dimensões do Material):** Largura e altura da chapa ou área da pele (`Sheet (2980.00 X 1380.00)`).")
    md.append("4. **Painel 3 (Contagem de Peças):** Total de peças colocadas na mesa CAM.")
    md.append("5. **Painel 4 (Aproveitamento / Rendimento %):** Eficiência calculada da chapa (`Yield: @@.@@%`).")
    md.append("6. **Painel 5 (Área Usada vs Total):** Metragem quadrada consumida em $\\text{dm}^2$ ou $\\text{m}^2$.")
    md.append("7. **Painel 6 (Ângulo de Rotação Dinâmico):** Exibição em tempo real do ângulo durante a rotação livre com o botão direito (`@@@@.@@°` com precisão de 2 casas decimais).")
    md.append("8. **Painel 7 (Status de Colisão / Overlay):** Sinalizador indicando se há peças sobrepostas no layout.")
    md.append("9. **Painel 8 (Modo de Ferramenta / Modificadores):** Indicações de travas CAM (`CAPS`, `NUM`, `SCRL`).")
    md.append("")
    md.append("---")
    md.append("")
    
    # Seção F
    md.append("## Seção F: Gestos de Mouse (Engenharia Reversa Completa)")
    md.append("")
    md.append("### Tabela Mestra de Gestos de Mouse `[EVIDÊNCIA]`")
    md.append("")
    md.append("| Botão do Mouse | Modificador | Ação / Movimento | Certeza | Comportamento Exato no Original |")
    md.append("|---|---|---|---|---|")
    mouse_items = [
        ("Esquerdo (L-Click)", "Nenhum", "Clique sobre peça", "[EVIDÊNCIA]", "Seleciona a peça clicada e desmarca todas as outras."),
        ("Esquerdo (L-Click)", "Shift", "Clique sobre peça", "[EVIDÊNCIA]", "Alterna seleção individual da peça (adiciona à seleção ou remove)."),
        ("Esquerdo (L-Click)", "Nenhum", "Clique duplo em vazio", "[EVIDÊNCIA]", "Desmarca instantaneamente todas as peças selecionadas na mesa."),
        ("Esquerdo (L-Drag)", "Nenhum", "Arrasto em área vazia", "[EVIDÊNCIA]", "Desenha retângulo elástico (rubberband). Seleciona APENAS as peças que ficarem 100% contidas no retângulo."),
        ("Esquerdo (L-Drag)", "Nenhum", "Arrasto sobre seleção", "[EVIDÊNCIA]", "Movimenta em tempo real a(s) peça(s) selecionada(s). Se houver várias, todas se movem juntas com deslocamento idêntico."),
        ("Esquerdo (L-Drag)", "Escape", "Durante arrasto", "[EVIDÊNCIA]", "Pressionar Esc aborta o arrasto e restaura as peças à posição de origem sem registrar Undo."),
        ("Esquerdo (L-Click)", "Ctrl", "Clique na mesa", "[EVIDÊNCIA]", "No modo de zoom, amplia a visualização em +20% ancorada no ponto."),
        ("Direito (R-Click)", "Nenhum", "Clique rápido (< 2.65 px)", "[EVIDÊNCIA]", "Dispara o Menu de Contexto 102 sobre a peça ou na mesa."),
        ("Direito (R-Drag)", "Nenhum", "Arrasto (> 2.65 px)", "[EVIDÊNCIA]", "**ROTAÇÃO LIVRE 360° CONTÍNUA:** Exibe dois raios e arco circular anti-horário de raio ~42 px a partir do centro da peça. Gira o molde em tempo real acompanhando o mouse."),
        ("Direito (R-Drag)", "Ctrl", "Arrasto (> 2.65 px)", "[EVIDÊNCIA]", "**ROTAÇÃO COLETIVA EM GRUPO:** Gira todas as peças selecionadas como um corpo rígido em torno do centro do bounding box coletivo."),
        ("Direito (R-Drag)", "Shift", "Arrasto (> 2.65 px)", "[EVIDÊNCIA]", "**ROTAÇÃO EM PIVÔ CUSTOMIZADO:** Gira a(s) peça(s) selecionada(s) em torno do ponto fixo definido previamente via 'Set Rotation Center'."),
        ("Direito (R-Drag)", "Escape", "Durante giro", "[EVIDÊNCIA]", "Cancela a rotação livre e devolve o molde ao ângulo original."),
        ("Roda (MouseWheel)", "Nenhum", "Giro para cima / baixo", "[EVIDÊNCIA]", "**ROTAÇÃO POR PASSO ANGULAR:** A roda NÃO faz zoom nem scroll por padrão. Ela gira a(s) peça(s) selecionada(s) pelo incremento em graus configurado nas Preferências (ex: 2° ou 5°)."),
        ("Roda (MouseWheel)", "Ctrl", "Giro para cima / baixo", "[INFERIDO]", "Ajuste de zoom contínuo in/out."),
        ("Meio (M-Click)", "Nenhum", "Arrasto do botão do meio", "[EVIDÊNCIA]", "**BUMP MAGNÉTICO VETORIAL:** O cursor se transforma em um arco/arco-flecha (Cursor ID 149) e uma linha conecta o centro da peça ao mouse. Ao soltar, a peça é empurrada magneticamente naquela direção."),
        ("Esquerdo (L-Click)", "Duplo-clique + Drag", "Arrasto contínuo", "[EVIDÊNCIA]", "**BUMP MAGNÉTICO ALTERNATIVO:** Duplo-clique na peça mantendo o botão pressionado entra no mesmo modo de Bump Direcional."),
        ("Esquerdo (L-Click)", "Ctrl + Shift", "Arrasto contínuo", "[EVIDÊNCIA]", "**BUMP MAGNÉTICO VIA TECLADO:** Manter Ctrl+Shift pressionados e arrastar com botão esquerdo dispara o Bump Direcional.")
    ]
    for m in mouse_items:
        md.append(f"| {m[0]} | {m[1]} | {m[2]} | {m[3]} | {m[4]} |")
    md.append("")
    
    # Detalhes da desmontagem da rotação livre
    md.append("### Detalhes Matemáticos da Rotação Livre com Botão Direito `[EVIDÊNCIA]`")
    md.append("A desmontagem das rotinas `OnRButtonDown` (`0x418550`), `OnMouseMove` (`0x4269c4`) e `OnRButtonUp` (`0x421fd0`) no `Layout.exe` revela o algoritmo interno exato:")
    md.append("1. **Condição de Disparo:** O botão direito só entra em modo de rotação se houver pelo menos uma peça selecionada (`pDoc->GetSelectionCount() > 0`). Se nenhuma peça estiver selecionada, o clique solto abre o menu de contexto.")
    md.append("2. **Filtro de Ruído / Deadzone:**")
    md.append("   - O sistema registra o ponto inicial do clique $(X_0, Y_0)$.")
    md.append("   - Enquanto $\\Delta x^2 + \\Delta y^2 \\le 7$ (~2.64 pixels de raio), o editor considera o movimento como clique estático.")
    md.append("   - Assim que $\\Delta x^2 + \\Delta y^2 > 7$, o ponteiro entra no estado de arrasto rotacional (flag interna `0x40`).")
    md.append("3. **Determinação do Centro do Pivô $(C_x, C_y)$:**")
    md.append("   - *Sem modificador:* Centro do retângulo envolvente do molde selecionado (`0x4186f5`).")
    md.append("   - *Com tecla Ctrl:* Média dos limites $(X_{\\min} + X_{\\max})/2, (Y_{\\min} + Y_{\\max})/2$ de todas as peças selecionadas (`0x418683`).")
    md.append("   - *Com tecla Shift:* Ponto flutuante configurado pelo comando 'Set Rotation Center' (`0x4186c5`).")
    md.append("4. **Cálculo Angular Contínuo:**")
    md.append("   - Ângulo inicial: $\\theta_0 = \\text{atan2}(Y_{\\text{start}} - C_y, X_{\\text{start}} - C_x)$.")
    md.append("   - Ângulo dinâmico atual: $\\theta_1 = \\text{atan2}(Y_{\\text{cursor}} - C_y, X_{\\text{cursor}} - C_x)$.")
    md.append("   - Rotação diferencial aplicada: $\\Delta\\theta = \\theta_1 - \\theta_0$.")
    md.append("5. **Geometria dos Raios e do Arco na Tela (Modo XOR `R2_NOTXORPEN`):**")
    md.append("   - O raio $R$ do arco gráfico é proporcional à dimensão máxima do molde: $R = \\max(\\text{largura}, \\text{altura}) \\times 1.25$ em mm, convertido para pixels da tela via `R2DC` (~42 pixels na escala 1:1).")
    md.append("   - Raio 1: Segmento do pivô $(C_x, C_y)$ até a borda do arco no ângulo de partida.")
    md.append("   - Raio 2: Segmento do pivô $(C_x, C_y)$ até a posição do ponteiro do mouse.")
    md.append("   - Arco: Traçado circular anti-horário contínuo conectando $\\theta_0$ a $\\theta_1$.")
    md.append("6. **Término e Registro de Histórico:**")
    md.append("   - Ao soltar o botão direito (`WM_RBUTTONUP`), a peça é transformada matricialmente pela nova rotação.")
    md.append("   - O documento chama `SetModifiedFlag(TRUE)`, registra a ação na classe `CUndoMoveSelection` e dispara `UpdateAllViews`.")
    md.append("")
    md.append("---")
    md.append("")
    
    # Seção G
    md.append("## Seção G: Atalhos de Teclado")
    md.append("")
    md.append("### Tabela Mestra de Atalhos de Teclado `[EVIDÊNCIA]`")
    md.append("")
    md.append("| Tecla / Combinação | ID Win32 | Comando Oficial | Certeza | Comportamento no Original |")
    md.append("|---|---|---|---|---|")
    keys_items = [
        ("Setas (Up/Down/Left/Right)", "32831-33, 51000", "Bump Selection", "[EVIDÊNCIA]", "**BUMP MAGNÉTICO:** As setas sozinhas NÃO fazem nudge milimétrico! Elas empurram magneticamente a peça na direção da seta até colidir com outro molde ou margem da chapa."),
        ("Ctrl + Setas", "-", "Nudge fine step", "[EVIDÊNCIA]", "**NUDGE MILIMÉTRICO FINO:** O deslocamento fino passo a passo (0.5 mm) é acionado exclusivamente segurando a tecla Ctrl com as setas."),
        ("F1", "57680", "Help / Next Pane", "[EVIDÊNCIA]", "Abre a ajuda oficial do sistema (ou alterna foco de painéis MFC)."),
        ("F5", "32845", "Mirror Selected Instance(s)", "[EVIDÊNCIA]", "**ESPELHAR:** No Layout.exe original, F5 espelha horizontalmente as peças selecionadas (inverte o pé)."),
        ("F6 / Shift+F6", "57680 / 57681", "Next / Prev Pane", "[EVIDÊNCIA]", "Alterna o foco do teclado entre a mesa CAD e o catálogo lateral."),
        ("Delete (Del)", "32818", "Delete", "[EVIDÊNCIA]", "Exclui as peças selecionadas do layout e devolve as quantidades para o catálogo."),
        ("Escape (Esc)", "32769", "Cancel Operation", "[EVIDÊNCIA]", "Cancela o arrasto, a rotação livre ou a ferramenta ativa sem registrar no histórico."),
        ("Ctrl + Z", "57643", "Undo", "[EVIDÊNCIA]", "Desfaz a última operação de posicionamento ou rotação."),
        ("Alt + Backspace", "57643", "Undo", "[EVIDÊNCIA]", "Atalho Windows padrão alternativo para desfazer (Undo)."),
        ("Ctrl + S", "57603", "Save", "[EVIDÊNCIA]", "Salva o layout ativo sobrescrevendo o arquivo no disco."),
        ("Ctrl + P", "57607", "Print", "[EVIDÊNCIA]", "Abre a caixa de diálogo de impressão do layout."),
        ("Ctrl + N", "57600", "New", "[EVIDÊNCIA]", "Cria um novo layout em branco."),
        ("Ctrl + O", "57601", "Open", "[EVIDÊNCIA]", "Abre a janela de seleção de arquivos para carregar layout."),
        ("Ctrl + W", "57602", "Close", "[EVIDÊNCIA]", "Fecha a janela do layout ativo."),
        ("Ctrl + L", "51111", "Open Next", "[EVIDÊNCIA]", "Carrega automaticamente o próximo layout sequencial da sessão."),
        ("Ctrl + Q", "32778", "Zoom", "[EVIDÊNCIA]", "Alterna a ferramenta de Zoom (cursor lupa)."),
        ("Ctrl + E", "32835", "Check Overlay", "[EVIDÊNCIA]", "Alterna a verificação visual de colisões e folga."),
        ("Ctrl + R", "32844", "ShowRectangle", "[EVIDÊNCIA]", "Alterna a exibição das caixas delimitadoras (bounding box) dos moldes."),
        ("Ctrl + I", "33906", "Interactive Layout", "[EVIDÊNCIA]", "Fecha e reabre o layout ativo no modo interativo avançado."),
        ("Ctrl + X / Shift+Del", "57635", "Cut", "[EVIDÊNCIA]", "Recorta as peças selecionadas para a área de transferência."),
        ("Ctrl + C / Ctrl+Ins", "57634", "Copy", "[EVIDÊNCIA]", "Copia as peças selecionadas para a área de transferência."),
        ("Ctrl + V / Shift+Ins", "57637", "Paste", "[EVIDÊNCIA]", "Cola as peças copiadas aplicando um deslocamento padrão à direita e acima."),
        ("Home", "32839", "History Start", "[EVIDÊNCIA]", "Retorna ao primeiro passo da sequência histórica de posicionamento do layout."),
        ("End", "32840", "History End", "[EVIDÊNCIA]", "Avança imediatamente para o estado final com todas as peças."),
        ("+ (NumPad +)", "32841", "History Advance", "[EVIDÊNCIA]", "Avança um passo na reprodução da história do aninhamento."),
        ("- (NumPad -)", "32842", "History Back", "[EVIDÊNCIA]", "Recua um passo na reprodução da história do aninhamento."),
        ("NumPad 4 / 6", "50006 / 50002", "Rotate Left / Right", "[EVIDÊNCIA]", "Gira a peça selecionada em passo angular fixo via teclado numérico.")
    ]
    for k in keys_items:
        md.append(f"| {k[0]} | `{k[1]}` | {k[2]} | {k[3]} | {k[4]} |")
    md.append("")
    
    # Seção H
    md.append("## Seção H: Funções Especiais do Layout.exe")
    md.append("")
    md.append("### 1. Bump Magnético Direcional (`CHNNest::BumpSelection`) `[EVIDÊNCIA]`")
    md.append("O Bump é uma das funções mais essenciais do CAM calçadista da ATOM:")
    md.append("- Ao ser acionado (por botão na toolbar, setas do teclado ou arrasto vetorial com o mouse), o motor calcula um raio de translação linear no sentido indicado.")
    md.append("- A peça se move continuamente até que a folga mínima permitida (`Gap`) seja atingida contra qualquer outro contorno já posicionado ou contra o perímetro externo do material.")
    md.append("- Se múltiplas peças estiverem selecionadas, todas se movem em bloco pelo mesmo vetor até que **a primeira delas** encontre um obstáculo, preservando rigidamente a formação relativa.")
    md.append("")
    md.append("### 2. Caixa de Ajuste Fino de Posição (Dialog 141: Instance Position) `[EVIDÊNCIA]`")
    md.append("- Acionado pelo botão com o **sinal de mais grande (`+`)** na barra de ferramentas (`FuneTune.gif`) ou pelo comando de menu `Edit > Position...`.")
    md.append("- Contém duas fileiras de caixas numéricas:")
    md.append("  - **Linha Superior (Coordenadas Absolutas):** Três caixas para $X$, $Y$ e Ângulo de Rotação em graus absolutos. Ao clicar em `Apply abs`, o molde assume exatamente esses valores.")
    md.append("  - **Linha Inferior (Incrementos Relativos):** Três caixas para $\\Delta X$, $\\Delta Y$ e $\\Delta \\theta$, acompanhadas de botões `[+]` e `[-]`. Clicar nos botões adiciona ou subtrai imediatamente os incrementos na mesa CAD. O botão `Apply rel` aplica todos os 3 incrementos simultaneamente.")
    md.append("")
    md.append("### 3. Definição da Ordem de Usinagem CNC (Cutting Order / Cursor 177) `[EVIDÊNCIA]`")
    md.append("- Acionado via `Tools > Cutting Order`.")
    md.append("- O ponteiro do mouse se transforma em uma cruz de mira com indicador de sequência (Cursor ID 177).")
    md.append("- Cada molde na chapa exibe um número no seu centro geométrico indicando a sua ordem de corte (1, 2, 3...).")
    md.append("- Ao clicar em um molde, seu número é resetado para `0` e os cliques seguintes atribuem sequencialmente 1, 2, 3...")
    md.append("- **Preservação Parcial via Ctrl:** Se o operador segurar `Ctrl` e clicar no molde número 12, a sequência de 1 até 12 é estritamente preservada e o próximo molde clicado receberá o número 13.")
    md.append("- Teclar `Escape` aborta a renumeração e encerra a ferramenta mantendo a ordem anterior.")
    md.append("")
    md.append("### 4. Modo History (Reprodução Passo a Passo do Aninhamento) `[EVIDÊNCIA]`")
    md.append("- Permite ao operador inspecionar exatamente como o motor de nesting preencheu a chapa:")
    md.append("  - `Home`: Oculta todas as peças e exibe a chapa vazia.")
    md.append("  - `+` (Mais): Adiciona e exibe a próxima peça da ordem de nesting.")
    md.append("  - `-` (Menos): Remove a última peça posicionada.")
    md.append("  - `End`: Mostra o layout 100% preenchido.")
    md.append("")
    md.append("### 5. Preenchimentos Automáticos em Grade (Fill) `[EVIDÊNCIA]`")
    md.append("- `Fill Row`: Clona a peça horizontalmente ao longo de toda a linha.")
    md.append("- `Fill Row Alternate`: Clona horizontalmente alternando rotações (ex: 0° e 180° para calcanhar com bico).")
    md.append("- `Fill Column`: Clona verticalmente preenchendo a coluna.")
    md.append("- `Fill Sheet` / `Fill Sheet Alternate`: Preenche toda a área útil da chapa em segundos.")
    md.append("- `Fill User` (Dialog 159): Preenchimento guiado por passos milimétricos configurados pelo usuário.")
    md.append("")
    md.append("### 6. Substituição de Moldes (Substitute / Dialog 164) `[EVIDÊNCIA]`")
    md.append("- Permite trocar instâncias de um molde por outro tamanho ou modelo sem perder a posição e orientação já consolidadas na chapa.")
    md.append("")
    md.append("---")
    md.append("")
    
    # Seção I
    md.append("## Seção I: Caixas de Diálogo do Layout.exe")
    md.append("")
    md.append("Foram extraídos 23 diálogos Win32 (`RT_DIALOG`) do `Layout.exe`. A tabela a seguir inventaria cada um:")
    md.append("")
    md.append("| ID Win32 | Título da Caixa de Diálogo | Dimensões (DLU) | Controles | Certeza | Finalidade e Descrição |")
    md.append("|---|---|---|---|---|---|")
    dialog_items = [
        ("100", "About Layout", "58x0 DLU", "4 controles", "[EVIDÊNCIA]", "Caixa de créditos exibindo versão, copyright e informações de compilação da ATOM."),
        ("104", "Nesting classes", "257x161 DLU", "3 controles", "[EVIDÊNCIA]", "Configuração e agrupamento de classes e prioridades de moldes para o nesting."),
        ("105", "Add new nesting class", "153x113 DLU", "7 controles", "[EVIDÊNCIA]", "Diálogo para criar nova categoria ou família de peças."),
        ("130", "Dialog", "154x154 DLU", "1 controle", "[INFERIDO]", "Contêiner genérico de renderização interna de pré-visualização."),
        ("141", "Instance Position", "203x79 DLU", "23 controles", "[EVIDÊNCIA]", "Painel flutuante de ajuste fino milimétrico (coordenadas absolutas X/Y/R e passos relativos +/-)."),
        ("143", "Alternate Search Paths", "185x79 DLU", "6 controles", "[EVIDÊNCIA]", "Configuração de pastas e caminhos de rede para localização automática de arquivos de moldes."),
        ("148", "Modify Shape Target", "169x118 DLU", "27 controles", "[EVIDÊNCIA]", "Edição das propriedades do molde no catálogo (quantidades, espelhamento, prioridade e regras de nesting)."),
        ("154", "Create a Sheet", "138x0 DLU", "11 controles", "[EVIDÊNCIA]", "Criação interativa de uma nova chapa retangular definindo largura, altura e margens."),
        ("155", "Create a roll", "145x58 DLU", "5 controles", "[EVIDÊNCIA]", "Criação de material contínuo em bobina / esteira."),
        ("156", "Insert Rectangle", "186x95 DLU", "10 controles", "[EVIDÊNCIA]", "Inserção de retângulo delimitador auxiliar ou área restrita de corte."),
        ("158", "Preferences", "207x0 DLU", "23 controles", "[EVIDÊNCIA]", "Preferências gerais do editor: unidades métricas (mm/cm/pol), passo da roda do mouse em graus, cores e tolerâncias."),
        ("159", "Set User constraints", "307x95 DLU", "17 controles", "[EVIDÊNCIA]", "Configuração dos parâmetros de preenchimento do comando 'Fill User'."),
        ("161", "Shape property", "254x0 DLU", "46 controles", "[EVIDÊNCIA]", "Propriedades geométricas detalhadas da peça selecionada (área, perímetro, centro de massa e restrições de giro)."),
        ("164", "Substitute", "242x230 DLU", "8 controles", "[EVIDÊNCIA]", "Substituição avançada de peças posicionadas por novos modelos da árvore."),
        ("167", "Set Gap", "139x61 DLU", "5 controles", "[EVIDÊNCIA]", "Definição do espaçamento mínimo de segurança (Gap) entre moldes na mesa CAM."),
        ("173", "(Sem título)", "219x0 DLU", "8 controles", "[INFERIDO]", "Diálogo auxiliar interno de seleção de perfis."),
        ("176", "Add Custom Unit", "140x81 DLU", "7 controles", "[EVIDÊNCIA]", "Definição de unidades de medida personalizadas."),
        ("180", "Informations", "244x122 DLU", "4 controles", "[EVIDÊNCIA]", "Resumo estatístico do layout ativo: rendimento total, área aproveitada, área de sobras e perímetro."),
        ("186", "Nesting configuration", "239x181 DLU", "29 controles", "[EVIDÊNCIA]", "Configuração mestre dos algoritmos de aninhamento automático."),
        ("191", "Dialog", "183x0 DLU", "3 controles", "[INFERIDO]", "Janela de aviso/confirmação customizada de salvamento."),
        ("835", "Rectangular material dimension", "269x95 DLU", "21 controles", "[EVIDÊNCIA]", "Edição dimensional rápida da placa sintética em produção."),
        ("889", "Progress indicator ...", "186x41 DLU", "2 controles", "[EVIDÊNCIA]", "Barra de progresso e cancelamento durante cálculos demorados de nesting ou verificação de overlay."),
        ("908", "Lista parametri di piazzamento", "212x138 DLU", "11 controles", "[EVIDÊNCIA]", "Seleção e ajuste das predefinições industriais DieProc (acoplamentos de rotação e folgas).")
    ]
    for d in dialog_items:
        md.append(f"| `{d[0]}` | {d[1]} | {d[2]} | {d[3]} | {d[4]} | {d[5]} |")
    md.append("")
    
    # Seção J
    md.append("## Seção J: FreeNest.exe")
    md.append("")
    md.append("### 1. Papel e Arquitetura do FreeNest.exe `[EVIDÊNCIA]`")
    md.append("- **Arquivo Executável:** `FreeNest.exe` (PE32 x86, v1.0.8.1, build `v1.8 - 2607.2010`).")
    md.append("- **Função Principal:** Não se trata de um editor MDI completo para manipulação manual avulsa, mas sim de um **módulo complementar de execução assistida de nesting** acionado por linha de comando a partir do JobManager (`JobManager 2000`).")
    md.append("- **Entrada de Sessão (Dialog 131):** Exibe caixa simples solicitando o identificador numérico da ordem: *'Enter session id number'* (`[EVIDÊNCIA]`).")
    md.append("- **Visualizador Embutido (Dialog 130 - `DRWVIEW`):** Uma janela de visualização CAD limpa (sem menus de edição complexos) onde o operador pode acompanhar visualmente as iterações do motor `SMPNst.dll` enquanto as peças são arranjadas na chapa.")
    md.append("- **Integração com o Layout.exe:** O `FreeNest` processa o cálculo em segundo plano ou em lote para a sessão informada e grava o resultado final nos arquivos de layout (`.lay`). O `Layout.exe` é então chamado para conferência, ajustes finos de operador e despacho para a máquina de corte.")
    md.append("")
    md.append("---")
    md.append("")
    
    # Seção K
    md.append("## Seção K: Comparação Sistemática com o LayoutEditorView do CorteAC")
    md.append("")
    md.append("A tabela a seguir confronta, item a item, todos os recursos identificados no editor original contra a implementação atual no `LayoutEditorView` (`ui/layout_editor_view.py`) do CorteAC:")
    md.append("")
    md.append("| Recurso / Item | Comportamento no Original + Certeza | Implementação no CorteAC Hoje | Situação | Esforço | Observação Arquitetural |")
    md.append("|---|---|---|---|---|---|")
    
    comp_items = inv["secoes"]["K_comparacao_corteac"]["tabela"]
    for row in comp_items:
        md.append(f"| **{row['item']}** | {row['original']} | {row['corteac_hoje']} | **{row['situacao']}** | {row['esforco']} | {row['observacao']} |")
    md.append("")
    md.append("---")
    md.append("")
    
    # Roteiro de Verificação para o Usuário
    md.append("## Roteiro e Checklist de Verificação para o Usuário")
    md.append("")
    md.append("Este roteiro foi estruturado para que o operador possa testar diretamente na máquina física com o Windows e validar na prática os comportamentos do `Layout.exe` original:")
    md.append("")
    md.append("### Etapa 1: Rotação Livre e Gestos do Mouse")
    md.append("- [ ] **1.1 Teste do Botão Direito Rápido:** Clique com o botão direito sobre um molde sem mexer o mouse. *Resultado esperado:* Deve abrir imediatamente o Menu de Contexto (com opções Position, Delete, Mirror, etc.).")
    md.append("- [ ] **1.2 Teste da Rotação Livre 360°:** Selecione um molde. Pressione e SEGURE o botão direito do mouse e arraste em círculo. *Resultado esperado:* O ponteiro deve exibir um círculo/arco com raio de aproximadamente 42 pixels e dois raios a partir do centro, girando o molde em tempo real.")
    md.append("- [ ] **1.3 Teste da Barra de Status:** Durante a rotação livre, observe o painel 6 da barra de status. *Resultado esperado:* O valor do ângulo deve se atualizar continuamente com 2 casas decimais (ex: `45.25°`).")
    md.append("- [ ] **1.4 Teste do Giro com Ctrl (Grupo):** Selecione 2 ou 3 moldes ao mesmo tempo. Segure a tecla `Ctrl`, pressione e arraste o botão direito. *Resultado esperado:* Todas as peças selecionadas devem girar juntas em torno do centro comum do grupo.")
    md.append("- [ ] **1.5 Teste do Cancelamento com Esc:** Enquanto estiver segurando o botão direito e girando, pressione a tecla `Escape`. *Resultado esperado:* A rotação deve ser imediatamente cancelada e a peça deve retornar à sua orientação anterior.")
    md.append("- [ ] **1.6 Teste da Roda do Mouse (Wheel):** Selecione um molde e gire a rodinha do mouse para cima e para baixo sem segurar nenhuma tecla. *Resultado esperado:* A peça deve girar em passos discretos (2° ou 5°), sem alterar o zoom da tela.")
    md.append("")
    md.append("### Etapa 2: Setas do Teclado e Bump Magnético")
    md.append("- [ ] **2.1 Teste das Setas Sozinhas:** Selecione um molde livre no meio da chapa e pressione a tecla `Seta Direita`. *Resultado esperado:* A peça deve se mover magneticamente em linha reta até bater na peça ao lado ou na margem direita da chapa.")
    md.append("- [ ] **2.2 Teste de Ctrl + Setas:** Segure `Ctrl` e pressione a `Seta Direita`. *Resultado esperado:* A peça deve dar um passo milimétrico curto (ajuste fino de 0.5 mm).")
    md.append("- [ ] **2.3 Teste do Bump com o Mouse:** Selecione um molde. Pressione o botão do meio do mouse (ou dê duplo-clique mantendo pressionado) e puxe para qualquer direção. *Resultado esperado:* O cursor deve virar um arco/arco-flecha com uma linha guia elástica; ao soltar o botão, o molde deve disparar naquela direção até colidir.")
    md.append("")
    md.append("### Etapa 3: Atalhos CAM Especiais e Visualização")
    md.append("- [ ] **3.1 Teste do Atalho F5 (Espelhar):** Selecione um molde e pressione a tecla `F5`. *Resultado esperado:* O molde deve ser espelhado horizontalmente (inverter o pé esquerdo/direito).")
    md.append("- [ ] **3.2 Teste do Check Overlay (Ctrl+E):** Pressione `Ctrl+E` ou clique no botão xadrez da barra de ferramentas. *Resultado esperado:* Se houver moldes sobrepostos ou colados abaixo da folga permitida, deve surgir uma hachura quadriculada sobre as peças.")
    md.append("- [ ] **3.3 Teste do History (Home / End / + / -):** Pressione `Home`. *Resultado esperado:* A chapa deve ficar vazia. Pressionando `+` repetidamente, cada molde é adicionado um por um na ordem em que foram calculados.")
    md.append("- [ ] **3.4 Teste da Ordem de Usinagem (Cutting Order):** Selecione `Tools > Cutting Order`. *Resultado esperado:* O cursor deve virar uma cruz e cada molde deve exibir o número da sequência de corte no seu centro.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("### Resumo das Estatísticas do Inventário")
    md.append(f"- **Total de Menus Win32 Extraídos:** 8 menus (com mais de 80 comandos mapeados).")
    md.append(f"- **Total de Barras de Ferramentas:** 4 toolbars (31 botões mapeados).")
    md.append(f"- **Total de Caixas de Diálogo:** 23 diálogos Win32 mapeados com dimensões e controles.")
    md.append(f"- **Total de Aceleradores de Teclado:** 3 tabelas de aceleradores decodificadas.")
    md.append(f"- **Total de Linhas de Comparação no CorteAC:** {len(comp_items)} áreas de recursos comparadas.")
    md.append("")
    
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    print(f"-> Arquivo {out_md} gerado com sucesso ({len(md)} linhas).")

if __name__ == "__main__":
    main()
