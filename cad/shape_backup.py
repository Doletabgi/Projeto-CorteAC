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


@dataclass
class BackupInspectionResult:
    is_valid: bool
    app_version: str = ""
    created_at: str = ""
    total_shapes: int = 0
    total_folders: int = 0
    total_articles: int = 0
    folders: List[str] = field(default_factory=list)
    shapes: List[Dict[str, Any]] = field(default_factory=list)
    is_legacy_die_zip: bool = False
    error: Optional[str] = None


@dataclass
class RestoreResult:
    total_in_backup: int
    imported_new: int
    updated_existing: int
    skipped: int
    folders_created: int
    errors: List[str] = field(default_factory=list)


def create_shapes_backup(
    db,
    target_file: str | Path,
    folder_filter: Optional[List[str]] = None,
    include_die_files: bool = True,
    on_progress: Optional[Callable[[int, int, str], None]] = None
) -> BackupSummary:
    """
    Gera um pacote de backup compactado (.zip ou .csh) contendo todos os moldes
    cadastrados (ou os pertencentes às pastas especificadas em folder_filter).
    
    Estrutura do arquivo ZIP:
      - manifest.json: Metadados do backup (data/hora, versão, contagens)
      - shapes.json: Lista estruturada completa de geometrias, furos e formatos
      - folders.json: Pastas de moldes cadastradas
      - articles.json: Artigos e pares associados
      - dies/<pasta>/<nome>.die: Arquivos .die individuais ATOM FlashCut (se include_die_files=True)
    """
    target_path = Path(target_file)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Obter todos os moldes do banco de dados
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

    # Garante que qualquer pasta referenciada nos moldes exportados esteja incluída
    for s in shapes_to_backup:
        f = (s.get("folder") or "").strip()
        if f and f not in folders_to_backup:
            folders_to_backup.append(f)
    folders_to_backup.sort()

    # 3. Mapear artigos
    article_ids = {s.get("article_id") for s in shapes_to_backup if s.get("article_id")}
    articles_to_backup = []
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

    created_iso = datetime.now().isoformat(timespec="seconds")

    # 4. Preparar lista canônica de moldes
    clean_shapes = []
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

    # 5. Criar arquivo ZIP
    total_steps = len(clean_shapes) + 4
    current_step = 0

    if on_progress:
        on_progress(current_step, total_steps, "Inicializando arquivo de backup...")

    manifest_data = {
        "app": APP_NAME,
        "app_version": APP_VERSION,
        "format_version": "1.0",
        "created_at": created_iso,
        "total_shapes": len(clean_shapes),
        "total_folders": len(folders_to_backup),
        "total_articles": len(articles_to_backup),
        "description": "Backup completo de moldes cadastrados no CorteAC"
    }

    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Grava metadados
        zf.writestr("manifest.json", json.dumps(manifest_data, indent=2, ensure_ascii=False))
        current_step += 1
        if on_progress:
            on_progress(current_step, total_steps, "Gravando metadados...")

        # Grava moldes em JSON canônico
        zf.writestr("shapes.json", json.dumps(clean_shapes, indent=2, ensure_ascii=False))
        current_step += 1
        if on_progress:
            on_progress(current_step, total_steps, "Gravando geometrias de moldes...")

        # Grava pastas
        zf.writestr("folders.json", json.dumps(folders_to_backup, indent=2, ensure_ascii=False))
        current_step += 1
        if on_progress:
            on_progress(current_step, total_steps, "Gravando catálogo de pastas...")

        # Grava artigos
        zf.writestr("articles.json", json.dumps(articles_to_backup, indent=2, ensure_ascii=False))
        current_step += 1
        if on_progress:
            on_progress(current_step, total_steps, "Gravando artigos...")

        # Grava arquivos individuais .die (opcional, para compatibilidade ATOM)
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
                    # Falha na serialização .die individual não interrompe o backup canônico
                    pass

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
        included_dies=include_die_files
    )


def inspect_shapes_backup(backup_file: str | Path) -> BackupInspectionResult:
    """
    Inspeciona um arquivo de backup (.zip/.csh) sem aplicar alterações no banco de dados.
    Valida a assinatura, extrai estatísticas, lista de moldes e pastas.
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

            # Cenário 1: Pacote de backup nativo do CorteAC (manifest.json + shapes.json)
            if "manifest.json" in namelist and "shapes.json" in namelist:
                try:
                    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                except Exception:
                    manifest = {}

                shapes_raw = json.loads(zf.read("shapes.json").decode("utf-8"))

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
                return BackupInspectionResult(
                    is_valid=True,
                    app_version=str(manifest.get("app_version", "1.x")),
                    created_at=str(manifest.get("created_at", "")),
                    total_shapes=len(shape_summaries),
                    total_folders=len(folders_list),
                    total_articles=len(articles_list),
                    folders=folders_list,
                    shapes=shape_summaries,
                    is_legacy_die_zip=False
                )

            # Cenário 2: ZIP contendo arquivos .die avulsos (backup legado ou externo)
            die_files = [n for n in namelist if n.lower().endswith(".die") and not n.startswith("__MACOSX")]
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
                        folders=folders_sorted,
                        shapes=shape_summaries,
                        is_legacy_die_zip=True
                    )

            return BackupInspectionResult(
                is_valid=False,
                error="O arquivo ZIP não contém dados reconhecíveis de moldes (shapes.json ou arquivos .die)."
            )

    except Exception as exc:
        return BackupInspectionResult(is_valid=False, error=f"Erro ao ler pacote de backup: {str(exc)}")


def restore_shapes_backup(
    db,
    backup_file: str | Path,
    conflict_strategy: str = "overwrite",
    target_folder: Optional[str] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None
) -> RestoreResult:
    """
    Restaura os moldes do pacote de backup no banco de dados.

    Estratégias de conflito (quando molde de mesmo nome, tamanho e pasta já existe):
      - 'overwrite': Atualiza contorno, furos, costuras, cor e formato do molde existente.
      - 'skip': Mantém o molde atual do banco intacto e ignora o do backup.
      - 'rename': Cria novo molde com sufixo numérico (ex: molde_copia, molde_copia2).

    Se target_folder for especificado, força todos os moldes a serem restaurados nessa pasta.
    Caso contrário, preserva as pastas originais gravadas no backup.
    """
    inspection = inspect_shapes_backup(backup_file)
    if not inspection.is_valid:
        return RestoreResult(
            total_in_backup=0,
            imported_new=0,
            updated_existing=0,
            skipped=0,
            folders_created=0,
            errors=[inspection.error or "Arquivo de backup inválido."]
        )

    shapes_list = [s["raw_shape"] for s in inspection.shapes if "raw_shape" in s]
    total_shapes = len(shapes_list)

    # 1. Mapeia moldes existentes no banco de dados para identificação de conflitos
    existing_shapes = db.get_all_shapes() if hasattr(db, "get_all_shapes") else []

    # Chave de unicidade lógica: (nome_normalizado, tamanho_normalizado, pasta_normalizada)
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

    # 2. Assegura criação de todas as pastas necessárias
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

    folders_created = 0
    if hasattr(db, "create_shape_folder"):
        for folder_name in sorted(list(folders_to_ensure)):
            try:
                db.create_shape_folder(folder_name)
                folders_created += 1
            except Exception:
                pass

    # 3. Execução da restauração molde a molde
    imported_new = 0
    updated_existing = 0
    skipped = 0
    errors = []

    for idx, shape_data in enumerate(shapes_list):
        s_name = str(shape_data.get("name", "Molde")).strip()
        s_size = str(shape_data.get("size", "41")).strip()
        s_color = shape_data.get("color")
        s_format = str(shape_data.get("shape_format", "1x1")).strip()
        s_folder = target_folder if target_folder is not None else str(shape_data.get("folder", "") or "").strip()

        contour = shape_data.get("contour") or []
        holes = shape_data.get("holes") or []
        stitching = shape_data.get("stitching") or []

        if on_progress:
            on_progress(idx + 1, total_shapes, f"Processando molde {s_name} ({s_size})...")

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
                    # Gera um novo nome livre de colisão
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
                    # Registra no mapa local para evitar colisão com próximos moldes do mesmo lote
                    existing_map[_make_key(cand_name, s_size, s_folder)] = {"id": new_id, "name": cand_name}
                    imported_new += 1
            else:
                # Molde novo que ainda não existe no sistema
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
            errors.append(f"{s_name} ({s_size}): {str(exc)}")

    if on_progress:
        on_progress(total_shapes, total_shapes, "Restauração de moldes concluída!")

    return RestoreResult(
        total_in_backup=total_shapes,
        imported_new=imported_new,
        updated_existing=updated_existing,
        skipped=skipped,
        folders_created=folders_created,
        errors=errors
    )
