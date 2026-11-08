"""
JobManager 2000 / CorteAC (Python Edition)
UI: Diálogo de Backup e Restauração de Moldes Cadastrados
Interface gráfica para geração e importação de pacotes de backup compactados (.zip / .csh).
"""

import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

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


class ShapeBackupRestoreDialog(tk.Toplevel):
    """
    Diálogo modal completo para Backup e Restauração do Catálogo de Moldes.
    Permite exportar todos os moldes e pastas em um pacote .zip atômico,
    e restaurar com pré-visualização, filtro de pastas e resolução de conflitos.
    """

    def __init__(self, parent, db=None, on_shapes_changed: Optional[Callable[[], None]] = None, initial_tab: int = 0):
        super().__init__(parent)
        self.parent_window = parent
        self.db = db
        self.on_shapes_changed = on_shapes_changed

        self.title("Backup e Restauração de Moldes Cadastrados")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.configure(bg=THEME["bg_surface"])

        dlg_w, dlg_h = 780, 640
        self.geometry(f"{dlg_w}x{dlg_h}")
        self.minsize(700, 520)

        # Centraliza sobre a janela pai
        self.update_idletasks()
        rx = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
        ry = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
        self.geometry(f"+{max(10, rx)}+{max(10, ry)}")

        # Estado interno - Backup
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

        self.setup_ui()
        self.load_initial_stats()

        if initial_tab == 1:
            self.notebook.select(1)

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

        self.notebook.add(self.tab_backup, text="  💾 Criar Backup (Exportar)  ")
        self.notebook.add(self.tab_restore, text="  📥 Restaurar Backup (Importar)  ")

        self.setup_backup_tab()
        self.setup_restore_tab()

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
        card_stats.pack(fill="x", pady=(0, 10))

        self.lbl_stats_summary = tk.Label(
            card_stats,
            text="Carregando estatísticas...",
            bg=THEME["bg_surface"],
            fg="#1e40af",
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_stats_summary.pack(fill="x")

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
        grp_scope.pack(fill="x", pady=(0, 10))

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
        grp_opts.pack(fill="x", pady=(0, 10))

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
        grp_dest.pack(fill="x", pady=(0, 10))

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
            text="Nenhum arquivo de backup selecionado. Clique em 'Selecionar Backup...' para abrir.",
            bg="#f8fafc",
            fg="#64748b",
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_inspect_summary.pack(fill="x")

        # Tabela com lista dos moldes contidos no backup
        grp_preview = tk.LabelFrame(
            self.tab_restore,
            text="Moldes Encontrados no Pacote",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=6
        )
        grp_preview.pack(fill="both", expand=True, pady=(0, 8))

        cols = ("name", "size", "folder", "format", "points", "holes")
        self.tree_preview = ttk.Treeview(
            grp_preview,
            columns=cols,
            show="headings",
            selectmode="extended",
            height=6
        )
        self.tree_preview.heading("name", text="Nome do Molde")
        self.tree_preview.heading("size", text="Tamanho")
        self.tree_preview.heading("folder", text="Pasta Original")
        self.tree_preview.heading("format", text="Formato")
        self.tree_preview.heading("points", text="Vértices")
        self.tree_preview.heading("holes", text="Furos")

        self.tree_preview.column("name", width=180, anchor="w")
        self.tree_preview.column("size", width=70, anchor="center")
        self.tree_preview.column("folder", width=160, anchor="w")
        self.tree_preview.column("format", width=70, anchor="center")
        self.tree_preview.column("points", width=65, anchor="center")
        self.tree_preview.column("holes", width=55, anchor="center")

        sb_tree_y = ttk.Scrollbar(grp_preview, orient="vertical", command=self.tree_preview.yview)
        self.tree_preview.configure(yscrollcommand=sb_tree_y.set)
        self.tree_preview.pack(side="left", fill="both", expand=True)
        sb_tree_y.pack(side="right", fill="y")

        # Grupo: Opções de Restauração e Conflitos
        grp_conflict = tk.LabelFrame(
            self.tab_restore,
            text="Opções de Restauração e Resolução de Conflitos",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=6
        )
        grp_conflict.pack(fill="x", pady=(0, 8))

        f_opts_grid = tk.Frame(grp_conflict, bg=THEME["bg_surface"])
        f_opts_grid.pack(fill="x")

        # Coluna Esquerda: Conflito
        col_left = tk.Frame(f_opts_grid, bg=THEME["bg_surface"])
        col_left.pack(side="left", fill="x", expand=True)

        tk.Label(col_left, text="Quando o molde já existir no sistema:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Radiobutton(
            col_left,
            text="Substituir existentes (Atualizar contornos e dados)",
            variable=self.var_conflict_strategy,
            value="overwrite",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")
        tk.Radiobutton(
            col_left,
            text="Ignorar existentes (Manter os atuais sem modificar)",
            variable=self.var_conflict_strategy,
            value="skip",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")
        tk.Radiobutton(
            col_left,
            text="Criar cópias (Renomear para molde_copia)",
            variable=self.var_conflict_strategy,
            value="rename",
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        # Coluna Direita: Pasta Destino
        col_right = tk.Frame(f_opts_grid, bg=THEME["bg_surface"])
        col_right.pack(side="right", fill="x", expand=True, padx=(12, 0))

        tk.Label(col_right, text="Destino das pastas dos moldes:", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
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
        self.lbl_restore_status.pack(fill="x", pady=(0, 2))

        self.prog_restore = ttk.Progressbar(f_bottom_res, orient="horizontal", mode="determinate")
        self.prog_restore.pack(fill="x", pady=(0, 6))

        self.btn_run_restore = tk.Button(
            f_bottom_res,
            text="📥 Iniciar Restauração de Moldes...",
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
    # LÓGICA DE BACKUP (EXPORTAÇÃO)
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

            # Sugere nome com timestamp para o backup
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
        curr = self.var_backup_dest_path.get()
        initial_dir = str(Path(curr).parent) if curr else str(EXPORTS_DIR)
        initial_file = Path(curr).name if curr else f"backup_moldes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

        fpath = filedialog.asksaveasfilename(
            parent=self,
            title="Escolha o destino do arquivo de backup",
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[
                ("Arquivo de Backup ZIP (*.zip)", "*.zip"),
                ("Backup CorteAC Shapes (*.csh)", "*.csh"),
                ("Todos os Arquivos (*.*)", "*.*")
            ],
            defaultextension=".zip"
        )
        if fpath:
            self.var_backup_dest_path.set(fpath)

    def _on_start_backup(self):
        if self.is_busy:
            return

        dest_str = self.var_backup_dest_path.get().strip()
        if not dest_str:
            messagebox.showwarning("Destino Inválido", "Por favor, especifique o caminho de destino do arquivo de backup.", parent=self)
            return

        folder_filter = None
        if self.var_backup_scope.get() == "folder":
            fld = self.var_backup_folder.get().strip()
            if not fld:
                messagebox.showwarning("Pasta Inválida", "Selecione uma pasta para filtrar o backup.", parent=self)
                return
            folder_filter = [fld]

        include_dies = self.var_include_dies.get()

        self.is_busy = True
        self.btn_run_backup.config(state="disabled")
        self.prog_backup["value"] = 0
        self.lbl_backup_status.config(text="Iniciando geração de backup...", fg="#0284c7")

        def _worker():
            try:
                def _prog(cur, tot, msg):
                    pct = int((cur / max(1, tot)) * 100)
                    self.after(0, lambda: self._update_backup_progress(pct, msg))

                summary = create_shapes_backup(
                    db=self.db,
                    target_file=dest_str,
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
            self.lbl_backup_status.config(text=f"Erro: {err}", fg="#b91c1c")
            messagebox.showerror("Erro no Backup", f"Ocorreu um erro ao gerar o arquivo de backup:\n\n{err}", parent=self)
        elif summary:
            self.prog_backup["value"] = 100
            size_kb = summary.file_size_bytes / 1024.0
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{(size_kb/1024.0):.2f} MB"
            msg = (
                f"✅ Backup concluído com sucesso!\n\n"
                f"• Arquivo: {summary.target_file}\n"
                f"• Moldes exportados: {summary.total_shapes}\n"
                f"• Pastas incluídas: {summary.total_folders}\n"
                f"• Tamanho do arquivo: {size_str}"
            )
            self.lbl_backup_status.config(text=f"Concluído: {summary.total_shapes} moldes salvos ({size_str}).", fg="#15803d")
            messagebox.showinfo("Backup Criado com Sucesso", msg, parent=self)

    # =========================================================================
    # LÓGICA DE RESTAURAÇÃO (IMPORTAÇÃO)
    # =========================================================================
    def _on_restore_folder_mode_change(self):
        if self.var_restore_folder_mode.get() == "custom":
            self.cb_restore_custom_folder.config(state="normal")
        else:
            self.cb_restore_custom_folder.config(state="disabled")

    def _on_browse_restore_src(self):
        fpath = filedialog.askopenfilename(
            parent=self,
            title="Selecione o arquivo de backup para restaurar",
            filetypes=[
                ("Arquivos de Backup de Moldes (*.zip, *.csh)", ("*.zip", "*.csh")),
                ("Arquivos ZIP (*.zip)", "*.zip"),
                ("Todos os Arquivos (*.*)", "*.*")
            ]
        )
        if fpath:
            self.var_restore_src_path.set(fpath)
            self._inspect_file(fpath)

    def _inspect_file(self, fpath: str):
        """Inspeciona o arquivo de backup e popula a tabela de prévia."""
        self.tree_preview.delete(*self.tree_preview.get_children())
        self.btn_run_restore.config(state="disabled")

        inspection = inspect_shapes_backup(fpath)
        self.current_inspection = inspection

        if not inspection.is_valid:
            self.lbl_inspect_summary.config(
                text=f"❌ {inspection.error or 'Arquivo de backup inválido.'}",
                fg="#b91c1c"
            )
            self.lbl_restore_status.config(text=f"Erro ao ler arquivo: {inspection.error}", fg="#b91c1c")
            return

        date_str = inspection.created_at or "Não informada"
        if "T" in date_str:
            date_str = date_str.replace("T", " ")

        folders_str = ", ".join(inspection.folders[:3])
        if len(inspection.folders) > 3:
            folders_str += f" (+{len(inspection.folders)-3} mais)"
        elif not folders_str:
            folders_str = "Raiz"

        msg = (
            f"✅ Pacote válido | Origem: CorteAC {inspection.app_version} | "
            f"Data: {date_str} | "
            f"Total: {inspection.total_shapes} molde(s) em {len(inspection.folders)} pasta(s) [{folders_str}]"
        )
        self.lbl_inspect_summary.config(text=msg, fg="#15803d")
        self.lbl_restore_status.config(text=f"{inspection.total_shapes} moldes prontos para restauração.", fg=THEME["text_main"])

        # Popula tabela Treeview
        for s in inspection.shapes:
            self.tree_preview.insert("", "end", values=(
                s.get("name", ""),
                s.get("size", ""),
                s.get("folder", "") or "(Raiz)",
                s.get("shape_format", "1x1"),
                s.get("points_count", 0),
                s.get("holes_count", 0)
            ))

        self.btn_run_restore.config(state="normal")

    def _on_start_restore(self):
        if self.is_busy or not self.current_inspection or not self.current_inspection.is_valid:
            return

        fpath = self.var_restore_src_path.get().strip()
        if not fpath:
            return

        strategy = self.var_conflict_strategy.get()
        target_folder = None
        if self.var_restore_folder_mode.get() == "custom":
            target_folder = self.var_restore_custom_folder.get().strip()
            if not target_folder:
                messagebox.showwarning("Pasta Destino", "Por favor, informe a pasta de destino para os moldes.", parent=self)
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
