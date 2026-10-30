"""
JobManager 2000 (Python Edition)
ui/nesting_mode_widget.py - Camada 1: Seletor de Modo de Encaixe com 6 Modos Industriais

Hierarquia de 4 Camadas:
1. Modo de Encaixe (NestingModeWidget)
2. Avançado (Estratégia, Parâmetros, Gap, Margens)
3. Macro / Aprendizado (MacroPanel)
4. Debug / Diagnóstico (DebugPanel)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, Optional

from config import THEME

MODES: Dict[str, Dict[str, Any]] = {
    "auto": {
        "label": "🟢 Automático (recomendado)",
        "engine": "ia_teste",
        "strategy": "flashnestsheet",
        "params": "macro_default",
        "description": "Otimização autônoma (Day-1, yield 69,56%)",
    },
    "fast": {
        "label": "⚡ Rápido",
        "engine": "nfp",
        "strategy": "flashnestsheet",
        "params": "FastNest",
        "description": "Cálculo instantâneo (< 20ms, yield 55,65%)",
    },
    "economic": {
        "label": "💰 Econômico",
        "engine": "nfp",
        "strategy": "flashnestsheet",
        "params": "HighYield",
        "description": "Máximo aproveitamento analítico",
    },
    "tapes": {
        "label": "🎗️ Fitas / Correias",
        "engine": "nfp",
        "strategy": "tape_a",
        "params": "stdNOTFill",
        "description": "Alinhamento linear longitudinal",
    },
    "remnants": {
        "label": "♻️ Sobras / Retalhos",
        "engine": "nfp",
        "strategy": "freenest",
        "params": "stdNOTFill",
        "description": "Aproveitamento livre em retalhos",
    },
    "custom": {
        "label": "🔓 Personalizado",
        "engine": None,
        "strategy": None,
        "params": None,
        "description": "Controle manual de todos os parâmetros",
    },
}

# Mapeamentos bidirecionais entre chave interna e label visual
LABEL_TO_KEY = {mode_info["label"]: key for key, mode_info in MODES.items()}
KEY_TO_LABEL = {key: mode_info["label"] for key, mode_info in MODES.items()}


class NestingModeWidget(tk.Frame):
    """Widget de seleção de modo de encaixe industrial (Camada 1 de UX)."""

    def __init__(
        self,
        parent: tk.Widget,
        current_mode: str = "auto",
        on_mode_change: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        bg: Optional[str] = None,
        **kwargs,
    ):
        card_bg = bg or THEME.get("bg_card", "#f0f0f0")
        super().__init__(parent, bg=card_bg, **kwargs)

        self.on_mode_change = on_mode_change
        self._current_mode = current_mode if current_mode in MODES else "custom"

        # Frame superior com rótulo e combobox
        top_row = tk.Frame(self, bg=card_bg)
        top_row.pack(fill="x", pady=(0, 2))

        lbl_title = tk.Label(
            top_row,
            text="Modo de Encaixe:",
            bg=card_bg,
            fg=THEME.get("text_main", "#000000"),
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )
        lbl_title.pack(side="left", padx=(0, 8))

        mode_labels = [MODES[k]["label"] for k in MODES]
        self.cb_mode = ttk.Combobox(
            top_row,
            values=mode_labels,
            state="readonly",
            font=("Segoe UI", 9),
            width=30,
        )
        self.cb_mode.pack(side="left", fill="x", expand=True)
        self.cb_mode.bind("<<ComboboxSelected>>", self._on_combobox_selected)

        # Rótulo de descrição informativa do modo selecionado
        self.lbl_desc = tk.Label(
            self,
            text="",
            bg=card_bg,
            fg=THEME.get("text_dim", "#555555"),
            font=("Segoe UI", 8, "italic"),
            anchor="w",
            justify="left",
        )
        self.lbl_desc.pack(fill="x", pady=(2, 0))

        # Inicializa seleção
        self.set_mode(self._current_mode, notify=False)

    def _on_combobox_selected(self, event=None):
        label_val = self.cb_mode.get()
        mode_key = LABEL_TO_KEY.get(label_val, "custom")
        self._current_mode = mode_key
        self._update_description()
        if self.on_mode_change:
            self.on_mode_change(mode_key, MODES[mode_key])

    def _update_description(self):
        desc = MODES.get(self._current_mode, {}).get("description", "")
        self.lbl_desc.config(text=f"ℹ️  {desc}")

    def get_mode(self) -> str:
        """Retorna a chave do modo atualmente selecionado ('auto', 'fast', etc.)."""
        return self._current_mode

    def set_mode(self, mode: str, notify: bool = True):
        """Define o modo selecionado no widget."""
        clean_mode = str(mode).strip().lower()
        if clean_mode not in MODES:
            # Tenta encontrar por label
            clean_mode = LABEL_TO_KEY.get(mode, "custom")

        self._current_mode = clean_mode
        label = KEY_TO_LABEL.get(clean_mode, MODES["custom"]["label"])
        self.cb_mode.set(label)
        self._update_description()

        if notify and self.on_mode_change:
            self.on_mode_change(self._current_mode, MODES[self._current_mode])

    def get_mode_config(self, mode: Optional[str] = None) -> Dict[str, Any]:
        """Retorna o dicionário de configuração do modo solicitado ou atual."""
        target = mode if mode is not None else self._current_mode
        return dict(MODES.get(target, MODES["custom"]))
