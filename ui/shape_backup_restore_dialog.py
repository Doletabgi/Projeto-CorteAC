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

    def __init__(self, parent, db=None, on_shapes_changed: Optional[Callable[[], None]] = None, initial_tab: int = 0):
        super().__init__(parent)
        self.parent_window = parent
        self.db = db
        self.on_shapes_changed = on_shapes_changed

        self.title("Backup, Restauração e Programação de Moldes Cadastrados")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.configure(bg=THEME["bg_surface"])

        dlg_w, dlg_h = 820, 680
        self.geometry(f"{dlg_w}x{dlg_h}")
        self.minsize(740, 560)

        # Centraliza sobre a janela pai
        self.update_idletasks()
        rx = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
        ry = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
        self.geometry(f"+{max(10, rx)}+{max(10, ry)}")

        # Estado interno - Backup Manual
        self.var_backup_scope = tk.StringVar(value="all")  # "all" ou "folder"
        self.var_backup_folder = tk.StringVar(value="")
        self.var_include_dies = tk.BooleanVar(value=True)
        self.var_backup_dest_path = tk.StringVar(value="")
        self.is_busy = False

        # Estado interno - Restauração
        self.var_restore_src_path = tk.StringVar(value="")
        self.var_conflict_strategy = tk.StringVar(value="overwrite")  # "overwrite", "skip", "rename"
        self.var_restore_folder_mode = tk.StringVar(value="original")  # "original" ou "custom"
        self.var_restore_custom_folder = tk.StringVar(value="")
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

        lbl_title = tk.Label(
            header_frame,
            text="📦 Backup e Restauração de Moldes Cadastrados",
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

        self.notebook = ttk.Notebook(main_box)
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
            text="Status Atual do Catálogo no Sistema",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=8
        )
        card_stats.pack(fill="x", pady=(0, 8))

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
        self.card_sched_banner = tk.Frame(self.tab_backup, bg="#f0fdf4", bd=1, relief="solid", padx=10, pady=6)
        self.card_sched_banner.pack(fill="x", pady=(0, 8))

        self.lbl_sched_banner_text = tk.Label(
            self.card_sched_banner,
            text="⏰ Agendamento Automático: Verificando...",
            bg="#f0fdf4",
            fg="#15803d",
            font=("Segoe UI", 9)
        )
        self.lbl_sched_banner_text.pack(side="left")

        btn_sched_goto = tk.Button(
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

        # Grupo: Escopo do Backup
        grp_scope = tk.LabelFrame(
            self.tab_backup,
            text="Escopo do Backup",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=8
        )
        grp_scope.pack(fill="x", pady=(0, 8))

        rb_all = tk.Radiobutton(
            grp_scope,
            text="Exportar TODOS os moldes cadastrados no sistema (Recomendado)",
            variable=self.var_backup_scope,
            value="all",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9),
            command=self._on_backup_scope_change
        )
        rb_all.pack(anchor="w", pady=2)

        f_folder_scope = tk.Frame(grp_scope, bg=THEME["bg_surface"])
        f_folder_scope.pack(fill="x", pady=2)

        rb_folder = tk.Radiobutton(
            f_folder_scope,
            text="Exportar apenas moldes da pasta:",
            variable=self.var_backup_scope,
            value="folder",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9),
            command=self._on_backup_scope_change
        )
        rb_folder.pack(side="left")

        self.cb_backup_folder = ttk.Combobox(
            f_folder_scope,
            textvariable=self.var_backup_folder,
            state="disabled",
            width=28
        )
        self.cb_backup_folder.pack(side="left", padx=8)

        # Grupo: Opções de Compatibilidade
        grp_opts = tk.LabelFrame(
            self.tab_backup,
            text="Formato do Pacote",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=8
        )
        grp_opts.pack(fill="x", pady=(0, 8))

        chk_dies = tk.Checkbutton(
            grp_opts,
            text="Incluir arquivos individuais .die (ATOM FlashCut) no pacote ZIP para máxima compatibilidade",
            variable=self.var_include_dies,
            bg=THEME["bg_surface"],
            font=("Segoe UI", 9)
        )
        chk_dies.pack(anchor="w")

        lbl_dies_hint = tk.Label(
            grp_opts,
            text="Permite abrir os moldes exportados tanto no CorteAC quanto em máquinas ATOM antigas e outros softwares CAM.",
            bg=THEME["bg_surface"],
            fg="#64748b",
            font=("Segoe UI", 8)
        )
        lbl_dies_hint.pack(anchor="w", padx=20)

        # Grupo: Arquivo de Destino
        grp_dest = tk.LabelFrame(
            self.tab_backup,
            text="Arquivo de Destino (.zip)",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=8
        )
        grp_dest.pack(fill="x", pady=(0, 8))

        f_dest_entry = tk.Frame(grp_dest, bg=THEME["bg_surface"])
        f_dest_entry.pack(fill="x", pady=2)

        self.ent_backup_dest = ttk.Entry(f_dest_entry, textvariable=self.var_backup_dest_path, font=("Segoe UI", 9))
        self.ent_backup_dest.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse_dest = tk.Button(
            f_dest_entry,
            text="Procurar...",
            bg=THEME["bg_surface"],
            padx=10,
            command=self._on_browse_backup_dest
        )
        btn_browse_dest.pack(side="right")

        # Barra inferior de ação e progresso
        f_bottom = tk.Frame(self.tab_backup, bg=THEME["bg_surface"])
        f_bottom.pack(side="bottom", fill="x", pady=(6, 0))

        self.lbl_backup_status = tk.Label(
            f_bottom,
            text="Pronto para gerar backup.",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_backup_status.pack(fill="x", pady=(0, 4))

        self.prog_backup = ttk.Progressbar(f_bottom, orient="horizontal", mode="determinate")
        self.prog_backup.pack(fill="x", pady=(0, 8))

        self.btn_run_backup = tk.Button(
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
            pady=8
        )
        grp_file.pack(fill="x", pady=(0, 8))

        f_file_row = tk.Frame(grp_file, bg=THEME["bg_surface"])
        f_file_row.pack(fill="x")

        self.ent_restore_src = ttk.Entry(f_file_row, textvariable=self.var_restore_src_path, font=("Segoe UI", 9))
        self.ent_restore_src.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse_src = tk.Button(
            f_file_row,
            text="📂 Selecionar Backup...",
            bg=THEME["bg_surface"],
            padx=10,
            command=self._on_browse_restore_src
        )
        btn_browse_src.pack(side="right")

        # Painel de resumo da inspeção do arquivo selecionado
        self.card_inspection = tk.Frame(self.tab_restore, bg="#f8fafc", bd=1, relief="solid", padx=10, pady=6)
        self.card_inspection.pack(fill="x", pady=(0, 8))

        self.lbl_inspect_summary = tk.Label(
            self.card_inspection,
            text="Nenhum arquivo inspecionado no momento. Selecione um arquivo .zip acima.",
            bg="#f8fafc",
            fg="#475569",
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_inspect_summary.pack(fill="x")

        # Tabela de pré-visualização dos moldes no backup
        grp_preview = tk.LabelFrame(
            self.tab_restore,
            text="Moldes Detectados no Pacote",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=6
        )
        grp_preview.pack(fill="both", expand=True, pady=(0, 8))

        cols = ("idx", "name", "folder", "article", "points", "status")
        self.tree_inspect = ttk.Treeview(grp_preview, columns=cols, show="headings", height=6)
        self.tree_inspect.heading("idx", text="#")
        self.tree_inspect.heading("name", text="Nome do Molde")
        self.tree_inspect.heading("folder", text="Pasta")
        self.tree_inspect.heading("article", text="Artigo")
        self.tree_inspect.heading("points", text="Vértices")
        self.tree_inspect.heading("status", text="No Sistema Atual?")

        self.tree_inspect.column("idx", width=40, anchor="center")
        self.tree_inspect.column("name", width=180, anchor="w")
        self.tree_inspect.column("folder", width=110, anchor="w")
        self.tree_inspect.column("article", width=110, anchor="w")
        self.tree_inspect.column("points", width=70, anchor="center")
        self.tree_inspect.column("status", width=140, anchor="center")

        sb_tree_y = ttk.Scrollbar(grp_preview, orient="vertical", command=self.tree_inspect.yview)
        self.tree_inspect.configure(yscrollcommand=sb_tree_y.set)

        self.tree_inspect.pack(side="left", fill="both", expand=True)
        sb_tree_y.pack(side="right", fill="y")

        # Opções de importação e conflito
        grp_import_opts = tk.LabelFrame(
            self.tab_restore,
            text="Opções de Restauração",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6
        )
        grp_import_opts.pack(fill="x", pady=(0, 8))

        col_left = tk.Frame(grp_import_opts, bg=THEME["bg_surface"])
        col_left.pack(side="left", fill="x", expand=True)

        tk.Label(col_left, text="Resolução de Nomes Duplicados:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(anchor="w")

        tk.Radiobutton(
            col_left,
            text="Sobrescrever / Atualizar existente (Recomendado)",
            variable=self.var_conflict_strategy,
            value="overwrite",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        tk.Radiobutton(
            col_left,
            text="Pular existentes (importar apenas novos)",
            variable=self.var_conflict_strategy,
            value="skip",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        tk.Radiobutton(
            col_left,
            text="Renomear cópia (ex: 'Molde (1)')",
            variable=self.var_conflict_strategy,
            value="rename",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        col_right = tk.Frame(grp_import_opts, bg=THEME["bg_surface"])
        col_right.pack(side="right", fill="x", expand=True)

        tk.Label(col_right, text="Direcionamento de Pastas:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(anchor="w")

        tk.Radiobutton(
            col_right,
            text="Restaurar nas pastas originais do backup",
            variable=self.var_restore_folder_mode,
            value="original",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._on_restore_folder_mode_change
        ).pack(anchor="w")

        f_cust_row = tk.Frame(col_right, bg=THEME["bg_surface"])
        f_cust_row.pack(fill="x")
        tk.Radiobutton(
            f_cust_row,
            text="Forçar para pasta específica:",
            variable=self.var_restore_folder_mode,
            value="custom",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self._on_restore_folder_mode_change
        ).pack(side="left")

        self.cb_restore_custom_folder = ttk.Combobox(
            f_cust_row,
            textvariable=self.var_restore_custom_folder,
            state="disabled",
            width=18
        )
        self.cb_restore_custom_folder.pack(side="left", padx=4)

        # Barra inferior de restauração
        f_bottom_res = tk.Frame(self.tab_restore, bg=THEME["bg_surface"])
        f_bottom_res.pack(side="bottom", fill="x", pady=(4, 0))

        self.lbl_restore_status = tk.Label(
            f_bottom_res,
            text="Selecione um arquivo de backup para inspecionar.",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_restore_status.pack(fill="x", pady=(0, 4))

        self.prog_restore = ttk.Progressbar(f_bottom_res, orient="horizontal", mode="determinate")
        self.prog_restore.pack(fill="x", pady=(0, 6))

        self.btn_run_restore = tk.Button(
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
            btn_p = tk.Button(
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

        f_dest_line = tk.Frame(grp_dest_ret, bg=THEME["bg_surface"])
        f_dest_line.pack(fill="x", pady=(0, 4))

        tk.Label(f_dest_line, text="Pasta dos Backups:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        ent_sdir = ttk.Entry(f_dest_line, textvariable=self.var_sched_backup_dir, font=("Segoe UI", 9))
        ent_sdir.pack(side="left", fill="x", expand=True, padx=(0, 6))

        tk.Button(f_dest_line, text="Procurar...", bg=THEME["bg_surface"], padx=6, command=self._on_browse_sched_dir).pack(side="left", padx=(0, 4))
        tk.Button(f_dest_line, text="📂 Abrir Pasta", bg=THEME["bg_surface"], padx=6, command=self._on_open_sched_dir).pack(side="left")

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

        btn_save_sched = tk.Button(
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

        btn_run_sched_now = tk.Button(
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

        btn_refresh_hist = tk.Button(
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

        btn_restore_selected = tk.Button(
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
                # Se estiver YYYY-MM-DD converte para DD/MM/YYYY na UI
                try:
                    d_parsed = datetime.strptime(parts[0], "%Y-%m-%d").strftime("%d/%m/%Y")
                    self.var_sched_specific_date.set(d_parsed)
                except ValueError:
                    self.var_sched_specific_date.set(parts[0])
                self.var_sched_specific_time.set(parts[1])
            else:
                self.var_sched_specific_date.set(spec_dt)
        else:
            # Sugere data de amanhã
            tomorrow = datetime.now() + timedelta(days=1)
            self.var_sched_specific_date.set(tomorrow.strftime("%d/%m/%Y"))
            self.var_sched_specific_time.set("18:00")

        self.var_sched_backup_dir.set(str(cfg.get("backup_dir") or DEFAULT_BACKUPS_DIR))
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

        # Monta data e hora específica
        spec_date = self.var_sched_specific_date.get().strip()
        spec_time = self.var_sched_specific_time.get().strip() or "18:00"
        normalized_spec = ""
        if spec_date:
            # Tenta converter de DD/MM/AAAA para YYYY-MM-DD
            try:
                d_obj = datetime.strptime(spec_date, "%d/%m/%Y")
                normalized_spec = f"{d_obj.strftime('%Y-%m-%d')} {spec_time}"
            except ValueError:
                normalized_spec = f"{spec_date} {spec_time}"

        bdir = self.var_sched_backup_dir.get().strip() or str(DEFAULT_BACKUPS_DIR)

        try:
            max_ret = max(0, int(self.var_sched_max_retained.get()))
        except Exception:
            max_ret = 10

        inc_dies = self.var_sched_include_dies.get()

        # Mantém histórico anterior
        current_cfg = get_schedule_config(self.db)

        return {
            "enabled": enabled,
            "mode": mode,
            "times": times_list,
            "days_of_week": dow_list,
            "interval_hours": interval_h,
            "specific_datetime": normalized_spec,
            "backup_dir": bdir,
            "include_dies": inc_dies,
            "folder_filter": None,
            "max_retained_backups": max_ret,
            "last_run_timestamp": current_cfg.get("last_run_timestamp", ""),
            "last_run_status": current_cfg.get("last_run_status", ""),
            "last_run_message": current_cfg.get("last_run_message", ""),
            "last_run_file": current_cfg.get("last_run_file", "")
        }

    def _on_save_schedule(self):
        """Salva a configuração do agendamento e atualiza os indicadores."""
        cfg = self._collect_schedule_config_from_ui()

        # Validação de dias da semana se mode == weekly
        if cfg["mode"] == "weekly" and not cfg["days_of_week"]:
            messagebox.showwarning(
                "Configuração Incompleta",
                "Você selecionou o modo 'Dias da Semana específicos', mas nenhum dia foi marcado. Marque pelo menos um dia.",
                parent=self
            )
            return

        saved = save_schedule_config(self.db, cfg)
        self._update_sched_status_display(saved)

        # Cria a pasta caso ainda não exista
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
        self.lbl_sched_last_run.config(text="Executando backup de moldes agora...", fg="#0284c7")

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

        # Sucesso
        self._update_sched_status_display()
        self._refresh_sched_history()

        msg = (
            f"🎉 Backup executado com sucesso!\n\n"
            f"• Arquivo: {res.get('target_file')}\n"
            f"• Moldes exportados: {res.get('total_shapes')}\n"
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

            total_shapes = len(shapes)
            total_folders = len(folders)

            self.lbl_stats_summary.config(
                text=f"📊 Sistema possui {total_shapes} molde(s) cadastrado(s) distribuído(s) em {total_folders} pasta(s)."
            )

            # Preenche comboboxes com as pastas existentes
            self.cb_backup_folder["values"] = folders
            if folders:
                self.var_backup_folder.set(folders[0])

            self.cb_restore_custom_folder["values"] = folders
            if folders:
                self.var_restore_custom_folder.set(folders[0])

            # Sugere nome com timestamp para o backup manual
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            sugg_name = f"backup_moldes_{timestamp_str}.zip"
            sugg_path = Path(EXPORTS_DIR) / sugg_name
            self.var_backup_dest_path.set(str(sugg_path))

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
        init_name = Path(init_file).name if init_file else "backup_moldes.zip"

        chosen = filedialog.asksaveasfilename(
            parent=self,
            title="Salvar Arquivo de Backup dos Moldes",
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

        folder_filter = None
        if self.var_backup_scope.get() == "folder":
            sel_f = self.var_backup_folder.get().strip()
            if not sel_f:
                messagebox.showwarning("Pasta não Selecionada", "Selecione uma pasta para filtrar o backup.", parent=self)
                return
            folder_filter = [sel_f]

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
            self.lbl_backup_status.config(
                text=f"Concluído com sucesso! {summary.total_shapes} molde(s) salvo(s) em {sz_kb:.1f} KB.",
                fg="#15803d"
            )
            msg = (
                f"🎉 Backup gerado com sucesso!\n\n"
                f"• Arquivo: {summary.target_file}\n"
                f"• Total de moldes exportados: {summary.total_shapes}\n"
                f"• Pastas organizadas: {summary.total_folders}\n"
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
        """Inspeciona o arquivo e preenche a tabela de pré-visualização."""
        for item in self.tree_inspect.get_children():
            self.tree_inspect.delete(item)

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

        # Preenche resumo
        badge_text = "Coleção legada de arquivos .die" if inspection.is_legacy_die_zip else f"Backup CorteAC ({inspection.app_version})"
        self.lbl_inspect_summary.config(
            text=f"📦 {badge_text} | Total de moldes: {inspection.total_shapes} | Pastas: {inspection.total_folders} | Criado em: {inspection.created_at}",
            fg="#15803d"
        )

        # Checa duplicados com o banco atual para exibir na tabela
        existing_names = set()
        if self.db and hasattr(self.db, "get_all_shapes"):
            try:
                existing_names = {s.get("name", "") for s in self.db.get_all_shapes()}
            except Exception:
                existing_names = set()

        for idx, shp in enumerate(inspection.shapes, 1):
            nm = shp.get("name", "")
            fld = shp.get("folder", "")
            art = shp.get("article_name", "") or "-"
            pts = len(shp.get("points") or [])
            is_dup = nm in existing_names
            status_text = "⚠️ Já existe (duplicado)" if is_dup else "✨ Novo"

            item_id = self.tree_inspect.insert(
                "",
                "end",
                values=(idx, nm, fld, art, pts, status_text)
            )
            if is_dup:
                self.tree_inspect.item(item_id, tags=("dup",))

        self.tree_inspect.tag_configure("dup", foreground="#b45309")

        self.btn_run_restore.config(state="normal")
        self.lbl_restore_status.config(
            text=f"Pronto para restaurar {inspection.total_shapes} molde(s). Escolha a estratégia de conflito e clique no botão abaixo.",
            fg="#15803d"
        )

    def _on_start_restore(self):
        if self.is_busy or not self.current_inspection or not self.current_inspection.is_valid:
            return

        fpath = self.var_restore_src_path.get().strip()
        strategy = self.var_conflict_strategy.get()
        target_folder = None
        if self.var_restore_folder_mode.get() == "custom":
            target_folder = self.var_restore_custom_folder.get().strip()
            if not target_folder:
                messagebox.showwarning("Pasta não Selecionada", "Selecione uma pasta para forçar o destino dos moldes.", parent=self)
                return

        # Confirmação do operador
        msg_confirm = (
            f"Deseja iniciar a restauração de {self.current_inspection.total_shapes} molde(s)?\n\n"
            f"• Estratégia de conflito: "
            f"{'Substituir existentes' if strategy == 'overwrite' else ('Ignorar existentes' if strategy == 'skip' else 'Criar cópias renomeadas')}\n"
            f"• Destino das pastas: "
            f"{'Pastas originais do backup' if not target_folder else f'Forçar na pasta \"{target_folder}\"'}"
        )
        if not messagebox.askyesno("Confirmar Restauração", msg_confirm, parent=self):
            return

        self.is_busy = True
        self.btn_run_restore.config(state="disabled")
        self.prog_restore["value"] = 0
        self.lbl_restore_status.config(text="Restaurando moldes no banco de dados...", fg="#16a34a")

        def _worker():
            try:
                def _prog(cur, tot, msg):
                    pct = int((cur / max(1, tot)) * 100)
                    self.after(0, lambda: self._update_restore_progress(pct, msg))

                res = restore_shapes_backup(
                    db=self.db,
                    backup_file=fpath,
                    conflict_strategy=strategy,
                    target_folder=target_folder,
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
            messagebox.showerror("Erro na Restauração", f"Falha ao restaurar moldes:\n\n{err}", parent=self)
            return

        if res:
            self.prog_restore["value"] = 100
            msg = (
                f"🎉 Restauração concluída com sucesso!\n\n"
                f"• Total de moldes processados: {res.total_in_backup}\n"
                f"• Novos moldes importados: {res.imported_new}\n"
                f"• Moldes existentes atualizados: {res.updated_existing}\n"
                f"• Moldes ignorados (conflitos): {res.skipped}\n"
                f"• Pastas criadas/asseguradas: {res.folders_created}"
            )
            if res.errors:
                msg += f"\n\n⚠️ Erros em {len(res.errors)} molde(s):\n" + "\n".join(res.errors[:5])

            self.lbl_restore_status.config(
                text=f"Concluído: {res.imported_new} novos, {res.updated_existing} atualizados, {res.skipped} ignorados.",
                fg="#15803d"
            )
            messagebox.showinfo("Restauração Concluída", msg, parent=self)

            # Notifica a janela principal para recarregar imediatamente a árvore e o grid
            if callable(self.on_shapes_changed):
                try:
                    self.on_shapes_changed()
                except Exception:
                    pass

            # Atualiza também as estatísticas da Aba de Backup
            self.load_initial_stats()
