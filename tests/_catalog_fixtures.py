"""
tests/_catalog_fixtures.py

Banco SQLite temporário e semeado para os testes do Catálogo de Moldes.

Motivo: esses testes usavam o `jobmanager.db` de PRODUÇÃO. Quando o operador
apagava artigos/moldes no app, a suíte ficava vermelha sem nenhuma regressão de
código (os moldes ficavam com `article_id = NULL`). Agora cada módulo cria seu
próprio banco descartável com o cenário esperado: 17 moldes, 16 tamanhos e a
lacuna proposital (PALM_CAVA sem o tamanho 22a).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

BOX = [
    {"x": 0.0, "y": 0.0},
    {"x": 120.0, "y": 0.0},
    {"x": 120.0, "y": 260.0},
    {"x": 0.0, "y": 260.0},
]

# 16 tamanhos distintos (22a..36a + 41), como no cenário original do catálogo
SIZES_22_36 = [f"{n}a" for n in range(22, 37)]  # 15 tamanhos


def make_temp_catalog_db(db_module):
    """Cria um DatabaseManager em arquivo temporário com 17 moldes do artigo 1.

    Cenário esperado pelos testes do catálogo:
      - 3 peças bases: '323_PalAcb', 'PALM_CAVA', 'teste2';
      - 16 tamanhos distintos (22a..36a + 41);
      - 17 moldes no total;
      - célula vazia proposital: PALM_CAVA no tamanho 22a.
    """
    tmp_dir = tempfile.mkdtemp(prefix="corteac_catalog_")
    db_path = str(Path(tmp_dir) / "catalog_test.db")
    db = db_module.DatabaseManager(db_path=db_path)

    with db.get_connection() as conn:
        cur = conn.cursor()
        # Banco novo pode já ter dados semeados pelo init_db: limpa e recria o cenário
        cur.execute("DELETE FROM shapes")
        cur.execute("DELETE FROM articles")
        cur.execute("INSERT OR IGNORE INTO orders (id, code, customer, status, name) VALUES (999, 'ORD-TESTE', 'Teste', 'Aberto', 'Pedido Teste')")
        cur.execute("INSERT INTO articles (id, order_id, name, pairs_count, material_id) VALUES (1, 999, 'Artigo Teste', 10, NULL)")

        contour_json = json.dumps(BOX)
        rows = []
        shape_id = 1
        for size in SIZES_22_36[:-1]:  # 22a..35a -> 14 moldes
            rows.append((shape_id, f"323_PalAcb_{size}", size)); shape_id += 1
        for size in ("35a", "36a"):    # 2 moldes (sem 22a -> lacuna proposital)
            rows.append((shape_id, f"PALM_CAVA_{size}", size)); shape_id += 1
        rows.append((shape_id, "teste2", "41"))  # 1 molde no tamanho 41

        for sid, nome, size in rows:
            cur.execute(
                "INSERT INTO shapes (id, article_id, name, color, contour_json, holes_json, stitching_json, folder, size) "
                "VALUES (?, 1, ?, '#000080', ?, '[]', '[]', 'PALM', ?)",
                (sid, nome, contour_json, size),
            )
        conn.commit()

    return db, tmp_dir
