# Simbólica: inserção manual de piques

Implementação em código em 12/11/2026, a partir de
`docs/02_Comelz_CAM_22A18.md` e da confirmação do operador: ativar a função,
escolher o tipo e clicar na peça. A correção de uso integra a versão 1.8.9.

## Uso no OpenCorte

1. Abra a peça no editor de moldes. A Simbólica funciona com a trava de
   geometria ativa: escolher a ferramenta autoriza essa inserção específica,
   mantendo bloqueado o arraste de vértices.
2. Clique em **Simbólica** e escolha o tipo; o diálogo mostra uma prévia.
3. Clique próximo à borda onde deseja os piques. A posição é projetada na
   aresta mais próxima (tolerância de 12 pixels).
4. A ferramenta permanece ativa para novas inserções. **Esc** encerra;
   **Ctrl+Z** desfaz o grupo inteiro. Salve o molde para persistir a alteração.

Tipos disponíveis: pequeno (4,5 × 1 mm), grande (7 × 2 mm), duplo pequeno e
sequência pelo último dígito do tamanho inteiro. Espaço entre piques: 1 mm.
Na sequência, 0 = dois grandes; 1–4 = um a quatro pequenos; 5 = um grande;
6–9 = um grande mais um a quatro pequenos. Tamanhos fracionários ou com letras
exigem escolha manual nesta implementação.

Cada pique é um V voltado para dentro e incorporado ao contorno de corte.
O grupo pode ocupar vários segmentos consecutivos de uma borda reta ou curva,
inclusive atravessando o ponto inicial do contorno. A largura acompanha a
distância ao longo da borda. Cantos com mudança acumulada de direção superior
a 45 graus no trecho do grupo e cruzamentos com outro trecho são rejeitados. Posições inválidas são rejeitadas sem alterar a peça nem
criar uma entrada no histórico. A marcação acompanha rotações e espelhamentos
por pertencer ao próprio contorno. Não é convertida em furo de broca.

O banco preserva a geometria e a indicação `symbolic_notch` nos pontos
inseridos. A exportação `.die` grava as coordenadas do contorno. No pacote ATOM,
o marcador faz o resolvedor usar a geometria atual do banco em vez de copiar
um original potencialmente anterior aos piques. Esse caminho usa o aviso já
existente de molde reconstruído: metadados originais de fio/direção e qualidade
podem não ser preservados. A biblioteca original não é sobrescrita.

Layouts já calculados contêm sua própria geometria: precisam ser atualizados
ou gerados novamente a partir do molde salvo. A saída `.onx` existente referencia
modelos, sem incorporar o contorno completo; este trabalho não adiciona a
atualização de modelos `.cmz` nem certifica o corte pela Comelz.

## Evidências da suíte Comelz

A habilidade utilizada foi
[`reverse-engineer-anything`](/home/dola/.agents/skills/reverse-engineer-anything/SKILL.md).
O instalador foi aberto com REA para identificar o artefato e extraído
estaticamente com `innoextract`; o subinstalador CM44 foi extraído com `7z`.
Nenhum executável Comelz foi executado ou instalado.

Artefato: `/home/dola/Documentos/arquivosRea/Setups/comelz/Comelz-CAM-22A.18-setup.exe`.
SHA-256 retornado pelo REA:
`e9ea955452395abdbbfcbd9a6ac80f8676a2edcf229e276ff044b0716f32dd96`.

Arquivos observados dentro de `CM44GL3.15722A.18.exe`:

| Arquivo | Observação direta |
|---|---|
| `conf/_standard_.smk` | Seções `NOTCHES`, `OPTIONS`, `SIZE RULES`; dimensões 7×2 e 4,5×1; espaço padrão 1; regras pelo último dígito e regras adicionais fracionárias. |
| `conf/standard.smb`, `piccola.smb`, `grande.smb` | Perfis de simbólica e expansões dos códigos 0–9. |
| `conf/simbolica_con_lettere.smb` | Perfil com expansões adicionais para identificação de pares por letras. |
| `extra/parms.def` | `FILE_SIMBOLICO` e `FILE_SIMBOLICO2` selecionam perfis; `ModificaIntSimbolica` habilita edição interativa; `simbolica_capogruppo` escolhe tamanho principal versus tamanho da peça. |
| `bin/gl.exe` | Texto em offset de arquivo `0x201f200` descreve botão esquerdo para criar/mover, direito para apagar e central para conferir graduação. `0x201fcd5`: rótulo de modificação de piques de tamanho. |

Hash de `conf/_standard_.smk`:
`b6d89de5c9b626a583a67cfb9b6af3b6322d30ded5fa6196ca487802830247ab`.
Hash de `bin/gl.exe`:
`b8420b2abc66751dbf17e663733be867a96bf76f101071d5e88908b6bafb5289`.

Essas observações estabelecem a existência da função, dos perfis e dos textos
de interação. Não houve decompilação do algoritmo geométrico ou observação da
interface em execução. Os V do OpenCorte são um equivalente funcional com
dimensões de referência; não se afirma reprodução exata das primitivas S/s ou
interpretação completa dos formatos `.smb`/`.smk` da Comelz. Movimento/remoção de
grupos, códigos de letras e frações permanecem fora desta primeira versão;
o desfazer existente permite remover a inserção como uma operação inteira.

## Validação

Em cópia isolada do código, com banco SQLite de teste e sem copiar `db.ini` ou
banco operacional: testes de simbólica, editor com múltiplos moldes, dupla saída
e empacotador: **56 aprovados, 1 ignorado**. O ignorado depende de arquivo de
referência em caminho antigo ausente. A suíte cobre clique real no canvas,
trava, seleção/cancelamento do diálogo, desfazer, orientação das quatro bordas
nos dois sentidos, fechamento explícito, posições inválidas, peça fina,
persistência SQLite, `.die` e preferência pela geometria atual no pacote.
Prévia do diálogo conferida visualmente. Ensaio de corte físico não realizado.

Verificação adicional de segurança, abertura, costuras e tela cheia do editor:
**17 aprovados e 6 falhas**. A mesma execução, removendo apenas as adições da
simbólica na cópia de teste, reproduziu exatamente as seis falhas. Elas envolvem
o molde fixo de ID 27 ausente no banco de teste e expectativas antigas de texto
dos botões após a migração de ícones já presente no checkout. Não foram
alterados testes/dados operacionais para mascarar essas falhas.

Regressão da inserção: seleção pelo botão com trava ativa, clique em molde
com segmentos de 1 mm, gravação, desfazer, curvas nos dois sentidos, fechamento
explícito, passagem pelo primeiro vértice e conservação dos pontos entre piques.
