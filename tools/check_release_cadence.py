#!/usr/bin/env python3
"""
Verificador de Cadência de Release (Regra dos 5 Commits)
Projeto CorteAC / ATOM JobManager Reborn

Calcula a quantidade de commits acumulados desde a última tag de release.
Regra definida no PROJETO_ATOM_JOBMANAGER.md (Seção 12):
A cada 5 commits, uma nova versão de release (v2026.X) deve ser publicada no GitHub.
"""

import sys
import subprocess
from pathlib import Path

CADENCE_TARGET = 5

def run_git(*args):
    try:
        res = subprocess.run(
            ["git", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return ""

def get_current_app_version():
    root = Path(__file__).resolve().parent.parent
    config_py = root / "config.py"
    if config_py.exists():
        content = config_py.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("APP_VERSION"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "2026.2"

def get_next_version(current_ver):
    parts = current_ver.split(".")
    if len(parts) >= 2 and parts[1].isdigit():
        next_num = int(parts[1]) + 1
        return f"{parts[0]}.{next_num}"
    return f"{current_ver}.1"

def check_cadence():
    latest_tag = run_git("describe", "--tags", "--abbrev=0")
    if not latest_tag:
        latest_tag = "v2026.1"

    current_app_version = get_current_app_version()
    
    # Contar commits desde a última tag
    count_str = run_git("rev-list", "--count", f"{latest_tag}..HEAD")
    count = int(count_str) if count_str.isdigit() else 0

    next_version = get_next_version(current_app_version)

    print("=" * 64)
    print(f"📦 CorteAC — Status da Cadência de Releases (Regra dos {CADENCE_TARGET} Commits)")
    print("=" * 64)
    print(f"• Última Tag Publicada: {latest_tag}")
    print(f"• Versão no config.py : {current_app_version}")
    print(f"• Commits acumulados  : {count} de {CADENCE_TARGET}")

    if count >= CADENCE_TARGET:
        print("\n🚀 [ALERTA DE CADÊNCIA ATINGIDA]")
        print(f"Foram acumulados {count} commits desde a tag {latest_tag}!")
        print(f"➡️  Está na hora de publicar a próxima versão: v{next_version}")
        print("\n📝 Commits acumulados neste ciclo:")
        log_commits = run_git("log", "--oneline", f"{latest_tag}..HEAD")
        for c in log_commits.splitlines():
            print(f"   • {c}")
        print("\n📋 Passos recomendados:")
        print(f"   1. Atualizar config.py para APP_VERSION = \"{next_version}\"")
        print(f"   2. Atualizar notas em .github/workflows/release.yml")
        print(f"   3. Rodar: python3 tools/sync_project_doc.py")
        print(f"   4. Commit: git commit -am \"chore(release): lancamento da versao v{next_version}\"")
        print(f"   5. Tag e Push: git tag -a v{next_version} -m \"CorteAC v{next_version}\" && git push origin master --tags")
    else:
        remaining = CADENCE_TARGET - count
        print(f"\n✅ Cadência em andamento: faltam {remaining} commit(s) para a próxima release (v{next_version}).")
        if count > 0:
            print("\n📝 Commits acumulados até agora:")
            log_commits = run_git("log", "--oneline", f"{latest_tag}..HEAD")
            for c in log_commits.splitlines():
                print(f"   • {c}")
    print("=" * 64)

if __name__ == "__main__":
    check_cadence()
