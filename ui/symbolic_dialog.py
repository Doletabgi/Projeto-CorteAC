"""Escolha da simbólica antes da colocação manual no molde."""
import tkinter as tk
from tkinter import ttk, messagebox
from cad.symbolic_notches import SYMBOL_TYPES, symbol_pattern


class SymbolicDialog(tk.Toplevel):
    def __init__(self, parent, size="", initial=None):
        super().__init__(parent)
        self.title("Simbólica — piques de identificação")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.result = None
        self.size = size
        box = ttk.Frame(self, padding=14)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="Tipo de simbólica:").pack(anchor="w")
        self.kind = tk.StringVar(value=initial if initial in SYMBOL_TYPES else next(iter(SYMBOL_TYPES)))
        combo = ttk.Combobox(box, textvariable=self.kind, values=list(SYMBOL_TYPES), state="readonly", width=39)
        combo.pack(fill="x", pady=(4, 8))
        combo.bind("<<ComboboxSelected>>", self._preview)
        self.preview = tk.Canvas(box, width=320, height=85, background="white", highlightthickness=1)
        self.preview.pack(fill="x")
        self.description = ttk.Label(box, wraplength=320)
        self.description.pack(anchor="w", pady=8)
        ttk.Label(box, text="Depois, clique próximo à borda da peça.\nOs piques alteram o contorno de corte. Ctrl+Z desfaz.").pack(anchor="w")
        buttons = ttk.Frame(box)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Adicionar à peça", command=self._accept).pack(side="right", padx=6)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._accept())
        self._preview()
        self.grab_set()
        combo.focus_set()
        self.wait_window()

    def _preview(self, event=None):
        self.preview.delete("all")
        try:
            pattern = symbol_pattern(self.kind.get(), self.size)
        except ValueError as exc:
            self.description.config(text=str(exc))
            return
        width = sum(w for w, _ in pattern)+len(pattern)-1
        scale = min(14, 280/max(1, width))
        x, baseline = (320-width*scale)/2, 25
        coords = [12, baseline]
        for w, d in pattern:
            coords.extend((x, baseline, x+w*scale/2, baseline+d*scale, x+w*scale, baseline))
            x += (w+1)*scale
        coords.extend((308, baseline))
        self.preview.create_line(*coords, fill="#b00080", width=2)
        dims = " + ".join(f"{w:g} × {d:g}" for w, d in pattern)
        self.description.config(text=f"{len(pattern)} pique(s) — largura × profundidade em mm: {dims}. Espaço entre piques: 1 mm.")

    def _accept(self):
        try:
            symbol_pattern(self.kind.get(), self.size)
        except ValueError as exc:
            messagebox.showwarning("Simbólica", str(exc), parent=self)
            return
        self.result = self.kind.get()
        self.destroy()
