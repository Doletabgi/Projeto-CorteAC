"""Verificações do assistente: achados úteis, orientação e ações sem alterar dados."""

import copy
import gc
import json
import threading
import time
import tkinter as tk

import pytest

from cad.session_diagnostics import check_session
from ui.debug_panel import DebugPanel


@pytest.fixture
def context():
    return {
        'session_id': 123, 'session_name': 'Pedido de exemplo', 'mode': 'custom',
        'material': {'code': 'EVA', 'width_mm': 1000, 'height_mm': 2000},
        'shapes': [{'pairs': 12, 'contour_points': 4}], 'gap_mm': 1,
        'margins': dict(left=10, right=10, top=10, bottom=10),
        'layouts_count': 1, 'placed_count': 12,
    }


def by_key(context):
    return {row['key']: row for row in check_session(context)}


def test_valid_session_is_read_only(context):
    original = copy.deepcopy(context)
    assert all(row['status'] == 'ok' for row in check_session(context))
    assert context == original


def test_empty_session_explains_what_to_fill():
    checks = by_key({})
    assert checks['material']['status'] == 'attention'
    assert checks['material']['target'] == 'materials'
    assert checks['shapes']['status'] == 'attention'
    assert checks['shapes']['target'] == 'shapes'
    assert checks['layouts']['status'] == 'info'


@pytest.mark.parametrize('value', [-1, 1.5, 'abc', float('nan'), None])
def test_invalid_demand_is_not_reported_as_ready(context, value):
    context['shapes'][0]['pairs'] = value
    assert by_key(context)['shapes']['status'] == 'attention'


def test_only_requested_shapes_need_geometry(context):
    context['shapes'].append({'pairs': 0, 'contour_points': 0})
    assert by_key(context)['contours']['status'] == 'ok'
    context['shapes'][0]['contour_points'] = 0
    assert by_key(context)['contours']['status'] == 'attention'


@pytest.mark.parametrize('field,value', [('gap_mm', 'nan'), ('gap_mm', -1), ('margins', dict(left=500, right=500, top=0, bottom=0))])
def test_invalid_cutting_spaces_have_actionable_result(context, field, value):
    context[field] = value
    check = by_key(context)['spacing']
    assert check['status'] == 'attention'
    assert check['target'] == 'general'


def test_zero_gap_and_missing_layout_are_information(context):
    context.update(gap_mm=0, placed_count=0, layouts_count=0)
    checks = by_key(context)
    assert checks['spacing']['status'] == 'info'
    assert checks['layouts']['status'] == 'info'
    assert 'colisões' in by_key(dict(context, placed_count=12))['layouts']['guidance']


@pytest.fixture
def panel(context, monkeypatch):
    # Objetos de raízes Tk anteriores precisam ser coletados na thread principal.
    gc.collect()
    monkeypatch.setenv('CORTEAC_BACKEND', 'nfp')
    monkeypatch.setenv('CORTEAC_NFP_SANITY', '0')
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tkinter indisponível')
    root.withdraw()
    widget = DebugPanel(root, get_context=lambda: context)
    widget.pack(fill='both', expand=True)
    yield widget
    root.destroy()
    gc.collect()


def test_checks_refresh_and_point_to_the_right_tab(panel, context):
    opened = []
    panel.on_open_section = opened.append
    panel.refresh_context()
    context['material'] = {}
    panel.refresh_context()
    assert panel.results.selection() == ('material',)
    assert panel.btn_open_section.cget('text') == 'Abrir Materiais'
    panel._open_selected_section()
    assert opened == ['materials']
    assert context['material'] == {}


def test_report_contains_current_findings_without_running_nesting(panel, context, tmp_path, monkeypatch):
    path = tmp_path / 'suporte.txt'
    monkeypatch.setattr('ui.debug_panel.filedialog.asksaveasfilename', lambda **kw: str(path))
    context['material'] = {}
    panel.issue_var.set('support')
    panel._run_guided_action()
    report = path.read_text(encoding='utf-8')
    assert 'Sessão #123' in report
    assert 'Nenhum material selecionado' in report
    assert 'Preciso de ajuda' in report
    assert 'não analisa colisões' in report


def test_advanced_settings_preserve_auto_lock_and_single_use_profile(panel, monkeypatch):
    panel.set_mode('auto')
    assert str(panel.cb_engine.cget('state')) == 'disabled'
    panel.set_mode('custom')
    assert str(panel.cb_engine.cget('state')) == 'readonly'
    panel.set_engine('python')
    panel.var_profile.set(True)
    panel.refresh_context()
    assert panel.get_engine() == 'python'
    assert panel.is_profile_requested() is True
    assert panel.is_profile_requested() is False


def test_cleanup_waits_for_live_nesting(panel, context, monkeypatch):
    calls = []
    monkeypatch.setattr('cad.geometry.clear_transform_cache', lambda: calls.append('geometry'))
    monkeypatch.setattr('cad.nfp.clear_nfp_cache', lambda: calls.append('nfp'))
    monkeypatch.setattr('cad.macro_engine.clear_macro_caches', lambda: calls.append('macro'))
    context['nesting_in_progress'] = True
    panel.clear_caches()
    assert calls == []
    context['nesting_in_progress'] = False
    panel.clear_caches()
    assert calls == ['geometry', 'nfp', 'macro']
    assert 'liberada' in panel.lbl_action_msg.cget('text')


@pytest.mark.parametrize('failure', [False, True])
def test_background_test_reports_completion_and_errors_on_the_ui(panel, tmp_path, monkeypatch, failure):
    path = tmp_path / 'desempenho.json'
    monkeypatch.setattr('ui.debug_panel.filedialog.asksaveasfilename', lambda **kw: str(path))
    ui_thread = threading.get_ident()

    def benchmark(**kwargs):
        assert threading.get_ident() != ui_thread
        if failure:
            raise RuntimeError('Teste interrompido')
        return {'pieces': kwargs['pieces'], 'runs': kwargs['runs']}

    monkeypatch.setattr('tools.bench_nest.run_benchmark', benchmark)
    panel.export_benchmark()
    deadline = time.monotonic() + 3
    while panel._benchmark_running and time.monotonic() < deadline:
        panel.update()
        time.sleep(0.01)
    assert panel._benchmark_running is False
    assert panel.btn_export_bench.cget('state') == 'normal'
    if failure:
        assert 'Teste interrompido' in panel.lbl_action_msg.cget('text')
    else:
        assert json.loads(path.read_text()) == {'pieces': 60, 'runs': 2}
        assert 'Teste concluído' in panel.lbl_action_msg.cget('text')


def test_assistant_reads_the_problem_and_guides_the_actual_pending_item(panel, context):
    context['material'] = {}
    assistant = panel.assistant
    assistant.respond('Não consigo gerar meu encaixe')
    assert assistant.issue == 'generate'
    assert 'Nenhum material selecionado' in assistant.history[-1]['text']
    assert 'Materiais' in assistant.history[-1]['text']
    assert assistant.progress['value'] == 3


def test_assistant_checks_corrections_on_return_without_assuming_success(panel, context):
    context['material'] = {}
    opened = []
    panel.on_open_section = opened.append
    assistant = panel.assistant
    assistant.choose('Conferir', 'check')
    assistant.choose('Abrir Materiais', 'open:materials')
    assert opened == ['materials']
    panel.on_reopen()
    assert 'Nenhum material selecionado' in assistant.history[-1]['text']
    context['material'] = {'code': 'EVA', 'width_mm': 1000, 'height_mm': 2000}
    assistant.choose('Já ajustei', 'recheck')
    assert 'há peças no layout' in assistant.history[-1]['text']
    assert assistant.phase != 'complete'
    assistant.choose('Sim, funcionou', 'resolved')
    assert assistant.phase == 'complete'


def test_assistant_includes_the_users_description_in_the_support_report(panel, context, tmp_path, monkeypatch):
    path = tmp_path / 'conversa.txt'
    monkeypatch.setattr('ui.debug_panel.filedialog.asksaveasfilename', lambda **kw: str(path))
    assistant = panel.assistant
    assistant.choose('Preciso de suporte', 'support')
    assistant.respond('Ao gerar aparece a mensagem: nenhuma peça coube.')
    assert assistant.phase == 'report'
    assert not path.exists()
    assistant.choose('Salvar conversa e relatório', 'save')
    report = path.read_text(encoding='utf-8')
    assert 'Conversa com o assistente' in report
    assert 'Você: Ao gerar aparece a mensagem: nenhuma peça coube.' in report
    assert 'Motivo: Preciso de suporte' in report
    assert assistant.phase == 'report_saved'


def test_assistant_does_not_claim_cleanup_happened_while_nesting(panel, context):
    context['nesting_in_progress'] = True
    assistant = panel.assistant
    assistant.choose('O cálculo está lento', 'slow')
    assert 'sendo calculado' in assistant.history[-1]['text']
    assistant.choose('Liberar memória', 'clear')
    assert 'Não consegui concluir' in assistant.history[-1]['text']
    assert assistant.phase != 'resolution'


def test_assistant_keeps_cancelled_report_available_for_retry(panel, monkeypatch):
    monkeypatch.setattr('ui.debug_panel.filedialog.asksaveasfilename', lambda **kw: '')
    assistant = panel.assistant
    assistant.choose('Preciso de suporte', 'support')
    assistant.respond('O programa demorou para gerar.')
    assistant.choose('Salvar', 'save')
    assert assistant.phase == 'report'
    assert 'Relatório salvo' not in assistant.history[-1]['text']


def test_assistant_restart_only_clears_the_conversation(panel, context):
    original = copy.deepcopy(context)
    assistant = panel.assistant
    assistant.respond('Quero conferir a sessão')
    panel.var_profile.set(True)
    assistant.restart()
    assert len(assistant.history) == 1
    assert assistant.phase == 'welcome'
    assert context == original
    assert panel.var_profile.get() is True


def test_assistant_handles_an_immediately_completed_performance_test(panel):
    assistant = panel.assistant

    def immediate_test():
        assistant.benchmark_finished(True, 'resultado.json')
        return True

    assistant.test_performance = immediate_test
    assistant.choose('Testar com exemplos', 'test')
    assert assistant.phase == 'test_complete'
    assert 'terminou' in assistant.history[-1]['text']
    assert 'em andamento' not in assistant.history[-1]['text']


def test_assistant_accepts_typed_yes_after_asking_if_the_problem_was_resolved(panel):
    assistant = panel.assistant
    assistant.respond('Quero conferir minha sessão')
    assert assistant.phase == 'resolution'
    assistant.respond('sim')
    assert assistant.phase == 'complete'
