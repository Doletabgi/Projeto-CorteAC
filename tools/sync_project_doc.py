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


CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?\w+\s*\((?:[^()]|\([^()]*\))*\)", re.I)


def block_schema(root, files):
    out = []
    for f in files:
        if f.suffix.lower() in DB_EXT:
            stmts = schema_from_db(f)
            rel = f.relative_to(root).as_posix()
            if stmts is None:
                out.append(f"-- {rel}: não foi possível ler (arquivo inválido ou bloqueado)")
            else:
                out.append(f"-- Banco: {rel}")
                out.extend(s.strip() + ";" for s in stmts)
                out.append("")
    if not out:
        seen = set()
        for f in files:
            if f.suffix in {".py", ".sql"}:
                for m in CREATE_RE.finditer(read(f)):
                    stmt = " ".join(m.group(0).split())
                    if stmt not in seen:
                        seen.add(stmt)
                        out.append(f"-- {f.relative_to(root).as_posix()}")
                        out.append(m.group(0).strip() + ";")
                        out.append("")
        if out:
            out.insert(0, "-- Nenhum arquivo de banco no repositório; schema extraído dos CREATE TABLE do código")
    if not out:
        out = ["-- Nenhum banco nem CREATE TABLE encontrado"]
    return "```sql\n" + "\n".join(out).rstrip() + "\n```"


# --- atalhos
KEY_LINE = re.compile(r"shortcut|QKeySequence|\.bind\(|bind_all|accelerator|Key_|keyPressEvent|"
                      r"keyboard|hotkey|add_command|Binding", re.I)
STR_KEY = re.compile(
    r"""["']((?:(?:Ctrl|Shift|Alt|Meta|Control)\+)*"""
    r"""(?:F\d{1,2}|[A-Za-z]|Del|Delete|Esc|Escape|Left|Right|Up|Down|Space|Return|Enter))["']""")
TK_KEY = re.compile(r"""["'](<[^>"']+>)["']""")
QT_KEY = re.compile(r"Key_(\w+)")
MODS = ["ctrl", "shift", "alt", "meta"]


def norm_key(raw):
    parts = [p.lower() for p in re.split(r"[+\-]", raw.strip("<>")) if p]
    parts = [{"control": "ctrl", "key": None, "keypress": None}.get(p, p) for p in parts]
    parts = [p for p in parts if p]
    if not parts:
        return raw
    mods = [m for m in MODS if m in parts]
    key = [p for p in parts if p not in MODS]
    if not key:
        return raw
    k = key[-1]
    k = k.upper() if len(k) == 1 or re.fullmatch(r"f\d+", k) else k.capitalize()
    return "+".join([m.capitalize() for m in mods] + [k])


def find_shortcuts(root, files):
    found = []  # (tecla, local, linha de código)
    for f in files:
        if f.suffix != ".py":
            continue
        rel = f.relative_to(root).as_posix()
        for i, line in enumerate(read(f).splitlines(), 1):
            if not KEY_LINE.search(line):
                continue
            keys = {norm_key(m.group(1)) for m in STR_KEY.finditer(line)}
            keys |= {norm_key(m.group(1)) for m in TK_KEY.finditer(line)}
            for m in QT_KEY.finditer(line):
                k = norm_key(m.group(1))
                if re.search(r"Control|Ctrl", line) and not k.startswith("Ctrl+"):
                    k = "Ctrl+" + k
                keys.add(k)
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
    multi = [k for k, v in by_key.items() if len({w.split(':')[0] for w, _ in v}) > 1]
    if multi:
        out += ["", "**Mesma tecla em mais de um arquivo (verificar conflito):** "
                + ", ".join(sorted(multi))]
    out += ["", "_Detecção por texto (QShortcut, setShortcut, bind, accelerator, Key_*). "
                "Atalhos montados dinamicamente podem não aparecer._"]
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
    ap.add_argument("--doc", default=None, help=f"documento (padrão: <root>/{DOC_NAME})")
    ap.add_argument("--check", action="store_true", help="não grava; exit 1 se desatualizado")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    doc_path = Path(args.doc) if args.doc else root / DOC_NAME
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
    # Sincroniza também as cópias na raiz do projeto pai para manter integridade
    parent_doc = root.parent / DOC_NAME
    if parent_doc != doc_path and root.parent.exists():
        try:
            parent_doc.write_text(new, encoding="utf-8", newline="\n")
        except Exception:
            pass
    parent_doc_space = root.parent / "PROJETO_ATOM_JOBMANAGER "
    if parent_doc_space.exists():
        try:
            parent_doc_space.write_text(new, encoding="utf-8", newline="\n")
        except Exception:
            pass
    print("Documento atualizado. Blocos alterados: " + ", ".join(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
