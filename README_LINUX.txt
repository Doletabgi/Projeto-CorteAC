============================================================
  OpenCorte (Edição Python para Linux 64-bit)
  Recriação Moderna do Sistema Jm2k & ATOM Nesting
============================================================

COMO EXECUTAR NO LINUX:
1. Abra o terminal nesta pasta.
2. Dê permissão de execução (se necessário):
   chmod +x ./opencorte_linux
3. Execute:
   ./opencorte_linux

ATALHO COM ICONE NA AREA DE TRABALHO (OPCIONAL):
1. Dê permissão e execute:
   chmod +x ./instalar_atalho.sh && ./instalar_atalho.sh
2. Isso cria o atalho "OpenCorte-<versão>" (ex.: OpenCorte-1.6.11) no menu de
   aplicativos e na área de trabalho, apontando para ESTA pasta, usando o
   ícone corteac.png e removendo os atalhos de versões anteriores.
3. Se o ícone não atualizar na hora, saia e entre na sessão (ou rode
   "gtk-update-icon-cache"), pois o ambiente guarda o ícone em cache.

BANCO DE DADOS:
- Na primeira execução, o banco SQLite local ("jobmanager.db")
  será inicializado automaticamente nesta pasta.

CONFIGURAÇÃO MYSQL (OPCIONAL):
- Abra Ferramentas > Conexão com Banco de Dados.
- Escolha "Compartilhado na rede (MySQL)" e informe os dados
  fornecidos pelo responsável pela rede.
- Clique em "Testar conexão" e "Salvar configuração".
- Feche e abra o OpenCorte para usar a configuração salva.
- Os dados existentes não serão transferidos entre os bancos.
- Para continuar usando o banco local, escolha "Somente neste computador".

REQUISITOS DO SISTEMA:
- Linux x86_64 (Ubuntu 20.04+, Debian 11+, Mint 20+, Fedora 36+, etc.)
- Nenhuma dependência externa de Python é necessária.
============================================================
