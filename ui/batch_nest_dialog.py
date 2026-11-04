"""
JobManager 2000 (Python Edition)
ui/batch_nest_dialog.py - Diálogo de Configuração e Execução de Auto-Nest em Massa
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Any, Optional, Callable

from config import THEME
from cad.layers_rule import encode_session_params


class BatchAutoNestDialog(tk.Toplevel):
    """
    Diálogo para revisar as sessões selecionadas em massa, ajustar as configurações
    de encaixe que serão salvas e disparar o cálculo do lote.
    """
    def __init__(
        self,
        parent,
        selected_sessions: List[Dict[str, Any]],
        initial_config: Optional[Dict[str, Any]] = None,
        on_start_batch: Optional[Callable[[List[Dict[str, Any]], Dict[str, Any]], None]] = None
    ):
        super().__init__(parent)
        self.parent = parent
        self.selected_sessions = selected_sessions or []
        self.initial_config = initial_config or {}
        self.on_start_batch = on_start_batch
        self.confirmed = False
        self.result_config = None

        self.title("⚡ Auto-Nest em Massa (Batch Nesting)")
        self.geometry("740x650")
        self.minsize(620, 560)
        self.configure(bg=THEME["bg_surface"])

        try:
            self.transient(parent)
            self.grab_set()
        except Exception:
            pass

        self.setup_ui()

    def setup_ui(self):
        # 1. Cabeçalho explicativo
        header_frame = tk.Frame(self, bg=THEME["bg_surface"], padx=12, pady=10)
        header_frame.pack(fill="x")

        tk.Label(
            header_frame,
            text=f"⚡ Cálculo em Massa de Auto-Nest ({len(self.selected_sessions)} sessões selecionadas)",
            font=("Segoe UI", 11, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["text_main"]
        ).pack(anchor="w")

        tk.Label(
            header_frame,
            text="As configurações abaixo serão salvas e aplicadas em todas as sessões selecionadas para o cálculo de encaixe.",
            font=("Segoe UI", 8),
            bg=THEME["bg_surface"],
            fg=THEME["text_muted"]
        ).pack(anchor="w", pady=(2, 0))

        # 2. Tabela de Sessões Selecionadas
        table_frame = tk.LabelFrame(
            self,
            text=f" Sessões a Processar ({len(self.selected_sessions)}) ",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            padx=8,
            pady=6
        )
        table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        columns = ("id", "job", "name", "shapes", "material", "status")
        self.tree_sess = ttk.Treeview(table_frame, columns=columns, show="headings", height=6, selectmode="browse")

        self.tree_sess.heading("id", text="ID")
        self.tree_sess.heading("job", text="Pasta / Produção")
        self.tree_sess.heading("name", text="Nome da Sessão")
        self.tree_sess.heading("shapes", text="Moldes")
        self.tree_sess.heading("material", text="Material")
        self.tree_sess.heading("status", text="Status")

        self.tree_sess.column("id", width=50, anchor="center")
        self.tree_sess.column("job", width=120, anchor="w")
        self.tree_sess.column("name", width=150, anchor="w")
        self.tree_sess.column("shapes", width=65, anchor="center")
        self.tree_sess.column("material", width=150, anchor="w")
        self.tree_sess.column("status", width=80, anchor="center")

        sb_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_sess.yview)
        self.tree_sess.configure(yscrollcommand=sb_y.set)

        self.tree_sess.pack(side="left", fill="both", expand=True)
        sb_y.pack(side="right", fill="y")

        has_warning = False
        for s in self.selected_sessions:
            s_id = s.get("id")
            s_job = s.get("job") or "ProduçãoNova"
            s_name = s.get("name") or f"Sessão #{s_id}"
            shapes = s.get("shapes") or []
            s_shapes = len(shapes)
            mat = s.get("material")
            mat_txt = "(não definido)"
            if isinstance(mat, dict):
                mat_txt = f"{mat.get('id', '')} {mat.get('name', '')}".strip()
            elif s.get("material_id"):
                mat_txt = str(s.get("material_id"))
            status = s.get("status") or "Stand by"

            tag = "normal"
            if s_shapes == 0:
                tag = "warn"
                has_warning = True

            self.tree_sess.insert(
                "", "end",
                values=(str(s_id), s_job, s_name, str(s_shapes), mat_txt, status),
                tags=(tag,)
            )

        self.tree_sess.tag_configure("warn", background="#fef08a")

        if has_warning:
            lbl_warn = tk.Label(
                table_frame,
                text="⚠️ Sessões destacadas em amarelo não contêm moldes e serão ignoradas no cálculo.",
                font=("Segoe UI", 8, "italic"),
                bg=THEME["bg_surface"],
                fg="#b45309"
            )
            lbl_warn.pack(anchor="w", pady=(4, 0))

        # 3. Painel de Configurações a Salvar em Massa
        config_frame = tk.LabelFrame(
            self,
            text=" Configurações de Cálculo a Salvar nas Sessões ",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            padx=10,
            pady=8
        )
        config_frame.pack(fill="x", padx=12, pady=(0, 10))

        # Linha 1: Modo de Encaixe e Estratégia
        r1 = tk.Frame(config_frame, bg=THEME["bg_surface"])
        r1.pack(fill="x", pady=2)

        tk.Label(r1, text="Modo de Encaixe:", width=15, anchor="w", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8)).pack(side="left")
        self.var_mode = tk.StringVar(value=self.initial_config.get("nesting_mode", "auto"))
        cb_mode = ttk.Combobox(r1, textvariable=self.var_mode, values=["auto", "economic", "fast", "custom"], state="readonly", width=14)
        cb_mode.pack(side="left", padx=(0, 20))

        tk.Label(r1, text="Estratégia:", width=12, anchor="w", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8)).pack(side="left")
        self.var_strat = tk.StringVar(value=self.initial_config.get("strategy", "flashnestsheet"))
        cb_strat = ttk.Combobox(r1, textvariable=self.var_strat, values=["flashnestsheet", "freenest", "tape_a"], width=18)
        cb_strat.pack(side="left")

        # Linha 2: Parâmetros e Máquina
        r2 = tk.Frame(config_frame, bg=THEME["bg_surface"])
        r2.pack(fill="x", pady=2)

        tk.Label(r2, text="Parâmetros:", width=15, anchor="w", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8)).pack(side="left")
        self.var_params = tk.StringVar(value=self.initial_config.get("params", "HighYield"))
        cb_params = ttk.Combobox(r2, textvariable=self.var_params, values=["HighYield", "FastNest", "stdNOTFill", "std", "ALTERNADO"], width=14)
        cb_params.pack(side="left", padx=(0, 20))

        tk.Label(r2, text="Máquina:", width=12, anchor="w", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8)).pack(side="left")
        self.var_machine = tk.StringVar(value=self.initial_config.get("machine", "ATOM FlashCut Flex 3020"))
        cb_machine = ttk.Combobox(r2, textvariable=self.var_machine, values=["ATOM FlashCut Flex 3020", "ATOM FlashCut", "ATOM IntelliCut"], width=18)
        cb_machine.pack(side="left")

        # Linha 3: Folga (Gap) e Margem
        r3 = tk.Frame(config_frame, bg=THEME["bg_surface"])
        r3.pack(fill="x", pady=2)

        tk.Label(r3, text="Folga (Gap mm):", width=15, anchor="w", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8)).pack(side="left")
        self.var_gap = tk.StringVar(value=str(self.initial_config.get("gap_mm", 1.0)))
        ent_gap = tk.Entry(r3, textvariable=self.var_gap, width=10, relief="sunken", bd=1)
        ent_gap.pack(side="left", padx=(0, 20))

        tk.Label(r3, text="Margem (mm):", width=12, anchor="w", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8)).pack(side="left")
        self.var_margin = tk.StringVar(value=str(self.initial_config.get("margin_mm", 10.0)))
        ent_margin = tk.Entry(r3, textvariable=self.var_margin, width=10, relief="sunken", bd=1)
        ent_margin.pack(side="left")

        # Linha 4: Checkboxes Refile e Sobras
        r4 = tk.Frame(config_frame, bg=THEME["bg_surface"])
        r4.pack(fill="x", pady=(4, 2))

        self.var_refile = tk.BooleanVar(value=bool(self.initial_config.get("refile_auto", True)))
        chk_refile = tk.Checkbutton(
            r4,
            text="✂ Refile automático dos layouts (final das peças + 1.0 mm)",
            variable=self.var_refile,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 8)
        )
        chk_refile.pack(side="left", padx=(0, 16))

        self.var_sobras = tk.BooleanVar(value=bool(self.initial_config.get("separar_sobras", True)))
        chk_sobras = tk.Checkbutton(
            r4,
            text="🗂️ Separar sobras de 4 camadas em layout de 2 camadas",
            variable=self.var_sobras,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 8)
        )
        chk_sobras.pack(side="left")

        # Linha 5: Salvar no banco
        r5 = tk.Frame(config_frame, bg=THEME["bg_surface"])
        r5.pack(fill="x", pady=(2, 0))

        self.var_save_db = tk.BooleanVar(value=True)
        chk_save = tk.Checkbutton(
            r5,
            text="💾 Salvar permanentemente estas configurações no banco de dados para todas as sessões",
            variable=self.var_save_db,
            bg=THEME["bg_surface"],
            fg="#0f766e",
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 8, "bold")
        )
        chk_save.pack(side="left")

        # Linha 6: Exportação automática para a máquina após o cálculo
        r6 = tk.Frame(config_frame, bg=THEME["bg_surface"])
        r6.pack(fill="x", pady=(6, 0))

        self.var_export_machine = tk.BooleanVar(value=bool(self.initial_config.get("export_machine", False)))
        chk_machine = tk.Checkbutton(
            r6,
            text="📤 Salvar cada sessão na pasta da máquina após o cálculo",
            variable=self.var_export_machine,
            bg=THEME["bg_surface"],
            fg="#0f766e",
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 8, "bold")
        )
        chk_machine.pack(side="left")

        r6b = tk.Frame(config_frame, bg=THEME["bg_surface"])
        r6b.pack(fill="x", pady=(1, 0))
        tk.Label(r6b, text="Destino:", width=8, anchor="w", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8)).pack(side="left")
        self.var_machine_dir = tk.StringVar(value=str(self.initial_config.get("machine_target_dir", "") or ""))
        ent_machine = tk.Entry(r6b, textvariable=self.var_machine_dir, width=48, relief="sunken", bd=1)
        ent_machine.pack(side="left", fill="x", expand=True)
        btn_machine = tk.Button(
            r6b, text="...", width=3, relief="raised", bd=1,
            bg=THEME["bg_surface"], fg=THEME["text_main"],
            command=self._choose_machine_dir
        )
        btn_machine.pack(side="left", padx=(3, 0))

        # 4. Barra de Botões inferior
        btn_bar = tk.Frame(self, bg=THEME["bg_surface"], padx=12, pady=10)
        btn_bar.pack(fill="x", side="bottom")

        btn_cancel = tk.Button(
            btn_bar,
            text="Cancelar",
            width=12,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            relief="raised",
            bd=2,
            font=("Segoe UI", 8),
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(6, 0))

        btn_start = tk.Button(
            btn_bar,
            text="⚡ Iniciar Cálculo em Massa",
            width=26,
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief="raised",
            bd=2,
            font=("Segoe UI", 9, "bold"),
            command=self.on_confirm
        )
        btn_start.pack(side="right")

    def _choose_machine_dir(self):
        initial = self.var_machine_dir.get().strip() or None
        chosen = filedialog.askdirectory(
            parent=self,
            title="Pasta de destino para a máquina (rede ou pendrive)",
            initialdir=initial,
            mustexist=False,
        )
        if chosen:
            self.var_machine_dir.set(chosen)

    def on_confirm(self):
        try:
            gap_val = float(self.var_gap.get().replace(",", "."))
        except ValueError:
            gap_val = 1.0

        try:
            margin_val = float(self.var_margin.get().replace(",", "."))
        except ValueError:
            margin_val = 10.0

        machine_dir = self.var_machine_dir.get().strip()
        if self.var_export_machine.get() and not machine_dir:
            machine_dir = filedialog.askdirectory(
                parent=self,
                title="Escolha a pasta de destino para a máquina",
                mustexist=False,
            )
            if not machine_dir:
                messagebox.showwarning(
                    "Destino da máquina",
                    "Escolha a pasta de destino ou desmarque a exportação automática.",
                    parent=self,
                )
                return
            self.var_machine_dir.set(machine_dir)

        raw_preset = self.var_params.get().strip() or "HighYield"
        encoded_params = encode_session_params(
            raw_preset,
            {
                "separar_sobras": "1" if self.var_sobras.get() else "0",
                "refile_auto": "1" if self.var_refile.get() else "0",
            }
        )

        self.result_config = {
            "nesting_mode": self.var_mode.get(),
            "strategy": self.var_strat.get().strip() or "flashnestsheet",
            "params": encoded_params,
            "raw_preset": raw_preset,
            "machine": self.var_machine.get().strip() or "ATOM FlashCut Flex 3020",
            "gap_mm": gap_val,
            "margin_mm": margin_val,
            "margins": {
                "left": margin_val,
                "right": margin_val,
                "top": margin_val,
                "bottom": margin_val
            },
            "refile_auto": self.var_refile.get(),
            "separar_sobras": self.var_sobras.get(),
            "save_to_db": self.var_save_db.get(),
            "export_machine": self.var_export_machine.get(),
            "machine_target_dir": machine_dir,
        }

        self.confirmed = True
        self.destroy()

        if callable(self.on_start_batch):
            self.on_start_batch(self.selected_sessions, self.result_config)


class BatchProgressDialog(tk.Toplevel):
    """
    Janela modal de progresso em tempo real durante a execução do lote de cálculo.
    """
    def __init__(self, parent, total_sessions: int, on_cancel: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.parent = parent
        self.total_sessions = max(1, total_sessions)
        self.on_cancel = on_cancel
        self.is_cancelled = False

        self.title("⚡ Progresso do Auto-Nest em Massa")
        self.geometry("520x340")
        self.minsize(440, 280)
        self.configure(bg=THEME["bg_surface"])

        try:
            self.transient(parent)
            self.grab_set()
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self.on_request_cancel)
        self.setup_ui()

    def setup_ui(self):
        pad = tk.Frame(self, bg=THEME["bg_surface"], padx=14, pady=12)
        pad.pack(fill="both", expand=True)

        self.lbl_main = tk.Label(
            pad,
            text=f"Iniciando cálculo de {self.total_sessions} sessões em massa...",
            font=("Segoe UI", 10, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            anchor="w"
        )
        self.lbl_main.pack(fill="x", pady=(0, 4))

        self.lbl_sub = tk.Label(
            pad,
            text="Preparando ambiente de aninhamento...",
            font=("Segoe UI", 8),
            bg=THEME["bg_surface"],
            fg=THEME["text_muted"],
            anchor="w"
        )
        self.lbl_sub.pack(fill="x", pady=(0, 8))

        # Barra de progresso geral do lote
        tk.Label(pad, text="Progresso Geral do Lote:", font=("Segoe UI", 8, "bold"), bg=THEME["bg_surface"], fg=THEME["text_main"], anchor="w").pack(fill="x")
        self.prog_overall = ttk.Progressbar(pad, orient="horizontal", mode="determinate", maximum=self.total_sessions)
        self.prog_overall.pack(fill="x", pady=(2, 8))

        # Barra de progresso da sessão atual
        tk.Label(pad, text="Progresso da Sessão Atual:", font=("Segoe UI", 8), bg=THEME["bg_surface"], fg=THEME["text_main"], anchor="w").pack(fill="x")
        self.prog_current = ttk.Progressbar(pad, orient="horizontal", mode="determinate", maximum=100)
        self.prog_current.pack(fill="x", pady=(2, 10))

        # Log de status das sessões concluídas
        log_frame = tk.Frame(pad, bg=THEME["bg_surface"], relief="sunken", bd=1)
        log_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.txt_log = tk.Text(log_frame, bg="#ffffff", fg="#000000", font=("Consolas", 8), height=5, wrap="word", relief="flat")
        self.txt_log.pack(side="left", fill="both", expand=True)
        sb_log = ttk.Scrollbar(log_frame, orient="vertical", command=self.txt_log.yview)
        sb_log.pack(side="right", fill="y")
        self.txt_log.configure(yscrollcommand=sb_log.set)

        # Botão de cancelamento
        self.btn_cancel = tk.Button(
            pad,
            text="Cancelar Lote",
            width=16,
            bg=THEME["bg_surface"],
            fg="#dc2626",
            font=("Segoe UI", 9, "bold"),
            relief="raised",
            bd=2,
            command=self.on_request_cancel
        )
        self.btn_cancel.pack(side="right")

    def update_overall(self, current_index: int, total: int, session_title: str):
        self.prog_overall["value"] = current_index
        pct = int((current_index / max(1, total)) * 100)
        self.lbl_main.config(text=f"Processando Sessão {current_index} de {total} ({pct}%)...")
        self.lbl_sub.config(text=f"Sessão atual: {session_title}")
        self.prog_current["value"] = 0

    def update_session_progress(self, current_placed: int, total_to_place: int):
        if total_to_place > 0:
            pct = min(100, int((current_placed / total_to_place) * 100))
            self.prog_current["value"] = pct

    def append_log(self, text: str):
        try:
            self.txt_log.insert("end", text + "\n")
            self.txt_log.see("end")
        except Exception:
            pass

    def on_request_cancel(self):
        if self.is_cancelled:
            return
        if messagebox.askyesno(
            "Cancelar Lote",
            "Deseja interromper o cálculo das próximas sessões do lote?\nAs sessões já calculadas serão preservadas.",
            parent=self
        ):
            self.is_cancelled = True
            self.btn_cancel.config(state="disabled", text="Cancelando...")
            self.lbl_sub.config(text="Cancelamento solicitado pelo operador. Finalizando sessão atual...")
            if callable(self.on_cancel):
                self.on_cancel()

    def mark_completed(self, summary_text: str):
        self.prog_overall["value"] = self.total_sessions
        self.prog_current["value"] = 100
        self.lbl_main.config(text="✓ Cálculo em massa concluído!")
        self.lbl_sub.config(text=summary_text)
        self.btn_cancel.config(text="Fechar", fg="#000000", state="normal", command=self.destroy)
