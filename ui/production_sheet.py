"""Ficha de produção: projeção somente leitura das regras industriais existentes."""
from collections import defaultdict
import math
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageFont
from cad.layers_rule import layers_for_piece, shape_multiplier, clamp_tip_zone, format_enfesto_operator_text, resolve_layout_layers
from cad.geometry import transform_contour
from cad.barcode import generate_code128_pillow
from ui.units import format_m


def plate_length_mm(plate, defaults=None):
    """Metragem linear: comprimento original × camadas, antes do refile."""
    data = {**(defaults or {}), **plate}
    trim = data.get('trim_cut_line') or {}
    height = data.get('height_mm') or data.get('sheet_h_mm')
    if trim.get('enabled', True) and trim.get('orig_h'):
        height = trim['orig_h']
    try:
        height = float(height)
        layers = resolve_layout_layers(
            layout=data, session=data.get('session'), material=data.get('material'),
            default=data.get('material_layers') or 2,
        )
        total = height * layers
    except (TypeError, ValueError, OverflowError):
        return None
    return total if math.isfinite(total) and height > 0 and layers > 0 else None


def production_rows(pieces, shapes, layout):
    """Não usa piece.pairs (demanda) como produção nem mistura camadas de placas."""
    index = {}
    by_name_size = {}
    for s in shapes:
        for field in ('id', 'shape_id'):
            if s.get(field) is not None:
                index[str(s[field])] = s
        by_name_size[(s.get('name'), str(s.get('size') or '-'))] = s
    rows = {}
    for p in pieces:
        nested = p.get('shape') or {}
        identifiers = [p.get('shape_id'), p.get('target_id'), nested.get('id')]
        name = p.get('name') or nested.get('name') or 'Molde não informado'
        size = str(p.get('size') or nested.get('size') or '-')
        target = by_name_size.get((name, size), {})
        if not target:
            target = next((index[str(identifier)] for identifier in identifiers
                           if identifier is not None and str(identifier) in index), {})
        s = {**target, **nested}
        size = str(p.get('size') or s.get('size') or '-')
        sid = next((value for value in (p.get('shape_id'), p.get('target_id'), s.get('shape_id'), s.get('id')) if value is not None), None)
        fmt = p.get('shape_format') or s.get('shape_format') or '1x1'
        factor = shape_multiplier(fmt)
        key = (str(sid) if sid is not None else name, name, size, factor)
        if key not in rows:
            rows[key] = dict(name=name, size=size, shape_id=sid, instances=0, physical=0,
                             factor=factor, demand=target.get('pairs'), layer_counts=defaultdict(int))
        row = rows[key]
        layers = layers_for_piece(layout, p)
        row['instances'] += 1
        row['physical'] += layers
        row['layer_counts'][layers] += 1
    for row in rows.values():
        row['pairs'] = row['physical'] // 2
        row['unpaired'] = row['physical'] % 2
        row['equivalent_pairs'] = row['pairs'] * row['factor']
    return list(rows.values())


def render_sheet(dialog, dpi=150):
    """Páginas A4; medidas em pontos, sem encolher o texto para caber."""
    scale = dpi / 72
    landscape = getattr(dialog, 'orientation', 'portrait') == 'landscape'
    w, h = (841.89, 595.28) if landscape else (595.28, 841.89)
    pages = []
    dialog.print_texts = []
    fonts = {}
    def font(size=9, bold=False):
        key = (size, bold)
        if key not in fonts:
            candidates = [str(Path(__file__).resolve().parent.parent / 'assets' / 'fonts' / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),
                          '/usr/share/fonts/truetype/dejavu/' + ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'),
                          'arialbd.ttf' if bold else 'arial.ttf']
            for path in candidates:
                try:
                    fonts[key] = ImageFont.truetype(path, round(size * scale)); break
                except OSError:
                    continue
            else:
                raise RuntimeError('Fonte TrueType não disponível para a ficha de produção')
        return fonts[key]
    layout = dict(dialog.current_layout)
    layout.update(layers=dialog.layout_layers, tip_zone=dialog.tip_zone, layers_tip=dialog.layers_tip)
    rows = production_rows(dialog.placed_pieces, dialog.session_shapes, layout)
    source = {**dialog.layout_data, **dialog.current_layout}
    session = source.get('session') or {}
    missing = 'não informado'
    sid = source.get('session_id') or session.get('id') or missing
    order = source.get('order_code') or source.get('order_id') or session.get('order_id') or missing
    session_name = source.get('session_name') or session.get('name') or ''
    session_label = f"Sessão #{sid}"
    if session_name and session_name != session_label:
        session_label += f" - {session_name}"
    layouts = getattr(dialog, 'layouts', None) or [dialog.current_layout]
    def same_session(plate):
        plate_session = plate.get('session') or {}
        plate_sid = plate.get('session_id') or plate_session.get('id') or source.get('session_id') or sid
        return str(plate_sid) == str(sid)
    session_indices = [i for i, plate in enumerate(layouts) if same_session(plate)]
    plate_number = session_indices.index(dialog.current_layout_index)+1 if dialog.current_layout_index in session_indices else 1
    plate_count = max(1,len(session_indices))
    identity = f"{session_label} | {dialog.get_display_layout_name()} | Placa {plate_number} de {plate_count}"
    margin = 36
    y = 0
    im = draw = None
    def text(x, yy, value, size=9, bold=False, fill='black'):
        dialog.print_texts.append(str(value))
        draw.text((round(x*scale), round(yy*scale)), str(value), font=font(size,bold), fill=fill)
    def line(yy):
        draw.line((margin*scale, yy*scale, (w-margin)*scale, yy*scale), fill='#777777', width=max(1, round(scale/2)))
    def wrap(value, width, size=9, bold=False):
        # Quebra inclusive identificadores sem espaços, sem cortar informação.
        result, current = [], ''
        for ch in str(value):
            candidate = current + ch
            if current and draw.textlength(candidate, font=font(size,bold)) > width*scale:
                cut = current.rfind(' ')
                if cut > len(current)//2:
                    result.append(current[:cut]); current = current[cut+1:] + ch
                else:
                    result.append(current); current = ch
            else:
                current = candidate
        return result + ([current] if current else [])
    def paragraph(value, size=9, bold=False):
        nonlocal y
        for value_line in wrap(value, w-2*margin, size, bold):
            if y + size + 6 > h-45:
                new_page()
            text(margin,y,value_line,size,bold); y += size+5
    def new_page():
        nonlocal im, draw, y
        im = Image.new('RGB', (round(w*scale), round(h*scale)), 'white')
        draw = ImageDraw.Draw(im); pages.append(im)
        text(margin, 28, 'FICHA DE PRODUÇÃO', 16, True)
        logo = getattr(dialog, 'company_logo_raw', None)
        if logo is not None:
            logo = logo.copy()
            logo.thumbnail((round(100*scale), round(32*scale)), Image.Resampling.LANCZOS)
            im.paste(logo, (round((w-margin)*scale)-logo.width, round(25*scale)), logo if logo.mode=='RGBA' else None)
        text(margin, 51, f'Emissão: {dialog.date_str}', 9)
        y = 71
        paragraph(identity,9,True)
        paragraph(f"Usuário responsável pela produção: {source.get('production_user') or missing}",9,True)
        payload,label = dialog.get_barcode_payload_and_label()
        barcode = generate_code128_pillow(payload,height=round(23*scale),module_width=max(1,round(scale)),show_text=True,label=label)
        if barcode:
            # Não reamostrar barras. Reservar altura real e manter quiet zones.
            if barcode.width > (w-2*margin)*scale:
                barcode = generate_code128_pillow(payload,height=round(23*scale),module_width=1,show_text=True,label=label)
            im.paste(barcode,(round(margin*scale),round(y*scale)))
            y += barcode.height/scale + 8
        layout_path = str(getattr(dialog, 'layout_path', '') or source.get('layout_path') or '').strip()
        path_label = ('Caminho da sessão: ' + layout_path if layout_path else
                      'Caminho da sessão: não informado (exporte a sessão para a máquina).')
        # Mantém o caminho completo e legível, inclusive UNC longo, em cada folha.
        for path_line in wrap(path_label, w-2*margin, 9):
            text(margin, y, path_line, 9)
            y += 14
        y += 3
        line(y); y += 8
    new_page()
    paragraph(f'Ordem: {order}',bold=True)
    material = re.sub(r'\(\s*\d+\s*layer\(s\)\s*\)', '', dialog.material_name, flags=re.I).strip()
    paragraph('PREPARAÇÃO DO MATERIAL',11,True)
    paragraph(f'Material: {material}',14,True)
    if dialog.tip_zone:
        paragraph(format_enfesto_operator_text(layout=layout,sheet_w=dialog.sheet_w_mm,sheet_h=dialog.sheet_h_mm,tip_mode=dialog.tip_mode),bold=True)
    else:
        paragraph(f'Separar {dialog.layout_layers} folhas de {dialog.dimensions_str}.',14,True)
    current_plate = {**dialog.current_layout, 'sheet_h_mm': dialog.sheet_h_mm,
                     'layers': dialog.layout_layers, 'trim_cut_line': dialog.trim_cut_line}
    plate_total = plate_length_mm(current_plate)
    # Medidas e refile da placa aberta não são padrões das outras placas.
    session_defaults = {key: dialog.layout_data[key]
                        for key in ('session', 'material', 'material_layers', 'layers')
                        if key in dialog.layout_data}
    session_lengths = [
        plate_length_mm(current_plate if i == dialog.current_layout_index else layouts[i], session_defaults)
        for i in session_indices
    ]
    layout_total = sum(session_lengths) if session_lengths and all(value is not None for value in session_lengths) else None
    paragraph(f"Total do layout: {format_m(layout_total) + ' m' if layout_total is not None else 'não informado'}",bold=True)
    paragraph(f"Total da placa em Metros: {format_m(plate_total) + ' m' if plate_total is not None else 'não informado'}",bold=True)
    paragraph('RESUMO DESTA PLACA',11,True)
    paragraph(f'Aproveitamento geométrico: {dialog.yield_pct:.2f}%',bold=True)
    paragraph(f"Total de pares da placa: {sum(r['pairs'] for r in rows)}",bold=True)
    # Colunas independentes: o mapa ocupa toda a altura disponível e se repete
    # nas continuações, para manter a referência de retirada junto às quantidades.
    gutter = 18
    usable_w = w - 2*margin
    side_w = min(240, usable_w * 0.46)
    graph_w = usable_w - side_w - gutter
    side_x = w - margin - side_w
    dialog.print_regions = []

    from ui.layout_print_dialog import format_size
    groups = {}
    for row in rows:
        size = row['size']
        variants = {size, format_size(size)}
        suffix = '|'.join(re.escape(v) for v in sorted(variants, key=len, reverse=True) if v and v != '-')
        name = re.sub(r'[\s_-]+(?:' + suffix + r')[a-zA-Z]?$', '', row['name']) if suffix else row['name']
        groups.setdefault(name, []).append(row)
    box_top = 0
    pad = 7
    inner_w = side_w - 2*pad

    def finish_box():
        bottom = y+5
        draw.rectangle((side_x*scale,box_top*scale,(w-margin)*scale,bottom*scale),
                       outline='black',width=max(1,round(scale)))
        dialog.print_regions[-1]['models'] = (side_x,box_top,w-margin,bottom)

    def visual_columns():
        nonlocal y, box_top
        top = y
        box_top = top-5
        text(side_x+pad, top, 'MODELOS E QUANTIDADES', 9, True)
        text(side_x+pad, top+15, 'n/m = pares na placa / pedido da sessão', 8)
        draw.line(((side_x+pad)*scale,(top+29)*scale,(w-margin-pad)*scale,(top+29)*scale),fill='#777777')
        bw, bh = dialog.sheet_w_mm, dialog.sheet_h_mm
        gx, gy = margin+26, top+34
        graph_h = max(1, h-110-gy)
        ratio = min((graph_w-26)/max(1,bw), graph_h/max(1,bh)) if bw > 0 and bh > 0 else 0
        def point(x, yy):
            return ((gx+x*ratio)*scale, (gy+(bh-yy)*ratio)*scale)
        dialog.print_regions.append(dict(page=len(pages),
            map=(gx,gy,gx+bw*ratio,gy+bh*ratio),
            models=(side_x,top,w-margin,h-65)))
        if ratio > 0:
            # Preserva a grade de 100 mm e as réguas em metros também no PDF/PNG.
            # Em placas longas, espaça os rótulos para evitar sobreposição.
            label_step = max(1, math.ceil(16 / (100*ratio)))
            for axis, length in (('x', bw), ('y', bh)):
                for index in range(1, int(length//100)+1):
                    value = index*100
                    if axis == 'x':
                        px, py = point(value, 0)
                        draw.line((*point(value,bh),px,py),fill='#dddddd',width=max(1,round(scale/2)))
                        draw.line((px,py,px,py+3*scale),fill='#555555',width=max(1,round(scale/2)))
                        if index % label_step == 0:
                            label = format_m(value, 1)
                            label_w = draw.textlength(label, font=font(8)) / scale
                            text(px/scale-label_w/2,py/scale+4,label,8)
                    else:
                        px, py = point(0, value)
                        draw.line((px,py,*point(bw,value)),fill='#dddddd',width=max(1,round(scale/2)))
                        draw.line((px-3*scale,py,px,py),fill='#555555',width=max(1,round(scale/2)))
                        if index % label_step == 0:
                            text(gx-24,py/scale-4,format_m(value, 1),8)
            draw.rectangle((*point(0,bh),*point(bw,0)), outline='black', width=max(1,round(scale)))
            for p in dialog.placed_pieces:
                contour = p.get('contour') or (p.get('shape') or {}).get('contour') or []
                if len(contour) >= 3:
                    poly = transform_contour(contour,float(p.get('x',0)),float(p.get('y',0)),
                        float(p.get('rotation',p.get('angle',p.get('rot_deg',0)))))
                    draw.polygon([point(pt['x'],pt['y']) if isinstance(pt,dict) else point(*pt) for pt in poly],
                                 fill=p.get('color') or '#dddddd',outline='black')
            zone = clamp_tip_zone(dialog.tip_zone,bw,bh)
            if zone:
                x0,y0,x1,y1=zone
                draw.rectangle((*point(x0,y1),*point(x1,y0)),outline='#333333',width=max(2,round(scale*2)))
            trim = dialog.trim_cut_line or {}
            if trim.get('enabled',True):
                if trim.get('has_cut_y'):
                    draw.line((*point(0,float(trim['y'])),*point(bw,float(trim['y']))),fill='black',width=max(2,round(scale*2)))
                if trim.get('has_cut_x'):
                    draw.line((*point(float(trim['x']),0),*point(float(trim['x']),bh)),fill='black',width=max(2,round(scale*2)))
        caption_y = gy + bh*ratio + 20
        caption = f'Largura × comprimento: {dialog.dimensions_str}'
        if dialog.tip_zone:
            caption += f' | Ponta: {dialog.layers_tip} camadas'
        for value in wrap(caption, graph_w):
            text(gx,caption_y,value); caption_y += 14
        y = top+35

    def next_visual_page():
        finish_box()
        new_page()
        visual_columns()

    if y + 180 > h-65:
        new_page()
    visual_columns()
    active_model = ''

    def compact_line(value, bold=False):
        nonlocal y
        if y+11 > h-70:
            next_visual_page()
            if not bold and active_model:
                # Identificar o modelo também quando seus tamanhos continuam.
                heading = wrap(active_model + ' (continuação)',inner_w,8,True)[0]
                text(side_x+pad,y,heading,8,True); y += 11
        text(side_x+pad,y,value,8,bold)
        y += 11

    for name, model_rows in groups.items():
        active_model = name
        if y+27 > h-70:
            next_visual_page()
        for label in wrap(name,inner_w,8,True):
            compact_line(label,True)
        tokens = []
        for r in sorted(model_rows, key=lambda r: float(format_size(r['size'])) if re.fullmatch(r'\d+(?:\.\d+)?',format_size(r['size'])) else float('inf')):
            demand = r['demand'] if r['demand'] is not None else '?'
            token = f"{format_size(r['size'])}: {r['pairs']}/{demand}"
            if r['shape_id'] is not None:
                token += f" #{r['shape_id']}"
            tokens.append(token)
        # Quebrar somente entre tokens: preservar cada fração inteira.
        current = ''
        for token in tokens:
            candidate = current + (', ' if current else '') + token
            if current and draw.textlength(candidate,font=font(8)) > inner_w*scale:
                compact_line(current)
                current = token
            else:
                current = candidate
        if current:
            compact_line(current)
        for r in model_rows:
            if r['factor'] != 1:
                for label in wrap(f"{format_size(r['size'])}: Fator ×{r['factor']} | Equiv.: {r['equivalent_pairs']} pares",inner_w,8):
                    compact_line(label)
            if r['unpaired']:
                for label in wrap(f"{format_size(r['size'])}: 1 peça física sem par completo.",inner_w,8):
                    compact_line(label)
        y += 4
    if not rows:
        compact_line('Nenhuma peça posicionada nesta placa.')
    finish_box()
    text(margin,h-52,'Conferência: Almoxarifado __________ Operador __________ Supervisão __________')
    for i,page in enumerate(pages):
        draw = ImageDraw.Draw(page)
        text(margin,h-28,f'Sessão #{sid} | {dialog.get_display_layout_name()} | Folha {i+1}/{len(pages)}',9)
    return pages
