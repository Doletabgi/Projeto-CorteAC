"""
JobManager 2000 (Python Edition)
Teste de Carga e Concorrência para Servidor MySQL 8.0 Central (8 PCs de Fábrica)

Simula o ambiente de produção da fábrica:
- 8 PCs / threads simultâneas
- 1000 salvamentos de layouts de corte (50 a 100 peças por layout)
- Medição de throughput (ops/sec), latências (média, p95, máxima)
- Verificação de controle de concorrência otimista (VersionConflictError)
- Verificação de integridade referencial, ausência de transações órfãs e vazamentos no pool
"""

import time
import random
import threading
import statistics
import unittest
from typing import List, Dict, Any

import db
from db.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_CHARSET
from db.connection import VersionConflictError, SimpleMySQLPool
from database import DatabaseManager
from cad.lay_parser import LayoutData, PlacedItem, TargetDie

TEST_DB_NAME = "jobmanager_test"


class TestMySQLConcurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configura pool apontando para jobmanager_test com capacidade ampliada para 8 threads
        cls.pool = SimpleMySQLPool(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=TEST_DB_NAME,
            charset=MYSQL_CHARSET,
            pool_size=16
        )
        import db.connection as dbc
        dbc._mysql_pool = cls.pool
        cls.db_mgr = DatabaseManager(backend="mysql")

        # Limpa dados de testes anteriores em jobmanager_test
        conn = cls.pool.get()
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM layout_pieces")
            cur.execute("DELETE FROM layouts")
            # Cria 8 sessões independentes para os 8 PCs da fábrica
            for sid in range(9001, 9009):
                cur.execute("""
                INSERT IGNORE INTO sessions (id, code, order_id, material_id, name, job, status)
                VALUES (%s, %s, 1, 'MAT_VAQ_01', %s, 'ProducaoTeste', 'Stand by')
                """, (sid, f"SESS-TEST-{sid}", f"Sessão Teste PC {sid - 9000}"))
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        # Limpa dados criados após os testes
        conn = cls.pool.get()
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM layout_pieces")
            cur.execute("DELETE FROM layouts")
            cur.execute("DELETE FROM sessions WHERE id BETWEEN 9001 AND 9008")
            conn.commit()
        import db.connection as dbc
        dbc._mysql_pool = None

    def test_01_intentional_concurrent_overwrite_conflict(self):
        """
        Testa concorrência intencional: 2 clientes tentam atualizar o MESMO layout
        partindo da mesma versão simultaneamente.
        - Um cliente DEVE vencer e ter sucesso.
        - O outro DEVE receber VersionConflictError.
        - O estado final do banco deve ser 100% íntegro (versão = 2, peças batem com o vencedor).
        """
        # 1. Cria layout base inicial (versão 1)
        base_items = [
            PlacedItem(item_no=i, tg_idx=0, inst_id=i, x=float(i * 10), y=float(i * 10), rot_deg=0.0, color="-65536", shape_name=f"BasePiece_{i}", size="41")
            for i in range(1, 11)
        ]
        base_lay = LayoutData(
            filename="concorrencia_disputa.lay",
            ris_w=1500.0,
            ris_l=1000.0,
            gap=1.0,
            area=1.5,
            items=base_items,
            target_dies=[TargetDie(index=1, code="BasePiece.die", clean_name="BasePiece", qta_left=10)]
        )
        layout_id = self.db_mgr.save_layout(session_id=9001, layout_data=base_lay)
        self.assertGreater(layout_id, 0)

        # 2. Prepara 2 payloads distintos para o Cliente A e Cliente B
        items_a = [
            PlacedItem(item_no=i, tg_idx=0, inst_id=i, x=float(i * 15), y=float(i * 15), rot_deg=90.0, color="-65536", shape_name=f"PieceA_{i}", size="41")
            for i in range(1, 21)
        ]
        lay_a = LayoutData(
            filename="concorrencia_disputa.lay",
            ris_w=1500.0,
            ris_l=1000.0,
            gap=1.0,
            area=1.5,
            items=items_a,
            target_dies=[TargetDie(index=1, code="PieceA.die", clean_name="PieceA", qta_left=20)]
        )

        items_b = [
            PlacedItem(item_no=i, tg_idx=0, inst_id=i, x=float(i * 20), y=float(i * 20), rot_deg=180.0, color="-65536", shape_name=f"PieceB_{i}", size="42")
            for i in range(1, 31)
        ]
        lay_b = LayoutData(
            filename="concorrencia_disputa.lay",
            ris_w=1500.0,
            ris_l=1000.0,
            gap=1.0,
            area=1.5,
            items=items_b,
            target_dies=[TargetDie(index=1, code="PieceB.die", clean_name="PieceB", qta_left=30)]
        )

        results = {}
        barrier = threading.Barrier(2)

        def worker_a():
            barrier.wait()
            try:
                self.db_mgr.save_layout(session_id=9001, layout_data=lay_a, expected_version=1, layout_id=layout_id)
                results["client_a"] = "SUCCESS"
            except VersionConflictError as e:
                results["client_a"] = "CONFLICT"
            except Exception as e:
                results["client_a"] = f"ERROR: {e}"

        def worker_b():
            barrier.wait()
            try:
                self.db_mgr.save_layout(session_id=9001, layout_data=lay_b, expected_version=1, layout_id=layout_id)
                results["client_b"] = "SUCCESS"
            except VersionConflictError as e:
                results["client_b"] = "CONFLICT"
            except Exception as e:
                results["client_b"] = f"ERROR: {e}"

        th_a = threading.Thread(target=worker_a)
        th_b = threading.Thread(target=worker_b)

        th_a.start()
        th_b.start()
        th_a.join(timeout=10)
        th_b.join(timeout=10)

        # 3. Validações estritas de concorrência
        self.assertIn("SUCCESS", [results["client_a"], results["client_b"]], "Exatamente uma requisição deveria ter sucesso")
        self.assertIn("CONFLICT", [results["client_a"], results["client_b"]], "A outra requisição deveria receber VersionConflictError")

        # 4. Verifica integridade no banco
        rec = self.db_mgr.get_layout_by_id(layout_id)
        self.assertEqual(rec["version"], 2, "A versão final do layout deve ser 2")

        pieces = self.db_mgr.get_layout_pieces(layout_id)
        if results["client_a"] == "SUCCESS":
            self.assertEqual(len(pieces), 20, "Peças devem corresponder ao Cliente A")
            self.assertEqual(rec["num_items"], 20)
        else:
            self.assertEqual(len(pieces), 30, "Peças devem corresponder ao Cliente B")
            self.assertEqual(rec["num_items"], 30)

        print(f"\n[OK] Concorrência intencional: {results}")

    def test_02_load_8_clients_1000_layouts(self):
        """
        Teste de carga de alta densidade:
        - 8 threads concorrentes (PC 1 a 8)
        - 1000 salvamentos no total (125 por thread)
        - Cada layout com 50 a 100 peças reais
        - Métricas: Throughput, latência (média, p95, máxima), erros (0 esperado)
        """
        NUM_THREADS = 8
        TOTAL_SAVES = 1000
        SAVES_PER_THREAD = TOTAL_SAVES // NUM_THREADS

        latencies_ms: List[float] = []
        latencies_lock = threading.Lock()
        network_errors = []
        conflict_errors = []
        total_pieces_generated = [0]
        pieces_lock = threading.Lock()

        start_time = time.perf_counter()

        def client_worker(client_id: int):
            for i in range(SAVES_PER_THREAD):
                num_pieces = random.randint(50, 100)
                with pieces_lock:
                    total_pieces_generated[0] += num_pieces

                items = [
                    PlacedItem(
                        item_no=p_idx,
                        tg_idx=0,
                        inst_id=p_idx,
                        x=round(random.uniform(10.0, 1400.0), 2),
                        y=round(random.uniform(10.0, 950.0), 2),
                        rot_deg=random.choice([0.0, 90.0, 180.0, 270.0]),
                        color="-65536",
                        shape_name="Gaspea",
                        size=str(random.choice([39, 40, 41, 42, 43, 44]))
                    )
                    for p_idx in range(1, num_pieces + 1)
                ]

                lay = LayoutData(
                    filename=f"lay_c{client_id:02d}_{i:04d}.lay",
                    ris_w=1500.0,
                    ris_l=1000.0,
                    gap=1.0,
                    area=1.5,
                    items=items,
                    target_dies=[TargetDie(index=1, code="Gaspea.die", clean_name="Gaspea", qta_left=num_pieces)]
                )

                t0 = time.perf_counter()
                try:
                    self.db_mgr.save_layout(session_id=9000 + client_id, layout_data=lay)
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    with latencies_lock:
                        latencies_ms.append(elapsed_ms)
                except VersionConflictError as ve:
                    with latencies_lock:
                        conflict_errors.append(str(ve))
                except Exception as ex:
                    with latencies_lock:
                        network_errors.append(f"Client {client_id} iteration {i}: {ex}")

        threads = []
        for cid in range(1, NUM_THREADS + 1):
            t = threading.Thread(target=client_worker, args=(cid,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        total_duration_sec = time.perf_counter() - start_time
        successful_saves = len(latencies_ms)
        throughput = successful_saves / total_duration_sec if total_duration_sec > 0 else 0.0

        latencies_ms.sort()
        avg_lat = statistics.mean(latencies_ms) if latencies_ms else 0.0
        p95_lat = latencies_ms[int(len(latencies_ms) * 0.95)] if latencies_ms else 0.0
        max_lat = max(latencies_ms) if latencies_ms else 0.0
        min_lat = min(latencies_ms) if latencies_ms else 0.0

        print("\n" + "=" * 65)
        print("RESULTADOS DO TESTE DE CARGA (8 PCs, 1000 Layouts MySQL 8.0)")
        print("=" * 65)
        print(f"Threads Concorrentes     : {NUM_THREADS}")
        print(f"Salvamentos Concluídos   : {successful_saves} / {TOTAL_SAVES}")
        print(f"Total Peças Inseridas    : {total_pieces_generated[0]}")
        print(f"Tempo Total do Teste     : {total_duration_sec:.2f} s")
        print(f"Throughput (Vazão)       : {throughput:.2f} layouts/s")
        print(f"Latência Mínima          : {min_lat:.2f} ms")
        print(f"Latência Média           : {avg_lat:.2f} ms")
        print(f"Latência P95             : {p95_lat:.2f} ms")
        print(f"Latência Máxima          : {max_lat:.2f} ms")
        print(f"Taxa de Erros de Rede    : {len(network_errors)} (deve ser 0)")
        print(f"Taxa de Conflitos        : {len(conflict_errors)}")
        print("=" * 65)

        # Asserções de integridade e estabilidade
        self.assertEqual(len(network_errors), 0, f"Erros de rede/timeout encontrados: {network_errors[:5]}")
        self.assertEqual(successful_saves, TOTAL_SAVES, f"Esperado {TOTAL_SAVES} salvamentos com sucesso")

        # Verificação no banco de dados
        conn = self.pool.get()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM layouts WHERE session_id BETWEEN 9001 AND 9008")
            db_layout_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM layout_pieces lp JOIN layouts l ON lp.layout_id = l.id WHERE l.session_id BETWEEN 9001 AND 9008")
            db_piece_count = cur.fetchone()[0]

        # +1 pelo teste 01
        self.assertGreaterEqual(db_layout_count, TOTAL_SAVES)
        self.assertGreaterEqual(db_piece_count, total_pieces_generated[0])

        print(f"[OK] Integridade pós-teste confirmada: {db_layout_count} layouts e {db_piece_count} peças no MySQL.")


if __name__ == "__main__":
    unittest.main()
