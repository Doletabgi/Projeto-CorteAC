"""Medidas e ordenação usadas pelas apresentações do catálogo."""
from cad.shape_library import contour_points, shape_folder
from ui.sort_utils import natural_sort_key, size_sort_key

VIEW_MODES = {
    'cards': 'Cartões grandes',
    'compact': 'Cartões compactos',
    'list': 'Lista com prévias',
    'details': 'Tabela de detalhes',
}

# Chave, título, largura base, alinhamento.
DETAIL_COLUMNS = (
    ('name', 'Nome do molde', 245, 'w'),
    ('size', 'Tamanho', 85, 'w'),
    ('folder', 'Pasta', 170, 'w'),
    ('width', 'Largura (mm)', 110, 'e'),
    ('height', 'Altura (mm)', 110, 'e'),
    ('area', 'Área externa (cm²)', 165, 'e'),
    ('status', 'Situação', 140, 'w'),
)


def shape_metrics(shape):
    """Largura/altura em mm e área externa em cm²; sem descontar furos."""
    points = contour_points(shape)
    if not points:
        return None
    width = max(x for x, y in points)-min(x for x, y in points)
    height = max(y for x, y in points)-min(y for x, y in points)
    area = abs(sum(x*y2-x2*y for (x, y), (x2, y2) in zip(points, points[1:]+points[:1])))/200
    return width, height, area


def sort_value(shape, column, metrics, status):
    if column == 'name':
        return natural_sort_key(shape.get('name', ''))
    if column == 'size':
        return size_sort_key(str(shape.get('size') or ''))
    if column == 'folder':
        return natural_sort_key(shape_folder(shape))
    if column in ('width', 'height', 'area'):
        return (metrics is None, metrics[('width', 'height', 'area').index(column)] if metrics else 0)
    return natural_sort_key(status)
