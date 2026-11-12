# 5. Alertas e validação antes do corte

Estudo do checkout local, concluído em 12/11/2026. Não implementa novos alertas,
indicadores ou bloqueios. Por orientação do usuário, as decisões de bloquear ou
pedir confirmação para molde ausente e colisão confirmada permanecem em aberto
para definição com os operadores.

## Verificações existentes e limites

| Tema | Evidência no código | Comportamento observado e lacuna |
|---|---|---|
| Baixo aproveitamento | `ui/layout_editor_view.py`: `update_status`; `analytics/production_dashboard.py` | Há indicadores de rendimento. Não foi localizada uma política comum de limiar por material que dispare alerta antes da exportação. Rendimento não comprova ausência de erros. |
| Molde ausente | `cad/project_packager.py`: `_resolve_die`, `export_session`; `tests/test_project_packager.py`: `test_missing_die_is_reported_and_can_be_strict` | O pacote registra ausentes e motivos no manifesto. `strict=False` é o padrão; `strict=True` já lança `MissingDiesError` antes de escrever os moldes/layouts novos, embora pastas possam ter sido criadas. Os chamadores de produção consultados não ativam esse parâmetro. |
| Molde reconstruído | `cad/project_packager.py`: `_resolve_die`; `ui/layout_editor_view.py`: `export_session_to_machine` | Sem original, pode gerar `.die` com geometria do banco e avisar sobre possível perda de fio/direção e qualidade. Isso é diferente de não conseguir resolver o molde. |
| Colisão e limites | `ui/layout_editor_view.py`: `redraw`, `on_canvas_release`, `validate_placement_status`; `cad/geometry.py` | Há destaque no editor e reversão de arrasto inválido. A verificação de status compara colisões da peça selecionada; sem seleção, verifica limites apenas das primeiras dez peças. O cache visual agrega colisões e ultrapassagem de margens. Não é um relatório completo da sessão. |
| Importação de layout | `cad/lay_parser.py`: `validate_layout_placement` | Avisos informativos de limites, fio, colisão e qualidade. Os limites são testados pela posição de referência; colisões são pesquisadas somente entre os primeiros cem itens e ignoram contornos ausentes. Ausência de aviso não comprova aprovação integral. |
| Material incompatível | `ui/layout_editor_view.py`: `validate_placement_status`; `cad/lay_parser.py`: `validate_layout_placement` | Há heurísticas de fio por nome/rotação e verificação de zonas de defeito quando disponíveis. Não foi localizada uma matriz explícita de compatibilidade material × molde × máquina/ferramenta nos caminhos de exportação consultados. Heurística não deve ser tratada como incompatibilidade comprovada. |
| Ponta e camadas | `cad/layers_rule.py`: `layers_for_piece`, `resolve_layout_layers`; `ui/layout_editor_view.py`: arrasto | Há aviso de cruzamento da ponta durante arrasto e resolução compartilhada das camadas. A atribuição por centro da caixa do contorno não demonstra contenção integral da peça na zona. Rotinas de separação têm verificações próprias de conservação; falta consolidar evidências na saída. |
| Dimensões | `cad/nesting_engine.py`: `nest_multi_sheet`; `ui/main_window.py` | Existem rejeições de dimensões superiores a 10.000 mm na geração. O limite não comprova compatibilidade com a máquina escolhida nem substitui checagem dos contornos e margens em todas as placas exportadas. |
| Alterações não salvas | `ui/layout_editor_view.py`: `on_close_click`, `export_session_to_machine` | Ao fechar, pergunta se deve salvar. A entrega para máquina sincroniza/persiste layouts antes de empacotar e interrompe se a gravação falhar ou retornar falso. Revisar o fechamento: chama `save_layout()` e continua sem confirmar o sucesso. |
| Banco indisponível | `db/connection.py`: `get_connection`; `ui/layout_editor_view.py`: `export_session_to_machine` | Falha de conexão pode gerar `ServerUnreachableError`; a entrega pelo editor trata falha de persistência. Isso não equivale a um indicador contínuo de disponibilidade. A exportação avulsa usa dados em memória e tem outro fluxo. |

### Caminhos que precisam da mesma cobertura

- Exportação avulsa `.lay`, `.onx` e dupla: `LayoutEditorView.export_layout_dialog`
  e `SessionView.export_lay_file`, usando `DualLayoutExporter`.
- Sessão para máquina: `LayoutEditorView.export_session_to_machine`, acessível
  também por `MainWindow.on_export_session_to_machine`.
- Pasta de produção: `MainWindow.on_export_job_folder_to_machine`.
- Exportação automática em lote: `MainWindow._export_batch_session`.
- Conversor: `cad/layout_converter.py`; precisa declarar quais verificações são
  possíveis sem contexto de sessão, material e arquivos originais.

O botão de corte da sessão está ligado a `MainWindow.on_toggle_sim`, uma
simulação. A entrega de arquivos é o ponto operacional disponível neste
checkout; este estudo não estabelece comando de corte físico nem comunicação
confirmada com uma máquina.

### Mensagens que precisam de revisão

- `check_overlay()` anuncia “Layout pronto para corte CNC” após uma checagem
  parcial. A mensagem deveria explicitar o escopo realmente verificado.
- Na exportação por pasta, `all_missing` é preenchido com `res.missing`, mas a
  mensagem os descreve como moldes gerados do banco. Separar ausentes de
  reconstruídos usando as informações já existentes no resultado.
- `ExportResult.complete` significa apenas que a lista de ausentes está vazia;
  `success` significa que há layouts. Nenhum dos dois certifica geometria,
  material, camadas ou compatibilidade da máquina.

## Matriz para discussão com operadores

Todas as ações abaixo são questões/propostas para validação, não regras ativadas.
Aviso informa e permite continuar; confirmação exige decisão explícita;
bloqueio impede a operação até correção. Separar o resultado técnico da ação
operacional para que uma mudança de política não duplique os validadores.

| Situação | Momento a avaliar | Decisão pendente |
|---|---|---|
| Baixo aproveitamento | Após gerar/editar e no resumo de exportação | Definir limiar por material e estratégia, tratamento da última placa/sobras e se basta aviso ou exige confirmação. Não adotar percentual universal sem dados. |
| Molde ausente | Antes de publicar o pacote | Avisar, confirmar ou bloquear? Como proceder com biblioteca externa que não pode ser verificada neste computador? Decisão em aberto. |
| Molde reconstruído | Antes da entrega | Quais operações/metadados precisam de conferência e quem pode aceitar a reconstrução? Tratar separadamente do ausente. |
| Colisão confirmada | Após alteração e verificação completa prévia à saída | Avisar, confirmar ou bloquear? Definir tolerância numérica, contato permitido e folga mínima antes de classificar conflito. Decisão em aberto. |
| Material incompatível | Ao trocar material e antes de exportar | Cadastrar compatibilidades explícitas; definir tratamento de informação ausente versus incompatibilidade comprovada. |
| Ponta/camadas incorretas | Após mover, refilar ou alterar chapa e na saída | Definir contenção, cruzamento permitido, camadas reais e reconciliação da produção por molde. |
| Alterações não salvas | Fechar, trocar de contexto e entregar arquivos | Confirmar expectativa de salvamento automático versus confirmação; assegurar que a revisão exportada seja a revisão conferida. |
| Banco indisponível | Ao ler/salvar e antes da entrega dependente do banco | Definir operações permitidas com dados em memória e como identificar revisão não confirmada. Falha não pode aparecer como gravação concluída. |

Registrar a reunião com: caso real, regra escolhida, limite/tolerância, exceções,
responsável pela decisão, data e comportamento no lote sem operador presente.
Na avaliação atual, nenhum desses novos acordos está aprovado.

## Indicador de confiabilidade proposto

Usar um painel de **verificações explícitas**, com estados por regra:
**aprovada**, **falhou**, **não verificada**, **desatualizada** e
**não aplicável** (com justificativa). Não apresentar um percentual de segurança
ou uma nota média que esconda falhas críticas.

| Grupo | Evidência mínima a reunir |
|---|---|
| Geometria | Todos os contornos necessários presentes e válidos, coordenadas finitas, transformações/espelhamento coerentes, conflitos por peça e margens com tolerância e folga identificadas. |
| Dimensões | Unidades explícitas, medidas positivas, limites do material e da máquina confirmada, todas as peças dentro da região útil considerando refile. |
| Camadas | Origem explícita do enfesto de cada placa, ponta válida, contenção das peças e produção física por molde reconciliada com o pedido e suas exceções acordadas. Valores padrão não contam como confirmação operacional. |
| Arquivos | Cada referência resolvida, origem do molde identificada, arquivos legíveis/interpretáveis, metadados necessários presentes, manifesto e arquivos de saída coerentes após releitura. Hash verifica identidade, não correção do molde. |
| Contexto | Material compatível quando houver regra cadastrada, revisão salva identificada e dados do banco confirmados para a operação que deles depende. |

Exemplo de apresentação: “Verificação parcial — 3 de 5 grupos concluídos.
Arquivos: 1 molde ausente. Camadas: não verificadas. Ver placa 2 / peça 18”.
Os números seriam derivados de verificações executadas; este exemplo não é
resultado medido neste checkout. Preferir “Sem falhas nas verificações
concluídas” a “Seguro para cortar”.

Cada motivo deve mostrar placa/peça/molde afetado, valor observado, regra e
limite aplicado, origem da evidência, momento da verificação e ação de correção.
Resultado técnico e autorização operacional devem permanecer visíveis como
informações separadas, inclusive após eventual confirmação de uma exceção.

## Reutilização e implementação futura

1. Consolidar um relatório por sessão com identificadores estáveis de regra,
   motivos e evidências. Adaptar os resultados dos componentes existentes;
   reutilizar geometria, resolução de camadas e resolução de moldes, sem copiar
   algoritmos para cada tela. Distinguir erro de execução de reprovação técnica.
2. Verificar todas as placas/peças do conjunto de saída. O validador parcial do
   status e o cache de desenho servem à interação, não à aprovação da entrega.
   Padronizar tolerâncias, margem após refile e campos de espelhamento.
3. Separar preparação/validação de escrita. A resolução do packager já existe,
   mas hoje está dentro da exportação; expor uma etapa reutilizável antes da
   publicação, sem executar uma exportação apenas para descobrir ausentes.
4. Validar o conjunto final depois de ajustes de ponta, sobras e refile. Vincular
   o relatório à revisão dos layouts, material, camadas, moldes e política. Uma
   mudança invalida as evidências afetadas; confirmar novamente se necessário.
5. Mostrar resumo persistente com detalhes navegáveis; agrupar avisos para não
   abrir uma janela por peça. No lote, registrar resultado por sessão e continuar
   as demais conforme política acordada. Não reutilizar uma confirmação antiga
   depois de alterar os dados.
6. Só conectar aviso/confirmação/bloqueio após o acordo dos operadores. O
   `strict=True` existente pode ser reaproveitado para ausentes se essa for a
   decisão, mas não resolve colisão, material nem integridade do pacote inteiro.

## Verificação realizada e critérios futuros

Foram executados os testes existentes `test_project_packager.py`,
`test_layout_editor_machine_export.py` e `test_dual_exporter.py` em cópia
temporária isolada do código, sem copiar o banco ou o `db.ini` operacional,
com backend SQLite explícito: **26 aprovados e 1 ignorado**. O teste ignorado
depende do arquivo de referência `AS74467.onx`, ausente no ambiente de teste.
Esses testes confirmam apenas os comportamentos cobertos; não demonstram uma
validação integral antes do corte. Não houve ensaio com operadores/máquina,
queda real de rede ou MySQL de produção.

Na implementação futura, cobrir: colisão além do centésimo item e em placa não
aberta; contorno ausente/inválido; espelhamento; margem após refile; tolerâncias
acordadas; ponta cruzada; camadas indefinidas; divergência de produção; molde
ausente versus reconstruído; biblioteca externa inacessível; falha de gravação;
alteração após validação; destino indisponível e exportação parcial/dupla.
Exigir os mesmos resultados técnicos na saída individual, por pasta e em lote.
Um erro de validação ou um arquivo não verificado deve aparecer explicitamente,
sem ser convertido em aprovação por falta de aviso.
