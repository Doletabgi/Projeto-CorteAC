"""Notas preenchidas, reproduzíveis por tag e sem dados operacionais."""
from pathlib import Path
import atualizar as update
from test_atualizar import repository


def test_gera_notas_das_mudancas_e_ignora_banco_e_credenciais(repository):
    update.git(repository, 'tag', 'v1.2.3')
    (repository/'ui').mkdir()
    (repository/'ui/nesting_wizard.py').write_text('new = True\n')
    (repository/'jobmanager.db').write_bytes(b'dados privados')
    (repository/'db.ini').write_text('password=secreto')
    notes = update.release_notes(repository, '1.2.4')
    assert 'Assistente de encaixe' in notes
    assert 'jobmanager.db' not in notes
    assert 'secreto' not in notes
    assert 'db.ini' not in notes


def test_notas_revisadas_sao_preservadas_na_retomada(repository):
    path = repository/'docs/releases/v1.2.4.md'
    path.parent.mkdir(parents=True)
    path.write_text('- Melhoria revisada pelo operador.\n', encoding='utf-8')
    update.write_release_notes(repository, '1.2.4')
    assert path.read_text() == '- Melhoria revisada pelo operador.\n'


def test_notas_geradas_entram_na_copia_e_no_commit(repository):
    ignore = repository/'.gitignore'
    ignore.write_text(ignore.read_text() + 'docs/*\n!docs/releases/\n!docs/releases/*.md\n')
    path = update.write_release_notes(repository, '1.2.4')
    assert path.relative_to(repository).as_posix() in update.source_files(repository)


def test_tag_sem_arquivo_de_notas_gera_resumo_daquela_versao(repository):
    update.git(repository, 'tag', 'v1.2.3')
    (repository/'ui').mkdir()
    (repository/'ui/production_dashboard.py').write_text('feature = 1\n')
    update.git(repository, 'add', 'ui')
    update.git(repository, 'commit', '-m', 'Adiciona relatório')
    update.git(repository, 'tag', 'v1.2.4')
    (repository/'ui/nesting_wizard.py').write_text('nao_publicado = 1\n')
    notes = update.release_notes(repository, '1.2.4', ref='v1.2.4')
    assert 'Painel de Produção' in notes
    assert 'Assistente de encaixe' not in notes


def test_tag_utiliza_notas_versionadas(repository):
    path = repository/'docs/releases/v1.2.4.md'
    path.parent.mkdir(parents=True)
    path.write_text('- Alteração da versão publicada.\n')
    update.git(repository, 'add', 'docs')
    update.git(repository, 'commit', '-m', 'Notas')
    update.git(repository, 'tag', 'v1.2.4')
    path.write_text('- Texto posterior, ainda não publicado.\n')
    assert update.release_notes(repository, '1.2.4', ref='v1.2.4') == '- Alteração da versão publicada.\n'


def test_primeira_versao_e_versao_so_com_metadados_nao_ficam_vazias(repository):
    assert update.release_notes(repository, '1.2.4').startswith('- ')
    update.git(repository, 'tag', 'v1.2.3')
    (repository/'config.py').write_text('APP_VERSION = "1.2.4"\n')
    assert 'Atualização da versão' in update.release_notes(repository, '1.2.4')


def test_workflow_publica_notas_explicitamente():
    workflow = (update.ROOT/'.github/workflows/release.yml').read_text()
    assert 'steps.release_notes.outputs.changes' in workflow
    assert 'fetch-depth: 0' in workflow
    assert 'Consulte as notas geradas' not in workflow
    assert 'generate_release_notes: false' in workflow


def test_substitui_apenas_alteracoes_e_preserva_secoes():
    original = ('# Instalação\nInstruções existentes.\n\n### Alterações desta versão\n'
                'Consulte as notas geradas.\nA compilação dos pacotes não substitui a homologação operacional em máquina.\n'
                '## Downloads\nArquivos existentes.\n')
    body = update.replace_release_changes(original, '- Melhoria concreta.\n')
    assert 'Instruções existentes.' in body
    assert '## Downloads\nArquivos existentes.' in body
    assert 'A compilação dos pacotes' in body
    assert '- Melhoria concreta.' in body
    assert 'Consulte as notas' not in body
    assert update.replace_release_changes(body, '- Melhoria concreta.\n') == body


def test_atualiza_release_sem_mexer_em_assets(monkeypatch):
    import io
    import json
    monkeypatch.setenv('GH_TOKEN', 'token-de-teste')
    api = update.GitHub('example/OpenCorte')
    monkeypatch.setattr(api, 'get', lambda *a, **k: {'id': 123, 'body': '# Instruções\n'})
    requests = []
    def open_request(request, **kwargs):
        requests.append(request)
        return io.BytesIO(b'{}')
    monkeypatch.setattr(update, 'urlopen', open_request)
    assert api.update_release_notes('v1.2.4', '- Novidade.\n')
    assert requests[0].method == 'PATCH'
    assert requests[0].full_url.endswith('/releases/123')
    assert set(json.loads(requests[0].data)) == {'body'}


def test_nao_edita_release_inexistente_ou_inalterada(monkeypatch):
    api = update.GitHub('example/OpenCorte')
    monkeypatch.setattr(api, 'get', lambda *a, **k: None)
    assert not api.update_release_notes('v1.2.4', '- Novidade.\n')
    body = update.replace_release_changes('', '- Novidade.\n')
    monkeypatch.setattr(api, 'get', lambda *a, **k: {'id': 1, 'body': body})
    assert not api.update_release_notes('v1.2.4', '- Novidade.\n')
