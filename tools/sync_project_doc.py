#!/usr/bin/env python3
"""Sincroniza PROJETO_ATOM_JOBMANAGER.md com o código real do repositório.

Uso (a partir da raiz do projeto):
    python tools/sync_project_doc.py            # atualiza o documento
    python tools/sync_project_doc.py --check    # só verifica (exit 1 se desatualizado)
    python tools/sync_project_doc.py --root CAMINHO --doc CAMINHO/DOC.md

Só reescreve os blocos entre <!-- AUTO:nome:start --> e <!-- AUTO:nome:end -->.
Todo o resto do documento é manual e nunca é tocado.
Não importa nem executa o código do projeto: só lê texto e usa ast.parse.

Blocos: header, tree, symbols, schema, shortcuts, gitlog.
O --check ignora header e gitlog (mudam a cada commit).
"""
import argparse
import ast
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DOC_NAME = "PROJETO_ATOM_JOBMANAGER.md"
IGNORE_DIRS = {"node_modules", "__pycache__", "venv", "env", "build", "dist"}
TREE_EXT = {".py", ".md", ".sql", ".ini", ".json", ".toml", ".yml", ".yaml",
            ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".sh", ".bat"}
DB_EXT = {".db", ".sqlite", ".sqlite3"}
MAX_TREE = 500

# Atalhos do LayoutEditorView (seção 7.1 do documento)
EXPECTED_SHORTCUTS = ["F1", "F2", "F3", "F4", "Ctrl+Z", "Ctrl+S"]
FORBIDDEN_SHORTCUTS = ["Shift+F3", "Ctrl+Y"]


# ----------------------------------------------------------------- utilidades
def read(path):
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
        except OSError:
            return ""
    return ""


def iter_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in IGNORE_DIRS and not d.startswith(".") and not d.endswith(".egg-info")
        )
        for name in sorted(filenames):
            files.append(Path(dirpath) / name)
    return files


def first_doc_line(node):
    doc = ast.get_docstring(node)
    return doc.strip().splitlines()[0] if doc and doc.strip() else ""


def parse_py(path):
    try:
        return ast.parse(read(path))
    except SyntaxError:
        return None


def git(root, *args):
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                             text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


# --------------------------------------------------------------------- blocos
def block_header(root, files):
    py = [f for f in files if f.suffix == ".py"]
    loc = sum(read(f).count("\n") + 1 for f in py)
    head = git(root, "rev-parse", "--short", "HEAD") or "sem git"
    return (f"**Última sincronização com o código:** {datetime.now():%Y-%m-%d %H:%M} "
            f"(HEAD ao gerar: `{head}`; {len(py)} arquivos Python, ~{loc} linhas)")


def block_tree(root, files):
    shown = [f for f in files if f.suffix.lower() in TREE_EXT]
    rows = []
    for f in shown[:MAX_TREE]:
        rel = f.relative_to(root).as_posix()
        doc = ""
        if f.suffix == ".py":
            tree = parse_py(f)
            doc = first_doc_line(tree) if tree else "(erro de sintaxe)"
        rows.append((rel, doc))
    width = min(max((len(r[0]) for r in rows), default=0), 60)
    lines = [f"{rel.ljust(width)}  # {doc}".rstrip(" #") if doc else rel for rel, doc in rows]
    extra = f"\n... e mais {len(shown) - MAX_TREE} arquivos" if len(shown) > MAX_TREE else ""
    return "```\n" + "\n".join(lines) + extra + "\n```"


def block_symbols(root, files):
    out = []
    for f in files:
        if f.suffix != ".py":
            continue
        rel = f.relative_to(root).as_posix()
        tree = parse_py(f)
        if tree is None:
            out.append(f"### `{rel}`\n- erro de sintaxe: não analisado\n")
            continue
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if not classes and not funcs:
            continue
        out.append(f"### `{rel}`")
        for c in classes:
            methods = [n for n in c.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            doc = first_doc_line(c)
            out.append(f"- `class {c.name}` (linha {c.lineno}, {len(methods)} métodos)"
                       + (f": {doc}" if doc else ""))
        if funcs:
            names = ", ".join(f"`{n.name}`" for n in funcs[:15])
            more = f" (+{len(funcs) - 15})" if len(funcs) > 15 else ""
            out.append(f"- funções: {names}{more}")
        out.append("")
    return "\n".join(out).strip() or "_Nenhum símbolo Python encontrado._"


def schema_from_db(path):
    try:
        con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        rows = con.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
            "ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name").fetchall()
        con.close()
        return [r[0] for r in rows]
    except sqlite3.Error:
        return None


def check_db_outdated(db_path, code_path):
    if not db_path.exists() or not code_path.exists():
        return []
    try:
        con = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
        db_tables = {r[0]: set() for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}
        for t in db_tables:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})").fetchall()]
            db_tables[t] = set(cols)
        con.close()
    except Exception:
        return []

    code = read(code_path)
    create_re = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\)", re.DOTALL | re.IGNORECASE)
    code_tables = {}
    for m in create_re.finditer(code):
        tname = m.group(1).lower()
        body = m.group(2)
        cols = set()
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.upper().startswith(("FOREIGN", "PRIMARY KEY", "INDEX", "UNIQUE", "CHECK", ")", "CONSTRAINT")):
                continue
            cname = line.split()[0].strip("\"'`")
            if cname and not cname.upper().startswith(("ENGINE",)):
                cols.add(cname)
        code_tables.setdefault(tname, set()).update(cols)

    warnings = []
    missing_tables = sorted(set(code_tables.keys()) - set(db_tables.keys()))
    if missing_tables:
        warnings.append(f"- **Tabelas ausentes no `.db`:** " + ", ".join(f"`{t}`" for t in missing_tables))
    for t in sorted(code_tables.keys()):
        if t in db_tables:
            diff = sorted(code_tables[t] - db_tables[t])
            if diff:
                warnings.append(f"- **Colunas ausentes na tabela `{t}`:** " + ", ".join(f"`{c}`" for c in diff))
    return warnings


def block_schema(root, files):
    out = []

    # 1. MySQL Schema (Principal)
    mysql_path = root / "db" / "schema_mysql.sql"
    mig_dir = root / "db" / "migrations"
    mysql_sql = []
    if mysql_path.exists():
        mysql_sql.append("-- =============================================================================")
        mysql_sql.append("-- DDL Base: db/schema_mysql.sql")
        mysql_sql.append("-- =============================================================================")
        mysql_sql.append(read(mysql_path).strip())
        mysql_sql.append("")
    if mig_dir.exists():
        for mf in sorted(mig_dir.glob("*.sql")):
            rel_mig = mf.relative_to(root).as_posix()
            mysql_sql.append("-- -----------------------------------------------------------------------------")
            mysql_sql.append(f"-- Migração: {rel_mig}")
            mysql_sql.append("-- -----------------------------------------------------------------------------")
            mysql_sql.append(read(mf).strip())
            mysql_sql.append("")

    if mysql_sql:
        out.append("### 4.1 Schema MySQL 8.0 (Banco de Dados Principal Central)")
        out.append("")
        out.append("DDL base (`db/schema_mysql.sql`) e migrações versionadas (`db/migrations/*.sql`):")
        out.append("")
        out.append("```sql")
        out.extend(mysql_sql)
        out.append("```")
        out.append("")

    # 2. SQLite Schema (Reserva local / contingência)
    out.append("### 4.2 Schema SQLite (Reserva Local / Legado)")
    out.append("")
    out.append("Origem: `jobmanager.db` (banco de contingência offline local)")
    out.append("")

    db_file = root / "jobmanager.db"
    if db_file.exists():
        diff_warnings = check_db_outdated(db_file, root / "database.py")
        if diff_warnings:
            out.append("> [!WARNING]")
            out.append("> **Aviso de desatualização do arquivo local `jobmanager.db`:**")
            out.append("> O arquivo `jobmanager.db` versionado no repositório está desatualizado em relação às tabelas e colunas criadas dinamicamente pelo código (`database.py`):")
            for w in diff_warnings:
                out.append(f"> {w}")
            out.append("> *(Nota: Em tempo de execução, o `database.py` aplica as migrações automaticamente no SQLite via `_migrate_layouts_table()` e `CREATE TABLE IF NOT EXISTS`).*")
            out.append("")

        stmts = schema_from_db(db_file)
        if stmts:
            out.append("```sql")
            out.append("-- Banco: jobmanager.db")
            out.extend(s.strip() + ";" for s in stmts)
            out.append("```")
        else:
            out.append("_Não foi possível ler o schema de `jobmanager.db`._")
    else:
        out.append("_Arquivo `jobmanager.db` não encontrado._")

    return "\n".join(out).strip()


# --- atalhos
KEY_LINE = re.compile(r"shortcut|QKeySequence|\.bind\(|bind_all|accelerator|Key_|keyPressEvent|"
                      r"keyboard|hotkey|add_command|Binding", re.I)
STR_KEY = re.compile(
    r"""["']((?:(?:Ctrl|Shift|Alt|Meta|Control)\+)*"""
    r"""(?:F\d{1,2}|[A-Za-z]|Del|Delete|Esc|Escape|Left|Right|Up|Down|Space|Return|Enter))["']""")
TK_KEY = re.compile(r"""["'](<[^>"']+>)["']""")
QT_KEY = re.compile(r"Key_(\w+)")
MODS = ["ctrl", "shift", "alt", "meta"]

IGNORE_TK_EVENTS = {
    "button", "buttonpress", "buttonrelease", "double", "triple",
    "motion", "b1-motion", "b2-motion", "b3-motion",
    "enter", "leave", "configure", "focusin", "focusout",
    "mousewheel", "activate", "deactivate", "destroy", "expose",
    "map", "unmap", "visibility", "property", "colormap",
    "keyrelease", "keypress"
}


def norm_key(raw):
    parts = [p.lower() for p in re.split(r"[+\-]", raw.strip("<>'\"")) if p]
    if any(p in IGNORE_TK_EVENTS for p in parts):
        return None
    parts = [{"control": "ctrl", "key": None}.get(p, p) for p in parts]
    parts = [p for p in parts if p]
    if not parts:
        return None
    mods = [m for m in MODS if m in parts]
    key = [p for p in parts if p not in MODS]
    if not key:
        return None
    k = key[-1]
    if re.fullmatch(r"\d+", k):
        return None
    if k in ("del", "delete"):
        k = "Delete"
    elif k in ("enter", "return"):
        k = "Return"
    elif k in ("esc", "escape"):
        k = "Escape"
    elif len(k) == 1 or re.fullmatch(r"f\d+", k):
        k = k.upper()
    else:
        k = k.capitalize()
    return "+".join([m.capitalize() for m in mods] + [k])


def find_shortcuts(root, files):
    found = []  # (tecla, local, linha de código)
    for f in files:
        if f.suffix != ".py":
            continue
        rel = f.relative_to(root).as_posix()
        if rel.startswith(("tools/", "tests/")):
            continue
        for i, line in enumerate(read(f).splitlines(), 1):
            if not KEY_LINE.search(line):
                continue
            keys = set()
            for m in STR_KEY.finditer(line):
                nk = norm_key(m.group(1))
                if nk:
                    keys.add(nk)
            for m in TK_KEY.finditer(line):
                nk = norm_key(m.group(1))
                if nk:
                    keys.add(nk)
            for m in QT_KEY.finditer(line):
                raw = m.group(1)
                nk = norm_key(raw)
                if nk:
                    if re.search(r"Control|Ctrl", line) and not nk.startswith("Ctrl+"):
                        nk = "Ctrl+" + nk
                    keys.add(nk)
            for k in keys:
                found.append((k, f"{rel}:{i}", line.strip()[:80]))
    return found


def block_shortcuts(root, files):
    found = find_shortcuts(root, files)
    by_key = {}
    for k, where, code in found:
        by_key.setdefault(k, []).append((where, code))
    out = ["**Atalhos esperados (seção 7.1):**", "",
           "| Atalho | Estado no código | Onde |", "|---|---|---|"]
    for k in EXPECTED_SHORTCUTS:
        hits = by_key.get(k)
        if hits:
            out.append(f"| {k} | encontrado | {', '.join(f'`{w}`' for w, _ in hits[:3])} |")
        else:
            out.append(f"| {k} | **NÃO ENCONTRADO** (pode estar registrado de forma dinâmica) | |")
    for k in FORBIDDEN_SHORTCUTS:
        hits = by_key.get(k)
        if hits:
            all_break = all('"break"' in code or "'break'" in code for _, code in hits)
            if all_break:
                out.append(f"| {k} | bloqueado (correto) | {', '.join(f'`{w}`' for w, _ in hits[:3])} |")
            else:
                out.append(f"| {k} | **PRESENTE, mas deveria NÃO existir** | "
                           f"{', '.join(f'`{w}`' for w, _ in hits[:3])} |")
        else:
            out.append(f"| {k} | ausente (correto) | |")
    out += ["", "**Todos os atalhos detectados no código:**", "",
            "| Atalho | Local | Linha |", "|---|---|---|"]
    if not found:
        out.append("| _nenhum_ | | |")
    for k in sorted(by_key):
        for where, code in by_key[k]:
            out.append(f"| {k} | `{where}` | `{code.replace('|', chr(92) + '|')}` |")

    # Conflitos reais: teclas com concorrência global via bind_all em múltiplos arquivos
    real_conflicts = []
    for k, entries in sorted(by_key.items()):
        ba_files = sorted({w.split(':')[0] for w, c in entries if "bind_all" in c and '"break"' not in c and "'break'" not in c})
        if len(ba_files) > 1:
            real_conflicts.append(f"- `{k}`: múltiplos `bind_all` concorrentes em arquivos distintos ({', '.join(f'`{f}`' for f in ba_files)}).")

    if real_conflicts:
        out += ["", "**Conflitos reais detectados:**", ""] + real_conflicts
    else:
        out += ["", "**Conflitos reais:** Nenhum conflito real detectado (atalhos em arquivos diferentes pertencem a janelas e diálogos independentes)."]

    out += ["", "_Detecção por texto (QShortcut, setShortcut, bind, accelerator, Key_*). "
                "Eventos de mouse (Button, Motion, Wheel) e de ciclo de vida (Configure, Focus) são ignorados._"]
    return "\n".join(out)


def block_gitlog(root, files):
    log = git(root, "log", "-n", "15", "--pretty=format:%h\x1f%ad\x1f%an\x1f%s", "--date=short")
    if not log:
        return "_Sem histórico git disponível._"
    out = ["| Commit | Data | Autor | Mensagem |", "|---|---|---|---|"]
    for line in log.splitlines():
        h, d, a, s = (line.split("\x1f") + ["", "", "", ""])[:4]
        out.append(f"| `{h}` | {d} | {a} | {s.replace('|', '/')} |")
    return "\n".join(out)


# ----------------------------------------------------------------------- main
def replace_block(doc, name, body):
    pat = re.compile(rf"(<!-- AUTO:{name}:start -->)(.*?)(<!-- AUTO:{name}:end -->)", re.S)
    if not pat.search(doc):
        return doc, False
    return pat.sub(lambda m: f"{m.group(1)}\n{body.strip()}\n{m.group(3)}", doc), True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--root", default=".", help="raiz do projeto (padrão: diretório atual)")
    ap.add_argument("--doc", default=None, help=f"documento (padrão: <root>/docs/{DOC_NAME} ou <root>/{DOC_NAME})")
    ap.add_argument("--check", action="store_true", help="não grava; exit 1 se desatualizado")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if args.doc:
        doc_path = Path(args.doc)
    elif (root / "docs" / DOC_NAME).exists():
        doc_path = root / "docs" / DOC_NAME
    else:
        doc_path = root / DOC_NAME

    if not doc_path.exists():
        print(f"ERRO: documento não encontrado: {doc_path}", file=sys.stderr)
        return 2

    original = read(doc_path).replace("\r\n", "\n")
    skip = {doc_path.resolve(), Path(__file__).resolve()}
    files = [f for f in iter_files(root) if f.resolve() not in skip]

    builders = {"tree": block_tree, "symbols": block_symbols,
                "schema": block_schema, "shortcuts": block_shortcuts}
    if not args.check:
        builders = {"header": block_header, **builders, "gitlog": block_gitlog}

    new, changed = original, []
    for name, fn in builders.items():
        before = new
        new, ok = replace_block(new, name, fn(root, files))
        if not ok:
            print(f"AVISO: marcador AUTO:{name} não existe no documento (bloco ignorado)",
                  file=sys.stderr)
        elif new != before:
            changed.append(name)

    if new == original:
        print("Documento já está em dia.")
        return 0
    if args.check:
        print("DESATUALIZADO. Blocos diferentes: " + ", ".join(changed))
        print("Rode: python tools/sync_project_doc.py")
        return 1
    doc_path.write_text(new, encoding="utf-8", newline="\n")
    print("Documento atualizado. Blocos alterados: " + ", ".join(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
