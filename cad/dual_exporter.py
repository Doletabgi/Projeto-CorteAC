"""
JobManager 2000 (Python Edition)
CAM / CAD: Orquestrador de Dupla Saída de Layout (ATOM .lay + Comelz .onx)
Permite salvar e exportar encaixes simultaneamente ou individualmente para
ambos os ecossistemas industriais de máquinas de corte CNC.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

from cad.lay_parser import export_layout_from_pieces
from cad.onx_exporter import save_onx_file


class DualLayoutExporter:
    """
    Exportador unificado para máquinas de corte ATOM (FlashCut .lay)
    e Comelz (CNC .onx / CZLIB v2).
    """

    @staticmethod
    def export_atom_lay(
        placed_pieces: List[Dict[str, Any]],
        material: Dict[str, Any],
        file_path: Union[str, Path],
        session_id: Optional[int] = 1
    ) -> str:
        """
        Gera e grava arquivo .lay compatível com ATOM FlashCut (508584LAYOUT.v3508584).
        """
        p = Path(file_path)
        if not p.suffix.lower() == ".lay":
            p = p.with_suffix(".lay")

        content = export_layout_from_pieces(
            placed_pieces=placed_pieces,
            material=material,
            session_id=session_id,
            filename=p.name
        )

        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="latin1", newline="") as fp:
            fp.write(content)

        return str(p)

    @staticmethod
    def export_comelz_onx(
        placed_pieces: List[Dict[str, Any]],
        material: Dict[str, Any],
        file_path: Union[str, Path],
        margins_mm: Union[float, Tuple[float, float, float, float]] = 15.0,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Gera e grava arquivo .onx compactado com CZLIB v2 compatível com Comelz.
        """
        p = Path(file_path)
        if not p.suffix.lower() == ".onx":
            p = p.with_suffix(".onx")

        return save_onx_file(
            placed_pieces=placed_pieces,
            material=material,
            file_path=p,
            margins_mm=margins_mm,
            options=options
        )

    @classmethod
    def export_dual_layout(
        cls,
        placed_pieces: List[Dict[str, Any]],
        material: Dict[str, Any],
        base_path: Union[str, Path],
        margins_mm: Union[float, Tuple[float, float, float, float]] = 15.0,
        session_id: Optional[int] = 1,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Exporta SIMULTANEAMENTE para ambas as máquinas de corte:
        - <base_path>.lay (ATOM)
        - <base_path>.onx (Comelz)

        Retorna dicionário com os caminhos dos arquivos e estatísticas.
        """
        p = Path(base_path)
        # Remove extensão existente para manter o mesmo stem base
        stem_path = p.parent / p.stem

        lay_file = stem_path.with_suffix(".lay")
        onx_file = stem_path.with_suffix(".onx")

        lay_res = cls.export_atom_lay(
            placed_pieces=placed_pieces,
            material=material,
            file_path=lay_file,
            session_id=session_id
        )

        onx_res = cls.export_comelz_onx(
            placed_pieces=placed_pieces,
            material=material,
            file_path=onx_file,
            margins_mm=margins_mm,
            options=options
        )

        return {
            "lay_path": lay_res,
            "onx_path": onx_res,
            "total_pieces": len(placed_pieces),
            "base_name": p.stem
        }
