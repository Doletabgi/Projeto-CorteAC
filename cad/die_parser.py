"""
JobManager 2000 (Python Edition)
ATOM Shape (.die) Parser & Exporter
Suporte aprimorado ao formato de moldes proprietário ATOM ($$FUSTELLA.v3$$, $$FUSTELLA.v2$$, $$SHAPE2$$ / .die / .shp / .d)
"""

import os
import re
import json
import math
from pathlib import Path
from cad.geometry import polygon_area, polygon_perimeter, polygon_bbox
from cad.colors import get_color_for_size


def _parse_float(val: str, default: float = 0.0) -> float:
    """Converte string para float com suporte a separador decimal de ponto ou vírgula."""
    if not val:
        return default
    v = val.strip().replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return default


def interpolate_arc_bulge(p1: dict, p2: dict, bulge: float, num_segments: int = 8) -> list:
    """
    Interpola vértices intermediários ao longo de um arco definido por dois pontos
    e o valor de bulge (bulge = tan(theta/4)).
    Padrão industrial DXF e ATOM CAD (Afcgeo.dll).
    """
    if abs(bulge) < 1e-5:
        return []

    x1, y1 = p1["x"], p1["y"]
    x2, y2 = p2["x"], p2["y"]
    dx = x2 - x1
    dy = y2 - y1
    chord = math.hypot(dx, dy)
    if chord < 1e-4:
        return []

    theta = 4.0 * math.atan(bulge)
    # Raio do arco
    radius = chord * (1.0 + bulge * bulge) / (4.0 * abs(bulge))
    # Ponto médio da corda
    mx = (x1 + x2) / 2.0
    my = (y1 + y2) / 2.0
    # Sagitta e distância ao centro
    sagitta = bulge * chord / 2.0
    dist_to_center = radius - abs(sagitta)

    # Vetor unitário normal à corda
    ux = dx / chord
    uy = dy / chord
    if bulge > 0:
        nx, ny = -uy, ux
    else:
        nx, ny = uy, -ux

    cx = mx + nx * dist_to_center
    cy = my + ny * dist_to_center

    start_angle = math.atan2(y1 - cy, x1 - cx)
    pts = []
    for step in range(1, num_segments):
        frac = step / float(num_segments)
        current_angle = start_angle + theta * frac
        pts.append({
            "x": round(cx + radius * math.cos(current_angle), 2),
            "y": round(cy + radius * math.sin(current_angle), 2)
        })
    return pts


def clean_shape_name(raw_name: str, default_name: str = "Molde_Importado") -> str:
    """Limpa e formata o nome de um molde, eliminando caminhos de rede e prefixos de arquivo."""
    if not raw_name:
        return default_name

    s = raw_name.strip().strip('"').strip("'")
    # Remove caminhos de rede ou pastas do Windows (ex: \\lab-inf\modelos\..., C:\Users\...)
    if "\\" in s or "/" in s:
        s = Path(s).name

    # Remove extensões comuns de molde
    for ext in [".die", ".Die", ".DIE", ".shp", ".SHP", ".d", ".D"]:
        if s.endswith(ext):
            s = s[:-len(ext)]

    # Se o nome iniciar com 'MODEL ', extrai o nome real após o prefixo
    if s.upper().startswith("MODEL "):
        s = s[6:].strip()

    return s if s else default_name


def parse_die_content(content: str, default_name="Molde_Importado") -> dict:
    """
    Analisa o conteúdo textual de um arquivo .die da máquina de corte ATOM.
    Suporta as variantes $$FUSTELLA$$, $$FUSTELLA.v2$$, $$FUSTELLA.v3$$, $$SHAPE2$$ e formatos correlatos.
    """
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    # 1. Tenta formato JSON se aplicável
    trimmed = content.strip()
    if trimmed.startswith("{") and trimmed.endswith("}"):
        try:
            data = json.loads(trimmed)
            if "contour" in data:
                return {
                    "name": data.get("name", default_name),
                    "contour": data.get("contour", []),
                    "holes": data.get("holes", []),
                    "stitching": data.get("stitching", []),
                    "size": str(data.get("size", "41")),
                    "color": get_color_for_size(data.get("size") or data.get("name") or "41"),
                    "metadata": data.get("metadata", {})
                }
        except Exception:
            pass

    # 2. Analisador padrão ATOM ($$FUSTELLA$$ / .die)
    shape_name = clean_shape_name(default_name)
    size = "41"
    quality_zone = 1
    dir_from = None
    dir_to = None
    grain_angle = 0.0

    raw_contour_points = []  # Lista de dict(x, y, bulge)
    drills = []
    hpoints = []
    current_hole_ring = []
    hole_polygons = []
    cuts = []
    cut_polylines = []
    current_cut = []
    metadata = {}

    current_section = "header"

    for line in lines:
        if line.startswith("#") or line.startswith("//") or line.startswith(";"):
            continue

        # Cabeçalhos de versão ATOM
        if line.startswith("$$FUSTELLA") or line.startswith("$$SHAPE") or line.startswith("$$DIE"):
            metadata["format"] = line
            continue

        # Metadados de identificação e regras de corte
        if line.startswith("descrizione="):
            val = line.split("=", 1)[1].strip()
            if val:
                shape_name = clean_shape_name(val, default_name=shape_name)
            metadata["descrizione"] = val

        elif line.startswith("name_of_shape="):
            val = line.split("=", 1)[1].strip()
            if val and not val.startswith("\\\\"):
                shape_name = clean_shape_name(val, default_name=shape_name)
            metadata["name_of_shape"] = val

        elif line.startswith("name_of_die"):
            parts = line.split("=", 1)
            if len(parts) > 1:
                vals = parts[1].strip().split()
                if vals:
                    # Se o primeiro termo for 'MODEL', o nome é o próximo termo
                    first_token = vals[0].strip()
                    if first_token.upper() == "MODEL" and len(vals) > 1:
                        cand = clean_shape_name(vals[1], default_name=shape_name)
                    else:
                        cand = clean_shape_name(first_token, default_name=shape_name)

                    if cand and not cand.startswith("\\\\") and (shape_name == default_name or shape_name.startswith("\\\\")):
                        shape_name = cand
                metadata["name_of_die"] = parts[1].strip()

        elif line.startswith("taglia="):
            t_val = line.split("=", 1)[1].strip()
            if t_val:
                size = t_val
            metadata["taglia"] = size

        elif line.startswith("def_quality=") or line.startswith("level_of_qarea="):
            q_val = line.split("=", 1)[1].strip()
            try:
                q = int(q_val)
                if 1 <= q <= 5:
                    quality_zone = q
            except ValueError:
                pass
            metadata["def_quality"] = quality_zone

        elif line.startswith("part="):
            metadata["part"] = line.split("=", 1)[1].strip()

        elif line.startswith("codart="):
            metadata["codart"] = line.split("=", 1)[1].strip()

        elif line.startswith("data_digit="):
            metadata["data_digit"] = line.split("=", 1)[1].strip()

        elif line.startswith("metodo="):
            metadata["metodo"] = line.split("=", 1)[1].strip()

        elif line.startswith("baseAngle="):
            metadata["baseAngle"] = _parse_float(line.split("=", 1)[1].strip())

        # Fio / Fibra do Couro (AngleRange)
        elif line.startswith("directionFrom="):
            parts = line.split("=", 1)[1].strip().replace(",", " ").split()
            if len(parts) >= 2:
                dir_from = (_parse_float(parts[0]), _parse_float(parts[1]))
        elif line.startswith("directionTo="):
            parts = line.split("=", 1)[1].strip().replace(",", " ").split()
            if len(parts) >= 2:
                dir_to = (_parse_float(parts[0]), _parse_float(parts[1]))

        # Métricas gravadas no arquivo
        elif line.startswith("area="):
            metadata["file_area"] = _parse_float(line.split("=", 1)[1].strip())
        elif line.startswith("perimetro="):
            metadata["file_perimetro"] = _parse_float(line.split("=", 1)[1].strip())
        elif line.startswith("piatto_dim_x="):
            metadata["piatto_dim_x"] = _parse_float(line.split("=", 1)[1].strip())
        elif line.startswith("piatto_dim_y="):
            metadata["piatto_dim_y"] = _parse_float(line.split("=", 1)[1].strip())
        elif line.startswith("altezza="):
            metadata["altezza"] = _parse_float(line.split("=", 1)[1].strip())

        # Vértices do contorno principal: point=X Y [Z] [bulge] ou p=X Y
        elif line.startswith("point=") or line.startswith("pt=") or line.startswith("p="):
            raw_coords = line.split("=", 1)[1].strip()
            coords = raw_coords.replace(",", " ").split()
            if len(coords) >= 2:
                try:
                    x = _parse_float(coords[0])
                    y = _parse_float(coords[1])
                    bulge = 0.0
                    if len(coords) >= 4:
                        # point=X Y Z bulge
                        bulge = _parse_float(coords[3])
                    elif len(coords) == 3 and not (coords[2].startswith("0.000") or coords[2] == "0"):
                        # point=X Y bulge
                        bulge = _parse_float(coords[2])
                    raw_contour_points.append({"x": round(x, 2), "y": round(y, 2), "bulge": bulge})
                except Exception:
                    pass

        # Furos e furações
        elif line.startswith("hpoint="):
            # Ponto de furo / contorno de furo: hpoint=X Y [Z]
            raw_coords = line.split("=", 1)[1].strip()
            coords = raw_coords.replace(",", " ").split()
            if len(coords) >= 2:
                try:
                    x = _parse_float(coords[0])
                    y = _parse_float(coords[1])
                    pt = {"x": round(x, 2), "y": round(y, 2), "r": 2.5}
                    hpoints.append(pt)
                    current_hole_ring.append(pt)
                except Exception:
                    pass

        elif line.startswith("drill="):
            # Furo de broca: drill=X Y [Z] [raio/ferramenta] [tipo]
            raw_coords = line.split("=", 1)[1].strip()
            parts = raw_coords.replace(",", " ").split()
            if len(parts) >= 2:
                try:
                    x = _parse_float(parts[0])
                    y = _parse_float(parts[1])
                    r = 2.5
                    if len(parts) > 2:
                        val2 = _parse_float(parts[2])
                        if val2 > 0:
                            r = val2
                        elif len(parts) > 3:
                            val3 = _parse_float(parts[3])
                            if val3 > 0:
                                r = val3
                    drills.append({"x": round(x, 2), "y": round(y, 2), "r": round(r, 2)})
                except Exception:
                    pass

        elif line.startswith("pricker=") or line.startswith("punch=") or line.startswith("notch="):
            # Punções, piques em V e marcações de montagem
            raw_coords = line.split("=", 1)[1].strip()
            parts = raw_coords.replace(",", " ").split()
            if len(parts) >= 2:
                try:
                    x = _parse_float(parts[0])
                    y = _parse_float(parts[1])
                    r = 1.0
                    if len(parts) > 2:
                        val2 = _parse_float(parts[2])
                        if val2 > 0:
                            r = val2
                    drills.append({"x": round(x, 2), "y": round(y, 2), "r": round(r, 2), "type": "PUNCH"})
                except Exception:
                    pass

        # Linhas de costura, rasgos internos e cortes
        elif line.startswith("num_of_cpoints=") or line.startswith("num_of_cuts="):
            if current_cut:
                cut_polylines.append(current_cut)
                current_cut = []

        elif line.startswith("cpoint="):
            # Ponto de corte interno / costura
            raw_coords = line.split("=", 1)[1].strip()
            coords = raw_coords.replace(",", " ").split()
            if len(coords) >= 2:
                try:
                    x = _parse_float(coords[0])
                    y = _parse_float(coords[1])
                    pt = {"x": round(x, 2), "y": round(y, 2)}
                    cuts.append(pt)
                    current_cut.append(pt)
                except Exception:
                    pass

    if current_cut:
        cut_polylines.append(current_cut)

    # 3. Fallback: Se não encontrou 'point=', analisa linhas puras 'X Y' ou 'X Y Z'
    if not raw_contour_points:
        for line in lines:
            parts = line.replace(",", " ").split()
            if len(parts) >= 2:
                try:
                    x = _parse_float(parts[0])
                    y = _parse_float(parts[1])
                    raw_contour_points.append({"x": round(x, 2), "y": round(y, 2), "bulge": 0.0})
                except Exception:
                    pass

    # Expansão de arcos curvos (bulge) no contorno principal
    contour = []
    n_pts = len(raw_contour_points)
    for i in range(n_pts):
        curr_pt = raw_contour_points[i]
        contour.append({"x": curr_pt["x"], "y": curr_pt["y"]})
        bulge = curr_pt.get("bulge", 0.0)
        if abs(bulge) > 1e-4 and n_pts > 1:
            next_pt = raw_contour_points[(i + 1) % n_pts]
            arc_pts = interpolate_arc_bulge(curr_pt, next_pt, bulge)
            contour.extend(arc_pts)

    # Consolidação de Furação e Costuras
    holes = drills if drills else hpoints
    stitching = cut_polylines if cut_polylines else ([cuts] if cuts else [])

    # Cálculo da linha de fio da pele (AngleRange)
    if dir_from and dir_to:
        dx = dir_to[0] - dir_from[0]
        dy = dir_to[1] - dir_from[1]
        grain_angle = round(math.degrees(math.atan2(dy, dx)), 1)
        metadata["grain_angle_deg"] = grain_angle
        metadata["grain_angle_min"] = round(grain_angle - 10.0, 1)
        metadata["grain_angle_max"] = round(grain_angle + 10.0, 1)
        metadata["allowed_discrete_angles"] = [0.0, 180.0]

    metadata["quality_zone"] = quality_zone

    # Validação mínima de polígono
    if len(contour) < 3:
        raise ValueError("O arquivo não contém coordenadas de contorno válidas para um molde (mínimo de 3 vértices necessários).")

    return {
        "name": shape_name,
        "contour": contour,
        "holes": holes,
        "stitching": stitching,
        "size": size,
        "color": get_color_for_size(size),
        "quality_zone": quality_zone,
        "metadata": metadata
    }


def parse_die_file(file_path: str) -> dict:
    """
    Lê um arquivo .die ou .d do disco com detecção resiliente de codificação (UTF-8, Latin-1, CP1252)
    e retorna a estrutura de dados completa do molde.
    """
    p = Path(file_path)
    default_name = p.stem

    # Se for arquivo .d (sidecar ATOM), procura o arquivo .die/.Die correspondente
    if p.suffix.lower() == ".d":
        die_candidate = None
        for ext in [".Die", ".die", ".DIE"]:
            cand = p.with_suffix(ext)
            if cand.exists():
                die_candidate = cand
                break
        if not die_candidate:
            try:
                for enc in ["latin1", "utf-8", "cp1252"]:
                    try:
                        with open(p, "r", encoding=enc, errors="ignore") as f:
                            d_content = f.read()
                        m = re.search(r"F\d+=(.*?\.die)", d_content, re.IGNORECASE)
                        if m:
                            target_name = m.group(1).strip()
                            for sib in p.parent.glob("*"):
                                if sib.name.lower() == target_name.lower():
                                    die_candidate = sib
                                    break
                        if die_candidate:
                            break
                    except Exception:
                        pass
            except Exception:
                pass
        if die_candidate and die_candidate.exists():
            p = die_candidate
            default_name = p.stem

    content = None
    for enc in ["utf-8", "latin1", "cp1252", "iso-8859-1"]:
        try:
            with open(p, "r", encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        with open(p, "r", encoding="latin1", errors="replace") as f:
            content = f.read()

    return parse_die_content(content, default_name=default_name)


def generate_die_content(shape_data: dict) -> str:
    """
    Gera o conteúdo textual no formato oficial ATOM $$FUSTELLA.v3$$ (.die)
    a partir de um dicionário de molde com metadados completos de corte.
    """
    name = shape_data.get("name", "Molde_ATOM")
    contour = shape_data.get("contour", [])
    holes = shape_data.get("holes", [])
    cuts = shape_data.get("stitching", [])
    size = str(shape_data.get("size", "41"))
    q = shape_data.get("quality_zone", 1)

    perim = polygon_perimeter(contour) if len(contour) >= 2 else 0.0
    area_mm2 = polygon_area(contour) if len(contour) >= 3 else 0.0

    if contour:
        min_x, min_y, max_x, max_y = polygon_bbox(contour)
        w = max_x - min_x
        h = max_y - min_y
    else:
        w, h = 0.0, 0.0

    out = []
    out.append("$$FUSTELLA.v3$$")
    out.append(f"name_of_die = MODEL {name}")
    out.append("type_of_die=S")
    out.append(f"descrizione={name}")
    out.append(f"codart={name}")
    out.append(f"taglia={size}")
    out.append(f"directionFrom=0.000000 0.000000")
    out.append(f"directionTo=100.000000 0.000000")
    out.append(f"piatto_dim_x={w:.2f}")
    out.append(f"piatto_dim_y={h:.2f}")
    out.append(f"altezza={h:.2f}")
    out.append(f"area={area_mm2:.2f}")
    out.append(f"perimetro={perim:.2f}")
    out.append("num_of_shapes=1")
    out.append("SAGOMA 1")
    out.append(f"name_of_shape={name}")
    out.append(f"def_quality={q}")

    # Vértices do contorno
    out.append(f"num_of_points= {len(contour)}")
    for pt in contour:
        out.append(f"point={pt['x']:.2f} {pt['y']:.2f} 0.000000")

    # Furos e Punções
    if holes:
        out.append(f"num_of_holes={len(holes)}")
        out.append(f"num_of_hpoints={len(holes)}")
        for h_pt in holes:
            out.append(f"hpoint={h_pt['x']:.2f} {h_pt['y']:.2f} 0.000000")
            r = h_pt.get("r", 2.5)
            out.append(f"drill={h_pt['x']:.2f} {h_pt['y']:.2f} {r:.2f} 1 DRILL")
        out.append(f"num_of_drills={len(holes)}")
    else:
        out.append("num_of_holes=0")
        out.append("num_of_drills=0")

    # Linhas de corte interno / costura
    if cuts:
        total_cuts = len(cuts)
        out.append(f"num_of_cuts={total_cuts}")
        for c_item in cuts:
            if isinstance(c_item, list):
                out.append(f"num_of_cpoints={len(c_item)}")
                for pt in c_item:
                    out.append(f"cpoint={pt['x']:.2f} {pt['y']:.2f} 0.000000")
            else:
                out.append("num_of_cpoints=1")
                out.append(f"cpoint={c_item['x']:.2f} {c_item['y']:.2f} 0.000000")
    else:
        out.append("num_of_cuts=0")

    out.append("num_of_qarea=0")
    out.append("")
    return "\n".join(out)


def save_die_file(shape_data: dict, file_path: str):
    """Salva o molde como arquivo .die no disco no formato ATOM $$FUSTELLA.v3$$."""
    content = generate_die_content(shape_data)
    with open(file_path, "w", encoding="latin1") as f:
        f.write(content)

