"""Perfis reais, restrições de rotação, teste isolado e aplicação na sessão."""
import copy
import math
import time
import tkinter as tk
from unittest.mock import MagicMock
import pytest
from cad.nesting_wizard import build_profile, is_guided_profile, validate_gap
from cad.nesting_engine import auto_nest_pieces, parse_coupling_angles
from cad.layers_rule import parse_session_params
from database import DatabaseManager
from ui.dieproc_dialog import DieProcDialog
from ui.nesting_wizard import NestingWizard
from ui.session_view import SessionView


@pytest.mark.parametrize('goal', ['fast', 'balanced', 'quality'])
@pytest.mark.parametrize('rotation,angles', [('fixed', [0]), ('half', [0, 180]), ('free', [0, 90, 180, 270])])
def test_regras_de_rotacao_e_perfis_reais(goal, rotation, angles):
    profile = build_profile('Meu perfil', 'fabric', goal, rotation, '1,5')
    assert parse_coupling_angles(profile['coupling']) == angles
    assert profile['gap1'] == 1.5
    assert is_guided_profile(profile)
    if rotation != 'free':
        assert profile['range1_from'] == profile['range1_to'] == 0
    assert profile['macro_script'] == ''


@pytest.mark.parametrize('value', ['NaN', 'inf', '-1', '50.1', 'abc', ''])
def test_distancia_invalida(value):
    with pytest.raises(ValueError):
        validate_gap(value)


@pytest.mark.parametrize('name', ['', 'x' * 81, 'Perfil;teste', 'Perfil?teste', 'Perfil\nteste'])
def test_nomes_invalidos(name):
    with pytest.raises(ValueError):
        build_profile(name, 'synthetic', 'balanced', 'half', 1)


def shapes():
    return [{'id': 1, 'name': 'Peça L', 'size': '38', 'pairs': 12,
             'contour': [(0, 0), (55, 0), (55, 25), (30, 25), (30, 65), (0, 65)]}]


@pytest.mark.parametrize('backend', ['python', 'nfp'])
def test_motor_respeita_rotacao_fixa_e_distancia(backend, monkeypatch):
    from cad.geometry import polygons_collide
    monkeypatch.setenv('CORTEAC_BACKEND', backend)
    profile = build_profile('Meu perfil', 'fabric', 'quality', 'fixed', 3)
    result = auto_nest_pieces(shapes(), 320, 240, target_count=8, strategy='flashnestsheet',
                             params=profile['name'], dieproc_params=profile, gap_mm=3, layers=2)
    assert len(result) > 1
    for index, item in enumerate(result):
        assert float(item['rotation']) % 360 == 0
        for other in result[:index]:
            assert not polygons_collide(item['poly'], other['poly'], gap=2.99)


@pytest.fixture
def wizard():
    root = tk.Tk()
    root.withdraw()
    callback_errors = []
    root.report_callback_exception = lambda *args: callback_errors.append(args)
    db = DatabaseManager(':memory:')
    job = dict(shapes=shapes(), width=320, height=240, layers=2, limit=8,
               margins={'left': 10, 'right': 10, 'top': 10, 'bottom': 10})
    callback = MagicMock()
    window = NestingWizard(root, db, context=dict(can_apply=True, gap=1., job=job, session_name='Teste'), on_created=callback)
    window.created_callback = callback
    try:
        yield window
        assert not callback_errors, callback_errors
    finally:
        window.destroy()
        root.destroy()


def test_navegacao_e_salvamento_so_no_final(wizard):
    original = wizard.db.get_dieproc_presets()
    for index in range(5):
        wizard.show_step(index)
        wizard.update()
    wizard.show_step(2)
    wizard.values['rotation'].set('fixed')
    wizard.show_step(3)
    wizard.values['gap'].set('2,5')
    wizard.show_step(4)
    wizard.values['name'].set('Meu perfil guiado')
    assert wizard.db.get_dieproc_presets() == original
    wizard.finish(False)
    saved = wizard.db.get_dieproc_preset('Meu perfil guiado')
    assert saved['gap1'] == 2.5
    assert is_guided_profile(saved)
    wizard.created_callback.assert_called_once()
    assert wizard.created_callback.call_args.args[1] is False


def test_nome_existente_nao_sobrescreve(wizard):
    original = wizard.db.get_dieproc_presets()
    existing = next(iter(original))
    wizard.values['name'].set(existing.lower())
    wizard.finish(True)
    assert 'já existe' in wizard.status.cget('text')
    assert wizard.db.get_dieproc_presets() == original
    wizard.created_callback.assert_not_called()


def test_cancelamento_nao_grava(wizard):
    original = wizard.db.get_dieproc_presets()
    wizard.show_step(4)
    wizard.destroy()
    assert wizard.db.get_dieproc_presets() == original
    wizard.created_callback.assert_not_called()


def test_previa_real_nao_modifica_banco_e_e_invalidada(wizard):
    original = wizard.db.get_dieproc_presets()
    snapshot = copy.deepcopy(wizard.context)
    wizard.show_step(4)
    wizard.run_preview()
    deadline = time.monotonic() + 15
    while wizard._process is not None and time.monotonic() < deadline:
        wizard.update()
        time.sleep(.02)
    assert wizard._process is None
    assert wizard._result is not None, wizard.test_status.cget('text')
    assert wizard._result['pieces']
    assert len(wizard.canvas.find_withtag('preview_piece')) == len(wizard._result['pieces'])
    assert math.isfinite(wizard._result['yield_pct'])
    assert wizard.context == snapshot
    assert wizard.db.get_dieproc_presets() == original
    wizard.values['rotation'].set('fixed')
    assert wizard._result is None


def test_fechar_cancela_processo_e_agendamentos(wizard):
    wizard.run_preview()
    process = wizard._process
    wizard.destroy()
    assert not process.is_alive()
    assert wizard._poll_job is None


def test_aplicar_perfil_guia_persiste_modo_gap_e_opcoes():
    root = tk.Tk()
    root.withdraw()
    db = DatabaseManager(':memory:')
    sid = db.create_session(name='Teste', nesting_mode='auto', params='stdNOTFill;tip_mode=faixa;folga_ponta=15')
    view = SessionView(root, session_data=db.get_session(sid), db=db)
    try:
        profile = build_profile('Minha configuração', 'fabric', 'quality', 'fixed', 2.5)
        db.save_dieproc_preset(profile)
        view.on_dieproc_preset_selected(profile)
        saved = db.get_session(sid)
        assert saved['nesting_mode'] == 'custom'
        assert saved['strategy'] == 'flashnestsheet'
        assert view.get_gap_mm() == saved['gap_mm'] == 2.5
        name, options = parse_session_params(saved['params'])
        assert name == profile['name']
        assert options['tip_mode'] == 'faixa'
        editor = DieProcDialog(root, db, initial_preset=profile['name'])
        try:
            assert editor.txt_macro.get('1.0', 'end-1c') == ''
            assert is_guided_profile(editor.get_current_fields_dict())
        finally:
            editor.destroy()
    finally:
        view.destroy()
        root.destroy()


@pytest.mark.parametrize('apply', [False, True])
def test_fluxo_pelo_botao_dieproc_e_perfil_salvo(apply):
    root = tk.Tk()
    root.withdraw()
    db = DatabaseManager(':memory:')
    material = db.get_materials()[0]
    sid = db.create_session(name='Sessão do assistente', material_id=material['id'], shapes=shapes())
    view = SessionView(root, session_data=db.get_session(sid), db=db)
    root.session_view = view
    editor = DieProcDialog(root, db, on_select=view.on_dieproc_preset_selected)
    try:
        before = db.get_session(sid)
        editor.btn_wizard.invoke()
        wizard = next(child for child in editor.winfo_children() if isinstance(child, NestingWizard))
        assert wizard.context['job']['shapes']
        wizard.show_step(4)
        wizard.values['name'].set('Minha nova configuração')
        wizard.values['gap'].set('3,5')
        wizard.finish(apply)
        assert db.get_dieproc_preset('Minha nova configuração')['gap1'] == 3.5
        if apply:
            session = db.get_session(sid)
            assert session['gap_mm'] == 3.5
            assert parse_session_params(session['params'])[0] == 'Minha nova configuração'
            assert session['placed_pieces_json'] == before['placed_pieces_json']
        else:
            assert db.get_session(sid) == before
            assert editor.active_preset_name == 'Minha nova configuração'
            assert editor.notebook.select() == str(editor.tab_dieproc)
    finally:
        if editor.winfo_exists():
            editor.destroy()
        view.destroy()
        root.destroy()


def test_migracao_preserva_perfis_existentes(tmp_path):
    db = DatabaseManager(tmp_path / 'local.db')
    before = db.get_dieproc_presets()
    with db.get_connection() as conn:
        conn.cursor().execute('ALTER TABLE dieproc_presets DROP COLUMN wizard_settings_json')
        conn.commit()
    migrated = DatabaseManager(tmp_path / 'local.db')
    migrated.init_db()
    assert migrated.get_dieproc_presets() == before
