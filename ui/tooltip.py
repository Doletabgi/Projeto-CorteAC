"""
ui/tooltip.py - Tooltip flutuante para os botões do Layout Editor.

Mostra o nome da ferramenta ao parar o mouse sobre o ícone (como no Layout.exe),
sem depender da barra de status e sem interferir no clique.
"""

from __future__ import annotations

import tkinter as tk

# Apenas um tooltip visível por vez em toda a aplicação
_ATIVO = {"tip": None}

DELAY_MS = 450


class ToolTip:
    """Tooltip simples: agenda no <Enter>, mostra perto do cursor e esconde no <Leave>."""

    def __init__(self, widget, text, delay_ms: int = DELAY_MS, bg: str = "#ffffe1", fg: str = "#000000"):
        self.widget = widget
        self.text = str(text)
        self.delay_ms = int(delay_ms)
        self.bg = bg
        self.fg = fg
        self._after_id = None
        self._win = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")
        widget.bind("<Destroy>", self._on_leave, add="+")

    # ---------------- ciclo de vida ----------------
    def _on_enter(self, _event=None):
        self._cancel()
        try:
            self._after_id = self.widget.after(self.delay_ms, self.show)
        except tk.TclError:
            self._after_id = None

    def _on_leave(self, _event=None):
        self._cancel()
        self.hide()

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except (tk.TclError, ValueError):
                pass
            self._after_id = None

    # ---------------- exibição ----------------
    def show(self):
        if self._win is not None or not self.text:
            return
        anterior = _ATIVO.get("tip")
        if anterior is not None and anterior is not self:
            anterior.hide()
        try:
            x = self.widget.winfo_pointerx() + 14
            y = self.widget.winfo_pointery() + 18
            win = tk.Toplevel(self.widget)
            win.wm_overrideredirect(True)   # sem barra de título
            win.wm_geometry(f"+{x}+{y}")
            try:
                win.wm_attributes("-topmost", True)
            except tk.TclError:
                pass
            lbl = tk.Label(
                win, text=self.text, justify="left",
                bg=self.bg, fg=self.fg, relief="solid", bd=1,
                font=("Segoe UI", 8), padx=6, pady=2,
            )
            lbl.pack()
            self._win = win
            _ATIVO["tip"] = self
        except tk.TclError:
            self._win = None

    def hide(self):
        if self._win is not None:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None
        if _ATIVO.get("tip") is self:
            _ATIVO["tip"] = None

    def is_visible(self) -> bool:
        return self._win is not None

    def update_text(self, text: str):
        """Permite atualizar o texto (ex.: botão que alterna entre Simular/Parar)."""
        self.text = str(text)
        if self._win is not None:
            self.hide()
