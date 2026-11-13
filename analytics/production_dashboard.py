"""Indicadores de planejamento a partir de sessões e layouts persistidos."""
from collections import defaultdict
from datetime import date
import json
import math


def _date(value):
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def fetch_data(db):
    """Consultas portáveis SQLite/MySQL; não altera dados e não usa layouts inferidos."""
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT s.id, s.order_id, s.material_id, s.created_at, s.shapes_json, m.name AS material_name FROM sessions s LEFT JOIN materials m ON m.id = s.material_id')
        sessions = [dict(r) for r in cur.fetchall()]
        try:
            cur.execute('SELECT session_id, width_mm, height_mm, yield_percent, yield_pct, production_user FROM layouts')
        except Exception as exc:
            # Bancos antigos ainda sem o responsável registrado.
            if 'production_user' not in str(exc):
                raise
            cur.execute('SELECT session_id, width_mm, height_mm, yield_percent, yield_pct FROM layouts')
        layouts = [dict(r) for r in cur.fetchall()]
    return sessions, layouts


def summarize(sessions, layouts, start=None, end=None, material=None):
    """Período por criação da sessão; aproveitamento ponderado pela área salva."""
    selected = []
    undated = 0
    for s in sessions:
        if material is not None and str(s.get('material_id') or '') != str(material):
            continue
        dt = _date(s.get('created_at'))
        if dt is None:
            undated += 1
            if start or end:
                continue
        if dt and ((start and dt < start) or (end and dt > end)):
            continue
        selected.append(s)
    by_id = {s['id']: s for s in selected}
    groups = defaultdict(lambda: {'layouts': 0, 'area': 0.0, 'used': 0.0})
    days = defaultdict(lambda: {'layouts': 0, 'area': 0.0, 'used': 0.0})
    users = defaultdict(lambda: {'layouts': 0, 'area': 0.0, 'used': 0.0})
    orders = {s.get('order_id') for s in selected if s.get('order_id') is not None}
    pairs, missing_pairs = 0, 0
    for s in selected:
        try:
            shapes = s.get('shapes') if s.get('shapes') is not None else json.loads(s.get('shapes_json') or '[]')
            if not isinstance(shapes, list):
                raise ValueError('lista inválida')
            if not shapes:
                raise ValueError('sem quantidades de moldes')
            for shape in shapes:
                n = _number(shape.get('pairs'))
                if n is None or n < 0 or not n.is_integer():
                    raise ValueError('quantidade inválida')
            pairs += sum(int(shape['pairs']) for shape in shapes)
        except (ValueError, TypeError, AttributeError, KeyError, json.JSONDecodeError):
            missing_pairs += 1
    n_layouts = invalid_layouts = 0
    for ly in layouts:
        session = by_id.get(ly.get('session_id'))
        if session is None:
            continue
        n_layouts += 1
        w, h, y = (_number(ly.get(k)) for k in ('width_mm', 'height_mm', 'yield_percent'))
        if y is None or y == 0:
            y = _number(ly.get('yield_pct'))
        if w is None or h is None or y is None or w <= 0 or h <= 0 or not 0 < y <= 100:
            invalid_layouts += 1
            continue
        area = w * h / 1_000_000
        key = (str(session.get('material_id') or ''), session.get('material_name') or 'Sem material')
        d = str(session.get('created_at') or '')[:10]
        user = str(ly.get('production_user') or '').strip() or 'Não informado'
        for row in (groups[key], days[d], users[user]):
            row['layouts'] += 1
            row['area'] += area
            row['used'] += area * y / 100
    area = sum(v['area'] for v in groups.values())
    used = sum(v['used'] for v in groups.values())
    def finish(row):
        return {**row, 'yield_pct': row['used'] / row['area'] * 100 if row['area'] else None}
    return {'sessions': len(selected), 'orders': len(orders), 'pairs_planned': pairs,
            'sessions_missing_pairs': missing_pairs, 'layouts': n_layouts,
            'invalid_layouts': invalid_layouts, 'undated_sessions': undated,
            'area_m2_per_layer': area, 'unoccupied_m2_per_layer': max(0, area - used),
            'yield_pct': used / area * 100 if area else None,
            'materials': [(k, finish(v)) for k, v in sorted(groups.items())],
            'days': [(k, finish(v)) for k, v in sorted(days.items())],
            'users': [(k, finish(v)) for k, v in sorted(users.items())]}
