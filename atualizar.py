#!/usr/bin/env python3
"""Atualização completa do OpenCorte: versão, documentação, build, mesa e GitHub.

Uso: python3 atualizar.py [--simular] [--incremento patch|minor|major] [--retomar]
Uma execução real cria commit/tag e publica no origin. Nunca usa force-push.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import tarfile
import zipfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
SOURCE_SUFFIXES = {'.py', '.md', '.rst', '.txt', '.sql', '.ini', '.toml', '.yml',
                   '.yaml', '.sh', '.bat', '.ps1', '.iss', '.json', '.png', '.ico',
                   '.gif', '.jpg', '.jpeg', '.svg', '.ttf', '.otf', '.css', '.html',
                   '.die', '.lay', '.onx', '.cmz'}
CHECKS = ['tests/test_atualizar.py', 'tests/test_semver.py', 'tests/test_desktop_shortcut.py',
          'tests/test_database_cleanup.py',
          'tests/test_production_sheet.py', 'tests/test_layout_print_legend.py',
          'tests/test_symbolic_notches.py', 'tests/test_project_packager.py',
          'tests/test_dual_exporter.py', 'tests/test_connection_settings.py']
SOURCE_DIRS = {'.github', 'analytics', 'assets', 'cad', 'db', 'docs', 'packaging',
               'samples', 'tests', 'tools', 'ui'}


class UpdateError(RuntimeError):
    pass


def command(args, cwd=ROOT, *, capture=False, env=None, timeout=None):
    """Argumentos estruturados: caminhos com espaços não passam por shell."""
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                            capture_output=capture, text=True, timeout=timeout)
    if result.returncode:
        detail = result.stderr.strip() if capture else 'consulte a saída acima'
        raise UpdateError(f'{args[0]} terminou com código {result.returncode}: {detail}')
    return result.stdout.strip() if capture else ''


def git(root, *args):
    return command(['git', *args], root, capture=True, timeout=120)


def current_version(root):
    tree = ast.parse((root / 'config.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'APP_VERSION' for t in node.targets):
            return ast.literal_eval(node.value)
    raise UpdateError('APP_VERSION não encontrada em config.py.')


def set_version(root, version):
    from cad.semver import SemVer
    version = str(SemVer.parse(version))
    path = root/'config.py'
    text, count = re.subn(r'^APP_VERSION\s*=.*$', f'APP_VERSION = "{version}"',
                          path.read_text(encoding='utf-8'), count=1, flags=re.M)
    if count != 1:
        raise UpdateError('Não foi possível atualizar APP_VERSION.')
    path.write_text(text, encoding='utf-8')
    installer = root/'packaging/corteac_setup.iss'
    if installer.exists():
        text = re.sub(r'(#define MyAppVersion )"[^"]+"', rf'\g<1>"{version}"',
                      installer.read_text(encoding='utf-8'))
        installer.write_text(text, encoding='utf-8')


def next_version(version, increment):
    # Não importa config: a leitura de versão não abre banco nem cria diretórios.
    match = re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version)
    if not match:
        raise UpdateError('A versão atual deve usar MAJOR.MINOR.PATCH sem sufixos.')
    major, minor, patch = map(int, match.groups())
    if increment == 'major':
        return f'{major+1}.0.0'
    if increment == 'minor':
        return f'{major}.{minor+1}.0'
    return f'{major}.{minor}.{patch+1}'


def allowed_source(name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts:
        return False
    if len(p.parts) > 1 and p.parts[0] not in SOURCE_DIRS:
        return False
    if len(p.parts) == 1 and p.suffix.lower() in {'.die', '.lay', '.onx', '.cmz', '.png', '.jpg'}:
        return False
    if any(part.startswith('.') and part != '.github' for part in p.parts[:-1]):
        return False
    if p.parts[0] in {'backups', 'output', 'scratch', 'dist', 'build', 'dist_linux',
                      'dist_package', 'venv', 'env', '__pycache__'}:
        return False
    if p.name.lower() in {'db.ini', '.env'} or p.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.pem', '.key'}:
        return False
    if p.suffix.lower() == '.ini' and p.name != 'db.example.ini':
        return False
    return p.name in {'.gitignore', '.gitattributes'} or p.suffix.lower() in SOURCE_SUFFIXES


def source_files(root):
    raw = command(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                  root, capture=True)
    return sorted({name for name in raw.split('\0') if name and allowed_source(name)})


def fingerprint(root, files):
    result = {}
    for name in files:
        p = root / name
        if p.is_symlink():
            raise UpdateError(f'Fonte simbólica não suportada: {name}')
        result[name] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    return result


def snapshot(root, target, files):
    target.mkdir(parents=True, exist_ok=True)
    for name in files:
        source = root / name
        if source.is_file():
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)


def isolated_env(stage):
    env = os.environ.copy()
    env.update(DB_BACKEND='sqlite', SQLITE_PATH=str(stage / 'jobmanager.db'),
               CORTEAC_SHAPES_DIR='', CORTEAC_SESSIONS_DIR='', CORTEAC_SHAPES_ROOT='',
               CI='1', PYTHONPATH=str(stage), PYTHONUNBUFFERED='1', TZ='America/Sao_Paulo')
    return env


def repository_name(remote):
    match = re.fullmatch(r'(?:git@github\.com:|https://github\.com/)([\w.-]+/[\w.-]+?)(?:\.git)?/?', remote)
    if not match:
        raise UpdateError('O origin deve ser um repositório github.com por SSH ou HTTPS.')
    return match.group(1)


class GitHub:
    def __init__(self, repo):
        self.repo = repo
        self.token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')

    def get(self, path, *, missing_ok=False):
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'OpenCorte-update',
                   'X-GitHub-Api-Version': '2022-11-28'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        request = Request(f'https://api.github.com/repos/{self.repo}/{path}', headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            raise UpdateError(f'GitHub HTTP {exc.code}. Verifique acesso ao repositório; para privado, defina GH_TOKEN com leitura de Actions.') from exc
        except URLError as exc:
            raise UpdateError('Não foi possível consultar o GitHub. Verifique a rede e use --retomar.') from exc

    def wait_release(self, sha, tag, version, minutes):
        deadline = time.monotonic() + minutes*60
        last = None
        while time.monotonic() < deadline:
            query = urlencode({'head_sha': sha, 'event': 'push', 'per_page': 30})
            runs = self.get(f'actions/runs?{query}')['workflow_runs']
            runs = [r for r in runs if r.get('path', '').split('@')[0] == '.github/workflows/release.yml']
            if runs:
                run = max(runs, key=lambda r: (r['id'], r.get('run_attempt', 1)))
                status = (run['id'], run.get('run_attempt'), run['status'], run.get('conclusion'))
                if status != last:
                    print(f"GitHub: {run['status']} / {run.get('conclusion') or 'em andamento'} — {run['html_url']}", flush=True)
                    last = status
                if run['status'] == 'completed':
                    if run['conclusion'] != 'success':
                        raise UpdateError(f"Build/release falhou: {run['html_url']}. Corrija/reexecute no GitHub e use --retomar.")
                    release = self.get(f'releases/tags/{quote(tag, safe="")}', missing_ok=True)
                    required = {'CorteAC.exe', 'CorteAC-Windows-x64.zip', 'corteac_linux',
                                'CorteAC-Linux-x64.tar.gz', f'CorteAC-Setup-{version}.exe'}
                    assets = {a['name'] for a in (release or {}).get('assets', []) if a.get('size', 0) > 0}
                    if release and not release.get('draft') and required <= assets:
                        return release['html_url']
                    if release:
                        raise UpdateError('Release sem todos os cinco artefatos: ' + ', '.join(sorted(required-assets)))
            time.sleep(min(60, max(0, deadline-time.monotonic())))
        raise UpdateError('Tempo de espera esgotado; use --retomar para continuar acompanhando a mesma versão.')


def atomic_copy(source, dest, backup_dir):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / (dest.name + '.anterior')
        if not backup.exists():
            shutil.copy2(dest, backup)
    fd, temporary = tempfile.mkstemp(prefix=dest.name+'.', dir=dest.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, dest)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def execution_lock(root):
    # O lock do SO é liberado inclusive após interrupção ou encerramento abrupto.
    path = root / '.release' / 'execucao.lock'
    path.parent.mkdir(exist_ok=True)
    with path.open('a+b') as handle:
        try:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise UpdateError('Já existe uma atualização em execução nesta pasta.') from exc
        yield


# Documentação: implementação centralizada, somente leitura dos fontes/schema.
DOC_FILENAME = "PROJETO_ATOM_JOBMANAGER.md"
DOC_IGNORE_DIRS = {"node_modules", "__pycache__", "venv", "env", "build", "dist"}
DOC_TREE_EXT = {".py", ".md", ".sql", ".ini", ".json", ".toml", ".yml", ".yaml",
            ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".sh", ".bat"}
DOC_DB_EXT = {".db", ".sqlite", ".sqlite3"}
DOC_MAX_TREE = 500

# Atalhos do LayoutEditorView (seção 7.1 do documento)
DOC_EXPECTED_SHORTCUTS = ["F1", "F2", "F3", "F4", "Ctrl+Z", "Ctrl+S"]
DOC_FORBIDDEN_SHORTCUTS = ["Shift+F3", "Ctrl+Y"]


# ----------------------------------------------------------------- utilidades
def doc_document_brand(text):
    """Atualiza a marca no texto; preserva código, caminhos e URLs existentes."""
    protected = re.compile(
        r"```[\s\S]*?```|`[^`\n]+`|https?://[^\s<>\"')]+|"
        r"\b(?:[\w.~-]+[/\\])+[\w.~-]+|"
        r"\bCorteAC(?:-[\w.-]+)?\.(?:exe|spec|desktop|lnk|png|ico|zip|tar\.gz)\b",
        re.IGNORECASE,
    )
    chunks = []
    end = 0
    for match in protected.finditer(text):
        chunks.append(re.sub(r'\bCorteAC\b', 'OpenCorte', text[end:match.start()], flags=re.IGNORECASE))
        chunks.append(match.group())
        end = match.end()
    chunks.append(re.sub(r'\bCorteAC\b', 'OpenCorte', text[end:], flags=re.IGNORECASE))
    return ''.join(chunks)


def doc_read(path):
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
        except OSError:
            return ""
    return ""


def doc_iter_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in DOC_IGNORE_DIRS and not d.startswith(".") and not d.endswith(".egg-info")
        )
        for name in sorted(filenames):
            files.append(Path(dirpath) / name)
    return files


def doc_first_doc_line(node):
    doc = ast.get_docstring(node)
    return doc_document_brand(doc.strip().splitlines()[0]) if doc and doc.strip() else ""


def doc_parse_py(path):
    try:
        return ast.parse(doc_read(path))
    except SyntaxError:
        return None


def doc_git(root, *args):
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                             text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


# --------------------------------------------------------------------- blocos
def doc_block_header(root, files):
    py = [f for f in files if f.suffix == ".py"]
    loc = sum(doc_read(f).count("\n") + 1 for f in py)
    head = doc_git(root, "rev-parse", "--short", "HEAD") or "sem git"
    tree = doc_parse_py(root / "config.py")
    version = "não informada"
    for node in tree.body if tree else []:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "APP_VERSION" for t in node.targets):
            try:
                version = str(ast.literal_eval(node.value))
            except (ValueError, TypeError):
                pass
    return (f"**Versão do aplicativo:** `{version}`\n\n"
            f"**Última sincronização com o código:** {datetime.now():%Y-%m-%d %H:%M} "
            f"(HEAD ao gerar: `{head}`; {len(py)} arquivos Python, ~{loc} linhas)")


def doc_block_tree(root, files):
    shown = [f for f in files if f.suffix.lower() in DOC_TREE_EXT]
    rows = []
    for f in shown[:DOC_MAX_TREE]:
        rel = f.relative_to(root).as_posix()
        doc = ""
        if f.suffix == ".py":
            tree = doc_parse_py(f)
            doc = doc_first_doc_line(tree) if tree else "(erro de sintaxe)"
        rows.append((rel, doc))
    width = min(max((len(r[0]) for r in rows), default=0), 60)
    lines = [f"{rel.ljust(width)}  # {doc}".rstrip(" #") if doc else rel for rel, doc in rows]
    extra = f"\n... e mais {len(shown) - DOC_MAX_TREE} arquivos" if len(shown) > DOC_MAX_TREE else ""
    return "```\n" + "\n".join(lines) + extra + "\n```"


def doc_block_symbols(root, files):
    out = []
    for f in files:
        if f.suffix != ".py":
            continue
        rel = f.relative_to(root).as_posix()
        tree = doc_parse_py(f)
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
            doc = doc_first_doc_line(c)
            out.append(f"- `class {c.name}` (linha {c.lineno}, {len(methods)} métodos)"
                       + (f": {doc}" if doc else ""))
        if funcs:
            names = ", ".join(f"`{n.name}`" for n in funcs[:15])
            more = f" (+{len(funcs) - 15})" if len(funcs) > 15 else ""
            out.append(f"- funções: {names}{more}")
        out.append("")
    return "\n".join(out).strip() or "_Nenhum símbolo Python encontrado._"


def doc_schema_from_db(path):
    try:
        con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        rows = con.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
            "ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name").fetchall()
        con.close()
        return [r[0] for r in rows]
    except sqlite3.Error:
        return None


def doc_check_db_outdated(db_path, code_path):
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

    code = doc_read(code_path)
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


def doc_block_schema(root, files):
    out = []

    # 1. MySQL Schema (Principal)
    mysql_path = root / "db" / "schema_mysql.sql"
    mig_dir = root / "db" / "migrations"
    mysql_sql = []
    if mysql_path.exists():
        mysql_sql.append("-- =============================================================================")
        mysql_sql.append("-- DDL Base: db/schema_mysql.sql")
        mysql_sql.append("-- =============================================================================")
        mysql_sql.append(doc_read(mysql_path).strip())
        mysql_sql.append("")
    if mig_dir.exists():
        for mf in sorted(mig_dir.glob("*.sql")):
            rel_mig = mf.relative_to(root).as_posix()
            mysql_sql.append("-- -----------------------------------------------------------------------------")
            mysql_sql.append(f"-- Migração: {rel_mig}")
            mysql_sql.append("-- -----------------------------------------------------------------------------")
            mysql_sql.append(doc_read(mf).strip())
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
        diff_warnings = doc_check_db_outdated(db_file, root / "database.py")
        if diff_warnings:
            out.append("> [!WARNING]")
            out.append("> **Aviso de desatualização do arquivo local `jobmanager.db`:**")
            out.append("> O arquivo `jobmanager.db` versionado no repositório está desatualizado em relação às tabelas e colunas criadas dinamicamente pelo código (`database.py`):")
            for w in diff_warnings:
                out.append(f"> {w}")
            out.append("> *(Nota: Em tempo de execução, o `database.py` aplica as migrações automaticamente no SQLite via `_migrate_layouts_table()` e `CREATE TABLE IF NOT EXISTS`).*")
            out.append("")

        stmts = doc_schema_from_db(db_file)
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
DOC_KEY_LINE = re.compile(r"shortcut|QKeySequence|\.bind\(|bind_all|accelerator|Key_|keyPressEvent|"
                      r"keyboard|hotkey|add_command|Binding", re.I)
DOC_STR_KEY = re.compile(
    r"""["']((?:(?:Ctrl|Shift|Alt|Meta|Control)\+)*"""
    r"""(?:F\d{1,2}|[A-Za-z]|Del|Delete|Esc|Escape|Left|Right|Up|Down|Space|Return|Enter))["']""")
DOC_TK_KEY = re.compile(r"""["'](<[^>"']+>)["']""")
DOC_QT_KEY = re.compile(r"Key_(\w+)")
DOC_MODS = ["ctrl", "shift", "alt", "meta"]

DOC_IGNORE_TK_EVENTS = {
    "button", "buttonpress", "buttonrelease", "double", "triple",
    "motion", "b1-motion", "b2-motion", "b3-motion",
    "enter", "leave", "configure", "focusin", "focusout",
    "mousewheel", "activate", "deactivate", "destroy", "expose",
    "map", "unmap", "visibility", "property", "colormap",
    "keyrelease", "keypress"
}


def doc_norm_key(raw):
    parts = [p.lower() for p in re.split(r"[+\-]", raw.strip("<>'\"")) if p]
    if any(p in DOC_IGNORE_TK_EVENTS for p in parts):
        return None
    parts = [{"control": "ctrl", "key": None}.get(p, p) for p in parts]
    parts = [p for p in parts if p]
    if not parts:
        return None
    mods = [m for m in DOC_MODS if m in parts]
    key = [p for p in parts if p not in DOC_MODS]
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


def doc_find_shortcuts(root, files):
    found = []  # (tecla, local, linha de código)
    for f in files:
        if f.suffix != ".py":
            continue
        rel = f.relative_to(root).as_posix()
        if rel == "atualizar.py" or rel.startswith(("tools/", "tests/")):
            continue
        for i, line in enumerate(doc_read(f).splitlines(), 1):
            if not DOC_KEY_LINE.search(line):
                continue
            keys = set()
            for m in DOC_STR_KEY.finditer(line):
                nk = doc_norm_key(m.group(1))
                if nk:
                    keys.add(nk)
            for m in DOC_TK_KEY.finditer(line):
                nk = doc_norm_key(m.group(1))
                if nk:
                    keys.add(nk)
            for m in DOC_QT_KEY.finditer(line):
                raw = m.group(1)
                nk = doc_norm_key(raw)
                if nk:
                    if re.search(r"Control|Ctrl", line) and not nk.startswith("Ctrl+"):
                        nk = "Ctrl+" + nk
                    keys.add(nk)
            for k in keys:
                found.append((k, f"{rel}:{i}", line.strip()[:80]))
    return found


def doc_block_shortcuts(root, files):
    found = doc_find_shortcuts(root, files)
    by_key = {}
    for k, where, code in found:
        by_key.setdefault(k, []).append((where, code))
    out = ["**Atalhos esperados (seção 7.1):**", "",
           "| Atalho | Estado no código | Onde |", "|---|---|---|"]
    for k in DOC_EXPECTED_SHORTCUTS:
        hits = by_key.get(k)
        if hits:
            out.append(f"| {k} | encontrado | {', '.join(f'`{w}`' for w, _ in hits[:3])} |")
        else:
            out.append(f"| {k} | **NÃO ENCONTRADO** (pode estar registrado de forma dinâmica) | |")
    for k in DOC_FORBIDDEN_SHORTCUTS:
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


def doc_block_gitlog(root, files):
    log = doc_git(root, "log", "-n", "15", "--pretty=format:%h\x1f%ad\x1f%an\x1f%s", "--date=short")
    if not log:
        return "_Sem histórico git disponível._"
    out = ["| Commit | Data | Autor | Mensagem |", "|---|---|---|---|"]
    for line in log.splitlines():
        h, d, a, s = (line.split("\x1f") + ["", "", "", ""])[:4]
        out.append(f"| `{h}` | {d} | {a} | {s.replace('|', '/')} |")
    return "\n".join(out)


# ----------------------------------------------------------------------- main
def doc_replace_block(doc, name, body):
    pat = re.compile(rf"(<!-- AUTO:{name}:start -->)(.*?)(<!-- AUTO:{name}:end -->)", re.S)
    if not pat.search(doc):
        return doc, False
    return pat.sub(lambda m: f"{m.group(1)}\n{body.strip()}\n{m.group(3)}", doc), True



# Instaladores gerados nos pacotes portáteis, sem scripts-fonte paralelos.
LINUX_SHORTCUT_TEMPLATE = r'''#!/usr/bin/env bash
# Instala/atualiza o atalho do CorteAC na Área de Trabalho e no menu de aplicativos.
#
# O nome do atalho carrega a VERSÃO (ex.: "CorteAC-1.6.10") e a versão anterior é
# removida, para o operador saber exatamente qual build está na máquina.
#
# A versão é preenchida pelo atualizador central durante o empacotamento.
set -e

VERSAO_PADRAO="@VERSAO@"
DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. Descobre a versão: primeiro perguntando ao próprio binário, depois o valor gravado no pacote
VERSAO=""
if [ -x "$DIR/corteac_linux" ]; then
    VERSAO="$("$DIR/corteac_linux" --version 2>/dev/null | awk '{print $NF}' | head -n1 || true)"
fi
case "$VERSAO" in
    [0-9]*) : ;;
    *) VERSAO="$VERSAO_PADRAO" ;;
esac

NOME="CorteAC-$VERSAO"
ARQ="corteac-$VERSAO.desktop"
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"

# 2. Remove atalhos de versões anteriores (mantém sempre um único ícone na mesa).
#    Cobre os antigos criados à mão ("CorteAC.desktop") e a pasta pt-BR do Mint.
rm -f "$APPS"/corteac.desktop "$APPS"/corteac-*.desktop "$APPS"/CorteAC*.desktop 2>/dev/null || true

DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
if [ -z "$DESKTOP_DIR" ] || [ ! -d "$DESKTOP_DIR" ]; then
    for cand in "$HOME/Desktop" "$HOME/Área de Trabalho" "$HOME/Area de Trabalho"; do
        if [ -d "$cand" ]; then DESKTOP_DIR="$cand"; break; fi
    done
fi
if [ -z "$DESKTOP_DIR" ]; then DESKTOP_DIR="$HOME/Desktop"; fi

for d in "$DESKTOP_DIR" "$HOME/Desktop" "$HOME/Área de Trabalho" "$HOME/Area de Trabalho"; do
    [ -d "$d" ] || continue
    rm -f "$d"/corteac.desktop "$d"/corteac-*.desktop "$d"/CorteAC*.desktop 2>/dev/null || true
done

# 3. Gera o .desktop (Exec= aspeado: o caminho pode conter espaços)
DESK="$APPS/$ARQ"
cat > "$DESK" <<ENTRY
[Desktop Entry]
Type=Application
Name=$NOME
GenericName=Encaixe e Corte
Comment=JobManager 2000 Reborn - encaixe de couro e corte CAM (v$VERSAO)
Exec="$DIR/corteac_linux"
Path=$DIR
Icon=$DIR/corteac.png
Terminal=false
Categories=Graphics;Engineering;
StartupWMClass=corteac_linux
X-CorteAC-Version=$VERSAO
ENTRY
chmod +x "$DESK"

# 4. Copia para a Área de Trabalho com o nome versionado
if [ -d "$DESKTOP_DIR" ]; then
    cp "$DESK" "$DESKTOP_DIR/$ARQ"
    chmod +x "$DESKTOP_DIR/$ARQ"
    gio set "$DESKTOP_DIR/$ARQ" metadata::trusted true 2>/dev/null || true
fi

update-desktop-database "$APPS" 2>/dev/null || true

echo "Atalho instalado: $NOME"
echo "  arquivo : $DESK"
[ -d "$DESKTOP_DIR" ] && echo "  desktop : $DESKTOP_DIR/$ARQ"
echo "  icone   : $DIR/corteac.png"
echo "Se o icone ou o nome nao atualizarem na hora, saia e entre na sessao (cache do ambiente)."
'''

WINDOWS_SHORTCUT_TEMPLATE = r'''# Cria/atualiza o atalho do CorteAC na Area de Trabalho com a VERSAO no nome.
# Ex.: "CorteAC-1.6.11.lnk"  (mantem o icone embutido no .exe)
#
# Uso: clique com o botao direito -> "Executar com PowerShell" nesta pasta,
# ou no terminal:  powershell -ExecutionPolicy Bypass -File .\criar_atalho_windows.ps1

$ErrorActionPreference = 'Stop'
$pasta = Split-Path -Parent $MyInvocation.MyCommand.Definition
$exe = Join-Path $pasta 'CorteAC.exe'

if (-not (Test-Path $exe)) {
    Write-Host "CorteAC.exe nao encontrado nesta pasta: $pasta" -ForegroundColor Red
    exit 1
}

# Versao: arquivo versao.txt gerado no empacotamento; senao, versao do proprio .exe
$versao = $null
$arquivoVersao = Join-Path $pasta 'versao.txt'
if (Test-Path $arquivoVersao) {
    $versao = (Get-Content $arquivoVersao -Raw).Trim()
}
if ([string]::IsNullOrWhiteSpace($versao)) {
    $versao = (Get-Item $exe).VersionInfo.ProductVersion
}
if ([string]::IsNullOrWhiteSpace($versao)) { $versao = 'dev' }

$nome = "CorteAC-$versao.lnk"
$desktop = [Environment]::GetFolderPath('Desktop')

# Remove atalhos antigos do CorteAC na Area de Trabalho (CorteAC.lnk e CorteAC-*.lnk)
Get-ChildItem -Path $desktop -Filter 'CorteAC*.lnk' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

$atalho = Join-Path $desktop $nome
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($atalho)
$s.TargetPath = $exe
$s.WorkingDirectory = $pasta
$s.IconLocation = "$exe,0"
$s.Description = "CorteAC $versao - JobManager 2000 Reborn"
$s.Save()

Write-Host "Atalho criado: $nome" -ForegroundColor Green
Write-Host "  destino: $exe"
Write-Host "  area de trabalho: $desktop"
Write-Host "Se o icone ou o nome nao atualizarem, pressione F5 na Area de Trabalho."
'''


def sync_documentation(root, *, check=False):
    """Atualiza os blocos automáticos e preserva o restante do documento mestre."""
    path = root/'docs'/DOC_FILENAME
    if not path.exists():
        raise UpdateError(f'Documento não encontrado: {path}')
    original = doc_read(path).replace('\r\n', '\n')
    files = [p for p in doc_iter_files(root) if p.resolve() != path.resolve()]
    builders = {'tree': doc_block_tree, 'symbols': doc_block_symbols,
                'schema': doc_block_schema, 'shortcuts': doc_block_shortcuts}
    if not check:
        builders = {'header': doc_block_header, **builders, 'gitlog': doc_block_gitlog}
    result = original
    changed = []
    for name, builder in builders.items():
        previous = result
        result, found = doc_replace_block(result, name, builder(root, files))
        if not found:
            print(f'Aviso: bloco AUTO:{name} ausente no documento.')
        elif result != previous:
            changed.append(name)
    branded = doc_document_brand(result)
    if branded != result:
        changed.append('marca')
        result = branded
    if result != original:
        if check:
            raise UpdateError('Documentação desatualizada: ' + ', '.join(changed))
        path.write_text(result, encoding='utf-8', newline='\n')
        print('Documento atualizado: ' + ', '.join(changed))
    else:
        print('Documento já está em dia.')


def clean_db(db_path, verbose=True, *, installed_version=None):
    """Limpa apenas o SQLite explicitamente fornecido pela cópia de distribuição."""
    path = Path(db_path)
    if not path.is_file():
        return False
    try:
        with sqlite3.connect(path) as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ('layout_pieces', 'layouts'):
                if table in tables:
                    db.execute(f'DELETE FROM {table}')
            if 'sessions' in tables:
                db.execute("DELETE FROM sessions WHERE name LIKE '%Teste%' OR name LIKE '%Test%' OR name LIKE '%Empty%' OR name LIKE '%Exclusao%' OR name LIKE '%Refazer%'")
                db.execute("UPDATE sessions SET placed_pieces_json='[]', yield_percent=0, cutting_time_sec=0, status='Stand by'")
                if 'settings' in tables:
                    last = db.execute('SELECT id FROM sessions ORDER BY id DESC LIMIT 1').fetchone()
                    if last:
                        db.execute("REPLACE INTO settings (`key`,`value`) VALUES ('last_active_session_id',?)", (str(last[0]),))
                    else:
                        db.execute("DELETE FROM settings WHERE `key`='last_active_session_id'")
            if 'sqlite_sequence' in tables:
                db.execute("DELETE FROM sqlite_sequence WHERE name IN ('layouts','layout_pieces')")
            if installed_version and 'settings' in tables:
                db.execute("REPLACE INTO settings (`key`,`value`) VALUES ('installed_version',?)", (installed_version,))
            db.commit()
            db.execute('VACUUM')
        if verbose:
            print(f'Banco de distribuição preparado: {path}')
        return True
    except sqlite3.Error as exc:
        if verbose:
            print(f'Falha ao preparar o banco de distribuição: {exc}')
        return False


def prepare_distribution_database(stage):
    """Cria um banco novo na cópia isolada; não copia dados da instalação."""
    for suffix in ('', '-wal', '-shm'):
        (stage/('jobmanager.db'+suffix)).unlink(missing_ok=True)
    command([sys.executable, '-c', 'from database import DatabaseManager; DatabaseManager()'],
            stage, env=isolated_env(stage))


def linux_shortcut_installer(version):
    return LINUX_SHORTCUT_TEMPLATE.replace('@VERSAO@', version)


def windows_shortcut_installer():
    return WINDOWS_SHORTCUT_TEMPLATE


def package_distribution(stage, executable, version, platform=None):
    """Produz o ZIP/TAR.GZ e os instaladores de atalhos a partir deste arquivo."""
    platform = platform or sys.platform
    dist = stage/'dist'
    dist.mkdir(exist_ok=True)
    (dist/'versao.txt').write_text(version, encoding='utf-8')
    artifacts = [executable, dist/'versao.txt']
    with tempfile.TemporaryDirectory(prefix='opencorte-package-') as temp:
        package = Path(temp)/'CorteAC'
        package.mkdir()
        windows = platform == 'win32'
        name = 'CorteAC.exe' if windows else 'corteac_linux'
        shutil.copy2(executable, package/name)
        for source, target in [('db.example.ini','db.example.ini'),
                               ('README_WINDOWS.txt' if windows else 'README_LINUX.txt',
                                'README_WINDOWS.txt' if windows else 'README_LINUX.txt')]:
            shutil.copy2(stage/source, package/target)
        if windows:
            (package/'criar_atalho_windows.ps1').write_text(windows_shortcut_installer(), encoding='utf-8-sig')
            shutil.copy2(package/'criar_atalho_windows.ps1', dist/'criar_atalho_windows.ps1')
            shutil.copy2(dist/'versao.txt', package/'versao.txt')
            archive = dist/'CorteAC-Windows-x64.zip'
            with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as output:
                for path in sorted(package.rglob('*')):
                    if path.is_file():
                        output.write(path,path.relative_to(package))
            artifacts.append(dist/'criar_atalho_windows.ps1')
        else:
            shutil.copy2(stage/'assets/app_icon.png', package/'corteac.png')
            (package/'instalar_atalho.sh').write_text(linux_shortcut_installer(version), encoding='utf-8')
            (package/'run.sh').write_text('#!/usr/bin/env bash\nset -e\nDIR="$(cd "$(dirname "$0")" && pwd)"\nexec "$DIR/corteac_linux" "$@"\n', encoding='utf-8')
            for name in ('corteac_linux','instalar_atalho.sh','run.sh'):
                (package/name).chmod(0o755)
            alias = dist/'corteac_linux'
            if executable != alias:
                shutil.copy2(executable,alias)
            artifacts.append(alias)
            archive = dist/'CorteAC-Linux-x64.tar.gz'
            with tarfile.open(archive,'w:gz') as output:
                output.add(package,arcname='CorteAC')
        artifacts.append(archive)
    return artifacts


def windows_installer_compiler():
    for name in ('ISCC.exe','ISCC'):
        found = shutil.which(name)
        if found:
            return found
    path = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)'))/'Inno Setup 6/ISCC.exe'
    return str(path) if path.is_file() else None


def build_windows_installer(stage, version, compiler):
    command([compiler,f'/DMyAppVersion={version}',stage/'packaging/corteac_setup.iss'],stage)
    artifact = stage/'dist'/f'CorteAC-Setup-{version}.exe'
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise UpdateError('O Inno Setup não gerou o instalador Windows esperado.')
    return artifact


def build_distribution(stage):
    """Única receita PyInstaller para build local e para o GitHub Actions."""
    windows = sys.platform == 'win32'
    if not windows and not sys.platform.startswith('linux'):
        raise UpdateError('Build suportada em Linux e Windows.')
    args = [sys.executable,'-m','PyInstaller','--clean','--noconfirm','--onefile']
    if windows:
        args.extend(['--noconsole','--icon','assets/app_icon.ico'])
    for source, target in [('assets','assets'),('samples','samples'),('jobmanager.db','.'),('db.example.ini','.')]:
        args.extend(['--add-data',f'{source}{os.pathsep}{target}'])
    modules = ['pymysql','cryptography','cad.project_packager','cad.barcode','cad.layout_converter',
               'cad.czlib','cad.onx_exporter','cad.dual_exporter','cad.shape_backup',
               'cad.shape_backup_scheduler','ui.user_dialog','ui.layout_converter_dialog',
               'ui.production_dashboard','analytics.production_dashboard',
               'ui.shape_backup_restore_dialog','ui.alter_sheet_dialog']
    for module in modules:
        args.extend(['--hidden-import',module])
    args.extend(['--name','CorteAC','main.py'])
    env = isolated_env(stage)
    command(args,stage,env=env)
    executable = stage/'dist'/('CorteAC.exe' if windows else 'CorteAC')
    reported = command([executable,'--version'],stage,capture=True,env=env,timeout=60)
    version = current_version(stage)
    if reported.split()[-1:] != [version]:
        raise UpdateError('O executável gerado não confirmou a versão esperada.')
    artifacts = package_distribution(stage,executable,version)
    if windows:
        compiler = windows_installer_compiler()
        if compiler:
            artifacts.append(build_windows_installer(stage,version,compiler))
        elif os.environ.get('GITHUB_ACTIONS') == 'true':
            raise UpdateError('Inno Setup ausente no runner Windows.')
        else:
            print('Inno Setup não encontrado: exe e ZIP gerados; o instalador oficial será gerado no GitHub.')
    return artifacts


def build_only(root):
    """Modo de CI/compilação: sem alterar versão, GitHub ou Área de Trabalho."""
    version = current_version(root)
    ref = os.environ.get('GITHUB_REF','')
    requested_tag = os.environ.get('OPEN_CORTE_TAG','')
    tag = ref.removeprefix('refs/tags/') if ref.startswith('refs/tags/') else requested_tag
    if tag and tag != 'v'+version:
        raise UpdateError(f'A tag {tag} não coincide com APP_VERSION={version}.')
    stage = Path(tempfile.mkdtemp(prefix='opencorte-ci-build-'))
    snapshot(root,stage,source_files(root))
    prepare_distribution_database(stage)
    if not clean_db(stage/'jobmanager.db', installed_version=version):
        raise UpdateError('Falha ao preparar banco de distribuição.')
    artifacts = build_distribution(stage)
    for artifact in artifacts:
        atomic_copy(artifact,root/'dist'/artifact.name,root/'.release/backups'/version)
    print(f'Build {version} concluída em {root/"dist"}.')


class Updater:
    def __init__(self, root, args):
        self.root, self.args = root, args
        self.state_path = root / '.release' / 'estado.json'
        self.state = {}

    def save(self):
        self.state_path.parent.mkdir(exist_ok=True)
        temp = self.state_path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, self.state_path)

    def phase(self, name, action):
        if name in self.state['done']:
            print(f'Já concluído: {name}', flush=True)
            return
        print(f'\n>>> {name}', flush=True)
        self.state['current'] = name
        self.save()
        action()
        self.state['done'].append(name)
        self.save()

    def start(self):
        root = self.root
        branch = git(root, 'branch', '--show-current')
        if not branch:
            raise UpdateError('Selecione uma branch antes de atualizar; HEAD está destacado.')
        repo = repository_name(git(root, 'remote', 'get-url', 'origin'))
        version = current_version(root)
        previous = json.loads(self.state_path.read_text()) if self.state_path.exists() else None
        if self.args.retomar:
            if not previous or previous.get('complete'):
                raise UpdateError('Não há atualização pendente para retomar.')
            self.state = previous
            if (self.state['branch'], self.state['repo']) != (branch, repo):
                raise UpdateError('A branch/origin não coincide com a atualização pendente.')
            target = self.state['version']
        else:
            if previous and not previous.get('complete'):
                raise UpdateError('Há atualização pendente. Use --retomar, sem gerar outra versão.')
            target = next_version(version, self.args.incremento)
            self.state = dict(version=target, branch=branch, repo=repo, done=[], complete=False)
        print(f'OpenCorte: {version} → {target} | origin: {repo} | branch: {branch}')
        files = source_files(root)
        print(f'{len(files)} arquivos de fonte elegíveis; bancos, db.ini, credenciais e binários locais ficam fora do commit.')
        if self.args.simular:
            print('SIMULAÇÃO: versão → documentação → cópia isolada → verificações → build local → Área de Trabalho → commit/tag → push atômico → builds Windows/Linux e release no GitHub.')
            print('Nenhum arquivo, versão, atalho, commit ou tag foi alterado.')
            return
        api = GitHub(repo)
        api.get('actions/workflows/release.yml')  # acesso de leitura, sem exigir gh CLI
        if not self.args.retomar and git(root, 'diff', '--cached', '--name-only'):
            raise UpdateError('O índice Git já contém arquivos preparados. Faça commit ou retire-os do índice antes de iniciar.')
        git(root, 'var', 'GIT_AUTHOR_IDENT')
        if not self.args.retomar:
            git(root, 'fetch', 'origin', branch)
            try:
                git(root, 'merge-base', '--is-ancestor', 'FETCH_HEAD', 'HEAD')
            except UpdateError as exc:
                raise UpdateError('O GitHub tem commits que faltam nesta branch. Integre-os antes de iniciar a atualização.') from exc
            existing = git(root, 'ls-remote', '--tags', 'origin', f'refs/tags/v{target}')
            if existing or git(root, 'tag', '--list', f'v{target}'):
                raise UpdateError(f'A tag v{target} já existe. Revise APP_VERSION antes de continuar.')
            command([sys.executable, '-c', 'import PyInstaller, pytest'], root)
            self.state['base'] = git(root, 'rev-parse', 'HEAD')
        if self.args.retomar and 'commit' not in self.state['done'] and git(root, 'rev-parse', 'HEAD') != self.state['base']:
            message = f"chore(release): OpenCorte v{target}"
            expected = self.state.get('fingerprints', {})
            if (git(root, 'log', '-1', '--format=%s') != message
                    or git(root, 'rev-parse', 'HEAD^') != self.state['base']
                    or fingerprint(root, self.state['files']) != expected
                    or set(source_files(root)) - set(self.state['files'])
                    or git(root, 'diff', '--name-only', 'HEAD', '--', *self.state['files'])):
                raise UpdateError('HEAD mudou antes de registrar o commit. Confira a revisão e os fontes da atualização pendente.')
            self.state['sha'] = git(root, 'rev-parse', 'HEAD')
            self.state['done'].append('commit')
        if 'commit' in self.state['done']:
            if git(root, 'rev-parse', 'HEAD') != self.state['sha']:
                raise UpdateError('HEAD mudou após o commit da atualização. Retome na revisão registrada.')
        elif self.args.retomar:
            expected = self.state.get('fingerprints')
            if expected and (fingerprint(root, self.state['files']) != expected
                             or set(source_files(root)) - set(self.state['files'])
                             or not Path(self.state.get('stage', '')).is_dir()):
                self.state['done'] = []  # mesma versão; recompila o código corrigido
        self.save()
        self.phase('versão e documentação', self.prepare)
        self.phase('verificações e build isolada', self.build)
        self.phase('binários e Área de Trabalho', self.install)
        self.phase('commit', self.commit)
        self.phase('tag', self.tag)
        self.phase('push', lambda: git(root, 'push', '--atomic', 'origin',
                   f'HEAD:refs/heads/{branch}', f'refs/tags/v{target}:refs/tags/v{target}'))
        self.phase('builds e release no GitHub', lambda: self.confirm_release(api))
        self.state['complete'] = True
        self.state['current'] = 'concluído'
        self.save()
        print(f"\nAtualização v{target} concluída.\n{self.state['release_url']}", flush=True)

    def prepare(self):
        set_version(self.root,self.state['version'])
        sync_documentation(self.root)
        sync_documentation(self.root,check=True)
        files = source_files(self.root)
        self.state['files'] = files
        self.state['fingerprints'] = fingerprint(self.root, files)
        stage = Path(tempfile.mkdtemp(prefix='opencorte-build-'))
        self.state['stage'] = str(stage)
        snapshot(self.root, stage, files)
        self.save()

    def build(self):
        stage = Path(self.state['stage'])
        if not stage.exists():
            raise UpdateError('A cópia de build foi removida. Faça uma alteração de fonte ou refaça a preparação antes de retomar.')
        env = isolated_env(stage)
        prepare_distribution_database(stage)
        checks = [p for p in CHECKS if (stage / p).is_file()]
        if not checks:
            raise UpdateError('Nenhuma verificação de release encontrada na cópia.')
        command([sys.executable, '-m', 'pytest', '-q', *checks], stage, env=env)
        if not clean_db(stage/'jobmanager.db', installed_version=self.state['version']):
            raise UpdateError('Falha ao preparar o banco da cópia de build.')
        with sqlite3.connect(stage/'jobmanager.db') as db:
            if db.execute('SELECT count(*) FROM layouts').fetchone()[0]:
                raise UpdateError('O banco de distribuição ainda contém layouts.')
        build_distribution(stage)
        executable = stage/'dist'/('CorteAC.exe' if sys.platform=='win32' else 'CorteAC')
        self.state['verified_binary'] = hashlib.sha256(executable.read_bytes()).hexdigest()

    def install(self):
        stage = Path(self.state['stage'])
        backup = self.root/'.release/backups'/self.state['version']
        source = stage / ('dist/CorteAC' if sys.platform.startswith('linux') else 'dist/CorteAC.exe')
        if hashlib.sha256(source.read_bytes()).hexdigest() != self.state['verified_binary']:
            raise UpdateError('O binário mudou após a verificação.')
        if sys.platform.startswith('linux'):
            for name in ('corteac_linux', 'teste_dola_linux', 'dist/CorteAC', 'dist/corteac_linux', 'dist/teste_dola'):
                atomic_copy(source, self.root/name, backup)
            atomic_copy(stage/'dist/CorteAC-Linux-x64.tar.gz', self.root/'dist/CorteAC-Linux-x64.tar.gz', backup)
            spec = importlib.util.spec_from_file_location('update_shortcut', self.root/'ui/desktop_shortcut.py')
            shortcuts = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(shortcuts)
            if not shortcuts._desktop_dirs():
                desktop = Path.home()/'Desktop'
                if shutil.which('xdg-user-dir'):
                    value = command(['xdg-user-dir', 'DESKTOP'], capture=True)
                    if value:
                        desktop = Path(value)
                desktop.mkdir(parents=True, exist_ok=True)
            result = shortcuts.sincronizar_atalho(self.state['version'],
                exe_path=str(self.root/'corteac_linux'), icon_path=str(self.root/'assets/app_icon.png'),
                criar_se_ausente=True)
            desktop_dirs = shortcuts._desktop_dirs()
            if result.get('erro') or not any(Path(p).parent in desktop_dirs for p in result.get('criados', [])):
                raise UpdateError('Não foi possível atualizar a Área de Trabalho: ' + str(result.get('erro')))
            self.state['shortcuts'] = result['criados']
        else:
            atomic_copy(stage/'dist/CorteAC.exe', self.root/'dist/CorteAC.exe', backup)
            atomic_copy(stage/'dist/CorteAC-Windows-x64.zip', self.root/'dist/CorteAC-Windows-x64.zip', backup)
            installer = stage/'dist'/f'CorteAC-Setup-{self.state["version"]}.exe'
            if installer.exists():
                atomic_copy(installer,self.root/'dist'/installer.name,backup)
            (self.root/'dist/criar_atalho_windows.ps1').write_text(windows_shortcut_installer(),encoding='utf-8-sig')
            (self.root/'dist/versao.txt').write_text(self.state['version'])
            command(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                     self.root/'dist/criar_atalho_windows.ps1'], self.root)
        print('Binários locais e atalho atualizados; cópias anteriores em .release/backups/.', flush=True)

    def commit(self):
        if fingerprint(self.root, source_files(self.root)) != self.state['fingerprints']:
            raise UpdateError('Os fontes mudaram durante a build. Use --retomar para recompilar antes do commit.')
        message = f"chore(release): OpenCorte v{self.state['version']}"
        # Recupera interrupção ocorrida entre git commit e gravação do estado.
        head = git(self.root, 'rev-parse', 'HEAD')
        if head != self.state['base']:
            if git(self.root, 'log', '-1', '--format=%s') != message:
                raise UpdateError('HEAD mudou durante a atualização; revise os commits antes de retomar.')
        else:
            files = self.state['files']
            staged = set(git(self.root, 'diff', '--cached', '--name-only').splitlines())
            if staged - set(files):
                raise UpdateError('Há arquivos adicionais preparados no índice Git.')
            for offset in range(0, len(files), 100):
                git(self.root, 'add', '-A', '--', *files[offset:offset+100])
            git(self.root, 'commit', '-m', message)
        if (fingerprint(self.root, self.state['files']) != self.state['fingerprints']
                or git(self.root, 'diff', '--name-only', 'HEAD', '--', *self.state['files'])):
            raise UpdateError('O commit diverge dos fontes da build, possivelmente por um hook Git. Revise antes de publicar.')
        self.state['sha'] = git(self.root, 'rev-parse', 'HEAD')

    def tag(self):
        tag = 'v'+self.state['version']
        if git(self.root, 'tag', '--list', tag):
            if git(self.root, 'rev-list', '-n', '1', tag) != self.state['sha']:
                raise UpdateError('A tag existente aponta para outro commit.')
        else:
            git(self.root, 'tag', '-a', tag, '-m', f'OpenCorte {tag}')

    def confirm_release(self, api):
        self.state['release_url'] = api.wait_release(self.state['sha'], 'v'+self.state['version'],
                                                   self.state['version'], self.args.espera)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--simular', action='store_true', help='mostra as etapas, sem alterar nada nem acessar a rede')
    parser.add_argument('--incremento', choices=['patch', 'minor', 'major'], default='patch')
    parser.add_argument('--retomar', action='store_true', help='continua a mesma versão após uma falha')
    parser.add_argument('--espera', type=int, default=60, help='limite em minutos para o GitHub (padrão: 60)')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--documentacao',action='store_true',help='somente sincronizar o documento mestre')
    mode.add_argument('--build',action='store_true',help='somente build e pacote em cópia isolada (também usado no CI)')
    parser.add_argument('--check',action='store_true',help='com --documentacao, somente verificar atualização')
    args = parser.parse_args(argv)
    if args.espera <= 0:
        parser.error('--espera deve ser positivo')
    if args.check and not args.documentacao:
        parser.error('--check requer --documentacao')
    if (args.documentacao or args.build) and (args.simular or args.retomar):
        parser.error('os modos individuais não aceitam --simular ou --retomar')
    updater = Updater(ROOT, args)
    try:
        if args.documentacao:
            sync_documentation(ROOT,check=args.check)
        elif args.build:
            with execution_lock(ROOT):
                build_only(ROOT)
        elif args.simular:
            updater.start()
        else:
            with execution_lock(ROOT):
                updater.start()
        return 0
    except (UpdateError, OSError, ValueError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        try:
            pending = updater.state_path.exists() and not json.loads(updater.state_path.read_text()).get('complete')
        except (OSError, ValueError):
            pending = False
        if args.documentacao:
            retry = 'python3 atualizar.py --documentacao'
        elif args.build:
            retry = 'python3 atualizar.py --build'
        else:
            retry = 'python3 atualizar.py --retomar' if pending else 'python3 atualizar.py'
        print(f'\nAtualização interrompida: {exc}\nApós resolver, execute: {retry}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
