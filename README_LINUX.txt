============================================================
  CorteAC (Edição Python para Linux 64-bit)
  Recriação Moderna do Sistema Jm2k & ATOM Nesting
============================================================

COMO EXECUTAR NO LINUX:
1. Abra o terminal nesta pasta.
2. Dê permissão de execução (se necessário):
   chmod +x ./corteac_linux
3. Execute:
   ./corteac_linux

ATALHO COM ICONE NA AREA DE TRABALHO (OPCIONAL):
1. Dê permissão e execute:
   chmod +x ./instalar_atalho.sh && ./instalar_atalho.sh
2. Isso cria "CorteAC" no menu de aplicativos e na área de trabalho,
   apontando para ESTA pasta e usando o ícone corteac.png.
3. Se o ícone não atualizar na hora, saia e entre na sessão (ou rode
   "gtk-update-icon-cache"), pois o ambiente guarda o ícone em cache.

BANCO DE DADOS:
- Na primeira execução, o banco SQLite local ("jobmanager.db")
  será inicializado automaticamente nesta pasta.

CONFIGURAÇÃO MYSQL (OPCIONAL):
- Se desejar conectar a um servidor MySQL corporativo,
  renomeie "db.example.ini" para "db.ini" e configure o host/porta.

REQUISITOS DO SISTEMA:
- Linux x86_64 (Ubuntu 20.04+, Debian 11+, Mint 20+, Fedora 36+, etc.)
- Nenhuma dependência externa de Python é necessária.
============================================================
