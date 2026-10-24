"""
JobManager 2000 (Python Edition)
CAM / Nesting: Parser e Gerador de Arquivos .lay (Layout de Corte ATOM $$LAYOUT.v3$$)
Compatível com fn98.exe, dp98.exe e LayoutNT (Layout.exe).
"""

import os
import re
import math
import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from cad.die_parser import clean_shape_name
from cad.colors import get_color_for_size
from cad.geometry import transform_contour, polygon_bbox, polygons_collide, polygon_area

DEFAULT_FALLBACK_CONTOUR = [
    {"x": 0.0, "y": -38.0},
    {"x": -2.0, "y": -20.0},
    {"x": -2.0, "y": 20.0},
    {"x": 0.0, "y": 38.0},
    {"x": 10.0, "y": 36.0},
    {"x": 24.0, "y": 28.0},
    {"x": 38.0, "y": 16.0},
    {"x": 46.0, "y": 0.0},
    {"x": 38.0, "y": -16.0},
    {"x": 24.0, "y": -28.0},
    {"x": 10.0, "y": -36.0},
]

def _parse_float(val: Any) -> float:
    """Converte string para float tolerando ponto ou vírgula decimal."""
    if val is None:
        return 0.0
    s = str(val).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0

def _parse_int(val: Any) -> int:
    """Converte string para inteiro de forma segura."""
    if val is None:
        return 0
    s = str(val).strip()
    try:
        return int(float(s.replace(",", ".")))
    except ValueError:
        return 0

@dataclass
class TargetDie:
    """Representa uma matriz alvo (TG) declarada no layout."""
    index: int = 1
    lib: str = ""
    code: str = ""
    die_id: int = 0
    has_die_id: bool = False
    qta_left: int = 0
    qta_right: int = 0
    single_left: int = 0
    single_right: int = 0
    is_filler: int = 0
    targ_left: int = 0
    targ_right: int = 0
    clean_name: str = ""

    def __post_init__(self):
        if not self.clean_name and self.code:
            self.clean_name = clean_shape_name(self.code)

@dataclass
class PlacedItem:
    """Representa uma peça individual posicionada no layout (I)."""
    item_no: int = 1
    tg_idx: int = 0
    inst_id: int = 0
    flags: int = 0
    x: float = 0.0
    y: float = 0.0
    rot_rad: float = 0.0
    rot_deg: float = 0.0
    color: str = "#2563eb"
    color_raw: int = -65536
    tag: str = "Pasted"
    is_mirrored: bool = False
    shape_name: str = ""
    size: str = ""
    target_die: Optional[TargetDie] = None
    contour: List[Dict[str, float]] = field(default_factory=lambda: [dict(pt) for pt in DEFAULT_FALLBACK_CONTOUR])
    holes: List[Dict[str, Any]] = field(default_factory=list)
    stitching: List[Any] = field(default_factory=list)
    internal_cuts: List[Any] = field(default_factory=list)
    quality_zone: int = 1
    matched_in_db: bool = False

@dataclass
class QualityZone:
    """Zona de qualidade ou defeito em couro/pele."""
    name: str = ""
    level: int = 1  # 1 = Top Quality, 4 = Defeito severo
    polygon: List[Dict[str, float]] = field(default_factory=list)

@dataclass
class LayoutData:
    """Estrutura consolidada de um layout de corte .lay."""
    version: str = "$$LAYOUT.v3$$"
    path: str = ""
    filename: str = "l0000.lay"
    desc: str = "fn98 - v1.2.36 - 12.09.2012"
    gap: float = 1.0
    cod_r: str = ""
    hide_path: str = ""
    ris_w: float = 1350.0
    ris_l: float = 2553.38
    y_max: float = 0.0
    y_last: float = 0.0
    area: float = 0.0
    no_dies: int = 0
    target_dies: List[TargetDie] = field(default_factory=list)
    num_of_items: int = 0
    items: List[PlacedItem] = field(default_factory=list)
    quality_zones: List[QualityZone] = field(default_factory=list)
    yield_percent: float = 0.0
    session_id: Optional[int] = None
    raw_lines: List[str] = field(default_factory=list)

    def calculate_yield(self) -> float:
        """Calcula o aproveitamento percentual da chapa/área útil."""
        sheet_area = max(1.0, self.ris_w * self.ris_l)
        if self.area > 0.0:
            self.yield_percent = round((self.area / sheet_area) * 100.0, 2)
        elif self.items:
            tot_a = 0.0
            for it in self.items:
                if it.contour:
                    tot_a += polygon_area(it.contour)
            self.area = tot_a
            self.yield_percent = round((tot_a / sheet_area) * 100.0, 2)
        return self.yield_percent


def parse_lay(source: Any, db=None) -> LayoutData:
    """
    Realiza o parsing de um arquivo ou conteúdo em string/bytes .lay (padrão $$LAYOUT.v3$$).
    Tolerante a encodings (latin1, utf-8, cp1252), vírgula decimal e moldes não cadastrados.
    """
    raw_content = ""
    file_path = ""
    filename = "l0000.lay"

    # Detecção automática do formato Comelz .onx (CZLIB v2 ou XML)
    if (isinstance(source, (str, os.PathLike)) and str(source).lower().endswith(".onx")) or \
       (isinstance(source, bytes) and source.startswith(b"CZLIB")):
        from cad.onx_exporter import parse_onx
        return parse_onx(source, db=db)

    if isinstance(source, (str, os.PathLike)) and os.path.exists(str(source)):
        try:
            with open(str(source), "rb") as probe_fp:
                if probe_fp.read(6).startswith(b"CZLIB"):
                    from cad.onx_exporter import parse_onx
                    return parse_onx(source, db=db)
        except Exception:
            pass
        file_path = os.path.abspath(str(source))
        filename = os.path.basename(file_path)
        for enc in ("latin1", "utf-8", "cp1252", "iso-8859-1"):
            try:
                with open(file_path, "r", encoding=enc, errors="replace") as fp:
                    raw_content = fp.read()
                break
            except Exception:
                continue
    elif isinstance(source, bytes):
        for enc in ("latin1", "utf-8", "cp1252", "iso-8859-1"):
            try:
                raw_content = source.decode(enc)
                break
            except Exception:
                continue
    elif isinstance(source, str):
        raw_content = source
    else:
        raise ValueError(f"Fonte inválida para parse_lay: {type(source)}")

    if not raw_content or not raw_content.strip():
        raise ValueError("Arquivo .lay vazio ou sem conteúdo legível.")

    lines = [l.strip() for l in raw_content.splitlines() if l.strip()]
    if not lines:
        raise ValueError("Arquivo .lay não contém linhas válidas.")

    # 1. Validação do Magic Header
    header = lines[0]
    if not header.startswith("$$LAYOUT"):
        raise ValueError(f"Assinatura de layout inválida: '{header}'. Esperado '$$LAYOUT.v3$$'.")

    layout = LayoutData(version=header, path=file_path, filename=filename, raw_lines=lines)

    # 2. Leitura da linha 2 (Caminho e nome do arquivo)
    idx = 1
    if len(lines) > 1 and not ("=" in lines[1]) and not lines[1].startswith("TG "):
        path_line = lines[1]
        rparts = path_line.rsplit(None, 1)
        if len(rparts) == 2:
            layout.path = rparts[0]
            layout.filename = rparts[1]
        elif len(rparts) == 1:
            layout.filename = rparts[0]
        idx = 2

    # 3. Parsing dos Metadados Gerais
    current_tg: Optional[TargetDie] = None

    while idx < len(lines):
        line = lines[idx]
        idx += 1

        if line.startswith("num_of_items="):
            layout.num_of_items = _parse_int(line.split("=", 1)[1])
            break

        if line.startswith("TG "):
            tg_num = _parse_int(line[3:])
            current_tg = TargetDie(index=tg_num)
            layout.target_dies.append(current_tg)
            continue

        if current_tg is not None:
            if line.startswith("dLib="):
                current_tg.lib = line.split("=", 1)[1].strip()
            elif line.startswith("dCode="):
                current_tg.code = line.split("=", 1)[1].strip()
                current_tg.clean_name = clean_shape_name(current_tg.code)
            elif line.startswith("dId="):
                current_tg.die_id = _parse_int(line.split("=", 1)[1])
                current_tg.has_die_id = True
            elif line.startswith("dQta="):
                vals = line.split("=", 1)[1].split(",")
                current_tg.qta_left = _parse_int(vals[0]) if len(vals) > 0 else 0
                current_tg.qta_right = _parse_int(vals[1]) if len(vals) > 1 else 0
            elif line.startswith("dSingle="):
                vals = line.split("=", 1)[1].split(",")
                current_tg.single_left = _parse_int(vals[0]) if len(vals) > 0 else 0
                current_tg.single_right = _parse_int(vals[1]) if len(vals) > 1 else 0
            elif line.startswith("dIsFiller="):
                current_tg.is_filler = _parse_int(line.split("=", 1)[1])
            elif line.startswith("dTarg="):
                vals = line.split("=", 1)[1].split(",")
                current_tg.targ_left = _parse_int(vals[0]) if len(vals) > 0 else 0
                current_tg.targ_right = _parse_int(vals[1]) if len(vals) > 1 else 0
            continue

        # Chaves de metadados gerais
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()

            if key == "desc":
                layout.desc = val
            elif key == "gap":
                layout.gap = _parse_float(val)
            elif key == "codR":
                layout.cod_r = val
            elif key == "hide":
                layout.hide_path = val
            elif key == "risW":
                layout.ris_w = _parse_float(val)
            elif key == "risL":
                layout.ris_l = _parse_float(val)
            elif key == "Y_max":
                layout.y_max = _parse_float(val)
            elif key == "Y_last":
                layout.y_last = _parse_float(val)
            elif key == "area":
                layout.area = _parse_float(val)
            elif key == "no_dies":
                layout.no_dies = _parse_int(val)

    # 4. Parsing das Peças Posicionadas (I ...)
    while idx < len(lines):
        line = lines[idx]
        idx += 1
        if not line.startswith("I "):
            continue

        parts = line.split()
        if len(parts) < 10:
            continue

        item_no = _parse_int(parts[1])
        tg_idx = _parse_int(parts[2])
        inst_id = _parse_int(parts[3])
        flags = _parse_int(parts[4])
        x = _parse_float(parts[5])
        y = _parse_float(parts[6])
        rot_rad = _parse_float(parts[7])
        rot_deg = round(math.degrees(rot_rad), 3)
        color_raw = _parse_int(parts[8])
        tag = parts[9]
        is_mirrored = ("M" in tag)

        tg = layout.target_dies[tg_idx] if (0 <= tg_idx < len(layout.target_dies)) else None
        shp_name = tg.clean_name if tg else f"Item_{item_no}"
        
        # Extrai número / tamanho do nome do molde
        digits = re.findall(r"\d+", shp_name)
        size_str = digits[-1] if digits else "41"
        if "a" in shp_name.lower():
            size_str += "a"

        piece_color = get_color_for_size(size_str, item_no)

        item = PlacedItem(
            item_no=item_no,
            tg_idx=tg_idx,
            inst_id=inst_id,
            flags=flags,
            x=x,
            y=y,
            rot_rad=rot_rad,
            rot_deg=rot_deg,
            color=piece_color,
            color_raw=color_raw,
            tag=tag,
            is_mirrored=is_mirrored,
            shape_name=shp_name,
            size=size_str,
            target_die=tg
        )
        layout.items.append(item)

    layout.no_dies = len(layout.target_dies)
    layout.num_of_items = len(layout.items)
    layout.calculate_yield()

    # 5. Vinculação com o Banco de Dados (se fornecido)
    if db is not None:
        link_layout_items_to_db(layout, db)

    return layout


def link_layout_items_to_db(layout: LayoutData, db) -> None:
    """
    Vincula os moldes do banco de dados (SQLite) a cada peça do layout,
    associando contorno, furações, costuras e qualidade.
    """
    try:
        shapes = db.get_all_shapes() if hasattr(db, "get_all_shapes") else []
    except Exception:
        shapes = []

    shapes_by_name = {}
    for s in shapes:
        norm_n = clean_shape_name(s.get("name", ""))
        shapes_by_name[norm_n.lower()] = s
        if s.get("name"):
            shapes_by_name[s["name"].lower()] = s

    for it in layout.items:
        key = it.shape_name.lower()
        matched = shapes_by_name.get(key)
        if not matched and it.target_die:
            matched = shapes_by_name.get(it.target_die.clean_name.lower())
            if not matched:
                matched = shapes_by_name.get(it.target_die.code.lower())

        if matched:
            it.matched_in_db = True
            it.contour = matched.get("contour", [])
            it.holes = matched.get("holes", [])
            it.stitching = matched.get("stitching", [])
            it.internal_cuts = matched.get("internal_cuts", [])
            it.quality_zone = int(matched.get("quality_zone") or 1)
            if matched.get("size"):
                it.size = str(matched["size"])
                it.color = get_color_for_size(it.size, it.item_no)
        else:
            it.matched_in_db = False
            if not it.contour:
                it.contour = [dict(pt) for pt in DEFAULT_FALLBACK_CONTOUR]


def generate_lay_content(
    layout_data: LayoutData,
    target_dies: Optional[List[TargetDie]] = None,
    placed_pieces: Optional[List[Dict[str, Any]]] = None,
    path_override: Optional[str] = None,
    filename_override: Optional[str] = None
) -> str:
    """
    Gera o conteúdo em texto puro formatado no padrão oficial $$LAYOUT.v3$$
    com terminadores CRLF (\\r\\n), preservando a ordem de usinagem e vácuo:
    1º Furações e ilhoses (DRILL/HOLES)
    2º Piques e punções (PUNCH/PRICKER)
    3º Costuras e rasgos internos (CUTS/CPOINTS)
    4º Contorno externo (TOOL_KNIFE_DOWN - sempre por último).
    """
    out = []
    out.append("$$LAYOUT.v3$$")

    # Linha 2: Path e Filename
    p = path_override or layout_data.path or "\\\\lab-inf\\NSDATAV1\\Compiti\\JobManager"
    fn = filename_override or layout_data.filename or "l0000.lay"
    out.append(f"{p} {fn}")

    # Metadados
    out.append(f"desc={layout_data.desc}")
    out.append(f"gap={layout_data.gap:.6f}")
    out.append(f"codR={layout_data.cod_r}")
    if layout_data.hide_path:
        out.append(f"hide={layout_data.hide_path}")

    out.append(f"risW={layout_data.ris_w:.6f}")
    out.append(f"risL={layout_data.ris_l:.6f}")
    out.append(f"Y_max={layout_data.y_max:.6f}")
    out.append(f"Y_last={layout_data.y_last:.6f}")
    out.append(f"area={layout_data.area:.6f}")

    # Matrizes TG
    dies = target_dies if target_dies is not None else layout_data.target_dies
    out.append(f"no_dies={len(dies)}")

    for tg in dies:
        out.append(f"TG {tg.index}")
        out.append(f"dLib={tg.lib}")
        out.append(f"dCode={tg.code}")
        if tg.has_die_id:
            out.append(f"dId={tg.die_id}")
        out.append(f"dQta={tg.qta_left}, {tg.qta_right}")
        out.append(f"dSingle={tg.single_left}, {tg.single_right}")
        out.append(f"dIsFiller={tg.is_filler}")
        out.append(f"dTarg={tg.targ_left}, {tg.targ_right}")

    # Lista de Peças Posicionadas (I)
    items = layout_data.items
    out.append(f"num_of_items={len(items)}")

    for it in items:
        out.append(
            f"I {it.item_no} {it.tg_idx} {it.inst_id} {it.flags} "
            f"{it.x:.6f} {it.y:.6f} {it.rot_rad:.6f} {it.color_raw} {it.tag}"
        )

    # Terminador Windows CRLF em todas as linhas
    return "\r\n".join(out) + "\r\n"


def validate_layout_placement(layout: LayoutData, quality_zones: Optional[List[QualityZone]] = None) -> List[str]:
    """
    Valida a integridade do layout importado e retorna lista de alertas informativos (não bloqueantes):
    - Peças sobrepostas / colisão entre peças.
    - Peças fora dos limites físicos da chapa ou pele.
    - Peça de cabedal girada a 90° em relação à linha do fio (perda de tração).
    - Peça exigindo qualidade maior em zona de defeito severo (L_def <= Q_req).
    """
    warnings = []
    w_limit = layout.ris_w
    l_limit = layout.ris_l

    # 1. Verificação de limites físicos da chapa
    for it in layout.items:
        if it.x < -1.0 or it.y < -1.0:
            warnings.append(f"Peça #{it.item_no} ({it.shape_name}) posicionada em coordenadas negativas: (X:{it.x:.1f}, Y:{it.y:.1f})")
        if w_limit > 0 and it.x > w_limit + 1.0:
            warnings.append(f"Peça #{it.item_no} ({it.shape_name}) excede a largura da chapa ({it.x:.1f} > {w_limit:.1f}mm)")
        if l_limit > 0 and it.y > l_limit + 1.0:
            warnings.append(f"Peça #{it.item_no} ({it.shape_name}) excede o comprimento da chapa ({it.y:.1f} > {l_limit:.1f}mm)")

    # 2. Verificação de rotação a 90° em peças de cabedal
    for it in layout.items:
        deg = abs(it.rot_deg) % 180.0
        if 75.0 <= deg <= 105.0:
            nm = it.shape_name.lower()
            if any(k in nm for k in ("gasp", "cabedal", "vamp", "tras", "canext", "lateral")):
                warnings.append(
                    f"Atenção: Peça de cabedal #{it.item_no} ({it.shape_name}) com rotação de {it.rot_deg:.1f}°. "
                    "Pode violar a linha de tração/fio da pele."
                )

    # 3. Verificação de colisões / sobreposição entre peças
    n_items = len(layout.items)
    for i in range(min(n_items, 100)):
        p1 = layout.items[i]
        if not p1.contour:
            continue
        poly1 = transform_contour(p1.contour, p1.x, p1.y, p1.rot_deg)
        bbox1 = polygon_bbox(poly1)

        for j in range(i + 1, min(n_items, 100)):
            p2 = layout.items[j]
            if not p2.contour:
                continue
            poly2 = transform_contour(p2.contour, p2.x, p2.y, p2.rot_deg)
            bbox2 = polygon_bbox(poly2)

            if polygons_collide(poly1, poly2, gap=0.0, bbox_a=bbox1, bbox_b=bbox2):
                warnings.append(f"Possível sobreposição detectada entre Peça #{p1.item_no} e Peça #{p2.item_no}")
                break

    # 4. Verificação de Zonas de Defeito (Regra: L_def <= Q_req)
    q_zones = quality_zones or layout.quality_zones
    if q_zones:
        for it in layout.items:
            q_req = getattr(it, "quality_zone", 1)
            # Para cada zona de defeito
            for qz in q_zones:
                if qz.level > q_req:
                    # Defeito pior que a exigência da peça
                    if it.contour and qz.polygon:
                        poly_it = transform_contour(it.contour, it.x, it.y, it.rot_deg)
                        if polygons_collide(poly_it, qz.polygon, gap=0.0):
                            warnings.append(
                                f"Alerta de Qualidade: Peça #{it.item_no} (Q{q_req}) cobre defeito severo "
                                f"'{qz.name}' (Nível {qz.level}). Regra violada: L_def ({qz.level}) > Q_req ({q_req})."
                            )

    return warnings


def export_layout_from_pieces(
    placed_pieces: List[Dict[str, Any]],
    material: Dict[str, Any],
    session_id: Optional[int] = 1,
    filename: str = "l0000.lay",
    path: str = "\\\\lab-inf\\NSDATAV1\\Compiti\\JobManager"
) -> str:
    """
    Exporta uma lista de peças posicionadas (do LayoutEditorView ou SessionView)
    para o formato padrão $$LAYOUT.v3$$, garantindo ordenação CAM de usinagem e
    preservação de vácuo:
    1º Furações e ilhoses (DRILL/HOLES)
    2º Piques e punções (PUNCH/PRICKER)
    3º Costuras e rasgos internos (CUTS/CPOINTS)
    4º Contorno externo (TOOL_KNIFE_DOWN - sempre por último).
    """
    ris_w = float(material.get("width_mm", 1350.0))
    ris_l = float(material.get("height_mm", 2553.38))
    gap = float(material.get("gap_mm", 1.0))
    mat_code = str(material.get("id") or material.get("name") or "884412")
    if material.get("name") and material.get("name") not in mat_code:
        mat_code = f"{mat_code} - {material.get('name')}"

    # Agrupa peças por molde para gerar os blocos TG
    shape_map = {}
    for p in placed_pieces:
        shp = p.get("shape", {}) if isinstance(p.get("shape"), dict) else {}
        name = str(p.get("name") or shp.get("name") or f"Molde_{p.get('target_id', 1)}")
        if name not in shape_map:
            die_code = name if name.endswith(".die") else f"{name}.die"
            shape_map[name] = {
                "code": die_code,
                "clean_name": clean_shape_name(name),
                "die_id": p.get("target_id") or shp.get("id") or (len(shape_map) + 1),
                "pieces": []
            }
        shape_map[name]["pieces"].append(p)

    target_dies = []
    tg_lookup = {}
    for idx, (name, sdata) in enumerate(shape_map.items()):
        tg_num = idx + 1
        tg_lookup[name] = idx  # 0-based index for item line

        # Conta peças normais vs espelhadas
        qta_left = sum(1 for p in sdata["pieces"] if not p.get("is_mirrored", False))
        qta_right = sum(1 for p in sdata["pieces"] if p.get("is_mirrored", False))
        if qta_left == 0 and qta_right == 0:
            qta_left = len(sdata["pieces"])

        tg = TargetDie(
            index=tg_num,
            lib="\\\\lab-inf\\NSDATAV1\\Shapes",
            code=sdata["code"],
            die_id=sdata["die_id"],
            has_die_id=True,
            qta_left=qta_left,
            qta_right=qta_right,
            single_left=0,
            single_right=0,
            is_filler=0,
            targ_left=max(qta_left, 1),
            targ_right=max(qta_right, 1),
            clean_name=sdata["clean_name"]
        )
        target_dies.append(tg)

    # Cria itens posicionados
    items = []
    tot_area_mm2 = 0.0

    for idx, p in enumerate(placed_pieces, start=1):
        shp = p.get("shape", {}) if isinstance(p.get("shape"), dict) else {}
        name = str(p.get("name") or shp.get("name") or "Molde")
        tg_idx = tg_lookup.get(name, 0)
        tg = target_dies[tg_idx] if tg_idx < len(target_dies) else None

        px = float(p.get("x", 0.0))
        py = float(p.get("y", 0.0))
        rot_deg = float(p.get("rotation", 0.0))
        rot_rad = math.radians(rot_deg)
        is_mir = bool(p.get("is_mirrored", False))

        tag = "fn98MR" if is_mir else "Pasted"

        contour = p.get("contour") or shp.get("contour") or []
        if contour:
            tot_area_mm2 += polygon_area(contour)

        item = PlacedItem(
            item_no=idx,
            tg_idx=tg_idx,
            inst_id=idx - 1,
            flags=0,
            x=px,
            y=py,
            rot_rad=rot_rad,
            rot_deg=rot_deg,
            color=p.get("color", "#2563eb"),
            color_raw=-65536,
            tag=tag,
            is_mirrored=is_mir,
            shape_name=name,
            size=str(p.get("size") or shp.get("size") or "41"),
            target_die=tg,
            contour=contour,
            holes=p.get("holes") or shp.get("holes") or [],
            stitching=p.get("stitching") or shp.get("stitching") or [],
            internal_cuts=p.get("internal_cuts") or shp.get("internal_cuts") or []
        )
        items.append(item)

    layout = LayoutData(
        version="$$LAYOUT.v3$$",
        path=path,
        filename=filename,
        desc="CorteAC Nesting CAM",
        gap=gap,
        cod_r=mat_code,
        ris_w=ris_w,
        ris_l=ris_l,
        y_max=0.0,
        y_last=0.0,
        area=round(tot_area_mm2, 6),
        no_dies=len(target_dies),
        target_dies=target_dies,
        num_of_items=len(items),
        items=items,
        session_id=session_id
    )
    layout.calculate_yield()
    return generate_lay_content(layout)
