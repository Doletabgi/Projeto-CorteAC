"""
JobManager 2000 (Python Edition)
Material Importer - Parser e validador de arquivos de lista de materiais (CSV, TSV, TXT, JSON).
Suporta detecção automática de delimitador (; , \\t |), codificações (UTF-8, Latin-1, CP1252)
e conversão inteligente de unidades (metros para milímetros).
"""

import io
import csv
import json
import re
from typing import Dict, List, Any, Optional, Set, Tuple


def _decode_bytes(raw_bytes: bytes) -> str:
    """Decodifica os bytes usando fallbacks inteligentes de encoding."""
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1", "iso-8859-1"]
    for enc in encodings:
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _parse_float(val: Any, default: float = 0.0) -> float:
    """Converte valor numérico com suporte a vírgula ou ponto decimal."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(" ", "")
    if not s:
        return default
    # Se contiver vírgula e ponto (ex: 1.380,00 ou 1,380.00)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return default


def _parse_int(val: Any, default: int = 2) -> int:
    """Converte valor para inteiro com fallback."""
    if val is None:
        return default
    try:
        f = _parse_float(val, float(default))
        return int(round(f))
    except (ValueError, TypeError):
        return default


def _normalize_dimension(val_float: float, default_mm: float = 1380.0) -> float:
    """
    Normaliza a dimensão para milímetros.
    Heurística:
      - Se val_float <= 25.0 (ex: 1.38, 2.98, 0.5), considera como metros e converte para mm (* 1000).
      - Se val_float > 25.0 (ex: 1380, 2980), já está em milímetros.
    """
    if val_float <= 0:
        return default_mm
    if val_float <= 25.0:
        return round(val_float * 1000.0, 2)
    return round(val_float, 2)


# Mapeamento flexível de aliases para identificação de colunas
_FIELD_ALIASES = {
    "id": [
        "codigo", "código", "code", "id", "cod", "referencia", "referência",
        "material_id", "mat_id", "cod_material", "codigo_material"
    ],
    "name": [
        "descricao", "descrição", "desc", "nome", "name", "material",
        "nome_material", "designacao", "designação", "detalhe"
    ],
    "type": [
        "definicao", "definição", "tipo", "type", "formato", "mode", "definicao_tipo"
    ],
    "width": [
        "largura", "largura_m", "largura_mm", "width", "larg", "largura (m)",
        "largura (mm)", "w", "largura_placa", "largura_rolo"
    ],
    "height": [
        "comprimento", "comprimento_m", "comprimento_mm", "altura", "height",
        "length", "comp", "comprimento (m)", "comprimento (mm)", "h", "l"
    ],
    "layers": [
        "camadas", "camada", "layers", "layer", "folhas", "folha", "qtd_camadas"
    ],
    "thickness": [
        "espessura", "espessura_mm", "thickness", "esp", "bitola"
    ],
    "gap": [
        "folga", "folga_mm", "gap", "gap_mm", "espacamento", "espaçamento"
    ]
}


def _match_header_key(raw_header: str) -> Optional[str]:
    """Descobre o campo canônico a partir do nome da coluna."""
    cleaned = re.sub(r"[_\s\-\(\)\/]+", " ", raw_header.strip().lower()).strip()
    norm_no_accents = (
        cleaned.replace("ã", "a").replace("á", "a").replace("à", "a")
        .replace("é", "e").replace("ê", "e").replace("í", "i")
        .replace("ó", "o").replace("ô", "o").replace("ú", "u")
        .replace("ç", "c")
    )
    for canonical, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            a_clean = alias.lower()
            if cleaned == a_clean or norm_no_accents == a_clean:
                return canonical
            # Substring match if exact prefix
            if re.sub(r"[_\s]+", "", norm_no_accents) == re.sub(r"[_\s]+", "", a_clean):
                return canonical
    return None


def detect_delimiter(sample_text: str) -> str:
    """Detecta automaticamente o delimitador de um arquivo tabular."""
    first_lines = [line for line in sample_text.splitlines() if line.strip()][:5]
    if not first_lines:
        return ";"

    candidates = [";", ",", "\t", "|"]
    best_delim = ";"
    best_score = -1

    for delim in candidates:
        counts = [line.count(delim) for line in first_lines]
        if all(c > 0 for c in counts):
            # Consistência nas contagens é sinal forte
            diff = max(counts) - min(counts)
            avg = sum(counts) / len(counts)
            score = avg - (diff * 2)
            if score > best_score:
                best_score = score
                best_delim = delim

    return best_delim


def parse_material_file(file_content_or_path: Any, existing_ids: Optional[Set[str]] = None) -> Dict[str, Any]:
    """
    Lê e valida um arquivo ou texto contendo lista de materiais.

    Retorna um dicionário:
    {
        "items": [
            {
                "id": str,
                "name": str,
                "type": str,
                "width_mm": float,
                "height_mm": float,
                "layers": int,
                "thickness_mm": float,
                "gap_mm": float,
                "status": "new" | "update" | "invalid",
                "error_msg": str or None,
                "raw": dict
            }, ...
        ],
        "summary": {
            "total": int,
            "valid": int,
            "new": int,
            "update": int,
            "invalid": int
        }
    }
    """
    if existing_ids is None:
        existing_ids = set()
    else:
        existing_ids = {str(eid).strip() for eid in existing_ids}

    # Carrega o conteúdo como texto
    if isinstance(file_content_or_path, bytes):
        text = _decode_bytes(file_content_or_path)
    elif isinstance(file_content_or_path, str):
        # Pode ser caminho de arquivo ou o próprio conteúdo
        if "\n" not in file_content_or_path and len(file_content_or_path) < 1024:
            try:
                with open(file_content_or_path, "rb") as f:
                    text = _decode_bytes(f.read())
            except (OSError, IOError):
                text = file_content_or_path
        else:
            text = file_content_or_path
    elif hasattr(file_content_or_path, "read"):
        raw = file_content_or_path.read()
        text = _decode_bytes(raw) if isinstance(raw, bytes) else str(raw)
    else:
        text = str(file_content_or_path)

    text = text.strip()
    if not text:
        return {
            "items": [],
            "summary": {"total": 0, "valid": 0, "new": 0, "update": 0, "invalid": 0}
        }

    # Verifica se é JSON
    if text.startswith("[") or text.startswith("{"):
        try:
            return _parse_json_materials(text, existing_ids)
        except Exception:
            pass  # Prossegue para tentar CSV se JSON falhar

    # CSV / TSV / TXT
    return _parse_csv_materials(text, existing_ids)


def _parse_json_materials(text: str, existing_ids: Set[str]) -> Dict[str, Any]:
    """Realiza parsing de lista de materiais em formato JSON."""
    data = json.loads(text)
    if isinstance(data, dict):
        # Procura por chave contendo a lista (materiais, materials, items, data)
        for key in ["materials", "materiais", "items", "data", "lista"]:
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            # Caso seja um único dicionário de material
            data = [data]

    if not isinstance(data, list):
        raise ValueError("JSON não contém uma lista de materiais válida.")

    items = []
    for raw_row in data:
        if not isinstance(raw_row, dict):
            continue
        mapped = {}
        for k, v in raw_row.items():
            canonical = _match_header_key(k)
            if canonical:
                mapped[canonical] = v
            else:
                mapped[k] = v

        item = _build_material_record(mapped, existing_ids, raw_dict=raw_row)
        items.append(item)

    return _build_response_payload(items)


def _parse_csv_materials(text: str, existing_ids: Set[str]) -> Dict[str, Any]:
    """Realiza parsing de CSV, TSV ou TXT."""
    delim = detect_delimiter(text)
    f_in = io.StringIO(text)
    reader = csv.reader(f_in, delimiter=delim)

    rows = []
    for r in reader:
        # Ignora linhas totalmente vazias ou de comentários (#)
        if not r or not any(field.strip() for field in r):
            continue
        if r[0].strip().startswith("#"):
            continue
        rows.append([cell.strip() for cell in r])

    if not rows:
        return _build_response_payload([])

    # Analisa a primeira linha para determinar se é cabeçalho
    first_row = rows[0]
    matched_cols = [_match_header_key(c) for c in first_row]
    has_header = any(m in ("id", "name", "width", "height") for m in matched_cols if m)

    items = []
    start_idx = 1 if has_header else 0

    if has_header:
        header_map = {}
        for idx, col_name in enumerate(first_row):
            can = _match_header_key(col_name)
            if can:
                header_map[idx] = can

        for r in rows[start_idx:]:
            row_dict = {}
            for idx, val in enumerate(r):
                can_key = header_map.get(idx)
                if can_key:
                    row_dict[can_key] = val
                else:
                    row_dict[f"col_{idx}"] = val
            item = _build_material_record(row_dict, existing_ids, raw_dict=dict(zip(first_row, r)))
            items.append(item)
    else:
        # Sem cabeçalho: assume ordem posicional padrão
        # [0: Código, 1: Descrição, 2: Definição/Tipo ou Largura, 3: Largura ou Comprimento, ...]
        for r in rows:
            row_dict = {}
            if len(r) > 0:
                row_dict["id"] = r[0]
            if len(r) > 1:
                row_dict["name"] = r[1]

            # Se o índice 2 for numérico, pode ser largura diretamente
            idx_offset = 0
            if len(r) > 2:
                # Testa se r[2] é texto descritivo de tipo ("como placa", etc.) ou número
                test_num = _parse_float(r[2], -1)
                if test_num > 0:
                    row_dict["type"] = "como placa"
                    row_dict["width"] = r[2]
                    idx_offset = -1
                else:
                    row_dict["type"] = r[2]

            if len(r) > (3 + idx_offset):
                if "width" not in row_dict:
                    row_dict["width"] = r[3 + idx_offset]
                else:
                    row_dict["height"] = r[3 + idx_offset]

            if len(r) > (4 + idx_offset):
                if "height" not in row_dict:
                    row_dict["height"] = r[4 + idx_offset]
                else:
                    row_dict["layers"] = r[4 + idx_offset]

            if len(r) > (5 + idx_offset):
                if "layers" not in row_dict:
                    row_dict["layers"] = r[5 + idx_offset]

            item = _build_material_record(row_dict, existing_ids, raw_dict={"positional": r})
            items.append(item)

    return _build_response_payload(items)


def _build_material_record(data: Dict[str, Any], existing_ids: Set[str], raw_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Valida e normaliza um registro de material individual."""
    mat_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()
    m_type = str(data.get("type", "como placa")).strip() or "como placa"
    if m_type.lower() in ["sheet", "leather", "placa", "chapa", "como placa"]:
        m_type = "como placa"

    raw_width = data.get("width")
    raw_height = data.get("height")
    raw_layers = data.get("layers")
    raw_thickness = data.get("thickness")
    raw_gap = data.get("gap")

    errors = []
    if not mat_id:
        errors.append("Código do material ausente.")

    # Se não houver nome/descrição, utiliza o próprio ID
    if not name and mat_id:
        name = mat_id

    # Normalização de dimensões
    w_float = _parse_float(raw_width, 1.38)
    h_float = _parse_float(raw_height, 2.98)

    if w_float <= 0:
        errors.append("Largura inválida ou zerada.")
    if h_float <= 0:
        errors.append("Comprimento inválido ou zerado.")

    width_mm = _normalize_dimension(w_float, 1380.0)
    height_mm = _normalize_dimension(h_float, 2980.0)

    layers = _parse_int(raw_layers, 2)
    if layers < 1:
        layers = 1

    thickness_mm = _parse_float(raw_thickness, 0.0)
    gap_mm = _parse_float(raw_gap, 1.0)
    if gap_mm < 0:
        gap_mm = 0.0

    is_invalid = len(errors) > 0
    if is_invalid:
        status = "invalid"
        error_msg = "; ".join(errors)
    elif mat_id in existing_ids:
        status = "update"
        error_msg = None
    else:
        status = "new"
        error_msg = None

    return {
        "id": mat_id,
        "name": name,
        "type": m_type,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "layers": layers,
        "thickness_mm": thickness_mm,
        "gap_mm": gap_mm,
        "status": status,
        "error_msg": error_msg,
        "raw": raw_dict
    }


def _build_response_payload(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcula estatísticas de resumo do lote importado."""
    valid_count = sum(1 for it in items if it["status"] in ("new", "update"))
    new_count = sum(1 for it in items if it["status"] == "new")
    update_count = sum(1 for it in items if it["status"] == "update")
    invalid_count = sum(1 for it in items if it["status"] == "invalid")

    return {
        "items": items,
        "summary": {
            "total": len(items),
            "valid": valid_count,
            "new": new_count,
            "update": update_count,
            "invalid": invalid_count
        }
    }


def generate_csv_template(delimiter: str = ";") -> str:
    """Gera um arquivo de exemplo modelo CSV com cabeçalhos e exemplos reais."""
    lines = [
        f"codigo{delimiter}descricao{delimiter}definicao{delimiter}largura{delimiter}comprimento{delimiter}camadas{delimiter}espessura{delimiter}folga",
        f"SINT-PRETO-140{delimiter}Sintético Preto 1.40m{delimiter}como placa{delimiter}1,40{delimiter}3,00{delimiter}2{delimiter}0,0{delimiter}1,0",
        f"COURO-BOVINO-01{delimiter}Couro Bovino Genuíno{delimiter}como placa{delimiter}1380{delimiter}2980{delimiter}1{delimiter}1,2{delimiter}2,0",
        f"TECIDO-CANVAS-02{delimiter}Tecido Canvas Bege{delimiter}como placa{delimiter}1,50{delimiter}50,00{delimiter}4{delimiter}0,0{delimiter}1,0",
        f"EVA-ALTA-DENS{delimiter}Placa EVA 20mm{delimiter}como placa{delimiter}1,00{delimiter}2,00{delimiter}1{delimiter}20,0{delimiter}3,0"
    ]
    return "\n".join(lines) + "\n"
