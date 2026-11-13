"""Prévia exige ação de imprimir e mantém as páginas conferidas pelo usuário."""
from unittest.mock import MagicMock
from test_production_dashboard_export import panel


def test_preview_navigation_zoom_and_print_only_after_click(panel, monkeypatch):
    def fail(title, message, **kwargs):
        raise AssertionError(message)
    monkeypatch.setattr('ui.production_dashboard.messagebox.showerror', fail)
    report = panel._report()
    report['tables'][0][2][:] = [(f'Material {i}', '1', '2', '80', '0.4') for i in range(55)]
    monkeypatch.setattr(panel, '_report', lambda: report)
    printer = MagicMock()
    saver = MagicMock()
    monkeypatch.setattr(panel, '_print_report', printer)
    monkeypatch.setattr(panel, 'save_as_pdf', saver)
    preview = panel.do_print()
    try:
        preview.update()
        assert len(preview.pages) > 1
        assert preview._photo is not None
        printer.assert_not_called()
        assert str(preview.previous.cget('state')) == 'disabled'
        preview.next.invoke()
        assert preview.page_index == 1
        assert 'Página 2' in preview.page_label.cget('text')
        preview.show_page(len(preview.pages) - 1)
        assert str(preview.next.cget('state')) == 'disabled'
        preview.zoom_choice.set('125%')
        preview.change_zoom()
        assert preview.zoom == 1.25
        assert preview.canvas.bbox('all')[2] > preview.canvas.winfo_width()
        preview.zoom_choice.set('Ajustar página')
        preview.change_zoom()
        assert preview.zoom is None
        panel.material.set('B — Lona')
        buttons = preview.winfo_children()[0].winfo_children()
        next(b for b in buttons if b.cget('text') == 'Imprimir...').invoke()
        printer.assert_called_once_with(report, preview.pages)
        next(b for b in buttons if b.cget('text') == 'Salvar PDF...').invoke()
        saver.assert_called_once_with(report, preview.pages)
    finally:
        preview.destroy()


def test_closing_preview_does_not_print_or_save(panel, monkeypatch):
    def fail(title, message, **kwargs):
        raise AssertionError(message)
    monkeypatch.setattr('ui.production_dashboard.messagebox.showerror', fail)
    printer, saver = MagicMock(), MagicMock()
    monkeypatch.setattr(panel, '_print_report', printer)
    monkeypatch.setattr(panel, 'save_as_pdf', saver)
    preview = panel.do_print()
    preview.update()
    preview.destroy()
    printer.assert_not_called()
    saver.assert_not_called()


def test_pdf_uses_preview_pages_without_rendering_again(tmp_path, monkeypatch):
    from PIL import Image
    from ui.production_dashboard_report import save_report_pdf
    render = MagicMock(side_effect=AssertionError('A prévia não deve ser recalculada'))
    monkeypatch.setattr('ui.production_dashboard_report.render_report', render)
    page = Image.new('RGB', (120, 80), 'white')
    try:
        path = tmp_path / 'previa.pdf'
        save_report_pdf({}, path, pages=[page])
        assert path.read_bytes().startswith(b'%PDF-')
        assert page.getpixel((0, 0)) == (255, 255, 255)
        render.assert_not_called()
    finally:
        page.close()
