#!/usr/bin/env python3
"""
tools/scrub_all_sessions_shapes.py

Utilitário de Manutenção e Higienização de Integridade das Sessões (JobManager 2000).
Varre o banco de dados identificando e corrigindo contaminações em sessions.shapes_json:
1. Remove moldes fantasmas (moldes que foram injetados do catálogo global mas possuem 0 peças nos layouts).
2. Recupera 'pairs', 'sequence' e metadados legítimos a partir dos moldes embutidos nas peças colocadas (placed_pieces).
3. Recalcula e restaura 'rest' e 'resto' com exatidão física.
4. Salva a lista de moldes autossuficiente e consistente.
"""

import os
import sys
import json
import sqlite3
import argparse
from typing import Dict, Any, List, Optional, Tuple

# Adiciona o diretório raiz ao sys.path para permitir imports de cad e ui se necessário
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from cad.nesting_engine import piece_matches_shape
    from cad.layers_rule import calc_resto_efetivo, is_separar_sobras_enabled
except ImportError:
    piece_matches_shape = None
    calc_resto_efetivo = None
    is_separar_sobras_enabled = None


def _fallback_piece_matches_shape(piece: dict, shape: dict) -> bool:
    """Verificação fallback se cad.nesting_engine não estiver disponível."""
    p_shp = piece.get("shape") if isinstance(piece.get("shape"), dict) else {}
    if p_shp and p_shp.get("id") is not None and shape.get("id") is not None:
        if str(p_shp.get("id")) == str(shape.get("id")):
            return True
    p_tid = str(piece.get("target_id") or "")
    s_id = str(shape.get("id") or "")
    if p_tid and s_id and p_tid == s_id:
        return True
    p_nm = str(piece.get("name") or "")
    s_nm = str(shape.get("name") or "")
    p_sz = str(piece.get("size") or "")
    s_sz = str(shape.get("size") or "")
    if p_nm and s_nm and p_nm == s_nm:
        if not p_sz or not s_sz or p_sz == s_sz:
            return True
    return False


def match_fn(piece: dict, shape: dict) -> bool:
    if piece_matches_shape is not None:
        return piece_matches_shape(piece, shape)
    return _fallback_piece_matches_shape(piece, shape)


def scrub_sessions(
    db_path: str = "jobmanager.db",
    dry_run: bool = False,
    target_session_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Higieniza as sessões do banco de dados, removendo moldes fantasmas e restaurando
    metadados legítimos (pairs, sequence, rest).
    """
    if not os.path.exists(db_path):
        print(f"[ERRO] Banco de dados '{db_path}' não encontrado.")
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM sessions"
    params = ()
    if target_session_id is not None:
        query += " WHERE id = ?"
        params = (int(target_session_id),)
    query += " ORDER BY id"

    cursor.execute(query, params)
    sessions = [dict(r) for r in cursor.fetchall()]

    results = []

    for sess in sessions:
        sess_id = sess["id"]
        sess_name = sess.get("name") or f"Sessão #{sess_id}"
        shapes_raw = sess.get("shapes_json") or "[]"
        try:
            shapes = json.loads(shapes_raw) if isinstance(shapes_raw, str) else shapes_raw
        except Exception:
            shapes = []

        # Busca layouts da sessão
        cursor.execute("SELECT * FROM layouts WHERE session_id = ? ORDER BY layout_index", (sess_id,))
        layout_rows = [dict(r) for r in cursor.fetchall()]

        all_pieces = []
        for lr in layout_rows:
            pj_raw = lr.get("placed_pieces_json") or "[]"
            try:
                pj = json.loads(pj_raw) if isinstance(pj_raw, str) else pj_raw
            except Exception:
                pj = []
            all_pieces.extend(pj)

        # Se não há peças nos layouts, checa placed_pieces_json da sessão
        if not all_pieces:
            sess_pj_raw = sess.get("placed_pieces_json") or "[]"
            try:
                all_pieces = json.loads(sess_pj_raw) if isinstance(sess_pj_raw, str) else sess_pj_raw
            except Exception:
                all_pieces = []

        if not all_pieces:
            # Sessão sem layouts nem peças colocadas: nada a podar
            continue

        # Coleta todas as peças e mapeia moldes embutidos nelas
        embedded_by_id = {}
        embedded_by_name_size = {}
        piece_folders = set()

        for p in all_pieces:
            p_shp = p.get("shape")
            if isinstance(p_shp, dict):
                sid = p_shp.get("id")
                if sid is not None and sid not in embedded_by_id:
                    embedded_by_id[str(sid)] = p_shp
                nm = p_shp.get("name") or p.get("name")
                sz = p_shp.get("size") or p.get("size")
                if nm and (nm, sz) not in embedded_by_name_size:
                    embedded_by_name_size[(str(nm), str(sz))] = p_shp
                fld = p_shp.get("folder")
                if fld:
                    piece_folders.add(str(fld))

        # Determina quais moldes da lista de shapes possuem peças físicas
        legit_shapes = []
        ghost_shapes = []

        for s in shapes:
            has_piece = any(match_fn(p, s) for p in all_pieces)
            if has_piece:
                legit_shapes.append(s)
            else:
                ghost_shapes.append(s)

        # Se não encontramos nenhuma correspondência, não arriscamos apagar tudo
        if not legit_shapes and shapes:
            continue

        # Se havia moldes fantasmas ou metadados nulos/corrompidos
        needs_update = False
        if len(ghost_shapes) > 0:
            needs_update = True

        cleaned_shapes = []
        for idx, s in enumerate(legit_shapes, start=1):
            s_clean = dict(s)
            sid = str(s_clean.get("id")) if s_clean.get("id") is not None else None
            emb = embedded_by_id.get(sid)
            if not emb and s_clean.get("name"):
                emb = embedded_by_name_size.get((str(s_clean.get("name")), str(s_clean.get("size"))))

            # Recupera pairs se nulo ou zero
            orig_pairs = s_clean.get("pairs")
            if (orig_pairs is None or orig_pairs == 0) and emb and emb.get("pairs"):
                s_clean["pairs"] = int(emb["pairs"])
                needs_update = True
            elif s_clean.get("pairs") is not None:
                s_clean["pairs"] = int(s_clean["pairs"])

            # Recupera sequence se nulo
            if s_clean.get("sequence") is None and emb and emb.get("sequence"):
                s_clean["sequence"] = int(emb["sequence"])
                needs_update = True
            elif s_clean.get("sequence") is not None:
                s_clean["sequence"] = int(s_clean["sequence"])
            else:
                s_clean["sequence"] = idx

            # Recupera target_pieces
            if s_clean.get("target_pieces") is None and emb and emb.get("target_pieces"):
                s_clean["target_pieces"] = int(emb["target_pieces"])

            # Recalcula saldo restante de pares considerando peças cortadas
            sess_layers = int(sess.get("layers") or 4)
            tot_phys = 0
            for lr in layout_rows:
                ly_l = int(lr.get("layers") or sess_layers)
                pj_raw = lr.get("placed_pieces_json") or "[]"
                try:
                    pj = json.loads(pj_raw) if isinstance(pj_raw, str) else pj_raw
                except Exception:
                    pj = []
                cnt = sum(1 for p in pj if match_fn(p, s_clean))
                tot_phys += cnt * ly_l

            pairs_cut = tot_phys // 2
            req_pairs = int(s_clean.get("pairs") or 0)
            rem = max(0, req_pairs - pairs_cut)
            s_clean["rest"] = rem

            is_sep = True
            if is_separar_sobras_enabled is not None:
                is_sep = is_separar_sobras_enabled(sess)
            if calc_resto_efetivo is not None:
                s_clean["resto"] = calc_resto_efetivo(req_pairs, sess_layers, separar=is_sep)
            else:
                s_clean["resto"] = rem

            cleaned_shapes.append(s_clean)

        report_entry = {
            "session_id": sess_id,
            "name": sess_name,
            "shapes_before": len(shapes),
            "shapes_after": len(cleaned_shapes),
            "ghosts_removed": [s.get("name") for s in ghost_shapes],
            "needs_update": needs_update
        }
        results.append(report_entry)

        if needs_update:
            print(f"[*] Sessão #{sess_id} ({sess_name}):")
            print(f"    - Moldes antes: {len(shapes)} -> depois: {len(cleaned_shapes)}")
            if ghost_shapes:
                print(f"    - Fantasmas removidos: {[s.get('name') for s in ghost_shapes]}")
            if not dry_run:
                cursor.execute(
                    "UPDATE sessions SET shapes_json = ? WHERE id = ?",
                    (json.dumps(cleaned_shapes), sess_id)
                )
                conn.commit()
                print(f"    -> [ATUALIZADO COM SUCESSO NO BANCO]")
            else:
                print(f"    -> [DRY-RUN: NENHUMA ALTERAÇÃO SALVA]")

    conn.close()
    return results


def main():
    parser = argparse.ArgumentParser(description="Higieniza moldes corrompidos das sessões no SQLite.")
    parser.add_argument("--db", default="jobmanager.db", help="Caminho do banco SQLite (padrão: jobmanager.db)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas simula e audita sem alterar o banco")
    parser.add_argument("--session-id", type=int, default=None, help="Executa apenas na sessão especificada")
    args = parser.parse_args()

    print(f"Iniciando varredura em: {args.db} (dry_run={args.dry_run})")
    results = scrub_sessions(db_path=args.db, dry_run=args.dry_run, target_session_id=args.session_id)
    print(f"\nConcluído! Total de sessões auditadas com layouts: {len(results)}")


if __name__ == "__main__":
    main()
