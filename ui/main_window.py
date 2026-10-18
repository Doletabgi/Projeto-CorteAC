"""
JobManager 2000 (Edição Python para Windows 10 / 11)
Main Window - Cópia 100% fiel das telas do Job Manager original (Windows XP)
"""

import os
import sys
import time
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import datetime
from pathlib import Path


import copy
from config import THEME, APP_NAME, APP_VERSION, ATOM_MACHINE, EXPORTS_DIR
from database import DatabaseManager
from cad.nesting_engine import auto_nest_pieces, calculate_yield, calculate_atom_cutting_time
from cad.colors import get_color_for_size
from cad.exporter import export_gcode, export_xml_report
from cad.die_parser import parse_die_file, save_die_file
from cad.geometry import polygon_area
from ui.cad_canvas import CADCanvas
from ui.order_view import OrderView
from ui.session_view import SessionView
from ui.shape_editor_view import ShapeEditorView
from ui.layout_editor_view import LayoutEditorView
from ui.material_codes_view import MaterialCodesView
from ui.options_dialog import OptionsDialog
from ui.params_dialog import NestingParamsDialog
from ui.dieproc_dialog import DieProcDialog
from ui.sort_utils import natural_sort_key, size_sort_key, clean_session_display_name

def get_assets_dir():
    if getattr(sys, 'frozen', False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent.parent
    return base / "assets"

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        # Título da janela exatamente no formato original
        self.title("teste dola - C:\\NSDATA\\")
        self.geometry("1180x720")
        self.minsize(980, 600)
        self.configure(bg=THEME["bg_main"])

        # Inicia a janela principal maximizada ocupando a tela cheia do monitor
        try:
            self.attributes("-zoomed", True)
        except Exception:
            try:
                self.state("zoomed")
            except Exception:
                pass

        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)
        self.bind("<Control-s>", self.handle_ctrl_s)
        self.bind("<Control-S>", self.handle_ctrl_s)
        self.bind("<Control-p>", self.handle_ctrl_p)
        self.bind("<Control-P>", self.handle_ctrl_p)

        # Carrega Ícones Nativos Extraídos do Sistema Original
        self.load_icons()

        # Banco de Dados SQLite
        self.db = DatabaseManager()
        self.materials = self.db.get_materials()
        self.current_material = self.materials[0] if self.materials else None
        if self.current_material:
            if self.current_material.get("width_mm") == 1200 and self.current_material.get("height_mm") == 800:
                self.current_material["width_mm"] = 1380.0
                self.current_material["height_mm"] = 1080.0
                self.current_material["type"] = "como placa"
                self.current_material["code"] = "853412"
                self.current_material["layers"] = 2
                self.current_material["gap_mm"] = 1.0
                self.db.update_material(self.current_material["id"], width_mm=1380.0, height_mm=1080.0, type="como placa")
            self.current_material.setdefault("width_mm", 1380.0)
            self.current_material.setdefault("height_mm", 1080.0)
            self.current_material.setdefault("layers", 2)
            self.current_material.setdefault("gap_mm", 1.0)
            self.current_material.setdefault("code", "853412")
            self.current_material.setdefault("type", "como placa")
        self.current_shapes = []
        self.sessions = []
        self.current_session = None
        self.orders = []
        self.current_order = None

        # Estado da Janela MDI Ativa e MDI Manager
        self.active_child = None
        self.current_mode = "jobs"
        self.open_sessions = {}
        self.open_windows = []
        self.minimized_windows = {}
        self.app_settings = self.db.get_all_settings()
        self._window_layout_mode = "maximized" if self.app_settings.get("start_maximized", "1") == "1" else "windowed"
        self.bind_all("<F5>", lambda e: self.on_refresh_f5())

        # Estilos TTK
        self.setup_styles()

        # Montagem dos Componentes idênticos aos prints do Windows XP
        self.create_menu_bar()
        self.create_toolbar()
        self.create_main_split_layout()
        self.create_status_bar()

        # Carrega Dados Iniciais
        self.load_initial_data()

    def load_icons(self):
        assets_dir = get_assets_dir()
        self.icons = {}
        icon_files = {
            "cut": "tlbCut.gif",
            "copy": "tlbCopy.gif",
            "paste": "tlbPaste.gif",
            "details": "tlbDetails.gif",
            "btn_prod": "btn_prod.png",
            "btn_moldes": "btn_moldes.png",
            "btn_mat": "btn_mat.png",
            "node_base": "iconJobNodeBase.gif",
            "job_folder": "iconJobJobFolder.gif",
            "job_order": "iconJobOrder.gif",
            "job_session": "iconJobSession.gif",
            "shp_base": "iconShpShpBase.gif",
            "shp_article": "iconShpArticle.gif",
            "shed": "iconShed.gif",
            "mat_base": "iconMatBase.gif",
            "app_icon": "app_icon.png",
            "layout_icon": "layout/layout_icon.png"
        }
        for k, v in icon_files.items():
            p = assets_dir / v
            if p.exists():
                try:
                    self.icons[k] = tk.PhotoImage(file=str(p))
                except Exception:
                    self.icons[k] = None
            else:
                self.icons[k] = None

        app_icon_photos = []
        for sz_file in ["app_icon_16.png", "app_icon_32.png", "app_icon_48.png", "app_icon_64.png", "app_icon.png"]:
            p = assets_dir / sz_file
            if p.exists():
                try:
                    img_photo = tk.PhotoImage(file=str(p))
                    app_icon_photos.append(img_photo)
                    self.icons[sz_file] = img_photo
                except Exception:
                    pass

        if app_icon_photos:
            self.iconphoto(True, *app_icon_photos)
        elif self.icons.get("app_icon"):
            self.iconphoto(True, self.icons["app_icon"])

        ico_p = assets_dir / "app_icon.ico"
        if ico_p.exists():
            try:
                self.iconbitmap(default=str(ico_p))
            except Exception:
                pass

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Treeview Classic WinXP (Fundo branco puro, cabeçalho #ece9d8 com relevo 3D)
        style.configure(
            "Treeview",
            background=THEME["bg_input"],
            foreground=THEME["text_main"],
            fieldbackground=THEME["bg_input"],
            rowheight=20,
            borderwidth=1,
            relief="sunken",
            font=("Segoe UI", 9)
        )
        style.map(
            "Treeview",
            background=[("selected", THEME["select_bg"])],
            foreground=[("selected", THEME["select_fg"])]
        )
        style.configure(
            "Treeview.Heading",
            background=THEME["bg_main"],
            foreground=THEME["text_main"],
            relief="raised",
            borderwidth=1,
            font=("Segoe UI", 8, "bold")
        )
        style.map(
            "Treeview.Heading",
            background=[("active", THEME["bg_hover"])]
        )

        # Notebook tabs Classic WinXP
        style.configure("TNotebook", background=THEME["bg_surface"], borderwidth=1)
        style.configure(
            "TNotebook.Tab",
            background=THEME["bg_card"],
            foreground=THEME["text_main"],
            padding=[8, 3],
            relief="raised",
            font=("Segoe UI", 9)
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", THEME["bg_surface"])],
            foreground=[("selected", THEME["text_main"])]
        )

    # =========================================================================
    # 1. Menu Bar (Arquivo, Editar, Exibir, Ferramentas, Janela, Ajuda)
    # =========================================================================
    def create_menu_bar(self):
        menubar = tk.Menu(self, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])

        # Arquivo
        file_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
        file_menu.add_command(label="Nova Sessão...", command=self.on_new_session)
        file_menu.add_command(label="Abrir Ordem...", command=self.show_order_window)
        file_menu.add_command(label="🧩 Abrir Layout Editor...", command=self.show_layout_editor)
        file_menu.add_separator()
        file_menu.add_command(label="📁 Criar Produção...", command=self.on_create_production)
        file_menu.add_command(label="📁 Criar Subpasta de Produção...", command=self.on_create_job_subfolder_menu_action)
        file_menu.add_command(label="📁 Criar Pasta de Moldes...", command=self.on_create_shape_folder)
        file_menu.add_command(label="📁 Criar Subpasta de Moldes...", command=self.on_create_subfolder_menu_action)
        file_menu.add_command(label="📂 Importar Molde (.die)...", command=self.on_import_die)
        file_menu.add_command(label="📂 Abrir Layout (.lay)...", command=self.on_open_lay_file)
        file_menu.add_command(label="💾 Exportar Layout (.lay)...", command=self.on_export_lay_file)
        file_menu.add_command(label="Exportar G-Code (ATOM)...", command=self.on_export_gcode)
        file_menu.add_command(label="Exportar Relatório XML...", command=self.on_export_xml)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.quit)
        menubar.add_cascade(label="Arquivo", menu=file_menu)

        # Editar
        edit_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
        edit_menu.add_command(label="Desfazer / Reverter", accelerator="Ctrl+Z", command=self.on_global_undo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Recortar", accelerator="Ctrl+X")
        edit_menu.add_command(label="Copiar", accelerator="Ctrl+C")
        edit_menu.add_command(label="Colar", accelerator="Ctrl+V")
        edit_menu.add_command(label="Excluir", accelerator="Del", command=self.on_global_delete_key)
        edit_menu.add_separator()
        edit_menu.add_command(label="Selecionar tudo", accelerator="Ctrl+A", command=self.on_select_all)
        self.edit_menu = edit_menu
        menubar.add_cascade(label="Editar", menu=edit_menu)

        # Exibir
        view_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
        view_menu.add_command(label="Produção", command=lambda: self.switch_tree_mode("jobs"))
        view_menu.add_command(label="Moldes", command=lambda: self.switch_tree_mode("shapes"))
        view_menu.add_command(label="Estoque de material", command=lambda: self.switch_tree_mode("materials"))
        view_menu.add_separator()
        view_menu.add_command(label="Códigos materiais...", command=self.show_material_codes_window)
        menubar.add_cascade(label="Exibir", menu=view_menu)

        # Ferramentas (conforme media_1792065456571.jpg)
        self.tools_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
        tools_menu = self.tools_menu
        tools_menu.add_command(label="Atualizar", accelerator="F5", command=self.on_refresh_f5)
        tools_menu.add_command(label="Opções", command=self.show_options_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="🧩 Layout Editor (Nesting)...", command=self.show_layout_editor)
        tools_menu.add_command(label="Shape Editor (Editor de Moldes)...", command=self.show_shape_editor)
        tools_menu.add_command(label="📋 Códigos materiais (Listagem)...", command=self.show_material_codes_window)
        tools_menu.add_command(label="📁 Criar Produção...", command=self.on_create_production)
        tools_menu.add_command(label="📁 Criar Subpasta de Produção...", command=self.on_create_job_subfolder_menu_action)
        tools_menu.add_command(label="📁 Criar Pasta de Moldes...", command=self.on_create_shape_folder)
        tools_menu.add_command(label="📁 Criar Subpasta de Moldes...", command=self.on_create_subfolder_menu_action)
        tools_menu.add_command(label="📂 Importar Shape (.die)...", command=self.on_import_die)
        tools_menu.add_separator()
        tools_menu.add_command(label="Parâmetros de Nesting...", command=self.open_params_dialog)
        tools_menu.add_command(label="⚙️ Configuração DieProc (Encaixe Sintético)...", command=self.open_dieproc_dialog)
        tools_menu.add_command(label="Executar Auto-Nest...", command=self.on_auto_nest)
        tools_menu.add_command(label="Simular Corte na Mesa...", command=self.on_toggle_sim)
        menubar.add_cascade(label="Ferramentas", menu=tools_menu)

        # Janela
        win_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
        win_menu.add_command(label="Layout Editor", command=self.show_layout_editor)
        win_menu.add_command(label="Shape Editor", command=self.show_shape_editor)
        win_menu.add_command(label="Códigos materiais", command=self.show_material_codes_window)
        win_menu.add_command(label="Detalhes da Sessão", command=self.show_session_window)
        win_menu.add_separator()
        win_menu.add_command(label="Em cascata", command=self.cascade_windows)
        win_menu.add_command(label="Lado a lado horizontal", command=self.tile_horizontal)
        win_menu.add_command(label="Lado a lado vertical", command=self.tile_vertical)
        win_menu.add_separator()
        win_menu.add_command(label="Maximizar", command=lambda: self.maximize_window(self.active_child) if self.active_child else None)
        win_menu.add_command(label="Minimizar janela ativa", command=lambda: self.minimize_window(self.active_child) if self.active_child else None)
        win_menu.add_separator()
        win_menu.add_command(label="Fechar janela ativa", command=self.close_child_window)
        menubar.add_cascade(label="Janela", menu=win_menu)

        # Ajuda
        help_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
        help_menu.add_command(label="Manual do Job Manager", command=lambda: messagebox.showinfo("Ajuda", "Manual em HTML disponível na pasta antigo/Help/JM2K"))
        help_menu.add_command(label="Sobre teste dola", command=lambda: messagebox.showinfo("Sobre", f"{APP_NAME} - {APP_VERSION}\nRecriação moderna em Python para Windows 10 / 11"))
        menubar.add_cascade(label="Ajuda", menu=help_menu)

        self.config(menu=menubar)

    # =========================================================================
    # 2. Toolbar Superior (como no print clássico do Windows XP)
    # =========================================================================
    def create_toolbar(self):
        tbar = tk.Frame(self, bg=THEME["bg_surface"], height=32, padx=4, pady=2, relief="raised", borderwidth=1)
        tbar.pack(side="top", fill="x")

        # Botões padrão: Recortar, Copiar, Colar, Detalhes com ícones autênticos
        btn_cut_kw = {"image": self.icons["cut"]} if self.icons.get("cut") else {"text": "✂️"}
        tk.Button(tbar, **btn_cut_kw, bg=THEME["bg_surface"], relief="raised", bd=1, width=22, height=22).pack(side="left", padx=1)

        btn_copy_kw = {"image": self.icons["copy"]} if self.icons.get("copy") else {"text": "📄"}
        tk.Button(tbar, **btn_copy_kw, bg=THEME["bg_surface"], relief="raised", bd=1, width=22, height=22).pack(side="left", padx=1)

        btn_paste_kw = {"image": self.icons["paste"]} if self.icons.get("paste") else {"text": "📋"}
        tk.Button(tbar, **btn_paste_kw, bg=THEME["bg_surface"], relief="raised", bd=1, width=22, height=22).pack(side="left", padx=1)

        # Divisor
        tk.Frame(tbar, bg=THEME["border"], width=1, height=20, relief="sunken", bd=1).pack(side="left", padx=4)

        btn_details_kw = {"image": self.icons["details"]} if self.icons.get("details") else {"text": "📑"}
        tk.Button(tbar, **btn_details_kw, bg=THEME["bg_surface"], relief="raised", bd=1, width=22, height=22, command=self.show_session_window).pack(side="left", padx=1)

        btn_lay_kw = {"image": self.icons["layout_icon"]} if self.icons.get("layout_icon") else {"text": "🧩"}
        tk.Button(tbar, **btn_lay_kw, bg=THEME["bg_surface"], relief="raised", bd=1, width=22, height=22, command=self.show_layout_editor).pack(side="left", padx=1)

        btn_shed_kw = {"image": self.icons["shed"]} if self.icons.get("shed") else {"text": "📐"}
        tk.Button(tbar, **btn_shed_kw, bg=THEME["bg_surface"], relief="raised", bd=1, width=22, height=22, command=self.show_shape_editor).pack(side="left", padx=1)

        tk.Button(
            tbar, text="📂 Importar .die", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=1, padx=4, font=("Segoe UI", 8), command=self.on_import_die
        ).pack(side="left", padx=2)

        # Divisor
        tk.Frame(tbar, bg=THEME["border"], width=1, height=20, relief="sunken", bd=1).pack(side="left", padx=6)

        # Ações diretas úteis
        tk.Button(
            tbar, text="⚙️ Parâmetros", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, padx=6, font=("Segoe UI", 8), command=self.open_params_dialog
        ).pack(side="left", padx=2)

        tk.Button(
            tbar, text="⚡ Auto-Nest", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, padx=8, font=("Segoe UI", 8, "bold"), command=self.on_auto_nest
        ).pack(side="left", padx=2)

        self.btn_sim = tk.Button(
            tbar, text="▶ Simular", bg=THEME["bg_surface"], fg="#800000",
            relief="raised", bd=2, padx=8, font=("Segoe UI", 8, "bold"), command=self.on_toggle_sim
        )
        self.btn_sim.pack(side="left", padx=2)

        tk.Button(
            tbar, text="💾 Exportar G-Code", bg=THEME["bg_surface"], fg="#000080",
            relief="raised", bd=2, padx=8, font=("Segoe UI", 8), command=self.on_export_gcode
        ).pack(side="left", padx=2)

    # =========================================================================
    # 3. Main Split Layout: Esquerda (Árvore + Grid) | Direita (Área MDI Cinza)
    # =========================================================================
    def create_main_split_layout(self):
        paned = tk.PanedWindow(self, orient="horizontal", bg=THEME["bg_main"], sashwidth=4, sashrelief="raised")
        paned.pack(fill="both", expand=True)

        # -------------------------------------------------------------
        # PAINEL ESQUERDO: Barra de 3 Botões de Modo + Árvore + Grid
        # -------------------------------------------------------------
        left_box = tk.Frame(paned, bg=THEME["bg_surface"], width=210, relief="sunken", bd=1)
        paned.add(left_box, width=210, minsize=180)

        # Barra de seleção de modo com os 3 botões quadrados idênticos aos prints
        mode_bar = tk.Frame(left_box, bg=THEME["bg_surface"], height=32, padx=2, pady=2)
        mode_bar.pack(fill="x")

        btn_jobs_kw = {"image": self.icons["btn_prod"]} if self.icons.get("btn_prod") else {"text": "🖥️"}
        self.btn_mode_jobs = tk.Button(
            mode_bar, **btn_jobs_kw, bg=THEME["bg_surface"],
            relief="sunken", bd=2, width=26, height=24, padx=0, pady=0,
            command=lambda: self.switch_tree_mode("jobs")
        )
        self.btn_mode_jobs.pack(side="left", padx=1)

        btn_shp_kw = {"image": self.icons["btn_moldes"]} if self.icons.get("btn_moldes") else {"text": "🟩"}
        self.btn_mode_shapes = tk.Button(
            mode_bar, **btn_shp_kw, bg=THEME["bg_surface"],
            relief="raised", bd=2, width=26, height=24, padx=0, pady=0,
            command=lambda: self.switch_tree_mode("shapes")
        )
        self.btn_mode_shapes.pack(side="left", padx=1)

        btn_mat_kw = {"image": self.icons["btn_mat"]} if self.icons.get("btn_mat") else {"text": "📚"}
        self.btn_mode_materials = tk.Button(
            mode_bar, **btn_mat_kw, bg=THEME["bg_surface"],
            relief="raised", bd=2, width=26, height=24, padx=0, pady=0,
            command=lambda: self.switch_tree_mode("materials")
        )
        self.btn_mode_materials.pack(side="left", padx=1)
        self.btn_mode_materials.bind("<Button-3>", self.show_materials_button_menu)

        # Divisão vertical esquerda: Árvore no topo e Grid embaixo
        v_paned = tk.PanedWindow(left_box, orient="vertical", bg=THEME["bg_surface"], sashwidth=4, sashrelief="raised")
        v_paned.pack(fill="both", expand=True)

        # Árvore Superior (Tree View) com moldura rebaixada
        tree_frame = tk.Frame(v_paned, bg=THEME["bg_surface"], relief="sunken", bd=2)
        v_paned.add(tree_frame, minsize=170)

        self.tree_main = ttk.Treeview(tree_frame, show="tree", selectmode="extended")
        self.tree_main.pack(fill="both", expand=True)
        self.tree_main.bind("<<TreeviewSelect>>", self.on_tree_selected)
        self.tree_main.bind("<Double-1>", self.on_tree_double_click)
        self.tree_main.bind("<Button-3>", self.show_tree_context_menu)
        self.tree_main.bind("<ButtonPress-1>", self.on_tree_drag_start, add="+")
        self.tree_main.bind("<B1-Motion>", self.on_tree_drag_motion, add="+")
        self.tree_main.bind("<ButtonRelease-1>", self.on_tree_drag_end, add="+")

        # Menu de contexto clássico (botão direito na árvore) idêntico ao print media_1791842155312.png
        self.tree_menu = tk.Menu(self, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
        self.tree_menu.add_command(label="Abrir", state="disabled", command=self.on_tree_menu_open)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Criar sessão", command=self.on_new_session)
        self.tree_menu.add_command(label="Criar pedido", command=self.on_create_order)
        self.tree_menu.add_command(label="Criar Produção", command=self.on_create_production)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Explodir", state="disabled")
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Renomear", command=self.on_rename_tree_item)
        self.tree_menu.add_command(label="Excluir", command=self.on_delete_tree_item)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Publish", command=self.on_publish)
        self.tree_menu.add_command(label="Export as xml...", command=self.on_export_xml)
        self.tree_menu.add_command(label="Import xml here...", command=self.on_import_xml)
        self.tree_menu.add_command(label="Importar Shape (.die)...", command=self.on_import_die)
        self.tree_menu.add_command(label="🧩 Abrir no Layout Editor...", command=self.show_layout_editor)

        # Menu de contexto específico para o Modo 2 (Moldes)
        self.moldes_menu = tk.Menu(self, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])

        # Menu de contexto específico para o Modo 3 (Estoque de material): Listagem de materiais e Criar material
        self.materials_menu = tk.Menu(
            self, tearoff=0,
            bg=THEME["bg_surface"], fg=THEME["text_main"],
            activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"],
            font=("Segoe UI", 9)
        )
        self.materials_menu.add_command(label="Listagem de materiais...", command=self.show_material_codes_window)
        self.materials_menu.add_command(label="Criar material...", command=self.on_create_material)

        # Grid Inferior com moldura rebaixada
        grid_frame = tk.Frame(v_paned, bg=THEME["bg_surface"], relief="sunken", bd=2)
        v_paned.add(grid_frame, minsize=130)

        self.grid_lower = ttk.Treeview(grid_frame, show="headings", height=5, selectmode="extended")
        self.grid_lower.pack(fill="both", expand=True)
        self.grid_lower.bind("<Double-1>", self.on_grid_double_click)
        self.grid_lower.bind("<Button-3>", self.show_grid_context_menu)
        self.grid_lower.bind("<ButtonPress-1>", self.on_grid_drag_start, add="+")
        self.grid_lower.bind("<B1-Motion>", self.on_tree_drag_motion, add="+")
        self.grid_lower.bind("<ButtonRelease-1>", self.on_tree_drag_end, add="+")

        # -------------------------------------------------------------
        # PAINEL DIREITO: Área de Trabalho MDI Cinza (#808080)
        # Começa limpa exatamente como nos 3 prints do Windows XP!
        # -------------------------------------------------------------
        self.right_box = tk.Frame(paned, bg=THEME["bg_workspace"])
        paned.add(self.right_box, minsize=450)

        # Área de trabalho MDI principal para janelas filhas
        self.mdi_workspace = tk.Frame(self.right_box, bg=THEME["bg_workspace"])
        self.mdi_workspace.pack(fill="both", expand=True)

        # Barra inferior de janelas minimizadas MDI (Dock clássico Windows XP)
        self.mdi_dock = tk.Frame(self.right_box, bg="#404040", height=28, relief="sunken", bd=1)

        # Criação das views filhas MDI únicas
        self.order_view = OrderView(
            self.mdi_workspace,
            on_close=lambda *args: self.close_window(self.order_view),
            on_minimize=lambda *args: self.minimize_window(self.order_view),
            on_maximize=lambda *args: self.toggle_maximize_window(self.order_view)
        )
        self.shape_editor_view = ShapeEditorView(
            self.mdi_workspace,
            on_close=lambda *args: self.close_window(self.shape_editor_view),
            on_minimize=lambda *args: self.minimize_window(self.shape_editor_view),
            on_maximize=lambda *args: self.toggle_maximize_window(self.shape_editor_view),
            on_save=self.on_shape_saved,
            on_import_die=self.on_import_die
        )
        self.layout_editor_view = LayoutEditorView(
            self,
            on_close=lambda *args: self.close_window(self.layout_editor_view),
            on_minimize=lambda *args: self.minimize_window(self.layout_editor_view),
            on_maximize=lambda *args: self.toggle_maximize_window(self.layout_editor_view),
            on_save=self.on_layout_editor_save,
            db=self.db
        )
        self.material_codes_view = MaterialCodesView(
            self.mdi_workspace,
            self.db,
            on_close=lambda *args: self.close_window(self.material_codes_view),
            on_minimize=lambda *args: self.minimize_window(self.material_codes_view),
            on_maximize=lambda *args: self.toggle_maximize_window(self.material_codes_view),
            on_material_changed=self.refresh_materials_everywhere
        )
        if self.current_material:
            self.layout_editor_view.set_sheet_size(
                self.current_material["width_mm"],
                self.current_material["height_mm"]
            )

        # Inicializa a view da primeira sessão
        self.session_view = None
        if self.current_session:
            self.session_view = self.get_or_create_session_view(self.current_session)

        # Integra a mesa CAD interativa em segundo plano para cálculos e simulações
        self.setup_cad_in_session()

        # Garante que qualquer clique fora ou tecla Escape feche imediatamente qualquer menu de contexto
        self._last_popup_time = 0
        self._active_popup_menu = None
        self.bind_all("<Button-1>", self.dismiss_popup_menus, add="+")
        self.bind_all("<Button-2>", self.dismiss_popup_menus, add="+")
        self.bind_all("<Button-3>", self.dismiss_popup_menus, add="+")
        self.bind_all("<Escape>", self.dismiss_popup_menus, add="+")
        self.bind_all("<Delete>", self.on_global_delete_key, add="+")
        self.bind_all("<BackSpace>", self.on_global_delete_key, add="+")
        self.bind_all("<Control-a>", self.on_select_all, add="+")
        self.bind_all("<Control-A>", self.on_select_all, add="+")
        self.bind_all("<Control-Key-a>", self.on_select_all, add="+")
        self.bind_all("<Control-Key-A>", self.on_select_all, add="+")
        self.bind_all("<Control-z>", self.on_global_undo, add="+")
        self.bind_all("<Control-Z>", self.on_global_undo, add="+")
        self.bind_all("<Control-Key-z>", self.on_global_undo, add="+")
        self.bind_all("<Control-Key-Z>", self.on_global_undo, add="+")

    def setup_cad_in_session(self):
        # CADCanvas para gestão em segundo plano de peças, simulação e exportação
        self.canvas = CADCanvas(self)
        self.canvas.on_change = self.update_all_metrics

    def on_session_material_changed(self, mat_dict):
        """Atualiza dimensões de layout, camadas e parâmetros do material na sessão e CAD."""
        if not self.current_material:
            self.current_material = {}

        self.current_material["width_mm"] = mat_dict["width_mm"]
        self.current_material["height_mm"] = mat_dict["height_mm"]
        self.current_material["area_m2"] = mat_dict["area_m2"]
        self.current_material["layers"] = mat_dict["layers"]
        self.current_material["gap_mm"] = mat_dict["gap"]
        self.current_material["code"] = mat_dict["code"]
        self.current_material["type"] = mat_dict["type"]
        self.current_material["name"] = f"Chapa {mat_dict['code']} ({mat_dict['width_m']:.2f}x{mat_dict['length_m']:.2f}m)"

        mat_id = self.current_material.get("id")
        if mat_id:
            self.db.update_material(
                mat_id,
                width_mm=mat_dict["width_mm"],
                height_mm=mat_dict["height_mm"],
                area_m2=mat_dict["area_m2"],
                type=mat_dict["type"],
                name=self.current_material["name"],
                layers=mat_dict.get("layers", 2),
                gap_mm=mat_dict.get("gap", 1.0)
            )

        # Atualiza o material na mesa CAD
        self.canvas.set_material(self.current_material)

        # Atualiza a chapa no Layout Editor
        if hasattr(self, "layout_editor_view"):
            self.layout_editor_view.set_sheet_size(mat_dict["width_mm"], mat_dict["height_mm"])

        # Salva o estado da sessão
        if self.current_session:
            self.current_session["material"] = dict(self.current_material)
            self.save_current_session_state()

        # Recalcula métricas e resumo
        self.update_all_metrics()

        w_m = mat_dict["width_m"]
        l_m = mat_dict["length_m"]
        layers = mat_dict["layers"]
        self.lbl_status_msg.config(
            text=f"Material atualizado: Largura={w_m:.2f}m, Comprimento={l_m:.2f}m, Camadas={layers}"
        )

    # =========================================================================
    # Gerenciamento de Janelas Filhas MDI na Área Cinza e Múltiplas Sessões
    # =========================================================================
    def get_or_create_session_view(self, sess_dict):
        """Cria ou recupera a instância MDI de uma sessão pelo seu ID."""
        sess_id = sess_dict["id"]
        if sess_id in self.open_sessions:
            view = self.open_sessions[sess_id]
            view.load_session(sess_dict)
            return view

        view = SessionView(
            self.mdi_workspace,
            session_data=sess_dict,
            on_close=lambda *args, s=sess_id: self.close_session_window(s),
            on_minimize=lambda *args: self.minimize_window(view),
            on_maximize=lambda *args: self.toggle_maximize_window(view),
            on_edit_shape=self.show_shape_editor,
            on_delete_shape=self.on_delete_shape,
            on_import_die=self.on_import_die,
            on_open_layout_editor=self.show_layout_editor,
            on_material_change=self.on_session_material_changed,
            on_nest=self.on_auto_nest,
            on_standby=self.on_session_standby,
            on_rewind=self.on_clear_bed,
            on_cut=self.on_toggle_sim,
            on_strategy_change=self.on_session_strategy_changed,
            on_add_shapes=self.on_session_shapes_changed,
            all_shapes_catalog=self.current_shapes,
            db=self.db,
            on_open_dieproc=self.open_dieproc_dialog
        )
        view.set_materials_list(self.materials)
        session_shapes = sess_dict.get("shapes", [])
        view.set_shapes_data(session_shapes)
        self.open_sessions[sess_id] = view
        return view

    def show_session_window(self, session_data_or_id=None):
        """Abre ou ativa uma sessão na área de trabalho MDI."""
        if session_data_or_id is None:
            if self.current_session:
                sess_dict = self.current_session
            elif self.sessions:
                sess_dict = self.sessions[0]
            else:
                return None
        elif isinstance(session_data_or_id, dict):
            sess_dict = session_data_or_id
        else:
            sess_dict = next((s for s in self.sessions if s["id"] == session_data_or_id), None)
            if not sess_dict:
                sess_dict = {"id": session_data_or_id, "name": f"Sessão #{session_data_or_id}", "status": "Stand by"}

        if "material" not in sess_dict and self.current_material:
            sess_dict["material"] = self.current_material

        view = self.get_or_create_session_view(sess_dict)

        if view in self.minimized_windows:
            self.restore_window(view)
        else:
            self.activate_window(view)

        view.load_session(sess_dict)
        self.session_view = view
        self.current_session = sess_dict
        self.lbl_status_msg.config(text=f"Sessão #{sess_dict['id']} aberta na área de trabalho.")
        return view

    def on_session_shapes_changed(self, sess_id, shapes):
        """Salva a lista de moldes da sessão no SQLite e sincroniza a sessão em memória."""
        self.db.update_session_shapes(sess_id, shapes)
        for s in self.sessions:
            if s["id"] == sess_id:
                s["shapes"] = list(shapes)
                break
        if self.current_session and self.current_session["id"] == sess_id:
            self.current_session["shapes"] = list(shapes)
        if hasattr(self, "layout_editor_view") and self.layout_editor_view:
            self.layout_editor_view.set_session_shapes(shapes)
        cnt = len(shapes)
        self.lbl_status_msg.config(text=f"Sessão #{sess_id}: {cnt} molde(s) configurado(s) na aba Moldes.")

    def minimize_window(self, window):
        """Minimiza uma janela MDI exibindo-a como mini-barra na dock inferior."""
        if not window or window in self.minimized_windows:
            return

        window.pack_forget()
        window.place_forget()
        if window in self.open_windows:
            self.open_windows.remove(window)

        title = "Janela"
        if hasattr(window, "lbl_title"):
            title = window.lbl_title.cget("text")
        elif hasattr(window, "session_data"):
            title = f"🗂️ Session #{window.session_data.get('id', '')}"

        dock_item = tk.Frame(self.mdi_dock, bg=THEME["title_bar_bg"], relief="raised", bd=2, width=180, height=24)
        dock_item.pack_propagate(False)

        lbl = tk.Label(
            dock_item, text=title,
            bg=THEME["title_bar_bg"], fg=THEME["title_bar_fg"],
            font=("Segoe UI", 8, "bold"), anchor="w", cursor="hand2"
        )
        lbl.pack(side="left", fill="x", expand=True, padx=4)

        btn_restore = tk.Button(
            dock_item, text="🗖", relief="raised", bd=1,
            bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0,
            cursor="hand2",
            command=lambda: self.restore_window(window)
        )
        btn_restore.pack(side="right", padx=1)

        btn_close = tk.Button(
            dock_item, text="✕", relief="raised", bd=1,
            bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0,
            cursor="hand2",
            command=lambda: self.close_window(window)
        )
        btn_close.pack(side="right", padx=1)

        dock_item.bind("<Button-1>", lambda e: self.restore_window(window))
        lbl.bind("<Button-1>", lambda e: self.restore_window(window))

        dock_item.pack(side="left", padx=2, pady=1)
        self.minimized_windows[window] = dock_item
        self.mdi_dock.pack(side="bottom", fill="x", padx=2, pady=2)

        if self.open_windows:
            self.activate_window(self.open_windows[-1])
        else:
            self.active_child = None

        self.lbl_status_msg.config(text=f"{title} minimizada.")

    def restore_window(self, window):
        """Restaura uma janela MDI da dock para a área de trabalho."""
        if not window:
            return
        if window in self.minimized_windows:
            dock_item = self.minimized_windows.pop(window)
            dock_item.destroy()

        if not self.minimized_windows:
            self.mdi_dock.pack_forget()

        if window not in self.open_windows:
            self.open_windows.append(window)

        self.activate_window(window)

    def activate_window(self, window):
        """Torna a janela filha ativa e visível no MDI."""
        if not window:
            return
        if window in self.minimized_windows:
            self.restore_window(window)
            return

        if window not in self.open_windows:
            self.open_windows.append(window)

        if self._window_layout_mode == "maximized":
            for w in self.open_windows:
                if w != window:
                    w.pack_forget()
                    w.place_forget()
            if window == self.layout_editor_view:
                window.place(in_=self, x=0, y=0, relwidth=1.0, relheight=1.0)
                window.lift()
            else:
                window.pack(fill="both", expand=True, padx=2, pady=2)
        elif self._window_layout_mode in ("tile_h", "tile_v", "cascade"):
            window.lift()
        else:
            if not window.winfo_ismapped():
                ww = max(420, int(self.mdi_workspace.winfo_width() * 0.85))
                wh = max(320, int(self.mdi_workspace.winfo_height() * 0.85))
                if window == self.layout_editor_view:
                    window.place(in_=self.mdi_workspace, x=25, y=15, width=ww, height=wh)
                else:
                    window.place(x=25, y=15, width=ww, height=wh)
            window.lift()

        self.active_child = window
        if isinstance(window, SessionView):
            self.session_view = window
            self.current_session = window.session_data
            if hasattr(self, "canvas") and "placed_pieces" in self.current_session:
                self.canvas.placed_pieces = [dict(p) for p in self.current_session.get("placed_pieces", [])]
                self.canvas.redraw()
            if self.current_session:
                self.lbl_status_msg.config(text=f"Sessão #{self.current_session.get('id', '')} ativa.")

    def toggle_fullscreen(self, event=None):
        try:
            is_fs = bool(self.attributes("-fullscreen"))
            self.attributes("-fullscreen", not is_fs)
        except Exception:
            pass

    def exit_fullscreen(self, event=None):
        try:
            if self.attributes("-fullscreen"):
                self.attributes("-fullscreen", False)
        except Exception:
            pass

    def handle_ctrl_s(self, event=None):
        if hasattr(self, "layout_editor_view") and self.layout_editor_view.winfo_ismapped():
            self.layout_editor_view.save_layout_dialog()
            return "break"
        if hasattr(self, "session_view") and self.session_view and self.session_view.winfo_ismapped():
            self.lbl_status_msg.config(text="Sessão salva com sucesso no banco de dados.")
            return "break"

    def handle_ctrl_p(self, event=None):
        if hasattr(self, "layout_editor_view") and self.layout_editor_view and self.layout_editor_view.winfo_ismapped():
            self.layout_editor_view.print_layout()
            return "break"
        return None

    def on_layout_editor_save(self, placed_pieces, sheet_w=1350.0, sheet_h=2553.38, layout_name="[I0000]"):
        """Salva as peças posicionadas no layout de volta para a sessão ativa e banco de dados SQLite."""
        active_sess = self.current_session
        if not active_sess and getattr(self, "sessions", None):
            active_sess = self.sessions[0]

        if not active_sess:
            return False

        # 1. Atualiza as peças na sessão em memória
        active_sess["placed_pieces"] = copy.deepcopy(placed_pieces)

        # 2. Recalcula a área utilizada e a eficiência de aproveitamento (Yield %)
        tot_area_mm2 = sum(polygon_area(p.get("contour", [])) for p in placed_pieces)
        sheet_area_mm2 = max(1.0, sheet_w * sheet_h)
        yield_pct = round((tot_area_mm2 / sheet_area_mm2) * 100.0, 2)
        used_area_m2 = round(tot_area_mm2 / 1_000_000.0, 2)

        active_sess["yield_percent"] = yield_pct
        active_sess["used_area_m2"] = used_area_m2
        active_sess["status"] = "Nested"

        # 3. Persiste no banco de dados SQLite
        self.db.update_session(
            active_sess["id"],
            placed_pieces=placed_pieces,
            yield_pct=yield_pct,
            status="Nested"
        )

        # 4. Sincroniza a SessionView se estiver aberta
        sess_view = self.open_sessions.get(active_sess["id"])
        if sess_view:
            sess_view.session_data["placed_pieces"] = copy.deepcopy(placed_pieces)
            sess_view.session_data["yield_percent"] = yield_pct
            sess_view.session_data["used_area_m2"] = used_area_m2

            # Atualiza resumo
            time_sec = active_sess.get("cutting_time_sec", 32.0)
            sess_view.update_summary_text(len(placed_pieces), yield_pct, time_sec)

            # Atualiza tabela da aba Layout
            if hasattr(sess_view, "tree_lays"):
                sess_view.tree_lays.delete(*sess_view.tree_lays.get_children())
                eff_str = f"{yield_pct:.2f}%".replace('.', ',')
                pieces_cnt = str(len(placed_pieces))
                time_str = f"{int(time_sec // 60):02d}:{int(time_sec % 60):02d}"
                area_str = f"{used_area_m2:.2f}".replace('.', ',')
                sess_view.tree_lays.insert("", "end", iid="lay_0", values=("▶", "0", eff_str, "1", "0", time_str, pieces_cnt, area_str))
                sess_view.tree_lays.selection_set("lay_0")

            # Redesenha a miniatura da chapa na aba Layout com as novas peças
            sess_view.draw_mini_layout_preview()

        # 5. Atualiza o painel de status do Layout Editor
        if hasattr(self.layout_editor_view, "lbl_stat_yield"):
            self.layout_editor_view.lbl_stat_yield.config(text=f"{yield_pct:.2f}%")

        self.lbl_status_msg.config(text=f"Layout {layout_name} salvo com sucesso no banco ({len(placed_pieces)} peças, {yield_pct:.2f}%).")
        return True

    def toggle_maximize_window(self, window):
        """Alterna entre maximizado e restaurado/flutuante."""
        if not window:
            return
        if self._window_layout_mode == "maximized":
            self._window_layout_mode = "windowed"
            window.pack_forget()
            window.place_forget()
            ww = max(420, int(self.mdi_workspace.winfo_width() * 0.85))
            wh = max(320, int(self.mdi_workspace.winfo_height() * 0.85))
            if window == self.layout_editor_view:
                window.place(in_=self.mdi_workspace, x=25, y=15, width=ww, height=wh)
            else:
                window.place(x=25, y=15, width=ww, height=wh)
            if hasattr(window, "btn_max"):
                window.btn_max.config(text="□")
            window.lift()
        else:
            self.maximize_window(window)

    def maximize_window(self, window):
        if not window:
            return
        self._window_layout_mode = "maximized"
        for w in self.open_windows:
            w.place_forget()
            if w != window:
                w.pack_forget()
        if window == self.layout_editor_view:
            window.place(in_=self, x=0, y=0, relwidth=1.0, relheight=1.0)
            window.lift()
        else:
            window.pack(fill="both", expand=True, padx=2, pady=2)
        if hasattr(window, "btn_max"):
            window.btn_max.config(text="❐")
        self.activate_window(window)

    def close_window(self, window):
        """Fecha uma janela MDI liberando recursos."""
        if not window:
            return
        if window in self.minimized_windows:
            dock_item = self.minimized_windows.pop(window)
            dock_item.destroy()

        if not self.minimized_windows:
            self.mdi_dock.pack_forget()

        if window in self.open_windows:
            self.open_windows.remove(window)

        window.pack_forget()
        window.place_forget()

        for sid, v in list(self.open_sessions.items()):
            if v == window:
                del self.open_sessions[sid]
                break

        if window not in (self.order_view, self.shape_editor_view, self.layout_editor_view, getattr(self, "material_codes_view", None)):
            try:
                window.destroy()
            except Exception:
                pass

        if self.open_windows:
            self.activate_window(self.open_windows[-1])
        else:
            self.active_child = None
            if self.open_sessions:
                last_sess_id = next(iter(self.open_sessions.keys()))
                self.session_view = self.open_sessions[last_sess_id]
                self.current_session = self.session_view.session_data
                self.activate_window(self.session_view)
            else:
                self.session_view = None
            self.lbl_status_msg.config(text="Job Manager está pronto")

    def close_session_window(self, sess_id_or_view):
        if isinstance(sess_id_or_view, SessionView):
            self.close_window(sess_id_or_view)
            return
        if sess_id_or_view in self.open_sessions:
            view = self.open_sessions[sess_id_or_view]
            self.close_window(view)

    def tile_horizontal(self):
        """Organiza janelas abertas empilhadas horizontalmente."""
        if not self.open_windows:
            return
        self._window_layout_mode = "tile_h"
        N = len(self.open_windows)
        for i, w in enumerate(self.open_windows):
            w.pack_forget()
            if w == self.layout_editor_view:
                w.place(in_=self.mdi_workspace, x=2, rely=i / N, relwidth=0.99, relheight=1.0 / N - 0.01)
            else:
                w.place(x=2, rely=i / N, relwidth=0.99, relheight=1.0 / N - 0.01)
            w.lift()
            if hasattr(w, "btn_max"):
                w.btn_max.config(text="❐")

    def tile_vertical(self):
        """Organiza janelas abertas lado a lado verticalmente."""
        if not self.open_windows:
            return
        self._window_layout_mode = "tile_v"
        N = len(self.open_windows)
        for i, w in enumerate(self.open_windows):
            w.pack_forget()
            if w == self.layout_editor_view:
                w.place(in_=self.mdi_workspace, relx=i / N, y=2, relwidth=1.0 / N - 0.01, relheight=0.99)
            else:
                w.place(relx=i / N, y=2, relwidth=1.0 / N - 0.01, relheight=0.99)
            w.lift()
            if hasattr(w, "btn_max"):
                w.btn_max.config(text="❐")

    def cascade_windows(self):
        """Organiza janelas abertas em cascata."""
        if not self.open_windows:
            return
        self._window_layout_mode = "cascade"
        ww = max(450, int(self.mdi_workspace.winfo_width() * 0.75))
        wh = max(350, int(self.mdi_workspace.winfo_height() * 0.75))
        for i, w in enumerate(self.open_windows):
            w.pack_forget()
            offset = i * 26
            if w == self.layout_editor_view:
                w.place(in_=self.mdi_workspace, x=10 + offset, y=10 + offset, width=ww, height=wh)
            else:
                w.place(x=10 + offset, y=10 + offset, width=ww, height=wh)
            w.lift()
            if hasattr(w, "btn_max"):
                w.btn_max.config(text="❐")

    def get_next_session_number(self):
        """Calcula o próximo número sequencial de sessão estritamente único e monotônico."""
        try:
            return self.db.get_next_session_number()
        except Exception:
            existing_ids = {s["id"] for s in getattr(self, "sessions", []) if isinstance(s.get("id"), int)}
            return max(existing_ids, default=0) + 1

    def save_current_session_state(self):
        """Salva as peças colocadas e métricas da sessão ativa no banco e memória."""
        if self.current_session:
            self.current_session["placed_pieces"] = [dict(p) for p in self.canvas.placed_pieces]
            yield_pct = 0.0
            time_sec = 0.0
            used_m2 = 0.0
            if self.current_material and self.canvas.placed_pieces:
                yield_pct, used_m2 = calculate_yield(self.canvas.placed_pieces, self.current_material["area_m2"])
                est_sec, _ = calculate_atom_cutting_time(self.canvas.placed_pieces)
                time_sec = est_sec
            self.current_session["yield_percent"] = yield_pct
            self.current_session["cutting_time_sec"] = time_sec
            self.current_session["used_area_m2"] = used_m2
            try:
                self.db.update_session(
                    self.current_session["id"],
                    placed_pieces=self.current_session["placed_pieces"],
                    yield_pct=yield_pct,
                    time_sec=time_sec
                )
            except Exception:
                pass

    def switch_to_session(self, sess_id):
        """Alterna para a sessão indicada restaurando suas peças na mesa CAD."""
        target_sess = next((s for s in self.sessions if s.get("id") == sess_id), None)
        if not target_sess:
            return

        self.save_current_session_state()
        self.current_session = target_sess
        self.canvas.clear_bed()
        for p in target_sess.get("placed_pieces", []):
            self.canvas.placed_pieces.append(dict(p))
        self.canvas.redraw()

        self.show_session_window(target_sess)
        if self.session_view:
            self.session_view.notebook.select(self.session_view.tab_lays)
        self.update_all_metrics()

        if self.current_mode == "jobs":
            self.select_session_in_tree(sess_id)
            self.select_session_in_grid(sess_id)

    def select_session_in_tree(self, sess_id):
        for item in self.tree_main.get_children():
            self._find_and_select_session_node(item, sess_id)

    def _find_and_select_session_node(self, node, sess_id):
        vals = self.tree_main.item(node, "values")
        if vals and len(vals) >= 2 and vals[0] == "session":
            try:
                if int(vals[1]) == int(sess_id):
                    current_sel = self.tree_main.selection()
                    if len(current_sel) > 1 and node in current_sel:
                        return True
                    if current_sel != (node,):
                        self.tree_main.selection_set(node)
                    self.tree_main.see(node)
                    return True
            except (ValueError, TypeError):
                pass
        for ch in self.tree_main.get_children(node):
            if self._find_and_select_session_node(ch, sess_id):
                return True
        return False

    def select_session_in_grid(self, sess_id):
        for item in self.grid_lower.get_children():
            vals = self.grid_lower.item(item, "values")
            if vals and len(vals) >= 1 and str(vals[0]) == str(sess_id):
                current_sel = self.grid_lower.selection()
                if len(current_sel) > 1 and item in current_sel:
                    return
                if current_sel != (item,):
                    self.grid_lower.selection_set(item)
                self.grid_lower.see(item)
                break

    def show_order_window(self, order_id_or_data=None):
        target_order = None
        if isinstance(order_id_or_data, dict):
            target_order = order_id_or_data
        elif isinstance(order_id_or_data, int):
            target_order = next((o for o in self.orders if o["id"] == order_id_or_data), None)
        elif self.orders:
            target_order = self.orders[0]

        if target_order and hasattr(self.order_view, "load_order"):
            self.order_view.load_order(target_order)
            self.current_order = target_order

        if self.order_view in self.minimized_windows:
            self.restore_window(self.order_view)
        else:
            self.activate_window(self.order_view)

        ord_name = target_order.get("name", "Pedido") if target_order else "Pedido"
        self.lbl_status_msg.config(text=f"Ordem [{ord_name}] aberta na área de trabalho.")

    def on_create_order(self):
        order_name = simpledialog.askstring("Criar Pedido", "Nome ou descrição do pedido:", initialvalue="Novo Pedido", parent=self)
        if not order_name:
            return
        cust_name = simpledialog.askstring("Criar Pedido", "Nome do cliente:", initialvalue="Calçados Elite S/A", parent=self) or "Calçados Elite S/A"
        new_id = self.db.create_order(name=order_name, customer=cust_name)
        self.orders = self.db.get_orders()
        self.current_order = next((o for o in self.orders if o["id"] == new_id), None)
        if self.current_mode == "jobs":
            self.switch_tree_mode("jobs")
            self.select_order_in_tree(new_id)
        self.show_order_window(new_id)
        self.lbl_status_msg.config(text=f"Pedido '{order_name}' criado com sucesso.")

    def select_order_in_tree(self, order_id):
        for item in self.tree_main.get_children():
            self._find_and_select_order_node(item, order_id)

    def _find_and_select_order_node(self, node, order_id):
        vals = self.tree_main.item(node, "values")
        if vals and len(vals) >= 2 and vals[0] == "order":
            try:
                if int(vals[1]) == int(order_id):
                    current_sel = self.tree_main.selection()
                    if current_sel != (node,):
                        self.tree_main.selection_set(node)
                    self.tree_main.see(node)
                    return True
            except (ValueError, TypeError):
                pass
        for ch in self.tree_main.get_children(node):
            if self._find_and_select_order_node(ch, order_id):
                return True
        return False

    def show_shape_editor(self, shape_id_or_data=None):
        target_shape = None
        if isinstance(shape_id_or_data, dict):
            target_shape = shape_id_or_data
        elif isinstance(shape_id_or_data, int):
            target_shape = self.db.get_shape(shape_id_or_data)
        elif shape_id_or_data is None:
            sel = self.tree_main.selection()
            if sel:
                val = self.tree_main.item(sel[0], "values")
                if val and len(val) >= 2 and val[0] == "shape":
                    try:
                        target_shape = self.db.get_shape(int(val[1]))
                    except (ValueError, TypeError):
                        pass
            if not target_shape and self.current_shapes:
                target_shape = self.current_shapes[0]

        if not target_shape and self.current_shapes:
            target_shape = self.current_shapes[0]

        if target_shape:
            self.shape_editor_view.load_shape(target_shape)

        if self.shape_editor_view in self.minimized_windows:
            self.restore_window(self.shape_editor_view)
        else:
            self.activate_window(self.shape_editor_view)

        shp_name = target_shape.get("name", "Molde") if target_shape else ""
        self.lbl_status_msg.config(text=f"Shape Editor: [{shp_name}] aberto na área de trabalho.")

    def show_layout_editor(self, layout_name=None, force=False):
        # Sincroniza moldes e peças da sessão ativa caso existam
        active_sess = self.current_session
        if not active_sess and getattr(self, "sessions", None):
            active_sess = self.sessions[0]

        placed = active_sess.get("placed_pieces") if isinstance(active_sess, dict) else None
        if not force and (not active_sess or not placed):
            messagebox.showwarning(
                "Layout Editor",
                "Não há layout calculado para esta sessão.\nExecute o cálculo de encaixe (Nest) primeiro.",
                parent=self
            )
            return

        if self.layout_editor_view in self.minimized_windows:
            self.restore_window(self.layout_editor_view)
        self.maximize_window(self.layout_editor_view)

        if active_sess:
            sess_mat = active_sess.get("material") or self.current_material
            if sess_mat and hasattr(self.layout_editor_view, "set_sheet_size"):
                w = float(sess_mat.get("width_mm", 1350.0))
                h = float(sess_mat.get("height_mm", 2553.38))
                self.layout_editor_view.set_sheet_size(w, h)

            sess_shapes = active_sess.get("shapes") or []
            if hasattr(self.layout_editor_view, "set_session_shapes"):
                self.layout_editor_view.set_session_shapes(sess_shapes)

            if active_sess.get("placed_pieces"):
                le_pieces = []
                for p in active_sess["placed_pieces"]:
                    shp = p.get("shape", {}) if isinstance(p.get("shape"), dict) else {}
                    contour = p.get("contour") or shp.get("contour") or []
                    name = p.get("name") or shp.get("name") or "Peça"
                    size = str(p.get("size") or shp.get("size") or "41")
                    color = get_color_for_size(size)
                    le_pieces.append({
                        "target_id": p.get("id", 1),
                        "name": name,
                        "size": size,
                        "color": color,
                        "contour": contour,
                        "x": p.get("x", 0.0),
                        "y": p.get("y", 0.0),
                        "rotation": p.get("rotation", 0.0)
                    })
                self.layout_editor_view.placed_pieces = le_pieces
            else:
                self.layout_editor_view.placed_pieces = []
            self.layout_editor_view.redraw()
            self.layout_editor_view.update_status()

        doc_name = layout_name or (active_sess.get("layout_name") if active_sess else None) or "[I0000]"
        self.lbl_status_msg.config(text=f"Layout Editor: {doc_name} aberto na área de trabalho.")

    def show_material_codes_window(self):
        """Abre ou ativa a janela MDI Códigos materiais (Listagem de materiais)."""
        if hasattr(self, "material_codes_view"):
            self.material_codes_view.refresh_table()
            if self.material_codes_view in self.minimized_windows:
                self.restore_window(self.material_codes_view)
            else:
                self.activate_window(self.material_codes_view)
            self.lbl_status_msg.config(text="Códigos materiais aberto na área de trabalho.")

    def refresh_materials_everywhere(self):
        """Atualiza a lista de materiais em cache, na árvore, grid, sessões e layout editor."""
        self.materials = self.db.get_materials()
        if self.current_mode == "materials":
            self.switch_tree_mode("materials")
        for sv in self.open_sessions.values():
            sv.set_materials_list(self.materials)
        if hasattr(self, "material_codes_view"):
            self.material_codes_view.refresh_table()

    def show_options_dialog(self):
        """Abre a janela modal de Opções do sistema (Ferramentas -> Opções)."""
        OptionsDialog(self, self.db, on_apply=self.on_apply_options)

    def on_apply_options(self, settings):
        """Aplica as configurações do sistema imediatamente."""
        self.app_settings = settings
        if settings.get("start_maximized", "1") == "1":
            self._window_layout_mode = "maximized"
        else:
            self._window_layout_mode = "windowed"

        # Atualiza orientação de chapas se necessário
        if hasattr(self, "layout_editor_view") and self.current_material:
            is_horiz = settings.get("materials_horizontal", "0") == "1"
            w = float(self.current_material.get("width_mm", 1380.0))
            h = float(self.current_material.get("height_mm", 2980.0))
            if is_horiz and w < h:
                w, h = h, w
            elif not is_horiz and w > h:
                w, h = h, w
            self.layout_editor_view.set_sheet_size(w, h)

        self.lbl_status_msg.config(text="Opções do sistema aplicadas com sucesso.")

    def on_refresh_f5(self):
        """Atualiza todos os dados do sistema a partir do banco de dados SQLite (F5)."""
        self.materials = self.db.get_materials()
        self.current_shapes = self.db.get_shapes()
        self.orders = self.db.get_orders()
        self.sessions = self.db.get_sessions()
        self.app_settings = self.db.get_all_settings()

        # Atualiza a visualização da árvore e grid inferior no modo atual
        self.switch_tree_mode(self.current_mode)

        # Atualiza materiais e catálogo de moldes nas sessões abertas
        for sv in self.open_sessions.values():
            sv.set_materials_list(self.materials)
            sv.all_shapes_catalog = self.current_shapes

        # Atualiza tabela de materiais se a view estiver aberta
        if hasattr(self, "material_codes_view"):
            self.material_codes_view.refresh_table()

        self.lbl_status_msg.config(text="Dados do sistema atualizados com sucesso (F5).")

    def on_shape_saved(self, updated_shape):
        shape_id = updated_shape.get("id")
        if shape_id:
            self.db.update_shape(
                shape_id,
                updated_shape.get("name"),
                updated_shape.get("contour"),
                updated_shape.get("holes"),
                updated_shape.get("stitching")
            )
            for i, s in enumerate(self.current_shapes):
                if s["id"] == shape_id:
                    self.current_shapes[i] = copy.deepcopy(updated_shape)
                    break

        for sv in self.open_sessions.values():
            sv.all_shapes_catalog = self.current_shapes
            for idx, shp in enumerate(sv.shapes_list):
                if shp.get("id") == shape_id:
                    sv.shapes_list[idx] = copy.deepcopy(updated_shape)
                    sv.set_shapes_data(sv.shapes_list)
                    break

        if self.current_mode == "shapes":
            self.switch_tree_mode("shapes")

        self.lbl_status_msg.config(text=f"Molde '{updated_shape.get('name')}' salvo com sucesso no banco de dados.")

    def get_selected_folder(self):
        """Retorna o nome da pasta de moldes atualmente selecionada na árvore."""
        sel = self.tree_main.selection()
        if sel:
            vals = self.tree_main.item(sel[0], "values")
            if vals and len(vals) >= 2:
                if vals[0] == "folder":
                    return str(vals[1])
                elif vals[0] == "shape" and len(vals) >= 3:
                    return str(vals[2]) if vals[2] else ""
        return ""

    def select_folder_node(self, folder_name):
        """Localiza e destaca visualmente o nó da pasta na árvore."""
        def _check(item):
            vals = self.tree_main.item(item, "values")
            if vals and len(vals) >= 2 and vals[0] == "folder" and vals[1] == folder_name:
                self.tree_main.selection_set(item)
                self.tree_main.focus(item)
                self.tree_main.see(item)
                return True
            for child in self.tree_main.get_children(item):
                if _check(child):
                    return True
            return False

        for r in self.tree_main.get_children(""):
            if _check(r):
                break

    def select_job_folder_node(self, folder_name):
        """Localiza e destaca visualmente o nó da pasta de produção na árvore."""
        def _check(item):
            vals = self.tree_main.item(item, "values")
            if vals and len(vals) >= 2 and vals[0] == "job_folder" and vals[1] == folder_name:
                self.tree_main.selection_set(item)
                self.tree_main.focus(item)
                self.tree_main.see(item)
                return True
            for child in self.tree_main.get_children(item):
                if _check(child):
                    return True
            return False

        for r in self.tree_main.get_children(""):
            if _check(r):
                break

    def on_create_shape_folder(self, parent_folder=""):
        """Cria uma nova pasta ou subpasta para organizar moldes .die."""
        if parent_folder:
            name = simpledialog.askstring("Criar Subpasta de Moldes", f"Nome da nova subpasta dentro de '{parent_folder}':", initialvalue="Nova Subpasta", parent=self)
            if name and name.strip():
                sub_name = name.strip().strip("/")
                folder_path = f"{parent_folder}/{sub_name}"
                self.db.create_shape_folder(folder_path)
                if self.current_mode == "shapes":
                    self.switch_tree_mode("shapes")
                    self.select_folder_node(folder_path)
                self.lbl_status_msg.config(text=f"Subpasta de moldes '{folder_path}' criada com sucesso.")
        else:
            name = simpledialog.askstring("Criar Pasta de Moldes", "Nome da nova pasta de moldes:", initialvalue="Nova Pasta", parent=self)
            if name and name.strip():
                folder_name = name.strip().strip("/")
                self.db.create_shape_folder(folder_name)
                if self.current_mode == "shapes":
                    self.switch_tree_mode("shapes")
                    self.select_folder_node(folder_name)
                self.lbl_status_msg.config(text=f"Pasta de moldes '{folder_name}' criada com sucesso.")

    def on_create_shape_subfolder(self, parent_folder):
        """Cria explicitamente uma subpasta dentro de parent_folder."""
        self.on_create_shape_folder(parent_folder=parent_folder)

    def on_create_subfolder_menu_action(self):
        """Ação de menu para criar subpasta: se houver pasta selecionada na árvore, usa-a como pai."""
        parent_folder = ""
        if self.current_mode == "shapes":
            sel = self.tree_main.selection()
            if sel:
                vals = self.tree_main.item(sel[0], "values")
                if vals and vals[0] == "folder":
                    parent_folder = str(vals[1])
        if not parent_folder:
            folders = self.db.get_shape_folders()
            if not folders:
                messagebox.showinfo("Criar Subpasta", "Nenhuma pasta raiz existe ainda. Crie primeiro uma pasta raiz.", parent=self)
                return self.on_create_shape_folder()
            parent_folder = self.prompt_select_parent_folder(folders)
            if not parent_folder:
                return
        self.on_create_shape_subfolder(parent_folder)

    def prompt_select_parent_folder(self, folders):
        """Diálogo para selecionar uma pasta existente como pai da nova subpasta."""
        dlg = tk.Toplevel(self)
        dlg.title("Selecionar Pasta Pai")
        dlg.geometry("320x260")
        dlg.resizable(False, False)
        dlg.configure(bg=THEME["bg_surface"])
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Selecione a pasta onde criar a subpasta:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9, "bold")).pack(padx=10, pady=8, anchor="w")

        lb_frame = tk.Frame(dlg, bg=THEME["bg_surface"], relief="sunken", bd=1)
        lb_frame.pack(fill="both", expand=True, padx=10, pady=4)

        lb = tk.Listbox(lb_frame, bg="white", fg="black", selectbackground=THEME["select_bg"], selectforeground="white", font=("Segoe UI", 9))
        lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lb_frame, orient="vertical", command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.config(yscrollcommand=sb.set)

        for f in folders:
            depth = f.count("/")
            indent = "    " * depth
            name_part = f.split("/")[-1]
            lb.insert("end", f"{indent}📁 {name_part} ({f})")
        lb.selection_set(0)

        chosen = [None]
        def do_confirm():
            sel_idx = lb.curselection()
            if sel_idx:
                chosen[0] = folders[sel_idx[0]]
            dlg.destroy()

        btn_box = tk.Frame(dlg, bg=THEME["bg_surface"], pady=6)
        btn_box.pack(fill="x", padx=10)
        tk.Button(btn_box, text="Avançar", width=10, bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, command=do_confirm).pack(side="right", padx=4)
        tk.Button(btn_box, text="Cancelar", width=10, bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, command=dlg.destroy).pack(side="right", padx=4)

        self.wait_window(dlg)
        return chosen[0]

    def on_rename_shape_folder(self, folder_name):
        """Renomeia uma pasta de moldes existente e atualiza suas subpastas."""
        folder_name = folder_name.strip().strip("/")
        base_name = folder_name.split("/")[-1]
        parent_prefix = "/".join(folder_name.split("/")[:-1])
        new_base = simpledialog.askstring("Renomear Pasta", f"Novo nome para a pasta '{base_name}':", initialvalue=base_name, parent=self)
        if new_base and new_base.strip() and new_base.strip() != base_name:
            new_base = new_base.strip().strip("/")
            new_name = f"{parent_prefix}/{new_base}" if parent_prefix else new_base
            self.db.rename_shape_folder(folder_name, new_name)
            self.reload_shapes()
            if self.current_mode == "shapes":
                self.switch_tree_mode("shapes")
                self.select_folder_node(new_name)
            self.lbl_status_msg.config(text=f"Pasta renomeada para '{new_name}'.")

    def on_delete_shape_folder(self, folder_name):
        """Exclui uma pasta de moldes (e suas subpastas) com opção de mover ou excluir os moldes."""
        folder_name = folder_name.strip().strip("/")
        f_prefix = folder_name + "/"
        shapes_in_folder = [s for s in self.current_shapes if (s.get("folder") or "").strip() == folder_name or (s.get("folder") or "").strip().startswith(f_prefix)]
        if len(shapes_in_folder) == 0:
            if not messagebox.askyesno("Excluir Pasta de Moldes", f"Deseja realmente excluir a pasta '{folder_name}'?", parent=self):
                return
            delete_shapes = False
        else:
            resp = messagebox.askyesnocancel(
                "Excluir Pasta de Moldes",
                f"Deseja excluir a pasta '{folder_name}' e todas as suas subpastas?\n\n"
                f"• Clique 'Sim' para excluir a pasta E todos os moldes dentro dela ({len(shapes_in_folder)} moldes).\n"
                f"• Clique 'Não' para excluir apenas as pastas (os moldes irão para a raiz 'Moldes').\n"
                f"• Clique 'Cancelar' para desistir.",
                parent=self
            )
            if resp is None:
                return
            delete_shapes = (resp is True)

        self.db.delete_shape_folder(folder_name, delete_shapes=delete_shapes)
        self.reload_shapes()
        if self.current_mode == "shapes":
            self.switch_tree_mode("shapes")
        self.lbl_status_msg.config(text=f"Pasta '{folder_name}' excluída.")

    def on_move_shape_to_folder(self, shape_id):
        """Abre janela para mover um molde para outra pasta ou subpasta."""
        target = next((s for s in self.current_shapes if s["id"] == shape_id), None)
        if not target:
            return

        folders = self.db.get_shape_folders()
        dlg = tk.Toplevel(self)
        dlg.title("Mover Molde")
        dlg.geometry("340x280")
        dlg.resizable(False, False)
        dlg.configure(bg=THEME["bg_surface"])
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=f"Mover '{target['name']}' para a pasta:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9, "bold")).pack(padx=10, pady=8, anchor="w")

        lb_frame = tk.Frame(dlg, bg=THEME["bg_surface"], relief="sunken", bd=1)
        lb_frame.pack(fill="both", expand=True, padx=10, pady=4)

        lb = tk.Listbox(lb_frame, bg="white", fg="black", selectbackground=THEME["select_bg"], selectforeground="white", font=("Segoe UI", 9))
        lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lb_frame, orient="vertical", command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.config(yscrollcommand=sb.set)

        lb.insert("end", "[ Moldes (Raiz / Sem Pasta) ]")
        for f in folders:
            depth = f.count("/")
            indent = "    " * depth
            name_part = f.split("/")[-1]
            lb.insert("end", f"{indent}📁 {name_part} ({f})")

        curr_folder = target.get("folder", "")
        if curr_folder in folders:
            idx = folders.index(curr_folder) + 1
            lb.selection_set(idx)
        else:
            lb.selection_set(0)

        def do_move():
            sel_idx = lb.curselection()
            if not sel_idx:
                return
            idx = sel_idx[0]
            dest = "" if idx == 0 else folders[idx - 1]
            self.move_shape_to_folder(shape_id, dest)
            dlg.destroy()

        btn_box = tk.Frame(dlg, bg=THEME["bg_surface"], pady=6)
        btn_box.pack(fill="x", padx=10)
        tk.Button(btn_box, text="Mover", width=10, bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, command=do_move).pack(side="right", padx=4)
        tk.Button(btn_box, text="Cancelar", width=10, bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, command=dlg.destroy).pack(side="right", padx=4)

    def move_shape_to_folder(self, shape_id, dest_folder):
        """Move o molde para uma pasta específica no banco e atualiza a interface."""
        target = next((s for s in self.current_shapes if s["id"] == shape_id), None)
        target_name = target["name"] if target else f"ID {shape_id}"
        curr_folder = target.get("folder", "") if target else ""

        if curr_folder == dest_folder:
            dest_desc = f"pasta '{dest_folder}'" if dest_folder else "raiz de Moldes"
            self.lbl_status_msg.config(text=f"O molde '{target_name}' já está na {dest_desc}.")
            return

        self.db.update_shape_folder(shape_id, dest_folder)
        self.reload_shapes()
        if self.current_mode == "shapes":
            self.switch_tree_mode("shapes")
            if dest_folder:
                self.select_folder_node(dest_folder)

        dest_desc = f"pasta '{dest_folder}'" if dest_folder else "raiz de Moldes"
        self.lbl_status_msg.config(text=f"Molde '{target_name}' movido com sucesso para a {dest_desc}!")

    def on_rename_shape(self, shape_id):
        """Renomeia um molde."""
        target = next((s for s in self.current_shapes if s["id"] == shape_id), None)
        curr = target["name"] if target else ""
        new_name = simpledialog.askstring("Renomear Molde", "Novo nome do molde:", initialvalue=curr, parent=self)
        if new_name and new_name.strip():
            self.db.rename_shape(shape_id, new_name.strip())
            self.reload_shapes()
            if self.current_mode == "shapes":
                self.switch_tree_mode("shapes")
            self.lbl_status_msg.config(text=f"Molde renomeado para '{new_name.strip()}'.")

    def on_delete_shape(self, shape_id):
        """Exclui um molde do banco e da interface."""
        target = next((s for s in self.current_shapes if s["id"] == shape_id), None)
        shp_name = target["name"] if target else f"ID {shape_id}"
        if messagebox.askyesno("Excluir Molde", f"Deseja realmente excluir o molde '{shp_name}'?", parent=self):
            self.db.delete_shape(shape_id)
            self.current_shapes = [s for s in self.current_shapes if s["id"] != shape_id]
            self.reload_shapes()
            if self.current_mode == "shapes":
                self.switch_tree_mode("shapes")
            for sv in self.open_sessions.values():
                sv.all_shapes_catalog = self.current_shapes
                sv.shapes_list = [s for s in sv.shapes_list if s.get("id") != shape_id]
                sv.set_shapes_data(sv.shapes_list)
            self.lbl_status_msg.config(text=f"Molde '{shp_name}' excluído com sucesso.")

    def on_export_shape_die(self, shape_id):
        """Exporta um molde individual para arquivo .die padrão ATOM."""
        target = next((s for s in self.current_shapes if s["id"] == shape_id), None)
        if not target:
            return
        file_path = filedialog.asksaveasfilename(
            title=f"Exportar Molde '{target['name']}' (.die)",
            defaultextension=".die",
            initialfile=f"{target['name'].replace(' ', '_')}.die",
            filetypes=[
                ("Arquivos Shape ATOM (*.die)", "*.die"),
                ("Todos os Arquivos (*.*)", "*.*")
            ],
            parent=self
        )
        if file_path:
            save_die_file(file_path, target)
            messagebox.showinfo("Exportar Shape (.die)", f"Molde exportado com sucesso para:\n{file_path}", parent=self)
            self.lbl_status_msg.config(text=f"Molde '{target['name']}' exportado para {Path(file_path).name}.")

    def _prompt_choose_folder_for_import(self):
        """Exibe um diálogo modal rápido para escolher ou criar a pasta de destino dos moldes."""
        folders = self.db.get_shape_folders()

        dlg = tk.Toplevel(self)
        dlg.title("Selecionar Pasta de Destino")
        dlg.geometry("360x280")
        dlg.resizable(False, False)
        dlg.configure(bg=THEME["bg_surface"])
        dlg.transient(self)
        dlg.grab_set()

        try:
            self.update_idletasks()
            px = self.winfo_rootx() + (self.winfo_width() - 360) // 2
            py = self.winfo_rooty() + (self.winfo_height() - 280) // 2
            dlg.geometry(f"+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass

        tk.Label(
            dlg,
            text="📁 Selecione a pasta onde os moldes serão importados:",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold")
        ).pack(padx=12, pady=(12, 6), anchor="w")

        lb_frame = tk.Frame(dlg, bg=THEME["bg_surface"], relief="sunken", bd=1)
        lb_frame.pack(fill="both", expand=True, padx=12, pady=4)

        lb = tk.Listbox(lb_frame, bg="white", fg="black", selectbackground=THEME["select_bg"], selectforeground="white", font=("Segoe UI", 9))
        lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lb_frame, orient="vertical", command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.config(yscrollcommand=sb.set)

        items = ["[ Moldes (Raiz / Sem Pasta) ]", "[ ➕ Criar Nova Pasta... ]"] + folders
        for it in items:
            lb.insert("end", f"  {it}")
        lb.selection_set(0)

        result = {"folder": None, "confirmed": False}

        def on_confirm():
            sel_idx = lb.curselection()
            if not sel_idx:
                return
            idx = sel_idx[0]
            if idx == 0:
                result["folder"] = ""
                result["confirmed"] = True
                dlg.destroy()
            elif idx == 1:
                new_name = simpledialog.askstring("Nova Pasta", "Nome da nova pasta de moldes:", initialvalue="Nova Pasta", parent=dlg)
                if new_name and new_name.strip():
                    folder_name = new_name.strip()
                    self.db.create_shape_folder(folder_name)
                    result["folder"] = folder_name
                    result["confirmed"] = True
                    dlg.destroy()
            else:
                result["folder"] = folders[idx - 2]
                result["confirmed"] = True
                dlg.destroy()

        lb.bind("<Double-Button-1>", lambda e: on_confirm())

        btn_box = tk.Frame(dlg, bg=THEME["bg_surface"], pady=10)
        btn_box.pack(fill="x", padx=12)

        tk.Button(
            btn_box,
            text="Confirmar",
            width=10,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            relief="raised",
            bd=2,
            font=("Segoe UI", 9, "bold"),
            command=on_confirm
        ).pack(side="right", padx=4)

        tk.Button(
            btn_box,
            text="Cancelar",
            width=10,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            relief="raised",
            bd=1,
            command=dlg.destroy
        ).pack(side="right", padx=4)

        self.wait_window(dlg)
        if result["confirmed"]:
            return result["folder"]
        return None

    def on_import_die(self, target_folder=None):
        """Abre caixa de diálogo para importar arquivo(s) de molde .die (formato ATOM) em massa."""
        if target_folder is None:
            target_folder = self.get_selected_folder()
            if not target_folder:
                folders = self.db.get_shape_folders()
                if folders:
                    chosen = self._prompt_choose_folder_for_import()
                    if chosen is None:
                        return
                    target_folder = chosen

        title_txt = f"Importar Shape(s) ATOM (.die) para pasta '{target_folder}'" if target_folder else "Importar Shape(s) ATOM (.die)"
        file_paths = filedialog.askopenfilenames(
            title=title_txt,
            filetypes=[
                ("Arquivos Shape ATOM (*.die, *.d)", ("*.die", "*.Die", "*.DIE", "*.d", "*.D")),
                ("Moldes ATOM (.die)", ("*.die", "*.Die", "*.DIE")),
                ("Sidecars ATOM (.d)", ("*.d", "*.D")),
                ("Arquivos Shape (*.die, *.d, *.shp, *.json)", ("*.die", "*.Die", "*.d", "*.D", "*.shp", "*.json")),
                ("Todos os Arquivos (*.*)", "*.*")
            ],
            parent=self
        )
        if not file_paths:
            return

        # Deduplicação inteligente de caminhos (.d vs .die/.Die selecionados juntos)
        normalized_paths = []
        path_set = set(os.path.normcase(os.path.abspath(p)) for p in file_paths)
        for p in file_paths:
            p_abs = os.path.abspath(p)
            p_lower = p_abs.lower()
            if p_lower.endswith(".d"):
                stem = p_abs[:-2]
                if (os.path.normcase(stem + ".die") in path_set or
                    os.path.normcase(stem + ".Die") in path_set):
                    continue
            normalized_paths.append(p)

        imported = []
        errors = []
        article_id = None
        if self.current_shapes and "article_id" in self.current_shapes[0]:
            article_id = self.current_shapes[0]["article_id"]
        else:
            try:
                orders = self.db.get_orders()
                if orders:
                    arts = self.db.get_articles_by_order(orders[0]["id"])
                    if arts:
                        article_id = arts[0]["id"]
            except Exception:
                pass

        for file_path in normalized_paths:
            try:
                shape_data = parse_die_file(file_path)
                s_name = shape_data["name"]
                s_size = shape_data.get("size", "41")

                existing = next((
                    s for s in self.current_shapes
                    if s.get("name", "").strip().lower() == s_name.strip().lower()
                    and (s.get("folder") or "") == (target_folder or "")
                ), None)

                if existing:
                    self.db.update_shape(
                        shape_id=existing["id"],
                        name=s_name,
                        contour=shape_data["contour"],
                        holes=shape_data.get("holes", []),
                        stitching=shape_data.get("stitching", []),
                        folder=target_folder or "",
                        size=s_size
                    )
                    clr = get_color_for_size(s_size or s_name)
                    shape_data["id"] = existing["id"]
                    shape_data["article_id"] = existing.get("article_id", article_id)
                    shape_data["color"] = clr
                    shape_data["folder"] = target_folder or ""
                    shape_data["size"] = s_size
                else:
                    clr = get_color_for_size(s_size or s_name)
                    new_id = self.db.create_shape(
                        article_id=article_id,
                        name=s_name,
                        color=clr,
                        contour=shape_data["contour"],
                        holes=shape_data.get("holes", []),
                        stitching=shape_data.get("stitching", []),
                        folder=target_folder or "",
                        size=s_size
                    )
                    shape_data["id"] = new_id
                    shape_data["article_id"] = article_id
                    shape_data["color"] = clr
                    shape_data["folder"] = target_folder or ""
                    shape_data["size"] = s_size

                imported.append(shape_data)
            except Exception as e:
                errors.append(f"{Path(file_path).name}: {str(e)}")

        if imported:
            self.reload_shapes()

            # Força a exibição do modo Moldes para que a pasta e os novos moldes apareçam imediatamente na árvore
            self.switch_tree_mode("shapes")
            if target_folder:
                self.select_folder_node(target_folder)

            # Se uma janela de Sessão estiver aberta e visível, adiciona os novos moldes diretamente à sessão
            sess_is_active = hasattr(self, "session_view") and self.session_view and self.session_view.winfo_ismapped()
            if sess_is_active:
                for shp in imported:
                    self.session_view.add_shape(shp)
                try:
                    self.session_view.notebook.select(1)  # Mantém foco na Aba Moldes
                except Exception:
                    pass

            # Se o Shape Editor estiver ativo, carrega nele; se não houver janela ativa, exibe o Shape Editor
            if hasattr(self, "shape_editor_view") and self.shape_editor_view and self.shape_editor_view.winfo_ismapped() and self.active_child == self.shape_editor_view:
                self.shape_editor_view.load_shape(imported[0])
            elif not sess_is_active:
                self.show_shape_editor(imported[0])

            folder_info = f" na pasta '{target_folder}'" if target_folder else " na raiz de Moldes"
            if len(imported) == 1:
                s = imported[0]
                msg = (
                    f"Molde '{s['name']}' importado com sucesso{folder_info}!\n\n"
                    f"Arquivo: {Path(normalized_paths[0]).name}\n"
                    f"Vértices: {len(s['contour'])}\n"
                    f"Furos: {len(s.get('holes', []))}\n"
                    f"Tamanho/Taglia: {s.get('size', '41')}"
                )
            else:
                nomes_preview = ", ".join(s["name"] for s in imported[:6])
                if len(imported) > 6:
                    nomes_preview += f" ... (+{len(imported)-6} outros)"
                msg = f"{len(imported)} moldes importados com sucesso{folder_info}!\n\n({nomes_preview})"

            if errors:
                msg += f"\n\nFalhas em {len(errors)} arquivo(s):\n" + "\n".join(errors)

            self.lbl_status_msg.config(text=f"{len(imported)} molde(s) importado(s){folder_info}.")
            messagebox.showinfo("Importar Shape (.die)", msg, parent=self)
        elif errors:
            messagebox.showerror("Erro na Importação", "Falha ao importar molde(s):\n" + "\n".join(errors), parent=self)

    def on_open_lay_file(self):
        """Abre e importa um arquivo de layout .lay no Layout Editor e sincroniza com a sessão ativa."""
        self.show_layout_editor(force=True)
        if hasattr(self, "layout_editor_view") and self.layout_editor_view:
            self.layout_editor_view.open_layout_dialog()

    def on_export_lay_file(self):
        """Exporta o layout atual para arquivo .lay compatível com fn98/dp98 e mesa ATOM CNC."""
        if hasattr(self, "layout_editor_view") and self.layout_editor_view:
            self.layout_editor_view.export_layout_dialog()

    def close_child_window(self):
        if self.active_child:
            self.close_window(self.active_child)
        else:
            self.lbl_status_msg.config(text="Job Manager está pronto")

    # =========================================================================
    # 4. Status Bar Autêntica WinXP (idêntica ao print do usuário)
    # =========================================================================
    def create_status_bar(self):
        sbar = tk.Frame(self, bg=THEME["bg_surface"], height=22, padx=1, pady=1, relief="sunken", borderwidth=1)
        sbar.pack(side="bottom", fill="x")

        # Painel 1: "Status"
        p1 = tk.Frame(sbar, relief="sunken", bd=1, bg=THEME["bg_surface"], padx=5, pady=1)
        p1.pack(side="left", padx=1)
        tk.Label(p1, text="Status", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8)).pack()

        # Painel 2: Hora atual formatada HH:MM
        p2 = tk.Frame(sbar, relief="sunken", bd=1, bg=THEME["bg_surface"], padx=6, pady=1)
        p2.pack(side="left", padx=1)
        now_time = datetime.datetime.now().strftime("%H:%M")
        self.lbl_time = tk.Label(p2, text=now_time, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8))
        self.lbl_time.pack()

        # Painel 3: Data atual formatada DD/MM/AAAA
        p3 = tk.Frame(sbar, relief="sunken", bd=1, bg=THEME["bg_surface"], padx=6, pady=1)
        p3.pack(side="left", padx=1)
        now_date = datetime.datetime.now().strftime("%d/%m/%Y")
        tk.Label(p3, text=now_date, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8)).pack()

        # Painéis 4, 5, 6: 3 LEDs ovais roxos separados (Dongle de segurança ATOM)
        for _ in range(3):
            p_led = tk.Frame(sbar, relief="sunken", bd=1, bg=THEME["bg_surface"], padx=4, pady=1)
            p_led.pack(side="left", padx=1)
            tk.Label(p_led, text="⬭", bg=THEME["bg_surface"], fg="#a21caf", font=("Segoe UI", 8, "bold")).pack()

        # Painel 7: Mensagem do sistema
        p7 = tk.Frame(sbar, relief="sunken", bd=1, bg=THEME["bg_surface"], padx=8, pady=1)
        p7.pack(side="left", fill="x", expand=True, padx=1)
        self.lbl_status_msg = tk.Label(p7, text="Job Manager está pronto", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), anchor="w")
        self.lbl_status_msg.pack(fill="x")

        # Painel 8: Espaçador rebaixado no final da barra
        p8 = tk.Frame(sbar, relief="sunken", bd=1, bg=THEME["bg_surface"], width=20, pady=1)
        p8.pack(side="right", padx=1)

    # =========================================================================
    # Lógica de Carregamento e Alternância de Modos (Prints 1, 2 e 3)
    # =========================================================================
    def reload_shapes(self):
        """Recarrega os moldes do banco de dados e sincroniza o catálogo com as views."""
        shapes = self.db.get_all_shapes()
        self.current_shapes = shapes if shapes is not None else []
        for sv in self.open_sessions.values():
            sv.all_shapes_catalog = self.current_shapes

    def load_initial_data(self):
        self.orders = self.db.get_orders()
        if self.orders:
            self.current_order = self.orders[0]

        # Carrega sessões salvas no banco de dados e exibe a sessão padrão na área de trabalho
        self.sessions = self.db.get_sessions()
        if self.sessions:
            sess_91 = next((s for s in self.sessions if s["id"] == 91), None)
            self.current_session = sess_91 or self.sessions[0]
            if self.current_session.get("placed_pieces"):
                self.canvas.placed_pieces = [dict(p) for p in self.current_session["placed_pieces"]]
                self.canvas.redraw()
            self.show_session_window(self.current_session)

        self.reload_shapes()

        if not self.current_shapes:
            for ord_item in self.orders:
                articles = self.db.get_articles_by_order(ord_item["id"])
                if articles:
                    self.current_shapes = self.db.get_shapes_by_article(articles[0]["id"])
                    break
            for sv in self.open_sessions.values():
                sv.all_shapes_catalog = self.current_shapes

        if self.current_material:
            self.canvas.set_material(self.current_material)

        if self.current_session:
            self.update_all_metrics()

        # Inicia no modo Produção (Print 1)
        self.switch_tree_mode("jobs")

    def switch_tree_mode(self, mode):
        self.current_mode = mode
        self.tree_main.delete(*self.tree_main.get_children())

        self.grid_lower.delete(*self.grid_lower.get_children())

        # Reset dos 3 botões visuais
        self.btn_mode_jobs.config(relief="raised", bg=THEME["bg_surface"])
        self.btn_mode_shapes.config(relief="raised", bg=THEME["bg_surface"])
        self.btn_mode_materials.config(relief="raised", bg=THEME["bg_surface"])

        if mode == "jobs":
            # -------------------------------------------------------------
            # MODO 1: Produção (Prints 1 e media_1791842155312.png)
            # -------------------------------------------------------------
            self.btn_mode_jobs.config(relief="sunken", bg=THEME["bg_hover"])

            # Configura colunas do Grid: SessId | Produção | Nome sessão | Status
            self.grid_lower["columns"] = ("sess_id", "prod", "nome", "status")
            self.grid_lower.heading("sess_id", text="SessId", command=lambda: self.sort_grid_lower("sess_id"))
            self.grid_lower.heading("prod", text="Produção", command=lambda: self.sort_grid_lower("prod"))
            self.grid_lower.heading("nome", text="Nome sessão", command=lambda: self.sort_grid_lower("nome"))
            self.grid_lower.heading("status", text="Status", command=lambda: self.sort_grid_lower("status"))

            self.grid_lower.column("sess_id", width=50, anchor="center")
            self.grid_lower.column("prod", width=80, anchor="w")
            self.grid_lower.column("nome", width=110, anchor="w")
            self.grid_lower.column("status", width=65, anchor="center")

            # Árvore: Nó raiz Produção com ícone de PC e nós de pastas de Produção com ícone de pasta amarela
            img_root = {"image": self.icons["node_base"]} if self.icons.get("node_base") else {}
            root = self.tree_main.insert("", "end", text=" Produção", open=True, values=("root_production", ""), **img_root)

            img_folder = {"image": self.icons["job_folder"]} if self.icons.get("job_folder") else {}
            img_order = {"image": self.icons["job_order"]} if self.icons.get("job_order") else {}
            img_sess = {"image": self.icons["job_session"]} if self.icons.get("job_session") else {}

            # Carrega pastas de produção do banco
            job_folders = self.db.get_job_folders()

            # Se não houver pastas no banco e existirem sessões ou pedidos, assegura a pasta padrão
            if not job_folders and (self.sessions or self.orders):
                self.db.create_job_folder("ProduçãoNova")
                job_folders = ["ProduçãoNova"]

            folder_nodes = {}

            def get_or_create_job_node(j_path):
                j_path = (j_path or "").strip().strip("/")
                if not j_path:
                    return root
                parts = [p.strip() for p in j_path.split("/") if p.strip()]
                curr_parent = root
                curr_path = ""
                for part in parts:
                    curr_path = f"{curr_path}/{part}" if curr_path else part
                    if curr_path not in folder_nodes:
                        fn_id = self.tree_main.insert(curr_parent, "end", text=f" {part}", open=True, values=("job_folder", curr_path), **img_folder)
                        folder_nodes[curr_path] = fn_id
                    curr_parent = folder_nodes[curr_path]
                return curr_parent

            for j_name in job_folders:
                get_or_create_job_node(j_name)

            first_parent = folder_nodes[job_folders[0]] if (job_folders and job_folders[0] in folder_nodes) else root

            # Insere pedidos/ordens dinamicamente
            for ord_item in self.orders:
                o_id = ord_item["id"]
                o_name = ord_item.get("name") or (f"Derby Masculino #41" if o_id == 1 else f"Pedido #{o_id}")
                self.tree_main.insert(first_parent, "end", text=f" {o_name}", values=("order", o_id), **img_order)

            # Insere as sessões dinamicamente
            selected_sess_item = None
            for sess in self.sessions:
                s_id = sess["id"]
                s_name = sess.get("name", f"Sessão #{s_id}")
                s_status = sess.get("status", "Stand by")
                s_job = (sess.get("job") or "").strip().strip("/") or (job_folders[0] if job_folders else "ProduçãoNova")

                # Assegura que o nó da pasta (e eventuais ancestrais) existe
                parent_node = get_or_create_job_node(s_job)

                # Formatação do rótulo na árvore
                disp_name = clean_session_display_name(s_name)
                if not disp_name or disp_name == f"(#{s_id})":
                    disp_name = f"Sessão #{s_id}"
                node_text = f" {disp_name}"

                item_id = self.tree_main.insert(parent_node, "end", text=node_text, values=("session", s_id), **img_sess)
                if self.current_session and self.current_session.get("id") == s_id:
                    selected_sess_item = item_id

                # Alimenta grid inferior: SessId preserva o ID original e Name exibe o nome limpo
                self.grid_lower.insert("", "end", values=(str(s_id), s_job, disp_name, s_status))

            # Seleciona o item da sessão ativa ou primeira pasta ou raiz
            if selected_sess_item:
                self.tree_main.selection_set(selected_sess_item)
            elif job_folders and job_folders[0] in folder_nodes:
                self.tree_main.selection_set(folder_nodes[job_folders[0]])
            else:
                self.tree_main.selection_set(root)

        elif mode == "shapes":
            # -------------------------------------------------------------
            # MODO 2: Moldes (Print 2 com suporte completo a Pastas)
            # -------------------------------------------------------------
            self.btn_mode_shapes.config(relief="sunken", bg=THEME["bg_hover"])

            # Configura colunas do Grid: ShapeId | Percurso | Nome | Tamanho | Pasta
            self.grid_lower["columns"] = ("shape_id", "percurso", "nome", "tamanho", "pasta")
            self.grid_lower.heading("shape_id", text="ShapeId", command=lambda: self.sort_grid_lower("shape_id"))
            self.grid_lower.heading("percurso", text="Percurso", command=lambda: self.sort_grid_lower("percurso"))
            self.grid_lower.heading("nome", text="Nome", command=lambda: self.sort_grid_lower("nome"))
            self.grid_lower.heading("tamanho", text="Tamanho", command=lambda: self.sort_grid_lower("tamanho"))
            self.grid_lower.heading("pasta", text="Pasta", command=lambda: self.sort_grid_lower("pasta"))

            self.grid_lower.column("shape_id", width=55, anchor="center")
            self.grid_lower.column("percurso", width=70, anchor="w")
            self.grid_lower.column("nome", width=120, anchor="w")
            self.grid_lower.column("tamanho", width=55, anchor="center")
            self.grid_lower.column("pasta", width=85, anchor="w")

            # Árvore: Nó raiz Moldes com ícone autêntico
            img_shp = {"image": self.icons["shp_base"]} if self.icons.get("shp_base") else {}
            img_folder = {"image": self.icons["job_folder"]} if self.icons.get("job_folder") else {}

            root = self.tree_main.insert("", "end", text=" Moldes", open=True, values=("root_shapes", ""), **img_shp)

            # 1. Carrega pastas cadastradas de forma hierárquica (suporte a subpastas)
            folders = self.db.get_shape_folders()
            folder_nodes = {}

            def get_or_create_folder_node(f_path):
                f_path = f_path.strip().strip("/")
                if not f_path:
                    return root
                parts = [p.strip() for p in f_path.split("/") if p.strip()]
                curr_parent = root
                curr_path = ""
                for part in parts:
                    curr_path = f"{curr_path}/{part}" if curr_path else part
                    if curr_path not in folder_nodes:
                        fn_id = self.tree_main.insert(curr_parent, "end", text=f" {part}", open=True, values=("folder", curr_path), **img_folder)
                        folder_nodes[curr_path] = fn_id
                    curr_parent = folder_nodes[curr_path]
                return curr_parent

            for f_name in folders:
                get_or_create_folder_node(f_name)

            # 2. Adiciona os moldes sob sua respectiva pasta ou diretamente na raiz
            for s in self.current_shapes:
                s_folder = s.get("folder", "").strip().strip("/")
                parent = get_or_create_folder_node(s_folder) if s_folder else root

                self.tree_main.insert(parent, "end", text=f" {s['name']}", values=("shape", s["id"], s_folder), **img_shp)
                self.grid_lower.insert("", "end", values=(s["id"], "Externo", s["name"], s.get("size", "41"), s_folder or "-"))

            # Seleciona nó raiz com destaque azul clássico
            self.tree_main.selection_set(root)

        elif mode == "materials":
            # -------------------------------------------------------------
            # MODO 3: Estoque de material (Print 3)
            # -------------------------------------------------------------
            self.btn_mode_materials.config(relief="sunken", bg=THEME["bg_hover"])

            # Configura colunas do Grid: Cod. Mat. | Partida | Definição | Comprimento (m) | Largura (m)
            self.grid_lower["columns"] = ("cod_mat", "partida", "definicao", "comprimento", "largura")
            self.grid_lower.heading("cod_mat", text="Cod. Mat.", command=lambda: self.sort_grid_lower("cod_mat"))
            self.grid_lower.heading("partida", text="Partida", command=lambda: self.sort_grid_lower("partida"))
            self.grid_lower.heading("definicao", text="Definição", command=lambda: self.sort_grid_lower("definicao"))
            self.grid_lower.heading("comprimento", text="Comprimento (m)", command=lambda: self.sort_grid_lower("comprimento"))
            self.grid_lower.heading("largura", text="Largura (m)", command=lambda: self.sort_grid_lower("largura"))

            self.grid_lower.column("cod_mat", width=75, anchor="w")
            self.grid_lower.column("partida", width=55, anchor="center")
            self.grid_lower.column("definicao", width=95, anchor="w")
            self.grid_lower.column("comprimento", width=105, anchor="center")
            self.grid_lower.column("largura", width=85, anchor="center")

            # Árvore: Nó raiz Estoque de material com ícone autêntico
            img_mat = {"image": self.icons["mat_base"]} if self.icons.get("mat_base") else {}
            root = self.tree_main.insert("", "end", text=" Estoque de material", open=True, values=("root_materials", ""), **img_mat)
            for m in self.materials:
                self.tree_main.insert(root, "end", text=f" {m['id']}", values=("material", m["id"]), **img_mat)
                w_m = f"{m.get('width_mm', 1380.0)/1000.0:.2f}m".replace(".", ",")
                h_m = f"{m.get('height_mm', 2980.0)/1000.0:.2f}m".replace(".", ",")
                t_def = m.get("type", "como placa").capitalize()
                self.grid_lower.insert("", "end", iid=m["id"], values=(m["id"], "1", t_def, h_m, w_m))

            # Seleciona nó raiz com destaque azul clássico
            self.tree_main.selection_set(root)

    populate_tree = switch_tree_mode

    def _is_inside_menu(self, menu, x_root, y_root):
        if not menu:
            return False
        try:
            if not menu.winfo_exists() or not menu.winfo_ismapped():
                return False
            mx = menu.winfo_rootx()
            my = menu.winfo_rooty()
            mw = menu.winfo_width()
            mh = menu.winfo_height()
            return (mx <= x_root <= mx + mw) and (my <= y_root <= my + mh)
        except Exception:
            return False

    def show_popup_menu(self, menu, x_root, y_root):
        """Abre menu de contexto garantindo que qualquer outro anterior seja fechado."""
        self._last_popup_time = time.time()
        self.dismiss_popup_menus()
        self._active_popup_menu = menu
        try:
            menu.tk_popup(x_root, y_root)
        except Exception:
            pass

    def dismiss_popup_menus(self, event=None):
        """Fecha qualquer menu de contexto ativo ao clicar fora ou teclar Escape."""
        if event and hasattr(event, "x_root") and hasattr(event, "y_root"):
            # Se for clique com botão 3 disparado logo ao abrir menu, não desfaz imediatamente
            if getattr(event, "num", None) == 3 and (time.time() - getattr(self, "_last_popup_time", 0)) < 0.08:
                return

            xr, yr = event.x_root, event.y_root
            # Se o clique ocorreu dentro de um menu aberto, permite o acionamento do item
            for m in (getattr(self, "_active_popup_menu", None),
                      getattr(self, "tree_menu", None),
                      getattr(self, "moldes_menu", None),
                      getattr(self, "materials_menu", None)):
                if self._is_inside_menu(m, xr, yr):
                    return
            for s_view in getattr(self, "open_sessions", {}).values():
                if hasattr(s_view, "_active_mat_menu") and self._is_inside_menu(s_view._active_mat_menu, xr, yr):
                    return
            if hasattr(self, "shape_editor_view") and hasattr(self.shape_editor_view, "ctx_menu"):
                if self._is_inside_menu(self.shape_editor_view.ctx_menu, xr, yr):
                    return
            if hasattr(self, "material_codes_view") and hasattr(self.material_codes_view, "ctx_menu"):
                if self._is_inside_menu(self.material_codes_view.ctx_menu, xr, yr):
                    return

        # Desfaz e esconde todos os menus
        for m in (getattr(self, "_active_popup_menu", None),
                  getattr(self, "tree_menu", None),
                  getattr(self, "moldes_menu", None),
                  getattr(self, "materials_menu", None)):
            if m:
                try:
                    m.grab_release()
                except Exception:
                    pass
                try:
                    m.unpost()
                except Exception:
                    pass
        self._active_popup_menu = None

        for s_view in getattr(self, "open_sessions", {}).values():
            if hasattr(s_view, "dismiss_context_menu"):
                s_view.dismiss_context_menu()
        if hasattr(self, "shape_editor_view") and hasattr(self.shape_editor_view, "dismiss_context_menu"):
            self.shape_editor_view.dismiss_context_menu()
        if hasattr(self, "material_codes_view") and hasattr(self.material_codes_view, "ctx_menu"):
            try:
                self.material_codes_view.ctx_menu.unpost()
            except Exception:
                pass

    def show_materials_button_menu(self, event):
        self.materials_menu.delete(0, "end")
        self.materials_menu.add_command(label="Criar material...", command=self.on_create_material)
        self.materials_menu.add_command(label="Listagem de materiais...", command=self.show_material_codes_window)
        self.materials_menu.add_separator()
        self.materials_menu.add_command(label="Atualizar Estoque", command=lambda: self.switch_tree_mode("materials"))
        self.show_popup_menu(self.materials_menu, event.x_root, event.y_root)

    def show_tree_context_menu(self, event):
        iid = self.tree_main.identify_row(event.y)
        sel = self.tree_main.selection()
        if iid:
            if iid not in sel:
                self.tree_main.selection_set(iid)
                sel = (iid,)
            vals = self.tree_main.item(iid, "values")
        else:
            if sel:
                iid = sel[0]
                vals = self.tree_main.item(iid, "values")
            else:
                vals = ()

        # Se estiver no modo Estoque de material ou o nó selecionado for do estoque de material:
        if self.current_mode == "materials" or (vals and vals[0] in ("root_materials", "material")):
            self.materials_menu.delete(0, "end")
            mats_sel = []
            for item_id in sel:
                v = self.tree_main.item(item_id, "values")
                if v and len(v) >= 2 and v[0] == "material":
                    mats_sel.append((item_id, str(v[1])))

            if mats_sel:
                if len(mats_sel) == 1:
                    mat_id = mats_sel[0][1]
                    self.materials_menu.add_command(
                        label="Aplicar à Sessão",
                        command=lambda m=mat_id: self.apply_material_to_session(m)
                    )
                    self.materials_menu.add_command(
                        label="Criar material...",
                        command=self.on_create_material
                    )
                    self.materials_menu.add_command(
                        label="Listagem de materiais...",
                        command=self.show_material_codes_window
                    )
                    self.materials_menu.add_separator()
                    self.materials_menu.add_command(
                        label="Excluir Material",
                        accelerator="Del",
                        command=self.on_delete_tree_item
                    )
                    self.materials_menu.add_command(
                        label="Excluir",
                        command=self.on_delete_tree_item
                    )
                else:
                    self.materials_menu.add_command(
                        label="Criar material...",
                        command=self.on_create_material
                    )
                    self.materials_menu.add_command(
                        label="Listagem de materiais...",
                        command=self.show_material_codes_window
                    )
                    self.materials_menu.add_separator()
                    self.materials_menu.add_command(
                        label=f"Excluir ({len(mats_sel)} materiais)",
                        accelerator="Del",
                        command=self.on_delete_tree_item
                    )
                    self.materials_menu.add_command(
                        label="Excluir",
                        command=self.on_delete_tree_item
                    )
            else:
                self.materials_menu.add_command(
                    label="Criar material...",
                    command=self.on_create_material
                )
                self.materials_menu.add_command(
                    label="Listagem de materiais...",
                    command=self.show_material_codes_window
                )
                self.materials_menu.add_separator()
                self.materials_menu.add_command(
                    label="Atualizar Estoque",
                    command=lambda: self.switch_tree_mode("materials")
                )

            self.show_popup_menu(self.materials_menu, event.x_root, event.y_root)
            return

        if self.current_mode == "shapes":
            self.moldes_menu.delete(0, "end")
            node_type = vals[0] if vals else "root_shapes"

            if node_type == "folder":
                folder_name = str(vals[1])
                disp_name = folder_name.split("/")[-1]
                self.moldes_menu.add_command(
                    label="📂 Importar Shape (.die) nesta pasta...",
                    command=lambda f=folder_name: self.on_import_die(target_folder=f)
                )
                self.moldes_menu.add_command(
                    label=f"📁 Criar Subpasta em '{disp_name}'...",
                    command=lambda f=folder_name: self.on_create_shape_subfolder(f)
                )
                self.moldes_menu.add_command(
                    label="📁 Criar Pasta na Raiz...",
                    command=lambda: self.on_create_shape_folder(parent_folder="")
                )
                self.moldes_menu.add_separator()
                self.moldes_menu.add_command(
                    label="✏️ Renomear Pasta...",
                    command=lambda f=folder_name: self.on_rename_shape_folder(f)
                )
                self.moldes_menu.add_command(
                    label="🗑️ Excluir Pasta...",
                    command=lambda f=folder_name: self.on_delete_shape_folder(f)
                )
                self.moldes_menu.add_separator()
                self.moldes_menu.add_command(
                    label="🔄 Atualizar Moldes",
                    command=lambda: self.switch_tree_mode("shapes")
                )

            elif node_type == "shape":
                shape_id = int(vals[1])
                self.moldes_menu.add_command(
                    label="📐 Abrir no Shape Editor",
                    command=lambda s=shape_id: self.show_shape_editor(s)
                )
                self.moldes_menu.add_command(
                    label="📤 Exportar como .die...",
                    command=lambda s=shape_id: self.on_export_shape_die(s)
                )
                self.moldes_menu.add_separator()
                self.moldes_menu.add_command(
                    label="📁 Mover para Pasta...",
                    command=lambda s=shape_id: self.on_move_shape_to_folder(s)
                )
                self.moldes_menu.add_command(
                    label="✏️ Renomear Molde...",
                    command=lambda s=shape_id: self.on_rename_shape(s)
                )
                self.moldes_menu.add_command(
                    label="🗑️ Excluir Molde...",
                    command=self.on_delete_tree_item
                )
                self.moldes_menu.add_command(
                    label="Excluir\tDel",
                    command=self.on_delete_tree_item
                )
                self.moldes_menu.add_separator()
                self.moldes_menu.add_command(
                    label="🔄 Atualizar Moldes",
                    command=lambda: self.switch_tree_mode("shapes")
                )

            else:  # root_shapes ou espaço vazio
                self.moldes_menu.add_command(
                    label="📁 Criar Pasta de Moldes...",
                    command=self.on_create_shape_folder
                )
                self.moldes_menu.add_command(
                    label="📂 Importar Shape (.die)...",
                    command=lambda: self.on_import_die(target_folder="")
                )
                self.moldes_menu.add_separator()
                self.moldes_menu.add_command(
                    label="🔄 Atualizar Moldes",
                    command=lambda: self.switch_tree_mode("shapes")
                )

            self.show_popup_menu(self.moldes_menu, event.x_root, event.y_root)

        else:
            # Modo Produção (Print 1)
            self.tree_menu.delete(0, "end")
            sel = self.tree_main.selection()
            if len(sel) > 1:
                sess_count = sum(1 for item in sel if self.tree_main.item(item, "values") and len(self.tree_main.item(item, "values")) >= 2 and self.tree_main.item(item, "values")[0] == "session")
                lbl_del = f"Excluir ({sess_count} sessões)" if sess_count > 0 else f"Excluir ({len(sel)} selecionados)"
                self.tree_menu.add_command(label="Abrir", state="disabled")
                self.tree_menu.add_separator()
                self.tree_menu.add_command(label=lbl_del, command=self.on_delete_tree_item)
            else:
                vals = self.tree_main.item(sel[0], "values") if sel else ()
                node_type = vals[0] if vals else "root_production"

                if node_type == "job_folder":
                    folder_path = str(vals[1])
                    disp_name = folder_path.split("/")[-1]
                    self.tree_menu.add_command(label="Abrir", command=self.on_tree_menu_open)
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label=f"📁 Criar Subpasta em '{disp_name}'...", command=lambda f=folder_path: self.on_create_job_subfolder(f))
                    self.tree_menu.add_command(label="📁 Criar Produção na Raiz...", command=lambda: self.on_create_production(parent_folder=""))
                    self.tree_menu.add_command(label=f"Criar sessão em '{disp_name}'", command=self.on_new_session)
                    self.tree_menu.add_command(label="Criar pedido", command=self.on_create_order)
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="Explodir", state="disabled")
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="Renomear", command=self.on_rename_tree_item)
                    self.tree_menu.add_command(label="Excluir", command=self.on_delete_tree_item)
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="Publish", command=self.on_publish)
                    self.tree_menu.add_command(label="Export as xml...", command=self.on_export_xml)
                    self.tree_menu.add_command(label="Import xml here...", command=self.on_import_xml)
                    self.tree_menu.add_command(label="Importar Shape (.die)...", command=self.on_import_die)
                    self.tree_menu.add_command(label="🧩 Abrir no Layout Editor...", command=self.show_layout_editor)

                elif node_type == "session":
                    sess_id = int(vals[1])
                    self.tree_menu.add_command(label="Abrir", command=self.on_tree_menu_open)
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="Criar sessão", command=self.on_new_session)
                    self.tree_menu.add_command(label="Criar pedido", command=self.on_create_order)
                    self.tree_menu.add_command(label="📁 Criar Produção...", command=self.on_create_production)
                    self.tree_menu.add_command(label="📁 Criar Subpasta de Produção...", command=self.on_create_job_subfolder_menu_action)
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="📁 Mover para Pasta de Produção...", command=lambda s=sess_id: self.on_move_session_to_job_folder(s))
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="Explodir", state="disabled")
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="Renomear", command=self.on_rename_tree_item)
                    self.tree_menu.add_command(label="Excluir", command=self.on_delete_tree_item)
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="Publish", command=self.on_publish)
                    self.tree_menu.add_command(label="Export as xml...", command=self.on_export_xml)
                    self.tree_menu.add_command(label="Import xml here...", command=self.on_import_xml)
                    self.tree_menu.add_command(label="Importar Shape (.die)...", command=self.on_import_die)
                    self.tree_menu.add_command(label="🧩 Abrir no Layout Editor...", command=self.show_layout_editor)

                elif node_type == "order":
                    order_id = int(vals[1])
                    self.tree_menu.add_command(label="Abrir", command=self.on_tree_menu_open)
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="Renomear", command=self.on_rename_tree_item)
                    self.tree_menu.add_command(label="Excluir Artigo", command=self.on_delete_tree_item)
                    self.tree_menu.add_command(label="Excluir", command=self.on_delete_tree_item)

                else:  # root_production ou outros
                    self.tree_menu.add_command(label="Abrir", state="disabled")
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="📁 Criar Produção...", command=lambda: self.on_create_production(parent_folder=""))
                    self.tree_menu.add_command(label="📁 Criar Subpasta de Produção...", command=self.on_create_job_subfolder_menu_action)
                    self.tree_menu.add_command(label="Criar sessão", command=self.on_new_session)
                    self.tree_menu.add_command(label="Criar pedido", command=self.on_create_order)
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="Explodir", state="disabled")
                    self.tree_menu.add_separator()
                    self.tree_menu.add_command(label="Publish", command=self.on_publish)
                    self.tree_menu.add_command(label="Export as xml...", command=self.on_export_xml)
                    self.tree_menu.add_command(label="Import xml here...", command=self.on_import_xml)
                    self.tree_menu.add_command(label="Importar Shape (.die)...", command=self.on_import_die)
                    self.tree_menu.add_command(label="🧩 Abrir no Layout Editor...", command=self.show_layout_editor)

            self.show_popup_menu(self.tree_menu, event.x_root, event.y_root)

    def show_grid_context_menu(self, event):
        iid = self.grid_lower.identify_row(event.y)
        sel = self.grid_lower.selection()
        if iid:
            if iid not in sel:
                self.grid_lower.selection_set(iid)
                sel = (iid,)
        if self.current_mode == "materials":
            self.materials_menu.delete(0, "end")
            sel = self.grid_lower.selection()
            if sel:
                if len(sel) == 1:
                    gvals = self.grid_lower.item(sel[0], "values")
                    mat_id = str(gvals[0]) if gvals else str(sel[0])
                    self.materials_menu.add_command(
                        label="Aplicar à Sessão",
                        command=lambda m=mat_id: self.apply_material_to_session(m)
                    )
                    self.materials_menu.add_command(
                        label="Criar material...",
                        command=self.on_create_material
                    )
                    self.materials_menu.add_command(
                        label="Listagem de materiais...",
                        command=self.show_material_codes_window
                    )
                    self.materials_menu.add_separator()
                    self.materials_menu.add_command(
                        label="Excluir Material",
                        accelerator="Del",
                        command=self.on_delete_grid_item
                    )
                    self.materials_menu.add_command(
                        label="Excluir",
                        command=self.on_delete_grid_item
                    )
                else:
                    self.materials_menu.add_command(
                        label="Criar material...",
                        command=self.on_create_material
                    )
                    self.materials_menu.add_command(
                        label="Listagem de materiais...",
                        command=self.show_material_codes_window
                    )
                    self.materials_menu.add_separator()
                    self.materials_menu.add_command(
                        label=f"Excluir ({len(sel)} materiais)",
                        accelerator="Del",
                        command=self.on_delete_grid_item
                    )
                    self.materials_menu.add_command(
                        label="Excluir",
                        command=self.on_delete_grid_item
                    )
            else:
                self.materials_menu.add_command(
                    label="Criar material...",
                    command=self.on_create_material
                )
                self.materials_menu.add_command(
                    label="Listagem de materiais...",
                    command=self.show_material_codes_window
                )
                self.materials_menu.add_separator()
                self.materials_menu.add_command(
                    label="Atualizar Estoque",
                    command=lambda: self.switch_tree_mode("materials")
                )
            self.show_popup_menu(self.materials_menu, event.x_root, event.y_root)
            return
        elif self.current_mode == "shapes":
            sel = self.grid_lower.selection()
            if sel:
                gvals = self.grid_lower.item(sel[0], "values")
                if gvals:
                    try:
                        shp_id = int(gvals[0])
                        self.moldes_menu.delete(0, "end")
                        self.moldes_menu.add_command(
                            label="📐 Abrir no Shape Editor",
                            command=lambda s=shp_id: self.show_shape_editor(s)
                        )
                        self.moldes_menu.add_command(
                            label="📤 Exportar como .die...",
                            command=lambda s=shp_id: self.on_export_shape_die(s)
                        )
                        self.moldes_menu.add_separator()
                        self.moldes_menu.add_command(
                            label="📁 Mover para Pasta...",
                            command=lambda s=shp_id: self.on_move_shape_to_folder(s)
                        )
                        self.moldes_menu.add_command(
                            label="✏️ Renomear Molde...",
                            command=lambda s=shp_id: self.on_rename_shape(s)
                        )
                        self.moldes_menu.add_command(
                            label="🗑️ Excluir Molde...",
                            command=lambda s=shp_id: self.on_delete_shape(s)
                        )
                        self.moldes_menu.add_command(
                            label="Excluir\tDel",
                            command=lambda s=shp_id: self.on_delete_shape(s)
                        )
                        self.moldes_menu.add_separator()
                        self.moldes_menu.add_command(
                            label="🔄 Atualizar Moldes",
                            command=lambda: self.switch_tree_mode("shapes")
                        )
                    except Exception:
                        pass
            self.show_popup_menu(self.moldes_menu, event.x_root, event.y_root)
        elif self.current_mode == "jobs":
            sel = self.grid_lower.selection()
            if len(sel) > 1:
                self.tree_menu.entryconfig("Abrir", state="disabled")
                self.tree_menu.entryconfig("Renomear", state="disabled")
                self.tree_menu.entryconfig("Excluir", state="normal", label=f"Excluir ({len(sel)} sessões)", command=self.on_delete_grid_item)
            else:
                self.tree_menu.entryconfig("Abrir", state="normal", label="Abrir", command=self.on_tree_menu_open)
                self.tree_menu.entryconfig("Renomear", state="normal")
                self.tree_menu.entryconfig("Excluir", state="normal", label="Excluir", command=self.on_delete_grid_item)
            self.show_popup_menu(self.tree_menu, event.x_root, event.y_root)

    def sort_grid_lower(self, col):
        """Classifica os itens visíveis no grid inferior pelo cabeçalho clicado (alternando maior/menor)."""
        children = self.grid_lower.get_children("")
        if not children:
            return

        if not hasattr(self, "_grid_sort_state"):
            self._grid_sort_state = {}

        curr = self._grid_sort_state.get(col, None)
        if curr is None:
            # Padrão: maior para o menor para tamanho, nome, comprimento, largura
            desc = True if col in ("tamanho", "nome", "comprimento", "largura") else False
        else:
            desc = not curr
        self._grid_sort_state[col] = desc

        cols = list(self.grid_lower["columns"])
        if col not in cols:
            return
        col_idx = cols.index(col)

        def get_sort_key(item_id):
            vals = self.grid_lower.item(item_id, "values")
            val = vals[col_idx] if col_idx < len(vals) else ""
            if col == "tamanho":
                name_val = vals[2] if len(vals) > 2 else ""
                return size_sort_key(val, name_val)
            elif col in ("nome", "pasta", "percurso", "prod", "definicao", "status"):
                return natural_sort_key(val)
            elif col in ("shape_id", "sess_id", "partida"):
                try:
                    return (0, int(val), "")
                except Exception:
                    return (1, 0, str(val))
            elif col in ("comprimento", "largura"):
                try:
                    return (0, float(str(val).replace(",", ".")), "")
                except Exception:
                    return (1, 0, str(val))
            return natural_sort_key(val)

        items_sorted = sorted(children, key=get_sort_key, reverse=desc)
        for idx, k in enumerate(items_sorted):
            self.grid_lower.move(k, "", idx)

        # Atualiza indicador de seta ▲ / ▼ no cabeçalho
        arrow = " ▼" if desc else " ▲"
        for c in cols:
            base_txt = self.grid_lower.heading(c, "text").rstrip(" ▲▼")
            if c == col:
                self.grid_lower.heading(c, text=base_txt + arrow)
            else:
                self.grid_lower.heading(c, text=base_txt)

        dir_lbl = "Maior → Menor" if desc else "Menor → Maior"
        self.lbl_status_msg.config(text=f"Grid classificado por '{col}' ({dir_lbl}).")

    def on_create_material(self):
        """Abre a janela modal clássica para cadastrar um novo material no estoque."""
        dialog = tk.Toplevel(self)
        dialog.title("Criar Material")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("380x360")
        dialog.resizable(False, False)
        dialog.configure(bg=THEME["bg_card"])

        self.update_idletasks()
        rx = self.winfo_rootx() + (self.winfo_width() - 380) // 2
        ry = self.winfo_rooty() + (self.winfo_height() - 360) // 2
        dialog.geometry(f"+{max(10, rx)}+{max(10, ry)}")

        hdr = tk.Frame(dialog, bg=THEME["title_bar_bg"], height=28, padx=8, pady=4)
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text="Cadastro de Novo Material no Estoque",
            bg=THEME["title_bar_bg"],
            fg=THEME["title_bar_fg"],
            font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        body = tk.Frame(dialog, bg=THEME["bg_card"], padx=14, pady=12)
        body.pack(fill="both", expand=True)

        existing_mats = self.db.get_materials()
        next_num = len(existing_mats) + 1
        default_code = f"8534{12 + next_num}"
        default_name = f"Chapa {default_code} (1.38x1.08m)"

        fields = [
            ("Código do Material:", default_code),
            ("Nome / Descrição:", default_name),
            ("Definição / Tipo:", "como placa"),
            ("Largura (m):", "1,38"),
            ("Comprimento / Altura (m):", "1,08"),
            ("Camadas de corte:", "2"),
            ("Gap entre peças (mm):", "1.0"),
            ("Espessura (%1):", "0"),
        ]

        entries = {}
        for row_idx, (lbl_txt, init_val) in enumerate(fields):
            tk.Label(body, text=lbl_txt, bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").grid(row=row_idx, column=0, sticky="w", pady=3)
            ent = tk.Entry(body, font=("Segoe UI", 9), relief="sunken", bd=2, width=20)
            ent.insert(0, str(init_val))
            ent.grid(row=row_idx, column=1, sticky="e", pady=3, padx=(10, 0))
            entries[row_idx] = ent

        entries[0].focus_set()
        entries[0].select_range(0, "end")

        btn_box = tk.Frame(dialog, bg=THEME["bg_card"], pady=8)
        btn_box.pack(fill="x", padx=14)

        def save():
            mat_code = entries[0].get().strip() or default_code
            mat_name = entries[1].get().strip() or f"Material {mat_code}"
            mat_type = entries[2].get().strip() or "como placa"
            try:
                w_m = float(entries[3].get().strip().replace(",", "."))
            except ValueError:
                w_m = 1.38
            try:
                l_m = float(entries[4].get().strip().replace(",", "."))
            except ValueError:
                l_m = 1.08
            try:
                layers = int(entries[5].get().strip())
            except ValueError:
                layers = 2
            try:
                gap = float(entries[6].get().strip().replace(",", "."))
            except ValueError:
                gap = 1.0
            try:
                thick = float(entries[7].get().strip().replace(",", "."))
            except ValueError:
                thick = 0.0

            w_mm = w_m * 1000.0
            h_mm = l_m * 1000.0
            area_m2 = round(w_m * l_m, 4)

            new_mat = self.db.create_material(
                mat_id=mat_code,
                name=mat_name,
                type=mat_type,
                width_mm=w_mm,
                height_mm=h_mm,
                area_m2=area_m2,
                thickness_mm=thick,
                layers=layers,
                gap_mm=gap
            )

            self.materials = self.db.get_materials()
            self.current_material = new_mat

            if self.current_mode == "materials":
                self.switch_tree_mode("materials")

            if hasattr(self, "session_view"):
                self.session_view.set_material_data(new_mat)
            if hasattr(self, "canvas"):
                self.canvas.set_material(new_mat)
            if hasattr(self, "layout_editor_view"):
                self.layout_editor_view.set_sheet_size(w_mm, h_mm)

            self.update_all_metrics()
            self.lbl_status_msg.config(text=f"Material '{mat_name}' criado com sucesso no estoque.")
            dialog.destroy()

        btn_ok = tk.Button(btn_box, text="Criar Material", width=14, relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9, "bold"), command=save)
        btn_ok.pack(side="right", padx=4)
        btn_can = tk.Button(btn_box, text="Cancelar", width=10, relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), command=dialog.destroy)
        btn_can.pack(side="right", padx=4)

        dialog.bind("<Return>", lambda e: save())
        dialog.bind("<Escape>", lambda e: dialog.destroy())

    # =========================================================================
    # Drag & Drop: Materiais (para Sessão) e Moldes (para Pastas)
    # =========================================================================
    def on_tree_drag_start(self, event):
        iid = self.tree_main.identify_row(event.y)
        if not iid:
            sel = self.tree_main.selection()
            if sel:
                iid = sel[0]
            else:
                self._drag_data = None
                return

        # Verifica teclas modificadoras (Shift ou Control)
        is_shift = bool(event.state & 0x0001)
        is_ctrl = bool(event.state & 0x0004)

        if is_shift or is_ctrl:
            # Usuário está montando seleção múltipla (Shift ou Ctrl)
            self._drag_data = None
            self._pending_single_select = None
            return

        curr_sel = list(self.tree_main.selection())
        # Se o item clicado já faz parte de uma seleção múltipla, mantemos toda a grade selecionada!
        if iid in curr_sel and len(curr_sel) > 1:
            selected_iids = curr_sel
            self._pending_single_select = iid
        else:
            selected_iids = [iid]
            self._pending_single_select = None
            try:
                self.tree_main.selection_set(iid)
                self.tree_main.focus(iid)
            except Exception:
                pass

        vals = self.tree_main.item(iid, "values")
        text = self.tree_main.item(iid, "text").strip()

        if vals and len(vals) >= 2:
            if vals[0] == "material":
                self._drag_data = {
                    "type": "material",
                    "id": vals[1],
                    "name": text
                }
                self._drag_start_xy = (event.x_root, event.y_root)
                self._is_dragging = False
                return

        # Coleta todos os moldes selecionados ou pertencentes à pasta/grade
        shapes_to_drag = []
        folder_name = ""

        # Verifica se o item clicado é uma pasta de moldes
        if vals and len(vals) >= 2 and vals[0] == "folder":
            folder_name = str(vals[1])
            for child_id in self.tree_main.get_children(iid):
                c_vals = self.tree_main.item(child_id, "values")
                if c_vals and len(c_vals) >= 2 and c_vals[0] == "shape":
                    shp = next((s for s in self.current_shapes if str(s.get("id")) == str(c_vals[1])), None)
                    if shp and shp not in shapes_to_drag:
                        shapes_to_drag.append(shp)
        else:
            # Varre todos os iids selecionados
            for s_iid in selected_iids:
                s_vals = self.tree_main.item(s_iid, "values")
                if not s_vals or len(s_vals) < 2:
                    continue
                if s_vals[0] == "shape":
                    shp = next((s for s in self.current_shapes if str(s.get("id")) == str(s_vals[1])), None)
                    if shp and shp not in shapes_to_drag:
                        shapes_to_drag.append(shp)
                        if not folder_name:
                            folder_name = shp.get("folder", "")
                elif s_vals[0] == "folder":
                    f_name = str(s_vals[1])
                    for child_id in self.tree_main.get_children(s_iid):
                        c_vals = self.tree_main.item(child_id, "values")
                        if c_vals and len(c_vals) >= 2 and c_vals[0] == "shape":
                            shp = next((s for s in self.current_shapes if str(s.get("id")) == str(c_vals[1])), None)
                            if shp and shp not in shapes_to_drag:
                                shapes_to_drag.append(shp)
                    if not folder_name:
                        folder_name = f_name

        if shapes_to_drag:
            cnt = len(shapes_to_drag)
            if cnt > 1:
                name_lbl = f"Grade '{folder_name}' ({cnt} moldes)" if folder_name else f"Grade ({cnt} moldes)"
            else:
                name_lbl = shapes_to_drag[0].get("name", text)

            self._drag_data = {
                "type": "shape",
                "id": shapes_to_drag[0].get("id"),
                "name": name_lbl,
                "folder": folder_name,
                "shapes": shapes_to_drag,
                "count": cnt,
                "source_iids": selected_iids
            }
            self._drag_start_xy = (event.x_root, event.y_root)
            self._is_dragging = False
        else:
            self._drag_data = None

    def on_grid_drag_start(self, event):
        if (event.state & 1) or (event.state & 4):
            return
        if self.current_mode == "materials":
            iid = self.grid_lower.identify_row(event.y)
            if not iid:
                sel = self.grid_lower.selection()
                if sel:
                    iid = sel[0]
                else:
                    self._drag_data = None
                    return
            mat = next((m for m in self.materials if m["id"] == iid), None)
            if not mat:
                vals = self.grid_lower.item(iid, "values")
                if vals and len(vals) >= 1:
                    mat_id = str(vals[0])
                    mat = next((m for m in self.materials if m["id"] == mat_id or str(m["id"]).startswith(mat_id)), None)
            if mat:
                try:
                    self.grid_lower.selection_set(iid)
                except Exception:
                    pass
                self._drag_data = {
                    "type": "material",
                    "id": mat["id"],
                    "name": mat["name"]
                }
                self._drag_start_xy = (event.x_root, event.y_root)
                self._is_dragging = False
            else:
                self._drag_data = None
        elif self.current_mode == "shapes":
            iid = self.grid_lower.identify_row(event.y)
            if not iid:
                sel = self.grid_lower.selection()
                if sel:
                    iid = sel[0]
                else:
                    self._drag_data = None
                    return
            vals = self.grid_lower.item(iid, "values")
            if vals and len(vals) >= 3:
                try:
                    shape_id = int(vals[0])
                except (ValueError, TypeError):
                    shape_id = vals[0]
                shape_name = str(vals[2])
                shape_folder = str(vals[4]) if len(vals) >= 5 and vals[4] != "-" else ""
                try:
                    self.grid_lower.selection_set(iid)
                except Exception:
                    pass
                self._drag_data = {
                    "type": "shape",
                    "id": shape_id,
                    "name": shape_name,
                    "folder": shape_folder,
                    "source_iid": iid
                }
                self._drag_start_xy = (event.x_root, event.y_root)
                self._is_dragging = False
            else:
                self._drag_data = None
        else:
            self._drag_data = None

    def on_tree_drag_motion(self, event):
        if not getattr(self, "_drag_data", None):
            return

        dx = abs(event.x_root - self._drag_start_xy[0])
        dy = abs(event.y_root - self._drag_start_xy[1])

        if not getattr(self, "_is_dragging", False) and (dx > 6 or dy > 6):
            self._is_dragging = True
            self._pending_single_select = None

        if getattr(self, "_is_dragging", False):
            if not getattr(self, "_drag_avatar", None):
                avatar = tk.Toplevel(self)
                avatar.overrideredirect(True)
                avatar.attributes("-topmost", True)
                avatar.configure(bg="#ffffd0")
                frame = tk.Frame(avatar, bg="#ffffd0", relief="solid", bd=1, padx=8, pady=4)
                frame.pack()
                icon = "📦" if self._drag_data.get("type") == "material" else "📐"
                cnt = self._drag_data.get("count", 1)
                cnt_suffix = f" [{cnt} moldes]" if cnt > 1 else ""
                tk.Label(
                    frame,
                    text=f"{icon} {self._drag_data['name']}{cnt_suffix}",
                    bg="#ffffd0",
                    fg="#000000",
                    font=("Segoe UI", 9, "bold")
                ).pack()
                self._drag_avatar = avatar

            if self._drag_avatar:
                self._drag_avatar.geometry(f"+{event.x_root + 15}+{event.y_root + 15}")

            drag_type = self._drag_data.get("type")
            if drag_type == "material":
                try:
                    rx = self.right_box.winfo_rootx()
                    ry = self.right_box.winfo_rooty()
                    rw = self.right_box.winfo_width()
                    rh = self.right_box.winfo_height()
                    is_over = (rx <= event.x_root <= rx + rw and ry <= event.y_root <= ry + rh)
                except Exception:
                    is_over = False

                if is_over:
                    try:
                        self.config(cursor="hand2")
                    except Exception:
                        pass
                    self.lbl_status_msg.config(text=f"⬇️ Solte o botão do mouse para aplicar '{self._drag_data['name']}' à Sessão.")
                else:
                    try:
                        self.config(cursor="circle" if sys.platform != "win32" else "no")
                    except Exception:
                        try:
                            self.config(cursor="fleur")
                        except Exception:
                            pass
                    self.lbl_status_msg.config(text=f"Arraste '{self._drag_data['name']}' até a área da Sessão à direita...")

            elif drag_type == "shape":
                is_over_session = False
                try:
                    rx = self.right_box.winfo_rootx()
                    ry = self.right_box.winfo_rooty()
                    rw = self.right_box.winfo_width()
                    rh = self.right_box.winfo_height()
                    is_over_session = (rx <= event.x_root <= rx + rw and ry <= event.y_root <= ry + rh)
                except Exception:
                    is_over_session = False

                if is_over_session:
                    try:
                        self.config(cursor="hand2")
                    except Exception:
                        pass
                    self.lbl_status_msg.config(text=f"⬇️ Solte para adicionar {self._drag_data['name']} aos Moldes do Layout / Sessão.")
                    return

                try:
                    tx = event.x_root - self.tree_main.winfo_rootx()
                    ty = event.y_root - self.tree_main.winfo_rooty()
                    tw = self.tree_main.winfo_width()
                    th = self.tree_main.winfo_height()
                    is_over_tree = (0 <= tx <= tw and 0 <= ty <= th)
                except Exception:
                    is_over_tree = False

                if is_over_tree:
                    target_iid = self.tree_main.identify_row(ty)
                    if target_iid:
                        t_vals = self.tree_main.item(target_iid, "values")
                        if t_vals:
                            if t_vals[0] == "folder":
                                folder_name = str(t_vals[1])
                                try:
                                    self.tree_main.selection_set(target_iid)
                                except Exception:
                                    pass
                                self.config(cursor="hand2")
                                self.lbl_status_msg.config(text=f"⬇️ Solte para mover {self._drag_data['name']} para a pasta '{folder_name}'.")
                                return
                            elif t_vals[0] == "root_shapes":
                                try:
                                    self.tree_main.selection_set(target_iid)
                                except Exception:
                                    pass
                                self.config(cursor="hand2")
                                self.lbl_status_msg.config(text=f"⬇️ Solte para mover {self._drag_data['name']} para a raiz de Moldes.")
                                return
                            elif t_vals[0] == "shape":
                                s_folder = str(t_vals[2]) if len(t_vals) >= 3 else ""
                                target_desc = f"pasta '{s_folder}'" if s_folder else "raiz de Moldes"
                                self.config(cursor="hand2")
                                self.lbl_status_msg.config(text=f"⬇️ Solte para mover {self._drag_data['name']} para a {target_desc}.")
                                return
                    self.config(cursor="hand2")
                    self.lbl_status_msg.config(text=f"Arraste {self._drag_data['name']} sobre uma pasta ou para a área da Sessão / Layout...")
                else:
                    try:
                        self.config(cursor="circle" if sys.platform != "win32" else "no")
                    except Exception:
                        try:
                            self.config(cursor="fleur")
                        except Exception:
                            pass
                    self.lbl_status_msg.config(text=f"Arraste {self._drag_data['name']} até a área do Layout / Sessão à direita...")

    def on_tree_drag_end(self, event):
        if getattr(self, "_drag_avatar", None):
            try:
                self._drag_avatar.destroy()
            except Exception:
                pass
            self._drag_avatar = None

        try:
            self.config(cursor="")
        except Exception:
            pass

        if getattr(self, "_is_dragging", False) and getattr(self, "_drag_data", None):
            drag_type = self._drag_data.get("type")
            if drag_type == "material":
                try:
                    rx = self.right_box.winfo_rootx()
                    ry = self.right_box.winfo_rooty()
                    rw = self.right_box.winfo_width()
                    rh = self.right_box.winfo_height()
                    is_over = (rx <= event.x_root <= rx + rw and ry <= event.y_root <= ry + rh)
                except Exception:
                    is_over = False

                if is_over:
                    mat_id = self._drag_data["id"]
                    self.apply_material_to_session(mat_id)

            elif drag_type == "shape":
                shapes_to_add = self._drag_data.get("shapes", [])
                if not shapes_to_add and "id" in self._drag_data:
                    s_one = next((s for s in self.current_shapes if s["id"] == self._drag_data["id"]), None)
                    if s_one:
                        shapes_to_add = [s_one]

                is_over_session = False
                try:
                    rx = self.right_box.winfo_rootx()
                    ry = self.right_box.winfo_rooty()
                    rw = self.right_box.winfo_width()
                    rh = self.right_box.winfo_height()
                    is_over_session = (rx <= event.x_root <= rx + rw and ry <= event.y_root <= ry + rh)
                except Exception:
                    is_over_session = False

                if is_over_session and shapes_to_add:
                    cnt = len(shapes_to_add)
                    f_name = self._drag_data.get("folder", "")
                    lbl = f"Grade '{f_name}' ({cnt} moldes)" if (f_name and cnt > 1) else f"{cnt} molde(s)"

                    # 1. Se LayoutEditorView estiver aberto, adiciona diretamente aos moldes do layout
                    if hasattr(self, "layout_editor_view") and self.layout_editor_view and self.layout_editor_view.winfo_ismapped():
                        self.layout_editor_view.add_session_shapes(shapes_to_add)
                        if self.session_view:
                            self.session_view.add_shapes(shapes_to_add)
                        elif self.current_session:
                            self.db.update_session_shapes(self.current_session["id"], self.layout_editor_view.session_shapes)
                        self.lbl_status_msg.config(text=f"Toda a {lbl} adicionada com sucesso aos Moldes do Layout!")
                    # 2. Se SessionView estiver aberto, adiciona à aba Moldes da sessão
                    elif self.session_view and self.session_view.winfo_ismapped():
                        self.session_view.add_shapes(shapes_to_add)
                        self.session_view.notebook.select(1) # Aba Moldes
                        if hasattr(self, "layout_editor_view") and self.layout_editor_view:
                            self.layout_editor_view.set_session_shapes(self.session_view.shapes_list)
                        self.lbl_status_msg.config(text=f"Toda a {lbl} adicionada com sucesso à aba Moldes da Sessão.")
                    # 3. Se nenhuma view estiver mapeada, abre a sessão ativa e adiciona os moldes
                    elif self.current_session:
                        self.show_session_window(self.current_session)
                        if self.session_view:
                            self.session_view.add_shapes(shapes_to_add)
                            self.session_view.notebook.select(1)
                        if hasattr(self, "layout_editor_view") and self.layout_editor_view:
                            self.layout_editor_view.set_session_shapes(self.session_view.shapes_list if self.session_view else shapes_to_add)
                        self.lbl_status_msg.config(text=f"Toda a {lbl} adicionada aos Moldes da Sessão #{self.current_session['id']}.")
                else:
                    try:
                        tx = event.x_root - self.tree_main.winfo_rootx()
                        ty = event.y_root - self.tree_main.winfo_rooty()
                        tw = self.tree_main.winfo_width()
                        th = self.tree_main.winfo_height()
                        is_over_tree = (0 <= tx <= tw and 0 <= ty <= th)
                    except Exception:
                        is_over_tree = False

                    if is_over_tree and shapes_to_add:
                        target_iid = self.tree_main.identify_row(ty)
                        if not target_iid:
                            sel = self.tree_main.selection()
                            if sel:
                                target_iid = sel[0]

                        if target_iid:
                            t_vals = self.tree_main.item(target_iid, "values")
                            if t_vals:
                                dest_folder = None
                                if t_vals[0] == "folder":
                                    dest_folder = str(t_vals[1])
                                elif t_vals[0] == "root_shapes":
                                    dest_folder = ""
                                elif t_vals[0] == "shape":
                                    dest_folder = str(t_vals[2]) if len(t_vals) >= 3 else ""

                                if dest_folder is not None:
                                    moved_cnt = 0
                                    for s_item in shapes_to_add:
                                        self.db.update_shape_folder(s_item["id"], dest_folder)
                                        s_item["folder"] = dest_folder
                                        moved_cnt += 1
                                    self.reload_shapes()
                                    if self.current_mode == "shapes":
                                        self.switch_tree_mode("shapes")
                                        if dest_folder:
                                            self.select_folder_node(dest_folder)
                                    dest_desc = f"pasta '{dest_folder}'" if dest_folder else "raiz de Moldes"
                                    self.lbl_status_msg.config(text=f"{moved_cnt} molde(s) da grade movido(s) com sucesso para a {dest_desc}!")
        else:
            if getattr(self, "_pending_single_select", None):
                try:
                    self.tree_main.selection_set(self._pending_single_select)
                except Exception:
                    pass

        self._pending_single_select = None
        self._is_dragging = False
        self._drag_data = None

    def apply_material_to_session(self, mat_id):
        """Aplica o material selecionado à sessão ativa e atualiza todas as visualizações CAD."""
        mat = next((m for m in self.materials if m["id"] == mat_id or str(m["id"]).startswith(str(mat_id))), None)
        if not mat:
            mat = self.db.get_material(mat_id)
        if not mat:
            return

        # Garante que a janela de sessão esteja aberta e visível
        self.show_session_window()

        self.current_material = dict(mat)

        # Se houver sessão atual ativa, atualiza seu material
        if self.current_session:
            self.current_session["material"] = dict(mat)
            self.current_session["material_id"] = mat["id"]
            self.db.update_session(self.current_session["id"], material_id=mat["id"])
            self.save_current_session_state()

        # Atualiza a tabela Materiais na SessionView e foca na aba Materiais
        if hasattr(self, "session_view"):
            self.session_view.set_material_data(mat)
            self.session_view.notebook.select(self.session_view.tab_mat)

        # Atualiza a mesa CAD
        if hasattr(self, "canvas"):
            self.canvas.set_material(mat)

        # Atualiza o Layout Editor
        if hasattr(self, "layout_editor_view"):
            self.layout_editor_view.set_sheet_size(mat["width_mm"], mat["height_mm"])

        # Recalcula as métricas
        self.update_all_metrics()

        sess_num = self.current_session["id"] if self.current_session else 1
        self.lbl_status_msg.config(
            text=f"✅ Material '{mat['name']}' aplicado com sucesso à Sessão #{sess_num} via Arrastar e Soltar."
        )

    def on_tree_menu_open(self):
        sel = self.tree_main.selection()
        if sel:
            vals = self.tree_main.item(sel[0], "values")
            if vals and len(vals) >= 2:
                if vals[0] == "order":
                    try:
                        self.show_order_window(int(vals[1]))
                        return
                    except (ValueError, TypeError):
                        self.show_order_window()
                        return
                elif vals[0] == "session":
                    try:
                        self.switch_to_session(int(vals[1]))
                        return
                    except (ValueError, TypeError):
                        pass
                elif vals[0] == "shape":
                    try:
                        self.show_shape_editor(int(vals[1]))
                        return
                    except (ValueError, TypeError):
                        pass
        if self.current_mode == "shapes":
            self.show_shape_editor()
        else:
            self.show_session_window()

    def on_create_production(self, parent_folder=""):
        """Cria uma nova pasta ou subpasta de produção (job)."""
        if parent_folder:
            disp_parent = parent_folder.split("/")[-1]
            name = simpledialog.askstring("Criar Subpasta de Produção", f"Nome da nova subpasta dentro de '{disp_parent}':", initialvalue="Nova Subpasta", parent=self)
            if name and name.strip():
                sub_name = name.strip().strip("/")
                folder_path = f"{parent_folder}/{sub_name}"
                self.db.create_job_folder(folder_path)
                self.switch_tree_mode("jobs")
                self.select_job_folder_node(folder_path)
                self.lbl_status_msg.config(text=f"Subpasta de produção '{folder_path}' criada com sucesso.")
        else:
            name = simpledialog.askstring("Criar Produção", "Nome da nova Produção:", initialvalue="ProduçãoNova_2", parent=self)
            if name and name.strip():
                folder_name = name.strip().strip("/")
                self.db.create_job_folder(folder_name)
                self.switch_tree_mode("jobs")
                self.select_job_folder_node(folder_name)
                self.lbl_status_msg.config(text=f"Pasta de produção '{folder_name}' criada.")

    def on_create_job_subfolder(self, parent_folder: str):
        """Cria explicitamente uma subpasta dentro de parent_folder."""
        self.on_create_production(parent_folder=parent_folder)

    def on_create_job_subfolder_menu_action(self):
        """Ação de menu para criar subpasta de produção: usa a pasta selecionada ou solicita ao usuário."""
        parent_folder = ""
        if self.current_mode == "jobs":
            sel = self.tree_main.selection()
            if sel:
                vals = self.tree_main.item(sel[0], "values")
                if vals and vals[0] == "job_folder":
                    parent_folder = str(vals[1])
                elif vals and vals[0] == "session":
                    s_id = int(vals[1])
                    s_obj = next((s for s in self.sessions if s["id"] == s_id), None)
                    if s_obj and s_obj.get("job"):
                        parent_folder = s_obj["job"]
        if not parent_folder:
            folders = self.db.get_job_folders()
            if not folders:
                messagebox.showinfo("Criar Subpasta", "Nenhuma pasta de produção existe ainda. Crie primeiro uma pasta raiz.", parent=self)
                return self.on_create_production()
            parent_folder = self.prompt_select_parent_job_folder(folders)
            if not parent_folder:
                return
        self.on_create_job_subfolder(parent_folder)

    def prompt_select_parent_job_folder(self, folders):
        """Diálogo para selecionar uma pasta de produção existente como pai da nova subpasta."""
        dlg = tk.Toplevel(self)
        dlg.title("Selecionar Pasta Pai de Produção")
        dlg.geometry("340x280")
        dlg.resizable(False, False)
        dlg.configure(bg=THEME["bg_surface"])
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Selecione a pasta onde criar a subpasta de produção:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9, "bold")).pack(padx=10, pady=8, anchor="w")

        lb_frame = tk.Frame(dlg, bg=THEME["bg_surface"], relief="sunken", bd=1)
        lb_frame.pack(fill="both", expand=True, padx=10, pady=4)

        lb = tk.Listbox(lb_frame, bg="white", fg="black", selectbackground=THEME["select_bg"], selectforeground="white", font=("Segoe UI", 9))
        lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lb_frame, orient="vertical", command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.config(yscrollcommand=sb.set)

        for f in folders:
            depth = f.count("/")
            indent = "    " * depth
            name_part = f.split("/")[-1]
            lb.insert("end", f"{indent}📁 {name_part} ({f})")
        lb.selection_set(0)

        chosen = [None]
        def do_confirm():
            sel_idx = lb.curselection()
            if sel_idx:
                chosen[0] = folders[sel_idx[0]]
            dlg.destroy()

        btn_box = tk.Frame(dlg, bg=THEME["bg_surface"], pady=6)
        btn_box.pack(fill="x", padx=10)

        tk.Button(btn_box, text="Avançar", width=10, bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, command=do_confirm).pack(side="right", padx=4)
        tk.Button(btn_box, text="Cancelar", width=10, bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, command=dlg.destroy).pack(side="right", padx=4)

        lb.bind("<Double-1>", lambda e: do_confirm())
        self.wait_window(dlg)
        return chosen[0]

    def on_move_session_to_job_folder(self, sess_id: int):
        """Abre janela para mover uma sessão para outra pasta ou subpasta de produção."""
        target = next((s for s in self.sessions if s["id"] == sess_id), None)
        if not target:
            return

        folders = self.db.get_job_folders()
        if not folders:
            return

        dlg = tk.Toplevel(self)
        dlg.title("Mover Sessão")
        dlg.geometry("340x280")
        dlg.resizable(False, False)
        dlg.configure(bg=THEME["bg_surface"])
        dlg.transient(self)
        dlg.grab_set()

        s_name = target.get("name") or f"Sessão #{sess_id}"
        tk.Label(dlg, text=f"Mover '{s_name}' para a pasta de produção:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9, "bold")).pack(padx=10, pady=8, anchor="w")

        lb_frame = tk.Frame(dlg, bg=THEME["bg_surface"], relief="sunken", bd=1)
        lb_frame.pack(fill="both", expand=True, padx=10, pady=4)

        lb = tk.Listbox(lb_frame, bg="white", fg="black", selectbackground=THEME["select_bg"], selectforeground="white", font=("Segoe UI", 9))
        lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lb_frame, orient="vertical", command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.config(yscrollcommand=sb.set)

        for f in folders:
            depth = f.count("/")
            indent = "    " * depth
            name_part = f.split("/")[-1]
            lb.insert("end", f"{indent}📁 {name_part} ({f})")

        curr_job = target.get("job", "")
        if curr_job in folders:
            idx = folders.index(curr_job)
            lb.selection_set(idx)
        else:
            lb.selection_set(0)

        def do_move():
            sel_idx = lb.curselection()
            if not sel_idx:
                return
            dest = folders[sel_idx[0]]
            self.move_session_to_job_folder(sess_id, dest)
            dlg.destroy()

        btn_box = tk.Frame(dlg, bg=THEME["bg_surface"], pady=6)
        btn_box.pack(fill="x", padx=10)
        tk.Button(btn_box, text="Mover", width=10, bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, command=do_move).pack(side="right", padx=4)
        tk.Button(btn_box, text="Cancelar", width=10, bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, command=dlg.destroy).pack(side="right", padx=4)

        lb.bind("<Double-1>", lambda e: do_move())
        self.wait_window(dlg)

    def move_session_to_job_folder(self, sess_id: int, dest_folder: str):
        """Atualiza a pasta de produção da sessão no banco e na memória."""
        self.db.update_session(sess_id, job=dest_folder)
        for s in self.sessions:
            if s.get("id") == sess_id:
                s["job"] = dest_folder
                break
        if self.current_session and self.current_session.get("id") == sess_id:
            self.current_session["job"] = dest_folder
        self.switch_tree_mode("jobs")
        self.select_job_folder_node(dest_folder)
        self.lbl_status_msg.config(text=f"Sessão #{sess_id} movida para '{dest_folder}'.")

    def on_rename_tree_item(self):
        sel = self.tree_main.selection()
        if not sel and self.current_mode == "jobs":
            g_sel = self.grid_lower.selection()
            if g_sel:
                vals = self.grid_lower.item(g_sel[0], "values")
                if vals:
                    try:
                        sid = int(vals[0])
                        roots = self.tree_main.get_children("")
                        if roots:
                            self._select_session_in_tree(roots[0], sid)
                            sel = self.tree_main.selection()
                    except Exception:
                        pass
        if not sel:
            return
        curr = self.tree_main.item(sel[0], "text").strip()
        vals = self.tree_main.item(sel[0], "values")
        if vals and len(vals) >= 2 and vals[0] == "session":
            sess_id = int(vals[1])
            s_obj = next((s for s in self.sessions if s.get("id") == sess_id), None)
            raw_name = (s_obj.get("name") if s_obj else curr) or curr
            curr = clean_session_display_name(raw_name)

        new_name = simpledialog.askstring("Renomear", "Novo nome:", initialvalue=curr, parent=self)
        if new_name and new_name.strip():
            new_name = new_name.strip()
            if vals and len(vals) >= 2 and vals[0] == "session":
                sess_id = int(vals[1])
                clean_name = clean_session_display_name(new_name)
                self.db.update_session(sess_id, name=clean_name)
                for s in self.sessions:
                    if s.get("id") == sess_id:
                        s["name"] = clean_name
                        break
                if self.current_session and self.current_session.get("id") == sess_id:
                    self.current_session["name"] = clean_name
                    if getattr(self, "session_view", None):
                        self.session_view.load_session(self.current_session)
                if self.current_mode == "jobs":
                    self.switch_tree_mode("jobs")
                    roots = self.tree_main.get_children("")
                    if roots:
                        self._select_session_in_tree(roots[0], sess_id)
            elif vals and len(vals) >= 2 and vals[0] == "order":
                order_id = int(vals[1])
                self.db.update_order(order_id, name=new_name)
                for o in self.orders:
                    if o.get("id") == order_id:
                        o["name"] = new_name
                        break
                if self.current_order and self.current_order.get("id") == order_id:
                    self.current_order["name"] = new_name
                    self.order_view.load_order(self.current_order)
                if self.current_mode == "jobs":
                    self.switch_tree_mode("jobs")
            elif vals and len(vals) >= 2 and vals[0] == "job_folder":
                old_name = str(vals[1])
                disp_old = old_name.split("/")[-1]
                new_name = simpledialog.askstring("Renomear Produção", "Novo nome da pasta de produção:", initialvalue=disp_old, parent=self)
                if new_name and new_name.strip():
                    new_part = new_name.strip().strip("/")
                    if "/" in old_name:
                        parent_path = old_name.rsplit("/", 1)[0]
                        full_new_name = f"{parent_path}/{new_part}"
                    else:
                        full_new_name = new_part
                    self.db.rename_job_folder(old_name, full_new_name)
                    self.sessions = self.db.get_sessions()
                    self.switch_tree_mode("jobs")
                    self.select_job_folder_node(full_new_name)
                    self.lbl_status_msg.config(text=f"Pasta de produção renomeada para '{full_new_name}'.")
                    return
            elif vals and len(vals) >= 2 and vals[0] == "folder":
                old_name = str(vals[1])
                self.db.rename_shape_folder(old_name, new_name)
                self.reload_shapes()
                self.switch_tree_mode("shapes")
                self.lbl_status_msg.config(text=f"Pasta de moldes renomeada para '{new_name}'.")
                return
            else:
                self.tree_main.item(sel[0], text=f" {new_name}")
            disp_renamed = clean_name if (vals and len(vals) >= 2 and vals[0] == "session") else new_name
            if getattr(self, "lbl_status_msg", None):
                self.lbl_status_msg.config(text=f"Item renomeado para '{disp_renamed}'.")

    def on_delete_job_folder(self, folder_name: str):
        """Exclui uma pasta de produção (job) com confirmação e opção de exclusão em cascata."""
        folder_name = folder_name.strip().strip("/")
        sessions_in_job = [s for s in self.sessions if (s.get("job") or "").strip() == folder_name or (s.get("job") or "").strip().startswith(folder_name + "/")]
        num_sess = len(sessions_in_job)

        if num_sess == 0:
            if not messagebox.askyesno("Excluir Produção", f"Deseja realmente excluir a pasta de produção '{folder_name}' e suas eventuais subpastas?", parent=self):
                return
            self.db.delete_job_folder(folder_name, delete_sessions=False)
        else:
            resp = messagebox.askyesnocancel(
                "Excluir Pasta de Produção",
                f"A pasta '{folder_name}' (ou subpastas) contém {num_sess} sessão(ões).\n\n"
                f"• Clique 'Sim' para excluir a pasta, subpastas E todas as suas sessões.\n"
                f"• Clique 'Não' para excluir apenas a pasta (as sessões serão mantidas).\n"
                f"• Clique 'Cancelar' para desistir.",
                parent=self
            )
            if resp is None:
                return
            delete_sessions = (resp is True)
            if delete_sessions:
                sess_ids = [s["id"] for s in sessions_in_job]
                for sid in sess_ids:
                    if sid in self.open_sessions:
                        self.close_session_window(sid)
                self.db.delete_sessions(sess_ids)
                self.db.delete_job_folder(folder_name, delete_sessions=False)
                del_set = set(sess_ids)
                self.sessions = [s for s in self.sessions if s.get("id") not in del_set]
                if self.current_session and self.current_session.get("id") in del_set:
                    self.current_session = self.sessions[0] if self.sessions else None
                    if not self.current_session:
                        self.canvas.clear_bed()
                        if self.active_child == self.session_view:
                            self.close_child_window()
            else:
                self.db.delete_job_folder(folder_name, delete_sessions=False)
                self.sessions = self.db.get_sessions()

        if self.current_mode == "jobs":
            self.switch_tree_mode("jobs")
        self.lbl_status_msg.config(text=f"Pasta de produção '{folder_name}' excluída com sucesso.")

    def on_delete_tree_item(self):
        sel = self.tree_main.selection()
        if not sel:
            return

        # Agrupa itens selecionados por tipo
        sessions_to_del = []
        shapes_to_del = []
        folders_to_del = []
        job_folders_to_del = []
        orders_to_del = []
        materials_to_del = []

        for iid in sel:
            vals = self.tree_main.item(iid, "values")
            name = self.tree_main.item(iid, "text").strip()
            parent_id = self.tree_main.parent(iid)

            if not vals:
                if self.current_mode == "jobs" and parent_id:
                    job_folders_to_del.append((iid, name))
                continue

            node_type = vals[0]
            if node_type == "session" and len(vals) >= 2:
                try:
                    sessions_to_del.append((iid, int(vals[1]), name))
                except (ValueError, TypeError):
                    pass
            elif node_type == "shape" and len(vals) >= 2:
                try:
                    shapes_to_del.append((iid, int(vals[1]), name))
                except (ValueError, TypeError):
                    pass
            elif node_type == "folder" and len(vals) >= 2:
                folders_to_del.append((iid, str(vals[1])))
            elif node_type == "job_folder" and len(vals) >= 2:
                job_folders_to_del.append((iid, str(vals[1])))
            elif node_type == "order" and len(vals) >= 2:
                try:
                    orders_to_del.append((iid, int(vals[1]), name))
                except (ValueError, TypeError):
                    pass
            elif node_type == "material" and len(vals) >= 2:
                materials_to_del.append((iid, str(vals[1])))

        # 1. Trata sessões selecionadas
        if sessions_to_del:
            num = len(sessions_to_del)
            if num == 1:
                confirm_msg = f"Deseja realmente excluir a {sessions_to_del[0][2]}?"
            else:
                confirm_msg = f"Deseja realmente excluir as {num} sessões selecionadas?"
            if not messagebox.askyesno("Excluir Sessões" if num > 1 else "Excluir Sessão", confirm_msg, parent=self):
                return

            sess_ids = [s_id for _, s_id, _ in sessions_to_del]
            try:
                self.db.delete_sessions(sess_ids)
            except Exception as e:
                messagebox.showerror("Erro ao Excluir", f"Falha ao excluir sessões no banco de dados: {e}", parent=self)
                return

            for sid in sess_ids:
                if sid in self.open_sessions:
                    self.close_session_window(sid)

            del_set = set(sess_ids)
            self.sessions = [s for s in self.sessions if s.get("id") not in del_set]
            if self.current_session and self.current_session.get("id") in del_set:
                if self.sessions:
                    self.switch_to_session(self.sessions[0]["id"])
                else:
                    self.current_session = None
                    self.canvas.clear_bed()
                    if self.active_child == self.session_view:
                        self.close_child_window()

            if self.current_mode == "jobs":
                self.switch_tree_mode("jobs")
            else:
                for iid, _, _ in sessions_to_del:
                    try:
                        self.tree_main.delete(iid)
                    except Exception:
                        pass

            self.lbl_status_msg.config(
                text=f"{sessions_to_del[0][2]} excluída com sucesso." if num == 1
                else f"{num} sessões excluídas com sucesso."
            )
            return

        # 2. Trata moldes selecionados
        if shapes_to_del:
            num = len(shapes_to_del)
            if num == 1:
                self.on_delete_shape(shapes_to_del[0][1])
            else:
                if messagebox.askyesno("Excluir Moldes", f"Deseja realmente excluir os {num} moldes selecionados?", parent=self):
                    for _, shp_id, _ in shapes_to_del:
                        self.db.delete_shape(shp_id)
                    shp_ids = {s_id for _, s_id, _ in shapes_to_del}
                    self.current_shapes = [s for s in self.current_shapes if s.get("id") not in shp_ids]
                    self.switch_tree_mode("shapes")
                    self.lbl_status_msg.config(text=f"{num} moldes excluídos com sucesso.")
            return

        # 3. Trata pastas de moldes selecionadas
        if folders_to_del:
            for _, f_name in folders_to_del:
                self.on_delete_shape_folder(f_name)
            return

        # 3.1 Trata pastas de produção (jobs) selecionadas
        if job_folders_to_del:
            for _, f_name in job_folders_to_del:
                self.on_delete_job_folder(f_name)
            return

        # 4. Trata materiais selecionados
        if materials_to_del:
            num = len(materials_to_del)
            if num == 1:
                mat_id = materials_to_del[0][1]
                if messagebox.askyesno("Excluir Material", f"Deseja realmente excluir o material '{mat_id}'?", parent=self):
                    self.db.delete_material(mat_id)
                    self.materials = [m for m in self.materials if m.get("id") != mat_id]
                    if self.current_material and self.current_material.get("id") == mat_id:
                        self.current_material = self.materials[0] if self.materials else None
                    self.refresh_materials_everywhere()
                    self.lbl_status_msg.config(text=f"Material '{mat_id}' excluído com sucesso.")
            else:
                if messagebox.askyesno("Excluir Materiais", f"Deseja realmente excluir os {num} materiais selecionados?", parent=self):
                    for _, mat_id in materials_to_del:
                        self.db.delete_material(mat_id)
                    mat_ids = {m_id for _, m_id in materials_to_del}
                    self.materials = [m for m in self.materials if m.get("id") not in mat_ids]
                    if self.current_material and self.current_material.get("id") in mat_ids:
                        self.current_material = self.materials[0] if self.materials else None
                    self.refresh_materials_everywhere()
                    self.lbl_status_msg.config(text=f"{num} materiais excluídos com sucesso.")
            return

        # 5. Trata pedidos/ordens/artigos
        if orders_to_del:
            num = len(orders_to_del)
            confirm_msg = f"Deseja realmente excluir o artigo '{orders_to_del[0][2]}'?" if num == 1 else f"Deseja realmente excluir os {num} artigos selecionados?"
            if not messagebox.askyesno("Excluir Artigo" if num == 1 else "Excluir Artigos", confirm_msg, parent=self):
                return
            for iid, o_id, o_name in orders_to_del:
                self.db.delete_order(o_id)
            del_ids = {o_id for _, o_id, _ in orders_to_del}
            self.orders = [o for o in self.orders if o.get("id") not in del_ids]
            if self.current_order and self.current_order.get("id") in del_ids:
                self.current_order = self.orders[0] if self.orders else None
                if getattr(self, "active_child", None) == getattr(self, "order_view", None):
                    if self.current_order:
                        if hasattr(self, "order_view") and self.order_view:
                            self.order_view.load_order(self.current_order)
                    else:
                        if hasattr(self, "close_child_window"):
                            self.close_child_window()
            if self.current_mode == "jobs":
                self.switch_tree_mode("jobs")
            self.lbl_status_msg.config(text=f"Artigo excluído com sucesso." if num == 1 else f"{num} artigos excluídos com sucesso.")
            return

    def on_delete_grid_item(self):
        sel = self.grid_lower.selection()
        if not sel:
            return
        if self.current_mode == "shapes":
            try:
                shp_ids = []
                for item in sel:
                    v = self.grid_lower.item(item, "values")
                    if v and len(v) >= 1:
                        shp_ids.append(int(v[0]))
                if not shp_ids:
                    return
                if len(shp_ids) == 1:
                    self.on_delete_shape(shp_ids[0])
                else:
                    if messagebox.askyesno("Excluir Moldes", f"Deseja realmente excluir os {len(shp_ids)} moldes selecionados?", parent=self):
                        for sid in shp_ids:
                            self.db.delete_shape(sid)
                        del_shps = set(shp_ids)
                        self.current_shapes = [s for s in self.current_shapes if s.get("id") not in del_shps]
                        self.switch_tree_mode("shapes")
                        self.lbl_status_msg.config(text=f"{len(shp_ids)} moldes excluídos com sucesso.")
            except Exception:
                pass
        elif self.current_mode == "jobs":
            try:
                sess_ids = []
                for item in sel:
                    v = self.grid_lower.item(item, "values")
                    if v and len(v) >= 1:
                        try:
                            sess_ids.append(int(v[0]))
                        except (ValueError, TypeError):
                            pass
                if not sess_ids:
                    return
                num = len(sess_ids)
                prompt = f"Deseja realmente excluir a Sessão #{sess_ids[0]}?" if num == 1 else f"Deseja realmente excluir as {num} sessões selecionadas?"
                if not messagebox.askyesno("Excluir Sessões" if num > 1 else "Excluir Sessão", prompt, parent=self):
                    return
                try:
                    self.db.delete_sessions(sess_ids)
                except Exception as e:
                    messagebox.showerror("Erro ao Excluir", f"Falha ao excluir sessões: {e}", parent=self)
                    return
                for sid in sess_ids:
                    if sid in self.open_sessions:
                        self.close_session_window(sid)
                del_set = set(sess_ids)
                self.sessions = [s for s in self.sessions if s.get("id") not in del_set]
                if self.current_session and self.current_session.get("id") in del_set:
                    if self.sessions:
                        self.switch_to_session(self.sessions[0]["id"])
                    else:
                        self.current_session = None
                        self.canvas.clear_bed()
                        if self.active_child == self.session_view:
                            self.close_child_window()
                self.switch_tree_mode("jobs")
                self.lbl_status_msg.config(text=f"{num} sessão(ões) excluída(s) com sucesso.")
            except Exception as e:
                messagebox.showerror("Erro ao Excluir", f"Falha ao excluir sessão(ões): {e}", parent=self)
        elif self.current_mode == "materials":
            try:
                mat_ids = []
                for item in sel:
                    v = self.grid_lower.item(item, "values")
                    if v and len(v) >= 1:
                        mat_ids.append(str(v[0]))
                    else:
                        mat_ids.append(str(item))
                if not mat_ids:
                    return
                num = len(mat_ids)
                prompt = f"Deseja realmente excluir o material '{mat_ids[0]}'?" if num == 1 else f"Deseja realmente excluir os {num} materiais selecionados?"
                if not messagebox.askyesno("Excluir Materiais" if num > 1 else "Excluir Material", prompt, parent=self):
                    return
                for mid in mat_ids:
                    self.db.delete_material(mid)
                del_mats = set(mat_ids)
                self.materials = [m for m in self.materials if m.get("id") not in del_mats]
                if self.current_material and self.current_material.get("id") in del_mats:
                    self.current_material = self.materials[0] if self.materials else None
                self.refresh_materials_everywhere()
                self.lbl_status_msg.config(text=f"Material '{mat_ids[0]}' excluído com sucesso." if num == 1 else f"{num} materiais excluídos com sucesso.")
            except Exception as e:
                messagebox.showerror("Erro ao Excluir", f"Falha ao excluir material: {e}", parent=self)

    def on_global_delete_key(self, event=None):
        widget = self.focus_get()
        if isinstance(widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox, ttk.Spinbox)):
            return

        if hasattr(self, "layout_editor_view") and self.layout_editor_view and self.layout_editor_view.winfo_ismapped():
            if widget and str(widget).startswith(str(self.layout_editor_view)):
                return
        if hasattr(self, "shape_editor_view") and self.shape_editor_view and self.shape_editor_view.winfo_ismapped():
            if widget and str(widget).startswith(str(self.shape_editor_view)):
                return

        if widget == self.grid_lower:
            sel_grid = self.grid_lower.selection()
            if sel_grid:
                self.on_delete_grid_item()
                return "break"

        sel_tree = self.tree_main.selection()
        if sel_tree:
            self.on_delete_tree_item()
            return "break"

        sel_grid = self.grid_lower.selection()
        if sel_grid:
            self.on_delete_grid_item()
            return "break"

        for sv in self.open_sessions.values():
            if sv.winfo_ismapped() and hasattr(sv, "tree_shapes"):
                sel_shp = sv.tree_shapes.selection()
                if sel_shp:
                    sv.delete_selected_shape()
                    return "break"

    def on_select_all(self, event=None):
        widget = self.focus_get()
        if isinstance(widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox, ttk.Spinbox)):
            try:
                widget.selection_range(0, 'end')
            except Exception:
                pass
            return "break"

        if widget == self.grid_lower:
            children = self.grid_lower.get_children()
            if children:
                self.grid_lower.selection_set(children)
                self.lbl_status_msg.config(text=f"{len(children)} itens selecionados no grid.")
            return "break"

        # No tree_main
        if self.current_mode == "jobs":
            sess_nodes = []
            for item in self.tree_main.get_children():
                self._collect_session_nodes(item, sess_nodes)
            if sess_nodes:
                self.tree_main.selection_set(sess_nodes)
                self.lbl_status_msg.config(text=f"{len(sess_nodes)} sessões selecionadas.")
                return "break"
        elif self.current_mode == "shapes":
            shape_nodes = []
            for item in self.tree_main.get_children():
                self._collect_shape_nodes(item, shape_nodes)
            if shape_nodes:
                self.tree_main.selection_set(shape_nodes)
                self.lbl_status_msg.config(text=f"{len(shape_nodes)} moldes selecionados.")
                return "break"

        all_children = []
        for item in self.tree_main.get_children():
            all_children.extend(self.tree_main.get_children(item))
        if all_children:
            self.tree_main.selection_set(all_children)
        return "break"

    def _collect_session_nodes(self, node, result_list):
        vals = self.tree_main.item(node, "values")
        if vals and len(vals) >= 2 and vals[0] == "session":
            result_list.append(node)
        for child in self.tree_main.get_children(node):
            self._collect_session_nodes(child, result_list)

    def _collect_shape_nodes(self, node, result_list):
        vals = self.tree_main.item(node, "values")
        if vals and len(vals) >= 2 and vals[0] == "shape":
            result_list.append(node)
        for child in self.tree_main.get_children(node):
            self._collect_shape_nodes(child, result_list)

    def on_global_undo(self, event=None):
        widget = self.focus_get()
        if isinstance(widget, (tk.Entry, ttk.Entry, tk.Text)):
            return

        active = getattr(self, "active_child", None)

        # 1. Se o Shape Editor estiver ativo ou visível
        if active == getattr(self, "shape_editor_view", None) or (hasattr(self, "shape_editor_view") and self.shape_editor_view and self.shape_editor_view.winfo_ismapped()):
            if hasattr(self, "shape_editor_view") and self.shape_editor_view:
                self.shape_editor_view.undo_or_revert()
                return "break"

        # 2. Se o Layout Editor estiver ativo ou visível
        if active == getattr(self, "layout_editor_view", None) or (hasattr(self, "layout_editor_view") and self.layout_editor_view and self.layout_editor_view.winfo_ismapped()):
            if hasattr(self, "layout_editor_view") and self.layout_editor_view:
                self.layout_editor_view.undo_action()
                return "break"

    def on_publish(self):
        messagebox.showinfo("Publish", "Produção publicada para corte na mesa CNC ATOM.", parent=self)
        self.lbl_status_msg.config(text="Produção publicada.")

    def on_import_xml(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Arquivos XML", "*.xml"), ("Todos os Arquivos", "*.*")],
            parent=self
        )
        if file_path:
            messagebox.showinfo("Import XML", f"Arquivo XML importado com sucesso:\n{Path(file_path).name}", parent=self)
            self.lbl_status_msg.config(text=f"XML importado: {Path(file_path).name}")

    def on_tree_selected(self, event=None):
        sel = self.tree_main.selection()
        if not sel:
            return

        if len(sel) > 1:
            # Multi-seleção ativa: NÃO alternar de sessão para não colapsar a seleção
            if self.current_mode == "jobs":
                sess_ids = []
                for item in sel:
                    v = self.tree_main.item(item, "values")
                    if v and len(v) >= 2 and v[0] == "session":
                        try:
                            sess_ids.append(int(v[1]))
                        except (ValueError, TypeError):
                            pass
                if sess_ids:
                    self.lbl_status_msg.config(text=f"{len(sess_ids)} sessões selecionadas.")
                    return
            elif self.current_mode == "shapes":
                shape_ids = []
                for item in sel:
                    v = self.tree_main.item(item, "values")
                    if v and len(v) >= 2 and v[0] == "shape":
                        try:
                            shape_ids.append(int(v[1]))
                        except (ValueError, TypeError):
                            pass
                if shape_ids:
                    self.lbl_status_msg.config(text=f"{len(shape_ids)} moldes selecionados.")
                    return
            self.lbl_status_msg.config(text=f"{len(sel)} itens selecionados.")
            return

        vals = self.tree_main.item(sel[0], "values")
        if not vals:
            return

        if self.current_mode == "shapes":
            node_type = vals[0]
            if node_type == "folder":
                folder_name = vals[1]
                self.lbl_status_msg.config(text=f"Pasta de moldes selecionada: '{folder_name}'")
                self.grid_lower.delete(*self.grid_lower.get_children())
                f_prefix = folder_name + "/"
                for s in self.current_shapes:
                    s_f = s.get("folder", "").strip()
                    if s_f == folder_name or s_f.startswith(f_prefix):
                        self.grid_lower.insert("", "end", values=(s["id"], "Externo", s["name"], s.get("size", "41"), s_f))
            elif node_type == "root_shapes":
                self.lbl_status_msg.config(text="Todos os moldes (Raiz)")
                self.grid_lower.delete(*self.grid_lower.get_children())
                for s in self.current_shapes:
                    s_folder = s.get("folder", "").strip()
                    self.grid_lower.insert("", "end", values=(s["id"], "Externo", s["name"], s.get("size", "41"), s_folder or "-"))
            elif node_type == "shape":
                shape_id = int(vals[1])
                s_folder = vals[2] if len(vals) >= 3 else ""
                self.lbl_status_msg.config(text=f"Molde selecionado: ID {shape_id} (Pasta: {s_folder or 'Raiz'})")
        elif self.current_mode == "jobs":
            node_type = vals[0]
            if node_type == "job_folder":
                folder_name = vals[1] if len(vals) >= 2 else ""
                self.lbl_status_msg.config(text=f"Pasta de produção selecionada: '{folder_name}'")
            elif node_type == "root_production":
                self.lbl_status_msg.config(text="Ambiente de Produção (Raiz)")
            elif node_type == "session" and len(vals) >= 2:
                try:
                    sess_id = int(vals[1])
                    if self.current_session and self.current_session.get("id") == sess_id and self.active_child == self.session_view:
                        return
                    self.switch_to_session(sess_id)
                except (ValueError, TypeError):
                    pass
            elif node_type == "order" and len(vals) >= 2:
                try:
                    order_id = int(vals[1])
                    self.show_order_window(order_id)
                except (ValueError, TypeError):
                    self.show_order_window()
        elif self.current_mode == "materials":
            node_type = vals[0] if vals else ""
            if node_type == "material" and len(vals) >= 2:
                mat_id = str(vals[1])
                self.lbl_status_msg.config(text=f"Material selecionado: '{mat_id}'")
                if self.grid_lower.exists(mat_id):
                    self.grid_lower.selection_set(mat_id)
                    self.grid_lower.see(mat_id)
            elif node_type == "root_materials":
                self.lbl_status_msg.config(text="Estoque de material (Raiz)")

    def on_tree_double_click(self, event):
        sel = self.tree_main.selection()
        if not sel:
            return
        item_text = self.tree_main.item(sel[0], "text")
        item_vals = self.tree_main.item(sel[0], "values")

        if self.current_mode == "shapes":
            if item_vals and len(item_vals) >= 2:
                if item_vals[0] == "shape":
                    try:
                        self.show_shape_editor(int(item_vals[1]))
                        return
                    except (ValueError, TypeError):
                        pass
                elif item_vals[0] == "folder":
                    self.tree_main.item(sel[0], open=not self.tree_main.item(sel[0], "open"))
                    return
            self.show_shape_editor()
            return

        if self.current_mode == "materials":
            if item_vals and len(item_vals) >= 2 and item_vals[0] == "material":
                self.apply_material_to_session(item_vals[1])
                return
            elif item_vals and len(item_vals) >= 1 and item_vals[0] == "root_materials":
                self.show_material_codes_window()
                return

        if self.current_mode == "jobs":
            if item_vals and len(item_vals) >= 2:
                if item_vals[0] == "job_folder":
                    self.tree_main.item(sel[0], open=not self.tree_main.item(sel[0], "open"))
                    return
                elif item_vals[0] == "session":
                    try:
                        self.switch_to_session(int(item_vals[1]))
                        return
                    except (ValueError, TypeError):
                        pass
                elif item_vals[0] == "order":
                    try:
                        self.show_order_window(int(item_vals[1]))
                        return
                    except (ValueError, TypeError):
                        self.show_order_window()
                        return
            if "Derby" in item_text or "Lote" in item_text or "Ordem" in item_text or "Pedido" in item_text:
                self.show_order_window()
            else:
                self.show_session_window()
            return

    def on_grid_double_click(self, event):
        sel = self.grid_lower.selection()
        if not sel:
            return
        if self.current_mode == "shapes":
            vals = self.grid_lower.item(sel[0], "values")
            if vals and len(vals) >= 1:
                try:
                    shape_id = int(vals[0])
                    self.show_shape_editor(shape_id)
                    return
                except (ValueError, TypeError):
                    pass
            self.show_shape_editor()
            return
        elif self.current_mode == "materials":
            vals = self.grid_lower.item(sel[0], "values")
            if vals and len(vals) >= 1:
                mat_id = str(vals[0])
                for m in self.materials:
                    if m["id"] == mat_id or str(m["id"]).startswith(mat_id):
                        self.apply_material_to_session(m["id"])
                        return
        elif self.current_mode == "jobs":
            vals = self.grid_lower.item(sel[0], "values")
            if vals and len(vals) >= 1:
                try:
                    sess_id = int(vals[0])
                    self.switch_to_session(sess_id)
                    return
                except (ValueError, TypeError):
                    pass
            self.show_session_window()
        elif self.current_mode == "jobs":
            vals = self.grid_lower.item(sel[0], "values")
            if vals and len(vals) >= 1:
                try:
                    sess_id = int(vals[0])
                    self.switch_to_session(sess_id)
                    return
                except (ValueError, TypeError):
                    pass
            self.show_session_window()

    def on_session_standby(self):
        if self.current_session:
            self.current_session["status"] = "Stand by"
            self.db.update_session(self.current_session["id"], status="Stand by")
            if self.current_mode == "jobs":
                self.switch_tree_mode("jobs")
            if self.session_view:
                self.session_view.load_session(self.current_session)
        self.lbl_status_msg.config(text="Sessão colocada em 'Stand by'.")

    def on_session_strategy_changed(self, strategy):
        if self.current_session:
            self.current_session["strategy"] = strategy
            self.db.update_session(self.current_session["id"], strategy=strategy)
        self.lbl_status_msg.config(text=f"Estratégia de corte alterada para '{strategy}'.")

    def on_auto_nest(self):
        if getattr(self, "_nesting_in_progress", False):
            self.lbl_status_msg.config(text="Cálculo de Nesting já em andamento... aguarde.")
            return

        strategy = self.session_view.get_strategy() if getattr(self, "session_view", None) else "flashnestsheet"
        params = self.session_view.get_params() if getattr(self, "session_view", None) else "ALTERNADO"
        machine = self.session_view.get_machine() if getattr(self, "session_view", None) else "ATOM FlashCut Flex 3020"
        self.show_session_window()

        # Verifica os moldes configurados na sessão ativa
        sess_shapes = []
        if getattr(self, "session_view", None) and self.session_view.shapes_list:
            sess_shapes = self.session_view.shapes_list
        elif self.current_session and self.current_session.get("shapes"):
            sess_shapes = self.current_session["shapes"]

        if not sess_shapes:
            messagebox.showwarning(
                "Nenhum Molde na Sessão",
                "A sessão atual está em branco.\n\nPor favor, vá até a aba 'Moldes' e clique em '➕ Adicionar Molde...' para selecionar os moldes a cortar antes de executar o Nesting.",
                parent=self
            )
            if self.session_view:
                self.session_view.notebook.select(1)  # Abre a aba Moldes
            return

        if not self.current_material:
            self.lbl_status_msg.config(text="Atenção: Selecione um material na aba Materiais para calcular.")
            return

        # Recupera parâmetros DieProc ativos (acoplamento de rotação, ranges, gaps, row interlock)
        dieproc_params = None
        if getattr(self, "session_view", None):
            dieproc_params = self.session_view.get_dieproc_params()
        if not dieproc_params and self.db:
            dieproc_params = self.db.get_dieproc_preset(params)

        gap = float(dieproc_params.get("gap1", 1.0) if dieproc_params else (self.current_material.get("gap_mm", 1.0) or 1.0))
        # Ordena moldes pela sequência de geração configurada pelo usuário
        sess_shapes = sorted(sess_shapes, key=lambda s: int(s.get("sequence", 999)))
        for idx, s in enumerate(sess_shapes, start=1):
            s_size = str(s.get("size", "41"))
            s["color"] = get_color_for_size(s_size, idx)

        # 1 par de calçados = 2 peças físicas a cortar (pé esquerdo + pé direito)
        target_count = sum(int(s.get("pairs", 24)) * 2 for s in sess_shapes)
        target_count = max(1, target_count)

        mat_w = self.current_material["width_mm"]
        mat_h = self.current_material["height_mm"]

        self._nesting_in_progress = True
        self.config(cursor="watch")
        self.lbl_status_msg.config(text=f"Calculando Nesting automático '{strategy}' ({params})... aguarde.")

        nest_q = queue.Queue()

        def _worker():
            try:
                pieces = auto_nest_pieces(
                    sess_shapes,
                    mat_w,
                    mat_h,
                    target_count=target_count,
                    strategy=strategy,
                    params=params,
                    gap_mm=gap,
                    dieproc_params=dieproc_params
                )
                nest_q.put(("SUCCESS", pieces))
            except Exception as e:
                nest_q.put(("ERROR", str(e)))

        th = threading.Thread(target=_worker, daemon=True)
        th.start()
        self.after(50, lambda: self._poll_nest_worker(nest_q, strategy, params, machine))

    def _poll_nest_worker(self, q, strategy, params, machine):
        try:
            status, data = q.get_nowait()
        except queue.Empty:
            self.after(50, lambda: self._poll_nest_worker(q, strategy, params, machine))
            return

        self._nesting_in_progress = False
        self.config(cursor="")

        if status == "SUCCESS":
            pieces = data
            self.canvas.set_pieces(pieces)
            self.save_current_session_state()
            if self.current_session:
                self.current_session["status"] = "Nested"
                self.current_session["strategy"] = strategy
                self.current_session["params"] = params
                self.current_session["machine"] = machine
                self.db.update_session(
                    self.current_session["id"],
                    status="Nested",
                    strategy=strategy,
                    params=params,
                    machine=machine
                )
                if self.current_mode == "jobs":
                    self.switch_tree_mode("jobs")
                if self.session_view:
                    self.session_view.load_session(self.current_session)
            if self.session_view:
                self.session_view.notebook.select(self.session_view.tab_lays)
            self.lbl_status_msg.config(
                text=f"Auto-Nest concluído com estratégia '{strategy}' ({params}) na máquina {machine}. ({len(pieces)} peças encaixadas)"
            )
        else:
            messagebox.showerror("Erro no Auto-Nest", f"Falha no cálculo de nesting:\n{data}", parent=self)
            self.lbl_status_msg.config(text="Erro ao calcular nesting automático.")


    def on_clear_bed(self):
        self.canvas.clear_bed()
        self.save_current_session_state()
        if self.current_session:
            self.current_session["status"] = "Stand by"
            self.db.update_session(self.current_session["id"], status="Stand by")
            if self.current_mode == "jobs":
                self.switch_tree_mode("jobs")
            if self.session_view:
                self.session_view.load_session(self.current_session)
        if self.session_view:
            self.session_view.notebook.select(self.session_view.tab_lays)
        self.lbl_status_msg.config(text="Layouts reinicializados (Rewind executado). Mesa limpa.")

    def on_toggle_sim(self):
        self.show_session_window()
        if self.session_view:
            self.session_view.notebook.select(self.session_view.tab_lays)
        if self.canvas.sim_running:
            self.canvas.stop_simulation()
            self.btn_sim.config(text="▶ Simular", bg=THEME["bg_surface"])
            self.lbl_status_msg.config(text="Simulação de corte parada.")
        else:
            if not self.canvas.placed_pieces:
                self.on_auto_nest()
            self.canvas.start_simulation()
            self.btn_sim.config(text="⏹ Parar", bg=THEME["bg_hover"])
            self.lbl_status_msg.config(text="Simulando cabeçote de corte ATOM...")

    def update_all_metrics(self):
        if not self.current_material:
            return
        yield_pct, used_m2 = calculate_yield(self.canvas.placed_pieces, self.current_material["area_m2"])
        est_sec, cut_len_mm = calculate_atom_cutting_time(self.canvas.placed_pieces)
        if self.session_view:
            self.session_view.update_summary_text(len(self.canvas.placed_pieces), yield_pct, est_sec)
        curr_id = self.current_session.get("id") if self.current_session else None
        for sv in self.open_sessions.values():
            if sv != self.session_view and getattr(sv, "session_data", None) and sv.session_data.get("id") == curr_id:
                sv.update_summary_text(len(self.canvas.placed_pieces), yield_pct, est_sec)

    def open_params_dialog(self):
        NestingParamsDialog(self)

    def open_dieproc_dialog(self, initial_preset=None, callback=None):
        """Abre a janela de configuração DieProc (dp98) para ajuste de coupling, ranges e row interlock."""
        preset = initial_preset
        if not preset and getattr(self, "session_view", None):
            preset = self.session_view.get_params()

        def _on_select(data):
            if callback:
                callback(data)
            elif getattr(self, "session_view", None):
                self.session_view.on_dieproc_preset_selected(data)
            self.lbl_status_msg.config(text=f"Perfil DieProc '{data['name']}' selecionado.")

        DieProcDialog(self, self.db, initial_preset=preset, on_select=_on_select)

    def _select_session_in_tree(self, parent_item, target_sess_id):
        """Busca recursivamente o item da sessão na árvore e o seleciona/abre."""
        vals = self.tree_main.item(parent_item, "values")
        if vals and len(vals) >= 2 and vals[0] == "session":
            try:
                if int(vals[1]) == target_sess_id:
                    self.tree_main.selection_set(parent_item)
                    self.tree_main.focus(parent_item)
                    self.tree_main.see(parent_item)
                    return True
            except (ValueError, TypeError):
                pass
        for child in self.tree_main.get_children(parent_item):
            if self._select_session_in_tree(child, target_sess_id):
                self.tree_main.item(parent_item, open=True)
                return True
        return False

    def on_new_session(self):
        """
        Cria uma nova sessão em branco numerando sequencialmente (#1, #2, #3...),
        garantindo unicidade estrita (números apagados nunca são reutilizados).
        """
        # 1. Salva o estado da sessão atual antes de criar a nova
        self.save_current_session_state()

        # 2. Calcula próximo número sequencial monotônico (#1, #2, #3...)
        next_id = self.get_next_session_number()
        sess_name = f"Sessão #{next_id}"

        # Determina a pasta de produção (job) para a nova sessão
        sel = self.tree_main.selection()
        sess_job = None
        if sel:
            vals = self.tree_main.item(sel[0], "values")
            if vals and len(vals) >= 2 and vals[0] == "job_folder":
                sess_job = str(vals[1])
            elif vals and len(vals) >= 2 and vals[0] == "session":
                s_obj = next((s for s in self.sessions if s["id"] == int(vals[1])), None)
                if s_obj and s_obj.get("job"):
                    sess_job = s_obj["job"]

        if not sess_job and self.current_session and self.current_session.get("job"):
            sess_job = self.current_session["job"]

        if not sess_job:
            folders = self.db.get_job_folders()
            sess_job = folders[0] if folders else "ProduçãoNova"

        # Garante que a pasta de produção existe no banco
        self.db.create_job_folder(sess_job)

        # Conexão com Opções: Pergunta o nome da sessão ao criá-la
        ask_name = self.db.get_setting("ask_session_name", "1") == "1"
        if ask_name:
            from tkinter import simpledialog
            user_name = simpledialog.askstring("Nova Sessão", "Nome da sessão:", initialvalue=sess_name, parent=self)
            if user_name is None:
                return
            if user_name.strip():
                sess_name = user_name.strip()

        # Conexão com Opções: Estratégia e Parâmetros padrão
        def_strat = self.db.get_setting("default_strategy", "flashnestsheet")
        def_params = self.db.get_setting("default_nesting_params", "Padrao")
        if def_params == "Padrao":
            def_params = "stdNOTFill"

        # 3. Cria no banco de dados com mesa vazia (em branco)
        mat_id = self.current_material["id"] if (self.current_material and "id" in self.current_material) else "MAT_VAQ_01"
        try:
            orders = self.db.get_orders()
            order_id = orders[0]["id"] if orders else None
        except Exception:
            order_id = None

        try:
            actual_id = self.db.create_session(
                session_id=next_id,
                name=sess_name,
                job=sess_job,
                order_id=order_id,
                material_id=mat_id,
                status="Stand by",
                placed_pieces=[],
                strategy=def_strat,
                params=def_params,
                shapes=[]
            )
            self.sessions = self.db.get_sessions()
            self.current_session = next((s for s in self.sessions if s["id"] == actual_id), None)
            if not self.current_session:
                self.current_session = self.db.get_session(actual_id) or {
                    "id": actual_id,
                    "name": sess_name,
                    "job": sess_job,
                    "order_id": order_id,
                    "material_id": mat_id,
                    "status": "Stand by",
                    "placed_pieces": [],
                    "shapes": [],
                    "strategy": def_strat,
                    "params": def_params
                }
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Erro ao Criar Sessão", f"Não foi possível criar a sessão no banco de dados:\n{e}", parent=self)
            self.lbl_status_msg.config(text=f"Erro ao criar sessão: {e}")
            return

        # 4. Limpa completamente a mesa CAD (em branco)
        self.canvas.clear_bed()

        # 5. SEMPRE alterna a visualização para modo Produção ('jobs')
        self.switch_tree_mode("jobs")

        # Seleciona a sessão na árvore
        for root_item in self.tree_main.get_children():
            self._select_session_in_tree(root_item, actual_id)

        # 6. Exibe a janela da sessão com a aba Moldes ativa em branco
        view = self.show_session_window(self.current_session)
        if view:
            view.load_session(self.current_session)
            view.set_shapes_data([])
            if hasattr(view, "notebook"):
                view.notebook.select(1)  # Aba Moldes (índice 1)
        self.update_all_metrics()

        self.lbl_status_msg.config(text=f"Nova sessão #{actual_id} criada com sucesso. Adicione os moldes na aba Moldes.")

    def on_export_gcode(self):
        if not self.canvas.placed_pieces:
            messagebox.showwarning("Exportar", "Adicione peças à mesa antes de exportar.")
            return
        file_path = filedialog.asksaveasfilename(
            initialdir=str(EXPORTS_DIR),
            initialfile="corte_atom_flex3020.iso",
            defaultextension=".iso",
            filetypes=[("Arquivos CNC ISO / G-Code", "*.iso *.gcode *.tap"), ("Todos os Arquivos", "*.*")]
        )
        if file_path:
            out = export_gcode(self.canvas.placed_pieces, self.current_material, file_path)
            messagebox.showinfo("Sucesso", f"Programa G-Code gerado com sucesso!\nSalvo em: {out}")
            self.lbl_status_msg.config(text=f"G-Code exportado para {Path(out).name}")

    def on_export_xml(self):
        if not self.canvas.placed_pieces:
            messagebox.showwarning("Exportar", "Adicione peças à mesa antes de exportar.")
            return
        yield_pct, _ = calculate_yield(self.canvas.placed_pieces, self.current_material["area_m2"])
        est_sec, _ = calculate_atom_cutting_time(self.canvas.placed_pieces)
        sess_name = self.current_session["name"] if self.current_session else "Sessão #1"
        file_path = filedialog.asksaveasfilename(
            initialdir=str(EXPORTS_DIR),
            initialfile="session_report.xml",
            defaultextension=".xml",
            filetypes=[("Relatório XML", "*.xml"), ("Todos os Arquivos", "*.*")]
        )
        if file_path:
            out = export_xml_report(sess_name, self.current_material, self.canvas.placed_pieces, yield_pct, est_sec, file_path)
            messagebox.showinfo("Sucesso", f"Relatório XML gerado com sucesso!\nSalvo em: {out}")
            self.lbl_status_msg.config(text=f"Relatório XML exportado para {Path(out).name}")
