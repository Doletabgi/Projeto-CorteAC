# OpenCorte — Edição Python para Windows 10 / 11

Para atualizar versão, documentação, builds, Área de Trabalho e GitHub com um
único comando, execute `python3 atualizar.py` na pasta do projeto. Para conferir
as etapas sem alterar nada, use `python3 atualizar.py --simular`. Depois de uma
falha, use `python3 atualizar.py --retomar` para continuar a mesma versão.
Veja o [guia da atualização completa](docs/fases/ATUALIZACAO_UNIFICADA.md).

O atualizador preenche as alterações de cada versão em `docs/releases/v<versão>.md`.
Esse texto é publicado na seção **Alterações desta versão** do GitHub. Notas já
revisadas são preservadas ao retomar a atualização; alterações nesses arquivos
também atualizam as notas de versões publicadas, sem recompilar os instaladores.

Recriação moderna em **Python** do sistema industrial **OpenCorte** (evolução direta do legado **JobManager 2000 / Jm2k** e **ATOM Nesting System**, originalmente desenvolvido em Visual Basic 6 para Windows XP).

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

4. **Exportação CNC**:
   - Geração de arquivos **G-Code / ISO CNC** prontos para máquinas de corte industrial da ATOM (série FlashCut Flex).
   - Exportação de relatórios de produção em **XML** baseados no modelo original `Report.xsl`.

5. **Entrega de Sessão para a Máquina**:
   - Botão **📤** no Layout Editor e item **Arquivo → Salvar Sessão para Máquina…**.
   - Exporta **todas as placas** da sessão (`lay0000.lay`, `lay0001.lay`, ...) para uma pasta de rede ou pendrive.
   - Copia somente os moldes `.die` referenciados para `Shapes/`, com manifesto de auditoria e lista de ausentes.
   - Exportação automática opcional no **Auto-Nest em Massa**.

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

## Catálogo visual de moldes

Abra **Catálogo** na barra superior ou **Ferramentas → Catálogo de Moldes**.

1. Busque pelo nome, pasta, modelo ou tamanho. A busca também encontra nomes sem digitar os acentos.
2. Use as pastas e o filtro de tamanho para reduzir os resultados.
3. Clique nos moldes para selecioná-los. A seleção permanece ao trocar os filtros.
4. Escolha a **Sessão de destino** e ajuste os pares de cada molde, ou use **Aplicar a todos**.
5. Clique em **Adicionar à sessão**. Os moldes são salvos no banco e a sessão aberta é atualizada.

O indicador **Já na sessão** evita duplicação e preserva as quantidades existentes. Você pode trocar a sessão de destino para reutilizar a seleção. O botão **Adicionar Molde** da sessão também abre essa biblioteca com o destino já escolhido.

No seletor **Visualização**, escolha **Cartões grandes**, **Cartões compactos**, **Lista com prévias** ou **Tabela de detalhes**. A seleção e os pares permanecem ao trocar de modo. Na tabela, clique nos títulos das colunas para ordenar por nome, tamanho, pasta, medidas, área do contorno ou situação.

## Painel de Produção

Abra **Ferramentas → Painel de Produção** e selecione o período e o material.
Use **Salvar PDF...** para salvar o relatório ou **Imprimir...** para enviá-lo à
impressora padrão. As duas ações aplicam os filtros atuais e incluem o resumo,
as tabelas **Por material** e **Evolução por dia** e os avisos sobre os dados.
O relatório usa páginas A4 em paisagem e inclui todas as linhas das tabelas.
Se a impressão direta estiver indisponível, use o PDF em um leitor para imprimir.

## 📦 Como Gerar o Executável Standalone Localmente

### No Linux:
Para compilar o executável standalone no Linux:
```bash
python3 atualizar.py --build
```
O executável gerado estará em:
```bash
./dist/CorteAC
```

### No Windows 10 / 11:
Para gerar o executável `.exe` direto no Windows:
1. Execute `python atualizar.py --build` no terminal da pasta do projeto.
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

O **OpenCorte** opera conectado a uma instância central do **MySQL 8.0** na rede local da fábrica, atendendo até **8 PCs simultâneos** com suporte a alta concorrência (>1000 layouts/dia).

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
3. O OpenCorte inicializará instantaneamente utilizando o banco local `jobmanager.db`, garantindo 100% das funcionalidades operacionais mesmo sem conexão com a rede.
