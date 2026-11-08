"""
JobManager 2000 / CorteAC (Python Edition)
CAD / DB: Motor de Backup e Restauração de Moldes Cadastrados
Gerenciamento de pacotes de backup compactados (.zip / .csh), inspeção de integridade,
resolução de conflitos e restauração nos bancos SQLite e MySQL.
"""

import os
import sys
import json
import zipfile
import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from config import APP_NAME, APP_VERSION
from cad.die_parser import generate_die_content, parse_die_content


@dataclass
class BackupSummary:
    target_file: str
    total_shapes: int
    total_folders: int
    total_articles: int
    file_size_bytes: int
    created_at: str
    included_dies: bool = True
    total_sessions: int = 0
    total_layouts: int = 0
    backup_type: str = "all"  # "all", "shapes_only", "sessions_only"


@dataclass
class BackupInspectionResult:
    is_valid: bool
    app_version: str = ""
    created_at: str = ""
    total_shapes: int = 0
    total_folders: int = 0
    total_articles: int = 0
    total_sessions: int = 0
    total_layouts: int = 0
    has_shapes: bool = False
    has_sessions: bool = False
    folders: List[str] = field(default_factory=list)
    shapes: List[Dict[str, Any]] = field(default_factory=list)
    sessions: List[Dict[str, Any]] = field(default_factory=list)
    is_legacy_die_zip: bool = False
    error: Optional[str] = None


@dataclass
class RestoreResult:
    total_in_backup: int
    imported_new: int
    updated_existing: int
    skipped: int
    folders_created: int
    total_sessions_in_backup: int = 0
    sessions_imported: int = 0
    sessions_updated: int = 0
    sessions_skipped: int = 0
    errors: List[str] = field(default_factory=list)


def create_shapes_backup(
    db,
    target_file: str | Path,
    folder_filter: Optional[List[str]] = None,
    include_die_files: bool = True,
    backup_scope: str = "all",  # "all", "shapes_only", "sessions_only"
    session_filter_job: Optional[str] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None
) -> BackupSummary:
    """
    Gera um pacote de backup compactado (.zip ou .csh) contendo moldes e/ou sessões de corte.
    
    Estrutura do arquivo ZIP:
      - manifest.json: Metadados do backup (data/hora, versão, contagens, backup_type)
      - shapes.json: Lista estruturada completa de geometrias, furos e formatos (se shapes inclusos)
      - folders.json: Pastas de moldes cadastradas (se shapes inclusos)
      - articles.json: Artigos e pares associados (se shapes inclusos)
      - dies/<pasta>/<nome>.die: Arquivos .die individuais ATOM FlashCut (se include_die_files=True)
      - sessions.json: Lista completa de sessões com todas as suas placas/layouts e peças
      - materials.json: Materiais referenciados pelas sessões (para portabilidade total)
    """
    target_path = Path(target_file)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    include_shapes = backup_scope in ("all", "shapes_only")
    include_sessions = backup_scope in ("all", "sessions_only")

    clean_shapes = []
    folders_to_backup = []
    articles_to_backup = []

    if include_shapes:
        # 1. Obter moldes do banco de dados
        all_shapes = db.get_all_shapes() if hasattr(db, "get_all_shapes") else []

        if folder_filter:
            folder_set = set(folder_filter)
            shapes_to_backup = [s for s in all_shapes if (s.get("folder") or "") in folder_set]
        else:
            shapes_to_backup = list(all_shapes)

        # 2. Obter pastas de moldes
        all_folders = db.get_shape_folders() if hasattr(db, "get_shape_folders") else []
        if folder_filter:
            folders_to_backup = [f for f in all_folders if f in folder_set]
        else:
            folders_to_backup = list(all_folders)

        for s in shapes_to_backup:
            f = (s.get("folder") or "").strip()
            if f and f not in folders_to_backup:
                folders_to_backup.append(f)
        folders_to_backup.sort()

        # 3. Mapear artigos
        article_ids = {s.get("article_id") for s in shapes_to_backup if s.get("article_id")}
        try:
            orders = db.get_orders() if hasattr(db, "get_orders") else []
            for o in orders:
                arts = db.get_articles_by_order(o["id"]) if hasattr(db, "get_articles_by_order") else []
                for a in arts:
                    if a.get("id") in article_ids:
                        articles_to_backup.append({
                            "id": a.get("id"),
                            "name": a.get("name"),
                            "pairs_count": a.get("pairs_count", 1),
                            "material_id": a.get("material_id")
                        })
        except Exception:
            pass

        # 4. Preparar lista canônica de moldes
        for s in shapes_to_backup:
            clean_shapes.append({
                "name": str(s.get("name", "Molde")).strip(),
                "size": str(s.get("size", "41")).strip(),
                "color": str(s.get("color", "#000080")),
                "folder": str(s.get("folder", "") or "").strip(),
                "shape_format": str(s.get("shape_format", "1x1")).strip(),
                "contour": s.get("contour", []),
                "holes": s.get("holes", []),
                "stitching": s.get("stitching", []),
                "article_id": s.get("article_id")
            })

    # 5. Obter e preparar sessões de corte e layouts
    clean_sessions = []
    materials_to_backup = []
    total_layouts_count = 0

    if include_sessions:
        all_sessions = db.get_sessions() if hasattr(db, "get_sessions") else []
        if session_filter_job:
            sess_job_clean = str(session_filter_job).strip().lower()
            sessions_to_backup = [s for s in all_sessions if str(s.get("job") or "").strip().lower() == sess_job_clean]
        else:
            sessions_to_backup = list(all_sessions)

        referenced_mat_ids = set()

        for s in sessions_to_backup:
            s_id = s.get("id")
            lys = []
            if s_id and hasattr(db, "get_session_layouts"):
                try:
                    lys = db.get_session_layouts(s_id)
                except Exception:
                    lys = []
            total_layouts_count += len(lys)

            m_id = s.get("material_id")
            if m_id:
                referenced_mat_ids.add(str(m_id).strip())

            clean_sessions.append({
                "id": s_id,
                "code": s.get("code"),
                "name": str(s.get("name") or "Sessão").strip(),
                "job": str(s.get("job") or "ProduçãoNova").strip(),
                "status": str(s.get("status") or "Stand by").strip(),
                "order_id": s.get("order_id"),
                "material_id": m_id,
                "yield_percent": float(s.get("yield_percent", 0.0) or 0.0),
                "cutting_time_sec": float(s.get("cutting_time_sec", 0.0) or 0.0),
                "strategy": s.get("strategy") or "flashnestsheet",
                "params": s.get("params") or "stdNOTFill",
                "machine": s.get("machine") or "ATOM FlashCut Flex 3020",
                "gap_mm": float(s.get("gap_mm", 1.0) if s.get("gap_mm") is not None else 1.0),
                "margin_left": float(s.get("margin_left", 10.0) if s.get("margin_left") is not None else 10.0),
                "margin_right": float(s.get("margin_right", 10.0) if s.get("margin_right") is not None else 10.0),
                "margin_top": float(s.get("margin_top", 10.0) if s.get("margin_top") is not None else 10.0),
                "margin_bottom": float(s.get("margin_bottom", 10.0) if s.get("margin_bottom") is not None else 10.0),
                "nesting_mode": s.get("nesting_mode") or "custom",
                "layers": int(s["layers"]) if s.get("layers") is not None else None,
                "shapes": s.get("shapes") or [],
                "placed_pieces": s.get("placed_pieces") or [],
                "layouts": lys
            })

        # Obter materiais vinculados para portabilidade
        if hasattr(db, "get_materials"):
            try:
                all_mats = db.get_materials() or []
                for m in all_mats:
                    if str(m.get("id") or "").strip() in referenced_mat_ids:
                        materials_to_backup.append(dict(m))
            except Exception:
                pass

    created_iso = datetime.now().isoformat(timespec="seconds")

    total_steps = len(clean_shapes) + len(clean_sessions) + 5
    current_step = 0

    if on_progress:
        on_progress(current_step, total_steps, "Inicializando arquivo de backup...")

    manifest_data = {
        "app": APP_NAME,
        "app_version": APP_VERSION,
        "format_version": "2.0",
        "created_at": created_iso,
        "backup_type": backup_scope,
        "total_shapes": len(clean_shapes),
        "total_folders": len(folders_to_backup),
        "total_articles": len(articles_to_backup),
        "total_sessions": len(clean_sessions),
        "total_layouts": total_layouts_count,
        "description": "Backup do CorteAC (Moldes e Sessões de Corte)"
    }

    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Grava metadados
        zf.writestr("manifest.json", json.dumps(manifest_data, indent=2, ensure_ascii=False))
        current_step += 1
        if on_progress:
            on_progress(current_step, total_steps, "Gravando metadados do pacote...")

        if include_shapes:
            zf.writestr("shapes.json", json.dumps(clean_shapes, indent=2, ensure_ascii=False))
            current_step += 1
            if on_progress:
                on_progress(current_step, total_steps, "Gravando geometrias de moldes...")

            zf.writestr("folders.json", json.dumps(folders_to_backup, indent=2, ensure_ascii=False))
            current_step += 1
            if on_progress:
                on_progress(current_step, total_steps, "Gravando catálogo de pastas...")

            zf.writestr("articles.json", json.dumps(articles_to_backup, indent=2, ensure_ascii=False))
            current_step += 1
            if on_progress:
                on_progress(current_step, total_steps, "Gravando artigos...")

            if include_die_files:
                for s in clean_shapes:
                    current_step += 1
                    s_name = s.get("name", "molde")
                    s_folder = s.get("folder", "")
                    if on_progress:
                        on_progress(current_step, total_steps, f"Exportando .die de {s_name}...")

                    try:
                        die_text = generate_die_content(s)
                        clean_folder_part = re.sub(r'[\\:*?"<>|]', '_', s_folder).strip() if s_folder else ""
                        clean_file_part = re.sub(r'[\\:*?"<>|]', '_', s_name).strip() or "molde"
                        if clean_folder_part:
                            die_arcname = f"dies/{clean_folder_part}/{clean_file_part}.die"
                        else:
                            die_arcname = f"dies/{clean_file_part}.die"
                        zf.writestr(die_arcname, die_text)
                    except Exception:
                        pass

        if include_sessions:
            zf.writestr("sessions.json", json.dumps(clean_sessions, indent=2, ensure_ascii=False))
            current_step += 1
            if on_progress:
                on_progress(current_step, total_steps, "Gravando sessões e layouts de corte...")

            if materials_to_backup:
                zf.writestr("materials.json", json.dumps(materials_to_backup, indent=2, ensure_ascii=False))

    file_size = target_path.stat().st_size if target_path.exists() else 0

    if on_progress:
        on_progress(total_steps, total_steps, "Backup gerado com sucesso!")

    return BackupSummary(
        target_file=str(target_path),
        total_shapes=len(clean_shapes),
        total_folders=len(folders_to_backup),
        total_articles=len(articles_to_backup),
        file_size_bytes=file_size,
        created_at=created_iso,
        included_dies=include_die_files and len(clean_shapes) > 0,
        total_sessions=len(clean_sessions),
        total_layouts=total_layouts_count,
        backup_type=backup_scope
    )


def inspect_shapes_backup(backup_file: str | Path) -> BackupInspectionResult:
    """
    Inspeciona um arquivo de backup (.zip/.csh) sem aplicar alterações no banco de dados.
    Valida a assinatura, extrai estatísticas, lista de moldes, pastas e sessões de corte.
    Também reconhece ZIPs com arquivos .die avulsos de sistemas legados.
    """
    backup_path = Path(backup_file)
    if not backup_path.exists() or not backup_path.is_file():
        return BackupInspectionResult(is_valid=False, error="Arquivo de backup não encontrado.")

    if not zipfile.is_zipfile(backup_path):
        return BackupInspectionResult(is_valid=False, error="O arquivo selecionado não é um arquivo ZIP válido.")

    try:
        with zipfile.ZipFile(backup_path, "r") as zf:
            namelist = zf.namelist()

            manifest = {}
            if "manifest.json" in namelist:
                try:
                    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                except Exception:
                    manifest = {}

            has_native_shapes = "shapes.json" in namelist
            has_native_sessions = "sessions.json" in namelist
            die_files = [n for n in namelist if n.lower().endswith(".die") and not n.startswith("__MACOSX")]

            # Cenário 1: Pacote de backup nativo do CorteAC (manifest.json, shapes.json e/ou sessions.json)
            if has_native_shapes or has_native_sessions:
                folders_list = []
                if "folders.json" in namelist:
                    try:
                        folders_list = json.loads(zf.read("folders.json").decode("utf-8"))
                    except Exception:
                        pass

                articles_list = []
                if "articles.json" in namelist:
                    try:
                        articles_list = json.loads(zf.read("articles.json").decode("utf-8"))
                    except Exception:
                        pass

                # Prepara resumos leves de cada molde para exibição
                shape_summaries = []
                if has_native_shapes:
                    try:
                        shapes_raw = json.loads(zf.read("shapes.json").decode("utf-8"))
                    except Exception:
                        shapes_raw = []

                    for s in shapes_raw:
                        cntr = s.get("contour") or []
                        holes = s.get("holes") or []
                        folder = s.get("folder") or ""
                        if folder and folder not in folders_list:
                            folders_list.append(folder)
                        shape_summaries.append({
                            "name": s.get("name", "Molde"),
                            "size": str(s.get("size", "41")),
                            "color": s.get("color", "#000080"),
                            "folder": folder,
                            "shape_format": s.get("shape_format", "1x1"),
                            "points_count": len(cntr),
                            "holes_count": len(holes),
                            "raw_shape": s
                        })
                folders_list.sort()

                # Prepara resumos de cada sessão de corte
                session_summaries = []
                total_layouts = 0
                if has_native_sessions:
                    try:
                        sessions_raw = json.loads(zf.read("sessions.json").decode("utf-8"))
                    except Exception:
                        sessions_raw = []

                    for sess in sessions_raw:
                        lys = sess.get("layouts", [])
                        total_layouts += len(lys)
                        session_summaries.append({
                            "id": sess.get("id"),
                            "code": sess.get("code"),
                            "name": sess.get("name", "Sessão"),
                            "job": sess.get("job", "ProduçãoNova"),
                            "status": sess.get("status", "Stand by"),
                            "layouts_count": len(lys),
                            "shapes_count": len(sess.get("shapes", [])),
                            "pieces_count": len(sess.get("placed_pieces", [])),
                            "material_id": sess.get("material_id"),
                            "raw_session": sess
                        })

                return BackupInspectionResult(
                    is_valid=True,
                    app_version=str(manifest.get("app_version", "2.0")),
                    created_at=str(manifest.get("created_at", "")),
                    total_shapes=len(shape_summaries),
                    total_folders=len(folders_list),
                    total_articles=len(articles_list),
                    total_sessions=len(session_summaries),
                    total_layouts=total_layouts,
                    has_shapes=len(shape_summaries) > 0,
                    has_sessions=len(session_summaries) > 0,
                    folders=folders_list,
                    shapes=shape_summaries,
                    sessions=session_summaries,
                    is_legacy_die_zip=False
                )

            # Cenário 2: ZIP contendo arquivos .die avulsos (backup legado ou externo)
            if die_files:
                shape_summaries = []
                folders_set = set()

                for arcname in die_files:
                    try:
                        raw_bytes = zf.read(arcname)
                        for enc in ("utf-8", "cp1252", "latin-1"):
                            try:
                                text = raw_bytes.decode(enc)
                                break
                            except UnicodeDecodeError:
                                text = ""

                        if not text:
                            continue

                        shape_data = parse_die_content(text, default_name=Path(arcname).stem)
                        # Deriva a pasta a partir da hierarquia do arquivo no ZIP
                        parts = Path(arcname).parts
                        if len(parts) > 1 and parts[0].lower() == "dies":
                            folder = "/".join(parts[1:-1])
                        elif len(parts) > 1:
                            folder = "/".join(parts[:-1])
                        else:
                            folder = ""

                        if folder:
                            folders_set.add(folder)

                        shape_data["folder"] = folder
                        shape_summaries.append({
                            "name": shape_data.get("name", Path(arcname).stem),
                            "size": str(shape_data.get("size", "41")),
                            "color": shape_data.get("color", "#000080"),
                            "folder": folder,
                            "shape_format": shape_data.get("shape_format", "1x1"),
                            "points_count": len(shape_data.get("contour") or []),
                            "holes_count": len(shape_data.get("holes") or []),
                            "raw_shape": shape_data
                        })
                    except Exception:
                        pass

                if shape_summaries:
                    folders_sorted = sorted(list(folders_set))
                    return BackupInspectionResult(
                        is_valid=True,
                        app_version="Legado / Externo (.die)",
                        created_at="",
                        total_shapes=len(shape_summaries),
                        total_folders=len(folders_sorted),
                        total_articles=0,
                        total_sessions=0,
                        total_layouts=0,
                        has_shapes=True,
                        has_sessions=False,
                        folders=folders_sorted,
                        shapes=shape_summaries,
                        sessions=[],
                        is_legacy_die_zip=True
                    )

            return BackupInspectionResult(
                is_valid=False,
                error="O arquivo ZIP não contém dados reconhecíveis de backup (shapes.json, sessions.json ou arquivos .die)."
            )

    except Exception as exc:
        return BackupInspectionResult(is_valid=False, error=f"Erro ao ler pacote de backup: {str(exc)}")


def restore_shapes_backup(
    db,
    backup_file: str | Path,
    conflict_strategy: str = "overwrite",
    target_folder: Optional[str] = None,
    restore_shapes: bool = True,
    restore_sessions: bool = True,
    session_conflict_strategy: str = "import_new_id",  # "import_new_id", "overwrite", "skip"
    target_job: Optional[str] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None
) -> RestoreResult:
    """
    Restaura os moldes e/ou sessões de corte do pacote de backup no banco de dados.

    Estratégias de conflito para moldes (quando molde de mesmo nome, tamanho e pasta já existe):
      - 'overwrite': Atualiza contorno, furos, costuras, cor e formato do molde existente.
      - 'skip': Mantém o molde atual do banco intacto e ignora o do backup.
      - 'rename': Cria novo molde com sufixo numérico (ex: molde_copia, molde_copia2).

    Estratégias de conflito para sessões de corte:
      - 'import_new_id': Cria sempre com novo ID monotônico sequencial (#189...), preservando sessões existentes.
      - 'overwrite': Atualiza a sessão e seus layouts caso o ID já exista; se não existir, insere.
      - 'skip': Pula a sessão caso o ID já exista no banco de dados.
    """
    inspection = inspect_shapes_backup(backup_file)
    if not inspection.is_valid:
        return RestoreResult(
            total_in_backup=0,
            imported_new=0,
            updated_existing=0,
            skipped=0,
            folders_created=0,
            total_sessions_in_backup=0,
            sessions_imported=0,
            sessions_updated=0,
            sessions_skipped=0,
            errors=[inspection.error or "Arquivo de backup inválido."]
        )

    do_shapes = restore_shapes and inspection.has_shapes
    do_sessions = restore_sessions and inspection.has_sessions

    shapes_list = [s["raw_shape"] for s in inspection.shapes if "raw_shape" in s] if do_shapes else []
    sessions_list = [s["raw_session"] for s in inspection.sessions if "raw_session" in s] if do_sessions else []

    total_ops = len(shapes_list) + len(sessions_list)
    current_op = 0

    imported_new = 0
    updated_existing = 0
    skipped = 0
    folders_created = 0
    errors = []

    # 1. Restauração de Moldes
    if do_shapes and shapes_list:
        existing_shapes = db.get_all_shapes() if hasattr(db, "get_all_shapes") else []

        def _make_key(name, size, folder):
            return (
                str(name or "").strip().lower(),
                str(size or "41").strip().lower(),
                str(folder or "").strip().lower()
            )

        existing_map = {}
        for s in existing_shapes:
            k = _make_key(s.get("name"), s.get("size"), s.get("folder"))
            existing_map[k] = s

        folders_to_ensure = set()
        if target_folder:
            folders_to_ensure.add(target_folder.strip())
        else:
            for f in inspection.folders:
                if f.strip():
                    folders_to_ensure.add(f.strip())
            for s in shapes_list:
                f = (s.get("folder") or "").strip()
                if f:
                    folders_to_ensure.add(f)

        if hasattr(db, "create_shape_folder"):
            for folder_name in sorted(list(folders_to_ensure)):
                try:
                    db.create_shape_folder(folder_name)
                    folders_created += 1
                except Exception:
                    pass

        for idx, shape_data in enumerate(shapes_list):
            current_op += 1
            s_name = str(shape_data.get("name", "Molde")).strip()
            s_size = str(shape_data.get("size", "41")).strip()
            s_color = shape_data.get("color")
            s_format = str(shape_data.get("shape_format", "1x1")).strip()
            s_folder = target_folder if target_folder is not None else str(shape_data.get("folder", "") or "").strip()

            contour = shape_data.get("contour") or []
            holes = shape_data.get("holes") or []
            stitching = shape_data.get("stitching") or []

            if on_progress:
                on_progress(current_op, total_ops, f"Processando molde {s_name} ({s_size})...")

            k = _make_key(s_name, s_size, s_folder)
            existing = existing_map.get(k)

            try:
                if existing:
                    if conflict_strategy == "skip":
                        skipped += 1
                        continue

                    elif conflict_strategy == "overwrite":
                        db.update_shape(
                            shape_id=existing["id"],
                            name=s_name,
                            contour=contour,
                            holes=holes,
                            stitching=stitching,
                            folder=s_folder,
                            size=s_size,
                            color=s_color,
                            shape_format=s_format
                        )
                        updated_existing += 1

                    elif conflict_strategy == "rename":
                        base_name = s_name
                        cand_name = f"{base_name}_copia"
                        suffix_num = 1
                        while _make_key(cand_name, s_size, s_folder) in existing_map:
                            suffix_num += 1
                            cand_name = f"{base_name}_copia{suffix_num}"

                        new_id = db.create_shape(
                            article_id=existing.get("article_id"),
                            name=cand_name,
                            color=s_color or "#000080",
                            contour=contour,
                            holes=holes,
                            stitching=stitching,
                            folder=s_folder,
                            size=s_size,
                            shape_format=s_format
                        )
                        existing_map[_make_key(cand_name, s_size, s_folder)] = {"id": new_id, "name": cand_name}
                        imported_new += 1
                else:
                    new_id = db.create_shape(
                        article_id=shape_data.get("article_id"),
                        name=s_name,
                        color=s_color or "#000080",
                        contour=contour,
                        holes=holes,
                        stitching=stitching,
                        folder=s_folder,
                        size=s_size,
                        shape_format=s_format
                    )
                    existing_map[k] = {"id": new_id, "name": s_name}
                    imported_new += 1

            except Exception as exc:
                errors.append(f"Molde {s_name} ({s_size}): {str(exc)}")

    # 2. Restauração de Sessões de Corte
    sessions_imported = 0
    sessions_updated = 0
    sessions_skipped = 0

    if do_sessions and sessions_list:
        # 2.1 Assegura importação de materiais para evitar erro de chave estrangeira
        try:
            with zipfile.ZipFile(backup_file, "r") as zf:
                if "materials.json" in zf.namelist():
                    mats_data = json.loads(zf.read("materials.json").decode("utf-8"))
                    with db.get_connection() as conn:
                        cur = conn.cursor()
                        for m in mats_data:
                            m_id = m.get("id")
                            if not m_id:
                                continue
                            cur.execute("SELECT id FROM materials WHERE id = ?", (m_id,))
                            if not cur.fetchone():
                                cur.execute("""
                                    INSERT INTO materials (id, name, type, width_mm, height_mm, area_m2, thickness_mm, layers, gap_mm)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    m_id, str(m.get("name") or m_id), str(m.get("type") or "como placa"),
                                    float(m.get("width_mm", 1380.0) or 1380.0), float(m.get("height_mm", 1080.0) or 1080.0),
                                    float(m.get("area_m2", 1.4904) or 1.4904), float(m.get("thickness_mm", 1.4) or 1.4),
                                    int(m.get("layers", 1) or 1), float(m.get("gap_mm", 1.0) or 1.0)
                                ))
                        conn.commit()
        except Exception as exc:
            print(f"[AVISO] Falha ao importar materiais do backup: {exc}")

        for sess_data in sessions_list:
            current_op += 1
            orig_id = sess_data.get("id")
            s_name = str(sess_data.get("name") or f"Sessão #{orig_id}").strip()
            s_job = target_job if target_job is not None else str(sess_data.get("job") or "ProduçãoNova").strip()
            s_status = str(sess_data.get("status") or "Stand by").strip()
            s_order_id = sess_data.get("order_id")
            s_mat_id = sess_data.get("material_id")
            s_pieces = sess_data.get("placed_pieces") or []
            s_shapes = sess_data.get("shapes") or []
            s_strat = str(sess_data.get("strategy") or "flashnestsheet")
            s_params = str(sess_data.get("params") or "stdNOTFill")
            s_mach = str(sess_data.get("machine") or "ATOM FlashCut Flex 3020")
            s_gap = float(sess_data.get("gap_mm", 1.0) if sess_data.get("gap_mm") is not None else 1.0)
            s_ml = float(sess_data.get("margin_left", 10.0) if sess_data.get("margin_left") is not None else 10.0)
            s_mr = float(sess_data.get("margin_right", 10.0) if sess_data.get("margin_right") is not None else 10.0)
            s_mt = float(sess_data.get("margin_top", 10.0) if sess_data.get("margin_top") is not None else 10.0)
            s_mb = float(sess_data.get("margin_bottom", 10.0) if sess_data.get("margin_bottom") is not None else 10.0)
            s_mode = str(sess_data.get("nesting_mode") or "custom")
            s_layers = int(sess_data["layers"]) if sess_data.get("layers") is not None else None
            layouts = sess_data.get("layouts") or []

            if on_progress:
                on_progress(current_op, total_ops, f"Processando sessão {s_name}...")

            try:
                # Verifica se a sessão já existe no banco
                existing_sess = None
                if orig_id is not None and hasattr(db, "get_session"):
                    existing_sess = db.get_session(orig_id)

                if session_conflict_strategy == "import_new_id":
                    new_id = db.get_next_session_number() if hasattr(db, "get_next_session_number") else None
                    assigned_id = db.create_session(
                        session_id=new_id,
                        name=s_name,
                        job=s_job,
                        order_id=s_order_id,
                        material_id=s_mat_id,
                        status=s_status,
                        placed_pieces=s_pieces,
                        strategy=s_strat,
                        params=s_params,
                        machine=s_mach,
                        shapes=s_shapes,
                        gap_mm=s_gap,
                        margin_left=s_ml,
                        margin_right=s_mr,
                        margin_top=s_mt,
                        margin_bottom=s_mb,
                        nesting_mode=s_mode,
                        layers=s_layers
                    )
                    if layouts and hasattr(db, "save_session_layouts"):
                        db.save_session_layouts(assigned_id, layouts)
                    sessions_imported += 1

                elif session_conflict_strategy == "skip":
                    if existing_sess:
                        sessions_skipped += 1
                        continue
                    else:
                        assigned_id = db.create_session(
                            session_id=orig_id,
                            name=s_name,
                            job=s_job,
                            order_id=s_order_id,
                            material_id=s_mat_id,
                            status=s_status,
                            placed_pieces=s_pieces,
                            strategy=s_strat,
                            params=s_params,
                            machine=s_mach,
                            shapes=s_shapes,
                            gap_mm=s_gap,
                            margin_left=s_ml,
                            margin_right=s_mr,
                            margin_top=s_mt,
                            margin_bottom=s_mb,
                            nesting_mode=s_mode,
                            layers=s_layers
                        )
                        if layouts and hasattr(db, "save_session_layouts"):
                            db.save_session_layouts(assigned_id, layouts)
                        sessions_imported += 1

                elif session_conflict_strategy == "overwrite":
                    assigned_id = db.create_session(
                        session_id=orig_id,
                        name=s_name,
                        job=s_job,
                        order_id=s_order_id,
                        material_id=s_mat_id,
                        status=s_status,
                        placed_pieces=s_pieces,
                        strategy=s_strat,
                        params=s_params,
                        machine=s_mach,
                        shapes=s_shapes,
                        gap_mm=s_gap,
                        margin_left=s_ml,
                        margin_right=s_mr,
                        margin_top=s_mt,
                        margin_bottom=s_mb,
                        nesting_mode=s_mode,
                        layers=s_layers
                    )
                    if layouts and hasattr(db, "save_session_layouts"):
                        db.save_session_layouts(assigned_id, layouts)
                    if existing_sess:
                        sessions_updated += 1
                    else:
                        sessions_imported += 1

            except Exception as exc:
                errors.append(f"Sessão {s_name} (ID {orig_id}): {str(exc)}")

    if on_progress:
        on_progress(total_ops, total_ops, "Restauração concluída com sucesso!")

    return RestoreResult(
        total_in_backup=len(shapes_list),
        imported_new=imported_new,
        updated_existing=updated_existing,
        skipped=skipped,
        folders_created=folders_created,
        total_sessions_in_backup=len(sessions_list),
        sessions_imported=sessions_imported,
        sessions_updated=sessions_updated,
        sessions_skipped=sessions_skipped,
        errors=errors
    )
