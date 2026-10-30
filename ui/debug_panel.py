"""
JobManager 2000 (Python Edition)
ui/debug_panel.py - Camada 4: Painel de Debug & Diagnóstico

Hierarquia de 4 Camadas:
1. Modo de Encaixe (NestingModeWidget)
2. Avançado (Estratégia, Parâmetros, Gap, Margens)
3. Macro / Aprendizado (MacroPanel)
4. Debug / Diagnóstico (DebugPanel)
"""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, Optional

from config import THEME


class DebugPanel(tk.LabelFrame):
    """
    Camada 4: Debug / Diagnóstico.
    Controles analíticos de desenvolvimento, profiling de execução,
    oráculo de colisão (Sanity pass), limpeza de caches e exportação de benchmarks.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_engine_change: Optional[Callable[[str], None]] = None,
        bg: Optional[str] = None,
        **kwargs,
    ):
        card_bg = bg or THEME.get("bg_card", "#f0f0f0")
        super().__init__(
            parent,
            text="Debug / Diagnóstico",
            bg=card_bg,
            fg=THEME.get("text_main", "#000000"),
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            padx=8,
            pady=6,
            **kwargs,
        )

        self.on_engine_change = on_engine_change
        self._current_mode = "auto"

        # Linha 1: Seletor de Motor (Engine) + Badge (auto)
        row1 = tk.Frame(self, bg=card_bg)
        row1.pack(fill="x", pady=(0, 4))

        tk.Label(
            row1,
            text="Engine ativo:",
            bg=card_bg,
            fg=THEME.get("text_main", "#000000"),
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left", padx=(0, 4))

        self.cb_engine = ttk.Combobox(
            row1,
            values=["nfp", "python", "ia_teste"],
            state="readonly",
            font=("Segoe UI", 9),
            width=12,
        )
        # Sincroniza com a variável de ambiente atual
        current_env = os.environ.get("CORTEAC_BACKEND", "nfp").strip().lower()
        if current_env not in ("nfp", "python", "ia_teste"):
            current_env = "nfp"
        self.cb_engine.set(current_env)
        self.cb_engine.pack(side="left", padx=(0, 6))
        self.cb_engine.bind("<<ComboboxSelected>>", self._on_engine_selected)

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
        self.lbl_auto_badge.pack(side="left", padx=(0, 6))

        # Versão do backend ativo
        self.lbl_version = tk.Label(
            row1,
            text="Versão: NFP 2026.4 / IA-teste 2026.5",
            bg=card_bg,
            fg=THEME.get("text_dim", "#555555"),
            font=("Segoe UI", 8, "italic"),
            anchor="e",
        )
        self.lbl_version.pack(side="right")

        # Linha 2: Checkboxes de Sanity pass e Profiling
        row2 = tk.Frame(self, bg=card_bg)
        row2.pack(fill="x", pady=(2, 4))

        self.var_sanity = tk.BooleanVar(value=os.environ.get("CORTEAC_NFP_SANITY", "0").strip() == "1")
        self.chk_sanity = tk.Checkbutton(
            row2,
            text="Sanity pass (oráculo SAT)",
            variable=self.var_sanity,
            bg=card_bg,
            fg=THEME.get("text_main", "#000000"),
            selectcolor="#ffffff",
            activebackground=card_bg,
            font=("Segoe UI", 8),
            command=self._on_sanity_toggle,
        )
        self.chk_sanity.pack(side="left", padx=(0, 16))

        self.var_profile = tk.BooleanVar(value=False)
        self.chk_profile = tk.Checkbutton(
            row2,
            text="cProfile no próximo nest",
            variable=self.var_profile,
            bg=card_bg,
            fg=THEME.get("text_main", "#000000"),
            selectcolor="#ffffff",
            activebackground=card_bg,
            font=("Segoe UI", 8),
        )
        self.chk_profile.pack(side="left")

        # Linha 3: Botões de ação (Limpar Caches | Exportar Benchmark)
        row3 = tk.Frame(self, bg=card_bg)
        row3.pack(fill="x", pady=(2, 0))

        self.btn_clear_cache = tk.Button(
            row3,
            text="🗑️ Limpar caches",
            bg=THEME.get("bg_surface", "#e0e0e0"),
            fg=THEME.get("text_main", "#000000"),
            font=("Segoe UI", 8),
            relief="raised",
            bd=1,
            cursor="hand2",
            padx=6,
            pady=0,
            command=self.clear_caches,
        )
        self.btn_clear_cache.pack(side="left", padx=(0, 8))

        self.btn_export_bench = tk.Button(
            row3,
            text="📊 Exportar benchmark",
            bg=THEME.get("bg_surface", "#e0e0e0"),
            fg=THEME.get("text_main", "#000000"),
            font=("Segoe UI", 8),
            relief="raised",
            bd=1,
            cursor="hand2",
            padx=6,
            pady=0,
            command=self.export_benchmark,
        )
        self.btn_export_bench.pack(side="left")

        self.lbl_action_msg = tk.Label(
            row3,
            text="",
            bg=card_bg,
            fg="#006400",
            font=("Segoe UI", 8, "italic"),
            anchor="e",
        )
        self.lbl_action_msg.pack(side="right")

    def _on_engine_selected(self, event=None):
        eng = self.cb_engine.get()
        os.environ["CORTEAC_BACKEND"] = eng
        if self.on_engine_change:
            self.on_engine_change(eng)

    def _on_sanity_toggle(self):
        val = "1" if self.var_sanity.get() else "0"
        os.environ["CORTEAC_NFP_SANITY"] = val

    def set_mode(self, mode: str):
        self._current_mode = mode
        if mode == "auto":
            self.lbl_auto_badge.pack(side="left", padx=(0, 6))
            self.cb_engine.config(state="disabled")
        else:
            self.lbl_auto_badge.pack_forget()
            self.cb_engine.config(state="readonly")

    def get_engine(self) -> str:
        return self.cb_engine.get()

    def set_engine(self, engine_name: str):
        if engine_name in ("nfp", "python", "ia_teste"):
            self.cb_engine.set(engine_name)
            os.environ["CORTEAC_BACKEND"] = engine_name

    def is_profile_requested(self) -> bool:
        """Verifica se o operador solicitou profiling e reseta a flag para falso (uso único)."""
        if self.var_profile.get():
            self.var_profile.set(False)
            return True
        return False

    def clear_caches(self):
        """Limpa todos os caches geométricos e de colisão da sessão."""
        cleared_count = 0
        try:
            from cad.geometry import clear_transform_cache

            clear_transform_cache()
            cleared_count += 1
        except Exception:
            pass

        try:
            from cad.nfp import clear_nfp_cache

            clear_nfp_cache()
            cleared_count += 1
        except Exception:
            pass

        try:
            from cad.macro_engine import clear_macro_caches

            clear_macro_caches()
            cleared_count += 1
        except Exception:
            pass

        self.lbl_action_msg.config(text="Caches limpos!")
        self.after(3000, lambda: self.lbl_action_msg.config(text=""))
        parent_window = self.winfo_toplevel()
        messagebox.showinfo(
            "Caches Limpos",
            "Todos os caches em memória (transformações trigonométricas, Minkowski NFP e contornos RDP) foram liberados.",
            parent=parent_window,
        )

    def export_benchmark(self):
        """Executa medição rápida de benchmark e salva o relatório em JSON."""
        parent_window = self.winfo_toplevel()
        save_path = filedialog.asksaveasfilename(
            parent=parent_window,
            defaultextension=".json",
            filetypes=[("Arquivos JSON", "*.json"), ("Todos os Arquivos", "*.*")],
            initialfile="benchmark_ia_teste_fase52.json",
            title="Exportar Relatório de Benchmark",
        )
        if not save_path:
            return

        self.btn_export_bench.config(state="disabled")
        self.lbl_action_msg.config(text="Gerando benchmark...")

        def _worker():
            try:
                from tools.bench_ia_teste_optimized import run_optimized_benchmark

                results = run_optimized_benchmark(pieces=100, runs=3)
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)

                def _on_success():
                    self.btn_export_bench.config(state="normal")
                    self.lbl_action_msg.config(text="Exportado com sucesso!")
                    self.after(4000, lambda: self.lbl_action_msg.config(text=""))
                    messagebox.showinfo(
                        "Benchmark Exportado",
                        f"Relatório de desempenho gravado com sucesso em:\n{save_path}",
                        parent=parent_window,
                    )

                self.after(0, _on_success)
            except Exception as e:

                def _on_error(err=str(e)):
                    self.btn_export_bench.config(state="normal")
                    self.lbl_action_msg.config(text="Erro ao exportar")
                    messagebox.showerror(
                        "Falha no Benchmark",
                        f"Ocorreu um erro ao gerar benchmark: {err}",
                        parent=parent_window,
                    )

                self.after(0, _on_error)

        threading.Thread(target=_worker, daemon=True).start()
