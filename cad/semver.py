"""
Sistema de Versionamento SemVer (Semantic Versioning 2.0.0)
Padrão MAJOR.MINOR.PATCH para CorteAC / ATOM JobManager Reborn

Regras de Versionamento:
• MAJOR: 1.0.0 → 2.0.0 (Mudanças grandes que podem exigir adaptações / breaking changes)
• MINOR: 1.0.0 → 1.1.0 (Novas funcionalidades sem quebrar a compatibilidade / feat)
• PATCH: 1.0.0 → 1.0.1 (Correções de erros e falhas de segurança / fix, docs, chore, build)
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple

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
