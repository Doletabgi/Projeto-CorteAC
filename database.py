"""
JobManager 2000 (Python Edition)
SQLite Database Manager (Substitui os antigos arquivos DAO/Jet MDB)
"""

import sqlite3
import json
from typing import Optional, List, Dict, Any
from config import DATABASE_PATH, DEFAULT_MATERIALS
from cad.colors import get_color_for_size

class DatabaseManager:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = str(db_path)
        self._memory_conn = None
        if self.db_path == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:")
            self._memory_conn.row_factory = sqlite3.Row
        self.init_db()

    def get_connection(self):
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Tabela de Materiais
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

            # Tabela de Ordens (Orders)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                customer TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pendente',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Tabela de Artigos (Articles)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                pairs_count INTEGER NOT NULL DEFAULT 1,
                material_id TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (material_id) REFERENCES materials(id)
            )
            """)

            # Tabela de Pastas de Moldes (Shape Folders)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shape_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
            """)

            # Tabela de Peças / Moldes (Shapes / Dies)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shapes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                contour_json TEXT NOT NULL,
                holes_json TEXT DEFAULT '[]',
                stitching_json TEXT DEFAULT '[]',
                folder TEXT DEFAULT '',
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
            """)

            # Migração caso as colunas folder e size ainda não existam
            cursor.execute("PRAGMA table_info(shapes)")
            cols = [c[1] for c in cursor.fetchall()]
            if "folder" not in cols:
                cursor.execute("ALTER TABLE shapes ADD COLUMN folder TEXT DEFAULT ''")
            if "size" not in cols:
                cursor.execute("ALTER TABLE shapes ADD COLUMN size TEXT DEFAULT '41'")


            # Tabela de Sessões de Nesting (Sessions)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                order_id INTEGER NOT NULL,
                material_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                job TEXT NOT NULL DEFAULT 'ProduçãoNova',
                status TEXT NOT NULL DEFAULT 'Planejado',
                yield_percent REAL DEFAULT 0.0,
                cutting_time_sec REAL DEFAULT 0.0,
                placed_pieces_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (material_id) REFERENCES materials(id)
            )
            """)

            # Migração caso as colunas name, job, placed_pieces_json, strategy, params, machine ainda não existam em sessions
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

            # Migração caso a coluna name ainda não exista em orders
            cursor.execute("PRAGMA table_info(orders)")
            o_cols = [c[1] for c in cursor.fetchall()]
            if "name" not in o_cols:
                cursor.execute("ALTER TABLE orders ADD COLUMN name TEXT DEFAULT 'Derby Masculino #41'")

            # Tabela de Configurações do Sistema (Ferramentas -> Opções)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """)

            # Tabela de Presets DieProc (Configuração de Rotação / Sintéticos dp98)
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
                diagonal INTEGER DEFAULT 0
            )
            """)

            # Tabela de Layouts de Corte (.lay)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS layouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                code TEXT NOT NULL DEFAULT 'l0000.lay',
                path TEXT DEFAULT '',
                desc TEXT DEFAULT '',
                material_code TEXT DEFAULT '',
                material_name TEXT DEFAULT '',
                gap_mm REAL DEFAULT 1.0,
                ris_w REAL DEFAULT 0.0,
                ris_l REAL DEFAULT 0.0,
                area_mm2 REAL DEFAULT 0.0,
                yield_percent REAL DEFAULT 0.0,
                num_items INTEGER DEFAULT 0,
                num_dies INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """)

            # Tabela de Peças Posicionadas do Layout
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS layout_pieces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                layout_id INTEGER NOT NULL,
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
                is_mirrored INTEGER DEFAULT 0,
                color TEXT DEFAULT '#2563eb',
                tag TEXT DEFAULT 'Pasted',
                quality_zone INTEGER DEFAULT 1,
                FOREIGN KEY (layout_id) REFERENCES layouts(id) ON DELETE CASCADE,
                FOREIGN KEY (shape_id) REFERENCES shapes(id)
            )
            """)

            conn.commit()


        # Seed data inicial se tabela estiver vazia
        self.seed_initial_data()

    def seed_initial_data(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Inserir materiais padrão
            for mat in DEFAULT_MATERIALS:
                cursor.execute("""
                INSERT OR IGNORE INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm)
                VALUES (:id, :name, :type, :width_mm, :height_mm, :area_m2, :thickness_mm, :layers, :gap_mm)
                """, {
                    "id": mat["id"],
                    "name": mat["name"],
                    "type": mat.get("type", "como placa"),
                    "width_mm": mat.get("width_mm", 1380.0),
                    "height_mm": mat.get("height_mm", 2980.0),
                    "area_m2": mat.get("area_m2", 4.1124),
                    "thickness_mm": mat.get("thickness_mm", 1.0),
                    "layers": mat.get("layers", 2),
                    "gap_mm": mat.get("gap_mm", 1.0)
                })

            # Inserir configurações padrão (Ferramentas -> Opções)
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
                cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))

            # Inserir presets padrão DieProc (ATOM dp98)
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

            # Verificar se já existem ordens
            cursor.execute("SELECT COUNT(*) FROM orders")
            if cursor.fetchone()[0] == 0:
                # Criar Ordem Modelo
                cursor.execute("""
                INSERT INTO orders (code, customer, status)
                VALUES ('ORD-2026-001', 'Calçados Elite S/A', 'Em Produção')
                """)
                order_id = cursor.lastrowid

                # Criar Artigo
                cursor.execute("""
                INSERT INTO articles (order_id, name, pairs_count, material_id)
                VALUES (?, 'Sapato Derby Masculino #41', 24, 'MAT_VAQ_01')
                """, (order_id,))
                article_id = cursor.lastrowid
            else:
                cursor.execute("SELECT id FROM articles LIMIT 1")
                row = cursor.fetchone()
                article_id = row[0] if row else 1

            # Moldes CAD padrão de calçados (somente se a tabela shapes estiver vazia)
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

            # Verificar se já existem sessões
            cursor.execute("SELECT COUNT(*) FROM sessions")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                INSERT OR IGNORE INTO sessions (id, code, order_id, material_id, name, job, status, yield_percent, cutting_time_sec, placed_pieces_json)
                VALUES (91, 'SESS-091', 1, 'MAT_VAQ_01', 'Sessão Principal #91', 'ProduçãoNova', 'Stand by', 0.0, 0.0, '[]')
                """)
                cursor.execute("""
                INSERT OR IGNORE INTO sessions (id, code, order_id, material_id, name, job, status, yield_percent, cutting_time_sec, placed_pieces_json)
                VALUES (38, 'SESS-038', 1, 'MAT_VAQ_01', 'Corte Vamp/Toe', 'ProduçãoNova', 'Nested', 68.5, 142.0, '[]')
                """)

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
            cursor.execute("SELECT id FROM articles WHERE order_id = ?", (order_id,))
            art_ids = [r[0] for r in cursor.fetchall()]
            for aid in art_ids:
                cursor.execute("DELETE FROM shapes WHERE article_id = ?", (aid,))
            cursor.execute("DELETE FROM articles WHERE order_id = ?", (order_id,))
            cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
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
            cursor.execute("""
            INSERT OR REPLACE INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (mat_id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm))
            conn.commit()
            return self.get_material(mat_id)

    def delete_material(self, mat_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
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

    def create_shape(self, article_id, name, color, contour, holes=None, stitching=None, folder="", size="41"):
        s_size = str(size or name or "41")
        color = get_color_for_size(s_size)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO shapes (article_id, name, color, contour_json, holes_json, stitching_json, folder, size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article_id,
                name,
                color,
                json.dumps(contour),
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
        name = name.strip()
        if not name:
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT OR IGNORE INTO shape_folders (name) VALUES (?)", (name,))
                conn.commit()
                return True
            except Exception:
                return False

    def rename_shape_folder(self, old_name, new_name):
        old_name = old_name.strip()
        new_name = new_name.strip()
        if not old_name or not new_name:
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE shape_folders SET name = ? WHERE name = ?", (new_name, old_name))
            cursor.execute("UPDATE shapes SET folder = ? WHERE folder = ?", (new_name, old_name))
            conn.commit()
            return True

    def delete_shape_folder(self, name, delete_shapes=False):
        name = name.strip()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM shape_folders WHERE name = ?", (name,))
            if delete_shapes:
                cursor.execute("DELETE FROM shapes WHERE folder = ?", (name,))
            else:
                cursor.execute("UPDATE shapes SET folder = '' WHERE folder = ?", (name,))
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
                # Se houver duplicatas com o mesmo nome na mesma pasta, remove para evitar fantasmas
                cursor.execute("DELETE FROM shapes WHERE name = ? AND folder = ? AND id != ?", (shp_name, shp_folder, shape_id))
            conn.commit()

    def get_sessions(self, order_id=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if order_id:
                cursor.execute("""
                    SELECT * FROM sessions WHERE order_id = ? 
                    ORDER BY CASE WHEN id = 91 THEN 1 WHEN id = 38 THEN 2 ELSE 3 END, id ASC
                """, (order_id,))
            else:
                cursor.execute("""
                    SELECT * FROM sessions 
                    ORDER BY CASE WHEN id = 91 THEN 1 WHEN id = 38 THEN 2 ELSE 3 END, id ASC
                """)
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d["placed_pieces"] = json.loads(d.get("placed_pieces_json") or "[]")
                d["shapes"] = json.loads(d.get("shapes_json") or "[]")
                d["strategy"] = d.get("strategy") or "flashnestsheet"
                d["params"] = d.get("params") or "stdNOTFill"
                d["machine"] = d.get("machine") or "ATOM FlashCut Flex 3020"

                # Garante que todo molde tenha sua respectiva cor exclusiva por número (sem repetições)
                for idx, s in enumerate(d["shapes"], start=1):
                    s_sz = str(s.get("size") or s.get("name") or "41")
                    s["color"] = get_color_for_size(s_sz, idx)

                # Garante que cada peça posicionada tenha sua cor resolvida exclusivamente por tamanho
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

    def create_session(self, session_id, name, job="ProduçãoNova", order_id=1, material_id="MAT_VAQ_01", status="Stand by", placed_pieces=None, strategy="flashnestsheet", params="stdNOTFill", machine="ATOM FlashCut Flex 3020", shapes=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            code = f"SESS-{session_id:03d}"
            cursor.execute("""
            INSERT OR REPLACE INTO sessions (id, code, order_id, material_id, name, job, status, yield_percent, cutting_time_sec, placed_pieces_json, strategy, params, machine, shapes_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, ?, ?, ?, ?, ?)
            """, (
                session_id,
                code,
                order_id,
                material_id,
                name,
                job,
                status,
                json.dumps(placed_pieces or []),
                strategy,
                params,
                machine,
                json.dumps(shapes or [])
            ))
            conn.commit()
            return session_id

    def update_session(self, session_id, name=None, status=None, placed_pieces=None, yield_pct=None, time_sec=None, material_id=None, strategy=None, params=None, machine=None, shapes=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            values = []
            if name is not None:
                updates.append("name = ?")
                values.append(name)
            if material_id is not None:
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

    def delete_session(self, session_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()

    # -------------------------------------------------------------
    # Gestão de Opções / Configurações (Ferramentas -> Opções)
    # -------------------------------------------------------------
    def get_setting(self, key, default=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key, value):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()

    def get_all_settings(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    def save_settings(self, settings_dict):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for k, v in settings_dict.items():
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
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
            INSERT OR REPLACE INTO dieproc_presets 
            (name, coupling, step, solutions, range1_from, range1_to, range1_step, range2_from, range2_to, range2_step, range3_from, range3_to, range3_step, gap1, gap2, gap3, row_interlock, diagonal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                1 if p.get("diagonal", False) else 0
            ))
            conn.commit()

    def delete_dieproc_preset(self, name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dieproc_presets WHERE name = ?", (name,))
            conn.commit()

    def save_layout(self, session_id: int, layout_data) -> int:
        """
        Salva um LayoutData nas tabelas layouts e layout_pieces do SQLite,
        atualizando também a sessão correspondente com o rendimento e peças em JSON.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Calcula yield se necessário
            yield_pct = layout_data.calculate_yield()

            cursor.execute("""
            INSERT INTO layouts (
                session_id, code, path, desc, material_code, material_name,
                gap_mm, ris_w, ris_l, area_mm2, yield_percent, num_items, num_dies
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                layout_data.filename or "l0000.lay",
                layout_data.path or "",
                layout_data.desc or "",
                layout_data.cod_r or "",
                layout_data.cod_r or "",
                float(layout_data.gap),
                float(layout_data.ris_w),
                float(layout_data.ris_l),
                float(layout_data.area),
                float(yield_pct),
                len(layout_data.items),
                len(layout_data.target_dies)
            ))
            layout_id = cursor.lastrowid

            # Mapeia moldes existentes no banco para linkar FK shape_id
            cursor.execute("SELECT id, name FROM shapes")
            shape_lookup = {row["name"].lower(): row["id"] for row in cursor.fetchall()}

            # Insere peças
            placed_pieces_list = []
            for it in layout_data.items:
                shp_id = shape_lookup.get(it.shape_name.lower())
                cursor.execute("""
                INSERT INTO layout_pieces (
                    layout_id, shape_id, item_index, target_index, instance_id,
                    piece_name, size, x, y, rotation_deg, rotation_rad,
                    is_mirrored, color, tag, quality_zone
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    layout_id,
                    shp_id,
                    it.item_no,
                    it.tg_idx,
                    it.inst_id,
                    it.shape_name,
                    it.size,
                    it.x,
                    it.y,
                    it.rot_deg,
                    it.rot_rad,
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

            # Atualiza também a tabela sessions com o layout ativo
            cursor.execute("""
            UPDATE sessions 
            SET placed_pieces_json = ?, yield_percent = ?, status = 'Nested'
            WHERE id = ?
            """, (json.dumps(placed_pieces_list), yield_pct, session_id))

            conn.commit()
            return layout_id

    def get_layouts(self, session_id: Optional[int] = None) -> list:
        """Retorna a lista de layouts salvos para a sessão especificada."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if session_id is not None:
                cursor.execute("SELECT * FROM layouts WHERE session_id = ? ORDER BY id ASC", (session_id,))
            else:
                cursor.execute("SELECT * FROM layouts ORDER BY id ASC")
            return [dict(row) for row in cursor.fetchall()]

    def get_layout_by_id(self, layout_id: int) -> Optional[dict]:
        """Retorna os dados completos de um layout com sua lista de peças."""
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




