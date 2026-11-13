# Guia de Instalação e Testes no Windows 10 e Windows 11

Este guia foi elaborado para que qualquer usuário consiga baixar, executar e testar o **OpenCorte** rapidamente em computadores com **Windows 10** ou **Windows 11**.

---

## Opção 1: Baixar a Versão Pronta (.exe Standalone) - [Recomendada]

Você **não precisa instalar o Python nem configurar nada**. Basta baixar o pacote pronto gerado automaticamente pelo GitHub Actions:

1. Acesse a página oficial de lançamentos (Releases):
   👉 **[https://github.com/Doletabgi/Projeto-CorteAC/releases](https://github.com/Doletabgi/Projeto-CorteAC/releases)**
2. Localize a versão mais recente e baixe o arquivo:
   📦 **`OpenCorte-Windows-x64.zip`** (ou `OpenCorte.exe`)
3. Extraia o conteúdo do arquivo `.zip` em uma pasta de sua preferência (ex: `C:\CorteAC` ou na sua Área de Trabalho).
4. Dê duplo clique no arquivo **`OpenCorte.exe`**.

> **Nota sobre o Banco de Dados:**
> Ao abrir pela primeira vez, o OpenCorte cria automaticamente seu banco de dados SQLite local (`jobmanager.db`) na mesma pasta do executável, garantindo que todas as ordens, modelos e chapas fiquem salvas permanentemente.

> **Aviso do Windows Defender / SmartScreen:**
> Como o executável é recém-gerado com PyInstaller e não possui certificado digital comercial pago, o Windows SmartScreen pode exibir uma tela azul ("O Windows protegeu o seu computador").
> Basta clicar em **"Mais informações"** e depois no botão **"Executar assim mesmo"**.

---

## Opção 2: Executar a partir do Código Fonte (com Python)

Se você clonou o repositório ou baixou o código-fonte compactado (`Download ZIP`):

1. **Instale o Python 3 (versão 3.10 ou superior):**
   - Baixe no site oficial: [https://www.python.org/downloads/](https://www.python.org/downloads/)
   - ⚠️ **MUITO IMPORTANTE:** Durante a instalação, marque a opção **"Add python.exe to PATH"** (Adicionar Python ao PATH).
2. Na pasta do projeto, dê duplo clique no script:
   🚀 **`executar_windows.bat`** (ou `run.bat`)
3. O script verificará o ambiente, instalará automaticamente as bibliotecas necessárias (`Pillow`, `pymysql`, `cryptography`) e abrirá o OpenCorte na tela.

---

## Opção 3: Compilar o Executável (.exe) na sua própria máquina

Caso deseje gerar um novo arquivo executável localmente:

1. Com o Python e o PyInstaller instalados, execute no terminal da pasta do projeto:
   **`python atualizar.py --build`**
2. Aguarde o processo de compilação do PyInstaller.
3. Ao finalizar, o executável estará pronto na pasta:
   📂 `dist\OpenCorte.exe`

---

## Salvar Sessão para a Máquina (rede ou pendrive)

No **Layout Editor**, clique no botão **📤** da toolbar (ou use **Arquivo → 📤 Salvar Sessão para Máquina…**):

1. Escolha a pasta de destino (rede ou pendrive).
2. O OpenCorte cria `<destino>\<código da sessão>\` com:
   - todas as placas da sessão (`lay0000.lay`, `lay0001.lay`, ...);
   - `Shapes\` contendo somente os `.die` usados;
   - `manifest.json` com a lista de placas, moldes e avisos.
3. O último destino fica memorizado para a próxima exportação.

No **Auto-Nest em Massa**, marque **“📤 Salvar cada sessão na pasta da máquina após o cálculo”** para exportar automaticamente cada sessão do lote.

> Se a máquina ATOM não encontrar as facas, verifique o `dLib` no `.lay` e a pasta `Shapes`; o `manifest.json` lista os moldes ausentes e os que foram gerados a partir do banco.

---

## Suporte a Banco de Dados MySQL (Opcional)

Por padrão, o OpenCorte funciona 100% offline com **SQLite** sem precisar configurar nenhum servidor.

Para configurar pela tela:
1. Abra **Ferramentas → Conexão com Banco de Dados**.
2. Escolha **Somente neste computador** ou **Compartilhado na rede (MySQL)**.
3. Para MySQL, preencha endereço do servidor, nome do banco, usuário e senha fornecidos pelo responsável pela rede. A porta padrão é 3306.
4. Clique em **Testar conexão** e depois em **Salvar configuração**. Salvar também testa a conexão automaticamente.
5. Feche e abra o OpenCorte para usar a configuração salva. Os dados existentes não serão transferidos entre os bancos.

A configuração é gravada no arquivo `db.ini`, ao lado do executável. A edição manual continua disponível usando `db.example.ini` como modelo.

## Ícone do atalho na Área de Trabalho

O executável `OpenCorte.exe` já carrega o ícone oficial (`assets/app_icon.ico`) gerado a cada
release. O atalho da Área de Trabalho herda esse ícone automaticamente **quando criado a partir
do .exe**. Se você substituiu o `.exe` na mesma pasta, o Windows mantém o ícone antigo em cache:
para atualizar, crie um atalho novo (botão direito no `OpenCorte.exe` → Enviar para → Área de
Trabalho) ou reinicie o Explorer (`taskkill /f /im explorer.exe && start explorer`).

## Atalho versionado na Área de Trabalho

O pacote Windows traz `criar_atalho_windows.ps1` e `versao.txt`. Clique com o botão direito no
`criar_atalho_windows.ps1` → **Executar com PowerShell** (ou
`powershell -ExecutionPolicy Bypass -File .\criar_atalho_windows.ps1`).

Ele cria o atalho **`CorteAC-<versão>.lnk`** (ex.: `CorteAC-1.6.11.lnk`) apontando para o
`OpenCorte.exe`, usando o ícone embutido no executável, e **remove os atalhos antigos** do OpenCorte
da Área de Trabalho. Assim o operador sempre sabe qual build está instalado.

O setup oferece **Instalar localmente** ou **Usar um servidor na rede**. No modo
de rede, informe apenas nome/IP ou uma raiz como `\\SERVIDOR\Fabrica`: o setup
deriva as pastas Moldes e Sessoes e o host MySQL. Veja
[Instalação local ou rede](docs/fases/INSTALACAO_LOCAL_OU_REDE.md).
