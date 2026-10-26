"""
JobManager 2000 (Python Edition)
Import Materials Dialog - Janela modal para importação em lote de materiais.
Permite selecionar arquivos CSV, TSV, TXT ou JSON, pré-visualizar itens com detecção
de novos / atualizados / erros, gerar modelo de exemplo e gravar no banco de dados.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import Optional, Callable

from config import THEME
from cad.material_importer import parse_material_file, generate_csv_template


class ImportMaterialsDialog(tk.Toplevel):
    """Diálogo autêntico Windows XP para importação de lista de materiais."""

    def __init__(self, parent, db, on_success: Optional[Callable] = None):
        super().__init__(parent)
        self.db = db
        self.on_success_cb = on_success

        self.title("Importar Lista de Materiais")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.configure(bg=THEME["bg_surface"])

        # Dimensões da janela modal
        dlg_w, dlg_h = 760, 520
        self.geometry(f"{dlg_w}x{dlg_h}")
        self.minsize(620, 400)

        # Centraliza sobre o parent
        self.update_idletasks()
        rx = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
        ry = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
        self.geometry(f"+{max(10, rx)}+{max(10, ry)}")

        self.current_filepath = None
        self.parsed_result = None
        self.var_overwrite = tk.BooleanVar(value=True)

        self.setup_ui()

        self.bind("<Escape>", lambda e: self.destroy())

    def setup_ui(self):
        # 1. Cabeçalho estilizado
        hdr = tk.Frame(self, bg=THEME["title_bar_bg"], height=28, padx=8, pady=4)
        hdr.pack(fill="x")

        tk.Label(
            hdr,
            text="📥 Importar Lista de Materiais para o Estoque",
            bg=THEME["title_bar_bg"],
            fg=THEME["title_bar_fg"],
            font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        # Container principal
        main_box = tk.Frame(self, bg=THEME["bg_surface"], padx=8, pady=8)
        main_box.pack(fill="both", expand=True)

        # 2. Área de Seleção de Arquivo e Modelo
        file_frame = tk.LabelFrame(
            main_box,
            text="Arquivo de Origem (CSV / TSV / TXT / JSON)",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8, "bold"),
            padx=8, pady=6
        )
        file_frame.pack(fill="x", pady=(0, 6))

        row_file = tk.Frame(file_frame, bg=THEME["bg_surface"])
        row_file.pack(fill="x")

        self.ent_filepath = tk.Entry(row_file, font=("Segoe UI", 9), relief="sunken", bd=1)
        self.ent_filepath.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.ent_filepath.bind("<Return>", lambda e: self.load_file_from_path(self.ent_filepath.get()))

        btn_browse = tk.Button(
            row_file,
            text="📂 Procurar...",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 8),
            padx=8, pady=1,
            command=self.browse_file
        )
        btn_browse.pack(side="left", padx=2)

        btn_template = tk.Button(
            row_file,
            text="📄 Baixar Modelo CSV...",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 8),
            padx=8, pady=1,
            command=self.download_csv_template
        )
        btn_template.pack(side="left", padx=2)

        # 3. Grade de Pré-visualização dos Dados
        preview_frame = tk.LabelFrame(
            main_box,
            text="Pré-visualização dos Materiais Identificados",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8, "bold"),
            padx=4, pady=4
        )
        preview_frame.pack(fill="both", expand=True, pady=4)

        grid_box = tk.Frame(preview_frame, bg="#ffffff", relief="sunken", bd=1)
        grid_box.pack(fill="both", expand=True)

        sb_y = ttk.Scrollbar(grid_box, orient="vertical")
        sb_y.pack(side="right", fill="y")
        sb_x = ttk.Scrollbar(grid_box, orient="horizontal")
        sb_x.pack(side="bottom", fill="x")

        self.cols = ("status", "code", "desc", "definicao", "largura", "comprimento", "camadas", "detalhes")
        self.tree = ttk.Treeview(
            grid_box,
            columns=self.cols,
            show="headings",
            yscrollcommand=sb_y.set,
            xscrollcommand=sb_x.set,
            selectmode="extended"
        )
        self.tree.pack(fill="both", expand=True)
        sb_y.config(command=self.tree.yview)
        sb_x.config(command=self.tree.xview)

        # Cabeçalhos
        self.tree.heading("status", text="Status", anchor="center")
        self.tree.heading("code", text="Código", anchor="w")
        self.tree.heading("desc", text="Descrição", anchor="w")
        self.tree.heading("definicao", text="Definição", anchor="w")
        self.tree.heading("largura", text="Largura (m)", anchor="center")
        self.tree.heading("comprimento", text="Comprimento (m)", anchor="center")
        self.tree.heading("camadas", text="Camadas", anchor="center")
        self.tree.heading("detalhes", text="Detalhes / Erro", anchor="w")

        # Larguras
        self.tree.column("status", width=90, minwidth=70, stretch=False, anchor="center")
        self.tree.column("code", width=110, minwidth=80, stretch=False, anchor="w")
        self.tree.column("desc", width=220, minwidth=140, stretch=True, anchor="w")
        self.tree.column("definicao", width=95, minwidth=75, stretch=False, anchor="w")
        self.tree.column("largura", width=85, minwidth=65, stretch=False, anchor="center")
        self.tree.column("comprimento", width=105, minwidth=75, stretch=False, anchor="center")
        self.tree.column("camadas", width=65, minwidth=50, stretch=False, anchor="center")
        self.tree.column("detalhes", width=140, minwidth=100, stretch=True, anchor="w")

        # Configurações visuais de tags
        self.tree.tag_configure("status_new", background="#ffffff", foreground="#006600")
        self.tree.tag_configure("status_update", background="#f0f7ff", foreground="#0044aa")
        self.tree.tag_configure("status_invalid", background="#ffebee", foreground="#bb0000")

        # 4. Opções e Resumo
        opts_box = tk.Frame(main_box, bg=THEME["bg_surface"])
        opts_box.pack(fill="x", pady=(4, 0))

        chk_overwrite = tk.Checkbutton(
            opts_box,
            text="Sobrescrever / atualizar materiais existentes com o mesmo código",
            variable=self.var_overwrite,
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8)
        )
        chk_overwrite.pack(side="left")

        self.lbl_summary = tk.Label(
            opts_box,
            text="Nenhum arquivo carregado.",
            bg=THEME["bg_surface"],
            fg="#444444",
            font=("Segoe UI", 8, "bold")
        )
        self.lbl_summary.pack(side="right")

        # 5. Barra Inferior de Botões
        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill="x", padx=8, pady=(4, 4))

        btn_bar = tk.Frame(self, bg=THEME["bg_surface"], padx=8, pady=6)
        btn_bar.pack(fill="x")

        self.btn_import = tk.Button(
            btn_bar,
            text="✔ Confirmar Importação",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 9, "bold"),
            padx=12, pady=2,
            state="disabled",
            command=self.execute_import
        )
        self.btn_import.pack(side="right", padx=4)

        btn_cancel = tk.Button(
            btn_bar,
            text="Cancelar",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 9),
            padx=12, pady=2,
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=4)

    def browse_file(self):
        """Abre diálogo para seleção do arquivo de materiais."""
        types = [
            ("Arquivos de Dados (*.csv, *.tsv, *.txt, *.json)", "*.csv;*.tsv;*.txt;*.json"),
            ("Arquivos CSV (*.csv)", "*.csv"),
            ("Arquivos Texto / TSV (*.tsv, *.txt)", "*.tsv;*.txt"),
            ("Arquivos JSON (*.json)", "*.json"),
            ("Todos os Arquivos (*.*)", "*.*")
        ]
        chosen = filedialog.askopenfilename(
            parent=self,
            title="Selecionar Arquivo de Materiais",
            filetypes=types
        )
        if chosen:
            self.load_file_from_path(chosen)

    def download_csv_template(self):
        """Permite ao usuário salvar um arquivo modelo CSV de exemplo."""
        chosen = filedialog.asksaveasfilename(
            parent=self,
            title="Salvar Modelo CSV de Materiais",
            defaultextension=".csv",
            initialfile="modelo_materiais.csv",
            filetypes=[("Arquivos CSV (*.csv)", "*.csv"), ("Todos os Arquivos (*.*)", "*.*")]
        )
        if chosen:
            try:
                content = generate_csv_template(delimiter=";")
                with open(chosen, "w", encoding="utf-8-sig") as f:
                    f.write(content)
                messagebox.showinfo(
                    "Modelo Salvo",
                    f"Arquivo modelo CSV salvo com sucesso em:\n{chosen}\n\nVocê pode abri-lo no Excel ou Bloco de Notas para preencher seus materiais.",
                    parent=self
                )
            except Exception as e:
                messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo:\n{e}", parent=self)

    def load_file_from_path(self, filepath: str):
        """Lê e processa o arquivo informado."""
        filepath = filepath.strip()
        if not filepath or not os.path.isfile(filepath):
            messagebox.showwarning("Aviso", "O arquivo especificado não existe ou não é válido.", parent=self)
            return

        self.current_filepath = filepath
        self.ent_filepath.delete(0, "end")
        self.ent_filepath.insert(0, filepath)

        try:
            # Busca IDs existentes no banco para detectar duplicados/atualizações
            existing_mats = self.db.get_materials()
            existing_ids = {str(m["id"]).strip() for m in existing_mats}

            self.parsed_result = parse_material_file(filepath, existing_ids=existing_ids)
            self.populate_preview(self.parsed_result)
        except Exception as e:
            messagebox.showerror("Erro na Leitura", f"Falha ao ler o arquivo:\n{e}", parent=self)
            self.btn_import.config(state="disabled")

    def populate_preview(self, result: dict):
        """Preenche a tabela Treeview com os materiais identificados."""
        self.tree.delete(*self.tree.get_children())
        items = result.get("items", [])
        summary = result.get("summary", {})

        for item in items:
            status_code = item["status"]
            if status_code == "new":
                status_txt = "➕ Novo"
                tag = "status_new"
            elif status_code == "update":
                status_txt = "↻ Atualizar"
                tag = "status_update"
            else:
                status_txt = "❌ Erro"
                tag = "status_invalid"

            w_m = f"{item['width_mm'] / 1000.0:.2f}".replace(".", ",")
            l_m = f"{item['height_mm'] / 1000.0:.2f}".replace(".", ",")
            details = item.get("error_msg") or ("Atualizará material existente" if status_code == "update" else "Pronto para cadastro")

            self.tree.insert(
                "", "end",
                values=(
                    status_txt,
                    item["id"],
                    item["name"],
                    item["type"],
                    w_m,
                    l_m,
                    str(item["layers"]),
                    details
                ),
                tags=(tag,)
            )

        # Atualiza resumo
        tot = summary.get("total", 0)
        v_new = summary.get("new", 0)
        v_upd = summary.get("update", 0)
        v_err = summary.get("invalid", 0)

        self.lbl_summary.config(
            text=f"Total: {tot} item(s) | Novos: {v_new} | Atualizações: {v_upd} | Inválidos: {v_err}"
        )

        valid_count = summary.get("valid", 0)
        if valid_count > 0:
            self.btn_import.config(state="normal")
        else:
            self.btn_import.config(state="disabled")

    def execute_import(self):
        """Grava os materiais válidos no banco de dados SQLite/MySQL."""
        if not self.parsed_result:
            return

        items = self.parsed_result.get("items", [])
        overwrite = self.var_overwrite.get()

        imported_count = 0
        updated_count = 0
        skipped_count = 0

        try:
            for it in items:
                status = it["status"]
                if status == "invalid":
                    skipped_count += 1
                    continue

                if status == "update" and not overwrite:
                    skipped_count += 1
                    continue

                # Cria ou atualiza via DatabaseManager
                self.db.create_material(
                    mat_id=it["id"],
                    name=it["name"],
                    type=it["type"],
                    width_mm=it["width_mm"],
                    height_mm=it["height_mm"],
                    thickness_mm=it.get("thickness_mm", 0.0),
                    layers=it.get("layers", 2),
                    gap_mm=it.get("gap_mm", 1.0)
                )

                if status == "update":
                    updated_count += 1
                else:
                    imported_count += 1

            # Sucesso
            msg = f"Importação concluída com sucesso!\n\n"
            msg += f"• Novos materiais cadastrados: {imported_count}\n"
            msg += f"• Materiais atualizados: {updated_count}\n"
            if skipped_count > 0:
                msg += f"• Itens ignorados/erros: {skipped_count}\n"

            messagebox.showinfo("Importação Concluída", msg, parent=self)

            if self.on_success_cb:
                self.on_success_cb()

            self.destroy()

        except Exception as e:
            messagebox.showerror("Erro na Gravação", f"Ocorreu um erro ao gravar os materiais:\n{e}", parent=self)
