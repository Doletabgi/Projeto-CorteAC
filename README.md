# CorteAC — Edição Python para Windows 10 / 11

Recriação moderna em **Python** do sistema industrial **CorteAC** (evolução direta do legado **JobManager 2000 / Jm2k** e **ATOM Nesting System**, originalmente desenvolvido em Visual Basic 6 para Windows XP).

---

## 🚀 Principais Melhorias em relação à versão legada

1. **Compatibilidade Nativa com Windows 10 / 11 e Linux**:
   - Não requer drivers legados de 16/32 bits de porta paralela ou USB (`eusk2par.sys`, `eusk3usb.sys`, `skeyvdd.dll`).
   - Não depende de componentes ActiveX/OCX obsoletos (`COMCTL32.OCX`, `GridEX16.ocx`, etc.) que falham em sistemas de 64 bits.
   - Não depende de DAO 3.5/3.6 ou MDAC descontinuados — utiliza banco de dados **SQLite** rápido e integrado.

2. **Mesa de Corte CAD Interativa**:
   - Canvas vetorial 2D com suporte a **Pan** (arrastar com botão direito/meio) e **Zoom** (rodinha do mouse).
   - Manipulação de peças por arrastar e soltar (*drag & drop*) e rotação com a tecla **`R`**.
   - Cálculo em tempo real do **Rendimento de Material (*Yield %*)** e área útil cortada.

3. **Motor de Aninhamento Automático (*Auto-Nest*)**:
   - Algoritmo de empacotamento inteligente de alta densidade que recria e aprimora a função do antigo *FreeNest.exe*.

4. **Simulador de Corte e Estimador de Tempo ATOM**:
   - Animação do cabeçote de corte CNC percorrendo os contornos em tempo real.
   - Cálculo preciso de tempo de ciclo (*ATOM Cutting Time Estimator*) baseado na velocidade de 650 mm/s e punções.

5. **Exportação CNC**:
   - Geração de arquivos **G-Code / ISO CNC** prontos para máquinas de corte industrial da ATOM (série FlashCut Flex).
   - Exportação de relatórios de produção em **XML** baseados no modelo original `Report.xsl`.

---

## 💻 Como Baixar e Executar no Windows 10 / 11

### Opção 1: Baixar a Versão Pronta (.exe Standalone) — [Recomendada]
Não é necessário instalar Python nem configurar nada:
1. Acesse a aba **[Releases](https://github.com/Doletabgi/Projeto-CorteAC/releases)** do repositório.
2. Baixe o pacote **`CorteAC-Windows-x64.zip`** (ou o executável direto `CorteAC.exe`).
3. Extraia o conteúdo e dê dois cliques em **`CorteAC.exe`**.
4. O sistema cria automaticamente o banco SQLite local (`jobmanager.db`) e abre imediatamente!

👉 Para o guia passo a passo completo, consulte o [README_WINDOWS.md](README_WINDOWS.md).

### Opção 2: Executar Direto pelo Arquivo BAT
Se você baixou o código-fonte, basta dar um duplo clique no arquivo:
```cmd
executar_windows.bat
```
*(ou `run.bat`)*

### Opção 3: Pelo Prompt de Comando / PowerShell
Certifique-se de ter o Python 3 instalado no Windows (marcando "Add python.exe to PATH"):
```cmd
python main.py
```

---

## 📦 Como Gerar o Executável Standalone Localmente

### No Linux:
Para compilar o executável standalone no Linux:
```bash
./build_linux.sh
```
O executável gerado estará em:
```bash
./dist/CorteAC
```

### No Windows 10 / 11:
Para gerar o executável `.exe` direto no Windows:
1. Dê um duplo clique no arquivo `build_exe_windows.bat`.
2. Ele instalará o PyInstaller e gerará o executável em `dist\CorteAC.exe`.
3. Pronto! O arquivo `dist\CorteAC.exe` pode ser levado para qualquer Windows 10/11 sem precisar do Python instalado.

---

## 🐧 Como Executar no Linux
```bash
./run.sh
# ou:
python3 main.py
```

---

## 🗄️ Arquitetura de Banco de Dados Central (MySQL 8.0)

O **CorteAC** opera conectado a uma instância central do **MySQL 8.0** na rede local da fábrica, atendendo até **8 PCs simultâneos** com suporte a alta concorrência (>1000 layouts/dia).

O banco local **SQLite (`jobmanager.db`)** é mantido estritamente como **reserva offline / emergência / demonstração**.

### 1. Configuração de Rede dos Terminais (`db.ini`)
Cada um dos 8 computadores da fábrica deve ter um arquivo `db.ini` no diretório da aplicação (ao lado do executável):

```ini
[database]
# Backend ativo: 'mysql' (produção na fábrica) ou 'sqlite' (modo offline / reserva)
backend = mysql

# Endereço IP do servidor central MySQL 8.0 na rede
host = 192.168.1.100
port = 3306

# Credenciais de acesso
user = jm_app
password = jm_factory_2026
database = jobmanager
charset = utf8mb4
connect_timeout = 5

[sqlite]
# Caminho do banco local de reserva
path = jobmanager.db
```

> **Dica**: As configurações também podem ser injetadas por variáveis de ambiente: `DB_BACKEND`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`.

---

### 2. Criação do Usuário Dedicado no Servidor MySQL
No servidor MySQL 8.0, execute como `root` para criar o usuário da aplicação com privilégios mínimos necessários:

```sql
-- Cria usuário da aplicação com autenticação moderna caching_sha2_password
CREATE USER 'jm_app'@'%' IDENTIFIED WITH caching_sha2_password BY 'jm_factory_2026';

-- Concede privilégios estritos de DML no banco de produção e de teste
GRANT SELECT, INSERT, UPDATE, DELETE ON jobmanager.* TO 'jm_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON jobmanager_test.* TO 'jm_app'@'%';

-- Atualiza privilégios
FLUSH PRIVILEGES;
```

---

### 3. Configuração do Slow Query Log no MySQL
Para monitorar queries lentas e diagnosticar gargalos na rede da fábrica:

```sql
-- Ativa o slow query log no servidor
SET GLOBAL slow_query_log = 'ON';

-- Define limiar de 500 ms (0.5 s)
SET GLOBAL long_query_time = 0.5;

-- Grava em arquivo de log
SET GLOBAL log_output = 'FILE';
```

Ou adicione ao arquivo de configuração `/etc/mysql/my.cnf`:
```ini
[mysqld]
slow_query_log = 1
slow_query_log_file = /var/log/mysql/mysql-slow.log
long_query_time = 0.5
log_queries_not_using_indexes = 0
```

---

### 4. Rotina de Backup (`mysqldump`) e Restauração Point-in-Time

#### Backup Diário Consistente (InnoDB Transacional)
Execute via cron ou tarefa agendada:
```bash
mysqldump -h 127.0.0.1 -u jm_app -pjm_factory_2026 \
  --single-transaction \
  --quick \
  --routines \
  --triggers \
  --databases jobmanager > /backup/jobmanager_$(date +%Y%m%d_%H%M%S).sql
```

#### Restauração Completa de Backup
```bash
mysql -h 127.0.0.1 -u jm_app -pjm_factory_2026 jobmanager < /backup/jobmanager_20261018_000000.sql
```

#### Restauração Point-in-Time via Binary Log (Binlog)
Se houver falha durante o dia e for necessário restaurar transações até um minuto exato:
```bash
# 1. Restaura o último backup base
mysql -h 127.0.0.1 -u jm_app -pjm_factory_2026 jobmanager < /backup/jobmanager_base.sql

# 2. Reaplica eventos do binlog até o horário desejado
mysqlbinlog --start-datetime="2026-10-18 00:00:00" \
            --stop-datetime="2026-10-18 14:30:00" \
            /var/log/mysql/binlog.000001 | mysql -h 127.0.0.1 -u jm_app -pjm_factory_2026 jobmanager
```

---

### 5. Modo Offline / Demonstração (SQLite de Reserva)
Se o servidor MySQL estiver fora do ar ou o terminal for levado para campo/demonstração:
1. Abra o arquivo `db.ini` no computador.
2. Altere a linha:
   ```ini
   backend = sqlite
   ```
3. O CorteAC inicializará instantaneamente utilizando o banco local `jobmanager.db`, garantindo 100% das funcionalidades operacionais mesmo sem conexão com a rede.
