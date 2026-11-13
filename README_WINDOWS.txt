============================================================
  OpenCorte (Python Edition para Windows 10 e Windows 11)
  Recriacao Moderna do Sistema Jm2k & ATOM Nesting
============================================================

COMO EXECUTAR:
1. De duplo clique no arquivo "OpenCorte.exe".
2. O sistema inicializara imediatamente.

BANCO DE DADOS:
- Na primeira execucao, o banco de dados SQLite local
  ("jobmanager.db") e inicializado automaticamente nesta mesma
  pasta. Todas as suas ordens e chapas serao salvas nele.

INSTALACAO PELO SETUP:
- Local: escolha "Instalar localmente". Nao e necessario endereco.
- Rede: escolha "Usar um servidor na rede" e informe um unico
  nome/IP (ex.: SERVIDOR ou 192.168.1.100) ou uma raiz compartilhada
  (ex.: \\SERVIDOR\Fabrica).
- Com apenas nome/IP, usa \\SERVIDOR\Fabrica como raiz.
  Moldes ficam em Moldes, sessoes em Sessoes e o banco MySQL
  usa o mesmo servidor. O servidor deve ter o compartilhamento
  e o banco configurados; o setup configura este computador.
- Ao atualizar sem alterar a escolha/endereco, preserva o db.ini
  existente. Credenciais personalizadas sao mantidas.
- Para o pacote portatil, copie db.example.ini para db.ini e
  ajuste a conexao com ajuda do responsavel pela rede.

SUPORTE E ATUALIZACOES:
- Repositorio Oficial: https://github.com/Doletabgi/Projeto-CorteAC
- Lancamentos e versoes: https://github.com/Doletabgi/Projeto-CorteAC/releases
============================================================
