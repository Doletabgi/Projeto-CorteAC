"""Selecionar um perfil deve persistir a escolha sem apagar opções da sessão."""
import tkinter as tk
from database import DatabaseManager
from cad.layers_rule import parse_session_params
from ui.session_view import SessionView


def test_selecao_dieproc_persiste_e_preserva_opcoes():
    root = tk.Tk()
    root.withdraw()
    db = DatabaseManager(':memory:')
    sid = db.create_session(name='Teste DieProc', params='stdNOTFill;tip_mode=faixa;folga_ponta=15')
    view = SessionView(root, session_data=db.get_session(sid), db=db)
    try:
        profile = dict(next(iter(db.get_dieproc_presets().values())))
        profile['name'] = 'PERFIL_TESTE'
        db.save_dieproc_preset(profile)
        view.on_dieproc_preset_selected(profile)
        assert view.cb_params.get() == 'PERFIL_TESTE'
        name, options = parse_session_params(db.get_session(sid)['params'])
        assert name == 'PERFIL_TESTE'
        assert options['tip_mode'] == 'faixa'
        assert options['folga_ponta'] == '15'
        view.load_session(db.get_session(sid))
        assert view.cb_params.get() == 'PERFIL_TESTE'
    finally:
        view.destroy()
        root.destroy()
