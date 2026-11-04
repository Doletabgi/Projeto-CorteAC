"""
CorteAC - Exportação de Sessão Multi-Placa para a Máquina ATOM.

Este módulo é independente da interface Tkinter. Ele recebe uma sessão do banco
(SQLite/MySQL), monta uma pasta de entrega com TODOS os layouts da sessão
(lay0000.lay, lay0001.lay, ...) e copia para ``Shapes/`` apenas os moldes
realmente referenciados por esses layouts.

Estratégia de resolução dos moldes, em ordem:

1. ``source_path``/``die_path`` gravado no molde (quando existir);
2. ``dLib + dCode`` gravado no molde (quando existir);
3. índice de arquivos ``.die`` informado pelo operador (``--shapes-root``);
4. geração a partir de ``contour``/``holes``/``stitching`` do banco.

O passo 4 é lossy: o gerador atual do CorteAC não preserva o fio
(``directionFrom``/``directionTo``) nem a zona de qualidade original. Por isso
o manifesto grava ``source: "db"`` e um aviso explícito. O ideal é sempre
encontrar o ``.die`` original.

Formato da pasta gerada::

    <destino>/<session_code>/
        manifest.json
        lay0000.lay
        lay0001.lay
        Shapes/
            <dCode>

O ``.cac`` é apenas um ZIP opcional dessa pasta (para e-mail/arquivo).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from cad.die_parser import clean_shape_name, generate_die_content
from cad.lay_parser import export_layout_from_pieces

try:  # import tardio para não quebrar ferramentas que só usam o packager
    from config import APP_VERSION
except Exception:  # pragma: no cover - ambiente mínimo
    APP_VERSION = "desconhecida"


CAC_FORMAT = "corteac.session.v1"
SHAPES_DIRNAME = "Shapes"
MANIFEST_NAME = "manifest.json"


class PackagingError(Exception):
    """Erro de empacotamento/exportação de sessão."""


class MissingDiesError(PackagingError):
    """Um ou mais moldes referenciados não puderam ser resolvidos."""

    def __init__(self, missing: Sequence[dict]):
        self.missing = list(missing)
        names = ", ".join(str(m.get("name") or "?") for m in self.missing[:8])
        if len(self.missing) > 8:
            names += f" ... (+{len(self.missing) - 8})"
        super().__init__(f"Moldes ausentes ({len(self.missing)}): {names}")


@dataclass
class DieAsset:
    """Um molde resolvido, pronto para ir para ``Shapes/`` ou para o manifesto."""

    name: str
    code: str
    filename: str
    data: bytes
    source: str  # "file" | "db"
    original_path: str = ""
    warning: str = ""
    copied: bool = True

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    @property
    def size(self) -> int:
        return len(self.data)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "code": self.code,
            "file": f"{SHAPES_DIRNAME}/{self.filename}" if self.copied else None,
            "source": self.source,
            "original_path": self.original_path,
            "sha256": self.sha256,
            "bytes": self.size,
            "warning": self.warning,
        }


@dataclass
class LayoutAsset:
    """Um layout (placa) exportado."""

    index: int
    filename: str
    path: str
    num_items: int
    width_mm: float
    height_mm: float

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "file": self.filename,
            "path": self.path,
            "num_items": self.num_items,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
        }


@dataclass
class ExportResult:
    """Resultado completo de uma exportação de sessão."""

    session_id: int
    session_code: str
    target_dir: Path
    session_dir: Path
    shapes_dir: Optional[Path]
    layouts: list[LayoutAsset] = field(default_factory=list)
    dies: list[DieAsset] = field(default_factory=list)
    missing: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    elapsed_sec: float = 0.0
    manifest_path: Optional[Path] = None
    cac_path: Optional[Path] = None

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def success(self) -> bool:
        return bool(self.layouts)

    def to_dict(self) -> dict:
        return {
            "format": CAC_FORMAT,
            "session_id": self.session_id,
            "session_code": self.session_code,
            "target_dir": str(self.target_dir),
            "session_dir": str(self.session_dir),
            "shapes_dir": str(self.shapes_dir) if self.shapes_dir else None,
            "manifest": str(self.manifest_path) if self.manifest_path else None,
            "cac": str(self.cac_path) if self.cac_path else None,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "complete": self.complete,
            "layouts": [l.to_dict() for l in self.layouts],
            "dies": [d.to_dict() for d in self.dies],
            "missing": list(self.missing),
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _as_list(value: Any) -> list:
    """Aceita lista ou string JSON e devolve sempre uma lista."""
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []
    return value if isinstance(value, list) else []


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _safe_component(value: Any, fallback: str = "sessao") -> str:
    """Sanitiza um nome para uso como pasta (Windows + Linux)."""
    s = str(value or "").strip()
    s = s.replace("\\", "/").split("/")[-1]
    s = re.sub(r'[<>:"|?*]', "_", s)
    s = s.strip(" .")
    if not s:
        s = fallback
    if s.split(".")[0].upper() in _WINDOWS_RESERVED:
        s = f"_{s}"
    return s[:120]


def _safe_filename(value: Any, suffix: str, fallback: str) -> str:
    """Sanitiza um nome de arquivo e garante a extensão desejada."""
    s = str(value or "").strip()
    s = s.replace("\\", "/").split("/")[-1]
    s = re.sub(r'[<>:"|?*]', "_", s)
    s = s.strip(" .")
    if not s:
        s = fallback
    low = s.lower()
    if not low.endswith(suffix.lower()):
        # remove extensão antiga diferente, ex.: "foo.die" com suffix ".lay"
        if "." in s:
            s = s.rsplit(".", 1)[0]
        s += suffix
    if s.split(".")[0].upper() in _WINDOWS_RESERVED:
        s = f"_{s}"
    if len(s) > 120:
        stem, ext = os.path.splitext(s)
        digest = hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()[:8]
        s = f"{stem[:100]}_{digest}{ext}"
    return s


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _write_json_atomic(path: Path, payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _write_bytes_atomic(path, text.encode("utf-8"))


def _die_code(name: str) -> str:
    n = str(name or "").strip()
    # Mesma regra de export_layout_from_pieces (case-sensitive).
    if n.endswith(".die"):
        return n
    return f"{n}.die"


def _is_die_file(path: Path) -> bool:
    return path.suffix.lower() == ".die"


def _resolve_sidecar(path: Path) -> Optional[Path]:
    """Se vier um .d, procura o .die irmão; caso contrário exige .die."""
    if path.suffix.lower() == ".d":
        for ext in (".die", ".Die", ".DIE"):
            cand = path.with_suffix(ext)
            if cand.is_file():
                return cand
        return None
    if _is_die_file(path) and path.is_file():
        return path
    return None


def _existing_die_path(raw: Any, code: str = "") -> Optional[Path]:
    if not raw:
        return None
    try:
        p = Path(str(raw)).expanduser()
        if p.is_dir():
            p = p / code
        return _resolve_sidecar(p)
    except (OSError, ValueError):
        return None


class DieSourceIndex:
    """Índice nome-do-arquivo -> caminho, opcional, para achar .die na rede."""

    def __init__(self, roots: Optional[Sequence[str]] = None):
        self._by_name: dict[str, list[Path]] = {}
        self.roots: list[Path] = []
        for root in roots or []:
            self.add_root(root)

    @property
    def count(self) -> int:
        return sum(len(paths) for paths in self._by_name.values())

    def add_root(self, root: str | Path) -> int:
        p = Path(str(root)).expanduser()
        if not p.exists():
            return 0
        if p.is_file():
            if p.suffix.lower() in (".die", ".d"):
                self._by_name.setdefault(p.name.lower(), []).append(p)
                return 1
            return 0
        self.roots.append(p)
        found = 0
        for dirpath, _dirnames, filenames in os.walk(p):
            base = Path(dirpath)
            for fn in filenames:
                if fn.lower().endswith((".die", ".d")):
                    self._by_name.setdefault(fn.lower(), []).append(base / fn)
                    found += 1
        return found

    def find(self, code: str) -> Optional[Path]:
        key = Path(str(code).replace("\\", "/")).name.lower()
        for path in self._by_name.get(key, []):
            resolved = _resolve_sidecar(path)
            if resolved is not None:
                return resolved
        return None


# ---------------------------------------------------------------------------
# Normalização de peças/moldes
# ---------------------------------------------------------------------------

def _normalize_shape(raw: Any, fallback_name: str) -> dict:
    data = dict(raw) if isinstance(raw, dict) else {}
    contour = _as_list(data.get("contour")) or _as_list(data.get("contour_json"))
    holes = _as_list(data.get("holes")) or _as_list(data.get("holes_json"))
    stitching = _as_list(data.get("stitching")) or _as_list(data.get("stitching_json"))
    name = clean_shape_name(str(data.get("name") or fallback_name or "Molde"))
    return {
        "name": name,
        "contour": contour,
        "holes": holes,
        "stitching": stitching,
        "size": str(data.get("size") or "41"),
        "quality_zone": _as_int(data.get("quality_zone") or data.get("def_quality"), 1),
        "source_path": data.get("source_path") or data.get("die_path") or "",
        "dlib": data.get("dlib") or data.get("source_dlib") or "",
        "original_code": data.get("dcode") or data.get("original_code") or "",
        "raw": data,
    }


def _normalize_piece(raw: Any, index: int) -> dict:
    piece = raw if isinstance(raw, dict) else {}
    shape_raw = piece.get("shape") if isinstance(piece.get("shape"), dict) else {}
    name = str(piece.get("name") or shape_raw.get("name") or f"Molde_{index}")
    contour = _as_list(piece.get("contour")) or _as_list(shape_raw.get("contour")) or _as_list(shape_raw.get("contour_json"))
    holes = _as_list(piece.get("holes")) or _as_list(shape_raw.get("holes")) or _as_list(shape_raw.get("holes_json"))
    stitching = _as_list(piece.get("stitching")) or _as_list(shape_raw.get("stitching")) or _as_list(shape_raw.get("stitching_json"))
    rotation = piece.get("rotation", piece.get("rot_deg", piece.get("rotation_deg", 0.0)))
    # Peças de layout_pieces/placed_pieces trazem a geometria no nível de cima,
    # não dentro de "shape". O packager precisa enxergar as duas formas.
    merged_shape = dict(shape_raw)
    if contour and not _as_list(merged_shape.get("contour")):
        merged_shape["contour"] = contour
    if holes and not merged_shape.get("holes"):
        merged_shape["holes"] = holes
    if stitching and not merged_shape.get("stitching"):
        merged_shape["stitching"] = stitching
    if name and not merged_shape.get("name"):
        merged_shape["name"] = name
    if piece.get("size") and not merged_shape.get("size"):
        merged_shape["size"] = piece.get("size")
    for meta_key in ("source_path", "die_path", "dlib", "source_dlib", "original_code", "quality_zone"):
        if piece.get(meta_key) is not None and merged_shape.get(meta_key) in (None, ""):
            merged_shape[meta_key] = piece.get(meta_key)
    return {
        "id": piece.get("id", index + 1),
        "target_id": piece.get("target_id") or shape_raw.get("id") or (index + 1),
        "name": name,
        "size": str(piece.get("size") or shape_raw.get("size") or "41"),
        "color": piece.get("color") or shape_raw.get("color") or "#2563eb",
        "x": _as_float(piece.get("x", 0.0)),
        "y": _as_float(piece.get("y", 0.0)),
        "rotation": _as_float(rotation),
        "is_mirrored": bool(piece.get("is_mirrored", piece.get("mirrored", False))),
        "contour": contour,
        "holes": holes,
        "stitching": stitching,
        "quality_zone": _as_int(piece.get("quality_zone") or shape_raw.get("quality_zone"), 1),
        "shape_raw": merged_shape,
    }


def _normalize_layout(raw: Any, index: int) -> dict:
    layout = raw if isinstance(raw, dict) else {}
    pieces_raw = layout.get("pieces") or layout.get("placed_pieces") or []
    pieces = [_normalize_piece(p, i) for i, p in enumerate(pieces_raw)]
    l_index = int(layout.get("layout_index", index) if layout.get("layout_index") is not None else index)
    return {
        "index": l_index,
        "code": str(layout.get("code") or layout.get("name") or f"lay{l_index:04d}"),
        "name": str(layout.get("name") or layout.get("code") or f"lay{l_index:04d}"),
        "pieces": pieces,
        "width_mm": _as_float(layout.get("width_mm") or layout.get("ris_w"), 1380.0),
        "height_mm": _as_float(layout.get("height_mm") or layout.get("ris_l"), 1080.0),
        "gap_mm": _as_float(layout.get("gap_mm"), 1.0),
        "layers": layout.get("layers"),
        "layers_tip": layout.get("layers_tip"),
        "tip_zone": layout.get("tip_zone"),
        "yield_percent": _as_float(layout.get("yield_percent") or layout.get("yield_pct"), 0.0),
        "material_code": str(layout.get("material_code") or ""),
        "material_name": str(layout.get("material_name") or ""),
    }


def _shape_has_geometry(shape: dict) -> bool:
    return bool(shape and len(shape.get("contour") or []) >= 3)


def _select_shape(
    name: str,
    size: str,
    piece_shape: dict,
    db_by_name: dict[str, list[dict]],
) -> dict:
    key = clean_shape_name(str(name)).lower()
    candidates = db_by_name.get(key) or []
    chosen: dict = {}
    if candidates:
        same_size = [s for s in candidates if str(s.get("size") or "") == str(size)]
        chosen = dict(same_size[0] if same_size else candidates[0])
    if piece_shape:
        # A geometria que veio montada no layout é mais atual que o banco,
        # mas não pode sobrescrever uma geometria válida com lista vazia.
        for key, value in piece_shape.items():
            if key in ("contour", "holes", "stitching", "contour_json", "holes_json", "stitching_json") and not value:
                continue
            chosen[key] = value
    normalized = _normalize_shape(chosen, fallback_name=name)
    normalized["size"] = str(size or normalized.get("size") or "41")
    return normalized


def _find_die_in_index(index: Optional[DieSourceIndex], code: str, name: str) -> Optional[Path]:
    if index is None:
        return None
    for candidate in (code, f"{name}.die", _safe_filename(code, ".die", f"{name}.die")):
        found = index.find(candidate)
        if found is not None:
            return found
    return None


def _resolve_die(
    name: str,
    code: str,
    shape: dict,
    index: Optional[DieSourceIndex],
    used_filenames: set[str],
) -> tuple[Optional[DieAsset], Optional[dict]]:
    """Resolve um molde em arquivo original, índice ou banco."""
    original_code = str(shape.get("original_code") or code)
    candidates: list[Any] = []
    if shape.get("source_path"):
        candidates.append(shape["source_path"])
    if shape.get("dlib"):
        candidates.append(Path(str(shape["dlib"])) / original_code)
    if shape.get("raw"):
        raw = shape["raw"]
        for key in ("source_path", "die_path", "path"):
            if raw.get(key):
                candidates.append(raw[key])
        if raw.get("dlib"):
            candidates.append(Path(str(raw["dlib"])) / original_code)

    source_path: Optional[Path] = None
    for candidate in candidates:
        source_path = _existing_die_path(candidate, original_code)
        if source_path is not None:
            break
    if source_path is None:
        source_path = _find_die_in_index(index, original_code, name)

    if source_path is not None:
        try:
            data = source_path.read_bytes()
        except OSError as exc:
            return None, {
                "name": name,
                "code": code,
                "reason": f"Falha ao ler {source_path}: {exc}",
            }
        stored = _safe_filename(code, ".die", f"{name}.die")
        stored = _dedupe_filename(stored, used_filenames)
        return DieAsset(
            name=name,
            code=code,
            filename=stored,
            data=data,
            source="file",
            original_path=str(source_path),
        ), None

    if _shape_has_geometry(shape):
        die_data = {
            "name": name,
            "contour": shape.get("contour") or [],
            "holes": shape.get("holes") or [],
            "stitching": shape.get("stitching") or [],
            "size": shape.get("size") or "41",
            "quality_zone": shape.get("quality_zone") or 1,
        }
        try:
            payload = generate_die_content(die_data).encode("latin1", "replace")
        except Exception as exc:
            return None, {
                "name": name,
                "code": code,
                "reason": f"Falha ao gerar .die a partir do banco: {exc}",
            }
        stored = _safe_filename(code, ".die", f"{name}.die")
        stored = _dedupe_filename(stored, used_filenames)
        return DieAsset(
            name=name,
            code=code,
            filename=stored,
            data=payload,
            source="db",
            warning=(
                "Molde gerado a partir do contorno do banco: fio/direção e "
                "zona de qualidade originais podem ter sido perdidos."
            ),
        ), None

    return None, {
        "name": name,
        "code": code,
        "reason": "Sem arquivo .die de origem e sem contorno no banco.",
    }


def _dedupe_filename(filename: str, used: set[str]) -> str:
    lower = filename.lower()
    if lower not in used:
        used.add(lower)
        return filename
    stem, ext = os.path.splitext(filename)
    digest = hashlib.sha1(filename.encode("utf-8", "replace")).hexdigest()[:8]
    candidate = f"{stem}_{digest}{ext}"
    n = 2
    while candidate.lower() in used:
        candidate = f"{stem}_{digest}_{n}{ext}"
        n += 1
    used.add(candidate.lower())
    return candidate


# ---------------------------------------------------------------------------
# Geração do .lay
# ---------------------------------------------------------------------------

def _build_lay_content(
    layout: dict,
    session: dict,
    session_dir: Path,
    filename: str,
    shapes_dir: Optional[Path],
    dlib_override: Optional[str],
    code_map: dict[str, str],
) -> str:
    material = {
        "width_mm": layout["width_mm"],
        "height_mm": layout["height_mm"],
        "gap_mm": layout["gap_mm"],
        "id": layout.get("material_code") or session.get("material_id") or "884412",
        "name": layout.get("material_name") or session.get("material_name") or "",
        "layers": layout.get("layers"),
    }
    content = export_layout_from_pieces(
        placed_pieces=layout["pieces"],
        material=material,
        session_id=session.get("id"),
        filename=filename,
        path=str(session_dir),
        layers=layout.get("layers"),
        tip_zone=layout.get("tip_zone"),
        layers_tip=layout.get("layers_tip"),
    )

    target_lib = ""
    if shapes_dir is not None:
        target_lib = str(shapes_dir)
    elif dlib_override:
        target_lib = str(dlib_override)

    out: list[str] = []
    for line in content.splitlines():
        if line.startswith("dLib=") and target_lib:
            out.append(f"dLib={target_lib}")
        elif line.startswith("dCode="):
            code = line.split("=", 1)[1].strip()
            mapped = code_map.get(code) or code_map.get(code.lower()) or code
            out.append(f"dCode={mapped}")
        else:
            out.append(line)
    return "\r\n".join(out) + "\r\n"


def _layout_filename(layout: dict, used: set[str]) -> str:
    base = _safe_filename(layout.get("code") or layout.get("name"), ".lay", f"lay{layout['index']:04d}.lay")
    if base.lower() not in used:
        used.add(base.lower())
        return base
    stem, ext = os.path.splitext(base)
    n = 2
    candidate = f"{stem}_{n}{ext}"
    while candidate.lower() in used:
        n += 1
        candidate = f"{stem}_{n}{ext}"
    used.add(candidate.lower())
    return candidate


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------

def export_session(
    db: Any,
    session_id: int,
    target_dir: str | Path,
    *,
    create_subfolder: bool = True,
    copy_dies: bool = True,
    dlib_override: Optional[str] = None,
    shapes_search_roots: Optional[Sequence[str]] = None,
    shape_catalog: Optional[Sequence[dict]] = None,
    die_index: Optional[DieSourceIndex] = None,
    strict: bool = False,
    clean_existing_layouts: bool = True,
    progress: Optional[Callable[[str, int, int], None]] = None,
) -> ExportResult:
    """
    Exporta TODOS os layouts de uma sessão para uma pasta pronta para a máquina.

    Parâmetros
    ----------
    db:
        Instância de ``database.Database`` ou objeto com ``get_session``,
        ``get_all_shapes`` e ``get_session_shapes``.
    session_id:
        ID da sessão.
    target_dir:
        Pasta escolhida pelo operador (rede ou pendrive). Se
        ``create_subfolder`` for True, a sessão é gravada em
        ``target_dir/<session_code>``.
    copy_dies:
        True (padrão): copia apenas os ``.die`` referenciados para
        ``Shapes/`` e reescreve o ``dLib`` de cada TG.
        False: modo referência; não copia e deixa o ``dLib`` original/override.
    dlib_override:
        Usado quando ``copy_dies=False`` para apontar para uma biblioteca
        existente.
    shapes_search_roots:
        Pastas onde procurar os ``.die`` originais por nome de arquivo.
        Útil para ``\\\\lab-inf\\NSDATAV1\\Shapes``. Para lotes, prefira passar
        um ``die_index`` já construído para não reescanear a rede a cada sessão.
    shape_catalog:
        Lista de moldes já carregada (opcional). Evita um ``get_all_shapes()``
        por sessão em lotes de 1000/dia.
    die_index:
        Índice ``DieSourceIndex`` reutilizável (opcional).
    strict:
        Se True, levanta ``MissingDiesError`` quando algum molde não é
        resolvido. Se False, grava o que existe e lista os ausentes.
    """
    t0 = time.perf_counter()
    if db is None:
        raise PackagingError("Banco de dados não informado.")
    if not hasattr(db, "get_session"):
        raise PackagingError("O banco informado não implementa get_session().")

    session = db.get_session(int(session_id))
    if not session:
        raise PackagingError(f"Sessão #{session_id} não encontrada.")

    layouts_raw = session.get("layouts") or []
    if not layouts_raw and hasattr(db, "get_session_layouts"):
        try:
            layouts_raw = db.get_session_layouts(int(session_id)) or []
        except Exception:
            layouts_raw = []
    if not layouts_raw and session.get("placed_pieces"):
        layouts_raw = [{
            "layout_index": 0,
            "code": "lay0000",
            "name": "lay0000",
            "pieces": session.get("placed_pieces") or [],
            "width_mm": session.get("sheet_width", 1380.0),
            "height_mm": session.get("sheet_height", 1080.0),
            "gap_mm": session.get("gap_mm", 1.0),
        }]
    if not layouts_raw:
        raise PackagingError(f"Sessão #{session_id} não possui layouts para exportar.")

    layouts = [_normalize_layout(l, i) for i, l in enumerate(layouts_raw)]
    layouts.sort(key=lambda l: (l["index"], l["code"].lower()))

    target = Path(str(target_dir)).expanduser()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PackagingError(f"Não foi possível criar a pasta de destino {target}: {exc}") from exc
    # os.path.abspath evita o prefixo \\?\ de Path.resolve() em UNC no Windows.
    target = Path(os.path.abspath(str(target)))

    session_code = str(session.get("code") or f"SESS-{session_id}")
    session_dir = target / _safe_component(session_code, f"SESS-{session_id}") if create_subfolder else target
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PackagingError(f"Não foi possível criar a pasta da sessão {session_dir}: {exc}") from exc

    shapes_dir: Optional[Path] = None
    if copy_dies:
        shapes_dir = session_dir / SHAPES_DIRNAME
        try:
            shapes_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PackagingError(f"Não foi possível criar a pasta Shapes: {exc}") from exc

    warnings: list[str] = []
    if not copy_dies and not dlib_override:
        warnings.append(
            "copy_dies=False sem dlib_override: o .lay manterá o dLib gerado "
            "pelo CorteAC (raiz da biblioteca), o que pode não encontrar os moldes."
        )

    # Moldes do banco e da própria sessão (a sessão pode ter geometria mais nova).
    db_shapes: list[dict] = []
    try:
        if shape_catalog is not None:
            db_shapes = list(shape_catalog)
        elif hasattr(db, "get_all_shapes"):
            db_shapes = db.get_all_shapes() or []
    except Exception as exc:
        warnings.append(f"Não foi possível carregar todos os moldes do banco: {exc}")
    session_shapes: list[dict] = []
    try:
        if isinstance(session.get("shapes"), list) and session["shapes"]:
            session_shapes = session["shapes"]
        elif hasattr(db, "get_session_shapes"):
            session_shapes = db.get_session_shapes(int(session_id)) or []
    except Exception:
        session_shapes = []

    db_by_name: dict[str, list[dict]] = {}
    for shape in list(db_shapes) + list(session_shapes):
        if not isinstance(shape, dict):
            continue
        key = clean_shape_name(str(shape.get("name") or "")).lower()
        if key:
            db_by_name.setdefault(key, []).append(shape)

    # Coleta os nomes distintos de moldes (ordem estável).
    unique_pieces: dict[str, dict] = {}
    for layout in layouts:
        for piece in layout["pieces"]:
            name = str(piece.get("name") or "").strip()
            if not name:
                continue
            existing = unique_pieces.get(name)
            if existing is None:
                unique_pieces[name] = piece
            elif not _shape_has_geometry(_normalize_shape(existing.get("shape_raw"), name)) and \
                    _shape_has_geometry(_normalize_shape(piece.get("shape_raw"), name)):
                unique_pieces[name] = piece

    index = die_index
    if index is None and shapes_search_roots:
        index = DieSourceIndex(shapes_search_roots)
    if index is not None and index.count:
        warnings.append(f"Índice de moldes: {index.count} arquivo(s) .die/.d encontrados.")

    used_die_names: set[str] = set()
    dies: list[DieAsset] = []
    missing: list[dict] = []
    code_map: dict[str, str] = {}

    if copy_dies:
        total_dies = len(unique_pieces)
        for pos, (name, piece) in enumerate(unique_pieces.items(), start=1):
            if progress:
                try:
                    progress("dies", pos, total_dies)
                except Exception:
                    pass
            code = _die_code(name)
            shape = _select_shape(name, str(piece.get("size") or "41"), piece.get("shape_raw") or {}, db_by_name)
            asset, miss = _resolve_die(name, code, shape, index, used_die_names)
            if asset is not None:
                dies.append(asset)
                code_map[code] = asset.filename
                code_map[code.lower()] = asset.filename
                if asset.warning:
                    warnings.append(f"{name}: {asset.warning}")
            else:
                missing.append(miss or {"name": name, "code": code, "reason": "Molde não encontrado."})
    else:
        warnings.append("Modo referência: os .die não foram copiados nem gerados; o dLib deve apontar para a biblioteca existente.")

    if strict and missing:
        raise MissingDiesError(missing)

    # Escreve os moldes antes dos layouts: se algo falhar, o .lay não aponta
    # para uma pasta Shapes incompleta.
    if copy_dies and shapes_dir is not None:
        for asset in dies:
            _write_bytes_atomic(shapes_dir / asset.filename, asset.data)

    # Prepara todo o conteúdo antes de apagar qualquer .lay antigo.
    prepared: list[tuple[str, str, dict]] = []
    used_layout_names: set[str] = set()
    for pos, layout in enumerate(layouts, start=1):
        if progress:
            try:
                progress("layouts", pos, len(layouts))
            except Exception:
                pass
        filename = _layout_filename(layout, used_layout_names)
        content = _build_lay_content(
            layout,
            session,
            session_dir,
            filename,
            shapes_dir,
            dlib_override,
            code_map,
        )
        prepared.append((filename, content, layout))

    # Limpa apenas .lay antigos que não fazem parte da nova exportação.
    manifest_path = session_dir / MANIFEST_NAME
    new_names = {name.lower() for name, _content, _layout in prepared}
    if clean_existing_layouts and manifest_path.is_file():
        try:
            old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if old_manifest.get("format") == CAC_FORMAT:
                for old_lay in session_dir.glob("*.lay"):
                    if old_lay.name.lower() not in new_names:
                        try:
                            old_lay.unlink()
                        except OSError:
                            pass
        except Exception:
            pass

    layout_assets: list[LayoutAsset] = []
    for filename, content, layout in prepared:
        path = session_dir / filename
        try:
            payload = content.encode("latin1")
        except UnicodeEncodeError:
            payload = content.encode("latin1", "replace")
            warnings.append(
                f"{filename}: havia caracteres fora do Latin-1; foram substituídos por '?'."
            )
        _write_bytes_atomic(path, payload)
        layout_assets.append(LayoutAsset(
            index=layout["index"],
            filename=filename,
            path=str(path),
            num_items=len(layout["pieces"]),
            width_mm=layout["width_mm"],
            height_mm=layout["height_mm"],
        ))

    elapsed = time.perf_counter() - t0
    result = ExportResult(
        session_id=int(session_id),
        session_code=session_code,
        target_dir=target,
        session_dir=session_dir,
        shapes_dir=shapes_dir,
        layouts=layout_assets,
        dies=sorted(dies, key=lambda d: d.name.lower()),
        missing=missing,
        warnings=warnings,
        elapsed_sec=elapsed,
        manifest_path=manifest_path,
    )

    manifest = {
        "format": CAC_FORMAT,
        "app_version": APP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session": {
            "id": int(session_id),
            "code": session_code,
            "name": session.get("name") or "",
            "job": session.get("job") or "",
        },
        "target_dir": str(target),
        "session_dir": str(session_dir),
        "shapes_dir": str(shapes_dir) if shapes_dir else None,
        "dlib_override": dlib_override or "",
        "elapsed_sec": round(elapsed, 3),
        "complete": result.complete,
        "layouts": [l.to_dict() for l in result.layouts],
        "dies": [d.to_dict() for d in result.dies],
        "missing": result.missing,
        "warnings": result.warnings,
    }
    _write_json_atomic(manifest_path, manifest)
    return result


def pack_session_folder(folder: str | Path, output_cac: str | Path) -> Path:
    """Compacta uma pasta de sessão em um arquivo ``.cac`` (ZIP)."""
    folder_path = Path(str(folder)).expanduser()
    if not folder_path.is_dir():
        raise PackagingError(f"Pasta da sessão não encontrada: {folder_path}")
    output = Path(str(output_cac)).expanduser()
    if output.suffix.lower() != ".cac":
        output = output.with_suffix(".cac")
    output.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in folder_path.rglob("*") if p.is_file())
    tmp = output.with_name(f".{output.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}")
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for file in files:
                rel = file.relative_to(folder_path).as_posix()
                zf.write(file, rel)
        os.replace(tmp, output)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
    return output


def export_session_cac(
    db: Any,
    session_id: int,
    output_cac: str | Path,
    *,
    target_dir: Optional[str | Path] = None,
    **export_kwargs: Any,
) -> ExportResult:
    """
    Atalho: exporta a sessão para uma pasta temporária e devolve o ``.cac``.

    Se ``target_dir`` for informado, a pasta também é preservada nesse local.
    """
    cleanup: Optional[Path] = None
    if target_dir is None:
        cleanup = Path(tempfile.mkdtemp(prefix="corteac_session_"))
        target = cleanup
    else:
        target = Path(target_dir)
    result = export_session(db, session_id, target, **export_kwargs)
    result.cac_path = pack_session_folder(result.session_dir, output_cac)
    if cleanup is not None:
        try:
            shutil.rmtree(cleanup)
        except OSError:
            pass
    return result


__all__ = [
    "CAC_FORMAT",
    "MANIFEST_NAME",
    "SHAPES_DIRNAME",
    "PackagingError",
    "MissingDiesError",
    "DieAsset",
    "LayoutAsset",
    "ExportResult",
    "DieSourceIndex",
    "export_session",
    "pack_session_folder",
    "export_session_cac",
]
