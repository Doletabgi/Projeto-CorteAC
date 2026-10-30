"""
JobManager 2000 (Python Edition)
Shape Catalog View (Catálogo de Moldes - Grid View Matrix)
Inspirado no Shape Editor Comelz (MA166_166_207.cmz) e adaptado à arquitetura Win32 MDI do CorteAC.
"""

import copy
import json
import math
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

if not hasattr(tk, "Combobox"):
    tk.Combobox = ttk.Combobox

from cad.die_parser import parse_die_file, save_die_file
from cad.geometry import polygon_area, polygon_bbox, polygon_perimeter
from ui.sort_utils import natural_sort_key, size_sort_key


def extract_piece_base_name(name: str, size: str = "") -> str:
    """
    Extrai o nome base da peça removendo sufixos de tamanho (ex: '323_PalAcb_22a' -> '323_PalAcb',
    'PALM_CAVA-25a' -> 'PALM_CAVA', 'teste2' -> 'teste2').
    """
    n = str(name or "").strip()
    s = str(size or "").strip()
    if s and n.lower().endswith(("_" + s.lower(), "-" + s.lower())):
        return n[: -len(s) - 1]
    m = re.search(r"[-_]\d+(?:[.,]\d+)?[a-zA-Z]?$", n)
    if m:
        return n[: m.start()]
    return n


class ShapeCatalogView(tk.Frame):
    """
    Visão MDI em Matriz Grid (Peças × Tamanhos) para exibição e gerenciamento
    do catálogo completo de moldes de um artigo.
    """

    def __init__(
        self,
        parent,
        article_id: int = 1,
        article_name: str = "",
        db=None,
        on_close=None,
        on_minimize=None,
        on_maximize=None,
        on_edit_shape=None,
        **kwargs,
    ):
        super().__init__(parent, bg="#d4d0c8", relief="ridge", bd=2, **kwargs)
        self.article_id = article_id
        self.article_name = article_name or f"Artigo #{article_id}"
        self.db = db
        self.on_close_cb = on_close
        self.on_minimize_cb = on_minimize
        self.on_maximize_cb = on_maximize
        self.on_edit_shape_cb = on_edit_shape

        # Estado da matriz
        self.shapes_list = []
        self.piece_names = []  # Colunas
        self.sizes_list = []  # Linhas
        self.grid_matrix = {}  # (piece_name, size) -> shape_dict
        self.selected_coords = None  # (col_idx, row_idx)
        self.order_mode = "alphabetic"  # "alphabetic" ou "registered"

        # Pilha de desfeita local (até 20 níveis)
        self.undo_stack = []

        # Configurações de layout e Zoom do Grid Canvas
        self.zoom_factor = 1.0
        self.base_cell_w = 110
        self.base_cell_h = 75
        self.base_header_h = 42
        self.base_sidebar_w = 65

        self.cell_w = self.base_cell_w
        self.cell_h = self.base_cell_h
        self.header_h = self.base_header_h
        self.sidebar_w = self.base_sidebar_w

        # Filtros de visualização
        self.filter_size = "Todos"
        self.filter_piece = "Todas"
        self.all_piece_names = []
        self.all_sizes_list = []

        # Fontes clássicas Win32
        self.font_title = ("MS Sans Serif", 8, "bold")
        self.font_btn = ("MS Sans Serif", 8)
        self.font_btn_bold = ("MS Sans Serif", 8, "bold")
        self.font_grid = ("MS Sans Serif", 8)
        self.font_grid_small = ("MS Sans Serif", 7)
        self.font_badge = ("MS Sans Serif", 7, "bold")

        self.setup_ui()
        self.load_data()

    # =========================================================================
    # Camada 1: Interface Gráfica Win32 MDI
    # =========================================================================
    def setup_ui(self):
        # 1. Barra de Título MDI Clássica Windows XP (#0a246a)
        self.title_bar = tk.Frame(self, bg="#0a246a", height=24, padx=4, pady=2)
        self.title_bar.pack(fill="x")

        self.lbl_title = tk.Label(
            self.title_bar,
            text=f"📐 Catálogo de Moldes - [{self.article_name}]",
            bg="#0a246a",
            fg="#ffffff",
            font=self.font_title,
        )
        self.lbl_title.pack(side="left")

        btn_box = tk.Frame(self.title_bar, bg="#0a246a")
        btn_box.pack(side="right")
        self.btn_min = tk.Button(
            btn_box,
            text="_",
            relief="raised",
            bd=1,
            bg="#d4d0c8",
            fg="#000000",
            font=("MS Sans Serif", 7, "bold"),
            width=2,
            height=1,
            padx=0,
            pady=0,
            command=self.on_minimize_click,
        )
        self.btn_min.pack(side="left", padx=1)
        self.btn_max = tk.Button(
            btn_box,
            text="□",
            relief="raised",
            bd=1,
            bg="#d4d0c8",
            fg="#000000",
            font=("MS Sans Serif", 7, "bold"),
            width=2,
            height=1,
            padx=0,
            pady=0,
            command=self.on_maximize_click,
        )
        self.btn_max.pack(side="left", padx=1)
        self.btn_close = tk.Button(
            btn_box,
            text="✕",
            relief="raised",
            bd=1,
            bg="#d4d0c8",
            fg="#000000",
            font=("MS Sans Serif", 7, "bold"),
            width=2,
            height=1,
            padx=0,
            pady=0,
            command=self.on_close_click,
        )
        self.btn_close.pack(side="left", padx=1)

        # Arrastar janela MDI pelo título
        self.title_bar.bind("<ButtonPress-1>", self._on_title_press)
        self.title_bar.bind("<B1-Motion>", self._on_title_motion)
        self.lbl_title.bind("<ButtonPress-1>", self._on_title_press)
        self.lbl_title.bind("<B1-Motion>", self._on_title_motion)
        self.bind("<Button-1>", lambda e: self.lift(), add="+")

        # 1.5 Barra de Ferramentas CAD (Zoom e Filtros)
        self.toolbar = tk.Frame(self, bg="#d4d0c8", height=28, padx=6, pady=2, relief="raised", bd=1)
        self.toolbar.pack(fill="x")

        # Controles de Zoom
        tk.Label(self.toolbar, text="Zoom:", bg="#d4d0c8", font=self.font_btn).pack(side="left", padx=(0, 2))
        self.btn_zoom_in = tk.Button(self.toolbar, text="➕", width=2, relief="raised", bd=1, bg="#d4d0c8", font=("MS Sans Serif", 8, "bold"), command=lambda: self.zoom_step(1.2))
        self.btn_zoom_in.pack(side="left", padx=1)
        self.btn_zoom_out = tk.Button(self.toolbar, text="➖", width=2, relief="raised", bd=1, bg="#d4d0c8", font=("MS Sans Serif", 8, "bold"), command=lambda: self.zoom_step(1.0 / 1.2))
        self.btn_zoom_out.pack(side="left", padx=1)
        self.btn_zoom_reset = tk.Button(self.toolbar, text="🔍 100%", relief="raised", bd=1, bg="#d4d0c8", font=self.font_btn, command=self.reset_zoom)
        self.btn_zoom_reset.pack(side="left", padx=1)
        self.lbl_zoom = tk.Label(self.toolbar, text="100%", bg="#d4d0c8", font=self.font_btn, width=5)
        self.lbl_zoom.pack(side="left", padx=(0, 4))

        # Separador vertical
        tk.Frame(self.toolbar, width=2, bg="#a0a0a0", relief="sunken", bd=1).pack(side="left", fill="y", padx=6, pady=2)

        # Filtro por Tamanho
        tk.Label(self.toolbar, text="Tamanho:", bg="#d4d0c8", font=self.font_btn).pack(side="left", padx=(0, 2))
        self.combo_size = ttk.Combobox(self.toolbar, values=["Todos"], state="readonly", width=8, font=self.font_btn)
        self.combo_size.set("Todos")
        self.combo_size.pack(side="left", padx=2)
        self.combo_size.bind("<<ComboboxSelected>>", self.on_size_filter_changed)

        # Filtro por Peça
        tk.Label(self.toolbar, text="Peça:", bg="#d4d0c8", font=self.font_btn).pack(side="left", padx=(6, 2))
        self.combo_piece = ttk.Combobox(self.toolbar, values=["Todas"], state="readonly", width=14, font=self.font_btn)
        self.combo_piece.set("Todas")
        self.combo_piece.pack(side="left", padx=2)
        self.combo_piece.bind("<<ComboboxSelected>>", self.on_piece_filter_changed)

        # Botão Reset Filtros
        self.btn_reset_filters = tk.Button(self.toolbar, text="🔄 Mostrar tudo", relief="raised", bd=1, bg="#d4d0c8", font=self.font_btn, command=self.reset_filters)
        self.btn_reset_filters.pack(side="left", padx=4)

        # 2. Área Central: Canvas + Painel Lateral Direito
        content_frame = tk.Frame(self, bg="#d4d0c8")
        content_frame.pack(fill="both", expand=True)

        # Painel Lateral Direito (10 Botões + Mini-Painel de Informações)
        self.panel_right = tk.Frame(content_frame, bg="#d4d0c8", width=175, relief="raised", bd=2, padx=4, pady=4)
        self.panel_right.pack(side="right", fill="y")
        self.panel_right.pack_propagate(False)

        self.setup_right_panel()

        # Container do Canvas com barras de rolagem Win32
        canvas_container = tk.Frame(content_frame, bg="#1e293b", relief="sunken", bd=2)
        canvas_container.pack(side="left", fill="both", expand=True)

        self.hbar = tk.Scrollbar(canvas_container, orient="horizontal")
        self.hbar.pack(side="bottom", fill="x")
        self.vbar = tk.Scrollbar(canvas_container, orient="vertical")
        self.vbar.pack(side="right", fill="y")

        self.canvas = tk.Canvas(
            canvas_container,
            bg="#1e293b",
            highlightthickness=0,
            cursor="hand2",
            xscrollcommand=self.hbar.set,
            yscrollcommand=self.vbar.set,
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        self.hbar.config(command=self.canvas.xview)
        self.vbar.config(command=self.canvas.yview)

        # Eventos do Canvas e Teclado
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_click)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<Configure>", lambda e: self.redraw_grid())

        # Pan com botão do meio do mouse
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_motion)
        self.canvas.bind("<ButtonRelease-2>", self.on_pan_end)

        # Zoom com roda do mouse
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_step(1.2))
        self.canvas.bind("<Button-5>", lambda e: self.zoom_step(1.0 / 1.2))

        # Bindings de Navegação e Atalhos
        self.bind("<Up>", lambda e: self.navigate_selection(0, -1))
        self.bind("<Down>", lambda e: self.navigate_selection(0, 1))
        self.bind("<Left>", lambda e: self.navigate_selection(-1, 0))
        self.bind("<Right>", lambda e: self.navigate_selection(1, 0))
        self.bind("<Return>", lambda e: self.open_selected_shape())
        self.bind("<KP_Enter>", lambda e: self.open_selected_shape())
        self.bind("<Escape>", lambda e: self.on_close_click())
        self.bind("<Control-z>", lambda e: self.action_undo())
        self.bind("<Control-Z>", lambda e: self.action_undo())

        # Atalhos de Teclado para Zoom
        self.bind("<Control-equal>", lambda e: self.zoom_step(1.2))
        self.bind("<Control-plus>", lambda e: self.zoom_step(1.2))
        self.bind("<Control-KP_Add>", lambda e: self.zoom_step(1.2))
        self.bind("<Control-minus>", lambda e: self.zoom_step(1.0 / 1.2))
        self.bind("<Control-KP_Subtract>", lambda e: self.zoom_step(1.0 / 1.2))
        self.bind("<Control-0>", lambda e: self.reset_zoom())
        self.bind("<Control-KP_0>", lambda e: self.reset_zoom())

        # 3. Barra de Status Inferior Win32
        self.sbar = tk.Frame(self, bg="#d4d0c8", height=22, relief="sunken", bd=1, padx=4, pady=1)
        self.sbar.pack(side="bottom", fill="x")

        p_info = tk.Frame(self.sbar, relief="sunken", bd=1, bg="#d4d0c8", padx=6)
        p_info.pack(side="left", fill="x", expand=True)
        self.lbl_sbar_status = tk.Label(
            p_info,
            text="Catálogo de Moldes pronto | 2 cliques para abrir no editor CAD",
            bg="#d4d0c8",
            fg="#000000",
            font=self.font_btn,
            anchor="w",
        )
        self.lbl_sbar_status.pack(fill="x")

        p_stat = tk.Frame(self.sbar, relief="sunken", bd=1, bg="#d4d0c8", padx=6)
        p_stat.pack(side="right")
        self.lbl_sbar_counts = tk.Label(
            p_stat,
            text="Matriz: 0x0 | 0 moldes",
            bg="#d4d0c8",
            fg="#000000",
            font=self.font_btn,
        )
        self.lbl_sbar_counts.pack()

    def setup_right_panel(self):
        """Monta os 10 botões de ação e o painel informativo lateral."""
        # Grupo: 10 Botões de Ação
        grp_actions = tk.LabelFrame(
            self.panel_right, text="Ações do Catálogo", bg="#d4d0c8", fg="#000000", font=self.font_title, padx=2, pady=2
        )
        grp_actions.pack(fill="x", pady=(0, 4))

        buttons_def = [
            ("Reimportar", self.action_reimport),
            ("Mesclar arq.", self.action_merge_file),
            ("Organizar peças", self.action_organize_pieces),
            ("Espelhar", self.action_flip_shape),
            ("Apagar peça", self.action_delete_shape),
            ("Desfazer (Ctrl+Z)", self.action_undo),
            ("Editar peça", self.action_edit_piece),
            ("Salvar como...", self.action_save_as),
            ("Salvar", self.action_save),
            ("Esc (Fechar)", self.on_close_click),
        ]

        self.action_buttons = {}
        for text, cmd in buttons_def:
            btn = tk.Button(
                grp_actions,
                text=text,
                relief="raised",
                bd=2,
                bg="#d4d0c8",
                fg="#000000",
                font=self.font_btn,
                pady=1,
                anchor="center",
                command=cmd,
            )
            btn.pack(fill="x", pady=1)
            self.action_buttons[text] = btn

        # Grupo: Detalhes da Célula Selecionada (Camada 7)
        self.grp_details = tk.LabelFrame(
            self.panel_right, text="Detalhes da Peça", bg="#d4d0c8", fg="#000000", font=self.font_title, padx=4, pady=3
        )
        self.grp_details.pack(fill="both", expand=True, pady=2)

        self.lbl_det_piece = tk.Label(self.grp_details, text="Peça: Nenhuma", bg="#d4d0c8", font=self.font_btn_bold, anchor="w")
        self.lbl_det_piece.pack(fill="x")

        self.lbl_det_size = tk.Label(self.grp_details, text="Tamanho: -", bg="#d4d0c8", font=self.font_btn, anchor="w")
        self.lbl_det_size.pack(fill="x")

        self.lbl_det_parity = tk.Label(self.grp_details, text="Paridade: [2*]", bg="#d4d0c8", font=self.font_badge, fg="#000080", anchor="w")
        self.lbl_det_parity.pack(fill="x")

        self.lbl_det_dims = tk.Label(self.grp_details, text="Dim: 0.0 x 0.0 mm", bg="#d4d0c8", font=self.font_btn, anchor="w")
        self.lbl_det_dims.pack(fill="x")

        self.lbl_det_area = tk.Label(self.grp_details, text="Área Líq: 0.00 dm²", bg="#d4d0c8", font=self.font_btn, anchor="w")
        self.lbl_det_area.pack(fill="x")

        self.lbl_det_counts = tk.Label(self.grp_details, text="Costuras: 0 | Furos: 0", bg="#d4d0c8", font=self.font_btn, anchor="w")
        self.lbl_det_counts.pack(fill="x")

        self.lbl_det_status = tk.Label(self.grp_details, text="Status: Vazio", bg="#d4d0c8", font=self.font_btn, fg="#666666", anchor="w")
        self.lbl_det_status.pack(fill="x", pady=(2, 0))

    # =========================================================================
    # Camada 2, 3 e 4: Carregamento de Dados e Construção da Matriz Esparsa
    # =========================================================================
    def load_data(self, article_id: int = None):
        """Carrega os dados dos moldes do artigo a partir do banco de dados."""
        if article_id is not None:
            self.article_id = article_id

        if not self.db:
            try:
                import database as db_mod

                self.db = db_mod.DatabaseManager()
            except Exception:
                self.db = None

        if self.db:
            if hasattr(self.db, "get_article_shape_catalog"):
                self.shapes_list = self.db.get_article_shape_catalog(self.article_id)
            else:
                self.shapes_list = self.db.get_shapes_by_article(self.article_id)
        else:
            self.shapes_list = []

        self.rebuild_matrix()
        self.redraw_grid()
        self.update_info_panel()

    def rebuild_matrix(self):
        """
        Organiza a lista de moldes em uma matriz esparsa indexada por (nome_base, tamanho).
        Camada 2 (Colunas) + Camada 3 (Linhas).
        """
        self.grid_matrix.clear()
        pieces_set = set()
        sizes_set = set()
        registered_order = []

        for s in self.shapes_list:
            raw_name = s.get("name", "Molde")
            size = str(s.get("size") or "41")
            base_p = extract_piece_base_name(raw_name, size)
            if base_p not in pieces_set:
                pieces_set.add(base_p)
                registered_order.append(base_p)
            sizes_set.add(size)
            self.grid_matrix[(base_p, size)] = s

        # Ordenação de Colunas (Peças)
        if self.order_mode == "alphabetic":
            self.all_piece_names = sorted(list(pieces_set), key=lambda x: natural_sort_key(x))
        else:
            self.all_piece_names = registered_order

        # Ordenação de Linhas (Tamanhos) usando size_sort_key de ui/sort_utils
        self.all_sizes_list = sorted(list(sizes_set), key=lambda sz: size_sort_key(sz))

        self.update_filter_combos()
        self.apply_filters()

    def update_filter_combos(self):
        if hasattr(self, "combo_size"):
            size_values = ["Todos"] + list(self.all_sizes_list)
            self.combo_size["values"] = size_values
            if self.filter_size not in size_values:
                self.filter_size = "Todos"
            self.combo_size.set(self.filter_size)

        if hasattr(self, "combo_piece"):
            piece_values = ["Todas"] + list(self.all_piece_names)
            self.combo_piece["values"] = piece_values
            if self.filter_piece not in piece_values:
                self.filter_piece = "Todas"
            self.combo_piece.set(self.filter_piece)

    def apply_filters(self):
        """Aplica os filtros de tamanho e peça sobre a matriz do catálogo."""
        if self.filter_piece and self.filter_piece != "Todas":
            self.piece_names = [p for p in self.all_piece_names if p == self.filter_piece]
        else:
            self.piece_names = list(self.all_piece_names)

        if self.filter_size and self.filter_size != "Todos":
            self.sizes_list = [sz for sz in self.all_sizes_list if sz == self.filter_size]
        else:
            self.sizes_list = list(self.all_sizes_list)

        # Atualiza seleção se estiver fora dos limites
        if not self.selected_coords or self.selected_coords[0] >= len(self.piece_names) or self.selected_coords[1] >= len(self.sizes_list):
            found = False
            for r_idx, sz in enumerate(self.sizes_list):
                for c_idx, p in enumerate(self.piece_names):
                    if (p, sz) in self.grid_matrix:
                        self.selected_coords = (c_idx, r_idx)
                        found = True
                        break
                if found:
                    break
            if not found:
                self.selected_coords = (0, 0) if self.piece_names and self.sizes_list else None

        total_cells = len(self.piece_names) * len(self.sizes_list)
        filled_cells = sum(1 for p in self.piece_names for sz in self.sizes_list if (p, sz) in self.grid_matrix)
        self.lbl_sbar_counts.config(
            text=f"Matriz: {len(self.piece_names)}x{len(self.sizes_list)} ({total_cells} cél.) | {filled_cells} moldes"
        )

    def on_size_filter_changed(self, event=None):
        if hasattr(self, "combo_size"):
            self.filter_size = self.combo_size.get()
        self.apply_filters()
        self.redraw_grid()
        self.update_info_panel()

    def on_piece_filter_changed(self, event=None):
        if hasattr(self, "combo_piece"):
            self.filter_piece = self.combo_piece.get()
        self.apply_filters()
        self.redraw_grid()
        self.update_info_panel()

    def reset_filters(self):
        self.filter_size = "Todos"
        self.filter_piece = "Todas"
        if hasattr(self, "combo_size"):
            self.combo_size.set("Todos")
        if hasattr(self, "combo_piece"):
            self.combo_piece.set("Todas")
        self.apply_filters()
        self.redraw_grid()
        self.update_info_panel()

    def zoom_step(self, factor: float):
        """Aplica zoom in ou zoom out centrado, respeitando limites 0.5x a 4.0x."""
        new_zoom = max(0.5, min(4.0, round(self.zoom_factor * factor, 2)))
        if abs(new_zoom - self.zoom_factor) < 1e-3:
            return
        self.zoom_factor = new_zoom
        self.cell_w = int(self.base_cell_w * self.zoom_factor)
        self.cell_h = int(self.base_cell_h * self.zoom_factor)
        self.header_h = int(self.base_header_h * self.zoom_factor)
        self.sidebar_w = int(self.base_sidebar_w * self.zoom_factor)

        if hasattr(self, "lbl_zoom") and self.lbl_zoom:
            self.lbl_zoom.config(text=f"{int(round(self.zoom_factor * 100))}%")

        self.redraw_grid()

    def reset_zoom(self):
        """Restaura o zoom para 100% (1.0x)."""
        self.zoom_factor = 1.0
        self.cell_w = self.base_cell_w
        self.cell_h = self.base_cell_h
        self.header_h = self.base_header_h
        self.sidebar_w = self.base_sidebar_w

        if hasattr(self, "lbl_zoom") and self.lbl_zoom:
            self.lbl_zoom.config(text="100%")

        self.redraw_grid()

    def on_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.config(cursor="fleur")

    def on_pan_motion(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_pan_end(self, event):
        self.canvas.config(cursor="hand2")

    def on_mousewheel(self, event):
        if event.delta > 0:
            self.zoom_step(1.2)
        else:
            self.zoom_step(1.0 / 1.2)

    # =========================================================================
    # Camada 4: Renderização do Grid no Canvas Único
    # =========================================================================
    def redraw_grid(self):
        """Renderiza todo o catálogo de moldes em Canvas único de alta velocidade."""
        self.canvas.delete("all")
        n_cols = len(self.piece_names)
        n_rows = len(self.sizes_list)

        if n_cols == 0 or n_rows == 0:
            self.canvas.create_text(
                200, 100, text="Nenhum molde cadastrado para este artigo.", fill="#94a3b8", font=self.font_title
            )
            return

        total_w = self.sidebar_w + n_cols * self.cell_w + 20
        total_h = self.header_h + n_rows * self.cell_h + 20
        self.canvas.config(scrollregion=(0, 0, total_w, total_h))

        # 1. Header de Colunas (Nomes das Peças e Badge [2*])
        for col_idx, piece_name in enumerate(self.piece_names):
            x1 = self.sidebar_w + col_idx * self.cell_w
            y1 = 0
            x2 = x1 + self.cell_w
            y2 = self.header_h

            # Fundo do header clássico 3D
            self.canvas.create_rectangle(x1, y1, x2, y2, fill="#e2e8f0", outline="#64748b", width=1)
            self.canvas.create_line(x1 + 1, y1 + 1, x2 - 1, y1 + 1, fill="#ffffff")
            self.canvas.create_line(x1 + 1, y1 + 1, x1 + 1, y2 - 1, fill="#ffffff")

            # Badge de Paridade [2*]
            # TODO: Fase 6.2 — ler de shapes.pairs_per_shape se coluna existir
            badge_text = "[2*]"
            bw = 24
            bh = 13
            bx1 = (x1 + x2) / 2.0 - bw / 2.0
            by1 = y1 + 4
            bx2 = bx1 + bw
            by2 = by1 + bh
            self.canvas.create_rectangle(bx1, by1, bx2, by2, fill="#0284c7", outline="#0369a1", width=1)
            self.canvas.create_text((bx1 + bx2) / 2.0, (by1 + by2) / 2.0, text=badge_text, fill="#ffffff", font=self.font_badge)

            # Nome da Peça
            disp_name = piece_name if len(piece_name) <= 13 else piece_name[:12] + "…"
            self.canvas.create_text((x1 + x2) / 2.0, y1 + 27, text=disp_name, fill="#0f172a", font=self.font_title)

        # 2. Sidebar Esquerda de Linhas (Tamanhos)
        for row_idx, size_str in enumerate(self.sizes_list):
            x1 = 0
            y1 = self.header_h + row_idx * self.cell_h
            x2 = self.sidebar_w
            y2 = y1 + self.cell_h

            # Fundo da sidebar de tamanho
            self.canvas.create_rectangle(x1, y1, x2, y2, fill="#334155", outline="#475569", width=1)
            self.canvas.create_line(x1 + 1, y1 + 1, x2 - 1, y1 + 1, fill="#64748b")
            self.canvas.create_text((x1 + x2) / 2.0, (y1 + y2) / 2.0, text=size_str, fill="#f8fafc", font=self.font_title)

        # Canto superior esquerdo (TAM)
        self.canvas.create_rectangle(0, 0, self.sidebar_w, self.header_h, fill="#1e293b", outline="#64748b", width=1)
        self.canvas.create_text(self.sidebar_w / 2.0, self.header_h / 2.0, text="TAM", fill="#94a3b8", font=self.font_title)

        # 3. Matriz de Células Centrais
        for row_idx, size_str in enumerate(self.sizes_list):
            for col_idx, piece_name in enumerate(self.piece_names):
                cx1 = self.sidebar_w + col_idx * self.cell_w
                cy1 = self.header_h + row_idx * self.cell_h
                cx2 = cx1 + self.cell_w
                cy2 = cy1 + self.cell_h

                is_selected = self.selected_coords == (col_idx, row_idx)
                shape_data = self.grid_matrix.get((piece_name, size_str))

                # Fundo da célula
                bg_cell = "#2b3442" if shape_data else "#1e293b"
                border_color = "#f59e0b" if is_selected else "#334155"
                border_w = 2 if is_selected else 1

                self.canvas.create_rectangle(cx1, cy1, cx2, cy2, fill=bg_cell, outline=border_color, width=border_w)

                if shape_data:
                    self.render_shape_cell(shape_data, cx1, cy1, cx2, cy2)
                else:
                    # Célula vazia na matriz esparsa
                    self.canvas.create_text(
                        (cx1 + cx2) / 2.0,
                        (cy1 + cy2) / 2.0,
                        text="[-]",
                        fill="#475569",
                        font=self.font_title,
                    )

    def render_shape_cell(self, shape_data: dict, x1: float, y1: float, x2: float, y2: float):
        """
        Desenha a miniatura vetorial do molde dentro da célula especificada:
        - Contorno branco (#ffffff)
        - Costuras magenta (#ff00ff)
        - Piques em V magenta (#ff00ff)
        - Furos amarelos (#facc15) com cruz
        - Fio da pele ciano (#38bdf8) se existir
        """
        contour = shape_data.get("contour") or []
        if not contour or len(contour) < 3:
            return

        min_x, min_y, max_x, max_y = polygon_bbox(contour)
        w_shape = max(1.0, max_x - min_x)
        h_shape = max(1.0, max_y - min_y)

        # Margens internas da célula
        pad_x = 8
        pad_y = 6
        avail_w = (x2 - x1) - 2 * pad_x
        avail_h = (y2 - y1) - 2 * pad_y

        scale = min(avail_w / w_shape, avail_h / h_shape)

        # Centraliza o molde no retângulo da célula
        off_x = x1 + pad_x + (avail_w - w_shape * scale) / 2.0 - min_x * scale
        off_y = y1 + pad_y + (avail_h - h_shape * scale) / 2.0 - min_y * scale

        def to_screen(wx, wy):
            return (wx * scale + off_x, wy * scale + off_y)

        # 1. Contorno Branco da Peça
        pts_screen = []
        for pt in contour:
            sx, sy = to_screen(pt["x"], pt["y"])
            pts_screen.extend([sx, sy])

        # Preenchimento leve para destacar a forma e contorno nítido
        self.canvas.create_polygon(pts_screen, fill="#243040", outline="#ffffff", width=1.5)

        # 2. Costuras Internas (stitching_json) em Magenta #ff00ff
        for poly in shape_data.get("stitching") or []:
            if isinstance(poly, list) and len(poly) >= 2:
                poly_pts = []
                for pt in poly:
                    sx, sy = to_screen(pt["x"], pt["y"])
                    poly_pts.extend([sx, sy])
                self.canvas.create_line(poly_pts, fill="#ff00ff", width=1.2)

        # 3. Furos de Broca (Amarelo #facc15) e Piques (Magenta #ff00ff)
        for h in shape_data.get("holes") or []:
            hx, hy = to_screen(h["x"], h["y"])
            is_punch = h.get("type") == "PUNCH" or h.get("r", 2.5) <= 1.2
            if is_punch:
                # Pique em V ou traço curto magenta
                sz = 3.0
                self.canvas.create_line(hx - sz, hy - sz, hx, hy, fill="#ff00ff", width=1.5)
                self.canvas.create_line(hx, hy, hx + sz, hy - sz, fill="#ff00ff", width=1.5)
            else:
                # Furo de broca amarelo com cruz
                hr = max(2.0, min(4.0, (h.get("r", 2.5) * scale)))
                self.canvas.create_oval(hx - hr, hy - hr, hx + hr, hy + hr, fill="#facc15", outline="#ca8a04", width=1)
                self.canvas.create_line(hx - hr * 0.7, hy, hx + hr * 0.7, hy, fill="#713f12", width=1)
                self.canvas.create_line(hx, hy - hr * 0.7, hx, hy + hr * 0.7, fill="#713f12", width=1)

        # 4. Fio da Pele (Grain Angle) em Ciano #38bdf8 se existir
        meta = shape_data.get("metadata") or {}
        grain = meta.get("grain_angle_deg")
        if grain is not None:
            mid_x = (min_x + max_x) / 2.0
            mid_y = (min_y + max_y) / 2.0
            cx, cy = to_screen(mid_x, mid_y)
            rad = math.radians(float(grain))
            vec_len = 10.0
            ax = cx + vec_len * math.cos(rad)
            ay = cy + vec_len * math.sin(rad)
            self.canvas.create_line(cx - vec_len * 0.5 * math.cos(rad), cy - vec_len * 0.5 * math.sin(rad), ax, ay, fill="#38bdf8", width=1.2, arrow="last")

    # =========================================================================
    # Camada 5: Interações (Clique, Duplo-clique, Teclado)
    # =========================================================================
    def on_canvas_click(self, event):
        """Clique simples: seleciona a célula e atualiza o painel de informações."""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        col_idx = int((cx - self.sidebar_w) // self.cell_w)
        row_idx = int((cy - self.header_h) // self.cell_h)

        if 0 <= col_idx < len(self.piece_names) and 0 <= row_idx < len(self.sizes_list):
            self.selected_coords = (col_idx, row_idx)
            self.redraw_grid()
            self.update_info_panel()

    def on_canvas_double_click(self, event):
        """Duplo clique: abre a peça no ShapeEditorView."""
        self.on_canvas_click(event)
        self.open_selected_shape()

    def navigate_selection(self, dx: int, dy: int):
        """Navega pela matriz com as teclas direcionais."""
        if not self.selected_coords:
            self.selected_coords = (0, 0)
        else:
            col, row = self.selected_coords
            new_col = max(0, min(len(self.piece_names) - 1, col + dx))
            new_row = max(0, min(len(self.sizes_list) - 1, row + dy))
            self.selected_coords = (new_col, new_row)

        self.redraw_grid()
        self.update_info_panel()
        return "break"

    def get_selected_shape(self):
        """Retorna o molde correspondente à célula selecionada ou None se vazia."""
        if not self.selected_coords:
            return None
        col, row = self.selected_coords
        if 0 <= col < len(self.piece_names) and 0 <= row < len(self.sizes_list):
            p = self.piece_names[col]
            s = self.sizes_list[row]
            return self.grid_matrix.get((p, s))
        return None

    def get_cell_bbox(self, col_idx: int, row_idx: int):
        """Retorna (x1, y1, x2, y2) da célula em coordenadas do canvas."""
        x1 = self.sidebar_w + col_idx * self.cell_w
        y1 = self.header_h + row_idx * self.cell_h
        x2 = x1 + self.cell_w
        y2 = y1 + self.cell_h
        return (x1, y1, x2, y2)

    def get_visible_cells(self):
        """Retorna lista de tuplas (piece, size) atualmente filtradas e presentes no grid."""
        visible = []
        for sz in self.sizes_list:
            for piece in self.piece_names:
                if (piece, sz) in self.grid_matrix:
                    visible.append((piece, sz))
        return visible

    def is_cell_in_viewport(self, col_idx: int, row_idx: int) -> bool:
        """Verifica se o bounding box da célula (col_idx, row_idx) está dentro da área visível do canvas."""
        if col_idx < 0 or col_idx >= len(self.piece_names) or row_idx < 0 or row_idx >= len(self.sizes_list):
            return False
        cx1, cy1, cx2, cy2 = self.get_cell_bbox(col_idx, row_idx)
        vx1 = self.canvas.canvasx(0)
        vy1 = self.canvas.canvasy(0)
        vw = self.canvas.winfo_width()
        vh = self.canvas.winfo_height()
        if vw <= 1:
            vw = 800
        if vh <= 1:
            vh = 600
        vx2 = vx1 + vw
        vy2 = vy1 + vh
        return not (cx2 <= vx1 or cx1 >= vx2 or cy2 <= vy1 or cy1 >= vy2)

    def update_info_panel(self):
        """Atualiza os dados de métricas no painel lateral direito."""
        shape = self.get_selected_shape()
        if not self.selected_coords:
            return

        col, row = self.selected_coords
        piece_name = self.piece_names[col] if col < len(self.piece_names) else ""
        size_str = self.sizes_list[row] if row < len(self.sizes_list) else ""

        if shape:
            contour = shape.get("contour") or []
            holes = shape.get("holes") or []
            stitching = shape.get("stitching") or []

            min_x, min_y, max_x, max_y = polygon_bbox(contour) if len(contour) >= 3 else (0, 0, 0, 0)
            w = max_x - min_x
            h = max_y - min_y
            area_gross_dm2 = (polygon_area(contour) if len(contour) >= 3 else 0.0) / 10000.0
            holes_area = sum(math.pi * (hole.get("r", 2.5) ** 2) for hole in holes) / 10000.0
            area_net_dm2 = max(0.0, area_gross_dm2 - holes_area)

            n_punches = sum(1 for hole in holes if hole.get("type") == "PUNCH" or hole.get("r", 2.5) <= 1.2)
            n_drills = len(holes) - n_punches

            self.lbl_det_piece.config(text=f"Peça: {shape.get('name')}")
            self.lbl_det_size.config(text=f"Tamanho: {size_str}")
            self.lbl_det_parity.config(text="Paridade: [2*] (1E + 1D)")
            self.lbl_det_dims.config(text=f"Dim: {w:.1f} x {h:.1f} mm")
            self.lbl_det_area.config(text=f"Área Líq: {area_net_dm2:.2f} dm²")
            self.lbl_det_counts.config(text=f"Costuras: {len(stitching)} | Furos: {n_drills} | Piques: {n_punches}")
            self.lbl_det_status.config(text="Status: Pronto", fg="#006400")
            self.lbl_sbar_status.config(
                text=f"[{shape.get('name')}] Tam: {size_str} | W: {w:.1f}mm, H: {h:.1f}mm | Pronto para edição"
            )
        else:
            self.lbl_det_piece.config(text=f"Peça: {piece_name}")
            self.lbl_det_size.config(text=f"Tamanho: {size_str}")
            self.lbl_det_parity.config(text="Paridade: [-]")
            self.lbl_det_dims.config(text="Dim: 0.0 x 0.0 mm")
            self.lbl_det_area.config(text="Área Líq: 0.00 dm²")
            self.lbl_det_counts.config(text="Costuras: 0 | Furos: 0")
            self.lbl_det_status.config(text="Status: Vazio [-]", fg="#64748b")
            self.lbl_sbar_status.config(text=f"Célula ({piece_name}, {size_str}) vazia | Moldes ativos: {len(self.grid_matrix)}")

    def open_selected_shape(self):
        """Abre o molde selecionado na tela detalhada do ShapeEditorView."""
        shape = self.get_selected_shape()
        if not shape:
            return
        if self.on_edit_shape_cb:
            shape_id = shape.get("id")
            self.on_edit_shape_cb(shape_id if shape_id else shape)

    # =========================================================================
    # Camada 6: 10 Botões de Ação
    # =========================================================================
    def action_reimport(self):
        """1. Reimportar: recarrega os moldes a partir do banco de dados ignorando cache."""
        self.load_data()
        self.lbl_sbar_status.config(text="Dados do catálogo recarregados do banco com sucesso.")

    def _resolve_duplicate_name(self, name: str) -> str:
        """Verifica nomes existentes no artigo e gera 'Nome (2)', 'Nome (3)' se duplicado."""
        existing_names = {s.get("name") for s in self.shapes_list}
        if name not in existing_names:
            return name

        idx = 2
        while True:
            candidate = f"{name} ({idx})"
            if candidate not in existing_names:
                return candidate
            idx += 1

    def merge_shape_data(self, shape_data: dict) -> int:
        """
        Adiciona os dados de um molde ao artigo atual no banco.
        Se o nome já existir, acrescenta sufixo numérico '(2)', '(3)' etc.
        """
        raw_name = shape_data.get("name", "Molde_Novo")
        final_name = self._resolve_duplicate_name(raw_name)

        shape_id = None
        if self.db:
            shape_id = self.db.create_shape(
                article_id=self.article_id,
                name=final_name,
                contour=shape_data.get("contour", []),
                holes=shape_data.get("holes", []),
                stitching=shape_data.get("stitching", []),
                size=shape_data.get("size", "41"),
            )
        self.load_data()
        return shape_id

    def action_merge_file(self):
        """2. Mesclar arquivo: importa um arquivo .die ou .cmz e adiciona ao artigo."""
        file_paths = filedialog.askopenfilenames(
            title="Mesclar Arquivo Shape (.die / .cmz)",
            filetypes=[("Arquivos Shape ATOM (*.die, *.d)", ("*.die", "*.d")), ("Todos os Arquivos (*.*)", "*.*")],
            parent=self,
        )
        if not file_paths:
            return
        try:
            imported_count = 0
            for fp in file_paths:
                shape_data = parse_die_file(fp)
                self.merge_shape_data(shape_data)
                imported_count += 1
            if not getattr(self, "_suppress_dialogs", False):
                messagebox.showinfo(
                    "Mesclar Arquivos", f"{imported_count} molde(s) mesclado(s) com sucesso ao catálogo!", parent=self
                )
        except Exception as e:
            if not getattr(self, "_suppress_dialogs", False):
                messagebox.showerror("Erro na Importação", f"Falha ao mesclar arquivo:\n{str(e)}", parent=self)

    def action_organize_pieces(self):
        """3. Organizar peças: alterna a ordenação das colunas entre alfabética e ordem de cadastro."""
        self.order_mode = "registered" if self.order_mode == "alphabetic" else "alphabetic"
        self.rebuild_matrix()
        self.redraw_grid()
        self.update_info_panel()
        mode_label = "Alfabética" if self.order_mode == "alphabetic" else "Ordem de Cadastro"
        self.lbl_sbar_status.config(text=f"Colunas organizadas por: {mode_label}.")

    def action_flip_shape(self):
        """4. Espelhar: inverte horizontalmente a peça selecionada e persiste."""
        shape = self.get_selected_shape()
        if not shape:
            messagebox.showwarning("Aviso", "Selecione uma peça válida para espelhar.", parent=self)
            return

        contour = shape.get("contour", [])
        if not contour:
            return

        # Guarda estado na pilha de desfeita local
        self.undo_stack.append(("flip", shape.get("id"), copy.deepcopy(shape)))
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

        min_x, _, max_x, _ = polygon_bbox(contour)
        mid_x = (min_x + max_x) / 2.0

        for pt in contour:
            pt["x"] = round(mid_x - (pt["x"] - mid_x), 2)
        for h in shape.get("holes", []):
            h["x"] = round(mid_x - (h["x"] - mid_x), 2)
        for poly in shape.get("stitching", []):
            if isinstance(poly, list):
                for pt in poly:
                    pt["x"] = round(mid_x - (pt["x"] - mid_x), 2)

        if self.db and shape.get("id"):
            self.db.update_shape(
                shape_id=shape["id"],
                name=shape.get("name"),
                contour=shape.get("contour"),
                holes=shape.get("holes"),
                stitching=shape.get("stitching"),
                folder=shape.get("folder"),
                size=shape.get("size"),
            )

        self.redraw_grid()
        self.update_info_panel()
        self.lbl_sbar_status.config(text=f"Peça '{shape.get('name')}' espelhada horizontalmente com sucesso.")

    def action_delete_shape(self):
        """5. Apagar peça: exclui o molde selecionado do artigo com confirmação."""
        shape = self.get_selected_shape()
        if not shape:
            messagebox.showwarning("Aviso", "Selecione uma peça válida para excluir.", parent=self)
            return

        if messagebox.askyesno(
            "Excluir Peça", f"Deseja realmente excluir a peça '{shape.get('name')}' do artigo?", parent=self
        ):
            shape_id = shape.get("id")
            self.undo_stack.append(("delete", shape_id, copy.deepcopy(shape)))
            if self.db and shape_id:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM shapes WHERE id = ?", (shape_id,))
                    conn.commit()
            self.load_data()
            self.lbl_sbar_status.config(text="Peça excluída do catálogo.")

    def action_undo(self, event=None):
        """6. Desfazer (Ctrl+Z): reverte a última alteração local do catálogo."""
        if not self.undo_stack:
            self.lbl_sbar_status.config(text="Nenhuma alteração para desfazer.")
            return "break"

        action_type, shape_id, old_shape = self.undo_stack.pop()
        if action_type in ("flip", "delete"):
            if self.db and shape_id:
                if action_type == "delete":
                    self.db.create_shape(
                        article_id=self.article_id,
                        name=old_shape.get("name"),
                        contour=old_shape.get("contour"),
                        holes=old_shape.get("holes"),
                        stitching=old_shape.get("stitching"),
                        size=old_shape.get("size"),
                        folder=old_shape.get("folder"),
                    )
                else:
                    self.db.update_shape(
                        shape_id=shape_id,
                        name=old_shape.get("name"),
                        contour=old_shape.get("contour"),
                        holes=old_shape.get("holes"),
                        stitching=old_shape.get("stitching"),
                        size=old_shape.get("size"),
                        folder=old_shape.get("folder"),
                    )
            self.load_data()
            self.lbl_sbar_status.config(text="Última ação desfeita com sucesso.")
        return "break"

    def action_edit_piece(self):
        """7. Editar peça: abre o ShapeEditorView para a peça selecionada."""
        self.open_selected_shape()

    def export_shapes_to_directory(self, folder_path: str) -> int:
        """Exporta todas as peças do artigo para arquivos .die na pasta indicada."""
        exported_count = 0
        dest_dir = Path(folder_path)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for shape in self.shapes_list:
            file_name = f"{shape.get('name', 'molde')}.die"
            out_path = dest_dir / file_name
            save_die_file(shape, str(out_path))
            exported_count += 1
        return exported_count

    def action_save_as(self):
        """8. Salvar como: exporta todas as peças do artigo para arquivos .die."""
        folder = filedialog.askdirectory(title="Selecionar Pasta para Exportar Moldes ATOM (.die)", parent=self)
        if not folder:
            return
        try:
            exported_count = self.export_shapes_to_directory(folder)
            if not getattr(self, "_suppress_dialogs", False):
                messagebox.showinfo("Exportar Catálogo", f"{exported_count} moldes exportados para:\n{folder}", parent=self)
        except Exception as e:
            if not getattr(self, "_suppress_dialogs", False):
                messagebox.showerror("Erro na Exportação", f"Falha ao exportar catálogo:\n{str(e)}", parent=self)

    def action_save(self):
        """9. Salvar: confirma persistência dos dados e sincroniza com o banco de dados."""
        self.load_data()
        self.lbl_sbar_status.config(text="Catálogo sincronizado com o banco de dados.")
        if not getattr(self, "_suppress_dialogs", False):
            try:
                messagebox.showinfo("Salvar Catálogo", "Todas as alterações do catálogo estão salvas no banco de dados.", parent=self)
            except Exception:
                pass

    # =========================================================================
    # Gerenciamento de Janela MDI
    # =========================================================================
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
            except Exception:
                pass
        self.pack_forget()
        self.place_forget()
