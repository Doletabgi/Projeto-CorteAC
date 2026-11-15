"""Assistente de diagnóstico da sessão e controles técnicos de encaixe."""

from __future__ import annotations

from datetime import datetime
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Callable, Optional

from cad.session_diagnostics import check_session
from config import APP_NAME, APP_VERSION, THEME
from ui.icon_widgets import IconButton


class DebugPanel(tk.Frame):
    """Ajuda guiada para o operador, com os controles técnicos em uma aba própria."""

    ISSUES = {
        "check": (
            "Conferir minha sessão",
            "Confira material, moldes e espaços de corte. Selecione um resultado para saber o que fazer.",
            "Verificar sessão",
        ),
        "slow": (
            "O cálculo está lento",
            "Libere a memória temporária e tente gerar novamente. Seus moldes, sessões e layouts são mantidos.",
            "Liberar memória temporária",
        ),
        "support": (
            "Preciso de ajuda",
            "Salve um resumo da sessão e das verificações para enviar ao suporte, junto com a descrição do problema.",
            "Salvar relatório para suporte",
        ),
    }

    def __init__(self, parent: tk.Widget,
                 on_engine_change: Optional[Callable[[str], None]] = None,
                 bg: Optional[str] = None,
                 get_context: Optional[Callable[[], dict]] = None,
                 on_open_section: Optional[Callable[[str], None]] = None, **kwargs):
        self.card_bg = bg or THEME.get("bg_card", "#f0f0f0")
        super().__init__(parent, bg=self.card_bg, **kwargs)
        self.on_engine_change = on_engine_change
        self.get_context = get_context
        self.on_open_section = on_open_section
        self._current_mode = "custom"
        self._checks = []
        self._context = {}
        self._benchmark_running = False
        self._poll_id = None
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._label(self, "Como podemos ajudar?", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        self._label(self, "Confira a sessão, resolva dúvidas e prepare informações para o suporte.").pack(anchor="w", pady=(3, 12))
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)
        self.guide_tab = tk.Frame(self.tabs, bg=self.card_bg, padx=12, pady=10)
        self.advanced_tab = tk.Frame(self.tabs, bg=self.card_bg, padx=12, pady=10)
        self.tabs.add(self.guide_tab, text="Ajuda rápida")
        self.tabs.add(self.advanced_tab, text="Avançado / suporte")
        self._build_guide()
        self._build_advanced()
        self.lbl_action_msg = self._label(self, "Escolha uma opção para começar.", wraplength=710, fg="#264b6a")
        # Reserva o rodapé antes da área expansível, inclusive em telas menores.
        self.tabs.pack_forget()
        self.lbl_action_msg.pack(side="bottom", fill="x", pady=(10, 0))
        self.tabs.pack(fill="both", expand=True)

    def _label(self, parent, text, **kwargs):
        options = dict(bg=self.card_bg, fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w", justify="left")
        options.update(kwargs)
        return tk.Label(parent, text=text, **options)

    def _button(self, parent, text, command):
        return IconButton(parent, text=text, command=command,
                          bg=THEME["bg_surface"], fg=THEME["text_main"],
                          font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2")

    def _build_guide(self):
        parent = self.guide_tab
        self.lbl_session = self._label(parent, "", font=("Segoe UI", 9, "bold"), wraplength=690)
        self.lbl_session.pack(fill="x", pady=(0, 10))
        self._label(parent, "O que você precisa?", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        choices = tk.Frame(parent, bg=self.card_bg)
        choices.pack(fill="x", pady=5)
        self.issue_var = tk.StringVar(self, value="check")
        for key, (label, _, _) in self.ISSUES.items():
            tk.Radiobutton(choices, text=label, variable=self.issue_var, value=key,
                           bg=self.card_bg, activebackground=self.card_bg,
                           font=("Segoe UI", 9), command=self._on_issue_changed).pack(side="left", padx=(0, 12))
        self.lbl_help = self._label(parent, "", wraplength=690, height=2)
        self.lbl_help.pack(fill="x")
        actions = tk.Frame(parent, bg=self.card_bg)
        actions.pack(fill="x", pady=(2, 12))
        self.btn_guided = self._button(actions, "Verificar sessão", self._run_guided_action)
        self.btn_guided.pack(side="left")
        self.btn_report = self._button(actions, "Salvar relatório…", self.save_support_report)
        self.btn_report.pack(side="right")

        self.lbl_summary = self._label(parent, "Resultados da verificação", font=("Segoe UI", 10, "bold"))
        self.lbl_summary.pack(fill="x", pady=(0, 5))
        table_frame = tk.Frame(parent, bg=self.card_bg)
        table_frame.pack(fill="both", expand=True)
        self.results = ttk.Treeview(table_frame, columns=("status", "item", "result"), show="headings", height=6, selectmode="browse")
        for name, label, width in (("status", "Situação", 85), ("item", "Verificação", 155), ("result", "O que encontramos", 440)):
            self.results.heading(name, text=label)
            self.results.column(name, width=width, minwidth=60, stretch=(name == "result"))
        self.results.tag_configure("ok", foreground="#246435")
        self.results.tag_configure("attention", foreground="#9a3e12")
        self.results.tag_configure("info", foreground="#305b86")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.results.yview)
        self.results.configure(yscrollcommand=scroll.set)
        self.results.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.results.bind("<<TreeviewSelect>>", self._show_selected_check)
        self.results.bind("<Double-1>", lambda _: self._open_selected_section())

        details = tk.LabelFrame(parent, text="Próximo passo", bg=self.card_bg, padx=10, pady=8)
        details.pack(fill="x", pady=(10, 4))
        self.lbl_guidance = self._label(details, "Selecione um resultado acima para ver a orientação.", wraplength=660, height=2)
        self.lbl_guidance.pack(fill="x")
        self.btn_open_section = self._button(details, "Abrir sessão", self._open_selected_section)
        self.btn_open_section.pack(anchor="e", pady=(3, 0))
        self.btn_open_section.config(state="disabled")
        note = self._label(parent, "Conferência de dados e configurações. Revise as posições das peças no Layout Editor.",
                           wraplength=690, fg=THEME.get("text_dim", "#555555"), font=("Segoe UI", 8))
        # O resultado pode rolar; a orientação e seu botão precisam ficar visíveis.
        table_frame.pack_forget()
        details.pack_forget()
        note.pack(side="bottom", fill="x", pady=(5, 0))
        details.pack(side="bottom", fill="x", pady=(10, 4))
        table_frame.pack(fill="both", expand=True)
        self._on_issue_changed()

    def _build_advanced(self):
        parent = self.advanced_tab
        self._label(parent, "Controles técnicos", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self._label(parent, "Use estes recursos quando precisar investigar um problema com o suporte.", wraplength=680).pack(fill="x", pady=(4, 14))
        engine_row = tk.Frame(parent, bg=self.card_bg)
        engine_row.pack(fill="x")
        self._label(engine_row, "Motor de cálculo:").pack(side="left", padx=(0, 8))
        self.cb_engine = ttk.Combobox(engine_row, values=["nfp", "python", "ia_teste"], state="readonly", width=14)
        engine = os.environ.get("CORTEAC_BACKEND", "nfp").strip().lower()
        self.cb_engine.set(engine if engine in ("nfp", "python", "ia_teste") else "nfp")
        self.cb_engine.pack(side="left")
        self.cb_engine.bind("<<ComboboxSelected>>", self._on_engine_selected)
        self.lbl_auto_badge = self._label(engine_row, "Definido pelo modo Automático", fg="#246435")
        self.lbl_auto_badge.pack(side="left", padx=8)
        self._label(parent, "nfp: motor geométrico · python: motor de referência · ia_teste: motor experimental.", wraplength=680).pack(fill="x", pady=(6, 14))
        self.var_sanity = tk.BooleanVar(self, value=os.environ.get("CORTEAC_NFP_SANITY", "0").strip() == "1")
        self.chk_sanity = tk.Checkbutton(parent, text="Conferência extra de sobreposição no próximo cálculo",
                                        variable=self.var_sanity, command=self._on_sanity_toggle,
                                        bg=self.card_bg, activebackground=self.card_bg, font=("Segoe UI", 9))
        self.chk_sanity.pack(anchor="w")
        self._label(parent, "Ativa a checagem adicional do motor NFP. Pode aumentar o tempo de cálculo; fica ativa até desmarcar.", wraplength=660).pack(fill="x", padx=24, pady=(2, 12))
        self.var_profile = tk.BooleanVar(self, value=False)
        self.chk_profile = tk.Checkbutton(parent, text="Registrar tempos detalhados no próximo cálculo (cProfile)",
                                         variable=self.var_profile, bg=self.card_bg, activebackground=self.card_bg,
                                         font=("Segoe UI", 9))
        self.chk_profile.pack(anchor="w")
        self._label(parent, "O detalhamento aparece no log técnico do programa. A opção é desmarcada após um uso.", wraplength=660).pack(fill="x", padx=24, pady=(2, 16))
        self.btn_clear_cache = self._button(parent, "Liberar memória temporária", self.clear_caches)
        self.btn_clear_cache.pack(anchor="w")
        self._label(parent, "Libera cálculos guardados em memória. Não apaga moldes, sessões ou layouts salvos.", wraplength=680).pack(fill="x", pady=(4, 16))
        self.btn_export_bench = self._button(parent, "Testar desempenho com exemplos…", self.export_benchmark)
        self.btn_export_bench.pack(anchor="w")
        self._label(parent, "Executa um teste com 60 peças de exemplo, em duas rodadas, e salva um arquivo JSON para o suporte.", wraplength=680).pack(fill="x", pady=(4, 8))
        self.benchmark_progress = ttk.Progressbar(parent, mode="indeterminate")
        self.lbl_version = self._label(parent, f"{APP_NAME} {APP_VERSION}", fg="#555555", font=("Segoe UI", 8))
        self.lbl_version.pack(anchor="w", pady=10)

    def _on_issue_changed(self):
        _, help_text, action = self.ISSUES[self.issue_var.get()]
        self.lbl_help.config(text=help_text)
        self.btn_guided.config(text=action)

    def _run_guided_action(self):
        action = self.issue_var.get()
        if action == "slow":
            self.clear_caches()
        elif action == "support":
            self.save_support_report()
        else:
            self.refresh_context()

    def refresh_context(self):
        """Relê a sessão a cada verificação e reabertura da janela."""
        try:
            self._context = self.get_context() if self.get_context else {}
            self._checks = check_session(self._context)
        except Exception as exc:
            self._checks = []
            self.results.delete(*self.results.get_children())
            self.btn_open_section.config(state="disabled")
            self.lbl_guidance.config(text="Volte à sessão e tente verificar novamente.")
            self.lbl_summary.config(text="Não foi possível verificar a sessão")
            self.lbl_action_msg.config(text=f"Falha ao ler os dados: {exc}")
            return False
        mode = self._context.get("mode", self._current_mode)
        modes = {"auto": "Automático", "custom": "Personalizado", "fast": "Rápido", "economic": "Econômico",
                 "tapes": "Fitas / Correias", "remnants": "Sobras / Retalhos"}
        self.lbl_session.config(text=f"Sessão #{self._context.get('session_id', '—')} · {self._context.get('session_name', '')} · Modo {modes.get(mode, mode)}")
        self.var_sanity.set(os.environ.get("CORTEAC_NFP_SANITY", "0").strip() == "1")
        self.results.delete(*self.results.get_children())
        labels = {"ok": "OK", "attention": "Ajustar", "info": "Conferir"}
        for check in self._checks:
            self.results.insert("", "end", iid=check["key"], values=(labels[check["status"]], check["title"], check["result"]), tags=(check["status"],))
        pending = sum(check["status"] == "attention" for check in self._checks)
        self.lbl_summary.config(text=f"{pending} ponto(s) para ajustar" if pending else "Nenhuma pendência básica encontrada")
        first = next((c for c in self._checks if c["status"] == "attention"),
                     next((c for c in self._checks if c["status"] == "info"), self._checks[0]))
        self.results.selection_set(first["key"])
        self._show_selected_check()
        self.lbl_action_msg.config(text="Verificação atualizada. Selecione uma linha para ver o próximo passo.")
        return True

    def _selected_check(self):
        selected = self.results.selection()
        return next((c for c in self._checks if selected and c["key"] == selected[0]), None)

    def _show_selected_check(self, event=None):
        check = self._selected_check()
        if check is None:
            return
        self.lbl_guidance.config(text=check["guidance"])
        labels = {"materials": "Abrir Materiais", "shapes": "Abrir Moldes", "general": "Abrir Geral", "layouts": "Abrir Layout"}
        self.btn_open_section.config(text=labels[check["target"]], state="normal" if self.on_open_section else "disabled")

    def _open_selected_section(self):
        check = self._selected_check()
        if check and self.on_open_section:
            self.on_open_section(check["target"])

    def _on_engine_selected(self, event=None):
        eng = self.cb_engine.get()
        os.environ["CORTEAC_BACKEND"] = eng
        if self.on_engine_change:
            self.on_engine_change(eng)

    def _on_sanity_toggle(self):
        os.environ["CORTEAC_NFP_SANITY"] = "1" if self.var_sanity.get() else "0"

    def set_mode(self, mode: str):
        self._current_mode = mode
        if mode == "auto":
            self.lbl_auto_badge.pack(side="left", padx=8)
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
        """Consome a solicitação de perfil uma única vez."""
        requested = self.var_profile.get()
        self.var_profile.set(False)
        return requested

    def _can_run_maintenance(self):
        if self._benchmark_running:
            self.lbl_action_msg.config(text="Aguarde o teste de desempenho terminar.")
            return False
        context = self.get_context() if self.get_context else {}
        if context.get("nesting_in_progress"):
            self.lbl_action_msg.config(text="Há um encaixe sendo calculado. Aguarde terminar para executar esta ação.")
            return False
        return True

    def clear_caches(self):
        if not self._can_run_maintenance():
            return
        from cad.geometry import clear_transform_cache
        from cad.nfp import clear_nfp_cache
        from cad.macro_engine import clear_macro_caches
        failures = []
        for clear in (clear_transform_cache, clear_nfp_cache, clear_macro_caches):
            try:
                clear()
            except Exception as exc:
                failures.append(str(exc))
        if failures:
            self.lbl_action_msg.config(text="A liberação ficou incompleta: " + "; ".join(failures))
        else:
            self.lbl_action_msg.config(text="Memória temporária liberada. Volte à sessão e tente Gerar novamente. Seus dados foram mantidos.")

    def save_support_report(self):
        if not self.refresh_context():
            return
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), title="Salvar relatório para suporte",
                                          initialfile=f"diagnostico_sessao_{self._context.get('session_id', 'atual')}.txt",
                                          defaultextension=".txt", filetypes=[("Relatório de texto", "*.txt")])
        if not path:
            return
        mode = self._context.get("mode", self._current_mode)
        effective_engine = self.get_engine() if mode == "custom" else "nfp"
        lines = [f"{APP_NAME} {APP_VERSION} — Diagnóstico da sessão", datetime.now().astimezone().isoformat(timespec="seconds"),
                 self.lbl_session.cget("text"), f"Motivo: {self.ISSUES[self.issue_var.get()][0]}",
                 f"Motor previsto: {effective_engine} | Estratégia: {self._context.get('strategy', '—')} | Parâmetros: {self._context.get('params', '—')}",
                 f"Conferência extra: {'ativa' if self.var_sanity.get() else 'desativada'}", "",
                 "Verificação de cadastro e configurações; não analisa colisões entre peças."]
        for check in self._checks:
            lines.extend(["", f"{check['title']}: {check['result']}", check["guidance"]])
        try:
            with open(path, "w", encoding="utf-8") as report:
                report.write("\n".join(lines) + "\n")
        except OSError as exc:
            self.lbl_action_msg.config(text=f"Não foi possível salvar o relatório: {exc}")
            return
        self.lbl_action_msg.config(text=f"Relatório salvo em {path}. Envie ao suporte com a descrição do problema.")

    def export_benchmark(self):
        if not self._can_run_maintenance():
            return
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), title="Salvar teste de desempenho",
                                          initialfile="teste_desempenho.json", defaultextension=".json",
                                          filetypes=[("Relatório JSON", "*.json")])
        if not path:
            return
        self._benchmark_running = True
        self.btn_export_bench.config(state="disabled")
        self.btn_clear_cache.config(state="disabled")
        self.benchmark_progress.pack(fill="x", pady=5)
        self.benchmark_progress.start()
        self.lbl_action_msg.config(text="Testando com peças de exemplo… Aguarde. A sessão não será recalculada.")
        results_queue = queue.Queue()

        def worker():
            try:
                from tools.bench_nest import run_benchmark
                results = run_benchmark(pieces=60, runs=2, engines=["flashnestsheet"])
                with open(path, "w", encoding="utf-8") as output:
                    json.dump(results, output, indent=2, ensure_ascii=False)
                results_queue.put((True, path))
            except Exception as exc:
                results_queue.put((False, str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_benchmark(results_queue)

    def _poll_benchmark(self, results_queue):
        self._poll_id = None
        try:
            success, detail = results_queue.get_nowait()
        except queue.Empty:
            self._poll_id = self.after(100, lambda: self._poll_benchmark(results_queue))
            return
        self._benchmark_running = False
        self.benchmark_progress.stop()
        self.benchmark_progress.pack_forget()
        self.btn_export_bench.config(state="normal")
        self.btn_clear_cache.config(state="normal")
        self.lbl_action_msg.config(text=f"Teste concluído. Relatório salvo em {detail}." if success else f"Não foi possível concluir o teste: {detail}")

    def _on_destroy(self, event):
        if event.widget is self and self._poll_id is not None:
            self.after_cancel(self._poll_id)
            self._poll_id = None
