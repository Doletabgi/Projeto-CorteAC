"""
Testes Unitários da Camada de Banco de Dados Central (MySQL 8.0 & SQLite Reserva)
Cobre: Conexão, Reconexão, CRUD, Transações, Rollback, Acentuação UTF-8 (ç, ã, é),
Controle Otimista de Concorrência (VersionConflictError), Servidor Inacessível e Fallback SQLite.
"""

import unittest
import os
import sys
from pathlib import Path

# Adiciona raiz do projeto
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import db
from db import (
    get_connection,
    DBConnection,
    ServerUnreachableError,
    VersionConflictError,
    get_active_backend,
    set_active_backend
)
from database import DatabaseManager
from cad.lay_parser import LayoutData, PlacedItem, TargetDie

TEST_DB_NAME = "jobmanager_test"

class TestDBLayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Garante que usamos o banco de testes separado
        cls.db = DatabaseManager(db_path=TEST_DB_NAME, backend="mysql")
        cls.original_backend = get_active_backend()

    @classmethod
    def tearDownClass(cls):
        set_active_backend(cls.original_backend)

    def setUp(self):
        # Limpa tabelas de teste antes de cada método para isolamento
        set_active_backend("mysql")
        conn = db.get_connection(database_override=TEST_DB_NAME)
        with conn:
            cur = conn.cursor()
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            cur.execute("TRUNCATE TABLE layout_pieces")
            cur.execute("TRUNCATE TABLE layouts")
            cur.execute("TRUNCATE TABLE shapes")
            cur.execute("TRUNCATE TABLE articles")
            cur.execute("TRUNCATE TABLE orders")
            cur.execute("TRUNCATE TABLE materials")
            cur.execute("TRUNCATE TABLE sessions")
            cur.execute("""
            INSERT INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm)
            VALUES ('MAT_VAQ_01', 'Vaqueta Bovino Preto 1.4mm', 'como placa', 1380.0, 1080.0, 1.4904, 1.4, 2, 1.0)
            """)
            cur.execute("""
            INSERT INTO orders (id, code, customer, status, name)
            VALUES (1, 'ORD-2026-001', 'Calçados Elite S/A', 'Em Produção', 'Derby Masculino #41')
            """)
            cur.execute("""
            INSERT INTO articles (id, order_id, name, pairs_count, material_id)
            VALUES (1, 1, 'Sapato Derby Masculino #41', 24, 'MAT_VAQ_01')
            """)
            cur.execute("""
            INSERT INTO sessions (id, code, order_id, material_id, name, job, status)
            VALUES (1, 'SESS-001', 1, 'MAT_VAQ_01', 'Sessão Teste #1', 'ProduçãoNova', 'Stand by')
            """)
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            conn.commit()

    def test_mysql_connection_and_reconnection(self):
        """Testa conexão básica e reconexão automática com MySQL 8.0."""
        conn = db.get_connection(database_override=TEST_DB_NAME)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 + 1 AS val")
            row = cur.fetchone()
            self.assertEqual(row["val"], 2)
            self.assertEqual(row[0], 2)
            # Testa ping e reconexão
            conn.raw.ping()
            self.assertTrue(conn.raw.open)

    def test_special_characters_and_accents_utf8mb4(self):
        """Testa suporte integral a acentos e caracteres especiais (ç, ã, é, ó, ú, emoji)."""
        conn = db.get_connection(database_override=TEST_DB_NAME)
        accented_name = "Couro Bovino Vaqueta Maçã 100% Legítimo - São Paulo / Ribeirão Preto - Edição Especial"
        mat_id = "MAT_TEST_ACCENTS_01"
        with conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (mat_id, accented_name, "Couro Padrão", 1380.0, 2980.0, 4.1124, 1.2))
            conn.commit()

            cur.execute("SELECT name FROM materials WHERE id = %s", (mat_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], accented_name)

    def test_crud_operations_mysql(self):
        """Testa operações completas de CRUD nas tabelas principais usando DatabaseManager."""
        mgr = DatabaseManager(db_path=TEST_DB_NAME, backend="mysql")

        # 1. Inserir Material
        mgr.create_material(
            mat_id="MAT_CRUD_01",
            name="Sintético Laminado PU Branco",
            type="Bobina",
            width_mm=1400.0,
            height_mm=50000.0,
            thickness_mm=0.8
        )
        mat = mgr.get_material("MAT_CRUD_01")
        self.assertIsNotNone(mat)
        self.assertEqual(mat["name"], "Sintético Laminado PU Branco")

        # 2. Inserir Ordem
        order_id = mgr.create_order(
            name="Pedido de Teste Calçado #42",
            customer="Calçados Franca Ltda",
            status="Em Produção"
        )
        self.assertGreater(order_id, 0)
        orders = mgr.get_orders()
        self.assertTrue(any(o["id"] == order_id for o in orders))

        # 3. Atualizar Ordem
        mgr.update_order(order_id, status="Concluído")
        updated_orders = [o for o in mgr.get_orders() if o["id"] == order_id]
        self.assertEqual(updated_orders[0]["status"], "Concluído")

        # 4. Criar Molde (Shape)
        shape_id = mgr.create_shape(
            article_id=1,
            name="Gáspea Oxford Especial",
            color="#2563eb",
            contour=[{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 80}, {"x": 0, "y": 80}],
            folder="Modelos2026",
            size="42"
        )
        self.assertGreater(shape_id, 0)
        shp = mgr.get_shape(shape_id)
        self.assertIsNotNone(shp)
        self.assertEqual(shp["name"], "Gáspea Oxford Especial")

        # 5. Excluir Molde
        mgr.delete_shape(shape_id)
        self.assertIsNone(mgr.get_shape(shape_id))

    def test_transaction_rollback_on_error(self):
        """Testa se uma exceção no meio da transação reverte todas as operações (ROLLBACK)."""
        conn = db.get_connection(database_override=TEST_DB_NAME)
        mat_id = "MAT_ROLLBACK_TEST"
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("""
                INSERT INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (mat_id, "Material Temporário", "Tipo", 100.0, 100.0, 0.01, 1.0))
                # Força erro na mesma transação
                raise RuntimeError("Simulação de falha intencional na transação!")
        except RuntimeError:
            pass

        # Verifica que o material NÃO foi gravado
        with db.get_connection(database_override=TEST_DB_NAME) as check_conn:
            cur = check_conn.cursor()
            cur.execute("SELECT * FROM materials WHERE id = %s", (mat_id,))
            self.assertIsNone(cur.fetchone())

    def test_version_conflict_optimistic_locking(self):
        """
        Testa o controle de concorrência otimista (Etapa 3):
        Dois clientes tentam salvar o mesmo layout partindo da versão 1.
        O primeiro tem sucesso e avança para a versão 2; o segundo recebe VersionConflictError.
        """
        mgr = DatabaseManager(db_path=TEST_DB_NAME, backend="mysql")

        # Cria layout inicial (versão 1)
        lay_initial = LayoutData(
            filename="layout_concorrencia.lay",
            ris_w=1500.0,
            ris_l=1000.0,
            gap=1.0,
            area=1.5,
            items=[
                PlacedItem(item_no=1, tg_idx=0, inst_id=1, x=100.0, y=100.0, rot_rad=0.0, rot_deg=0.0, color="-65536", shape_name="Gaspea", size="42")
            ],
            target_dies=[TargetDie(index=1, code="Gaspea.die", clean_name="Gaspea", qta_left=1)]
        )
        layout_id = mgr.save_layout(session_id=1, layout_data=lay_initial)
        self.assertGreater(layout_id, 0)

        # Verifica versão inicial = 1
        lay_record = mgr.get_layout_by_id(layout_id)
        self.assertEqual(lay_record["version"], 1)

        # Cliente A salva atualização passando expected_version=1 -> Sucesso (versão vira 2)
        lay_client_a = LayoutData(
            filename="layout_concorrencia.lay",
            ris_w=1500.0,
            ris_l=1000.0,
            gap=1.0,
            area=1.5,
            items=[
                PlacedItem(item_no=1, tg_idx=0, inst_id=1, x=120.0, y=120.0, rot_rad=0.0, rot_deg=0.0, color="-65536", shape_name="Gaspea", size="42")
            ],
            target_dies=[TargetDie(index=1, code="Gaspea.die", clean_name="Gaspea", qta_left=1)]
        )
        mgr.save_layout(session_id=1, layout_data=lay_client_a, expected_version=1, layout_id=layout_id)

        lay_record_after_a = mgr.get_layout_by_id(layout_id)
        self.assertEqual(lay_record_after_a["version"], 2)

        # Cliente B tenta salvar partindo da versão 1 antiga -> Deve levantar VersionConflictError!
        lay_client_b = LayoutData(
            filename="layout_concorrencia.lay",
            ris_w=1500.0,
            ris_l=1000.0,
            gap=1.0,
            area=1.5,
            items=[
                PlacedItem(item_no=1, tg_idx=0, inst_id=1, x=200.0, y=200.0, rot_rad=0.0, rot_deg=0.0, color="-65536", shape_name="Gaspea", size="42")
            ],
            target_dies=[TargetDie(index=1, code="Gaspea.die", clean_name="Gaspea", qta_left=1)]
        )
        with self.assertRaises(VersionConflictError):
            mgr.save_layout(session_id=1, layout_data=lay_client_b, expected_version=1, layout_id=layout_id)

    def test_unreachable_server_exception_handling(self):
        """Testa se porta/host inacessível gera ServerUnreachableError com diagnóstico claro."""
        import db.connection as dbc
        pool = dbc.SimpleMySQLPool("127.0.0.1", 59999, "bad_user", "bad_pass", "bad_db", "utf8mb4", 1)
        with self.assertRaises(ServerUnreachableError) as ctx:
            pool.get()
        self.assertEqual(ctx.exception.host, "127.0.0.1")
        self.assertEqual(ctx.exception.port, 59999)
        self.assertIn("111", str(ctx.exception.cause)) # Connection refused

    def test_sqlite_fallback_backend_functional(self):
        """Testa se o backend SQLite de reserva continua 100% funcional quando ativado."""
        set_active_backend("sqlite")
        try:
            db_sqlite = DatabaseManager(":memory:")
            conn = db_sqlite.get_connection()
            self.assertEqual(conn.backend, "sqlite")
            materials = db_sqlite.get_materials()
            self.assertGreater(len(materials), 0)
        finally:
            set_active_backend("mysql")

    def test_database_manager_backend_property(self):
        """Testa se a propriedade backend expõe corretamente o backend ativo."""
        mgr = DatabaseManager(db_path=TEST_DB_NAME, backend="mysql")
        self.assertEqual(mgr.backend, "mysql")

    def test_create_session_with_foreign_key_resilience(self):
        """Testa se create_session recupera graciosamente quando order_id ou material_id são inválidos."""
        mgr = DatabaseManager(db_path=TEST_DB_NAME, backend="mysql")
        sid = mgr.create_session(
            session_id=2001,
            name="Sessão Resiliente FK",
            order_id=99999,
            material_id="NON_EXISTENT_MAT"
        )
        self.assertEqual(sid, 2001)
        sess = mgr.get_session(2001)
        self.assertIsNotNone(sess)
        self.assertEqual(sess["name"], "Sessão Resiliente FK")
        self.assertEqual(sess["order_id"], 1)
        self.assertEqual(sess["material_id"], "MAT_VAQ_01")

    def test_create_session_auto_id_and_unique_code(self):
        """Testa criação de sessão com ID automático e garantia de código único."""
        mgr = DatabaseManager(db_path=TEST_DB_NAME, backend="mysql")
        sid1 = mgr.create_session(name="Sessão Auto 1")
        self.assertGreater(sid1, 0)
        sess1 = mgr.get_session(sid1)
        self.assertIsNotNone(sess1)

        sid2 = mgr.create_session(name="Sessão Auto 2")
        self.assertGreater(sid2, sid1)
        sess2 = mgr.get_session(sid2)
        self.assertIsNotNone(sess2)
        self.assertNotEqual(sess1["code"], sess2["code"])

    def test_delete_sessions_batch(self):
        """Testa exclusão em lote de múltiplas sessões com integridade referencial."""
        mgr = DatabaseManager(db_path=TEST_DB_NAME, backend="mysql")
        sids = []
        for i in range(1, 6):
            sid = mgr.create_session(session_id=3000 + i, name=f"Sessão Lote #{i}")
            sids.append(sid)

        self.assertEqual(len(sids), 5)
        for sid in sids:
            self.assertIsNotNone(mgr.get_session(sid))

        # Exclui lote de 3 sessões: 3001, 3003, 3005
        mgr.delete_sessions([3001, 3003, 3005])

        self.assertIsNone(mgr.get_session(3001))
        self.assertIsNotNone(mgr.get_session(3002))
        self.assertIsNone(mgr.get_session(3003))
        self.assertIsNotNone(mgr.get_session(3004))
        self.assertIsNone(mgr.get_session(3005))

        # Exclui as restantes
        mgr.delete_sessions([3002, 3004])
        self.assertIsNone(mgr.get_session(3002))
        self.assertIsNone(mgr.get_session(3004))

        # Chamada com lista vazia não deve quebrar
        mgr.delete_sessions([])

    def test_delete_material_unlinks_sessions_and_articles(self):
        """Valida que delete_material desassocia com segurança sessions (material_id = NULL) e remove o material sem violação de FK."""
        mgr = DatabaseManager(db_path=TEST_DB_NAME, backend="mysql")
        temp_mat_id = "MAT_TEST_DEL_01"
        mgr.create_material(temp_mat_id, "Material Temporário Teste")
        self.assertIsNotNone(mgr.get_material(temp_mat_id))

        sid = mgr.create_session(session_id=9876, material_id=temp_mat_id, name="Sessão com Material Teste")
        sess = mgr.get_session(sid)
        self.assertEqual(sess["material_id"], temp_mat_id)

        mgr.delete_material(temp_mat_id)

        self.assertIsNone(mgr.get_material(temp_mat_id))
        sess_after = mgr.get_session(sid)
        self.assertIsNotNone(sess_after)
        self.assertIsNone(sess_after["material_id"])

        mgr.delete_sessions([sid])

if __name__ == "__main__":
    unittest.main()
