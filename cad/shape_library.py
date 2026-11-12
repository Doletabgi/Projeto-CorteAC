"""Busca e inclusão de moldes do catálogo, preservando os dados da sessão."""
import copy
from dataclasses import dataclass
import json
import math
import re
import unicodedata

from cad.colors import get_color_for_size
from ui.sort_utils import natural_sort_key, size_sort_key


def search_text(value):
    return ''.join(char for char in unicodedata.normalize('NFKD', str(value or ''))
                   if not unicodedata.combining(char)).casefold()


def shape_folder(shape):
    return str(shape.get('folder') or '').replace('\\', '/').strip('/')


def contour_points(shape):
    """Normaliza somente para desenhar; a geometria salva nunca é simplificada."""
    result = []
    try:
        for point in shape.get('contour') or []:
            x, y = (point['x'], point['y']) if isinstance(point, dict) else point[:2]
            x, y = float(x), float(y)
            if not math.isfinite(x) or not math.isfinite(y):
                return []
            result.append((x, y))
    except (KeyError, TypeError, ValueError, IndexError):
        return []
    if len(set(result)) < 3:
        return []
    area = sum(x*y2-x2*y for (x, y), (x2, y2) in zip(result, result[1:]+result[:1]))
    return result if abs(area) > 1e-8 else []


def validate_pairs(value):
    text = str(value).strip()
    if len(text) > 4 or not re.fullmatch(r'[0-9]+', text) or not 1 <= int(text) <= 9999:
        raise ValueError('Informe uma quantidade de pares entre 1 e 9999.')
    return int(text)


def filter_shapes(shapes, query='', folder=None, size='', article_id=None):
    """None = todas as pastas; string vazia = sem pasta."""
    words = search_text(query).split()
    result = []
    for shape in shapes:
        current_folder = shape_folder(shape)
        if folder is not None and current_folder != folder and not (folder and current_folder.startswith(folder + '/')):
            continue
        if size and str(shape.get('size') or '') != size:
            continue
        if article_id is not None and str(shape.get('article_id')) != str(article_id):
            continue
        haystack = search_text(' '.join(str(shape.get(key) or '') for key in ('name', 'folder', 'size', 'id', 'article_id')))
        if all(word in haystack for word in words):
            result.append(shape)
    return sorted(result, key=lambda shape: (natural_sort_key(shape.get('name', '')),
                                           size_sort_key(str(shape.get('size') or '')), str(shape.get('id'))))


@dataclass
class AdditionResult:
    shapes: list
    added: int
    skipped: int


def add_shapes_to_session(db, session_id, selection):
    """Inclui em uma transação com leitura atual da sessão e bloqueio de escrita.

    Não altera layouts, materiais ou quantidades dos moldes já presentes.
    A geometria vem novamente do banco para não gravar uma prévia desatualizada.
    """
    if not selection:
        raise ValueError('Selecione pelo menos um molde para adicionar.')
    requested = {}
    for item in selection:
        try:
            shape_id = int(item['id'])
        except (KeyError, ValueError, TypeError):
            raise ValueError('Um dos moldes não está mais disponível. Atualize o catálogo.')
        requested.setdefault(shape_id, validate_pairs(item.get('pairs')))
    with db.get_connection() as connection:
        cursor = connection.cursor()
        if connection.backend == 'sqlite':
            cursor.execute('BEGIN IMMEDIATE')
        lock = ' FOR UPDATE' if connection.backend == 'mysql' else ''
        cursor.execute('SELECT id, shapes_json FROM sessions WHERE id = ?' + lock, (session_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError('A sessão escolhida não existe mais. Escolha outra sessão.')
        try:
            shapes = json.loads(row['shapes_json'] or '[]')
        except (TypeError, ValueError):
            raise ValueError('Não foi possível ler os moldes desta sessão. A sessão não foi alterada.')
        if not isinstance(shapes, list) or any(not isinstance(shape, dict) for shape in shapes):
            raise ValueError('Não foi possível ler os moldes desta sessão. A sessão não foi alterada.')
        existing = {str(shape['id']) for shape in shapes if shape.get('id') is not None}
        pending = [shape_id for shape_id in requested if str(shape_id) not in existing]
        if not pending:
            return AdditionResult(shapes, 0, len(requested))
        sources = {}
        for start in range(0, len(pending), 500):
            batch = pending[start:start+500]
            placeholders = ','.join('?' for _ in batch)
            cursor.execute(f'SELECT * FROM shapes WHERE id IN ({placeholders})', tuple(batch))
            sources.update({int(source['id']): dict(source) for source in cursor.fetchall()})
        if len(sources) != len(pending):
            raise ValueError('Um dos moldes foi removido do banco. Atualize o catálogo e selecione novamente.')
        sequences = [len(shapes)]
        for shape in shapes:
            try:
                sequences.append(int(shape.get('sequence', 0)))
            except (ValueError, TypeError):
                pass
        sequence = max(sequences)
        for shape_id in pending:
            source = copy.deepcopy(sources[shape_id])
            try:
                for field in ('contour', 'holes', 'stitching'):
                    source[field] = json.loads(source.get(field + '_json') or '[]')
            except (TypeError, ValueError):
                raise ValueError('Um dos moldes tem dados inválidos. Confira o molde no editor antes de adicionar.')
            if not contour_points(source):
                raise ValueError('Um dos moldes está sem contorno válido. Confira o molde no editor antes de adicionar.')
            sequence += 1
            source.update(pairs=requested[shape_id], sequence=sequence,
                          color=get_color_for_size(source.get('size') or source.get('name') or '41'),
                          shape_format=source.get('shape_format') or '1x1')
            shapes.append(source)
        cursor.execute('UPDATE sessions SET shapes_json = ? WHERE id = ?', (json.dumps(shapes), session_id))
    return AdditionResult(shapes, len(pending), len(requested) - len(pending))
