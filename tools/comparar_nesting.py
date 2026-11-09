#!/usr/bin/env python3
"""Comparação diagnóstica de estratégias; não salva nem escolhe layouts.

Exemplo: python tools/comparar_nesting.py --pecas 30 --estrategias flashnestsheet IA-teste
Para dados próprios use --entrada arquivo.json (ver --help).
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import math
import os
import random
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cad.geometry import polygon_area, polygon_bbox, polygons_collide, transform_contour
from cad.layers_rule import pecas_na_mesa
from cad.layers_rule import resolve_session_layers
from cad.die_parser import parse_die_file
from cad.trim_engine import trim_layout_dict
import cad.nesting_engine as nesting_engine
from cad.nesting_engine import nest_multi_sheet


def load_benchmark_shapes(total_pieces):
    files = ['Gaspea_Derby_41.die', 'Biqueira_Esportiva_40.die', 'Lateral_Sapato_42.die']
    samples = [parse_die_file(str(ROOT / 'samples' / name)) for name in files]
    shapes = []
    for index, sample in enumerate(samples):
        qty = total_pieces // len(samples) + (index < total_pieces % len(samples))
        if qty:
            shapes.append({'id': index + 1, 'name': sample.get('name', f'Molde_{index + 1}'),
                           'size': str(sample.get('size', '41')), 'pairs': qty,
                           'sequence': index + 1, 'contour': sample['contour'], 'layers': 2})
    return shapes


def analyze_trim(layouts, width, height, gap):
    """Estima a área após refile usando cópias; não representa consumo físico confirmado."""
    original = len(layouts) * width * height / 1_000_000
    trimmed = 0.0
    for layout in layouts:
        copy_layout = trim_layout_dict(copy.deepcopy(layout), original_w=width, original_h=height, gap_mm=gap)
        trimmed += float(copy_layout['width_mm']) * float(copy_layout['height_mm']) / 1_000_000
    return {'area_original_m2': round(original, 4), 'area_apos_refile_m2': round(trimmed, 4),
            'area_recortada_m2': round(max(0.0, original - trimmed), 4),
            'aviso': 'Estimativa geométrica por camada; área recortada não equivale automaticamente a material reutilizável.'}


def analyze_demand(shapes, layouts, layers):
    """Exige associação inequívoca para não validar uma troca de moldes."""
    expected = [max(0, int(s.get('target_pieces', 0))) if int(s.get('pairs', 0)) <= 0
                else pecas_na_mesa(int(s['pairs']), int(s.get('layers') or layers)) for s in shapes]
    counts = [0] * len(shapes)
    unidentified = 0
    ambiguous = 0
    for layout in layouts:
        for piece in layout.get('pieces', []):
            matches = [i for i, shape in enumerate(shapes) if nesting_engine.piece_matches_shape(piece, shape)]
            if len(matches) == 1:
                counts[matches[0]] += 1
            elif matches:
                ambiguous += 1
            else:
                unidentified += 1
    return {'atendida': expected == counts and not ambiguous and not unidentified,
            'por_molde': [{'id': shape.get('id'), 'nome': shape.get('name'),
                           'solicitadas': expected[i], 'posicionadas': counts[i]}
                          for i, shape in enumerate(shapes)],
            'pecas_ambiguas': ambiguous, 'pecas_nao_identificadas': unidentified}


class FallbackCapture(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages = []

    def emit(self, record):
        message = record.getMessage()
        if 'fallback' in message.lower():
            self.messages.append(message)


def validate_layouts(layouts, width, height, margins, gap):
    violations = {'contornos_invalidos': 0, 'fora_das_margens': 0, 'pares_em_conflito': 0}
    max_excess = 0.0
    for layout in layouts:
        polygons = []
        for piece in layout.get('pieces', []):
            shape = piece.get('shape') or {}
            contour = piece.get('contour') or shape.get('contour') or []
            try:
                if len(contour) < 3:
                    raise ValueError('contorno ausente')
                poly = transform_contour(contour, float(piece['x']), float(piece['y']),
                                         float(piece.get('rotation', piece.get('angle', 0))))
                box = polygon_bbox(poly)
                if not all(math.isfinite(float(v)) for v in box):
                    raise ValueError('coordenada inválida')
                if polygon_area(poly) <= 0:
                    raise ValueError('contorno sem área')
            except (ValueError, TypeError, KeyError, IndexError, OverflowError):
                violations['contornos_invalidos'] += 1
                continue
            excess = max(0.0, margins['left'] - box[0], margins['bottom'] - box[1],
                         box[2] - (width - margins['right']), box[3] - (height - margins['top']))
            max_excess = max(max_excess, excess)
            if excess > 1e-6:
                violations['fora_das_margens'] += 1
            for prev_poly, prev_box in polygons:
                if polygons_collide(poly, prev_poly, gap=gap, bbox_a=box, bbox_b=prev_box):
                    violations['pares_em_conflito'] += 1
            polygons.append((poly, box))
    violations['maior_excesso_margem_mm'] = round(max_excess, 8)
    return violations


def compare_case(shapes, width, height, layers, margins, gap, strategy, backend, seconds, params='stdNOTFill', fill_holes=False):
    # O ponto de entrada atual seleciona o backend por variável de ambiente. Este
    # utilitário é sequencial e restaura o valor para não interferir no chamador.
    old_backend = os.environ.get('CORTEAC_BACKEND')
    os.environ['CORTEAC_BACKEND'] = backend
    handler = FallbackCapture()
    logger = logging.getLogger('cad.nesting_backend')
    logger.addHandler(handler)
    state = random.getstate()
    original_core = nesting_engine._auto_nest_pieces_core
    core_calls = []

    def tracked_core(*args, **kwargs):
        core_calls.append(True)
        return original_core(*args, **kwargs)

    nesting_engine._auto_nest_pieces_core = tracked_core
    random.seed(0)
    started = time.perf_counter()
    try:
        result = nest_multi_sheet(copy.deepcopy(shapes), width, height, strategy=strategy,
                                  params=params, gap_mm=gap, layers=layers, margins=dict(margins),
                                  dieproc_params={'deterministic': True},
                                  max_total_sec=seconds)
        elapsed = time.perf_counter() - started
        layouts = result.get('layouts', [])
        violations = validate_layouts(layouts, width, height, margins, gap)
        demand = analyze_demand(shapes, layouts, layers)
        expected = sum(max(0, int(s.get('target_pieces', 0))) if int(s.get('pairs', 0)) <= 0
                       else pecas_na_mesa(int(s['pairs']), int(s.get('layers') or layers))
                       for s in shapes)
        count = sum(len(layout.get('pieces', [])) for layout in layouts)
        area = sum(float(layout.get('used_area_m2', 0)) for layout in layouts)
        yield_pct = 100 * area / (len(layouts) * width * height / 1_000_000) if layouts else None
        filling = None
        if fill_holes:
            filled, info = nesting_engine.preencher_buracos_em_placas(
                copy.deepcopy(layouts), gap_mm=gap, session={'layers': layers}, shapes=copy.deepcopy(shapes))
            filling = {'movidas': info.get('movidas'), 'placas_removidas': info.get('placas_removidas'),
                       'demanda_por_molde': analyze_demand(shapes, filled, layers),
                       'validacoes_geometricas': validate_layouts(filled, width, height, margins, gap),
                       'refile_estimado': analyze_trim(filled, width, height, gap),
                       'aviso': 'Simulação em cópia; não altera nem aplica o layout.'}
        return {'estrategia': strategy, 'backend_solicitado': backend,
                'chamadas_motor_classico': len(core_calls),
                'observacao_backend': ('NFP solicitado; houve delegação ao motor clássico.'
                                       if backend == 'nfp' and core_calls else None),
                'fallback': handler.messages, 'tempo_segundos': round(elapsed, 3),
                'pecas_solicitadas': expected, 'pecas_posicionadas': count,
                'placas': len(layouts), 'aproveitamento_area_total_pct': round(yield_pct, 3) if yield_pct is not None else None,
                'resultado_completo': bool(result.get('success')) and count == expected,
                'demanda_por_molde': demand,
                'refile_estimado': analyze_trim(layouts, width, height, gap),
                'preenchimento_simulado': filling,
                'validacoes_geometricas': violations, 'aviso_motor': result.get('warning'),
                'moldes_nao_posicionados': result.get('unplaced_shapes', [])}
    except Exception as exc:
        return {'estrategia': strategy, 'backend_solicitado': backend,
                'erro': f'{type(exc).__name__}: {exc}', 'fallback': handler.messages}
    finally:
        random.setstate(state)
        nesting_engine._auto_nest_pieces_core = original_core
        logger.removeHandler(handler)
        if old_backend is None:
            os.environ.pop('CORTEAC_BACKEND', None)
        else:
            os.environ['CORTEAC_BACKEND'] = old_backend


def load_sqlite_session(path, session_id):
    """Lê parâmetros persistidos sem gravar nem criar banco de dados."""
    uri = path.resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM sessions WHERE id = ?', (session_id,)).fetchone()
        if row is None:
            raise ValueError(f'Sessão {session_id} não encontrada')
        session = dict(row)
        material = conn.execute('SELECT * FROM materials WHERE id = ?', (session.get('material_id'),)).fetchone()
        if material is None:
            raise ValueError('Sessão sem material cadastrado; forneça um JSON com dimensões explícitas')
        material = dict(material)
    shapes = json.loads(session.get('shapes_json') or '[]')
    for shape in shapes:
        if not shape.get('contour') and shape.get('contour_json'):
            shape['contour'] = json.loads(shape['contour_json'])
    if not material.get('width_mm') or not material.get('height_mm'):
        raise ValueError('Material sem dimensões; forneça um JSON com dimensões explícitas')
    return {'shapes': shapes, 'width_mm': material['width_mm'], 'height_mm': material['height_mm'],
            'params': session.get('params') or 'stdNOTFill',
            'layers': resolve_session_layers(session=session, material=material),
            'gap_mm': session.get('gap_mm') if session.get('gap_mm') is not None else 1,
            'margins': {side: session.get('margin_' + side) if session.get('margin_' + side) is not None else 10
                        for side in ('left', 'right', 'top', 'bottom')}}


def main():
    parser = argparse.ArgumentParser(description='Compara encaixes sem salvar resultados. JSON de entrada: objeto com shapes, width_mm, height_mm, layers, gap_mm e margins (opcionais exceto shapes).')
    parser.add_argument('--entrada', type=Path, help='Arquivo JSON com moldes e parâmetros; sem ele usa samples do projeto')
    parser.add_argument('--sessao', type=int, help='ID da sessão SQLite (leitura apenas)')
    parser.add_argument('--banco', type=Path, default=ROOT / 'jobmanager.db', help='Banco SQLite da sessão')
    parser.add_argument('--pecas', type=int, default=30, help='Demanda para amostras (padrão: 30)')
    parser.add_argument('--estrategias', nargs='+', default=['flashnestsheet', 'IA-teste'])
    parser.add_argument('--backends', nargs='+', choices=['python', 'nfp'], default=['python', 'nfp'])
    parser.add_argument('--limite-segundos', type=float, default=30.0, help='Limite por cálculo; pode retornar resultado parcial')
    parser.add_argument('--preencher-buracos', action='store_true', help='Simula a ferramenta existente em cópias dos layouts')
    args = parser.parse_args()
    if args.pecas < 1 or not math.isfinite(args.limite_segundos) or args.limite_segundos <= 0:
        parser.error('peças e limite de tempo devem ser positivos')
    if args.sessao is not None and args.entrada:
        parser.error('use --sessao ou --entrada, não ambos')
    if args.sessao is not None:
        data = load_sqlite_session(args.banco, args.sessao)
    else:
        data = json.loads(args.entrada.read_text(encoding='utf-8')) if args.entrada else {'shapes': load_benchmark_shapes(args.pecas)}
    shapes = data['shapes']
    width, height = float(data.get('width_mm', 2000)), float(data.get('height_mm', 1200))
    layers, gap = int(data.get('layers', 2)), float(data.get('gap_mm', 1))
    margins = {side: float((data.get('margins') or {}).get(side, 10)) for side in ('left', 'right', 'top', 'bottom')}
    if (not shapes or layers < 1 or not all(math.isfinite(x) for x in [width, height, gap, *margins.values()])
            or gap < 0 or any(x < 0 for x in margins.values())
            or width <= margins['left'] + margins['right'] or height <= margins['top'] + margins['bottom']):
        parser.error('moldes ou dimensões, camadas, folga e margens inválidos')
    report = {'origem': f'sessão SQLite {args.sessao}' if args.sessao is not None else str(args.entrada) if args.entrada else 'amostras do projeto (dados ilustrativos)',
              'parametros': {'width_mm': width, 'height_mm': height, 'layers': layers, 'gap_mm': gap, 'margins': margins, 'params': data.get('params', 'stdNOTFill')},
              'nota': 'Comparação diagnóstica: geometria verificada com as funções do projeto; não certifica regras industriais, preenchimento de demanda por molde ou adequação para corte.',
              'resultados': [compare_case(shapes, width, height, layers, margins, gap, strategy, backend, args.limite_segundos, data.get('params', 'stdNOTFill'), args.preencher_buracos)
                             for strategy in args.estrategias for backend in args.backends]}
    eligible = [r for r in report['resultados'] if r.get('resultado_completo') and not r.get('aviso_motor')
                and r['demanda_por_molde']['atendida']
                and not any(r['validacoes_geometricas'][key] for key in
                            ('contornos_invalidos', 'fora_das_margens', 'pares_em_conflito'))]
    best = min((r['placas'] for r in eligible), default=None)
    report['candidatos_analise'] = [{'estrategia': r['estrategia'], 'backend_solicitado': r['backend_solicitado']}
                                   for r in eligible if r['placas'] == best]
    report['nota_candidatos'] = ('Candidatos com menor número de placas e verificações satisfeitas; '
                                 'não há aplicação automática nem certificação industrial. Empates não são decididos pelo tempo de uma execução.')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
