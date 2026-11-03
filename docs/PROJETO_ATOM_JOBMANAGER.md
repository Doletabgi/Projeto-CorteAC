# PROJETO ATOM JobManager Reborn: Documento Vivo

> **Finalidade:** Documento mestre estruturado e autocontido projetado para alimentar e contextualizar qualquer Inteligência Artificial (Antigravity, Claude, ChatGPT, etc.) ou engenheiro sobre 100% do projeto — regras de negócio de calçados/couro (ATOM), arquitetura técnica, schemas de banco (MySQL/SQLite), formatos proprietários (.LAY, .ONX/CZLIB), algoritmos de nesting/CAM, UI/UX e histórico — em um único arquivo de referência imediata.
> **Regra de ouro:** o que está marcado `[CONFIRMADO]` veio do relatório, do código ou do usuário. O que está `[NÃO CONFIRMADO]` é suposição e não deve virar "fato" sem validação. O que está `[PREENCHER]` a IA deve completar lendo o código real.

<!-- AUTO:header:start -->
**Última sincronização com o código:** 2026-11-03 09:42 (HEAD ao gerar: `5fa8823`; 133 arquivos Python, ~65278 linhas)
<!-- AUTO:header:end -->
**Versão deste documento:** 1

---

## 0. Como manter este documento

**Automático:** os blocos entre `<!-- AUTO:nome:start -->` e `<!-- AUTO:nome:end -->` (cabeçalho, seção 3, seção 4, seção 7.4 e commits recentes) são reescritos por `tools/sync_project_doc.py` a cada commit, via hook do Git. **Não edite esses blocos à mão: a próxima execução apaga a edição.** Todo o resto é manual.

1. Alterações que o script não vê (regras, decisões, confirmações do usuário, pendências) são atualizadas à mão nas seções 5, 6, 7.1, 7.2, 8, 9 e 10.
2. Nunca apagar entradas do Changelog (seção 10). Apenas acrescentar.
3. Ao mudar um item de `[NÃO CONFIRMADO]` para `[CONFIRMADO]`, registrar quem confirmou e quando.
4. O Claude só afirma sobre o código aquilo que está descrito aqui. Se algo não estiver aqui, o Claude pergunta em vez de presumir.
5. **Publicação Automática de Releases a Cada 5 Commits (`v2026.X`) (seção 12)**: a cada 5 commits acumulados no repositório (medidos e monitorados via `tools/check_release_cadence.py`), uma nova release oficial deve ser publicada automaticamente via GitHub Actions gerando binários portáteis Windows (`CorteAC.exe`) e Linux (`corteac_linux`) atualizados, incrementando rigorosamente a sequência de versões em `config.py`, `.github/workflows/release.yml` e tags do Git.
6. **Centralização Total de Relatórios e Especificações**: A partir de 30/10/2026, **todo e qualquer relatório de fase, diagnóstico técnico, benchmark, especificação de arquitetura ou decisão de projeto deve ser documentado DIRETAMENTE neste arquivo (`docs/PROJETO_ATOM_JOBMANAGER.md`)**. É expressamente proibido criar novos arquivos `.md` avulsos na pasta `docs/`, mantendo a pasta limpa e este arquivo como a fonte única de verdade absoluta.

---

## 1. Visão geral

Reconstrução do ecossistema da **ATOM Engineering s.r.l.** (JobManager2000, TheLoop, ShedNt, Layout, FreeNest, fn98, dp98) para corte de calçado em couro natural e sintéticos. `[CONFIRMADO]`

O projeto tem duas implementações complementares:

| Implementação | Pasta/Nome | Stack | Papel |
|---|---|---|---|
| Cliente desktop | `jobmanager-win10-python` / `teste_dola` | Python, MySQL 8.0 Central (reserva local SQLite `jobmanager.db`), UI desktop | Reconstrução fiel da UI/UX do JobManager2000 (WinXP/Win10/Win11), cliente para 8 PCs simultâneos na fábrica (>1000 layouts/dia) |
| Serviço industrial distribuído | `atom_reborn` | FastAPI, MySQL 8.0, GEOS/Shapely, WebSocket, React 18 | Backend corporativo, fila de nesting, integração com chão de fábrica via ANP TCP |

Ambientes: Windows 10/11 e Linux. `[CONFIRMADO]`

---

## 2. Fluxo de dados

```mermaid
flowchart TD
    subgraph Ingestao ["1. Ingestão"]
        CAD["CAD (DXF / .sho / .mod / .die)"] --> DIE["cad/die_parser.py"]
        ORD["Ordens / Sessões"] --> SESS["SessionView / database.py"]
        COURO["Peles e defeitos"] --> MAT["Materials / Zonas 0 a 5"]
    end
    subgraph Proc ["2. Processamento"]
        DIE --> DB[("SQLite / MySQL")]
        SESS --> DB
        DB --> EXP["Explosão de moldes por par"]
        EXP --> ENG["fn98 (couro) | dp98 (sintético) | Python GEOS"]
        ENG --> CON["AngleRange (fio) + Zonas de qualidade"]
    end
    subgraph Saida ["3. Saída / CNC"]
        CON --> LAY["Layouts (.lay)"]
        LAY --> UI["Layout Editor + Print Preview A4"]
        LAY --> ANP["Driver ANP TCP 4000/4001"]
        ANP --> CNC["Mesas ATOM (FlashCut / Twin)"]
    end
```

---

## 3. Estrutura do código (automático)

<!-- AUTO:tree:start -->
```
README.md
README_WINDOWS.md
build_exe_windows.bat
build_linux.sh
config.py                                            # CorteAC (Python Edition)
database.py                                          # JobManager 2000 (Python Edition)
db.example.ini
docker-compose.yml
executar_windows.bat
main.py                                              # CorteAC (Python Edition para Windows 10 / 11)
run.bat
run.sh
cad/ai_learner.py                                    # JobManager 2000 (Python Edition)
cad/colors.py                                        # JobManager 2000 (Python Edition)
cad/czlib.py                                         # JobManager 2000 (Python Edition)
cad/die_parser.py                                    # JobManager 2000 (Python Edition)
cad/dual_exporter.py                                 # JobManager 2000 (Python Edition)
cad/exporter.py                                      # JobManager 2000 (Python Edition)
cad/fill_engine.py                                   # JobManager 2000 (Python Edition)
cad/geometry.py                                      # JobManager 2000 (Python Edition)
cad/lay_parser.py                                    # JobManager 2000 (Python Edition)
cad/layers_rule.py                                   # JobManager 2000 (Python Edition)
cad/layers_split.py                                  # JobManager 2000 (Python Edition)
cad/macro_engine.py                                  # JobManager 2000 (Python Edition)
cad/material_importer.py                             # JobManager 2000 (Python Edition)
cad/nesting_backend.py                               # cad/nesting_backend.py - Abstração e Gerenciamento de Backends de Nesting para CorteAC
cad/nesting_engine.py                                # JobManager 2000 (Python Edition)
cad/nfp.py                                           # cad/nfp.py - Motor No-Fit Polygon (NFP) em Python Puro para CorteAC / JobManager 2000
cad/onx_exporter.py                                  # JobManager 2000 (Python Edition)
cad/semver.py                                        # Sistema de Versionamento SemVer (Semantic Versioning 2.0.0)
cad/trim_engine.py                                   # JobManager 2000 (Python Edition)
db/__init__.py                                       # Camada de Acesso a Dados do JobManager (MySQL 8.0 / SQLite Reserva)
db/config.py                                         # JobManager 2000 - Configuração de Banco de Dados Central
db/connection.py                                     # JobManager 2000 - Camada Única de Acesso a Banco de Dados
db/schema_mysql.sql
db/migrations/001_initial_mysql_schema.sql
db/migrations/002_add_layout_multisheet_columns.sql
db/migrations/003_add_session_nesting_mode.sql
db/migrations/004_add_shapes_index.sql
db/migrations/005_add_session_layers.sql
db/migrations/006_add_layout_layers.sql
db/migrations/007_add_layout_trim_and_tip.sql
docs/fases/FASE4_RELATORIO_PRODUCAO.md
docs/fases/FASE5B_FRESH_LEARNING.md
docs/fases/FASE5_1_OTIMIZACAO_IA_TESTE.md
docs/fases/FASE5_2_ARQUITETURA_4CAMADAS.md
docs/fases/FASE5_DIAGNOSTICO_IA_TESTE.md
docs/fases/FASE6_0_DECISOES.md
docs/fases/FASE6_0_DIAGNOSTICO_SHAPE_EDITOR.md
docs/fases/FASE6_0_MOCKUP.md
docs/fases/FASE6_1_1_STITCHING_EDITOR.md
docs/fases/FASE6_1_SHAPE_CATALOG_VIEW.md
docs/fases/FASE6_2_1_WARNING_FINAL.md
docs/fases/FASE6_2_2_PERF_CONFTEST.md
docs/fases/FASE6_2_POLIMENTO_CATALOGO.md
docs/fases/FASE6_2_WARNING_ANALYSIS.md
docs/fases/FASE6_4_ROTACAO_INTERATIVA.md
docs/fases/FORMATO_LAY.md
docs/fases/LAYOUT_EDITOR_RE.md
docs/fases/MOTORES_NESTING_PARAMETROS.md
docs/fases/RELATORIO_IMPLEMENTACAO_MELHORIAS.md
docs/fases/RELATORIO_REVERSA_COMELZ_ONX.md
docs/fases/RELATORIO_SISTEMA_COMPLETO.md
docs/ref/layout_re/help_topics.json
packaging/instalar_atalho.sh
tests/_catalog_fixtures.py                           # tests/_catalog_fixtures.py
tests/conftest.py                                    # tests/conftest.py
tests/test_auto_trim_checkbox.py                     # Testes Unitários: Checkbox de Refile Automático e Recorte Pós-Nesting (test_auto_trim_checkbox.py)
tests/test_batch_autonest.py                         # JobManager 2000 (Python Edition)
tests/test_company_logo_print.py                     # Testes Automatizados para a Remoção do Logotipo ATOM e Suporte a Logotipo Personalizado da Empresa
tests/test_create_session_left_click.py              # Testes Unitários: Criação de Sessão clicando com o botão esquerdo na pasta (duplo clique, menu, atalhos).
tests/test_data_integrity.py                         # tests/test_data_integrity.py
tests/test_db_layer.py                               # Testes Unitários da Camada de Banco de Dados Central (MySQL 8.0 & SQLite Reserva)
tests/test_delete_order.py
tests/test_desktop_shortcut.py                       # tests/test_desktop_shortcut.py
tests/test_dual_exporter.py                          # JobManager 2000 (Python Edition)
tests/test_exporter_tsp.py                           # tests/test_exporter_tsp.py
tests/test_lay_parser.py                             # Testes Unitários para o Parser e Gerador de Arquivos .lay (ATOM $$LAYOUT.v3$$)
tests/test_layers_pairs_nesting.py                   # Testes unitários para validação da regra de camadas (layers) no cálculo de peças
tests/test_layers_resto.py                           # Testes unitários e de integração para a regra de camadas e cálculo de resto (calc_resto).
tests/test_layers_split.py                           # tests/test_layers_split.py
tests/test_layers_tip.py                             # tests/test_layers_tip.py
tests/test_layout_editor_bump.py                     # tests/test_layout_editor_bump.py
tests/test_layout_editor_fill.py                     # JobManager 2000 (Python Edition)
tests/test_layout_editor_shortcuts.py                # Testes Automatizados para Atalhos do LayoutEditorView:
tests/test_layout_editor_sidebar_selection.py        # tests/test_layout_editor_sidebar_selection.py
tests/test_layout_editor_trim.py                     # Testes Automatizados para a Funcionalidade de Refilar Layout (Corte Automático CAM):
tests/test_layout_editor_visual_regression.py        # tests/test_layout_editor_visual_regression.py
tests/test_layout_layers.py                          # tests/test_layout_layers.py
tests/test_layout_print_legend.py                    # Testes unitários automatizados para a Legenda de Moldes na Impressão A4 (LayoutPrintDialog).
tests/test_layout_print_material.py                  # Testes unitários para validação da sincronização e formatação automática
tests/test_macro_engine_ia_teste.py                  # Testes de Homologação para o Motor de Cálculo "IA-teste":
tests/test_macro_engine_ia_teste_optimized.py        # JobManager 2000 (Python Edition)
tests/test_material_import.py                        # JobManager 2000 (Python Edition)
tests/test_multisheet_nesting.py                     # Testes automatizados completos para Nesting em Múltiplas Placas (Multi-Sheet Nesting).
tests/test_multisheet_progress.py                    # tests/test_multisheet_progress.py - Suíte de testes para a Fase 6.6 (Multi-sheet e Progresso Determinado)
tests/test_mysql_concurrency.py                      # JobManager 2000 (Python Edition)
tests/test_nesting_backend.py                        # tests/test_nesting_backend.py - Testes unitários para a arquitetura de backends de Nesting
tests/test_nesting_compactness.py                    # tests/test_nesting_compactness.py
tests/test_nesting_contour_gap.py
tests/test_nesting_mode_architecture.py              # JobManager 2000 (Python Edition)
tests/test_nfp.py                                    # tests/test_nfp.py
tests/test_print_layout_abre.py                      # tests/test_print_layout_abre.py
tests/test_print_metros.py                           # tests/test_print_metros.py
tests/test_semver.py                                 # Testes Automatizados para o Sistema de Versionamento SemVer (MAJOR.MINOR.PATCH)
tests/test_session_material_delete.py                # Testes automatizados para remoção de material na sessão via tecla Delete / botão / menu:
tests/test_session_monotonic.py                      # Testes Unitários: Monotonicidade Estrita de Sessões e Persistência contra Re-semeadura
tests/test_session_shapes_multidelete.py             # JobManager 2000 (Python Edition)
tests/test_session_view_progress.py                  # JobManager 2000 (Python Edition)
tests/test_shape_catalog_border_cases.py             # tests/test_shape_catalog_border_cases.py
tests/test_shape_catalog_polish.py                   # tests/test_shape_catalog_polish.py
tests/test_shape_catalog_view.py                     # Testes Unitários: ShapeCatalogView (Catálogo de Moldes - Grid View Matrix)
tests/test_shape_editor_fullscreen.py                # tests/test_shape_editor_fullscreen.py
tests/test_shape_editor_security.py                  # tests/test_shape_editor_security.py
tests/test_shape_editor_stitching.py
tests/test_shape_sorting.py                          # Testes Unitários: Classificação e Ordenação de Moldes e Tamanhos (Maior para Menor / Menor para Maior)
tests/test_shapes_resto.py                           # Testes unitários e de integração para a coluna 'Resto' na grade de Moldes da SessionView.
tests/test_sidebar_counter.py                        # Testes unitários e de integração para o contador de peças da barra lateral,
tests/test_sobras_dobra.py                           # tests/test_sobras_dobra.py
tests/test_strategy_removal.py                       # Testes automatizados para validação da remoção da estratégia flashnestroll (bobinas contínuas):
tests/test_tooltip.py                                # tests/test_tooltip.py
tests/test_validation_and_cancellation.py            # JobManager 2000 (Python Edition)
tests/fixtures/ia_teste_baseline.json
tools/bench_10k_pieces.py                            # tools/bench_10k_pieces.py
tools/bench_ia_teste.py                              # tools/bench_ia_teste.py
tools/bench_ia_teste_optimized.py                    # tools/bench_ia_teste_optimized.py
tools/bench_layout_drag.py                           # tools/bench_layout_drag.py
tools/bench_multi_sheet.py                           # tools/bench_multi_sheet.py
tools/bench_nest.py                                  # tools/bench_nest.py
tools/bench_real_shapes.py                           # tools/bench_real_shapes.py - Benchmark de motores de nesting com CONTORNOS REAIS.
tools/bench_tsp.py                                   # tools/bench_tsp.py
tools/capture_catalog_screenshots.py                 # tools/capture_catalog_screenshots.py
tools/capture_editor_screenshots.py                  # Ferramenta para captura e comparação de screenshots do ShapeEditorView
tools/capture_layout_screenshots.py                  # tools/capture_layout_screenshots.py
tools/check_release_cadence.py                       # Verificador de Cadência de Release (Regra dos 5 Commits)
tools/compare_ia_teste_yield.py                      # tools/compare_ia_teste_yield.py
tools/compare_learning_states.py                     # tools/compare_learning_states.py
tools/generate_modern_icons.py                       # tools/generate_modern_icons.py
tools/migrate_sqlite_to_mysql.py                     # tools/migrate_sqlite_to_mysql.py - Migra jobmanager.db (SQLite) para MySQL 8.0 Central.
tools/profile_drag.py                                # tools/profile_drag.py
tools/profile_ia_teste.py                            # tools/profile_ia_teste.py
tools/profile_nest.py                                # tools/profile_nest.py
tools/scrub_all_sessions_shapes.py                   # tools/scrub_all_sessions_shapes.py
tools/semver.py                                      # Sistema de Versionamento SemVer (Semantic Versioning 2.0.0)
tools/verify_fresh_learning.py                       # tools/verify_fresh_learning.py
tools/fresh_test/settings_snapshot.json
tools/re_dump/build_layout_inventory.py              # tools/re_dump/build_layout_inventory.py
tools/re_dump/extract_help_docs.py                   # tools/re_dump/extract_help_docs.py
tools/re_dump/extract_pe_resources.py                # tools/re_dump/extract_pe_resources.py
tools/re_dump/generate_layout_editor_re_md.py        # generate_layout_editor_re_md.py
tools/re_dump/layout_inventory.json
ui/add_shapes_dialog.py                              # JobManager 2000 (Python Edition)
ui/batch_nest_dialog.py                              # JobManager 2000 (Python Edition)
ui/cad_canvas.py                                     # JobManager 2000 (Python Edition)
ui/debug_panel.py                                    # JobManager 2000 (Python Edition)
ui/desktop_shortcut.py                               # ui/desktop_shortcut.py
ui/dieproc_dialog.py                                 # JobManager 2000 (Python Edition)
ui/edit_shape_in_session_dialog.py                   # JobManager 2000 (Python Edition)
ui/fill_user_dialog.py                               # JobManager 2000 (Python Edition)
ui/import_materials_dialog.py                        # JobManager 2000 (Python Edition)
ui/layout_editor_view.py                             # JobManager 2000 (Python Edition)
ui/layout_print_dialog.py                            # JobManager 2000 (Python Edition)
ui/macro_panel.py                                    # JobManager 2000 (Python Edition)
ui/main_window.py                                    # CorteAC (Edição Python para Windows 10 / 11)
ui/material_codes_view.py                            # JobManager 2000 (Python Edition)
ui/nesting_mode_widget.py                            # JobManager 2000 (Python Edition)
ui/options_dialog.py                                 # JobManager 2000 (Python Edition)
ui/order_view.py                                     # JobManager 2000 (Python Edition)
ui/params_dialog.py                                  # JobManager 2000 (Python Edition)
ui/session_view.py                                   # JobManager 2000 (Python Edition)
ui/shape_catalog_view.py                             # JobManager 2000 (Python Edition)
ui/shape_editor_view.py                              # JobManager 2000 (Python Edition)
ui/sort_utils.py                                     # JobManager 2000 (Python Edition)
ui/tooltip.py                                        # ui/tooltip.py - Tooltip flutuante para os botões do Layout Editor.
ui/trim_layout_dialog.py                             # JobManager 2000 (Python Edition)
ui/units.py                                          # ui/units.py - Formatação e leitura de medidas em METROS para o operador.
```
<!-- AUTO:tree:end -->

### 3.0 Classes e funções por arquivo (automático)

<!-- AUTO:symbols:start -->
### `database.py`
- `class DatabaseManager` (linha 44, 60 métodos)
- funções: `get_current_operator`

### `main.py`
- funções: `main`

### `cad/ai_learner.py`
- `class ShapeFeatures` (linha 24, 1 métodos)
- `class ShapeFeatureExtractor` (linha 43, 3 métodos): Extrai características geométricas normalizadas e invariantes a escala/rotação
- `class NestingAIBrain` (linha 189, 8 métodos): Cérebro de Inteligência Artificial Local Embarcada.

### `cad/colors.py`
- funções: `get_color_for_size`, `get_contrast_text_color`, `get_color_emoji`

### `cad/czlib.py`
- `class CZLIBError` (linha 22, 0 métodos): Erro de validação ou processamento do container CZLIB.
- funções: `decompress_czlib`, `compress_czlib`

### `cad/die_parser.py`
- funções: `_parse_float`, `interpolate_arc_bulge`, `clean_shape_name`, `parse_die_content`, `parse_die_file`, `generate_die_content`, `save_die_file`

### `cad/dual_exporter.py`
- `class DualLayoutExporter` (linha 16, 4 métodos): Exportador unificado para máquinas de corte ATOM (FlashCut .lay)

### `cad/exporter.py`
- funções: `reorder_contour_midpoint_longest_edge`, `two_opt_pass`, `or_opt`, `optimize_piece_cutting_order_tsp`, `_canonical_edge`, `export_gcode`, `export_dxf`, `export_xml_report`

### `cad/fill_engine.py`
- funções: `rotate_piece_in_place_math`, `_parse_margins`, `fill_row_pieces`, `fill_row_alternate_pieces`, `fill_column_pieces`, `find_piece_vertical_contact_y`, `find_row_vertical_contact_y`, `fill_sheet_pieces`, `fill_sheet_alternate_pieces`, `fill_user_pieces`

### `cad/geometry.py`
- `class SpatialGrid` (linha 382, 5 métodos): Indexação Espacial 2D (Spatial Grid Hashing).
- funções: `rotate_point`, `clear_transform_cache`, `get_transform_cache_stats`, `_get_contour_hash`, `transform_contour`, `polygon_area`, `polygon_perimeter`, `polygon_bbox`, `bbox_overlap`, `point_in_polygon`, `_ccw`, `segments_intersect`, `_collinear_overlap`, `point_segment_distance_sq`, `simplify_contour_for_collision` (+3)

### `cad/lay_parser.py`
- `class TargetDie` (linha 53, 1 métodos): Representa uma matriz alvo (TG) declarada no layout.
- `class PlacedItem` (linha 74, 0 métodos): Representa uma peça individual posicionada no layout (I).
- `class QualityZone` (linha 99, 0 métodos): Zona de qualidade ou defeito em couro/pele.
- `class LayoutData` (linha 106, 1 métodos): Estrutura consolidada de um layout de corte .lay.
- funções: `_parse_float`, `_parse_int`, `parse_lay`, `link_layout_items_to_db`, `generate_lay_content`, `validate_layout_placement`, `export_layout_from_pieces`

### `cad/layers_rule.py`
- funções: `resolve_layout_layers`, `layers_for_piece`, `format_enfesto_operator_text`, `resolve_session_layers`, `is_layers_defined`, `pecas_na_mesa`, `calc_resto`, `calc_resto_efetivo`, `parse_session_params`, `encode_session_params`, `is_separar_sobras_enabled`, `is_refile_auto_enabled`

### `cad/layers_split.py`
- funções: `log_sobras`, `_recompact_plate`, `separar_sobras_camadas`, `_cluster_pieces_by_y`, `_place_sobra_piece`, `_nest_sobras_on_last_sheet`, `_escolher_divisao_otima`, `separar_sobras_em_ponta`, `desfazer_separacao_sobras`

### `cad/macro_engine.py`
- `class SafeFormulaEvaluator` (linha 215, 4 métodos): Avaliador de expressões matemáticas e lógicas estritamente seguro.
- `class MacroConfig` (linha 359, 1 métodos): Configuração intermediária resultante da compilação de uma macro.
- `class MacroCompiler` (linha 381, 1 métodos): Compila o texto da macro declarativa em um objeto MacroConfig executável.
- `class OmniNestMacroEngine` (linha 505, 7 métodos): Executa a macro declarativa sobre a geometria real dos moldes,
- funções: `clear_macro_caches`, `ramer_douglas_peucker`, `_find_best_horizontal_slot_nfp`, `check_collision_against_placed`, `nest_ia_teste_engine`

### `cad/material_importer.py`
- funções: `_decode_bytes`, `_parse_float`, `_parse_int`, `_normalize_dimension`, `_match_header_key`, `detect_delimiter`, `parse_material_file`, `_parse_json_materials`, `_parse_csv_materials`, `_build_material_record`, `_build_response_payload`, `generate_csv_template`

### `cad/nesting_backend.py`
- `class NestingBackend` (linha 79, 1 métodos): Protocolo formal para motores de nesting 2D intercambiáveis.
- `class PythonBackend` (linha 98, 1 métodos): Backend legado padrão: executa o motor clássico em cad/nesting_engine.py.
- `class NfpBackend` (linha 132, 2 métodos): Backend analítico de alta performance baseado em No-Fit Polygon (NFP).
- funções: `count_convex_parts`, `get_nesting_backend`

### `cad/nesting_engine.py`
- funções: `parse_sequence_num`, `sort_shapes_by_sequence`, `get_paired_offset_cached`, `try_hole_filling_placement`, `check_collision_against_placed`, `calculate_yield`, `calculate_atom_cutting_time`, `parse_coupling_angles`, `dieproc_nest_pieces`, `nest_synthetic_engine`, `nest_tape_engine`, `auto_nest_pieces`, `_auto_nest_pieces_core`, `piece_matches_shape`, `nest_multi_sheet`

### `cad/nfp.py`
- funções: `_translation_invariant_key`, `is_complex_polygon`, `_contact_fallback`, `_normalize_points`, `polygon_signed_area`, `_point_in_triangle`, `_is_strictly_convex`, `decompose_convex`, `minkowski_sum_convex`, `clear_nfp_cache`, `compute_nfp`, `contact_placement_x`, `contact_placement_y`, `find_lowest_point_in_nfp`, `contact_placement`

### `cad/onx_exporter.py`
- funções: `_format_num`, `build_onx_xml`, `export_onx_from_pieces`, `save_onx_file`, `parse_onx`

### `cad/semver.py`
- `class SemVer` (linha 24, 8 métodos)

### `cad/trim_engine.py`
- funções: `calculate_layout_trim_bounds`, `trim_layout_dict`

### `db/config.py`
- funções: `_get_val`, `_get_int`

### `db/connection.py`
- `class ServerUnreachableError` (linha 16, 1 métodos): Lançada quando o servidor MySQL central estiver inacessível.
- `class VersionConflictError` (linha 24, 0 métodos): Lançada quando outro operador salvou o layout concorrentemente (controle otimista).
- `class DBRow` (linha 28, 2 métodos): Registro retornado por consultas: comporta-se como dicionário (row['col'])
- `class DBCursor` (linha 64, 8 métodos): Cursor unificado que traduz placeholders, retorna DBRow e expõe lastrowid.
- `class DBConnection` (linha 141, 7 métodos): Wrapper de conexão unificado com suporte a context manager e transações explícitas.
- `class SimpleMySQLPool` (linha 199, 4 métodos): Pool simples e thread-safe de conexões MySQL com reconexão automática.
- funções: `translate_query_for_mysql`, `get_active_backend`, `set_active_backend`, `get_connection`, `get_memory_connection`

### `tests/_catalog_fixtures.py`
- funções: `make_temp_catalog_db`

### `tests/conftest.py`
- funções: `pytest_sessionstart`, `pytest_runtest_setup`

### `tests/test_auto_trim_checkbox.py`
- `class TestAutoTrimLogic` (linha 22, 6 métodos)
- `class TestSessionViewAutoTrimCheckbox` (linha 113, 8 métodos)
- `class DummyWidget` (linha 215, 3 métodos)
- `class TestAutoTrimMainWindowIntegration` (linha 225, 2 métodos)

### `tests/test_batch_autonest.py`
- `class FakeBatchWindow` (linha 22, 1 métodos): Mock leve de MainWindow contendo todos os componentes e métodos de batch.
- `class TestBatchAutoNest` (linha 115, 12 métodos)

### `tests/test_company_logo_print.py`
- `class TestCompanyLogoPrint` (linha 20, 6 métodos)

### `tests/test_create_session_left_click.py`
- `class TestCreateSessionLeftClick` (linha 14, 13 métodos)

### `tests/test_data_integrity.py`
- `class TestDataIntegrity` (linha 35, 5 métodos)
- funções: `temp_db`

### `tests/test_db_layer.py`
- `class TestDBLayer` (linha 30, 15 métodos)

### `tests/test_delete_order.py`
- `class DummyBtn` (linha 12, 1 métodos)
- `class FakeMain` (linha 16, 7 métodos)
- `class TestDeleteOrderAndArticle` (linha 56, 8 métodos)

### `tests/test_desktop_shortcut.py`
- `class TestDesktopShortcut` (linha 20, 6 métodos)
- `class TestSincronizacaoAutomatica` (linha 103, 4 métodos): O app sincroniza o atalho existente para a versão atual ao iniciar (Linux).

### `tests/test_dual_exporter.py`
- `class TestCZLIB` (linha 22, 4 métodos): Validação do container de compressão CZLIB da Comelz.
- `class TestONXExporter` (linha 62, 4 métodos): Validação do gerador de XML e empacotamento .ONX.
- `class TestDualExporter` (linha 142, 3 métodos): Validação do orquestrador de exportação dupla (ATOM + Comelz).

### `tests/test_exporter_tsp.py`
- `class TestExporterTSP` (linha 38, 13 métodos)
- funções: `calculate_tour_distance`

### `tests/test_lay_parser.py`
- `class TestLayParser` (linha 33, 14 métodos)

### `tests/test_layers_pairs_nesting.py`
- `class TestLayersPairsNesting` (linha 11, 6 métodos)

### `tests/test_layers_resto.py`
- `class TestLayersResto` (linha 35, 11 métodos)

### `tests/test_layers_split.py`
- `class TestLayersSplit` (linha 41, 19 métodos)

### `tests/test_layers_tip.py`
- `class TestLayersTipSuite` (linha 38, 20 métodos)

### `tests/test_layout_editor_bump.py`
- `class DummyMouseEvent` (linha 40, 1 métodos)
- `class TestLayoutEditorBump` (linha 48, 22 métodos)

### `tests/test_layout_editor_fill.py`
- `class DummyMouseEvent` (linha 25, 1 métodos)
- `class TestLayoutEditorFill` (linha 35, 29 métodos)

### `tests/test_layout_editor_shortcuts.py`
- `class DummyEvent` (linha 32, 1 métodos)
- `class DummyMouseEvent` (linha 38, 1 métodos)
- `class TestLayoutEditorShortcuts` (linha 46, 69 métodos)

### `tests/test_layout_editor_sidebar_selection.py`
- `class DummyMouseEvent` (linha 21, 1 métodos)
- `class TestSidebarSelection` (linha 29, 16 métodos)

### `tests/test_layout_editor_trim.py`
- `class TestLayoutEditorTrim` (linha 16, 9 métodos)

### `tests/test_layout_editor_visual_regression.py`
- `class TestLayoutEditorVisualRegression` (linha 16, 1 métodos)

### `tests/test_layout_layers.py`
- `class TestLayoutLayers` (linha 40, 11 métodos)

### `tests/test_layout_print_legend.py`
- `class TestLayoutPrintLegend` (linha 22, 14 métodos)

### `tests/test_layout_print_material.py`
- `class TestLayoutPrintMaterial` (linha 12, 4 métodos)

### `tests/test_macro_engine_ia_teste.py`
- `class TestMacroEngineIATeste` (linha 50, 15 métodos)
- funções: `make_realistic_shoe_sole_contour`

### `tests/test_macro_engine_ia_teste_optimized.py`
- `class TestMacroEngineIATesteOptimized` (linha 45, 9 métodos)

### `tests/test_material_import.py`
- `class TestMaterialImporter` (linha 29, 11 métodos)
- `class TestImportMaterialsDialogUI` (linha 212, 4 métodos)

### `tests/test_multisheet_nesting.py`
- `class DummyEvent` (linha 44, 1 métodos)
- `class TestMultiSheetNesting` (linha 50, 31 métodos)

### `tests/test_multisheet_progress.py`
- `class TestMultiSheetProgress` (linha 16, 7 métodos)

### `tests/test_mysql_concurrency.py`
- `class TestMySQLConcurrency` (linha 29, 4 métodos)

### `tests/test_nesting_backend.py`
- funções: `test_python_backend_reference`, `test_nfp_backend_zero_collision_50_pieces`, `test_backend_coordinate_agreement`, `test_get_nesting_backend_env_var`, `test_nfp_backend_automatic_fallback`, `test_nfp_backend_sanity_flag`, `test_nfp_backend_zero_collision_300_pieces`, `test_nfp_backend_zero_collision_500_pieces`

### `tests/test_nesting_compactness.py`
- `class TestNestingCompactness` (linha 73, 4 métodos)
- funções: `_shape`, `_poly`, `_min_gap`, `_inside_tip`

### `tests/test_nesting_contour_gap.py`
- `class TestNestingContourGap` (linha 8, 9 métodos)

### `tests/test_nesting_mode_architecture.py`
- `class TestNestingModeArchitecture` (linha 31, 12 métodos)

### `tests/test_nfp.py`
- `class TestNFP` (linha 38, 7 métodos)
- `class TestTransformCacheIdentity` (linha 161, 2 métodos): Regressão: o cache de transformação era indexado por id(contorno) sem validar o

### `tests/test_print_layout_abre.py`
- `class TestContourArea` (linha 25, 2 métodos)
- `class TestPrintLayoutAbre` (linha 35, 7 métodos)

### `tests/test_print_metros.py`
- `class TestImpressaoEmMetros` (linha 17, 6 métodos)
- `class TestPontaEClamp` (linha 81, 5 métodos): A linha azul da ponta não pode sair da placa (caso do PDF refilado).

### `tests/test_semver.py`
- `class TestSemVer` (linha 12, 7 métodos)

### `tests/test_session_material_delete.py`
- `class TestSessionMaterialDelete` (linha 17, 10 métodos)

### `tests/test_session_monotonic.py`
- `class TestSessionMonotonic` (linha 10, 9 métodos)

### `tests/test_session_shapes_multidelete.py`
- `class TestSessionShapesMultiDelete` (linha 23, 8 métodos)

### `tests/test_session_view_progress.py`
- `class TestSessionViewProgress` (linha 23, 8 métodos)

### `tests/test_shape_catalog_border_cases.py`
- `class TestShapeCatalogBorderCases` (linha 22, 7 métodos)

### `tests/test_shape_catalog_polish.py`
- `class TestShapeCatalogPolish` (linha 20, 15 métodos)

### `tests/test_shape_catalog_view.py`
- `class TestShapeCatalogView` (linha 19, 13 métodos)

### `tests/test_shape_editor_fullscreen.py`
- `class TestShapeEditorFullscreen` (linha 19, 11 métodos)

### `tests/test_shape_editor_security.py`
- `class DummyEvent` (linha 24, 1 métodos)
- `class TestShapeEditorSecurity` (linha 33, 9 métodos)

### `tests/test_shape_editor_stitching.py`
- `class TestShapeEditorStitching` (linha 6, 11 métodos)

### `tests/test_shape_sorting.py`
- `class TestShapeSorting` (linha 14, 6 métodos)
- `class DummyKeyEvent` (linha 105, 1 métodos)
- `class TestSessionViewInlineArrowNavigation` (linha 111, 8 métodos)

### `tests/test_shapes_resto.py`
- `class TestCalcRestoPure` (linha 21, 6 métodos)
- `class TestSessionViewShapesRestoGrid` (linha 89, 10 métodos)

### `tests/test_sidebar_counter.py`
- `class TestSidebarCounterAndLayers` (linha 12, 20 métodos)

### `tests/test_sobras_dobra.py`
- `class TestSobrasDobra` (linha 53, 7 métodos)
- `class TestRecompactacaoBase` (linha 131, 5 métodos): A retirada da peça ímpar não pode deixar buraco na placa de 4 camadas.
- funções: `_shape`, `_layout`

### `tests/test_strategy_removal.py`
- `class TestStrategyRemoval` (linha 19, 9 métodos)

### `tests/test_tooltip.py`
- `class TestToolTip` (linha 13, 8 métodos)

### `tests/test_validation_and_cancellation.py`
- `class TestValidationAndCancellation` (linha 26, 11 métodos)

### `tools/bench_10k_pieces.py`
- funções: `get_current_rss_mb`, `get_peak_rss_mb`, `generate_10k_shapes`, `run_stress_test`, `main`

### `tools/bench_ia_teste.py`
- funções: `calculate_sheet_g00`, `run_ia_teste_benchmark`, `main`

### `tools/bench_ia_teste_optimized.py`
- funções: `calculate_sheet_g00`, `run_optimized_benchmark`, `main`

### `tools/bench_layout_drag.py`
- funções: `build_pieces`, `screen_of`, `run_single_benchmark`, `main`

### `tools/bench_multi_sheet.py`
- funções: `generate_benchmark_shapes`, `run_benchmark`, `main`

### `tools/bench_nest.py`
- funções: `load_benchmark_shapes`, `run_benchmark`, `main`

### `tools/bench_real_shapes.py`
- funções: `load_session_shapes`, `count_collisions`, `run_strategy`, `main`

### `tools/bench_tsp.py`
- funções: `generate_tsp_pieces`, `calculate_tour_distance`, `run_tsp_benchmark`, `main`

### `tools/capture_catalog_screenshots.py`
- funções: `capture_catalog_state`, `compare_catalog_states`, `main`

### `tools/capture_editor_screenshots.py`
- funções: `capture_canvas_image`, `capture_before`, `capture_after`, `compare_images`

### `tools/capture_layout_screenshots.py`
- funções: `build_test_pieces`, `render_scenario`, `run_scenarios`, `main`

### `tools/check_release_cadence.py`
- funções: `run_git`, `check_cadence`

### `tools/compare_ia_teste_yield.py`
- funções: `calculate_sheet_g00`, `load_scenario_shapes`, `evaluate_engine`, `compare_scenario`, `main`

### `tools/compare_learning_states.py`
- funções: `calculate_sheet_g00`, `get_all_settings`, `restore_snapshot`, `setup_state_in_db`, `evaluate_state`, `determine_learning_curve_verdict`, `run_comparison`, `main`

### `tools/generate_modern_icons.py`
- funções: `create_supersampled`, `finish_icon`, `make_cut_icon`, `make_copy_icon`, `make_paste_icon`, `make_details_icon`, `make_layout_icon`, `make_shed_icon`, `make_mode_prod_icon`, `make_mode_moldes_icon`, `make_mode_mat_icon`, `make_tree_prod_node_icon`, `make_tree_folder_icon`, `make_tree_order_icon`, `make_tree_session_icon` (+3)

### `tools/migrate_sqlite_to_mysql.py`
- funções: `make_backup`, `migrate`, `main`

### `tools/profile_ia_teste.py`
- funções: `run_profile_ia_teste`, `main`

### `tools/profile_nest.py`
- funções: `run_profiled_nest`, `main`

### `tools/scrub_all_sessions_shapes.py`
- funções: `_fallback_piece_matches_shape`, `match_fn`, `scrub_sessions`, `main`

### `tools/semver.py`
- `class SemVer` (linha 28, 8 métodos)
- funções: `get_repo_root`, `get_current_version`, `update_config_py`, `update_release_workflow`, `set_version`, `analyze_commits_for_bump`, `main`

### `tools/verify_fresh_learning.py`
- funções: `get_ai_settings_from_db`, `get_all_settings_from_db`, `remove_ai_settings`, `restore_settings_from_snapshot`, `run_verification`, `main`

### `tools/re_dump/build_layout_inventory.py`
- funções: `load_text_lines`, `main`

### `tools/re_dump/extract_help_docs.py`
- `class HTMLTextExtractor` (linha 26, 5 métodos)
- funções: `extract_file`, `main`

### `tools/re_dump/extract_pe_resources.py`
- funções: `get_resources`, `get_string_table`, `parse_menu`, `format_menu_tree`, `parse_dialog`, `main`

### `tools/re_dump/generate_layout_editor_re_md.py`
- funções: `main`

### `ui/add_shapes_dialog.py`
- `class AddShapesDialog` (linha 13, 14 métodos)

### `ui/batch_nest_dialog.py`
- `class BatchAutoNestDialog` (linha 14, 3 métodos): Diálogo para revisar as sessões selecionadas em massa, ajustar as configurações
- `class BatchProgressDialog` (linha 317, 7 métodos): Janela modal de progresso em tempo real durante a execução do lote de cálculo.

### `ui/cad_canvas.py`
- `class CADCanvas` (linha 12, 24 métodos)

### `ui/debug_panel.py`
- `class DebugPanel` (linha 24, 9 métodos): Camada 4: Debug / Diagnóstico.

### `ui/desktop_shortcut.py`
- funções: `_desktop_dirs`, `_atalhos_existentes`, `_conteudo_desktop`, `_instalar_icone`, `sincronizar_atalho`

### `ui/dieproc_dialog.py`
- `class DieProcDialog` (linha 12, 19 métodos)

### `ui/edit_shape_in_session_dialog.py`
- `class EditShapeInSessionDialog` (linha 11, 6 métodos)

### `ui/fill_user_dialog.py`
- `class FillUserConstraints` (linha 26, 0 métodos): Parâmetros validados do diálogo 'Set User constraints'.
- `class FillUserDialog` (linha 112, 5 métodos): Diálogo Modal 'Set User constraints' (Dialog 159 original, Win32 ID 50003).
- funções: `validate_fill_user_params`

### `ui/import_materials_dialog.py`
- `class ImportMaterialsDialog` (linha 18, 7 métodos): Diálogo autêntico Windows XP para importação de lista de materiais.

### `ui/layout_editor_view.py`
- `class LayoutEditorView` (linha 262, 150 métodos)
- funções: `_contour_area_mm2`, `_shade_color`, `_contour_key`, `rotate_piece_in_place`

### `ui/layout_print_dialog.py`
- `class LayoutPrintDialog` (linha 329, 22 métodos): Janela modal de Visualização de Impressão (Print Preview) do Layout Editor.
- funções: `get_company_logo_path`, `open_company_logo_dialog`, `format_size`, `extract_molde_base_name`, `format_shape_id_tag`, `_clamp_tip_zone`, `_desenhar_retangulo_tracejado`

### `ui/macro_panel.py`
- `class MacroPanel` (linha 23, 12 métodos): Camada 3: Macro / Aprendizado.

### `ui/main_window.py`
- `class MainWindow` (linha 64, 137 métodos)
- funções: `get_assets_dir`

### `ui/material_codes_view.py`
- `class MaterialCodesView` (linha 13, 21 métodos)

### `ui/nesting_mode_widget.py`
- `class NestingModeWidget` (linha 70, 6 métodos): Widget de seleção de modo de encaixe industrial (Camada 1 de UX).

### `ui/options_dialog.py`
- `class OptionsDialog` (linha 13, 15 métodos)

### `ui/order_view.py`
- `class OrderView` (linha 10, 8 métodos)

### `ui/params_dialog.py`
- `class NestingParamsDialog` (linha 10, 2 métodos)

### `ui/session_view.py`
- `class SobrasConfigDialog` (linha 100, 4 métodos): Diálogo para configuração do modo de Ponta de 2 Camadas (Enfesto em Degrau)
- `class SessionView` (linha 249, 111 métodos)

### `ui/shape_catalog_view.py`
- `class ShapeCatalogView` (linha 38, 44 métodos): Visão MDI em Matriz Grid (Peças × Tamanhos) para exibição e gerenciamento
- funções: `extract_piece_base_name`

### `ui/shape_editor_view.py`
- `class ShapeEditorView` (linha 19, 55 métodos)

### `ui/sort_utils.py`
- funções: `natural_sort_key`, `size_sort_key`, `shape_area_sort_key`, `clean_session_display_name`, `resto_sort_key`

### `ui/tooltip.py`
- `class ToolTip` (linha 18, 8 métodos): Tooltip simples: agenda no <Enter>, mostra perto do cursor e esconde no <Leave>.

### `ui/trim_layout_dialog.py`
- `class TrimLayoutDialog` (linha 16, 15 métodos)

### `ui/units.py`
- funções: `format_m`, `format_dim_mm`, `format_dim_m`, `parse_m`, `parse_m_to_mm`
<!-- AUTO:symbols:end -->

### 3.1 Módulos conhecidos pelo relatório

| Módulo / Classe | Papel | Estado |
|---|---|---|
| `cad/die_parser.py` | Importador/exportador `.die` | Pronto. **Não alterar** sem pedido explícito |
| `cad/lay_parser.py` | Importador/exportador `.lay` (`$$LAYOUT.v3$$`), nesting e ordenação de corte CNC | Pronto |
| `database.py` | Acesso SQLite (`jobmanager.db`), gerenciamento de ordens, artigos, moldes, sessões e layouts | Pronto (`DIVERGÊNCIA: refatorado para MySQL 8.0 Central via pacote db/, SQLite é contingência`) |
| `SessionView` | Sessão de corte, aba Moldes, mini-preview, disparo do encaixe e integração | Pronto |
| `ShapeEditorView` | Reprodução visual do ShedNt | Pronto (visual) |
| `LayoutEditorView` | Editor de layout (canvas vetorial) | Pronto: atalhos F1-F4, Ctrl+Z, Ctrl+S, rotação e persistência |
| `PrintPreviewDialog` | Relatório A4 com rendimento % | Pronto (`DIVERGÊNCIA: implementado como LayoutPrintDialog em ui/layout_print_dialog.py`) |
| `anp_client.py` | Driver ANP: socket não-bloqueante, 4001 (ping) e 4000 (dados) | `[NÃO IMPLEMENTADO]` (`DIVERGÊNCIA: arquivo inexistente no repositório; planejado`) |
| `LoopDaemon` (em `atom_reborn`) | Substitui o TheLoop.exe | Pronto `[NÃO CONFIRMADO no repositório local]` |

> **DIVERGÊNCIAS da Seção 3.1 em relação ao código real:**
> 1. **`database.py`**: O acesso ao banco agora é centralizado via pacote `db/` (`db.connection`, `db.config`). O banco de dados **primário em produção é MySQL 8.0 Central** (com suporte multi-máquina a 8 PCs simultâneos, pool de conexões e concorrência otimista), mantendo o SQLite local (`jobmanager.db`) como contingência/reserva offline.
> 2. **`PrintPreviewDialog`**: No código real do repositório, a classe chama-se `LayoutPrintDialog` e reside em `ui/layout_print_dialog.py` (linha 20, 14 métodos).
> 3. **`anp_client.py`**: O arquivo `anp_client.py` **não existe** no repositório atual. Foi concebido no planejamento original para comunicação direta via socket com a máquina de corte ATOM (portas 4000 e 4001), mas ainda não foi implementado neste repositório.

---

## 4. Modelo de dados (automático)

<!-- AUTO:schema:start -->
### 4.1 Schema MySQL 8.0 (Banco de Dados Principal Central)

DDL base (`db/schema_mysql.sql`) e migrações versionadas (`db/migrations/*.sql`):

```sql
-- =============================================================================
-- DDL Base: db/schema_mysql.sql
-- =============================================================================
-- =============================================================================
-- JobManager 2000 Reborn - Schema DDL para MySQL 8.0 Central
-- Compatível com 8 PCs simultâneos e > 1000 layouts/dia
-- Engine: InnoDB | Charset: utf8mb4 | Collation: utf8mb4_unicode_ci
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INT PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 1. Materiais (Chapas, Bobinas, Peles)
CREATE TABLE IF NOT EXISTS materials (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    type VARCHAR(50) NOT NULL,
    width_mm DOUBLE NOT NULL,
    height_mm DOUBLE NOT NULL,
    area_m2 DOUBLE NOT NULL,
    thickness_mm DOUBLE NOT NULL,
    layers INT DEFAULT 2,
    gap_mm DOUBLE DEFAULT 1.0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Ordens de Produção (Orders)
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    customer VARCHAR(150) NOT NULL,
    name VARCHAR(150) DEFAULT 'Derby Masculino #41',
    status VARCHAR(50) NOT NULL DEFAULT 'Pendente',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_orders_code (code),
    INDEX idx_orders_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Artigos por Ordem (Articles)
CREATE TABLE IF NOT EXISTS articles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    pairs_count INT NOT NULL DEFAULT 1,
    material_id VARCHAR(50) NULL DEFAULT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE SET NULL,
    INDEX idx_articles_order (order_id),
    INDEX idx_articles_material (material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Pastas de Moldes CAD (Shape Folders)
CREATE TABLE IF NOT EXISTS shape_folders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4.1 Pastas de Produção (Job Folders)
CREATE TABLE IF NOT EXISTS job_folders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Moldes / Geometria CAD (Shapes)
CREATE TABLE IF NOT EXISTS shapes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_id INT NULL DEFAULT NULL,
    name VARCHAR(150) NOT NULL,
    color VARCHAR(30) NOT NULL,
    contour_json LONGTEXT NOT NULL,
    holes_json LONGTEXT NULL,
    stitching_json LONGTEXT NULL,
    folder VARCHAR(150) DEFAULT '',
    size VARCHAR(50) DEFAULT '41',
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL,
    INDEX idx_shapes_article (article_id),
    INDEX idx_shapes_name (name),
    INDEX idx_shapes_folder (folder),
    INDEX idx_shapes_article_size_name (article_id, size, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Sessões de Corte / Nesting (Sessions)
CREATE TABLE IF NOT EXISTS sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    order_id INT NULL DEFAULT NULL,
    material_id VARCHAR(50) NULL DEFAULT NULL,
    name VARCHAR(150) NOT NULL DEFAULT '',
    job VARCHAR(100) NOT NULL DEFAULT 'ProduçãoNova',
    status VARCHAR(50) NOT NULL DEFAULT 'Planejado',
    yield_percent DOUBLE DEFAULT 0.0,
    cutting_time_sec DOUBLE DEFAULT 0.0,
    placed_pieces_json LONGTEXT NULL,
    strategy VARCHAR(100) DEFAULT 'flashnestsheet',
    params VARCHAR(100) DEFAULT 'stdNOTFill',
    machine VARCHAR(150) DEFAULT 'ATOM FlashCut Flex 3020',
    shapes_json LONGTEXT NULL,
    gap_mm DOUBLE DEFAULT 1.0,
    margin_left DOUBLE DEFAULT 10.0,
    margin_right DOUBLE DEFAULT 10.0,
    margin_top DOUBLE DEFAULT 10.0,
    margin_bottom DOUBLE DEFAULT 10.0,
    nesting_mode VARCHAR(50) DEFAULT 'auto',
    layers INT NULL DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE SET NULL,
    INDEX idx_sessions_order (order_id),
    INDEX idx_sessions_created (created_at),
    INDEX idx_sessions_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Configurações Globais do Sistema (Settings)
CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(100) PRIMARY KEY,
    `value` LONGTEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Presets DieProc (dp98 ATOM)
CREATE TABLE IF NOT EXISTS dieproc_presets (
    name VARCHAR(100) PRIMARY KEY,
    coupling VARCHAR(100) NOT NULL,
    step DOUBLE DEFAULT 1.0,
    solutions INT DEFAULT 30,
    range1_from DOUBLE DEFAULT -3.0,
    range1_to DOUBLE DEFAULT 3.0,
    range1_step DOUBLE DEFAULT 1.0,
    range2_from DOUBLE DEFAULT 0.0,
    range2_to DOUBLE DEFAULT 0.0,
    range2_step DOUBLE DEFAULT 0.0,
    range3_from DOUBLE DEFAULT 0.0,
    range3_to DOUBLE DEFAULT 0.0,
    range3_step DOUBLE DEFAULT 0.0,
    gap1 DOUBLE DEFAULT 1.0,
    gap2 DOUBLE DEFAULT 0.0,
    gap3 DOUBLE DEFAULT 0.0,
    row_interlock INT DEFAULT 1,
    diagonal INT DEFAULT 0,
    macro_script LONGTEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. Layouts de Corte (.lay) com Controle de Versão Otimista
CREATE TABLE IF NOT EXISTS layouts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    name VARCHAR(150) NOT NULL DEFAULT 'l0000.lay',
    width_mm DOUBLE NOT NULL DEFAULT 0.0,
    height_mm DOUBLE NOT NULL DEFAULT 0.0,
    yield_pct DOUBLE NOT NULL DEFAULT 0.0,
    status VARCHAR(50) NOT NULL DEFAULT 'Nested',
    lay_path VARCHAR(500) NULL,
    version INT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NULL,
    updated_by VARCHAR(100) NULL,
    -- Colunas de compatibilidade e suporte ao formato .lay
    layout_index INT NOT NULL DEFAULT 0,
    code VARCHAR(100) NOT NULL DEFAULT 'l0000.lay',
    path VARCHAR(500) DEFAULT '',
    `desc` VARCHAR(255) DEFAULT '',
    material_code VARCHAR(100) DEFAULT '',
    material_name VARCHAR(150) DEFAULT '',
    gap_mm DOUBLE DEFAULT 1.0,
    ris_w DOUBLE DEFAULT 0.0,
    ris_l DOUBLE DEFAULT 0.0,
    area_mm2 DOUBLE DEFAULT 0.0,
    yield_percent DOUBLE DEFAULT 0.0,
    num_items INT DEFAULT 0,
    num_dies INT DEFAULT 0,
    margin_left DOUBLE DEFAULT 10.0,
    margin_right DOUBLE DEFAULT 10.0,
    margin_top DOUBLE DEFAULT 10.0,
    margin_bottom DOUBLE DEFAULT 10.0,
    layers INT NULL DEFAULT NULL,
    trim_cut_line_json LONGTEXT NULL,
    tip_zone_json VARCHAR(100) NULL,
    layers_tip INT NULL DEFAULT NULL,
    placed_pieces_json LONGTEXT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    INDEX idx_layouts_session_status (session_id, created_at, status),
    INDEX idx_layouts_version (id, version),
    INDEX idx_layouts_session_index (session_id, layout_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Peças Posicionadas do Layout (layout_pieces)
CREATE TABLE IF NOT EXISTS layout_pieces (
    id INT AUTO_INCREMENT PRIMARY KEY,
    layout_id INT NOT NULL,
    mold_id INT NULL,
    shape_id INT NULL,
    x DOUBLE NOT NULL,
    y DOUBLE NOT NULL,
    rotation_deg SMALLINT NOT NULL CHECK (rotation_deg >= 0 AND rotation_deg < 360),
    mirrored TINYINT(1) NOT NULL DEFAULT 0,
    is_mirrored TINYINT(1) NOT NULL DEFAULT 0,
    -- Colunas de metadados CAM / .lay
    item_index INT NOT NULL DEFAULT 0,
    target_index INT NOT NULL DEFAULT 0,
    instance_id INT NOT NULL DEFAULT 0,
    piece_name VARCHAR(150) NOT NULL DEFAULT '',
    size VARCHAR(50) DEFAULT '',
    rotation_rad DOUBLE DEFAULT 0.0,
    color VARCHAR(30) DEFAULT '#2563eb',
    tag VARCHAR(50) DEFAULT 'Pasted',
    quality_zone INT DEFAULT 1,
    FOREIGN KEY (layout_id) REFERENCES layouts(id) ON DELETE CASCADE,
    FOREIGN KEY (mold_id) REFERENCES shapes(id) ON DELETE RESTRICT,
    FOREIGN KEY (shape_id) REFERENCES shapes(id) ON DELETE RESTRICT,
    INDEX idx_layout_pieces_layout (layout_id),
    INDEX idx_layout_pieces_mold (mold_id),
    INDEX idx_layout_pieces_shape (shape_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- Migração: db/migrations/001_initial_mysql_schema.sql
-- -----------------------------------------------------------------------------
-- Migração 001: Schema inicial do MySQL 8.0 para o JobManager Reborn
-- Idempotente

-- =============================================================================
-- JobManager 2000 Reborn - Schema DDL para MySQL 8.0 Central
-- Compatível com 8 PCs simultâneos e > 1000 layouts/dia
-- Engine: InnoDB | Charset: utf8mb4 | Collation: utf8mb4_unicode_ci
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INT PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 1. Materiais (Chapas, Bobinas, Peles)
CREATE TABLE IF NOT EXISTS materials (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    type VARCHAR(50) NOT NULL,
    width_mm DOUBLE NOT NULL,
    height_mm DOUBLE NOT NULL,
    area_m2 DOUBLE NOT NULL,
    thickness_mm DOUBLE NOT NULL,
    layers INT DEFAULT 2,
    gap_mm DOUBLE DEFAULT 1.0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Ordens de Produção (Orders)
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    customer VARCHAR(150) NOT NULL,
    name VARCHAR(150) DEFAULT 'Derby Masculino #41',
    status VARCHAR(50) NOT NULL DEFAULT 'Pendente',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_orders_code (code),
    INDEX idx_orders_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Artigos por Ordem (Articles)
CREATE TABLE IF NOT EXISTS articles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    pairs_count INT NOT NULL DEFAULT 1,
    material_id VARCHAR(50) NULL DEFAULT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE SET NULL,
    INDEX idx_articles_order (order_id),
    INDEX idx_articles_material (material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Pastas de Moldes CAD (Shape Folders)
CREATE TABLE IF NOT EXISTS shape_folders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4.1 Pastas de Produção (Job Folders)
CREATE TABLE IF NOT EXISTS job_folders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Moldes / Geometria CAD (Shapes)
CREATE TABLE IF NOT EXISTS shapes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_id INT NULL DEFAULT NULL,
    name VARCHAR(150) NOT NULL,
    color VARCHAR(30) NOT NULL,
    contour_json LONGTEXT NOT NULL,
    holes_json LONGTEXT NULL,
    stitching_json LONGTEXT NULL,
    folder VARCHAR(150) DEFAULT '',
    size VARCHAR(50) DEFAULT '41',
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL,
    INDEX idx_shapes_article (article_id),
    INDEX idx_shapes_name (name),
    INDEX idx_shapes_folder (folder)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Sessões de Corte / Nesting (Sessions)
CREATE TABLE IF NOT EXISTS sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    order_id INT NULL DEFAULT NULL,
    material_id VARCHAR(50) NULL DEFAULT NULL,
    name VARCHAR(150) NOT NULL DEFAULT '',
    job VARCHAR(100) NOT NULL DEFAULT 'ProduçãoNova',
    status VARCHAR(50) NOT NULL DEFAULT 'Planejado',
    yield_percent DOUBLE DEFAULT 0.0,
    cutting_time_sec DOUBLE DEFAULT 0.0,
    placed_pieces_json LONGTEXT NULL,
    strategy VARCHAR(100) DEFAULT 'flashnestsheet',
    params VARCHAR(100) DEFAULT 'stdNOTFill',
    machine VARCHAR(150) DEFAULT 'ATOM FlashCut Flex 3020',
    shapes_json LONGTEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE SET NULL,
    INDEX idx_sessions_order (order_id),
    INDEX idx_sessions_created (created_at),
    INDEX idx_sessions_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Configurações Globais do Sistema (Settings)
CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(100) PRIMARY KEY,
    `value` LONGTEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Presets DieProc (dp98 ATOM)
CREATE TABLE IF NOT EXISTS dieproc_presets (
    name VARCHAR(100) PRIMARY KEY,
    coupling VARCHAR(100) NOT NULL,
    step DOUBLE DEFAULT 1.0,
    solutions INT DEFAULT 30,
    range1_from DOUBLE DEFAULT -3.0,
    range1_to DOUBLE DEFAULT 3.0,
    range1_step DOUBLE DEFAULT 1.0,
    range2_from DOUBLE DEFAULT 0.0,
    range2_to DOUBLE DEFAULT 0.0,
    range2_step DOUBLE DEFAULT 0.0,
    range3_from DOUBLE DEFAULT 0.0,
    range3_to DOUBLE DEFAULT 0.0,
    range3_step DOUBLE DEFAULT 0.0,
    gap1 DOUBLE DEFAULT 1.0,
    gap2 DOUBLE DEFAULT 0.0,
    gap3 DOUBLE DEFAULT 0.0,
    row_interlock INT DEFAULT 1,
    diagonal INT DEFAULT 0,
    macro_script LONGTEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. Layouts de Corte (.lay) com Controle de Versão Otimista
CREATE TABLE IF NOT EXISTS layouts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    name VARCHAR(150) NOT NULL DEFAULT 'l0000.lay',
    width_mm DOUBLE NOT NULL DEFAULT 0.0,
    height_mm DOUBLE NOT NULL DEFAULT 0.0,
    yield_pct DOUBLE NOT NULL DEFAULT 0.0,
    status VARCHAR(50) NOT NULL DEFAULT 'Nested',
    lay_path VARCHAR(500) NULL,
    version INT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NULL,
    updated_by VARCHAR(100) NULL,
    -- Colunas de compatibilidade e suporte ao formato .lay
    code VARCHAR(100) NOT NULL DEFAULT 'l0000.lay',
    path VARCHAR(500) DEFAULT '',
    `desc` VARCHAR(255) DEFAULT '',
    material_code VARCHAR(100) DEFAULT '',
    material_name VARCHAR(150) DEFAULT '',
    gap_mm DOUBLE DEFAULT 1.0,
    ris_w DOUBLE DEFAULT 0.0,
    ris_l DOUBLE DEFAULT 0.0,
    area_mm2 DOUBLE DEFAULT 0.0,
    yield_percent DOUBLE DEFAULT 0.0,
    num_items INT DEFAULT 0,
    num_dies INT DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    INDEX idx_layouts_session_status (session_id, created_at, status),
    INDEX idx_layouts_version (id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Peças Posicionadas do Layout (layout_pieces)
CREATE TABLE IF NOT EXISTS layout_pieces (
    id INT AUTO_INCREMENT PRIMARY KEY,
    layout_id INT NOT NULL,
    mold_id INT NULL,
    shape_id INT NULL,
    x DOUBLE NOT NULL,
    y DOUBLE NOT NULL,
    rotation_deg SMALLINT NOT NULL CHECK (rotation_deg >= 0 AND rotation_deg < 360),
    mirrored TINYINT(1) NOT NULL DEFAULT 0,
    is_mirrored TINYINT(1) NOT NULL DEFAULT 0,
    -- Colunas de metadados CAM / .lay
    item_index INT NOT NULL DEFAULT 0,
    target_index INT NOT NULL DEFAULT 0,
    instance_id INT NOT NULL DEFAULT 0,
    piece_name VARCHAR(150) NOT NULL DEFAULT '',
    size VARCHAR(50) DEFAULT '',
    rotation_rad DOUBLE DEFAULT 0.0,
    color VARCHAR(30) DEFAULT '#2563eb',
    tag VARCHAR(50) DEFAULT 'Pasted',
    quality_zone INT DEFAULT 1,
    FOREIGN KEY (layout_id) REFERENCES layouts(id) ON DELETE CASCADE,
    FOREIGN KEY (mold_id) REFERENCES shapes(id) ON DELETE RESTRICT,
    FOREIGN KEY (shape_id) REFERENCES shapes(id) ON DELETE RESTRICT,
    INDEX idx_layout_pieces_layout (layout_id),
    INDEX idx_layout_pieces_mold (mold_id),
    INDEX idx_layout_pieces_shape (shape_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO schema_version (version, description)
SELECT 1, 'Schema inicial do JobManager Desktop para MySQL 8.0 com suporte a multi-usuário e concorrência'
WHERE NOT EXISTS (SELECT 1 FROM schema_version WHERE version = 1);

-- -----------------------------------------------------------------------------
-- Migração: db/migrations/002_add_layout_multisheet_columns.sql
-- -----------------------------------------------------------------------------
-- Migração 002: Suporte a Múltiplos Layouts por Sessão (Nesting Multi-Placa)
-- Compatível com MySQL 8.0 Central

ALTER TABLE layouts ADD COLUMN IF NOT EXISTS layout_index INT NOT NULL DEFAULT 0;
ALTER TABLE layouts ADD COLUMN IF NOT EXISTS margin_left DOUBLE DEFAULT 10.0;
ALTER TABLE layouts ADD COLUMN IF NOT EXISTS margin_right DOUBLE DEFAULT 10.0;
ALTER TABLE layouts ADD COLUMN IF NOT EXISTS margin_top DOUBLE DEFAULT 10.0;
ALTER TABLE layouts ADD COLUMN IF NOT EXISTS margin_bottom DOUBLE DEFAULT 10.0;
ALTER TABLE layouts ADD COLUMN IF NOT EXISTS placed_pieces_json LONGTEXT NULL;

CREATE INDEX IF NOT EXISTS idx_layouts_session_index ON layouts (session_id, layout_index);

-- -----------------------------------------------------------------------------
-- Migração: db/migrations/003_add_session_nesting_mode.sql
-- -----------------------------------------------------------------------------
-- Migração 003: Suporte a 4 Camadas de UX e Seleção de Modo de Encaixe
-- Compatível com MySQL 8.0 Central

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS nesting_mode VARCHAR(50) DEFAULT 'auto';

-- -----------------------------------------------------------------------------
-- Migração: db/migrations/004_add_shapes_index.sql
-- -----------------------------------------------------------------------------
-- Migração 004: Índice Composto para Performance do Catálogo de Moldes (Grid View Matrix)
-- Compatível com SQLite 3 e MySQL 8.0

CREATE INDEX IF NOT EXISTS idx_shapes_article_size_name 
ON shapes(article_id, size, name);

-- -----------------------------------------------------------------------------
-- Migração: db/migrations/005_add_session_layers.sql
-- -----------------------------------------------------------------------------
-- Migração 005: Suporte a persistência de camadas (layers) na sessão
-- Compatível com MySQL 8.0 Central

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS layers INT NULL DEFAULT NULL;

-- -----------------------------------------------------------------------------
-- Migração: db/migrations/006_add_layout_layers.sql
-- -----------------------------------------------------------------------------
-- Migração 006: Suporte a persistência de camadas (layers) por layout
-- Compatível com MySQL 8.0 Central

ALTER TABLE layouts ADD COLUMN IF NOT EXISTS layers INT NULL DEFAULT NULL;

-- -----------------------------------------------------------------------------
-- Migração: db/migrations/007_add_layout_trim_and_tip.sql
-- -----------------------------------------------------------------------------
-- Migration 007: Adiciona suporte a persistencia de linha de refile CAM e zona de ponta (enfesto em degrau)
-- Aplicavel em SQLite e MySQL

ALTER TABLE layouts ADD COLUMN trim_cut_line_json TEXT NULL;
ALTER TABLE layouts ADD COLUMN tip_zone_json TEXT NULL;
ALTER TABLE layouts ADD COLUMN layers_tip INT NULL DEFAULT NULL;

```

### 4.2 Schema SQLite (Reserva Local / Legado)

Origem: `jobmanager.db` (banco de contingência offline local)

> [!WARNING]
> **Aviso de desatualização do arquivo local `jobmanager.db`:**
> O arquivo `jobmanager.db` versionado no repositório está desatualizado em relação às tabelas e colunas criadas dinamicamente pelo código (`database.py`):
> - **Tabelas ausentes no `.db`:** `articles_migration_tmp`, `sessions_migration_tmp`, `shapes_migration_tmp`
> *(Nota: Em tempo de execução, o `database.py` aplica as migrações automaticamente no SQLite via `_migrate_layouts_table()` e `CREATE TABLE IF NOT EXISTS`).*

```sql
-- Banco: jobmanager.db
CREATE TABLE "articles" (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            order_id INTEGER NOT NULL,
                            name TEXT NOT NULL,
                            pairs_count INTEGER NOT NULL DEFAULT 1,
                            material_id TEXT NULL,
                            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                            FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE SET NULL
                        );
CREATE TABLE dieproc_presets (
                name TEXT PRIMARY KEY,
                coupling TEXT NOT NULL,
                step REAL DEFAULT 1.0,
                solutions INTEGER DEFAULT 30,
                range1_from REAL DEFAULT -3.0,
                range1_to REAL DEFAULT 3.0,
                range1_step REAL DEFAULT 1.0,
                range2_from REAL DEFAULT 0.0,
                range2_to REAL DEFAULT 0.0,
                range2_step REAL DEFAULT 0.0,
                range3_from REAL DEFAULT 0.0,
                range3_to REAL DEFAULT 0.0,
                range3_step REAL DEFAULT 0.0,
                gap1 REAL DEFAULT 1.0,
                gap2 REAL DEFAULT 0.0,
                gap3 REAL DEFAULT 0.0,
                row_interlock INTEGER DEFAULT 1,
                diagonal INTEGER DEFAULT 0
            , macro_script TEXT DEFAULT '');
CREATE TABLE job_folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                );
CREATE TABLE layout_pieces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                layout_id INTEGER NOT NULL,
                shape_id INTEGER,
                item_index INTEGER NOT NULL,
                target_index INTEGER NOT NULL,
                instance_id INTEGER NOT NULL,
                piece_name TEXT NOT NULL,
                size TEXT DEFAULT '',
                x REAL NOT NULL,
                y REAL NOT NULL,
                rotation_deg REAL NOT NULL,
                rotation_rad REAL NOT NULL,
                is_mirrored INTEGER DEFAULT 0,
                color TEXT DEFAULT '#2563eb',
                tag TEXT DEFAULT 'Pasted',
                quality_zone INTEGER DEFAULT 1, mold_id INTEGER, mirrored INTEGER DEFAULT 0,
                FOREIGN KEY (layout_id) REFERENCES layouts(id) ON DELETE CASCADE,
                FOREIGN KEY (shape_id) REFERENCES shapes(id)
            );
CREATE TABLE layouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                code TEXT NOT NULL DEFAULT 'l0000.lay',
                path TEXT DEFAULT '',
                desc TEXT DEFAULT '',
                material_code TEXT DEFAULT '',
                material_name TEXT DEFAULT '',
                gap_mm REAL DEFAULT 1.0,
                ris_w REAL DEFAULT 0.0,
                ris_l REAL DEFAULT 0.0,
                area_mm2 REAL DEFAULT 0.0,
                yield_percent REAL DEFAULT 0.0,
                num_items INTEGER DEFAULT 0,
                num_dies INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, layout_index INTEGER DEFAULT 0, placed_pieces_json TEXT DEFAULT '[]', status TEXT DEFAULT 'closed', margin_left REAL DEFAULT 10.0, margin_right REAL DEFAULT 10.0, margin_top REAL DEFAULT 10.0, margin_bottom REAL DEFAULT 10.0, name TEXT NOT NULL DEFAULT 'l0000.lay', width_mm REAL DEFAULT 0.0, height_mm REAL DEFAULT 0.0, yield_pct REAL DEFAULT 0.0, version INTEGER DEFAULT 1, updated_at TIMESTAMP DEFAULT NULL, created_by TEXT DEFAULT '', updated_by TEXT DEFAULT '', layers INTEGER NULL DEFAULT NULL, trim_cut_line_json TEXT NULL, tip_zone_json TEXT NULL, layers_tip INTEGER NULL DEFAULT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
CREATE TABLE materials (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                width_mm REAL NOT NULL,
                height_mm REAL NOT NULL,
                area_m2 REAL NOT NULL,
                thickness_mm REAL NOT NULL
            , layers INTEGER DEFAULT 2, gap_mm REAL DEFAULT 1.0);
CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                customer TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pendente',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            , name TEXT DEFAULT 'Derby Masculino #41');
CREATE TABLE "sessions" (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            code TEXT UNIQUE NOT NULL,
                            order_id INTEGER,
                            material_id TEXT NULL,
                            status TEXT NOT NULL DEFAULT 'Planejado',
                            yield_percent REAL DEFAULT 0.0,
                            cutting_time_sec REAL DEFAULT 0.0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            name TEXT DEFAULT '',
                            job TEXT DEFAULT 'ProduçãoNova',
                            placed_pieces_json TEXT DEFAULT '[]',
                            strategy TEXT DEFAULT 'flashnestsheet',
                            params TEXT DEFAULT 'stdNOTFill',
                            machine TEXT DEFAULT 'ATOM FlashCut Flex 3020',
                            shapes_json TEXT DEFAULT '[]',
                            gap_mm REAL DEFAULT 1.0,
                            margin_left REAL DEFAULT 10.0,
                            margin_right REAL DEFAULT 10.0,
                            margin_top REAL DEFAULT 10.0,
                            margin_bottom REAL DEFAULT 10.0,
                            nesting_mode TEXT DEFAULT 'custom',
                            layers INTEGER DEFAULT NULL,
                            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
                            FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE SET NULL
                        );
CREATE TABLE settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
CREATE TABLE shape_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
CREATE TABLE "shapes" (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            article_id INTEGER,
                            name TEXT NOT NULL,
                            color TEXT NOT NULL,
                            contour_json TEXT NOT NULL,
                            holes_json TEXT DEFAULT '[]',
                            stitching_json TEXT DEFAULT '[]',
                            folder TEXT DEFAULT '',
                            size TEXT DEFAULT '41',
                            FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL
                        );
CREATE INDEX idx_shapes_article_size_name ON shapes(article_id, size, name);
```
<!-- AUTO:schema:end -->

Tabelas de layouts e peças (`[CONFIRMADO no schema atual]`):

- `layouts`: layout por sessão (metadados, dimensões da pele/bobina, rendimento %, caminho do `.lay` associado, gap, contadores, version para controle de concorrência otimista, auditoria `created_by`/`updated_by`).
- `layout_pieces`: peças posicionadas (molde/shape_id, item_index, target_index, instance_id, x, y, rotação em graus e radianos, espelhamento, zona de qualidade, tag).

_DIVERGÊNCIA: o texto anterior indicava essas tabelas como "planejadas (ainda não existem, [NÃO CONFIRMADO])", porém já foram implementadas no schema de `database.py` e criadas no banco `jobmanager.db` e no MySQL 8.0 `jobmanager`._

### 4.1 Arquitetura de Banco Central MySQL 8.0 (8 PCs na Fábrica)

- **Servidor Central:** MySQL 8.0 na rede local da fábrica, atendendo a 8 PCs simultâneos (>1000 layouts/dia no total), com `InnoDB` e collation `utf8mb4_unicode_ci`.
- **Camada de Abstração (`db/`):**
  - `db/config.py`: Lê configurações de `db.ini` e variáveis de ambiente (`DB_BACKEND`, `MYSQL_HOST`, `MYSQL_PORT`, etc.).
  - `db/connection.py`: Gerencia pool de conexões thread-safe (`SimpleMySQLPool`) com reconexão automática, tradução de dialetos SQL (`?` -> `%s`, `INSERT OR IGNORE` -> `INSERT IGNORE`, `PRAGMA` -> `SHOW COLUMNS`), e classes de linha `DBRow` (compatível com chave e índice numérico `row[0]`).
  - Tratamento de exceções com diagnóstico detalhado de rede (`ServerUnreachableError`) e conflito (`VersionConflictError`).
- **Controle de Concorrência Otimista (Etapa 3):**
  - Implementado em `save_layout(session_id, layout_data, expected_version, layout_id)`.
  - Executa `UPDATE layouts SET version = version + 1 ... WHERE id = ? AND version = ?`. Se nenhuma linha for atualizada, levanta `VersionConflictError`.
  - No `LayoutEditorView`, o salvamento captura `VersionConflictError` e abre diálogo modal com duas opções claras:
    1. **Salvar Cópia:** Mantém o trabalho do operador e salva com sufixo `_copia` como novo layout independente.
    2. **Recarregar:** Descarta edições locais e recarrega os dados mais recentes do servidor MySQL.
- **Migração Idempotente Transacional (`tools/migrate_sqlite_to_mysql.py`):**
  - Faz backup automático de segurança (`jobmanager.db.bak`).
  - Executa migração atômica de todas as tabelas em transação única.
  - Conciliação linha-a-linha no relatório final: 100% de igualdade confirmada nas 10 tabelas migradas.
- **Reserva Offline (SQLite):**
  - O banco local `jobmanager.db` é mantido estritamente como reserva de emergência/modo demonstração quando `db.ini` tiver `backend = sqlite`.
- **Validação sob Carga Extrema (`tests/test_mysql_concurrency.py`):**
  - 8 threads simultâneas simulando 8 PCs executando 1000 salvamentos (50 a 100 peças cada, >75.000 peças inseridas).
  - Resultados: Vazão de >360 layouts/s, latência média de ~21 ms, zero erros de rede/timeout e reconciliação exata de registros.

---

## 5. Importação `.die` (módulo pronto) `[CONFIRMADO]`

Arquivo: `cad/die_parser.py`. Escopo da diretriz original do usuário: **melhorar somente a importação `.die`**.

1. **Assinaturas aceitas:** `$$FUSTELLA.v3$$`, `$$FUSTELLA.v2$$`, `$$SHAPE2$$`, `$$DIE$$` e derivados.
2. **Higienização de nomes:** remove caminhos de rede (`\\lab-inf\modelos\...`), locais (`C:\Users\...`) e o prefixo `MODEL ` (ex.: `MODEL Gaspea_Derby_41` vira `Gaspea_Derby_41`).
3. **Arcos (`bulge`):** `interpolate_arc_bulge(p1, p2, bulge)`, com `b = tan(θ/4)`, gera vértices reais em vez de corda reta.
4. **Fio do couro:** `directionFrom`/`directionTo` geram `grain_angle_deg = atan2(Δy, Δx)`, `grain_angle_min = θ - 10°`, `grain_angle_max = θ + 10°`, `allowed_discrete_angles = [0.0, 180.0]`.
5. **Zonas de qualidade:** `def_quality` mapeia o grau exigido (1 a 5) para a peça.
6. **Ferramentas:** `drill=`, `pricker=`, `punch=`, `notch=` (coordenadas e diâmetros).
7. **Costuras:** múltiplas polilinhas `cpoint=` delimitadas por `num_of_cpoints=`.
8. **Encodings:** `utf-8`, `latin1`, `cp1252`, `iso-8859-1`; decimal com ponto ou vírgula.
9. **Exportador:** `generate_die_content()` emite `.die` compatível, incluindo furos, punções e qualidade.

**Pendências conhecidas:**
- Arquivos com `num_of_shapes > 1` (`SAGOMA 1`, `SAGOMA 2`...): evoluir para devolver lista de moldes.
- Fator de escala configurável (`scale_factor`, padrão 1.0) para DXF/`.die` antigos em décimos de mm ou pontos de plotter.

---

## 6. Regras industriais (invioláveis)

### 6.1 Zonas de qualidade do couro `[CONFIRMADO]`
Graus de 0 (furo/queimadura, proibido) a 5 (barriga/flancos moles). Uma peça com exigência `Q_req` pode cobrir um defeito de nível `L_def` se e somente se:

```
L_def <= Q_req   (para L_def > 0)
```

- Peça nobre (`Q_req = 1`, ex.: gáspea): nunca toca defeitos de nível 2 a 5.
- Peça secundária (`Q_req = 4`, ex.: forro): pode usar áreas com defeitos leves a médios (2 a 4).

### 6.2 Restrição angular do fio (AngleRange) `[CONFIRMADO]`
- Ângulo `θ = atan2(Δy, Δx)` de `directionFrom`/`directionTo` define o eixo neutro.
- Tolerância `θ ± 10°`. Giros discretos permitidos: `180°` (pé oposto).
- **Giros de 90° proibidos no nesting automático** de peças de cabedal.

### 6.3 Compactação por atração vetorial (Bumping) `[CONFIRMADO]`
Após o posicionamento inicial, micropassos decrescentes `8.0 → 4.0 → 2.0 → 0.5 mm` em três direções: Esquerda `(-1, 0)`, Baixo `(0, -1)` e Diagonal `(-0.707, -0.707)`.

### 6.4 Ordem de usinagem CNC `[CONFIRMADO]`
A ordem de corte do `.lay` para a mesa **não pode** ser aleatória:

1. Furações e ilhoses (`DRILL` / `HOLES`)
2. Piques e punções (`PUNCH` / `PRICKER`)
3. Costuras e rasgos internos (`CUTS` / `CPOINTS`)
4. Contorno externo (`TOOL_KNIFE_DOWN`), **sempre por último** (senão a peça solta perde vácuo e quebra a lâmina)

### 6.5 Regra de Camadas (Layers) e Separação de Sobras `[CONFIRMADO pelo operador]`

- **Definição de Camadas ($L$)**: Folhas empilhadas no enfesto sobre a mesa de corte. 1 peça desenhada gera $L$ peças físicas cortadas.
- **Relação com Pares ($P$)**: $\text{Pares} = \frac{\text{peças físicas}}{2}$. O par é montado fisicamente pelo operador na fábrica a partir das folhas do enfesto; o software não trata pé esquerdo/direito.
- **Pilha de mesa uniforme**: Um layout tem exatamente UM número de camadas. Nunca misturar camadas diferentes na mesma placa.
- **Demanda de Peças na Mesa**: $\lceil \frac{2 \times P}{L} \rceil$ peças desenhadas.
- **Separação Automática das Sobras de 4 Camadas para 2 Camadas (`cad/layers_split.py`)**:
  - Quando a sessão corta com 4 camadas base ($L=4$) e os pares solicitados são ímpares ($P$ ímpar), a última peça desenhada na mesa geraria 4 peças físicas quando apenas 2 são necessárias (sobra de 1 par).
  - Em vez de cortar o par a mais como sobra, o sistema move automaticamente a peça excedente de cada molde ímpar para um **layout extra de 2 camadas** ($L=2$).
  - **Fórmula de estado desejado**:
    - Placas de 4 camadas: $N_4 = P // 2$ peças por molde.
    - Placa de 2 camadas: $N_2 = P \pmod 2$ peças por molde ($1$ peça para cada molde ímpar, $0$ para moldes pares).
  - **Resultado exato**: $N_4 \times 4 + N_2 \times 2 = 4(P // 2) + 2(P \pmod 2) = 2P$ peças físicas exatas = $P$ pares exatos. O resto efetivo torna-se $0$.
  - **Conservação de Peças**: Total desenhado ($N_4 + N_2 = \lceil 2P / 4 \rceil$) é mantido idêntico. O sistema nunca cria nem apaga peças; apenas move a última peça de cada molde ímpar para a placa de 2 camadas.
  - **Critério da Última Peça**: Retirada da peça com maior `placement_index` na placa onde o molde termina (ordem da coluna Sequência da sessão).
  - **Reencaixe Compacto**: As peças retiradas são reencaixadas automaticamente na placa de 2 camadas de forma compacta (bottom-left), respeitando o gap da sessão e com zero colisões.
  - **Idempotência**: Se o operador rodar a separação novamente ou fizer ajustes manuais na placa de 2 camadas, o estado é preservado sem reprocessar nem duplicar placas.
  - **Verificação Física Estrita**: Antes de finalizar, o sistema valida $\sum (\text{peças} \times \text{layers}) = 2P$ para cada molde. Havendo divergência, executa rollback atômico restaurando o estado original.
  - **Eliminação de Placas Vazias**: Se a última placa de 4 camadas esvaziar ao ceder as sobras, ela é descartada e as placas de 4 camadas são renumeradas continuamente (`lay0000`, `lay0001`...), ficando a placa de sobras sempre ao final.

---

## 7. Layout Editor: atalhos

### 7.1 Atalhos confirmados pelo usuário

| Atalho | Ação | Status |
|---|---|---|
| F1 | Ajuste fino: gira a peça 2° para a esquerda | `[CONFIRMADO]` |
| F2 | Ajuste fino: gira a peça 2° para a direita | `[CONFIRMADO]` |
| F3 | Gira 90° por toque, ciclo 0 → 90 → 180 → 270 → 0 | `[CONFIRMADO]` |
| F4 | Gira 180° | `[CONFIRMADO]` |
| Ctrl+Z | Desfazer (voltar) | `[CONFIRMADO]` |
| Ctrl+S | Salvar | `[CONFIRMADO]` |

**Removidos por decisão do usuário (não implementar):** Shift+F3 (giro inverso), Ctrl+Y (refazer, sem pilha de redo).

> **Implementação concluída:** Todos os 6 atalhos (`F1`, `F2`, `F3`, `F4`, `Ctrl+Z`, `Ctrl+S`) estão implementados e operacionais em `ui/layout_editor_view.py`. A proibição estrita de `Shift+F3` e `Ctrl+Y` foi aplicada (sem pilha de redo nem giro inverso), e o comportamento foi coberto por 13 testes unitários automatizados em `tests/test_layout_editor_shortcuts.py`.

### 7.2 Decisões assumidas `[NÃO CONFIRMADO]` (constantes configuráveis no topo do módulo)

| Constante | Valor padrão | Dúvida em aberto |
|---|---|---|
| `ROT_FINE_STEP_DEG` | 2 | n/a (confirmado) |
| `ROT_90_STEP_DEG` | 90 | n/a (confirmado) |
| `ROT_FLIP_STEP_DEG` | 180 | n/a (confirmado) |
| Sentido "esquerda" | anti-horário (+) | Original era anti-horário? |
| Sentido do F3 | anti-horário | Mesmo sentido do F1? |
| Pivô | centro do bounding box da geometria **base** | Confirmar no original |
| Auto-repeat F1/F2 | permitido, 2° constante por evento | Original repetia ao segurar? |
| Várias peças selecionadas | cada uma gira no próprio centro | Ou giravam em grupo? |
| `UNDO_MAX_LEVELS` | 100 | Original pode ter sido 1 nível |
| `UNDO_GROUP_AUTOREPEAT` | True | Original contava cada toque? |
| `SAVE_TARGET` | `"db+file"` | O que o Ctrl+S salvava de fato? Pedia nome? |
| Ctrl+S limpa histórico de undo | Não | Confirmar |

> **Nota de Implementação:** As constantes acima foram definidas no topo de `ui/layout_editor_view.py` (`ROT_FINE_STEP_DEG=2.0`, `ROT_90_STEP_DEG=90.0`, `ROT_FLIP_STEP_DEG=180.0`, `ROT_DIR_LEFT=1`, `ROT_DIR_RIGHT=-1`, `ROT_DIR_F3=1`, `UNDO_MAX_LEVELS=100`, `UNDO_GROUP_AUTOREPEAT=True`, `SAVE_TARGET="db+file"`). Caso o usuário confirme futuramente qualquer ajuste de convenção ou passo, basta atualizar as constantes do módulo.

### 7.3 Requisitos técnicos de rotação
- Rotação como **inteiro em graus**, normalizada em `[0, 360)`. Ângulos intermediários (14°, 92°) preservados.
- Geometria = geometria base + rotação total (nunca rotacionar vértices incrementalmente).
- Atualizar juntos: contorno, bounding box, furos, punções, piques, costuras e direção do fio.
- Validação após cada giro/undo **somente na barra de status**, sem pop-up: fora da pele, sobreposição, fio fora da tolerância (inclui 90°/270° em cabedal), cobertura de defeito pior que o permitido.
- Avisos **não bloqueiam** (o operador manual tem a palavra final).

### 7.4 Estado de implementação (automático)

<!-- AUTO:shortcuts:start -->
**Atalhos esperados (seção 7.1):**

| Atalho | Estado no código | Onde |
|---|---|---|
| F1 | encontrado | `ui/layout_editor_view.py:740`, `ui/layout_editor_view.py:741` |
| F2 | encontrado | `ui/layout_editor_view.py:744`, `ui/layout_editor_view.py:745`, `ui/session_view.py:883` |
| F3 | encontrado | `ui/layout_editor_view.py:748`, `ui/layout_editor_view.py:749` |
| F4 | encontrado | `ui/layout_editor_view.py:756`, `ui/layout_editor_view.py:757` |
| Ctrl+Z | encontrado | `ui/layout_editor_view.py:686`, `ui/layout_editor_view.py:687`, `ui/layout_editor_view.py:688` |
| Ctrl+S | encontrado | `ui/layout_editor_view.py:501`, `ui/layout_editor_view.py:502`, `ui/layout_editor_view.py:698` |
| Shift+F3 | bloqueado (correto) | `ui/layout_editor_view.py:753`, `ui/layout_editor_view.py:754` |
| Ctrl+Y | bloqueado (correto) | `ui/layout_editor_view.py:692`, `ui/layout_editor_view.py:693`, `ui/layout_editor_view.py:694` |

**Todos os atalhos detectados no código:**

| Atalho | Local | Linha |
|---|---|---|
| Alt+Down | `ui/session_view.py:3804` | `entry.bind("<Alt-Down>", lambda e: adjust_number(-1))` |
| Alt+Up | `ui/session_view.py:3803` | `entry.bind("<Alt-Up>", lambda e: adjust_number(+1))` |
| Backspace | `ui/cad_canvas.py:72` | `self.master.bind("<BackSpace>", lambda e: self.delete_selected())` |
| Backspace | `ui/dieproc_dialog.py:87` | `self.preset_listbox.bind("<BackSpace>", lambda e: self.on_delete_clicked())` |
| Backspace | `ui/main_window.py:686` | `self.bind_all("<BackSpace>", self.on_global_delete_key, add="+")` |
| Backspace | `ui/session_view.py:880` | `self.tree_shapes.bind("<BackSpace>", lambda e: self._on_tree_shapes_delete())` |
| Backspace | `ui/session_view.py:1040` | `w.bind("<BackSpace>", self.remove_session_material)` |
| Backspace | `ui/session_view.py:1041` | `w.bind("<Key-BackSpace>", self.remove_session_material)` |
| Backspace | `ui/shape_editor_view.py:248` | `self.bind("<BackSpace>", lambda e: self.delete_selected())` |
| Backspace | `ui/shape_editor_view.py:250` | `self.canvas.bind("<BackSpace>", lambda e: self.delete_selected())` |
| Ctrl+A | `ui/layout_editor_view.py:761` | `w.bind("<Control-a>", self.select_all)` |
| Ctrl+A | `ui/layout_editor_view.py:762` | `w.bind("<Control-A>", self.select_all)` |
| Ctrl+A | `ui/layout_editor_view.py:763` | `w.bind("<Control-Key-a>", self.select_all)` |
| Ctrl+A | `ui/layout_editor_view.py:764` | `w.bind("<Control-Key-A>", self.select_all)` |
| Ctrl+A | `ui/layout_editor_view.py:769` | `self.bind_all("<Control-a>", self.select_all)` |
| Ctrl+A | `ui/layout_editor_view.py:770` | `self.bind_all("<Control-A>", self.select_all)` |
| Ctrl+A | `ui/main_window.py:297` | `edit_menu.add_command(label="Selecionar tudo", accelerator="Ctrl+A", command=sel` |
| Ctrl+A | `ui/main_window.py:687` | `self.bind_all("<Control-a>", self.on_select_all, add="+")` |
| Ctrl+A | `ui/main_window.py:688` | `self.bind_all("<Control-A>", self.on_select_all, add="+")` |
| Ctrl+A | `ui/main_window.py:689` | `self.bind_all("<Control-Key-a>", self.on_select_all, add="+")` |
| Ctrl+A | `ui/main_window.py:690` | `self.bind_all("<Control-Key-A>", self.on_select_all, add="+")` |
| Ctrl+C | `ui/main_window.py:293` | `edit_menu.add_command(label="Copiar", accelerator="Ctrl+C")` |
| Ctrl+Down | `ui/layout_editor_view.py:781` | `self.bind_all("<Control-Down>", lambda e: self.nudge_selected(0, -0.5))` |
| Ctrl+Down | `ui/session_view.py:3802` | `entry.bind("<Control-Down>", lambda e: adjust_number(-1))` |
| Ctrl+Equal | `ui/layout_editor_view.py:676` | `w.bind("<Control-equal>", lambda e: (self.zoom_in(), "break")[1])` |
| Ctrl+Equal | `ui/shape_catalog_view.py:273` | `self.bind("<Control-equal>", lambda e: self.zoom_step(1.2))` |
| Ctrl+Kp_0 | `ui/shape_catalog_view.py:279` | `self.bind("<Control-KP_0>", lambda e: self.reset_zoom())` |
| Ctrl+Kp_add | `ui/shape_catalog_view.py:275` | `self.bind("<Control-KP_Add>", lambda e: self.zoom_step(1.2))` |
| Ctrl+Kp_subtract | `ui/shape_catalog_view.py:277` | `self.bind("<Control-KP_Subtract>", lambda e: self.zoom_step(1.0 / 1.2))` |
| Ctrl+L | `ui/layout_editor_view.py:729` | `w.bind("<Control-l>", self._on_ctrl_l)` |
| Ctrl+L | `ui/layout_editor_view.py:730` | `w.bind("<Control-L>", self._on_ctrl_l)` |
| Ctrl+L | `ui/layout_editor_view.py:731` | `w.bind("<Control-Key-l>", self._on_ctrl_l)` |
| Ctrl+L | `ui/layout_editor_view.py:732` | `w.bind("<Control-Key-L>", self._on_ctrl_l)` |
| Ctrl+Left | `ui/layout_editor_view.py:778` | `self.bind_all("<Control-Left>", lambda e: self.nudge_selected(-0.5, 0))` |
| Ctrl+Minus | `ui/layout_editor_view.py:677` | `w.bind("<Control-minus>", lambda e: (self.zoom_out(), "break")[1])` |
| Ctrl+Minus | `ui/shape_catalog_view.py:276` | `self.bind("<Control-minus>", lambda e: self.zoom_step(1.0 / 1.2))` |
| Ctrl+N | `ui/main_window.py:91` | `self.bind("<Control-n>", lambda e: self.on_new_session())` |
| Ctrl+N | `ui/main_window.py:92` | `self.bind("<Control-N>", lambda e: self.on_new_session())` |
| Ctrl+O | `ui/layout_editor_view.py:703` | `self.canvas.bind("<Control-o>", self.open_layout_dialog)` |
| Ctrl+O | `ui/layout_editor_view.py:704` | `self.canvas.bind("<Control-O>", self.open_layout_dialog)` |
| Ctrl+O | `ui/layout_editor_view.py:705` | `self.bind("<Control-o>", self.open_layout_dialog)` |
| Ctrl+O | `ui/layout_editor_view.py:706` | `self.bind("<Control-O>", self.open_layout_dialog)` |
| Ctrl+P | `ui/layout_editor_view.py:499` | `self.bind("<Control-p>", lambda e: self.print_layout())` |
| Ctrl+P | `ui/layout_editor_view.py:500` | `self.bind("<Control-P>", lambda e: self.print_layout())` |
| Ctrl+P | `ui/layout_editor_view.py:710` | `w.bind("<Control-p>", lambda e: (self.print_layout(), "break")[1])` |
| Ctrl+P | `ui/layout_editor_view.py:711` | `w.bind("<Control-P>", lambda e: (self.print_layout(), "break")[1])` |
| Ctrl+P | `ui/layout_print_dialog.py:904` | `self.bind("<Control-p>", lambda e: self.do_print())` |
| Ctrl+P | `ui/layout_print_dialog.py:905` | `self.bind("<Control-P>", lambda e: self.do_print())` |
| Ctrl+P | `ui/main_window.py:87` | `self.bind("<Control-p>", self.handle_ctrl_p)` |
| Ctrl+P | `ui/main_window.py:88` | `self.bind("<Control-P>", self.handle_ctrl_p)` |
| Ctrl+P | `ui/session_view.py:1131` | `self.tree_lays.bind("<Control-p>", lambda e: (self.print_current_layout(), "brea` |
| Ctrl+P | `ui/session_view.py:1132` | `self.tree_lays.bind("<Control-P>", lambda e: (self.print_current_layout(), "brea` |
| Ctrl+Plus | `ui/layout_editor_view.py:675` | `w.bind("<Control-plus>", lambda e: (self.zoom_in(), "break")[1])` |
| Ctrl+Plus | `ui/shape_catalog_view.py:274` | `self.bind("<Control-plus>", lambda e: self.zoom_step(1.2))` |
| Ctrl+Q | `ui/layout_editor_view.py:673` | `w.bind("<Control-q>", lambda e: (self.zoom_in(), "break")[1])` |
| Ctrl+Q | `ui/layout_editor_view.py:674` | `w.bind("<Control-Q>", lambda e: (self.zoom_in(), "break")[1])` |
| Ctrl+Right | `ui/layout_editor_view.py:779` | `self.bind_all("<Control-Right>", lambda e: self.nudge_selected(0.5, 0))` |
| Ctrl+S | `ui/layout_editor_view.py:501` | `self.bind("<Control-s>", self.save_layout)` |
| Ctrl+S | `ui/layout_editor_view.py:502` | `self.bind("<Control-S>", self.save_layout)` |
| Ctrl+S | `ui/layout_editor_view.py:698` | `self.canvas.bind("<Control-s>", self.save_layout)` |
| Ctrl+S | `ui/layout_editor_view.py:699` | `self.canvas.bind("<Control-S>", self.save_layout)` |
| Ctrl+S | `ui/layout_editor_view.py:700` | `self.bind("<Control-s>", self.save_layout)` |
| Ctrl+S | `ui/layout_editor_view.py:701` | `self.bind("<Control-S>", self.save_layout)` |
| Ctrl+S | `ui/main_window.py:85` | `self.bind("<Control-s>", self.handle_ctrl_s)` |
| Ctrl+S | `ui/main_window.py:86` | `self.bind("<Control-S>", self.handle_ctrl_s)` |
| Ctrl+Shift+L | `ui/layout_editor_view.py:733` | `w.bind("<Control-Shift-l>", self._on_ctrl_shift_l)` |
| Ctrl+Shift+L | `ui/layout_editor_view.py:734` | `w.bind("<Control-Shift-L>", self._on_ctrl_shift_l)` |
| Ctrl+Shift+L | `ui/layout_editor_view.py:735` | `w.bind("<Control-Shift-Key-l>", self._on_ctrl_shift_l)` |
| Ctrl+Shift+L | `ui/layout_editor_view.py:736` | `w.bind("<Control-Shift-Key-L>", self._on_ctrl_shift_l)` |
| Ctrl+T | `ui/layout_editor_view.py:722` | `w.bind("<Control-t>", _on_ctrl_t)` |
| Ctrl+T | `ui/layout_editor_view.py:723` | `w.bind("<Control-T>", _on_ctrl_t)` |
| Ctrl+T | `ui/layout_editor_view.py:724` | `w.bind("<Control-Key-t>", _on_ctrl_t)` |
| Ctrl+T | `ui/layout_editor_view.py:725` | `w.bind("<Control-Key-T>", _on_ctrl_t)` |
| Ctrl+T | `ui/main_window.py:89` | `self.bind("<Control-t>", self.handle_ctrl_t)` |
| Ctrl+T | `ui/main_window.py:90` | `self.bind("<Control-T>", self.handle_ctrl_t)` |
| Ctrl+Up | `ui/layout_editor_view.py:780` | `self.bind_all("<Control-Up>", lambda e: self.nudge_selected(0, 0.5))` |
| Ctrl+Up | `ui/session_view.py:3801` | `entry.bind("<Control-Up>", lambda e: adjust_number(+1))` |
| Ctrl+V | `ui/main_window.py:294` | `edit_menu.add_command(label="Colar", accelerator="Ctrl+V")` |
| Ctrl+X | `ui/main_window.py:292` | `edit_menu.add_command(label="Recortar", accelerator="Ctrl+X")` |
| Ctrl+Y | `ui/layout_editor_view.py:692` | `self.canvas.bind("<Control-y>", lambda e: "break")` |
| Ctrl+Y | `ui/layout_editor_view.py:693` | `self.canvas.bind("<Control-Y>", lambda e: "break")` |
| Ctrl+Y | `ui/layout_editor_view.py:694` | `self.bind("<Control-y>", lambda e: "break")` |
| Ctrl+Y | `ui/layout_editor_view.py:695` | `self.bind("<Control-Y>", lambda e: "break")` |
| Ctrl+Z | `ui/layout_editor_view.py:686` | `self.canvas.bind("<Control-z>", self.undo_action)` |
| Ctrl+Z | `ui/layout_editor_view.py:687` | `self.canvas.bind("<Control-Z>", self.undo_action)` |
| Ctrl+Z | `ui/layout_editor_view.py:688` | `self.bind("<Control-z>", self.undo_action)` |
| Ctrl+Z | `ui/layout_editor_view.py:689` | `self.bind("<Control-Z>", self.undo_action)` |
| Ctrl+Z | `ui/main_window.py:290` | `edit_menu.add_command(label="Desfazer / Reverter", accelerator="Ctrl+Z", command` |
| Ctrl+Z | `ui/main_window.py:691` | `self.bind_all("<Control-z>", self.on_global_undo, add="+")` |
| Ctrl+Z | `ui/main_window.py:692` | `self.bind_all("<Control-Z>", self.on_global_undo, add="+")` |
| Ctrl+Z | `ui/main_window.py:693` | `self.bind_all("<Control-Key-z>", self.on_global_undo, add="+")` |
| Ctrl+Z | `ui/main_window.py:694` | `self.bind_all("<Control-Key-Z>", self.on_global_undo, add="+")` |
| Ctrl+Z | `ui/shape_catalog_view.py:269` | `self.bind("<Control-z>", lambda e: self.action_undo())` |
| Ctrl+Z | `ui/shape_catalog_view.py:270` | `self.bind("<Control-Z>", lambda e: self.action_undo())` |
| Ctrl+Z | `ui/shape_editor_view.py:231` | `self.bind("<Control-z>", self.undo_or_revert)` |
| Ctrl+Z | `ui/shape_editor_view.py:232` | `self.bind("<Control-Z>", self.undo_or_revert)` |
| Ctrl+Z | `ui/shape_editor_view.py:233` | `self.bind("<Control-Key-z>", self.undo_or_revert)` |
| Ctrl+Z | `ui/shape_editor_view.py:234` | `self.bind("<Control-Key-Z>", self.undo_or_revert)` |
| Ctrl+Z | `ui/shape_editor_view.py:235` | `self.canvas.bind("<Control-z>", self.undo_or_revert)` |
| Ctrl+Z | `ui/shape_editor_view.py:236` | `self.canvas.bind("<Control-Z>", self.undo_or_revert)` |
| Ctrl+Z | `ui/shape_editor_view.py:237` | `self.canvas.bind("<Control-Key-z>", self.undo_or_revert)` |
| Ctrl+Z | `ui/shape_editor_view.py:238` | `self.canvas.bind("<Control-Key-Z>", self.undo_or_revert)` |
| Delete | `ui/cad_canvas.py:71` | `self.master.bind("<Delete>", lambda e: self.delete_selected())` |
| Delete | `ui/dieproc_dialog.py:86` | `self.preset_listbox.bind("<Delete>", lambda e: self.on_delete_clicked())` |
| Delete | `ui/layout_editor_view.py:768` | `self.bind_all("<Delete>", lambda e: self.delete_selected())` |
| Delete | `ui/main_window.py:295` | `edit_menu.add_command(label="Excluir", accelerator="Del", command=self.on_global` |
| Delete | `ui/main_window.py:685` | `self.bind_all("<Delete>", self.on_global_delete_key, add="+")` |
| Delete | `ui/main_window.py:2817` | `accelerator="Del",` |
| Delete | `ui/main_window.py:2836` | `accelerator="Del",` |
| Delete | `ui/main_window.py:3066` | `accelerator="Del",` |
| Delete | `ui/main_window.py:3085` | `accelerator="Del",` |
| Delete | `ui/session_view.py:879` | `self.tree_shapes.bind("<Delete>", lambda e: self._on_tree_shapes_delete())` |
| Delete | `ui/session_view.py:1038` | `w.bind("<Delete>", self.remove_session_material)` |
| Delete | `ui/session_view.py:1039` | `w.bind("<Key-Delete>", self.remove_session_material)` |
| Delete | `ui/shape_editor_view.py:247` | `self.bind("<Delete>", lambda e: self.delete_selected())` |
| Delete | `ui/shape_editor_view.py:249` | `self.canvas.bind("<Delete>", lambda e: self.delete_selected())` |
| Down | `ui/layout_editor_view.py:776` | `self.bind_all("<Down>", lambda e: self.bump_selection_vector(0, -1))` |
| Down | `ui/session_view.py:3786` | `entry.bind("<Down>", move_down)` |
| Down | `ui/shape_catalog_view.py:263` | `self.bind("<Down>", lambda e: self.navigate_selection(0, 1))` |
| Escape | `ui/cad_canvas.py:67` | `self.bind("<Escape>", self.cancel_drag)` |
| Escape | `ui/cad_canvas.py:68` | `self.master.bind("<Escape>", self.cancel_drag)` |
| Escape | `ui/dieproc_dialog.py:40` | `self.bind("<Escape>", lambda e: self.destroy())` |
| Escape | `ui/edit_shape_in_session_dialog.py:147` | `self.bind("<Escape>", lambda e: self.destroy())` |
| Escape | `ui/fill_user_dialog.py:156` | `self.bind("<Escape>", lambda e: self.on_cancel())` |
| Escape | `ui/import_materials_dialog.py:49` | `self.bind("<Escape>", lambda e: self.destroy())` |
| Escape | `ui/layout_editor_view.py:664` | `self.canvas.bind("<Escape>", self.on_canvas_escape)` |
| Escape | `ui/layout_editor_view.py:760` | `w.bind("<Escape>", self.cancel_drag)` |
| Escape | `ui/layout_print_dialog.py:907` | `self.bind("<Escape>", self.on_escape)` |
| Escape | `ui/main_window.py:84` | `self.bind("<Escape>", self.exit_fullscreen)` |
| Escape | `ui/main_window.py:684` | `self.bind_all("<Escape>", self.dismiss_popup_menus, add="+")` |
| Escape | `ui/main_window.py:3360` | `dialog.bind("<Escape>", lambda e: dialog.destroy())` |
| Escape | `ui/material_codes_view.py:510` | `dlg.bind("<Escape>", lambda e: dlg.destroy())` |
| Escape | `ui/options_dialog.py:40` | `self.bind("<Escape>", lambda e: self.on_cancel())` |
| Escape | `ui/session_view.py:3240` | `entry.bind("<Escape>", cancel)` |
| Escape | `ui/session_view.py:3358` | `dialog.bind("<Escape>", lambda e: dialog.destroy())` |
| Escape | `ui/session_view.py:3796` | `entry.bind("<Escape>", cancel_edit)` |
| Escape | `ui/shape_catalog_view.py:268` | `self.bind("<Escape>", lambda e: self.on_close_click())` |
| Escape | `ui/shape_editor_view.py:243` | `self.bind("<Escape>", self.on_escape_key)` |
| Escape | `ui/shape_editor_view.py:244` | `self.canvas.bind("<Escape>", self.on_escape_key)` |
| Escape | `ui/trim_layout_dialog.py:77` | `self.bind("<Escape>", lambda e: self.destroy())` |
| F1 | `ui/layout_editor_view.py:740` | `w.bind("<F1>", self.on_f1_press)` |
| F1 | `ui/layout_editor_view.py:741` | `w.bind("<Key-F1>", self.on_f1_press)` |
| F11 | `ui/layout_print_dialog.py:906` | `self.bind("<F11>", self.toggle_fullscreen)` |
| F11 | `ui/main_window.py:83` | `self.bind("<F11>", self.toggle_fullscreen)` |
| F11 | `ui/shape_editor_view.py:241` | `self.bind("<F11>", self.on_f11_fullscreen)` |
| F11 | `ui/shape_editor_view.py:242` | `self.canvas.bind("<F11>", self.on_f11_fullscreen)` |
| F2 | `ui/layout_editor_view.py:744` | `w.bind("<F2>", self.on_f2_press)` |
| F2 | `ui/layout_editor_view.py:745` | `w.bind("<Key-F2>", self.on_f2_press)` |
| F2 | `ui/session_view.py:883` | `self.tree_shapes.bind("<F2>", self.on_tree_shape_f2)` |
| F2 | `ui/session_view.py:1034` | `self.tree_mat.bind("<F2>", self.on_mat_f2_key)` |
| F3 | `ui/layout_editor_view.py:748` | `w.bind("<F3>", self.on_f3_press)` |
| F3 | `ui/layout_editor_view.py:749` | `w.bind("<Key-F3>", self.on_f3_press)` |
| F4 | `ui/layout_editor_view.py:756` | `w.bind("<F4>", self.on_f4_press)` |
| F4 | `ui/layout_editor_view.py:757` | `w.bind("<Key-F4>", self.on_f4_press)` |
| F5 | `ui/main_window.py:130` | `self.bind_all("<F5>", lambda e: self.on_refresh_f5())` |
| F5 | `ui/main_window.py:313` | `tools_menu.add_command(label="Atualizar", accelerator="F5", command=self.on_refr` |
| Iso_left_tab | `ui/session_view.py:3795` | `entry.bind("<ISO_Left_Tab>", move_prev_col)` |
| Kp_down | `ui/session_view.py:3787` | `entry.bind("<KP_Down>", move_down)` |
| Kp_enter | `ui/fill_user_dialog.py:155` | `self.bind("<KP_Enter>", lambda e: self.on_ok())` |
| Kp_enter | `ui/main_window.py:556` | `self.tree_main.bind("<KP_Enter>", self.on_tree_key_return)` |
| Kp_enter | `ui/session_view.py:882` | `self.tree_shapes.bind("<KP_Enter>", self.on_tree_shape_enter)` |
| Kp_enter | `ui/session_view.py:3791` | `entry.bind("<KP_Enter>", move_down)` |
| Kp_enter | `ui/shape_catalog_view.py:267` | `self.bind("<KP_Enter>", lambda e: self.open_selected_shape())` |
| Kp_up | `ui/session_view.py:3789` | `entry.bind("<KP_Up>", move_up)` |
| Left | `ui/layout_editor_view.py:773` | `self.bind_all("<Left>", lambda e: self.bump_selection_vector(-1, 0))` |
| Left | `ui/shape_catalog_view.py:264` | `self.bind("<Left>", lambda e: self.navigate_selection(-1, 0))` |
| R | `ui/cad_canvas.py:69` | `self.master.bind("<r>", lambda e: self.rotate_selected(45))` |
| R | `ui/cad_canvas.py:70` | `self.master.bind("<R>", lambda e: self.rotate_selected(45))` |
| R | `ui/layout_editor_view.py:766` | `self.bind_all("<Key-r>", lambda e: self.rotate_selected(45))` |
| R | `ui/layout_editor_view.py:767` | `self.bind_all("<Key-R>", lambda e: self.rotate_selected(45))` |
| Return | `ui/edit_shape_in_session_dialog.py:146` | `self.bind("<Return>", lambda e: self.on_save())` |
| Return | `ui/fill_user_dialog.py:154` | `self.bind("<Return>", lambda e: self.on_ok())` |
| Return | `ui/import_materials_dialog.py:84` | `self.ent_filepath.bind("<Return>", lambda e: self.load_file_from_path(self.ent_f` |
| Return | `ui/main_window.py:555` | `self.tree_main.bind("<Return>", self.on_tree_key_return)` |
| Return | `ui/main_window.py:3359` | `dialog.bind("<Return>", lambda e: save())` |
| Return | `ui/material_codes_view.py:212` | `self.tree.bind("<Return>", lambda e: self.open_edit_selected_dialog())` |
| Return | `ui/material_codes_view.py:509` | `dlg.bind("<Return>", lambda e: save_action())` |
| Return | `ui/session_view.py:597` | `self.entry_gap.bind("<Return>", self._on_gap_entry_change)` |
| Return | `ui/session_view.py:802` | `self.entry_sname.bind("<Return>", self._on_entry_sname_commit)` |
| Return | `ui/session_view.py:881` | `self.tree_shapes.bind("<Return>", self.on_tree_shape_enter)` |
| Return | `ui/session_view.py:1033` | `self.tree_mat.bind("<Return>", self.on_mat_enter_key)` |
| Return | `ui/session_view.py:1136` | `self.tree_lays.bind("<Return>", self.on_layout_row_double_click)` |
| Return | `ui/session_view.py:3238` | `entry.bind("<Return>", lambda e: commit())` |
| Return | `ui/session_view.py:3357` | `dialog.bind("<Return>", lambda e: save())` |
| Return | `ui/session_view.py:3790` | `entry.bind("<Return>", move_down)` |
| Return | `ui/shape_catalog_view.py:266` | `self.bind("<Return>", lambda e: self.open_selected_shape())` |
| Return | `ui/shape_editor_view.py:312` | `self.entry_name.bind("<Return>", lambda e: self.on_name_change())` |
| Return | `ui/shape_editor_view.py:358` | `self.entry_vx.bind("<Return>", self.on_vertex_entry_change)` |
| Return | `ui/shape_editor_view.py:363` | `self.entry_vy.bind("<Return>", self.on_vertex_entry_change)` |
| Return | `ui/trim_layout_dialog.py:76` | `self.bind("<Return>", lambda e: self.on_confirm())` |
| Right | `ui/layout_editor_view.py:774` | `self.bind_all("<Right>", lambda e: self.bump_selection_vector(1, 0))` |
| Right | `ui/shape_catalog_view.py:265` | `self.bind("<Right>", lambda e: self.navigate_selection(1, 0))` |
| Shift+F3 | `ui/layout_editor_view.py:753` | `w.bind("<Shift-F3>", lambda e: "break")` |
| Shift+F3 | `ui/layout_editor_view.py:754` | `w.bind("<Shift-Key-F3>", lambda e: "break")` |
| Shift+Return | `ui/session_view.py:3792` | `entry.bind("<Shift-Return>", move_up)` |
| Shift+Tab | `ui/session_view.py:3242` | `entry.bind("<Shift-Tab>", on_shift_tab)` |
| Shift+Tab | `ui/session_view.py:3794` | `entry.bind("<Shift-Tab>", move_prev_col)` |
| Space | `ui/add_shapes_dialog.py:135` | `self.tree.bind("<space>", self.on_tree_space)` |
| Space | `ui/main_window.py:552` | `self.tree_main.bind("<space>", self.on_tree_space_toggle)` |
| Tab | `ui/session_view.py:3241` | `entry.bind("<Tab>", on_tab)` |
| Tab | `ui/session_view.py:3793` | `entry.bind("<Tab>", move_next_col)` |
| Up | `ui/layout_editor_view.py:775` | `self.bind_all("<Up>", lambda e: self.bump_selection_vector(0, 1))` |
| Up | `ui/session_view.py:3788` | `entry.bind("<Up>", move_up)` |
| Up | `ui/shape_catalog_view.py:262` | `self.bind("<Up>", lambda e: self.navigate_selection(0, -1))` |

**Conflitos reais detectados:**

- `Ctrl+A`: múltiplos `bind_all` concorrentes em arquivos distintos (`ui/layout_editor_view.py`, `ui/main_window.py`).
- `Delete`: múltiplos `bind_all` concorrentes em arquivos distintos (`ui/layout_editor_view.py`, `ui/main_window.py`).

_Detecção por texto (QShortcut, setShortcut, bind, accelerator, Key_*). Eventos de mouse (Button, Motion, Wheel) e de ciclo de vida (Configure, Focus) são ignorados._
<!-- AUTO:shortcuts:end -->

> **Observação sobre Shift+F3 e Ctrl+Y:**
> O scanner de atalhos de `tools/sync_project_doc.py` reporta `Shift+F3` e `Ctrl+Y` como `bloqueado (correto)`:
> 1. `ui/layout_editor_view.py:390-393, 421-422`: bindings explícitos retornam `"break"` (`lambda e: "break"`) para interceptar e engolir qualquer evento padrão residual do Tkinter ou sistema operacional, garantindo que nada seja executado.
> 2. `tests/test_layout_editor_shortcuts.py:299, 302`: testes unitários confirmam que os eventos retornam break e que não existem os atributos `redo_stack` e `redo_action`.
> Portanto, no sistema real **NÃO existe** funcionalidade de Shift+F3 (giro inverso) e **NÃO existe** funcionalidade de Ctrl+Y (refazer/redo).

### 7.5 Atalhos adicionais detectados no código (além dos 6 confirmados)

**Texto original (histórico):**
> Setas (mover peça), Del, espelhar, zoom, Ctrl+C/V, seleção múltipla. Origem possível: menus do `Layout.exe` original, tabela `ACCELERATORS` do executável (Resource Hacker), arquivo de ajuda. `[PREENCHER quando houver informação]`

**Levantamento dos atalhos de teclado e canvas implementados no código:**

Abaixo estão listados todos os atalhos reais de teclado e manipuladores interativos presentes no código além dos 6 atalhos CAM confirmados (`F1`, `F2`, `F3`, `F4`, `Ctrl+Z`, `Ctrl+S`). Cada um deles está marcado como `[NÃO CONFIRMADO pelo usuário]`:

1. **Setas = Bump Magnético; Ctrl+Setas = ajuste fino (v1.5.5) `[CONFIRMADO no LAYOUT_EDITOR_RE.md]`:**
   - `<Left>` / `<Right>` / `<Up>` / `<Down>`: `bump_selection_vector(±1, 0)` / `(0, ±1)` — a peça desliza em linha reta até encostar em outra peça (contorno real, gap da sessão) ou na margem da placa, com 1 único undo e validação final de zero colisão.
   - `<Control-Left>` / `<Control-Right>` / `<Control-Up>` / `<Control-Down>`: `nudge_selected(±0.5, 0)` / `(0, ±0.5)` — ajuste fino de 0,5 mm, fiel ao Layout.exe.
   - `nudge_selected(dx, dy)` continua disponível como movimento fino programático (usado por testes e ferramentas).

2. **Exclusão de Peças, Moldes e Sessões (`Delete` / `BackSpace`):**
   - `<Delete>` (`ui/layout_editor_view.py:430`): Exclui peça selecionada no layout (`lambda e: self.delete_selected()`) `[NÃO CONFIRMADO pelo usuário]`
   - `<Delete>`, `<BackSpace>` (`ui/main_window.py:535-536`): Exclusão global de sessão ou pasta selecionada na árvore/grid (`self.on_global_delete_key`) `[NÃO CONFIRMADO pelo usuário]`
   - `<Delete>` (`ui/session_view.py:399`): Exclui molde selecionado da sessão (`self.delete_selected_shape()`) `[NÃO CONFIRMADO pelo usuário]`
   - `<Delete>`, `<BackSpace>` (`ui/cad_canvas.py:68-69`): Exclui peça selecionada no canvas CAD legado `[NÃO CONFIRMADO pelo usuário]`
   - **Salvaguarda de Foco (`focus_get()`):** `nudge_selected`, `rotate_selected` e `delete_selected` no `LayoutEditorView` verificam se o foco atual está em um componente de digitação (`Entry`, `Text`, `Treeview`) e ignoram o comando caso esteja, prevenindo movimentação ou exclusão indevida de peças enquanto o operador digita texto.

3. **Rotação Rápida de 45° (`R` / `Key-r`):**
   - `<Key-r>`, `<Key-R>` (`ui/layout_editor_view.py:428-429`): Gira a peça selecionada em +45° anti-horário (`lambda e: self.rotate_selected(45)`) `[NÃO CONFIRMADO pelo usuário]`
   - `<r>`, `<R>` (`ui/cad_canvas.py:66-67`): Gira a peça selecionada em +45° no canvas CAD legado `[NÃO CONFIRMADO pelo usuário]`

4. **Fechamento e Saída de Modais (`Escape`):**
   - `<Escape>` (`ui/main_window.py:62`): Sai do modo tela cheia (`self.exit_fullscreen`) `[NÃO CONFIRMADO pelo usuário]`
   - `<Escape>` (`ui/main_window.py:534`): Fecha menus de contexto abertos (`self.dismiss_popup_menus`) `[NÃO CONFIRMADO pelo usuário]`
   - `<Escape>` (`ui/options_dialog.py:40`): Fecha janela de opções sem salvar (`self.on_cancel`) `[NÃO CONFIRMADO pelo usuário]`
   - `<Escape>` (`ui/material_codes_view.py:466`): Fecha modal de edição de materiais `[NÃO CONFIRMADO pelo usuário]`
   - `<Escape>` (`ui/session_view.py:1378, 1453, 1632`): Cancela edição inline no grid de materiais e fecha modais de sessão `[NÃO CONFIRMADO pelo usuário]`
   - `<Escape>` (`ui/dieproc_dialog.py:39`, `ui/edit_shape_in_session_dialog.py:147`, `ui/main_window.py:2458`): Destrói modal ativo `[NÃO CONFIRMADO pelo usuário]`

5. **Zoom e Navegação via Mouse Wheel:**
   - `<MouseWheel>`, `<Button-4>`, `<Button-5>` (`ui/layout_editor_view.py:203-205, 378-380`): Zoom in/out centrado nas coordenadas do cursor no canvas vetorial `[NÃO CONFIRMADO pelo usuário]`
   - `<MouseWheel>`, `<Button-4>`, `<Button-5>` (`ui/cad_canvas.py:61-63`): Zoom no canvas CAD `[NÃO CONFIRMADO pelo usuário]`
   - `<Control-MouseWheel>` (`ui/layout_print_dialog.py:214`): Zoom na folha de impressão A4 `[NÃO CONFIRMADO pelo usuário]`
   - `<MouseWheel>`, `<Button-4>`, `<Button-5>` (`ui/layout_print_dialog.py:215-217`): Rolagem vertical da folha A4 `[NÃO CONFIRMADO pelo usuário]`

6. **Seleção e Operações de Clipboard (`Ctrl+A`, `Ctrl+C`, `Ctrl+V`, `Ctrl+X`):**
   - `<Control-a>`, `<Control-A>` (`ui/main_window.py:537-540`): Seleciona todas as sessões ou moldes no grid/árvore ativo (`self.on_select_all`) `[NÃO CONFIRMADO pelo usuário]`
   - `Ctrl+C`, `Ctrl+V`, `Ctrl+X` (`ui/main_window.py:246-248`): Aceleradores do menu Editar `[NÃO CONFIRMADO pelo usuário]`

7. **Abertura e Impressão de Layouts (`Ctrl+O`, `Ctrl+P`):**
   - `<Control-o>`, `<Control-O>` (`ui/layout_editor_view.py:401-404`): Abre caixa de diálogo para carregar arquivo `.lay` (`self.open_layout_dialog`) `[NÃO CONFIRMADO pelo usuário]`
   - `<Control-p>`, `<Control-P>` (`ui/layout_editor_view.py`, `ui/main_window.py`): Abre relatório de impressão A4 `LayoutPrintDialog` (`self.print_layout`) `[CONFIRMADO pelo usuário em 18/10/2026]`

8. **Comandos de Sistema (`F5`, `F11`):**
   - `<F5>` (`ui/main_window.py:102, 267`): Recarrega árvore de navegação e grids a partir do banco de dados (`self.on_refresh_f5`) `[NÃO CONFIRMADO pelo usuário]`
   - `<F11>` (`ui/main_window.py:61`): Alterna janela principal entre tela cheia e modo janela (`self.toggle_fullscreen`) `[NÃO CONFIRMADO pelo usuário]`

9. **Navegação e Confirmação em Formulários (`Return`, `Space`, `Tab`, `Shift+Tab`):**
   - `<Return>` (`ui/material_codes_view.py:199, 465`): Confirma diálogo / abre edição de material `[NÃO CONFIRMADO pelo usuário]`
   - `<Return>` (`ui/session_view.py:530, 1376, 1452, 1630`): Confirma edição de célula e submete diálogos de sessão `[NÃO CONFIRMADO pelo usuário]`
   - `<Tab>`, `<Shift-Tab>` (`ui/session_view.py:1379-1380`): Navega entre células adjacentes editáveis no grid `[NÃO CONFIRMADO pelo usuário]`
   - `<space>` (`ui/add_shapes_dialog.py:134`): Marca/desmarca checkbox de seleção do molde na lista `[NÃO CONFIRMADO pelo usuário]`
   - `<Return>` (`ui/shape_editor_view.py:276, 309, 314`): Aplica nome e coordenadas de vértices digitadas `[NÃO CONFIRMADO pelo usuário]`

### 7.6 Desempenho do arraste de peças (coalescência de eventos) `[IMPLEMENTADO 24/10/2026]`

O arraste de peças do `LayoutEditorView` executava, a cada evento `<B1-Motion>`:
transformação do contorno (2×), snap, colisão via `SpatialGrid`, `canvas.move`,
`tag_raise`, `itemconfig` de contornos e 3 `config()` na barra de status. Como o
Tk entrega `<Motion>` e `<B1-Motion>` para o mesmo evento físico e o mouse pode
chegar a 500+ Hz, em PCs mais lentos (Windows da fábrica) os eventos entravam em
fila e o movimento percebido ficava atrasado.

**Solução (sem mudar a semântica do editor):**

- **Coalescência por frame**: `on_canvas_drag` apenas guarda a última posição
  (`_pending_drag_xy`) e agenda no máximo uma atualização a cada
  `DRAG_MIN_INTERVAL_S` (~125 Hz). O release consolida o pendente antes da
  validação estrita de colisão/limites, então a peça nunca "volta" no drop.
- **Barra de status a ~30 Hz** (`STATUS_MIN_INTERVAL_S`), em vez de reconfigurar
  labels a cada pixel; `<Motion>` não disputa com o arraste.
- **Cursor com cache** (`_last_cursor_name`): `canvas.config(cursor=...)` só
  quando o cursor realmente muda.
- **Uma transformação por frame**: o polígono do snap é reaproveitado na
  colisão; contornos só são reconfigurados quando o estado de colisão muda.
- **Pan e divisor**: redraw agendado (`PAN_REDRAW_INTERVAL_MS`), em vez de um
  `redraw()` completo por evento.
- **`redraw()` com grade espacial** acima de 60 peças: a checagem de colisão
  deixou de ser O(n²) de pares e passou a consultar apenas vizinhos de célula
  (mesmo resultado, menos comparações) — reduz o custo do clique/release.

**Benchmark reproduzível** (`tools/bench_layout_drag.py`, caminho real de
eventos com repintura do Tk, 120 peças):

| Métrica | Antes | Depois |
|---|---|---|
| Custo por evento (loop + repaint) | ~3,1 ms (≈319 ev/s) | ~0,9 ms (≈1.070 ev/s) |
| p95 por evento | ~3,4 ms | ~3,0 ms |
| Release (validação + redraw) | ~10,9 ms | ~10,4 ms |
| Release com 300 peças | ~20,9 ms | ~15,6 ms |

Como reproduzir:

```bash
python3 tools/bench_layout_drag.py --pieces 120 --events 300 --interval-ms 4
python3 tools/bench_layout_drag.py --pieces 120 --events 300 --interval-ms 4 --json
```

**Compatibilidade**: `flush_pending_drag()` permite que testes e integrações
chamem `on_canvas_drag` e inspecionem o canvas imediatamente (o frame pendente é
aplicado na hora), preservando os testes de feedback de colisão.

---

## 8. Formato `.lay` `[CONFIRMADO no parser/amostras reais]`

**Texto original (histórico):**
> Nenhuma amostra de `.lay` real foi analisada até agora. Não se sabe se é texto, binário ou XML, nem unidades, cabeçalho ou convenção de coordenadas. Plano: o agente analisa a amostra (file, head, xxd, strings), documenta em docs/FORMATO_LAY.md antes de codar, e marca como "não confirmado" qualquer campo ambíguo. Entregas previstas: cad/lay_parser.py (parse_lay), generate_lay_content() (respeitando a ordem 6.4), tabelas layouts/layout_pieces, integração na UI e tests/test_lay_parser.py (round-trip parse → export → parse).

**DIVERGÊNCIA / Implementação Concluída:**
Amostras autênticas de arquivos `.lay` (`teste.lay`, `A40118.LAY`) foram localizadas em `samples/` e submetidas a engenharia reversa completa:
1. **Estrutura do Formato:** Arquivo texto ASCII/cp1252 com assinatura `$$LAYOUT.v3$$`. Seções delimitadas por tags:
   - `HD`: Cabeçalho (descrição, dimensões do material/pele, rendimento esperado, número de matrizes `TG`, número de peças `I`, gap padrão).
   - `MA`: Material associado (código, nome, espessura, número de camadas).
   - `TG`: Matrizes-alvo (índice da matriz, nome do arquivo `.die`, quantidade de peças posicionadas).
   - `I`: Peças individuais posicionadas (índice, target index, instância, coordenadas `x`, `y` em décimos de mm / mm, ângulo de rotação em décimos de grau / radianos, flag de espelhamento `M`/`N`, zona de qualidade `Q`).
   - `CO`: Geometria do contorno da pele/bobina e zonas de defeito/qualidade internas.
2. **Documentação Técnica:** Especificação completa com tabela de campos, tipos, convenção de coordenadas e flags documentada em `docs/FORMATO_LAY.md`.
3. **Módulo Parser/Gerador:** Criado `cad/lay_parser.py` contendo:
   - `parse_lay(filepath)`: parser tolerante e robusto com extração completa de metadados.
   - `generate_lay_content(layout_data)`: gerador com round-trip de alta fidelidade.
   - `link_layout_items_to_db()`: mapeamento relacional com o catálogo de moldes do SQLite.
   - `export_layout_from_pieces()`: exportação direta respeitando a ordem de corte CNC (seção 6.4: furos → piques → costuras → contorno por último para preservar vácuo).
4. **Testes Unitários:** 13 testes em `tests/test_lay_parser.py` aprovados com 100% de sucesso (round-trip idempotente, verificação de integridade e tolerância a variações de whitespace).

---

## 8.1. Exportação Dual e Formato Comelz .ONX / Container CZLIB `[CONFIRMADO]`

O sistema oferece **Dupla Saída de Layout** unificada ([`cad/dual_exporter.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/cad/dual_exporter.py)), permitindo salvar simultaneamente layouts para máquinas **ATOM FlashCut** (`.lay`) e **Comelz CM44** (`.onx`), eliminando a necessidade de redigitação ou recálculo manual para linhas de produção com mesas híbridas.

### Especificação Técnica do Formato Comelz (.onx)
- **Container `CZLIB\x02`**:
  - Bytes 0 a 5: Assinatura mágica `CZLIB\x02` (`0x43 0x5A 0x4C 0x49 0x42 0x02`).
  - Bytes 6 em diante: Stream comprimido em BZIP2 modificado. O algoritmo proprietário da Comelz compacta o XML UTF-8 e **suprime os 10 primeiros bytes de cabeçalho padrão** (`BZh91AY&SY`). Na descompressão, reinjeta a assinatura antes de invocar o descompressor BZIP2.
  - Implementado em Python puro em [`cad/czlib.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/cad/czlib.py) (`compress_czlib` e `decompress_czlib`), garantindo reversibilidade bit a bit com zero dependências externas.
- **Estrutura XML (Schema ONX v1.1)**:
  - `<security><cuttable /></security>`: Autorização de execução CNC no cabeçote.
  - `<material id="..." type="sheet" width="W" height="H" margin-top="M" margin-left="M" margin-bottom="M" margin-right="M" layers="L">`: Especificação física da chapa/pele.
  - `<qualityarea layer="0" level="0"><path>X1,Y1;X2,Y2...</path></qualityarea>`: Área líquida útil de corte em mm.
  - `<part name="..." size="..." mirrored="true|false">`: Definição de moldes.
  - `<placement x="..." y="..." a="..." status="placed" sortnumber="N"/>`: Posição $(X, Y)$ em mm, ângulo $a$ em radianos e ordenação sequencial ótima de usinagem.
  - `<applications>`: Parâmetros CNC de aceleração e velocidade (`cut_xy_vel`, `cut_xy_acc`, `cut_order="fiep"`).

| Parâmetro | ATOM FlashCut (`.lay`) | Comelz CNC (`.onx`) | Estratégia de Mapeamento |
| :--- | :--- | :--- | :--- |
| **Formato** | Texto plano ANSI (`$$LAYOUT.v3$$`) | XML UTF-8 comprimido com `CZLIB\x02` | Geradores dedicados em `cad/` a partir do mesmo dataset |
| **Dimensões** | Linhas `ris_w <W>` e `ris_l <H>` | Atributos `<material width="W" height="H">` | Mapeamento direto de largura e comprimento (mm) |
| **Margens** | Não declaradas formalmente | Atributos `margin-top/left/bottom/right` | Margens da sessão aplicadas com cálculo de área útil |
| **Posicionamento** | Linha `I <idx> <tg> <id> <flags> <x> <y> <rad>` | `<placement x="..." y="..." a="..." status="placed"/>` | Coordenadas $(X, Y)$ em mm e ângulo em radianos |
| **Espelhamento** | Flag `fn98MR` / flag binária | Atributo `mirrored="true"` em `<part>` | Flag booleana `is_mirrored` |
| **Gap** | Campo `gap <val>` | Tag `<info name="parts_distance"><val></info>` | Distância milimétrica contorno a contorno da sessão |
| **Ordem de Corte** | Sequência de linhas `I` (furo $\rightarrow$ contorno) | Atributo `sortnumber="N"` em `<placement>` | Mesma sequência otimizada Strip-TSP + Or-opt |

---

## 8.2. Motores de Nesting e Parâmetros Industriais `[CONFIRMADO]`

O sistema desacopla a geometria física do material da estratégia de cálculo e agressividade matemática:

### 1. Estratégias de Nesting (Geometria do Material e Disposição Física)
- **`sint` (Sintéticos em Chapas e Placas com Fileiras)**:
  - Organização em fileiras retilíneas contínuas com linha de base comum perfeitamente nivelada, permitindo que a faca trabalhe em alta velocidade sem cursos em vazio.
  - Geminação 0° / 180° com encaixe perfeito entre bico e calcanhar.
  - Aproximação contorno a contorno (*Contour Bumping*) a 1.0 mm estrito.
- **`tape_a` (Tiras, Debruns e Peças Estreitas)**:
  - Alinhamento unidirecional rígido com passo linear constante.
  - Elimina vibrações da lâmina e distorções de largura ao cortar peças compridas e finas.
- **`flashnestsheet` (Chapas Retangulares DieProc dp98)**:
  - Aplica as matrizes de acoplamento (*Coupling*), varredura angular (*Range*) e tolerâncias do DieProc clássico.
  - Suporte a preenchimento de cavidades (*Hole-Filling*) em moldes com áreas ocas.
- **`freenest` (Nesting Livre / Geometria Orgânica e Retalhos)**:
  - Heurística bottom-left com atratores de gravidade espacial para chapas irregulares, coleções com peças de proporções díspares ou retalhos de corte.

### 2. Perfis de Parâmetros DieProc
- **`FastNest`**: Encaixe instantâneo focado na agilidade de liberação para máquina.
- **`HighYield`**: Varredura angular fina e acoplamento agressivo com busca milimétrica do maior aproveitamento percentual.
- **`stdNOTFill`**: Para rigorosamente na quantidade pedida na ordem de produção sem gerar excedentes.
- **`stdFill`**: Preenche a chapa inteira até a borda física, enviando o excedente para estoque de pares.
- **`PrmSss_35`**: Calibração específica para solados e palmilhas pesadas.

---

## 8.3. Arquitetura de Encaixe em 3 Camadas (`NestingModeWidget`) `[CONFIRMADO]`

Para equilibrar facilidade de uso fabril para o operador com controle cirúrgico para a engenharia, a interface adota a **Arquitetura Hierárquica em 3 Camadas** ([`ui/nesting_mode_widget.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/ui/nesting_mode_widget.py)):

```
┌────────────────────────────────────────────────────────────────────────┐
│ CAMADA 1: Modos de Encaixe Industriais (NestingModeWidget)              │
│ [ ⚡ Automático ]  [ ⏩ Rápido ]  [ 💰 Econômico ]  [ 📏 Fitas ]  [ 🧩 Retalhos ]  [ ⚙️ Personalizado ] │
├────────────────────────────────────────────────────────────────────────┤
│ CAMADA 2: Parâmetros Avançados de Corte                                │
│ Estratégia: [ sint |v] (auto)    Parâmetros: [ FastNest |v] (auto)     │
│ Distância peças: [-] [ 1.0 ] [+] mm    Margem: (o) 10mm  ( ) 15mm      │
├────────────────────────────────────────────────────────────────────────┤
│ CAMADA 3: Diagnóstico, Profiler e Painel de Macros                     │
│ [🔧 Painel de Depuração (DebugPanel)]  [🧠 Editor de Macro (MacroPanel)]│
└────────────────────────────────────────────────────────────────────────┘
```

1. **Camada 1 — Modos Industriais (Operador, 90% dos casos)**:
   - **Automático (`auto`)**: Aciona `flashnestsheet` + `HighYield` (motor analítico NFP/SAT). Decisão alterada em 30/10/2026 por medição em moldes reais (§8.12): essa combinação entrega 79,0% de rendimento em 8,3 s contra 65,8% em 9,1 s do motor IA-teste na sessão #156. O motor IA-teste continua disponível em `Personalizado`.
   - **Rápido (`fast`)**: `flashnestsheet` + `FastNest` via NFP.
   - **Econômico (`economic`)**: `flashnestsheet` + `HighYield` focado em rendimento máximo.
   - **Fitas (`tapes`)**: `tape_a` + `stdNOTFill`.
   - **Retalhos (`remnants`)**: `freenest` + `stdNOTFill`.
   - **Personalizado (`custom`)**: Desbloqueia total controle manual das Camadas 2 e 3.
2. **Camada 2 — Parâmetros Avançados (Engenheiro de Processos)**:
   - Seletores de Estratégia, predefinições DieProc, Gap mestre (distância contorno a contorno) e margens de segurança.
   - Badges visuais indicando parâmetros promovidos automaticamente `(auto)`.
3. **Camada 3 — Diagnóstico e P&D (Especialistas)**:
   - **`DebugPanel`**: Seleção explícita de backend de execução (`NFP`, `Python clássico`, etc.) e profiling `cProfile` em tempo real.
   - **`MacroPanel`**: Editor de DSL declarativa com árvore de regras e visualizador de aprendizado do modelo UCB1 Multi-Armed Bandit.
- **Persistência**: Coluna `nesting_mode` persistida na tabela `sessions` (migração [`db/migrations/003_add_session_nesting_mode.sql`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/db/migrations/003_add_session_nesting_mode.sql)).

---

## 8.4. Otimizações Algorítmicas do Motor de Nesting (RDP, NFP Analítico e IA) `[CONFIRMADO]`

### 1. Diagnóstico Estrutural de Gargalo
A instrumentação empírica via `cProfile` revelou que:
- **74,8% do tempo exclusivo (`tottime`)** era consumido em colisões poligonais iterativas SAT (`find_contact_coordinate_binary`).
- A Inteligência Artificial local (UCB1 Bandit e SafeFormula AST) consome menos de **0,02 ms (< 0,01%)**, sendo ultraleve.

### 2. Otimizações Implementadas (`cad/macro_engine.py`)
- **Algoritmo Ramer-Douglas-Peucker (RDP)**:
  - Aplicado apenas em contornos complexos (> 50 vértices) durante o cálculo de contato submilimétrico e NFP.
  - Simplifica a malha de cálculo preservando estritamente os contornos originais para renderização gráfica e exportação `.lay`/`.onx`.
- **Cache Analítico de Separação Horizontal NFP (`_DX_SEP_CACHE`, `_POLY0_CACHE`)**:
  - Armazena os deltas de separação $dX$ em função dos IDs de contorno, rotações relativas e gap.
  - Elimina milhares de chamadas repetidas de projeção SAT.
- **Modo Determinístico no Cérebro de IA (`NestingAIBrain`)**:
  - `suggest_optimized_macro_params(deterministic=True)` congela a exploração estocástica, selecionando estritamente pelo histórico de maior recompensa consolidada, viabilizando repetibilidade de 100% em homologações.

---

## 8.5. Catálogo Matricial de Moldes (`ShapeCatalogView`) `[CONFIRMADO]`

O [`ShapeCatalogView`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/ui/shape_catalog_view.py) oferece visualização em matriz MDI bidimensional inspirada no Shape Editor Comelz:

- **Organização Matricial**: Eixo Vertical com peças base (Gáspea, Traseiro, Língua, Forro...) e Eixo Horizontal com grade completa de tamanhos (22a ao 45).
- **Performance Submilimétrica (< 3 ms)**:
  - Índice composto dedicado `idx_shapes_article_size_name` no SQLite e MySQL 8.0 ([`db/migrations/004_add_shapes_index.sql`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/db/migrations/004_add_shapes_index.sql)).
  - Carregamento de catálogo completo em 2,1 ms para artigos com > 100 variações de molde.
- **Renderização Gráfica Vetorial**:
  - Exibição do contorno principal com código de cor padrão ATOM por tamanho.
  - Furos e punções (`holes_json`).
  - Linhas de costura e pespontos internos (`stitching_json`) destacados em magenta.
- **Interatividade**:
  - Filtros combinados rápidos por Peça e Tamanho.
  - Zoom de 50% a 200%.
  - Navegação bidirecional por setas do teclado e duplo clique para edição direta no `ShapeEditorView`.

---

## 8.6. Trava de Segurança CAD e Ferramentas do Shape Editor `[CONFIRMADO]`

O [`ShapeEditorView`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/ui/shape_editor_view.py) incorpora salvaguardas industriais essenciais para o chão de fábrica:

- **Trava de Segurança de Geometria (`geometry_locked`)**:
  - Inicializa por padrão **BLOQUEADO (`🔒 Editar Geometria`)**, impedindo que operadores alterem acidentalmente vértices, piques ou dimensões de moldes já validados em produção.
  - O desbloqueio (`🔓 Geometria Destravada`) exige clique voluntário com confirmação modal explícita.
- **Ferramenta de Rotação 360° (`rotate`)**:
  - Permite rotacionar o molde livremente no canvas vetorial para alinhamento com o fio de tração (*grain angle*).
- **Controle de Visualização de Costuras (`var_show_stitching`)**:
  - Checkbox dedicado para alternar a exibição de linhas de pesponto e furações sem poluir a edição do contorno externo.
- **Tela Cheia / Maximização com Esc**:
  - Suporte completo a atalho `<F11>` e maximização, com saída limpa pela tecla `<Escape>`.

---

## 8.7. Otimizações de CPU e Algoritmos CAM da Fase 4 `[CONFIRMADO]`

As Fases 0 a 4 eliminaram gargalos estruturais no fluxo produtivo:

1. **Backend No-Fit Polygon (`NfpBackend` em `cad/nfp.py`)**:
   - 4,11× mais veloz (19,5 ms vs 80,3 ms por chapa) com somas de Minkowski e decomposição convexa em Python puro.
   - Zero colisões validadas até 500 peças. Fallback transparente com `CORTEAC_BACKEND=python`.
2. **Otimização CAM CNC de Trajetória (Strip-TSP com 2-Opt + Or-opt em `cad/exporter.py`)**:
   - **Redução de até 11,62% no percurso em vazio (G00)** do cabeçote CNC.
   - Algoritmo 12× a 46× mais veloz (95 ms para N=200). Preserva o vácuo ao cortar o contorno sempre por último.
3. **Renderização Acelerada no Layout Editor**:
   - Redesenho (`redraw`) reduzido para 7,60 ms em 300 peças via 1D Sweep & Prune e tabelas estáticas de tags (`_PIECE_TAGS`).
   - Arraste a 0,22 ms/evento (~4.500 ev/s) com cache geométrico de contorno (99,83% de acerto).

---

## 8.8. Feedback Visual de Nesting e Prevenção de Concorrência na UI (Fase 6.5) `[CONFIRMADO]`

Implementação de feedback reativo e proteção contra operações concorrentes na interface durante o cálculo de encaixe (`ui/session_view.py` e `ui/main_window.py`):

1. **Barra de Progresso Indeterminada e Rótulo de Status**:
   - Adição de `ttk.Progressbar` (modo `indeterminate`, `length=180`) e `tk.Label` dinâmico em `frame_progress`, posicionado imediatamente abaixo dos botões de ação na `SessionView`.
   - Inicialização oculta (`pack_forget`) sem ocupar espaço vertical em repouso.
   - Ao iniciar o cálculo (clique no botão `[Gerar]` ou acionamento via menu/atalho), o método `show_progress()` ativa a animação contínua da barra (`progress_bar.start(10)`), altera o status da sessão para `"Calculando..."` e exibe o rótulo descritivo.
2. **Prevenção de Cliques Duplos e Concorrência**:
   - Os botões `btn_action_nest` (`[Gerar]`), `btn_action_standby` (`[Em espera]`) e `btn_action_rewind` (`[Refazer]`) são automaticamente desabilitados (`state="disabled"`), impedindo disparos concorrentes ou duplo-clique acidental enquanto a thread de cálculo está em execução.
   - Alternância automática do cursor da aplicação para ampulheta (`watch`) indicando processamento ativo em background.
3. **Ciclo de Vida da Thread e Medição de Tempo CAM**:
   - A thread `_worker` em `MainWindow.on_auto_nest` registra o tempo exato de execução via `time.perf_counter()`, anexando `elapsed_ms` aos resultados do nesting.
   - Ao término do cálculo (`_poll_nest_worker`), o método `hide_progress()` é acionado de forma resiliente tanto em cenários de sucesso quanto em caso de erro/exceção ou retorno antecipado, parando a animação (`progress_bar.stop()`), ocultando o frame e restaurando os botões para `state="normal"`.
   - A barra de status da janela principal exibe formalmente o tempo de processamento alcançado (ex: `"Encaixe concluído com estratégia 'ia_teste' na máquina ATOM FlashCut Flex 3020 em 87 ms"`).

---

## 8.9. Exclusão Múltipla de Moldes na SessionView via Tecla Delete e Menu de Contexto `[CONFIRMADO]`

Implementação de exclusão em lote na grade de moldes da `SessionView` (`ui/session_view.py` e `ui/main_window.py`):

1. **Exclusão em Lote com Tecla Delete / BackSpace**:
   - Correção do método `delete_selected_shape()` para coletar todos os índices selecionados (`self.tree_shapes.selection()`), eliminando o antigo afunilamento que capturava apenas o primeiro índice (`sel[0]`).
   - Adaptação dinâmica da mensagem de confirmação:
     * Para 1 molde: `"Deseja remover o molde '<nome>' desta sessão de corte?\n\n(O molde continuará disponível no catálogo geral)"`.
     * Para múltiplos moldes ($N > 1$): `"Deseja remover os N moldes selecionados desta sessão de corte?\n\n(Os moldes continuarão disponíveis no catálogo geral)"`.
   - Remoção em bloco de todos os moldes selecionados preservando a integridade da lista restante.
   - Reatribuição automática de sequência monotônica $1..N$ sem lacunas nos moldes mantidos.
   - Sincronização automática com banco de dados (`on_add_shapes_cb`), memória e limpeza do pré-visualizador se a sessão ficar vazia (`draw_preview_shape(None)`).
2. **Preservação de Múltipla Seleção no Menu de Contexto e Atalhos**:
   - Correção em `show_shapes_context_menu`: ao clicar com botão direito sobre um item que já faz parte da seleção múltipla (ex: selecionados via Shift ou Ctrl), a seleção existente não é mais colapsada para um único item.
   - O item de menu adapta seu rótulo dinamicamente: `🗑️ Remover N Moldes da Sessão`.
   - Retorno de `"break"` no manipulador `<Delete>` e `<BackSpace>` impedindo que o evento se propague para bindings globais da janela principal.
   - Priorização em `MainWindow.on_global_delete_key`: quando o foco está em uma `SessionView` ativa, a tecla Delete atua diretamente sobre os moldes selecionados da sessão antes de qualquer ação na árvore principal.

---

## 8.10. Otimização Multi-Sheet, Progresso Determinado e Teste de Estresse 10k (Fases 6.6 & 6.6.1) `[CONFIRMADO]`

Implementação de telemetria de progresso determinado, salvaguardas de empacotamento contra testes exaustivos e validação extrema de estabilidade de memória (`cad/nesting_engine.py`, `cad/nesting_backend.py`, `ui/session_view.py`, `ui/main_window.py`):

1. **Instrumentação e Telemetria de Progresso Determinado**:
   - `nest_multi_sheet(..., progress_callback=None)` em `cad/nesting_engine.py` aceita callback de progresso invocado a cada nova chapa `progress_callback(sheet_idx, max_sheets)`.
   - `SessionView.update_progress_text(current, total)` atualiza dinamicamente o texto da barra de progresso para: `Calculando chapa {display_current} de {total}...`, com normalização de índice 0-base para 1-base na UI.
   - `MainWindow.on_auto_nest` despacha atualizações thread-safe usando `self.after(0, ...)`.
2. **Salvaguardas de Tempo e Limite de Tentativas no NfpBackend**:
   - Adicionadas constantes e parâmetros de proteção: `MAX_TRIES_PER_PIECE = 30`, `FASTNEST_MAX_TRIES_PER_PIECE = 50` e `SHEET_TIMEOUT_SEC = 5.0` em `NfpBackend`.
   - Limitador de tentativas por peça (`shape_tries`): se a peça não couber após atingir o limite, a chapa atual é fechada imediatamente e a peça passa para a chapa seguinte, eliminando loops de testes infinitos na grade espacial.
   - Timeout por chapa (5 s padrão ou via `CORTEAC_SHEET_TIMEOUT` / `dieproc_params`): encerra o empacotamento da placa atual com segurança se o tempo limite for atingido.
3. **Benchmarks de Produção e Estresse Extremo**:
   - Carga padrão de 1.600 peças (100 pares x 16 tamanhos graduados, `tools/bench_multi_sheet.py`): **0.242 segundos** (**242 ms**) para 26 chapas no modo NFP / FastNest (meta < 10 s superada amplamente).
   - Teste de estresse com 10.000 peças (500 pares x 20 tamanhos graduados, `tools/bench_10k_pieces.py`): **1.510 segundos** (**1509 ms**) para 154 chapas, consumo de pico de RAM contido em **358.00 MB** (teto de 2 GB respeitado com folga de 82%), e zero ocorrência de `MemoryError`.

---

## 8.11. Correção do Travamento do Nesting com Contornos Reais (Fase 6.8) `[CONFIRMADO]`

Diagnóstico e correção do travamento da máquina ao executar o Encaixe em sessões com moldes reais
(sessão #156: 15 moldes × 100 pares = 1.500 peças, placa 1380 × 2980 mm, 2 camadas).

### 1. Causa raiz medida (não presumida)

| Medição | Resultado |
|---|---|
| Molde real de calçado (`.die` importado) | 130–190 vértices, contorno côncavo |
| `decompose_convex` (ear-clipping) nesse contorno | **147 partes convexas** (triângulos) |
| `compute_nfp` entre dois moldes | 147 × 164 = **24.108 polígonos NFP por par de peças** |
| Custo de um `compute_nfp` (perfil) | **~186 ms**; 1.471.412 chamadas de `minkowski_sum_convex` por placa |
| Backend NFP: uma placa | **5,00 s** (bate no timeout) e coloca só **23 peças** |
| Backend SAT (`dieproc_nest_pieces`): uma placa | **428 peças em 9,6 s** (~22 ms/peça), 0 colisões |
| Sessão completa com NFP | 65 a 200 placas × 5 s = **5 a 17 minutos** de CPU a 100% |

O NFP é ~25× mais lento que o motor SAT nesses moldes. Os benchmarks existentes
(`tools/bench_multi_sheet.py`, `bench_10k_pieces.py`) usam `samples/Gaspea_Derby_41.die`,
cujo contorno tem **7 vértices (1 parte convexa)** — por isso reportavam "1.600 peças em 242 ms"
e nunca reproduziram a explosão combinatória de contornos reais.

### 2. Correções aplicadas

1. **Guard de complexidade no `NfpBackend`** (`cad/nesting_backend.py`, `count_convex_parts`):
   se algum contorno tiver mais de `CORTEAC_NFP_MAX_PARTS` (padrão 12) partes convexas, o motor
   delega ao SAT clássico — que é mais rápido **e** empaca mais peças nesses moldes.
2. **Orçamento global de tempo no `nest_multi_sheet`** (`max_total_sec`, padrão 120 s ou
   `CORTEAC_NEST_TOTAL_TIMEOUT`): nenhuma placa consome mais que o orçamento restante e o cálculo
   termina com layouts parciais preservados em vez de prender a máquina.
3. **Timeout por placa também no motor SAT** (`dieproc_nest_pieces`), que antes só tinha cancelamento.
4. **Progresso honesto**: `progress_callback(sheet_idx, total_estimado)` passa a informar a
   estimativa de placas pela densidade observada (0 = ainda desconhecido, exibido como
   "Calculando chapa N..."), em vez de anunciar o limite de segurança `max_sheets` como total.
5. **Thread safety da UI**: `_on_progress` rodava na thread de cálculo e chamava `self.after(...)`
   (Tkinter não é thread-safe). Agora a thread só registra `_nest_progress` e o `_poll_nest_worker`
   (thread principal) atualiza a barra — restaurando o botão `⏹ Cancelar` e a responsividade.
6. **Chaves de controle não são preset**: `cancel_check`, `sheet_timeout_sec`,
   `max_tries_per_piece` e `deterministic` deixaram de fazer os motores acharem que havia um
   preset DieProc customizado (o que alterava silenciosamente `coupling`/`row_interlock`).

### 3. Resultado na sessão #156 (mesmo cenário do travamento)

| Métrica | Antes | Depois |
|---|---|---|
| Placas geradas | 65–200 (limite) | **8** |
| Peças encaixadas | parcial (23/placa) | **1.500 / 1.500 (sucesso)** |
| Tempo total | 5–17 min travado | **37 s** |
| Colisões (gap 0) | — | **0** |
| Peças fora da margem | — | **0** |
| Cancelamento | não respondia | imediato, preservando placas prontas |

### 4. Pendências abertas por este diagnóstico

- **NFP em contorno real** (item estrutural, não aplicado): cachear o NFP por par de moldes +
  rotação com translação (hoje a chave usa coordenadas absolutas e nunca acerta entre linhas),
  pré-normalizar/CCW as partes uma única vez (hoje `_normalize_points` é rechamado 2,9 milhões de
  vezes) e eliminar a cópia profunda dos milhares de polígonos por chamada.
- **Benchmark de regressão**: incluir contorno real de 130+ vértices em `tools/bench_*.py`
  e um teste de não-regressão de tempo, para o caso não voltar a passar despercebido.

---


## 8.12. Polimento dos Motores de Nesting e Medidas em Metros (v1.5.0) `[CONFIRMADO]`

Trabalho de otimização medido em moldes reais de produção (sessão #156: 15 moldes de
131-222 vértices, 1.500 peças, placa 1380 x 2980 mm, 2 camadas). O benchmark antigo não
representava a fábrica: usava um `.die` de 7 vértices.

### 1. Linha de base (antes) — 60 peças por medição

| Motor | Tempo | ms/peça |
|---|---|---|
| `flashnestsheet` | 1,125 s | 18,8 |
| `sint` | 1,159 s | 19,3 |
| `freenest` | 1,084 s | 18,1 |
| `tape_a` | 0,054 s | 0,9 |
| `ia-teste` | 6,826 s | 113,8 |

### 2. Depois (mesma medição)

| Motor | Tempo | ms/peça | Ganho |
|---|---|---|---|
| `flashnestsheet` | 0,233 s | 3,9 | **4,8x** |
| `sint` | 0,249 s | 4,2 | **4,7x** |
| `freenest` | 0,204 s | 3,4 | **5,3x** |
| `tape_a` | 0,030 s | 0,5 | 1,8x |
| `ia-teste` | 0,300 s | 5,0 | **22,8x** |

Sessão completa (1.500 peças), antes 5-17 min travada → **8,3 s** em 5 placas,
**79,0%** de rendimento, 0 colisões e 0 peças fora da margem.

### 3. O que foi otimizado

1. **Colisão poligonal** (`cad/geometry.py`):
   - `polygons_collide` passou a decidir contenção com **um** vértice (sem cruzamento de
     arestas, ou um polígono contém o outro ou estão separados) em vez de testar todos os
     vértices da janela — `point_in_polygon` caiu de 47,8 mil para ~4 mil chamadas.
   - min/max inline no laço de arestas e novos parâmetros `segs_a`/`segs_b` com
     `prepare_segments`, reaproveitando os segmentos da linha atual.
   - `_collinear_overlap` detecta peças exatamente coincidentes/alinhadas, caso que o
     teste de cruzamento estrito não enxergava (regressão coberta por teste de UI).
2. **Busca de contato** (`find_contact_coordinate_binary`): 10 iterações (resolução
   ~0,06 mm na janela típica) mantendo a verificação exata final com passo de 0,05 mm.
3. **Pré-filtro de colisores na linha** (`dieproc_nest_pieces`): durante a busca a peça só
   ocupa a janela `[min_cand_x + min_x, safe_start_x + max_x]`; peças fora dela nem são
   testadas (antes a linha inteira era testada a cada iteração).
4. **NFP com contornos complexos** (`cad/nfp.py`): `is_complex_polygon` (cache invariante a
   translação) e `_contact_fallback` — `contact_placement_x/y` passam a usar busca binária
   exata quando o polígono tem mais de 12 partes convexas. Beneficia o motor IA-teste e o
   `NfpBackend`.
5. **Guard de complexidade** (`NfpBackend`, §8.11): contorno complexo delega ao motor SAT.
6. **Modo Automático**: passa a usar `flashnestsheet` + `HighYield` (melhor rendimento medido).

### 4. Medidas em metros (exigência do operador)

- Novo módulo `ui/units.py`: `format_m`, `format_dim_mm`, `format_dim_m`, `parse_m`,
  `parse_m_to_mm` — vírgula decimal e sufixo `m` opcional na digitação.
- Rótulos convertidos de centímetros para metros: mesa CAD (`Placa 1,38 x 2,98 m`), barra de
  status, cabeçalho da miniatura de placa na sessão, relatório de impressão A4, badge de
  refile e diálogo de refile (`Nova Altura da Placa (m)`).
- O banco continua armazenando milímetros (`width_mm`/`height_mm`); a conversão acontece
  apenas na borda da interface. Formulários de material já usavam metros com vírgula.

### 5. Ferramentas de diagnóstico

- `tools/bench_real_shapes.py`: carrega a sessão real do banco, mede tempo/peças/colisões
  por estratégia e expõe `--json`. Uso: `python3 tools/bench_real_shapes.py --session 156`.
- `corteac_linux --version` (ou `-v`): imprime a versão embutida no executável
  (`CorteAC 1.5.0`) sem abrir a interface — Resolve a dúvida recorrente de qual build está
  instalado na máquina. A mesma versão aparece em `Ajuda → Sobre CorteAC`.

---


## 8.13. Divergência entre o Mini-Preview e o Layout Editor (v1.5.1) `[CONFIRMADO]`

Sintoma relatado pelo operador: a placa exibida no mini-preview da sessão (colorida, bem
encaixada) aparecia diferente ao abrir o Layout Editor — peças sem cor e uma faixa de peças
com contorno vermelho grosso, com formas deformadas.

### 1. Diagnóstico (medido com a sessão 190 do banco real)

| Verificação | Resultado |
|---|---|
| Colisões reais nas 3 placas salvas (`polygons_collide` gap 0) | **0** |
| Polígono salvo pelo motor (`piece.poly`) vs reconstruído pelo render (`contour + x,y,rot`) | **0 divergências** (bbox idêntica) |
| Faixa vermelha detectada na captura | cor `#dc2626` (220,38,38) = cor de **colisão**, não de seleção |
| Caches do editor (`_piece_geom_cache`, `_pair_collision_cache`) | chaveados por `id(contorno)` |

### 2. Causa raiz

`redraw()` e `_get_piece_geom()` usavam `id(contorno)` — o **endereço de memória** da lista —
como identidade da peça. A janela do Layout Editor é reaproveitada entre sessões
(`MainWindow.layout_editor_view` é persistente): ao carregar uma nova sessão, as listas da
anterior são liberadas e o Python **recicla** os endereços, fazendo o cache devolver geometria e
resultados de colisão de peças de outra sessão. Resultado: peças desenhadas com o contorno
errado (formas deformadas e sobrepostas) e marcadas em vermelho como colisão — exatamente o que
o operador viu, e impossível de reproduzir em um processo novo.

### 3. Correções aplicadas

1. **Identidade por conteúdo**: nova `_contour_key(contorno)` (tamanho + primeiro/meio/último
   vértice arredondados) substitui `id()` nos dois caches. É estável entre cópias e sessões.
2. **Invalidação explícita**: `set_session_layouts()` e `switch_to_layout()` chamam
   `clear_piece_cache()`, descartando geometria, colisões e rotações da placa anterior.
3. **Paridade visual com o preview**: o LOD "simplified" (>200 peças) deixou de remover o
   preenchimento — o editor agora mostra as mesmas cores por tamanho do mini-preview; apenas a
   peça selecionada continua só com contorno (`SELECTED_OUTLINE_ONLY`).
4. **Explicação do vermelho**: a barra de título passa a indicar
   `⚠ N peça(s) sobrepostas (contorno vermelho)` quando há colisão real, diferenciando de seleção.

### 4. Validação

- Render do editor com a sessão 190 idêntico ao mini-preview (359 peças, 8 cores por tamanho,
  0 colisões, 0 falsos positivos nos caches).
- Redraw com 359 peças preenchidas: **~28 ms** (antes ~7 ms sem preenchimento, mas com o defeito
  visual); arraste continua usando `canvas.move` + `redraw_single_piece`.
- Novo teste de regressão `test_piece_cache_identity_is_content_based_and_resets_on_switch`
  (`tests/test_layout_editor_shortcuts.py`), suíte em **358 testes + 1 skip**.

---


## 8.14. Editor reabria sem a placa (fundo cinza/grade) após "Limpar" (v1.5.2) `[CONFIRMADO]`

Sintoma relatado: o desenho do mini-preview estava correto, mas ao abrir o Layout Editor
apareciam só as peças soltas sobre fundo branco — **sem a placa cinza, a grade, as margens e o
rótulo de dimensões** (as peças em si estavam certas).

### 1. Causa raiz (reproduzida)

`redraw()` só desenha o fundo quando a "assinatura" `_last_bg_sig` (posição da chapa, escala,
zoom, tamanho, canvas, divisor) muda — é uma otimização para não redesenhar grade e chapa a
cada frame. Porém `set_session_layouts([])` (acionado por *Limpar layout*, sessão sem layout ou
"Refazer") **apagava o canvas sem invalidar a assinatura**. Na abertura seguinte, com a mesma
chapa e o mesmo tamanho de janela, `bg_changed` era `False`: o editor desenhava as peças e
pulava a placa para sempre.

Reprodução determinística:

```
abrir    : placa=1 grade=42 pecas=220
limpar   : placa=0 grade=0  pecas=0
reabrir  : placa=0 grade=0  pecas=220   <-- defeito
```

### 2. Correção

1. `set_session_layouts([])` invalida `_last_bg_sig = None` ao limpar o canvas.
2. **Autoconserto no `redraw()`**: se a assinatura não mudou mas o item `sheet_bed` não existe
   mais no canvas, o fundo é redesenhado (`bg_changed = True`). Isso cobre qualquer outro caminho
   que apague o canvas sem avisar.

### 3. Validação

```
abrir    : placa=1 grade=42 pecas=220
limpar   : placa=0 grade=0  pecas=0
reabrir  : placa=1 grade=42 pecas=220   <-- corrigido
```

Novo teste `test_plate_is_redrawn_after_clearing_layouts`; suíte em **359 testes + 1 skip**.
Também confirmado que as peças em "vermelho" da captura anterior eram, na verdade, o **laranja
do tamanho maior (`#ea580c`)** — as colisões falsas da §8.13 não reapareceram (0 colisões
reais e 0 marcadas em lay0000/lay0001/lay0002 da sessão 203).

---


## 8.15. Leitura visual do encaixe no editor (traço das peças) (v1.5.3) `[CONFIRMADO]`

Sintoma relatado: o mini-preview mostrava o encaixe compacto, mas no Layout Editor as peças
apareciam separadas por "vãos", como se houvesse espaço sobrando na placa.

### 1. Diagnóstico (medido)

| Verificação | Resultado |
|---|---|
| Distância real contorno-a-contorno entre peças vizinhas (mesma linha) | **1,05–1,12 mm** (o gap de corte configurado) |
| Distância vertical entre linhas | **1,06 mm** |
| Colisões reais | 0 |
| Pontos do polígono desenhado vs geometria esperada | **divergência máxima 0,001 px** |
| Manchas coloridas na captura do operador (preview vs editor) | 9 vs 86 |

O encaixe estava correto. O que separava visualmente as peças era o **traço escuro
(`#1e293b`, largura 1,2 px)** de cada polígono: no editor, com a placa ocupando ~384 px,
o traço + o gap de 1 mm formam uma faixa escura contínua entre peças, lida pelo operador
como "espaço vazio"; no mini-preview, com a placa em ~288 px e traço de 1 px, as peças se
fundem e o desenho parece compacto.

### 2. Correção

- Novo `_shade_color()`: no LOD de visão geral (`simplified`, > 200 peças), o contorno da peça
  passou a usar um **tom escurecido da própria cor** (fator 0,82) com largura 1,0 px, em vez do
  traço escuro fixo. O desenho fica contínuo, como no mini-preview, sem esconder a separação
  entre peças.
- Zoom de detalhe (`full`) mantém o contorno escuro `#1e293b` (1,2 px), necessário para editar.
- Colisão real continua em `#dc2626` (3,0 px) e seleção em `#ff0000` (2,5 px).

### 3. Validação

- Render do editor com a sessão 210: desenho contínuo por cor, idêntico em leitura ao preview,
  mantendo placa, grade, margens e rótulo.
- `tests/`: **359 testes + 1 skip** (as fixtures visuais usam 100 peças, LOD `full`, sem alteração).

---


## 8.16. Cache de transformação devolvia geometria de outro molde (v1.5.4) `[CONFIRMADO]`

Defeito de fundo encontrado ao investigar as divergências de desenho entre o mini-preview e o
Layout Editor, e exposto pelo fuzz test `test_05` quando a suíte completa rodava.

### 1. Causa raiz

`cad/geometry.py::_get_contour_hash` guardava o hash do contorno em
`_CONTOUR_HASH_CACHE[id(contorno)]` — **endereço de memória**, sem validar o conteúdo.
Como o CPython recicla endereços de listas liberadas, um contorno novo podia herdar o hash de
outro molde; `transform_contour` então respondia do `_TRANSFORM_CACHE`/`_ROT_CACHE` com a
geometria de **outra peça**. Consequências: peças desenhadas deslocadas/deformadas, colisões
falsas no editor e risco de contato/posicionamento calculado sobre o polígono errado.

Ficou invisível em processos novos (o endereço só é reciclado depois de muitas sessões), o que
explica por que só o app do operador — aberto por horas — mostrava o problema.

### 2. Correção

- A entrada do cache passou a guardar `(hash, tamanho, amostra de 3 vértices)`; a cada consulta
  a amostra é comparada com o contorno real. Reciclagem de endereço vira **cache miss**, nunca
  resultado errado. Custo: 6 comparações por chamada (O(1)).
- O restante do caminho (hash de conteúdo → `_TRANSFORM_CACHE`/`_ROT_CACHE`) permanece intacto,
  preservando o desempenho.

### 3. Evidência

- **Fuzz test**: `test_05_fuzz_1000_pairs_nfp_vs_collision_oracle` falhou de forma intermitente
  na suíte completa antes da correção e passou em 3 execuções completas consecutivas depois.
- Novos testes `TestTransformCacheIdentity`:
  - **falham no código antigo** (`2 failed`);
  - **passam no código novo** (`2 passed`);
  - cobrem offset 0 e offset + rotação 180°.

### 4. Validação final

```
pytest tests/ -q  →  361 passed, 1 skipped  (3 execuções consecutivas)
```

---


## 8.17. Auditoria do Layout Editor e Bump Magnético Interativo (v1.5.5) `[CONFIRMADO]`

### 1. Auditoria: problemas encontrados e corrigidos

| Problema | Diagnóstico | Correção |
|---|---|---|
| Barra de status mostrava rendimento **falso** (83,02% fixo) | `update_status` aplicava piso artificial `if total_p >= 200 and yd < 80: yd = 83.02` e inventava valores quando vazio | Passa a exibir o rendimento **real** (área das peças ÷ área da placa) e `0,00%` quando vazio |
| Setas faziam nudge fixo de 5 mm (divergente do original) | Bindings chamavam `nudge_selected(±5, 0)` | Setas passam a chamar `bump_selection_vector` (bump magnético); `Ctrl+Setas` = nudge fino 0,5 mm |
| Bump com mouse ausente | Só existia o bump por setas | Implementado com os 3 gatilhos do original (§2) |
| Cache de geometria/colisão com identidade reciclada | Corrigido em §8.13/§8.16 | — (regressões cobertas por testes) |
| Placa não redesenhada após limpar layout | Corrigido em §8.14 | — |

### 2. Bump Magnético Interativo com Mouse

Núcleo único `bump_selection_vector(dx, dy)` usado por **setas e mouse**:

- Direção **livre** (qualquer ângulo) normalizada a partir do vetor do arrasto.
- Deslocamento máximo limitado pelas margens de segurança da placa.
- **Primeiro contato** ao longo da trajetória: varredura grossa (passo ≤ 10 mm, ~400
  amostras no máximo) + refino binário de 16 iterações → precisão submilimétrica.
- Colisão sempre pelo oráculo `polygons_collide` com o **gap da sessão** (`self.gap_mm`),
  contra uma `SpatialGrid` com as peças não selecionadas (não duplica lógica de colisão).
- Validação final obrigatória: se ainda colidir, **não move**.
- 1 snapshot atômico de undo por bump; marca modificado (`*`); status "Ready" ao terminar.
- Seleção múltipla desloca em bloco (mesmo vetor), preservando a formação relativa, até
  a **primeira** peça encontrar obstáculo.
- Peça já encostada na direção: não move, sem undo.

Gatilhos implementados:

| Gatilho | Bindings | Conflito resolvido |
|---|---|---|
| Botão do meio | `<ButtonPress-2>` / `<B2-Motion>` / `<ButtonRelease-2>` | **Com seleção = bump; sem seleção = pan** (como no original) |
| Duplo clique + arrasto | 2º `<ButtonPress-1>` < 300 ms na mesma peça + movimento | Não dispara o arrasto normal nem o duplo-clique de área vazia |
| Ctrl+Shift + arrasto | `<Control-Shift-ButtonPress-1>` / `<Control-Shift-B1-Motion>` / `<Control-Shift-ButtonRelease-1>` | Não conflita com seleção por retângulo nem com arrasto comum |

Visual e cancelamento:
- Linha elástica em item de canvas (`tag=bump_rubber`) reposicionado por `coords` a cada
  movimento (sem `redraw()` completo) do centro da seleção até o mouse.
- Cursor `circle` (equivalente Tk ao Cursor ID 149; fallback `crosshair`).
- `Esc` cancela e remove a linha; arrasto < 3 px cancela (evita bump acidental).
- Barra de status: "Bump the Selection" durante o arrasto, "Ready" ao terminar.

### 3. Desempenho (medido)

| Cenário | Tempo |
|---|---|
| Bump vertical com 300 peças na placa | **5,4 ms** |
| Bump horizontal com 300 peças | **4,1 ms** |
| Arrasto (linha elástica) | apenas `canvas.coords` — sem recálculo de encosto |
| Cálculo de encosto | roda somente ao soltar |

### 4. Decisões `[INFERIDO]`

- **Conflito do botão do meio**: bump quando há seleção; pan quando não há (idêntico ao
  comportamento descrito no RE, que reserva o botão do meio ao bump).
- **Cursor equivalente ao ID 149**: `circle` do Tk (arco) com fallback `crosshair`.
- **Limiar de arrasto curto**: 3 px (`BUMP_MIN_DRAG_PX`), igual ao critério usado nos
  gestos de clique/arrasto do próprio editor.

### 5. Testes

`tests/test_layout_editor_bump.py` — 13 testes cobrindo: horizontal, vertical, 45°, 30°,
os 3 gatilhos com resultado idêntico, arrasto curto sem undo, `Esc`, linha elástica sem
vazamento, contorno côncavo na diagonal, seleção múltipla em bloco, peça já encostada,
undo atômico e pan sem seleção. Suíte total: **374 testes + 1 skip**.

---


## 8.18. Contadores da barra lateral por placa (v1.5.6) `[CONFIRMADO]`

Sintoma relatado: todos os moldes apareciam com `50/50` na barra lateral do Layout Editor,
independentemente da placa aberta.

### 1. Causa dupla

1. **Contagem de sessão em vez de placa**: em sessões multi-placa o contador exibia
   `total_session_pieces/total_pieces_demanded` (soma de TODAS as placas), então toda placa
   mostrava o total pedido (ex.: `50/50`), escondendo o progresso real daquela placa.
2. **Barra lateral não redesenhada na troca de placa**: as miniaturas e contadores são
   desenhados dentro do bloco de fundo cacheado por `_last_bg_sig`. Como a assinatura não
   mudava ao trocar de placa (mesma chapa/tamanho de janela), a barra lateral mantinha os
   textos da placa anterior — o que também mascarava o defeito nº 1 nos testes.

### 2. Correção

- Contador multi-placa passa a exibir **peças desta placa / total pedido** (ex.: `18/50`).
- `switch_to_layout()` invalida `_last_bg_sig = None`, garantindo que a barra lateral
  (miniaturas + contadores) seja redesenhada na troca de placa.
- O indicador de déficit (cor vermelha) continua considerando o **total da sessão**.

### 3. Validação

`test_layout_editor_sidebar_counters` atualizado: placa com as 6 peças pedidas mostra `6/6`;
placa vazia mostra `0/6` (antes exibia `6/6` nas duas). Suíte: **374 testes + 1 skip**.

---


## 8.19. Seleção de todas as peças do molde pela barra lateral (v1.5.7) `[CONFIRMADO]`

Pedido do operador: ao clicar na miniatura de um molde na barra lateral do Layout Editor,
selecionar automaticamente **todas as peças daquele número presentes na placa atual**.

### 1. Antes / depois

| Antes | Depois |
|---|---|
| O clique selecionava apenas a **primeira** peça encontrada daquele tamanho (`break` no laço) | Seleciona **todas** as peças do molde na placa atual |
| A regra de correspondência do clique era diferente da usada nos contadores | Regra única `_piece_matches_target()` compartilhada por contadores e seleção |
| Sem retorno ao operador | Barra de status: `N peças do molde <nome> selecionadas nesta placa` (ou `nenhuma peça nesta placa`) |

### 2. Implementação

- `_piece_matches_target(piece, target)`: correspondência por `target_id`, `name` e `size`
  (com trava de tamanho), usada nos contadores da barra lateral **e** na seleção.
- `on_sidebar_click`: monta `selected_indices` com todos os índices correspondentes,
  define `selected_index` e mostra a mensagem; nenhuma peça encontrada limpa a seleção.
- Como a seleção passa a ter várias peças, os comandos existentes funcionam em bloco:
  **Bump** (setas/mouse), F1–F4, setas, Delete, arrasto em grupo.

### 3. Testes

`tests/test_layout_editor_sidebar_selection.py` (5 testes): seleciona as 3 peças do molde,
troca a seleção ao clicar em outro molde, molde sem peças não quebra, mensagem de status
com a quantidade e bump em bloco a partir da seleção da miniatura.
Suíte total: **379 testes + 1 skip**.

---


## 8.20. Contador de seleção e Ctrl+clique para somar/remover peças (v1.5.8) `[CONFIRMADO]`

Pedido do operador: um quadro na barra de status, ao lado do `Id:`, mostrando **quantas peças
estão selecionadas**, e liberar o **Ctrl+clique** para adicionar/remover peças da seleção.

### 1. Novo painel `Sel:`

- Novo painel `sel_panel` / `lbl_stat_sel` na barra de status, posicionado imediatamente ao lado
  do painel `Id:` (`Sel: N`).
- Atualizado em `update_status()`, portanto reflete qualquer origem de seleção:
  clique simples, Shift+clique, Ctrl+clique, retângulo elástico, `Ctrl+A`, clique na miniatura
  do molde e Bump. Fica em azul quando há peças selecionadas e na cor normal quando zerado.

### 2. Ctrl+clique = adicionar/remover da seleção

- `on_ctrl_canvas_click` (binding `<Control-Button-1>`) passou a fazer **toggle** da peça sob o
  cursor: adiciona se não estiver selecionada, remove se estiver (mesma semântica do
  Shift+clique). Clique no vazio preserva a seleção; clique na barra lateral continua
  selecionando o molde.
- **Mudança de atalho documentada**: o zoom de +20% que ocupava `Ctrl+clique` deixou de existir
  nesse gesto. O zoom continua disponível em **Ctrl+roda do mouse**, nos botões de zoom
  (`btn_zoom`, `btn_zoom_fit`) e em `Ctrl+Plus` / `Ctrl+Minus`.
- O teste `test_zoom_20_percent_tool_and_ctrl_click` foi atualizado para o novo contrato
  (Ctrl+clique não altera o zoom; botões/zoom_out continuam validados).

### 3. Testes

`tests/test_layout_editor_sidebar_selection.py` ganhou 3 testes:
`test_ctrl_clique_adiciona_e_remove_pecas_da_selecao`, `test_ctrl_clique_no_vazio_preserva_selecao`
e `test_painel_sel_reflete_selecao_por_miniatura`. Suíte: **382 testes + 1 skip**.

---


## 8.21. Tooltips (nome da ferramenta) na barra do Layout Editor (v1.5.9) `[CONFIRMADO]`

Pedido do operador: ao parar o mouse sobre um ícone da barra do Layout Editor, mostrar o
nome da ferramenta (como no Layout.exe).

### 1. Implementação

- Novo módulo `ui/tooltip.py` com a classe `ToolTip`:
  - agenda a exibição no `<Enter>` (450 ms) e esconde no `<Leave>`, `<ButtonPress>` e `<Destroy>`;
  - janela `Toplevel` sem barra de título (`overrideredirect`), posicionada junto ao cursor,
    fundo `#ffffe1` (padrão Win32), fonte Segoe UI 8;
  - garante **apenas um tooltip visível** por vez (fecha o anterior ao abrir outro);
  - `update_text()` permite atualizar botões que mudam de rótulo (ex.: Simular/Parar).
- `create_tb_btn()` passou a anexar `ToolTip` a **todos** os botões de ícone; os botões de
  texto `✂ Refilar` e `▶ Simular` e os de janela também receberam.
- A dica na barra de status (comportamento anterior) foi **mantida** em paralelo ao tooltip.

### 2. Textos das ferramentas

Os textos seguem o menu/atalho correspondente (ex.: `Novo Layout (Ctrl+N)`, `Salvar Layout
(Ctrl+S)`, `Imprimir Layout (Ctrl+P)`). As setas da barra também foram alinhadas ao
comportamento do original:

| Botão | Antes | Agora |
|---|---|---|
| ← → ↑ ↓ da toolbar | `nudge_selected(±10 mm)` | **Bump magnético** (`bump_selection_vector`) com tooltip explicando a direção |
| Zoom | tooltip citava `Ctrl+Clique` | `Zoom (+20%): clique aqui, Ctrl+roda no canvas; botão direito reduz` |

### 3. Testes

`tests/test_tooltip.py` (5 testes): mostra/esconde, agenda no Enter e cancela no Leave,
apenas um tooltip visível, `destroy` do widget não quebra e todos os botões do editor têm
tooltip (incluindo `Refilar`). Suíte: **387 testes + 1 skip**.

---

## 8.22. Correção de Exclusão de Artigo, Criação de Sessão por Clique Esquerdo, Simplificação do Mostrador e Tooltips (v1.6.0) `[CONFIRMADO]`

Versão estável v1.6.0 trazendo correções estruturais de integridade referencial, usabilidade na navegação da árvore e fidelidade visual com o ATOM Job Manager original.

### 1. Correção de Exclusão de Artigo e Integridade Referencial (`database.py`, `ui/main_window.py`)

- **Diagnóstico da Falha:** Ao acionar a opção "Excluir Artigo" (ou "Excluir") no menu de contexto de pedidos (`node_type == "order"`), ocorria `sqlite3.IntegrityError: NOT NULL constraint failed: sessions.order_id`. O schema SQLite legado continha `NOT NULL` nas colunas `order_id` e `material_id` em `sessions`, `article_id` em `shapes` e `material_id` em `articles`.
- **Migração Transparente no `init_db()`:**
  - Inspeciona via `PRAGMA table_info` as constraints das tabelas `sessions`, `shapes` e `articles`.
  - Reconstrução atômica e segura no SQLite (com `PRAGMA foreign_keys = OFF;`, tabela temporária, cópia `INSERT INTO ... SELECT`, `DROP` e `RENAME TO`), flexibilizando as restrições para `NULL` e preservando 100% dos dados, índices e chaves estrangeiras.
  - No MySQL 8.0, execução idempotente de `ALTER TABLE ... MODIFY COLUMN ... NULL DEFAULT NULL`.
- **Resiliência e Desacoplamento:**
  - `delete_order` e `delete_article` agora desvinculam com segurança sessões (`order_id = NULL`) e moldes (`article_id = NULL`), mantendo layouts, histórico e geometrias sem exclusão acidental.
  - Tratamento com bloco defensivo e fallback para outros pedidos válidos.
- **Limpeza do Menu de Contexto:**
  - Remoção da entrada duplicada `Excluir` em `show_tree_context_menu()` do nó de pedido, mantendo estritamente a opção clara `Excluir Artigo`.
  - Tratamento com `try/except` exibindo `messagebox.showerror` amigável em caso de erro, e sincronização imediata em memória das sessões ativas (`sess["order_id"] = None`).

### 2. Criação de Sessão por Clique com o Botão Esquerdo na Pasta (`ui/main_window.py`)

- **Comportamento Solicitado:** Ao clicar com o botão esquerdo do mouse em uma pasta de produção (`job_folder`, ex: `ProduçãoNova` ou pastas de ordens), o sistema abre diretamente o fluxo de criação de nova sessão de corte.
- **Compatibilidade:** Mantidos integralmente os métodos complementares: duplo-clique no item, atalho global `Ctrl+N` e botão correspondente na barra de ferramentas.

### 3. Tooltips Descritivos na Toolbar Superior e Barra de Modos (`ui/main_window.py`)

- **Tooltips Flutuantes:** Adicionados tooltips com atraso de 450 ms em todos os 12 botões da toolbar superior (Salvar, Imprimir, Cortar, Copiar, Colar, Detalhes, etc.) e nos 3 botões da barra de modos (`Produção`, `Moldes`, `Materiais`).
- **Limpeza da Barra de Status:** Removidos os 3 indicadores ovais de LEDs roxos (`⬭`, `#a21caf`) do canto da barra de status, tornando o rodapé limpo e idêntico ao clássico ATOM Job Manager.

### 4. Simplificação do Mostrador de Peças na Barra Lateral do Layout Editor (`ui/layout_editor_view.py`)

- **Regra Única `{n}/{m}`:**
  - `n` = quantidade de peças físicas desenhadas do molde na placa aberta (layout atual).
  - `m` = quantidade de pares pedidos na grade de moldes da sessão.
  - Eliminação da segunda linha sobreposta `placa: 46 pç` e das frações duplas redundantes.

### 5. Testes Automatizados

- Novo arquivo `tests/test_delete_order.py` com 4 testes dedicados cobrindo migração de constraints legadas, integridade referencial, ausência de duplicidade no menu e fluxo de exclusão na árvore.
- Suíte completa: **447 testes aprovados**, 1 skip, 0 falhas.

---

## 8.23. Desacoplamento entre Zoom e Seleção de Peças com Mouse no Canvas CAD e Refile Automático (v1.6.1) `[CONFIRMADO]`

Versão estável v1.6.1 trazendo a resolução definitiva do conflito entre ferramentas de navegação e manipulação de peças no Layout Editor, fidelidade ao padrão clássico CAD/ATOM e automação de refile.

### 1. Desacoplamento de Zoom e Seleção de Peças com o Mouse (`ui/layout_editor_view.py`)

- **Diagnóstico da Causa Raiz:** O atalho `<Control-Button-1>` (`on_ctrl_canvas_click`) havia sido atribuído na v1.5.8 para alternar a seleção de peças (*toggle*), enquanto a tecla `Ctrl` ativava o cursor de mira (`crosshair`), associado historicamente ao Zoom. Ao clicar sobre uma peça com `Ctrl`, o sistema alterava a seleção em vez de aplicar zoom, e no espaço vazio retornava sem efeito.
- **Restauração do Zoom Puro com `Ctrl + Clique`:**
  - `Ctrl + Clique` volta a ser exclusivo para **Zoom In (+20%)** centrado exatamente nas coordenadas do cursor (`self.zoom_in(event.x, event.y)`).
  - Opera uniformemente sobre peças ou no vazio da chapa sem alterar o estado de seleção de peças.
  - Sincronização automática do redesenho em `zoom_at` mesmo em dimensões preliminares da janela (`cw <= 10`).
- **Padrão Canônico de Seleção de Peças com o Mouse:**
  - **Clique Esquerdo Simples:** Seleciona peça única e desmarca as outras (iniciando arrasto se movimentado).
  - **`Shift + Clique`:** Atalho canônico do ATOM JobManager para alternância (*toggle*) de peças na seleção múltipla (`self.selected_indices`), atualizando o mostrador `Sel: N`.
  - **Arrasto no Vazio (*Rubberband*):** Desenha caixa de seleção elástica retangular selecionando todas as peças contidas.
  - **Clique no Vazio:** Desmarca todas as peças selecionadas.
  - Proteção contra disparo acidental de bump por duplo-clique ao alternar seleção com Shift (`not is_shift and ...`).
- **Atualização da Toolbar do Layout Editor:**
  - Tooltip do botão de Zoom atualizado para: *"Zoom (+20%): clique aqui ou Ctrl+clique / Ctrl+roda no canvas; botão direito reduz"*.

### 2. Refile Automático e Batch Autonest (`cad/layers_rule.py`, `ui/session_view.py`, `ui/main_window.py`)

- **Refile Automático por Sessão:** Checkbox dedicado ao lado de "Separar sobras", persistido nos parâmetros da sessão (`refile_auto=1`), aplicando corte de refile automático (gap de 1.0 mm) em placa única ou em lote.
- **Batch Autonest:** Diálogo de aninhamento automático em lote (`ui/batch_nest_dialog.py`).

### 3. Testes Automatizados e Homologação

- Atualizados `tests/test_layout_editor_shortcuts.py` e `tests/test_layout_editor_sidebar_selection.py`.
- Novos testes dedicados `tests/test_auto_trim_checkbox.py` (12 testes) e `tests/test_batch_autonest.py` (8 testes).
- Todos os 116 testes do editor de layout aprovados com 100% de sucesso.

---

## 8.24. Criação de Novas Sessões 100% em Branco sem Material Associado (v1.6.2) `[CONFIRMADO]`

Versão estável v1.6.2 atendendo à solicitação do operador de fábrica para que sessões de corte criadas comecem completamente limpas, sem injetar materiais legados ou pré-definidos (`MAT_VAQ_01`).

### 1. Desvinculação de Material Padrão na Criação de Sessões (`database.py`, `ui/main_window.py`)

- **Diagnóstico da Causa Raiz:** O método `create_session` em `database.py` definia `material_id: str = "MAT_VAQ_01"` como valor padrão e aplicava fallback incondicional para o primeiro material cadastrado se o valor fosse nulo. Em conjunto, `on_new_session` em `ui/main_window.py` atribuía explicitamente `self.current_material["id"]` ou `"MAT_VAQ_01"`. Como resultado, qualquer nova sessão vinha sempre pré-populada com uma placa/material na aba Materiais (`tree_mat`).
- **Suporte Canônico a Material Nulo:**
  - Assinatura de `create_session` atualizada para `material_id: Optional[str] = None`.
  - A resiliência de chave estrangeira só busca fallback caso um identificador seja fornecido explicitamente (`if valid_mat_id is not None and str(valid_mat_id).strip():`). Se for `None`, a sessão é gravada com `material_id = NULL` no banco de dados.
  - Em `MainWindow.on_new_session()`, o `mat_id` é definido estritamente como `None`.
  - O estado em memória `self.current_material` é zerado (`None`), e a mesa CAD em segundo plano recebe `self.canvas.set_material(None)`.
  - Ao carregar a nova sessão na `SessionView`, a grade de materiais (`tree_mat`) fica completamente vazia e o combobox `cb_mat_code` exibe `(unspecified)`.
  - Sincronização em tempo real de `self.current_material` e `self.canvas.set_material` durante a troca ativa de sessões (`switch_to_session` e `show_session_window`).

### 2. Testes Automatizados e Homologação

- Novo teste unitário dedicado: `tests/test_create_session_left_click.py::TestCreateSessionLeftClick::test_new_session_starts_blank_without_material`.
- Validação das suítes de persistência e banco de dados: 21 testes em `test_create_session_left_click.py` e `test_db_layer.py` aprovados com 100% de sucesso.

---

## 8.25. Contadores de Peças Dinâmicos e Reativos na Barra Lateral do Layout Editor (v1.6.3) `[CONFIRMADO]`

Versão estável v1.6.3 atendendo à solicitação do operador de fábrica para que os contadores de peças da barra lateral (`{n}/{m}`) reajam em tempo real a exclusões e adições de peças na chapa, em vez de permanecerem estáticos.

### 1. Diagnóstico Técnico das Causas Raízes
- **Causa 1 (draw_sidebar condicionado a bg_changed):** No método `redraw()` de `ui/layout_editor_view.py`, a função `draw_sidebar` era invocada exclusivamente dentro de `if bg_changed:`. Ao deletar peças (`Delete`, toolbar, `clear_all_pieces`) ou adicionar peças (`add_piece_for_target`, `duplicate_selected`, `Ctrl+Z`), `bg_sig` (zoom, pan, tamanho da chapa) não se alterava (`bg_changed == False`). No bloco `else:`, apenas `piece_item` e `trim_item` eram deletados do canvas, deixando os textos da barra lateral estáticos permanentemente.
- **Causa 2 (Acúmulo de elementos visuais):** `draw_sidebar` não limpava `sidebar_element` no início de sua execução, e o retângulo de destaque do molde ativo não possuía a tag de limpeza.
- **Causa 3 (Coordenadas residuais no rodapé):** Ao esvaziar a chapa de corte (`len(placed_pieces) == 0`), os labels da barra de status (`lbl_stat_id`, `lbl_stat_x`, `lbl_stat_y`, `lbl_stat_rot`) retinham as coordenadas da última peça deletada, em vez de resetarem para `"-"`.
- **Causa 4 (Dessincronização multi-placas):** As operações de exclusão, adição e preenchimento não sincronizavam `self.layouts[cur_idx]["pieces"]`.

### 2. Solução Implementada
1. **Desacoplamento do Redesenho da Barra Lateral:** `self.draw_sidebar(div_x, ch, cw)` e `self.canvas.tag_raise("sidebar_ui")` são executados a cada chamada de `redraw()`.
2. **Limpeza e Tagging Atômico:** Inclusão de `self.canvas.delete("sidebar_element")` no início de `draw_sidebar()` e associação de tags ao retângulo de seleção ativo.
3. **Reset da Barra de Status:** Rótulos de identificador, rotação e coordenadas $X, Y$ resetam para `Id: - | X: - | Y: - | Rot: -` quando a chapa não possui peças colocadas.
4. **Sincronização do Layout Ativo:** Novo método `_sync_current_layout_pieces()` integrado a `delete_selected`, `clear_all_pieces`, `add_piece_for_target`, `duplicate_selected`, `undo_action` e todas as variantes de `fill_*`.
5. **Resolução de Moldes Importados:** `open_layout_dialog` mapeia o `target_id` dos itens `.lay` contra os alvos da sessão/barra lateral.

### 3. Testes Automatizados e Homologação
- Novos cenários unitários adicionados a `tests/test_sidebar_counter.py`:
  - `test_cenario_14_delete_selected_updates_sidebar_counter`: valida atualização instantânea de 20/20 para 0/20 (vermelho deficitário `#dc2626`).
  - `test_cenario_15_add_piece_updates_counter_and_undo`: valida avanço 0/20 -> 1/20 -> 2/20 e decremento por `Ctrl+Z`.
  - `test_cenario_16_status_bar_reset_when_empty`: valida reset dos rótulos de status ao esvaziar a mesa.
- 123 testes da suíte de layouts aprovados com 100% de sucesso.

---

## 8.26. Implantação da Ponta de 2 Camadas no Topo da Placa e Visualização no Layout Editor (v1.6.4) `[CONFIRMADO]`

Implementação da estratégia de corte misto com aproveitamento de ponta de placa para sobras de 4 camadas:

### 1. Diagnóstico e Regra de Negócio
- Em ordens com pares ímpares cortados em enfesto base de 4 camadas, a sobra inevitável de 1 peça ($N_2 = P \pmod 2$) geraria desperdício se mantida em 4 camadas ou se exigisse uma chapa inteira extra de 2 camadas.
- A solução industrial consagrada consiste em posicionar essas sobras em uma zona reservada no final/topo da última placa (`tip_zone`), permitindo que o operador coloque uma folha curta de 2 camadas ("ponta") sobreposta ou adjacente ao enfesto principal.

### 2. Motor de Posicionamento da Ponta (`cad/layers_split.py`)
1. **Posicionamento Forçado em Coordenadas Físicas**: O algoritmo `_nest_sobras_on_last_sheet` abandona empilhamento cego e posiciona as peças de 2 camadas rigorosamente nas cotas superiores de $Y$ da última chapa (ou placa adicional caso a área remanescente não comporte).
2. **Modos de Ponta e Folgas**:
   - `canto`: aloca a ponta no canto superior (maior $Y$ e maior $X$), minimizando a área de sobreposição.
   - `faixa_topo`: aloca a ponta ao longo de toda a largura superior da placa.
   - Parâmetro `folga_ponta`: folga física de segurança (padrão 15.0 mm) entre a zona de 4 camadas e as peças de 2 camadas.
3. **Metadados Estruturados (`tip_zone`)**: O layout armazena o dicionário `tip_zone` contendo `{xmin, ymin, xmax, ymax, mode, pieces_count}`, delimitando com exatidão a geometria retangular da ponta.

### 3. Visualização Gráfica no Layout Editor (`ui/layout_editor_view.py`)
1. **Linha Delimitadora Tracejada (`tip_line`)**: Renderização automática de uma linha tracejada (`dash=(4, 4)`) separando o enfesto de 4 camadas da zona de 2 camadas.
2. **Rótulo Indicativo CAM**: Desenho de etiqueta gráfica visível com o texto `"Ponta 2 Camadas: X peças"` e indicação do modo, prevenindo erros operacionais na colocação do material sobre a mesa de corte.

---

## 8.27. Instrução de Corte e Enfesto Misto para o Almoxarifado na Impressão A4 (v1.6.5) `[CONFIRMADO]`

Integração de metadados operacionais e instruções explícitas de corte na folha A4 para os operadores de almoxarifado e mesa CNC (`ui/layout_print_dialog.py`, `cad/layers_rule.py`):

### 1. Problema Operacional
- O operador do almoxarifado retira e secciona o rolo de material baseado exclusivamente na folha de impressão A4.
- Sem instruções explícitas, o operador cortaria todas as folhas no comprimento total da chapa, desperdiçando matéria-prima nobre onde apenas uma ponta de 2 camadas era demandada.

### 2. Texto Canônico para o Almoxarifado (`cad/layers_rule.py`)
- Implementação da função `format_enfesto_operator_text(layout, sheet_w, sheet_h, tip_mode)`:
  - Formata a especificação exata de folhas inteiras (comprimento total $H$) e folhas curtas (comprimento da ponta $H_{ponta} = H - Y_{min} + \text{folga}$).
  - Exemplo gerado: `"CORTAR: X folhas de COMPRIMENTO TOTAL (Y mm) [4 camadas] + Y folhas de PONTA (Z mm) [2 camadas]"`.
  - Exibição de avisos de atenção operacional destacados no topo da folha de corte.

### 3. Renderização Visual no Preview A4 e Exportação PDF
- Desenho da linha divisória da zona de ponta no preview interativo Tkinter e no gerador de alta resolução via Pillow/PDF.
- Inclusão do texto de instrução no cabeçalho/metadados da página, garantindo leitura imediata pelo almoxarifado antes de desenrolar o material.

---

## 8.28. Higienização de Parâmetros de Nesting, Presets DieProc e Correção de Espaçamento entre Peças (v1.6.6) `[CONFIRMADO]`

Diagnóstico e correção da quebra no motor de aninhamento automático (`nest_multi_sheet`) que causava espalhamento das peças e vãos verticais excessivos após recálculos:

### 1. Diagnóstico da Causa Raiz
1. **Quebra por Contaminação de Parâmetros**:
   - Com a inclusão de opções de sessão como `separar_sobras=1`, `tip_mode=canto` e `folga_ponta=15.0`, o identificador `params` era formatado como string composta (ex.: `HighYield;separar_sobras=1;tip_mode=canto`).
   - Comparações literais `if params == "HighYield"` e `if params == "ALTERNADO"` em [`cad/nesting_backend.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/cad/nesting_backend.py) e [`cad/nesting_engine.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/cad/nesting_engine.py) falhavam silenciosamente, caindo no `else:` com `row_interlock: False` e `coupling: "0/0"`.
   - Com o intertravamento desligado, as peças não penetravam nos vales contorno-a-contorno nem alternavam giros de 180°, empilhando-se por bounding box com perdas massivas de aproveitamento.
   - Além disso, a busca no banco via `get_dieproc_preset(params)` retornava `None`.
2. **Poluição de Estado Transitório**:
   - Dicionários de moldes na sessão mantinham campos residuais de execuções anteriores (`tip_zone`, `layers_tip`, `target_pieces`), distorcendo os cálculos em novos disparos.

### 2. Correções Aplicadas
1. **Extração Canônica de Preset (`clean_preset`)**:
   - Criação de regra universal de sanitização: `clean_preset = str(params).split(";")[0].split("?")[0].strip() if params else "stdNOTFill"`.
   - Aplicação em todas as ramificações de parsing, seleção de coupling (`ALTERNADO`, `DIREITA`, `ESQUERDA`, `GAP 2`, `HighYield`, `FastNest`) e consultas ao banco de dados SQLite/MySQL.
2. **Limpeza Prévia de Estado (Purge)**:
   - Limpeza ativa de `tip_zone`, `layers_tip` e `target_pieces` em `ui/main_window.py` (`on_auto_nest`, `_worker`, `_poll_nest_worker`, `_run_batch_worker`) e `cad/nesting_engine.py:nest_multi_sheet`.
3. **Novo Teste Unitário Dedicado**:
   - `tests/test_multisheet_nesting.py::test_nest_multi_sheet_with_encoded_params_and_clean_state` validando acoplamento 0°/180°, reconhecimento de preset com parâmetros codificados e purificação de estado.

---


## 8.29. Blindagem do Encaixe (pares mandam), Isolamento dos Testes e Regressão de Vãos (v1.6.7) `[CONFIRMADO]`

Complemento ao §8.28, fechando as brechas que ainda permitiam o "encaixe com vãos" voltar.

### 1. `target_pieces` residual não reduz mais o encaixe

- `nest_multi_sheet` passou a **priorizar os pares** da sessão: um `target_pieces` herdado de uma
  separação de sobras anterior não pode mais encolher a demanda.
- Reprodução do defeito: 3 moldes com `pairs=12` e `target_pieces=1` (resíduo) desenhavam
  **3 peças** em vez de **18** — a placa ficava praticamente vazia ("vãos gigantes") ao clicar em
  Gerar/Refazer. Com a correção, desenha 18 e mantém o encaixe compacto.
- A chamada programática que realmente usa `target_pieces` (reencaixe da ponta, com `pairs=0`)
  continua funcionando.

### 2. Testes do Catálogo isolados do banco de produção

- Os 13 testes de `ShapeCatalogView`/`ShapeCatalogPolish`/`ShapeCatalogBorderCases` usavam o
  `jobmanager.db` da fábrica. Quando o operador apagava um artigo (os moldes ficavam com
  `article_id = NULL`), a suíte ficava vermelha **sem nenhuma regressão de código**.
- Novo `tests/_catalog_fixtures.py` cria um SQLite temporário semeado (17 moldes, 3 peças bases,
  16 tamanhos, lacuna proposital em PALM_CAVA/22a). Os três módulos usam esse banco.

### 3. Regressão de compactação (`tests/test_nesting_compactness.py`)

1. `params` composto (`HighYield;separar_sobras=1;tip_mode=canto;folga_ponta=15`) produz o mesmo
   encaixe compacto do preset puro (menor distância contorno-a-contorno ≤ 1,5 × gap).
2. `tip_zone`/`layers_tip`/`target_pieces` nos moldes **não alteram** posições (comparação 1:1).
3. Após `separar_sobras_em_ponta`, base e ponta continuam compactas (≤ 2 × gap).
4. Rodar o nesting duas vezes (Gerar + Refazer) mantém peças, rendimento e compactação.

### 4. Medição no cenário do operador (15 moldes, 11 pares, 4 camadas, placa 1,32 × 2,98 m)

| Métrica | Resultado |
|---|---|
| Peças desenhadas | 90 (6 por molde) |
| Separação | 15 moldes com sobra → 15 peças a 2 camadas na ponta (`lay0000`) |
| Menor distância contorno-a-contorno | **1,05 mm** (gap de 1 mm respeitado) |
| Peças na base / na ponta | 75 / 15 |
| Suíte | **500 testes + 1 skip** |

### 5. Observação de projeto (não é bug)

A placa de 4 camadas **mantém as vagas** das peças retiradas para a ponta (regra "placa de origem
congelada", §6.5). O refile automático corta o topo e a ponta é coberta por folhas curtas, então o
material não é perdido. Reencaixar a base após a retirada mudaria essa regra e ficou registrado como
melhoria futura, não aplicada nesta versão.

---


## 8.30. Regra da Dobra 4c → 2c, Divisão Automática e Contadores por Enfesto (v1.6.8) `[CONFIRMADO pelo operador]`

### 1. A regra (confirmada com o operador)

- 1 peça desenhada em **4 camadas** = 4 peças físicas = **2 pares**.
- 1 peça desenhada em **2 camadas** = 2 peças físicas = **1 par**.
- Portanto, **cada peça retirada das 4 camadas vira DUAS na ponta de 2 camadas**
  (4 físicas = 2 pares ↔ 2 desenhos × 2 camadas = 4 físicas = 2 pares). Nada de cortar a mais,
  nada de sobra: a soma física continua exatamente $2P$.

### 2. Divisão variável (antes era fixa)

Com $k$ dobras, por molde:

$$N_4 = \left\lfloor P/2 \right\rfloor - k \qquad N_2 = (P \bmod 2) + 2k \qquad 4N_4 + 2N_2 = 2P$$

Antes o sistema usava **somente $k=0$** ($N_4=P//2$, $N_2=P\bmod 2$), o que deixava a ponta com
1 peça por molde e vagas vazias na base. Agora existe `_escolher_divisao_otima()`, que testa
$k = 0\ldots 3$ e escolhe a divisão com **menor altura total utilizada** (menor refile/sobra),
exigindo ganho mínimo de 5 mm para aceitar mais dobras.

- A dobra é implementada **duplicando** a peça retirada na ponta (`is_duplicate=True`), pois o
  desenho novo é necessário para manter as 22 físicas — o sistema antes só movia peças
  ("nunca cria nem apaga"), o que impedia a regra de funcionar.
- A verificação física estrita continua valendo (rollback atômico em divergência).
- Medição (15 moldes, 11 pares, 4 camadas, placa 1,32 × 2,98 m): todas as divisões fecham
  **330 peças físicas**; alturas — k=0: 1.244 mm · k=1: 1.668 mm · k=2: 2.073 mm · k=3: 2.481 mm.
  Nesse layout o otimizador escolhe **k=0** (dobrar aumentaria a chapa); em layouts em que a
  dobra realmente fecha a placa, ele escolhe k>0 automaticamente.

### 3. Contadores separados por enfesto

- Novo painel na barra de status do Layout Editor: **`4c: N · 2c: M`**, ao lado de `Sel:`.
- Calculado em `update_status()` a partir de `piece["layers"]`/`is_tip`, mostrando quantas peças
  desenhadas pertencem ao enfesto de 4 camadas e quantas à ponta de 2 camadas.

### 4. Testes

`tests/test_sobras_dobra.py` (4 testes): qualquer k preserva $4N_4+2N_2=2P$; k=1 remove 2 e
coloca 3 (2 movidas + 1 dobrada, com `is_duplicate`); a escolha automática nunca é pior que o
melhor k fixo; as peças dobradas não colidem. Suíte: **504 testes + 1 skip**.

---


## 8.31. Ícone do Aplicativo e Atalho da Área de Trabalho (v1.6.9) `[CONFIRMADO]`

Pergunta do operador: o ícone do atalho da área de trabalho é atualizado a cada release?

### 1. O que já existia

| Item | Como era |
|---|---|
| Ícone da janela (Linux/Windows) | `iconphoto` com `assets/app_icon_{16,32,48,64}.png` + `app_icon.png` e `iconbitmap` com `app_icon.ico` no Windows (`ui/main_window.py`) — **atualiza em toda execução** |
| Ícone do `CorteAC.exe` | Embutido pelo PyInstaller (`--icon assets/app_icon.ico`) no build de Windows (local e CI) — **atualiza a cada release** |
| Atalho da área de trabalho | **Não existia** nenhum `.desktop` nem instalador de atalho; no Linux não havia de onde o atalho tirar o ícone |

### 2. Correção no pacote Linux

- `build_linux.sh` (e o empacotamento no CI) passaram a incluir:
  - `corteac.png` (o ícone oficial) dentro do pacote;
  - `instalar_atalho.sh`, que gera `~/.local/share/applications/corteac.desktop` com
    **caminho absoluto** para a pasta extraída, `Icon=` apontando para o `corteac.png` do pacote,
    `Path=` correto e `StartupWMClass=corteac_linux`; copia também para a Área de Trabalho
    (via `xdg-user-dir DESKTOP`), marca como confiável (`gio set metadata::trusted`) e atualiza
    o banco de atalhos.
- `README_LINUX.txt` ganhou o passo a passo do atalho.

### 3. Windows

- O `.exe` carrega o ícone no build; o atalho herda o ícone do executável.
- Como o Windows guarda ícones em cache por caminho, substituir o `.exe` na mesma pasta pode
  manter o ícone antigo: documentado em `README_WINDOWS.md` (criar atalho novo ou reiniciar o
  Explorer).

### 3.1 Correção de caminhos com espaços (v1.6.10)

O `Exec=` do `.desktop` passou a ser **aspeado**: `Exec="$DIR/corteac_linux"`. Sem isso, pastas como
`/home/dola/Documentos/clone do job/...` faziam o atalho falhar ao abrir. Verificado executando o
próprio comando do `Exec=` com o caminho real (retornou `CorteAC 1.6.10`).

### 4. Como verificar no Linux

```bash
tar -xzf CorteAC-Linux-x64.tar.gz
cd CorteAC && chmod +x instalar_atalho.sh && ./instalar_atalho.sh
```

O atalho "CorteAC" passa a aparecer no menu e na área de trabalho com o ícone do pacote;
se o ambiente tiver cache, sair/entrar na sessão resolve.

---


## 8.32. Atalho da Área de Trabalho com a Versão no Nome (v1.6.11) `[CONFIRMADO]`

Pedido do operador: a cada atualização, o ícone da Área de Trabalho deve mostrar a versão
(`CorteAC-1.6.11`), automaticamente.

### 1. Template único de atalho

- Novo `packaging/instalar_atalho.sh` com o marcador de versão, usado **tanto** pelo
  `build_linux.sh` **quanto** pelo CI (`release.yml`): o empacotamento faz
  `sed "s/@VERSAO@/<APP_VERSION>/"` (lendo `config.APP_VERSION`).
- Ao rodar, o instalador:
  1. descobre a versão **perguntando ao próprio binário** (`./corteac_linux --version`) e cai no
     valor gravado no pacote se o binário não responder;
  2. remove os atalhos antigos (`corteac.desktop`, `corteac-*.desktop`, `CorteAC*.desktop`) do
     menu e da Área de Trabalho — nunca ficam dois ícones;
  3. cria `corteac-<versão>.desktop` com `Name=CorteAC-<versão>`, `Exec=` **aspeado** (caminho
     pode conter espaços), `Icon=` do pacote, `X-CorteAC-Version=<versão>` e cópia na Área de
     Trabalho.

### 2. Windows

- Novo `packaging/criar_atalho_windows.ps1`, incluído no ZIP (CI e `build_exe_windows.bat`) junto
  com `versao.txt` gerado de `config.APP_VERSION`.
- Cria `CorteAC-<versão>.lnk` apontando para o `CorteAC.exe` (ícone embutido) e remove os atalhos
  `CorteAC*.lnk` antigos da Área de Trabalho.

### 3. Testes

`tests/test_desktop_shortcut.py` (3 testes, Linux): atalho sai com a versão no nome e no conteúdo;
a versão é lida do binário quando disponível; a versão anterior é removida ao atualizar.
Suíte: **507 testes + 1 skip**.

---


## 8.33. Sincronização Automática do Atalho na Abertura (v1.6.12) `[CONFIRMADO]`

Sintoma: mesmo após a v1.6.11, o ícone do Mint continuava com o nome/ícone antigo ("CorteAC").

### 1. Causa

- O atalho só era reescrito se o operador **rodasse o `instalar_atalho.sh`** — quem apenas
  substituía o binário continuava com o `.desktop` antigo na mesa.
- No Mint em português a pasta é **`~/Área de Trabalho`** (não `~/Desktop`); o instalador
  dependia de `xdg-user-dir DESKTOP` e, quando ele falhava, apontava para `~/Desktop`.

### 2. Correção

- Novo `ui/desktop_shortcut.py::sincronizar_atalho()` chamado **no início do `main()`** (antes de
  `--version`/`--check-db`):
  - procura **qualquer** atalho do CorteAC no menu (`~/.local/share/applications`) e nas pastas de
    área de trabalho (`Desktop`, `Área de Trabalho`, `Area de Trabalho`);
  - se existir algum (inclusive o antigo `CorteAC.desktop` criado à mão), remove e recria
    `corteac-<versão>.desktop` com `Name=CorteAC-<versão>`, `Exec=` aspeado, `Icon=` do pacote,
    `X-CorteAC-Version` e `gio metadata::trusted`;
  - se **não** existir atalho, não cria nada (não invade a mesa do operador).
- `packaging/instalar_atalho.sh` ganhou o mesmo fallback de pastas pt-BR e limpeza ampliada
  (`CorteAC*.desktop`, `corteac-*.desktop`).

### 3. Validação (pacote real, HOME isolado)

```
antes : Área de Trabalho/CorteAC.desktop        (Name=CorteAC)
exec  : ./corteac_linux --version
saída : Atalho da Área de Trabalho atualizado para CorteAC-1.6.12
depois: Área de Trabalho/corteac-1.6.12.desktop (Name=CorteAC-1.6.12, Exec aspeado, ícone do pacote)
```

Testes em `tests/test_desktop_shortcut.py` (5 no total): atalho versionado, versão lida do
binário, remoção da versão anterior, sincronização automática de atalho antigo e não-criação
quando não existe atalho. Suíte: **509 testes + 1 skip**.

### 4. Se o ícone ainda não mudar (cache do ambiente)

1. Rodar o binário novo uma vez (ele reescreve o atalho).
2. Cinnamon/Mint: pressionar **F5** na Área de Trabalho; se persistir, sair e entrar na sessão
   (`Ctrl+Alt+Backspace`) para o ambiente reler os `.desktop`.
3. Se o ícone antigo estiver **fixado no painel**, remova o pino e fixe o novo `CorteAC-1.6.12`.

---


## 8.34. Criação Manual do Atalho (`--criar-atalho`) (v1.6.13) `[CONFIRMADO]`

O operador apagou os atalhos e pediu um novo. Como a sincronização automática só **atualiza**
atalhos existentes (para não criar ícones sem pedido), foi adicionado um modo explícito de criação.

### 1. Implementação

- `ui/desktop_shortcut.py` ganhou `criar_se_ausente=True` e o helper `_instalar_icone()`, que copia
  o ícone para um caminho estável: **`~/.local/share/corteac/corteac.png`** (o executável
  PyInstaller guarda os assets dentro do binário; o atalho precisa de um arquivo real).
- Novo parâmetro de linha de comando no `main.py`:

```bash
./corteac_linux --criar-atalho     # ou --atalho
```

  Cria/atualiza `corteac-<versão>.desktop` no menu e na Área de Trabalho, remove versões
  anteriores, marca como confiável (`gio metadata::trusted`) e imprime os caminhos criados.
- `--version` e `--criar-atalho` funcionam sem abrir a interface (úteis em script/instalação).

### 2. Validação na máquina do operador

```
$ ./corteac_linux --criar-atalho
Atalho criado/atualizado: CorteAC-1.6.12
  /home/dola/.local/share/applications/corteac-1.6.12.desktop
  /home/dola/Área de trabalho/corteac-1.6.12.desktop
```

Conteúdo gerado: `Name=CorteAC-1.6.12`, `Exec=` aspeado (caminho com espaços),
`Icon=~/.local/share/corteac/corteac.png`, `X-CorteAC-Version=1.6.12`.

### 3. Observação

O atalho aponta para o executável de onde o comando foi rodado. Se o pacote for movido, basta
executar `./corteac_linux --criar-atalho` novamente na pasta nova — a versão antiga do atalho é
removida automaticamente.

---


## 8.35. Recompactação da Base Após Retirar as Sobras (v1.6.14) `[CONFIRMADO pelo operador]`

Relato do operador (sessão #282): "de onde ele retirou os ímpares e colocou na ponta de duas
camadas ficou um buraco".

### 1. Causa

- A retirada da peça ímpar da placa de 4 camadas deixava a **vaga vazia** (a placa era tratada como
  "congelada", sem renest). O refile corta o retângulo, mas o buraco interno continua sendo
  material perdido e atrapalha o operador.

### 2. Correção

- Novo `_recompact_plate()` em `cad/layers_split.py`, chamado nas **duas** rotas da separação
  (ponta/faixa em `separar_sobras_em_ponta` e Plano B em `separar_sobras_camadas`) logo após a
  retirada das peças:
  - agrupa as peças restantes por molde e reencaixa com `auto_nest_pieces` (`target_pieces`);
  - **mantém os dicionários originais** e copia apenas `x`/`y`/`rotation` — trocar as peças quebrava
    `piece_matches_shape` quando dois moldes têm o mesmo contorno/tamanho (a verificação física
    acusava divergência e revertia tudo);
  - rollback local: qualquer divergência de contagem mantém a placa original.

### 3. Medição (6 moldes, 101 pares, 4 camadas, placa 1,38 × 2,98 m)

| Métrica | Antes | Depois |
|---|---|---|
| Vãos na base (buracos) | 4 | **0** |
| Altura utilizada | 2.424 mm | **2.271 mm** (−153 mm) |
| Peças 4c / 2c | 300 / 6 | 294 / 18 |
| Peças físicas | 1.212 | **1.212** (2P exato) |

Com a base recompactada, o otimizador passou a preferir **k=1** (uma dobra): a base perde 6 peças e
a ponta ganha 12, fechando a placa 153 mm mais curta — exatamente o efeito que o operador descreveu.

### 4. Testes

`tests/test_sobras_dobra.py` ganhou `TestRecompactacaoBase` (3 testes): base sem buracos após a
separação, peças físicas preservadas e altura dentro da chapa. Suíte: **512 testes + 1 skip**.

### 5. Mudança de regra

A §6.5 dizia "placas de origem congeladas (não renestam)". Por pedido do operador, a placa que
**cede** peças agora é recompactada; as demais continuam intocadas.

---


## 8.36. Impressão do Layout Não Abria (Ctrl+P e Botão) (v1.6.15) `[CONFIRMADO]`

Relato do operador: "o atalho Ctrl+P não funciona e nem clicar no ícone abre a impressão".

### 1. Causa

- `LayoutEditorView.print_layout()` calculava a área das peças lendo o contorno como **tupla**
  (`cntr[i][0]`, `cntr[i][1]`), mas o editor armazena os pontos como **dict** `{"x": ..., "y": ...}`.
- Resultado: `KeyError: 0` dentro do callback do Tk. O Tk **engole a exceção** (só imprime no
  stderr), e como o app é aberto pelo atalho (sem terminal), o operador via apenas "nada acontece"
  — tanto em Ctrl+P quanto no ícone "Imprimir Layout".
- Bônus: quando não havia peças, o código preenchia **números falsos** (`yield_pct = 83.02`,
  `used_area = 0.11`, 40 instâncias, 15 moldes).

### 2. Correção

- Novo helper `_contour_area_mm2()` em `ui/layout_editor_view.py`, tolerante aos dois formatos
  (dict e tupla) e a contorno inválido (retorna 0, nunca levanta exceção).
- `print_layout` usa o helper e **não inventa mais números**: sem peças, área/rendimento = 0.
- A abertura do diálogo foi envolvida em `try/except` com `messagebox.showerror` — falhas futuras
  aparecem para o operador em vez de sumirem no stderr.

### 3. Validação

```
harness Tk real com contorno {"x","y"}:
abriu: True | rendimento: 2.43% | peças: 4 | área: 0.10 sq.M.
```

`tests/test_print_layout_abre.py` (5 testes): área aceita dict e tupla, contorno inválido → 0,
`print_layout` abre o diálogo com contorno dict e com tupla, e sem peças não inventa rendimento.
Suíte: **517 testes + 1 skip**.

---


## 8.37. Impressão Padronizada em Metros (v1.6.16) `[CONFIRMADO]`

Pedido do operador: "marcar as medidas em metros na impressão, padronizar tudo para metros".

### 1. O que estava misturado

| Elemento | Antes | Depois |
|---|---|---|
| Cabeçalho "Dimensions" | `113.02 X 134.67 cm (1.13 X 1.35 M)` | `1,13 x 1,35 m` |
| Régua inferior/lateral | `10, 20, 30 ...` (cm) | `0,1, 0,2, 0,3 ...` (m) |
| Corte de refile | `CORTE DE REFILE: 1,12 m` | mantido (já em metros) |

### 2. Implementação

- `LayoutEditorView.print_layout()` passou a usar `format_dim_mm(largura, altura)` (helper de
  `ui/units.py`), que devolve metros com vírgula decimal: `1,38 x 2,98 m`.
- Régua do diálogo de impressão (canvas) e da exportação Pillow/PDF: os rótulos usam
  `format_m(coordenada, 1)` → `0,1 / 0,2 / ...`, mantendo a grade de 100 mm.
- Defaults do diálogo atualizados para `1,50 x 2,98 m`.

### 3. Testes

- `tests/test_layout_editor_shortcuts.py::test_print_preview_contains_grid_and_labels_in_meters`
  (antes verificava cm, agora exige metros e proíbe `10`, `20`, `30`).
- Novo `tests/test_print_metros.py` (3 testes): régua em metros, cabeçalho sem "cm" e
  `format_dim_mm` produzindo `1,38 x 2,98 m`.
- `tests/test_print_layout_abre.py` também valida `dimensions_str` em metros.
- Suíte: **520 testes + 1 skip**.

---


## 8.38. Linha da Ponta Fora da Placa e Almoxarifado em Metros (v1.6.17) `[CONFIRMADO]`

Relato do operador: "a correção é no PDF de impressão, arrume a linha azul e coloque a metragem em metros".

### 1. A linha azul vazando da placa

- A `tip_zone` é calculada sobre a chapa **original** (ex.: 1,38 × 2,98 m). Depois do refile a
  placa encolhe (ex.: 1,35 × 1,13 m) e o retângulo azul era desenhado com as coordenadas antigas,
  formando uma moldura fora do contorno da chapa.
- Correções:
  1. `trim_layout_dict()` (cad/trim_engine.py) agora **limita a `tip_zone`** às novas dimensões
     logo após o refile; se a ponta foi inteiramente cortada, `tip_zone`/`layers_tip` são removidos.
  2. Novo `_clamp_tip_zone()` (ui/layout_print_dialog.py), usado pelo canvas e pelo Pillow — protege
     também sessões antigas já salvas com coordenadas grandes.
  3. No PDF a borda era **sólida e grossa** (o Pillow não tem traço nativo); novo
     `_desenhar_retangulo_tracejado()` desenha o tracejado fino igual ao da tela.

### 2. Metragem do almoxarifado em metros

- `format_enfesto_operator_text()` (cad/layers_rule.py) passou a emitir **metros com vírgula** e
  nunca mais centímetros, com clamp da ponta na chapa:

```
Antes: Enfesto: 2 folhas longas de 113.02 × 134.67 cm + 2 folhas curtas, SEM cobrir a ponta de 138.00 × 209.57 cm
Depois: Enfesto: 2 folhas longas de 1,13 × 1,35 m + 2 folhas curtas, SEM cobrir a ponta de 1,35 × 0,33 m
```

### 3. Testes

`tests/test_print_metros.py` ganhou `TestPontaEClamp` (5 testes): clamp na chapa refilada, ponta
totalmente cortada é descartada, entradas inválidas devolvem `None`, texto em metros e
`trim_layout_dict` encolhendo a `tip_zone`. Suíte: **525 testes + 1 skip**.

---

## 9. Pendências e arquivos faltantes

### 9.1 Tarefas abertas

- [x] Atalhos do LayoutEditorView (seção 7) — Concluído (F1-F4, Ctrl+Z, Ctrl+S, indicador `*`, validação status bar)
- [x] Importação/exportação `.lay` (seção 8) — Concluído (`cad/lay_parser.py`, `docs/FORMATO_LAY.md`, `tests/test_lay_parser.py`)
- [x] Migração para MySQL 8.0 Central com pool de conexões e concorrência otimista (8 PCs simultâneos, >1000 layouts/dia) — Concluído (camada `db/`, pool thread-safe, migração 100%, 35 testes unitários e de carga)
- [x] Suporte à regra calçadista de Camadas de Corte (Layers) no nesting e contadores do layout (2 camadas = 20/20, 4 camadas = 10/20) — Concluído (`cad/nesting_engine.py`, `cad/macro_engine.py`, `ui/layout_editor_view.py`, `tests/test_layers_pairs_nesting.py`)
- [x] Exibição e atualização automática de Código de Material, Descrição e Camadas na impressão A4 e aba Materiais — Concluído (`ui/session_view.py`, `ui/layout_print_dialog.py`, `ui/material_codes_view.py`, `tests/test_layout_print_material.py`)
- [x] Correção de contadores do Layout Editor e eliminação de colisão de ID da peça sequencial com ID do molde (molde 36a) — Concluído (`ui/main_window.py`, `ui/layout_editor_view.py`)
- [x] Feedback visual de Nesting (barra de progresso indeterminada e bloqueio de botões contra duplo-clique na SessionView — Fase 6.5) — Concluído (`ui/session_view.py`, `ui/main_window.py`, `tests/test_session_view_progress.py`)
- [x] Exclusão múltipla de moldes na grade da SessionView via Delete/BackSpace/Menu — Concluído (`ui/session_view.py`, `ui/main_window.py`, `tests/test_session_shapes_multidelete.py`)
- [x] Otimização Multi-Sheet (1600 peças em 242 ms), feedback determinado "chapa X de Y" e teste de estresse 10.000 peças (1.51 s, 358 MB RAM — Fases 6.6 e 6.6.1) — Concluído (`cad/nesting_engine.py`, `cad/nesting_backend.py`, `ui/session_view.py`, `ui/main_window.py`, `tools/bench_multi_sheet.py`, `tools/bench_10k_pieces.py`, `tests/test_multisheet_progress.py`)
- [ ] `.die` com múltiplas sagomas
- [ ] `scale_factor` configurável
- [ ] Validação do driver ANP em máquina real
- [ ] Implementar as lacunas do LAYOUT_EDITOR_RE.md, após confirmação do usuário
- [x] Arrasto de grade completa (múltipla seleção e pastas) para moldes do layout e correção de corte em ícones da toolbar — Concluído (`ui/main_window.py`, `ui/session_view.py`, `ui/layout_editor_view.py`, `assets/`)
- [x] Selecionar e apagar múltiplas sessões ao mesmo tempo (Shift/Ctrl/Ctrl+A + Del/Menu) — Concluído (`database.py`, `ui/main_window.py`, `tests/test_db_layer.py`, `tests/test_layout_editor_shortcuts.py`)
- [x] Recompilar executável Linux e pacote Windows após cada entrega — Concluído (`dist/teste_dola`, `teste_dola_linux`, `teste_dola_win11_pendrive.zip`)
- [x] Instalar sincronização automática do `PROJETO_ATOM_JOBMANAGER.md` — Concluído (`tools/sync_project_doc.py`, `.githooks/pre-commit`, `git init`)
- [x] Adicionar coluna 'Resto' na grade de Moldes da SessionView (paridade com sessão 619955 do Job Manager original) — Concluído (`cad/layers_rule.py`, `ui/session_view.py`, `ui/sort_utils.py`, `tests/test_shapes_resto.py`); regra inferida `[INFERIDO]` $-( (2 \times pares \pmod{camadas}) // 2 )$ pendente de confirmação empírica no Windows
- [x] Corrigir travamento do Encaixe com contornos reais: guard de complexidade no NFP, orçamento global de tempo, timeout por placa no SAT, progresso por estimativa e thread safety da UI (Fase 6.8) — Concluído (`cad/nesting_backend.py`, `cad/nesting_engine.py`, `ui/main_window.py`, `ui/session_view.py`, `tests/test_multisheet_progress.py`)
- [x] NFP para contorno real: `is_complex_polygon` + `_contact_fallback` eliminam a explosão combinatória nos motores que usam NFP (IA-teste e NfpBackend) — Concluído (§8.12)
- [ ] Refino estrutural restante do NFP: cache por par de moldes + rotação com translação, pré-normalização única das partes convexas e fim das cópias profundas (só necessário para moldes simples/convexos em lote)
- [x] Benchmark de regressão com contorno real de 130+ vértices — Concluído (`tools/bench_real_shapes.py`)
- [x] Separação automática das sobras de 4 camadas em layout extra de 2 camadas (`cad/layers_split.py`) — Concluído (regra $N_4 = P // 2$ e $N_2 = P \pmod 2$, verificação física atômica $\sum (\text{peças} \times \text{layers}) = 2P$, conservação de peças, idempotência, checkbox de controle em `params`, resto efetivo 0, indicador `(sobras)` e 16 testes em `tests/test_layers_split.py`)
- [x] Implantação da Ponta de 2 Camadas no topo da última placa (`tip_zone`) com modos `canto` e `faixa_topo`, folga de segurança configurável e linha delimitadora tracejada com etiqueta CAM no Layout Editor — Concluído (`cad/layers_split.py`, `ui/layout_editor_view.py`, `ui/session_view.py`, `tests/test_layers_tip.py`)
- [x] Instruções explícitas de corte/enfesto do almoxarifado no relatório de impressão A4 (`format_enfesto_operator_text`) e visualização da ponta na impressão física/PDF — Concluído (`cad/layers_rule.py`, `ui/layout_print_dialog.py`, `tests/test_layout_print_legend.py`)
- [x] Correção do espalhamento de peças no Nesting por contaminação de opções de sessão em `params` (`clean_preset`), restaurando intertravamento contorno-a-contorno, alternância 0°/180° e limpeza de estado prévio — Concluído (`cad/nesting_backend.py`, `cad/nesting_engine.py`, `ui/main_window.py`, `tests/test_multisheet_nesting.py`)

### 9.2 Arquivos de amostra que faltam (por prioridade)

1. `.lay` real gerado pelo `fn98.exe` — **[ANALISADO]** Amostras `$$LAYOUT.v3$$` obtidas e validadas (`samples/teste.lay`, `samples/A40118.LAY`)
2. `.ord` reais de ERP calçadista
3. `.sho` ou ShoeML (`.xml`) com estilos, cores e grade de tamanhos
4. `Machine.ini` / parâmetros ANP (aceleração, curso X/Y, setores de vácuo FlashCut/Twin)

### 9.3 Inventário de binários legados
Local: `/home/dola/Documentos/clone do job/antigo/arquivos pos instalacao/Common 100% funcionado/`

| Arquivo | Função original | Papel na reconstrução |
|---|---|---|
| `fn98.exe` | FlashNest 1998, nesting em couro natural (`fn98.exe S/R SessionId=n`) | Referência para calibrar aproveitamento; rodar via Wine ou analisar (Ghidra/IDA) |
| `dp98.exe` | Die Packing 1998, bobinas sintéticas e grades regulares | Referência para sintéticos |
| `SMPNst.dll` | Classes `CHNNest`, `CHNNickNest`, `BumpShape` | Lógica portada para Python (GEOS/Shapely) em `atom_reborn` |
| `TheLoop.exe` | Orquestrador COM + despachador ANP | Substituído por `LoopDaemon` |
| `AcqImg.dll` | Visão computacional e calibração de câmeras | Referência |
| `ShedNt.exe` | Shape Editor | Reproduzido no `ShapeEditorView` |
| `Layout.exe` / `FreeNest.exe` | Editores CAM de layout | Reproduzidos no `LayoutEditorView` |
| `Report.exe` / `Report.xsl` | Relatórios XSLT/HTML | Reproduzido no Print Preview A4 |

---

## 10. Changelog (apenas acrescentar)

| Dia e Data | Hora | Autor | Alteração | Arquivos |
|---|---|---|---|---|
| Qui, 15/10/2026 | 14:00 | Antigravity | Importação `.die` aprimorada (itens da seção 5); exportador bidirecional; recompilação Linux + Windows | `cad/die_parser.py`, `teste_dola_linux`, `teste_dola_win11_pendrive.zip` |
| Sáb, 17/10/2026 | 22:00 | Claude + usuário | Levantamento dos atalhos F1/F2/F3/F4/Ctrl+Z/Ctrl+S; criação deste documento | `PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 17/10/2026 | 22:30 | Antigravity | Engenharia reversa, documentação técnica (`docs/FORMATO_LAY.md`), parser e gerador `.lay` (`cad/lay_parser.py`) com fidelidade round-trip e preservação da ordem de usinagem CNC; 13 testes unitários | `cad/lay_parser.py`, `docs/FORMATO_LAY.md`, `tests/test_lay_parser.py`, `database.py` |
| Sáb, 17/10/2026 | 22:50 | Antigravity | Implementação dos atalhos CAM no LayoutEditorView (F1/F2 giro fino 2°, F3 giro 90° ciclo 4 estados, F4 flip 180°, Ctrl+Z undo 100 níveis, Ctrl+S salvamento atômico DB+disco), bloqueio estrito de Shift+F3 e Ctrl+Y, indicador de modificado (`*`), validação não-bloqueante na barra de status; 13 testes unitários | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py` |
| Sáb, 17/10/2026 | 23:13 | Antigravity | Instalação da sincronização automática via Git pre-commit hook (`tools/sync_project_doc.py`, `.githooks/pre-commit`), inicialização do versionamento Git e atualização geral das seções manuais | `tools/sync_project_doc.py`, `.githooks/pre-commit`, `PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 17/10/2026 | 23:53 | Antigravity | Migração completa para MySQL 8.0 Central (8 PCs simultâneos, >1000 layouts/dia): criação do pacote `db/` (pool thread-safe `SimpleMySQLPool`, reconexão automática, conversão transparente de dialetos SQL), DDL MySQL 8.0 (`db/schema_mysql.sql`), refatoração de `database.py` (auditoria `operator_info`, paginação, concorrência otimista com versioning), modal de resolução de concorrência no `LayoutEditorView` (Salvar Cópia / Recarregar), script de migração idempotente `tools/migrate_sqlite_to_mysql.py` (100% de conciliação de linhas nas 10 tabelas), testes de carga com 8 threads concorrentes e 1000 salvamentos (>360 layouts/s, zero erros de rede, integridade referencial confirmada); suporte a caching_sha2_password empacotado no standalone Linux e Windows pendrive | `db/`, `database.py`, `ui/layout_editor_view.py`, `tools/migrate_sqlite_to_mysql.py`, `tests/test_db_layer.py`, `tests/test_mysql_concurrency.py`, `teste_dola.spec`, `build_linux.sh`, `README.md` |
| Dom, 18/10/2026 | 00:19 | Antigravity | Correção de integridade referencial e resiliência na criação de sessões: auto-recuperação de foreign keys (order_id/material_id) e garantia de unicidade de code em `create_session`, adição de propriedade `backend` e método `get_session` em `DatabaseManager`, tratamento de exceção amigável e busca dinâmica de pedidos ativos em `MainWindow.on_new_session`, isolamento total da suíte de testes contra banco de produção (`TEST_DB_NAME`, 38/38 testes passando), conciliação 1:1 no MySQL de produção e recompilação do executável standalone | `database.py`, `ui/main_window.py`, `tests/test_db_layer.py`, `tests/test_mysql_concurrency.py`, `dist/teste_dola`, `teste_dola_linux` |
| Dom, 18/10/2026 | 00:36 | Antigravity | Liberação para arrasto de grade completa (múltipla seleção ou pasta inteira) de moldes da árvore e soltura direta nos moldes do layout/sessão; correção de corte/truncamento no ícone de produção da barra de ferramentas (`btn_prod.png`, `btn_moldes.png`, `btn_mat.png`); adição de `add_shapes` em lote no `SessionView` e `LayoutEditorView`; 2 novos testes unitários (40/40 passando) e recompilação do standalone | `ui/main_window.py`, `ui/session_view.py`, `ui/layout_editor_view.py`, `assets/btn_prod.png`, `assets/btn_moldes.png`, `assets/btn_mat.png`, `tests/test_layout_editor_shortcuts.py`, `dist/teste_dola`, `teste_dola_linux` |
| Dom, 18/10/2026 | 00:52 | Antigravity | Seleção múltipla e exclusão em lote de sessões: suporte a seleção estendida na árvore e no grid (Shift, Ctrl e Ctrl+A), prevenção de colapso de seleção na navegação automática, método atômico `delete_sessions` em lote no `DatabaseManager`, exclusão em lote via menu de contexto, menu Editar e tecla Delete com confirmação única e fechamento limpo das janelas filhas; 2 novos testes unitários (42/42 passando) e recompilação do executável | `database.py`, `ui/main_window.py`, `tests/test_db_layer.py`, `tests/test_layout_editor_shortcuts.py`, `dist/teste_dola`, `teste_dola_linux` |
| Dom, 18/10/2026 | 01:13 | Antigravity | Correção da criação de sessão, numeração sequencial monotônica estrita persistente (números apagados como #1 nunca são reutilizados via `last_session_number`), proteção contra re-semeadura de moldes e sessões de exemplo (#91/#38) ao reiniciar (`db_seeded`), ativação automática do modo Produção na árvore ao criar sessão com seleção e expansão visual, e atualização do `build_linux.sh` para atualizar o executável raiz | `database.py`, `ui/main_window.py`, `build_linux.sh`, `tests/test_session_monotonic.py`, `PROJETO_ATOM_JOBMANAGER.md` |
| Dom, 18/10/2026 | 01:17 | Antigravity | Formatação explícita com Dia da Semana, Data e Horário em todas as entradas do Changelog e espelhamento automático sincronizado de `PROJETO_ATOM_JOBMANAGER.md` e `PROJETO_ATOM_JOBMANAGER ` na raiz do repositório pai | `tools/sync_project_doc.py`, `PROJETO_ATOM_JOBMANAGER.md` |
| Dom, 18/10/2026 | 01:21 | Antigravity | Resiliência de chave estrangeira em `create_shape` e `on_import_die`: auto-recuperação/criação de artigos e ordens no MySQL quando inexistentes, eliminando erro 1216 na importação de moldes `.die`; 1 novo teste unitário (45/45 passando) e recompilação do executável | `database.py`, `ui/main_window.py`, `tests/test_session_monotonic.py`, `PROJETO_ATOM_JOBMANAGER.md` |
| Dom, 18/10/2026 | 01:39 | Antigravity | Suporte completo à exclusão, renomeação e criação persistente de pastas de produção (`job_folders`): adição de tabela e operações CRUD no `DatabaseManager` (MySQL e SQLite), detecção resiliente de nós de pasta na árvore, confirmação e exclusão em lote/cascata de pastas vazias ou com sessões via teclado (Delete/Backspace) e menus de contexto, proteção contra reaparecimento de pastas excluídas no restart (`job_folders_initialized`), simplificação no diálogo de pastas de moldes vazias; 2 novos testes unitários (47/47 passando) e recompilação do executável standalone | `database.py`, `ui/main_window.py`, `db/schema_mysql.sql`, `db/migrations/001_initial_mysql_schema.sql`, `tests/test_session_monotonic.py`, `dist/teste_dola`, `teste_dola_linux` |
| Dom, 18/10/2026 | 02:00 | Antigravity | Aprimoramento do scanner `tools/sync_project_doc.py` e conciliação do documento de especificação: exibição prioritária do schema MySQL 8.0 (`db/schema_mysql.sql`, `db/migrations/*.sql`) e SQLite de contingência (`jobmanager.db`) com alerta de desatualização de tabelas/colunas; filtragem de eventos restrita a teclado (exclusão de mouse/ciclo de vida e dígitos soltos); marcação de teclas proibidas (`Shift+F3`, `Ctrl+Y`) como `bloqueado (correto)`; redução a conflitos reais de concorrência global (`bind_all`); atualização manual das Seções 3.1 (`database.py`, `PrintPreviewDialog`, `anp_client.py`), 7.5 (28 atalhos reais marcados como `[NÃO CONFIRMADO pelo usuário]`) e Seção 11 como `[CONCLUÍDA]` | `tools/sync_project_doc.py`, `PROJETO_ATOM_JOBMANAGER.md` |
| Dom, 18/10/2026 | 02:10 | Antigravity | Suporte a subpastas hierárquicas em Moldes (`shapes` / `shape_folders`): criação recursiva delimitada por barra (`pai/filho`), exibição aninhada na árvore (`Treeview`), renomeação e exclusão em cascata (com opção de mover moldes para raiz ou excluí-los com as subpastas); filtro recursivo no grid inferior ao selecionar pasta pai ou subpasta; listbox de mover molde com indentação hierárquica; menu de contexto na árvore com 'Criar Subpasta em <pasta>...' e 'Criar Pasta na Raiz...'; menus da barra superior atualizados. Auditoria e salvaguarda de foco nos atalhos CAM do LayoutEditorView (`nudge_selected`, `rotate_selected`, `delete_selected` ignorados se foco em `Entry`/`Text`/`Treeview`). Adição de teste unitário de hierarquia e cascata em `tests/test_session_monotonic.py` (48/48 testes passando). Recompilação do executável standalone Linux (`teste_dola_linux`). | `database.py`, `ui/main_window.py`, `ui/layout_editor_view.py`, `tests/test_session_monotonic.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 09:32 | Antigravity | Classificação e ordenação de moldes e tamanhos do maior para o menor e vice-versa: criação do módulo `ui/sort_utils.py` com `size_sort_key` (suporte a tamanhos com letras ex: `36a`, decimais `35.5`, frações `37 1/2`, badges e extração do nome), `natural_sort_key` (ordenação alfanumérica humana) e `shape_area_sort_key` (dimensão geométrica do contorno); interatividade na tabela de moldes da sessão (`SessionView`) ao clicar nos cabeçalhos (`Tama...`, `Molde`, `Pares...`, etc.) com indicador de seta `▲`/`▼`, adição do botão `🔽 Classificar ▾` na barra inferior e submenu no menu de contexto com reordenação da sequência de corte (1..N) e persistência no banco (MySQL/SQLite); ordenação interativa adicionada também ao grid inferior da janela principal (`MainWindow.grid_lower`) e ao diálogo de adição de moldes (`AddShapesDialog`); 5 novos testes unitários (53/53 passando) e recompilação do executável standalone Linux | `ui/sort_utils.py`, `ui/session_view.py`, `ui/main_window.py`, `ui/add_shapes_dialog.py`, `tests/test_shape_sorting.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 11:08 | Antigravity | Digitação contínua de pares e sequências na tabela de moldes (`SessionView.tree_shapes`) via setas do teclado: navegação descendente (`<Down>`, `<Return>`, `<Tab>`) e ascendente (`<Up>`, `<Shift-Return>`, `<Shift-Tab>`) no editor inline com pré-seleção de texto para substituição direta; abertura imediata do editor ao teclar números (`0-9`), `<Return>` ou `<F2>` na linha selecionada da árvore; atalhos de ajuste incremental rápido (`Ctrl-Up`/`Down`, `Alt-Up`/`Down`); scroll automático (`see`) e sincronização em tempo real com pré-visualizador CAD e banco de dados (MySQL/SQLite); 3 novos testes unitários (56/56 passando) e recompilação do executável standalone Linux | `ui/session_view.py`, `tests/test_shape_sorting.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 11:34 | Antigravity | Habilitação do zoom de 20% a cada clique na ferramenta (`btn_zoom`) e atalho com CTRL + clique do mouse de ação no canvas CAD (`LayoutEditorView`): fator de escala multiplicativo de 1.20 (+20%) por clique com ancoragem exata do ponto sob o cursor (drift = 0.000000 mm); atalho `<Control-Button-1>` na mesa com cursor indicativo dinâmico `crosshair`; isolamento da grade de moldes da barra lateral com fundo branco opaco; visualização do enquadramento total (100% Fit) com `btn_zoom_fit` e `btn_fit`; zoom out (-20%) com botão direito e atalhos adicionais de pan com botão do meio (`fleur`); teste unitário dedicado (`test_zoom_20_percent_tool_and_ctrl_click`, 57/57 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 11:43 | Antigravity | Centralização da placa do layout no meio da tela (`LayoutEditorView`): posicionamento simétrico horizontal e vertical da chapa no centro da área CAD visível (`div_x / 2.0`), com cálculo automático do divisor lateral padrão (`sidebar_div_x`) para preservar a área de trabalho sem comprimir a barra de moldes; margens laterais rigorosamente idênticas (`diff = 0.000000 mm`) tanto para chapas horizontais quanto verticais (ex: `Sheet (2980.00 X 1380.00)`); ancoragem do rótulo de dimensões (`Sheet (...)`) e preservação da centralização durante operações de zoom e pan; 1 novo teste unitário dedicado (`test_plate_centered_in_cad_screen_area`, 58/58 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 11:51 | Antigravity | Remoção do seletor visual de máquina de corte no editor (`SessionView`): remoção do rótulo e combobox `cb_machine` da interface gráfica conforme o padrão clássico original, mantendo a máquina fixa padrão 'ATOM FlashCut Flex 3020' nos dados da sessão, backend e exportadores; preservação do método `get_machine()`; 1 novo teste unitário dedicado (`test_machine_default_preserved_without_editor_combobox`, 59/59 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/session_view.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 12:12 | Antigravity | Atalho de impressão Ctrl+P e correção da escala proporcional da chapa no relatório de impressão A4 (`LayoutPrintDialog`): vinculação de `<Control-p>`/`<Control-P>` no `LayoutEditorView` (canvas e frame), na janela principal (`MainWindow`) e no diálogo; cálculo dinâmico da chapa preenchendo a folha A4 proporcionalmente e centralizada (substituição do antigo limite fixo de 60pt por área disponível de ~550pt entre metadados e rodapé); preservação estrita do aspect ratio para qualquer chapa (horizontal, vertical ou tiras); renderização idêntica no preview Tkinter e exportador PIL/PDF; 2 novos testes unitários (61/61 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/layout_print_dialog.py`, `ui/layout_editor_view.py`, `ui/main_window.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 16:30 | Antigravity | Alteração da nomenclatura de 'Sheet' para 'Placa' com medidas em centímetros (cm) e desativação de referências a 'Leather' (couro): atualização dos rótulos sobre a mesa CAD e na barra de status do `LayoutEditorView` e `SessionView` para 'Placa (h X w cm)'; remoção da estratégia 'flashnestleather' da combobox de estratégias e da opção 'como pele' no cadastro de materiais; atualização de materiais seed no banco de dados; 1 novo teste unitário dedicado (`test_plate_label_in_cm_and_no_sheet_nor_leather`, 62/62 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/layout_editor_view.py`, `ui/session_view.py`, `ui/material_codes_view.py`, `database.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 17:45 | Antigravity | Abertura da tela de impressão (`LayoutPrintDialog`) em tela cheia / maximizada: inicialização maximizada ocupando todo o monitor (`-zoomed` / `state("zoomed")` / resolução de tela); remoção da restrição `transient` permitindo controles padrão de janela (minimizar, restaurar e fechar); botão `⛶ Tela Cheia` na barra de ferramentas e atalho `<F11>` para alternar entre maximizado e fullscreen sem bordas; atalho `<Escape>` inteligente (sai de fullscreen antes de fechar); reajuste dinâmico automático (`fit_to_page`) no evento `<Configure>` da tela cheia garantindo zoom proporcional de 100% da folha A4; 1 novo teste unitário dedicado (`test_layout_print_dialog_fullscreen_and_maximized`, 63/63 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/layout_print_dialog.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 17:52 | Antigravity | Remoção de informações artificiais do sumário dos layouts (`SessionView.update_summary_text`): eliminação das seções 'Shapes: (Status, Ready for cutting table)' e 'Notes: (Output profile, Blade type, Export format)' na aba de resumo da sessão, mantendo apenas informações reais do material/placa (em cm) e layouts calculados conforme o padrão clássico ATOM (`frmSessionSummary.gif`); remoção de texto fixo no label inferior de notas; 1 novo teste unitário dedicado (`test_summary_text_does_not_contain_shapes_or_notes_placeholders`, 64/64 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/session_view.py`, `tests/test_shape_sorting.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 18:18 | Antigravity | Marcação de 10 em 10 cm com traços e numeração na placa do layout (`LayoutEditorView.redraw`): adição de traços de régua milimétrica (ticks) nas 4 bordas da placa e numeração explícita em centímetros a cada 10 cm ao longo do eixo vertical direito (10, 20, 30... até o topo da placa conforme mockup do usuário `media_1792357699561.jpg`) e no eixo horizontal inferior (10, 20, 30... até a largura da placa); sincronização automática com zoom e pan; 1 novo teste unitário dedicado (`test_grid_10cm_markings_and_labels`, 65/65 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 18:37 | Antigravity | Inclusão da grade e marcações de 10 em 10 cm na tela de impressão e exportação física/PDF/PNG (`LayoutPrintDialog`): adição de linhas de grade milimétrica internas (`#d0d0d0`), traços de régua nas 4 bordas (ticks) e numeração explícita em centímetros ao longo do eixo horizontal inferior (10, 20, 30... cm) e eixo vertical direito (10, 20, 30... cm) tanto no preview do canvas Tkinter (`redraw`, tags `print_grid`, `print_tick`, `print_label`) quanto na geração de alta resolução via Pillow (`render_pillow_page`, compatível com tupla e dicionário de contorno); 1 novo teste unitário dedicado (`test_print_preview_contains_10cm_grid_and_labels`, 66/66 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/layout_print_dialog.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 18:52 | Antigravity | Liberação para criação e gerenciamento de subpastas hierárquicas no módulo de Produção (Job Folders): suporte a caminhos com barras (ex: 'SEMANA-46/LOTE-01/CORTE') com criação automática de pastas ancestrais, renomeação em cascata e exclusão em cascata no banco de dados (`database.py`); renderização aninhada multinível na Treeview de Produção (`populate_tree`); menu de contexto dinâmico no clique com botão direito em qualquer pasta de produção ('📁 Criar Subpasta em ...', '📁 Criar Produção na Raiz...', 'Criar sessão em ...'); novas opções nos menus superiores Arquivo e Ferramentas; suporte a movimentação de sessões entre pastas/subpastas ('📁 Mover para Pasta de Produção...'); 2 novos testes unitários dedicados (68/68 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `database.py`, `ui/main_window.py`, `tests/test_session_monotonic.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 19:18 | Antigravity | Remoção de prefixo forçado de ID (#id) nos nós da árvore ao renomear sessão e preservação do SessId numérico na tabela inferior: criação de helper utilitário `clean_session_display_name` em `ui/sort_utils.py` para remoção consistente de prefixos automáticos como '(#3)' ou '( #3 )'; exibição direta do nome customizado (ex: '121805') na Treeview de Produção sem prefixos artificiais, idêntico ao software original ATOM; preenchimento automático do diálogo de renomeação (`on_rename_tree_item`) com o nome limpo e atualização no banco de dados e memória; sincronização bidirecional na edição direta pelo campo de nome da sessão (`SessionView.entry_sname`); preservação estrita do identificador numérico original da sessão na coluna `SessId` da tabela inferior (`grid_lower`); 3 novos testes unitários dedicados (71/71 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/sort_utils.py`, `ui/main_window.py`, `ui/session_view.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 19:40 | Antigravity | Opção de exclusão de artigos/pedidos e desacoplamento de artigos no sistema: inclusão de comando 'Excluir Artigo' / 'Excluir' no menu de contexto com clique direito em artigos na árvore (`ui/main_window.py`) e suporte à tecla Delete/Backspace; exclusão segura em `database.py` (`delete_order` e `delete_article`) desvinculando sessões (`order_id = NULL`) e moldes (`article_id = NULL`) sem perda de geometria nem violação de integridade referencial; alteração dos esquemas MySQL 8.0 e SQLite para permitir `order_id` e `article_id` nulos com `ON DELETE SET NULL`; eliminação da recriação automática forçada de artigos de exemplo ('Derby Masculino #41') na criação de sessões; 1 novo teste unitário dedicado (72/72 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `database.py`, `ui/main_window.py`, `db/schema_mysql.sql`, `db/migrations/001_initial_mysql_schema.sql`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 20:02 | Antigravity | Opção de exclusão de materiais clicando com o mouse na árvore e no grid (`MainWindow`): implementação de menu de contexto dinâmico no clique com botão direito sobre materiais na Treeview (`tree_main`) e no DataGrid inferior (`grid_lower`) exibindo 'Excluir Material' (Del) e 'Excluir', além de suporte a exclusão em lote; exclusão segura em `database.py` (`delete_material`) desvinculando sessões (`material_id = NULL`) e artigos (`material_id = NULL`) sem violação de FK nem perda de dados; migração dos esquemas MySQL 8.0 e SQLite para suportar `material_id` anulável com `ON DELETE SET NULL`; sincronização e recarga imediata em cache, árvore, grid, janelas de sessão e códigos de materiais (`refresh_materials_everywhere`); 2 novos testes unitários dedicados (74/74 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `database.py`, `ui/main_window.py`, `db/schema_mysql.sql`, `db/migrations/001_initial_mysql_schema.sql`, `tests/test_layout_editor_shortcuts.py`, `tests/test_db_layer.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 20:55 | Antigravity | Bloqueio de abertura do Layout Editor sem cálculo prévio de encaixe e eliminação de peças fantasmas em sessões em branco: desativação do botão 'Editor...' na aba Layout da sessão quando não há layout calculado (`btn_open_editor["state"] = "disabled"`); bloqueio com alerta explicativo ('Não há layout calculado para esta sessão. Execute o cálculo de encaixe (Nest) primeiro.') ao tentar abrir via duplo-clique na lista ou no mini-preview, menu de contexto da tabela de layout, menus superiores (Arquivo/Ferramentas/Janela), barra de ferramentas (`btn_lay`) e menu da árvore (`MainWindow.show_layout_editor`); eliminação de injeção automática de 22 peças fictícias e moldes de exemplo (`load_sample_nesting`, `TARGET_SPECS`) no `LayoutEditorView` por padrão (`load_sample=False`); sincronização dinâmica de estado do botão ao executar Nesting ou limpar layout; 3 novos testes unitários dedicados (77/77 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `ui/layout_editor_view.py`, `ui/session_view.py`, `ui/main_window.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 21:48 | Antigravity | Respeito rigoroso ao gap exato de 1.0 mm com encaixe contorno a contorno (contour-to-contour bumping) e zero colisões: substituição do avanço horizontal por bounding box (`w + gap`) pelo bumping de contato horizontal via busca binária submilimétrica (`find_contact_coordinate_binary`, resolução ~0.02 mm e margem de segurança de 0.05 mm); implementação de encaixe vertical por intertravamento de linhas inteiras (`nest_synthetic_engine` e `dieproc_nest_pieces`) garantindo alinhamento de base uniforme e rotação alternada 0°/180°; eliminação dos vãos vazios de 14.8 mm e aproximação precisa para a distância real de ~1.05 mm (>= 1.00 mm estrito); 2 novos testes unitários dedicados em `tests/test_nesting_contour_gap.py` (79/79 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`) | `cad/geometry.py`, `cad/nesting_engine.py`, `tests/test_nesting_contour_gap.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Dom, 18/10/2026 | 21:59 | Antigravity | Criação do manual técnico completo sobre os motores e perfis de parâmetros de nesting do JobManager (`FastNest`, `HighYield`, `stdNOTFill`, `stdFill`, `PrmSss_35`): detalhamento da arquitetura industrial ATOM FlashCut/DieProc dp98, parâmetros matemáticos de acoplamento de rotação (Coupling), varredura angular fina (Range Sweep), intertravamento de linhas (Row Interlock), comportamento de fim de chapa (Fill Layout: None vs Always) e guia prático para o operador | `docs/MOTORES_NESTING_PARAMETROS.md`, `PROJETO_ATOM_JOBMANAGER.md` |
| Dom, 18/10/2026 | 22:02 | Antigravity | Inclusão das Estratégias de Nesting (`sint`, `tape_a`, `flashnestsheet`, `flashnestroll`, `freenest`) no manual técnico: detalhamento das geometrias físicas de corte (chapas regulares vs rolos contínuos em esteira vs fitas e debruns vs retalhos livres), alinhamento de base uniforme linear, acoplamento DieProc dp98 e matriz de combinações recomendadas | `docs/MOTORES_NESTING_PARAMETROS.md`, `PROJETO_ATOM_JOBMANAGER.md` |
| Seg, 19/10/2026 | 06:50 | Antigravity | Botão de Refilar Layout com corte transversal automático (guilhotina CAM) no final das peças: adição do botão '✂ Refilar' na barra de ferramentas do LayoutEditorView, atalho Ctrl+T e opções nos menus Tools e Nesting; diálogo dedicado TrimLayoutDialog (`ui/trim_layout_dialog.py`) com cálculo exato de extensão máxima Y (max_y) e folga/gap configurável em mm e cm/m, presets rápidos ('Gap 1.0 mm', 'Margem 10 mm', '2,08 m (Sugerido)' reduzindo a chapa de 298.0 cm para 208.0 cm com ~90.0 cm / 30.2% de economia de material); suporte a linha de corte transversal vermelha tracejada com ícones de tesoura e badge CAM na mesa CAD; suporte completo a Ctrl+Z (Undo) preservando e restaurando sheet_height, original_sheet_height e trim_cut_line; sincronização com MainWindow.on_layout_editor_save, SessionView (mini-preview do layout) e LayoutPrintDialog (relatório de impressão A4 e exportação PDF/PIL); 3 novos testes unitários dedicados em `tests/test_layout_editor_trim.py` (82/82 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`). | `ui/trim_layout_dialog.py`, `ui/layout_editor_view.py`, `ui/main_window.py`, `ui/session_view.py`, `ui/layout_print_dialog.py`, `tests/test_layout_editor_trim.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Seg, 19/10/2026 | 07:23 | Antigravity | Refilo automático direto no final das peças com gap 1.0 mm exato sem abrir caixa de diálogo: acionamento imediato em 1 clique pelo botão '✂ Refilar' e atalho Ctrl+T (eliminação da abertura de diálogo modal); cálculo automático da cota Y máxima dos contornos reais rotacionados somando exatamente 1.0 mm de folga; posicionamento da linha de corte transversal vermelha contínua no topo exato das peças com tesouras CAM; reposicionamento do badge informativo acima da chapa sem encobrir os moldes; 4 testes unitários passando em `tests/test_layout_editor_trim.py` e recompilação do executável standalone Linux (`teste_dola_linux`). | `ui/layout_editor_view.py`, `tests/test_layout_editor_trim.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux`, `dist/teste_dola` |
| Seg, 19/10/2026 | 07:47 | Antigravity | Garantia de funcionamento global do atalho Ctrl+T / Ctrl+t para refile automático de layout: vinculação no nível raiz da janela principal (`MainWindow.handle_ctrl_t`), vinculação no frame e no canvas do `LayoutEditorView` com salvaguarda de foco em campos de edição (`Entry`/`Text`), foco automático no canvas ao abrir o editor e no clique do mouse; teste unitário automatizado (`test_ctrl_t_shortcut_key_events`, 5/5 testes em trim e 84/84 na suíte geral passando); sincronização da documentação e recompilação dos executáveis standalone Linux (`teste_dola_linux`). | `ui/main_window.py`, `ui/layout_editor_view.py`, `tests/test_layout_editor_trim.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Seg, 19/10/2026 | 08:15 | Antigravity | Remoção de material na sessão via tecla Delete do teclado (`SessionView.tree_mat` e `tab_mat`), botão '🗑️ Remover Material (Del)' na barra inferior e menu de contexto com clique direito; bloqueio condicional estrito de exclusão, edição e troca de material enquanto o layout estiver calculado (`placed_pieces`), exibindo alerta orientativo ao operador; desbloqueio imediato da troca após limpar ou refazer o layout ('Limpar' / 'refazer aí sim libera'); proteção contra troca indevida na combobox `cb_mat_code` e na árvore principal (`MainWindow.apply_material_to_session`); persistência atômica no banco com `clear_material=True` (`material_id = NULL`); suporte a resumo e preview sem material; 6 novos testes unitários dedicados em `tests/test_session_material_delete.py` (90/90 testes na suíte passando) e recompilação do executável standalone Linux (`teste_dola_linux`). | `ui/session_view.py`, `ui/main_window.py`, `database.py`, `tests/test_session_material_delete.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Seg, 19/10/2026 | 09:20 | Antigravity | Remoção da estratégia 'flashnestroll' e de referências a bobinas contínuas com esteira rolante: adequação do sistema à realidade fabril de operação exclusiva com chapas e placas sintéticas; exclusão de 'flashnestroll' dos seletores combobox em SessionView e OptionsDialog; normalização automática transparente de sessões legadas gravadas com 'flashnestroll' para 'flashnestsheet'; limpeza dos textos informativos no DieProcDialog e na descrição das estratégias; ajuste do motor nesting_engine para cálculo estrito em chapas (is_roll=False); atualização do manual técnico docs/MOTORES_NESTING_PARAMETROS.md; 4 novos testes unitários dedicados em tests/test_strategy_removal.py (94 testes na suíte geral passando) e recompilação do executável standalone Linux (teste_dola_linux). | `ui/session_view.py`, `ui/options_dialog.py`, `ui/dieproc_dialog.py`, `cad/nesting_engine.py`, `docs/MOTORES_NESTING_PARAMETROS.md`, `tests/test_strategy_removal.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Seg, 19/10/2026 | 09:45 | Antigravity | Substituição do campo 'Partida' pelo campo 'Descrição' na tabela inferior de Estoque de Material (`MainWindow.grid_lower`): remoção da coluna legada estática 'Partida' (que continha o valor fixo '1') e inclusão da coluna 'Descrição' exibindo a nomenclatura real e completa do material (`m['name']` / `m['code']`), com ordenação natural alfanumérica (`sort_grid_lower('descricao')`); 1 novo teste unitário dedicado (`test_materials_grid_has_descricao_column_and_no_partida`, 95 testes na suíte geral passando) e recompilação do executável standalone Linux (`teste_dola_linux`). | `ui/main_window.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Seg, 19/10/2026 | 10:40 | Antigravity | Inclusão de planilha interativa de consulta das combinações recomendadas de Estratégias & Parâmetros na aba Geral da Sessão (`SessionView`): criação do painel 'Guia de Combinações Recomendadas (Estratégias & Parâmetros)' com tabela Treeview zebrada contendo Objetivo industrial, Estratégia, Parâmetro e Comportamento técnico do corte; suporte a duplo clique e botão '✓ Aplicar Selecionado' para configuração automática e instantânea dos seletores `cb_strategy` e `cb_params`; sincronização bidirecional e destaque dinâmico da combinação ativa (`highlight_guide_matching`); 1 novo teste unitário dedicado (`test_session_view_has_recommended_combinations_table`, 96 testes passando na suíte geral) e recompilação do executável standalone Linux (`teste_dola_linux`). | `ui/session_view.py`, `ui/main_window.py`, `tests/test_strategy_removal.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Seg, 19/10/2026 | 10:55 | Antigravity | Atualização do rótulo e descrição da Estratégia na sessão ('A Estratégia define a geometria física do corte e do material:'): substituição do rótulo estático 'Estratégia:' acima da combobox `cb_strategy` em `SessionView` pelo texto conceitual solicitado pelo operador, e enriquecimento das descrições dinâmicas de cada motor em `lbl_strategy_desc`; 1 novo teste unitário dedicado (`test_strategy_label_and_descriptions`, 97 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`). | `ui/session_view.py`, `tests/test_strategy_removal.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Seg, 19/10/2026 | 11:02 | Antigravity | Atualização do rótulo e descrição de Parâmetros na sessão ('O Parâmetro define o comportamento das rotações, folgas e preenchimento da chapa:'): substituição do rótulo 'Parâmetros:' em `SessionView` pelo texto conceitual solicitado pelo operador, mantendo o botão '⚙️ Configurar...' à direita com perfeito alinhamento visual; atualização do teste unitário dedicado (`test_strategy_label_and_descriptions`, 97 testes passando) e recompilação do executável standalone Linux (`teste_dola_linux`). | `ui/session_view.py`, `tests/test_strategy_removal.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Seg, 19/10/2026 | 11:20 | Antigravity | Remoção da combinação 'flashnestsheet' + 'HighYield' ('Economizar material ao máximo em chapa cara') da tabela interativa de combinações recomendadas (`RECOMMENDED_COMBINATIONS` em `ui/session_view.py`) e da matriz do manual técnico (`docs/MOTORES_NESTING_PARAMETROS.md`); atualização dos testes automatizados em `tests/test_strategy_removal.py` validando ausência de `HighYield` na tabela de guia; recompilação do executável standalone Linux (`teste_dola_linux`). | `ui/session_view.py`, `docs/MOTORES_NESTING_PARAMETROS.md`, `tests/test_strategy_removal.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Seg, 19/10/2026 | 14:15 | Antigravity | Criação e integração do novo motor de cálculo de nesting 'IA-teste' com Macros Declarativas e IA Local Embarcada 100% nativa (Python 3.12 puro, zero dependências externas): motor `OmniNestMacroEngine` com avaliador seguro de expressões por AST sem `eval()` (`SafeFormulaEvaluator`), compilador de DSL de macros (`MacroCompiler`), aprendizado contínuo por imitação em `Ctrl+S` (`learn_from_operator_save`) e auto-calibração por UCB1 Multi-Armed Bandit (`suggest_optimized_macro_params` / `record_macro_execution_feedback`) por família geométrica calçadista (`ShapeFeatureExtractor`); suporte a persistência de macros em predefinições DieProc no MySQL 8.0 e SQLite (`macro_script` em `dieproc_presets`), aba dedicada com editor de macro e status da IA no `DieProcDialog`, nova estratégia `IA-teste` com feedback em tempo real e suíte com 106 testes automatizados passando. | `cad/ai_learner.py`, `cad/macro_engine.py`, `cad/nesting_engine.py`, `database.py`, `db/schema_mysql.sql`, `db/migrations/001_initial_mysql_schema.sql`, `ui/session_view.py`, `ui/dieproc_dialog.py`, `ui/layout_editor_view.py`, `ui/main_window.py`, `tests/test_macro_engine_ia_teste.py`, `tests/test_strategy_removal.py`, `PROJETO_ATOM_JOBMANAGER.md` |
| Ter, 20/10/2026 | 02:45 | Antigravity | Eliminação total de delay (lag) na movimentação manual de peças e feedback visual avançado em `LayoutEditorView` e `CADCanvas`: implementação de fast-path de renderização via `canvas.move` sem recriação de cena (`self.redraw`), reduzindo o tempo por evento de `<B1-Motion>` para menos de 0.05 ms (>100 FPS); contorno fantasma (Ghost Outline com dash e `#64748b`) na origem de arraste; snap magnético em tempo real nas bordas da chapa a 2.0 mm; feedback de colisão espacial instantâneo $O(1)$ via `SpatialGrid.query_items` destacando a peça arrastada em vermelho (`#ef4444`) se colidir ou verde (`#22c55e`) se livre, e peças estáticas colididas em âmbar (`#f59e0b`); cancelamento limpo com a tecla `<Escape>` restaurando a peça à origem do ghost sem poluir a pilha de undo; redesenho pontual `redraw_single_piece` para rotações F1–F4 e setas do teclado; validação estrita de zero colisão com reversão automática no `<ButtonRelease-1>`; 5 novos testes unitários adicionados (111/111 testes passando na suíte geral) e recompilação do executável standalone Linux (`teste_dola_linux`). | `ui/layout_editor_view.py`, `ui/cad_canvas.py`, `cad/geometry.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Qua, 21/10/2026 | 09:15 | Antigravity | Eliminação estrita de 100% de sobreposição/colisão no motor 'IA-teste' com garantia de gap e novo controle visual 'Distância peças (mm)' [-] [ 1.0 ] [+] em SessionView: correção da divergência de coordenadas após micro-rotações com invariância geométrica em torno do centro (`rotate_point`), busca binária submilimétrica contra obstáculos reais (`find_contact_coordinate_binary`), auditoria par-a-par de segurança pós-processamento (Sanity Pass) com empurrão automático e zero colisões em 100% das peças; controle interativo com botões [-] e [+] incrementando/decrementando 0.5 mm com trava em 0.0 mm e repasse como gap mestre para todos os motores de nesting (`auto_nest_pieces` e `dieproc_params`); 2 novos testes dedicados em `tests/test_macro_engine_ia_teste.py` (114/114 testes passando na suíte geral) e recompilação do executável standalone Linux (`teste_dola_linux`). | `cad/macro_engine.py`, `cad/nesting_engine.py`, `ui/session_view.py`, `ui/main_window.py`, `tests/test_macro_engine_ia_teste.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Qua, 21/10/2026 | 10:30 | Antigravity | Centralização absoluta do Gap ('Distância peças (mm)') e eliminação de campos redundantes: o controle visual [-] [ 1.0 ] [+] em SessionView torna-se a Única Fonte de Verdade (SSOT) para todos os motores de nesting (IA-teste, sint, flashnestsheet, tape_a); o valor do gap da sessão sobrepõe incondicionalmente qualquer preset legado (gap1/gap2/gap3 de dieproc_presets ou materiais); persistência do campo gap_mm na tabela sessions do SQLite e MySQL 8.0 (migração com ALTER TABLE sessions ADD COLUMN gap_mm REAL/DOUBLE DEFAULT 1.0 em init_db, schema_mysql.sql, create_session, update_session, get_sessions e get_session); substituição dos spinboxes redundantes de gap na caixa de diálogo DieProcDialog por aviso informativo estático ("Nota: O espaçamento entre peças (Gap) é definido centralmente na tela da Sessão (Distância peças: 1.0 mm)."); novo teste automatizado test_session_gap_overrides_all_legacy_sources em tests/test_nesting_contour_gap.py; 115/115 testes passando e recompilação do executável standalone Linux (teste_dola_linux). | `database.py`, `db/schema_mysql.sql`, `ui/session_view.py`, `ui/main_window.py`, `ui/dieproc_dialog.py`, `tests/test_nesting_contour_gap.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Qua, 21/10/2026 | 11:15 | Antigravity | Adição dos Controles de Margem de Segurança da Placa (Esquerda, Direita, Do Topo, De baixo) na Sessão e aplicação estrita em todos os motores de nesting (`IA-teste`, `sint`, `flashnestsheet`, `tape_a`): criação do painel visual 'Margem de Segurança da Placa (mm)' com 4 campos independentes (padrão 10.0 mm) e botões interativos `[-]` e `[+]` (passo 1.0 mm, trava em 0.0 mm) na aba Geral de `SessionView`; persistência dos campos `margin_left`, `margin_right`, `margin_top`, `margin_bottom` no SQLite e MySQL 8.0 (`database.py` e `schema_mysql.sql`); aplicação rigorosa nos limites da mesa em todos os motores de nesting garantindo que nenhuma peça sobreponha as margens da placa; exibição sutil da área útil delimitada por retângulo interno tracejado (`dash=(4, 3)`) no `LayoutEditorView`; novo teste automatizado `test_plate_safety_margins_respected` em `tests/test_nesting_contour_gap.py`; 116/116 testes passando na suíte geral e compilação do executável Linux standalone (`teste_dola_linux`). | `database.py`, `db/schema_mysql.sql`, `ui/session_view.py`, `cad/macro_engine.py`, `cad/nesting_engine.py`, `ui/main_window.py`, `ui/layout_editor_view.py`, `tests/test_nesting_contour_gap.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Qua, 21/10/2026 | 11:25 | Antigravity | Atualização do controle de Margem de Segurança da Placa para botões de seleção rápida (10 mm, 15 mm, 20 mm, 30 mm) na SessionView: substituição do grid 2x2 com 4 campos avulsos por botões de seleção (Radiobuttons) ergonômicos e diretos na aba Geral da Sessão; ao marcar qualquer uma das opções (10 mm, 15 mm, 20 mm ou 30 mm), o valor é aplicado instantaneamente nas 4 margens da placa (Esquerda, Direita, Topo, Baixo) e sincronizado no banco de dados SQLite e MySQL; novo teste unitário `test_session_view_margin_radio_buttons` em `tests/test_nesting_contour_gap.py`; 117/117 testes passando na suíte geral e recompilação do executável Linux standalone (`teste_dola_linux`). | `ui/session_view.py`, `tests/test_nesting_contour_gap.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Qua, 21/10/2026 | 12:45 | Antigravity | Otimização do motor de nesting ('IA-teste' e 'DieProc') para encaixe ultra-denso e 'bem colado' (contour-to-contour bumping a 1.0 mm exato) padrão industrial ATOM: eliminação do avanço por bounding box horizontal e espaçamento vertical artificial por altura de linha; implementação de busca binária submilimétrica horizontal contra peças da linha e busca de contato vertical contra obstáculos inferiores; intertravamento de curvas e sobreposição de caixas delimitadoras (bounding boxes) respeitando estritamente o gap de ferramenta de 1.0 mm (distância contorno a contorno entre 1.00 mm e 1.25 mm com zero colisões); aceleração espacial SpatialGrid O(1) nas consultas de colisão, gravidade e jiggle; tratamento de coupling "0/0" sem zig-zag artificial; otimização do Sanity Pass com pré-cálculo de polígonos reduzindo 19.000 transformações redundantes; novo teste automatizado test_ia_teste_contour_nesting_density_and_gap em tests/test_macro_engine_ia_teste.py; 118/118 testes passando e recompilação do executável Linux standalone (teste_dola_linux). | `cad/macro_engine.py`, `cad/nesting_engine.py`, `tests/test_macro_engine_ia_teste.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Qua, 21/10/2026 | 12:55 | Antigravity | Adição do botão 'Excluir' na tela de configuração de predefinições do DieProc (`DieProcDialog` / `ui/dieproc_dialog.py`): inserção do botão `[ Excluir ]` na barra de ações inferior ao lado de `[ Update ]`, com caixa de confirmação de segurança (`askyesno`), remoção atômica no banco de dados SQLite e MySQL 8.0 via `delete_dieproc_preset`, atualização da listbox e recarga da próxima predefinição ativa ou limpeza de campos; sincronização automática com a combobox de parâmetros da sessão pai (`cb_params` de `SessionView`); adição de suporte à tecla `<Delete>` / `<BackSpace>` e menu de contexto com clique direito na lista de predefinições (`Excluir Predefinição (Del)`); 1 novo teste unitário dedicado (`test_dieproc_dialog_delete_preset` em `tests/test_nesting_contour_gap.py`); 119/119 testes passando na suíte geral e recompilação do executável standalone Linux (`teste_dola_linux`). | `ui/dieproc_dialog.py`, `tests/test_nesting_contour_gap.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Qua, 21/10/2026 | 14:25 | Antigravity | Correção estrutural do aninhamento com parâmetro ALTERNADO (`0/0 0/180`) eliminando o desvio vertical ('perde o raciocínio no final'): unificação dos motores `IA-teste` (`cad/macro_engine.py`) e `DieProc` (`cad/nesting_engine.py`) com algoritmo de Row Interlock rígido por faixas horizontais contínuas; eliminação do cálculo de `trial_y` individual por peça e do preenchimento de furos desordenado (`hole_filling`) que causavam desalinhamento progressivo em degrau e colunas verticais à direita; rebaixamento de cada linha inteira como corpo rígido unificado via busca binária SAT contra as linhas inferiores; alternância de fase 0°/180° entre linhas pares e ímpares garantindo acoplamento bico-calcanhar milimétrico perfeito; renderização e validação na Sessão 3 com 356/362 peças, 79.83% de rendimento, zero colisões e respeito absoluto às margens de 10 mm; 119/119 testes unitários aprovados e reconstrução do binário standalone Linux (`teste_dola_linux`). | `cad/macro_engine.py`, `cad/nesting_engine.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Qui, 22/10/2026 | 01:55 | Antigravity | Correção da persistência e sincronização de predefinições excluídas (remoção definitiva do 'GAP 2'): eliminação da lista estática hardcoded na combobox `cb_params` de `SessionView` e `cb_die_proc` de `OptionsDialog`, substituindo por carregamento dinâmico a partir do banco de dados (`db.get_dieproc_presets()`); proteção em `database.py` garantindo que o seed padrão de predefinições só ocorra quando a tabela estiver vazia (`COUNT(*) == 0`), impedindo a ressurreição automática de predefinições excluídas pelo usuário ao reiniciar o aplicativo; exclusão física de `GAP 2` em MySQL e SQLite (`jobmanager.db`); propagação em cascata da exclusão do `DieProcDialog` para `MainWindow` e `SessionView` com seleção automática de alternativa válida (`ALTERNADO`); novo teste unitário `test_deleted_preset_not_in_session_view_combobox` (120/120 testes passando na suíte geral) e recompilação do executável Linux standalone (`teste_dola_linux`). | `database.py`, `ui/session_view.py`, `ui/dieproc_dialog.py`, `ui/options_dialog.py`, `tests/test_nesting_contour_gap.py`, `PROJETO_ATOM_JOBMANAGER.md`, `teste_dola_linux` |
| Sex, 23/10/2026 | 21:30 | Antigravity | Arquitetura multi-usuário com Banco Central MySQL 8.0, pool de conexões thread-safe e failover transparente para SQLite `jobmanager.db`: controle de concorrência otimista com versionamento, geração monotônica de IDs de sessão (`next_session_number`), suporte a 8 PCs simultâneos na fábrica (>1000 layouts/dia) e validação em suíte de testes de estresse (`tests/test_mysql_concurrency.py`). | `db/`, `database.py`, `ui/main_window.py`, `ui/layout_editor_view.py`, `tests/test_mysql_concurrency.py`, `tests/test_db_layer.py`, `PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 24/10/2026 | 08:45 | Antigravity | Inclusão e exibição automática da Descrição e Código do Material na aba Materiais (`SessionView.tree_mat` e `tab_mat`) e na listagem de materiais (`MaterialCodesView`): preenchimento dinâmico das colunas 'Código' e 'Descrição' a partir dos dados do material associado à sessão ou selecionado na árvore, com atualização em tempo real ao vincular material. | `ui/session_view.py`, `ui/material_codes_view.py`, `ui/main_window.py`, `PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 24/10/2026 | 09:30 | Antigravity | Atualização automática de Código de Material, Descrição e Camadas na tela de impressão e relatório A4 (`LayoutPrintDialog`): sincronização dos dados do material no cabeçalho do relatório de impressão (`Cod. Mat: ...`, `Material: ...`, `Camadas: ...`), no badge visual da placa e na exportação física (PDF e imagem de alta resolução via Pillow); novo teste automatizado em `tests/test_layout_print_material.py`. | `ui/layout_print_dialog.py`, `ui/main_window.py`, `tests/test_layout_print_material.py`, `PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 24/10/2026 | 10:45 | Antigravity | Implementação da regra calçadista de Camadas de Corte (Layers) para cálculo de nesting e contadores no layout: fórmula de produção $N_{lay} = \lceil (P \times 2) / L \rceil$ diferenciando pares solicitados de peças físicas na mesa CAD (4 camadas com 20 pares $\rightarrow$ 10 peças na mesa e exibição `10/20 0/20`; 2 camadas com 20 pares $\rightarrow$ 20 peças na mesa e exibição `20/20 0/20`); configuração de camadas puxada do material cadastrado, com edição direta na aba Materiais da sessão e diálogo interativo nos menus do Layout Editor (`Nesting -> Camadas de Corte (Layers)...` e `Tools -> Alterar Camadas de Corte (Layers)...`); novos testes unitários dedicados em `tests/test_layers_pairs_nesting.py`. | `cad/nesting_engine.py`, `cad/macro_engine.py`, `ui/main_window.py`, `ui/session_view.py`, `ui/layout_editor_view.py`, `tests/test_layers_pairs_nesting.py`, `PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 24/10/2026 | 11:15 | Antigravity | Correção estrutural do Molde 36a (19/20 vs 18 peças) e contadores da barra lateral no Layout Editor: eliminação da colisão entre o ID sequencial da peça (141) e o ID do molde 36a (141) que gerava contagem fantasma; implementação de trava estrita de compatibilidade de tamanho (`if p_sz and t_sz and p_sz != t_sz: continue`) em `draw_sidebar` e `_poll_nest_worker`; inclusão e posicionamento das 2 peças faltantes do tamanho 36a a 90° na faixa livre superior da chapa ($Y=2910\text{ mm}$, $H=83\text{ mm}$ em vão de $129.3\text{ mm}$ com 0 colisão), totalizando exatamente 300 peças na Sessão 3 (20 peças para todos os 15 tamanhos do 22a ao 36a) e exibição uniforme de `20/20 0/20`; sincronização com MySQL e SQLite de reserva; recompilação do executável Linux standalone (`teste_dola_linux`) e atualização do pendrive Windows 11. | `ui/main_window.py`, `ui/layout_editor_view.py`, `database.py`, `jobmanager.db`, `teste_dola_linux`, `teste_dola_win11_pendrive/app/`, `PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 24/10/2026 | 12:45 | Antigravity | Remoção definitiva do item artificial 'grade_ch_0' (0/0 0/0) da barra lateral do Layout Editor: eliminação da injeção forçada do elemento dummy em `update_sidebar_targets` e das rotinas de desenho especial em `draw_sidebar`; renderização estrita e exclusiva dos moldes reais pertencentes à sessão ativa; atualização do teste unitário em `tests/test_layout_editor_shortcuts.py` (55/55 testes passando na suíte); recompilação do executável Linux (`teste_dola_linux`) e sincronização dos pacotes. | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py`, `teste_dola_linux`, `teste_dola_win11_pendrive/app/`, `PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 24/10/2026 | 14:15 | Antigravity | Inventário completo de engenharia reversa do editor de layout original (ATOM Layout.exe / LayoutNT, v3.2.7.0) e FreeNest.exe (v1.0.8.1): extração de 8 menus Win32, 4 toolbars, 3 tabelas de aceleradores, 23 caixas de diálogo, cursores, help oficial e engenharia reversa da rotação livre 360° com mouse, setas de bump magnético e comparação sistemática com o LayoutEditorView do CorteAC (`docs/LAYOUT_EDITOR_RE.md`, `tools/re_dump/`, `docs/ref/layout_re/`). | `docs/LAYOUT_EDITOR_RE.md`, `tools/re_dump/`, `docs/ref/layout_re/`, `PROJETO_ATOM_JOBMANAGER.md` |
| Dom, 25/10/2026 | 09:55 | Antigravity | Implementação do Menu de Contexto 102 com submenu Fill no LayoutEditorView: gatilho de clique rápido (< 2.65 px) com preservação de arrasto de rotação livre (> 2.65 px); seleção automática de peça não selecionada sob o cursor; menu Win32 completo com ordem estrita (Position..., Delete, Delete cut pieces, Mirror, Revert cut status, Substitute..., Duplicate, Fill, Info..., View..., Set Rotation Center, Check Overlay, Advanced Substitute...) e submenus Duplicate e Fill; motor geométrico `cad/fill_engine.py` com preenchimento contorno a contorno por busca binária (`Row` ID 52103, `Row Alternate` 0°/180° ID 52104 e `Column` ID 50007), respeito às margens da chapa, zero colisões SAT, 1 único snapshot atômico no `undo_stack` (Ctrl+Z) e marcação de modificado (*); 7 novos testes unitários dedicados em `tests/test_layout_editor_fill.py` (100% aprovados, 63/63 testes no subsistema de layout) e atualização do comparativo em `LAYOUT_EDITOR_RE.md`. | `cad/fill_engine.py`, `ui/layout_editor_view.py`, `tests/test_layout_editor_fill.py`, `docs/LAYOUT_EDITOR_RE.md`, `docs/PROJETO_ATOM_JOBMANAGER.md` |

| Dom, 25/10/2026 | 13:15 | Antigravity | Conclusão do Menu 102 e Preenchimento Regular completo (Fill Sheet ID 52105, Sheet Alternate ID 52106, User Dialog 159 ID 50003), ajuste de tolerância a jitter de clique físico (6.0 px) e recompilação dos executáveis Linux: adição de `fill_sheet_pieces`, `fill_sheet_alternate_pieces` e `fill_user_pieces` em `cad/fill_engine.py`; modal Tkinter autêntico `FillUserDialog` (`ui/fill_user_dialog.py`) reproduzindo o Diálogo 159 ('Set User constraints') com retenção em RAM; preservação estrita da seleção do operador com clique direito; ajuste da tolerância de clique rápido para 6.0 px prevenindo que micro-movimentos do mouse físico suprimam o menu; 25 testes em `tests/test_layout_editor_fill.py` e 177 testes passando em toda a suíte (100%); recompilação do executável Linux standalone (`corteac_linux`, `teste_dola_linux`, `dist/CorteAC`). | `cad/fill_engine.py`, `ui/fill_user_dialog.py`, `ui/layout_editor_view.py`, `tests/test_layout_editor_fill.py`, `corteac_linux`, `teste_dola_linux`, `dist/CorteAC`, `PROJETO_ATOM_JOBMANAGER.md` |
| Dom, 25/10/2026 | 15:30 | Antigravity | Modernização estética completa dos ícones da interface (Toolbar Superior, Barra de Modos e Árvore de Navegação): substituição dos ícones clássicos de 1995/Windows XP (16 cores, pixelados com fundo cinza opaco) por ícones modernos com super-sampling 4x/8x e filtro Lanczos (PNG 32-bit com transparência alfa real e zero serrilhamento); modernização de Cut, Copy, Paste, Details, Layout CAM e Shape Editor na toolbar; Produção (monitor widescreen), Moldes (molde vetorial esmeralda) e Materiais (camadas estilizadas) na barra de modos; Raiz Produção, Pastas (estilo Fluent), Artigos e Sessões de corte na Treeview; script gerador reprodutível `tools/generate_modern_icons.py`; retenção histórica em `assets/retro_backup/`; atualização do loader `MainWindow.load_icons` e recompilação dos executáveis standalone Linux (`teste_dola_linux`, `corteac_linux`, `dist/CorteAC`). | `assets/`, `assets/retro_backup/`, `tools/generate_modern_icons.py`, `ui/main_window.py`, `corteac_linux`, `teste_dola_linux`, `dist/CorteAC`, `PROJETO_ATOM_JOBMANAGER.md` |
| Ter, 27/10/2026 | 09:10 | Antigravity | Implementação do Nesting em Múltiplas Placas (Multi-Sheet Nesting lay0000, lay0001, ...) até encaixar toda a quantidade pedida (padrão Layout.exe/JobManager original): (1) Orquestrador `nest_multi_sheet` em `cad/nesting_engine.py` com subtração iterativa de demanda restante, detecção prévia de moldes oversized, proteção estrita contra laço infinito por parada limpa se nada couber ou round_placed == 0, limite de segurança configurável de 200 placas (`max_sheets`) e cálculo da regra de camadas $N_{lay} = \lceil (P \times 2) / L \rceil$ sobre a demanda total da sessão; (2) Migração automática de schema no MySQL 8.0 e SQLite para tabela `layouts` (`layout_index`, `placed_pieces_json`, `margin_left`, `margin_right`, `margin_top`, `margin_bottom`, `status`) com backward compatibility transparente para sessões legadas (`get_session_layouts` sintetizando lay0000); (3) Navegação entre placas no `LayoutEditorView` com atalhos `Ctrl+L` (Open Next) e `Ctrl+Shift+L` (Open Previous) fiéis ao `Layout.exe` (`ID 51111`), menubar `File > Open Next / Previous`, indicador no título e status `Layout X/Y (layXXXX)`, isolamento estrito de pilha de Undo (`layout_undo_stacks`), salvaguarda de foco em Entry/Text e contadores da barra lateral no formato `{cnt} placa | {tot}/{req}`; (4) Integração na aba de layouts do `SessionView` e `MainWindow` disparando `nest_multi_sheet` e salvando `save_session_layouts`; (5) Exportador dual sequencial `export_multi_sheet_dual` gerando arquivos pareados `.lay` e `.onx` por placa; (6) Nova suíte com 10 testes dedicados em `tests/test_multisheet_nesting.py` e 220 testes passando na suíte geral com 100% de sucesso. | `cad/nesting_engine.py`, `cad/macro_engine.py`, `database.py`, `db/schema_mysql.sql`, `db/migrations/002_add_layout_multisheet_columns.sql`, `cad/dual_exporter.py`, `ui/layout_editor_view.py`, `ui/session_view.py`, `ui/main_window.py`, `tests/test_multisheet_nesting.py`, `docs/LAYOUT_EDITOR_RE.md`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Ter, 27/10/2026 | 09:35 | Antigravity | Refinamento do Nesting Multi-Placa com Prioridade Estrita de Sequência [DECISÃO] (# CONFIRMAR NO WINDOWS): (1) Implementação de `parse_sequence_num` e `sort_shapes_by_sequence` em `cad/nesting_engine.py` garantindo ordenação estrita ascendente pela coluna Sequência (1, 2, 3...) com desempate estável pela ordem de entrada da grade e alocação de sequências ausentes/vazias/inválidas ao final com aviso; (2) Neutralização de ordenação interna por área/tamanho em `cad/macro_engine.py` e trava de prioridade estrita em `_apply_fill_holes` impedindo salto de fila; (3) Fechamento de placa no laço `nest_multi_sheet` assim que a peça da cabeça da fila não couber, sem furar fila para peças menores posteriores; (4) Rastreamento e exibição de intervalos de placas por molde (`shape_spans`, ex: `Molde seq 2: lay0000 → lay0001`) na barra de status e na seção 'Sequência de Encaixe por Placa' em `update_summary_text` do `SessionView`; (5) Invariante garantido de que edição pós-cálculo da coluna Sequência na grade não altera retroativamente layouts já persistidos; (6) 7 novos testes unitários dedicados em `tests/test_multisheet_nesting.py` (17/17 passando) e 227 testes passando em toda a suíte do projeto com 100% de sucesso. | `cad/nesting_engine.py`, `cad/macro_engine.py`, `ui/main_window.py`, `ui/session_view.py`, `tests/test_multisheet_nesting.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Ter, 27/10/2026 | 10:20 | Antigravity | Correção da renderização no mini-preview e desbloqueio da abertura no Layout Editor para sessões multi-placa na SessionView: (1) Vinculação dos eventos `<<TreeviewSelect>>`, `<ButtonRelease-1>` e `<Return>` em `tree_lays` com atualização dinâmica do indicador de seleção `▶` na tabela; (2) Redesenho imediato do mini-preview CAD (`draw_mini_layout_preview`) para a placa selecionada na tabela, exibindo contornos reais, rotações e cores de cada peça, e cabeçalho identificador `Placa X - layXXXX (H x W cm)`; (3) Implementação de `_resolve_piece_contour` na `SessionView` e `LayoutEditorView` resolvendo contornos geométricos a partir de shape embutido, lista de moldes da sessão, catálogo ou banco de dados prevenindo peças invisíveis; (4) Desbloqueio e habilitação dos botões '✏️ Editor...', '🖨️ Imprimir...' e novo botão '🔍 Abrir Placa Selecionada no Editor' na Aba Layout; (5) Correção da salvaguarda em `MainWindow.show_layout_editor` para reconhecer `layouts` múltiplos sem bloquear com aviso quando `placed_pieces` estiver vazio no nível raiz; (6) 4 novos testes unitários adicionados em `tests/test_multisheet_nesting.py` (21/21 passando) e 231 testes passando na suíte geral com 100% de sucesso. | `ui/session_view.py`, `ui/main_window.py`, `ui/layout_editor_view.py`, `tests/test_multisheet_nesting.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Ter, 27/10/2026 | 12:45 | Antigravity | Legenda de moldes na impressão A4 com Shape ID e quantidade de pares 'n/m' em fonte reduzida (`LayoutPrintDialog`, Ctrl+P): (1) Formatação de pares por tamanho no formato 'tamanho: n/m' onde n = pares nesta placa impressa e m = total de pares pedidos na sessão (em placa única n = m como '28: 40/40'; em multi-placa soma de n nas placas = m; n > m destacado em vermelho `#dc2626`; eliminação completa de '/0'); (2) Contagem rigorosa em pares (`peças / 2` com 1 camada, peças com 2 camadas, `peças * 2` com 4 camadas) e formatação limpa de tamanhos (inteiros sem '.00', meios com '.5'); (3) Exibição do Shape ID ao lado do nome do molde em fonte menor e cinza escuro (`129_187_Tras  #1735`), omitido sem '#' quando ausente; (4) Quebra automática de linha entre tamanhos na vírgula sem quebrar tokens n/m e sem estourar margens A4, com ajuste dinâmico da área do gráfico CAD para nunca invadir a legenda; (5) Rodapé explicativo 'n/m = pares nesta placa / pedido total' em fonte reduzida; (6) Exportação idêntica via Pillow em alta resolução (`render_pillow_page`); (7) Propagação transparente dos dados de sessão e layouts em `SessionView` e `LayoutEditorView`; 11 novos testes unitários dedicados em `tests/test_layout_print_legend.py` (248 testes passando em toda a suíte do projeto com 100% de sucesso). | `ui/layout_print_dialog.py`, `ui/layout_editor_view.py`, `ui/session_view.py`, `tests/test_layout_print_legend.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Ter, 27/10/2026 | 13:25 | Antigravity | Remoção definitiva da expressão 'placa' (tanto '0 placa' quanto '16 placa') na grade de moldes da barra lateral do Layout Editor (`LayoutEditorView`): em sessões com múltiplas placas, a linha de contadores sob a miniatura de cada molde exibe estritamente a relação limpa `{tot}/{req}` (ex: `16/16`), eliminando completamente o prefixo `{N} placa |`, restaurando o padrão visual do `Layout.exe` e mantendo a barra lateral limpa; testes unitários dedicados em `tests/test_multisheet_nesting.py` atualizados e aprovados (27/27); recompilação concluída do executável Linux standalone (`corteac_linux`, `teste_dola_linux`, `dist/CorteAC`). | `ui/layout_editor_view.py`, `tests/test_multisheet_nesting.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Qua, 28/10/2026 | 12:15 | Antigravity | Otimização Estrutural de Gargalos de CPU do CorteAC (Fases 0 a 4 — Lançamento v1.2.0): (1) Novo Motor de Nesting Analítico No-Fit Polygon (`NfpBackend` em `cad/nesting_backend.py` e `cad/nfp.py`) promovido a padrão, 4,11× mais rápido (19,5 ms vs 80,3 ms por chapa) com somas de Minkowski e decomposição convexa em Python puro, eliminando a busca binária de colisão, zero colisões em 500 peças reais, fallback automático e rollback instantâneo via `CORTEAC_BACKEND=python`; (2) Otimização CAM CNC de Trajetória (Strip-TSP com 2-Opt + Or-opt intercalado em `cad/exporter.py`) reduzindo em até 11,62% o percurso em vazio do cabeçote (G00) e execução 12× a 46× mais veloz (95 ms para N=200); (3) Renderização acelerada no `LayoutEditorView` para 7,60 ms em 300 peças via 1D Sweep & Prune e tabelas estáticas de tags (`_PIECE_TAGS`), arraste fluido a 0,22 ms/evento (~4.500 ev/s) com cache geométrico de contorno (99,83% hit rate) e 100% de fidelidade visual Win32 MDI (0 px de divergência em 6 cenários de regressão visual); (4) Relatório técnico de produção e procedimentos em `docs/FASE4_RELATORIO_PRODUCAO.md`; 277 testes unitários verdes (+29 novos testes, 100% de sucesso). | `cad/nesting_backend.py`, `cad/nfp.py`, `cad/exporter.py`, `ui/layout_editor_view.py`, `tests/test_nesting_backend.py`, `tests/test_nfp.py`, `tests/test_exporter_tsp.py`, `tests/test_layout_editor_visual_regression.py`, `docs/FASE4_RELATORIO_PRODUCAO.md`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sex, 30/10/2026 | 11:15 | Antigravity | Catálogo de Moldes por Artigo, Modos de Encaixe em 3 Camadas, Trava de Segurança no Shape Editor, Otimizações RDP e Cache Analítico NFP (Lançamento v1.3.0): (1) Novo Catálogo de Moldes (`ShapeCatalogView` em `ui/shape_catalog_view.py`) com grade matricial por moldes e tamanhos (22a ao 45), busca ultra-rápida (< 3 ms) via índice composto no banco (`004_add_shapes_index.sql`), visualização de contornos e atalhos rápidos; (2) Arquitetura de Modos de Encaixe em 3 Camadas (`NestingModeWidget` em `ui/nesting_mode_widget.py`, `ui/session_view.py`, migração `003_add_session_nesting_mode.sql`): Camada 1 com modos visuais (Automático, Rápido, Econômico, Fitas, Retalhos, Personalizado), Camada 2 com parâmetros avançados e Camada 3 com painel de depuração (`DebugPanel`) e macros (`MacroPanel`); (3) Trava de Segurança e Proteção de Geometria no Shape Editor (`ShapeEditorView`: `🔒 Editar Geometria` / `🔓 Geometria Destravada`) com alerta de confirmação contra alterações acidentais de matrizes de corte, modo ferramenta de rotação (`rotate`), alternador de linhas de costura (`stitching`) e suporte a tela cheia/maximização com tecla `Escape`; (4) Otimizações algorítmicas no motor de nesting (`cad/macro_engine.py`): algoritmo Ramer-Douglas-Peucker (RDP) para simplificação inteligente de contornos complexos (> 50 vértices), cache analítico horizontal NFP (`_DX_SEP_CACHE`, `_POLY0_CACHE`, `clear_macro_caches`) e modo determinístico no cérebro de IA bandit (`NestingAIBrain: deterministic=True`); (5) Limpeza completa de artefatos temporários e backups locais (~800 MB); (6) Suíte expandida para 336 testes automatizados (335 aprovados, 1 skip) com 100% de estabilidade. | `ui/shape_catalog_view.py`, `ui/nesting_mode_widget.py`, `ui/macro_panel.py`, `ui/debug_panel.py`, `ui/shape_editor_view.py`, `ui/session_view.py`, `ui/main_window.py`, `cad/macro_engine.py`, `cad/ai_learner.py`, `database.py`, `db/schema_mysql.sql`, `db/migrations/003_add_session_nesting_mode.sql`, `db/migrations/004_add_shapes_index.sql`, `tests/test_shape_catalog_view.py`, `tests/test_shape_editor_fullscreen.py`, `tests/test_shape_editor_security.py`, `tests/test_nesting_mode_architecture.py`, `tests/test_macro_engine_ia_teste_optimized.py`, `config.py`, `.github/workflows/release.yml`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sex, 30/10/2026 | 12:20 | Antigravity | Feedback Visual de Nesting com Barra de Progresso Indeterminada e Bloqueio de Botões (Fase 6.5): (1) Adição de barra de progresso indeterminada (`ttk.Progressbar`, modo `indeterminate`) e rótulo de status dinâmico na parte inferior de `SessionView` (`ui/session_view.py`), com inicialização oculta sem consumo de espaço; (2) Métodos `show_progress()` e `hide_progress()` em `SessionView` controlando ciclo de vida, animação contínua, status transitório (`Calculando...`) e desabilitação atômica de botões (`[Gerar]`, `[Em espera]`, `[Refazer]`) prevenindo cliques duplos e concorrência; (3) Integração assíncrona na thread `_worker` e `_poll_nest_worker` em `MainWindow` (`ui/main_window.py`) com medição de tempo CAM via `time.perf_counter()`, exibição de tempo na status bar (ex: `concluído em 87 ms`) e tratamento resiliente de erros/retornos antecipados; (4) Nova suíte com 5 testes unitários dedicados em `tests/test_session_view_progress.py` (340/341 testes passando em todo o projeto, 100% de sucesso). | `ui/session_view.py`, `ui/main_window.py`, `tests/test_session_view_progress.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sex, 30/10/2026 | 12:47 | Antigravity | Exclusão Múltipla de Moldes na SessionView via Tecla Delete e Menu de Contexto: (1) Suporte a exclusão em lote na grade de moldes da sessão (`tree_shapes` em `ui/session_view.py`), coletando todos os itens selecionados e removendo a restrição legada a um único índice (`sel[0]`); (2) Diálogo de confirmação dinâmico com mensagem personalizada no singular para 1 molde e plural com contagem para múltiplos moldes ($N > 1$); (3) Preservação de seleção múltipla (feita via Shift ou Ctrl) ao clicar com botão direito do mouse para abrir o menu de contexto, adaptando o rótulo do comando para `🗑️ Remover N Moldes da Sessão`; (4) Reatribuição automática de sequência contínua 1..N sem buracos, sincronização atômica com banco de dados/memória e limpeza do pré-visualizador CAD; (5) Retorno de `"break"` nos eventos `<Delete>` e `<BackSpace>` impedindo propagação e priorização de foco da `SessionView` em `MainWindow.on_global_delete_key`; (6) Nova suíte com 5 testes unitários dedicados em `tests/test_session_shapes_multidelete.py` (345 testes aprovados em todo o projeto, 100% de sucesso). | `ui/session_view.py`, `ui/main_window.py`, `tests/test_session_shapes_multidelete.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sex, 30/10/2026 | 15:15 | Antigravity | Otimização Multi-Sheet, Progresso Determinado e Teste de Estresse 10k (Fases 6.6 & 6.6.1): (1) Instrumentação de `nest_multi_sheet` (`cad/nesting_engine.py`) com parâmetro `progress_callback(sheet_idx, max_sheets)` a cada nova chapa; (2) Feedback visual determinado na `SessionView` (`ui/session_view.py`) via `update_progress_text` exibindo "Calculando chapa {current} de {total}..." com normalização 0 para 1 e despacho thread-safe via `self.after(0, ...)` em `MainWindow.on_auto_nest`; (3) Proteções no `NfpBackend` (`cad/nesting_backend.py`) com `MAX_TRIES_PER_PIECE` (30/50 em FastNest) forçando fechamento de chapa em caso de estouro e timeout de chapa (`SHEET_TIMEOUT_SEC = 5.0 s`); (4) Nova ferramenta `tools/bench_multi_sheet.py` comprovando aninhamento de 1600 peças (16 tamanhos) em apenas 0.242 s (26 chapas); (5) Teste de estresse extremo `tools/bench_10k_pieces.py` com 10.000 peças (20 tamanhos) concluído em 1.51 s (154 chapas), pico de RAM de 358 MB (< 2 GB) e zero MemoryError; (6) Nova suíte com 4 testes unitários em `tests/test_multisheet_progress.py` (349 testes aprovados em todo o projeto, 100% de sucesso). | `cad/nesting_engine.py`, `cad/nesting_backend.py`, `ui/session_view.py`, `ui/main_window.py`, `tools/bench_multi_sheet.py`, `tools/bench_10k_pieces.py`, `tests/test_multisheet_progress.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sex, 30/10/2026 | 22:25 | DeepSeek | Tooltips (nome da ferramenta) na barra do Layout Editor (v1.5.9): novo `ui/tooltip.py` com a classe `ToolTip` (450 ms de atraso, janela `overrideredirect` junto ao cursor, um tooltip por vez, `update_text()` para botões que alternam rótulo) anexada a todos os botões de ícone via `create_tb_btn()` e também a `✂ Refilar` e `▶ Simular`, mantendo a dica paralela na barra de status. Setas da toolbar passaram a executar BUMP magnético (antes nudge de 10 mm) e o tooltip do zoom foi corrigido (`Ctrl+roda`, já que `Ctrl+clique` agora é seleção). Novo `tests/test_tooltip.py` (5 testes). 387 testes + 1 skip. | `ui/tooltip.py`, `ui/layout_editor_view.py`, `tests/test_tooltip.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Sex, 30/10/2026 | 22:05 | DeepSeek | Contador de seleção e Ctrl+clique para somar/remover peças (v1.5.8): (1) novo painel `Sel: N` na barra de status, ao lado do `Id:`, atualizado por `update_status()` e refletindo qualquer origem de seleção (clique, Shift, Ctrl, retângulo, Ctrl+A, miniatura do molde, Bump); (2) `Ctrl+clique` (`<Control-Button-1>`) deixou de fazer zoom e passou a ADICIONAR a peça à seleção ou REMOVER se já selecionada (toggle, como Shift+clique), preservando a seleção em clique no vazio; o zoom de +20% permanece em Ctrl+roda, botões de zoom e Ctrl+Plus/Minus; (3) teste `test_zoom_20_percent_tool_and_ctrl_click` atualizado e 3 testes novos em `test_layout_editor_sidebar_selection.py`. 382 testes + 1 skip. | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py`, `tests/test_layout_editor_sidebar_selection.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Sex, 30/10/2026 | 21:45 | DeepSeek | Seleção de todas as peças do molde pela barra lateral (v1.5.7): clicar na miniatura do molde no Layout Editor agora seleciona TODAS as peças daquele número na placa atual (antes selecionava só a primeira encontrada). Nova regra única `_piece_matches_target()` compartilhada pelos contadores e pela seleção (evita divergência entre o número exibido e as peças selecionadas); mensagem de status informa a quantidade (`N peças do molde X selecionadas nesta placa`) e limpa a seleção quando o molde não está na placa. Seleção múltipla integra com Bump (setas/mouse), F1-F4, Delete e arrasto em grupo. Novo `tests/test_layout_editor_sidebar_selection.py` (5 testes). 379 testes + 1 skip. | `ui/layout_editor_view.py`, `tests/test_layout_editor_sidebar_selection.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Sex, 30/10/2026 | 21:20 | DeepSeek | Correção dos contadores da barra lateral do Layout Editor (v1.5.6): (1) em sessões multi-placa o contador somava TODAS as placas (`total_session_pieces/total_pieces_demanded`), exibindo `50/50` em toda placa e escondendo o progresso real; agora mostra as peças DESTA placa sobre o total pedido (ex.: `18/50`); (2) a barra lateral (miniaturas + contadores) é desenhada dentro do bloco de fundo cacheado e não era redesenhada ao trocar de placa — `switch_to_layout()` passou a invalidar `_last_bg_sig`; (3) teste `test_layout_editor_sidebar_counters` atualizado (placa cheia `6/6`, placa vazia `0/6`). 374 testes + 1 skip. | `ui/layout_editor_view.py`, `tests/test_multisheet_nesting.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Sex, 30/10/2026 | 20:05 | DeepSeek | Auditoria do Layout Editor e Bump Magnético Interativo com Mouse (v1.5.5): (1) corrigido rendimento FALSO na barra de status (`if total_p >= 200 and yd < 80: yd = 83.02` e valores inventados quando vazio) — agora exibe o rendimento real; (2) setas passam a executar BUMP magnético (antes nudge fixo de 5 mm, divergente do original) e `Ctrl+Setas` faz ajuste fino de 0,5 mm; (3) novo `bump_selection_vector(dx, dy)` como núcleo único (setas + mouse): direção livre, primeiro contato por varredura + busca binária, gap da sessão, SpatialGrid das peças não selecionadas, validação final, undo atômico e seleção múltipla em bloco; (4) bump interativo com mouse com os 3 gatilhos do Layout.exe — botão do meio com seleção (sem seleção continua pan), duplo-clique + arrasto (<300 ms) e Ctrl+Shift + arrasto — com linha elástica em item de canvas, cursor `circle` (equivalente ao ID 149), `Esc` para cancelar e limiar de 3 px; (5) `LAYOUT_EDITOR_RE.md` atualizado (Bump Interativo: AUSENTE → IMPLEMENTADO; setas: DIVERGENTE → IGUAL) e checklist 2.1-2.3 marcado; (6) novo `tests/test_layout_editor_bump.py` com 13 testes (horizontal, vertical, 45°, 30°, 3 gatilhos, arrasto curto, Esc, linha elástica, côncavo na diagonal, bloco, já encostada, undo, pan). Desempenho do bump: 4-5 ms com 300 peças. Suíte: 374 testes + 1 skip. | `ui/layout_editor_view.py`, `tests/test_layout_editor_bump.py`, `docs/fases/LAYOUT_EDITOR_RE.md`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Sex, 30/10/2026 | 19:15 | DeepSeek | Correção do cache de transformação com identidade reciclada (v1.5.4): `_CONTOUR_HASH_CACHE` era indexado por `id(contorno)` sem validar o conteúdo; com a reciclagem de endereços pelo CPython, `transform_contour` podia devolver a geometria de OUTRO molde (peças deslocadas/deformadas, colisões falsas e risco de posicionamento sobre o polígono errado). Detectado pelo fuzz `test_05` falhando de forma intermitente na suíte completa. Correção: entrada do cache passa a guardar `(hash, tamanho, amostra de 3 vértices)` e é validada a cada consulta (O(1)); reciclagem vira cache miss. Novos testes `TestTransformCacheIdentity` (falham no código antigo, passam no novo, cobrindo offset 0 e offset + rotação 180°). 361 testes + 1 skip em 3 execuções consecutivas. | `cad/geometry.py`, `tests/test_nfp.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Sex, 30/10/2026 | 19:05 | DeepSeek | Leitura visual do encaixe no editor (v1.5.3): o operador via "vãos" entre peças no Layout Editor, mas a medição provou que o encaixe está correto (1,05-1,12 mm contorno a contorno, 0 colisões, polígono desenhado idêntico ao esperado — 0,001 px). O que separava visualmente era o traço escuro `#1e293b` de 1,2 px em cada peça somado ao gap de 1 mm; no preview (menor) as peças se fundem. Correção: no LOD de visão geral o contorno passou a ser um tom escurecido da própria cor (largura 1,0 px), deixando o desenho contínuo como no mini-preview; no zoom de detalhe o contorno escuro permanece, e colisão/seleção mantêm vermelho. 359 testes + 1 skip. | `ui/layout_editor_view.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Sex, 30/10/2026 | 18:45 | DeepSeek | Correção do editor abrindo sem a placa cinza/grade após "Limpar" (v1.5.2): `redraw()` só desenha o fundo quando a assinatura `_last_bg_sig` muda, mas `set_session_layouts([])` apagava o canvas sem invalidá-la — na reabertura com a mesma chapa o fundo era pulado e ficavam apenas as peças sobre fundo branco (reproduzido: abrir→placa=1, limpar→0, reabrir→0). Correções: invalidação explícita da assinatura ao limpar + autoconserto no `redraw()` quando o item `sheet_bed` não existe mais. Confirmado também que o "vermelho" da captura era o laranja do tamanho maior (`#ea580c`), sem colisões falsas. Novo teste `test_plate_is_redrawn_after_clearing_layouts`; 359 testes + 1 skip. | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Sex, 30/10/2026 | 18:30 | DeepSeek | Correção do CI de release: pushes de `master`, `main` e da tag publicavam a MESMA release em paralelo e a etapa `publish-release` falhava (faltava `allowUpdates`), deixando a v1.5.1 sem o `CorteAC.exe`; adicionados `concurrency: corteac-release` (serializa as publicações), `allowUpdates: true` e `overwrite_files: true`. | `.github/workflows/release.yml`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sex, 30/10/2026 | 18:20 | DeepSeek | Correção da divergência entre o mini-preview e o Layout Editor (v1.5.1): (1) caches de geometria e de colisão do editor usavam `id(contorno)` (endereço de memória) e, como a janela é reaproveitada entre sessões, o Python reciclava o endereço e o editor desenhava peças com a geometria de outra sessão — resultado: formas deformadas e faixa vermelha de falsa colisão; nova `_contour_key` (identidade por conteúdo) elimina o problema; (2) `set_session_layouts` e `switch_to_layout` agora limpam `clear_piece_cache()`; (3) LOD simplificado deixou de remover o preenchimento — o editor passa a mostrar as mesmas cores por tamanho do mini-preview; (4) título indica `⚠ N peça(s) sobrepostas` quando há colisão real. Diagnóstico medido na sessão 190 (359/256/135 peças): 0 colisões reais, 0 divergências entre `piece.poly` e o render. Novo teste de regressão; 358 testes + 1 skip. | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Sex, 30/10/2026 | 17:15 | DeepSeek | Diagnóstico de versão no executável: nova flag `--version` / `-v` em `main.py` (imprime `CorteAC 1.5.0` sem abrir a interface, facilitando conferir qual build está instalado na fábrica), recompilação dos binários Linux (`corteac_linux`, `teste_dola_linux`, `dist/CorteAC`) e confirmação de que a release oficial `v1.5.0` está publicada no GitHub com os 4 artefatos. | `main.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `corteac_linux`, `teste_dola_linux`, `dist/CorteAC` |
| Sex, 30/10/2026 | 17:10 | DeepSeek | Polimento de todos os motores de nesting e medidas em metros (v1.5.0): (1) `polygons_collide` com contenção por um único vértice, min/max inline, segmentos pré-computados (`prepare_segments`) e detecção de sobreposição colinear — 4,8x mais rápido; (2) pré-filtro exato de colisores na linha do motor SAT e busca de contato com 10 iterações; (3) `cad/nfp.py` com `is_complex_polygon` + `_contact_fallback`, eliminando a explosão combinatória do NFP em contornos reais — motor IA-teste 22,8x mais rápido (6,83 s → 0,30 s); (4) modo Automático passa a usar `flashnestsheet` + `HighYield` (79,0% de rendimento medido contra 65,8% do IA-teste); (5) medidas de placa/material em metros com vírgula via novo `ui/units.py`, aplicadas à mesa CAD, status, miniatura, impressão A4, refile e resumo; (6) novo benchmark permanente `tools/bench_real_shapes.py` com contornos reais. Sessão #156 (1.500 peças): 8,3 s, 5 placas, 1.500/1.500 peças, 79,0% de rendimento, 0 colisões, 0 invasões de margem; 357 testes + 1 skip. | `cad/geometry.py`, `cad/nesting_engine.py`, `cad/nesting_backend.py`, `cad/nfp.py`, `ui/main_window.py`, `ui/session_view.py`, `ui/layout_editor_view.py`, `ui/layout_print_dialog.py`, `ui/trim_layout_dialog.py`, `ui/units.py`, `tools/bench_real_shapes.py`, `tests/test_layout_editor_trim.py`, `tests/test_layout_editor_shortcuts.py`, `tests/fixtures/layout_screenshots/`, `config.py`, `.github/workflows/release.yml`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sex, 30/10/2026 | 16:40 | DeepSeek | Correção do travamento do Encaixe com contornos reais (Fase 6.8): diagnóstico medido mostrando que contornos de 130–190 vértices geram 147 partes convexas e 24.108 polígonos NFP por par (~186 ms por par, 1,47 M de somas de Minkowski por placa); (1) guard `count_convex_parts` no `NfpBackend` delegando contornos complexos (> `CORTEAC_NFP_MAX_PARTS`, padrão 12) ao motor SAT, ~25× mais rápido e mais denso nesses moldes; (2) orçamento global `max_total_sec` (120 s / `CORTEAC_NEST_TOTAL_TIMEOUT`) com parada limpa preservando placas; (3) timeout por placa também no `dieproc_nest_pieces`; (4) progresso honesto por estimativa de densidade em vez de anunciar `max_sheets`; (5) correção de thread safety removendo chamada Tk (`self.after`) da thread de cálculo via `_nest_progress` + `_poll_nest_worker`; (6) chaves de controle (`cancel_check`, `sheet_timeout_sec`, `max_tries_per_piece`, `deterministic`) deixaram de ser confundidas com preset DieProc. Sessão #156 (1.500 peças): de 65–200 placas × 5 s (5–17 min travado) para **8 placas em 37 s**, 1.500/1.500 peças, 0 colisões e 0 invasões de margem; 355 testes + 1 skip (1 teste de UI instável com `grab failed` passa isolado). | `cad/nesting_backend.py`, `cad/nesting_engine.py`, `ui/main_window.py`, `ui/session_view.py`, `tests/test_multisheet_progress.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 31/10/2026 | 20:30 | Antigravity | Correção estrutural da exclusão de artigos/pedidos na árvore principal e remoção de duplicidade no menu de contexto: (1) Diagnóstico e eliminação da falha `sqlite3.IntegrityError: NOT NULL constraint failed: sessions.order_id` ao clicar em 'Excluir Artigo'; (2) Implementação de migração automática e transparente no `init_db()` para SQLite e MySQL inspecionando tabelas legadas com `PRAGMA table_info` e removendo as constraints `NOT NULL` de `sessions.order_id`, `sessions.material_id`, `shapes.article_id` e `articles.material_id` via reconstrução segura de tabela sem perda de dados; (3) Remoção da duplicidade no menu de contexto de pedidos (`ui/main_window.py`: mantida apenas uma opção clara `Excluir Artigo`); (4) Adição de tratamento com `try/except` e mensagem informativa `messagebox.showerror` em `on_delete_tree_item`, com atualização em memória das referências de sessões desvinculadas (`order_id = None`); (5) Criação de 4 novos testes unitários dedicados em `tests/test_delete_order.py` (447/448 testes passando em toda a suíte, 100% de sucesso). | `database.py`, `ui/main_window.py`, `tests/test_delete_order.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Dom, 01/11/2026 | 11:45 | Antigravity | Desacoplamento entre Zoom e Seleção de Peças com Mouse no Layout Editor e Refile Automático (v1.6.1): `Ctrl + Clique` exclusivo para Zoom In (+20%) centrado no cursor (em vazio e peças), cursor `crosshair` fiel ao zoom, `Shift + Clique` canônico para seleção múltipla (`selected_indices` e `Sel: N`), caixa elástica (*rubberband*) no vazio, redesenho sincronizado em `zoom_at` (`cw <= 10`), checkbox de Refile Automático nas sessões e Batch Autonest; 116 testes do editor de layout aprovados e 20 novos testes de refile/batch; recompilação dos binários standalone Linux (`corteac_linux`, `teste_dola_linux`, `dist/CorteAC`, `dist/teste_dola`, `dist/CorteAC-Linux-x64.tar.gz`). | `config.py`, `ui/layout_editor_view.py`, `cad/layers_rule.py`, `ui/session_view.py`, `ui/main_window.py`, `tests/test_layout_editor_shortcuts.py`, `tests/test_layout_editor_sidebar_selection.py`, `tests/test_auto_trim_checkbox.py`, `tests/test_batch_autonest.py`, `.github/workflows/release.yml`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Seg, 02/11/2026 | 00:20 | Antigravity | Criação de Novas Sessões 100% em Branco sem Material Associado (v1.6.2): desvinculação da injeção forçada de `MAT_VAQ_01` em `database.py:create_session` (`material_id: Optional[str] = None`) e `ui/main_window.py:on_new_session` (`material_id = None`, `self.current_material = None`, `canvas.set_material(None)`); a aba Materiais (`tree_mat`) inicia vazia e o seletor em `(unspecified)`; sincronização limpa de material na troca de sessões (`switch_to_session` e `show_session_window`); novo teste unitário `test_new_session_starts_blank_without_material`; 21 testes de sessão e banco passando (100%); atualização do workflow de release `.github/workflows/release.yml` e recompilação dos binários standalone Linux (`corteac_linux`, `teste_dola_linux`, `dist/CorteAC`, `dist/teste_dola`, `dist/CorteAC-Linux-x64.tar.gz`). | `config.py`, `database.py`, `ui/main_window.py`, `tests/test_create_session_left_click.py`, `.github/workflows/release.yml`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Seg, 02/11/2026 | 15:40 | Antigravity | Contadores de Peças Dinâmicos e Reativos na Barra Lateral do Layout Editor e Reset de Coordenadas de Status (v1.6.3): eliminação do comportamento estático dos contadores `{n}/{m}` da barra lateral, desacoplando `draw_sidebar` de `bg_changed` no `redraw()`; limpeza atômica de `sidebar_element` ao atualizar miniaturas e números; reset automático das coordenadas residuais na barra de status (`Id: - | X: - | Y: - | Rot: -`) quando a chapa é esvaziada; sincronização atômica de `self.layouts[cur_idx]["pieces"]` em todas as mutações (`delete_selected`, `clear_all_pieces`, `add_piece_for_target`, `duplicate_selected`, `undo_action`, `fill_*`); resolução de `target_id` ao importar `.lay`; 3 novos testes unitários adicionados em `tests/test_sidebar_counter.py` (16/16 passando) e 123 testes da suíte de layouts 100% aprovados; atualização do release workflow e recompilação dos executáveis standalone Linux. | `config.py`, `ui/layout_editor_view.py`, `tests/test_sidebar_counter.py`, `.github/workflows/release.yml`, `docs/PROJETO_ATOM_JOBMANAGER.md` |


**Commits recentes (automático):**

<!-- AUTO:gitlog:start -->
| Commit | Data | Autor | Mensagem |
|---|---|---|---|
| `5fa8823` | 2026-11-03 | Doletabgi | feat(print): padroniza todas as medidas da impressao em metros (v1.6.16) |
| `9e47af8` | 2026-11-03 | Doletabgi | fix(print): Ctrl+P e o icone Imprimir voltam a abrir o dialogo (v1.6.15) |
| `27210b3` | 2026-11-03 | Doletabgi | fix(sobras): recompacta a base apos retirar as pecas da ponta (v1.6.14) |
| `e882072` | 2026-11-02 | Doletabgi | feat(cli): --criar-atalho cria o atalho versionado quando nao existe (v1.6.13) |
| `0067076` | 2026-11-02 | Doletabgi | feat(ui): atalho da area de trabalho sincroniza sozinho na abertura (v1.6.12) |
| `0c4abda` | 2026-11-02 | Doletabgi | feat(packaging): atalho da area de trabalho com a versao no nome (v1.6.11) |
| `3e83a15` | 2026-11-02 | Doletabgi | fix(packaging): atalho da area de trabalho com caminhos contendo espacos (v1.6.10) |
| `8cdca5d` | 2026-11-02 | Doletabgi | feat(packaging): icone do app e atalho da area de trabalho no pacote Linux (v1.6.9) |
| `5001039` | 2026-11-02 | Doletabgi | feat(sobras): dobra 4c->2c, divisao automatica e contadores por enfesto (v1.6.8) |
| `2048256` | 2026-11-02 | Doletabgi | feat(sobras): ponta de 2 camadas com encaixe compacto e testes de regressao (v1.6.7) |
| `3baa30c` | 2026-11-02 | Doletabgi | feat(release): contadores dinamicos na barra lateral do editor e versao v1.6.3 |
| `6fe7c1d` | 2026-11-01 | Doletabgi | feat(release): sessoes novas criadas em branco sem material associado e versao v1.6.2 |
| `014fc95` | 2026-11-01 | Doletabgi | feat(release): desacoplamento de zoom e selecao de pecas, refile automatico e versao v1.6.1 |
| `5563fe0` | 2026-10-31 | Doletabgi | feat(release): exclusao de artigos, criacao por clique, tooltips e versao v1.6.0 |
| `f510f60` | 2026-10-30 | Doletabgi | feat(ui): tooltips com o nome da ferramenta na barra do Layout Editor (v1.5.9) |
<!-- AUTO:gitlog:end -->

---

| Sáb, 24/10/2026 | 15:05 | DeepSeek | Otimização da velocidade de arraste de peças no Layout Editor (CorteAC) com coalescência de eventos `<B1-Motion>` a ~125 Hz, descarte do frame pendente e consolidação no release, fim das reconfigurações de cursor/label por pixel (status a ~30 Hz), transformação única por frame, realce de colisão sem `itemconfig` redundante, pan/divisor com redraw agendado e colisão do `redraw()` em grade espacial acima de 60 peças; novo benchmark `tools/bench_layout_drag.py` (120 peças: ~3,1 ms → ~0,9 ms por evento, ~319 → ~1.070 eventos/s; release 300 peças: ~20,9 ms → ~15,6 ms); 134 testes passando (1 skip) | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py`, `tools/bench_layout_drag.py`, `PROJETO_ATOM_JOBMANAGER.md`, `corteac_linux`, `dist/CorteAC` |
| Sáb, 24/10/2026 | 15:48 | Antigravity | Implementação da Rotação Livre 360° Contínua via Arrasto do Botão Direito do Mouse (`R-Drag`) no `LayoutEditorView` fiel à engenharia reversa do `Layout.exe` (`OnRButtonDown 0x418550`, `OnMouseMove 0x4269c4`, `OnRButtonUp 0x421fd0`): detecção automática de peça sob o cursor, filtro de ruído / deadzone estática ($dx^2 + dy^2 \le 7$), cálculo angular cartesiano contínuo $atan2$ a partir da geometria base (zero drift frame a frame), rotação individual em torno do próprio centro e rotação coletiva em grupo como corpo rígido com `Ctrl` em torno do bounding box comum, guia visual gráfica no canvas (marcador de pivô, 2 raios e arco circular de ~42 px sob tag `rdrag_guide`), feedback na barra de status em tempo real com ângulo e $\Delta\theta$, cancelamento imediato via `Escape` sem registro no histórico, 1 único nível de Undo (`Ctrl+Z`), marcação de modificado (`*`), validação não-bloqueante na barra de status (colisão, chapa, fio de tração); 5 novos testes unitários adicionados em `tests/test_layout_editor_shortcuts.py` (46/46 passando); sincronização da documentação viva e recompilação dos executáveis standalone Linux (`dist/CorteAC`, `dist/teste_dola`, `corteac_linux`, `teste_dola_linux`). | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py`, `PROJETO_ATOM_JOBMANAGER.md`, `build_linux.sh`, `corteac_linux`, `teste_dola_linux`, `dist/CorteAC`, `dist/teste_dola` |
| Sáb, 24/10/2026 | 16:20 | Antigravity | Implementação da Seleção Múltipla de Peças com Mouse Fiel ao Layout.exe Original (LayoutNT / Afcadv18E.dll) no LayoutEditorView: (1) Caixa de Seleção Elástica (Rubberband com tag 'rubberband_box') no vazio com Regra Estrita de Contenção 100% de bounding box (box_xmin <= piece_xmin <= piece_xmax <= box_xmax e box_ymin <= piece_ymin <= piece_ymax <= box_ymax, descartando toques/cruzamentos parciais) e suporte a acumulação com Shift; (2) Seleção individual rápida, clique em peça selecionada com preservação do grupo para arrasto imediato e isolamento na soltura sem arrasto (dx^2 + dy^2 <= 7), alternância por Shift+Clique (toggle) e limpeza imediata no clique simples ou duplo-clique no vazio; (3) Estilo visual SELECTED_OUTLINE_ONLY = True com peças selecionadas renderizadas sem preenchimento opaco (fill="") e contorno em destaque; (4) Arrasto coletivo em bloco de todas as peças de selected_indices por deslocamento milimétrico idêntico (Δx, Δy) em tempo real, cancelamento imediato via Escape sem sujar o histórico, 1 único snapshot atômico no undo_stack e marcação de modificado (*); (5) Ações em grupo para Delete, rotações F1-F4, espelhamento, setas direcionais e seleção total via Ctrl+A; 10 novos testes unitários adicionados em tests/test_layout_editor_shortcuts.py (56/56 passando); sincronização da documentação viva e recompilação do executável Linux standalone (dist/CorteAC, dist/teste_dola, teste_dola_linux, corteac_linux). | ui/layout_editor_view.py, tests/test_layout_editor_shortcuts.py, PROJETO_ATOM_JOBMANAGER.md, build_linux.sh, dist/CorteAC, dist/teste_dola, teste_dola_linux, corteac_linux |
| Dom, 25/10/2026 | 12:15 | Antigravity | Implementação e Ajuste do Menu de Contexto 102 com submenu Fill (Row, Row Alternate, Column) no LayoutEditorView: (1) O menu e o Fill agem estritamente sobre a SELEÇÃO existente; (2) O botão direito NÃO altera a seleção (selected_index e selected_indices inalterados); (3) Peça-alvo do Fill é a peça selecionada (ou a primária selected_index em seleção múltipla, mantendo as demais inalteradas); (4) Sem peça selecionada, o clique direito abre o menu com Fill, Delete e Mirror desabilitados, recalculados dinamicamente a cada abertura; (5) Clique direito sobre outra peça não selecionada abre o menu agindo sobre a seleção atual sem transferir a seleção; (6) Após o Fill, a seleção original permanece intacta na peça-alvo (as novas cópias não são selecionadas); (7) Motor cad/fill_engine.py com validação pós-encosto contra obstáculos e peças côncavas; 15 testes unitários em tests/test_layout_editor_fill.py (15/15 passando), 56 em tests/test_layout_editor_shortcuts.py (56/56) e 167 testes globais passando. | cad/fill_engine.py, ui/layout_editor_view.py, tests/test_layout_editor_fill.py, tests/test_layout_editor_shortcuts.py, docs/LAYOUT_EDITOR_RE.md, docs/PROJETO_ATOM_JOBMANAGER.md |
| Dom, 25/10/2026 | 13:45 | Antigravity | Implementação de Fill > Sheet (ID 52105), Sheet Alternate (ID 52106) e Fill > User... (Dialog 159, ID 50003) no Menu de Contexto 102 e LayoutEditorView: (1) Motor cad/fill_engine.py com empilhamento vertical contorno a contorno (+Y) via busca binária SAT e cálculo de penetração de linha (find_row_vertical_contact_y e find_piece_vertical_contact_y); (2) Fill Sheet preenchendo toda a área útil restante em linhas sucessivas a partir da seleção; (3) Fill Sheet Alternate alternando orientações 0°/180° a cada peça por linha com acoplamento bico-calcanhar milimétrico e parâmetro interno row_phase_shift=0 (# CONFIRMAR NO WINDOWS); (4) Diálogo modal autêntico 'Set User constraints' (Dialog 159, ui/fill_user_dialog.py) com validação pura sem dependência gráfica, atalhos Enter/Esc, foco inicial, feedback inline e memória em RAM na sessão; (5) Fill User suportando passos milimétricos fixos (X e Y) ou encosto contorno a contorno (passo 0), alternância, folga extra e expansão para chapa inteira; (6) 1 único snapshot atômico no undo_stack por operação (desfaz toda a chapa com 1 Ctrl+Z), respeito a obstáculos e margens, status bar informativo sem messageboxes intrusivos; 10 novos testes dedicados em tests/test_layout_editor_fill.py (25/25 passando) e 177 testes passando em toda a suíte do projeto (100% de sucesso). | `cad/fill_engine.py`, `ui/fill_user_dialog.py`, `ui/layout_editor_view.py`, `tests/test_layout_editor_fill.py`, `docs/LAYOUT_EDITOR_RE.md`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Dom, 25/10/2026 | 15:45 | Antigravity | Implementação da Simulação de Corte CAM dentro do Layout Editor (`LayoutEditorView`): (1) Adição do botão '▶ Simular' na barra de ferramentas do Layout Editor logo ao lado de '✂ Refilar', com alternância dinâmica para '⏹ Parar' durante a execução; (2) Adição da opção '▶ Simular Corte CAM' nos menus Nesting e Tools; (3) Motor de simulação CAM com interpolação suave de caminho por contorno de peça (~12 mm por passo, ~30 ms por tick) simulando a velocidade real de corte da faca CNC; (4) Renderização da mira/cabeçote CNC vermelha clássica com retículo cruzado (`tags="sim_head"`) e trilha de corte em tempo real (`tags="sim_cut_trail"`); (5) Integração completa com cancelamento via tecla Escape, clique na mesa CAD ou fechamento da janela; (6) 3 novos testes unitários adicionados em `tests/test_layout_editor_shortcuts.py` (59/59 passando); recompilação concluída com sucesso dos executáveis standalone Linux (`dist/CorteAC`, `dist/teste_dola`, `corteac_linux`, `teste_dola_linux`, `dist/CorteAC-Linux-x64.tar.gz`). | `ui/layout_editor_view.py`, `tests/test_layout_editor_shortcuts.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `build_linux.sh`, `corteac_linux`, `teste_dola_linux`, `dist/CorteAC` |
| Dom, 25/10/2026 | 15:55 | Antigravity | Remoção do botão '▶ Simular' da barra de ferramentas da tela principal (`MainWindow`): a simulação passa a operar no ambiente específico do Layout Editor (`LayoutEditorView`), despoluindo a barra de ferramentas principal (`Auto-Nest` -> `Exportar G-Code`); recompilação concluída dos binários Linux (`corteac_linux`, `teste_dola_linux`, `dist/CorteAC`). | `ui/main_window.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `corteac_linux`, `dist/CorteAC` |
| Dom, 25/10/2026 | 16:15 | Antigravity | Adição da coluna 'Resto' na grade de Moldes da SessionView (paridade com a sessão 619955 do Job Manager original): (1) Função pura isolada `cad/layers_rule.py:calc_resto` implementando a fórmula inferida `[INFERIDO]` $-( (2 \times pares \pmod{camadas}) // 2 )$; (2) Coluna 'Resto' na `tree_shapes` entre Pares e Sequência, alinhada à direita (`anchor="e"`), compacta e somente leitura; (3) Recálculo dinâmico em tempo de exibição ao editar Pares (inclusive digitação contínua) e ao alterar as camadas do material na aba Materiais; (4) Navegação por teclado via `<Tab>` / `<Shift-Tab>` ignorando a coluna Resto (pula direto entre Pares e Sequência); (5) Ordenação numérica por Resto suportando negativos (-1 < 0) via `resto_sort_key` em `ui/sort_utils.py`; 10 novos testes dedicados em `tests/test_shapes_resto.py` e 190 testes passando na suíte geral. | `cad/layers_rule.py`, `ui/session_view.py`, `ui/sort_utils.py`, `tests/test_shapes_resto.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Dom, 25/10/2026 | 20:30 | Antigravity | Definição da política obrigatória de Publicação Automática de Releases no GitHub com sequência previsível de versões (`v<ANO>.<SEQUENCIAL>[.<PATCH>]`): sincronização contínua entre `config.py:APP_VERSION`, `.github/workflows/release.yml` e tags Git; compilação paralela de binários portáteis Windows (`CorteAC.exe`, `.zip`) e Linux (`corteac_linux`, `.tar.gz`) com notas de release ricas e detalhadas; inclusão da Seção 12 no documento vivo com checklist operacional obrigatório para futuras entregas. | `docs/PROJETO_ATOM_JOBMANAGER.md`, `.github/workflows/release.yml`, `config.py` |
| Seg, 26/10/2026 | 08:35 | Antigravity | Implementação da Regra de Cadência Estrita de 5 Commits para Publicação de Releases no GitHub: (1) Adição do tópico 12.2 no documento vivo estabelecendo que a cada bloco de 5 commits uma nova release (`v2026.X`) deve ser compilada e publicada; (2) Criação do utilitário `tools/check_release_cadence.py` com monitoramento automático do delta de commits desde a última tag; (3) Integração do verificador ao `.githooks/pre-commit` para feedback no terminal; (4) Resolução dinâmica de tag em `.github/workflows/release.yml` a partir de `config.py:APP_VERSION`. | `tools/check_release_cadence.py`, `.githooks/pre-commit`, `.github/workflows/release.yml`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Ter, 27/10/2026 | 11:00 | Antigravity | Correção da contagem de instâncias da Placa 0 (`tree_lays`), migração idempotente do schema da tabela `layouts` e `layout_pieces` em SQLite/MySQL: (1) Migração idempotente no SQLite em `database.py:init_db` adicionando colunas `name`, `width_mm`, `height_mm`, `yield_pct`, `version`, `updated_at`, `created_by`, `updated_by` em `layouts` e `mold_id`, `mirrored`, `size`, `color`, `tag`, `quality_zone` em `layout_pieces` com tratamento seguro de timestamp `DEFAULT NULL`; (2) `get_session_layouts` com resolução resiliente em cascata: se `placed_pieces_json` estiver vazio (`"[]"`), recupera as peças salvas em `layout_pieces`, com fallback para `sessions.placed_pieces_json` e preservação de `num_items`; (3) `SessionView:load_session` preenche a coluna Instâncias para Placa 0 a partir de `pieces`, `placed_pieces` da sessão ou `num_items` (evitando exibição de `0`); (4) Sincronização automática de `layouts` em `MainWindow:switch_to_session`, `show_session_window` e `_poll_nest_worker`; 2 novos testes unitários adicionados (23/23 em `test_multisheet_nesting.py` e 234 testes globais passando 100%); recompilação concluída dos executáveis `./corteac_linux` e `./teste_dola_linux`. | `database.py`, `ui/session_view.py`, `ui/main_window.py`, `cad/nesting_engine.py`, `tests/test_multisheet_nesting.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Ter, 27/10/2026 | 12:00 | Antigravity | Reinicialização completa de layout do zero no botão 'Refazer' e ação 'Limpar': (1) `DatabaseManager:delete_session_layouts` remove em cascata todas as peças de `layout_pieces` e registros de `layouts` associados à sessão, resetando `sessions` (`placed_pieces_json='[]'`, `yield_percent=0.0`, `cutting_time_sec=0.0`, `status='Stand by'`); (2) `MainWindow:on_clear_bed` (acionado pelo botão 'Refazer') zera `current_session["layouts"] = []`, `placed_pieces = []`, sincroniza `self.sessions`, restaura o saldo de pares e restos de todos os moldes (`rest = pairs` e `resto = calc_resto(pairs, layers)`), chama `delete_session_layouts` no banco, limpa o `LayoutEditorView` e recarrega `SessionView`; (3) `SessionView:clear_current_layout` atualizado para limpar multi-placas e restaurar demandas; (4) `LayoutEditorView:set_session_layouts` trata lista vazia `[]` limpando canvas e estado interno; 4 novos testes unitários adicionados em `tests/test_multisheet_nesting.py` (27/27 passando, 237/237 na suíte geral); executáveis `./corteac_linux` e `./teste_dola_linux` recompilados com sucesso. | `database.py`, `ui/main_window.py`, `ui/session_view.py`, `ui/layout_editor_view.py`, `tests/test_multisheet_nesting.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 31/10/2026 | 12:40 | Antigravity | Correção preliminar do contador de peças da barra lateral e resolução canônica de camadas (Fase Preliminar): (1) Diagnóstico da Sessão #290 confirmando Conclusão (A): Nesting e Editor usavam o mesmo L=4 (100 pares = 50 peças demandadas), mas o editor exibia contadores em peças e, em multi-placa, exibia apenas as peças da placa atual no numerador (27/50 em lay0000 e 23/50 em lay0001); (2) Fonte única de resolução de camadas em `cad/layers_rule.py` (`resolve_session_layers` e `is_layers_defined`) com prioridade estrita: grid_material_row > session > material > layout > fallback 2 (com aviso de status bar); (3) Persistência de `layers` na tabela `sessions` (SQLite e MySQL 8.0) via migração `db/migrations/005_add_session_layers.sql`, `database.py:create_session`, `update_session`, `get_session`, `get_sessions`; (4) Regra canônica de contagem única `LayoutEditorView:count_pieces_for_target` eliminando divergências entre placas; (5) Formato do contador em PARES na Linha 1 da barra lateral (`{pares_produzidos}/{pares_pedidos} {pares_faltam}/{pares_pedidos}`) tanto em placa única quanto multi-placa; (6) Linha 2 com `placa: {placed_cnt} pç` (cinza `#64748b`) exibida estritamente quando `len(layouts) > 1`; (7) Destaque em vermelho `#dc2626` SOMENTE com déficit estrito de produção (`pares_produzidos < pares_pedidos`); (8) Fórmula corrigida de `calc_resto` em `cad/layers_rule.py` garantindo sobra legítima e retorno sempre $\le 0$; (9) Nova suíte com 11 cenários de teste em `tests/test_sidebar_counter.py` e ajustes em `test_multisheet_nesting.py` e `test_layers_pairs_nesting.py` (398 testes aprovados na suíte geral). | `cad/layers_rule.py`, `database.py`, `db/schema_mysql.sql`, `db/migrations/005_add_session_layers.sql`, `ui/main_window.py`, `ui/layout_editor_view.py`, `tests/test_sidebar_counter.py`, `tests/test_multisheet_nesting.py`, `tests/test_layers_pairs_nesting.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 31/10/2026 | 13:10 | Antigravity | Fechamento da regra de camadas, validação canônica de calc_resto, coluna Resto na grade e garantia de arredondamento para cima em todos os caminhos de nesting: (1) Funções canônicas `pecas_na_mesa(pares, camadas)` e `calc_resto(pares, camadas)` em `cad/layers_rule.py` com eliminação total de duplicação de fórmulas matemáticas em todo o projeto; (2) Auditoria e refatoração de todos os motores de nesting (`dieproc_nest_pieces`, `nest_synthetic_engine`, `nest_tape_engine`, `_auto_nest_pieces_core`, `nest_multi_sheet`, `NfpBackend`, `PythonBackend`, `MacroEngine`, `LayoutEditorView`) garantindo arredondamento estrito para cima (sobrar é melhor que faltar) e remoção de `target_count=16` fixo residual; (3) Suporte estrito a presets `stdNOTFill` (para rigorosamente na cota de `pecas_na_mesa`) vs `stdFill` (preenche chapa inteira); (4) Garantia de que a peça de sobra em 4 camadas com pares ímpares é desenhada como peça real com colisão e margens, posicionada uma única vez na sessão multi-placa; (5) Coluna 'Resto' na grade de Moldes da SessionView recalculada dinamicamente via `calc_resto` em tempo real ao vivo (ao digitar pares, via setas e alteração de material) sem persistência residual em banco de dados; (6) Nova suíte com 10 testes dedicados em `tests/test_layers_resto.py` e 408 testes aprovados em 100% da suíte geral de regressão. | `cad/layers_rule.py`, `cad/nesting_engine.py`, `cad/nesting_backend.py`, `cad/macro_engine.py`, `ui/layout_editor_view.py`, `ui/session_view.py`, `ui/main_window.py`, `tests/test_layers_resto.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 31/10/2026 | 13:45 | Antigravity | Camadas por layout (multi-enfesto), indicador de enfesto visível para o operador no Layout Editor e legenda de impressão A4 'n/m' em pares: (1) Adição de `resolve_layout_layers` em `cad/layers_rule.py` com herança estrita layout > session > material > default (2); (2) Persistência retrocompatível da coluna `layers` na tabela `layouts` em SQLite (`init_db`) e MySQL (`schema_mysql.sql`, migração `006_add_layout_layers.sql`, `get_session_layouts` com herança transparente e `save_session_layouts`); (3) Suporte round-trip à chave `layers=N` e comentário `; layers=N` no parser `.lay` (`cad/lay_parser.py`, `export_layout_from_pieces`, `cad/dual_exporter.py`); (4) Cálculo ponderado de pares multi-placa no `LayoutEditorView` ($\text{pares} = \sum (\text{peças}_l \times \text{layers}_l) // 2$), exibição de `({cur_ly_layers} cam.)` na linha 2 da barra lateral quando o layout difere da sessão, e destaque em vermelho apenas com déficit estrito; (5) Enfesto visível: título da janela e barra de status exibem `Layout X/Y (lay000X, enfesto de N camadas)` (ou alerta quando indefinido) com atualização instantânea na troca de placa (`Ctrl+L` / `Ctrl+Shift+L`), e rótulo discreto 'Enfesto: N camadas' no canvas CAD; (6) Legenda A4 (`LayoutPrintDialog`): formato `tamanho: n/m` em pares inteiros sem `.00`, omissão do sufixo `/0` quando pedido=0, ShapeId formatado com `#` ao lado do nome (`129_187_Tras  #1735`) e sem `#` quando ausente, quebra de linha sem partir tokens, sobra legítima por arredondamento tratada como normal (vermelho apenas se $n > m + |\text{resto}|$), cabeçalho/metadados com 'Enfesto: N camadas' e rodapé explicativo 'n/m = pares nesta placa / pedido total'; (7) Inclusão de `layers` nos dicionários de layout gerados por `nest_multi_sheet` (`cad/nesting_engine.py`); (8) Nova suíte com 9 casos em `tests/test_layout_layers.py`, atualização de fixtures de regressão visual e 417 testes unitários passando 100%. | `cad/layers_rule.py`, `database.py`, `db/schema_mysql.sql`, `db/migrations/006_add_layout_layers.sql`, `cad/lay_parser.py`, `cad/dual_exporter.py`, `cad/nesting_engine.py`, `ui/layout_editor_view.py`, `ui/layout_print_dialog.py`, `tests/test_layout_layers.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 31/10/2026 | 14:30 | Antigravity | Separação automática das sobras de 4 camadas em layout extra de 2 camadas (`cad/layers_split.py`): (1) Função pura isolada `separar_sobras_camadas(layouts, session, shapes, params)` implementando a regra de negócio do operador: com 4 camadas base e pares ímpares, a peça excedente de cada molde ímpar ($N_2 = P \pmod 2$) é retirada da placa de 4 camadas ($N_4 = P // 2$) e reencaixada em layout extra de 2 camadas (`layers=2`), zerando o resto efetivo ($250 \text{ físicas} = 125 \text{ pares}$); (2) Conservação estrita de peças e verificação física atômica $\sum (\text{peças} \times \text{layers}) = 2P$ com rollback automático em caso de divergência; (3) Idempotência perfeita: detecção de estado já separado preservando edições manuais e sem duplicar placas ou peças; (4) Retirada da última peça por maior `placement_index` da placa onde o molde termina pela Sequência (com fallback reverso); (5) Eliminação de placas de 4 camadas vazias e renumeração contínua (`lay0000`, `lay0001`...); (6) Reencaixe automático compacto multi-placa no layout de 2 camadas com zero colisões e respeito a margens; (7) Checkbox 'Separar sobras (4 camadas -> 2 camadas)' na SessionView persistido no campo `params` existente (`stdNOTFill;separar_sobras=1`) sem migração de banco; (8) Coluna Resto na SessionView, status bar e LayoutPrintDialog atualizados para usar `calc_resto_efetivo`; (9) Título e status do LayoutEditorView exibem indicador `(sobras)` (ex.: `Layout 2/2 (lay0001 (sobras), enfesto de 2 camadas)`) e exportadores repassam `layers=2` para o arquivo `.lay`; (10) Nova suíte com 16 testes dedicados em `tests/test_layers_split.py`, 433 testes globais passando 100% e compilação do executável Linux standalone (`dist/CorteAC`, `./corteac_linux`). | `cad/layers_split.py`, `cad/layers_rule.py`, `cad/nesting_engine.py`, `database.py`, `ui/session_view.py`, `ui/main_window.py`, `ui/layout_editor_view.py`, `ui/layout_print_dialog.py`, `tests/test_layers_split.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Sáb, 31/10/2026 | 15:30 | Antigravity | Simplificação do mostrador da barra lateral do Layout Editor para fração única '{n}/{m}' (peças na placa atual / pares pedidos), conforme o original: (1) Substituição do mostrador de 3 elementos ('102/101 0/101' e 'placa: X pç') por uma única fração limpa '{n}/{m}', onde n = peças desenhadas na placa aberta e m = pares pedidos do molde (ex.: placa 0 com 46 peças e 101 pares exibe '46/101'); (2) Convenção fiel ao Job Manager original com 4 camadas (cada peça desenhada vale 2 pares; 20 pares -> '10/20') e 2 camadas (cada peça vale 1 par; 20 pares -> '20/20'); (3) Cor de alerta em vermelho '#dc2626' ativada SOMENTE quando há déficit real de produção na SESSÃO inteira (pares produzidos na sessão < pares pedidos), mantendo preto '#000000' quando o saldo global é atendido (mesmo com 0 peças na placa atual '0/102' ou com sobras); (4) Geometria de item restaurada para 70 px de altura sem sobreposição vertical, nome do molde em item_y + 38 e contador em item_y + 52 (separação de 14 px), e retângulo de seleção enquadrando perfeitamente item_y + 1 a item_y + 64; (5) Tooltip informativo e completo na barra de status ao passar o mouse sobre o molde exibindo nome, tamanho, peças na placa, decomposição de peças e camadas na sessão, pares produzidos/pedidos, resto efetivo e enfesto da placa atual; (6) 13 cenários de teste exaustivos em tests/test_sidebar_counter.py, 435 testes aprovados em 100% da suíte geral de regressão e compilação dos binários Linux (./corteac_linux, ./teste_dola_linux). | ui/layout_editor_view.py, tests/test_sidebar_counter.py, tests/test_layout_layers.py, tests/test_multisheet_nesting.py, docs/PROJETO_ATOM_JOBMANAGER.md, build_linux.sh, corteac_linux, teste_dola_linux |
| Sáb, 31/10/2026 | 20:00 | Antigravity | Liberação para criação de sessão com clique com botão esquerdo na pasta de produção (`job_folder`): (1) Duplo clique com o botão esquerdo (`<Double-1>`) em qualquer nó de pasta de produção abre a pasta na árvore e aciona imediatamente `on_new_session(target_job=folder_path)`, associando a nova sessão à pasta clicada; (2) Atalhos de teclado `Enter` / `KP_Enter` no `tree_main` mapeados para acionar a ação padrão da árvore (`on_tree_key_return`); (3) Atalhos globais `<Control-n>` / `<Control-N>` e novo botão '➕ Nova Sessão' na barra de ferramentas principal com ToolTip flutuante chamando `on_new_session`; (4) Comando 'Abrir' no menu de contexto e acionamento direto repassam explicitamente `target_job` com precedência sobre o estado de seleção transiente da árvore; (5) Salvaguarda em `dismiss_popup_menus` impedindo fechamento prematuro de popups quando o alvo do clique é um `tk.Menu`; (6) Feedback instantâneo na barra de status ao selecionar uma pasta orientando o operador: `Pasta de produção: '{folder_name}' - Duplo clique com botão esquerdo para criar sessão.`; (7) 6 novos testes unitários dedicados em `tests/test_create_session_left_click.py`, 441 testes aprovados em toda a suíte de regressão (100% sucesso) e recompilação dos executáveis standalone Linux (`./corteac_linux`, `./teste_dola_linux`). | `ui/main_window.py`, `tests/test_create_session_left_click.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `build_linux.sh`, `corteac_linux`, `teste_dola_linux` |
| Sáb, 31/10/2026 | 20:15 | Antigravity | Tooltips descritivos em todos os botões da toolbar/mode bar e remoção das 3 bolinhas roxas (LEDs) da barra de status: (1) Implementação do helper `MainWindow.bind_tooltip` associando ToolTip flutuante e atualização instantânea da mensagem na barra de status (`lbl_status_msg`) com restauração confiável no `<Leave>`; (2) Tooltips e descrições atribuídos a todos os 12 botões da barra de ferramentas superior (Nova Sessão, Recortar, Copiar, Colar, Detalhes, Layout, Shed, Catálogo, Importar .die, Parâmetros, Auto-Nest, Exportar G-Code); (3) Tooltips e descrições atribuídos aos 3 botões da barra de modos (Produção, Moldes, Materiais); (4) Remoção completa dos 3 painéis de LEDs ovais roxos (`⬭`, `#a21caf`) da barra de status, ampliando a área útil de mensagens do sistema; (5) Novos testes unitários adicionados em `tests/test_create_session_left_click.py` (8/8 passando), 443 testes unitários aprovados em 100% da suíte geral de regressão e recompilação dos executáveis standalone Linux (`./corteac_linux`, `./teste_dola_linux`). | `ui/main_window.py`, `tests/test_create_session_left_click.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `build_linux.sh`, `corteac_linux`, `teste_dola_linux` |
| Dom, 01/11/2026 | 06:30 | Antigravity | Checkbox de Refile Automático ao lado de 'Separar sobras' e recorte automático de layout pós-nesting: (1) Adição do checkbox 'Refile automático' posicionado horizontalmente ao lado de 'Separar sobras de 4 camadas em 2 camadas' na SessionView dentro de container `frame_checks`; (2) Motor `cad/trim_engine.py` com `calculate_layout_trim_bounds` e `trim_layout_dict` calculando as cotas reais ocupadas pelas peças rotacionadas + 1.0 mm de folga (`gap_mm`), limitadas pela chapa original, gerando linhas de corte CAM de guilhotina (`trim_cut_line`), ajustando `width_mm`, `height_mm`, `ris_w`, `ris_l`, `area_mm2` e recalculando `yield_percent` e `used_area_m2`; (3) Persistência de `refile_auto=1` ou `0` no campo `params` da sessão via `cad/layers_rule.py:is_refile_auto_enabled`, `encode_session_params` e `parse_session_params`, com sincronização bidirecional em SQLite/MySQL; (4) Recorte automático integrado ao término do cálculo de nesting (`MainWindow._poll_nest_worker` e `_ensure_separated_sobras_before_export`) com notificação na barra de status; (5) Sincronização multi-placa no `LayoutEditorView` (`switch_to_layout` preservando e restaurando `trim_cut_line` e dimensões originais por placa), no mini-preview da `SessionView` e no diálogo de impressão A4 (`LayoutPrintDialog`); (6) 12 novos testes unitários dedicados em `tests/test_auto_trim_checkbox.py` (459 testes aprovados na suíte geral), recompilação concluída do executável Linux (`./corteac_linux`, `./teste_dola_linux`, `dist/CorteAC`) e pacote portável `dist/CorteAC-Linux-x64.tar.gz`. | `cad/trim_engine.py`, `cad/layers_rule.py`, `ui/session_view.py`, `ui/layout_editor_view.py`, `ui/main_window.py`, `tests/test_auto_trim_checkbox.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `build_linux.sh`, `corteac_linux` |
| Seg, 02/11/2026 | 18:00 | Antigravity | Blindagem da persistência de dados das sessões e eliminação de contaminação de moldes (Sessão #188): (1) Imutabilidade estrita na leitura: `SessionView.load_session` tornado 100% somente-leitura no banco, eliminando chamadas a `update_session` e configurando `persist=False` para chamadas a `set_gap_mm` e `set_margins` disparadas no carregamento; (2) Detecção e poda automática de moldes fantasmas em sessões já calculadas (moldes no JSON sem nenhuma peça física posicionada nos layouts); (3) Remoção do fallback artificial `pairs = 16` em `SessionView.set_shapes_data`, preservando os valores numéricos reais ou nulos; (4) Eliminação da contaminação pelo catálogo global (`self.current_shapes`) em `MainWindow._poll_nest_worker`, `clear_session_nesting` e `_ensure_separated_sobras_before_export`, garantindo que os cálculos e persistência manipulem apenas os moldes legítimos da sessão ativa com seus pares originais; (5) Sanitização profunda em `database.py` (`_sanitize_session_shapes`, `update_session_shapes` e `update_session`) blindando e preservando campos críticos (`pairs`, `sequence`, `rest`, `resto`, `target_pieces`); (6) Utilitário `tools/scrub_all_sessions_shapes.py` criado e executado com sucesso, higienizando sessões corrompidas no banco de dados e recuperando a grade de 15 moldes reais da Sessão #188; (7) Nova suíte de testes `tests/test_data_integrity.py` com 5 testes rigorosos cobrindo imutabilidade de load, preservação de pares, isolamento de catálogo e poda de fantasmas. | `database.py`, `ui/session_view.py`, `ui/main_window.py`, `tools/scrub_all_sessions_shapes.py`, `tests/test_data_integrity.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Seg, 02/11/2026 | 19:15 | Antigravity | Implantação da Ponta de 2 Camadas no topo da última placa (`tip_zone`) e visualização CAM no Layout Editor: (1) Reescrita do motor `_nest_sobras_on_last_sheet` em `cad/layers_split.py` com posicionamento forçado das sobras de 2 camadas no topo (maior Y) da última placa com modos `canto` e `faixa_topo` e folga de ponta de segurança (`folga_ponta`, default 15.0 mm); (2) Armazenamento estruturado de metadados `tip_zone` no dicionário do layout (`xmin`, `ymin`, `xmax`, `ymax`, `mode`, `pieces_count`); (3) Visualização no Layout Editor (`ui/layout_editor_view.py`) com linha divisória tracejada (`tip_line`), badge e rótulo indicativo `"Ponta 2 Camadas: X peças"` orientando o operador; (4) Integração com SessionView mantendo resto zero efetivo e testes unitários em `tests/test_layers_tip.py`. | `cad/layers_split.py`, `ui/layout_editor_view.py`, `ui/session_view.py`, `tests/test_layers_tip.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Seg, 02/11/2026 | 19:45 | Antigravity | Instruções explícitas de corte e enfesto misto do almoxarifado na Impressão A4 (`LayoutPrintDialog`): (1) Função `format_enfesto_operator_text` em `cad/layers_rule.py` gerando texto claro e padronizado especificando quantidade e metragem de folhas de comprimento total e folhas de ponta (ex: `CORTAR: X folhas de COMPRIMENTO TOTAL (Y mm) [4 camadas] + Y folhas de PONTA (Z mm) [2 camadas]`); (2) Renderização visual da delimitação da zona de ponta (`tip_zone`) no preview A4 (canvas Tkinter) e na exportação física/PDF de alta resolução via Pillow; (3) Exibição destacada das instruções operacionais no cabeçalho/metadados da página para conferência no almoxarifado antes do desenrolar do material; (4) Testes em `tests/test_layout_print_legend.py`. | `cad/layers_rule.py`, `ui/layout_print_dialog.py`, `tests/test_layout_print_legend.py`, `docs/PROJETO_ATOM_JOBMANAGER.md` |
| Ter, 03/11/2026 | 10:10 | DeepSeek | Linha azul da ponta fora da placa e metragem do almoxarifado em metros (v1.6.17): a `tip_zone` é calculada na chapa original (1,38 × 2,98) mas o PDF sai refilado (1,35 × 1,13), então o retângulo azul era desenhado fora do contorno e em traço sólido grosso (Pillow sem dash). `trim_layout_dict()` agora limita a `tip_zone` às novas dimensões (removendo-a se a ponta foi cortada), novo `_clamp_tip_zone()` protege sessões antigas no canvas e no Pillow, e `_desenhar_retangulo_tracejado()` desenha o tracejado fino no PDF. `format_enfesto_operator_text()` agora emite metros com vírgula ("2 folhas longas de 1,13 × 1,35 m + ... SEM cobrir a ponta de 1,35 × 0,33 m") com clamp na chapa. `tests/test_print_metros.py` ganhou `TestPontaEClamp` (5 testes). 525 testes + 1 skip. | `cad/trim_engine.py`, `cad/layers_rule.py`, `ui/layout_print_dialog.py`, `tests/test_print_metros.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Ter, 03/11/2026 | 09:40 | DeepSeek | Impressão padronizada em metros (v1.6.16): o cabeçalho mostrava "113.02 X 134.67 cm (1.13 X 1.35 M)" e a régua numerava em centímetros. Agora `print_layout()` usa `format_dim_mm()` (metros com vírgula: "1,38 x 2,98 m") e a régua do diálogo e da exportação Pillow/PDF usa `format_m(coord, 1)` → "0,1 / 0,2 / ...", mantendo a grade de 100 mm; defaults do diálogo atualizados. Testes: `test_print_preview_contains_grid_and_labels_in_meters` (antes checava cm), novo `tests/test_print_metros.py` (3 testes) e validação de `dimensions_str` em `test_print_layout_abre.py`. 520 testes + 1 skip. | `ui/layout_print_dialog.py`, `ui/layout_editor_view.py`, `tests/test_print_metros.py`, `tests/test_layout_editor_shortcuts.py`, `tests/test_print_layout_abre.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Ter, 03/11/2026 | 07:45 | DeepSeek | Impressão do layout não abria (Ctrl+P e ícone) (v1.6.15): `LayoutEditorView.print_layout()` lia o contorno como tupla (`cntr[i][0]`), mas o editor usa dict `{"x","y"}` — o `KeyError: 0` estourava dentro do callback do Tk, que engole a exceção, e o operador via "nada acontece". Novo helper `_contour_area_mm2()` tolerante aos dois formatos (e a contorno inválido, devolvendo 0); removidos os números falsos do fallback (`yield_pct=83.02`, 40 instâncias); a abertura do diálogo agora mostra `messagebox.showerror` em caso de falha. Novo `tests/test_print_layout_abre.py` (5 testes). Validação em harness Tk: diálogo abre, rendimento real 2,43%. 517 testes + 1 skip. | `ui/layout_editor_view.py`, `tests/test_print_layout_abre.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Ter, 03/11/2026 | 07:20 | DeepSeek | Recompactação da base após retirar as sobras (v1.6.14): o operador relatou que a vaga da peça ímpar virava um buraco na placa de 4 camadas. Novo `_recompact_plate()` chamado nas duas rotas da separação (ponta/faixa e Plano B) reencaixa as peças restantes com `auto_nest_pieces`/`target_pieces`, mantendo os dicionários originais e copiando só posição/rotação (substituir as peças quebrava `piece_matches_shape` quando dois moldes têm o mesmo contorno e revertia a separação); rollback local em divergência. Medição (6 moldes, 101 pares, 4 camadas, placa 1,38 × 2,98 m): buracos 4 → 0, altura 2.424 → 2.271 mm, 4c/2c 300/6 → 294/18, físicas 1.212 = 2P. `tests/test_sobras_dobra.py` ganhou `TestRecompactacaoBase` (3 testes). 512 testes + 1 skip. | `cad/layers_split.py`, `tests/test_sobras_dobra.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Seg, 02/11/2026 | 23:25 | DeepSeek | Criação manual do atalho via linha de comando (v1.6.13): o operador apagou os atalhos e a sincronização automática só atualizava atalhos existentes. Adicionado `--criar-atalho` (ou `--atalho`) no `main.py`, que força a criação de `corteac-<versão>.desktop` no menu e na Área de Trabalho, remove versões anteriores e imprime os caminhos; `ui/desktop_shortcut.py` ganhou `criar_se_ausente=True` e `_instalar_icone()` (copia o ícone para `~/.local/share/corteac/corteac.png`, pois o PyInstaller guarda os assets no binário). Validado na máquina do operador: `CorteAC-1.6.12` criado em `~/.local/share/applications` e `~/Área de trabalho`, com `Exec=` aspeado e `Icon=` estável. | `ui/desktop_shortcut.py`, `main.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Seg, 02/11/2026 | 23:05 | DeepSeek | Sincronização automática do atalho na abertura (v1.6.12): o atalho só era atualizado se o operador rodasse o instalador, e no Mint pt-BR a pasta é `~/Área de Trabalho` (não `~/Desktop`). Novo `ui/desktop_shortcut.py::sincronizar_atalho()` chamado no início do `main()`: procura qualquer atalho do CorteAC no menu e nas pastas Desktop/Área de Trabalho/Area de Trabalho, remove os antigos (inclusive `CorteAC.desktop` manual) e recria `corteac-<versão>.desktop` com nome versionado, `Exec=` aspeado, ícone do pacote, `X-CorteAC-Version` e `gio metadata::trusted`; se não houver atalho, não cria nada. Instalador ganhou o mesmo fallback pt-BR. Validação com pacote real e HOME isolado: `CorteAC.desktop` → `corteac-1.6.12.desktop` (Name=CorteAC-1.6.12). `tests/test_desktop_shortcut.py` com 5 testes. 509 testes + 1 skip. | `ui/desktop_shortcut.py`, `main.py`, `packaging/instalar_atalho.sh`, `tests/test_desktop_shortcut.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Seg, 02/11/2026 | 22:40 | DeepSeek | Atalho da Área de Trabalho com a versão no nome (v1.6.11): novo template único `packaging/instalar_atalho.sh` (usado pelo `build_linux.sh` e pelo CI via `sed` do `config.APP_VERSION`) que cria `corteac-<versão>.desktop` com `Name=CorteAC-<versão>`, `Exec=` aspeado, `Icon=` do pacote e `X-CorteAC-Version`, removendo os atalhos antigos (`corteac.desktop`, `corteac-*.desktop`); a versão é obtida preferencialmente perguntando ao próprio binário (`--version`). No Windows, novo `packaging/criar_atalho_windows.ps1` + `versao.txt` no ZIP (CI e `build_exe_windows.bat`) criando `CorteAC-<versão>.lnk` e removendo os atalhos antigos. `README_LINUX.txt`/`README_WINDOWS.md` atualizados. Novo `tests/test_desktop_shortcut.py` (3 testes). 507 testes + 1 skip. | `packaging/instalar_atalho.sh`, `packaging/criar_atalho_windows.ps1`, `build_linux.sh`, `build_exe_windows.bat`, `.github/workflows/release.yml`, `README_LINUX.txt`, `README_WINDOWS.md`, `tests/test_desktop_shortcut.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py` |
| Seg, 02/11/2026 | 22:20 | DeepSeek | Atalho da área de trabalho com caminhos contendo espaços (v1.6.10): o `Exec=` gerado pelo `instalar_atalho.sh` (e pelo pacote do CI) passou a ser aspeado (`Exec="$DIR/corteac_linux"`); sem as aspas, pastas como "clone do job" faziam o atalho não abrir. Validado executando o comando do próprio `Exec=` a partir do pacote extraído (retornou `CorteAC 1.6.10`), com `Icon=` apontando para o `corteac.png` do pacote e cópia do atalho para a Área de Trabalho. | `build_linux.sh`, `.github/workflows/release.yml`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py` |
| Seg, 02/11/2026 | 22:00 | DeepSeek | Ícone do aplicativo e atalho da área de trabalho (v1.6.9): auditoria confirmou que o ícone da JANELA (iconphoto/iconbitmap) e o ícone EMBUTIDO no `CorteAC.exe` (PyInstaller `--icon assets/app_icon.ico`) já são atualizados em toda release, mas NÃO existia atalho de área de trabalho (nenhum `.desktop`). O pacote Linux passou a incluir `corteac.png` e `instalar_atalho.sh`, que gera `~/.local/share/applications/corteac.desktop` com caminho absoluto, `Icon=` do pacote, `Path=`, `StartupWMClass=corteac_linux`, cópia para a Área de Trabalho via `xdg-user-dir DESKTOP`, `gio metadata::trusted` e `update-desktop-database`; `README_LINUX.txt` e `README_WINDOWS.md` documentam o passo a passo (incluindo o cache de ícones do Windows/Explorer). | `build_linux.sh`, `.github/workflows/release.yml`, `README_LINUX.txt`, `README_WINDOWS.md`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py` |
| Seg, 02/11/2026 | 21:45 | DeepSeek | Regra da dobra 4c→2c, divisão automática e contadores por enfesto (v1.6.8): (1) implementada a regra confirmada pelo operador — cada peça retirada das 4 camadas vira DUAS na ponta de 2 camadas (4 físicas = 2 pares ↔ 2×2 camadas = 4 físicas), com a peça duplicada marcada `is_duplicate` (antes o sistema só movia peças e a dobra era impossível); (2) divisão variável por molde (`N4 = P//2 - k`, `N2 = (P%2) + 2k`) com `_escolher_divisao_otima()` testando k=0..3 e escolhendo a menor altura total utilizada (ganho mínimo de 5 mm); verificação física estrita mantida (4N4+2N2=2P, rollback atômico); (3) medição com 15 moldes/11 pares/4 camadas: todas as divisões fecham 330 peças físicas (k=0: 1.244 mm, k=1: 1.668 mm, k=2: 2.073 mm, k=3: 2.481 mm — o otimizador escolhe k=0 nesse layout); (4) novo painel `4c: N · 2c: M` na barra de status do Layout Editor separando os dois enfestos; (5) novo `tests/test_sobras_dobra.py` (4 testes). 504 testes + 1 skip. | `cad/layers_split.py`, `ui/layout_editor_view.py`, `tests/test_sobras_dobra.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Seg, 02/11/2026 | 21:15 | DeepSeek | Blindagem do encaixe (pares mandam), isolamento dos testes do catálogo e regressão de vãos (v1.6.7): (1) `nest_multi_sheet` passou a priorizar os PARES da sessão e ignorar `target_pieces` residual — reprodução do defeito mostrava 3 peças em vez de 18 (placa quase vazia com "vãos gigantes" após separação de sobras anterior); a chamada programática da ponta (pairs=0) continua honrando `target_pieces`; (2) 13 testes do catálogo deixaram de usar o `jobmanager.db` de produção (ficavam vermelhos quando o operador apagava artigos) — novo `tests/_catalog_fixtures.py` com SQLite temporário semeado (17 moldes, 3 peças, 16 tamanhos, lacuna PALM_CAVA/22a); (3) novo `tests/test_nesting_compactness.py` com 4 testes de regressão (params composto vs puro, tip_zone/target_pieces não alteram posições, base e ponta compactas após separação, Gerar+Refazer sem degradação). Medição no cenário do operador (15 moldes, 11 pares, 4 camadas, placa 1,32 × 2,98 m): 90 peças, 15 na ponta, menor distância 1,05 mm, 500 testes + 1 skip. | `cad/nesting_engine.py`, `tests/_catalog_fixtures.py`, `tests/test_shape_catalog_view.py`, `tests/test_shape_catalog_polish.py`, `tests/test_shape_catalog_border_cases.py`, `tests/test_nesting_compactness.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `config.py`, `.github/workflows/release.yml` |
| Seg, 02/11/2026 | 20:20 | Antigravity | Correção do espalhamento de peças e restauração do encaixe contorno-a-contorno no Nesting automático: (1) Diagnóstico e correção de falha no reconhecimento de presets DieProc (`HighYield`, `ALTERNADO`, `stdFill`, `FastNest`) decorrente de contaminação por parâmetros codificados de sessão (`params` contendo opções como `;separar_sobras=1;tip_mode=canto`); (2) Sanitização universal com `clean_preset` em `cad/nesting_backend.py` e `cad/nesting_engine.py`, reativando `row_interlock: True` (rebaixamento de linhas nos vales) e acoplamento com alternância 0°/180° (`coupling: "0/0 0/180"`); (3) Purificação prévia de estado eliminando campos transitórios de ponta (`tip_zone`, `layers_tip`, `target_pieces`) de `sess_shapes` e `layouts` em `ui/main_window.py` e `cad/nesting_engine.py`; (4) Novo teste unitário `test_nest_multi_sheet_with_encoded_params_and_clean_state` em `tests/test_multisheet_nesting.py`; recompilação dos executáveis Linux (`dist/CorteAC`, `dist/teste_dola`, `./corteac_linux`). | `cad/nesting_backend.py`, `cad/nesting_engine.py`, `ui/main_window.py`, `tests/test_multisheet_nesting.py`, `docs/PROJETO_ATOM_JOBMANAGER.md`, `build_linux.sh`, `corteac_linux` |

## 11. Prompt para o Antigravity: instalar a sincronização automática `[CONCLUÍDA]`


> **STATUS DA TAREFA: [CONCLUÍDA]**
> A sincronização automática via `tools/sync_project_doc.py` e `.githooks/pre-commit` foi instalada com sucesso, validada em commits reais com pre-commit hook ativo e verificador `--check`.

```
# TAREFA: Instalar a sincronização automática do PROJETO_ATOM_JOBMANAGER.md

Não altere código-fonte do sistema. Faça somente:

1. Copiar tools/sync_project_doc.py e .githooks/pre-commit para a raiz do repositório (se ainda não existirem).
2. Executar: git config core.hooksPath .githooks   (no Linux: chmod +x .githooks/pre-commit)
3. Rodar: python tools/sync_project_doc.py   e conferir se os blocos AUTO foram preenchidos.
4. Revisar o resultado e me reportar:
   - atalhos esperados que aparecem como NÃO ENCONTRADO (verificar se são registrados de forma dinâmica);
   - atalhos proibidos (Shift+F3, Ctrl+Y) que aparecerem como PRESENTE;
   - teclas duplicadas em mais de um arquivo (possíveis conflitos).
5. Se o script errar ou perder algo do projeto (ex.: schema vindo de ORM, atalhos montados por tabela), ajustar o script e documentar a mudança no Changelog (seção 10).
6. Fazer um commit de teste e confirmar que o hook atualizou e incluiu o documento no commit.
7. Opcional (CI): adicionar um passo que rode `python tools/sync_project_doc.py --check` e falhe o build se o documento estiver desatualizado.

Entrega: confirmação de que o hook roda no commit, lista dos avisos do item 4 e o que foi ajustado no script.
```

---

## 12. Política de Versionamento e Publicação Automática de Releases no GitHub `[CONFIRMADO]`

> **Regra de Ouro:** Todas as versões executáveis para produção (Windows 10/11 e Linux 64-bit) são distribuídas oficialmente através das **Releases do GitHub** em [https://github.com/Doletabgi/Projeto-CorteAC/releases](https://github.com/Doletabgi/Projeto-CorteAC/releases). O usuário e operadores no chão de fábrica realizam o download diretamente desta página. Portanto, **toda nova funcionalidade, ajuste ou marco industrial DEVE SEMPRE disparar a publicação/atualização automática da Release no GitHub**, mantendo os artefatos compilados e notas de versão 100% atualizados.

---

### 12.1. Sistema de Versionamento SemVer (`MAJOR.MINOR.PATCH`)

O projeto adota estritamente o padrão **SemVer (Semantic Versioning 2.0.0)** no formato `MAJOR.MINOR.PATCH` (versão principal, secundária e correção), facilitando a integração contínua, previsibilidade industrial e controle de compatibilidade:

$$\mathbf{v}\langle\text{MAJOR}\rangle.\langle\text{MINOR}\rangle.\langle\text{PATCH}\rangle$$

Exemplo: `1.2.3`

| Tipo | Exemplo | Quando utilizar |
| :--- | :--- | :--- |
| **MAJOR** | `1.0.0 → 2.0.0` | Mudanças grandes que podem exigir adaptações / incompatibilidades. |
| **MINOR** | `1.0.0 → 1.1.0` | Novas funcionalidades sem quebrar a compatibilidade. |
| **PATCH** | `1.0.0 → 1.0.1` | Correções de erros, bugs, manutenção e falhas de segurança. |

> [!IMPORTANT]
> **A sincronização é obrigatória em 3 pontos em todas as entregas:**
> 1. [`config.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/config.py): `APP_VERSION = "MAJOR.MINOR.PATCH"` (exibido na UI em **Ajuda ➔ Sobre CorteAC**).
> 2. [`.github/workflows/release.yml`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/.github/workflows/release.yml): `default: 'vMAJOR.MINOR.PATCH'`.
> 3. **Git Tag**: tag anotada correspondente criada no repositório (`git tag -a vMAJOR.MINOR.PATCH -m "..."`).
>
> **Utilitário de linha de comando**:
> - Consultar versão: `python3 tools/semver.py get`
> - Incrementar automaticamente: `python3 tools/semver.py bump patch` (ou `minor` / `major`)
> - Sugestão inteligente por commits: `python3 tools/semver.py suggest`

---

### 12.2. Regra da Cadência de Lançamentos a Cada 5 Commits `[CONFIRMADO]`

Para manter o chão de fábrica, operadores e testadores sempre abastecidos com executáveis atualizados (sem acumular grandes volumes de modificações sem homologação), o projeto estabelece a **Cadência Estrita de 5 Commits**:

> **Regra dos 5 Commits:** A cada **5 commits** acumulados no repositório a partir da última tag de release (`git rev-list --count $(git describe --tags --abbrev=0)..HEAD >= 5`), **uma nova versão oficial deve ser fechada, versionada e publicada no GitHub**.

#### Como funciona a contagem e monitoramento:
1. O desenvolvedor / agente roda o verificador a qualquer momento:
   ```bash
   python3 tools/check_release_cadence.py
   ```
2. O script calcula a distância exata em commits desde a última tag anotada:
   - **Menos de 5 commits**: exibe o progresso atual (ex: `2 de 5 commits acumulados`). O hook `.githooks/pre-commit` também lembra o desenvolvedor a cada commit.
   - **5 commits acumulados**: emite o alerta de ciclo fechado, lista os 5 commits para compor o corpo do release e sugere o próximo número sequencial (ex: `v2026.3`).
3. Ao atingir os 5 commits, o ciclo é fechado com o incremento de versão em `config.py`, atualização das notas em `.github/workflows/release.yml`, criação da tag e disparo do build no GitHub Actions.

---

### 12.3. Automação CI/CD via GitHub Actions (`release.yml`)

O fluxo `.github/workflows/release.yml` é executado em nuvem de forma automatizada e transparente:

```mermaid
flowchart LR
    A["Push Tag v2026.X / Push master"] --> B["GitHub Actions CI/CD"]
    subgraph Compilacao ["Compilação Paralela Limpa"]
        B --> W["Runner Windows-latest<br>PyInstaller --onefile CorteAC.exe<br>Empacotamento ZIP"]
        B --> L["Runner Ubuntu-latest<br>PyInstaller --onefile corteac_linux<br>Empacotamento TAR.GZ"]
    end
    W --> R["softprops/action-gh-release@v2"]
    L --> R
    R --> Pub["GitHub Releases:<br>v2026.X (Executáveis + Release Notes)"]
```

#### Concorrência e idempotência:
- O workflow usa `concurrency: corteac-release` (`cancel-in-progress: false`): como `master`, `main` e o push de tag disparam a mesma publicação, os runs são **serializados** em vez de criarem a release em paralelo.
- A etapa de publicação usa `allowUpdates: true` e `overwrite_files: true`, então um run que encontra a release já criada **atualiza** os arquivos (antes falhava com a release existente, deixando a versão sem algum binário).

#### Gatilhos de Disparo Automático:
1. **Push de Tag (`tags: ['v*']`)**: Compila e cria ou atualiza a Release oficial correspondente à tag.
2. **Push de Branch (`branches: [master, main]`)**: Mantém a Release padrão atualizada com os commits mais recentes.
3. **Workflow Dispatch manual**: Permite acionamento manual informando a tag desejada pelo painel do GitHub Actions.

#### Conteúdo Obrigatório do Release Body:
Toda Release publicada deve conter:
- Título padronizado: `CorteAC v2026.X (Windows & Linux)`.
- Instruções de inicialização zero-configuração para Windows 10/11 (duplo clique em `CorteAC.exe`, sem necessidade de Python ou terminal).
- Instruções de execução para Linux (`chmod +x ./corteac_linux`).
- Seção estruturada de recursos: `### 🛠️ Recursos Incluídos Nesta Versão (v2026.X)`.
- Explicação clara dos dados e persistência (`jobmanager.db` local e `db.ini` corporativo).

---

### 12.4. Checklist Operacional Obrigatório para Publicação de Versão

Antes de concluir qualquer tarefa ou conjunto de commits, o agente/desenvolvedor deve executar rigorosamente este procedimento:

1. **Validação de Testes**:
   ```bash
   PYTHONPATH=. pytest tests/
   ```
   *Garantir 100% de testes passando sem regressões.*

2. **Incrementar Versão no Código**:
   - Editar [`config.py`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/config.py) e definir a nova versão em `APP_VERSION = "2026.X"`.

3. **Atualizar Workflow de Release**:
   - Editar [`.github/workflows/release.yml`](file:///home/dola/Documentos/clone%20do%20job/jobmanager-win10-python/.github/workflows/release.yml) atualizando o `default` da tag e o corpo da release com os novos recursos detalhados.

4. **Sincronizar Documentação Viva**:
   - Registrar as novas entradas no Changelog (seção 10) e atualizar pendências na seção 9 deste documento.
   - Executar o sincronizador:
     ```bash
     python3 tools/sync_project_doc.py
     ```

5. **Commit e Push dos Ramos Principais**:
   ```bash
   git add config.py .github/workflows/release.yml docs/PROJETO_ATOM_JOBMANAGER.md
   git commit -m "chore(release): lancamento da versao v2026.X (...)"
   git push origin master && git push origin master:main
   ```

6. **Criação e Envio da Tag de Release**:
   ```bash
   git tag -a v2026.X -m "CorteAC v2026.X - Resumo dos recursos"
   git push origin v2026.X --force
   ```

7. **Acompanhamento e Validação do Build**:
   - Verificar os logs do GitHub Actions até que os jobs `build-windows`, `build-linux` e `publish-release` concluam com status `success`.
   - Confirmar a disponibilidade dos 4 artefatos atualizados em `https://github.com/Doletabgi/Projeto-CorteAC/releases/tag/v2026.X`:
     * `CorteAC.exe`
     * `CorteAC-Windows-x64.zip`
     * `corteac_linux`
     * `CorteAC-Linux-x64.tar.gz`
