"""
JobManager 2000 (Python Edition)
Options Dialog - Reprodução 100% autêntica da janela 'Opções' (media_1792065478205.jpg a 211.jpg)
Abas: Geral | Moldes | Encaixe | Unidade de medida | Idioma
Conexões com o banco de dados SQLite e com as rotinas do sistema.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from config import THEME
from ui.dieproc_dialog import DieProcDialog

class OptionsDialog(tk.Toplevel):
    def __init__(self, parent, db, on_apply=None):
        super().__init__(parent)
        self.db = db
        self.on_apply_cb = on_apply
        self.title("Opções")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.configure(bg=THEME["bg_surface"])

        # Dimensões exatas proporcionais ao print do Windows XP
        dlg_w, dlg_h = 560, 430
        self.geometry(f"{dlg_w}x{dlg_h}")

        # Centraliza sobre o parent
        self.update_idletasks()
        rx = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
        ry = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
        self.geometry(f"+{max(10, rx)}+{max(10, ry)}")

        self._has_changes = False
        self.settings = self.db.get_all_settings()

        self.setup_ui()
        self.load_settings()

        self.bind("<Escape>", lambda e: self.on_cancel())

    def mark_changed(self, *args):
        self._has_changes = True
        if hasattr(self, "btn_apply"):
            self.btn_apply.config(state="normal")

    def setup_ui(self):
        # Container principal com padding
        main_box = tk.Frame(self, bg=THEME["bg_surface"], padx=8, pady=8)
        main_box.pack(fill="both", expand=True)

        # Configura estilo clássico do Notebook
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("WinClassic.TNotebook", background=THEME["bg_surface"], borderwidth=1)
        style.configure("WinClassic.TNotebook.Tab", background=THEME["bg_surface"], foreground=THEME["text_main"],
                        padding=[8, 3], font=("Segoe UI", 9))
        style.map("WinClassic.TNotebook.Tab",
                  background=[("selected", "#ffffff")],
                  foreground=[("selected", "#000000")])

        self.notebook = ttk.Notebook(main_box, style="WinClassic.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        # 5 Abas Oficiais
        self.tab_general = tk.Frame(self.notebook, bg=THEME["bg_surface"], padx=16, pady=14)
        self.tab_molds = tk.Frame(self.notebook, bg=THEME["bg_surface"], padx=14, pady=12)
        self.tab_nesting = tk.Frame(self.notebook, bg=THEME["bg_surface"], padx=20, pady=16)
        self.tab_units = tk.Frame(self.notebook, bg=THEME["bg_surface"], padx=12, pady=14)
        self.tab_language = tk.Frame(self.notebook, bg=THEME["bg_surface"], padx=20, pady=16)

        self.notebook.add(self.tab_general, text="Geral")
        self.notebook.add(self.tab_molds, text="Moldes")
        self.notebook.add(self.tab_nesting, text="Encaixe")
        self.notebook.add(self.tab_units, text="Unidade de medida")
        self.notebook.add(self.tab_language, text="Idioma")

        # Configuração do conteúdo de cada aba
        self._setup_tab_general()
        self._setup_tab_molds()
        self._setup_tab_nesting()
        self._setup_tab_units()
        self._setup_tab_language()

        # Barra inferior de botões (OK | Cancelar | Aplicar)
        btn_bar = tk.Frame(self, bg=THEME["bg_surface"], padx=12, pady=10)
        btn_bar.pack(fill="x", side="bottom")

        self.btn_apply = tk.Button(
            btn_bar, text="Aplicar", width=10, relief="raised", bd=1,
            bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9),
            state="disabled", command=self.on_apply
        )
        self.btn_apply.pack(side="right", padx=(4, 0))

        self.btn_cancel = tk.Button(
            btn_bar, text="Cancelar", width=10, relief="raised", bd=1,
            bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9),
            command=self.on_cancel
        )
        self.btn_cancel.pack(side="right", padx=4)

        self.btn_ok = tk.Button(
            btn_bar, text="OK", width=10, relief="raised", bd=2,
            bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9, "bold"),
            command=self.on_ok
        )
        self.btn_ok.pack(side="right", padx=4)

    # =========================================================================
    # ABA 1: Geral (media_1792065478205.jpg)
    # =========================================================================
    def _setup_tab_general(self):
        pane = self.tab_general

        # Painel esquerdo (Checkboxes)
        left_box = tk.Frame(pane, bg=THEME["bg_surface"])
        left_box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.var_ask_session_name = tk.BooleanVar(value=True)
        cb1 = tk.Checkbutton(
            left_box, text="Pergunta o nome da\nsessão ao criá-la",
            variable=self.var_ask_session_name, bg=THEME["bg_surface"], fg=THEME["text_main"],
            activebackground=THEME["bg_surface"], font=("Segoe UI", 9),
            justify="left", anchor="w", command=self.mark_changed
        )
        cb1.pack(anchor="w", pady=(0, 8))

        self.var_start_maximized = tk.BooleanVar(value=True)
        cb2 = tk.Checkbutton(
            left_box, text="Inicia maximizado",
            variable=self.var_start_maximized, bg=THEME["bg_surface"], fg=THEME["text_main"],
            activebackground=THEME["bg_surface"], font=("Segoe UI", 9),
            anchor="w", command=self.mark_changed
        )
        cb2.pack(anchor="w", pady=(0, 20))

        # Checkboxes recuados
        sub_left = tk.Frame(left_box, bg=THEME["bg_surface"], padx=20)
        sub_left.pack(anchor="w")

        self.var_allow_article_hiding = tk.BooleanVar(value=True)
        cb3 = tk.Checkbutton(
            sub_left, text="Allow article hiding",
            variable=self.var_allow_article_hiding, bg=THEME["bg_surface"], fg=THEME["text_main"],
            activebackground=THEME["bg_surface"], font=("Segoe UI", 9),
            anchor="w", command=self.mark_changed
        )
        cb3.pack(anchor="w", pady=2)

        self.var_show_hidden_articles = tk.BooleanVar(value=True)
        cb4 = tk.Checkbutton(
            sub_left, text="Show hidden articles",
            variable=self.var_show_hidden_articles, bg=THEME["bg_surface"], fg=THEME["text_main"],
            activebackground=THEME["bg_surface"], font=("Segoe UI", 9),
            anchor="w", command=self.mark_changed
        )
        cb4.pack(anchor="w", pady=2)

        # Painel direito (Materiais horizontais + Groupbox Xfer)
        right_box = tk.Frame(pane, bg=THEME["bg_surface"])
        right_box.pack(side="right", fill="both", expand=True)

        self.var_materials_horizontal = tk.BooleanVar(value=False)
        cb_mat = tk.Checkbutton(
            right_box, text="Materiais horizontais",
            variable=self.var_materials_horizontal, bg=THEME["bg_surface"], fg=THEME["text_main"],
            activebackground=THEME["bg_surface"], font=("Segoe UI", 9),
            anchor="w", command=self.mark_changed
        )
        cb_mat.pack(anchor="w", pady=(0, 10))

        # GroupBox Xfer clássico com borda rebaixada
        xfer_box = tk.LabelFrame(
            right_box, text="Xfer", bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), padx=10, pady=6, relief="groove", bd=1
        )
        xfer_box.pack(fill="x", pady=5)

        tk.Label(xfer_box, text="Login", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
        self.entry_xfer_login = tk.Entry(xfer_box, font=("Segoe UI", 9), relief="sunken", bd=2)
        self.entry_xfer_login.pack(fill="x", pady=(2, 6))
        self.entry_xfer_login.bind("<KeyRelease>", self.mark_changed)

        tk.Label(xfer_box, text="Password", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
        self.entry_xfer_pass = tk.Entry(xfer_box, font=("Segoe UI", 9), relief="sunken", bd=2, show="*")
        self.entry_xfer_pass.pack(fill="x", pady=(2, 6))
        self.entry_xfer_pass.bind("<KeyRelease>", self.mark_changed)

        tk.Label(xfer_box, text="Remote root folder", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
        self.entry_xfer_root = tk.Entry(xfer_box, font=("Segoe UI", 9), relief="sunken", bd=2)
        self.entry_xfer_root.pack(fill="x", pady=(2, 6))
        self.entry_xfer_root.bind("<KeyRelease>", self.mark_changed)

    # =========================================================================
    # ABA 2: Moldes (media_1792065478208.jpg)
    # =========================================================================
    def _setup_tab_molds(self):
        pane = self.tab_molds

        outer_box = tk.LabelFrame(
            pane, text="Contagem de moldes", bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), padx=12, pady=10, relief="groove", bd=1
        )
        outer_box.pack(fill="both", expand=True)

        self.var_mold_count_mode = tk.StringVar(value="pairs")

        # Opção 1: Contagem por pares
        r1_frame = tk.Frame(outer_box, bg=THEME["bg_surface"])
        r1_frame.pack(fill="x", pady=(0, 6))

        rb1 = tk.Radiobutton(
            r1_frame, text="Contagem por\npares", variable=self.var_mold_count_mode,
            value="pairs", bg=THEME["bg_surface"], fg=THEME["text_main"],
            activebackground=THEME["bg_surface"], font=("Segoe UI", 9),
            justify="left", anchor="w", width=14, command=self._on_mold_mode_toggle
        )
        rb1.pack(side="left", anchor="n")

        self.sub_box1 = tk.LabelFrame(
            r1_frame, text="Visualiza moldes a posicionar", bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), padx=8, pady=4, relief="groove", bd=1
        )
        self.sub_box1.pack(side="left", fill="x", expand=True, padx=(10, 0))

        self.var_mold_view_pairs = tk.StringVar(value="pairs")
        self.rb1_sub1 = tk.Radiobutton(
            self.sub_box1, text="Normais e\nespelhados", variable=self.var_mold_view_pairs,
            value="normal_mirrored", bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 8), justify="left", anchor="w", command=self.mark_changed
        )
        self.rb1_sub1.pack(side="left", padx=6)

        self.rb1_sub2 = tk.Radiobutton(
            self.sub_box1, text="Pares", variable=self.var_mold_view_pairs,
            value="pairs", bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), anchor="w", command=self.mark_changed
        )
        self.rb1_sub2.pack(side="left", padx=12)

        # Opção 2: Contagem como moldes individuais
        r2_frame = tk.Frame(outer_box, bg=THEME["bg_surface"])
        r2_frame.pack(fill="x", pady=(4, 10))

        rb2 = tk.Radiobutton(
            r2_frame, text="Contagem como\nmoldes individuais", variable=self.var_mold_count_mode,
            value="individual", bg=THEME["bg_surface"], fg=THEME["text_main"],
            activebackground=THEME["bg_surface"], font=("Segoe UI", 9),
            justify="left", anchor="w", width=14, command=self._on_mold_mode_toggle
        )
        rb2.pack(side="left", anchor="n")

        self.sub_box2 = tk.LabelFrame(
            r2_frame, text="Visualiza moldes a posicionar", bg=THEME["bg_surface"], fg="#808080",
            font=("Segoe UI", 9), padx=8, pady=4, relief="groove", bd=1
        )
        self.sub_box2.pack(side="left", fill="x", expand=True, padx=(10, 0))

        self.var_mold_view_ind = tk.StringVar(value="normal_mirrored")
        self.rb2_sub1 = tk.Radiobutton(
            self.sub_box2, text="Normais e\nespelhados", variable=self.var_mold_view_ind,
            value="normal_mirrored", bg=THEME["bg_surface"], fg="#808080",
            state="disabled", font=("Segoe UI", 8), justify="left", anchor="w", command=self.mark_changed
        )
        self.rb2_sub1.pack(side="left", padx=6)

        self.rb2_sub2 = tk.Radiobutton(
            self.sub_box2, text="Quantidades\nindividuais", variable=self.var_mold_view_ind,
            value="individual_qty", bg=THEME["bg_surface"], fg="#808080",
            state="disabled", font=("Segoe UI", 8), justify="left", anchor="w", command=self.mark_changed
        )
        self.rb2_sub2.pack(side="left", padx=10)

        # Rodapé: Botão de Ajuda clássico [?] e Tabela de cores
        footer_frame = tk.Frame(outer_box, bg=THEME["bg_surface"])
        footer_frame.pack(fill="x", pady=(6, 0))

        btn_q = tk.Button(
            footer_frame, text="?", relief="raised", bd=2, width=3, height=1,
            bg=THEME["bg_surface"], fg="#cc0000", font=("Segoe UI", 12, "bold"),
            command=lambda: messagebox.showinfo("Ajuda", "Modo de contagem por pares: organiza os pares espelhados conforme a ordem de produção.", parent=self)
        )
        btn_q.pack(side="left", padx=(10, 20), pady=4)

        # Tabela clássica Pares a fazer | Resto
        tbl_frame = tk.Frame(footer_frame, bg=THEME["bg_surface"], relief="sunken", bd=1)
        tbl_frame.pack(side="left", fill="x", expand=True)

        self.tree_molds = ttk.Treeview(tbl_frame, columns=("pares", "resto", "extra"), show="headings", height=2)
        self.tree_molds.heading("pares", text="Pares a fazer")
        self.tree_molds.heading("resto", text="Resto")
        self.tree_molds.heading("extra", text="")

        self.tree_molds.column("pares", width=95, anchor="center")
        self.tree_molds.column("resto", width=80, anchor="center")
        self.tree_molds.column("extra", width=120, anchor="center")

        self.tree_molds.tag_configure("green_row", background="#a6d8c0")
        self.tree_molds.tag_configure("yellow_row", background="#ffffbe")

        self.tree_molds.insert("", "end", values=("24", "0", ""), tags=("green_row",))
        self.tree_molds.insert("", "end", values=("12", "0", ""), tags=("yellow_row",))
        self.tree_molds.pack(fill="both", expand=True)

    def _on_mold_mode_toggle(self):
        self.mark_changed()
        mode = self.var_mold_count_mode.get()
        if mode == "pairs":
            self.sub_box1.config(fg=THEME["text_main"])
            self.rb1_sub1.config(state="normal", fg=THEME["text_main"])
            self.rb1_sub2.config(state="normal", fg=THEME["text_main"])

            self.sub_box2.config(fg="#808080")
            self.rb2_sub1.config(state="disabled", fg="#808080")
            self.rb2_sub2.config(state="disabled", fg="#808080")
        else:
            self.sub_box1.config(fg="#808080")
            self.rb1_sub1.config(state="disabled", fg="#808080")
            self.rb1_sub2.config(state="disabled", fg="#808080")

            self.sub_box2.config(fg=THEME["text_main"])
            self.rb2_sub1.config(state="normal", fg=THEME["text_main"])
            self.rb2_sub2.config(state="normal", fg=THEME["text_main"])

    # =========================================================================
    # ABA 3: Encaixe (media_1792065478209.jpg)
    # =========================================================================
    def _setup_tab_nesting(self):
        pane = self.tab_nesting

        grid_frame = tk.Frame(pane, bg=THEME["bg_surface"])
        grid_frame.pack(fill="both", expand=True, pady=4)

        # Linha 1: Estratégia padrão
        tk.Label(grid_frame, text="Estratégia padrão", bg=THEME["bg_surface"], fg=THEME["text_main"],
                 font=("Segoe UI", 9), anchor="w").grid(row=0, column=0, sticky="w", pady=6)
        self.cb_strategy = ttk.Combobox(grid_frame, values=["sint", "tape_a", "flashnestsheet", "std"], state="readonly", width=26)
        self.cb_strategy.set("sint")
        self.cb_strategy.grid(row=0, column=1, sticky="w", padx=(30, 0), pady=6)
        self.cb_strategy.bind("<<ComboboxSelected>>", self.mark_changed)

        # Linha 2: Parâmetros de encaixe padrão
        tk.Label(grid_frame, text="Parâmetros de encaixe padrão", bg=THEME["bg_surface"], fg=THEME["text_main"],
                 font=("Segoe UI", 9), anchor="w").grid(row=1, column=0, sticky="w", pady=6)
        self.cb_nest_params = ttk.Combobox(grid_frame, values=["Padrao", "stdNOTFill", "stdFill", "Personalizado"], state="readonly", width=26)
        self.cb_nest_params.set("Padrao")
        self.cb_nest_params.grid(row=1, column=1, sticky="w", padx=(30, 0), pady=6)
        self.cb_nest_params.bind("<<ComboboxSelected>>", self.mark_changed)

        # Linha 3: Postbuilder padrão
        tk.Label(grid_frame, text="Postbuilder padrão", bg=THEME["bg_surface"], fg=THEME["text_main"],
                 font=("Segoe UI", 9), anchor="w").grid(row=2, column=0, sticky="w", pady=6)
        self.cb_postbuilder = ttk.Combobox(grid_frame, values=["(nenhum)", "ATOM FlashCut Flex", "G-Code ISO"], state="readonly", width=26)
        self.cb_postbuilder.set("(nenhum)")
        self.cb_postbuilder.grid(row=2, column=1, sticky="w", padx=(30, 0), pady=6)
        self.cb_postbuilder.bind("<<ComboboxSelected>>", self.mark_changed)

        # Espaçador clássico
        tk.Frame(grid_frame, height=20, bg=THEME["bg_surface"]).grid(row=3, column=0, columnspan=2)

        # Linha 4: Parâmetros do molde padrão
        tk.Label(grid_frame, text="Parâmetros do molde padrão", bg=THEME["bg_surface"], fg=THEME["text_main"],
                 font=("Segoe UI", 9), anchor="w").grid(row=4, column=0, sticky="w", pady=6)
        self.cb_mold_params = ttk.Combobox(grid_frame, values=["(nenhum)", "Padrão 1", "Manual"], state="readonly", width=26)
        self.cb_mold_params.set("(nenhum)")
        self.cb_mold_params.grid(row=4, column=1, sticky="w", padx=(30, 0), pady=6)
        self.cb_mold_params.bind("<<ComboboxSelected>>", self.mark_changed)

        # Linha 5: Parâmetros do Die Proc padrão
        tk.Label(grid_frame, text="Parâmetros do Die Proc\npadrão", bg=THEME["bg_surface"], fg=THEME["text_main"],
                 font=("Segoe UI", 9), justify="left", anchor="w").grid(row=5, column=0, sticky="w", pady=6)
        dp_frame = tk.Frame(grid_frame, bg=THEME["bg_surface"])
        dp_frame.grid(row=5, column=1, sticky="w", padx=(30, 0), pady=6)

        self.cb_die_proc = ttk.Combobox(
            dp_frame,
            values=["ALTERNADO", "DIREITA", "ESQUERDA", "GAP 2", "Fixo", "Variável", "Automático"],
            state="readonly",
            width=16
        )
        self.cb_die_proc.set("ALTERNADO")
        self.cb_die_proc.pack(side="left")
        self.cb_die_proc.bind("<<ComboboxSelected>>", self.mark_changed)

        btn_dp_cfg = tk.Button(
            dp_frame, text="⚙️ Configurar...", bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 8), relief="raised", bd=1, cursor="hand2", padx=4,
            command=self._open_dieproc_config
        )
        btn_dp_cfg.pack(side="left", padx=(6, 0))

    def _open_dieproc_config(self):
        def _on_select(data):
            name = data.get("name", "ALTERNADO")
            vals = list(self.cb_die_proc["values"])
            if name not in vals:
                vals.insert(0, name)
                self.cb_die_proc["values"] = vals
            self.cb_die_proc.set(name)
            self.mark_changed()

        DieProcDialog(self, self.db, initial_preset=self.cb_die_proc.get(), on_select=_on_select)

    # =========================================================================
    # ABA 4: Unidade de medida (media_1792065478211.jpg)
    # =========================================================================
    def _setup_tab_units(self):
        pane = self.tab_units

        units_box = tk.Frame(pane, bg=THEME["bg_surface"])
        units_box.pack(fill="both", expand=True, pady=10)

        length_units = ["metre (m)", "millimetre (mm)", "centimetre (cm)", "inch (in)"]
        area_units = ["metre (m)", "square metre (m²)", "sq dm", "sq ft"]

        # 1. Shapes
        box_shapes = tk.LabelFrame(units_box, text="Shapes", bg=THEME["bg_surface"], fg=THEME["text_main"],
                                   font=("Segoe UI", 9), padx=8, pady=8, relief="groove", bd=1)
        box_shapes.pack(side="left", fill="both", expand=True, padx=4)

        tk.Label(box_shapes, text="Lengths", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
        self.cb_u_shapes_len = ttk.Combobox(box_shapes, values=length_units, state="readonly", width=14)
        self.cb_u_shapes_len.set("metre (m)")
        self.cb_u_shapes_len.pack(fill="x", pady=(2, 10))
        self.cb_u_shapes_len.bind("<<ComboboxSelected>>", self.mark_changed)

        tk.Label(box_shapes, text="Areas", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
        self.cb_u_shapes_area = ttk.Combobox(box_shapes, values=area_units, state="readonly", width=14)
        self.cb_u_shapes_area.set("metre (m)")
        self.cb_u_shapes_area.pack(fill="x", pady=(2, 4))
        self.cb_u_shapes_area.bind("<<ComboboxSelected>>", self.mark_changed)

        # 2. Materials
        box_mats = tk.LabelFrame(units_box, text="Materials", bg=THEME["bg_surface"], fg=THEME["text_main"],
                                  font=("Segoe UI", 9), padx=8, pady=8, relief="groove", bd=1)
        box_mats.pack(side="left", fill="both", expand=True, padx=4)

        tk.Label(box_mats, text="Lengths", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
        self.cb_u_mats_len = ttk.Combobox(box_mats, values=length_units, state="readonly", width=14)
        self.cb_u_mats_len.set("metre (m)")
        self.cb_u_mats_len.pack(fill="x", pady=(2, 10))
        self.cb_u_mats_len.bind("<<ComboboxSelected>>", self.mark_changed)

        tk.Label(box_mats, text="Areas", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
        self.cb_u_mats_area = ttk.Combobox(box_mats, values=area_units, state="readonly", width=14)
        self.cb_u_mats_area.set("metre (m)")
        self.cb_u_mats_area.pack(fill="x", pady=(2, 4))
        self.cb_u_mats_area.bind("<<ComboboxSelected>>", self.mark_changed)

        # 3. Layouts
        box_lays = tk.LabelFrame(units_box, text="Layouts", bg=THEME["bg_surface"], fg=THEME["text_main"],
                                 font=("Segoe UI", 9), padx=8, pady=8, relief="groove", bd=1)
        box_lays.pack(side="left", fill="both", expand=True, padx=4)

        tk.Label(box_lays, text="Lengths", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
        self.cb_u_lays_len = ttk.Combobox(box_lays, values=length_units, state="readonly", width=14)
        self.cb_u_lays_len.set("metre (m)")
        self.cb_u_lays_len.pack(fill="x", pady=(2, 10))
        self.cb_u_lays_len.bind("<<ComboboxSelected>>", self.mark_changed)

        tk.Label(box_lays, text="Areas", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
        self.cb_u_lays_area = ttk.Combobox(box_lays, values=area_units, state="readonly", width=14)
        self.cb_u_lays_area.set("metre (m)")
        self.cb_u_lays_area.pack(fill="x", pady=(2, 4))
        self.cb_u_lays_area.bind("<<ComboboxSelected>>", self.mark_changed)

    # =========================================================================
    # ABA 5: Idioma
    # =========================================================================
    def _setup_tab_language(self):
        pane = self.tab_language

        lang_box = tk.LabelFrame(
            pane, text="Idioma do Sistema", bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), padx=14, pady=12, relief="groove", bd=1
        )
        lang_box.pack(fill="both", expand=True)

        self.var_language = tk.StringVar(value="Português (Brasil)")
        langs = [
            ("Português (Brasil)", "Português (Brasil)"),
            ("English (United States)", "English"),
            ("Italiano (Italia)", "Italiano"),
            ("Español (España)", "Español")
        ]
        for text, val in langs:
            rb = tk.Radiobutton(
                lang_box, text=text, variable=self.var_language, value=val,
                bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["bg_surface"],
                font=("Segoe UI", 9), anchor="w", command=self.mark_changed
            )
            rb.pack(anchor="w", pady=4)

    # =========================================================================
    # Carga e Persistência de Dados
    # =========================================================================
    def load_settings(self):
        st = self.settings
        self.var_ask_session_name.set(st.get("ask_session_name", "1") == "1")
        self.var_start_maximized.set(st.get("start_maximized", "1") == "1")
        self.var_allow_article_hiding.set(st.get("allow_article_hiding", "1") == "1")
        self.var_show_hidden_articles.set(st.get("show_hidden_articles", "1") == "1")
        self.var_materials_horizontal.set(st.get("materials_horizontal", "0") == "1")

        self.entry_xfer_login.delete(0, "end")
        self.entry_xfer_login.insert(0, st.get("xfer_login", ""))

        self.entry_xfer_pass.delete(0, "end")
        self.entry_xfer_pass.insert(0, st.get("xfer_password", ""))

        self.entry_xfer_root.delete(0, "end")
        self.entry_xfer_root.insert(0, st.get("xfer_remote_root", ""))

        self.var_mold_count_mode.set(st.get("mold_count_mode", "pairs"))
        self.var_mold_view_pairs.set(st.get("mold_view_mode", "pairs"))
        self._on_mold_mode_toggle()

        strat = st.get("default_strategy", "flashnestsheet")
        if strat == "flashnestroll":
            strat = "flashnestsheet"
        self.cb_strategy.set(strat)
        self.cb_nest_params.set(st.get("default_nesting_params", "Padrao"))
        self.cb_postbuilder.set(st.get("default_postbuilder", "(nenhum)"))
        self.cb_mold_params.set(st.get("default_mold_params", "(nenhum)"))
        self.cb_die_proc.set(st.get("default_die_proc_params", "Fixo"))

        self.cb_u_shapes_len.set(st.get("unit_shapes_length", "metre (m)"))
        self.cb_u_shapes_area.set(st.get("unit_shapes_area", "metre (m)"))
        self.cb_u_mats_len.set(st.get("unit_materials_length", "metre (m)"))
        self.cb_u_mats_area.set(st.get("unit_materials_area", "metre (m)"))
        self.cb_u_lays_len.set(st.get("unit_layouts_length", "metre (m)"))
        self.cb_u_lays_area.set(st.get("unit_layouts_area", "metre (m)"))

        self.var_language.set(st.get("language", "Português (Brasil)"))

        self._has_changes = False
        self.btn_apply.config(state="disabled")

    def gather_settings(self):
        return {
            "ask_session_name": "1" if self.var_ask_session_name.get() else "0",
            "start_maximized": "1" if self.var_start_maximized.get() else "0",
            "allow_article_hiding": "1" if self.var_allow_article_hiding.get() else "0",
            "show_hidden_articles": "1" if self.var_show_hidden_articles.get() else "0",
            "materials_horizontal": "1" if self.var_materials_horizontal.get() else "0",
            "xfer_login": self.entry_xfer_login.get().strip(),
            "xfer_password": self.entry_xfer_pass.get().strip(),
            "xfer_remote_root": self.entry_xfer_root.get().strip(),
            "mold_count_mode": self.var_mold_count_mode.get(),
            "mold_view_mode": self.var_mold_view_pairs.get() if self.var_mold_count_mode.get() == "pairs" else self.var_mold_view_ind.get(),
            "default_strategy": self.cb_strategy.get(),
            "default_nesting_params": self.cb_nest_params.get(),
            "default_postbuilder": self.cb_postbuilder.get(),
            "default_mold_params": self.cb_mold_params.get(),
            "default_die_proc_params": self.cb_die_proc.get(),
            "unit_shapes_length": self.cb_u_shapes_len.get(),
            "unit_shapes_area": self.cb_u_shapes_area.get(),
            "unit_materials_length": self.cb_u_mats_len.get(),
            "unit_materials_area": self.cb_u_mats_area.get(),
            "unit_layouts_length": self.cb_u_lays_len.get(),
            "unit_layouts_area": self.cb_u_lays_area.get(),
            "language": self.var_language.get()
        }

    def on_apply(self):
        data = self.gather_settings()
        self.db.save_settings(data)
        self.settings = data
        self._has_changes = False
        self.btn_apply.config(state="disabled")
        if self.on_apply_cb:
            self.on_apply_cb(data)

    def on_ok(self):
        data = self.gather_settings()
        self.db.save_settings(data)
        self.settings = data
        if self.on_apply_cb:
            self.on_apply_cb(data)
        self.destroy()

    def on_cancel(self):
        self.destroy()
