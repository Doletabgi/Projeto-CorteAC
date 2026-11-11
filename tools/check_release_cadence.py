#!/usr/bin/env python3
"""
Verificador de Cadência de Release (Regra dos 5 Commits)
Sistema de Versionamento SemVer (MAJOR.MINOR.PATCH)
Projeto CorteAC / ATOM JobManager Reborn

Calcula a quantidade de commits acumulados desde a última tag de release e
aplica as regras SemVer definidas:
- MAJOR: 1.0.0 → 2.0.0 (Mudanças grandes que podem exigir adaptações)
- MINOR: 1.0.0 → 1.1.0 (Novas funcionalidades sem quebrar a compatibilidade)
- PATCH: 1.0.0 → 1.0.1 (Correções de erros e falhas de segurança)
"""

import sys
import subprocess
from pathlib import Path

# Garante acesso ao módulo tools.semver
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools.semver import SemVer, get_current_version, analyze_commits_for_bump

CADENCE_TARGET = 5


def run_git(*args):
    try:
        res = subprocess.run(
            ["git", *args],
            cwd=ROOT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return ""


def check_cadence():
    latest_tag = run_git("describe", "--tags", "--abbrev=0")
    if not latest_tag:
        latest_tag = "v1.0.0"

    current_app_version = get_current_version()
    try:
        current_sem = SemVer.parse(current_app_version)
    except ValueError:
        current_sem = SemVer(1, 0, 0)

    # Contar commits desde a última tag
    count_str = run_git("rev-list", "--count", f"{latest_tag}..HEAD")
    count = int(count_str) if count_str.isdigit() else 0

    bump_type, bump_reason, commits = analyze_commits_for_bump(latest_tag)
    suggested_sem = current_sem.bump(bump_type)

    print("=" * 68)
    print(f"📦 CorteAC — Status da Cadência de Releases (SemVer MAJOR.MINOR.PATCH)")
    print("=" * 68)
    print(f"• Padrão de Versão    : MAJOR.MINOR.PATCH (ex: 1.2.3)")
    print(f"• Versão no config.py : {current_app_version}")
    print(f"• Última Tag no Git   : {latest_tag}")
    print(f"• Commits acumulados  : {count} de {CADENCE_TARGET}")

    print("\n📋 Tabela de Regras SemVer:")
    print("  Tipo   Exemplo         Quando utilizar")
    print("  MAJOR  1.0.0 → 2.0.0   Mudanças grandes que podem exigir adaptações.")
    print("  MINOR  1.0.0 → 1.1.0   Novas funcionalidades sem quebrar a compatibilidade.")
    print("  PATCH  1.0.0 → 1.0.1   Correções de erros e falhas de segurança.")

    if count >= CADENCE_TARGET:
        print("\n🚀 [ALERTA DE CADÊNCIA ATINGIDA]")
        print(f"Foram acumulados {count} commits desde a tag {latest_tag}!")
        print(f"➡️  Próxima versão recomendada ({bump_type.upper()}): {current_sem} ➔ {suggested_sem} ({suggested_sem.tag})")
        print(f"    Motivo: {bump_reason}")
        print("\n📝 Commits acumulados neste ciclo:")
        for c in commits:
            print(f"   • {c}")
        print("\n📋 Passos automatizados para publicar:")
        print(f"   1. Executar bump: python3 tools/semver.py bump {bump_type}")
        print(f"   2. Atualizar notas em .github/workflows/release.yml")
        print(f"   3. Sincronizar doc: python3 tools/sync_project_doc.py")
        print(f"   4. Commit: git commit -am \"chore(release): lancamento da versao {suggested_sem.tag}\"")
        print(f"   5. Tag e Push: git tag -a {suggested_sem.tag} -m \"CorteAC {suggested_sem.tag}\" && git push origin master --tags")
    else:
        remaining = CADENCE_TARGET - count
        print(f"\n✅ Cadência em andamento: faltam {remaining} commit(s) para a próxima release ({bump_type.upper()}: {suggested_sem.tag}).")
        if count > 0:
            print("\n📝 Commits acumulados até agora:")
            for c in commits:
                print(f"   • {c}")
    print("=" * 68)


if __name__ == "__main__":
    check_cadence()
