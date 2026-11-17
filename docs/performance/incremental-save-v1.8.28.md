# Desempenho do salvamento incremental — v1.8.28

Comparação com v1.8.27. SQLite em arquivos temporários locais; nenhum banco operacional foi utilizado. Python 3.12.3.

Sessões de 10, 50 e 100 placas, com 100 peças por placa e contornos de 20 pontos. Sete medições por cenário após duas execuções de aquecimento. Inicialização do banco e geração dos dados ficam fora do tempo medido. O cenário sem cache limpa somente as conversões em memória antes de cada medição. Não houve medição de MySQL nem simulação de latência de rede.

| Cenário | Placas | Antes (média ms) | Depois (média ms) | Redução do tempo |
|---|---:|---:|---:|---:|
| Uma placa alterada, salvamentos repetidos | 10 | 18.4 | 6.9 | 62.6% |
| Uma placa alterada, sem cache de conversão | 10 | 18.8 | 15.8 | 16.3% |
| Salvar novamente sem alterações | 10 | 19.2 | 3.3 | 82.9% |
| Todas as placas alteradas | 10 | 18.5 | 19.4 | -4.8% |
| Uma placa alterada, salvamentos repetidos | 50 | 83.8 | 12.4 | 85.3% |
| Uma placa alterada, sem cache de conversão | 50 | 83.1 | 61.2 | 26.4% |
| Salvar novamente sem alterações | 50 | 83.3 | 9.0 | 89.1% |
| Todas as placas alteradas | 50 | 84.0 | 82.3 | 2.1% |
| Uma placa alterada, salvamentos repetidos | 100 | 160.4 | 19.6 | 87.8% |
| Uma placa alterada, sem cache de conversão | 100 | 163.9 | 120.0 | 26.8% |
| Salvar novamente sem alterações | 100 | 160.7 | 16.6 | 89.7% |
| Todas as placas alteradas | 100 | 160.2 | 169.9 | -6.1% |

## Médias por cenário

Média aritmética das reduções percentuais dos três tamanhos, com peso igual por tamanho:

- Uma placa alterada, salvamentos repetidos: 78.6% de redução do tempo.
- Uma placa alterada, sem cache de conversão: 23.2% de redução do tempo.
- Salvar novamente sem alterações: 87.3% de redução do tempo.
- Todas as placas alteradas: -3.0% de redução do tempo.

Percentuais negativos indicam aumento de tempo. Alterar todas as placas não elimina trabalho e teve aproximadamente 3% de aumento médio neste ensaio. O ganho da edição de uma placa é maior após salvar a mesma sessão, pois a conversão dos contornos é reaproveitada. O primeiro salvamento de dados no formato legado pode normalizar sua representação JSON uma única vez, sem mudar a geometria ou os IDs das placas.

O cache fica restrito à última sessão salva, compara snapshots de conteúdo e é validado contra os dados/versionamento lidos do banco; não usa somente a identidade dos objetos. Permanece necessário consultar os dados das placas e atualizar o resumo da sessão. Nenhum percentual aqui representa velocidade do sistema inteiro ou ganho comprovado em rede.

Reprodução: `python3 tools/bench_incremental_layout_save.py --output /tmp/save-benchmark.json`.
