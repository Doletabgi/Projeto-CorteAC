"""
JobManager 2000 / CorteAC (Python Edition)
UI: Diálogo de Backup e Restauração de Moldes Cadastrados
Interface gráfica para geração e importação de pacotes de backup compactados (.zip / .csh),
e agendamento programado de datas e horas de backup automático.
"""

import os
import sys
import threading
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Union

import tkinter as tk
from ui.icon_widgets import IconButton, IconLabel, IconNotebook
from tkinter import ttk, filedialog, messagebox

from config import THEME, APP_NAME, APP_VERSION, EXPORTS_DIR
from cad.shape_backup import (
    create_shapes_backup,
    inspect_shapes_backup,
    restore_shapes_backup,
    BackupSummary,
    BackupInspectionResult,
    RestoreResult
)
from cad.shape_backup_scheduler import (
    get_schedule_config,
    save_schedule_config,
    get_next_scheduled_run,
    execute_scheduled_backup,
    list_backup_history,
    DEFAULT_BACKUPS_DIR
)


def open_folder_in_file_manager(folder_path: Union[str, Path]):
    """Abre um diretório no explorador de arquivos do sistema operacional."""
    p = Path(folder_path)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(str(p))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)], check=False)
        else:
            subprocess.run(["xdg-open", str(p)], check=False)
    except Exception as exc:
        print(f"[AVISO] Não foi possível abrir o diretório {p}: {exc}")


class ShapeBackupRestoreDialog(tk.Toplevel):
    """
    Diálogo modal completo para Backup, Restauração e Programação de Datas/Horas do Catálogo de Moldes.
    Permite:
      1. Exportar moldes e pastas em um pacote .zip atômico;
      2. Restaurar com pré-visualização, filtro de pastas e resolução de conflitos;
      3. Programar datas e horários automáticos de backup com retenção e monitoramento em segundo plano.
    """

    def __init__(
        self,
        parent,
        db=None,
        on_shapes_changed: Optional[Callable[[], None]] = None,
        on_sessions_changed: Optional[Callable[[], None]] = None,
        initial_tab: int = 0
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.db = db
        self.on_shapes_changed = on_shapes_changed
        self.on_sessions_changed = on_sessions_changed

        self.title("Backup, Restauração e Programação (Moldes e Sessões)")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.configure(bg=THEME["bg_surface"])

        dlg_w, dlg_h = 860, 710
        self.geometry(f"{dlg_w}x{dlg_h}")
        self.minsize(780, 580)

        # Centraliza sobre a janela pai
        self.update_idletasks()
        rx = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
        ry = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
        self.geometry(f"+{max(10, rx)}+{max(10, ry)}")

        # Estado interno - Backup Manual
        self.var_backup_type = tk.StringVar(value="all")  # "all", "shapes_only", "sessions_only"
        self.var_backup_scope = tk.StringVar(value="all")  # "all" ou "folder" (moldes)
        self.var_backup_folder = tk.StringVar(value="")
        self.var_backup_job_scope = tk.StringVar(value="all")  # "all" ou "job" (sessões)
        self.var_backup_job = tk.StringVar(value="")
        self.var_include_dies = tk.BooleanVar(value=True)
        self.var_backup_dest_path = tk.StringVar(value="")
        self.is_busy = False

        # Estado interno - Restauração
        self.var_restore_src_path = tk.StringVar(value="")
        self.var_restore_shapes = tk.BooleanVar(value=True)
        self.var_restore_sessions = tk.BooleanVar(value=True)
        self.var_conflict_strategy = tk.StringVar(value="overwrite")  # "overwrite", "skip", "rename"
        self.var_session_conflict_strategy = tk.StringVar(value="import_new_id")  # "import_new_id", "overwrite", "skip"
        self.var_restore_folder_mode = tk.StringVar(value="original")  # "original" ou "custom"
        self.var_restore_custom_folder = tk.StringVar(value="")
        self.var_restore_job_mode = tk.StringVar(value="original")  # "original" ou "custom"
        self.var_restore_custom_job = tk.StringVar(value="")
        self.current_inspection: Optional[BackupInspectionResult] = None

        # Estado interno - Programação / Agendamento
        self.var_sched_enabled = tk.BooleanVar(value=False)
        self.var_sched_mode = tk.StringVar(value="daily")  # "daily", "weekly", "interval", "specific_datetime"
        self.var_sched_times = tk.StringVar(value="18:00")
        self.var_sched_dow_0 = tk.BooleanVar(value=True)  # Seg
        self.var_sched_dow_1 = tk.BooleanVar(value=True)  # Ter
        self.var_sched_dow_2 = tk.BooleanVar(value=True)  # Qua
        self.var_sched_dow_3 = tk.BooleanVar(value=True)  # Qui
        self.var_sched_dow_4 = tk.BooleanVar(value=True)  # Sex
        self.var_sched_dow_5 = tk.BooleanVar(value=False) # Sáb
        self.var_sched_dow_6 = tk.BooleanVar(value=False) # Dom
        self.var_sched_interval_hours = tk.StringVar(value="4")
        self.var_sched_specific_date = tk.StringVar(value="")
        self.var_sched_specific_time = tk.StringVar(value="18:00")
        self.var_sched_backup_dir = tk.StringVar(value=str(DEFAULT_BACKUPS_DIR))
        self.var_sched_backup_type = tk.StringVar(value="all")  # "all", "shapes_only", "sessions_only"
        self.var_sched_max_retained = tk.StringVar(value="10")
        self.var_sched_include_dies = tk.BooleanVar(value=True)
        self.var_sched_scope = tk.StringVar(value="all")
        self.var_sched_folder = tk.StringVar(value="")

        self.setup_ui()
        self.load_initial_stats()
        self.load_schedule_into_ui()

        if initial_tab in (0, 1, 2):
            self.notebook.select(initial_tab)

        self.bind("<Escape>", lambda e: self._on_close())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        if self.is_busy:
            if not messagebox.askyesno("Operação em Andamento", "Uma operação está em execução. Deseja realmente fechar?", parent=self):
                return
        self.destroy()

    def setup_ui(self):
        # 1. Cabeçalho estilizado padrão CorteAC / Windows XP
        header_frame = tk.Frame(self, bg=THEME["title_bar_bg"], height=42, padx=14, pady=6)
        header_frame.pack(fill="x")

        lbl_title = IconLabel(
            header_frame,
            text="📦 Backup e Restauração de Moldes e Sessões de Corte",
            bg=THEME["title_bar_bg"],
            fg=THEME["title_bar_fg"],
            font=("Segoe UI", 11, "bold")
        )
        lbl_title.pack(side="left")

        lbl_sub = tk.Label(
            header_frame,
            text=f"{APP_NAME} v{APP_VERSION}",
            bg=THEME["title_bar_bg"],
            fg="#cbd5e1",
            font=("Segoe UI", 9)
        )
        lbl_sub.pack(side="right", padx=(0, 6))

        # 2. Container principal com abas
        main_box = tk.Frame(self, bg=THEME["bg_surface"], padx=8, pady=8)
        main_box.pack(fill="both", expand=True)

        self.notebook = IconNotebook(main_box)
        self.notebook.pack(fill="both", expand=True)

        self.tab_backup = tk.Frame(self.notebook, bg=THEME["bg_surface"], padx=10, pady=10)
        self.tab_restore = tk.Frame(self.notebook, bg=THEME["bg_surface"], padx=10, pady=10)
        self.tab_schedule = tk.Frame(self.notebook, bg=THEME["bg_surface"], padx=10, pady=10)

        self.notebook.add(self.tab_backup, text="  💾 Criar Backup (Exportar)  ")
        self.notebook.add(self.tab_restore, text="  📥 Restaurar Backup (Importar)  ")
        self.notebook.add(self.tab_schedule, text="  ⏰ Programar Backup (Agendamento)  ")

        self.setup_backup_tab()
        self.setup_restore_tab()
        self.setup_schedule_tab()

    # =========================================================================
    # ABA 1: CRIAR BACKUP (EXPORTAR)
    # =========================================================================
    def setup_backup_tab(self):
        # Card com estatísticas atuais do banco
        card_stats = tk.LabelFrame(
            self.tab_backup,
            text="Status Atual do Sistema",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=8
        )
        card_stats.pack(fill="x", pady=(0, 6))

        self.lbl_stats_summary = tk.Label(
            card_stats,
            text="Carregando estatísticas...",
            bg=THEME["bg_surface"],
            fg="#1e40af",
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_stats_summary.pack(fill="x")

        # Card informativo sobre o Agendamento Automático
        self.card_sched_banner = tk.Frame(self.tab_backup, bg="#f0fdf4", bd=1, relief="solid", padx=10, pady=5)
        self.card_sched_banner.pack(fill="x", pady=(0, 6))

        self.lbl_sched_banner_text = IconLabel(
            self.card_sched_banner,
            text="⏰ Agendamento Automático: Verificando...",
            bg="#f0fdf4",
            fg="#15803d",
            font=("Segoe UI", 8)
        )
        self.lbl_sched_banner_text.pack(side="left")

        btn_sched_goto = IconButton(
            self.card_sched_banner,
            text="Configurar Agendamento ➔",
            bg="#ffffff",
            fg="#15803d",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            cursor="hand2",
            command=lambda: self.notebook.select(2)
        )
        btn_sched_goto.pack(side="right")

        # Grupo 1: Conteúdo do Pacote (O que incluir)
        grp_content = tk.LabelFrame(
            self.tab_backup,
            text="Conteúdo a Incluir no Backup",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=6
        )
        grp_content.pack(fill="x", pady=(0, 6))

        rb_btype_all = tk.Radiobutton(
            grp_content,
            text="Backup Completo: Moldes Cadastrados + Sessões de Corte (Recomendado)",
            variable=self.var_backup_type,
            value="all",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9, "bold"),
            command=self._on_backup_type_change
        )
        rb_btype_all.pack(anchor="w", pady=1)

        f_sub_types = tk.Frame(grp_content, bg=THEME["bg_surface"])
        f_sub_types.pack(fill="x", pady=1)

        rb_btype_shapes = tk.Radiobutton(
            f_sub_types,
            text="Apenas Moldes Cadastrados",
            variable=self.var_backup_type,
            value="shapes_only",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9),
            command=self._on_backup_type_change
        )
        rb_btype_shapes.pack(side="left", padx=(0, 20))

        rb_btype_sessions = tk.Radiobutton(
            f_sub_types,
            text="Apenas Sessões de Corte (com placas e layouts)",
            variable=self.var_backup_type,
            value="sessions_only",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9),
            command=self._on_backup_type_change
        )
        rb_btype_sessions.pack(side="left")

        # Grupo 2: Filtros de Exportação
        self.grp_filters = tk.LabelFrame(
            self.tab_backup,
            text="Filtros de Exportação (Opcional)",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=6
        )
        self.grp_filters.pack(fill="x", pady=(0, 6))

        # Filtro de pasta de moldes
        self.f_shapes_filter_line = tk.Frame(self.grp_filters, bg=THEME["bg_surface"])
        self.f_shapes_filter_line.pack(fill="x", pady=2)

        tk.Label(self.f_shapes_filter_line, text="Moldes:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold"), width=10, anchor="w").pack(side="left")
        rb_all_shapes = tk.Radiobutton(
            self.f_shapes_filter_line,
            text="Todas as pastas",
            variable=self.var_backup_scope,
            value="all",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._on_backup_scope_change
        )
        rb_all_shapes.pack(side="left", padx=(0, 10))

        rb_fld_shapes = tk.Radiobutton(
            self.f_shapes_filter_line,
            text="Apenas da pasta:",
            variable=self.var_backup_scope,
            value="folder",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._on_backup_scope_change
        )
        rb_fld_shapes.pack(side="left")

        self.cb_backup_folder = ttk.Combobox(
            self.f_shapes_filter_line,
            textvariable=self.var_backup_folder,
            state="disabled",
            width=22
        )
        self.cb_backup_folder.pack(side="left", padx=6)

        # Filtro de sessões por pasta de produção (Job)
        self.f_sessions_filter_line = tk.Frame(self.grp_filters, bg=THEME["bg_surface"])
        self.f_sessions_filter_line.pack(fill="x", pady=2)

        tk.Label(self.f_sessions_filter_line, text="Sessões:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold"), width=10, anchor="w").pack(side="left")
        rb_all_jobs = tk.Radiobutton(
            self.f_sessions_filter_line,
            text="Todas as ordens",
            variable=self.var_backup_job_scope,
            value="all",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._on_backup_job_scope_change
        )
        rb_all_jobs.pack(side="left", padx=(0, 10))

        rb_fld_jobs = tk.Radiobutton(
            self.f_sessions_filter_line,
            text="Apenas da pasta (Job):",
            variable=self.var_backup_job_scope,
            value="job",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._on_backup_job_scope_change
        )
        rb_fld_jobs.pack(side="left")

        self.cb_backup_job = ttk.Combobox(
            self.f_sessions_filter_line,
            textvariable=self.var_backup_job,
            state="disabled",
            width=22
        )
        self.cb_backup_job.pack(side="left", padx=6)

        # Grupo: Opções de Compatibilidade
        grp_opts = tk.LabelFrame(
            self.tab_backup,
            text="Opções de Compatibilidade",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=6
        )
        grp_opts.pack(fill="x", pady=(0, 6))

        self.chk_dies = tk.Checkbutton(
            grp_opts,
            text="Incluir arquivos individuais .die (ATOM FlashCut) no pacote ZIP para máxima compatibilidade",
            variable=self.var_include_dies,
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        )
        self.chk_dies.pack(anchor="w")

        # Grupo: Arquivo de Destino
        grp_dest = tk.LabelFrame(
            self.tab_backup,
            text="Arquivo de Destino (.zip)",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=6
        )
        grp_dest.pack(fill="x", pady=(0, 6))

        f_dest_entry = tk.Frame(grp_dest, bg=THEME["bg_surface"])
        f_dest_entry.pack(fill="x", pady=2)

        self.ent_backup_dest = ttk.Entry(f_dest_entry, textvariable=self.var_backup_dest_path, font=("Segoe UI", 9))
        self.ent_backup_dest.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse_dest = IconButton(
            f_dest_entry,
            text="Procurar...",
            bg=THEME["bg_surface"],
            padx=10,
            command=self._on_browse_backup_dest
        )
        btn_browse_dest.pack(side="right")

        # Barra inferior de ação e progresso
        f_bottom = tk.Frame(self.tab_backup, bg=THEME["bg_surface"])
        f_bottom.pack(side="bottom", fill="x", pady=(4, 0))

        self.lbl_backup_status = tk.Label(
            f_bottom,
            text="Pronto para gerar backup.",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_backup_status.pack(fill="x", pady=(0, 2))

        self.prog_backup = ttk.Progressbar(f_bottom, orient="horizontal", mode="determinate")
        self.prog_backup.pack(fill="x", pady=(0, 6))

        self.btn_run_backup = IconButton(
            f_bottom,
            text="💾 Gerar Arquivo de Backup...",
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._on_start_backup
        )
        self.btn_run_backup.pack(side="right")

    # =========================================================================
    # ABA 2: RESTAURAR BACKUP (IMPORTAR)
    # =========================================================================
    def setup_restore_tab(self):
        # Grupo: Seleção de Arquivo
        grp_file = tk.LabelFrame(
            self.tab_restore,
            text="Arquivo de Backup para Restauração",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=6
        )
        grp_file.pack(fill="x", pady=(0, 6))

        f_file_row = tk.Frame(grp_file, bg=THEME["bg_surface"])
        f_file_row.pack(fill="x")

        self.ent_restore_src = ttk.Entry(f_file_row, textvariable=self.var_restore_src_path, font=("Segoe UI", 9))
        self.ent_restore_src.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse_src = IconButton(
            f_file_row,
            text="📂 Selecionar Backup...",
            bg=THEME["bg_surface"],
            padx=10,
            command=self._on_browse_restore_src
        )
        btn_browse_src.pack(side="right")

        # Painel de resumo da inspeção do arquivo selecionado
        self.card_inspection = tk.Frame(self.tab_restore, bg="#f8fafc", bd=1, relief="solid", padx=10, pady=5)
        self.card_inspection.pack(fill="x", pady=(0, 6))

        self.lbl_inspect_summary = tk.Label(
            self.card_inspection,
            text="Nenhum arquivo inspecionado no momento. Selecione um arquivo .zip ou .csh acima.",
            bg="#f8fafc",
            fg="#475569",
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_inspect_summary.pack(fill="x")

        # Container com Abas para Pré-visualização (Moldes e Sessões)
        self.nb_inspect = IconNotebook(self.tab_restore)
        self.nb_inspect.pack(fill="both", expand=True, pady=(0, 6))

        # Aba de Pré-visualização de Moldes
        self.tab_insp_shapes = tk.Frame(self.nb_inspect, bg=THEME["bg_surface"], padx=4, pady=4)
        self.nb_inspect.add(self.tab_insp_shapes, text="  Moldes Detectados (0)  ")

        cols_s = ("idx", "name", "size", "folder", "article", "points", "status")
        self.tree_inspect = ttk.Treeview(self.tab_insp_shapes, columns=cols_s, show="headings", height=5)
        self.tree_inspect.heading("idx", text="#")
        self.tree_inspect.heading("name", text="Nome do Molde")
        self.tree_inspect.heading("size", text="Tam.")
        self.tree_inspect.heading("folder", text="Pasta")
        self.tree_inspect.heading("article", text="Artigo")
        self.tree_inspect.heading("points", text="Vértices")
        self.tree_inspect.heading("status", text="No Sistema Atual?")

        self.tree_inspect.column("idx", width=35, anchor="center")
        self.tree_inspect.column("name", width=170, anchor="w")
        self.tree_inspect.column("size", width=45, anchor="center")
        self.tree_inspect.column("folder", width=110, anchor="w")
        self.tree_inspect.column("article", width=100, anchor="w")
        self.tree_inspect.column("points", width=60, anchor="center")
        self.tree_inspect.column("status", width=130, anchor="center")

        sb_tree_s_y = ttk.Scrollbar(self.tab_insp_shapes, orient="vertical", command=self.tree_inspect.yview)
        self.tree_inspect.configure(yscrollcommand=sb_tree_s_y.set)
        self.tree_inspect.pack(side="left", fill="both", expand=True)
        sb_tree_s_y.pack(side="right", fill="y")

        # Aba de Pré-visualização de Sessões
        self.tab_insp_sessions = tk.Frame(self.nb_inspect, bg=THEME["bg_surface"], padx=4, pady=4)
        self.nb_inspect.add(self.tab_insp_sessions, text="  Sessões de Corte (0)  ")

        cols_sess = ("idx", "code", "name", "job", "layouts", "pieces", "material", "status")
        self.tree_inspect_sess = ttk.Treeview(self.tab_insp_sessions, columns=cols_sess, show="headings", height=5)
        self.tree_inspect_sess.heading("idx", text="#")
        self.tree_inspect_sess.heading("code", text="Código")
        self.tree_inspect_sess.heading("name", text="Nome da Sessão")
        self.tree_inspect_sess.heading("job", text="Pasta/Job")
        self.tree_inspect_sess.heading("layouts", text="Placas/Layouts")
        self.tree_inspect_sess.heading("pieces", text="Peças")
        self.tree_inspect_sess.heading("material", text="Material")
        self.tree_inspect_sess.heading("status", text="No Sistema?")

        self.tree_inspect_sess.column("idx", width=35, anchor="center")
        self.tree_inspect_sess.column("code", width=80, anchor="center")
        self.tree_inspect_sess.column("name", width=150, anchor="w")
        self.tree_inspect_sess.column("job", width=110, anchor="w")
        self.tree_inspect_sess.column("layouts", width=95, anchor="center")
        self.tree_inspect_sess.column("pieces", width=60, anchor="center")
        self.tree_inspect_sess.column("material", width=110, anchor="w")
        self.tree_inspect_sess.column("status", width=120, anchor="center")

        sb_tree_sess_y = ttk.Scrollbar(self.tab_insp_sessions, orient="vertical", command=self.tree_inspect_sess.yview)
        self.tree_inspect_sess.configure(yscrollcommand=sb_tree_sess_y.set)
        self.tree_inspect_sess.pack(side="left", fill="both", expand=True)
        sb_tree_sess_y.pack(side="right", fill="y")

        # Opções de importação e conflito
        grp_import_opts = tk.LabelFrame(
            self.tab_restore,
            text="Opções de Restauração e Resolução de Conflitos",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6
        )
        grp_import_opts.pack(fill="x", pady=(0, 6))

        # Coluna Esquerda: Opções de Moldes
        col_left = tk.Frame(grp_import_opts, bg=THEME["bg_surface"])
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.chk_restore_shapes = tk.Checkbutton(
            col_left,
            text="Restaurar Moldes Cadastrados",
            variable=self.var_restore_shapes,
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8, "bold"),
            command=self._on_restore_scope_toggle
        )
        self.chk_restore_shapes.pack(anchor="w", pady=(0, 2))

        self.f_shapes_conflicts = tk.Frame(col_left, bg=THEME["bg_surface"], padx=14)
        self.f_shapes_conflicts.pack(fill="x")

        tk.Radiobutton(
            self.f_shapes_conflicts,
            text="Sobrescrever existente (Recomendado)",
            variable=self.var_conflict_strategy,
            value="overwrite",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        tk.Radiobutton(
            self.f_shapes_conflicts,
            text="Pular existentes (apenas novos)",
            variable=self.var_conflict_strategy,
            value="skip",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        tk.Radiobutton(
            self.f_shapes_conflicts,
            text="Renomear cópia (ex: 'Molde_copia')",
            variable=self.var_conflict_strategy,
            value="rename",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        f_cust_row = tk.Frame(self.f_shapes_conflicts, bg=THEME["bg_surface"])
        f_cust_row.pack(fill="x", pady=(2, 0))
        tk.Radiobutton(
            f_cust_row,
            text="Pastas originais",
            variable=self.var_restore_folder_mode,
            value="original",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._on_restore_folder_mode_change
        ).pack(side="left")

        tk.Radiobutton(
            f_cust_row,
            text="Forçar pasta:",
            variable=self.var_restore_folder_mode,
            value="custom",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._on_restore_folder_mode_change
        ).pack(side="left", padx=(6, 2))

        self.cb_restore_custom_folder = ttk.Combobox(
            f_cust_row,
            textvariable=self.var_restore_custom_folder,
            state="disabled",
            width=14
        )
        self.cb_restore_custom_folder.pack(side="left")

        # Coluna Direita: Opções de Sessões de Corte
        col_right = tk.Frame(grp_import_opts, bg=THEME["bg_surface"])
        col_right.pack(side="right", fill="both", expand=True)

        self.chk_restore_sessions = tk.Checkbutton(
            col_right,
            text="Restaurar Sessões de Corte",
            variable=self.var_restore_sessions,
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8, "bold"),
            command=self._on_restore_scope_toggle
        )
        self.chk_restore_sessions.pack(anchor="w", pady=(0, 2))

        self.f_sessions_conflicts = tk.Frame(col_right, bg=THEME["bg_surface"], padx=14)
        self.f_sessions_conflicts.pack(fill="x")

        tk.Radiobutton(
            self.f_sessions_conflicts,
            text="Importar com novo número sequencial (#189...) [Seguro]",
            variable=self.var_session_conflict_strategy,
            value="import_new_id",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        tk.Radiobutton(
            self.f_sessions_conflicts,
            text="Sobrescrever sessão existente com mesmo ID",
            variable=self.var_session_conflict_strategy,
            value="overwrite",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        tk.Radiobutton(
            self.f_sessions_conflicts,
            text="Pular existentes (ignorar se ID já existir)",
            variable=self.var_session_conflict_strategy,
            value="skip",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        f_cust_job_row = tk.Frame(self.f_sessions_conflicts, bg=THEME["bg_surface"])
        f_cust_job_row.pack(fill="x", pady=(2, 0))
        tk.Radiobutton(
            f_cust_job_row,
            text="Job original",
            variable=self.var_restore_job_mode,
            value="original",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._on_restore_job_mode_change
        ).pack(side="left")

        tk.Radiobutton(
            f_cust_job_row,
            text="Forçar Job:",
            variable=self.var_restore_job_mode,
            value="custom",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._on_restore_job_mode_change
        ).pack(side="left", padx=(6, 2))

        self.cb_restore_custom_job = ttk.Combobox(
            f_cust_job_row,
            textvariable=self.var_restore_custom_job,
            state="disabled",
            width=14
        )
        self.cb_restore_custom_job.pack(side="left")

        # Barra inferior de restauração
        f_bottom_res = tk.Frame(self.tab_restore, bg=THEME["bg_surface"])
        f_bottom_res.pack(side="bottom", fill="x", pady=(2, 0))

        self.lbl_restore_status = tk.Label(
            f_bottom_res,
            text="Selecione um arquivo de backup para inspecionar.",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_restore_status.pack(fill="x", pady=(0, 2))

        self.prog_restore = ttk.Progressbar(f_bottom_res, orient="horizontal", mode="determinate")
        self.prog_restore.pack(fill="x", pady=(0, 6))

        self.btn_run_restore = IconButton(
            f_bottom_res,
            text="📥 Iniciar Restauração no Banco...",
            bg="#16a34a",
            fg="#ffffff",
            activebackground="#15803d",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            padx=16,
            pady=6,
            cursor="hand2",
            state="disabled",
            command=self._on_start_restore
        )
        self.btn_run_restore.pack(side="right")

    def _on_backup_type_change(self):
        btype = self.var_backup_type.get()
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        if btype == "shapes_only":
            prefix = "backup_moldes_"
            if hasattr(self, "chk_dies"):
                self.chk_dies.config(state="normal")
        elif btype == "sessions_only":
            prefix = "backup_sessoes_"
            if hasattr(self, "chk_dies"):
                self.chk_dies.config(state="disabled")
        else:
            prefix = "backup_corteac_"
            if hasattr(self, "chk_dies"):
                self.chk_dies.config(state="normal")

        sugg_name = f"{prefix}{timestamp_str}.zip"
        sugg_path = Path(EXPORTS_DIR) / sugg_name
        self.var_backup_dest_path.set(str(sugg_path))

    def _on_backup_job_scope_change(self):
        if self.var_backup_job_scope.get() == "job":
            self.cb_backup_job.config(state="readonly")
        else:
            self.cb_backup_job.config(state="disabled")

    def _on_restore_job_mode_change(self):
        if self.var_restore_job_mode.get() == "custom":
            self.cb_restore_custom_job.config(state="normal")
        else:
            self.cb_restore_custom_job.config(state="disabled")

    def _on_restore_scope_toggle(self):
        s_on = self.var_restore_shapes.get()
        for child in self.f_shapes_conflicts.winfo_children():
            try:
                child.config(state="normal" if s_on else "disabled")
            except Exception:
                pass

        sess_on = self.var_restore_sessions.get()
        for child in self.f_sessions_conflicts.winfo_children():
            try:
                child.config(state="normal" if sess_on else "disabled")
            except Exception:
                pass

    # =========================================================================
    # ABA 3: PROGRAMAR BACKUP (AGENDAMENTO DE DATAS E HORAS)
    # =========================================================================
    def setup_schedule_tab(self):
        # Card superior de status do agendador
        self.card_sched_status = tk.Frame(self.tab_schedule, bg="#f1f5f9", bd=1, relief="solid", padx=12, pady=8)
        self.card_sched_status.pack(fill="x", pady=(0, 8))

        f_status_top = tk.Frame(self.card_sched_status, bg="#f1f5f9")
        f_status_top.pack(fill="x", pady=(0, 4))

        self.lbl_sched_badge = tk.Label(
            f_status_top,
            text="[ AGENDAMENTO DESATIVADO ]",
            bg="#64748b",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=2
        )
        self.lbl_sched_badge.pack(side="left")

        self.lbl_sched_next_run = tk.Label(
            f_status_top,
            text="Próxima execução: Nenhuma programada",
            bg="#f1f5f9",
            fg="#0f172a",
            font=("Segoe UI", 9, "bold"),
            padx=10
        )
        self.lbl_sched_next_run.pack(side="left")

        self.lbl_sched_last_run = tk.Label(
            self.card_sched_status,
            text="Último backup: Nunca executado",
            bg="#f1f5f9",
            fg="#475569",
            font=("Segoe UI", 8),
            anchor="w"
        )
        self.lbl_sched_last_run.pack(fill="x")

        # Grupo: Ativação
        grp_activation = tk.LabelFrame(
            self.tab_schedule,
            text="Controle do Agendador Automático",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=6
        )
        grp_activation.pack(fill="x", pady=(0, 8))

        chk_active = tk.Checkbutton(
            grp_activation,
            text="Ativar rotina de backup automático de moldes agendado (executa silenciosamente em segundo plano)",
            variable=self.var_sched_enabled,
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9, "bold"),
            command=self._on_sched_enabled_toggle
        )
        chk_active.pack(anchor="w")

        # Grupo: Periodicidade, Datas e Horas
        self.grp_sched_timing = tk.LabelFrame(
            self.tab_schedule,
            text="Programação de Datas e Horas",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=8
        )
        self.grp_sched_timing.pack(fill="x", pady=(0, 8))

        # Modos de agendamento (Radiobuttons)
        f_modes = tk.Frame(self.grp_sched_timing, bg=THEME["bg_surface"])
        f_modes.pack(fill="x", pady=(0, 6))

        tk.Radiobutton(
            f_modes,
            text="Diário (todos os dias)",
            variable=self.var_sched_mode,
            value="daily",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9),
            command=self._on_sched_mode_change
        ).pack(side="left", padx=(0, 14))

        tk.Radiobutton(
            f_modes,
            text="Dias da Semana específicos",
            variable=self.var_sched_mode,
            value="weekly",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9),
            command=self._on_sched_mode_change
        ).pack(side="left", padx=(0, 14))

        tk.Radiobutton(
            f_modes,
            text="A cada X horas (Intervalo)",
            variable=self.var_sched_mode,
            value="interval",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9),
            command=self._on_sched_mode_change
        ).pack(side="left", padx=(0, 14))

        tk.Radiobutton(
            f_modes,
            text="Data e Hora específica",
            variable=self.var_sched_mode,
            value="specific_datetime",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9),
            command=self._on_sched_mode_change
        ).pack(side="left")

        # Subpainel para Dias da Semana (Weekly)
        self.f_dow = tk.Frame(self.grp_sched_timing, bg=THEME["bg_surface"])
        self.f_dow.pack(fill="x", pady=(2, 6))

        tk.Label(self.f_dow, text="Dias permitidos:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 8))
        dows = [
            ("Seg", self.var_sched_dow_0),
            ("Ter", self.var_sched_dow_1),
            ("Qua", self.var_sched_dow_2),
            ("Qui", self.var_sched_dow_3),
            ("Sex", self.var_sched_dow_4),
            ("Sáb", self.var_sched_dow_5),
            ("Dom", self.var_sched_dow_6),
        ]
        for name, var in dows:
            tk.Checkbutton(self.f_dow, text=name, variable=var, bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left", padx=2)

        # Subpainel de Horários do Dia (Diário e Semanal)
        self.f_times_row = tk.Frame(self.grp_sched_timing, bg=THEME["bg_surface"])
        self.f_times_row.pack(fill="x", pady=(2, 4))

        tk.Label(self.f_times_row, text="Horários de Execução (HH:MM):", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        self.ent_sched_times = ttk.Entry(self.f_times_row, textvariable=self.var_sched_times, width=20, font=("Segoe UI", 9))
        self.ent_sched_times.pack(side="left", padx=(0, 8))

        tk.Label(self.f_times_row, text="Atalhos rápidos:", bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        for preset in ["12:00", "18:00", "12:00, 18:00", "22:00"]:
            btn_p = IconButton(
                self.f_times_row,
                text=preset,
                bg="#ffffff",
                font=("Segoe UI", 8),
                padx=4,
                pady=1,
                command=lambda p=preset: self._on_preset_time(p)
            )
            btn_p.pack(side="left", padx=2)

        # Subpainel de Intervalo em horas
        self.f_interval_row = tk.Frame(self.grp_sched_timing, bg=THEME["bg_surface"])
        self.f_interval_row.pack(fill="x", pady=(2, 4))
        tk.Label(self.f_interval_row, text="Executar a cada:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        cb_interval = ttk.Combobox(self.f_interval_row, textvariable=self.var_sched_interval_hours, values=["1", "2", "3", "4", "6", "8", "12", "24"], width=6)
        cb_interval.pack(side="left", padx=(0, 6))
        tk.Label(self.f_interval_row, text="horas após a última execução bem-sucedida.", bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left")

        # Subpainel de Data e Hora Específica
        self.f_specific_row = tk.Frame(self.grp_sched_timing, bg=THEME["bg_surface"])
        self.f_specific_row.pack(fill="x", pady=(2, 4))
        tk.Label(self.f_specific_row, text="Data (DD/MM/AAAA):", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))
        self.ent_specific_date = ttk.Entry(self.f_specific_row, textvariable=self.var_sched_specific_date, width=14, font=("Segoe UI", 9))
        self.ent_specific_date.pack(side="left", padx=(0, 10))

        tk.Label(self.f_specific_row, text="Hora (HH:MM):", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))
        self.ent_specific_time = ttk.Entry(self.f_specific_row, textvariable=self.var_sched_specific_time, width=10, font=("Segoe UI", 9))
        self.ent_specific_time.pack(side="left")

        # Grupo: Destino, Retenção e Formato
        grp_dest_ret = tk.LabelFrame(
            self.tab_schedule,
            text="Destino e Política de Retenção",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=6
        )
        grp_dest_ret.pack(fill="x", pady=(0, 8))

        f_stype_line = tk.Frame(grp_dest_ret, bg=THEME["bg_surface"])
        f_stype_line.pack(fill="x", pady=(0, 4))
        tk.Label(f_stype_line, text="Conteúdo a Salvar:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        tk.Radiobutton(f_stype_line, text="Moldes + Sessões de Corte (Completo)", variable=self.var_sched_backup_type, value="all", bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left", padx=(0, 8))
        tk.Radiobutton(f_stype_line, text="Apenas Moldes", variable=self.var_sched_backup_type, value="shapes_only", bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left", padx=(0, 8))
        tk.Radiobutton(f_stype_line, text="Apenas Sessões", variable=self.var_sched_backup_type, value="sessions_only", bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left")

        f_dest_line = tk.Frame(grp_dest_ret, bg=THEME["bg_surface"])
        f_dest_line.pack(fill="x", pady=(0, 4))

        tk.Label(f_dest_line, text="Pasta dos Backups:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        ent_sdir = ttk.Entry(f_dest_line, textvariable=self.var_sched_backup_dir, font=("Segoe UI", 9))
        ent_sdir.pack(side="left", fill="x", expand=True, padx=(0, 6))

        IconButton(f_dest_line, text="Procurar...", bg=THEME["bg_surface"], padx=6, command=self._on_browse_sched_dir).pack(side="left", padx=(0, 4))
        IconButton(f_dest_line, text="📂 Abrir Pasta", bg=THEME["bg_surface"], padx=6, command=self._on_open_sched_dir).pack(side="left")

        f_ret_line = tk.Frame(grp_dest_ret, bg=THEME["bg_surface"])
        f_ret_line.pack(fill="x")

        tk.Label(f_ret_line, text="Retenção automática:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))
        tk.Label(f_ret_line, text="Manter os últimos", bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        sp_ret = ttk.Spinbox(f_ret_line, from_=0, to=100, textvariable=self.var_sched_max_retained, width=5)
        sp_ret.pack(side="left", padx=(0, 4))
        tk.Label(f_ret_line, text="backups mais recentes (0 para manter todos)", bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left", padx=(0, 16))

        chk_sdies = tk.Checkbutton(
            f_ret_line,
            text="Incluir arquivos individuais .die no arquivo ZIP",
            variable=self.var_sched_include_dies,
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        )
        chk_sdies.pack(side="left")

        # Botões de Ação do Agendamento
        f_sched_actions = tk.Frame(self.tab_schedule, bg=THEME["bg_surface"])
        f_sched_actions.pack(fill="x", pady=(0, 6))

        btn_save_sched = IconButton(
            f_sched_actions,
            text="💾 Salvar Configurações de Agendamento",
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._on_save_schedule
        )
        btn_save_sched.pack(side="left", padx=(0, 8))

        btn_run_sched_now = IconButton(
            f_sched_actions,
            text="⚡ Executar Backup Agora",
            bg="#16a34a",
            fg="#ffffff",
            activebackground="#15803d",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._on_run_schedule_now
        )
        btn_run_sched_now.pack(side="left", padx=(0, 8))

        btn_refresh_hist = IconButton(
            f_sched_actions,
            text="🔄 Atualizar Lista",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            command=self._refresh_sched_history
        )
        btn_refresh_hist.pack(side="left")

        # Histórico de backups existentes na pasta
        grp_hist = tk.LabelFrame(
            self.tab_schedule,
            text="Histórico de Backups na Pasta de Destino",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=4
        )
        grp_hist.pack(fill="both", expand=True)

        cols_hist = ("date", "file", "size")
        self.tree_hist = ttk.Treeview(grp_hist, columns=cols_hist, show="headings", height=4)
        self.tree_hist.heading("date", text="Data e Hora")
        self.tree_hist.heading("file", text="Nome do Arquivo")
        self.tree_hist.heading("size", text="Tamanho")

        self.tree_hist.column("date", width=150, anchor="center")
        self.tree_hist.column("file", width=420, anchor="w")
        self.tree_hist.column("size", width=100, anchor="center")

        sb_hist_y = ttk.Scrollbar(grp_hist, orient="vertical", command=self.tree_hist.yview)
        self.tree_hist.configure(yscrollcommand=sb_hist_y.set)

        self.tree_hist.pack(side="left", fill="both", expand=True)
        sb_hist_y.pack(side="right", fill="y")

        # Barra inferior com ações para o arquivo selecionado no histórico
        f_hist_bottom = tk.Frame(grp_hist, bg=THEME["bg_surface"])
        f_hist_bottom.pack(side="bottom", fill="x", pady=(4, 0))

        btn_restore_selected = IconButton(
            f_hist_bottom,
            text="📥 Restaurar Backup Selecionado...",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._restore_selected_history_item
        )
        btn_restore_selected.pack(side="left", padx=4)

        self._on_sched_mode_change()

    # =========================================================================
    # LÓGICA DE PROGRAMAÇÃO E AGENDAMENTO
    # =========================================================================
    def load_schedule_into_ui(self):
        """Carrega a configuração de agendamento salva no banco e preenche os campos."""
        cfg = get_schedule_config(self.db)

        self.var_sched_enabled.set(bool(cfg.get("enabled", False)))
        self.var_sched_mode.set(cfg.get("mode", "daily"))

        times_list = cfg.get("times", ["18:00"])
        self.var_sched_times.set(", ".join(times_list))

        dow = set(cfg.get("days_of_week", [0, 1, 2, 3, 4]))
        self.var_sched_dow_0.set(0 in dow)
        self.var_sched_dow_1.set(1 in dow)
        self.var_sched_dow_2.set(2 in dow)
        self.var_sched_dow_3.set(3 in dow)
        self.var_sched_dow_4.set(4 in dow)
        self.var_sched_dow_5.set(5 in dow)
        self.var_sched_dow_6.set(6 in dow)

        self.var_sched_interval_hours.set(str(cfg.get("interval_hours", 4)))

        spec_dt = cfg.get("specific_datetime", "")
        if spec_dt:
            parts = spec_dt.split(" ")
            if len(parts) >= 2:
                try:
                    d_parsed = datetime.strptime(parts[0], "%Y-%m-%d").strftime("%d/%m/%Y")
                    self.var_sched_specific_date.set(d_parsed)
                except ValueError:
                    self.var_sched_specific_date.set(parts[0])
                self.var_sched_specific_time.set(parts[1])
            else:
                self.var_sched_specific_date.set(spec_dt)
        else:
            tomorrow = datetime.now() + timedelta(days=1)
            self.var_sched_specific_date.set(tomorrow.strftime("%d/%m/%Y"))
            self.var_sched_specific_time.set("18:00")

        self.var_sched_backup_dir.set(str(cfg.get("backup_dir") or DEFAULT_BACKUPS_DIR))
        self.var_sched_backup_type.set(str(cfg.get("backup_type", "all")))
        self.var_sched_max_retained.set(str(cfg.get("max_retained_backups", 10)))
        self.var_sched_include_dies.set(bool(cfg.get("include_dies", True)))

        self._update_sched_status_display(cfg)
        self._on_sched_mode_change()
        self._refresh_sched_history()

    def _update_sched_status_display(self, cfg: Optional[Dict[str, Any]] = None):
        """Atualiza os badges, texto de próxima execução e resumo na interface."""
        if cfg is None:
            cfg = get_schedule_config(self.db)

        is_enabled = bool(cfg.get("enabled", False))
        if is_enabled:
            self.lbl_sched_badge.config(text="[ AGENDAMENTO ATIVADO ]", bg="#15803d")
            next_dt = get_next_scheduled_run(cfg)
            if next_dt:
                now = datetime.now()
                delta = next_dt - now
                hours = int(delta.total_seconds() // 3600)
                minutes = int((delta.total_seconds() % 3600) // 60)
                diff_str = f"em {hours}h {minutes}min" if hours > 0 else f"em {minutes}min"
                if hours == 0 and minutes == 0:
                    diff_str = "agora"
                dt_fmt = next_dt.strftime("%d/%m/%Y às %H:%M")
                self.lbl_sched_next_run.config(text=f"Próxima execução: {dt_fmt} ({diff_str})", fg="#15803d")
                self.lbl_sched_banner_text.config(
                    text=f"⏰ Backup Automático: Ativado (Próximo: {dt_fmt})",
                    fg="#15803d"
                )
            else:
                self.lbl_sched_next_run.config(text="Próxima execução: Aguardando critérios...", fg="#b45309")
                self.lbl_sched_banner_text.config(text="⏰ Backup Automático: Ativado", fg="#15803d")
        else:
            self.lbl_sched_badge.config(text="[ AGENDAMENTO DESATIVADO ]", bg="#64748b")
            self.lbl_sched_next_run.config(text="Próxima execução: Nenhuma programada (Desativado)", fg="#64748b")
            self.lbl_sched_banner_text.config(
                text="⏰ Backup Automático: Desativado (clique em Configurar Agendamento para programar datas e horas)",
                fg="#64748b"
            )

        last_ts = cfg.get("last_run_timestamp", "")
        last_status = cfg.get("last_run_status", "")
        last_msg = cfg.get("last_run_message", "")
        if last_ts:
            try:
                dt_obj = datetime.fromisoformat(last_ts)
                ts_fmt = dt_obj.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                ts_fmt = last_ts
            st_icon = "✅" if last_status == "success" else "❌"
            self.lbl_sched_last_run.config(text=f"Último backup: {st_icon} {ts_fmt} — {last_msg}")
        else:
            self.lbl_sched_last_run.config(text="Último backup: Nunca executado nesta máquina")

    def _on_sched_enabled_toggle(self):
        """Alterna a visibilidade e status do agendador."""
        is_active = self.var_sched_enabled.get()
        if is_active:
            self.lbl_sched_badge.config(text="[ AGENDAMENTO ATIVADO ]", bg="#15803d")
        else:
            self.lbl_sched_badge.config(text="[ AGENDAMENTO DESATIVADO ]", bg="#64748b")

    def _on_sched_mode_change(self):
        """Ajusta a exibição dos subpainéis conforme o modo de agendamento selecionado."""
        mode = self.var_sched_mode.get()
        if mode == "daily":
            self.f_dow.pack_forget()
            self.f_interval_row.pack_forget()
            self.f_specific_row.pack_forget()
            self.f_times_row.pack(fill="x", pady=(2, 4))
        elif mode == "weekly":
            self.f_interval_row.pack_forget()
            self.f_specific_row.pack_forget()
            self.f_dow.pack(fill="x", pady=(2, 4))
            self.f_times_row.pack(fill="x", pady=(2, 4))
        elif mode == "interval":
            self.f_dow.pack_forget()
            self.f_times_row.pack_forget()
            self.f_specific_row.pack_forget()
            self.f_interval_row.pack(fill="x", pady=(2, 4))
        elif mode == "specific_datetime":
            self.f_dow.pack_forget()
            self.f_times_row.pack_forget()
            self.f_interval_row.pack_forget()
            self.f_specific_row.pack(fill="x", pady=(2, 4))

    def _on_preset_time(self, preset_str: str):
        self.var_sched_times.set(preset_str)

    def _on_browse_sched_dir(self):
        chosen = filedialog.askdirectory(
            parent=self,
            title="Selecione o Diretório de Destino para Backups Automáticos",
            initialdir=self.var_sched_backup_dir.get()
        )
        if chosen:
            self.var_sched_backup_dir.set(chosen)
            self._refresh_sched_history()

    def _on_open_sched_dir(self):
        d = self.var_sched_backup_dir.get().strip() or str(DEFAULT_BACKUPS_DIR)
        open_folder_in_file_manager(d)

    def _collect_schedule_config_from_ui(self) -> Dict[str, Any]:
        """Lê os valores atuais dos campos da UI e constrói o dicionário de configuração."""
        enabled = self.var_sched_enabled.get()
        mode = self.var_sched_mode.get()

        times_raw = self.var_sched_times.get()
        times_list = [t.strip() for t in times_raw.split(",") if t.strip()]

        dow_list = []
        if self.var_sched_dow_0.get(): dow_list.append(0)
        if self.var_sched_dow_1.get(): dow_list.append(1)
        if self.var_sched_dow_2.get(): dow_list.append(2)
        if self.var_sched_dow_3.get(): dow_list.append(3)
        if self.var_sched_dow_4.get(): dow_list.append(4)
        if self.var_sched_dow_5.get(): dow_list.append(5)
        if self.var_sched_dow_6.get(): dow_list.append(6)

        try:
            interval_h = max(1, int(self.var_sched_interval_hours.get()))
        except Exception:
            interval_h = 4

        spec_date = self.var_sched_specific_date.get().strip()
        spec_time = self.var_sched_specific_time.get().strip() or "18:00"
        normalized_spec = ""
        if spec_date:
            try:
                d_obj = datetime.strptime(spec_date, "%d/%m/%Y")
                normalized_spec = f"{d_obj.strftime('%Y-%m-%d')} {spec_time}"
            except ValueError:
                normalized_spec = f"{spec_date} {spec_time}"

        bdir = self.var_sched_backup_dir.get().strip() or str(DEFAULT_BACKUPS_DIR)
        btype = self.var_sched_backup_type.get().strip() or "all"

        try:
            max_ret = max(0, int(self.var_sched_max_retained.get()))
        except Exception:
            max_ret = 10

        inc_dies = self.var_sched_include_dies.get()

        current_cfg = get_schedule_config(self.db)

        return {
            "enabled": enabled,
            "mode": mode,
            "times": times_list,
            "days_of_week": dow_list,
            "interval_hours": interval_h,
            "specific_datetime": normalized_spec,
            "backup_dir": bdir,
            "backup_type": btype,
            "include_dies": inc_dies,
            "folder_filter": None,
            "session_filter_job": None,
            "max_retained_backups": max_ret,
            "last_run_timestamp": current_cfg.get("last_run_timestamp", ""),
            "last_run_status": current_cfg.get("last_run_status", ""),
            "last_run_message": current_cfg.get("last_run_message", ""),
            "last_run_file": current_cfg.get("last_run_file", "")
        }

    def _on_save_schedule(self):
        """Salva a configuração do agendamento e atualiza os indicadores."""
        cfg = self._collect_schedule_config_from_ui()

        if cfg["mode"] == "weekly" and not cfg["days_of_week"]:
            messagebox.showwarning(
                "Configuração Incompleta",
                "Você selecionou o modo 'Dias da Semana específicos', mas nenhum dia foi marcado. Marque pelo menos um dia.",
                parent=self
            )
            return

        saved = save_schedule_config(self.db, cfg)
        self._update_sched_status_display(saved)

        try:
            Path(saved["backup_dir"]).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        msg = "Configurações de agendamento de backup salvas com sucesso no banco de dados!"
        if saved.get("enabled"):
            next_dt = get_next_scheduled_run(saved)
            if next_dt:
                msg += f"\n\nPróximo backup programado para: {next_dt.strftime('%d/%m/%Y às %H:%M')}."
        else:
            msg += "\n\nO agendador está atualmente DESATIVADO."

        messagebox.showinfo("Agendamento Salvo", msg, parent=self)

    def _on_run_schedule_now(self):
        """Executa um backup imediatamente usando os parâmetros de agendamento."""
        if self.is_busy:
            messagebox.showwarning("Operação em Andamento", "Uma operação já está em execução.", parent=self)
            return

        cfg = self._collect_schedule_config_from_ui()

        self.is_busy = True
        self.lbl_sched_last_run.config(text="Executando backup programado agora...", fg="#0284c7")

        def _worker():
            try:
                res = execute_scheduled_backup(self.db, config=cfg, force=True)
                self.after(0, lambda: self._on_run_schedule_now_finished(res, None))
            except Exception as e:
                self.after(0, lambda: self._on_run_schedule_now_finished(None, str(e)))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _on_run_schedule_now_finished(self, res: Optional[Dict[str, Any]], err: Optional[str]):
        self.is_busy = False
        if err or (res and not res.get("success")):
            error_msg = err or (res.get("error") if res else "Erro desconhecido")
            self.lbl_sched_last_run.config(text=f"Erro na execução do backup: {error_msg}", fg="#b91c1c")
            messagebox.showerror("Erro no Backup", f"Falha ao executar backup imediato:\n\n{error_msg}", parent=self)
            return

        self._update_sched_status_display()
        self._refresh_sched_history()

        msg = (
            f"🎉 Backup executado com sucesso!\n\n"
            f"• Arquivo: {res.get('target_file')}\n"
            f"• Moldes exportados: {res.get('total_shapes', 0)}\n"
            f"• Sessões exportadas: {res.get('total_sessions', 0)}\n"
            f"• Placas/Layouts: {res.get('total_layouts', 0)}\n"
            f"• Tamanho: {res.get('file_size_bytes', 0) / 1024:.1f} KB\n"
            f"• Backups antigos purgados pela retenção: {res.get('purged_old_files', 0)}"
        )
        messagebox.showinfo("Backup Concluído", msg, parent=self)

    def _refresh_sched_history(self):
        """Recarrega a lista de arquivos de backup na pasta de destino."""
        bdir = self.var_sched_backup_dir.get().strip() or str(DEFAULT_BACKUPS_DIR)
        for item in self.tree_hist.get_children():
            self.tree_hist.delete(item)

        items = list_backup_history(bdir)
        for it in items:
            self.tree_hist.insert(
                "",
                "end",
                iid=it["filepath"],
                values=(it["date_display"], it["filename"], it["size_display"])
            )

    def _restore_selected_history_item(self):
        """Pega o item selecionado na tabela de histórico, joga para a Aba de Restauração e aciona a inspeção."""
        sel = self.tree_hist.selection()
        if not sel:
            messagebox.showinfo("Selecionar Arquivo", "Selecione um arquivo de backup na lista acima para restaurar.", parent=self)
            return

        filepath = sel[0]
        self.var_restore_src_path.set(filepath)
        self.notebook.select(1)
        self._inspect_file_and_populate(filepath)

    # =========================================================================
    # LÓGICA DE BACKUP MANUAL (EXPORTAÇÃO)
    # =========================================================================
    def load_initial_stats(self):
        """Carrega dados e estatísticas do banco de dados para a interface."""
        if not self.db:
            return

        try:
            shapes = self.db.get_all_shapes() if hasattr(self.db, "get_all_shapes") else []
            folders = self.db.get_shape_folders() if hasattr(self.db, "get_shape_folders") else []
            sessions = self.db.get_sessions() if hasattr(self.db, "get_sessions") else []

            total_shapes = len(shapes)
            total_folders = len(folders)
            total_sessions = len(sessions)
            total_layouts = 0
            jobs_set = set()
            for s in sessions:
                j = (s.get("job") or "").strip()
                if j:
                    jobs_set.add(j)
                if hasattr(self.db, "get_session_layouts"):
                    try:
                        total_layouts += len(self.db.get_session_layouts(s.get("id")))
                    except Exception:
                        pass

            jobs_list = sorted(list(jobs_set))

            self.lbl_stats_summary.config(
                text=f"📊 Moldes: {total_shapes} em {total_folders} pasta(s) | Sessões de Corte: {total_sessions} ({total_layouts} placas/layouts) em {len(jobs_list)} ordens/jobs."
            )

            self.cb_backup_folder["values"] = folders
            if folders:
                self.var_backup_folder.set(folders[0])

            self.cb_backup_job["values"] = jobs_list
            if jobs_list:
                self.var_backup_job.set(jobs_list[0])

            self.cb_restore_custom_folder["values"] = folders
            if folders:
                self.var_restore_custom_folder.set(folders[0])

            self.cb_restore_custom_job["values"] = jobs_list
            if jobs_list:
                self.var_restore_custom_job.set(jobs_list[0])

            self._on_backup_type_change()

        except Exception as e:
            self.lbl_stats_summary.config(text=f"Aviso ao carregar dados do catálogo: {str(e)}", fg="#b91c1c")

    def _on_backup_scope_change(self):
        if self.var_backup_scope.get() == "folder":
            self.cb_backup_folder.config(state="readonly")
        else:
            self.cb_backup_folder.config(state="disabled")

    def _on_browse_backup_dest(self):
        init_file = self.var_backup_dest_path.get()
        init_dir = str(Path(init_file).parent) if init_file else str(EXPORTS_DIR)
        init_name = Path(init_file).name if init_file else "backup_corteac.zip"

        chosen = filedialog.asksaveasfilename(
            parent=self,
            title="Salvar Arquivo de Backup do CorteAC",
            initialdir=init_dir,
            initialfile=init_name,
            filetypes=[("Pacote Compactado ZIP", "*.zip"), ("CorteAC Shape Archive", "*.csh"), ("Todos os Arquivos", "*.*")]
        )
        if chosen:
            if not (chosen.lower().endswith(".zip") or chosen.lower().endswith(".csh")):
                chosen += ".zip"
            self.var_backup_dest_path.set(chosen)

    def _on_start_backup(self):
        if self.is_busy:
            return

        dest_file = self.var_backup_dest_path.get().strip()
        if not dest_file:
            messagebox.showwarning("Destino Inválido", "Por favor, defina o arquivo de destino para o backup.", parent=self)
            return

        backup_type = self.var_backup_type.get()

        folder_filter = None
        if backup_type in ("all", "shapes_only") and self.var_backup_scope.get() == "folder":
            sel_f = self.var_backup_folder.get().strip()
            if not sel_f:
                messagebox.showwarning("Pasta não Selecionada", "Selecione uma pasta de moldes para filtrar o backup.", parent=self)
                return
            folder_filter = [sel_f]

        session_filter_job = None
        if backup_type in ("all", "sessions_only") and self.var_backup_job_scope.get() == "job":
            sel_j = self.var_backup_job.get().strip()
            if not sel_j:
                messagebox.showwarning("Job não Selecionado", "Selecione uma ordem/pasta (Job) para filtrar as sessões.", parent=self)
                return
            session_filter_job = sel_j

        include_dies = self.var_include_dies.get()

        self.is_busy = True
        self.btn_run_backup.config(state="disabled")
        self.prog_backup["value"] = 0
        self.lbl_backup_status.config(text="Iniciando exportação...", fg="#0284c7")

        def _worker():
            try:
                def _prog(cur, tot, msg):
                    pct = int((cur / max(1, tot)) * 100)
                    self.after(0, lambda: self._update_backup_progress(pct, msg))

                summary = create_shapes_backup(
                    db=self.db,
                    target_file=dest_file,
                    folder_filter=folder_filter,
                    include_die_files=include_dies,
                    backup_scope=backup_type,
                    session_filter_job=session_filter_job,
                    on_progress=_prog
                )
                self.after(0, lambda: self._on_backup_finished(summary, None))
            except Exception as e:
                self.after(0, lambda: self._on_backup_finished(None, str(e)))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _update_backup_progress(self, pct, msg):
        self.prog_backup["value"] = pct
        self.lbl_backup_status.config(text=f"[{pct}%] {msg}", fg="#0284c7")

    def _on_backup_finished(self, summary: Optional[BackupSummary], err: Optional[str]):
        self.is_busy = False
        self.btn_run_backup.config(state="normal")

        if err:
            self.prog_backup["value"] = 0
            self.lbl_backup_status.config(text=f"Erro no backup: {err}", fg="#b91c1c")
            messagebox.showerror("Erro no Backup", f"Falha ao gerar o arquivo de backup:\n\n{err}", parent=self)
            return

        if summary:
            self.prog_backup["value"] = 100
            sz_kb = summary.file_size_bytes / 1024
            items_str = []
            if summary.total_shapes > 0:
                items_str.append(f"{summary.total_shapes} molde(s) em {summary.total_folders} pasta(s)")
            if summary.total_sessions > 0:
                items_str.append(f"{summary.total_sessions} sessão(ões) com {summary.total_layouts} placa(s)/layout(s)")

            sum_desc = " + ".join(items_str) if items_str else "Nenhum item"
            self.lbl_backup_status.config(
                text=f"Concluído com sucesso! {sum_desc} salvos em {sz_kb:.1f} KB.",
                fg="#15803d"
            )
            msg = (
                f"🎉 Backup gerado com sucesso!\n\n"
                f"• Arquivo: {summary.target_file}\n"
                f"• Total de moldes exportados: {summary.total_shapes}\n"
                f"• Total de sessões de corte: {summary.total_sessions}\n"
                f"• Total de placas/layouts: {summary.total_layouts}\n"
                f"• Pastas de moldes organizadas: {summary.total_folders}\n"
                f"• Tamanho do arquivo: {sz_kb:.1f} KB\n"
                f"• Arquivos .die individuais: {'Sim' if summary.included_dies else 'Não'}"
            )
            messagebox.showinfo("Backup Concluído", msg, parent=self)

    # =========================================================================
    # LÓGICA DE RESTAURAÇÃO (IMPORTAÇÃO)
    # =========================================================================
    def _on_restore_folder_mode_change(self):
        if self.var_restore_folder_mode.get() == "custom":
            self.cb_restore_custom_folder.config(state="readonly")
        else:
            self.cb_restore_custom_folder.config(state="disabled")

    def _on_browse_restore_src(self):
        chosen = filedialog.askopenfilename(
            parent=self,
            title="Selecionar Pacote de Backup para Restauração",
            initialdir=str(EXPORTS_DIR),
            filetypes=[("Pacotes de Backup (*.zip; *.csh)", "*.zip;*.csh"), ("Arquivos ZIP (*.zip)", "*.zip"), ("Todos os Arquivos", "*.*")]
        )
        if chosen:
            self.var_restore_src_path.set(chosen)
            self._inspect_file_and_populate(chosen)

    def _inspect_file_and_populate(self, fpath: str):
        """Inspeciona o arquivo e preenche as tabelas de pré-visualização de moldes e sessões."""
        for item in self.tree_inspect.get_children():
            self.tree_inspect.delete(item)
        for item in self.tree_inspect_sess.get_children():
            self.tree_inspect_sess.delete(item)

        self.btn_run_restore.config(state="disabled")
        self.lbl_restore_status.config(text="Inspecionando integridade do arquivo...", fg="#0284c7")

        inspection = inspect_shapes_backup(fpath)
        self.current_inspection = inspection

        if not inspection.is_valid:
            self.lbl_inspect_summary.config(
                text=f"❌ Arquivo inválido ou corrompido: {inspection.error}",
                fg="#b91c1c"
            )
            self.lbl_restore_status.config(text="Falha na inspeção do arquivo.", fg="#b91c1c")
            messagebox.showerror("Arquivo Inválido", f"O arquivo selecionado não é um backup válido:\n\n{inspection.error}", parent=self)
            return

        badge_text = "Coleção legada de arquivos .die" if inspection.is_legacy_die_zip else f"Backup CorteAC ({inspection.app_version})"
        det_parts = []
        if inspection.has_shapes:
            det_parts.append(f"{inspection.total_shapes} moldes em {inspection.total_folders} pasta(s)")
        if inspection.has_sessions:
            det_parts.append(f"{inspection.total_sessions} sessões ({inspection.total_layouts} placas/layouts)")
        det_str = " + ".join(det_parts) or "Vazio"

        created_text = f" | Criado em: {inspection.created_at}" if inspection.created_at else ""
        self.lbl_inspect_summary.config(
            text=f"📦 {badge_text} | Conteúdo: {det_str}{created_text}",
            fg="#15803d"
        )

        self.nb_inspect.tab(0, text=f"  Moldes Detectados ({inspection.total_shapes})  ")
        self.nb_inspect.tab(1, text=f"  Sessões de Corte ({inspection.total_sessions})  ")

        self.var_restore_shapes.set(inspection.has_shapes)
        self.chk_restore_shapes.config(state="normal" if inspection.has_shapes else "disabled")
        self.var_restore_sessions.set(inspection.has_sessions)
        self.chk_restore_sessions.config(state="normal" if inspection.has_sessions else "disabled")

        if inspection.has_sessions and not inspection.has_shapes:
            self.nb_inspect.select(1)
        else:
            self.nb_inspect.select(0)

        existing_names = set()
        if self.db and hasattr(self.db, "get_all_shapes"):
            try:
                existing_names = {s.get("name", "") for s in self.db.get_all_shapes()}
            except Exception:
                existing_names = set()

        for idx, shp in enumerate(inspection.shapes, 1):
            nm = shp.get("name", "")
            sz = str(shp.get("size", "41"))
            fld = shp.get("folder", "")
            art = shp.get("article_name", "") or "-"
            pts = shp.get("points_count", 0)
            is_dup = nm in existing_names
            status_text = "⚠️ Já existe (duplicado)" if is_dup else "✨ Novo"

            item_id = self.tree_inspect.insert(
                "",
                "end",
                values=(idx, nm, sz, fld, art, pts, status_text)
            )
            if is_dup:
                self.tree_inspect.item(item_id, tags=("dup",))

        self.tree_inspect.tag_configure("dup", foreground="#b45309")

        existing_sess_ids = set()
        if self.db and hasattr(self.db, "get_sessions"):
            try:
                existing_sess_ids = {s.get("id") for s in self.db.get_sessions() if s.get("id") is not None}
            except Exception:
                existing_sess_ids = set()

        for idx, sess in enumerate(inspection.sessions, 1):
            s_id = sess.get("id")
            s_code = sess.get("code") or f"SESS-{s_id}"
            s_name = sess.get("name", "")
            s_job = sess.get("job", "")
            s_lys = sess.get("layouts_count", 0)
            s_pcs = sess.get("pieces_count", 0)
            s_mat = sess.get("material_id") or "-"
            is_dup_s = s_id in existing_sess_ids
            status_text = f"⚠️ ID #{s_id} já existe" if is_dup_s else f"✨ ID #{s_id} livre"

            item_id = self.tree_inspect_sess.insert(
                "",
                "end",
                values=(idx, s_code, s_name, s_job, s_lys, s_pcs, s_mat, status_text)
            )
            if is_dup_s:
                self.tree_inspect_sess.item(item_id, tags=("dup",))

        self.tree_inspect_sess.tag_configure("dup", foreground="#b45309")

        self.btn_run_restore.config(state="normal")
        self.lbl_restore_status.config(
            text=f"Pronto para restaurar. Selecione as opções desejadas e clique no botão abaixo.",
            fg="#15803d"
        )

    def _on_start_restore(self):
        if self.is_busy or not self.current_inspection or not self.current_inspection.is_valid:
            return

        fpath = self.var_restore_src_path.get().strip()
        do_shapes = self.var_restore_shapes.get() and self.current_inspection.has_shapes
        do_sessions = self.var_restore_sessions.get() and self.current_inspection.has_sessions

        if not do_shapes and not do_sessions:
            messagebox.showwarning("Nenhum Item Selecionado", "Marque pelo menos uma opção para restauração: Moldes ou Sessões de Corte.", parent=self)
            return

        strategy_shapes = self.var_conflict_strategy.get()
        target_folder = None
        if self.var_restore_folder_mode.get() == "custom":
            target_folder = self.var_restore_custom_folder.get().strip()
            if not target_folder:
                messagebox.showwarning("Pasta não Selecionada", "Selecione uma pasta para forçar o destino dos moldes.", parent=self)
                return

        strategy_sessions = self.var_session_conflict_strategy.get()
        target_job = None
        if self.var_restore_job_mode.get() == "custom":
            target_job = self.var_restore_custom_job.get().strip()
            if not target_job:
                messagebox.showwarning("Job não Selecionado", "Selecione ou digite um Job para forçar a pasta das sessões.", parent=self)
                return

        lines = ["Deseja iniciar a restauração dos dados?"]
        if do_shapes:
            lines.append(f"\n• Moldes ({self.current_inspection.total_shapes}): "
                         f"{'Substituir existentes' if strategy_shapes == 'overwrite' else ('Ignorar existentes' if strategy_shapes == 'skip' else 'Criar cópias renomeadas')}")
            if target_folder:
                lines.append(f"  Destino da pasta: Forçar na pasta \"{target_folder}\"")
        if do_sessions:
            lines.append(f"\n• Sessões ({self.current_inspection.total_sessions} com {self.current_inspection.total_layouts} placas): "
                         f"{'Novos números sequenciais (#189...)' if strategy_sessions == 'import_new_id' else ('Substituir sessões com mesmo ID' if strategy_sessions == 'overwrite' else 'Ignorar sessões com mesmo ID')}")
            if target_job:
                lines.append(f"  Destino do Job: Forçar no Job \"{target_job}\"")

        if not messagebox.askyesno("Confirmar Restauração", "\n".join(lines), parent=self):
            return

        self.is_busy = True
        self.btn_run_restore.config(state="disabled")
        self.prog_restore["value"] = 0
        self.lbl_restore_status.config(text="Restaurando dados no banco...", fg="#16a34a")

        def _worker():
            try:
                def _prog(cur, tot, msg):
                    pct = int((cur / max(1, tot)) * 100)
                    self.after(0, lambda: self._update_restore_progress(pct, msg))

                res = restore_shapes_backup(
                    db=self.db,
                    backup_file=fpath,
                    conflict_strategy=strategy_shapes,
                    target_folder=target_folder,
                    restore_shapes=do_shapes,
                    restore_sessions=do_sessions,
                    session_conflict_strategy=strategy_sessions,
                    target_job=target_job,
                    on_progress=_prog
                )
                self.after(0, lambda: self._on_restore_finished(res, None))
            except Exception as e:
                self.after(0, lambda: self._on_restore_finished(None, str(e)))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _update_restore_progress(self, pct, msg):
        self.prog_restore["value"] = pct
        self.lbl_restore_status.config(text=f"[{pct}%] {msg}", fg="#16a34a")

    def _on_restore_finished(self, res: Optional[RestoreResult], err: Optional[str]):
        self.is_busy = False
        self.btn_run_restore.config(state="normal")

        if err:
            self.prog_restore["value"] = 0
            self.lbl_restore_status.config(text=f"Erro na restauração: {err}", fg="#b91c1c")
            messagebox.showerror("Erro na Restauração", f"Falha ao restaurar dados:\n\n{err}", parent=self)
            return

        if res:
            self.prog_restore["value"] = 100
            msg_parts = ["🎉 Restauração concluída com sucesso!\n"]
            if res.total_in_backup > 0 or res.imported_new > 0 or res.updated_existing > 0:
                msg_parts.append(
                    f"Moldes:\n"
                    f"• Novos moldes importados: {res.imported_new}\n"
                    f"• Moldes atualizados: {res.updated_existing}\n"
                    f"• Moldes ignorados: {res.skipped}\n"
                    f"• Pastas criadas: {res.folders_created}\n"
                )
            if res.total_sessions_in_backup > 0 or res.sessions_imported > 0 or res.sessions_updated > 0:
                msg_parts.append(
                    f"Sessões de Corte:\n"
                    f"• Novas sessões importadas: {res.sessions_imported}\n"
                    f"• Sessões atualizadas: {res.sessions_updated}\n"
                    f"• Sessões ignoradas: {res.sessions_skipped}\n"
                )

            if res.errors:
                msg_parts.append(f"\n⚠️ Ocorreram avisos/erros em {len(res.errors)} item(ns):\n" + "\n".join(res.errors[:5]))

            msg = "\n".join(msg_parts)
            self.lbl_restore_status.config(
                text=f"Concluído! Moldes: +{res.imported_new} | Sessões: +{res.sessions_imported}.",
                fg="#15803d"
            )
            messagebox.showinfo("Restauração Concluída", msg, parent=self)

            if res.imported_new > 0 or res.updated_existing > 0 or res.total_in_backup > 0:
                if callable(self.on_shapes_changed):
                    try:
                        self.on_shapes_changed()
                    except Exception:
                        pass

            if res.sessions_imported > 0 or res.sessions_updated > 0 or res.total_sessions_in_backup > 0:
                if callable(self.on_sessions_changed):
                    try:
                        self.on_sessions_changed()
                    except Exception:
                        pass

            self.load_initial_stats()
