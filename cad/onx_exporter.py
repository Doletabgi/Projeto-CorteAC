"""
JobManager 2000 (Python Edition)
CAM / CAD: Exportador de Layout no Formato Comelz .ONX (Open Nesting XML Schema v1.1)
Gera arquivo XML compatível com máquinas de corte Comelz (CM44, P500, etc.)
e compacta no container proprietário CZLIB v2.
"""

import datetime
import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

from cad.czlib import compress_czlib, decompress_czlib
from cad.geometry import polygon_area, transform_contour
from cad.die_parser import clean_shape_name


def _format_num(val: float, decimals: int = 4) -> str:
    """Formata número float sem zeros redundantes no final."""
    s = f"{val:.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
        if not s:
            s = "0"
    return s


def build_onx_xml(
    placed_pieces: List[Dict[str, Any]],
    material: Dict[str, Any],
    title: str = "Layout",
    margins_mm: Union[float, Tuple[float, float, float, float]] = 15.0,
    options: Optional[Dict[str, Any]] = None
) -> str:
    """
    Constrói a árvore XML em conformidade estrita com o Schema Comelz ONX 1.1.
    Retorna o texto XML formatado em UTF-8.
    """
    opts = options or {}
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Margens: (top, left, bottom, right)
    if isinstance(margins_mm, (int, float)):
        m_top = m_left = m_bottom = m_right = float(margins_mm)
    elif len(margins_mm) == 4:
        m_top, m_left, m_bottom, m_right = [float(v) for v in margins_mm]
    else:
        m_top = m_left = m_bottom = m_right = 15.0

    width = float(material.get("width_mm", 1350.0))
    height = float(material.get("height_mm", 2553.38))
    thickness = float(material.get("thickness_mm", 1.0))
    gap = float(material.get("gap_mm", 1.0))
    layers = int(material.get("layers", 1))
    mat_name = str(material.get("name") or "SINTETICO")
    mat_code = str(material.get("id") or material.get("code") or "884412")
    clean_title = Path(title).stem

    # Área útil delimitada pelas margens
    x_min = m_left
    y_min = m_top
    x_max = max(x_min, width - m_right)
    y_max = max(y_min, height - m_bottom)

    # Polígono de contorno da chapa útil: (x_min, y_min) -> (x_min, y_max) -> (x_max, y_max) -> (x_max, y_min) -> (x_min, y_min)
    quality_path = f"{x_min:.0f},{y_min:.0f};{x_min:.0f},{y_max:.0f};{x_max:.0f},{y_max:.0f};{x_max:.0f},{y_min:.0f};{x_min:.0f},{y_min:.0f}"

    supplier_area = int(round(width * height * 1000.0))

    # Agrupa peças por modelo/artigo
    # Cada peça pertence a um molde (name) e tamanho (size)
    models_dict = {}
    orders_parts_count = {}

    for idx, p in enumerate(placed_pieces, start=1):
        shp = p.get("shape", {}) if isinstance(p.get("shape"), dict) else {}
        part_name = str(p.get("name") or shp.get("name") or f"Peca_{idx}")
        size = str(p.get("size") or shp.get("size") or "41")
        is_mir = bool(p.get("is_mirrored", False))

        # Modelo pai
        model_name = p.get("model_name") or shp.get("article") or "DefaultModel"
        if model_name not in models_dict:
            models_dict[model_name] = []

        # Contorno e área da peça
        contour = p.get("contour") or shp.get("contour") or []
        area_mm2 = float(p.get("area") or 0.0)
        if area_mm2 <= 0.0 and contour:
            area_mm2 = abs(polygon_area(contour))
        if area_mm2 <= 0.0:
            area_mm2 = 10000.0  # fallback estimado

        # Coordenadas e rotação em radianos
        px = float(p.get("x", 0.0))
        py = float(p.get("y", 0.0))
        rot_deg = float(p.get("rotation", 0.0))
        rot_rad = float(p.get("rot_rad", math.radians(rot_deg)))

        models_dict[model_name].append({
            "part_name": part_name,
            "size": size,
            "mirrored": "true" if is_mir else "false",
            "area": area_mm2,
            "x": px,
            "y": py,
            "angle_rad": rot_rad,
            "sort_idx": idx,
            "origin": p.get("origin", "auto")
        })

        # Contagem para o pedido
        key = (part_name, size)
        if key not in orders_parts_count:
            orders_parts_count[key] = {"right": 0, "mirror": 0}
        if is_mir:
            orders_parts_count[key]["mirror"] += 1
        else:
            orders_parts_count[key]["right"] += 1

    # Construção do XML em linhas estruturadas
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<onx xmlns="http://www.comelz.com/onx" version="1.1">',
        '',
        '<security>',
        '    <cuttable />',
        '</security>',
        '',
        '<metadata>',
        f'    <title>{clean_title}</title>',
        f'    <author>{opts.get("author", "CorteAC")}</author>',
        f'    <creationdate>{now}</creationdate>',
        '    <generator>CorteAC (Python Edition)</generator>',
        '</metadata>',
        '',
        f'<material id="{clean_title}" type="sheet" margin-top="{m_top:.0f}" margin-left="{m_left:.0f}" margin-bottom="{m_bottom:.0f}" margin-right="{m_right:.0f}" width="{width:.2f}" height="{height:.2f}" layers="{layers}">',
        '    <infos>',
        '        <info name="supplier_choice" displayname="Supplier Choice">0</info>',
        '        <info name="scrap" displayname="Scrap">0</info>',
        '        <info name="knife_width" displayname="Knife Width">0.000000</info>',
        f'        <info name="material_thickness" displayname="Material Thickness">{thickness:.6f}</info>',
        f'        <info name="parts_distance" displayname="Parts Distance">{gap:.6f}</info>',
        f'        <info name="profile_name" displayname="Profile Name">{opts.get("profile_name", "TypeA-01")}</info>',
        f'        <info name="supplier_area" displayname="Supplier Area">{supplier_area}</info>',
        f'        <info name="material_name" displayname="Material Name">{mat_name}</info>',
        f'        <info name="material_code" displayname="Material Code">{mat_code}</info>',
        '    </infos>',
        '   <qualityarea layer="0" level="0">',
        f'      <path>{quality_path}</path>',
        '   </qualityarea>',
        '</material>',
        '',
        '<orders>',
        '    <order id="1">',
        f'        <code>{opts.get("order_code", "1")}</code>',
        f'        <creationdate>{now}</creationdate>',
        '        <customer></customer>',
        '        <description></description>',
        '        <filename></filename>',
        f'        <material>{mat_name}</material>',
        f'        <model>{list(models_dict.keys())[0] if models_dict else "Default"}</model>',
        f'        <modificationdate>{now}</modificationdate>',
        '        <season></season>',
        '        <seasonyear></seasonyear>',
        '        <target></target>',
        '        <parts>'
    ]

    for (p_name, p_size), counts in orders_parts_count.items():
        lines.append(f'            <part name="{p_name}" size="{p_size}" rightqty="{counts["right"]}" mirrorqty="{counts["mirror"]}"/>')

    lines.extend([
        '        </parts>',
        '    </order>',
        '</orders>',
        '',
        '<models>'
    ])

    for model_name, pieces in models_dict.items():
        src_path = f"../models/{model_name}.cmz"
        lines.append(f'   <model src="{src_path}">')
        for item in pieces:
            lines.append(
                f'      <part name="{item["part_name"]}" size="{item["size"]}" mirrored="{item["mirrored"]}" area="{item["area"]:.1f}">'
            )
            lines.append(
                f'         <placement x="{item["x"]:.6f}" y="{item["y"]:.6f}" a="{item["angle_rad"]:.6f}" origin="{item["origin"]}" status="placed" sortnumber="{item["sort_idx"]}" familycounter="0" subfamilycounter="0"/>'
            )
            lines.append('      </part>')
        lines.append('   </model>')

    lines.extend([
        '</models>',
        '',
        '<applications>',
        '    <infos>',
        f'        <info app="gl" name="cut_xy_vel">{opts.get("cut_xy_vel", 50)}</info>',
        f'        <info app="gl" name="cut_xy_acc">{opts.get("cut_xy_acc", 70)}</info>',
        '        <info app="gl" name="cn_altezza_pos_1">400</info>',
        '        <info app="gl" name="pen_xy_vel">30</info>',
        '        <info app="gl" name="cut_vel_fustelle">50</info>',
        '        <info app="gl" name="cut_max_angle">45</info>',
        '        <info app="gl" name="cn_limite_min_taglio">20</info>',
        '        <info app="gl" name="cn_limite_min_taglio2">0</info>',
        '        <info app="gl" name="cn_limite_taglio">495</info>',
        '        <info app="gl" name="cn_limite_taglio2">495</info>',
        '        <info app="gl" name="cut_order">fiep</info>',
        '        <info app="gl" name="cut_penne_attive">1</info>',
        '        <info app="gl" name="cut_fustelle_attive">1</info>',
        '        <info app="gl" name="cut_segnati_doppi">0</info>',
        '        <info app="gl" name="cut_opt2_serial">0</info>',
        '    </infos>',
        '</applications>',
        '',
        '</onx>',
        ''
    ])

    return "\n".join(lines)


def export_onx_from_pieces(
    placed_pieces: List[Dict[str, Any]],
    material: Dict[str, Any],
    filename: str = "layout.onx",
    margins_mm: Union[float, Tuple[float, float, float, float]] = 15.0,
    options: Optional[Dict[str, Any]] = None
) -> bytes:
    """
    Gera o conteúdo binário compactado .ONX (CZLIB v2) a partir de uma lista de peças
    posicionadas e informações do material.
    """
    xml_str = build_onx_xml(
        placed_pieces=placed_pieces,
        material=material,
        title=filename,
        margins_mm=margins_mm,
        options=options
    )
    return compress_czlib(xml_str.encode("utf-8"), version=2)


def save_onx_file(
    placed_pieces: List[Dict[str, Any]],
    material: Dict[str, Any],
    file_path: Union[str, Path],
    margins_mm: Union[float, Tuple[float, float, float, float]] = 15.0,
    options: Optional[Dict[str, Any]] = None
) -> str:
    """
    Exporta e grava fisicamente um arquivo de corte .ONX compactado no caminho especificado.
    """
    p = Path(file_path)
    if not p.suffix.lower() == ".onx":
        p = p.with_suffix(".onx")

    onx_bytes = export_onx_from_pieces(
        placed_pieces=placed_pieces,
        material=material,
        filename=p.name,
        margins_mm=margins_mm,
        options=options
    )

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as fp:
        fp.write(onx_bytes)

    return str(p)


def parse_onx(source: Any, db=None) -> Any:
    """
    Realiza o parsing de um arquivo de corte Comelz .ONX (comprimido CZLIB v2 ou XML puro)
    e retorna uma instância de LayoutData compatível com o ecossistema JobManager.
    """
    from cad.lay_parser import LayoutData, TargetDie, PlacedItem, link_layout_items_to_db

    if isinstance(source, (str, Path)):
        file_path = str(source)
        with open(source, "rb") as f:
            raw_data = f.read()
    elif isinstance(source, (bytes, bytearray)):
        file_path = "imported.onx"
        raw_data = bytes(source)
    else:
        file_path = getattr(source, "name", "imported.onx")
        raw_data = source.read()

    if raw_data.startswith(b"CZLIB"):
        xml_bytes = decompress_czlib(raw_data)
    else:
        xml_bytes = raw_data

    root = ET.fromstring(xml_bytes)
    ns = {"onx": "http://www.comelz.com/onx"}

    mat_el = root.find("onx:material", ns)
    if mat_el is None:
        mat_el = root.find("{http://www.comelz.com/onx}material")

    w = 1350.0
    h = 2553.38
    gap = 1.0
    mat_code = "884412"
    if mat_el is not None:
        try:
            w = float(mat_el.attrib.get("width", 1350.0))
            h = float(mat_el.attrib.get("height", 2553.38))
        except ValueError:
            pass
        mat_code = mat_el.attrib.get("id", "884412")
        for info in mat_el.findall(".//onx:info", ns):
            if info.attrib.get("name") == "parts_distance":
                try:
                    gap = float(info.text or 1.0)
                except ValueError:
                    pass

    shape_map = {}
    items = []
    item_no = 1

    for model in root.findall(".//onx:model", ns):
        for part in model.findall("onx:part", ns):
            p_name = part.attrib.get("name", f"Molde_{item_no}")
            p_size = part.attrib.get("size", "41")
            is_mir = (part.attrib.get("mirrored", "false").lower() == "true")

            if p_name not in shape_map:
                shape_map[p_name] = {
                    "code": p_name,
                    "clean_name": p_name,
                    "die_id": len(shape_map) + 1,
                    "count": 0
                }

            for plc in part.findall("onx:placement", ns):
                try:
                    px = float(plc.attrib.get("x", 0.0))
                    py = float(plc.attrib.get("y", 0.0))
                    pa = float(plc.attrib.get("a", 0.0))
                except ValueError:
                    px, py, pa = 0.0, 0.0, 0.0

                tg_idx = list(shape_map.keys()).index(p_name)
                shape_map[p_name]["count"] += 1

                it = PlacedItem(
                    item_no=item_no,
                    tg_idx=tg_idx,
                    inst_id=item_no,
                    x=px,
                    y=py,
                    rot_rad=pa,
                    rot_deg=math.degrees(pa),
                    shape_name=p_name,
                    size=p_size,
                    is_mirrored=is_mir,
                    tag="fn98MR" if is_mir else "Pasted"
                )
                items.append(it)
                item_no += 1

    target_dies = []
    for idx, (sname, sinfo) in enumerate(shape_map.items()):
        tg = TargetDie(
            index=idx + 1,
            code=sinfo["code"],
            die_id=sinfo["die_id"],
            qta_left=sinfo["count"],
            clean_name=sinfo["clean_name"]
        )
        target_dies.append(tg)

    for it in items:
        if it.tg_idx < len(target_dies):
            it.target_die = target_dies[it.tg_idx]

    layout = LayoutData(
        version="$$LAYOUT.v3$$",
        filename=Path(file_path).name,
        ris_w=w,
        ris_l=h,
        gap=gap,
        cod_r=mat_code,
        target_dies=target_dies,
        no_dies=len(target_dies),
        items=items,
        num_of_items=len(items)
    )

    if db is not None:
        try:
            link_layout_items_to_db(layout, db)
        except Exception:
            pass

    layout.calculate_yield()
    return layout
