"""
tests/test_desktop_shortcut.py

Atalho da Área de Trabalho com a VERSÃO no nome (ex.: CorteAC-1.6.11), gerado pelo
template `packaging/instalar_atalho.sh` no empacotamento (build local e CI).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "packaging" / "instalar_atalho.sh"


class TestDesktopShortcut(unittest.TestCase):
    def setUp(self):
        if not sys.platform.startswith("linux"):
            self.skipTest("atalho .desktop é específico do Linux")
        if shutil.which("bash") is None:
            self.skipTest("bash indisponível")
        if not TEMPLATE.exists():
            self.fail(f"template ausente: {TEMPLATE}")

    def _montar_pacote(self, tmp: Path, versao: str, binario_reporta: str | None = None):
        pkg = tmp / "CorteAC"
        pkg.mkdir()
        (pkg / "corteac.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        binario = pkg / "corteac_linux"
        saida = binario_reporta or f"CorteAC {versao}"
        binario.write_text(f"#!/usr/bin/env bash\necho '{saida}'\n")
        binario.chmod(0o755)
        script = (TEMPLATE.read_text()).replace("@VERSAO@", versao)
        dest = pkg / "instalar_atalho.sh"
        dest.write_text(script)
        dest.chmod(0o755)
        return pkg

    def _rodar(self, pkg: Path, home: Path):
        env = dict(os.environ)
        env["HOME"] = str(home)
        env.pop("XDG_DESKTOP_DIR", None)
        return subprocess.run(["bash", str(pkg / "instalar_atalho.sh")], env=env,
                              capture_output=True, text=True, timeout=60)

    def test_at_shortcut_tem_versao_no_nome_e_no_conteudo(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            home = tmp / "home"
            (home / "Desktop").mkdir(parents=True)
            pkg = self._montar_pacote(tmp, "1.6.11")
            res = self._rodar(pkg, home)
            self.assertEqual(res.returncode, 0, res.stderr)

            apps = home / ".local/share/applications"
            desk_file = apps / "corteac-1.6.11.desktop"
            self.assertTrue(desk_file.exists(), f"atalho esperado em {desk_file}")
            conteudo = desk_file.read_text()
            self.assertIn("Name=CorteAC-1.6.11", conteudo)
            self.assertIn("X-CorteAC-Version=1.6.11", conteudo)
            self.assertIn('Exec="', conteudo)  # caminho aspeado (espaços)
            self.assertIn(str(pkg / "corteac.png"), conteudo)

            desktop_copy = home / "Desktop" / "corteac-1.6.11.desktop"
            self.assertTrue(desktop_copy.exists(), "atalho não copiado para a Área de Trabalho")

    def test_versao_lida_do_binario(self):
        """Se o binário responde --version, ele manda (não o @VERSAO@ do template)."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            home = tmp / "home"
            (home / "Desktop").mkdir(parents=True)
            pkg = self._montar_pacote(tmp, "0.0.0", binario_reporta="CorteAC 2.5.7")
            res = self._rodar(pkg, home)
            self.assertEqual(res.returncode, 0, res.stderr)
            apps = home / ".local/share/applications"
            self.assertTrue((apps / "corteac-2.5.7.desktop").exists())

    def test_versao_anterior_e_removida(self):
        """Atualizar não pode deixar dois ícones na mesa."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            home = tmp / "home"
            (home / "Desktop").mkdir(parents=True)
            apps = home / ".local/share/applications"
            apps.mkdir(parents=True)
            (apps / "corteac-1.0.0.desktop").write_text("[Desktop Entry]\n")
            (home / "Desktop" / "corteac-1.0.0.desktop").write_text("[Desktop Entry]\n")

            pkg = self._montar_pacote(tmp, "1.6.11")
            res = self._rodar(pkg, home)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertFalse((apps / "corteac-1.0.0.desktop").exists())
            self.assertFalse((home / "Desktop" / "corteac-1.0.0.desktop").exists())
            self.assertTrue((apps / "corteac-1.6.11.desktop").exists())



class TestSincronizacaoAutomatica(unittest.TestCase):
    """O app sincroniza o atalho existente para a versão atual ao iniciar (Linux)."""

    def setUp(self):
        if not sys.platform.startswith("linux"):
            self.skipTest("sincronização de .desktop é específica do Linux")

    def _home_fake(self, tmp: Path, com_atalho_antigo: bool):
        home = tmp / "home"
        area = home / "Área de Trabalho"   # padrão pt-BR do Mint
        area.mkdir(parents=True)
        if com_atalho_antigo:
            (area / "CorteAC.desktop").write_text("[Desktop Entry]\nName=CorteAC\n")
        return home, area

    def test_atualiza_atalho_antigo_para_a_versao(self):
        from unittest.mock import patch
        from ui.desktop_shortcut import sincronizar_atalho

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            home, area = self._home_fake(tmp, True)
            exe = tmp / "CorteAC" / "corteac_linux"
            exe.parent.mkdir(parents=True)
            exe.write_text("#!/bin/bash\n")
            icone = exe.parent / "corteac.png"
            icone.write_bytes(b"\x89PNG\r\n\x1a\n")

            with patch.dict(os.environ, {"HOME": str(home)}):
                info = sincronizar_atalho("9.9.9", exe_path=str(exe), icon_path=str(icone))

            self.assertEqual(info["acao"], "atualizado")
            novo = area / "corteac-9.9.9.desktop"
            self.assertTrue(novo.exists(), info)
            conteudo = novo.read_text()
            self.assertIn("Name=CorteAC-9.9.9", conteudo)
            self.assertIn('Exec="', conteudo)
            self.assertFalse((area / "CorteAC.desktop").exists(), "atalho antigo deveria sair")
            apps_novo = home / ".local/share/applications" / "corteac-9.9.9.desktop"
            self.assertTrue(apps_novo.exists(), "atalho do menu não criado")

    def test_sem_atalho_nao_cria_nada(self):
        from unittest.mock import patch
        from ui.desktop_shortcut import sincronizar_atalho

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            home, area = self._home_fake(tmp, False)
            with patch.dict(os.environ, {"HOME": str(home)}):
                info = sincronizar_atalho("9.9.9", exe_path=str(tmp / "x"), icon_path=str(tmp / "y.png"))
            self.assertEqual(info["acao"], "nenhum")
            self.assertEqual(list(area.glob("*.desktop")), [])


if __name__ == "__main__":
    unittest.main()
