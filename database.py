"""
JobManager 2000 (Python Edition)
Database Manager - Conexão Central MySQL 8.0 & Reserva SQLite
"""

import json
import time
import random
import getpass
import socket
from pathlib import Path
from typing import Optional, List, Dict, Any
from config import DATABASE_PATH, DEFAULT_MATERIALS
from cad.colors import get_color_for_size
from db import (
    get_connection as db_get_connection,
    get_memory_connection,
    DBConnection,
    DBCursor,
    DBRow,
    ServerUnreachableError,
    VersionConflictError,
    get_active_backend,
    set_active_backend,
    DB_BACKEND
)

_SENTINEL = object()

def get_current_operator() -> str:
    """Retorna identificação do operador e terminal (usuário@computador)."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "operator"
    try:
        host = socket.gethostname()
    except Exception:
        host = "pc"
    return f"{user}@{host}"


class DatabaseManager:
    def __init__(self, db_path=None, backend=None):
        if backend:
            set_active_backend(backend)
        self.db_path = str(db_path) if db_path is not None else None
        self._memory_conn = None
        if self.db_path == ":memory:":
            self._memory_conn = get_memory_connection()
        self.init_db()

    @property
    def backend(self) -> str:
        """Retorna o backend de banco de dados ativo ('mysql' ou 'sqlite')."""
        return get_active_backend()

    def get_connection(self) -> DBConnection:
        if self._memory_conn is not None:
            return self._memory_conn
        if self.db_path and self.db_path != ":memory:":
            return db_get_connection(database_override=self.db_path)
        return db_get_connection()

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if conn.backend == "mysql":
                # Verifica se as tabelas já foram criadas
                cursor.execute("SHOW TABLES LIKE 'materials'")
                if not cursor.fetchone():
                    schema_path = Path(__file__).resolve().parent / "db" / "schema_mysql.sql"
                    if schema_path.exists():
                        for stmt in schema_path.read_text(encoding="utf-8").split(";"):
                            stmt = stmt.strip()
                            if stmt:
                                cursor.execute(stmt)
                        conn.commit()
                # Migração transparente idempotente para MySQL (macro_script em dieproc_presets)
                try:
                    cursor.execute("""
                    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'dieproc_presets' AND COLUMN_NAME = 'macro_script'
                    """)
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE dieproc_presets ADD COLUMN macro_script LONGTEXT NULL")
                        conn.commit()
                    try:
                        from cad.macro_engine import DEFAULT_IA_TESTE_MACRO
                        cursor.execute("""
                        INSERT IGNORE INTO dieproc_presets
                        (name, coupling, step, solutions, range1_from, range1_to, range1_step, range2_from, range2_to, range2_step, range3_from, range3_to, range3_step, gap1, gap2, gap3, row_interlock, diagonal, macro_script)
                        VALUES ('MACRO_IA_TESTE', '0/0 0/180', 1.0, 30, -3.0, 3.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1, 0, %s)
                        """, (DEFAULT_IA_TESTE_MACRO,))
                        conn.commit()
                    except Exception:
                        pass
                except Exception:
                    pass
            else:
                # Backend SQLite (reserva / testes)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS materials (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    width_mm REAL NOT NULL,
                    height_mm REAL NOT NULL,
                    area_m2 REAL NOT NULL,
                    thickness_mm REAL NOT NULL,
                    layers INTEGER DEFAULT 2,
                    gap_mm REAL DEFAULT 1.0
                )
                """)
                try:
                    cursor.execute("ALTER TABLE materials ADD COLUMN layers INTEGER DEFAULT 2")
                except Exception:
                    pass
                try:
                    cursor.execute("ALTER TABLE materials ADD COLUMN gap_mm REAL DEFAULT 1.0")
                except Exception:
                    pass

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    customer TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Pendente',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    pairs_count INTEGER NOT NULL DEFAULT 1,
                    material_id TEXT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(id),
                    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE SET NULL
                )
                """)

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS shape_folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
                """)

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS shapes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER,
                    name TEXT NOT NULL,
                    color TEXT NOT NULL,
                    contour_json TEXT NOT NULL,
                    holes_json TEXT DEFAULT '[]',
                    stitching_json TEXT DEFAULT '[]',
                    folder TEXT DEFAULT '',
                    FOREIGN KEY (article_id) REFERENCES articles(id)
                )
                """)

                cursor.execute("PRAGMA table_info(shapes)")
                cols = [c[1] for c in cursor.fetchall()]
                if "folder" not in cols:
                    cursor.execute("ALTER TABLE shapes ADD COLUMN folder TEXT DEFAULT ''")
                if "size" not in cols:
                    cursor.execute("ALTER TABLE shapes ADD COLUMN size TEXT DEFAULT '41'")

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    order_id INTEGER,
                    material_id TEXT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    job TEXT NOT NULL DEFAULT 'ProduçãoNova',
                    status TEXT NOT NULL DEFAULT 'Planejado',
                    yield_percent REAL DEFAULT 0.0,
                    cutting_time_sec REAL DEFAULT 0.0,
                    placed_pieces_json TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders(id),
                    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE SET NULL
                )
                """)

                cursor.execute("PRAGMA table_info(sessions)")
                s_cols = [c[1] for c in cursor.fetchall()]
                if "name" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN name TEXT DEFAULT ''")
                if "job" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN job TEXT DEFAULT 'ProduçãoNova'")
                if "placed_pieces_json" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN placed_pieces_json TEXT DEFAULT '[]'")
                if "strategy" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN strategy TEXT DEFAULT 'flashnestsheet'")
                if "params" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN params TEXT DEFAULT 'stdNOTFill'")
                if "machine" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN machine TEXT DEFAULT 'ATOM FlashCut Flex 3020'")
                if "shapes_json" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN shapes_json TEXT DEFAULT '[]'")
                if "gap_mm" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN gap_mm REAL DEFAULT 1.0")
                if "margin_left" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN margin_left REAL DEFAULT 10.0")
                if "margin_right" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN margin_right REAL DEFAULT 10.0")
                if "margin_top" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN margin_top REAL DEFAULT 10.0")
                if "margin_bottom" not in s_cols:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN margin_bottom REAL DEFAULT 10.0")

                cursor.execute("PRAGMA table_info(orders)")
                o_cols = [c[1] for c in cursor.fetchall()]
                if "name" not in o_cols:
                    cursor.execute("ALTER TABLE orders ADD COLUMN name TEXT DEFAULT 'Derby Masculino #41'")

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    `key` TEXT PRIMARY KEY,
                    `value` TEXT NOT NULL
                )
                """)

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS dieproc_presets (
                    name TEXT PRIMARY KEY,
                    coupling TEXT NOT NULL,
                    step REAL DEFAULT 1.0,
                    solutions INTEGER DEFAULT 30,
                    range1_from REAL DEFAULT -3.0,
                    range1_to REAL DEFAULT 3.0,
                    range1_step REAL DEFAULT 1.0,
                    range2_from REAL DEFAULT 0.0,
                    range2_to REAL DEFAULT 0.0,
                    range2_step REAL DEFAULT 0.0,
                    range3_from REAL DEFAULT 0.0,
                    range3_to REAL DEFAULT 0.0,
                    range3_step REAL DEFAULT 0.0,
                    gap1 REAL DEFAULT 1.0,
                    gap2 REAL DEFAULT 0.0,
                    gap3 REAL DEFAULT 0.0,
                    row_interlock INTEGER DEFAULT 1,
                    diagonal INTEGER DEFAULT 0,
                    macro_script TEXT DEFAULT ''
                )
                """)
                try:
                    cursor.execute("ALTER TABLE dieproc_presets ADD COLUMN macro_script TEXT DEFAULT ''")
                except Exception:
                    pass

                try:
                    from cad.macro_engine import DEFAULT_IA_TESTE_MACRO
                    cursor.execute("""
                    INSERT OR IGNORE INTO dieproc_presets
                    (name, coupling, step, solutions, range1_from, range1_to, range1_step, range2_from, range2_to, range2_step, range3_from, range3_to, range3_step, gap1, gap2, gap3, row_interlock, diagonal, macro_script)
                    VALUES ('MACRO_IA_TESTE', '0/0 0/180', 1.0, 30, -3.0, 3.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1, 0, ?)
                    """, (DEFAULT_IA_TESTE_MACRO,))
                except Exception:
                    pass

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS layouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    name TEXT NOT NULL DEFAULT 'l0000.lay',
                    code TEXT NOT NULL DEFAULT 'l0000.lay',
                    path TEXT DEFAULT '',
                    `desc` TEXT DEFAULT '',
                    material_code TEXT DEFAULT '',
                    material_name TEXT DEFAULT '',
                    gap_mm REAL DEFAULT 1.0,
                    ris_w REAL DEFAULT 0.0,
                    width_mm REAL DEFAULT 0.0,
                    ris_l REAL DEFAULT 0.0,
                    height_mm REAL DEFAULT 0.0,
                    area_mm2 REAL DEFAULT 0.0,
                    yield_percent REAL DEFAULT 0.0,
                    yield_pct REAL DEFAULT 0.0,
                    num_items INTEGER DEFAULT 0,
                    num_dies INTEGER DEFAULT 0,
                    version INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT DEFAULT '',
                    updated_by TEXT DEFAULT '',
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
                """)

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS layout_pieces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    layout_id INTEGER NOT NULL,
                    mold_id INTEGER,
                    shape_id INTEGER,
                    item_index INTEGER NOT NULL,
                    target_index INTEGER NOT NULL,
                    instance_id INTEGER NOT NULL,
                    piece_name TEXT NOT NULL,
                    size TEXT DEFAULT '',
                    x REAL NOT NULL,
                    y REAL NOT NULL,
                    rotation_deg REAL NOT NULL,
                    rotation_rad REAL NOT NULL,
                    mirrored INTEGER DEFAULT 0,
                    is_mirrored INTEGER DEFAULT 0,
                    color TEXT DEFAULT '#2563eb',
                    tag TEXT DEFAULT 'Pasted',
                    quality_zone INTEGER DEFAULT 1,
                    FOREIGN KEY (layout_id) REFERENCES layouts(id) ON DELETE CASCADE,
                    FOREIGN KEY (shape_id) REFERENCES shapes(id)
                )
                """)

            # Tabela de pastas de produção (job_folders) para MySQL e SQLite
            if conn.backend == "mysql":
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_folders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(150) UNIQUE NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
                try:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN gap_mm DOUBLE DEFAULT 1.0")
                except Exception:
                    pass
                for m_col in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
                    try:
                        cursor.execute(f"ALTER TABLE sessions ADD COLUMN {m_col} DOUBLE DEFAULT 10.0")
                    except Exception:
                        pass
            else:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
                """)

            # Inicialização idempotente de job_folders (executa apenas uma vez no setup)
            cursor.execute("SELECT `value` FROM settings WHERE `key` = 'job_folders_initialized'")
            row_init = cursor.fetchone()
            if not row_init:
                cursor.execute("SELECT COUNT(*) FROM job_folders")
                if cursor.fetchone()[0] == 0:
                    cursor.execute("INSERT OR IGNORE INTO job_folders (name) VALUES ('ProduçãoNova')")
                    try:
                        cursor.execute("SELECT DISTINCT job FROM sessions WHERE job IS NOT NULL AND job != ''")
                        for r in cursor.fetchall():
                            cursor.execute("INSERT OR IGNORE INTO job_folders (name) VALUES (?)", (r[0],))
                    except Exception:
                        pass
                cursor.execute("REPLACE INTO settings (`key`, `value`) VALUES ('job_folders_initialized', '1')")

            conn.commit()

        self.seed_initial_data()

    def seed_initial_data(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Se o banco já foi inicializado anteriormente, NÃO recria sessões nem moldes apagados
            cursor.execute("SELECT `value` FROM settings WHERE `key` = 'db_seeded'")
            row_seeded = cursor.fetchone()
            if row_seeded:
                val = row_seeded["value"] if isinstance(row_seeded, dict) else row_seeded[0]
                if str(val) == "1":
                    return

            # Inserir materiais padrão se tabela estiver vazia
            cursor.execute("SELECT COUNT(*) FROM materials")
            if cursor.fetchone()[0] == 0:
                for mat in DEFAULT_MATERIALS:
                    cursor.execute("""
                    INSERT OR IGNORE INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        mat["id"],
                        mat["name"],
                        mat.get("type", "como placa"),
                        mat.get("width_mm", 1380.0),
                        mat.get("height_mm", 2980.0),
                        mat.get("area_m2", 4.1124),
                        mat.get("thickness_mm", 1.0),
                        mat.get("layers", 2),
                        mat.get("gap_mm", 1.0)
                    ))
                # Garante que material padrão das sessões de exemplo exista
                cursor.execute("""
                INSERT OR IGNORE INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm)
                VALUES ('MAT_VAQ_01', 'Placa (255.34 X 135.00 cm)', 'como placa', 1350.0, 2553.38, 3.447, 1.0, 2, 1.0)
                """)

            # Inserir configurações padrão sem sobrescrever as existentes
            default_settings = {
                "ask_session_name": "1",
                "start_maximized": "1",
                "allow_article_hiding": "1",
                "show_hidden_articles": "1",
                "materials_horizontal": "0",
                "xfer_login": "",
                "xfer_password": "",
                "xfer_remote_root": "",
                "mold_count_mode": "pairs",
                "mold_view_mode": "pairs",
                "default_strategy": "flashnestsheet",
                "default_nesting_params": "Padrao",
                "default_postbuilder": "(nenhum)",
                "default_mold_params": "(nenhum)",
                "default_die_proc_params": "Fixo",
                "unit_shapes_length": "metre (m)",
                "unit_shapes_area": "metre (m)",
                "unit_materials_length": "metre (m)",
                "unit_materials_area": "metre (m)",
                "unit_layouts_length": "metre (m)",
                "unit_layouts_area": "metre (m)",
                "language": "Português (Brasil)"
            }
            for k, v in default_settings.items():
                cursor.execute("SELECT `key` FROM settings WHERE `key` = ?", (k,))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO settings (`key`, `value`) VALUES (?, ?)", (k, str(v)))

            # Inserir presets padrão DieProc
            default_dieproc_presets = [
                ("ALTERNADO", "0/0 0/180", 1.0, 30, -3.0, 3.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1, 0),
                ("DIREITA", "0/0", 1.0, 30, -3.0, 3.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1, 0),
                ("ESQUERDA", "180/180", 1.0, 30, -3.0, 3.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1, 0),
                ("GAP 2", "0/0 0/180", 1.0, 30, -3.0, 3.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 1, 0),
            ]
            for dp in default_dieproc_presets:
                cursor.execute("""
                INSERT OR IGNORE INTO dieproc_presets 
                (name, coupling, step, solutions, range1_from, range1_to, range1_step, range2_from, range2_to, range2_step, range3_from, range3_to, range3_step, gap1, gap2, gap3, row_interlock, diagonal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, dp)

            # Preset padrão do novo motor de cálculo IA-teste com macro declarativa
            try:
                from cad.macro_engine import DEFAULT_IA_TESTE_MACRO
                cursor.execute("""
                INSERT OR IGNORE INTO dieproc_presets
                (name, coupling, step, solutions, range1_from, range1_to, range1_step, range2_from, range2_to, range2_step, range3_from, range3_to, range3_step, gap1, gap2, gap3, row_interlock, diagonal, macro_script)
                VALUES ('MACRO_IA_TESTE', '0/0 0/180', 1.0, 30, -3.0, 3.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1, 0, ?)
                """, (DEFAULT_IA_TESTE_MACRO,))
            except Exception:
                pass

            # Verificar se já existem ordens
            cursor.execute("SELECT COUNT(*) FROM orders")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                INSERT INTO orders (code, customer, status)
                VALUES ('ORD-2026-001', 'Calçados Elite S/A', 'Em Produção')
                """)
                order_id = cursor.lastrowid

                cursor.execute("""
                INSERT INTO articles (order_id, name, pairs_count, material_id)
                VALUES (?, 'Sapato Derby Masculino #41', 24, 'MAT_VAQ_01')
                """, (order_id,))
                article_id = cursor.lastrowid
            else:
                cursor.execute("SELECT id FROM articles LIMIT 1")
                row = cursor.fetchone()
                article_id = row[0] if row else 1

            # Moldes CAD padrão se vazia
            cursor.execute("SELECT COUNT(*) FROM shapes")
            if cursor.fetchone()[0] == 0:
                sample_shapes = [
                    {
                        "name": "Gáspea (Vamp)",
                        "color": "#000080",
                        "contour": [
                            {"x": 0, "y": 0}, {"x": 140, "y": -20}, {"x": 260, "y": 0},
                            {"x": 290, "y": 70}, {"x": 250, "y": 150}, {"x": 130, "y": 180},
                            {"x": 10, "y": 150}, {"x": -30, "y": 70}
                        ],
                        "holes": [
                            {"x": 50, "y": 50, "r": 2.5}, {"x": 80, "y": 50, "r": 2.5},
                            {"x": 180, "y": 50, "r": 2.5}, {"x": 210, "y": 50, "r": 2.5}
                        ],
                        "stitching": [[{"x": 30, "y": 130}, {"x": 130, "y": 155}, {"x": 230, "y": 130}]]
                    },
                    {
                        "name": "Biqueira (Toe Cap)",
                        "color": "#008080",
                        "contour": [
                            {"x": 0, "y": 0}, {"x": 120, "y": -35}, {"x": 240, "y": 0},
                            {"x": 210, "y": 90}, {"x": 120, "y": 120}, {"x": 30, "y": 90}
                        ],
                        "holes": [{"x": 120, "y": 30, "r": 3.0}],
                        "stitching": []
                    },
                    {
                        "name": "Quarteirão (Quarter)",
                        "color": "#800000",
                        "contour": [
                            {"x": 0, "y": 0}, {"x": 180, "y": 0}, {"x": 220, "y": 80},
                            {"x": 160, "y": 160}, {"x": 40, "y": 140}, {"x": -20, "y": 80}
                        ],
                        "holes": [
                            {"x": 20, "y": 25, "r": 2.5}, {"x": 40, "y": 25, "r": 2.5},
                            {"x": 60, "y": 25, "r": 2.5}, {"x": 80, "y": 25, "r": 2.5}
                        ],
                        "stitching": [[{"x": 10, "y": 120}, {"x": 150, "y": 140}]]
                    },
                    {
                        "name": "Talonete (Heel Counter)",
                        "color": "#800080",
                        "contour": [
                            {"x": 0, "y": 0}, {"x": 110, "y": -15}, {"x": 170, "y": 20},
                            {"x": 150, "y": 80}, {"x": 85, "y": 95}, {"x": 20, "y": 80}
                        ],
                        "holes": [],
                        "stitching": []
                    }
                ]

                for s in sample_shapes:
                    cursor.execute("""
                    INSERT INTO shapes (article_id, name, color, contour_json, holes_json, stitching_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        article_id,
                        s["name"],
                        s["color"],
                        json.dumps(s["contour"]),
                        json.dumps(s["holes"]),
                        json.dumps(s["stitching"])
                    ))

            # Sessões iniciais apenas se tabela estiver vazia na primeira inicialização
            cursor.execute("SELECT COUNT(*) FROM sessions")
            if cursor.fetchone()[0] == 0:
                # Busca um order_id válido
                cursor.execute("SELECT id FROM orders ORDER BY id ASC LIMIT 1")
                row_ord = cursor.fetchone()
                valid_oid = row_ord[0] if row_ord else 1
                cursor.execute("""
                INSERT OR IGNORE INTO sessions (id, code, order_id, material_id, name, job, status, yield_percent, cutting_time_sec, placed_pieces_json)
                VALUES (91, 'SESS-091', ?, 'MAT_VAQ_01', 'Sessão Principal #91', 'ProduçãoNova', 'Stand by', 0.0, 0.0, '[]')
                """, (valid_oid,))
                cursor.execute("""
                INSERT OR IGNORE INTO sessions (id, code, order_id, material_id, name, job, status, yield_percent, cutting_time_sec, placed_pieces_json)
                VALUES (38, 'SESS-038', ?, 'MAT_VAQ_01', 'Corte Vamp/Toe', 'ProduçãoNova', 'Nested', 68.5, 142.0, '[]')
                """, (valid_oid,))
                cursor.execute("REPLACE INTO settings (`key`, `value`) VALUES ('last_session_number', '91')")

            # Marca que o banco já foi semeado inicialmente
            cursor.execute("REPLACE INTO settings (`key`, `value`) VALUES ('db_seeded', '1')")
            conn.commit()

    def get_orders(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders ORDER BY id ASC")
            orders = []
            for row in cursor.fetchall():
                d = dict(row)
                if not d.get("name"):
                    d["name"] = "Derby Masculino #41" if d["id"] == 1 else f"Pedido #{d['id']}"
                orders.append(d)
            return orders

    def create_order(self, name="Novo Pedido", customer="Calçados Elite S/A", status="Em Produção"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) FROM orders")
            max_id = cursor.fetchone()[0] or 0
            next_id = max_id + 1
            code = f"ORD-2026-{next_id:03d}"
            cursor.execute("""
                INSERT INTO orders (id, code, name, customer, status)
                VALUES (?, ?, ?, ?, ?)
            """, (next_id, code, name, customer, status))
            conn.commit()
            return next_id

    def update_order(self, order_id, name=None, customer=None, status=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if customer is not None:
                updates.append("customer = ?")
                params.append(customer)
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if updates:
                params.append(order_id)
                cursor.execute(f"UPDATE orders SET {', '.join(updates)} WHERE id = ?", params)
                conn.commit()

    def delete_order(self, order_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE sessions SET order_id = NULL WHERE order_id = ?", (order_id,))
            cursor.execute("SELECT id FROM articles WHERE order_id = ?", (order_id,))
            art_ids = [r[0] if isinstance(r, (tuple, list)) else r["id"] for r in cursor.fetchall()]
            for aid in art_ids:
                cursor.execute("UPDATE shapes SET article_id = NULL WHERE article_id = ?", (aid,))
            cursor.execute("DELETE FROM articles WHERE order_id = ?", (order_id,))
            cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            conn.commit()

    def delete_article(self, article_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE shapes SET article_id = NULL WHERE article_id = ?", (article_id,))
            cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
            conn.commit()


    def get_articles_by_order(self, order_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM articles WHERE order_id = ?", (order_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_shapes_by_article(self, article_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shapes WHERE article_id = ?", (article_id,))
            shapes = []
            for row in cursor.fetchall():
                d = dict(row)
                d["contour"] = json.loads(d["contour_json"])
                d["holes"] = json.loads(d["holes_json"])
                d["stitching"] = json.loads(d["stitching_json"])
                d["folder"] = d.get("folder", "") or ""
                d["size"] = str(d.get("size") or "41")
                d["color"] = get_color_for_size(d.get("size") or d.get("name") or "41")
                shapes.append(d)
            return shapes

    def get_all_shapes(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shapes ORDER BY id ASC")
            shapes = []
            for row in cursor.fetchall():
                d = dict(row)
                d["contour"] = json.loads(d["contour_json"])
                d["holes"] = json.loads(d["holes_json"])
                d["stitching"] = json.loads(d["stitching_json"])
                d["folder"] = d.get("folder", "") or ""
                d["size"] = str(d.get("size") or "41")
                d["color"] = get_color_for_size(d.get("size") or d.get("name") or "41")
                shapes.append(d)
            return shapes

    def get_shapes(self):
        return self.get_all_shapes()

    def get_materials(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM materials")
            return [dict(row) for row in cursor.fetchall()]

    def get_material(self, mat_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM materials WHERE id = ?", (mat_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_material(self, mat_id, name, type="como placa", width_mm=1380.0, height_mm=1080.0, area_m2=None, thickness_mm=0.0, layers=2, gap_mm=1.0):
        if area_m2 is None:
            area_m2 = round((width_mm * height_mm) / 1_000_000.0, 4)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if conn.backend == "mysql":
                cursor.execute("""
                INSERT INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name), type=VALUES(type), width_mm=VALUES(width_mm),
                    height_mm=VALUES(height_mm), area_m2=VALUES(area_m2), thickness_mm=VALUES(thickness_mm),
                    layers=VALUES(layers), gap_mm=VALUES(gap_mm)
                """, (mat_id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm))
            else:
                cursor.execute("""
                REPLACE INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (mat_id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm))
            conn.commit()
            return self.get_material(mat_id)

    def delete_material(self, mat_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE sessions SET material_id = NULL WHERE material_id = ?", (mat_id,))
            cursor.execute("UPDATE articles SET material_id = NULL WHERE material_id = ?", (mat_id,))
            cursor.execute("DELETE FROM materials WHERE id = ?", (mat_id,))
            conn.commit()

    def update_material(self, mat_id, width_mm=None, height_mm=None, area_m2=None, thickness_mm=None, type=None, name=None, layers=None, gap_mm=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if width_mm is not None:
                updates.append("width_mm = ?")
                params.append(width_mm)
            if height_mm is not None:
                updates.append("height_mm = ?")
                params.append(height_mm)
            if area_m2 is not None:
                updates.append("area_m2 = ?")
                params.append(area_m2)
            if thickness_mm is not None:
                updates.append("thickness_mm = ?")
                params.append(thickness_mm)
            if type is not None:
                updates.append("type = ?")
                params.append(type)
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if layers is not None:
                updates.append("layers = ?")
                params.append(layers)
            if gap_mm is not None:
                updates.append("gap_mm = ?")
                params.append(gap_mm)
            if updates:
                params.append(mat_id)
                cursor.execute(f"UPDATE materials SET {', '.join(updates)} WHERE id = ?", tuple(params))
                conn.commit()

    def get_shape(self, shape_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shapes WHERE id = ?", (shape_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["contour"] = json.loads(d["contour_json"])
            d["holes"] = json.loads(d["holes_json"])
            d["stitching"] = json.loads(d["stitching_json"])
            d["folder"] = d.get("folder", "") or ""
            d["size"] = str(d.get("size") or "41")
            d["color"] = get_color_for_size(d.get("size") or d.get("name") or "41")
            return d

    def update_shape(self, shape_id, name, contour, holes=None, stitching=None, folder=None, size=None, color=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = ["name = ?", "contour_json = ?", "holes_json = ?", "stitching_json = ?"]
            params = [name, json.dumps(contour), json.dumps(holes or []), json.dumps(stitching or [])]
            if folder is not None:
                updates.append("folder = ?")
                params.append(folder or "")
            if size is not None:
                updates.append("size = ?")
                params.append(str(size))
            if color is not None:
                updates.append("color = ?")
                params.append(str(color))
            params.append(shape_id)
            cursor.execute(f"UPDATE shapes SET {', '.join(updates)} WHERE id = ?", tuple(params))
            conn.commit()

    def create_shape(self, article_id=None, name="Shape", color="#000080", contour=None, holes=None, stitching=None, folder="", size="41"):
        s_size = str(size or name or "41")
        color = get_color_for_size(s_size)
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Resiliência de chave estrangeira: article_id
            valid_article_id = article_id
            if valid_article_id is not None:
                cursor.execute("SELECT id FROM articles WHERE id = ?", (valid_article_id,))
                if not cursor.fetchone():
                    valid_article_id = None

            if valid_article_id is None:
                cursor.execute("SELECT id FROM articles ORDER BY id ASC LIMIT 1")
                row_art = cursor.fetchone()
                if row_art:
                    valid_article_id = row_art[0] if isinstance(row_art, (tuple, list)) else row_art["id"]
                else:
                    # Se articles estiver vazio, garante primeiro um pedido (order)
                    cursor.execute("SELECT id FROM orders ORDER BY id ASC LIMIT 1")
                    row_ord = cursor.fetchone()
                    if row_ord:
                        valid_order_id = row_ord[0] if isinstance(row_ord, (tuple, list)) else row_ord["id"]
                    else:
                        cursor.execute("""
                        INSERT INTO orders (code, customer, status, name)
                        VALUES ('ORD-2026-001', 'Calçados Elite S/A', 'Em Produção', 'Derby Masculino #41')
                        """)
                        valid_order_id = cursor.lastrowid or 1

                    # Garante que material MAT_VAQ_01 exista
                    cursor.execute("SELECT id FROM materials WHERE id = 'MAT_VAQ_01'")
                    if not cursor.fetchone():
                        cursor.execute("""
                        INSERT OR IGNORE INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm)
                        VALUES ('MAT_VAQ_01', 'Placa (255.34 X 135.00 cm)', 'como placa', 1350.0, 2553.38, 3.447, 1.0, 2, 1.0)
                        """)

                    cursor.execute("""
                    INSERT INTO articles (order_id, name, pairs_count, material_id)
                    VALUES (?, 'Sapato Derby Masculino #41', 24, 'MAT_VAQ_01')
                    """, (valid_order_id,))
                    valid_article_id = cursor.lastrowid or 1

            cursor.execute("""
            INSERT INTO shapes (article_id, name, color, contour_json, holes_json, stitching_json, folder, size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                valid_article_id,
                name,
                color,
                json.dumps(contour or []),
                json.dumps(holes or []),
                json.dumps(stitching or []),
                folder or "",
                s_size
            ))
            conn.commit()
            return cursor.lastrowid

    def get_shape_folders(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM shape_folders ORDER BY name ASC")
            return [row["name"] for row in cursor.fetchall()]

    def create_shape_folder(self, name):
        name = name.strip().strip("/")
        if not name:
            return False
        parts = [p.strip() for p in name.split("/") if p.strip()]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                curr = ""
                for part in parts:
                    curr = f"{curr}/{part}" if curr else part
                    cursor.execute("INSERT OR IGNORE INTO shape_folders (name) VALUES (?)", (curr,))
                conn.commit()
                return True
            except Exception:
                return False

    def rename_shape_folder(self, old_name, new_name):
        old_name = old_name.strip().strip("/")
        new_name = new_name.strip().strip("/")
        if not old_name or not new_name or old_name == new_name:
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE shape_folders SET name = ? WHERE name = ?", (new_name, old_name))
            cursor.execute("UPDATE shapes SET folder = ? WHERE folder = ?", (new_name, old_name))

            # Atualiza também subpastas filhas (ex: 807266/Sub1 -> Novo/Sub1)
            old_prefix = old_name + "/"
            cursor.execute("SELECT name FROM shape_folders WHERE name LIKE ?", (old_prefix + "%",))
            subs = [row["name"] for row in cursor.fetchall()]
            for sub in subs:
                updated_sub = new_name + "/" + sub[len(old_prefix):]
                cursor.execute("UPDATE shape_folders SET name = ? WHERE name = ?", (updated_sub, sub))

            cursor.execute("SELECT id, folder FROM shapes WHERE folder LIKE ?", (old_prefix + "%",))
            shps = cursor.fetchall()
            for s in shps:
                updated_f = new_name + "/" + s["folder"][len(old_prefix):]
                cursor.execute("UPDATE shapes SET folder = ? WHERE id = ?", (updated_f, s["id"]))

            conn.commit()
            return True

    def delete_shape_folder(self, name, delete_shapes=False):
        name = name.strip().strip("/")
        old_prefix = name + "/"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM shape_folders WHERE name = ? OR name LIKE ?", (name, old_prefix + "%"))
            if delete_shapes:
                cursor.execute("DELETE FROM shapes WHERE folder = ? OR folder LIKE ?", (name, old_prefix + "%"))
            else:
                cursor.execute("UPDATE shapes SET folder = '' WHERE folder = ? OR folder LIKE ?", (name, old_prefix + "%"))
            conn.commit()
            return True

    # -------------------------------------------------------------
    # Gestão de Pastas de Produção (Jobs)
    # -------------------------------------------------------------
    def get_job_folders(self) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM job_folders ORDER BY id ASC")
            folders = [row["name"] for row in cursor.fetchall()]
            return folders

    def create_job_folder(self, name: str) -> bool:
        name = name.strip().strip("/")
        if not name:
            return False
        parts = [p.strip() for p in name.split("/") if p.strip()]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                curr = ""
                for part in parts:
                    curr = f"{curr}/{part}" if curr else part
                    cursor.execute("INSERT OR IGNORE INTO job_folders (name) VALUES (?)", (curr,))
                conn.commit()
                return True
            except Exception:
                return False

    def rename_job_folder(self, old_name: str, new_name: str) -> bool:
        old_name = old_name.strip().strip("/")
        new_name = new_name.strip().strip("/")
        if not old_name or not new_name or old_name == new_name:
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE job_folders SET name = ? WHERE name = ?", (new_name, old_name))
            cursor.execute("UPDATE sessions SET job = ? WHERE job = ?", (new_name, old_name))

            # Atualiza também subpastas filhas (ex: SEMANA-46/LOTE-1 -> SEMANA-47/LOTE-1)
            old_prefix = old_name + "/"
            cursor.execute("SELECT name FROM job_folders WHERE name LIKE ?", (old_prefix + "%",))
            subs = [row["name"] for row in cursor.fetchall()]
            for sub in subs:
                updated_sub = new_name + "/" + sub[len(old_prefix):]
                cursor.execute("UPDATE job_folders SET name = ? WHERE name = ?", (updated_sub, sub))

            cursor.execute("SELECT id, job FROM sessions WHERE job LIKE ?", (old_prefix + "%",))
            sess_rows = cursor.fetchall()
            for s in sess_rows:
                updated_j = new_name + "/" + s["job"][len(old_prefix):]
                cursor.execute("UPDATE sessions SET job = ? WHERE id = ?", (updated_j, s["id"]))

            conn.commit()
            return True

    def delete_job_folder(self, name: str, delete_sessions: bool = False) -> bool:
        name = name.strip().strip("/")
        old_prefix = name + "/"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM job_folders WHERE name = ? OR name LIKE ?", (name, old_prefix + "%"))
            if delete_sessions:
                cursor.execute("SELECT id FROM sessions WHERE job = ? OR job LIKE ?", (name, old_prefix + "%"))
                s_ids = [r[0] for r in cursor.fetchall()]
                if s_ids:
                    self.delete_sessions(s_ids)
            else:
                cursor.execute("UPDATE sessions SET job = '' WHERE job = ? OR job LIKE ?", (name, old_prefix + "%"))
            conn.commit()
            return True

    def update_shape_folder(self, shape_id, folder_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE shapes SET folder = ? WHERE id = ?", (folder_name or "", shape_id))
            conn.commit()

    def rename_shape(self, shape_id, new_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE shapes SET name = ? WHERE id = ?", (new_name.strip(), shape_id))
            conn.commit()

    def delete_shape(self, shape_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, folder FROM shapes WHERE id = ?", (shape_id,))
            row = cursor.fetchone()
            shp_name = row[0] if row else None
            shp_folder = row[1] if row else ""
            cursor.execute("DELETE FROM shapes WHERE id = ?", (shape_id,))
            if shp_name:
                cursor.execute("DELETE FROM shapes WHERE name = ? AND folder = ? AND id != ?", (shp_name, shp_folder, shape_id))
            conn.commit()

    def get_sessions(self, order_id=None, limit: Optional[int] = None, offset: int = 0):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            sql = "SELECT * FROM sessions"
            params = []
            if order_id:
                sql += " WHERE order_id = ?"
                params.append(order_id)
            sql += " ORDER BY id ASC"
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params.extend([int(limit), int(offset)])
            
            cursor.execute(sql, tuple(params) if params else None)
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d["placed_pieces"] = json.loads(d.get("placed_pieces_json") or "[]")
                d["shapes"] = json.loads(d.get("shapes_json") or "[]")
                d["strategy"] = d.get("strategy") or "flashnestsheet"
                d["params"] = d.get("params") or "stdNOTFill"
                d["machine"] = d.get("machine") or "ATOM FlashCut Flex 3020"
                d["gap_mm"] = float(d.get("gap_mm", 1.0) if d.get("gap_mm") is not None else 1.0)
                d["margin_left"] = float(d.get("margin_left", 10.0) if d.get("margin_left") is not None else 10.0)
                d["margin_right"] = float(d.get("margin_right", 10.0) if d.get("margin_right") is not None else 10.0)
                d["margin_top"] = float(d.get("margin_top", 10.0) if d.get("margin_top") is not None else 10.0)
                d["margin_bottom"] = float(d.get("margin_bottom", 10.0) if d.get("margin_bottom") is not None else 10.0)

                for idx, s in enumerate(d["shapes"], start=1):
                    s_sz = str(s.get("size") or s.get("name") or "41")
                    s["color"] = get_color_for_size(s_sz, idx)

                for idx, p in enumerate(d["placed_pieces"], start=1):
                    shp = p.get("shape", {}) if isinstance(p.get("shape"), dict) else {}
                    p_sz = str(p.get("size") or shp.get("size") or p.get("name") or shp.get("name") or "41")
                    p_col = get_color_for_size(p_sz, idx)
                    p["color"] = p_col
                    p["size"] = p_sz
                    if isinstance(p.get("shape"), dict):
                        p["shape"]["color"] = p_col
                        p["shape"]["size"] = p_sz

                results.append(d)
            return results

    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Retorna os dados de uma única sessão pelo seu ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["gap_mm"] = float(d.get("gap_mm", 1.0) if d.get("gap_mm") is not None else 1.0)
            d["margin_left"] = float(d.get("margin_left", 10.0) if d.get("margin_left") is not None else 10.0)
            d["margin_right"] = float(d.get("margin_right", 10.0) if d.get("margin_right") is not None else 10.0)
            d["margin_top"] = float(d.get("margin_top", 10.0) if d.get("margin_top") is not None else 10.0)
            d["margin_bottom"] = float(d.get("margin_bottom", 10.0) if d.get("margin_bottom") is not None else 10.0)
            d["placed_pieces"] = json.loads(d.get("placed_pieces_json") or "[]")
            for p in d["placed_pieces"]:
                p_sz = p.get("size", "41")
                p_col = get_color_for_size(p_sz)
                p["color"] = p_col
                if isinstance(p.get("shape"), dict):
                    p["shape"]["color"] = p_col
                    p["shape"]["size"] = p_sz
            return d

    def get_next_session_number(self) -> int:
        """
        Retorna o próximo número sequencial de sessão estritamente único e monotônico (#1, #2, #3...).
        Mesmo que sessões anteriores (ex: #1) sejam apagadas, o contador nunca regride nem reutiliza números.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Busca último número registrado nas configurações
            cursor.execute("SELECT `value` FROM settings WHERE `key` = 'last_session_number'")
            row_set = cursor.fetchone()
            last_num = 0
            if row_set:
                try:
                    val = row_set["value"] if isinstance(row_set, dict) else row_set[0]
                    last_num = int(val)
                except (ValueError, TypeError):
                    last_num = 0

            # 2. Busca maior id atualmente existente em sessions
            cursor.execute("SELECT COALESCE(MAX(id), 0) FROM sessions")
            row_max = cursor.fetchone()
            max_id = 0
            if row_max:
                try:
                    val_m = row_max[0] if isinstance(row_max, (tuple, list)) else list(row_max.values())[0]
                    max_id = int(val_m)
                except (ValueError, TypeError):
                    max_id = 0

            next_num = max(last_num, max_id) + 1
            return next_num

    def create_session(
        self,
        session_id: Optional[int] = None,
        name: str = "Nova Sessão",
        job: str = "ProduçãoNova",
        order_id: Optional[int] = None,
        material_id: str = "MAT_VAQ_01",
        status: str = "Stand by",
        placed_pieces: Optional[List[Dict[str, Any]]] = None,
        strategy: str = "flashnestsheet",
        params: str = "stdNOTFill",
        machine: str = "ATOM FlashCut Flex 3020",
        shapes: Optional[List[Dict[str, Any]]] = None,
        gap_mm: float = 1.0,
        margin_left: float = 10.0,
        margin_right: float = 10.0,
        margin_top: float = 10.0,
        margin_bottom: float = 10.0
    ) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Se session_id não for informado, busca próximo id sequencial monotônico
            if session_id is None or session_id <= 0:
                session_id = self.get_next_session_number()

            # 2. Resiliência de chave estrangeira: order_id (opcional, sem recriação forçada de pedidos)
            valid_order_id = order_id
            if valid_order_id is not None:
                cursor.execute("SELECT id FROM orders WHERE id = ?", (valid_order_id,))
                if not cursor.fetchone():
                    cursor.execute("SELECT id FROM orders ORDER BY id ASC LIMIT 1")
                    row_ord = cursor.fetchone()
                    if row_ord:
                        valid_order_id = row_ord[0] if isinstance(row_ord, (tuple, list)) else row_ord["id"]
                    else:
                        valid_order_id = None


            # 3. Resiliência de chave estrangeira: material_id
            valid_mat_id = material_id
            cursor.execute("SELECT id FROM materials WHERE id = ?", (valid_mat_id,))
            if not cursor.fetchone():
                cursor.execute("SELECT id FROM materials ORDER BY id ASC LIMIT 1")
                row_mat = cursor.fetchone()
                if row_mat:
                    valid_mat_id = row_mat[0] if isinstance(row_mat, (tuple, list)) else row_mat["id"]
                else:
                    valid_mat_id = "MAT_VAQ_01"
                    cursor.execute("""
                        INSERT INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, ("MAT_VAQ_01", "Vaqueta Bovino Preto 1.4mm", "como placa", 1380.0, 1080.0, 1.4904, 1.4, 2, 1.0))

            # 4. Garante unicidade do code SESS-xxx
            code = f"SESS-{session_id:03d}"
            cursor.execute("SELECT id FROM sessions WHERE code = ? AND id != ?", (code, session_id))
            if cursor.fetchone():
                code = f"SESS-{session_id:03d}-{int(time.time()) % 10000}"

            # 5. Gravação da sessão
            if conn.backend == "mysql":
                cursor.execute("""
                INSERT INTO sessions (id, code, order_id, material_id, name, job, status, yield_percent, cutting_time_sec, placed_pieces_json, strategy, params, machine, shapes_json, gap_mm, margin_left, margin_right, margin_top, margin_bottom)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                    code = VALUES(code), name = VALUES(name), job = VALUES(job), status = VALUES(status),
                    material_id = VALUES(material_id), placed_pieces_json = VALUES(placed_pieces_json),
                    strategy = VALUES(strategy), params = VALUES(params), machine = VALUES(machine), shapes_json = VALUES(shapes_json),
                    gap_mm = VALUES(gap_mm), margin_left = VALUES(margin_left), margin_right = VALUES(margin_right),
                    margin_top = VALUES(margin_top), margin_bottom = VALUES(margin_bottom)
                """, (
                    session_id, code, valid_order_id, valid_mat_id, name, job, status,
                    json.dumps(placed_pieces or []), strategy, params, machine, json.dumps(shapes or []), float(gap_mm),
                    float(margin_left), float(margin_right), float(margin_top), float(margin_bottom)
                ))
            else:
                cursor.execute("""
                REPLACE INTO sessions (id, code, order_id, material_id, name, job, status, yield_percent, cutting_time_sec, placed_pieces_json, strategy, params, machine, shapes_json, gap_mm, margin_left, margin_right, margin_top, margin_bottom)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, code, valid_order_id, valid_mat_id, name, job, status,
                    json.dumps(placed_pieces or []), strategy, params, machine, json.dumps(shapes or []), float(gap_mm),
                    float(margin_left), float(margin_right), float(margin_top), float(margin_bottom)
                ))

            # 6. Atualiza o contador permanente de último número de sessão
            cursor.execute("SELECT `value` FROM settings WHERE `key` = 'last_session_number'")
            row_last = cursor.fetchone()
            curr_last = 0
            if row_last:
                try:
                    curr_last = int(row_last["value"] if isinstance(row_last, dict) else row_last[0])
                except (ValueError, TypeError):
                    curr_last = 0
            if session_id > curr_last:
                cursor.execute("REPLACE INTO settings (`key`, `value`) VALUES ('last_session_number', ?)", (str(session_id),))

            conn.commit()
            return session_id

    def update_session(self, session_id, name=None, status=None, placed_pieces=None, yield_pct=None, time_sec=None, material_id=_SENTINEL, strategy=None, params=None, machine=None, shapes=None, job=None, clear_material=False, gap_mm=None, margin_left=None, margin_right=None, margin_top=None, margin_bottom=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            values = []
            if name is not None:
                updates.append("name = ?")
                values.append(name)
            if clear_material:
                updates.append("material_id = NULL")
            elif material_id is not _SENTINEL:
                updates.append("material_id = ?")
                values.append(material_id)
            if status is not None:
                updates.append("status = ?")
                values.append(status)
            if placed_pieces is not None:
                updates.append("placed_pieces_json = ?")
                values.append(json.dumps(placed_pieces))
            if shapes is not None:
                updates.append("shapes_json = ?")
                values.append(json.dumps(shapes))
            if yield_pct is not None:
                updates.append("yield_percent = ?")
                values.append(yield_pct)
            if time_sec is not None:
                updates.append("cutting_time_sec = ?")
                values.append(time_sec)
            if strategy is not None:
                updates.append("strategy = ?")
                values.append(strategy)
            if params is not None:
                updates.append("params = ?")
                values.append(params)
            if machine is not None:
                updates.append("machine = ?")
                values.append(machine)
            if job is not None:
                updates.append("job = ?")
                values.append(job)
            if gap_mm is not None:
                updates.append("gap_mm = ?")
                values.append(float(gap_mm))
            if margin_left is not None:
                updates.append("margin_left = ?")
                values.append(float(margin_left))
            if margin_right is not None:
                updates.append("margin_right = ?")
                values.append(float(margin_right))
            if margin_top is not None:
                updates.append("margin_top = ?")
                values.append(float(margin_top))
            if margin_bottom is not None:
                updates.append("margin_bottom = ?")
                values.append(float(margin_bottom))
            if updates:
                values.append(session_id)
                cursor.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?", values)
                conn.commit()

    def get_session_shapes(self, session_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT shapes_json FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except Exception:
                    return []
            return []

    def update_session_shapes(self, session_id, shapes):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE sessions SET shapes_json = ? WHERE id = ?", (json.dumps(shapes or []), session_id))
            conn.commit()

    def delete_sessions(self, session_ids):
        """Exclui múltiplas sessões e seus layouts/peças associadas em lote de forma atômica."""
        if not session_ids:
            return
        valid_ids = [int(sid) for sid in session_ids if sid is not None]
        if not valid_ids:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(valid_ids))
            # Garante limpeza em cascata inclusive se foreign keys estiverem desabilitadas
            cursor.execute(f"DELETE FROM layout_pieces WHERE layout_id IN (SELECT id FROM layouts WHERE session_id IN ({placeholders}))", tuple(valid_ids))
            cursor.execute(f"DELETE FROM layouts WHERE session_id IN ({placeholders})", tuple(valid_ids))
            cursor.execute(f"DELETE FROM sessions WHERE id IN ({placeholders})", tuple(valid_ids))
            conn.commit()

    def delete_session(self, session_id):
        self.delete_sessions([session_id])

    # -------------------------------------------------------------
    # Gestão de Opções / Configurações (Ferramentas -> Opções)
    # -------------------------------------------------------------
    def get_setting(self, key, default=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT `value` FROM settings WHERE `key` = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key, value):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("REPLACE INTO settings (`key`, `value`) VALUES (?, ?)", (key, str(value)))
            conn.commit()

    def get_all_settings(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT `key`, `value` FROM settings")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    def save_settings(self, settings_dict):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for k, v in settings_dict.items():
                cursor.execute("REPLACE INTO settings (`key`, `value`) VALUES (?, ?)", (k, str(v)))
            conn.commit()

    # -------------------------------------------------------------
    # Gestão de Presets DieProc (Configuração de Rotação / dp98)
    # -------------------------------------------------------------
    def get_dieproc_presets(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dieproc_presets ORDER BY name ASC")
            presets = {}
            for row in cursor.fetchall():
                presets[row["name"]] = dict(row)
            return presets

    def get_dieproc_preset(self, name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dieproc_presets WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def save_dieproc_preset(self, p):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            REPLACE INTO dieproc_presets 
            (name, coupling, step, solutions, range1_from, range1_to, range1_step, range2_from, range2_to, range2_step, range3_from, range3_to, range3_step, gap1, gap2, gap3, row_interlock, diagonal, macro_script)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p.get("name", "ALTERNADO"),
                p.get("coupling", "0/0 0/180"),
                float(p.get("step", 1.0)),
                int(p.get("solutions", 30)),
                float(p.get("range1_from", -3.0)),
                float(p.get("range1_to", 3.0)),
                float(p.get("range1_step", 1.0)),
                float(p.get("range2_from", 0.0)),
                float(p.get("range2_to", 0.0)),
                float(p.get("range2_step", 0.0)),
                float(p.get("range3_from", 0.0)),
                float(p.get("range3_to", 0.0)),
                float(p.get("range3_step", 0.0)),
                float(p.get("gap1", 1.0)),
                float(p.get("gap2", 0.0)),
                float(p.get("gap3", 0.0)),
                1 if p.get("row_interlock", True) else 0,
                1 if p.get("diagonal", False) else 0,
                str(p.get("macro_script", "") or "")
            ))
            conn.commit()

    def delete_dieproc_preset(self, name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dieproc_presets WHERE name = ?", (name,))
            conn.commit()

    # -------------------------------------------------------------
    # Gestão de Layouts de Corte (.lay) com Concorrência Otimista
    # -------------------------------------------------------------
    def save_layout(self, session_id: int, layout_data, expected_version: Optional[int] = None, layout_id: Optional[int] = None) -> int:
        """
        Salva um LayoutData nas tabelas layouts e layout_pieces, atualizando a sessão.
        Suporta controle de versão otimista (expected_version) e auditoria de operador (created_by/updated_by).
        """
        operator_info = get_current_operator()
        max_retries = 5

        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    yield_pct = layout_data.calculate_yield()
                    now_sql = "NOW()" if conn.backend == "mysql" else "CURRENT_TIMESTAMP"

                    target_lid = layout_id or getattr(layout_data, "id", None)
                    if target_lid:
                        # UPDATE em layout existente com controle otimista de versão
                        if expected_version is not None:
                            sql_upd = f"""
                            UPDATE layouts
                            SET version = version + 1,
                                updated_at = {now_sql},
                                updated_by = ?,
                                name = ?,
                                code = ?,
                                path = ?,
                                `desc` = ?,
                                material_code = ?,
                                material_name = ?,
                                gap_mm = ?,
                                ris_w = ?,
                                width_mm = ?,
                                ris_l = ?,
                                height_mm = ?,
                                area_mm2 = ?,
                                yield_percent = ?,
                                yield_pct = ?,
                                num_items = ?,
                                num_dies = ?
                            WHERE id = ? AND version = ?
                            """
                            cursor.execute(sql_upd, (
                                operator_info,
                                layout_data.filename or "l0000.lay",
                                layout_data.filename or "l0000.lay",
                                layout_data.path or "",
                                layout_data.desc or "",
                                layout_data.cod_r or "",
                                layout_data.cod_r or "",
                                float(layout_data.gap),
                                float(layout_data.ris_w),
                                float(layout_data.ris_w),
                                float(layout_data.ris_l),
                                float(layout_data.ris_l),
                                float(layout_data.area),
                                float(yield_pct),
                                float(yield_pct),
                                len(layout_data.items),
                                len(layout_data.target_dies),
                                target_lid,
                                expected_version
                            ))
                            if cursor.rowcount == 0:
                                raise VersionConflictError(
                                    f"Conflito de versão concorrente no layout {target_lid}: outro operador já salvou uma versão mais recente (esperada: {expected_version})."
                                )
                        else:
                            sql_upd = f"""
                            UPDATE layouts
                            SET version = version + 1,
                                updated_at = {now_sql},
                                updated_by = ?,
                                name = ?,
                                code = ?,
                                path = ?,
                                `desc` = ?,
                                material_code = ?,
                                material_name = ?,
                                gap_mm = ?,
                                ris_w = ?,
                                width_mm = ?,
                                ris_l = ?,
                                height_mm = ?,
                                area_mm2 = ?,
                                yield_percent = ?,
                                yield_pct = ?,
                                num_items = ?,
                                num_dies = ?
                            WHERE id = ?
                            """
                            cursor.execute(sql_upd, (
                                operator_info,
                                layout_data.filename or "l0000.lay",
                                layout_data.filename or "l0000.lay",
                                layout_data.path or "",
                                layout_data.desc or "",
                                layout_data.cod_r or "",
                                layout_data.cod_r or "",
                                float(layout_data.gap),
                                float(layout_data.ris_w),
                                float(layout_data.ris_w),
                                float(layout_data.ris_l),
                                float(layout_data.ris_l),
                                float(layout_data.area),
                                float(yield_pct),
                                float(yield_pct),
                                len(layout_data.items),
                                len(layout_data.target_dies),
                                target_lid
                            ))
                        actual_lid = target_lid
                        cursor.execute("DELETE FROM layout_pieces WHERE layout_id = ?", (actual_lid,))
                    else:
                        # INSERT de novo layout
                        sql_ins = f"""
                        INSERT INTO layouts (
                            session_id, name, code, path, `desc`, material_code, material_name,
                            gap_mm, ris_w, width_mm, ris_l, height_mm, area_mm2, yield_percent, yield_pct,
                            num_items, num_dies, version, created_at, updated_at, created_by, updated_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, {now_sql}, {now_sql}, ?, ?)
                        """
                        cursor.execute(sql_ins, (
                            session_id,
                            layout_data.filename or "l0000.lay",
                            layout_data.filename or "l0000.lay",
                            layout_data.path or "",
                            layout_data.desc or "",
                            layout_data.cod_r or "",
                            layout_data.cod_r or "",
                            float(layout_data.gap),
                            float(layout_data.ris_w),
                            float(layout_data.ris_w),
                            float(layout_data.ris_l),
                            float(layout_data.ris_l),
                            float(layout_data.area),
                            float(yield_pct),
                            float(yield_pct),
                            len(layout_data.items),
                            len(layout_data.target_dies),
                            operator_info,
                            operator_info
                        ))
                        actual_lid = cursor.lastrowid

                    # Mapeia moldes existentes no banco para linkar FK mold_id / shape_id
                    cursor.execute("SELECT id, name FROM shapes")
                    shape_lookup = {row["name"].lower(): row["id"] for row in cursor.fetchall()}

                    # Insere peças em lote (executemany) em UMA ÚNICA transação atômica curta
                    pieces_data = []
                    placed_pieces_list = []
                    for it in layout_data.items:
                        shp_id = shape_lookup.get(it.shape_name.lower())
                        pieces_data.append((
                            actual_lid,
                            shp_id,
                            shp_id,
                            it.item_no,
                            it.tg_idx,
                            it.inst_id,
                            it.shape_name,
                            it.size,
                            it.x,
                            it.y,
                            int(it.rot_deg) % 360,
                            it.rot_rad,
                            1 if it.is_mirrored else 0,
                            1 if it.is_mirrored else 0,
                            it.color,
                            it.tag,
                            getattr(it, "quality_zone", 1)
                        ))

                        placed_pieces_list.append({
                            "id": it.item_no,
                            "target_id": shp_id or (it.tg_idx + 1),
                            "name": it.shape_name,
                            "size": it.size,
                            "color": it.color,
                            "contour": it.contour,
                            "holes": it.holes,
                            "stitching": it.stitching,
                            "x": it.x,
                            "y": it.y,
                            "rotation": it.rot_deg,
                            "is_mirrored": it.is_mirrored
                        })

                    if pieces_data:
                        cursor.executemany("""
                        INSERT INTO layout_pieces (
                            layout_id, mold_id, shape_id, item_index, target_index, instance_id,
                            piece_name, size, x, y, rotation_deg, rotation_rad,
                            mirrored, is_mirrored, color, tag, quality_zone
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, pieces_data)

                    # Atualiza também a tabela sessions com o layout ativo
                    cursor.execute("""
                    UPDATE sessions 
                    SET placed_pieces_json = ?, yield_percent = ?, status = 'Nested'
                    WHERE id = ?
                    """, (json.dumps(placed_pieces_list), yield_pct, session_id))

                    conn.commit()
                    return actual_lid
            except Exception as e:
                if isinstance(e, VersionConflictError):
                    raise
                err_code = getattr(e, "args", [None])[0] if getattr(e, "args", None) else None
                if err_code == 1213 and attempt < max_retries - 1:
                    time.sleep(random.uniform(0.02, 0.08))
                    continue
                raise

    def get_layout_pieces(self, layout_id: int) -> list:
        """Retorna a lista de peças de um layout ordenadas por item_index."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM layout_pieces WHERE layout_id = ? ORDER BY item_index ASC", (layout_id,))
            return [dict(p) for p in cursor.fetchall()]

    def get_layouts(self, session_id: Optional[int] = None, limit: Optional[int] = None, offset: int = 0) -> list:
        """Retorna a lista de layouts salvos (com paginação opcional)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            sql = "SELECT * FROM layouts"
            params = []
            if session_id is not None:
                sql += " WHERE session_id = ?"
                params.append(session_id)
            sql += " ORDER BY id ASC"
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params.extend([int(limit), int(offset)])
            cursor.execute(sql, tuple(params) if params else None)
            return [dict(row) for row in cursor.fetchall()]

    def get_layout_by_id(self, layout_id: int) -> Optional[dict]:
        """Retorna os dados completos de um layout com sua lista de peças em uma única consulta."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM layouts WHERE id = ?", (layout_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            cursor.execute("SELECT * FROM layout_pieces WHERE layout_id = ? ORDER BY item_index ASC", (layout_id,))
            res["pieces"] = [dict(p) for p in cursor.fetchall()]
            return res

    def delete_layout(self, layout_id: int) -> bool:
        """Remove um layout e suas peças associadas."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM layout_pieces WHERE layout_id = ?", (layout_id,))
            cursor.execute("DELETE FROM layouts WHERE id = ?", (layout_id,))
            conn.commit()
            return True
