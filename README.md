# JobManager 2000 — Edição Python para Windows 10 / 11

Recriação moderna em **Python** do sistema legado **JobManager 2000 (Jm2k)** e **Atom Nesting System** (originalmente desenvolvido em Visual Basic 6 para Windows XP).

---

## 🚀 Principais Melhorias em relação à versão do WinXP

1. **Compatibilidade Nativa com Windows 10 / 11 e Linux**:
   - Não requer drivers legados de 16/32 bits de porta paralela ou USB (`eusk2par.sys`, `eusk3usb.sys`, `skeyvdd.dll`).
   - Não depende de componentes ActiveX/OCX obsoletos (`COMCTL32.OCX`, `GridEX16.ocx`, etc.) que falham em sistemas de 64 bits.
   - Não depende de DAO 3.5/3.6 ou MDAC descontinuados — utiliza banco de dados **SQLite** rápido e integrado.

2. **Mesa de Corte CAD Interativa**:
   - Canvas vetorial 2D com suporte a **Pan** (arrastar com botão direito/meio) e **Zoom** (rodinha do mouse).
   - Manipulação de peças por arrastar e soltar (*drag & drop*) e rotação com a tecla **`R`**.
   - Cálculo em tempo real do **Rendimento de Material (*Yield %*)** e área útil cortada.

3. **Motor de Aninhamento Automático (*Auto-Nest*)**:
   - Algoritmo de empacotamento inteligente de alta densidade que recria a função do antigo *FreeNest.exe*.

4. **Simulador de Corte e Estimador de Tempo ATOM**:
   - Animação do cabeçote de corte CNC percorrendo os contornos em tempo real.
   - Cálculo preciso de tempo de ciclo (*ATOM Cutting Time Estimator*) baseado na velocidade de 650 mm/s e punções.

5. **Exportação CNC**:
   - Geração de arquivos **G-Code / ISO CNC** prontos para máquinas de corte industrial da ATOM (série FlashCut Flex).
   - Exportação de relatórios de produção em **XML** baseados no modelo original `Report.xsl`.

---

## 💻 Como Executar no Windows 10

### Opção 1: Executar Direto pelo Arquivo BAT
Basta dar um duplo clique no arquivo:
```cmd
run.bat
```

### Opção 2: Pelo Prompt de Comando / PowerShell
Certifique-se de ter o Python 3 instalado no Windows (disponível na Microsoft Store ou em [python.org](https://python.org)):
```cmd
cd jobmanager-win10-python
python main.py
```

---

## 📦 Como Gerar e Usar o Executável Standalone (Sem necessidade do Python)

### No Linux (Já Compilado!):
O executável de teste já foi compilado e está disponível em:
```bash
./dist/teste_dola
```
Para recompilar a qualquer momento no Linux:
```bash
./build_linux.sh
```

### No Windows 10 / 11:
Para gerar o executável `.exe` direto no Windows:
1. Dê um duplo clique no arquivo [`build_exe_windows.bat`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/build_exe_windows.bat).
2. Ele instalará o PyInstaller e gerará o executável em `dist\teste_dola.exe`.
3. Pronto! O arquivo `dist\teste_dola.exe` pode ser levado para qualquer Windows 10 sem precisar do Python instalado.

---

## 🐧 Como Executar no Linux
```bash
./run.sh
# ou:
python3 main.py
```
