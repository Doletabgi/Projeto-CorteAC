import copy
import tkinter as tk
from unittest.mock import patch
import pytest
from cad.layers_split import separar_sobras_em_ponta
from cad.layers_rule import layers_for_piece
from cad.nesting_engine import nest_multi_sheet, piece_matches_shape
from ui.session_view import SobrasConfigDialog


def scenario():
    contour = [{'x': 0, 'y': 0}, {'x': 50, 'y': 0}, {'x': 50, 'y': 40}, {'x': 0, 'y': 40}]
    shapes = [{'id': 1, 'name': 'M1', 'size': '41', 'pairs': 5, 'sequence': 1, 'contour': contour},
              {'id': 2, 'name': 'M2', 'size': '42', 'pairs': 4, 'sequence': 2, 'contour': contour}]
    session = {'layers': 4, 'params': 'stdNOTFill;separar_sobras=1;destino_sobras=placa',
               'material': {'width_mm': 500, 'height_mm': 500, 'layers': 4}, 'gap_mm': 1}
    result = nest_multi_sheet(copy.deepcopy(shapes), 500, 500, layers=4)
    assert result['success']
    return shapes, session, result['layouts']


def physical(layouts, shape):
    return sum(layers_for_piece(ly, p) for ly in layouts for p in ly['pieces'] if piece_matches_shape(p, shape))


def test_placa_separada_conserva_pares_e_eh_idempotente():
    shapes, session, layouts = scenario()
    original = copy.deepcopy(layouts)
    new, msg = separar_sobras_em_ponta(layouts, session=session, shapes=shapes)
    assert msg and any(ly['layers'] == 2 for ly in new)
    assert not any(ly.get('tip_zone') for ly in new)
    assert [physical(new, s) for s in shapes] == [10, 8]
    assert layouts == original
    again, _ = separar_sobras_em_ponta(new, session=session, shapes=shapes)
    assert again == new


def test_modo_ponta_continua_padrao_e_sobras_desativadas():
    shapes, session, layouts = scenario()
    session['params'] = 'stdNOTFill;separar_sobras=0;destino_sobras=placa'
    new, _ = separar_sobras_em_ponta(layouts, session=session, shapes=shapes)
    assert new == layouts
    session['params'] = 'stdNOTFill;separar_sobras=1'
    with patch('cad.layers_split._escolher_divisao_otima', return_value=(layouts, 'ponta')) as run:
        _, msg = separar_sobras_em_ponta(layouts, session=session, shapes=shapes)
        assert msg == 'ponta' and run.called


def test_converte_ponta_existente_para_placa_separada():
    shapes, session, layouts = scenario()
    source = dict(session, params='stdNOTFill;separar_sobras=1')
    tip, _ = separar_sobras_em_ponta(layouts, session=source, shapes=shapes, refile=False, _k=0)
    assert any(ly.get('tip_zone') for ly in tip)
    new, msg = separar_sobras_em_ponta(tip, session=session, shapes=shapes)
    assert msg and any(ly['layers'] == 2 for ly in new)
    assert not any(ly.get('tip_zone') for ly in new)
    assert [physical(new, s) for s in shapes] == [10, 8]


def test_dialogo_oferece_duas_opcoes_e_preserva_escolha():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Interface gráfica indisponível')
    root.withdraw()
    called = []
    try:
        dialog = SobrasConfigDialog(root, current_tip_mode='faixa', current_folga=0,
                                    current_destino='placa', on_save_cb=lambda *args: called.append(args))
        assert dialog.destino_var.get() == 'placa'
        assert str(dialog.entry_folga.cget('state')) == 'disabled'
        dialog._on_save()
        assert called == [('faixa', 0.0, 'placa')]
    finally:
        root.destroy()


def test_destino_salvo_sobrevive_a_preset_do_lote():
    shapes, session, layouts = scenario()
    new, msg = separar_sobras_em_ponta(layouts, session=session, shapes=shapes, params='FastNest')
    assert msg and any(ly['layers'] == 2 for ly in new)
    assert [physical(new, s) for s in shapes] == [10, 8]


def test_conversao_mal_sucedida_preserva_original():
    shapes, session, layouts = scenario()
    tip, _ = separar_sobras_em_ponta(layouts, session=dict(session, params='stdNOTFill;separar_sobras=1'),
                                      shapes=shapes, refile=False, _k=0)
    before = copy.deepcopy(tip)
    with patch('cad.layers_split.separar_sobras_camadas', side_effect=lambda base, **kw: (base, None)):
        result, msg = separar_sobras_em_ponta(tip, session=session, shapes=shapes)
    assert result == before and tip == before
    assert 'original preservado' in msg


def test_salvar_destino_preserva_opcoes_da_sessao(monkeypatch):
    from types import SimpleNamespace
    from cad.layers_rule import parse_session_params
    from ui.session_view import SessionView
    import ui.session_view as view
    saved = []
    scheduled = []
    session = {'id': 11, 'params': 'FastNest;separar_sobras=1;refile_auto=0;tip_mode=canto'}
    dummy = SimpleNamespace(session_data=session, db=SimpleNamespace(update_session=lambda sid, **kw: saved.append(kw['params'])),
                            var_separar_sobras=SimpleNamespace(get=lambda: True),
                            _on_decision_changed=lambda value: None,
                            reapply_sobras_separation=lambda enabled: saved.append(enabled),
                            after=lambda delay, callback: scheduled.append(callback))
    def fake_dialog(parent, **kwargs):
        assert kwargs['current_destino'] == 'ponta'
        kwargs['on_save_cb']('faixa', 12.0, 'placa')
    monkeypatch.setattr(view, 'SobrasConfigDialog', fake_dialog)
    SessionView.open_sobras_config_dialog(dummy)
    preset, options = parse_session_params(session['params'])
    assert preset == 'FastNest' and options['destino_sobras'] == 'placa'
    assert options['tip_mode'] == 'faixa' and options['refile_auto'] == '0'
    assert saved == [session['params']]
    assert len(scheduled) == 1
    scheduled[0]()
    assert saved == [session['params'], True]


def test_get_params_conserva_destino_e_configuracao_de_ponta():
    from types import SimpleNamespace
    from ui.session_view import SessionView
    from cad.layers_rule import parse_session_params
    dummy = SimpleNamespace(session_data={'params': 'FastNest;destino_sobras=placa;tip_mode=faixa;folga_ponta=12'},
                            cb_params=SimpleNamespace(get=lambda: 'FastNest'),
                            var_separar_sobras=SimpleNamespace(get=lambda: True),
                            var_refile_auto=SimpleNamespace(get=lambda: False))
    _, opts = parse_session_params(SessionView.get_params(dummy))
    assert opts['destino_sobras'] == 'placa' and opts['tip_mode'] == 'faixa'
    assert opts['folga_ponta'] == '12' and opts['separar_sobras'] == '1'


def test_reaplicar_atualiza_tabela_e_preserva_layout_se_banco_falhar(monkeypatch):
    from types import SimpleNamespace
    from ui.session_view import SessionView
    import ui.session_view as view
    shapes, session, layouts = scenario()
    session.update(id=1, shapes=shapes, layouts=layouts)
    old = copy.deepcopy(layouts)
    refreshed = []
    dummy = SimpleNamespace(session_data=session, db=SimpleNamespace(save_session_layouts=lambda *a: True),
                            get_session_layers=lambda: 4, refresh_layout_tab=lambda s: refreshed.append(s),
                            refresh_shapes_resto_column=lambda: None, winfo_toplevel=lambda: None, master=None)
    assert SessionView.reapply_sobras_separation(dummy, True) is True
    assert refreshed and any(ly['layers'] == 2 for ly in session['layouts'])
    session['layouts'] = old
    dummy.db = SimpleNamespace(save_session_layouts=lambda *a: False)
    with pytest.raises(RuntimeError):
        SessionView.reapply_sobras_separation(dummy, True)
    assert session['layouts'] == old


def test_dialogo_nao_fecha_se_persistencia_falha(monkeypatch):
    import ui.session_view as view
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Interface gráfica indisponível')
    root.withdraw()
    errors = []
    monkeypatch.setattr(view.messagebox, 'showerror', lambda *a, **kw: errors.append(a))
    def fail(*args):
        raise RuntimeError('banco indisponível')
    try:
        dialog = SobrasConfigDialog(root, on_save_cb=fail, current_destino='placa')
        dialog._on_save()
        assert dialog.winfo_exists() and errors
        dialog.destroy()
    finally:
        root.destroy()


def test_reaplicar_layout_ja_separado_nao_regrava_o_banco():
    from types import SimpleNamespace
    from ui.session_view import SessionView
    shapes, session, layouts = scenario()
    separated, _ = separar_sobras_em_ponta(layouts, session=session, shapes=shapes)
    session.update(id=7, shapes=shapes, layouts=separated)
    writes = []
    dummy = SimpleNamespace(session_data=session,
                            db=SimpleNamespace(save_session_layouts=lambda *args: writes.append(args)),
                            get_session_layers=lambda: 4, refresh_layout_tab=lambda data: None,
                            refresh_shapes_resto_column=lambda: None, winfo_toplevel=lambda: None, master=None)
    assert SessionView.reapply_sobras_separation(dummy, True) is True
    assert writes == []


def separated_last_row(extra_count=7):
    """Duas peças isoladas na última fileira de 4 camadas, sobras em outra placa."""
    contour = [{'x': 0, 'y': 0}, {'x': 90, 'y': 0},
               {'x': 90, 'y': 200}, {'x': 0, 'y': 200}]
    shape = {'id': 1, 'name': 'Molde_final', 'size': '41', 'sequence': 1,
             'pairs': 28 + extra_count, 'contour': contour}
    def piece(i, x, y, layers):
        return {'id': i, 'name': shape['name'], 'size': shape['size'],
                'shape': shape, 'contour': contour, 'x': x, 'y': y,
                'rotation': 0, 'layers': layers}
    base = [piece(i + 1, 10 + 91 * i, 10, 4) for i in range(12)]
    base += [piece(13 + i, 10 + 91 * i, 211, 4) for i in range(2)]
    extra = [piece(100 + i, 10 + 91 * i, 10, 2) for i in range(extra_count)]
    layouts = [{'layout_index': 0, 'layers': 4, 'pieces': base, 'width_mm': 1200, 'height_mm': 2400},
               {'layout_index': 1, 'layers': 2, 'pieces': extra, 'width_mm': 1200,
                'height_mm': 2400, 'sheet_width_mm': 1200, 'sheet_height_mm': 2400}]
    session = {'layers': 4, 'gap_mm': 1, 'strategy': 'flashnestsheet',
               'params': 'FastNest;separar_sobras=1;refile_auto=1;destino_sobras=placa',
               'material': {'width_mm': 1200, 'height_mm': 2400}}
    return shape, session, layouts


def test_duas_pecas_viram_quatro_na_placa_separada_sem_colisao_e_sem_placa_extra():
    from cad.layers_split import otimizar_sobras_existentes
    from cad.trim_engine import calculate_layout_trim_bounds, trim_layout_dict
    from cad.geometry import transform_contour, polygon_bbox, polygons_collide
    shape, session, layouts = separated_last_row()
    original = copy.deepcopy(layouts)
    new, msg = otimizar_sobras_existentes(layouts, session=session, shapes=[shape])
    assert msg and len(new) == 2
    assert [len(ly['pieces']) for ly in new] == [12, 11]
    assert physical(new, shape) == physical(layouts, shape) == 70
    assert layouts == original
    before = sum(calculate_layout_trim_bounds(ly['pieces'])[1] for ly in layouts)
    after = sum(calculate_layout_trim_bounds(ly['pieces'])[1] for ly in new)
    assert after < before - 190
    for ly in new:
        trim_layout_dict(ly, gap_mm=1)
        polys = [transform_contour(p['contour'], p['x'], p['y'], p.get('rotation', 0)) for p in ly['pieces']]
        boxes = [polygon_bbox(q) for q in polys]
        for i, poly in enumerate(polys):
            for j in range(i + 1, len(polys)):
                assert not polygons_collide(poly, polys[j], gap=1, bbox_a=boxes[i], bbox_b=boxes[j])
    repeated, _ = separar_sobras_em_ponta(new, session=session, shapes=[shape])
    assert repeated == new


def test_placa_separada_preserva_layout_quando_nao_ha_economia_ou_encaixe_falha():
    from cad.layers_split import otimizar_sobras_existentes
    shape, session, layouts = separated_last_row(extra_count=12)
    original = copy.deepcopy(layouts)
    new, msg = otimizar_sobras_existentes(layouts, session=session, shapes=[shape])
    assert new == original and not msg
    shape, session, layouts = separated_last_row()
    original = copy.deepcopy(layouts)
    with patch('cad.layers_split.nest_multi_sheet', return_value={'layouts': [dict(layouts[-1], pieces=[])]}):
        new, msg = otimizar_sobras_existentes(layouts, session=session, shapes=[shape])
    assert new == original and not msg
    session['params'] = session['params'].replace('separar_sobras=1', 'separar_sobras=0')
    with patch('cad.layers_split.nest_multi_sheet') as nesting:
        new, msg = otimizar_sobras_existentes(layouts, session=session, shapes=[shape])
        assert new == original and not msg and not nesting.called


def test_alternar_placa_otimizada_e_ponta_preserva_producao():
    from cad.layers_split import otimizar_sobras_existentes
    shape, session, layouts = separated_last_row()
    optimized, _ = otimizar_sobras_existentes(layouts, session=session, shapes=[shape])
    tip_session = dict(session, params=session['params'].replace('destino_sobras=placa', 'destino_sobras=ponta'))
    tip, _ = separar_sobras_em_ponta(optimized, session=tip_session, shapes=[shape], refile=False)
    assert any(ly.get('tip_zone') for ly in tip)
    assert physical(tip, shape) == 70
    separated, _ = separar_sobras_em_ponta(tip, session=session, shapes=[shape])
    assert not any(ly.get('tip_zone') for ly in separated)
    assert physical(separated, shape) == 70


def test_gravacao_e_recarga_da_placa_otimizada(tmp_path):
    from cad.layers_split import otimizar_sobras_existentes
    from database import DatabaseManager
    shape, session, layouts = separated_last_row()
    new, _ = separar_sobras_em_ponta(layouts, session=session, shapes=[shape])
    assert [len(ly['pieces']) for ly in new] == [12, 11]
    db = DatabaseManager(str(tmp_path / 'sobras.db'), backend='sqlite')
    sid = db.create_session(name='Placa de sobras otimizada')
    assert db.save_session_layouts(sid, new)
    loaded = db.get_session_layouts(sid)
    assert [len(ly['pieces']) for ly in loaded] == [12, 11]
    assert physical(loaded, shape) == 70


def test_segundo_preenchimento_usa_ultima_base_antes_da_placa_de_sobras():
    from cad.layers_split import preencher_buracos_apos_separacao, otimizar_sobras_existentes
    shape, session, layouts = separated_last_row()
    base = layouts[0]
    # Reconstitui a fileira antes de seis peças preencherem vãos da primeira base.
    six = [dict(base['pieces'][12], id=200 + i, x=10 + 91 * (i + 2)) for i in range(6)]
    base['pieces'].extend(six)
    first = dict(base, pieces=[])
    original_extra = copy.deepcopy(layouts[-1])
    def fill(plates, **kwargs):
        assert len(plates) == 2 and all(ly['layers'] == 4 for ly in plates)
        assert kwargs['shapes'][0]['pairs'] == 2 * sum(len(ly['pieces']) for ly in plates)
        plates[0]['pieces'] = plates[1]['pieces'][-6:]
        del plates[1]['pieces'][-6:]
        return plates, {'movidas': 6, 'placas_removidas': 0}
    with patch('cad.nesting_engine.preencher_buracos_em_placas', side_effect=fill):
        filled, info = preencher_buracos_apos_separacao([first] + layouts, session=session, shapes=[shape])
    assert info['movidas'] == 6
    assert filled[-1]['pieces'] == original_extra['pieces']
    optimized, _ = otimizar_sobras_existentes(filled, session=session, shapes=[shape])
    assert [len(ly['pieces']) for ly in optimized] == [6, 12, 11]
    assert physical(optimized, shape) == physical(filled, shape)
