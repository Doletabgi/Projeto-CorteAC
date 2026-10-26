"""
JobManager 2000 (Python Edition)
Material Codes View - Reprodução 100% autêntica da janela 'Códigos materiais' (media_1792065351450.jpg)
Tabela DataGrid com linhas zebradas (branco / pêssego #fed8b1), indicador de seleção [►],
linha de inserção [*] e cadastro rápido de materiais no estoque.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from config import THEME

class MaterialCodesView(tk.Frame):
    def __init__(self, parent, db, on_close=None, on_minimize=None, on_maximize=None, on_material_changed=None, **kwargs):
        super().__init__(parent, bg=THEME["bg_surface"], relief="ridge", bd=2, **kwargs)
        self.db = db
        self.on_close_cb = on_close
        self.on_minimize_cb = on_minimize
        self.on_maximize_cb = on_maximize
        self.on_material_changed_cb = on_material_changed

        self.icons = {}
        self.load_icons()
        self.setup_ui()
        self.refresh_table()

    def load_icons(self):
        assets_dir = Path(__file__).resolve().parent.parent / "assets"
        for name in ["btn_mat.png", "mode_mat.png", "app_icon_16.png"]:
            p = assets_dir / name
            if p.exists():
                try:
                    self.icons[name.replace(".png", "")] = tk.PhotoImage(file=str(p))
                except Exception:
                    pass

    def setup_ui(self):
        # -------------------------------------------------------------
        # 1. Barra de Título MDI Interna: 'Códigos materiais'
        # -------------------------------------------------------------
        title_bar = tk.Frame(self, bg=THEME["title_bar_bg"], height=24, padx=4, pady=2)
        title_bar.pack(fill="x")

        title_left = tk.Frame(title_bar, bg=THEME["title_bar_bg"])
        title_left.pack(side="left")

        icon_img = self.icons.get("btn_mat") or self.icons.get("mode_mat")
        if icon_img:
            tk.Label(title_left, image=icon_img, bg=THEME["title_bar_bg"]).pack(side="left", padx=(0, 4))

        self.lbl_title = tk.Label(
            title_left,
            text="Códigos materiais",
            bg=THEME["title_bar_bg"],
            fg=THEME["title_bar_fg"],
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_title.pack(side="left")

        # Botões de controle de janela
        btn_box = tk.Frame(title_bar, bg=THEME["title_bar_bg"])
        btn_box.pack(side="right")

        self.btn_min = tk.Button(btn_box, text="_", relief="raised", bd=1, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0, command=self.on_minimize_click)
        self.btn_min.pack(side="left", padx=1)
        self.btn_max = tk.Button(btn_box, text="□", relief="raised", bd=1, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0, command=self.on_maximize_click)
        self.btn_max.pack(side="left", padx=1)
        self.btn_close = tk.Button(btn_box, text="✕", relief="raised", bd=1, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0, command=self.on_close_click)
        self.btn_close.pack(side="left", padx=1)

        # Arrastar janela pelo título em modo flutuante
        title_bar.bind("<ButtonPress-1>", self._on_title_press)
        title_bar.bind("<B1-Motion>", self._on_title_motion)
        self.lbl_title.bind("<ButtonPress-1>", self._on_title_press)
        self.lbl_title.bind("<B1-Motion>", self._on_title_motion)
        self.bind("<Button-1>", lambda e: self.lift(), add="+")

        # -------------------------------------------------------------
        # 2. Barra de Ferramentas / Ações Rápidas (Facilita o Cadastro)
        # -------------------------------------------------------------
        toolbar = tk.Frame(self, bg=THEME["bg_surface"], relief="groove", bd=1, height=28, padx=4, pady=2)
        toolbar.pack(fill="x")

        btn_new = tk.Button(
            toolbar,
            text="➕ Novo Material",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 8, "bold"),
            padx=6, pady=1,
            command=self.open_new_material_dialog
        )
        btn_new.pack(side="left", padx=2)

        btn_edit = tk.Button(
            toolbar,
            text="✎ Editar",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 8),
            padx=6, pady=1,
            command=self.open_edit_selected_dialog
        )
        btn_edit.pack(side="left", padx=2)

        btn_del = tk.Button(
            toolbar,
            text="🗑 Excluir",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 8),
            padx=6, pady=1,
            command=self.delete_selected_material
        )
        btn_del.pack(side="left", padx=2)

        btn_refresh = tk.Button(
            toolbar,
            text="↻ Atualizar",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 8),
            padx=6, pady=1,
            command=self.refresh_table
        )
        btn_refresh.pack(side="left", padx=2)

        btn_import = tk.Button(
            toolbar,
            text="📥 Importar Lista...",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 8),
            padx=6, pady=1,
            command=self.open_import_dialog
        )
        btn_import.pack(side="left", padx=2)

        # Filtro de Busca Rápida
        tk.Label(toolbar, text="Filtrar:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8)).pack(side="left", padx=(12, 4))
        self.ent_search = tk.Entry(toolbar, font=("Segoe UI", 8), relief="sunken", bd=1, width=16)
        self.ent_search.pack(side="left", padx=2)
        self.ent_search.bind("<KeyRelease>", lambda e: self.filter_table(self.ent_search.get()))

        # Contador de Materiais Cadastrados
        self.lbl_count = tk.Label(toolbar, text="Total: 0", bg=THEME["bg_surface"], fg="#555555", font=("Segoe UI", 8))
        self.lbl_count.pack(side="right", padx=8)

        # -------------------------------------------------------------
        # 3. Tabela DataGrid Autêntica (media_1792065351450.jpg)
        # -------------------------------------------------------------
        grid_container = tk.Frame(self, bg="#ffffff", relief="sunken", bd=1)
        grid_container.pack(fill="both", expand=True, padx=2, pady=2)

        # Scrollbars
        sb_y = ttk.Scrollbar(grid_container, orient="vertical")
        sb_y.pack(side="right", fill="y")
        sb_x = ttk.Scrollbar(grid_container, orient="horizontal")
        sb_x.pack(side="bottom", fill="x")

        # Configura colunas exatamente como na imagem
        self.cols = ("sel", "code", "desc", "definicao", "largura", "comprimento", "camadas")
        self.tree = ttk.Treeview(
            grid_container,
            columns=self.cols,
            show="headings",
            yscrollcommand=sb_y.set,
            xscrollcommand=sb_x.set,
            selectmode="browse"
        )
        self.tree.pack(fill="both", expand=True)
        sb_y.config(command=self.tree.yview)
        sb_x.config(command=self.tree.xview)

        # Estilo dos cabeçalhos
        self.tree.heading("sel", text="", anchor="center")
        self.tree.heading("code", text="Código /", anchor="w")
        self.tree.heading("desc", text="Descrição", anchor="w")
        self.tree.heading("definicao", text="Definição", anchor="w")
        self.tree.heading("largura", text="Largura (m)", anchor="center")
        self.tree.heading("comprimento", text="Comprimento (m)", anchor="center")
        self.tree.heading("camadas", text="Camadas", anchor="center")

        # Larguras de coluna idênticas ao print
        self.tree.column("sel", width=26, minwidth=26, stretch=False, anchor="center")
        self.tree.column("code", width=95, minwidth=70, stretch=False, anchor="w")
        self.tree.column("desc", width=350, minwidth=180, stretch=True, anchor="w")
        self.tree.column("definicao", width=110, minwidth=85, stretch=False, anchor="w")
        self.tree.column("largura", width=85, minwidth=70, stretch=False, anchor="center")
        self.tree.column("comprimento", width=110, minwidth=85, stretch=False, anchor="center")
        self.tree.column("camadas", width=70, minwidth=55, stretch=False, anchor="center")

        # Cores zebradas autênticas: Branco e Pêssego (#fed8b1)
        self.tree.tag_configure("evenrow", background="#ffffff")
        self.tree.tag_configure("oddrow", background="#fed8b1")
        self.tree.tag_configure("insertrow", background="#f5f5f5", font=("Segoe UI", 8, "italic"))

        # Eventos do Treeview
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", self.on_row_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Return>", lambda e: self.open_edit_selected_dialog())

        # Menu de contexto com botão direito na tabela
        self.ctx_menu = tk.Menu(self, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
        self.ctx_menu.add_command(label="➕ Novo material...", command=self.open_new_material_dialog)
        self.ctx_menu.add_command(label="✎ Editar material...", command=self.open_edit_selected_dialog)
        self.ctx_menu.add_command(label="🗑 Excluir material", command=self.delete_selected_material)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="↻ Atualizar lista", command=self.refresh_table)
        self.ctx_menu.add_command(label="📥 Importar lista de materiais...", command=self.open_import_dialog)

    def refresh_table(self):
        """Recarrega todos os materiais do banco de dados SQLite."""
        self.all_materials = self.db.get_materials()
        self.populate_rows(self.all_materials)

    def filter_table(self, query):
        q = query.strip().lower()
        if not q:
            self.populate_rows(self.all_materials)
            return
        filtered = [m for m in self.all_materials if q in m["id"].lower() or q in m.get("name", "").lower()]
        self.populate_rows(filtered)

    def populate_rows(self, materials_list):
        self.tree.delete(*self.tree.get_children())

        # Linha superior de inserção [*] (conforme print original)
        self.tree.insert("", "end", iid="__new_record__", values=("*", "", "", "", "", "", ""), tags=("insertrow",))

        # Ordena alfanumericamente por código
        sorted_mats = sorted(materials_list, key=lambda x: str(x["id"]))
        self.lbl_count.config(text=f"Total: {len(sorted_mats)}")

        for idx, m in enumerate(sorted_mats):
            tag = "oddrow" if (idx % 2 == 1) else "evenrow"
            w_m = f"{m.get('width_mm', 1380.0) / 1000.0:.2f}".replace(".", ",") if m.get("width_mm") else ""
            l_m = f"{m.get('height_mm', 2980.0) / 1000.0:.2f}".replace(".", ",")
            layers = str(m.get("layers", 2))
            tipo = m.get("type", "como placa")
            if tipo in ["sheet", "leather"]:
                tipo = "como placa"

            self.tree.insert(
                "", "end",
                iid=m["id"],
                values=("", m["id"], m.get("name", ""), tipo, w_m, l_m, layers),
                tags=(tag,)
            )

        # Seleciona a primeira linha de dados se houver
        if sorted_mats:
            first_id = sorted_mats[0]["id"]
            self.tree.selection_set(first_id)
            self.tree.see(first_id)

    def on_row_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        sel_id = sel[0]

        # Atualiza o indicador [►] na linha selecionada
        for item in self.tree.get_children():
            vals = list(self.tree.item(item, "values"))
            if item == "__new_record__":
                vals[0] = "*"
            elif item == sel_id:
                vals[0] = "►"
            else:
                vals[0] = ""
            self.tree.item(item, values=vals)

    def on_row_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        sel_id = sel[0]
        if sel_id == "__new_record__":
            self.open_new_material_dialog()
        else:
            self.open_edit_material_dialog(sel_id)

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item and item != "__new_record__":
            self.tree.selection_set(item)
        try:
            self.ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.ctx_menu.grab_release()

    def open_new_material_dialog(self):
        """Abre modal ágil para cadastrar novo material."""
        self.show_material_dialog(mode="create")

    def open_edit_selected_dialog(self):
        sel = self.tree.selection()
        if not sel or sel[0] == "__new_record__":
            messagebox.showinfo("Códigos materiais", "Selecione um material para editar.", parent=self)
            return
        self.open_edit_material_dialog(sel[0])

    def open_edit_material_dialog(self, mat_id):
        mat = self.db.get_material(mat_id)
        if not mat:
            messagebox.showerror("Erro", f"Material {mat_id} não encontrado.", parent=self)
            return
        self.show_material_dialog(mode="edit", material=mat)

    def delete_selected_material(self):
        sel = self.tree.selection()
        if not sel or sel[0] == "__new_record__":
            return
        mat_id = sel[0]
        mat = self.db.get_material(mat_id)
        name = mat.get("name", mat_id) if mat else mat_id
        if messagebox.askyesno("Confirmar Exclusão", f"Deseja realmente excluir o material '{mat_id} - {name}'?", parent=self):
            self.db.delete_material(mat_id)
            self.refresh_table()
            if self.on_material_changed_cb:
                self.on_material_changed_cb()

    def open_import_dialog(self):
        """Abre diálogo para importação em lote de materiais (CSV, TSV, TXT, JSON)."""
        from ui.import_materials_dialog import ImportMaterialsDialog
        ImportMaterialsDialog(self, self.db, on_success=self.on_import_completed)

    def on_import_completed(self):
        """Callback executado após importar materiais com sucesso."""
        self.refresh_table()
        if self.on_material_changed_cb:
            self.on_material_changed_cb()

    def show_material_dialog(self, mode="create", material=None):
        """Modal autêntico para cadastro e edição rápida de materiais."""
        dlg = tk.Toplevel(self)
        dlg.title("Cadastro de Material" if mode == "create" else f"Editar Material [{material['id']}]")
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("420x340")
        dlg.resizable(False, False)
        dlg.configure(bg=THEME["bg_card"])

        rx = self.winfo_rootx() + (self.winfo_width() - 420) // 2
        ry = self.winfo_rooty() + (self.winfo_height() - 340) // 2
        dlg.geometry(f"+{max(10, rx)}+{max(10, ry)}")

        hdr = tk.Frame(dlg, bg=THEME["title_bar_bg"], height=26, padx=8, pady=3)
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text="Cadastro de Material - Estoque" if mode == "create" else f"Propriedades do Material: {material['id']}",
            bg=THEME["title_bar_bg"],
            fg=THEME["title_bar_fg"],
            font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        body = tk.Frame(dlg, bg=THEME["bg_card"], padx=16, pady=12)
        body.pack(fill="both", expand=True)

        # Valores padrão
        if mode == "edit" and material:
            c_val = str(material["id"])
            n_val = str(material.get("name", ""))
            t_val = str(material.get("type", "como placa"))
            w_val = f"{material.get('width_mm', 1380.0) / 1000.0:.2f}".replace(".", ",")
            l_val = f"{material.get('height_mm', 2980.0) / 1000.0:.2f}".replace(".", ",")
            lay_val = str(material.get("layers", 2))
            gap_val = str(material.get("gap_mm", 1.0))
        else:
            c_val = ""
            n_val = ""
            t_val = "como placa"
            w_val = "1,38"
            l_val = "2,98"
            lay_val = "2"
            gap_val = "1.0"

        fields = [
            ("Código:", c_val),
            ("Descrição:", n_val),
            ("Definição:", t_val),
            ("Largura (m):", w_val),
            ("Comprimento (m):", l_val),
            ("Camadas de corte:", lay_val),
            ("Gap / Espaçamento (mm):", gap_val),
        ]

        entries = {}
        for r_idx, (lbl, val) in enumerate(fields):
            tk.Label(body, text=lbl, bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").grid(row=r_idx, column=0, sticky="w", pady=3)
            if r_idx == 2:
                cb_def = ttk.Combobox(body, values=["como placa", "como rolo", "como retalho"], state="readonly", width=22)
                cb_def.set("como placa" if val in ("como pele", "leather", "sheet") else (val or "como placa"))
                cb_def.grid(row=r_idx, column=1, sticky="e", pady=3, padx=(10, 0))
                entries[r_idx] = cb_def
            else:
                ent = tk.Entry(body, font=("Segoe UI", 9), relief="sunken", bd=2, width=24)
                ent.insert(0, str(val))
                ent.grid(row=r_idx, column=1, sticky="e", pady=3, padx=(10, 0))
                if mode == "edit" and r_idx == 0:
                    ent.config(state="readonly")
                entries[r_idx] = ent

        entries[0 if mode == "create" else 1].focus_set()

        btn_box = tk.Frame(dlg, bg=THEME["bg_card"], pady=8)
        btn_box.pack(fill="x", padx=16)

        def save_action():
            code = entries[0].get().strip()
            name = entries[1].get().strip()
            tipo = entries[2].get().strip() or "como placa"
            try:
                w_m = float(entries[3].get().strip().replace(",", "."))
            except ValueError:
                w_m = 1.38
            try:
                l_m = float(entries[4].get().strip().replace(",", "."))
            except ValueError:
                l_m = 2.98
            try:
                layers = int(entries[5].get().strip())
            except ValueError:
                layers = 2
            try:
                gap = float(entries[6].get().strip().replace(",", "."))
            except ValueError:
                gap = 1.0

            if not code:
                messagebox.showwarning("Campo Obrigatório", "Informe o código do material.", parent=dlg)
                entries[0].focus_set()
                return

            if not name:
                name = f"Material {code}"

            w_mm = w_m * 1000.0
            h_mm = l_m * 1000.0
            area_m2 = round(w_m * l_m, 4)

            if mode == "create":
                self.db.create_material(
                    mat_id=code,
                    name=name,
                    type=tipo,
                    width_mm=w_mm,
                    height_mm=h_mm,
                    area_m2=area_m2,
                    thickness_mm=0.0,
                    layers=layers,
                    gap_mm=gap
                )
            else:
                self.db.update_material(
                    mat_id=code,
                    name=name,
                    type=tipo,
                    width_mm=w_mm,
                    height_mm=h_mm,
                    area_m2=area_m2,
                    layers=layers,
                    gap_mm=gap
                )

            dlg.destroy()
            self.refresh_table()
            if self.on_material_changed_cb:
                self.on_material_changed_cb()

        btn_save = tk.Button(btn_box, text="Salvar", bg=THEME["bg_surface"], activebackground=THEME["bg_hover"], relief="raised", bd=1, font=("Segoe UI", 9, "bold"), width=10, command=save_action)
        btn_save.pack(side="right", padx=4)

        btn_cancel = tk.Button(btn_box, text="Cancelar", bg=THEME["bg_surface"], activebackground=THEME["bg_hover"], relief="raised", bd=1, font=("Segoe UI", 9), width=10, command=dlg.destroy)
        btn_cancel.pack(side="right", padx=4)

        dlg.bind("<Return>", lambda e: save_action())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    # -------------------------------------------------------------
    # Controles de Janela MDI
    # -------------------------------------------------------------
    def _on_title_press(self, event):
        self.lift()
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._win_start_x = self.winfo_x()
        self._win_start_y = self.winfo_y()

    def _on_title_motion(self, event):
        if hasattr(self, "_drag_start_x"):
            dx = event.x_root - self._drag_start_x
            dy = event.y_root - self._drag_start_y
            if self.place_info():
                nx = max(0, self._win_start_x + dx)
                ny = max(0, self._win_start_y + dy)
                self.place_configure(x=nx, y=ny, relx=0, rely=0)

    def on_minimize_click(self):
        if hasattr(self, "on_minimize_cb") and self.on_minimize_cb:
            try:
                self.on_minimize_cb(self)
            except TypeError:
                self.on_minimize_cb()

    def on_maximize_click(self):
        if hasattr(self, "on_maximize_cb") and self.on_maximize_cb:
            try:
                self.on_maximize_cb(self)
            except TypeError:
                self.on_maximize_cb()

    def on_close_click(self):
        if hasattr(self, "on_close_cb") and self.on_close_cb:
            try:
                self.on_close_cb(self)
            except TypeError:
                try:
                    self.on_close_cb()
                except Exception:
                    pass
        self.pack_forget()
        self.place_forget()
