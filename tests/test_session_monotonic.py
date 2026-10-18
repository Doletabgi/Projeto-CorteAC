"""
Testes Unitários: Monotonicidade Estrita de Sessões e Persistência contra Re-semeadura
"""
import unittest
import tempfile
import os
from database import DatabaseManager


class TestSessionMonotonic(unittest.TestCase):
    def setUp(self):
        # Utiliza banco SQLite isolado para testes
        self.tmp_fd, self.tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_fd)
        self.db = DatabaseManager(self.tmp_path, backend="sqlite")

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            try:
                os.remove(self.tmp_path)
            except Exception:
                pass

    def test_monotonic_session_numbers_never_reused(self):
        """Testa que apagar uma sessão (#1) NUNCA permite que ela seja sugerida ou reutilizada."""
        # 1. Limpa todas as sessões iniciais se houver
        all_sess = self.db.get_sessions()
        if all_sess:
            self.db.delete_sessions([s["id"] for s in all_sess])

        # Define explicitamente last_session_number como 0 para testar a partir do início
        self.db.set_setting("last_session_number", "0")

        # Próxima sessão deve ser #1
        n1 = self.db.get_next_session_number()
        self.assertEqual(n1, 1)

        # Cria a sessão #1
        sid1 = self.db.create_session(session_id=n1, name="Sessão #1")
        self.assertEqual(sid1, 1)

        # Próxima sessão deve ser #2
        n2 = self.db.get_next_session_number()
        self.assertEqual(n2, 2)

        # Apaga a sessão #1
        self.db.delete_session(1)
        self.assertEqual(len(self.db.get_sessions()), 0)

        # CRÍTICO: Mesmo com o banco sem nenhuma sessão, a próxima NÃO pode ser #1!
        next_after_del = self.db.get_next_session_number()
        self.assertEqual(next_after_del, 2, "Número de sessão #1 nunca deve ser reutilizado após exclusão")

        # Cria a sessão #2
        sid2 = self.db.create_session(session_id=next_after_del, name="Sessão #2")
        self.assertEqual(sid2, 2)

        # Apaga a sessão #2
        self.db.delete_session(2)

        # Próxima deve ser #3
        next_after_del2 = self.db.get_next_session_number()
        self.assertEqual(next_after_del2, 3, "Número de sessão deve avançar monotonicamente para #3")

    def test_seed_guard_prevents_recreating_deleted_data(self):
        """Testa que fechar e abrir o programa (reinstanciar DatabaseManager) não recria sessões ou moldes apagados."""
        # 1. Apaga todas as sessões e todos os moldes
        for s in self.db.get_sessions():
            self.db.delete_session(s["id"])
        for shp in self.db.get_shapes():
            self.db.delete_shape(shp["id"])

        self.assertEqual(len(self.db.get_sessions()), 0)
        self.assertEqual(len(self.db.get_shapes()), 0)

        # 2. Simula fechar e abrir o programa (novo DatabaseManager no mesmo arquivo)
        db2 = DatabaseManager(self.tmp_path, backend="sqlite")

        # 3. Sessões e moldes apagados NÃO devem reaparecer
        self.assertEqual(len(db2.get_sessions()), 0, "Sessões apagadas não devem reaparecer ao reiniciar")
        self.assertEqual(len(db2.get_shapes()), 0, "Moldes apagados não devem reaparecer ao reiniciar")


    def test_create_shape_fk_resilience(self):
        """Testa que create_shape com article_id inválido ou None não falha com erro de chave estrangeira."""
        sid1 = self.db.create_shape(
            article_id=9999,
            name="Molde_FK_Invalido",
            color="#ff0000",
            contour=[{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 50}, {"x": 0, "y": 0}]
        )
        self.assertIsNotNone(sid1)
        self.assertGreater(sid1, 0)

        sid2 = self.db.create_shape(
            article_id=None,
            name="Molde_FK_None",
            color="#00ff00",
            contour=[{"x": 0, "y": 0}, {"x": 60, "y": 0}, {"x": 60, "y": 60}, {"x": 0, "y": 0}]
        )
        self.assertIsNotNone(sid2)
        self.assertGreater(sid2, 0)

    def test_job_folders_crud_and_persistence(self):
        """Testa criação, listagem, renomeação e exclusão de pastas de produção."""
        initial = self.db.get_job_folders()
        self.assertIn("ProduçãoNova", initial)

        # Cria nova pasta
        ok = self.db.create_job_folder("Lote_2026")
        self.assertTrue(ok)
        self.assertIn("Lote_2026", self.db.get_job_folders())

        # Renomeia
        ok = self.db.rename_job_folder("Lote_2026", "Lote_2026_Final")
        self.assertTrue(ok)
        self.assertNotIn("Lote_2026", self.db.get_job_folders())
        self.assertIn("Lote_2026_Final", self.db.get_job_folders())

        # Exclui pasta
        ok = self.db.delete_job_folder("Lote_2026_Final")
        self.assertTrue(ok)
        self.assertNotIn("Lote_2026_Final", self.db.get_job_folders())

    def test_delete_job_folder_persistence_across_restarts(self):
        """Testa que apagar uma pasta de produção (como ProduçãoNova) não reaparece ao reabrir o programa."""
        self.db.delete_job_folder("ProduçãoNova")
        self.assertEqual(len(self.db.get_job_folders()), 0)

        # Re-instancia DatabaseManager simulando fechar e reabrir o programa
        db2 = DatabaseManager(self.tmp_path, backend="sqlite")
        self.assertEqual(len(db2.get_job_folders()), 0, "Pasta excluída nunca deve reaparecer ao reiniciar")


if __name__ == "__main__":
    unittest.main()
