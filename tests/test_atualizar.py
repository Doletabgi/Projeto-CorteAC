"""Validação da atualização unificada sem acessar GitHub, banco ou atalhos reais."""
import argparse
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

import atualizar as update


@pytest.fixture
def repository(tmp_path):
    root = tmp_path/'projeto com espaços'
    root.mkdir()
    update.git(root, 'init', '-b', 'master')
    update.git(root, 'config', 'user.email', 'release@example.invalid')
    update.git(root, 'config', 'user.name', 'Release Test')
    (root/'config.py').write_text('APP_VERSION = "1.2.3"\n')
    (root/'code.py').write_text('value = 1\n')
    (root/'jobmanager.db').write_bytes(b'base versionada')
    (root/'.gitignore').write_text('.release/\ndb.ini\n')
    update.git(root, 'add', '.')
    update.git(root, 'commit', '-m', 'base')
    update.git(root, 'remote', 'add', 'origin', 'git@github.com:example/OpenCorte.git')
    return root


def arguments(**kwargs):
    return argparse.Namespace(simular=False, retomar=False, incremento='patch', espera=1, **kwargs)


@pytest.mark.parametrize('increment,expected', [('patch','1.2.4'), ('minor','1.3.0'), ('major','2.0.0')])
def test_version_increment_and_read_without_import(repository, increment, expected):
    assert update.current_version(repository) == '1.2.3'
    assert update.next_version('1.2.3', increment) == expected
    assert not (repository/'exports').exists()


@pytest.mark.parametrize('name', ['jobmanager.db', 'db.ini', '.env', 'secret.key', 'db/private.ini',
                                 '.release/estado.json', 'dist/app.py', 'backups/config.py',
                                 'exports/lay0000.lay', 'ordem.onx'])
def test_operational_files_excluded(name):
    assert not update.allowed_source(name)


def test_snapshot_and_commit_never_copy_or_publish_operational_data(repository, tmp_path):
    (repository/'jobmanager.db').write_bytes(b'BANCO DO OPERADOR')
    (repository/'db.ini').write_text('senha=privada')
    (repository/'code.py').write_text('value = 2\n')
    (repository/'new.py').write_text('feature = True\n')
    files = update.source_files(repository)
    assert 'jobmanager.db' not in files
    assert 'db.ini' not in files
    assert 'new.py' in files
    stage = tmp_path/'stage'
    update.snapshot(repository, stage, files)
    assert not (stage/'jobmanager.db').exists()
    assert not (stage/'db.ini').exists()
    updater = update.Updater(repository, arguments())
    updater.state = dict(version='1.2.4', files=files, fingerprints=update.fingerprint(repository,files),
                         base=update.git(repository,'rev-parse','HEAD'))
    updater.commit()
    assert update.git(repository, 'show', 'HEAD:jobmanager.db') == 'base versionada'
    assert (repository/'jobmanager.db').read_bytes() == b'BANCO DO OPERADOR'
    assert update.git(repository, 'show', 'HEAD:code.py') == 'value = 2'
    assert update.git(repository, 'show', 'HEAD:new.py') == 'feature = True'
    assert 'jobmanager.db' in update.git(repository, 'diff', '--name-only')
    updater.tag()
    updater.tag()  # retomada não recria nem move a tag
    assert update.git(repository, 'rev-list', '-n', '1', 'v1.2.4') == updater.state['sha']


def test_source_change_after_build_prevents_commit(repository):
    files = update.source_files(repository)
    updater = update.Updater(repository, arguments())
    updater.state = dict(version='1.2.4',files=files,fingerprints=update.fingerprint(repository,files))
    (repository/'code.py').write_text('value = 3\n')
    with pytest.raises(update.UpdateError, match='mudaram'):
        updater.commit()
    assert not update.git(repository,'diff','--cached','--name-only')


def test_dry_run_does_not_write_state_or_call_network(repository, monkeypatch):
    args = arguments()
    args.simular = True
    monkeypatch.setattr(update.GitHub, 'get', lambda *a, **k: pytest.fail('rede na simulação'))
    before = update.git(repository,'rev-parse','HEAD')
    update.Updater(repository,args).start()
    assert update.current_version(repository) == '1.2.3'
    assert update.git(repository,'rev-parse','HEAD') == before
    assert not (repository/'.release').exists()


def test_atomic_copy_preserves_original_once_and_is_repeatable(tmp_path):
    old, new, backups = tmp_path/'app', tmp_path/'build', tmp_path/'backups'
    old.write_bytes(b'versao anterior'); new.write_bytes(b'versao nova')
    update.atomic_copy(new,old,backups)
    update.atomic_copy(new,old,backups)
    assert old.read_bytes() == b'versao nova'
    assert (backups/'app.anterior').read_bytes() == b'versao anterior'


def test_isolation_overrides_production_database_and_network(monkeypatch, tmp_path):
    monkeypatch.setenv('DB_BACKEND','mysql')
    monkeypatch.setenv('SQLITE_PATH','/production/jobmanager.db')
    monkeypatch.setenv('CORTEAC_SHAPES_DIR','//production/shapes')
    env = update.isolated_env(tmp_path)
    assert env['DB_BACKEND'] == 'sqlite'
    assert env['SQLITE_PATH'] == str(tmp_path/'jobmanager.db')
    assert env['CORTEAC_SHAPES_DIR'] == ''
    assert env['CI'] == '1'


def test_github_requires_success_and_all_five_assets(monkeypatch):
    api = update.GitHub('example/OpenCorte')
    run = dict(id=5, run_attempt=1, status='completed', conclusion='success',
               path='.github/workflows/release.yml',html_url='https://github.com/example/OpenCorte/actions/runs/5')
    required = ['OpenCorte.exe','OpenCorte-Windows-x64.zip','opencorte_linux',
                'OpenCorte-Linux-x64.tar.gz','OpenCorte-Setup-1.2.4.exe']
    release = dict(html_url='https://github.com/example/OpenCorte/releases/tag/v1.2.4',
                   draft=False, assets=[dict(name=n,size=1) for n in required])
    def get(path, **kwargs):
        return {'workflow_runs':[run]} if path.startswith('actions/') else release
    monkeypatch.setattr(api,'get',get)
    assert api.wait_release('abc','v1.2.4','1.2.4',1) == release['html_url']
    release['assets'].pop()
    with pytest.raises(update.UpdateError,match='cinco artefatos'):
        api.wait_release('abc','v1.2.4','1.2.4',1)
    run['conclusion']='failure'
    with pytest.raises(update.UpdateError,match='Build/release falhou'):
        api.wait_release('abc','v1.2.4','1.2.4',1)


def test_repository_url_validation():
    assert update.repository_name('git@github.com:owner/project.git') == 'owner/project'
    assert update.repository_name('https://github.com/owner/project.git') == 'owner/project'
    with pytest.raises(update.UpdateError):
        update.repository_name('https://another.example/owner/project.git')


def test_main_version_does_not_touch_shortcuts(monkeypatch, capsys):
    import main
    monkeypatch.setattr(main.sys, 'argv', ['main.py', '--version'])
    import ui.desktop_shortcut
    monkeypatch.setattr(ui.desktop_shortcut,'sincronizar_atalho',lambda *a,**k: pytest.fail('atalho alterado'))
    main.main()
    assert update.current_version(update.ROOT) in capsys.readouterr().out


def test_resume_phase_skips_completed_action(repository):
    updater = update.Updater(repository, arguments())
    updater.state = {'done':['build']}
    updater.phase('build', lambda: pytest.fail('build repetida'))
    updater.phase('teste', lambda: updater.state.update(checked=True))
    assert updater.state['checked']
    assert updater.state['done'] == ['build','teste']


def test_resume_after_github_failure_reuses_version_commit_and_build(repository, monkeypatch, tmp_path):
    real_command = update.command
    calls = []
    def command(args, *a, **kw):
        if args[:2] in (['git','fetch'], ['git','merge-base'], ['git','ls-remote'], ['git','push']):
            calls.append(args[:2])
            return ''
        if args[:2] == [update.sys.executable,'-c']:
            return ''
        return real_command(args,*a,**kw)
    monkeypatch.setattr(update,'command',command)
    monkeypatch.setattr(update.GitHub,'get',lambda *a,**k: {})
    steps=[]
    def prepare(self):
        steps.append('prepare')
        (self.root/'config.py').write_text(f'APP_VERSION = "{self.state["version"]}"\n')
        self.state['files']=update.source_files(self.root)
        self.state['fingerprints']=update.fingerprint(self.root,self.state['files'])
        self.state['stage']=str(tmp_path/'build')
    monkeypatch.setattr(update.Updater,'prepare',prepare)
    monkeypatch.setattr(update.Updater,'build',lambda self: steps.append('build'))
    monkeypatch.setattr(update.Updater,'install',lambda self: steps.append('install'))
    def fail(*a,**kw):
        raise update.UpdateError('CI indisponível')
    monkeypatch.setattr(update.GitHub,'wait_release',fail)
    with pytest.raises(update.UpdateError,match='CI indisponível'):
        update.Updater(repository,arguments()).start()
    sha=update.git(repository,'rev-parse','HEAD')
    assert update.current_version(repository)=='1.2.4'
    assert json.loads((repository/'.release/estado.json').read_text())['complete'] is False
    with pytest.raises(update.UpdateError,match='pendente'):
        update.Updater(repository,arguments()).start()
    monkeypatch.setattr(update.GitHub,'wait_release',lambda *a,**kw:'https://github.com/example/OpenCorte/releases/tag/v1.2.4')
    args=arguments();args.retomar=True
    update.Updater(repository,args).start()
    assert update.git(repository,'rev-parse','HEAD')==sha
    assert update.current_version(repository)=='1.2.4'
    assert steps==['prepare','build','install']
    assert calls.count(['git','push'])==1
    assert json.loads((repository/'.release/estado.json').read_text())['complete'] is True


def test_version_updates_installer_fallback_without_loading_config(repository):
    (repository/'packaging').mkdir()
    installer=repository/'packaging/corteac_setup.iss'
    installer.write_text('#define MyAppVersion "1.2.3"\n')
    update.set_version(repository,'1.2.4')
    assert update.current_version(repository)=='1.2.4'
    assert '#define MyAppVersion "1.2.4"' in installer.read_text()
    assert not (repository/'exports').exists()


def test_documentation_is_central_preserves_manual_sections_and_is_idempotent(repository):
    (repository/'docs').mkdir()
    doc=repository/'docs/PROJETO_ATOM_JOBMANAGER.md'
    manual='Decisão manual do operador, preservar este texto.\n'
    blocks='\n'.join(f'<!-- AUTO:{n}:start -->\n<!-- AUTO:{n}:end -->' for n in ['header','tree','symbols','schema','shortcuts','gitlog'])
    doc.write_text(manual+blocks)
    update.sync_documentation(repository)
    text=doc.read_text()
    assert text.startswith(manual)
    assert '**Versão do aplicativo:** `1.2.3`' in text
    assert 'config.py' in text
    update.sync_documentation(repository,check=True)
    assert doc.read_text()==text
    (repository/'new.py').write_text('def example():\n    return 1\n')
    with pytest.raises(update.UpdateError,match='desatualizada'):
        update.sync_documentation(repository,check=True)
    assert doc.read_text()==text  # --check não grava


@pytest.mark.parametrize('platform',['linux','win32'])
def test_packaging_includes_generated_shortcuts_without_source_scripts(tmp_path,platform):
    stage=tmp_path/'stage';stage.mkdir()
    (stage/'assets').mkdir()
    (stage/'assets/app_icon.png').write_bytes(b'icon')
    for name in ['README_WINDOWS.txt','README_LINUX.txt','db.example.ini']:
        (stage/name).write_text('distribuicao')
    dist=stage/'dist';dist.mkdir()
    binary=dist/('OpenCorte.exe' if platform=='win32' else 'OpenCorte')
    binary.write_bytes(b'executable')
    files=update.package_distribution(stage,binary,'1.2.4',platform)
    assert all(p.exists() for p in files)
    assert (dist/'versao.txt').read_text()=='1.2.4'
    if platform=='linux':
        with tarfile.open(dist/'OpenCorte-Linux-x64.tar.gz') as archive:
            installer=archive.extractfile('OpenCorte/instalar_atalho.sh').read().decode()
            assert '1.2.4' in installer
            assert '@VERSAO@' not in installer
            assert archive.extractfile('OpenCorte/opencorte_linux').read()==b'executable'
            assert b'exec "$DIR/opencorte_linux"' in archive.extractfile('OpenCorte/run.sh').read()
    else:
        with zipfile.ZipFile(dist/'OpenCorte-Windows-x64.zip') as archive:
            assert archive.read('OpenCorte.exe')==b'executable'
            assert 'CreateShortcut' in archive.read('criar_atalho_windows.ps1').decode('utf-8-sig')
            assert archive.read('versao.txt')==b'1.2.4'
    assert not (stage/'packaging').exists()


def test_workflow_uses_central_build_and_legacy_sources_are_removed():
    root=update.ROOT
    legacy=['build_linux.sh','build_exe_windows.bat','tools/semver.py',
            'tools/sync_project_doc.py','tools/check_release_cadence.py','tools/clean_database.py',
            'packaging/instalar_atalho.sh','packaging/criar_atalho_windows.ps1']
    assert not any((root/name).exists() for name in legacy)
    workflow=(root/'.github/workflows/release.yml').read_text()
    assert workflow.count('run: python atualizar.py --build')==2
    assert 'tools/clean_database.py' not in workflow
    assert 'pyinstaller --clean' not in workflow
    assert 'ISCC.exe' not in workflow


def test_windows_installer_uses_version_and_accepts_paths_with_spaces(tmp_path,monkeypatch):
    stage=tmp_path/'build com espaços';(stage/'dist').mkdir(parents=True)
    compiler='C:/Program Files (x86)/Inno Setup 6/ISCC.exe'
    seen=[]
    def command(args,cwd,**kwargs):
        seen.append((args,cwd))
        (stage/'dist/OpenCorte-Setup-1.2.4.exe').write_bytes(b'installer')
    monkeypatch.setattr(update,'command',command)
    artifact=update.build_windows_installer(stage,'1.2.4',compiler)
    assert artifact.name=='OpenCorte-Setup-1.2.4.exe'
    assert seen==[([compiler,'/DMyAppVersion=1.2.4',stage/'packaging/corteac_setup.iss'],stage)]


def test_windows_installer_missing_output_is_a_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(update,'command',lambda *a,**k: None)
    with pytest.raises(update.UpdateError,match='não gerou'):
        update.build_windows_installer(tmp_path,'1.2.4','ISCC.exe')
