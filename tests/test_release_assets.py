"""Renomeação dos downloads preserva conteúdo e não remove arquivos."""
import copy
import pytest
import atualizar as update


def test_renomeia_assets_e_instrucoes_sem_upload_ou_exclusao(monkeypatch):
    names = ['CorteAC.exe', 'CorteAC-Windows-x64.zip', 'CorteAC-Linux-x64.tar.gz',
             'CorteAC-Setup-1.8.13.exe', 'corteac_linux']
    assets = [dict(id=i, name=name, size=100+i, digest=f'sha256:{i}') for i, name in enumerate(names)]
    original = copy.deepcopy(assets)
    release = dict(id=99, assets=assets, body='Extraia e dê dois cliques no **`CorteAC.exe`**.\n'
                   'Extraia os arquivos e no terminal execute:\nchmod +x ./corteac_linux\n./corteac_linux\n'
                   'https://github.com/Doletabgi/Projeto-CorteAC/releases')
    api = update.GitHub('example/OpenCorte')
    monkeypatch.setattr(api, 'get', lambda *a, **k: release)
    patches = []
    def patch(path, payload):
        patches.append((path, payload))
        if path == 'releases/99':
            release.update(payload)
            return release
        asset = next(a for a in assets if path == f'releases/assets/{a["id"]}')
        assert set(payload) == {'name'}
        asset.update(payload)
        return asset
    monkeypatch.setattr(api, 'patch', patch)
    assert api.rename_release_assets('v1.8.13') == 5
    assert {a['name'] for a in assets} == {'OpenCorte.exe', 'OpenCorte-Windows-x64.zip',
           'OpenCorte-Linux-x64.tar.gz', 'OpenCorte-Setup-1.8.13.exe', 'opencorte_linux'}
    for before, after in zip(original, assets):
        assert (before['id'], before['size'], before['digest']) == (after['id'], after['size'], after['digest'])
    assert 'Projeto-CorteAC/releases' in release['body']
    assert './run.sh' in release['body']
    assert 'chmod +x ./opencorte_linux' in release['body']
    assert 'executável incluído' in release['body']
    count = len(patches)
    assert api.rename_release_assets('v1.8.13') == 0
    assert len(patches) == count


def test_nome_em_conflito_nao_sobrescreve_download(monkeypatch):
    api = update.GitHub('example/OpenCorte')
    release = {'id': 1, 'assets': [{'name': 'CorteAC.exe'}, {'name': 'OpenCorte.exe'}]}
    monkeypatch.setattr(api, 'get', lambda *a, **k: release)
    monkeypatch.setattr(api, 'patch', lambda *a, **k: pytest.fail('não deveria alterar'))
    with pytest.raises(update.UpdateError, match='nenhum arquivo será sobrescrito'):
        api.rename_release_assets('v1.8.13')
