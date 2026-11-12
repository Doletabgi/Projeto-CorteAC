"""
JobManager 2000 / CorteAC (Python Edition)
CAM / CAD: Diálogo de Conversor de Arquivos de Corte (.lay ⇄ .onx)
Interface gráfica para conversão bidirecional e em lote entre ATOM FlashCut e Comelz CNC.
"""

import os
import sys
import threading
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

import tkinter as tk
from ui.icon_widgets import IconButton, IconLabel, IconRadiobutton
from tkinter import ttk, filedialog, messagebox

from config import THEME, APP_NAME
from cad.layout_converter import (
    convert_file,
    detect_file_format,
    ConversionResult
)


class LayoutConverterDialog(tk.Toplevel):
    """
    Janela modal para conversão bidirecional de layouts (.lay <-> .onx).
    Suporta seleção de múltiplos arquivos, pastas completas, pré-visualização,
    barra de progresso e relatório detalhado de conversão.
    """

    def __init__(self, parent, db=None, initial_files: Optional[List[str]] = None):
        super().__init__(parent)
        self.parent_window = parent
        self.db = db

        self.title("Conversor de Arquivos de Corte (.lay ⇄ .onx)")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.configure(bg=THEME["bg_surface"])

        dlg_w, dlg_h = 760, 600
        self.geometry(f"{dlg_w}x{dlg_h}")
        self.minsize(680, 500)

        # Centraliza sobre a janela pai
        self.update_idletasks()
        rx = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
        ry = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
        self.geometry(f"+{max(10, rx)}+{max(10, ry)}")

        # Estado interno
        self.files_list: List[Path] = []
        self.last_destination_dir: Optional[Path] = None
        self.is_converting = False

        # Variáveis de controle
        self.var_mode = tk.StringVar(value="auto")  # "auto", "lay_to_onx", "onx_to_lay"
        self.var_dest_mode = tk.StringVar(value="same")  # "same", "custom"
        self.var_custom_dest = tk.StringVar(value="")
        self.var_overwrite = tk.BooleanVar(value=True)
        self.var_status_text = tk.StringVar(value="Pronto para adicionar arquivos.")

        self.setup_ui()

        if initial_files:
            self.add_files(initial_files)

        self.bind("<Escape>", lambda e: self.destroy())

    def setup_ui(self):
        # 1. Cabeçalho estilizado
        header_frame = tk.Frame(self, bg=THEME["title_bar_bg"], height=38, padx=12, pady=6)
        header_frame.pack(fill="x")

        lbl_title = IconLabel(
            header_frame,
            text="🔄 Conversor de Arquivos de Corte (.lay ⇄ .onx)",
            bg=THEME["title_bar_bg"],
            fg=THEME["title_bar_fg"],
            font=("Segoe UI", 11, "bold")
        )
        lbl_title.pack(side="left")

        lbl_sub = tk.Label(
            header_frame,
            text="ATOM FlashCut ⇄ Comelz CNC",
            bg=THEME["title_bar_bg"],
            fg="#cbd5e1",
            font=("Segoe UI", 9)
        )
        lbl_sub.pack(side="right", padx=(0, 6))

        # Container principal
        main_box = tk.Frame(self, bg=THEME["bg_surface"], padx=10, pady=8)
        main_box.pack(fill="both", expand=True)

        # 2. Modo de Conversão
        mode_frame = tk.LabelFrame(
            main_box,
            text=" Modo de Conversão ",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=4
        )
        mode_frame.pack(fill="x", pady=(0, 6))

        row_modes = tk.Frame(mode_frame, bg=THEME["bg_surface"])
        row_modes.pack(fill="x")

        rb1 = IconRadiobutton(
            row_modes,
            text="🔄 Detecção Automática (.lay ⇄ .onx)",
            variable=self.var_mode,
            value="auto",
            command=self.refresh_table_targets,
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 9)
        )
        rb1.pack(side="left", padx=(0, 16))

        rb2 = IconRadiobutton(
            row_modes,
            text="🔵 Forçar ATOM (.lay) ➔ Comelz (.onx)",
            variable=self.var_mode,
            value="lay_to_onx",
            command=self.refresh_table_targets,
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 9)
        )
        rb2.pack(side="left", padx=(0, 16))

        rb3 = IconRadiobutton(
            row_modes,
            text="🟠 Forçar Comelz (.onx) ➔ ATOM (.lay)",
            variable=self.var_mode,
            value="onx_to_lay",
            command=self.refresh_table_targets,
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 9)
        )
        rb3.pack(side="left")

        # 3. Lista de Arquivos com Barra de Ferramentas
        files_frame = tk.LabelFrame(
            main_box,
            text=" Arquivos Selecionados ",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=6
        )
        files_frame.pack(fill="both", expand=True, pady=(0, 6))

        tb_files = tk.Frame(files_frame, bg=THEME["bg_surface"])
        tb_files.pack(fill="x", pady=(0, 6))

        btn_add = IconButton(
            tb_files,
            text="➕ Adicionar Arquivos...",
            command=self.on_add_files_clicked,
            bg=THEME["bg_card"],
            relief="raised",
            bd=2,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2
        )
        btn_add.pack(side="left", padx=(0, 6))

        btn_add_dir = IconButton(
            tb_files,
            text="📁 Adicionar Pasta...",
            command=self.on_add_folder_clicked,
            bg=THEME["bg_card"],
            relief="raised",
            bd=2,
            font=("Segoe UI", 8),
            padx=8,
            pady=2
        )
        btn_add_dir.pack(side="left", padx=(0, 6))

        btn_rem = IconButton(
            tb_files,
            text="➖ Remover Selecionado",
            command=self.on_remove_selected,
            bg=THEME["bg_card"],
            relief="raised",
            bd=2,
            font=("Segoe UI", 8),
            padx=6,
            pady=2
        )
        btn_rem.pack(side="left", padx=(0, 6))

        btn_clr = IconButton(
            tb_files,
            text="🗑️ Limpar Lista",
            command=self.on_clear_list,
            bg=THEME["bg_card"],
            relief="raised",
            bd=2,
            font=("Segoe UI", 8),
            padx=6,
            pady=2
        )
        btn_clr.pack(side="left")

        self.lbl_count = tk.Label(
            tb_files,
            text="0 arquivos na fila",
            bg=THEME["bg_surface"],
            fg=THEME["text_muted"],
            font=("Segoe UI", 8, "italic")
        )
        self.lbl_count.pack(side="right")

        # Tabela Treeview
        tree_container = tk.Frame(files_frame, bg=THEME["bg_surface"])
        tree_container.pack(fill="both", expand=True)

        cols = ("filename", "src_fmt", "dst_fmt", "size", "status")
        self.tree = ttk.Treeview(tree_container, columns=cols, show="headings", selectmode="extended", height=6)
        self.tree.heading("filename", text="Arquivo de Origem", anchor="w")
        self.tree.heading("src_fmt", text="Formato", anchor="center")
        self.tree.heading("dst_fmt", text="Converter Para", anchor="center")
        self.tree.heading("size", text="Tamanho", anchor="e")
        self.tree.heading("status", text="Status", anchor="center")

        self.tree.column("filename", width=340, anchor="w")
        self.tree.column("src_fmt", width=80, anchor="center")
        self.tree.column("dst_fmt", width=110, anchor="center")
        self.tree.column("size", width=80, anchor="e")
        self.tree.column("status", width=110, anchor="center")

        scroll_y = tk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        self.tree.tag_configure("ok", foreground="#15803d")
        self.tree.tag_configure("error", foreground="#b91c1c")
        self.tree.tag_configure("pending", foreground="#475569")

        # 4. Destino dos Arquivos
        dest_frame = tk.LabelFrame(
            main_box,
            text=" Destino dos Arquivos Convertidos ",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=4
        )
        dest_frame.pack(fill="x", pady=(0, 6))

        row_dest1 = tk.Frame(dest_frame, bg=THEME["bg_surface"])
        row_dest1.pack(fill="x", pady=(2, 2))

        rb_same = IconRadiobutton(
            row_dest1,
            text="Salvar na mesma pasta do arquivo de origem",
            variable=self.var_dest_mode,
            value="same",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 9)
        )
        rb_same.pack(side="left")

        cb_over = tk.Checkbutton(
            row_dest1,
            text="Sobrescrever arquivos existentes sem confirmação",
            variable=self.var_overwrite,
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 9)
        )
        cb_over.pack(side="right")

        row_dest2 = tk.Frame(dest_frame, bg=THEME["bg_surface"])
        row_dest2.pack(fill="x", pady=(2, 4))

        rb_custom = IconRadiobutton(
            row_dest2,
            text="Salvar em pasta personalizada:",
            variable=self.var_dest_mode,
            value="custom",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 9)
        )
        rb_custom.pack(side="left", padx=(0, 6))

        self.ent_dest = tk.Entry(
            row_dest2,
            textvariable=self.var_custom_dest,
            font=("Segoe UI", 9),
            bg=THEME["bg_input"]
        )
        self.ent_dest.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_browse = IconButton(
            row_dest2,
            text="Procurar...",
            command=self.on_browse_dest_dir,
            bg=THEME["bg_card"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 8),
            padx=6
        )
        btn_browse.pack(side="right")

        # 5. Progresso e Log de Execução
        log_frame = tk.LabelFrame(
            main_box,
            text=" Progresso e Registro de Operações ",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=4
        )
        log_frame.pack(fill="both", expand=True, pady=(0, 6))

        row_prog = tk.Frame(log_frame, bg=THEME["bg_surface"])
        row_prog.pack(fill="x", pady=(2, 4))

        self.progress_bar = ttk.Progressbar(row_prog, orient="horizontal", mode="determinate")
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.lbl_progress_pct = tk.Label(
            row_prog,
            textvariable=self.var_status_text,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8)
        )
        self.lbl_progress_pct.pack(side="right")

        # Caixa de texto de log com scroll
        log_box = tk.Frame(log_frame, bg=THEME["bg_surface"])
        log_box.pack(fill="both", expand=True)

        self.txt_log = tk.Text(
            log_box,
            height=5,
            font=("Consolas", 8),
            bg=THEME["bg_input"],
            fg=THEME["text_main"],
            wrap="word",
            relief="sunken",
            bd=1
        )
        log_scroll = tk.Scrollbar(log_box, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=log_scroll.set)
        self.txt_log.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        self.txt_log.tag_configure("ok", foreground="#16a34a", font=("Consolas", 8, "bold"))
        self.txt_log.tag_configure("err", foreground="#dc2626", font=("Consolas", 8, "bold"))
        self.txt_log.tag_configure("info", foreground="#0284c7")

        # 6. Rodapé com Botões de Ação
        footer = tk.Frame(self, bg=THEME["bg_surface"], padx=10, pady=8)
        footer.pack(fill="x")

        self.btn_convert = IconButton(
            footer,
            text="▶ Iniciar Conversão",
            command=self.start_conversion,
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="raised",
            bd=2,
            padx=16,
            pady=4
        )
        self.btn_convert.pack(side="left")

        self.btn_open_folder = IconButton(
            footer,
            text="📂 Abrir Pasta de Destino",
            command=self.open_destination_folder,
            bg=THEME["bg_card"],
            font=("Segoe UI", 9),
            relief="raised",
            bd=2,
            padx=10,
            pady=4,
            state="disabled"
        )
        self.btn_open_folder.pack(side="left", padx=(10, 0))

        btn_close = IconButton(
            footer,
            text="Fechar",
            command=self.destroy,
            bg=THEME["bg_card"],
            font=("Segoe UI", 9),
            relief="raised",
            bd=2,
            padx=14,
            pady=4
        )
        btn_close.pack(side="right")

    def log(self, message: str, tag: Optional[str] = None):
        """Adiciona uma mensagem à caixa de log com autoscroll."""
        self.txt_log.insert(tk.END, message + "\n", tag)
        self.txt_log.see(tk.END)

    def on_add_files_clicked(self):
        """Abre caixa de diálogo para seleção de múltiplos arquivos .lay e .onx."""
        files = filedialog.askopenfilenames(
            title="Selecionar Arquivos de Corte para Conversão",
            parent=self,
            filetypes=[
                ("Arquivos de Corte (*.lay;*.onx)", "*.lay;*.onx"),
                ("ATOM FlashCut Layout (*.lay)", "*.lay"),
                ("Comelz CNC (*.onx)", "*.onx"),
                ("Todos os Arquivos (*.*)", "*.*")
            ]
        )
        if files:
            self.add_files(files)

    def on_add_folder_clicked(self):
        """Abre caixa de diálogo para seleção de pasta e varre por arquivos .lay e .onx."""
        folder = filedialog.askdirectory(
            title="Selecionar Pasta com Arquivos de Corte",
            parent=self
        )
        if not folder:
            return

        p = Path(folder)
        found = []
        for ext in ("*.lay", "*.onx", "*.LAY", "*.ONX"):
            found.extend(list(p.glob(ext)))

        if not found:
            messagebox.showinfo(
                "Nenhum arquivo encontrado",
                f"Nenhum arquivo .lay ou .onx foi encontrado na pasta:\n{folder}",
                parent=self
            )
            return

        self.add_files([str(f) for f in sorted(set(found))])
        self.log(f"Adicionados {len(found)} arquivos da pasta '{p.name}'.", "info")

    def add_files(self, file_paths: List[str]):
        """Insere caminhos na lista de arquivos a converter evitando duplicatas."""
        for fp in file_paths:
            path_obj = Path(fp).resolve()
            if path_obj.is_file() and path_obj not in self.files_list:
                self.files_list.append(path_obj)

        self.refresh_table()

    def on_remove_selected(self):
        """Remove itens selecionados na tabela."""
        selected_items = self.tree.selection()
        if not selected_items:
            return

        indices_to_remove = set()
        for it in selected_items:
            try:
                idx = int(it)
                indices_to_remove.add(idx)
            except ValueError:
                pass

        self.files_list = [f for i, f in enumerate(self.files_list) if i not in indices_to_remove]
        self.refresh_table()

    def on_clear_list(self):
        """Limpa toda a lista de arquivos da fila."""
        self.files_list.clear()
        self.refresh_table()
        self.txt_log.delete("1.0", tk.END)
        self.var_status_text.set("Lista limpa.")
        self.progress_bar["value"] = 0

    def on_browse_dest_dir(self):
        """Abre diálogo para escolher a pasta de destino personalizada."""
        dir_path = filedialog.askdirectory(
            title="Selecionar Pasta de Destino",
            parent=self
        )
        if dir_path:
            self.var_custom_dest.set(dir_path)
            self.var_dest_mode.set("custom")

    def get_target_format_for_file(self, file_path: Path) -> str:
        """Determina o formato alvo do arquivo conforme o modo selecionado."""
        mode = self.var_mode.get()
        if mode == "lay_to_onx":
            return "onx"
        elif mode == "onx_to_lay":
            return "lay"
        else:
            fmt = detect_file_format(file_path)
            return "onx" if fmt == "lay" else "lay"

    def refresh_table(self):
        """Reconstrói as linhas da Treeview com base em self.files_list."""
        self.tree.delete(*self.tree.get_children())

        for idx, fp in enumerate(self.files_list):
            src_fmt = detect_file_format(fp).upper()
            dst_fmt = self.get_target_format_for_file(fp).upper()

            try:
                sz_bytes = fp.stat().st_size
                sz_str = f"{sz_bytes / 1024:.1f} KB" if sz_bytes >= 1024 else f"{sz_bytes} B"
            except Exception:
                sz_str = "0 B"

            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(fp.name, src_fmt, f"➔ .{dst_fmt.lower()}", sz_str, "Pendente"),
                tags=("pending",)
            )

        n = len(self.files_list)
        self.lbl_count.config(text=f"{n} arquivo{'s' if n != 1 else ''} na fila")
        if n > 0:
            self.var_status_text.set(f"{n} arquivo(s) aguardando conversão.")

    def refresh_table_targets(self):
        """Atualiza a coluna 'Converter Para' ao mudar a opção de modo."""
        for idx, fp in enumerate(self.files_list):
            iid = str(idx)
            if self.tree.exists(iid):
                cur_vals = list(self.tree.item(iid, "values"))
                dst_fmt = self.get_target_format_for_file(fp).upper()
                cur_vals[2] = f"➔ .{dst_fmt.lower()}"
                self.tree.item(iid, values=cur_vals)

    def start_conversion(self):
        """Inicia o processo de conversão em segundo plano para não travar a GUI."""
        if not self.files_list:
            messagebox.showwarning(
                "Nenhum arquivo",
                "Adicione ao menos um arquivo (.lay ou .onx) para conversão.",
                parent=self
            )
            return

        if self.is_converting:
            return

        # Valida pasta de destino personalizada
        if self.var_dest_mode.get() == "custom":
            cust_p = self.var_custom_dest.get().strip()
            if not cust_p:
                messagebox.showwarning(
                    "Pasta de Destino",
                    "Por favor selecione a pasta de destino personalizada.",
                    parent=self
                )
                return
            if not Path(cust_p).exists():
                try:
                    Path(cust_p).mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    messagebox.showerror(
                        "Erro na Pasta",
                        f"Não foi possível criar a pasta de destino:\n{e}",
                        parent=self
                    )
                    return

        self.is_converting = True
        self.btn_convert.config(state="disabled", text="⏳ Convertendo...")
        self.progress_bar["maximum"] = len(self.files_list)
        self.progress_bar["value"] = 0

        # Dispara thread de processamento
        worker = threading.Thread(target=self._worker_run, daemon=True)
        worker.start()

    def _worker_run(self):
        """Loop de conversão executado em thread separada."""
        total = len(self.files_list)
        successes = 0
        failures = 0

        dest_mode = self.var_dest_mode.get()
        custom_dir = Path(self.var_custom_dest.get().strip()) if dest_mode == "custom" else None

        for idx, src_path in enumerate(self.files_list):
            target_fmt = self.get_target_format_for_file(src_path)

            if custom_dir:
                dst_path = custom_dir / src_path.with_suffix(f".{target_fmt}").name
            else:
                dst_path = src_path.with_suffix(f".{target_fmt}")

            # Registra última pasta de destino para o botão "Abrir Pasta"
            self.last_destination_dir = dst_path.parent

            # Atualiza status na tabela para "Processando..."
            self.after(0, self._update_row_status, idx, "Processando...", "pending")
            self.after(0, self.var_status_text.set, f"Convertendo {idx + 1} de {total}...")

            res: ConversionResult = convert_file(
                input_path=src_path,
                output_path=dst_path,
                target_format=target_fmt,
                db=self.db
            )

            if res.success:
                successes += 1
                self.after(0, self._update_row_status, idx, "Concluído", "ok")
                log_msg = (
                    f"[OK] {src_path.name} ➔ {dst_path.name} | "
                    f"{res.items_count} peças, {res.dies_count} moldes | "
                    f"{res.width_mm:.1f} x {res.height_mm:.1f} mm"
                )
                self.after(0, self.log, log_msg, "ok")
            else:
                failures += 1
                self.after(0, self._update_row_status, idx, "Erro", "error")
                log_msg = f"[ERRO] {src_path.name}: {res.error_message}"
                self.after(0, self.log, log_msg, "err")

            self.after(0, self._increment_progress, idx + 1)

        # Finalização
        self.after(0, self._conversion_finished, total, successes, failures)

    def _update_row_status(self, idx: int, status: str, tag: str):
        iid = str(idx)
        if self.tree.exists(iid):
            vals = list(self.tree.item(iid, "values"))
            vals[4] = status
            self.tree.item(iid, values=vals, tags=(tag,))

    def _increment_progress(self, current_val: int):
        self.progress_bar["value"] = current_val

    def _conversion_finished(self, total: int, successes: int, failures: int):
        self.is_converting = False
        self.btn_convert.config(state="normal", text="▶ Iniciar Conversão")

        if self.last_destination_dir and self.last_destination_dir.exists():
            self.btn_open_folder.config(state="normal")

        summary = f"Concluído: {successes} com sucesso, {failures} falha(s) de um total de {total}."
        self.var_status_text.set(summary)
        self.log("=" * 60)
        self.log(summary, "info")

        if failures == 0:
            messagebox.showinfo(
                "Conversão Concluída",
                f"Todos os {successes} arquivo(s) foram convertidos com sucesso!",
                parent=self
            )
        else:
            messagebox.showwarning(
                "Conversão Concluída com Alertas",
                f"Conversão finalizada:\n- {successes} convertidos com sucesso\n- {failures} falharam\n\nConsulte o registro abaixo para detalhes.",
                parent=self
            )

    def open_destination_folder(self):
        """Abre a pasta onde os arquivos convertidos foram salvos no gerenciador do sistema."""
        target = self.last_destination_dir
        if not target or not target.exists():
            messagebox.showinfo("Pasta de Destino", "Nenhuma pasta de destino válida para abrir.", parent=self)
            return

        try:
            if sys.platform.startswith("win"):
                os.startfile(str(target))
            elif sys.platform.startswith("darwin"):
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as e:
            messagebox.showerror("Erro ao abrir pasta", f"Não foi possível abrir a pasta:\n{e}", parent=self)
