"""
JobManager 2000 (Python Edition)
User Management Dialog - Cadastro e Gerenciamento de Usuários / Operadores
Permite cadastrar operadores, definir o usuário ativo e configurar a exibição
do nome do operador na folha de impressão A4.
"""

import tkinter as tk
from ui.icon_widgets import IconButton, IconLabel
from tkinter import ttk, messagebox
from typing import Optional, Callable
from config import THEME


class UserManagementDialog(tk.Toplevel):
    """
    Diálogo modal para cadastrar, remover e alternar o usuário / operador ativo.
    O nome do operador ativo é impresso na folha de layout abaixo do título (lay0000.lay).
    """
    def __init__(self, parent, db=None, on_update_callback: Optional[Callable] = None):
        super().__init__(parent)
        self.parent = parent
        self.on_update_callback = on_update_callback

        # Obtenção do banco de dados
        if db is not None:
            self.db = db
        elif hasattr(parent, "db") and getattr(parent, "db", None):
            self.db = getattr(parent, "db")
        else:
            from database import DatabaseManager
            self.db = DatabaseManager()

        self.title("👤 Cadastro de Usuários / Operadores")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.configure(bg=THEME["bg_surface"])

        dlg_w, dlg_h = 540, 520
        self.geometry(f"{dlg_w}x{dlg_h}")

        # Centraliza sobre a janela pai
        self.update_idletasks()
        try:
            rx = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
            ry = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
            self.geometry(f"+{max(10, rx)}+{max(10, ry)}")
        except Exception:
            pass

        # Estado
        self.active_user = self.db.get_active_user()
        self.prefix_var = tk.StringVar(value=self.db.get_user_print_prefix() or "Usuário")

        self.setup_ui()
        self.refresh_user_list()
        self.update_preview()

        self.bind("<Escape>", lambda e: self.destroy())

    def setup_ui(self):
        main_box = tk.Frame(self, bg=THEME["bg_surface"], padx=14, pady=12)
        main_box.pack(fill="both", expand=True)

        # Cabeçalho
        IconLabel(
            main_box, text="👤 Cadastro de Usuários / Operadores",
            font=("Segoe UI", 11, "bold"), bg=THEME["bg_surface"], fg=THEME["text_main"]
        ).pack(anchor="w", pady=(0, 2))

        tk.Label(
            main_box,
            text="Cadastre os operadores e selecione quem está trabalhando.\n"
                 "Ao salvar a produção, o usuário ativo será registrado na folha.",
            font=("Segoe UI", 8), bg=THEME["bg_surface"], fg="#555555", justify="left"
        ).pack(anchor="w", pady=(0, 10))

        # 1. Campo de Adicionar Novo Usuário
        add_frame = tk.LabelFrame(
            main_box, text="Cadastrar Novo Usuário", bg=THEME["bg_surface"],
            fg=THEME["text_main"], font=("Segoe UI", 8, "bold"), padx=10, pady=8, relief="groove"
        )
        add_frame.pack(fill="x", pady=(0, 10))

        tk.Label(
            add_frame, text="Nome:", bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 6))

        self.entry_name = tk.Entry(add_frame, font=("Segoe UI", 9), relief="sunken", bd=2)
        self.entry_name.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_name.bind("<Return>", lambda e: self.on_add_user())

        btn_add = IconButton(
            add_frame, text="➕ Cadastrar", bg="#2563eb", fg="#ffffff",
            activebackground="#1d4ed8", activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"), relief="raised", bd=1, padx=10, pady=2,
            cursor="hand2", command=self.on_add_user
        )
        btn_add.pack(side="right")

        # 2. Lista de Usuários Cadastrados
        list_frame = tk.LabelFrame(
            main_box, text="Usuários do Sistema", bg=THEME["bg_surface"],
            fg=THEME["text_main"], font=("Segoe UI", 8, "bold"), padx=10, pady=8, relief="groove"
        )
        list_frame.pack(fill="both", expand=True, pady=(0, 10))

        content_list = tk.Frame(list_frame, bg=THEME["bg_surface"])
        content_list.pack(fill="both", expand=True)

        # Treeview com Scrollbar
        self.tree = ttk.Treeview(content_list, columns=("status", "name"), show="headings", height=5, selectmode="browse")
        self.tree.heading("status", text="Status")
        self.tree.heading("name", text="Nome do Operador / Usuário")
        self.tree.column("status", width=90, minwidth=80, stretch=False, anchor="center")
        self.tree.column("name", width=260, minwidth=180, anchor="w")

        scroll_tree = ttk.Scrollbar(content_list, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_tree.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll_tree.pack(side="left", fill="y", padx=(2, 8))

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self.on_set_active())

        # Botões de Ação na Lista
        btn_col = tk.Frame(content_list, bg=THEME["bg_surface"])
        btn_col.pack(side="right", fill="y")

        self.btn_set_active = IconButton(
            btn_col, text="✓ Definir Ativo", bg="#16a34a", fg="#ffffff",
            activebackground="#15803d", activeforeground="#ffffff",
            font=("Segoe UI", 8, "bold"), relief="raised", bd=1, padx=6, pady=4,
            cursor="hand2", command=self.on_set_active, state="disabled"
        )
        self.btn_set_active.pack(fill="x", pady=(0, 6))

        self.btn_delete = IconButton(
            btn_col, text="🗑️ Excluir", bg=THEME["bg_surface"], fg="#dc2626",
            activebackground="#fee2e2", activeforeground="#b91c1c",
            font=("Segoe UI", 8), relief="raised", bd=1, padx=6, pady=4,
            cursor="hand2", command=self.on_delete_user, state="disabled"
        )
        self.btn_delete.pack(fill="x")

        # 3. Formato do Rótulo de Impressão
        fmt_frame = tk.LabelFrame(
            main_box, text="Formato na Folha de Impressão", bg=THEME["bg_surface"],
            fg=THEME["text_main"], font=("Segoe UI", 8, "bold"), padx=10, pady=6, relief="groove"
        )
        fmt_frame.pack(fill="x", pady=(0, 10))

        radio_row = tk.Frame(fmt_frame, bg=THEME["bg_surface"])
        radio_row.pack(anchor="w")

        tk.Radiobutton(
            radio_row, text="Usuário: [Nome]", variable=self.prefix_var, value="Usuário",
            bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8),
            command=self._on_prefix_changed
        ).pack(side="left", padx=(0, 14))

        tk.Radiobutton(
            radio_row, text="Operador: [Nome]", variable=self.prefix_var, value="Operador",
            bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8),
            command=self._on_prefix_changed
        ).pack(side="left", padx=(0, 14))

        tk.Radiobutton(
            radio_row, text="Apenas [Nome]", variable=self.prefix_var, value="",
            bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8),
            command=self._on_prefix_changed
        ).pack(side="left")

        # 4. Prévia na Folha de Impressão
        prev_frame = tk.LabelFrame(
            main_box, text="Prévia na Folha de Impressão (Abaixo do Título)",
            bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 8, "bold"), padx=10, pady=6, relief="groove"
        )
        prev_frame.pack(fill="x", pady=(0, 10))

        card = tk.Frame(prev_frame, bg="#ffffff", relief="solid", bd=1, padx=10, pady=6)
        card.pack(fill="x")

        self.lbl_prev_title = tk.Label(
            card, text="lay0000 (Placa 1 de 2)", bg="#ffffff", fg="#000000",
            font=("Courier", 10, "bold"), anchor="w"
        )
        self.lbl_prev_title.pack(anchor="w")

        self.prev_line = tk.Frame(card, bg="#000000", height=2)
        self.prev_line.pack(fill="x", pady=(1, 3))

        self.lbl_prev_user = tk.Label(
            card, text="", bg="#ffffff", fg="#000000",
            font=("Courier", 9, "bold"), anchor="w"
        )
        self.lbl_prev_user.pack(anchor="w")

        # Barra Inferior de Botões
        btn_bar = tk.Frame(self, bg=THEME["bg_surface"], padx=14, pady=8)
        btn_bar.pack(fill="x", side="bottom")

        IconButton(
            btn_bar, text="✓ Concluir", bg="#2563eb", fg="#ffffff",
            activebackground="#1d4ed8", activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"), relief="raised", bd=1, padx=14, pady=4,
            cursor="hand2", command=self.on_close
        ).pack(side="right", padx=(4, 0))

        IconButton(
            btn_bar, text="Fechar", bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), relief="raised", bd=1, padx=10, pady=4,
            cursor="hand2", command=self.destroy
        ).pack(side="right")

    def refresh_user_list(self):
        """Recarrega a lista de usuários a partir do banco de dados."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.active_user = self.db.get_active_user()
        users = self.db.get_users()

        for u in users:
            name = u.get("name", "")
            is_active = (name == self.active_user) or bool(u.get("is_active"))
            status_txt = "✓ Ativo" if is_active else ""
            item_id = self.tree.insert("", "end", values=(status_txt, name))
            if is_active:
                self.tree.selection_set(item_id)

        self._on_tree_select()
        self.update_preview()

    def _on_tree_select(self, event=None):
        sel = self.tree.selection()
        if sel:
            self.btn_set_active.config(state="normal")
            self.btn_delete.config(state="normal")
        else:
            self.btn_set_active.config(state="disabled")
            self.btn_delete.config(state="disabled")

    def _on_prefix_changed(self):
        pref = self.prefix_var.get()
        self.db.set_user_print_prefix(pref)
        self.update_preview()
        if callable(self.on_update_callback):
            self.on_update_callback()

    def update_preview(self):
        pref = self.prefix_var.get()
        user = self.active_user or ""
        if user:
            if pref:
                if user.lower().startswith((pref.lower() + ":", "usuário:", "usuario:", "operador:")):
                    disp = user
                else:
                    disp = f"{pref}: {user}"
            else:
                disp = user
            self.lbl_prev_user.config(text=disp, fg="#000000")
        else:
            self.lbl_prev_user.config(
                text="[Nenhum usuário ativo selecionado]",
                fg="#888888"
            )

    def on_add_user(self):
        name = self.entry_name.get().strip()
        if not name:
            messagebox.showwarning("Nome Inválido", "Por favor, digite o nome do usuário.", parent=self)
            return

        if self.db.add_user(name):
            self.entry_name.delete(0, "end")
            self.refresh_user_list()
            if callable(self.on_update_callback):
                self.on_update_callback()
        else:
            messagebox.showerror("Erro", "Não foi possível cadastrar o usuário.", parent=self)

    def on_set_active(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if vals and len(vals) > 1:
            name = vals[1]
            self.db.set_active_user(name)
            self.refresh_user_list()
            if callable(self.on_update_callback):
                self.on_update_callback()

    def on_delete_user(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if not vals or len(vals) < 2:
            return
        name = vals[1]
        if messagebox.askyesno("Excluir Usuário", f"Deseja remover o usuário '{name}'?", parent=self):
            self.db.delete_user(name)
            self.refresh_user_list()
            if callable(self.on_update_callback):
                self.on_update_callback()

    def on_close(self):
        if callable(self.on_update_callback):
            self.on_update_callback()
        self.destroy()


def open_user_management_dialog(parent, db=None, on_update_callback=None):
    """Helper para instanciar e abrir o diálogo de cadastro de usuário."""
    return UserManagementDialog(parent, db=db, on_update_callback=on_update_callback)
