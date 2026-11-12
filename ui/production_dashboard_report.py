"""Relatório A4 do painel, com paginação independente da área visível da tela."""
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SOURCE = ('Fonte: sessões e layouts persistidos. Área não ocupada é estimativa '
          'geométrica por camada; não é desperdício medido.')
LIMITS = ('Produção efetiva, corte concluído, tempo de processamento e filtro por '
          'operador: indisponíveis até haver registros confiáveis.')


def render_report(report, dpi=150):
    """Inclui todas as linhas das duas tabelas, repetindo cabeçalhos nas continuações."""
    scale = dpi / 72
    width, height = 841.89, 595.28  # A4 paisagem
    margin, bottom = 30, height - 36
    pages, fonts = [], {}
    stamp = datetime.now().strftime('%d/%m/%Y %H:%M')

    def font(size=9, bold=False):
        key = (size, bold)
        if key not in fonts:
            filename = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
            for path in (Path(__file__).resolve().parent.parent / 'assets' / 'fonts' / filename,
                         Path('/usr/share/fonts/truetype/dejavu') / filename,
                         'arialbd.ttf' if bold else 'arial.ttf'):
                try:
                    fonts[key] = ImageFont.truetype(str(path), round(size * scale))
                    break
                except OSError:
                    continue
            else:
                raise RuntimeError('Fonte TrueType não disponível para o relatório.')
        return fonts[key]

    def wrap(value, available, size=9, bold=False):
        # Quebra inclusive identificadores longos sem espaços.
        lines = []
        for paragraph in str(value).split('\n'):
            line = ''
            for word in paragraph.split():
                candidate = f'{line} {word}'.strip()
                if font(size, bold).getlength(candidate) <= available * scale:
                    line = candidate
                    continue
                if line:
                    lines.append(line)
                    line = ''
                for char in word:
                    if line and font(size, bold).getlength(line + char) > available * scale:
                        lines.append(line)
                        line = ''
                    line += char
            lines.append(line)
        return lines

    def text(x, y, value, size=9, bold=False):
        draw.text((round(x * scale), round(y * scale)), str(value),
                  fill='#172033', font=font(size, bold))

    def new_page():
        nonlocal draw, y
        page = Image.new('RGB', (round(width * scale), round(height * scale)), 'white')
        pages.append(page)
        draw = ImageDraw.Draw(page)
        text(margin, 22, 'Painel de Produção — Planejamento', 15, True)
        text(margin, 45, f'Planejamento salvo • período pela data de criação da sessão • Emitido em {stamp}', 8)
        y = 62
        for line in wrap(report['filters'], width - 2 * margin, 8):
            text(margin, y, line, 8)
            y += 11
        y += 8

    def paragraph(value, size=9):
        nonlocal y
        for line in wrap(value, width - 2 * margin, size):
            if y + 14 > bottom:
                new_page()
            text(margin, y, line, size)
            y += 14
        y += 7

    draw, y = None, 0
    new_page()
    paragraph(report['summary'], 10)
    paragraph(report['notice'], 8)
    paragraph(SOURCE, 8)
    paragraph(LIMITS, 8)
    widths = [241.89, 95, 145, 140, 160]

    def table_row(cells, bold=False):
        nonlocal y
        lines = [wrap(cell, col_width - 12, 9, bold) for cell, col_width in zip(cells, widths)]
        row_height = max(len(cell) for cell in lines) * 13 + 10
        return lines, row_height

    def draw_row(lines, row_height, bold=False):
        nonlocal y
        x = margin
        for cell, col_width in zip(lines, widths):
            draw.rectangle((round(x * scale), round(y * scale),
                            round((x + col_width) * scale), round((y + row_height) * scale)),
                           fill='#e9eef5' if bold else 'white', outline='#cbd5e1', width=1)
            for index, line in enumerate(cell):
                text(x + 6, y + 4 + index * 13, line, 9, bold)
            x += col_width
        y += row_height

    for title, columns, rows in report['tables']:
        headers, header_height = table_row(columns, True)

        def heading():
            nonlocal y
            text(margin, y, title, 11, True)
            y += 21
            draw_row(headers, header_height, True)

        if y + 21 + header_height + 23 > bottom:
            new_page()
        heading()
        if not rows:
            paragraph('Nenhum registro para os filtros selecionados.')
        for row in rows:
            lines, _ = table_row(row)
            # Uma célula pode ocupar mais de uma página; cada trecho preserva as margens.
            offset = 0
            total_lines = max(len(cell) for cell in lines)
            while offset < total_lines:
                capacity = int((bottom - y - 10) // 13)
                if capacity < 1:
                    new_page()
                    heading()
                    capacity = int((bottom - y - 10) // 13)
                count = min(capacity, total_lines - offset)
                draw_row([cell[offset:offset + count] for cell in lines], count * 13 + 10)
                offset += count
        y += 14

    for number, page in enumerate(pages, 1):
        draw = ImageDraw.Draw(page)
        text(margin, height - 23, f'Painel de Produção • Página {number} de {len(pages)}', 8)
    return pages


def save_report_pdf(report, path):
    pages = render_report(report)
    try:
        pages[0].save(str(path), 'PDF', resolution=150, save_all=True, append_images=pages[1:])
    finally:
        for page in pages:
            page.close()
