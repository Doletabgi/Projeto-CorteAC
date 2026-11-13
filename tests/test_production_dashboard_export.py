"""Exportação e impressão do painel, com dados isolados e sem impressora real."""
from types import SimpleNamespace
from unittest.mock import MagicMock
import sqlite3
import tkinter as tk

from PIL import ImageDraw
import pytest

from ui.production_dashboard import ProductionDashboard
from ui.production_dashboard_report import render_report


@pytest.fixture
def panel(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Interface gráfica não disponível')
    root.withdraw()
    path = tmp_path / 'dashboard.sqlite'
    with sqlite3.connect(path) as conn:
        conn.executescript('''
            create table materials (id text, name text);
            create table sessions (id integer, order_id integer, material_id text, created_at text, shapes_json text);
            create table layouts (session_id integer, width_mm real, height_mm real, yield_percent real, yield_pct real);
            insert into materials values ('A', 'Couro'), ('B', 'Lona');
            insert into sessions values (1, 9, 'A', '2026-01-01', '[{"pairs": 20}]'),
                                        (2, 10, 'B', '2026-01-02', '[{"pairs": 5}]');
            insert into layouts values (1, 1000, 1000, 50, null), (2, 2000, 1000, 80, null);
        ''')

    class DB:
        def get_connection(self):
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            return conn

    window = ProductionDashboard(root, DB())
    try:
        yield window
    finally:
        window.destroy()
        root.destroy()


def test_report_applies_current_filters_and_contains_both_tables(panel):
    panel.start.set('2026-01-02')
    panel.end.set('2026-01-02')
    panel.material.set('B — Lona')
    report = panel._report()
    assert '2026-01-02' in report['filters'] and 'B — Lona' in report['filters']
    assert 'Pares planejados: 5' in report['summary']
    material, days, users = report['tables']
    assert material[2] == [('B — Lona', '1', '2.00', '80.00', '0.40')]
    assert days[2] == [('2026-01-02', '1', '2.00', '80.00', '0.40')]
    assert users[2] == [('Não informado', '1', '2.00', '80.00', '0.40')]


def test_responsaveis_registrados_aparecem_na_impressao_com_os_filtros(panel, monkeypatch):
    with panel.db.get_connection() as conn:
        conn.execute('ALTER TABLE layouts ADD COLUMN production_user TEXT')
        conn.execute("UPDATE layouts SET production_user = 'Ana' WHERE session_id = 1")
        conn.execute("UPDATE layouts SET production_user = 'Bruno' WHERE session_id = 2")
    report = panel._report()
    assert report['tables'][2][2] == [
        ('Ana', '1', '1.00', '50.00', '0.50'),
        ('Bruno', '1', '2.00', '80.00', '0.40'),
    ]
    panel.material.set('B — Lona')
    report = panel._report()
    assert report['tables'][2][2] == [('Bruno', '1', '2.00', '80.00', '0.40')]
    texts = []
    original = ImageDraw.ImageDraw.text
    def record(draw, xy, value, *args, **kwargs):
        texts.append(str(value))
        return original(draw, xy, value, *args, **kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', record)
    pages = render_report(report, dpi=100)
    assert 'Por usuário responsável' in texts
    assert 'Bruno' in texts
    assert 'Ana' not in texts
    for page in pages:
        page.close()


def test_pdf_saved_and_cancel_does_not_render(panel, tmp_path, monkeypatch):
    target = tmp_path / 'painel.pdf'
    info = MagicMock()
    monkeypatch.setattr('ui.production_dashboard.messagebox.showinfo', info)
    monkeypatch.setattr('ui.production_dashboard.filedialog.asksaveasfilename', lambda **kw: str(target))
    panel.save_as_pdf()
    assert target.read_bytes().startswith(b'%PDF-')
    assert info.called
    monkeypatch.setattr('ui.production_dashboard.filedialog.asksaveasfilename', lambda **kw: '')
    render = MagicMock()
    monkeypatch.setattr('ui.production_dashboard_report.save_report_pdf', render)
    panel.save_as_pdf()
    render.assert_not_called()


def test_invalid_filters_block_save_and_print(panel, monkeypatch):
    errors, dialog, render = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr('ui.production_dashboard.messagebox.showerror', errors)
    monkeypatch.setattr('ui.production_dashboard.filedialog.asksaveasfilename', dialog)
    monkeypatch.setattr('ui.production_dashboard_report.save_report_pdf', render)
    panel.start.set('2026-02-02')
    panel.end.set('2026-01-01')
    panel.save_as_pdf()
    panel.do_print()
    assert errors.call_count == 2
    dialog.assert_not_called()
    render.assert_not_called()


def test_print_sends_pdf_as_argument_and_cleans_spool_file(panel, monkeypatch):
    monkeypatch.setattr('ui.production_dashboard.sys.platform', 'linux')
    monkeypatch.setattr('ui.production_dashboard.shutil.which', lambda cmd: '/usr/bin/lp')
    monkeypatch.setattr('ui.production_dashboard.messagebox.showinfo', MagicMock())
    errors = MagicMock()
    monkeypatch.setattr('ui.production_dashboard.messagebox.showerror', errors)

    def send(args, **kwargs):
        from pathlib import Path
        assert args[0] == 'lp' and len(args) == 2
        assert not kwargs.get('shell')
        assert Path(args[1]).read_bytes().startswith(b'%PDF-')
        return SimpleNamespace(returncode=0)

    spool = MagicMock(side_effect=send)
    monkeypatch.setattr('ui.production_dashboard.subprocess.run', spool)
    panel._print_report(panel._report())
    from pathlib import Path
    assert not Path(spool.call_args.args[0][1]).exists()
    errors.assert_not_called()


def test_rejected_print_does_not_claim_success(panel, monkeypatch):
    monkeypatch.setattr('ui.production_dashboard.sys.platform', 'linux')
    monkeypatch.setattr('ui.production_dashboard.shutil.which', lambda cmd: '/usr/bin/lp')
    monkeypatch.setattr('ui.production_dashboard.subprocess.run', lambda *a, **kw: SimpleNamespace(returncode=1, stderr='Sem impressora'))
    info, errors = MagicMock(), MagicMock()
    monkeypatch.setattr('ui.production_dashboard.messagebox.showinfo', info)
    monkeypatch.setattr('ui.production_dashboard.messagebox.showerror', errors)
    panel._print_report(panel._report())
    info.assert_not_called()
    assert 'Sem impressora' in errors.call_args.args[1]


def test_windows_print_keeps_pdf_for_async_reader(panel, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr('ui.production_dashboard.sys.platform', 'win32')
    startfile = MagicMock()
    monkeypatch.setattr('ui.production_dashboard.os.startfile', startfile, raising=False)
    monkeypatch.setattr('ui.production_dashboard.messagebox.showinfo', MagicMock())
    panel._print_report(panel._report())
    path, verb = startfile.call_args.args
    try:
        assert verb == 'print' and Path(path).read_bytes().startswith(b'%PDF-')
    finally:
        Path(path).unlink(missing_ok=True)


def test_report_paginates_all_rows_without_clipping(panel, monkeypatch):
    report = panel._report()
    report['tables'][0][2][:] = [(f'Material único {i}', '1', '2.00', '80.00', '0.40') for i in range(100)]
    report['tables'][0][2].append(('NomeMuitoLongo' * 500, '1', '2.00', '80.00', '0.40'))
    texts = []
    original = ImageDraw.ImageDraw.text

    def record(draw, xy, value, **kwargs):
        bounds = draw.textbbox(xy, value, font=kwargs['font'])
        assert bounds[2] < draw._image.width - 15
        assert bounds[3] < draw._image.height - 10
        texts.append(str(value))
        return original(draw, xy, value, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', record)
    pages = render_report(report, dpi=100)
    try:
        assert len(pages) > 4
        assert all(page.width > page.height for page in pages)
        assert texts.count('Painel de Produção — Planejamento') == len(pages)
        assert texts.count('Layouts válidos') >= len(pages)
        for i in range(100):
            assert f'Material único {i}' in texts
        assert 'Evolução por dia' in texts
    finally:
        for page in pages:
            page.close()


def test_empty_report_keeps_limitations_and_both_sections(panel, monkeypatch):
    panel.start.set('2099-01-01')
    report = panel._report()
    texts = []
    original = ImageDraw.ImageDraw.text

    def record(draw, xy, value, **kwargs):
        texts.append(str(value))
        return original(draw, xy, value, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', record)
    pages = render_report(report, dpi=100)
    try:
        assert 'Indisponível' in '\n'.join(texts)
        assert texts.count('Nenhum registro para os filtros selecionados.') == 3
        assert 'não é desperdício medido.' in ' '.join(texts)
    finally:
        for page in pages:
            page.close()


def test_no_spooler_keeps_pdf_and_explains_fallback(panel, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr('ui.production_dashboard.sys.platform', 'linux')
    monkeypatch.setattr('ui.production_dashboard.shutil.which', lambda cmd: None)
    info = MagicMock()
    monkeypatch.setattr('ui.production_dashboard.messagebox.showinfo', info)
    panel._print_report(panel._report())
    message = info.call_args.args[1]
    path = Path(message.split('\n')[-1])
    try:
        assert 'Impressão direta indisponível' in message
        assert path.read_bytes().startswith(b'%PDF-')
    finally:
        path.unlink(missing_ok=True)
