#!/usr/bin/env python3
"""
tools/clean_database.py

Higienização e Limpeza Pré-Release do Banco de Dados SQLite (JobManager / CorteAC).
Remove todos os layouts e instâncias de testes executados na suíte de testes e desenvolvimento,
garantindo que após qualquer atualização o programa sempre abra limpo e vazio, pronto para produção.

Ações realizadas:
1. Remove todas as peças em layout_pieces
2. Remove todos os registros da tabela layouts
3. Reseta placed_pieces_json='[]', yield_percent=0.0 e status='Stand by' em todas as sessões
4. Remove sessões criadas temporariamente por testes automatizados (ex.: 'Teste', 'Exclusao', etc.)
5. Reseta a sequência autoincrement de layouts
6. Executa VACUUM para reduzir o tamanho físico do arquivo .db
"""

import os
import sys
import sqlite3
import argparse
from pathlib import Path


def clean_db(db_path: str, verbose: bool = True) -> bool:
    path = Path(db_path).resolve()
    if not path.exists():
        if verbose:
            print(f"[AVISO] Banco '{path}' nao encontrado. Ignorando.")
        return False

    if verbose:
        print(f"[LIMPEZA] Iniciando limpeza do banco: {path}")

    conn = sqlite3.connect(path)
    cur = conn.cursor()

    try:
        # 1. Contagens prévias
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='layouts'")
        has_layouts = cur.fetchone()[0] > 0

        n_layouts = 0
        n_pieces = 0
        if has_layouts:
            cur.execute("SELECT count(*) FROM layouts")
            n_layouts = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='layout_pieces'")
            if cur.fetchone()[0] > 0:
                cur.execute("SELECT count(*) FROM layout_pieces")
                n_pieces = cur.fetchone()[0]

            # Limpa layouts e peças de corte
            cur.execute("DELETE FROM layout_pieces")
            cur.execute("DELETE FROM layouts")

        # 2. Remove sessões puramente de teste geradas por suites automatizadas
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='sessions'")
        if cur.fetchone()[0] > 0:
            cur.execute("""
            DELETE FROM sessions
            WHERE name LIKE '%Teste%'
               OR name LIKE '%Test%'
               OR name LIKE '%Empty%'
               OR name LIKE '%Exclusao%'
               OR name LIKE '%Refazer%'
            """)
            del_test_sess = cur.rowcount

            # 3. Reseta sessões legítimas para estado limpo (sem peças colocadas)
            cur.execute("""
            UPDATE sessions
            SET placed_pieces_json = '[]',
                yield_percent = 0.0,
                cutting_time_sec = 0.0,
                status = 'Stand by'
            """)
            reset_sess = cur.rowcount

            # Mantém última sessão ativa apontando para a sessão disponível mais recente
            cur.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1")
            last_row = cur.fetchone()
            if last_row:
                last_id = last_row[0]
                cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='settings'")
                if cur.fetchone()[0] > 0:
                    cur.execute("REPLACE INTO settings (`key`, `value`) VALUES ('last_active_session_id', ?)", (str(last_id),))

        # 4. Reseta sequências autoincrement
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
        if cur.fetchone()[0] > 0:
            cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('layouts', 'layout_pieces')")

        # 5. Registra versão instalada da aplicação
        try:
            from config import APP_VERSION
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='settings'")
            if cur.fetchone()[0] > 0:
                cur.execute("REPLACE INTO settings (`key`, `value`) VALUES ('installed_version', ?)", (str(APP_VERSION),))
        except Exception:
            pass

        conn.commit()

        # 5. Executa VACUUM para otimizar espaço
        cur.execute("VACUUM")
        conn.commit()

        if verbose:
            print(f"   [OK] Layouts removidos: {n_layouts}")
            if has_layouts:
                print(f"   [OK] Pecas em layout_pieces removidas: {n_pieces}")
            print(f"   [OK] Sessoes de teste eliminadas: {del_test_sess}")
            print(f"   [OK] Sessoes resetadas para Stand by: {reset_sess}")
            print(f"   [OK] Banco compactado com VACUUM com sucesso.")

        return True

    except Exception as exc:
        print(f"[ERRO] Falha ao limpar banco '{path}': {exc}")
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Limpeza e higienização do banco de dados do CorteAC.")
    parser.add_argument("--db", default=None, help="Caminho do arquivo de banco de dados específico")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent

    if args.db:
        targets = [args.db]
    else:
        # Limpa tanto o banco raiz quanto o de distribuição se existirem
        targets = [
            str(root / "jobmanager.db"),
            str(root / "dist" / "jobmanager.db")
        ]

    for t in targets:
        clean_db(t)


if __name__ == "__main__":
    main()
