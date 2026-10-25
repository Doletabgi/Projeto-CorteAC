"""
JobManager 2000 (Python Edition)
ui/fill_user_dialog.py - Diálogo Modal 'Set User constraints' (Dialog 159, Win32 ID 50003)

Permite ao operador de corte definir parâmetros milimétricos customizados para preenchimento:
- Direção: Row (Horizontal) ou Column (Vertical)
- Passo X (mm) e Passo Y (mm) (0 ou vazio = encosto automático por contorno)
- Quantidade máxima de cópias (0 ou vazio = ilimitado até o limite da chapa)
- Alternar rotação 0° / 180° (acoplamento bico-calcanhar)
- Folga extra entre peças (mm), somada ao gap_mm do job
- Preencher chapa inteira (Fill Sheet customizado)

Design em conformidade com o Dialog 159 original (307x95 DLU, Layout.exe / LayoutNT).
Os rótulos exatos são [INFERIDO] e marcados com # CONFIRMAR NO WINDOWS.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import tkinter as tk
from tkinter import ttk

from config import THEME


@dataclass
class FillUserConstraints:
    """Parâmetros validados do diálogo 'Set User constraints'."""
    direction: str = "row"        # 'row' ou 'column'
    step_x_mm: float = 0.0        # 0.0 = encosto por contorno automático
    step_y_mm: float = 0.0        # 0.0 = encosto por contorno automático
    max_copies: int = 0           # 0 = sem limite de quantidade
    alternate_rot: bool = False   # Alternar 0° / 180°
    extra_gap_mm: float = 0.0     # Folga extra em mm
    fill_sheet: bool = False      # Preencher a chapa inteira


def validate_fill_user_params(raw_dict: Dict[str, Any]) -> Tuple[Optional[FillUserConstraints], Optional[str]]:
    """
    Função pura de validação de parâmetros de preenchimento do usuário.
    Permite testes unitários rápidos e isolados sem dependência de widgets Tkinter.
    Retorna (FillUserConstraints, None) se válido ou (None, mensagem_de_erro) se inválido.
    """
    direction = str(raw_dict.get("direction", "row")).lower().strip()
    if direction not in ("row", "column"):
        return None, "Direção inválida. Escolha Linha (Row) ou Coluna (Column)."

    # Passo X
    raw_step_x = raw_dict.get("step_x", 0.0)
    if raw_step_x is None or str(raw_step_x).strip() == "":
        step_x_mm = 0.0
    else:
        try:
            step_x_mm = float(str(raw_step_x).replace(",", "."))
            if step_x_mm < 0.0:
                return None, "O Passo X não pode ser negativo."
        except ValueError:
            return None, "Valor inválido para o Passo X (deve ser um número)."

    # Passo Y
    raw_step_y = raw_dict.get("step_y", 0.0)
    if raw_step_y is None or str(raw_step_y).strip() == "":
        step_y_mm = 0.0
    else:
        try:
            step_y_mm = float(str(raw_step_y).replace(",", "."))
            if step_y_mm < 0.0:
                return None, "O Passo Y não pode ser negativo."
        except ValueError:
            return None, "Valor inválido para o Passo Y (deve ser um número)."

    # Quantidade máxima de cópias
    raw_max = raw_dict.get("max_copies", 0)
    if raw_max is None or str(raw_max).strip() == "":
        max_copies = 0
    else:
        try:
            max_copies_val = float(str(raw_max).replace(",", "."))
            if not max_copies_val.is_integer():
                return None, "A Quantidade máxima deve ser um número inteiro."
            max_copies = int(max_copies_val)
            if max_copies < 0:
                return None, "A Quantidade máxima não pode ser negativa."
        except ValueError:
            return None, "Valor inválido para a Quantidade máxima (deve ser um número inteiro)."

    # Folga extra
    raw_extra = raw_dict.get("extra_gap", 0.0)
    if raw_extra is None or str(raw_extra).strip() == "":
        extra_gap_mm = 0.0
    else:
        try:
            extra_gap_mm = float(str(raw_extra).replace(",", "."))
            if extra_gap_mm < 0.0:
                return None, "A Folga extra não pode ser negativa."
        except ValueError:
            return None, "Valor inválido para a Folga extra."

    alternate_rot = bool(raw_dict.get("alternate_rot", False))
    fill_sheet = bool(raw_dict.get("fill_sheet", False))

    return FillUserConstraints(
        direction=direction,
        step_x_mm=round(step_x_mm, 4),
        step_y_mm=round(step_y_mm, 4),
        max_copies=max_copies,
        alternate_rot=alternate_rot,
        extra_gap_mm=round(extra_gap_mm, 4),
        fill_sheet=fill_sheet,
    ), None


class FillUserDialog(tk.Toplevel):
    """
    Diálogo Modal 'Set User constraints' (Dialog 159 original, Win32 ID 50003).
    # CONFIRMAR NO WINDOWS: rótulos exatos dos 17 controles do Dialog 159.
    """
    # Memória da sessão ativa (retém últimos valores na RAM sem gravar em disco)
    _last_values: Dict[str, Any] = {
        "direction": "row",
        "step_x": "",
        "step_y": "",
        "max_copies": "0",
        "alternate_rot": False,
        "extra_gap": "0.0",
        "fill_sheet": False,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.result: Optional[FillUserConstraints] = None

        self.title("Set User constraints")  # Título autêntico Win32 Dialog 159
        self.resizable(False, False)
        self.configure(bg=THEME.get("bg_surface", "#f3f4f6"))

        if parent:
            try:
                self.transient(parent)
            except Exception:
                pass

        self.setup_ui()

        # Centraliza a janela sobre o parent se disponível
        self._center_dialog(380, 360)

        try:
            self.grab_set()
        except Exception:
            pass

        # Atalhos de teclado
        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<KP_Enter>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.on_cancel())

        # Foco inicial no primeiro campo editável
        try:
            self.entry_step_x.focus_set()
        except Exception:
            pass

    def setup_ui(self):
        bg = THEME.get("bg_surface", "#f3f4f6")
        fg = THEME.get("text_main", "#111827")
        accent = THEME.get("accent_blue", "#2563eb")

        container = tk.Frame(self, bg=bg, padx=14, pady=12)
        container.pack(fill="both", expand=True)

        # 1. Direção (Row / Column)
        lbl_dir = tk.Label(container, text="Direção de Preenchimento:", bg=bg, fg=fg, font=("Segoe UI", 9, "bold"))
        lbl_dir.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        self.var_direction = tk.StringVar(value=self._last_values.get("direction", "row"))
        frame_dir = tk.Frame(container, bg=bg)
        frame_dir.grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 8))

        rb_row = tk.Radiobutton(
            frame_dir, text="Linha (Row - Horizontal)", variable=self.var_direction,
            value="row", bg=bg, fg=fg, activebackground=bg, font=("Segoe UI", 9)
        )
        rb_row.pack(side="left", padx=(0, 12))

        rb_col = tk.Radiobutton(
            frame_dir, text="Coluna (Column - Vertical)", variable=self.var_direction,
            value="column", bg=bg, fg=fg, activebackground=bg, font=("Segoe UI", 9)
        )
        rb_col.pack(side="left")

        # 2. Passo X (mm)
        lbl_step_x = tk.Label(container, text="Passo X (mm):", bg=bg, fg=fg, font=("Segoe UI", 9))
        lbl_step_x.grid(row=2, column=0, sticky="w", pady=3)
        self.entry_step_x = tk.Entry(container, width=14, font=("Segoe UI", 9))
        self.entry_step_x.insert(0, str(self._last_values.get("step_x", "")))
        self.entry_step_x.grid(row=2, column=1, sticky="w", padx=6, pady=3)

        lbl_step_x_hint = tk.Label(container, text="(0 ou vazio = encosto automático)", bg=bg, fg="#6b7280", font=("Segoe UI", 8))
        lbl_step_x_hint.grid(row=3, column=1, sticky="w", padx=6, pady=(0, 4))

        # 3. Passo Y (mm)
        lbl_step_y = tk.Label(container, text="Passo Y (mm):", bg=bg, fg=fg, font=("Segoe UI", 9))
        lbl_step_y.grid(row=4, column=0, sticky="w", pady=3)
        self.entry_step_y = tk.Entry(container, width=14, font=("Segoe UI", 9))
        self.entry_step_y.insert(0, str(self._last_values.get("step_y", "")))
        self.entry_step_y.grid(row=4, column=1, sticky="w", padx=6, pady=3)

        lbl_step_y_hint = tk.Label(container, text="(0 ou vazio = encosto automático)", bg=bg, fg="#6b7280", font=("Segoe UI", 8))
        lbl_step_y_hint.grid(row=5, column=1, sticky="w", padx=6, pady=(0, 4))

        # 4. Quantidade máxima de cópias
        lbl_max = tk.Label(container, text="Qtd. Máxima de Cópias:", bg=bg, fg=fg, font=("Segoe UI", 9))
        lbl_max.grid(row=6, column=0, sticky="w", pady=3)
        self.entry_max = tk.Entry(container, width=14, font=("Segoe UI", 9))
        self.entry_max.insert(0, str(self._last_values.get("max_copies", "0")))
        self.entry_max.grid(row=6, column=1, sticky="w", padx=6, pady=3)

        lbl_max_hint = tk.Label(container, text="(0 = sem limite / até borda da chapa)", bg=bg, fg="#6b7280", font=("Segoe UI", 8))
        lbl_max_hint.grid(row=7, column=1, sticky="w", padx=6, pady=(0, 4))

        # 5. Folga Extra (mm)
        lbl_extra = tk.Label(container, text="Folga Extra (mm):", bg=bg, fg=fg, font=("Segoe UI", 9))
        lbl_extra.grid(row=8, column=0, sticky="w", pady=3)
        self.entry_extra = tk.Entry(container, width=14, font=("Segoe UI", 9))
        self.entry_extra.insert(0, str(self._last_values.get("extra_gap", "0.0")))
        self.entry_extra.grid(row=8, column=1, sticky="w", padx=6, pady=3)

        # 6. Checkboxes: Alternar Rotação e Preencher Chapa Inteira
        self.var_alternate = tk.BooleanVar(value=bool(self._last_values.get("alternate_rot", False)))
        chk_alt = tk.Checkbutton(
            container, text="Alternar Rotação 0° / 180° (bico-calcanhar)",
            variable=self.var_alternate, bg=bg, fg=fg, activebackground=bg, font=("Segoe UI", 9)
        )
        chk_alt.grid(row=9, column=0, columnspan=2, sticky="w", pady=(6, 2))

        self.var_fill_sheet = tk.BooleanVar(value=bool(self._last_values.get("fill_sheet", False)))
        chk_sheet = tk.Checkbutton(
            container, text="Preencher chapa inteira (múltiplas linhas)",
            variable=self.var_fill_sheet, bg=bg, fg=fg, activebackground=bg, font=("Segoe UI", 9)
        )
        chk_sheet.grid(row=10, column=0, columnspan=2, sticky="w", pady=(0, 6))

        # 7. Label de Erro Inline
        self.lbl_error = tk.Label(container, text="", bg=bg, fg="#ef4444", font=("Segoe UI", 8, "bold"), wraplength=340)
        self.lbl_error.grid(row=11, column=0, columnspan=2, sticky="w", pady=(0, 4))

        # 8. Botões OK e Cancel
        btn_box = tk.Frame(container, bg=bg)
        btn_box.grid(row=12, column=0, columnspan=2, sticky="e", pady=(8, 0))

        btn_cancel = tk.Button(
            btn_box, text="Cancelar", width=10, command=self.on_cancel,
            bg=THEME.get("bg_card", "#ffffff"), fg=fg, font=("Segoe UI", 9)
        )
        btn_cancel.pack(side="right", padx=(6, 0))

        btn_ok = tk.Button(
            btn_box, text="OK", width=10, command=self.on_ok,
            bg=accent, fg="#ffffff", activebackground="#1d4ed8", font=("Segoe UI", 9, "bold")
        )
        btn_ok.pack(side="right")

    def _center_dialog(self, w: int, h: int):
        self.geometry(f"{w}x{h}")
        if self.parent:
            try:
                self.update_idletasks()
                px = self.parent.winfo_rootx() + (self.parent.winfo_width() - w) // 2
                py = self.parent.winfo_rooty() + (self.parent.winfo_height() - h) // 2
                self.geometry(f"+{max(10, px)}+{max(10, py)}")
            except Exception:
                pass

    def on_ok(self):
        """Valida entradas, atualiza memória da sessão e fecha se tudo estiver correto."""
        raw_dict = {
            "direction": self.var_direction.get(),
            "step_x": self.entry_step_x.get(),
            "step_y": self.entry_step_y.get(),
            "max_copies": self.entry_max.get(),
            "alternate_rot": self.var_alternate.get(),
            "extra_gap": self.entry_extra.get(),
            "fill_sheet": self.var_fill_sheet.get(),
        }

        constraints, error_msg = validate_fill_user_params(raw_dict)
        if error_msg:
            self.lbl_error.config(text=error_msg)
            return

        # Limpa mensagem de erro e memoriza valores para a sessão
        self.lbl_error.config(text="")
        FillUserDialog._last_values = raw_dict
        self.result = constraints
        self.destroy()

    def on_cancel(self):
        """Cancela o diálogo sem registrar alterações."""
        self.result = None
        self.destroy()
