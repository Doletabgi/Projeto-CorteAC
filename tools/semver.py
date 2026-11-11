#!/usr/bin/env python3
"""
Sistema de Versionamento SemVer (Semantic Versioning 2.0.0)
Padrão MAJOR.MINOR.PATCH para CorteAC / ATOM JobManager Reborn

Regras de Versionamento:
• MAJOR: 1.0.0 → 2.0.0 (Mudanças grandes que podem exigir adaptações / breaking changes)
• MINOR: 1.0.0 → 1.1.0 (Novas funcionalidades sem quebrar a compatibilidade / feat)
• PATCH: 1.0.0 → 1.0.1 (Correções de erros e falhas de segurança / fix, docs, chore, build)
"""

import re
import sys
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, List

SEMVER_REGEX = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


@dataclass
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None

    @classmethod
    def parse(cls, version_str: str) -> "SemVer":
        version_str = str(version_str).strip()
        m = SEMVER_REGEX.match(version_str)
        if not m:
            raise ValueError(
                f"Versão inválida: '{version_str}'. Deve seguir o padrão MAJOR.MINOR.PATCH (ex: 1.0.0, 1.2.3)."
            )
        return cls(
            major=int(m.group("major")),
            minor=int(m.group("minor")),
            patch=int(m.group("patch")),
            prerelease=m.group("prerelease"),
            build=m.group("buildmetadata"),
        )

    def bump_major(self) -> "SemVer":
        """Incrementa versão principal (mudanças grandes / incompatíveis). Reseta MINOR e PATCH."""
        return SemVer(major=self.major + 1, minor=0, patch=0)

    def bump_minor(self) -> "SemVer":
        """Incrementa versão secundária (novas funcionalidades compatíveis). Reseta PATCH."""
        return SemVer(major=self.major, minor=self.minor + 1, patch=0)

    def bump_patch(self) -> "SemVer":
        """Incrementa correção (correções de bugs, manutenção, sem novas features)."""
        return SemVer(major=self.major, minor=self.minor, patch=self.patch + 1)

    def bump(self, level: str) -> "SemVer":
        lvl = str(level).strip().lower()
        if lvl == "major":
            return self.bump_major()
        elif lvl == "minor":
            return self.bump_minor()
        elif lvl == "patch":
            return self.bump_patch()
        else:
            raise ValueError(f"Nível de bump inválido: '{level}'. Use: 'major', 'minor' ou 'patch'.")

    def __str__(self) -> str:
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += f"-{self.prerelease}"
        if self.build:
            s += f"+{self.build}"
        return s

    @property
    def tag(self) -> str:
        return f"v{self}"

    def tuple(self) -> Tuple[int, int, int]:
        return (self.major, self.minor, self.patch)


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_current_version() -> str:
    config_py = get_repo_root() / "config.py"
    if config_py.exists():
        content = config_py.read_text(encoding="utf-8")
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("APP_VERSION"):
                return line_str.split("=")[1].strip().strip('"').strip("'")
    return "1.0.0"


def update_config_py(new_version: str) -> bool:
    sem = SemVer.parse(new_version)
    config_py = get_repo_root() / "config.py"
    if not config_py.exists():
        return False
    content = config_py.read_text(encoding="utf-8")
    lines = content.splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith("APP_VERSION"):
            lines[i] = f'APP_VERSION = "{sem}"'
            found = True
            break
    if found:
        config_py.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    return False


def update_release_workflow(new_version: str) -> bool:
    sem = SemVer.parse(new_version)
    wf_path = get_repo_root() / ".github" / "workflows" / "release.yml"
    if not wf_path.exists():
        return False
    content = wf_path.read_text(encoding="utf-8")
    new_content = re.sub(
        r"(default:\s*['\"]v)[0-9a-zA-Z.-]+(['\"])",
        rf"\g<1>{sem}\g<2>",
        content,
        count=1
    )
    if new_content != content:
        wf_path.write_text(new_content, encoding="utf-8")
        return True
    return False


def set_version(new_version: str, update_files: bool = True) -> SemVer:
    sem = SemVer.parse(new_version)
    if update_files:
        update_config_py(str(sem))
        update_release_workflow(str(sem))
    return sem


def analyze_commits_for_bump(from_ref: Optional[str] = None) -> Tuple[str, str, List[str]]:
    """
    Analisa os commits acumulados desde from_ref segundo Conventional Commits:
    - BREAKING CHANGE ou !: -> major
    - feat(...) ou feat: -> minor
    - fix, chore, docs, build, etc. -> patch
    """
    args = ["log", "--oneline"]
    if from_ref:
        args.append(f"{from_ref}..HEAD")
    else:
        args.extend(["-n", "10"])

    try:
        res = subprocess.run(
            ["git", *args],
            cwd=get_repo_root(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        commits = [c.strip() for c in res.stdout.splitlines() if c.strip()]
    except Exception:
        commits = []

    has_breaking = False
    has_feat = False

    for c in commits:
        subj = c.split(" ", 1)[1] if " " in c else c
        lower_subj = subj.lower()
        if "breaking change" in lower_subj or re.search(r"^[a-z]+(\([^\)]+\))?!:", lower_subj):
            has_breaking = True
            break
        if re.search(r"^feat(\([^\)]+\))?:", lower_subj):
            has_feat = True

    if has_breaking:
        return "major", "Mudanças grandes que podem exigir adaptações (Breaking Changes detectadas)", commits
    elif has_feat:
        return "minor", "Novas funcionalidades sem quebrar a compatibilidade (Features detectadas)", commits
    else:
        return "patch", "Correções de erros, melhorias ou manutenção (Sem novas features)", commits


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Uso: python3 tools/semver.py [comando]")
        print("Comandos:")
        print("  get                      Mostra a versão atual configurada em config.py")
        print("  validate <versao>        Verifica se a string segue o padrão MAJOR.MINOR.PATCH")
        print("  bump <patch|minor|major> Incrementa a versão e atualiza os arquivos do projeto")
        print("  set <versao>             Define explicitamente a nova versão SemVer")
        print("  suggest [from_tag]       Analisa commits e sugere o tipo de bump adequado")
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "get":
        print(get_current_version())
    elif cmd == "validate":
        if len(sys.argv) < 3:
            print("Erro: informe a versão para validar.")
            sys.exit(1)
        try:
            sem = SemVer.parse(sys.argv[2])
            print(f"✅ Válida: {sem} (Major={sem.major}, Minor={sem.minor}, Patch={sem.patch})")
        except ValueError as err:
            print(f"❌ {err}")
            sys.exit(1)
    elif cmd == "bump":
        if len(sys.argv) < 3:
            print("Erro: informe o tipo de bump ('patch', 'minor' ou 'major').")
            sys.exit(1)
        level = sys.argv[2]
        current_str = get_current_version()
        current = SemVer.parse(current_str)
        new_sem = current.bump(level)
        set_version(str(new_sem), update_files=True)
        print(f"🚀 Versão atualizada: {current} ➔ {new_sem} (Tag: {new_sem.tag})")
    elif cmd == "set":
        if len(sys.argv) < 3:
            print("Erro: informe a nova versão.")
            sys.exit(1)
        new_ver = sys.argv[2]
        new_sem = set_version(new_ver, update_files=True)
        print(f"🚀 Versão definida: {new_sem} (Tag: {new_sem.tag})")
    elif cmd == "suggest":
        tag = sys.argv[2] if len(sys.argv) > 2 else None
        level, reason, commits = analyze_commits_for_bump(tag)
        current = SemVer.parse(get_current_version())
        next_v = current.bump(level)
        print(f"Sugestão de Versionamento SemVer: {level.upper()} ({current} ➔ {next_v})")
        print(f"Motivo: {reason}")
        if commits:
            print(f"Commits analisados ({len(commits)}):")
            for c in commits:
                print(f"  • {c}")
    else:
        print(f"Comando desconhecido: '{cmd}'")
        sys.exit(1)


if __name__ == "__main__":
    main()
