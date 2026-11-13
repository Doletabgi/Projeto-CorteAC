"""
JobManager 2000 (Python Edition)
ui/macro_panel.py - Camada 3: Painel de Macro & Aprendizado (IA Local Embarcada)

Hierarquia de 4 Camadas:
1. Modo de Encaixe (NestingModeWidget)
2. Avançado (Estratégia, Parâmetros, Gap, Margens)
3. Macro / Aprendizado (MacroPanel)
4. Debug / Diagnóstico (DebugPanel)
"""

from __future__ import annotations

import tkinter as tk
from ui.icon_widgets import IconButton
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from config import THEME
from ui.dieproc_dialog import DieProcDialog


class MacroPanel(tk.LabelFrame):
    """
    Camada 3: Macro / Aprendizado.
    Integração direta com DieProcDialog, monitoramento dos braços UCB1 da IA Local
    e controle de aprendizado contínuo por reforço e imitação.
    """

    def __init__(
        self,
        parent: tk.Widget,
        db: Any,
        on_macro_changed: Optional[Callable[[str], None]] = None,
        on_open_editor: Optional[Callable[[], None]] = None,
        bg: Optional[str] = None,
        **kwargs,
    ):
        card_bg = bg or THEME.get("bg_card", "#f0f0f0")
        super().__init__(
            parent,
            text="Macro / Aprendizado (IA Local)",
            bg=card_bg,
            fg=THEME.get("text_main", "#000000"),
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            padx=8,
            pady=6,
            **kwargs,
        )

        self.material_code = None
        self.db = db
        self.on_macro_changed = on_macro_changed
        self.on_open_editor_cb = on_open_editor
        self._current_mode = "auto"

        # Linha 1: Macro ativa + Badge (auto) + Botão Editar Macro...
        row1 = tk.Frame(self, bg=card_bg)
        row1.pack(fill="x", pady=(0, 4))

        tk.Label(
            row1,
            text="Macro ativa:",
            bg=card_bg,
            fg=THEME.get("text_main", "#000000"),
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left", padx=(0, 4))

        self.cb_macro = ttk.Combobox(
            row1,
            values=[],
            state="readonly",
            font=("Segoe UI", 9),
            width=20,
        )
        self.cb_macro.pack(side="left", padx=(0, 6))
        self.cb_macro.bind("<<ComboboxSelected>>", self._on_combobox_selected)

        self.lbl_auto_badge = tk.Label(
            row1,
            text="(auto)",
            bg="#e8f5e9",
            fg="#2e7d32",
            font=("Segoe UI", 8, "bold"),
            relief="solid",
            bd=1,
            padx=4,
            pady=0,
        )
        self.lbl_auto_badge.pack(side="left", padx=(0, 8))

        self.btn_edit_macro = IconButton(
            row1,
            text="📝 Editar Macro...",
            bg=THEME.get("bg_surface", "#e0e0e0"),
            fg=THEME.get("text_main", "#000000"),
            font=("Segoe UI", 8),
            relief="raised",
            bd=1,
            cursor="hand2",
            padx=6,
            pady=1,
            command=self.open_dieproc_dialog,
        )
        self.btn_edit_macro.pack(side="right")

        # Linha 2: Status do aprendizado UCB1
        row2 = tk.Frame(self, bg=card_bg)
        row2.pack(fill="x", pady=(2, 4))

        self.lbl_status = tk.Label(
            row2,
            text="Carregando status do aprendizado...",
            bg=card_bg,
            fg=THEME.get("text_dim", "#555555"),
            font=("Segoe UI", 8, "italic"),
            anchor="w",
        )
        self.lbl_status.pack(side="left", fill="x", expand=True)

        # Linha 3: Controles de aprendizado contínuo e reset
        row3 = tk.Frame(self, bg=card_bg)
        row3.pack(fill="x", pady=(2, 0))

        self.var_continuous = tk.BooleanVar(value=True)
        self._load_continuous_learning_setting()
        self.chk_continuous = tk.Checkbutton(
            row3,
            text="Permitir aprendizado contínuo",
            variable=self.var_continuous,
            bg=card_bg,
            fg=THEME.get("text_main", "#000000"),
            selectcolor="#ffffff",
            activebackground=card_bg,
            font=("Segoe UI", 8),
            command=self._on_continuous_toggle,
        )
        self.chk_continuous.pack(side="left")

        self.btn_reset = IconButton(
            row3,
            text="🔄 Resetar Aprendizado",
            bg=THEME.get("bg_surface", "#e0e0e0"),
            fg=THEME.get("text_main", "#000000"),
            font=("Segoe UI", 8),
            relief="raised",
            bd=1,
            cursor="hand2",
            padx=6,
            pady=0,
            command=self.reset_learning,
        )
        self.btn_reset.pack(side="right")

        self.refresh_presets()
        self.refresh_status()

    def _load_continuous_learning_setting(self):
        if self.db:
            try:
                val = self.db.get_setting("ai_continuous_learning", "1")
                self.var_continuous.set(str(val) in ("1", "true", "True"))
            except Exception:
                self.var_continuous.set(True)

    def _on_continuous_toggle(self):
        if self.db:
            try:
                val = "1" if self.var_continuous.get() else "0"
                self.db.set_setting("ai_continuous_learning", val)
            except Exception as e:
                print(f"[MacroPanel] Erro ao salvar ai_continuous_learning: {e}")

    def refresh_presets(self, select_name: Optional[str] = None):
        """Atualiza a lista de macros a partir do banco de dados."""
        presets = []
        if self.db:
            try:
                db_presets = self.db.get_dieproc_presets()
                presets = [p["name"] for p in db_presets if "name" in p]
            except Exception:
                presets = []

        if not presets:
            presets = ["ALTERNADO", "MACRO_IA_TESTE", "PADRAO"]

        self.cb_macro["values"] = presets
        target = select_name or self.cb_macro.get() or presets[0]
        if target not in presets and presets:
            target = presets[0]
        self.cb_macro.set(target)

    def set_material_code(self, code):
        self.material_code = str(code).strip() if code is not None else ""
        self.refresh_status()

    def refresh_status(self):
        from cad.ai_learner import NestingAIBrain
        brain = NestingAIBrain(self.db, material_code=self.material_code)
        if not brain.material_code:
            self.lbl_status.config(text="Selecione um material com código para usar o aprendizado")
            self.btn_reset.config(state="disabled")
            return
        self.btn_reset.config(state="normal")
        info = brain.get_memory_status()
        self.lbl_status.config(text=(
            f"Material {brain.material_code}: 5 braços UCB1 | "
            f"{info['habits_count']} padrões de corte | {info['total_runs']} execuções avaliadas"
        ))

    def _on_combobox_selected(self, event=None):
        macro_name = self.cb_macro.get()
        if self.on_macro_changed:
            self.on_macro_changed(macro_name)

    def set_mode(self, mode: str):
        """Ajusta aparência do painel conforme o modo ativo."""
        self._current_mode = mode
        if mode == "auto":
            self.lbl_auto_badge.pack(side="left", padx=(0, 8))
            self.cb_macro.config(state="disabled")
        else:
            self.lbl_auto_badge.pack_forget()
            self.cb_macro.config(state="readonly")

    def get_active_macro(self) -> str:
        return self.cb_macro.get()

    def set_active_macro(self, macro_name: str):
        if macro_name in self.cb_macro["values"]:
            self.cb_macro.set(macro_name)
        else:
            vals = list(self.cb_macro["values"]) + [macro_name]
            self.cb_macro["values"] = vals
            self.cb_macro.set(macro_name)

    def open_dieproc_dialog(self):
        """Abre o diálogo de configuração completa DieProc / Macro DSL."""
        if self.on_open_editor_cb:
            self.on_open_editor_cb()
        elif self.db:
            parent_window = self.winfo_toplevel()
            DieProcDialog(
                parent_window,
                self.db,
                initial_preset=self.cb_macro.get(),
                material_code=self.material_code,
                on_select=self._on_dialog_preset_selected,
            )

    def _on_dialog_preset_selected(self, preset_data: Optional[Dict[str, Any]]):
        if not preset_data:
            return
        name = preset_data.get("name")
        if name:
            self.refresh_presets(select_name=name)
            if self.on_macro_changed:
                self.on_macro_changed(name)

    def reset_learning(self):
        """Reseta apenas o aprendizado do material selecionado."""
        if not self.material_code:
            return
        parent_window = self.winfo_toplevel()
        confirm = messagebox.askyesno(
            "Resetar Aprendizado",
            f"Deseja redefinir os padrões e calibrações da IA do material {self.material_code}?\n\n"
            "Os demais materiais serão preservados.",
            parent=parent_window,
        )
        if not confirm:
            return

        if self.db:
            try:
                from cad.ai_learner import NestingAIBrain
                NestingAIBrain(self.db, self.material_code).reset_learning()
                self.refresh_status()
                messagebox.showinfo(
                    "Aprendizado Resetado",
                    "Os dados da IA Local foram resetados com sucesso.",
                    parent=parent_window,
                )
            except Exception as e:
                messagebox.showerror("Erro ao Resetar", f"Falha ao limpar dados: {e}", parent=parent_window)
