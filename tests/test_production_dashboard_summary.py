from datetime import date
from unittest.mock import MagicMock
import pytest
from PIL import ImageDraw
from analytics.production_dashboard import summarize
from ui.production_dashboard_report import build_compact_report, render_report
from test_production_dashboard_export import panel


@pytest.mark.parametrize('mode,value,expected', [
    ('day', '2026-01-02', 'Sessões: 1'),
    ('month', '2026-01', 'Sessões: 2'),
    ('month', '2024-02', 'Sessões: 0'),
])
def test_periodo_e_previa_do_resumo(panel, monkeypatch, mode, value, expected):
    monkeypatch.setattr('ui.production_dashboard.simpledialog.askstring', lambda *a, **k: value)
    preview = MagicMock()
    monkeypatch.setattr(panel, '_open_preview', preview)
    panel.show_compact_summary(mode)
    report = preview.call_args.args[0]
    assert expected in report['summary']
    if value == '2024-02':
        assert '29/02/2024' in report['filters']
    pages = render_report(report, 100)
    assert len(pages) == 1
    for page in pages:
        page.close()


def test_resumo_respeita_material_selecionado(panel, monkeypatch):
    panel.material.set('B — Lona')
    monkeypatch.setattr('ui.production_dashboard.simpledialog.askstring', lambda *a, **k: '2026-01')
    preview = MagicMock()
    monkeypatch.setattr(panel, '_open_preview', preview)
    panel.show_compact_summary('month')
    report = preview.call_args.args[0]
    assert 'Pares planejados: 5' in report['summary']
    assert 'B — Lona' in report['filters']


@pytest.mark.parametrize('value', [None, '2026-02-30', 'inválido'])
def test_cancelamento_e_data_invalida_nao_imprimem(panel, monkeypatch, value):
    monkeypatch.setattr('ui.production_dashboard.simpledialog.askstring', lambda *a, **k: value)
    errors, preview = MagicMock(), MagicMock()
    monkeypatch.setattr('ui.production_dashboard.messagebox.showerror', errors)
    monkeypatch.setattr(panel, '_open_preview', preview)
    panel.show_compact_summary('day')
    preview.assert_not_called()
    assert errors.call_count == (0 if value is None else 1)


def test_muitos_usuarios_cabem_em_uma_folha_sem_perder_totais(monkeypatch):
    sessions = [{'id': 1, 'created_at': '2026-01-01', 'shapes_json': '[{"pairs": 100}]'}]
    layouts = [{'session_id': 1, 'width_mm': 1000, 'height_mm': 1000, 'yield_percent': 80,
                'production_user': str(i) + 'W' * 300} for i in range(100)]
    data = summarize(sessions, layouts)
    report = build_compact_report(data, date(2026, 1, 1), date(2026, 1, 31), 'Material' * 500, True)
    rows = report['tables'][0][2]
    assert len(rows) == 5
    assert sum(int(row[1]) for row in rows) == 100
    assert sum(float(row[2]) for row in rows) == 100
    assert rows[-1][0] == 'Outros (96 usuários)'
    original = ImageDraw.ImageDraw.text
    def check(draw, xy, value, *a, **kw):
        bounds = draw.textbbox(xy, str(value), font=kw['font'])
        assert bounds[2] < draw._image.width - 15
        assert bounds[3] < draw._image.height - 10
        return original(draw, xy, value, *a, **kw)
    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', check)
    pages = render_report(report, 100)
    assert len(pages) == 1
    for page in pages:
        page.close()
