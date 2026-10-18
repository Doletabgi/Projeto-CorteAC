"""
JobManager 2000 (Python Edition)
Diálogo para Seleção e Adição de Moldes à Sessão de Corte (Aba Moldes)
"""

import copy
import tkinter as tk
from tkinter import ttk, messagebox
from config import THEME


class AddShapesDialog(tk.Toplevel):
    def __init__(self, parent, all_shapes, current_session_shapes=None, on_add_callback=None, **kwargs):
        super().__init__(parent, bg=THEME["bg_surface"], **kwargs)
        self.title("Adicionar Moldes à Sessão")
        self.geometry("720x540")
        self.minsize(580, 420)
        self.transient(parent)
        self.grab_set()

        self.all_shapes = all_shapes or []
        self.current_session_shapes = current_session_shapes or []
        self.on_add_callback = on_add_callback

        # IDs dos moldes já presentes nesta sessão para evitar duplicidade ou sinalizar
        self.existing_ids = {s.get("id") for s in self.current_session_shapes if s.get("id")}

        # Dicionário de seleção: {shape_id: bool}
        self.selected_map = {}
        # Dicionário de pares customizados: {shape_id: int}
        self.pairs_map = {}

        self.setup_ui()
        self.populate_tree()

        # Centraliza sobre o pai
        self.update_idletasks()
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(30, px)}+{max(30, py)}")
        except Exception:
            pass

    def setup_ui(self):
        # 1. Cabeçalho com Instrução e Busca
        top_frame = tk.Frame(self, bg=THEME["bg_surface"], padx=10, pady=8)
        top_frame.pack(side="top", fill="x")

        tk.Label(
            top_frame,
            text="Selecione os moldes do catálogo que deseja adicionar à sessão de corte:",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", pady=(0, 6))

        filter_bar = tk.Frame(top_frame, bg=THEME["bg_surface"])
        filter_bar.pack(fill="x")

        tk.Label(filter_bar, text="🔍 Buscar:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.entry_search = ttk.Entry(filter_bar, font=("Segoe UI", 9))
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_search.bind("<KeyRelease>", lambda e: self.filter_tree())

        # Filtro de Pasta
        tk.Label(filter_bar, text="Pasta:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        folders = ["(Todas as Pastas)"] + sorted(list({s.get("folder") or "Raiz" for s in self.all_shapes}))
        self.cb_folder = ttk.Combobox(filter_bar, values=folders, state="readonly", width=18, font=("Segoe UI", 9))
        self.cb_folder.set("(Todas as Pastas)")
        self.cb_folder.pack(side="left")
        self.cb_folder.bind("<<ComboboxSelected>>", lambda e: self.filter_tree())

        # 2. Barra de Seleção Rápida e Pares Padrão
        bar_actions = tk.Frame(self, bg=THEME["bg_card"], padx=10, pady=6, relief="groove", bd=1)
        bar_actions.pack(side="top", fill="x", padx=8, pady=(0, 6))

        tk.Button(
            bar_actions, text="☑️ Marcar Todos", relief="raised", bd=1,
            bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8),
            command=self.select_all
        ).pack(side="left", padx=2)

        tk.Button(
            bar_actions, text="⬜ Desmarcar Todos", relief="raised", bd=1,
            bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8),
            command=self.deselect_all
        ).pack(side="left", padx=2)

        # Pares padrão para os selecionados
        tk.Label(bar_actions, text="Pares padrão:", bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 9)).pack(side="left", padx=(16, 4))
        self.spin_pairs = ttk.Spinbox(bar_actions, from_=1, to=9999, width=6, font=("Segoe UI", 9))
        self.spin_pairs.set("24")
        self.spin_pairs.pack(side="left")

        tk.Button(
            bar_actions, text="Aplicar aos Selecionados", relief="raised", bd=1,
            bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8),
            command=self.apply_pairs_to_selected
        ).pack(side="left", padx=6)

        # 3. Tabela de Moldes
        tree_frame = tk.Frame(self, bg="#ffffff", relief="sunken", bd=2)
        tree_frame.pack(side="top", fill="both", expand=True, padx=8, pady=2)

        cols = ("sel", "id", "name", "folder", "size", "pairs", "status")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("sel", text="✓", anchor="center")
        self.tree.heading("id", text="ID", anchor="center")
        self.tree.heading("name", text="Nome do Molde", anchor="w")
        self.tree.heading("folder", text="Pasta / Percurso", anchor="w")
        self.tree.heading("size", text="Tamanho", anchor="center")
        self.tree.heading("pairs", text="Pares", anchor="center")
        self.tree.heading("status", text="Status na Sessão", anchor="center")

        self.tree.column("sel", width=36, anchor="center", stretch=False)
        self.tree.column("id", width=55, anchor="center", stretch=False)
        self.tree.column("name", width=190, anchor="w")
        self.tree.column("folder", width=150, anchor="w")
        self.tree.column("size", width=65, anchor="center", stretch=False)
        self.tree.column("pairs", width=65, anchor="center", stretch=False)
        self.tree.column("status", width=120, anchor="center", stretch=False)

        sb_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        sb_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<space>", self.on_tree_space)

        # 4. Rodapé com Botões de Ação
        bot_bar = tk.Frame(self, bg=THEME["bg_surface"], padx=10, pady=8)
        bot_bar.pack(side="bottom", fill="x")

        self.lbl_sel_count = tk.Label(
            bot_bar, text="0 molde(s) selecionado(s)",
            bg=THEME["bg_surface"], fg=THEME["text_muted"], font=("Segoe UI", 9)
        )
        self.lbl_sel_count.pack(side="left")

        tk.Button(
            bot_bar, text="✕ Cancelar", relief="raised", bd=2, width=12,
            bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9),
            command=self.destroy
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            bot_bar, text="➕ Adicionar à Sessão", relief="raised", bd=2, width=22,
            bg="#2563eb", fg="#ffffff", font=("Segoe UI", 9, "bold"),
            command=self.confirm_add
        ).pack(side="right", padx=4)

    def populate_tree(self):
        query = self.entry_search.get().strip().lower()
        folder_filter = self.cb_folder.get()

        self.tree.delete(*self.tree.get_children())

        for s in self.all_shapes:
            s_id = s.get("id")
            s_name = s.get("name", f"Molde #{s_id}")
            s_folder = s.get("folder") or "Raiz"
            s_size = str(s.get("size", "35.5a"))

            # Filtros
            if folder_filter != "(Todas as Pastas)":
                if folder_filter == "Raiz" and s_folder != "Raiz":
                    continue
                elif folder_filter != "Raiz" and s_folder != folder_filter:
                    continue

            if query:
                if query not in s_name.lower() and query not in s_folder.lower() and query not in s_size.lower():
                    continue

            # Estado de seleção
            is_sel = self.selected_map.get(s_id, False)
            mark = "☑" if is_sel else "☐"

            # Pares
            pairs = self.pairs_map.get(s_id, s.get("pairs", 24))

            # Status existente
            if s_id in self.existing_ids:
                status_txt = "Já na sessão"
            else:
                status_txt = "Disponível"

            iid = str(s_id)
            self.tree.insert(
                "", "end", iid=iid,
                values=(mark, s_id, s_name, s_folder, s_size, pairs, status_txt)
            )

        self.update_count_label()

    def filter_tree(self):
        self.populate_tree()

    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        iid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not iid:
            return

        if col == "#1" or region == "cell":
            try:
                s_id = int(iid)
                self.selected_map[s_id] = not self.selected_map.get(s_id, False)
                self.update_row_mark(iid, s_id)
                self.update_count_label()
            except ValueError:
                pass

    def on_tree_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        try:
            s_id = int(iid)
            self.selected_map[s_id] = not self.selected_map.get(s_id, False)
            self.update_row_mark(iid, s_id)
            self.update_count_label()
        except ValueError:
            pass

    def on_tree_space(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        for iid in sel:
            try:
                s_id = int(iid)
                self.selected_map[s_id] = not self.selected_map.get(s_id, False)
                self.update_row_mark(iid, s_id)
            except ValueError:
                pass
        self.update_count_label()

    def update_row_mark(self, iid, s_id):
        if not self.tree.exists(iid):
            return
        vals = list(self.tree.item(iid, "values"))
        is_sel = self.selected_map.get(s_id, False)
        vals[0] = "☑" if is_sel else "☐"
        self.tree.item(iid, values=vals)

    def select_all(self):
        for s in self.all_shapes:
            s_id = s.get("id")
            if s_id:
                self.selected_map[s_id] = True
        self.populate_tree()

    def deselect_all(self):
        self.selected_map.clear()
        self.populate_tree()

    def apply_pairs_to_selected(self):
        try:
            val = int(self.spin_pairs.get().strip())
        except ValueError:
            val = 24
        for s_id, is_sel in self.selected_map.items():
            if is_sel:
                self.pairs_map[s_id] = val
        self.populate_tree()

    def update_count_label(self):
        cnt = sum(1 for v in self.selected_map.values() if v)
        self.lbl_sel_count.config(text=f"{cnt} molde(s) selecionado(s)")

    def confirm_add(self):
        selected_shapes = []
        for s in self.all_shapes:
            s_id = s.get("id")
            if s_id and self.selected_map.get(s_id, False):
                shape_copy = copy.deepcopy(s)
                shape_copy["pairs"] = self.pairs_map.get(s_id, s.get("pairs", 24))
                selected_shapes.append(shape_copy)

        if not selected_shapes:
            messagebox.showwarning(
                "Nenhum Molde Selecionado",
                "Selecione ao menos um molde na tabela marcando a caixa de seleção [✓] antes de adicionar.",
                parent=self
            )
            return

        if self.on_add_callback:
            self.on_add_callback(selected_shapes)

        self.destroy()
