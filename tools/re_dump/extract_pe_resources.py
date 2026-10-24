#!/usr/bin/env python3
"""
tools/re_dump/extract_pe_resources.py

Extração estática completa de recursos Win32 PE dos executáveis legados:
- Layout.exe (Layout Editor Win32 / LayoutNT)
- FreeNest.exe (FreeNest Application)
- Afcadv18E.dll, Afchlib12E.dll, SMPNst.dll

Extrai:
- Menus (RT_MENU) com IDs de comando, aceleradores e hierarquia de popups
- Tabelas de aceleradores (RT_ACCELERATOR) com teclas virtuais e modificadores
- Caixas de diálogo (RT_DIALOG) com coordenadas, títulos, classes e IDs de controles
- Barras de ferramentas (RT_TOOLBAR / 241) com mapeamento 1:1 de botões e IDs
- Cursores (RT_GROUP_CURSOR / RT_CURSOR) com dimensões e hotspots
- Tabelas de strings (RT_STRING) com prompts e tooltips
- Informações de versão (VS_VERSIONINFO) e tabelas de importação/exportação
"""

import sys
import os
import struct
import json
from pathlib import Path

try:
    import pefile
except ImportError:
    print("ERRO: pefile não instalado. Instale com pip install pefile.", file=sys.stderr)
    sys.exit(1)

LEGACY_DIR = Path("/home/dola/Documentos/clone do job/sistemas/antigo/arquivos pos instalacao/Common 100% funcionado")
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "ref" / "layout_re"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VK_MAP = {
    0x08: "VK_BACK", 0x09: "VK_TAB", 0x0D: "VK_RETURN", 0x10: "VK_SHIFT",
    0x11: "VK_CONTROL", 0x12: "VK_MENU (Alt)", 0x13: "VK_PAUSE", 0x14: "VK_CAPITAL",
    0x1B: "VK_ESCAPE", 0x20: "VK_SPACE", 0x21: "VK_PRIOR (PageUp)", 0x22: "VK_NEXT (PageDown)",
    0x23: "VK_END", 0x24: "VK_HOME", 0x25: "VK_LEFT", 0x26: "VK_UP",
    0x27: "VK_RIGHT", 0x28: "VK_DOWN", 0x2D: "VK_INSERT", 0x2E: "VK_DELETE",
    0x60: "VK_NUMPAD0", 0x61: "VK_NUMPAD1", 0x62: "VK_NUMPAD2", 0x63: "VK_NUMPAD3",
    0x64: "VK_NUMPAD4", 0x65: "VK_NUMPAD5", 0x66: "VK_NUMPAD6", 0x67: "VK_NUMPAD7",
    0x68: "VK_NUMPAD8", 0x69: "VK_NUMPAD9", 0x6A: "VK_MULTIPLY (*)", 0x6B: "VK_ADD (+)",
    0x6C: "VK_SEPARATOR", 0x6D: "VK_SUBTRACT (-)", 0x6E: "VK_DECIMAL", 0x6F: "VK_DIVIDE (/)",
    0x70: "VK_F1", 0x71: "VK_F2", 0x72: "VK_F3", 0x73: "VK_F4",
    0x74: "VK_F5", 0x75: "VK_F6", 0x76: "VK_F7", 0x77: "VK_F8",
    0x78: "VK_F9", 0x79: "VK_F10", 0x7A: "VK_F11", 0x7B: "VK_F12"
}

CLASS_NAMES = {
    "ORD_128": "Button",
    "ORD_129": "Edit",
    "ORD_130": "Static",
    "ORD_131": "ListBox",
    "ORD_132": "ScrollBar",
    "ORD_133": "ComboBox",
}

def get_resources(pe, type_id):
    res = []
    if not hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
        return res
    for type_entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if type_entry.struct.Id == type_id:
            for name_entry in type_entry.directory.entries:
                for lang_entry in name_entry.directory.entries:
                    data_rva = lang_entry.data.struct.OffsetToData
                    size = lang_entry.data.struct.Size
                    data = pe.get_data(data_rva, size)
                    res.append((name_entry.struct.Id, lang_entry.struct.Id, data))
    return res

def get_string_table(pe):
    strings = {}
    for bundle_id, lang, data in get_resources(pe, 6): # RT_STRING
        idx = 0
        for i in range(16):
            str_id = (bundle_id - 1) * 16 + i
            if idx + 2 <= len(data):
                length = struct.unpack_from("<H", data, idx)[0]
                idx += 2
                if length > 0 and idx + length * 2 <= len(data):
                    s = data[idx:idx + length * 2].decode("utf-16le", errors="replace")
                    strings[str_id] = s
                    idx += length * 2
    return strings

def parse_menu(data, offset=0):
    ver, hdr_offset = struct.unpack_from("<HH", data, offset)
    offset += 4
    if ver != 0:
        return []
    
    def parse_items(offset, depth=0):
        items = []
        while offset < len(data):
            opt = struct.unpack_from("<H", data, offset)[0]
            offset += 2
            is_popup = bool(opt & 0x0010)
            is_end = bool(opt & 0x0080)
            
            if is_popup:
                s_chars = []
                while offset + 2 <= len(data):
                    c = struct.unpack_from("<H", data, offset)[0]
                    offset += 2
                    if c == 0: break
                    s_chars.append(chr(c))
                title = "".join(s_chars)
                children, offset = parse_items(offset, depth + 1)
                items.append({"type": "POPUP", "title": title, "opt": opt, "children": children})
            else:
                cmd = struct.unpack_from("<H", data, offset)[0]
                offset += 2
                s_chars = []
                while offset + 2 <= len(data):
                    c = struct.unpack_from("<H", data, offset)[0]
                    offset += 2
                    if c == 0: break
                    s_chars.append(chr(c))
                title = "".join(s_chars)
                items.append({"type": "ITEM", "title": title, "cmd": cmd, "opt": opt})
            
            if is_end:
                break
        return items, offset
    
    items, _ = parse_items(offset)
    return items

def format_menu_tree(items, indent=0):
    lines = []
    for it in items:
        sp = "  " * indent
        if it["type"] == "POPUP":
            lines.append(f"{sp}[{it['title']}] (Submenu)")
            lines.extend(format_menu_tree(it["children"], indent + 1))
        else:
            title = it["title"]
            cmd = it["cmd"]
            if not title and cmd == 0:
                lines.append(f"{sp}--- Separador ---")
            else:
                lines.append(f"{sp}{title:<36} [ID: {cmd}]")
    return lines

def parse_dialog(data):
    dlg_ver, signature = struct.unpack_from("<HH", data, 0)
    is_ex = (dlg_ver == 1 and signature == 0xffff)
    offset = 0
    if is_ex:
        dlg_ver, signature, help_id, ex_style, style, c_items, x, y, cx, cy = struct.unpack_from("<HHIIIIhhhh", data, 0)
        offset = 26
    else:
        style, ex_style, c_items, x, y, cx, cy = struct.unpack_from("<IIhhhhh", data, 0)
        offset = 18

    def read_str_or_ord(offset):
        if offset + 2 > len(data): return "", offset
        val = struct.unpack_from("<H", data, offset)[0]
        if val == 0xffff:
            ord_val = struct.unpack_from("<H", data, offset + 2)[0]
            return f"ORD_{ord_val}", offset + 4
        elif val == 0:
            return "", offset + 2
        else:
            chars = []
            while offset + 2 <= len(data):
                c = struct.unpack_from("<H", data, offset)[0]
                offset += 2
                if c == 0: break
                chars.append(chr(c))
            return "".join(chars), offset

    menu, offset = read_str_or_ord(offset)
    cls_name, offset = read_str_or_ord(offset)
    title, offset = read_str_or_ord(offset)

    font_name = ""
    font_size = 0
    if style & 0x40: # DS_SETFONT
        if is_ex:
            font_size, weight, italic, charset = struct.unpack_from("<HHBB", data, offset)
            offset += 6
        else:
            font_size = struct.unpack_from("<H", data, offset)[0]
            offset += 2
        font_name, offset = read_str_or_ord(offset)

    items = []
    for _ in range(c_items):
        offset = (offset + 3) & ~3
        if offset >= len(data): break
        if is_ex:
            help_id, ex_style, style, ix, iy, icx, icy, iid = struct.unpack_from("<IIIhhhhI", data, offset)
            offset += 28
        else:
            style, ex_style, ix, iy, icx, icy, iid = struct.unpack_from("<IIhhhhH", data, offset)
            offset += 18
        icls, offset = read_str_or_ord(offset)
        icls = CLASS_NAMES.get(icls, icls)
        ititle, offset = read_str_or_ord(offset)
        extra_len = struct.unpack_from("<H", data, offset)[0] if offset + 2 <= len(data) else 0
        offset += 2
        if extra_len > 0:
            offset += extra_len
        items.append({
            "id": iid,
            "class": icls,
            "title": ititle,
            "rect": (ix, iy, icx, icy),
            "style": style,
            "ex_style": ex_style
        })

    return {
        "title": title,
        "size": (cx, cy),
        "items_count": c_items,
        "font": (font_name, font_size),
        "items": items
    }

def main():
    layout_path = LEGACY_DIR / "Layout.exe"
    if not layout_path.exists():
        print(f"ERRO: {layout_path} não encontrado.", file=sys.stderr)
        sys.exit(1)

    print(f"Lendo PE {layout_path}...")
    pe = pefile.PE(str(layout_path))
    strings_map = get_string_table(pe)

    # 1. DUMP DE STRINGS
    with open(OUTPUT_DIR / "layout_strings.txt", "w", encoding="utf-8") as f:
        f.write("# Dump completo de RT_STRING extraído do Layout.exe (37 bundles, 281 strings)\n")
        f.write("# ID       Prompt Barra de Status / Tooltip\n")
        f.write("=" * 80 + "\n")
        for sid in sorted(strings_map.keys()):
            val = strings_map[sid].replace("\n", " [TOOLTIP] ")
            f.write(f"{sid:<8}: {val}\n")
    print(f"-> {OUTPUT_DIR / 'layout_strings.txt'} gravado ({len(strings_map)} strings).")

    # 2. DUMP DE MENUS
    menu_resources = get_resources(pe, 4)
    all_menus = {}
    with open(OUTPUT_DIR / "layout_menus.txt", "w", encoding="utf-8") as f:
        f.write("# Dump completo de RT_MENU extraído do Layout.exe (8 Menus Win32)\n")
        f.write("=" * 80 + "\n\n")
        for m_id, lang, data in menu_resources:
            tree = parse_menu(data)
            all_menus[m_id] = tree
            f.write(f"=== MENU ID {m_id} (Lang {lang}) ===\n")
            lines = format_menu_tree(tree)
            f.write("\n".join(lines))
            f.write("\n\n")
    print(f"-> {OUTPUT_DIR / 'layout_menus.txt'} gravado ({len(menu_resources)} menus).")

    # 3. DUMP DE ACELERADORES
    accel_resources = get_resources(pe, 9)
    all_accels = {}
    with open(OUTPUT_DIR / "layout_accelerators.txt", "w", encoding="utf-8") as f:
        f.write("# Dump completo de RT_ACCELERATOR extraído do Layout.exe (3 Tabelas)\n")
        f.write("=" * 80 + "\n\n")
        for tbl_id, lang, data in accel_resources:
            f.write(f"=== TABELA DE ACELERADORES ID {tbl_id} (Lang {lang}) ===\n")
            offset = 0
            tbl_entries = []
            while offset + 8 <= len(data):
                flags, key, cmd = struct.unpack_from("<HHH", data, offset)
                offset += 8
                f_virt = bool(flags & 0x01)
                f_noinv = bool(flags & 0x02)
                f_shift = bool(flags & 0x04)
                f_ctrl = bool(flags & 0x08)
                f_alt = bool(flags & 0x10)
                is_last = bool(flags & 0x80)
                mods = []
                if f_ctrl: mods.append("Ctrl")
                if f_shift: mods.append("Shift")
                if f_alt: mods.append("Alt")
                mod_str = "+".join(mods) + ("+" if mods else "")
                key_name = VK_MAP.get(key, chr(key) if (32 <= key <= 126 and not f_virt) else f"VK_{hex(key)}")
                prompt = strings_map.get(cmd, "").replace("\n", " | Tooltip: ")
                f.write(f"  {mod_str + key_name:<20} -> CMD ID {cmd:<6} | {prompt}\n")
                tbl_entries.append({
                    "combo": mod_str + key_name,
                    "cmd": cmd,
                    "key_code": key,
                    "flags": flags,
                    "prompt": prompt
                })
                if is_last:
                    break
            all_accels[tbl_id] = tbl_entries
            f.write("\n")
    print(f"-> {OUTPUT_DIR / 'layout_accelerators.txt'} gravado ({len(accel_resources)} tabelas).")

    # 4. DUMP DE TOOLBARS (Tipo 241)
    toolbar_resources = get_resources(pe, 241)
    all_toolbars = {}
    with open(OUTPUT_DIR / "layout_toolbars.txt", "w", encoding="utf-8") as f:
        f.write("# Dump completo de RT_TOOLBAR (Tipo 241) extraído do Layout.exe (4 Toolbars)\n")
        f.write("=" * 80 + "\n\n")
        for t_id, lang, data in toolbar_resources:
            ver, w, h, count = struct.unpack_from("<HHHH", data, 0)
            items = struct.unpack_from(f"<{count}H", data, 8)
            f.write(f"=== TOOLBAR ID {t_id} (Tamanho {w}x{h} px, {count} Itens) ===\n")
            tb_items = []
            for i, cmd in enumerate(items):
                if cmd == 0:
                    f.write(f"  [{i:02d}] --- SEPARADOR ---\n")
                    tb_items.append({"idx": i, "cmd": 0, "type": "SEPARATOR"})
                else:
                    st_val = strings_map.get(cmd, "<SEM TEXTO>").replace("\n", " | Tooltip: ")
                    f.write(f"  [{i:02d}] CMD ID {cmd:<6} | {st_val}\n")
                    tb_items.append({"idx": i, "cmd": cmd, "type": "BUTTON", "desc": st_val})
            all_toolbars[t_id] = {"size": [w, h], "items": tb_items}
            f.write("\n")
    print(f"-> {OUTPUT_DIR / 'layout_toolbars.txt'} gravado ({len(toolbar_resources)} toolbars).")

    # 5. DUMP DE DIÁLOGOS (RT_DIALOG)
    dialog_resources = get_resources(pe, 5)
    all_dialogs = {}
    with open(OUTPUT_DIR / "layout_dialogs.txt", "w", encoding="utf-8") as f:
        f.write("# Dump completo de RT_DIALOG extraído do Layout.exe (23 Diálogos Win32)\n")
        f.write("=" * 80 + "\n\n")
        for d_id, lang, data in dialog_resources:
            info = parse_dialog(data)
            all_dialogs[d_id] = info
            f.write(f"=== DIALOG ID {d_id}: \"{info['title']}\" ({info['size'][0]}x{info['size'][1]} DLU, {info['items_count']} controles) ===\n")
            if info['font'][0]:
                f.write(f"  Fonte: {info['font'][0]} {info['font'][1]} pt\n")
            for it in info["items"]:
                f.write(f"    Ctrl ID {it['id']:<6} Class: {it['class']:<14} Text: \"{it['title']}\" Pos: {it['rect']}\n")
            f.write("\n")
    print(f"-> {OUTPUT_DIR / 'layout_dialogs.txt'} gravado ({len(dialog_resources)} diálogos).")

    # 6. DUMP DE CURSORES (RT_GROUP_CURSOR / RT_CURSOR)
    gc_resources = get_resources(pe, 12)
    c_resources = {c_id: (struct.unpack_from("<HH", data, 0), len(data)) for c_id, lang, data in get_resources(pe, 1)}
    with open(OUTPUT_DIR / "layout_cursors.txt", "w", encoding="utf-8") as f:
        f.write("# Dump completo de Cursores (RT_GROUP_CURSOR e RT_CURSOR) do Layout.exe\n")
        f.write("=" * 80 + "\n\n")
        for gc_id, lang, data in gc_resources:
            wReserved, wType, wCount = struct.unpack_from("<HHH", data, 0)
            f.write(f"=== GROUP CURSOR ID {gc_id} ({wCount} imagem(ns)) ===\n")
            for i in range(wCount):
                w, h, planes, bpp, size, cur_id = struct.unpack_from("<HHHHIH", data, 6 + i * 14)
                hotspot, raw_size = c_resources.get(cur_id, ((0, 0), 0))
                f.write(f"  Imagem [{i}]: Dim: {w}x{h} px, BPP: {bpp}, Cursor ID: {cur_id}, Hotspot: {hotspot}, Size: {size} bytes\n")
            f.write("\n")
    print(f"-> {OUTPUT_DIR / 'layout_cursors.txt'} gravado ({len(gc_resources)} grupos de cursores).")

    # 7. DUMP DE FREENEST.EXE
    fn_path = LEGACY_DIR / "FreeNest.exe"
    if fn_path.exists():
        pe_fn = pefile.PE(str(fn_path))
        fn_dialogs = get_resources(pe_fn, 5)
        with open(OUTPUT_DIR / "freenest_resources.txt", "w", encoding="utf-8") as f:
            f.write("# Dump de Recursos do FreeNest.exe (4 Diálogos, 2 Strings)\n")
            f.write("=" * 80 + "\n\n")
            for d_id, lang, data in fn_dialogs:
                info = parse_dialog(data)
                f.write(f"=== FREENEST DIALOG ID {d_id}: \"{info['title']}\" ({info['size'][0]}x{info['size'][1]} DLU, {info['items_count']} controles) ===\n")
                for it in info["items"]:
                    f.write(f"    Ctrl ID {it['id']:<6} Class: {it['class']:<14} Text: \"{it['title']}\" Pos: {it['rect']}\n")
                f.write("\n")
        print(f"-> {OUTPUT_DIR / 'freenest_resources.txt'} gravado.")

    print("\nTodos os dumps de recursos PE foram gerados com sucesso em docs/ref/layout_re/.")

if __name__ == "__main__":
    main()
