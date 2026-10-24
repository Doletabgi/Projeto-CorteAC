# Guia de Instalação e Testes no Windows 10 e Windows 11

Este guia foi elaborado para que qualquer usuário consiga baixar, executar e testar o **CorteAC** rapidamente em computadores com **Windows 10** ou **Windows 11**.

---

## Opção 1: Baixar a Versão Pronta (.exe Standalone) - [Recomendada]

Você **não precisa instalar o Python nem configurar nada**. Basta baixar o pacote pronto gerado automaticamente pelo GitHub Actions:

1. Acesse a página oficial de lançamentos (Releases):
   👉 **[https://github.com/Doletabgi/Projeto-CorteAC/releases](https://github.com/Doletabgi/Projeto-CorteAC/releases)**
2. Localize a versão mais recente e baixe o arquivo:
   📦 **`CorteAC-Windows-x64.zip`** (ou `CorteAC.exe`)
3. Extraia o conteúdo do arquivo `.zip` em uma pasta de sua preferência (ex: `C:\CorteAC` ou na sua Área de Trabalho).
4. Dê duplo clique no arquivo **`CorteAC.exe`**.

> **Nota sobre o Banco de Dados:**
> Ao abrir pela primeira vez, o CorteAC cria automaticamente seu banco de dados SQLite local (`jobmanager.db`) na mesma pasta do executável, garantindo que todas as ordens, modelos e chapas fiquem salvas permanentemente.

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
3. O script verificará o ambiente, instalará automaticamente as bibliotecas necessárias (`Pillow`, `pymysql`, `cryptography`) e abrirá o CorteAC na tela.

---

## Opção 3: Compilar o Executável (.exe) na sua própria máquina

Caso deseje gerar um novo arquivo executável localmente:

1. Com o Python instalado, dê duplo clique em:
   🛠️ **`build_exe_windows.bat`**
2. Aguarde o processo de compilação do PyInstaller.
3. Ao finalizar, o executável estará pronto na pasta:
   📂 `dist\CorteAC.exe`

---

## Suporte a Banco de Dados MySQL (Opcional)

Por padrão, o CorteAC funciona 100% offline com **SQLite** sem precisar configurar nenhum servidor.

Se desejar conectar ao servidor de banco de dados corporativo **MySQL**:
1. Renomeie o arquivo `db.example.ini` para `db.ini`.
2. Abra o `db.ini` com o Bloco de Notas e preencha o IP do host, usuário, senha e porta do seu servidor MySQL.
3. Ao abrir o CorteAC, ele alternará automaticamente para o backend MySQL com failover automático para SQLite em caso de perda de conexão.
