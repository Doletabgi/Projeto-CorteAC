# Atualização completa do OpenCorte

Na pasta do projeto, execute:

```bash
python3 atualizar.py
```

No Windows, use `python atualizar.py`. Esse é o único script-fonte de
manutenção/publicação: versão, documentação, limpeza da cópia de build,
compilação, pacotes, atalhos e GitHub estão implementados nele.

## Execução completa

1. Confere branch, acesso ao origin, identidade Git e dependências; busca o
   estado remoto e exige que ele esteja integrado à branch local.
2. Incrementa a versão patch, por exemplo `1.8.6` → `1.8.7`, e atualiza a
   versão de reserva do instalador Inno Setup.
3. Sincroniza `docs/PROJETO_ATOM_JOBMANAGER.md` com os fontes e verifica o
   resultado. Preserva as seções manuais fora dos blocos automáticos.
4. Copia fontes/assets para uma pasta temporária, sem banco operacional ou
   `db.ini`. Cria um banco próprio, executa a seleção de testes em `CHECKS` e
   limpa somente esse banco de distribuição.
5. Usa uma única receita PyInstaller para a build local e para o GitHub.
   Confere a versão do executável e gera ZIP no Windows ou TAR.GZ no Linux.
   No Windows também gera o instalador quando o Inno Setup está disponível;
   o runner Windows instala essa dependência e exige o instalador na release.
6. Atualiza os executáveis locais e o atalho versionado da Área de Trabalho;
   preserva os binários anteriores em `.release/backups/<versão>/`.
7. Confere a correspondência dos fontes com a build; cria commit/tag e faz
   push atômico da branch e da tag, sem force-push. Bancos, conexão local,
   credenciais, exportações e binários gerados ficam fora do commit.
8. Acompanha o workflow do commit e só conclui depois do sucesso e da presença
   dos cinco artefatos: `CorteAC.exe`, `CorteAC-Windows-x64.zip`,
   `CorteAC-Setup-<versão>.exe`, `corteac_linux` e `CorteAC-Linux-x64.tar.gz`.

A execução real publica no origin configurado. As mudanças de fonte ainda não
preparadas serão incluídas conforme os diretórios/extensões aceitos e devem
estar prontas para publicação. O índice Git precisa estar vazio no início.
Se o remoto estiver à frente, integre os commits antes de começar; o script
não faz merge, rebase ou descarte automático.

## Modos no mesmo arquivo

```bash
# Ver o plano completo sem escrever nem acessar a rede.
python3 atualizar.py --simular

# Continuar a mesma versão após resolver uma falha.
python3 atualizar.py --retomar

# Incrementar minor em vez de patch.
python3 atualizar.py --incremento minor

# Somente sincronizar a documentação, sem build ou publicação.
python3 atualizar.py --documentacao
python3 atualizar.py --documentacao --check

# Somente compilar/empacotar em cópia isolada, sem mudar versão/Git/atalhos.
# Esse é o mesmo comando usado nos runners Windows e Linux do GitHub.
python3 atualizar.py --build
```

`--espera 120` permite aguardar até duas horas pela publicação; o padrão é
60 minutos, com consultas em intervalos de um minuto. Estado e lock ficam em
`.release/`, ignorada pelo Git. O lock do sistema impede execuções simultâneas
na mesma pasta e é liberado ao encerrar. Não apague o estado pendente: a
retomada evita nova versão, build e commit após uma falha no GitHub.

Antes do commit, fontes corrigidos fazem a retomada repetir documentação,
testes e build na mesma versão. Depois do commit, a retomada exige o mesmo HEAD
e continua aquela publicação. Reexecute um workflow com falha no GitHub antes
de retomar seu acompanhamento. O script não reinicia o aplicativo aberto;
no Windows, feche o executável se o sistema impedir sua substituição.

## Arquivos removidos e componentes preservados

Foram incorporados e removidos os oito scripts antigos de versão/cadência,
sincronização, limpeza de distribuição, builds Linux/Windows e instaladores de
atalhos. Uma cópia local foi guardada em `.release/legacy-scripts/`.

`packaging/corteac_setup.iss` permanece como definição do instalador Windows;
`ui/desktop_shortcut.py` permanece como biblioteca usada pela aplicação em
execução. `main.py`, `run.sh` e os lançadores Windows continuam abrindo o
programa. As ferramentas de análise, importação e diagnóstico não fazem parte
dessa remoção.

Os instaladores de atalhos `.sh`/`.ps1` agora são gerados pelo `atualizar.py`
dentro dos pacotes portáteis. Não existem scripts-fonte paralelos para manter.
O hook Git local também foi encaminhado para a verificação de documentação do
atualizador, sem reescrever ou preparar fontes durante o commit.
Os nomes técnicos dos arquivos e atalhos continuam compatíveis com os pacotes
existentes; a documentação e as novas notas de release usam OpenCorte.

## Dependências e validação

É necessário Python, Git, PyInstaller, pytest e as dependências do projeto.
O push usa a configuração normal do Git/SSH. O acompanhamento usa a API de
leitura do GitHub, sem exigir o `gh`. Para repositórios privados ou limites de
API, configure `GH_TOKEN` ou `GITHUB_TOKEN` com leitura do repositório/Actions;
o token não é gravado no estado nem exibido.

A seleção em `CHECKS` cobre atualização, versão, atalhos, limpeza em banco
isolado, impressão, simbólica, empacotador, dupla saída e conexão. Não representa
a suíte completa nem inclui ensaios de máquina ou MySQL de produção.

O acompanhamento consulta a
[API de execuções do GitHub Actions](https://docs.github.com/en/rest/actions/workflow-runs)
e a publicação usa [push atômico do Git](https://git-scm.com/docs/git-push).

O nome exibido no programa e nos atalhos é **OpenCorte**. A atualização remove os atalhos antigos CorteAC e OpenCorte, inclusive cópias renomeadas manualmente, e mantém um atalho OpenCorte com a versão atual em cada Área de Trabalho. Os nomes técnicos dos executáveis e pacotes existentes são preservados por compatibilidade.
