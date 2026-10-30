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

import json
import tkinter as tk
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

        self.btn_edit_macro = tk.Button(
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

        self.btn_reset = tk.Button(
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

    def refresh_status(self):
        """Atualiza o resumo dos braços UCB1 e hábitos registrados."""
        if not self.db:
            self.lbl_status.config(text="Status: 5 braços UCB1 ativos | Sem banco de dados")
            return

        try:
            settings = self.db.get_all_settings()
            # Conta operações registradas
            habits_raw = settings.get("ai_operator_habits", "[]")
            habits = json.loads(habits_raw) if habits_raw else []
            total_ops = len(habits) if isinstance(habits, list) else 0

            # Conta total trials dos bandits
            total_trials = 0
            for k, v in settings.items():
                if k.startswith("ai_bandit_"):
                    try:
                        b_data = json.loads(v)
                        total_trials += int(b_data.get("total_trials", 0))
                    except Exception:
                        pass

            self.lbl_status.config(
                text=f"Status: 5 braços UCB1 | {total_ops} padrões de corte | {total_trials} execuções avaliadas"
            )
        except Exception:
            self.lbl_status.config(text="Status: 5 braços UCB1 ativos | Modo autônomo")

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
        """Reseta todos os dados aprendidos pela IA com confirmação."""
        parent_window = self.winfo_toplevel()
        confirm = messagebox.askyesno(
            "Resetar Aprendizado",
            "Deseja realmente redefinir todos os padrões aprendidos e calibrações UCB1 da IA Local?\n\n"
            "Esta ação restaurará o motor ao estado 'fresh' de fábrica.",
            parent=parent_window,
        )
        if not confirm:
            return

        if self.db:
            try:
                settings = self.db.get_all_settings()
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    for k in list(settings.keys()):
                        if k.startswith("ai_bandit_") or k == "ai_operator_habits":
                            cursor.execute("DELETE FROM settings WHERE `key` = ?", (k,))
                    conn.commit()
                self.refresh_status()
                messagebox.showinfo(
                    "Aprendizado Resetado",
                    "Os dados da IA Local foram resetados com sucesso.",
                    parent=parent_window,
                )
            except Exception as e:
                messagebox.showerror("Erro ao Resetar", f"Falha ao limpar dados: {e}", parent=parent_window)
