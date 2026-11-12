"""
JobManager 2000 (Python Edition)
Diálogo "Alterar chapa" (AlterSheetDialog).

Permite ao operador editar as medidas da chapa (Largura e Altura em metros)
DEPOIS do encaixe, sem mover ou apagar peças.

Origem (0,0) fixa no canto inferior esquerdo (Y cartesiano para cima).
Aumentar ou diminuir altera unicamente as bordas DIREITA e SUPERIOR.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
import tkinter as tk
from ui.icon_widgets import IconTtkButton
from tkinter import ttk, messagebox

from config import THEME
from ui.units import format_m, parse_m_to_mm, format_dim_m, format_dim_mm, parse_m
from cad.geometry import transform_contour, polygon_bbox

parse_dim_m_to_mm = parse_m_to_mm

logger = logging.getLogger("alter_sheet_dialog")


def calc_pieces_minimum(
    placed_pieces: List[Dict[str, Any]],
    margin_right: float = 10.0,
    margin_top: float = 10.0,
    margin_left: float = 10.0,
    margin_bottom: float = 10.0,
    has_cut_x: bool = False,
    has_cut_y: bool = False,
) -> Tuple[float, float, float, float]:
    """
    Calcula o envelope mínimo (largura_mm, altura_mm, max_x_mm, max_y_mm)
    necessário para conter todas as peças com suas margens de segurança.
    Em bordas refiladas (has_cut_x / has_cut_y), a chapa já foi cortada rente
    às peças (+1mm gap), não exigindo a margem de segurança de fábrica.
    """
    max_x = 0.0
    max_y = 0.0
    for p in placed_pieces or []:
        contour = p.get("contour") or []
        if not contour and isinstance(p.get("shape"), dict):
            contour = p.get("shape", {}).get("contour") or []
        px = float(p.get("x", 0.0))
        py = float(p.get("y", 0.0))
        rot = float(p.get("rotation", p.get("rotation_deg", 0.0)))
        if contour and len(contour) >= 3:
            poly = transform_contour(contour, px, py, rot)
            _, _, bx2, by2 = polygon_bbox(poly)
            max_x = max(max_x, bx2)
            max_y = max(max_y, by2)
        else:
            max_x = max(max_x, px)
            max_y = max(max_y, py)

    eff_mr = 0.0 if has_cut_x else float(margin_right)
    eff_mt = 0.0 if has_cut_y else float(margin_top)
    min_w = max_x + eff_mr if max_x > 0 else 0.0
    min_h = max_y + eff_mt if max_y > 0 else 0.0
    return min_w, min_h, max_x, max_y


def count_pieces_outside(
    placed_pieces: List[Dict[str, Any]],
    target_w_mm: float,
    target_h_mm: float,
    margin_left: float = 10.0,
    margin_right: float = 10.0,
    margin_bottom: float = 10.0,
    margin_top: float = 10.0,
    has_cut_x: bool = False,
    has_cut_y: bool = False,
) -> Tuple[int, int, List[int]]:
    """
    Identifica quais peças ficariam fora da chapa ou fora da margem de segurança.
    Retorna: (total_fora_da_chapa, total_fora_da_margem, lista_indices_afetados).
    Em bordas refiladas, as peças já estão a 1mm do corte, então só ficam fora da margem
    se ultrapassarem a própria chapa (limit_w / limit_h).
    """
    outside_sheet = 0
    outside_margin = 0
    affected_indices: List[int] = []

    limit_w = float(target_w_mm)
    limit_h = float(target_h_mm)
    m_l = float(margin_left)
    m_r = float(margin_right)
    m_b = float(margin_bottom)
    m_t = float(margin_top)

    limit_right = limit_w if has_cut_x else (limit_w - m_r)
    limit_top = limit_h if has_cut_y else (limit_h - m_t)

    for idx, p in enumerate(placed_pieces or []):
        contour = p.get("contour") or []
        if not contour and isinstance(p.get("shape"), dict):
            contour = p.get("shape", {}).get("contour") or []
        px = float(p.get("x", 0.0))
        py = float(p.get("y", 0.0))
        rot = float(p.get("rotation", p.get("rotation_deg", 0.0)))

        if contour and len(contour) >= 3:
            poly = transform_contour(contour, px, py, rot)
            bx1, by1, bx2, by2 = polygon_bbox(poly)
        else:
            bx1, by1, bx2, by2 = px, py, px, py

        is_out_sheet = (bx2 > limit_w + 0.01 or by2 > limit_h + 0.01 or bx1 < -0.01 or by1 < -0.01)
        is_out_margin = (
            bx2 > limit_right + 0.01 or
            by2 > limit_top + 0.01 or
            bx1 < m_l - 0.01 or
            by1 < m_b - 0.01
        )

        if is_out_sheet:
            outside_sheet += 1
            affected_indices.append(idx)
        elif is_out_margin:
            outside_margin += 1
            affected_indices.append(idx)

    return outside_sheet, outside_margin, affected_indices


class AlterSheetDialog(tk.Toplevel):
    """
    Diálogo modal "Alterar chapa" conforme especificações autênticas.
    Permite alterar Largura e Altura em metros da placa aberta.
    """

    def __init__(
        self,
        parent: Optional[tk.Widget] = None,
        current_sheet_w_mm: float = 1380.0,
        current_sheet_h_mm: float = 2990.0,
        placed_pieces: Optional[List[Dict[str, Any]]] = None,
        margin_left: float = 10.0,
        margin_right: float = 10.0,
        margin_top: float = 10.0,
        margin_bottom: float = 10.0,
        tip_zone: Optional[Tuple[float, float, float, float]] = None,
        trim_cut_line: Optional[Dict[str, Any]] = None,
        on_apply: Optional[Callable[[float, float], None]] = None,
    ):
        super().__init__(parent, bg=THEME.get("bg_surface", "#f0f0f0"))
        self.parent = parent
        self.current_sheet_w_mm = float(current_sheet_w_mm)
        self.current_sheet_h_mm = float(current_sheet_h_mm)
        self.placed_pieces = placed_pieces or []
        self.margin_left = float(margin_left)
        self.margin_right = float(margin_right)
        self.margin_top = float(margin_top)
        self.margin_bottom = float(margin_bottom)
        self.tip_zone = tip_zone
        self.trim_cut_line = trim_cut_line
        trim_enabled = bool(trim_cut_line and trim_cut_line.get("enabled", True))
        self.has_cut_x = bool(trim_enabled and trim_cut_line.get("has_cut_x", False))
        self.has_cut_y = bool(trim_enabled and trim_cut_line.get("has_cut_y", False))
        self.on_apply_cb = on_apply
        self.on_apply = on_apply

        self.applied = False
        self.result_w_mm: Optional[float] = None
        self.result_h_mm: Optional[float] = None

        self.title("Alterar chapa")
        self.resizable(False, False)
        if parent:
            try:
                self.transient(parent)
            except Exception:
                pass
        try:
            self.grab_set()
        except Exception:
            pass

        # Cálculo do envelope mínimo seguro
        self.min_w_mm, self.min_h_mm, self.max_piece_x, self.max_piece_y = calc_pieces_minimum(
            self.placed_pieces,
            margin_right=self.margin_right,
            margin_top=self.margin_top,
            margin_left=self.margin_left,
            margin_bottom=self.margin_bottom,
            has_cut_x=self.has_cut_x,
            has_cut_y=self.has_cut_y,
        )

        self._setup_ui()
        self._center_window(380, 260)

        self.bind("<Return>", lambda e: self.on_confirm())
        self.bind("<Escape>", lambda e: self.on_cancel())

    def _setup_ui(self):
        container = tk.Frame(self, bg=THEME.get("bg_surface", "#f0f0f0"), padx=20, pady=16)
        container.pack(fill="both", expand=True)

        lbl_header = tk.Label(
            container,
            text="Medidas da Chapa (em metros):",
            font=("Segoe UI", 9, "bold"),
            bg=THEME.get("bg_surface", "#f0f0f0"),
            fg=THEME.get("text_main", "#000000"),
            anchor="w"
        )
        lbl_header.pack(fill="x", pady=(0, 12))

        # Grid de campos: Largura e Altura
        form_frame = tk.Frame(container, bg=THEME.get("bg_surface", "#f0f0f0"))
        form_frame.pack(fill="x", pady=(0, 10))

        # 1. Campo Largura (m)
        lbl_w = tk.Label(
            form_frame,
            text="Largura (m):",
            font=("Segoe UI", 9),
            bg=THEME.get("bg_surface", "#f0f0f0"),
            fg=THEME.get("text_main", "#000000"),
            anchor="e",
            width=12
        )
        lbl_w.grid(row=0, column=0, padx=(0, 8), pady=4, sticky="e")

        init_w_txt = format_m(self.current_sheet_w_mm, 2)
        self.entry_width = ttk.Entry(form_frame, font=("Segoe UI", 9), width=12)
        self.entry_width.insert(0, init_w_txt)
        self.entry_width.grid(row=0, column=1, padx=(0, 4), pady=4, sticky="w")
        lbl_unit_w = tk.Label(
            form_frame,
            text="m",
            font=("Segoe UI", 9),
            bg=THEME.get("bg_surface", "#f0f0f0"),
            fg=THEME.get("text_muted", "#64748b")
        )
        lbl_unit_w.grid(row=0, column=2, padx=(2, 0), pady=4, sticky="w")

        # 2. Campo Altura (m)
        lbl_h = tk.Label(
            form_frame,
            text="Altura (m):",
            font=("Segoe UI", 9),
            bg=THEME.get("bg_surface", "#f0f0f0"),
            fg=THEME.get("text_main", "#000000"),
            anchor="e",
            width=12
        )
        lbl_h.grid(row=1, column=0, padx=(0, 8), pady=4, sticky="e")

        init_h_txt = format_m(self.current_sheet_h_mm, 2)
        self.entry_height = ttk.Entry(form_frame, font=("Segoe UI", 9), width=12)
        self.entry_height.insert(0, init_h_txt)
        self.entry_height.grid(row=1, column=1, padx=(0, 4), pady=4, sticky="w")
        lbl_unit_h = tk.Label(
            form_frame,
            text="m",
            font=("Segoe UI", 9),
            bg=THEME.get("bg_surface", "#f0f0f0"),
            fg=THEME.get("text_muted", "#64748b")
        )
        lbl_unit_h.grid(row=1, column=2, padx=(2, 0), pady=4, sticky="w")

        # Texto de apoio (não é controle):
        # "Mínimo possível: L × A m (peças + margem de segurança)"
        if self.placed_pieces and (self.min_w_mm > 0 or self.min_h_mm > 0):
            min_txt = f"Mínimo possível: {format_m(self.min_w_mm, 2)} × {format_m(self.min_h_mm, 2)} m (peças + margem de segurança)"
        else:
            min_txt = "Mínimo possível: 0,10 × 0,10 m (sem peças posicionadas)"

        self.lbl_support = tk.Label(
            container,
            text=min_txt,
            font=("Segoe UI", 8, "italic"),
            bg=THEME.get("bg_surface", "#f0f0f0"),
            fg="#475569",
            justify="left",
            wraplength=340,
            anchor="w"
        )
        self.lbl_support.pack(fill="x", pady=(4, 14))

        # Linha de botões OK / Cancelar
        btn_frame = tk.Frame(container, bg=THEME.get("bg_surface", "#f0f0f0"))
        btn_frame.pack(fill="x", side="bottom")

        self.btn_cancel = IconTtkButton(btn_frame, text="Cancelar", command=self.on_cancel, width=10)
        self.btn_cancel.pack(side="right", padx=(6, 0))

        self.btn_ok = IconTtkButton(btn_frame, text="OK", command=self.on_confirm, width=10)
        self.btn_ok.pack(side="right")

        # Aliases de conveniência
        self.entry_w = self.entry_width
        self.entry_h = self.entry_height
        self._on_ok = self.on_confirm

        # Foco inicial no campo Largura com seleção
        self.entry_width.focus_set()
        self.entry_width.select_range(0, "end")

    def _center_window(self, width: int = 380, height: int = 260):
        try:
            self.update_idletasks()
            pw = self.parent.winfo_width() if self.parent else self.winfo_screenwidth()
            ph = self.parent.winfo_height() if self.parent else self.winfo_screenheight()
            px = self.parent.winfo_rootx() if self.parent else 0
            py = self.parent.winfo_rooty() if self.parent else 0
            x = px + max(0, (pw - width) // 2)
            y = py + max(0, (ph - height) // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            self.geometry(f"{width}x{height}")

    def on_confirm(self):
        """Valida os campos e aplica a alteração de chapa."""
        raw_w = self.entry_width.get().strip()
        raw_h = self.entry_height.get().strip()

        try:
            target_w_mm = parse_m_to_mm(raw_w)
            target_h_mm = parse_m_to_mm(raw_h)
        except (ValueError, TypeError):
            messagebox.showwarning(
                "Valor Inválido",
                "Por favor, insira valores válidos e positivos em metros para Largura e Altura (ex.: 1,38).",
                parent=self
            )
            return

        if target_w_mm <= 0.0 or target_h_mm <= 0.0:
            messagebox.showwarning(
                "Medida Inválida",
                "As medidas da chapa devem ser maiores que zero.",
                parent=self
            )
            return

        # Verifica se alguma peça fica fora da chapa ou da margem de segurança
        out_sheet, out_margin, affected = count_pieces_outside(
            self.placed_pieces,
            target_w_mm,
            target_h_mm,
            margin_left=self.margin_left,
            margin_right=self.margin_right,
            margin_bottom=self.margin_bottom,
            margin_top=self.margin_top,
            has_cut_x=self.has_cut_x,
            has_cut_y=self.has_cut_y,
        )

        total_affected = len(affected)
        if total_affected > 0:
            msg = (
                f"Com as dimensões informadas ({format_m(target_w_mm, 2)} × {format_m(target_h_mm, 2)} m), "
                f"{total_affected} peça(s) ficariam fora da chapa ou da margem de segurança.\n\n"
                f"As peças NÃO serão apagadas e serão destacadas em vermelho no desenho.\n\n"
                f"Deseja aplicar a alteração mesmo assim?"
            )
            if not messagebox.askyesno("Alterar chapa", msg, parent=self):
                return

        # Verifica ponta de 2 camadas (tip_zone)
        if self.tip_zone and len(self.tip_zone) == 4:
            tx0, ty0, tx1, ty1 = (float(v) for v in self.tip_zone)
            max_tx = max(tx0, tx1)
            max_ty = max(ty0, ty1)
            if max_tx > target_w_mm + 0.5 or max_ty > target_h_mm + 0.5:
                msg_tip = (
                    "Atenção: A nova dimensão da chapa deixará a ponta de 2 camadas parcialmente fora "
                    "ou cruzando a borda da placa.\n\n"
                    "Deseja confirmar a alteração?"
                )
                if not messagebox.askyesno("Ponta de 2 Camadas", msg_tip, parent=self):
                    return

        self.applied = True
        self.result_w_mm = target_w_mm
        self.result_h_mm = target_h_mm

        if self.on_apply_cb:
            self.on_apply_cb(target_w_mm, target_h_mm)

        self.destroy()

    def on_cancel(self):
        """Cancela o diálogo sem alterar as medidas."""
        self.applied = False
        self.destroy()
