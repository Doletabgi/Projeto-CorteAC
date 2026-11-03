"""
ui/desktop_shortcut.py

Mantém o atalho da Área de Trabalho/Menu do CorteAC com a VERSÃO no nome.

Roda no início da aplicação (Linux): se já existir QUALQUER atalho do CorteAC —
inclusive os antigos, criados à mão, com nome fixo "CorteAC" — ele é substituído
por `corteac-<versão>.desktop` (nome "CorteAC-<versão>"), apontando para o
executável e o ícone atuais. Sem atalho existente, nada é criado (não invadimos a
mesa do operador sem ele ter um atalho).

No Windows o atalho é criado pelo `criar_atalho_windows.ps1` do pacote.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _desktop_dirs() -> list[Path]:
    """Pastas de Área de Trabalho possíveis (inclui o padrão pt-BR do Mint)."""
    dirs: list[Path] = []
    try:
        out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=5)
        alvo = (out.stdout or "").strip()
        if alvo:
            dirs.append(Path(alvo))
    except Exception:
        pass
    home = Path.home()
    for nome in ("Desktop", "Área de Trabalho", "Area de Trabalho"):
        p = home / nome
        if p not in dirs:
            dirs.append(p)
    return [d for d in dirs if d.is_dir()]


def _atalhos_existentes(apps_dir: Path, desktops: list[Path]) -> list[Path]:
    """Todos os .desktop do CorteAC (nome antigo ou versionado) no menu e na mesa."""
    achados: list[Path] = []
    locais = [apps_dir] + desktops
    for base in locais:
        if not base.is_dir():
            continue
        for p in base.glob("*.desktop"):
            nome = p.name.lower()
            if nome.startswith("corteac") or nome.startswith("corteac-"):
                achados.append(p)
    return achados


def _conteudo_desktop(nome: str, versao: str, exe: Path, diretorio: Path, icone: Path) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={nome}\n"
        "GenericName=Encaixe e Corte\n"
        f"Comment=JobManager 2000 Reborn - encaixe de couro e corte CAM (v{versao})\n"
        f'Exec="{exe}"\n'
        f"Path={diretorio}\n"
        f"Icon={icone}\n"
        "Terminal=false\n"
        "Categories=Graphics;Engineering;\n"
        "StartupWMClass=corteac_linux\n"
        f"X-CorteAC-Version={versao}\n"
    )


def _instalar_icone(origem: Path) -> Path:
    """
    Copia o ícone para um caminho estável (~/.local/share/corteac/corteac.png).

    O executável PyInstaller guarda os assets dentro do próprio binário; o atalho
    precisa de um arquivo real no disco, então mantemos uma cópia de referência.
    """
    try:
        destino_dir = Path.home() / ".local" / "share" / "corteac"
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / "corteac.png"
        if origem.exists():
            shutil.copyfile(origem, destino)
        if destino.exists():
            return destino
    except Exception:
        pass
    return origem


def sincronizar_atalho(versao: str, exe_path: Optional[str] = None, icon_path: Optional[str] = None,
                       criar_se_ausente: bool = False) -> dict:
    """
    Atualiza (ou cria, se `criar_se_ausente`) o atalho para a versão atual.

    Retorna {"acao": "atualizado"|"criado"|"nenhum"|"indisponivel", "criados": [...], "removidos": [...], "erro": str|None}
    """
    resultado = {"acao": "nenhum", "criados": [], "removidos": [], "erro": None}
    if not sys.platform.startswith("linux"):
        resultado["acao"] = "indisponivel"
        return resultado

    exe = Path(exe_path or sys.executable)
    diretorio = exe.parent
    icone = Path(icon_path) if icon_path else (diretorio / "corteac.png")
    if not icone.exists():
        # No pacote PyInstaller o ícone viaja embutido; usa o do bundle quando existir
        bundle = Path(getattr(sys, "_MEIPASS", diretorio)) / "assets" / "app_icon.png"
        if bundle.exists():
            icone = bundle

    apps_dir = Path.home() / ".local" / "share" / "applications"
    desktops = _desktop_dirs()

    try:
        existentes = _atalhos_existentes(apps_dir, desktops)
    except Exception as exc:  # noqa: BLE001
        resultado["erro"] = str(exc)
        return resultado

    if not existentes and not criar_se_ausente:
        return resultado  # não cria atalho do nada sem o operador pedir

    icone = _instalar_icone(icone)
    nome = f"CorteAC-{versao}"
    arq = f"corteac-{versao.lower()}.desktop"
    conteudo = _conteudo_desktop(nome, versao, exe, diretorio, icone)

    # Remove os atalhos antigos (inclusive versionados de outra versão)
    for antigo in existentes:
        try:
            if antigo.name == arq:
                continue
            antigo.unlink()
            resultado["removidos"].append(str(antigo))
        except Exception:
            pass

    alvos = [apps_dir / arq]  # menu de aplicativos (criado se não existir)
    for d in desktops:
        alvos.append(d / arq)

    for alvo in alvos:
        try:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text(conteudo, encoding="utf-8")
            alvo.chmod(0o755)
            resultado["criados"].append(str(alvo))
            try:
                subprocess.run(["gio", "set", str(alvo), "metadata::trusted", "true"],
                               capture_output=True, timeout=5)
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            resultado["erro"] = str(exc)

    try:
        subprocess.run(["update-desktop-database", str(apps_dir)], capture_output=True, timeout=5)
    except Exception:
        pass

    if resultado["criados"]:
        resultado["acao"] = "atualizado" if existentes else "criado"
    return resultado
