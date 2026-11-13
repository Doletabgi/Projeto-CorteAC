"""Regras e teste isolado do assistente de criação de perfis DieProc."""
import json
import math


MATERIALS = {
    'synthetic': ('Sintético', 'half'),
    'fabric': ('Tecido', 'fixed'),
    'leather': ('Couro', 'free'),
    'other': ('Outro material', 'fixed'),
}
GOALS = {'fast': 'Mais rapidez', 'balanced': 'Equilíbrio', 'quality': 'Mais aproveitamento'}
ROTATIONS = {
    'fixed': ('Manter o sentido', '0/0'),
    'half': ('Permitir inversão', '0/0 0/180'),
    'free': ('Girar livremente', '0/0 0/90 0/180 0/270'),
}


def validate_gap(value):
    try:
        gap = float(str(value).strip().replace(',', '.'))
    except (ValueError, TypeError):
        raise ValueError('Informe a distância entre peças em milímetros.') from None
    if not math.isfinite(gap) or not 0 <= gap <= 50:
        raise ValueError('Use uma distância de 0 a 50 mm.')
    return round(gap, 1)


def build_profile(name, material, goal, rotation, gap):
    name = str(name).strip()
    if not name or len(name) > 80:
        raise ValueError('Dê um nome à configuração, com até 80 caracteres.')
    if any(ord(ch) < 32 or ch in ';?' for ch in name):
        raise ValueError('Use um nome sem ponto e vírgula, interrogação ou quebras de linha.')
    if material not in MATERIALS or goal not in GOALS or rotation not in ROTATIONS:
        raise ValueError('Confira as escolhas de material, prioridade e rotação.')
    gap = validate_gap(gap)
    # Giros restritos nunca recebem uma tolerância angular escondida.
    sweep = {'fast': 0, 'balanced': 3, 'quality': 5}[goal] if rotation == 'free' else 0
    profile = {
        'name': name, 'coupling': ROTATIONS[rotation][1],
        'step': .5 if goal == 'quality' else 1.,
        'solutions': {'fast': 10, 'balanced': 30, 'quality': 60}[goal],
        'range1_from': -sweep, 'range1_to': sweep,
        'range1_step': .5 if sweep and goal == 'quality' else 1. if sweep else 0.,
        'range2_from': 0., 'range2_to': 0., 'range2_step': 0.,
        'range3_from': 0., 'range3_to': 0., 'range3_step': 0.,
        'gap1': gap, 'gap2': 0., 'gap3': 0.,
        'row_interlock': int(goal != 'fast'), 'diagonal': 0, 'macro_script': '',
        'wizard_settings_json': json.dumps({
            'version': 1, 'material': material, 'goal': goal, 'rotation': rotation,
        }, ensure_ascii=False),
    }
    return profile


def is_guided_profile(profile):
    try:
        settings = json.loads(profile.get('wizard_settings_json') or '{}')
        return isinstance(settings, dict) and settings.get('version') == 1
    except (ValueError, TypeError):
        return False


def preview_worker(output, job):
    """Executado em processo separado: sem banco, Tk ou alteração de sessão."""
    try:
        from cad.nesting_engine import auto_nest_pieces, calculate_yield
        pieces = auto_nest_pieces(
            available_shapes=job['shapes'], bed_width_mm=job['width'],
            bed_height_mm=job['height'], target_count=job['limit'],
            strategy='flashnestsheet', params=job['profile']['name'],
            gap_mm=job['profile']['gap1'], dieproc_params=job['profile'],
            margins=job['margins'], layers=job['layers'],
        )
        yield_pct, _ = calculate_yield(pieces, job['width'] * job['height'] / 1_000_000)
        output.put({'pieces': pieces, 'yield_pct': yield_pct})
    except Exception as exc:
        output.put({'error': str(exc)})
