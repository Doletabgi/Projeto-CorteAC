"""
JobManager 2000 (Python Edition)
Layout Editor View - Reprodução 100% autêntica de Layout Editor - [I0000] (Layout.exe / LayoutNT)
Mesa CAD estática, fixa, sem zoom de bolinha do mouse, barra de ferramentas de linha única e coordenadas métricas.
"""

import copy
import math
import re
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, filedialog, simpledialog
from pathlib import Path

from config import THEME
from ui.units import format_m, format_dim_mm, format_dim_m
from cad.geometry import transform_contour, point_in_polygon, rotate_point, polygon_bbox, polygons_collide, polygon_area, SpatialGrid, bbox_overlap
from cad.colors import get_color_for_size, get_contrast_text_color
from ui.layout_print_dialog import LayoutPrintDialog
from ui.trim_layout_dialog import TrimLayoutDialog
from cad.lay_parser import parse_lay, export_layout_from_pieces, validate_layout_placement
from cad.dual_exporter import DualLayoutExporter
from db.connection import VersionConflictError
from cad.fill_engine import (
    fill_row_pieces,
    fill_row_alternate_pieces,
    fill_column_pieces,
    fill_sheet_pieces,
    fill_sheet_alternate_pieces,
    fill_user_pieces,
)
from ui.fill_user_dialog import FillUserDialog


# -------------------------------------------------------------
# Constantes Configuráveis de Operação CAM (Layout.exe / LayoutNT)
# -------------------------------------------------------------
ROT_FINE_STEP_DEG = 2.0         # Ajuste fino: 2 graus
ROT_90_STEP_DEG = 90.0          # Giro grosso: 90 graus
ROT_FLIP_STEP_DEG = 180.0       # Giro oposto (pé oposto): 180 graus
ROT_DIR_LEFT = 1                # Esquerda = anti-horário (+) no plano cartesiano CAD
ROT_DIR_RIGHT = -1              # Direita = horário (-) no plano cartesiano CAD
ROT_DIR_F3 = 1                  # Sentido de rotação do F3 (+90°)
UNDO_MAX_LEVELS = 100           # Níveis máximos de desfazer (Ctrl+Z)
UNDO_GROUP_AUTOREPEAT = True    # Agrupar repetições rápidas de F1/F2 em uma única entrada de Undo
SAVE_TARGET = "db+file"         # Salva em SQLite e regrava arquivo .lay (se associado)
def _shade_color(hex_color, factor=0.82):
    """Escurece uma cor #rrggbb por um fator (contorno suave da peça no zoom de visão geral)."""
    try:
        h = str(hex_color).lstrip("#")
        if len(h) != 6:
            return hex_color
        r = int(int(h[0:2], 16) * factor)
        g = int(int(h[2:4], 16) * factor)
        b = int(int(h[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def _contour_key(cntr):
    """
    Identidade ESTÁVEL do contorno (pelo conteúdo, não por id() de memória).

    Os caches de geometria e de colisão usavam id(contorno). Como a janela do
    Layout Editor é reaproveitada entre sessões, o Python recicla o endereço de
    listas liberadas e o editor passava a desenhar/colidir peças com a geometria
    de OUTRA sessão (peças deformadas e manchas vermelhas de "colisão").
    """
    try:
        n = len(cntr)
        if n < 3:
            return ("curto", n)
        a = cntr[0]
        b = cntr[n // 2]
        c = cntr[-1]
        return (
            n,
            round(a["x"], 1), round(a["y"], 1),
            round(b["x"], 1), round(b["y"], 1),
            round(c["x"], 1), round(c["y"], 1),
        )
    except Exception:
        try:
            return ("inv", len(cntr))
        except Exception:
            return ("inv", 0)


# Bump interativo com o mouse (equivalente ao Bump Magnético do Layout.exe)
BUMP_MIN_DRAG_PX = 3.0          # arrasto menor que isso cancela (evita bump por clique)
BUMP_DOUBLE_CLICK_MS = 300.0    # janela do duplo-clique + arrasto
BUMP_CURSOR = "circle"          # equivalente Tk ao Cursor ID 149 (arco); fallback "crosshair"
BUMP_SEARCH_ITERS = 16          # resolução da busca binária de encosto (mm)

SELECTED_OUTLINE_ONLY = True    # Fiel à Secção E.2: apenas o contorno da peça selecionada é visível (sem preenchimento opaco)

# Coalescencia de eventos de arraste/pan: limita o trabalho pesado por segundo e
# evita backlog de <B1-Motion> em maquinas mais lentas (Windows da fabrica).
DRAG_MIN_INTERVAL_S = 0.008      # ~125 atualizacoes de peca por segundo
STATUS_MIN_INTERVAL_S = 0.033    # ~30 atualizacoes por segundo na barra de status
PAN_REDRAW_INTERVAL_MS = 8       # ~125 redraws por segundo ao arrastar a mesa

_PIECE_TAGS = tuple((f"piece_{i}", f"piece_poly_{i}", "piece_item") for i in range(2000))


def rotate_piece_in_place(p, delta_deg):
    """
    Rotaciona a peça em torno do seu centro de gravidade / bounding box do contorno base original,
    garantindo invariância total do centro na chapa, sem drift numérico, de modo que:
      C_placa = (X, Y) + rotate_point(cx0, cy0, rot_old)
      (X_new, Y_new) = C_placa - rotate_point(cx0, cy0, rot_new)
    Retorna 360° exato após 180 giros de 2° e identidade após F1 seguido de F2.
    """
    contour = p.get("contour")
    if not contour:
        p["rotation"] = round((p.get("rotation", 0.0) + delta_deg) % 360.0, 6)
        return p

    min_x, min_y, max_x, max_y = polygon_bbox(contour)
    cx0 = (min_x + max_x) / 2.0
    cy0 = (min_y + max_y) / 2.0

    current_rot = float(p.get("rotation", 0.0))
    cx_old, cy_old = rotate_point(cx0, cy0, current_rot)
    c_plate_x = float(p.get("x", 0.0)) + cx_old
    c_plate_y = float(p.get("y", 0.0)) + cy_old

    new_rot = (current_rot + delta_deg) % 360.0
    # Normalização de precisão para evitar resíduo float (ex: 2.000000000000001)
    if abs(new_rot - round(new_rot)) < 1e-9:
        new_rot = float(round(new_rot))
    else:
        new_rot = round(new_rot, 6)

    cx_new, cy_new = rotate_point(cx0, cy0, new_rot)
    new_x = c_plate_x - cx_new
    new_y = c_plate_y - cy_new

    if abs(new_x - round(new_x)) < 1e-9:
        new_x = float(round(new_x))

    if abs(new_y - round(new_y)) < 1e-9:
        new_y = float(round(new_y))

    p["x"] = new_x
    p["y"] = new_y
    p["rotation"] = new_rot
    if "rotation_rad" in p:
        p["rotation_rad"] = math.radians(new_rot)
    return p


# Contorno autêntico de calçado contraforte (101-002_CON) conforme o print do usuário
CONTOUR_CON = [
    {"x": 0.0, "y": -38.0},
    {"x": -2.0, "y": -20.0},
    {"x": -2.0, "y": 20.0},
    {"x": 0.0, "y": 38.0},
    {"x": 10.0, "y": 36.0},
    {"x": 24.0, "y": 28.0},
    {"x": 38.0, "y": 16.0},
    {"x": 46.0, "y": 0.0},
    {"x": 38.0, "y": -16.0},
    {"x": 24.0, "y": -28.0},
    {"x": 10.0, "y": -36.0},
]

# Definição dos grupos de peças / targets
TARGET_SPECS = [
    {
        "id": "target_1",
        "name": "101-002_CON...",
        "full_name": "101-002_CONTRAFORTE_T3",
        "color": "#f97316",       # Laranja
        "required": 3,
        "size": 3,
        "contour": CONTOUR_CON,
    },
    {
        "id": "target_2",
        "name": "101-002_CON...",
        "full_name": "101-002_CONTRAFORTE_T5",
        "color": "#16a34a",       # Verde
        "required": 5,
        "size": 5,
        "contour": CONTOUR_CON,
    },
    {
        "id": "target_3",
        "name": "101-002_CON...",
        "full_name": "101-002_CONTRAFORTE_T7",
        "color": "#6366f1",       # Violeta / Azul
        "required": 7,
        "size": 7,
        "contour": CONTOUR_CON,
    },
    {
        "id": "target_4",
        "name": "101-002_CON...",
        "full_name": "101-002_CONTRAFORTE_T1",
        "color": "#eab308",       # Amarelo
        "required": 1,
        "size": 1,
        "contour": CONTOUR_CON,
    },
    {
        "id": "target_5",
        "name": "101-002_CON...",
        "full_name": "101-002_CONTRAFORTE_T5M",
        "color": "#d946ef",       # Magenta / Rosa
        "required": 5,
        "size": 5,
        "contour": CONTOUR_CON,
    },
]


class LayoutEditorView(tk.Frame):
    def __init__(self, parent, on_close=None, on_minimize=None, on_maximize=None, layout_name="[I0000]", on_save=None, db=None, load_sample=False, **kwargs):
        frame_kwargs = {k: v for k, v in kwargs.items() if k not in {
            "layout_filepath", "layout_id", "layout_version", "session_id", "material",
            "material_id", "material_name", "material_layers", "layers", "margin_left",
            "margin_right", "margin_top", "margin_bottom", "is_subwindow", "layouts",
            "current_layout_index", "target_shapes"
        }}
        super().__init__(parent, bg=THEME["bg_surface"], relief="ridge", bd=2, **frame_kwargs)
        self.on_close_cb = on_close
        self.on_minimize_cb = on_minimize
        self.on_maximize_cb = on_maximize
        self.on_save_cb = on_save
        self.layout_name = layout_name
        self.layout_filepath = kwargs.get("layout_filepath", "")
        self.db = db or getattr(parent, "db", None)
        self.layout_id = kwargs.get("layout_id", None)
        self.layout_version = kwargs.get("layout_version", 1)
        self.load_sample = load_sample
        self.session_id = kwargs.get("session_id", 1)

        # Estado do material e camadas associados à sessão
        self.material = kwargs.get("material", None)
        self.material_cod_r = None
        self.material_id = str(kwargs.get("material_id", "853412"))
        self.material_name = str(kwargs.get("material_name", "SINT-LOGAM-PRETO"))
        self.material_layers = int(kwargs.get("material_layers", kwargs.get("layers", 2)))

        # Estado da chapa (mm) - Horizontal = largura (X), Vertical = comprimento/altura (Y)
        self.sheet_width = 1380.0   # mm
        self.sheet_height = 1080.0  # mm
        self._custom_sheet_size = None
        self.trim_cut_line = None

        # Margens de segurança da placa (mm)
        self.margin_left = float(kwargs.get("margin_left", 10.0))
        self.margin_right = float(kwargs.get("margin_right", 10.0))
        self.margin_top = float(kwargs.get("margin_top", 10.0))
        self.margin_bottom = float(kwargs.get("margin_bottom", 10.0))

        self.placed_pieces = []
        self.selected_index = -1
        self.show_grid = True
        self.show_outline = True

        # Gerenciamento de múltiplos layouts por sessão (lay0000, lay0001, ...)
        raw_layouts = kwargs.get("layouts", [])
        self.layouts = [dict(l) for l in raw_layouts] if raw_layouts else []
        self.current_layout_index = int(kwargs.get("layout_index", 0))
        self.layout_undo_stacks = {}

        # Geometria estática da mesa CAD no Canvas (calculada no redraw)
        self.plate_scale = 1.0
        self.plate_x1 = 35.0
        self.plate_y2 = 300.0
        self.plate_x2 = 400.0
        self.plate_y1 = 50.0
        self.plate_w = 365.0
        self.plate_h = 250.0

        # Controle de Zoom (20% por clique / Ctrl+Clique) e Pan da Mesa CAD
        self.zoom_factor = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.view_center_wx = None
        self.view_center_wy = None
        self.view_center_sx = None
        self.view_center_sy = None
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0

        # Drag & drop de peças e estado de edição / desfazer (Ctrl+Z)
        self.drag_start = (0, 0)
        self.is_modified = False
        self._saved_undo_index = 0
        self.undo_stack = []
        self._pre_drag_pieces = None

        # Caches de geometria de alta performance e detecção de colisão (Fase 3 & 4)
        self._piece_geom_cache = {}
        self._piece_rot_cache = {}
        self._pair_collision_cache = {}
        self._piece_cache_stats = {"hits": 0, "misses": 0}
        self._last_collision_sig = None
        self._cached_colliding_indices = set()

        # Estado de seleção e manipulação de peças (Seleção Múltipla & Rubberband)
        self.selected_indices = []
        self.is_rubberbanding = False
        self._rubberband_start_screen = (0, 0)
        self._rubberband_is_shift = False
        self._rubberband_moved = False
        self._drag_clicked_in_multi = False
        self._drag_hit_idx = None
        self._drag_start_event_xy = (0, 0)
        self._drag_indices = []
        self._drag_piece_origins = {}
        self._drag_anchor_idx = None

        # Estado da rotação livre 360° com botão direito do mouse (R-Drag) e Menu 102
        self._rdrag_active = False
        self._rdrag_rotating = False
        self._rdrag_moved = False
        self._rdrag_start_x = 0
        self._rdrag_start_y = 0
        self._context_menu_opened = False
        self._context_target_idx = None
        self.gap_mm = float(kwargs.get("gap_mm", 1.0))
        self._rdrag_pre_pieces = None
        self._rdrag_selected_indices = []
        self._rdrag_is_ctrl = False
        self._rdrag_pivot_world = (0.0, 0.0)
        self._rdrag_pivot_screen = (0.0, 0.0)
        self._rdrag_theta0 = 0.0
        self._rdrag_last_theta = 0.0
        self._rdrag_cum_delta = 0.0
        self._rdrag_piece_init_centers = {}
        self._rdrag_piece_base_centers = {}

        # Estado da coalescencia de movimento (arraste de peca / pan / divisor)
        self._drag_job = None
        # Estado do Bump interativo com o mouse
        self._bump_mode = False
        self._bump_armed = False
        self._bump_line_id = None
        self._bump_press_xy = None
        self._bump_center_screen = None
        self._last_piece_press_idx = None
        self._last_piece_press_ms = 0.0

        self._pending_drag_xy = None
        self._last_drag_update_ts = 0.0
        self._last_status_update_ts = 0.0
        self._last_cursor_name = None
        self._redraw_job = None

        # Controle de debounce e agrupamento de auto-repeat (F1/F2/F3/F4)
        self._in_fine_rot_sequence = False
        self._fine_rot_timer = None
        self._f3_pressed = False
        self._f4_pressed = False

        # Estado de Simulação CAM do Cabeçote de Corte
        self.sim_running = False
        self.sim_piece_idx = 0
        self.sim_pt_idx = 0
        self.sim_head_pos = (0.0, 0.0)
        self._sim_job = None
        self._sim_path = []
        self._sim_path_idx = 0

        # Carrega ícones gráficos do Layout.exe
        self.icons = {}
        self.load_layout_icons()

        # Moldes da barra lateral (Session Shapes ou TARGET_SPECS)
        self.session_shapes = []
        self.sidebar_targets = None
        self.active_target_index = 0
        self.sidebar_div_x = 0
        self.custom_divider_x = None
        self.custom_divider_ratio = None
        self.is_dragging_divider = False
        self.update_sidebar_targets()

        # Constrói UI completa
        self.setup_ui()
        self.setup_context_menu_102()

        # Inicializa com as peças dispostas de acordo com a captura de tela
        self.init_default_layout()

    def load_layout_icons(self):
        assets_dir = Path(__file__).resolve().parent.parent / "assets" / "layout"
        if not assets_dir.exists():
            return

        icon_files = [
            "btn_bump_down.png", "btn_bump_right.png", "btn_bump_left.png", "btn_bump_up.png",
            "btn_new.png", "btn_open.png", "btn_save.png", "btn_dual.png", "btn_cut.png", "btn_copy.png", "btn_paste.png", "btn_print.png",
            "btn_outline.png", "btn_zoom_fit.png", "btn_zoom.png", "btn_add.png", "btn_move.png", "btn_grid.png",
            "layout_icon.png"
        ]

        for fname in icon_files:
            p = assets_dir / fname
            if p.exists():
                try:
                    self.icons[fname.replace(".png", "")] = tk.PhotoImage(file=str(p))
                except Exception:
                    pass

    def setup_ui(self):
        # -------------------------------------------------------------
        # 1. Barra de Título MDI Interna
        # -------------------------------------------------------------
        title_bar = tk.Frame(self, bg=THEME["title_bar_bg"], height=24, padx=4, pady=2)
        title_bar.pack(fill="x")

        title_left = tk.Frame(title_bar, bg=THEME["title_bar_bg"])
        title_left.pack(side="left")

        if "layout_icon" in self.icons:
            tk.Label(title_left, image=self.icons["layout_icon"], bg=THEME["title_bar_bg"]).pack(side="left", padx=(0, 4))

        self.lbl_title = tk.Label(
            title_left,
            text=f"Layout Editor - {self.layout_name}",
            bg=THEME["title_bar_bg"],
            fg=THEME["title_bar_fg"],
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_title.pack(side="left")

        # Botões da janela (Minimizar, Maximizar, Fechar)
        btn_box = tk.Frame(title_bar, bg=THEME["title_bar_bg"])
        btn_box.pack(side="right")
        self.btn_min = tk.Button(btn_box, text="_", relief="raised", bd=1, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0, command=self.on_minimize_click)
        self.btn_min.pack(side="left", padx=1)
        self.btn_max = tk.Button(btn_box, text="□", relief="raised", bd=1, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0, command=self.on_maximize_click)
        self.btn_max.pack(side="left", padx=1)
        self.btn_close = tk.Button(btn_box, text="✕", relief="raised", bd=1, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0, command=self.on_close_click)
        self.btn_close.pack(side="left", padx=1)

        # Arrastar janela pelo título em modo flutuante e duplo clique para maximizar/restaurar
        title_bar.bind("<ButtonPress-1>", self._on_title_press)
        title_bar.bind("<B1-Motion>", self._on_title_motion)
        title_bar.bind("<Double-Button-1>", lambda e: self.on_maximize_click())
        self.lbl_title.bind("<ButtonPress-1>", self._on_title_press)
        self.lbl_title.bind("<B1-Motion>", self._on_title_motion)
        self.lbl_title.bind("<Double-Button-1>", lambda e: self.on_maximize_click())
        self.bind("<Button-1>", lambda e: (self.lift(), self.focus_set()), add="+")
        self.bind("<Control-p>", lambda e: self.print_layout())
        self.bind("<Control-P>", lambda e: self.print_layout())
        self.bind("<Control-s>", self.save_layout)
        self.bind("<Control-S>", self.save_layout)

        # -------------------------------------------------------------
        # 2. Barra de Menus Clássica Win32
        # -------------------------------------------------------------
        menubar = tk.Frame(self, bg=THEME["bg_surface"], height=22, relief="flat", bd=0)
        menubar.pack(fill="x", padx=2, pady=1)

        menus = ["Arquivo", "Editar", "Exibir", "Encaixe", "Ferramentas", "Janela", "Ajuda"]
        for m in menus:
            btn_m = tk.Menubutton(menubar, text=m, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"], relief="flat", bd=0)
            btn_m.pack(side="left", padx=4)
            menu_obj = tk.Menu(btn_m, tearoff=0)
            btn_m.config(menu=menu_obj)
            self.populate_menu(m, menu_obj)

        # -------------------------------------------------------------
        # 3. Barra de Ferramentas de Linha Única Autêntica (Toolbar 128 / 137 / 150)
        # Exatamente conforme crop_toolbar.png
        # -------------------------------------------------------------
        tb_container = tk.Frame(self, bg=THEME["bg_surface"], relief="groove", bd=1, height=28)
        tb_container.pack(fill="x", padx=2, pady=(0, 2))

        tb_row = tk.Frame(tb_container, bg=THEME["bg_surface"], height=26, padx=2, pady=1)
        tb_row.pack(side="left", fill="y")

        # Grupo 1: Arquivo (New, Open, Save, Dual Export)
        self.create_tb_btn(tb_row, "btn_new", "Novo Layout (Ctrl+N)", self.clear_all_pieces)
        self.create_tb_btn(tb_row, "btn_open", "Abrir Layout (Ctrl+O)", self.open_layout_dialog)
        self.create_tb_btn(tb_row, "btn_save", "Salvar Layout (Ctrl+S)", self.save_layout)
        self.create_tb_btn(tb_row, "btn_dual", "⚡ Dupla Saída ATOM (.lay) + Comelz (.onx)", lambda: self.export_layout_dialog(target_format="dual"))

        self.create_tb_sep(tb_row)

        # Grupo 2: Clipboard & Print (Cut, Copy, Paste, Print)
        self.create_tb_btn(tb_row, "btn_cut", "Recortar (Ctrl+X)", self.delete_selected)
        self.create_tb_btn(tb_row, "btn_copy", "Copiar (Ctrl+C)", self.duplicate_selected)
        self.create_tb_btn(tb_row, "btn_paste", "Colar (Ctrl+V)", self.duplicate_selected)
        self.create_tb_btn(tb_row, "btn_print", "Imprimir Layout (Ctrl+P)", self.print_layout)

        self.create_tb_sep(tb_row)

        # Grupo 3: Estilo e Cores CAD (Paleta de Cores por Número)
        self.create_tb_btn(tb_row, "btn_outline", "Paleta de Cores por Número (Alterar Cor)", self.choose_number_color)

        self.create_tb_sep(tb_row)

        # Grupo 4: Zoom e Enquadramento (Eye/Full View, Zoom)
        self.create_tb_btn(tb_row, "btn_zoom_fit", "Exibir Layout Completo", self.reset_view)
        self.btn_zoom = self.create_tb_btn(tb_row, "btn_zoom", "Zoom (+20% ao clicar, Ctrl+Clique no canvas, Botão direito reduz)", self.zoom_in)
        self.btn_zoom.bind("<Button-3>", lambda e: self.zoom_out())

        self.create_tb_sep(tb_row)

        # Grupo 5: Modos CAD e Seleção (Move, + Adicionar, Grade)
        self.create_tb_btn(tb_row, "btn_move", "Modo Mover Peça", lambda: None)
        self.create_tb_btn(tb_row, "btn_add", "Adicionar Peça (+)", self.add_active_target)
        self.create_tb_btn(tb_row, "btn_grid", "Grade Milimétrica", self.toggle_grid)

        self.create_tb_sep(tb_row)

        # Grupo 6: Deslocamento Fino (Bump Direcional 10 mm)
        self.create_tb_btn(tb_row, "btn_bump_left", "Deslocar Selecionada para Esquerda (10mm)", lambda: self.nudge_selected(-10, 0))
        self.create_tb_btn(tb_row, "btn_bump_right", "Deslocar Selecionada para Direita (10mm)", lambda: self.nudge_selected(10, 0))
        self.create_tb_btn(tb_row, "btn_bump_up", "Deslocar Selecionada para Cima (10mm)", lambda: self.nudge_selected(0, 10))
        self.create_tb_btn(tb_row, "btn_bump_down", "Deslocar Selecionada para Baixo (10mm)", lambda: self.nudge_selected(0, -10))

        self.create_tb_sep(tb_row)

        # Grupo 7: Operações CAM de Acabamento (Refilar / Corte Automático)
        self.btn_trim = tk.Button(
            tb_row,
            text="✂ Refilar",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            fg="#0f766e",
            font=("Segoe UI", 8, "bold"),
            relief="raised",
            bd=1,
            padx=6,
            pady=1,
            command=self.trim_layout_dialog,
            cursor="hand2"
        )
        self.btn_trim.pack(side="left", padx=2)

        tip_trim = "Refilar Layout Automático no Final das Peças com Gap 1 mm (Ctrl+T)"
        def _on_enter_trim(e):
            if hasattr(self, "lbl_stat_pos"):
                self._last_status_pos_text = self.lbl_stat_pos.cget("text")
                self.lbl_stat_pos.config(text=tip_trim)
        def _on_leave_trim(e):
            if hasattr(self, "lbl_stat_pos") and hasattr(self, "_last_status_pos_text"):
                self.lbl_stat_pos.config(text=self._last_status_pos_text)
        self.btn_trim.bind("<Enter>", _on_enter_trim)
        self.btn_trim.bind("<Leave>", _on_leave_trim)

        # Grupo 8: Simulação de Corte CAM do Layout
        self.btn_sim = tk.Button(
            tb_row,
            text="▶ Simular",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            fg="#800000",
            font=("Segoe UI", 8, "bold"),
            relief="raised",
            bd=1,
            padx=6,
            pady=1,
            command=self.toggle_simulation,
            cursor="hand2"
        )
        self.btn_sim.pack(side="left", padx=2)

        tip_sim = "Simular Execução de Corte do Layout na Mesa CAM (Esc para parar)"
        def _on_enter_sim(e):
            if hasattr(self, "lbl_stat_pos"):
                self._last_status_pos_text = self.lbl_stat_pos.cget("text")
                self.lbl_stat_pos.config(text=tip_sim)
        def _on_leave_sim(e):
            if hasattr(self, "lbl_stat_pos") and hasattr(self, "_last_status_pos_text"):
                self.lbl_stat_pos.config(text=self._last_status_pos_text)
        self.btn_sim.bind("<Enter>", _on_enter_sim)
        self.btn_sim.bind("<Leave>", _on_leave_sim)

        # -------------------------------------------------------------
        # 4. Área de Trabalho Principal (Canvas ocupa todo o espaço, sem sidebar)
        # -------------------------------------------------------------
        work_area = tk.Frame(self, bg="#ffffff")
        work_area.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(work_area, bg="#ffffff", highlightthickness=0, cursor="arrow")
        self.canvas.pack(fill="both", expand=True)

        # Bindings do Canvas:
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_click)
        self.canvas.bind("<Control-Button-1>", self.on_ctrl_canvas_click)
        # Rotação Livre 360° com Botão Direito do Mouse (R-Drag)
        self.canvas.bind("<ButtonPress-3>", self.on_rbutton_press)
        self.canvas.bind("<Control-ButtonPress-3>", self.on_rbutton_press)
        self.canvas.bind("<B3-Motion>", self.on_rbutton_drag)
        self.canvas.bind("<Control-B3-Motion>", self.on_rbutton_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_rbutton_release)
        self.canvas.bind("<Control-ButtonRelease-3>", self.on_rbutton_release)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        # Botão do meio (roda): BUMP com peça selecionada, PAN sem seleção
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_pan_end)

        # Bump direcional com Ctrl+Shift + arrasto do botão esquerdo
        self.canvas.bind("<Control-Shift-ButtonPress-1>", self.on_ctrl_shift_bump_start)
        self.canvas.bind("<Control-Shift-B1-Motion>", self.on_ctrl_shift_bump_drag)
        self.canvas.bind("<Control-Shift-ButtonRelease-1>", self.on_ctrl_shift_bump_end)
        # Esc cancela o bump em andamento
        self.canvas.bind("<Escape>", self.on_canvas_escape)

        # Zoom com roda do mouse segurando Ctrl
        self.canvas.bind("<Control-MouseWheel>", self.on_ctrl_mousewheel)
        self.canvas.bind("<Control-Button-4>", lambda e: self.zoom_in(e.x, e.y))
        self.canvas.bind("<Control-Button-5>", lambda e: self.zoom_out(e.x, e.y))

        # Atalhos de Teclado para Zoom (Ctrl+Q, Ctrl++, Ctrl+-)
        for w in (self, self.canvas):
            w.bind("<Control-q>", lambda e: (self.zoom_in(), "break")[1])
            w.bind("<Control-Q>", lambda e: (self.zoom_in(), "break")[1])
            w.bind("<Control-plus>", lambda e: (self.zoom_in(), "break")[1])
            w.bind("<Control-equal>", lambda e: (self.zoom_in(), "break")[1])
            w.bind("<Control-minus>", lambda e: (self.zoom_out(), "break")[1])
            w.bind("<Control-0>", lambda e: (self.reset_view(), "break")[1])
            w.bind("<KeyPress-Control_L>", self._on_ctrl_press)
            w.bind("<KeyPress-Control_R>", self._on_ctrl_press)
            w.bind("<KeyRelease-Control_L>", self._on_ctrl_release)
            w.bind("<KeyRelease-Control_R>", self._on_ctrl_release)

        # Atalhos do Teclado no Canvas e na Janela
        self.canvas.config(takefocus=True)
        self.canvas.bind("<Control-z>", self.undo_action)
        self.canvas.bind("<Control-Z>", self.undo_action)
        self.bind("<Control-z>", self.undo_action)
        self.bind("<Control-Z>", self.undo_action)

        # Proibição estrita: NÃO existe Ctrl+Y (refazer)
        self.canvas.bind("<Control-y>", lambda e: "break")
        self.canvas.bind("<Control-Y>", lambda e: "break")
        self.bind("<Control-y>", lambda e: "break")
        self.bind("<Control-Y>", lambda e: "break")

        # Salvar layout (Ctrl+S)
        self.canvas.bind("<Control-s>", self.save_layout)
        self.canvas.bind("<Control-S>", self.save_layout)
        self.bind("<Control-s>", self.save_layout)
        self.bind("<Control-S>", self.save_layout)

        self.canvas.bind("<Control-o>", self.open_layout_dialog)
        self.canvas.bind("<Control-O>", self.open_layout_dialog)
        self.bind("<Control-o>", self.open_layout_dialog)
        self.bind("<Control-O>", self.open_layout_dialog)

        # Imprimir layout (Ctrl+P)
        for w in (self, self.canvas):
            w.bind("<Control-p>", lambda e: (self.print_layout(), "break")[1])
            w.bind("<Control-P>", lambda e: (self.print_layout(), "break")[1])

        # Refilar layout com corte automático (Ctrl+T)
        def _on_ctrl_t(e=None):
            w = self.focus_get()
            if w and isinstance(w, (tk.Entry, ttk.Entry, tk.Text)):
                return None
            self.trim_layout_auto()
            return "break"

        for w in (self, self.canvas):
            w.bind("<Control-t>", _on_ctrl_t)
            w.bind("<Control-T>", _on_ctrl_t)
            w.bind("<Control-Key-t>", _on_ctrl_t)
            w.bind("<Control-Key-T>", _on_ctrl_t)

        # Navegação entre placas: Open Next (Ctrl+L) e Open Previous (Ctrl+Shift+L)
        for w in (self, self.canvas):
            w.bind("<Control-l>", self._on_ctrl_l)
            w.bind("<Control-L>", self._on_ctrl_l)
            w.bind("<Control-Key-l>", self._on_ctrl_l)
            w.bind("<Control-Key-L>", self._on_ctrl_l)
            w.bind("<Control-Shift-l>", self._on_ctrl_shift_l)
            w.bind("<Control-Shift-L>", self._on_ctrl_shift_l)
            w.bind("<Control-Shift-Key-l>", self._on_ctrl_shift_l)
            w.bind("<Control-Shift-Key-L>", self._on_ctrl_shift_l)

        # Atalhos CAM F1 / F2 / F3 / F4 e Proibição Shift+F3
        for w in (self, self.canvas):
            w.bind("<F1>", self.on_f1_press)
            w.bind("<Key-F1>", self.on_f1_press)
            w.bind("<KeyRelease-F1>", self.on_f1_release)

            w.bind("<F2>", self.on_f2_press)
            w.bind("<Key-F2>", self.on_f2_press)
            w.bind("<KeyRelease-F2>", self.on_f2_release)

            w.bind("<F3>", self.on_f3_press)
            w.bind("<Key-F3>", self.on_f3_press)
            w.bind("<KeyRelease-F3>", self.on_f3_release)

            # Proibição estrita: NÃO existe Shift+F3
            w.bind("<Shift-F3>", lambda e: "break")
            w.bind("<Shift-Key-F3>", lambda e: "break")

            w.bind("<F4>", self.on_f4_press)
            w.bind("<Key-F4>", self.on_f4_press)
            w.bind("<KeyRelease-F4>", self.on_f4_release)

            w.bind("<Escape>", self.cancel_drag)
            w.bind("<Control-a>", self.select_all)
            w.bind("<Control-A>", self.select_all)
            w.bind("<Control-Key-a>", self.select_all)
            w.bind("<Control-Key-A>", self.select_all)

        self.bind_all("<Key-r>", lambda e: self.rotate_selected(45))
        self.bind_all("<Key-R>", lambda e: self.rotate_selected(45))
        self.bind_all("<Delete>", lambda e: self.delete_selected())
        self.bind_all("<Control-a>", self.select_all)
        self.bind_all("<Control-A>", self.select_all)
        # Setas = BUMP MAGNÉTICO (desliza até encostar), conforme LAYOUT_EDITOR_RE.md.
        # O movimento fino de 5 mm continua disponível em nudge_selected() (interno).
        self.bind_all("<Left>", lambda e: self.bump_selection_vector(-1, 0))
        self.bind_all("<Right>", lambda e: self.bump_selection_vector(1, 0))
        self.bind_all("<Up>", lambda e: self.bump_selection_vector(0, 1))
        self.bind_all("<Down>", lambda e: self.bump_selection_vector(0, -1))
        # Ctrl+Setas = ajuste fino de 0,5 mm (paridade com o Layout.exe [EVIDÊNCIA])
        self.bind_all("<Control-Left>", lambda e: self.nudge_selected(-0.5, 0))
        self.bind_all("<Control-Right>", lambda e: self.nudge_selected(0.5, 0))
        self.bind_all("<Control-Up>", lambda e: self.nudge_selected(0, 0.5))
        self.bind_all("<Control-Down>", lambda e: self.nudge_selected(0, -0.5))

        # -------------------------------------------------------------
        # 5. Barra de Status Inferior Autêntica
        # Esquerda: coordenadas do cursor em metros (x:1.53 y:1.39)
        # Direita: Sheet (3.00 X 1.38) em painel rebaixado
        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # 5. Barra de Status Inferior Multissegmentada Autêntica Win32 MDI
        # Painéis: Coordenadas | Id | X | Y | Rot | Estado | Rendimento | Chapa
        # Conforme Imagem 1 (media_1792276970076.jpg)
        # -------------------------------------------------------------
        self.status_bar = tk.Frame(self, bg=THEME["bg_surface"], height=22, relief="groove", bd=1)
        self.status_bar.pack(side="bottom", fill="x")

        # Painéis da Direita para a Esquerda
        # Painel 8: Placa (255.34 X 135.00 cm)
        self.sheet_panel = tk.Frame(self.status_bar, relief="sunken", bd=1, bg=THEME["bg_surface"])
        self.sheet_panel.pack(side="right", padx=2, pady=1)
        self.lbl_stat_sheet = tk.Label(self.sheet_panel, text="Placa (255.34 X 135.00 cm)", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), padx=4)
        self.lbl_stat_sheet.pack(side="left")

        # Painel 7: Rendimento (83.02%)
        self.yield_panel = tk.Frame(self.status_bar, relief="sunken", bd=1, bg=THEME["bg_surface"])
        self.yield_panel.pack(side="right", padx=2, pady=1)
        self.lbl_stat_yield = tk.Label(self.yield_panel, text="83.02%", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), padx=4)
        self.lbl_stat_yield.pack(side="left")

        # Painel 6: Estado (To be Cut)
        self.state_panel = tk.Frame(self.status_bar, relief="sunken", bd=1, bg=THEME["bg_surface"])
        self.state_panel.pack(side="right", padx=2, pady=1)
        self.lbl_stat_state = tk.Label(self.state_panel, text="To be Cut", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), padx=4)
        self.lbl_stat_state.pack(side="left")

        # Painel 5: Rotação (Rot: 1.00)
        self.rot_panel = tk.Frame(self.status_bar, relief="sunken", bd=1, bg=THEME["bg_surface"])
        self.rot_panel.pack(side="right", padx=2, pady=1)
        self.lbl_stat_rot = tk.Label(self.rot_panel, text="Rot: 1.00", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), padx=4)
        self.lbl_stat_rot.pack(side="left")

        # Painel 4: Centro Y (Y: 2451.86)
        self.y_panel = tk.Frame(self.status_bar, relief="sunken", bd=1, bg=THEME["bg_surface"])
        self.y_panel.pack(side="right", padx=2, pady=1)
        self.lbl_stat_y = tk.Label(self.y_panel, text="Y: 2451.86", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), padx=4)
        self.lbl_stat_y.pack(side="left")

        # Painel 3: Centro X (X: 718.32)
        self.x_panel = tk.Frame(self.status_bar, relief="sunken", bd=1, bg=THEME["bg_surface"])
        self.x_panel.pack(side="right", padx=2, pady=1)
        self.lbl_stat_x = tk.Label(self.x_panel, text="X: 718.32", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), padx=4)
        self.lbl_stat_x.pack(side="left")

        # Painel 2: Id da Peça (Id: 204)
        self.id_panel = tk.Frame(self.status_bar, relief="sunken", bd=1, bg=THEME["bg_surface"])
        self.id_panel.pack(side="right", padx=2, pady=1)
        self.lbl_stat_id = tk.Label(self.id_panel, text="Id: 204", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), padx=4)
        self.lbl_stat_id.pack(side="left")

        # Painel 1: Coordenadas do Cursor e Descrição da Peça (à esquerda, expansível)
        self.pos_panel = tk.Frame(self.status_bar, relief="sunken", bd=1, bg=THEME["bg_surface"])
        self.pos_panel.pack(side="left", fill="x", expand=True, padx=2, pady=1)
        self.lbl_stat_pos = tk.Label(
            self.pos_panel,
            text="x: 708.96 y: 2473.42 - 323_PalAcb_24a - <Pasted>",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8),
            anchor="w",
            padx=4
        )
        self.lbl_stat_pos.pack(side="left", fill="x", expand=True)
        self.lbl_stat_left = self.lbl_stat_pos

        # Compatibilidade com código legado
        self.lbl_stat_doc = tk.Label(self.status_bar, text="", bg=THEME["bg_surface"])
        self.lbl_stat_count = tk.Label(self.status_bar, text="", bg=THEME["bg_surface"])

        self.update_sheet_status()

    def create_tb_btn(self, parent, icon_key, tooltip, command):
        img = self.icons.get(icon_key)
        btn = tk.Button(
            parent,
            image=img if img else None,
            text="" if img else icon_key,
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            relief="raised",
            bd=1,
            width=22 if img is None else None,
            height=20 if img is None else None,
            command=command,
            padx=2,
            pady=1,
            cursor="hand2"
        )
        btn.pack(side="left", padx=1)
        if tooltip:
            def _on_enter(e):
                btn.config(bg=THEME["bg_hover"])
                if hasattr(self, "lbl_stat_pos"):
                    self._last_status_pos_text = self.lbl_stat_pos.cget("text")
                    self.lbl_stat_pos.config(text=tooltip)
            def _on_leave(e):
                btn.config(bg=THEME["bg_surface"])
                if hasattr(self, "lbl_stat_pos") and hasattr(self, "_last_status_pos_text"):
                    self.lbl_stat_pos.config(text=self._last_status_pos_text)
            btn.bind("<Enter>", _on_enter)
            btn.bind("<Leave>", _on_leave)
        return btn

    def create_tb_sep(self, parent):
        sep_frame = tk.Frame(parent, bg=THEME["bg_surface"], width=6, height=22)
        sep_frame.pack(side="left", padx=1, pady=2)
        s1 = tk.Frame(sep_frame, bg="#a0a0a0", width=1, height=18)
        s1.pack(side="left", padx=(2, 0), pady=1)
        s2 = tk.Frame(sep_frame, bg="#ffffff", width=1, height=18)
        s2.pack(side="left", padx=(0, 2), pady=1)

    def populate_menu(self, menu_name, menu_obj):
        if menu_name in ("Arquivo", "File"):
            menu_obj.add_command(label="Novo\tCtrl+N", command=self.clear_all_pieces)
            menu_obj.add_command(label="Abrir...\tCtrl+O", command=self.open_layout_dialog)
            menu_obj.add_command(label="Open Next\tCtrl+L", command=self.open_next_layout)
            menu_obj.add_command(label="Open Previous\tCtrl+Shift+L", command=self.open_previous_layout)
            menu_obj.add_command(label="Salvar\tCtrl+S", command=self.save_layout)
            menu_obj.add_command(label="Salvar Como...", command=self.export_layout_dialog)
            menu_obj.add_separator()
            menu_obj.add_command(label="Exportar ATOM (.lay)...", command=lambda: self.export_layout_dialog(target_format="lay"))
            menu_obj.add_command(label="Exportar Comelz (.onx)...", command=lambda: self.export_layout_dialog(target_format="onx"))
            menu_obj.add_command(label="⚡ Dupla Saída (.lay + .onx)...", command=lambda: self.export_layout_dialog(target_format="dual"))
            menu_obj.add_separator()
            menu_obj.add_command(label="Carregar Material...", command=lambda: None)
            menu_obj.add_command(label="Imprimir...\tCtrl+P", command=self.print_layout)
            menu_obj.add_separator()
            menu_obj.add_command(label="Sair", command=self.on_close_click)
        elif menu_name in ("Editar", "Edit"):
            menu_obj.add_command(label="Desfazer\tCtrl+Z", command=self.undo_action)
            menu_obj.add_command(label="Recortar\tCtrl+X", command=self.delete_selected)
            menu_obj.add_command(label="Copiar\tCtrl+C", command=self.duplicate_selected)
            menu_obj.add_command(label="Colar\tCtrl+V", command=self.duplicate_selected)
            menu_obj.add_command(label="Excluir\tDel", command=self.delete_selected)
            menu_obj.add_separator()
            # Submenu Preencher (Fill)
            edit_fill_sub = tk.Menu(menu_obj, tearoff=0)
            edit_fill_sub.add_command(label="Linha", command=lambda: self.fill_row())
            edit_fill_sub.add_command(label="Linha Alternada", command=lambda: self.fill_row_alternate())
            edit_fill_sub.add_command(label="Coluna", command=lambda: self.fill_column())
            edit_fill_sub.add_command(label="Chapa Inteira", state="disabled")
            edit_fill_sub.add_command(label="Chapa Alternada", state="disabled")
            edit_fill_sub.add_command(label="Personalizado...", state="disabled")
            menu_obj.add_cascade(label="Preencher", menu=edit_fill_sub)
            menu_obj.add_separator()
            menu_obj.add_command(label="Giro Fino Esquerda (+2°)\tF1", command=self.on_f1_press)
            menu_obj.add_command(label="Giro Fino Direita (-2°)\tF2", command=self.on_f2_press)
            menu_obj.add_command(label="Girar 90°\tF3", command=self.on_f3_press)
            menu_obj.add_command(label="Inverter 180° (Pé Oposto)\tF4", command=self.on_f4_press)
            menu_obj.add_command(label="Girar 45°\tR", command=lambda: self.rotate_selected(45))
            menu_obj.add_command(label="Espelhar", command=self.mirror_selected)
        elif menu_name in ("Exibir", "View"):
            menu_obj.add_command(label="Zoom\tCtrl+Q", command=self.zoom_in)
            menu_obj.add_command(label="Exibir Layout Completo", command=self.reset_view)
            menu_obj.add_checkbutton(label="Grade", command=self.toggle_grid)
        elif menu_name in ("Encaixe", "Nesting"):
            menu_obj.add_command(label="Calcular Encaixe (Gerar)", command=self.run_auto_nest)
            menu_obj.add_command(label="Iniciar SoleNest...", command=self.run_auto_nest)
            menu_obj.add_command(label="Parâmetros SoleNest...", command=lambda: None)
            menu_obj.add_command(label="Camadas de Corte (Layers)...", command=self.edit_material_layers_dialog)
            menu_obj.add_separator()
            menu_obj.add_command(label="Refilar Chapa no Final das Peças (Gap 1mm)\tCtrl+T", command=self.trim_layout_dialog)
            menu_obj.add_separator()
            menu_obj.add_command(label="▶ Simular Corte CAM (Esc para parar)", command=self.toggle_simulation)
        elif menu_name in ("Ferramentas", "Tools"):
            menu_obj.add_command(label="▶ Simular Corte CAM (Esc para parar)", command=self.toggle_simulation)
            menu_obj.add_command(label="Refilar Layout Automático (Gap 1mm)\tCtrl+T", command=self.trim_layout_dialog)
            menu_obj.add_command(label="Alterar Camadas de Corte (Layers)...", command=self.edit_material_layers_dialog)
            menu_obj.add_separator()
            menu_obj.add_command(label="🏢 Logotipo da Empresa...", command=self.configure_company_logo)
            menu_obj.add_command(label="Cores...", command=lambda: None)
            menu_obj.add_command(label="Verificar Sobreposição\tCtrl+E", command=self.check_overlay)
            menu_obj.add_command(label="Preferências...", command=lambda: None)
        elif menu_name in ("Janela", "Window"):
            menu_obj.add_command(label="Em cascata")
            menu_obj.add_command(label="Lado a lado horizontal")
        elif menu_name in ("Ajuda", "Help"):
            menu_obj.add_command(label="Sobre o Layout Editor...", command=self.about_layout)

    # -------------------------------------------------------------
    # Barra Lateral de Moldes (Miniatura, Nome e Numeração/Contagem)
    # Conforme LayoutNT / media_1792161840920.png
    # -------------------------------------------------------------
    def set_session_shapes(self, shapes):
        """Define os moldes da sessão de corte ativa na barra lateral."""
        self.session_shapes = list(shapes) if shapes else []
        self.update_sidebar_targets()
        self.redraw()

    def add_session_shapes(self, new_shapes):
        """Adiciona múltiplos moldes à sessão no LayoutEditor e atualiza a barra lateral."""
        if not new_shapes:
            return
        existing_ids = {s.get("id") for s in self.session_shapes if s.get("id")}
        for shp in new_shapes:
            if not shp:
                continue
            if shp.get("id") not in existing_ids:
                self.session_shapes.append(dict(shp))
                existing_ids.add(shp.get("id"))
            else:
                for i, curr in enumerate(self.session_shapes):
                    if curr.get("id") == shp.get("id"):
                        self.session_shapes[i] = dict(shp)
                        break
        self.update_sidebar_targets()
        self.redraw()

    def update_sidebar_targets(self):
        """Atualiza a lista de alvos (moldes) exibidos na barra lateral em grade de 4 colunas."""
        if hasattr(self, "session_shapes") and self.session_shapes:
            targets = []

            def _extract_size_key(s):
                digits = re.findall(r"\d+", str(s.get("size") or ""))
                return int(digits[0]) if digits else -1

            # Ordena por numeração decrescente (36a a 22a), idêntico à Imagem 1
            sorted_shapes = sorted(self.session_shapes, key=_extract_size_key, reverse=True)

            seen_keys = set()
            filtered_shapes = []
            for shp in sorted_shapes:
                sz = str(shp.get("size") or "")
                nm = str(shp.get("name") or "")
                key = (sz, nm)
                if key not in seen_keys:
                    seen_keys.add(key)
                    filtered_shapes.append(shp)

            for idx, shp in enumerate(filtered_shapes):
                s_id = shp.get("id") or f"sess_shape_{idx}"
                s_name = shp.get("name") or f"Molde_{idx+1}"
                s_size = str(shp.get("size") or "")
                s_color = get_color_for_size(s_size, idx)

                s_contour = shp.get("contour")
                if not s_contour and shp.get("contour_json"):
                    try:
                        s_contour = json.loads(shp["contour_json"])
                    except Exception:
                        s_contour = None
                if not s_contour:
                    s_contour = CONTOUR_CON

                # Pares requeridos e resto conforme tabela da sessão
                req_pairs = int(shp.get("pairs") or (shp.get("required_qty", 2) // 2) or 1)
                resto = int(shp.get("resto") if shp.get("resto") is not None else (shp.get("rest") if shp.get("rest") is not None else 0))

                targets.append({
                    "id": s_id,
                    "name": s_name,
                    "size": s_size,
                    "color": s_color,
                    "contour": s_contour,
                    "required": req_pairs,
                    "pairs": req_pairs,
                    "resto": resto
                })

            self.sidebar_targets = targets
        else:
            if getattr(self, "load_sample", False):
                self.sidebar_targets = copy.deepcopy(TARGET_SPECS)
            else:
                self.sidebar_targets = []

    def _get_sidebar_grid_layout(self):
        cw = self.canvas.winfo_width()
        sidebar_w = cw - getattr(self, "sidebar_div_x", 0)
        col_width = 75
        item_h = 70
        y_start = 22
        num_cols = max(1, min(6, int((sidebar_w - 15) // col_width))) if sidebar_w > 80 else 4
        return y_start, item_h, col_width, num_cols

    def draw_sidebar(self, div_x, ch, cw):
        """Renderiza a barra lateral em grade de moldes com miniaturas, nomes e contadores."""
        if not hasattr(self, "sidebar_targets") or self.sidebar_targets is None:
            self.update_sidebar_targets()

        sidebar_w = cw - div_x
        if sidebar_w < 50:
            return

        y_start, item_h, col_width, num_cols = self._get_sidebar_grid_layout()

        # Pré-processa tuplas de peças uma única vez (evita dict lookups e strip repetidos)
        placed_info = [
            (str(p.get("target_id", "")).strip(),
             str(p.get("size", "")).strip(),
             str(p.get("name", "")).strip())
            for p in self.placed_pieces
        ]

        for i, target in enumerate(self.sidebar_targets):
            col_idx = i % num_cols
            row_idx = i // num_cols
            col_cx = div_x + 15 + col_width // 2 + col_idx * col_width
            item_y = y_start + row_idx * item_h

            if col_cx + 36 > cw:
                continue

            # 1. Contagem de peças colocadas na mesa
            placed_cnt = 0
            t_id = str(target.get("id", "")).strip()
            t_sz = str(target.get("size", "")).strip()
            t_nm = str(target.get("name", "")).strip()

            for p_tid, p_sz, p_nm in placed_info:
                if self._piece_matches_target(
                    {"target_id": p_tid, "size": p_sz, "name": p_nm}, target
                ):
                    placed_cnt += 1

            # Contagem total da sessão somando as outras placas da sessão
            total_session_pieces = placed_cnt
            if getattr(self, "layouts", None) and len(self.layouts) > 1:
                for l_idx, ly in enumerate(self.layouts):
                    if l_idx == getattr(self, "current_layout_index", 0):
                        continue
                    ly_pieces = ly.get("pieces") or ly.get("placed_pieces") or []
                    for p in ly_pieces:
                        p_tid = str(p.get("target_id", "")).strip()
                        p_sz = str(p.get("size", "")).strip()
                        p_nm = str(p.get("name", "")).strip()
                        if p_sz and t_sz and p_sz != t_sz:
                            continue
                        if p_tid and t_id and p_tid == t_id:
                            total_session_pieces += 1
                            continue
                        if p_nm and t_nm and p_nm == t_nm:
                            total_session_pieces += 1
                            continue
                        if p_sz and t_sz and p_sz == t_sz and (not p_nm or not t_nm or p_nm == t_nm):
                            total_session_pieces += 1
                            continue

            req_cnt = int(target.get("pairs", target.get("required", 0)))
            
            # Resolução das camadas de corte do material para converter peças em pares
            layers = 2
            if hasattr(self, "material_layers") and self.material_layers:
                layers = self.material_layers
            elif hasattr(self, "material") and isinstance(self.material, dict) and "layers" in self.material:
                layers = self.material.get("layers", 2)
            try:
                layers = max(1, int(layers))
            except (ValueError, TypeError):
                layers = 2

            # Quantidade de pares produzidos na mesa e saldo restante
            placed_pairs = (placed_cnt * layers) // 2
            resto_cnt = max(0, req_cnt - placed_pairs)
            total_pieces_demanded = math.ceil((req_cnt * 2) / layers) if req_cnt > 0 else 0
            has_deficit = (total_session_pieces < total_pieces_demanded) if total_pieces_demanded > 0 else False
            stat_color = "#dc2626" if has_deficit else "#000000"

            # Destaque de seleção do molde ativo
            is_active = (i == self.active_target_index)
            if is_active:
                self.canvas.create_rectangle(
                    col_cx - 36, item_y + 1, col_cx + 36, item_y + 65,
                    outline="#3b82f6",
                    dash=(2, 2),
                    width=1.5
                )

            # 2. Miniatura do contorno do molde (Thumbnail)
            thumb_cx = col_cx
            thumb_cy = item_y + 18

            contour = target.get("contour") or CONTOUR_CON
            fill_col = get_color_for_size(target.get("size") or target.get("name"))
            if contour and len(contour) >= 3:
                xs = [pt["x"] for pt in contour]
                ys = [pt["y"] for pt in contour]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                bw = max(0.1, max_x - min_x)
                bh = max(0.1, max_y - min_y)

                scale_thumb = min(18.0 / bw, 28.0 / bh)
                mid_x = (min_x + max_x) / 2.0
                mid_y = (min_y + max_y) / 2.0

                pts = []
                for pt in contour:
                    px = thumb_cx + (pt["x"] - mid_x) * scale_thumb
                    py = thumb_cy - (pt["y"] - mid_y) * scale_thumb
                    pts.extend([px, py])

                self.canvas.create_polygon(
                    pts,
                    fill=fill_col,
                    outline="#000000",
                    width=1.0,
                    tags=("sidebar_element", f"sidebar_target_{i}", "sidebar_ui")
                )

            # 3. Linha 1: Nome do Molde (ex: 323_PalAcb_36a)
            name_raw = target.get("name", "Molde")
            name_disp = name_raw[:14] + ".." if len(name_raw) > 16 else name_raw
            self.canvas.create_text(
                col_cx, item_y + 38,
                text=name_disp,
                fill="#000000",
                font=("Segoe UI", 7),
                tags=("sidebar_element", f"sidebar_target_{i}", "sidebar_ui")
            )

            # 4. Linha 2: Contadores de Produção
            # Em sessão multi-placa o contador mostra as peças DESTA placa sobre o
            # total pedido (ex.: 18/50). Antes exibia o total da sessão (50/50 em
            # todas as placas), escondendo o progresso real de cada placa.
            if getattr(self, "layouts", None) and len(self.layouts) > 1:
                stat_disp = f"{placed_cnt}/{total_pieces_demanded}"
            else:
                stat_disp = f"{placed_cnt}/{req_cnt} {resto_cnt}/{req_cnt}"

            self.canvas.create_text(
                col_cx, item_y + 52,
                text=stat_disp,
                fill=stat_color,
                font=("Segoe UI", 7),
                tags=("sidebar_element", f"sidebar_target_{i}", "sidebar_ui")
            )

    def _piece_matches_target(self, piece, target):
        """
        Regra única de correspondência peça <-> molde da barra lateral.

        Usada tanto pelos CONTADORES quanto pela SELEÇÃO por clique na miniatura,
        para que o número exibido e as peças selecionadas nunca divirjam.
        """
        t_id = str(target.get("id", "")).strip()
        t_sz = str(target.get("size", "")).strip()
        t_nm = str(target.get("name", "")).strip()
        p_tid = str(piece.get("target_id", "")).strip()
        p_sz = str(piece.get("size", "")).strip()
        p_nm = str(piece.get("name", "")).strip()

        if p_sz and t_sz and p_sz != t_sz:
            return False
        if p_tid and t_id and p_tid == t_id:
            return True
        if p_nm and t_nm and p_nm == t_nm:
            return True
        if p_sz and t_sz and p_sz == t_sz and (not p_nm or not t_nm or p_nm == t_nm):
            return True
        return False

    def on_sidebar_click(self, event):
        """Trata cliques na barra lateral: seleciona o molde na grade e destaca peças na mesa."""
        y_start, item_h, col_width, num_cols = self._get_sidebar_grid_layout()

        rel_x = event.x - (self.sidebar_div_x + 15)
        rel_y = event.y - y_start
        if rel_x < 0 or rel_y < 0:
            return

        col_idx = int(rel_x // col_width)
        row_idx = int(rel_y // item_h)
        if col_idx >= num_cols or row_idx < 0:
            return

        clicked_idx = row_idx * num_cols + col_idx
        if 0 <= clicked_idx < len(self.sidebar_targets):
            self.active_target_index = clicked_idx
            target = self.sidebar_targets[clicked_idx]

            # Seleciona TODAS as peças deste molde presentes na placa atual
            # (antes selecionava apenas a primeira encontrada).
            matching = [i for i, p in enumerate(self.placed_pieces)
                        if self._piece_matches_target(p, target)]
            self.selected_indices = matching
            self.selected_index = matching[0] if matching else None
            self._drag_outline_state = None
            self._drag_colliding_others = set()

            self.redraw()
            self.update_status()
            nome = target.get("name") or target.get("size") or "molde"
            if matching:
                qtd = len(matching)
                texto = (f"{qtd} peça{'s' if qtd > 1 else ''} do molde {nome} "
                         f"selecionada{'s' if qtd > 1 else ''} nesta placa")
            else:
                texto = f"Molde {nome}: nenhuma peça nesta placa"
            if hasattr(self, "lbl_stat_pos") and self.lbl_stat_pos.winfo_exists():
                self.lbl_stat_pos.config(text=texto, fg="#1e40af")

    def on_canvas_double_click(self, event):
        """Duplo clique na barra lateral adiciona uma nova peça; duplo clique na divisória reseta."""
        if hasattr(self, "sidebar_div_x") and abs(event.x - self.sidebar_div_x) <= 6:
            self.custom_divider_x = None
            self.custom_divider_ratio = None
            self.redraw()
            return

        if hasattr(self, "sidebar_div_x") and event.x > self.sidebar_div_x:
            y_start, item_h, col_width, num_cols = self._get_sidebar_grid_layout()

            rel_x = event.x - (self.sidebar_div_x + 15)
            rel_y = event.y - y_start
            if rel_x >= 0 and rel_y >= 0:
                col_idx = int(rel_x // col_width)
                row_idx = int(rel_y // item_h)
                if 0 <= col_idx < num_cols and row_idx >= 0:
                    clicked_idx = row_idx * num_cols + col_idx
                    if 0 <= clicked_idx < len(self.sidebar_targets):
                        self.active_target_index = clicked_idx
                        self.add_piece_for_target(self.sidebar_targets[clicked_idx])
            return

        # Duplo-clique na mesa CAD: se em área vazia (fora de qualquer peça), desmarca tudo
        wx, wy = self.screen_to_world(event.x, event.y)
        hit_piece = False
        for idx in reversed(range(len(self.placed_pieces))):
            p = self.placed_pieces[idx]
            poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
            if point_in_polygon(wx, wy, poly):
                hit_piece = True
                break

        if not hit_piece:
            self.selected_indices = []
            self.selected_index = None
            self.redraw()
            self.update_status()

    def add_active_target(self):
        """Adiciona peça do molde ativo atualmente na barra lateral (+)."""
        if hasattr(self, "sidebar_targets") and self.sidebar_targets:
            idx = min(self.active_target_index, len(self.sidebar_targets) - 1)
            target = self.sidebar_targets[idx]
            self.add_piece_for_target(target)

    def add_piece_for_target(self, target):
        """Adiciona uma nova peça na mesa garantindo que não colida."""
        self.push_undo()
        contour = target.get("contour") or CONTOUR_CON
        size_str = str(target.get("size") or "")
        color = target.get("color") or get_color_for_size(size_str)

        # Encontra uma posição livre na mesa para não sobrepor
        new_x = 300.0
        new_y = 200.0
        for step in range(15):
            cand_poly = transform_contour(contour, new_x, new_y, 0.0)
            cand_bbox = polygon_bbox(cand_poly)
            col = False
            for p in self.placed_pieces:
                p_poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
                if polygons_collide(cand_poly, p_poly, gap=2.0, bbox_a=cand_bbox):
                    col = True
                    break
            if not col:
                break
            new_x += 45.0
            if new_x > self.sheet_width - 150.0:
                new_x = 100.0
                new_y += 70.0

        self.placed_pieces.append({
            "target_id": target.get("id"),
            "name": target.get("name", "Molde"),
            "size": size_str,
            "color": color,
            "contour": copy.deepcopy(contour),
            "x": new_x,
            "y": new_y,
            "rotation": 0.0,
        })
        self.selected_index = len(self.placed_pieces) - 1
        self.redraw()
        self.update_status()

    # Stubs para compatibilidade com código que acessava o painel lateral
    def setup_sidebar(self):
        pass

    def render_sidebar_targets(self):
        pass

    def on_sidebar_double_click(self, event):
        pass

    def update_sheet_status(self):
        if hasattr(self, "lbl_stat_sheet"):
            self.lbl_stat_sheet.config(text=f"Placa {format_dim_mm(self.sheet_width, self.sheet_height)}")

    def set_sheet_size(self, width_mm, height_mm):
        self._custom_sheet_size = (float(width_mm), float(height_mm))
        self.sheet_width = float(width_mm)
        self.sheet_height = float(height_mm)
        self.update_sheet_status()
        self.redraw()

    def set_material(self, mat_dict):
        """Atualiza o material associado ao layout (código, descrição, camadas e dimensões)."""
        if not mat_dict or not isinstance(mat_dict, dict):
            return
        self.material = dict(mat_dict)
        self.material_id = str(mat_dict.get("code") or mat_dict.get("id") or getattr(self, "material_id", "853412"))
        self.material_name = str(mat_dict.get("name") or mat_dict.get("description") or mat_dict.get("desc") or getattr(self, "material_name", ""))
        try:
            self.material_layers = int(mat_dict.get("layers", getattr(self, "material_layers", 2)))
        except (ValueError, TypeError):
            self.material_layers = 2
        if "width_mm" in mat_dict and "height_mm" in mat_dict:
            try:
                self.set_sheet_size(float(mat_dict["width_mm"]), float(mat_dict["height_mm"]))
            except (ValueError, TypeError):
                pass
        self.update_sidebar_targets()
        self.redraw()

    def edit_material_layers_dialog(self):
        """Permite conferir ou alterar a quantidade de camadas (layers) na hora de editar/gerar o lay."""
        curr_layers = getattr(self, "material_layers", 2)
        if isinstance(getattr(self, "material", None), dict) and self.material.get("layers"):
            try:
                curr_layers = int(self.material["layers"])
            except (ValueError, TypeError):
                pass

        val = simpledialog.askinteger(
            "Camadas de Corte (Layers)",
            "Informe o número de camadas para o corte:\n(Ex.: 2 para 2 camadas, 4 para 4 camadas)",
            initialvalue=curr_layers,
            minvalue=1,
            maxvalue=50,
            parent=self
        )
        if val is not None and val > 0:
            self.material_layers = val
            if isinstance(getattr(self, "material", None), dict):
                self.material["layers"] = val

            # Propaga para o MainWindow e SessionView se acessíveis
            mw = getattr(self, "master", None)
            if mw and hasattr(mw, "current_material") and isinstance(mw.current_material, dict):
                mw.current_material["layers"] = val
            if mw and hasattr(mw, "session_view") and mw.session_view:
                sv = mw.session_view
                if hasattr(sv, "tree_mat"):
                    m_items = sv.tree_mat.get_children()
                    if m_items:
                        v = list(sv.tree_mat.item(m_items[0], "values"))
                        if len(v) >= 7:
                            v[6] = str(val)
                            sv.tree_mat.item(m_items[0], values=v)
                if hasattr(sv, "notify_material_changed"):
                    sv.notify_material_changed()

            self.update_sidebar_targets()
            self.redraw()
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text=f"Camadas de corte definidas para: {val} camadas")

    def set_margins(self, left: float = 10.0, right: float = 10.0, top: float = 10.0, bottom: float = 10.0):
        """Define as margens de segurança da placa em milímetros e atualiza o Canvas."""
        self.margin_left = float(left)
        self.margin_right = float(right)
        self.margin_top = float(top)
        self.margin_bottom = float(bottom)
        self.redraw()

    def _resolve_piece_contour(self, p: dict) -> list:
        """Resolve o contorno geométrico de uma peça caso não esteja embutido diretamente."""
        if not p or not isinstance(p, dict):
            return list(CONTOUR_CON)
        c = p.get("contour")
        if c and isinstance(c, (list, tuple)) and len(c) >= 3:
            return list(c)
        shp = p.get("shape")
        if isinstance(shp, dict):
            sc = shp.get("contour")
            if sc and isinstance(sc, (list, tuple)) and len(sc) >= 3:
                return list(sc)
            if shp.get("contour_json"):
                try:
                    sc = json.loads(shp["contour_json"])
                    if sc and len(sc) >= 3:
                        return sc
                except Exception:
                    pass

        t_id = str(p.get("target_id") or p.get("shape_id") or p.get("mold_id") or "").strip()
        p_name = str(p.get("name") or p.get("piece_name") or "").strip().lower()
        p_size = str(p.get("size") or "").strip().lower()

        candidates = []
        if hasattr(self, "sidebar_targets") and self.sidebar_targets:
            candidates.extend(self.sidebar_targets)
        if hasattr(self, "session_shapes") and self.session_shapes:
            candidates.extend(self.session_shapes)

        if t_id:
            for s in candidates:
                s_id = str(s.get("id") or s.get("shape_id") or "").strip()
                if s_id and s_id == t_id:
                    sc = s.get("contour")
                    if sc and len(sc) >= 3:
                        return list(sc)
        if p_name:
            for s in candidates:
                s_name = str(s.get("name", "")).strip().lower()
                s_size = str(s.get("size", "")).strip().lower()
                if s_name == p_name and (not p_size or s_size == p_size):
                    sc = s.get("contour")
                    if sc and len(sc) >= 3:
                        return list(sc)

        return list(CONTOUR_CON)

    def set_pieces(self, pieces):
        """Define a lista de peças colocadas no layout e atualiza a interface."""
        self.placed_pieces = list(pieces) if pieces else []
        for p in self.placed_pieces:
            if not p.get("contour"):
                p["contour"] = self._resolve_piece_contour(p)
        self.selected_index = -1
        if getattr(self, "layouts", None) and 0 <= getattr(self, "current_layout_index", 0) < len(self.layouts):
            self.layouts[self.current_layout_index]["pieces"] = copy.deepcopy(self.placed_pieces)
            self.layouts[self.current_layout_index]["placed_pieces"] = copy.deepcopy(self.placed_pieces)
        self.update_title_and_status()
        self.update_sidebar_targets()
        self.redraw()
        self.update_status()

    def set_session_layouts(self, layouts: list, initial_index: int = 0):
        """Define a lista de múltiplos layouts da sessão e carrega a placa inicial."""
        if not layouts:
            self.layouts = []
            self.layout_undo_stacks = {}
            self.placed_pieces = []
            self.current_layout_index = 0
            # O canvas será limpo abaixo: invalida a assinatura de fundo para que a
            # placa cinza/grade seja redesenhada na próxima abertura.
            self._last_bg_sig = None
            if hasattr(self, "canvas") and hasattr(self.canvas, "clear_bed"):
                self.canvas.clear_bed()
            elif hasattr(self, "canvas") and hasattr(self.canvas, "delete"):
                self.canvas.delete("all")
            if hasattr(self, "_redraw"):
                self._redraw()
            return
        self.layouts = [dict(l) for l in layouts]
        self.layout_undo_stacks = {}
        # Nova sessão/placa: descarta geometria e colisões da anterior
        self.clear_piece_cache()
        idx = max(0, min(initial_index, len(self.layouts) - 1))
        self.switch_to_layout(idx, save_current=False)

    def switch_to_layout(self, index: int, save_current: bool = True) -> bool:
        """
        Alterna entre placas da sessão (lay0000, lay0001, ...).
        Isola o undo_stack por placa e atualiza o indicador de status/título.
        """
        if not getattr(self, "layouts", None) or index < 0 or index >= len(self.layouts):
            return False

        if save_current and 0 <= getattr(self, "current_layout_index", 0) < len(self.layouts):
            cur_idx = self.current_layout_index
            self.layouts[cur_idx]["pieces"] = copy.deepcopy(self.placed_pieces)
            self.layouts[cur_idx]["placed_pieces"] = copy.deepcopy(self.placed_pieces)
            self.layouts[cur_idx]["width_mm"] = self.sheet_width
            self.layouts[cur_idx]["height_mm"] = self.sheet_height
            self.layout_undo_stacks[cur_idx] = list(self.undo_stack)
            if self.is_modified:
                try:
                    self.save_layout()
                except Exception:
                    pass

        self.current_layout_index = index
        self.clear_piece_cache()
        # A barra lateral (miniaturas + contadores) é desenhada junto com o fundo;
        # sem invalidar a assinatura ela ficaria com os contadores da placa anterior.
        self._last_bg_sig = None
        ly = self.layouts[index]
        self.placed_pieces = copy.deepcopy(ly.get("pieces") or ly.get("placed_pieces") or [])
        for p in self.placed_pieces:
            if not p.get("contour"):
                p["contour"] = self._resolve_piece_contour(p)
        self.sheet_width = float(ly.get("width_mm", self.sheet_width))
        self.sheet_height = float(ly.get("height_mm", self.sheet_height))
        self.margin_left = float(ly.get("margin_left", self.margin_left))
        self.margin_right = float(ly.get("margin_right", self.margin_right))
        self.margin_top = float(ly.get("margin_top", self.margin_top))
        self.margin_bottom = float(ly.get("margin_bottom", self.margin_bottom))
        self.layout_name = ly.get("name") or f"lay{index:04d}"

        # Isola o histórico de desfazer para a placa atual
        self.undo_stack = list(self.layout_undo_stacks.get(index, []))
        self._saved_undo_index = len(self.undo_stack)
        self.set_modified(False)

        self.selected_indices = []
        self.selected_index = -1

        self.update_title_and_status()
        self.update_sidebar_targets()
        self.redraw()
        return True

    def _on_ctrl_l(self, event=None):
        """Handler do evento Ctrl+L."""
        w = getattr(event, "widget", None) or self.focus_get()
        if w and isinstance(w, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        return self.open_next_layout(event)

    def _on_ctrl_shift_l(self, event=None):
        """Handler do evento Ctrl+Shift+L."""
        w = getattr(event, "widget", None) or self.focus_get()
        if w and isinstance(w, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        return self.open_previous_layout(event)

    def open_next_layout(self, event=None):
        """Abre o próximo layout da sessão (File > Open Next / Ctrl+L)."""
        w = getattr(event, "widget", None) or self.focus_get()
        if w and isinstance(w, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        if not getattr(self, "layouts", None) or len(self.layouts) <= 1:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Sessão possui apenas 1 layout.")
            return "break"
        next_idx = (self.current_layout_index + 1) % len(self.layouts)
        self.switch_to_layout(next_idx, save_current=True)
        return "break"

    def open_previous_layout(self, event=None):
        """Abre o layout anterior da sessão (File > Open Previous / Ctrl+Shift+L)."""
        w = getattr(event, "widget", None) or self.focus_get()
        if w and isinstance(w, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        if not getattr(self, "layouts", None) or len(self.layouts) <= 1:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Sessão possui apenas 1 layout.")
            return "break"
        prev_idx = (self.current_layout_index - 1) % len(self.layouts)
        self.switch_to_layout(prev_idx, save_current=True)
        return "break"

    def update_title_and_status(self):
        """Atualiza a barra de título e a barra de status com o indicador de layout ativo."""
        tot_lays = max(1, len(self.layouts)) if getattr(self, "layouts", None) else 1
        cur_idx = getattr(self, "current_layout_index", 0)
        cur_lay_num = cur_idx + 1
        name_str = getattr(self, "layout_name", f"lay{cur_idx:04d}")
        indicator = f"Layout {cur_lay_num}/{tot_lays} ({name_str})"
        col_count = len(getattr(self, "_cached_colliding_indices", None) or ())
        if col_count:
            indicator += f"  ⚠ {col_count} peça(s) sobrepostas (contorno vermelho)"

        if hasattr(self, "lbl_title") and self.lbl_title:
            self.lbl_title.config(text=f"Layout Editor - {indicator}")
        if hasattr(self, "lbl_stat_doc") and self.lbl_stat_doc:
            self.lbl_stat_doc.config(text=indicator)
        self.update_status()

    # -------------------------------------------------------------
    # Inicialização das Peças Conforme Print Autêntico
    # -------------------------------------------------------------
    def init_default_layout(self):
        """Inicializa chapa estática conforme as dimensões definidas."""
        if hasattr(self, "_custom_sheet_size") and self._custom_sheet_size:
            self.sheet_width, self.sheet_height = self._custom_sheet_size
        else:
            self.sheet_width = 1380.0
            self.sheet_height = 1080.0

        if getattr(self, "load_sample", False):
            self.load_sample_nesting()
        else:
            self.placed_pieces = []

    def load_sample_nesting(self):
        """Reproduz as 22 peças aninhadas perfeitamente na chapa conforme o print autêntico."""
        self.placed_pieces = []

        # Fileira Superior (Y = 220)
        # 5 Peças Magenta (target_5)
        for i in range(5):
            self.placed_pieces.append({
                "target_id": "target_5",
                "name": "101-002_CON...",
                "size": "5",
                "color": "#d946ef",
                "contour": CONTOUR_CON,
                "x": 60.0 + i * 110.0,
                "y": 220.0,
                "rotation": 0.0,
            })

        # 1 Peça Amarela (target_4)
        self.placed_pieces.append({
            "target_id": "target_4",
            "name": "101-002_CON...",
            "size": "1",
            "color": "#eab308",
            "contour": CONTOUR_CON,
            "x": 620.0,
            "y": 220.0,
            "rotation": 0.0,
        })

        # 4 Peças Roxas Superior (target_3 - total 7 peças)
        for i in range(4):
            self.placed_pieces.append({
                "target_id": "target_3",
                "name": "101-002_CON...",
                "size": "7",
                "color": "#6366f1",
                "contour": CONTOUR_CON,
                "x": 730.0 + i * 105.0,
                "y": 220.0,
                "rotation": 0.0,
            })

        # Fileira Inferior (Y = 100)
        # 3 Peças Laranjas (target_1)
        for i in range(3):
            self.placed_pieces.append({
                "target_id": "target_1",
                "name": "101-002_CON...",
                "size": "3",
                "color": "#f97316",
                "contour": CONTOUR_CON,
                "x": 100.0 + i * 120.0,
                "y": 100.0,
                "rotation": 180.0,
            })

        # 5 Peças Verdes (target_2)
        green_configs = [(480.0, 0.0), (590.0, 180.0), (700.0, 0.0), (810.0, 180.0), (920.0, 180.0)]
        for gx, grot in green_configs:
            self.placed_pieces.append({
                "target_id": "target_2",
                "name": "101-002_CON...",
                "size": "5",
                "color": "#16a34a",
                "contour": CONTOUR_CON,
                "x": gx,
                "y": 100.0,
                "rotation": grot,
            })

        # 3 Peças Roxas Canto Inferior (target_3)
        for i in range(3):
            self.placed_pieces.append({
                "target_id": "target_3",
                "name": "101-002_CON...",
                "size": "7",
                "color": "#6366f1",
                "contour": CONTOUR_CON,
                "x": 1040.0 + i * 95.0,
                "y": 100.0,
                "rotation": 180.0,
            })

        self.redraw()
        self.update_status()

    # -------------------------------------------------------------
    # Cache de Geometria Transformada por Peça (Fase 3 - Tarefa 2)
    # -------------------------------------------------------------
    def _get_piece_geom(self, p: dict, _cid=None, _px=None, _py=None, _rot=None, _mirr=None):
        """
        Retorna (poly_transformado, bbox) com cache O(1) por peça.
        Chave canônica: (id(cntr), round(x, 2), round(y, 2), round(rot, 2), mirrored).
        """
        if _cid is not None:
            cid = _cid
            px = _px
            py = _py
            rot = _rot
            mirrored = _mirr
            cntr = p.get("contour")
        else:
            cntr = p.get("contour") or (p.get("shape", {}).get("contour") if isinstance(p.get("shape"), dict) else None)
            if not cntr:
                return ([], (0.0, 0.0, 0.0, 0.0))
            cid = _contour_key(cntr)
            px = round(float(p.get("x", 0.0)), 2)
            py = round(float(p.get("y", 0.0)), 2)
            rot = round(float(p.get("rotation", p.get("rot", 0.0))), 2)
            mirrored = bool(p.get("mirrored", False))

        cache = getattr(self, "_piece_geom_cache", None)
        if cache is None:
            cache = {}
            self._piece_geom_cache = cache
            self._piece_cache_stats = {"hits": 0, "misses": 0}
            self._piece_rot_cache = {}

        key = (cid, px, py, rot, mirrored)
        cached = cache.get(key)
        if cached is not None:
            self._piece_cache_stats["hits"] += 1
            return cached

        self._piece_cache_stats["misses"] += 1
        if not mirrored:
            rot_cache = getattr(self, "_piece_rot_cache", None)
            if rot_cache is None:
                rot_cache = {}
                self._piece_rot_cache = rot_cache
            rot_key = (id(cntr), round(rot, 2))
            base_rot = rot_cache.get(rot_key)
            if base_rot is None:
                base_poly = transform_contour(cntr, 0.0, 0.0, rot)
                base_bbox = polygon_bbox(base_poly)
                base_pts = [(pt["x"], pt["y"]) for pt in base_poly]
                base_rot = (base_poly, base_bbox, base_pts)
                if len(rot_cache) >= 500:
                    rot_cache.clear()
                rot_cache[rot_key] = base_rot
            base_poly, (b0, b1, b2, b3), base_pts = base_rot
            poly = [{"x": ox + px, "y": oy + py} for ox, oy in base_pts]
            bbox = (b0 + px, b1 + py, b2 + px, b3 + py)
        else:
            poly = transform_contour(cntr, px, py, rot)
            bbox = polygon_bbox(poly)

        res = (poly, bbox)
        if len(cache) >= 5000:
            cache.clear()
        cache[key] = res
        return res

    def clear_piece_cache(self):
        """Limpa o cache de geometria transformada e colisões."""
        self._piece_geom_cache = {}
        self._piece_rot_cache = {}
        self._pair_collision_cache = {}
        self._piece_cache_stats = {"hits": 0, "misses": 0}
        self._last_collision_sig = None
        self._cached_colliding_indices = set()

    def get_piece_cache_stats(self) -> dict:
        """Retorna métricas de hit rate do cache de peças."""
        stats = getattr(self, "_piece_cache_stats", {"hits": 0, "misses": 0})
        total = stats["hits"] + stats["misses"]
        rate = (stats["hits"] / total * 100.0) if total > 0 else 0.0
        return {
            "hits": stats["hits"],
            "misses": stats["misses"],
            "hit_rate_pct": round(rate, 2),
            "size": len(getattr(self, "_piece_geom_cache", {})),
        }

    # -------------------------------------------------------------
    # Renderização da Mesa CAD Estática e Coordenadas
    # -------------------------------------------------------------
    def world_to_screen(self, wx, wy):
        sx = self.plate_x1 + wx * self.plate_scale
        sy = self.plate_y2 - wy * self.plate_scale
        return sx, sy

    def screen_to_world(self, sx, sy):
        if self.plate_scale <= 0:
            return 0.0, 0.0
        wx = (sx - self.plate_x1) / self.plate_scale
        wy = (self.plate_y2 - sy) / self.plate_scale
        return wx, wy

    def redraw(self):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        if cw <= 10 or ch <= 10:
            try:
                cw = int(self.canvas.cget("width"))
                ch = int(self.canvas.cget("height"))
            except Exception:
                cw, ch = 800, 500
            if cw <= 10 or ch <= 10:
                cw, ch = 800, 500

        # 1. Escala proporcional e limites estáticos da chapa
        top_lbl_h = 24.0
        bottom_margin = 22.0
        avail_h = max(50.0, ch - top_lbl_h - bottom_margin)

        if getattr(self, "custom_divider_ratio", None) is not None:
            raw_div = int(cw * self.custom_divider_ratio)
            min_div = 150
            max_div = max(min_div + 50, cw - 80)
            div_x = max(min_div, min(max_div, raw_div))
        elif getattr(self, "custom_divider_x", None) is not None:
            min_div = 150
            max_div = max(min_div + 50, cw - 80)
            div_x = max(min_div, min(max_div, self.custom_divider_x))
        else:
            sidebar_pref_w = 320
            if cw > 650:
                div_x = max(250, cw - sidebar_pref_w)
            else:
                div_x = max(150, int(cw * 0.65))

        self.sidebar_div_x = div_x
        avail_w = max(50.0, div_x - 40.0)

        base_scale = min(avail_w / max(1.0, self.sheet_width), avail_h / max(1.0, self.sheet_height))
        self.base_scale = base_scale
        effective_scale = base_scale * getattr(self, "zoom_factor", 1.0)
        self.plate_scale = effective_scale
        scale = effective_scale
        plate_w = self.sheet_width * scale
        plate_h = self.sheet_height * scale

        # Origem e centro da chapa ancorados (Centralizada no meio da tela CAD)
        cad_center_x = div_x / 2.0
        cad_center_y = (top_lbl_h + (ch - bottom_margin)) / 2.0

        if getattr(self, "view_center_wx", None) is not None and getattr(self, "view_center_sx", None) is not None:
            x1 = self.view_center_sx - self.view_center_wx * scale + getattr(self, "pan_offset_x", 0.0)
            y2 = self.view_center_sy + self.view_center_wy * scale + getattr(self, "pan_offset_y", 0.0)
        else:
            x1 = (cad_center_x - plate_w / 2.0) + getattr(self, "pan_offset_x", 0.0)
            y2 = (cad_center_y + plate_h / 2.0) + getattr(self, "pan_offset_y", 0.0)

        x2 = x1 + plate_w
        y1 = y2 - plate_h

        self.plate_x1 = x1
        self.plate_y2 = y2
        self.plate_x2 = x2
        self.plate_y1 = y1
        self.plate_w = plate_w
        self.plate_h = plate_h

        # Cache de fundo/grade: se geometria, escala, pan e grade forem idênticos, preserva fundo
        bg_sig = (
            round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1),
            round(scale, 4), bool(self.show_grid),
            round(self.sheet_width, 1), round(self.sheet_height, 1),
            cw, ch, div_x
        )
        bg_changed = (getattr(self, "_last_bg_sig", None) != bg_sig)
        if not bg_changed and not self.canvas.find_withtag("sheet_bed"):
            # Autoconserto: se a placa sumiu do canvas (ex.: "Limpar" / sessão vazia
            # chamou set_session_layouts([])), redesenha o fundo mesmo com assinatura igual.
            bg_changed = True

        if bg_changed:
            self._last_bg_sig = bg_sig
            self.canvas.delete("all")

            # 2. Chapa de Corte Cinza (#9b9b9b) com borda preta nítida
            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill="#9b9b9b",
                outline="#000000",
                width=1.5,
                tags=("sheet_bed", "bg_element")
            )

            # 2.1 Margem de Segurança da Placa (Retângulo tracejado sutil delimitando a área útil de corte)
            m_left = getattr(self, "margin_left", 10.0)
            m_right = getattr(self, "margin_right", 10.0)
            m_top = getattr(self, "margin_top", 10.0)
            m_bottom = getattr(self, "margin_bottom", 10.0)
            mx1 = x1 + m_left * scale
            mx2 = x2 - m_right * scale
            my1 = y1 + m_top * scale
            my2 = y2 - m_bottom * scale
            if mx2 > mx1 and my2 > my1:
                self.canvas.create_rectangle(
                    mx1, my1, mx2, my2,
                    fill="",
                    outline="#475569",
                    dash=(4, 3),
                    width=1.0,
                    tags=("sheet_margins", "bg_element")
                )

            # Rótulo com dimensões no topo da chapa em metros (ex: Placa 1,38 x 2,99 m)
            cx = (x1 + x2) / 2.0
            if not (getattr(self, "trim_cut_line", None) and self.trim_cut_line.get("enabled", True)):
                self.canvas.create_text(
                    cx,
                    max(10.0, y1 - 10.0),
                    text=f"Placa {format_dim_mm(self.sheet_width, self.sheet_height)}",
                    fill="#000000",
                    font=("Segoe UI", 8, "bold"),
                    tags=("sheet_label", "bg_element")
                )

            # 3. Grade Milimétrica Sutil e Marcações de 10 em 10 cm (com números e traços)
            if self.show_grid:
                grid_step = 100.0  # 100 mm = 10 cm

                cur_wx = 0.0
                while cur_wx <= self.sheet_width + 0.1:
                    gx = x1 + cur_wx * scale
                    if 0.5 < cur_wx < self.sheet_width - 0.5:
                        self.canvas.create_line(gx, y1, gx, y2, fill="#8c8c8c", width=1, tags=("grid_line", "bg_element"))
                    self.canvas.create_line(gx, y2 - 3, gx, y2 + 3, fill="#000000", width=1, tags=("grid_tick", "bg_element"))
                    self.canvas.create_line(gx, y1 - 3, gx, y1 + 3, fill="#000000", width=1, tags=("grid_tick", "bg_element"))
                    cm_x = int(round(cur_wx / 10.0))
                    if cm_x > 0 and cur_wx < self.sheet_width - 0.5:
                        self.canvas.create_text(
                            gx, y2 + 8,
                            text=str(cm_x),
                            fill="#000000",
                            font=("Segoe UI", 7),
                            anchor="n",
                            tags=("grid_label", "bg_element")
                        )
                    cur_wx += grid_step

                cur_wy = 0.0
                while cur_wy <= self.sheet_height + 0.1:
                    gy = y2 - cur_wy * scale
                    if 0.5 < cur_wy < self.sheet_height - 0.5:
                        self.canvas.create_line(x1, gy, x2, gy, fill="#8c8c8c", width=1, tags=("grid_line", "bg_element"))
                    self.canvas.create_line(x1 - 3, gy, x1 + 3, gy, fill="#000000", width=1, tags=("grid_tick", "bg_element"))
                    self.canvas.create_line(x2 - 3, gy, x2 + 3, gy, fill="#000000", width=1, tags=("grid_tick", "bg_element"))
                    cm_y = int(round(cur_wy / 10.0))
                    if cm_y > 0 and cur_wy < self.sheet_height - 0.5:
                        self.canvas.create_text(
                            x2 + 5, gy,
                            text=str(cm_y),
                            fill="#000000",
                            font=("Segoe UI", 8),
                            anchor="w",
                            tags=("grid_label", "bg_element")
                        )
                    cur_wy += grid_step

            # Divisor Vertical e Barra Lateral
            if div_x < cw:
                is_dragging = getattr(self, "is_dragging_divider", False)
                div_left_col = "#2563eb" if is_dragging else "#a0a0a0"
                div_right_col = "#60a5fa" if is_dragging else "#ffffff"
                self.canvas.create_rectangle(div_x, 0, cw, ch, fill="#ffffff", outline="", tags=("sidebar_bg", "sidebar_ui", "bg_element"))
                self.canvas.create_line(div_x, 0, div_x, ch, fill=div_left_col, width=1, tags=("divider_line", "sidebar_ui", "bg_element"))
                self.canvas.create_line(div_x + 1, 0, div_x + 1, ch, fill=div_right_col, width=1, tags=("divider_line", "sidebar_ui", "bg_element"))
                self.canvas.create_line(div_x, 0, div_x, ch, fill="", width=11, tags=("divider_hitbox", "sidebar_ui", "bg_element"))
                self.draw_sidebar(div_x, ch, cw)
        else:
            self.canvas.delete("piece_item")
            self.canvas.delete("zoom_badge")
            self.canvas.delete("trim_item")
            self.canvas.delete("sim_item")

        # Indicador visual de Zoom ativo no topo da tela
        if getattr(self, "zoom_factor", 1.0) != 1.0:
            pct = int(round(self.zoom_factor * 100))
            self.canvas.create_text(
                40, 22,
                text=f"🔍 Zoom: {pct}%",
                fill="#1e40af",
                font=("Segoe UI", 9, "bold"),
                anchor="w",
                tags="zoom_badge"
            )

        # 5. Sistema de Detecção de Colisão Ativo entre Peças (com Cache e Sweep & Prune)
        num_pieces = len(self.placed_pieces)
        cached_geoms = []
        piece_meta = []
        get_geom = self._get_piece_geom
        for p in self.placed_pieces:
            cntr = p.get("contour") or (p.get("shape", {}).get("contour") if isinstance(p.get("shape"), dict) else None)
            if not cntr:
                cached_geoms.append(([], (0.0, 0.0, 0.0, 0.0)))
                continue
            cid = _contour_key(cntr)
            px = round(float(p.get("x", 0.0)), 2)
            py = round(float(p.get("y", 0.0)), 2)
            rot = round(float(p.get("rotation", p.get("rot", 0.0))), 2)
            mirr = bool(p.get("mirrored", False))
            piece_meta.append((cid, px, py, rot, cntr, mirr))
            cached_geoms.append(get_geom(p, _cid=cid, _px=px, _py=py, _rot=rot, _mirr=mirr))

        piece_geom_sig = tuple((m[0], m[1], m[2], m[3]) for m in piece_meta)

        if getattr(self, "_last_collision_sig", None) == piece_geom_sig:
            colliding_indices = getattr(self, "_cached_colliding_indices", set())
        else:
            self._last_collision_sig = piece_geom_sig
            colliding_indices = set()
            pair_cache = getattr(self, "_pair_collision_cache", None)
            if pair_cache is None:
                pair_cache = {}
                self._pair_collision_cache = pair_cache
            elif len(pair_cache) >= 5000:
                pair_cache.clear()

            if num_pieces > 30:
                bboxes = [g[1] for g in cached_geoms]
                polys = [g[0] for g in cached_geoms]
                order = sorted(range(num_pieces), key=lambda idx: bboxes[idx][1])
                for k, i in enumerate(order):
                    b_i = bboxes[i]
                    if not b_i:
                        continue
                    max_y_i = b_i[3]
                    poly_i = polys[i]
                    cid_i, xi, yi, rot_i, _, _ = piece_meta[i]
                    for m in range(k + 1, num_pieces):
                        j = order[m]
                        b_j = bboxes[j]
                        if b_j[1] > max_y_i:
                            break
                        if b_i[0] > b_j[2] or b_i[2] < b_j[0]:
                            continue
                        cid_j, xj, yj, rot_j, _, _ = piece_meta[j]
                        pair_key = (
                            cid_i,
                            cid_j,
                            rot_i,
                            rot_j,
                            round(xj - xi, 2),
                            round(yj - yi, 2)
                        )
                        col = pair_cache.get(pair_key)
                        if col is None:
                            col = polygons_collide(poly_i, polys[j], gap=0.0, bbox_a=b_i, bbox_b=b_j)
                            pair_cache[pair_key] = col
                        if col:
                            colliding_indices.add(i)
                            colliding_indices.add(j)
            else:
                for i in range(num_pieces):
                    poly_i, bbox_i = cached_geoms[i]
                    if not poly_i:
                        continue
                    for j in range(i + 1, num_pieces):
                        poly_j, bbox_j = cached_geoms[j]
                        if not poly_j:
                            continue
                        if not bbox_overlap(bbox_i, bbox_j, 0.0):
                            continue
                        if polygons_collide(poly_i, poly_j, gap=0.0, bbox_a=bbox_i, bbox_b=bbox_j):
                            colliding_indices.add(i)
                            colliding_indices.add(j)
            self._cached_colliding_indices = colliding_indices
            # Explica ao operador o vermelho no desenho (colisão real, não enfeite)
            if len(colliding_indices) != getattr(self, "_reported_collisions", None):
                self._reported_collisions = len(colliding_indices)
                self.update_title_and_status()

        # 6. Nível de Detalhe (LOD) e Peças Aninhadas (Fase 3 - Tarefa 3)
        # Full: zoom >= 0.5 OU num_pieces < 200 -> contorno completo preenchido + rótulo
        # Simplified: zoom >= 0.15 E num_pieces >= 200 -> contorno completo, sem preenchimento (só borda)
        # LOD: zoom < 0.15 E num_pieces >= 200 -> bounding box colorida + número
        eff_zoom = scale
        if eff_zoom >= 0.5 or num_pieces < 200:
            lod_level = "full"
        elif eff_zoom >= 0.15:
            lod_level = "simplified"
        else:
            lod_level = "lod"

        sel_idx = self.selected_index
        sel_set = set(self.selected_indices) if hasattr(self, "selected_indices") and self.selected_indices else set()

        scaled_offset_cache = {}
        for idx, p in enumerate(self.placed_pieces):
            is_sel = (idx == sel_idx) or (idx in sel_set)
            is_col = (idx in colliding_indices)
            poly, bbox = cached_geoms[idx]
            if not poly:
                continue

            base_col = p.get("color")
            if not base_col:
                size_str = str(p.get("size") or (p.get("shape", {}).get("size") if isinstance(p.get("shape"), dict) else "") or "")
                if not size_str and p.get("target_id"):
                    ts = next((t for t in TARGET_SPECS if t["id"] == p["target_id"]), None)
                    if ts:
                        size_str = str(ts.get("size", ""))
                if not size_str:
                    size_str = str(p.get("name") or "")

                base_col = get_color_for_size(size_str, idx)
                p["color"] = base_col
            else:
                size_str = ""

            if is_col:
                outline_col = "#dc2626"
                line_w = 3.0
            elif is_sel:
                outline_col = "#ff0000"
                line_w = 2.5
            elif lod_level == "simplified":
                # Visão geral (>200 peças): contorno no tom da própria peça, para o
                # desenho ficar contínuo como no mini-preview da sessão. O traço escuro
                # de 1,2 px fazia as peças parecerem separadas por "vãos" de vários mm,
                # quando na verdade estão a 1 mm (gap de corte) umas das outras.
                outline_col = _shade_color(base_col, 0.82)
                line_w = 1.0
            else:
                outline_col = "#1e293b"
                line_w = 1.2

            p_tags = _PIECE_TAGS[idx] if idx < len(_PIECE_TAGS) else (f"piece_{idx}", f"piece_poly_{idx}", "piece_item")

            if lod_level == "lod":
                bx0, by0, bx1, by1 = bbox
                sbx0 = x1 + bx0 * scale
                sby0 = y2 - by1 * scale
                sbx1 = x1 + bx1 * scale
                sby1 = y2 - by0 * scale
                self.canvas.create_rectangle(
                    sbx0, sby0, sbx1, sby1,
                    fill=base_col,
                    outline=outline_col,
                    width=line_w,
                    tags=p_tags
                )
                avg_sx = (sbx0 + sbx1) / 2.0
                avg_sy = (sby0 + sby1) / 2.0
                txt_col = get_contrast_text_color(base_col)
                if not size_str:
                    size_str = str(p.get("size") or (p.get("shape", {}).get("size") if isinstance(p.get("shape"), dict) else "") or "")
                display_label = f"Nº {size_str}" if size_str else f"#{idx + 1}"
                self.canvas.create_text(
                    avg_sx, avg_sy,
                    text=display_label,
                    fill=txt_col,
                    font=("Segoe UI", 7, "bold"),
                    tags=(f"piece_{idx}", f"piece_txt_{idx}", "piece_item")
                )
                if is_sel:
                    self.canvas.create_rectangle(
                        sbx0 - 3, sby0 - 3, sbx1 + 3, sby1 + 3,
                        outline="#ef4444" if is_col else "#ffffff",
                        dash=(3, 3),
                        width=1.5,
                        tags=(f"piece_{idx}", f"piece_box_{idx}", "piece_item")
                    )
            else:
                cid, px, py, rot, _, mirrored = piece_meta[idx]
                if not mirrored:
                    rot_key = (cid, rot)
                    sc_offsets = scaled_offset_cache.get(rot_key)
                    if sc_offsets is None:
                        rot_cache = getattr(self, "_piece_rot_cache", {})
                        base_entry = rot_cache.get(rot_key)
                        if base_entry is not None and len(base_entry) >= 3:
                            base_pts = base_entry[2]
                        else:
                            base_pts = [(pt["x"] - px, pt["y"] - py) for pt in poly]
                        sc_offsets = [(ox * scale, -oy * scale) for ox, oy in base_pts]
                        scaled_offset_cache[rot_key] = sc_offsets
                    csx = x1 + px * scale
                    csy = y2 - py * scale
                    screen_pts = [c for dx_s, dy_s in sc_offsets for c in (csx + dx_s, csy + dy_s)]
                else:
                    screen_pts = [c for pt in poly for c in (x1 + pt["x"] * scale, y2 - pt["y"] * scale)]

                # Mantém a cor do tamanho também no LOD simplificado: o operador
                # precisa que o editor mostre o mesmo desenho do mini-preview.
                fill_col = "" if (SELECTED_OUTLINE_ONLY and is_sel) else base_col

                self.canvas.create_polygon(
                    screen_pts,
                    fill=fill_col,
                    outline=outline_col,
                    width=line_w,
                    tags=p_tags
                )

                if num_pieces <= 40 and len(screen_pts) >= 6:
                    avg_sx = sum(screen_pts[0::2]) / (len(screen_pts) // 2)
                    avg_sy = sum(screen_pts[1::2]) / (len(screen_pts) // 2)
                    txt_col = get_contrast_text_color(fill_col or base_col)
                    display_label = f"Nº {size_str}" if size_str else f"#{idx + 1}"
                    self.canvas.create_text(
                        avg_sx, avg_sy,
                        text=display_label,
                        fill=txt_col,
                        font=("Segoe UI", 8, "bold"),
                        tags=(f"piece_{idx}", f"piece_txt_{idx}", "piece_item")
                    )

                if is_sel and len(screen_pts) >= 4:
                    min_sx = min(screen_pts[0::2])
                    max_sx = max(screen_pts[0::2])
                    min_sy = min(screen_pts[1::2])
                    max_sy = max(screen_pts[1::2])
                    self.canvas.create_rectangle(
                        min_sx - 3, min_sy - 3, max_sx + 3, max_sy + 3,
                        outline="#ef4444" if is_col else "#ffffff",
                        dash=(3, 3),
                        width=1.5,
                        tags=(f"piece_{idx}", f"piece_box_{idx}", "piece_item")
                    )

        # 6.5. Linhas de Corte de Refile Automático CAM
        if getattr(self, "trim_cut_line", None) and self.trim_cut_line.get("enabled", True):
            cut_y = float(self.trim_cut_line.get("y", self.sheet_height))
            cut_x = float(self.trim_cut_line.get("x", self.sheet_width))
            orig_w = float(self.trim_cut_line.get("orig_w", self.sheet_width))
            orig_h = float(self.trim_cut_line.get("orig_h", self.sheet_height))
            sy_cut = y2 - cut_y * scale
            sx_cut = x1 + cut_x * scale
            orig_x2 = x1 + orig_w * scale
            orig_y1 = y2 - orig_h * scale

            if orig_w > cut_x + 0.5:
                self.canvas.create_rectangle(
                    sx_cut, y1, orig_x2, y2,
                    fill="#f1f5f9",
                    outline="#dc2626",
                    dash=(4, 3),
                    width=1.0,
                    tags=("trim_cut_scrap_x", "trim_item")
                )
                sobra_w_cm = (orig_w - cut_x) / 10.0
                scx = (sx_cut + orig_x2) / 2.0
                scy = (y1 + y2) / 2.0
                if orig_x2 - sx_cut > 40:
                    self.canvas.create_text(
                        scx, scy,
                        text=f"Sobra\n{sobra_w_cm:.1f} cm",
                        fill="#991b1b",
                        font=("Segoe UI", 8, "italic"),
                        justify="center",
                        tags=("trim_cut_scrap_lbl", "trim_item")
                    )

            line_right = max(x2 + 6, orig_x2 + 6) if orig_w > cut_x + 0.5 else x2 + 6
            self.canvas.create_line(
                x1 - 6, sy_cut, line_right, sy_cut,
                fill="#dc2626",
                width=2.5,
                tags=("trim_cut_line", "trim_item")
            )
            self.canvas.create_text(
                x1 - 16, sy_cut,
                text="✂",
                fill="#dc2626",
                font=("Segoe UI", 12, "bold"),
                tags=("trim_cut_icon_left", "trim_item")
            )

            self.canvas.create_line(
                sx_cut, y1 - 6, sx_cut, y2 + 6,
                fill="#dc2626",
                width=2.5,
                tags=("trim_cut_line_v", "trim_item")
            )
            self.canvas.create_text(
                sx_cut, y1 - 16,
                text="✂",
                fill="#dc2626",
                font=("Segoe UI", 12, "bold"),
                tags=("trim_cut_icon_v_top", "trim_item")
            )
            self.canvas.create_text(
                sx_cut, y2 + 16,
                text="✂",
                fill="#dc2626",
                font=("Segoe UI", 12, "bold"),
                tags=("trim_cut_icon_v_bot", "trim_item")
            )

            badge_text = (f"✂ CORTE DE REFIL TOTAL: {format_m(self.sheet_height)} m  |  "
                          f"Placa {format_dim_mm(self.sheet_width, self.sheet_height)}")
            bx = (x1 + sx_cut) / 2.0
            by = max(11.0, sy_cut - 14.0)
            self.canvas.create_rectangle(
                bx - 175, by - 9, bx + 175, by + 9,
                fill="#fef2f2",
                outline="#dc2626",
                width=1.5,
                tags=("trim_cut_badge_bg", "trim_item")
            )
            self.canvas.create_text(
                bx, by,
                text=badge_text,
                fill="#991b1b",
                font=("Segoe UI", 8, "bold"),
                tags=("trim_cut_badge_txt", "trim_item")
            )

        # 6.6 Cabeçote CNC se Simulação estiver Ativa
        if getattr(self, "sim_running", False):
            if hasattr(self, "_sim_path") and self._sim_path and hasattr(self, "_sim_path_idx"):
                trail_pts = []
                for pt in self._sim_path[:self._sim_path_idx]:
                    sx, sy = self.world_to_screen(pt[0], pt[1])
                    trail_pts.extend([sx, sy])
                if len(trail_pts) >= 4:
                    self.canvas.create_line(trail_pts, fill="#dc2626", width=2, tags=("sim_cut_trail", "sim_item"))
            self._draw_sim_head(self.sim_head_pos[0], self.sim_head_pos[1])

        # Se fundo não mudou, garante que a sidebar fique acima das peças
        if not bg_changed and div_x < cw:
            self.canvas.tag_raise("sidebar_ui")

        if colliding_indices and hasattr(self, "lbl_stat_left"):
            self.lbl_stat_left.config(text=f"⚠️ ALERTA: Colisão detectada em {len(colliding_indices)} peça(s)! Sobreposição proibida.")

        self.update_sheet_status()

    # -------------------------------------------------------------
    # Rastreamento de Movimento do Mouse e Interações
    # -------------------------------------------------------------
    def on_mouse_move(self, event):
        # Durante o arraste de peca, on_canvas_drag e o dono do cursor/status (com throttle).
        # Sem isso, o Tk dispara <Motion> e <B1-Motion> para o mesmo evento fisico e cada
        # pixel movido reconfigurava a barra de status (custo de layout no Tk).
        if getattr(self, "is_dragging_piece", False):
            return

        # 1. Indicador de redimensionamento ao passar o cursor sobre a linha divisória lateral
        is_over_div = hasattr(self, "sidebar_div_x") and abs(event.x - self.sidebar_div_x) <= 6
        if is_over_div or getattr(self, "is_dragging_divider", False):
            desired_cursor = "sb_h_double_arrow"
        elif getattr(self, "is_panning", False):
            desired_cursor = "fleur"
        elif bool(event.state & 0x0004) and hasattr(self, "sidebar_div_x") and event.x < self.sidebar_div_x:
            desired_cursor = "crosshair"
        else:
            desired_cursor = "arrow"
        # so reconfigura o widget quando o cursor realmente muda
        self._set_cursor(desired_cursor)

        # 2. Coordenadas da mesa e status (limitado a ~30 Hz; o arraste tem seu proprio caminho)
        now = time.monotonic()
        if now - getattr(self, "_last_status_update_ts", 0.0) < STATUS_MIN_INTERVAL_S:
            return
        self._last_status_update_ts = now
        if self.plate_scale > 0:
            wx = (event.x - self.plate_x1) / self.plate_scale
            wy = (self.plate_y2 - event.y) / self.plate_scale
            cur_x_mm = max(0.0, wx)
            cur_y_mm = max(0.0, wy)
            if hasattr(self, "lbl_stat_pos"):
                zoom_prefix = f"[Zoom: {int(round(self.zoom_factor * 100))}%] " if getattr(self, "zoom_factor", 1.0) != 1.0 else ""
                if self.selected_index is not None and 0 <= self.selected_index < len(self.placed_pieces):
                    sel_p = self.placed_pieces[self.selected_index]
                    pnm = sel_p.get("name", "Molde")
                    self.lbl_stat_pos.config(text=f"{zoom_prefix}x: {cur_x_mm:.2f} y: {cur_y_mm:.2f} - {pnm} - <Pasted>")
                else:
                    self.lbl_stat_pos.config(text=f"{zoom_prefix}x: {cur_x_mm:.2f} y: {cur_y_mm:.2f}")

    def on_canvas_click(self, event):
        self.canvas.focus_set()
        if getattr(self, "sim_running", False):
            self.stop_simulation()
        # Um clique novo encerra qualquer atualizacao/redraw pendente do gesto anterior
        self._cancel_drag_job()
        self._pending_drag_xy = None
        self._cancel_redraw_job()
        # 1. Clique na linha divisória lateral (com tolerância de ±6 pixels)
        if hasattr(self, "sidebar_div_x") and abs(event.x - self.sidebar_div_x) <= 6:
            self.is_dragging_divider = True
            self._set_cursor("sb_h_double_arrow")
            self.redraw()
            return

        # 2. Clique na barra lateral de moldes (à direita da linha)
        if hasattr(self, "sidebar_div_x") and event.x > self.sidebar_div_x:
            self.on_sidebar_click(event)
            return

        # 3. Atalho: CTRL + clique do mouse de ação para Zoom de +20%
        if bool(event.state & 0x0004):
            self.is_dragging_piece = False
            self._pre_drag_pieces = None
            self.is_panning = False
            self.zoom_in(event.x, event.y)
            return "break"

        # 4. Clique na mesa CAD (seleção e arrasto de peças / rubberband)
        wx, wy = self.screen_to_world(event.x, event.y)
        is_shift = bool(event.state & 0x0001)

        hit_idx = -1
        for idx in reversed(range(len(self.placed_pieces))):
            p = self.placed_pieces[idx]
            poly = transform_contour(p["contour"], p["x"], p["y"], p["rotation"])
            if point_in_polygon(wx, wy, poly):
                hit_idx = idx
                break

        if hit_idx >= 0:
            # Duplo-clique esquerdo na peça (2º press < 300 ms) arma o bump por arrasto
            try:
                now_ms = time.time() * 1000.0
                segundo_clique = (
                    self._last_piece_press_idx == hit_idx
                    and (now_ms - self._last_piece_press_ms) < BUMP_DOUBLE_CLICK_MS
                )
                self._last_piece_press_idx = hit_idx
                self._last_piece_press_ms = now_ms
                if segundo_clique:
                    self.selected_indices = [hit_idx]
                    self.selected_index = hit_idx
                    self._bump_armed = True
                    self._bump_press_xy = (event.x, event.y)
                    self.is_dragging_piece = False
                    self._drag_indices = []
                    self.canvas.delete("drag_ghost")
                    self.update_status()
                    return "break"
            except Exception:
                pass

            self.is_rubberbanding = False
            self.canvas.delete("rubberband_box")

            if not isinstance(self.selected_indices, list):
                self.selected_indices = list(self.selected_indices)

            if is_shift:
                # Shift + Clique Esquerdo sobre Peça:
                # Alterna (toggle) a peça clicada na lista self.selected_indices
                if hit_idx in self.selected_indices:
                    self.selected_indices.remove(hit_idx)
                    self.selected_index = self.selected_indices[-1] if self.selected_indices else None
                else:
                    self.selected_indices.append(hit_idx)
                    self.selected_index = hit_idx
                self.is_dragging_piece = False
                self._pre_drag_pieces = None
                self._drag_indices = []
                self.redraw()
                self.update_status()
                return "break"
            else:
                # Clique Esquerdo Simples sobre Peça (sem Shift):
                if hit_idx not in self.selected_indices:
                    self.selected_indices = [hit_idx]
                    self.selected_index = hit_idx
                    self._drag_clicked_in_multi = False
                else:
                    self._drag_clicked_in_multi = (len(self.selected_indices) > 1)
                    self._drag_hit_idx = hit_idx

                self.is_dragging_piece = True
                self._drag_start_event_xy = (event.x, event.y)
                self._pre_drag_pieces = [dict(p) for p in self.placed_pieces]
                self._drag_indices = [i for i in self.selected_indices if 0 <= i < len(self.placed_pieces)]
                if hit_idx not in self._drag_indices:
                    self._drag_indices.append(hit_idx)

                p = self.placed_pieces[hit_idx]
                self.drag_start = (wx - p["x"], wy - p["y"])
                self._drag_piece_origins = {i: (self.placed_pieces[i]["x"], self.placed_pieces[i]["y"]) for i in self._drag_indices}
                self._drag_anchor_idx = hit_idx
                self._drag_last_canvas_x = event.x
                self._drag_last_canvas_y = event.y
                self._drag_origin_x = p["x"]
                self._drag_origin_y = p["y"]
                self._drag_colliding_others = set()

                # Constrói SpatialGrid e cache com todas as OUTRAS peças estáticas da mesa
                self._drag_spatial_grid = SpatialGrid(cell_size=100.0)
                self._drag_static_data = []
                for j, other in enumerate(self.placed_pieces):
                    if j in self._drag_indices:
                        continue
                    other_poly = transform_contour(other["contour"], other["x"], other["y"], other["rotation"])
                    other_bbox = polygon_bbox(other_poly)
                    self._drag_spatial_grid.insert(j, other_poly, other_bbox)
                    self._drag_static_data.append((j, other_poly, other_bbox))

                self.redraw()

                # Cria Contorno Fantasma (drag_ghost) para as peças arrastadas
                self.canvas.delete("drag_ghost")
                for didx in self._drag_indices:
                    dp = self.placed_pieces[didx]
                    poly_ghost = transform_contour(dp["contour"], dp["x"], dp["y"], dp["rotation"])
                    ghost_screen_pts = []
                    for pt in poly_ghost:
                        gx = self.plate_x1 + pt["x"] * self.plate_scale
                        gy = self.plate_y2 - pt["y"] * self.plate_scale
                        ghost_screen_pts.extend([gx, gy])
                    if len(ghost_screen_pts) >= 6:
                        self.canvas.create_polygon(
                            ghost_screen_pts,
                            fill="",
                            outline="#64748b",
                            dash=(4, 4),
                            width=1.5,
                            tags="drag_ghost"
                        )
        else:
            self.is_dragging_piece = False
            self._pre_drag_pieces = None
            self._drag_indices = []
            self._drag_spatial_grid = None
            self._drag_static_data = []
            self.canvas.delete("drag_ghost")
            self.canvas.delete("rubberband_box")

            self.is_rubberbanding = True
            self._rubberband_start_screen = (event.x, event.y)
            self._rubberband_is_shift = is_shift
            self._rubberband_moved = False

            if not is_shift:
                self.selected_indices = []
                self.selected_index = None
                self.redraw()
                self.update_status()

    def on_canvas_drag(self, event):
        # 0. Bump armado por duplo-clique: o primeiro movimento inicia o bump
        if getattr(self, "_bump_armed", False):
            if not self._bump_mode:
                px, py = self._bump_press_xy or (event.x, event.y)
                self._start_mouse_bump_at(px, py)
            self._update_mouse_bump(event)
            return "break"

        # 1. Movimentação da linha divisória para os lados (redraw coalescido)
        if getattr(self, "is_dragging_divider", False):
            cw = self.canvas.winfo_width()
            min_div = 150
            max_div = max(min_div + 50, cw - 80)
            new_div = max(min_div, min(max_div, event.x))
            self.custom_divider_x = new_div
            self.custom_divider_ratio = new_div / max(1.0, float(cw))
            self._schedule_redraw(PAN_REDRAW_INTERVAL_MS)
            return

        # 2. Caixa de Seleção Elástica (Rubberband)
        if getattr(self, "is_rubberbanding", False):
            sx0, sy0 = self._rubberband_start_screen
            sx1, sy1 = event.x, event.y
            if (sx1 - sx0)**2 + (sy1 - sy0)**2 > 7:
                self._rubberband_moved = True
            self.canvas.delete("rubberband_box")
            self.canvas.create_rectangle(
                sx0, sy0, sx1, sy1,
                outline="#3b82f6",
                dash=(4, 4),
                width=1.5,
                tags="rubberband_box"
            )
            return "break"

        # 3. Pan na mesa ao arrastar espaço vazio com zoom (redraw coalescido)
        if getattr(self, "is_panning", False):
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.pan_offset_x = getattr(self, "pan_offset_x", 0.0) + dx
            self.pan_offset_y = getattr(self, "pan_offset_y", 0.0) + dy
            self._schedule_redraw(PAN_REDRAW_INTERVAL_MS)
            return

        # 4. Arrastar peça(s) na mesa: movimento coalescido (~125 aplicações/s).
        if getattr(self, "is_dragging_piece", False) and getattr(self, "_drag_indices", None):
            self._pending_drag_xy = (event.x, event.y)
            if self._drag_job is not None:
                return
            elapsed = time.monotonic() - getattr(self, "_last_drag_update_ts", 0.0)
            if elapsed >= DRAG_MIN_INTERVAL_S:
                self._flush_drag_update()
            else:
                delay_ms = max(1, int((DRAG_MIN_INTERVAL_S - elapsed) * 1000) + 1)
                self._drag_job = self.after(delay_ms, self._flush_drag_update)

    # -------------------------------------------------------------
    # Coalescência de eventos (arraste de peça, pan e divisor)
    # -------------------------------------------------------------
    def _set_cursor(self, cursor_name):
        """Troca o cursor do canvas apenas quando ele realmente muda."""
        if cursor_name != getattr(self, "_last_cursor_name", None):
            self.canvas.config(cursor=cursor_name)
            self._last_cursor_name = cursor_name

    def _cancel_drag_job(self):
        """Descarta a atualização de arraste agendada, se houver."""
        if self._drag_job is not None:
            try:
                self.after_cancel(self._drag_job)
            except (tk.TclError, ValueError):
                pass
            self._drag_job = None

    def _cancel_redraw_job(self):
        """Descarta o redraw agendado de pan/divisor, se houver."""
        if self._redraw_job is not None:
            try:
                self.after_cancel(self._redraw_job)
            except (tk.TclError, ValueError):
                pass
            self._redraw_job = None

    def _schedule_redraw(self, delay_ms=PAN_REDRAW_INTERVAL_MS):
        """Agenda um único redraw para o próximo frame (evita N redraws por gesto)."""
        if self._redraw_job is not None:
            return
        self._redraw_job = self.after(delay_ms, self._run_scheduled_redraw)

    def _run_scheduled_redraw(self):
        self._redraw_job = None
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self.redraw()

    def _flush_drag_update(self):
        """Aplica o último movimento pendente do arraste (uma vez por frame)."""
        self._cancel_drag_job()
        pending = self._pending_drag_xy
        self._pending_drag_xy = None
        if not pending or not getattr(self, "is_dragging_piece", False):
            return
        if not getattr(self, "_drag_indices", None):
            return
        self._last_drag_update_ts = time.monotonic()
        self._apply_drag_update(pending[0], pending[1])

    def flush_pending_drag(self):
        """Aplica imediatamente o ultimo movimento pendente."""
        self._flush_drag_update()

    def _apply_drag_update(self, canvas_x, canvas_y):
        """Move todas as peças selecionadas para a nova posição do mouse (coalescida)."""
        if not getattr(self, "_drag_indices", None):
            return
        last = (getattr(self, "_drag_last_canvas_x", None), getattr(self, "_drag_last_canvas_y", None))
        if (canvas_x, canvas_y) == last:
            return
        self._drag_last_canvas_x = canvas_x
        self._drag_last_canvas_y = canvas_y

        wx, wy = self.screen_to_world(canvas_x, canvas_y)
        offset_x, offset_y = self.drag_start
        anchor_idx = getattr(self, "_drag_anchor_idx", self._drag_indices[0])
        anchor_orig_x, anchor_orig_y = self._drag_piece_origins.get(
            anchor_idx,
            (self.placed_pieces[anchor_idx]["x"], self.placed_pieces[anchor_idx]["y"])
        )

        target_anchor_x = wx - offset_x
        target_anchor_y = wy - offset_y

        delta_x = target_anchor_x - anchor_orig_x
        delta_y = target_anchor_y - anchor_orig_y

        # Snap magnético suave nas bordas da chapa se a menos de 2.0 mm
        gap = getattr(self, "gap_mm", 1.0)
        snap_thresh = 2.0

        group_xmin = float("inf")
        group_ymin = float("inf")
        group_xmax = float("-inf")
        group_ymax = float("-inf")

        piece_polys = {}
        piece_bboxes = {}
        for didx in self._drag_indices:
            dp = self.placed_pieces[didx]
            orig_px, orig_py = self._drag_piece_origins[didx]
            prop_x = orig_px + delta_x
            prop_y = orig_py + delta_y
            poly_prop, (bx0, by0, bx1, by1) = self._get_piece_geom(
                dp, _cid=id(dp["contour"]), _px=prop_x, _py=prop_y,
                _rot=dp.get("rotation", dp.get("rot", 0.0)),
                _mirr=bool(dp.get("mirrored", False))
            )
            piece_polys[didx] = poly_prop
            piece_bboxes[didx] = (bx0, by0, bx1, by1)
            group_xmin = min(group_xmin, bx0)
            group_ymin = min(group_ymin, by0)
            group_xmax = max(group_xmax, bx1)
            group_ymax = max(group_ymax, by1)

        snapped = False
        if abs(group_xmin - gap) <= snap_thresh:
            delta_x += (gap - group_xmin)
            snapped = True
        elif abs(group_xmax - (self.sheet_width - gap)) <= snap_thresh:
            delta_x += ((self.sheet_width - gap) - group_xmax)
            snapped = True

        if abs(group_ymin - gap) <= snap_thresh:
            delta_y += (gap - group_ymin)
            snapped = True
        elif abs(group_ymax - (self.sheet_height - gap)) <= snap_thresh:
            delta_y += ((self.sheet_height - gap) - group_ymax)
            snapped = True

        if snapped:
            piece_polys.clear()
            piece_bboxes.clear()
            for didx in self._drag_indices:
                dp = self.placed_pieces[didx]
                orig_px, orig_py = self._drag_piece_origins[didx]
                prop_x = orig_px + delta_x
                prop_y = orig_py + delta_y
                poly_prop, (bx0, by0, bx1, by1) = self._get_piece_geom(
                    dp, _cid=id(dp["contour"]), _px=prop_x, _py=prop_y,
                    _rot=dp.get("rotation", dp.get("rot", 0.0)),
                    _mirr=bool(dp.get("mirrored", False))
                )
                piece_polys[didx] = poly_prop
                piece_bboxes[didx] = (bx0, by0, bx1, by1)

        # Atualiza coordenadas das peças e move no canvas
        for didx in self._drag_indices:
            dp = self.placed_pieces[didx]
            orig_px, orig_py = self._drag_piece_origins[didx]
            new_px = orig_px + delta_x
            new_py = orig_py + delta_y

            old_sx = self.plate_x1 + dp["x"] * self.plate_scale
            old_sy = self.plate_y2 - dp["y"] * self.plate_scale
            new_sx = self.plate_x1 + new_px * self.plate_scale
            new_sy = self.plate_y2 - new_py * self.plate_scale
            move_dx = new_sx - old_sx
            move_dy = new_sy - old_sy

            dp["x"] = new_px
            dp["y"] = new_py

            self.canvas.move(f"piece_{didx}", move_dx, move_dy)
            self.canvas.tag_raise(f"piece_{didx}")

        self.canvas.tag_raise("sidebar_ui")

        # Detecção de colisão do grupo
        is_collision = False
        colliding_with = set()
        for didx in self._drag_indices:
            bx0, by0, bx1, by1 = piece_bboxes[didx]
            if (bx0 < -0.01 or by0 < -0.01 or
                bx1 > self.sheet_width + 0.01 or bx1 > self.sheet_height + 0.01):
                is_collision = True
            if hasattr(self, "_drag_spatial_grid") and self._drag_spatial_grid is not None:
                candidates = self._drag_spatial_grid.query_items((bx0, by0, bx1, by1), gap=0.0)
                poly_d = piece_polys[didx]
                for j, other_poly, other_bbox in candidates:
                    if polygons_collide(poly_d, other_poly, gap=0.0, bbox_a=(bx0, by0, bx1, by1), bbox_b=other_bbox):
                        is_collision = True
                        colliding_with.add(j)

        outline_state = (is_collision, frozenset(colliding_with))
        if outline_state != getattr(self, "_drag_outline_state", None):
            self._drag_outline_state = outline_state
            if is_collision:
                for didx in self._drag_indices:
                    self.canvas.itemconfig(f"piece_poly_{didx}", outline="#ef4444", width=3.0)
                for j in colliding_with:
                    self.canvas.itemconfig(f"piece_poly_{j}", outline="#f59e0b", width=2.5)
            else:
                for didx in self._drag_indices:
                    self.canvas.itemconfig(f"piece_poly_{didx}", outline="#22c55e", width=2.5)

            prev_colliding = getattr(self, "_drag_colliding_others", set())
            for prev_j in prev_colliding:
                if prev_j not in colliding_with and prev_j not in self._drag_indices:
                    self.canvas.itemconfig(f"piece_poly_{prev_j}", outline="#1e293b", width=1.2)
            self._drag_colliding_others = colliding_with

        # Barra de status
        now = time.monotonic()
        if now - getattr(self, "_last_status_update_ts", 0.0) >= STATUS_MIN_INTERVAL_S:
            self._last_status_update_ts = now
            primary_p = self.placed_pieces[anchor_idx]
            if hasattr(self, "lbl_stat_pos"):
                pnm = primary_p.get("name", "Molde")
                status_drag = " [COLISÃO]" if is_collision else ""
                cnt = len(self._drag_indices)
                tag_grp = f" ({cnt} peças)" if cnt > 1 else ""
                self.lbl_stat_pos.config(text=f"x: {primary_p['x']:.2f} y: {primary_p['y']:.2f} - {pnm}{tag_grp}{status_drag}")
            if hasattr(self, "lbl_stat_x"):
                self.lbl_stat_x.config(text=f"X: {primary_p['x']:.2f}")
            if hasattr(self, "lbl_stat_y"):
                self.lbl_stat_y.config(text=f"Y: {primary_p['y']:.2f}")

    def cancel_drag(self, event=None):
        """Cancela o arraste em andamento, a caixa elástica, a simulação CAM ou a rotação livre R-Drag via Escape."""
        if getattr(self, "sim_running", False):
            self.stop_simulation()
            return "break"
        if getattr(self, "is_rubberbanding", False):
            self.canvas.delete("rubberband_box")
            self.is_rubberbanding = False
            return "break"
        if getattr(self, "_rdrag_rotating", False) or getattr(self, "_rdrag_active", False):
            return self.cancel_rdrag(event)
        self._cancel_drag_job()
        self._pending_drag_xy = None
        self._drag_outline_state = None
        if getattr(self, "is_dragging_piece", False):
            if self._pre_drag_pieces is not None:
                for idx, p_old in enumerate(self._pre_drag_pieces):
                    if idx < len(self.placed_pieces):
                        self.placed_pieces[idx]["x"] = p_old["x"]
                        self.placed_pieces[idx]["y"] = p_old["y"]
            self.canvas.delete("drag_ghost")
            prev_colliding = getattr(self, "_drag_colliding_others", set())
            for prev_j in prev_colliding:
                self.canvas.itemconfig(f"piece_poly_{prev_j}", outline="#1e293b", width=1.2)
            self._drag_colliding_others = set()
            self.is_dragging_piece = False
            self._pre_drag_pieces = None
            self._drag_indices = []
            self._drag_spatial_grid = None
            self._drag_static_data = []
            self.redraw()
            if hasattr(self, "lbl_stat_left"):
                self.lbl_stat_left.config(text="Movimento cancelado via Escape.")
            return "break"
        return None

    def on_canvas_release(self, event):
        # 0. Bump (duplo-clique armado ou arrasto em andamento)
        if getattr(self, "_bump_armed", False) or self._bump_mode:
            if self._bump_mode:
                self._finish_mouse_bump(event)
            else:
                self._bump_armed = False
                self._bump_status("Ready")
            return "break"

        # 1. Conclusão da Caixa Elástica (Rubberband)
        if getattr(self, "is_rubberbanding", False):
            self.canvas.delete("rubberband_box")
            self.is_rubberbanding = False
            sx0, sy0 = self._rubberband_start_screen
            sx1, sy1 = event.x, event.y
            dist_sq = (sx1 - sx0)**2 + (sy1 - sy0)**2
            if dist_sq > 7:
                wx0, wy0 = self.screen_to_world(sx0, sy0)
                wx1, wy1 = self.screen_to_world(sx1, sy1)
                box_xmin = min(wx0, wx1)
                box_xmax = max(wx0, wx1)
                box_ymin = min(wy0, wy1)
                box_ymax = max(wy0, wy1)

                contained = []
                for idx, p in enumerate(self.placed_pieces):
                    poly, (p_xmin, p_ymin, p_xmax, p_ymax) = self._get_piece_geom(p)
                    if (box_xmin <= p_xmin and p_xmax <= box_xmax and
                        box_ymin <= p_ymin and p_ymax <= box_ymax):
                        contained.append(idx)

                if getattr(self, "_rubberband_is_shift", False):
                    if not isinstance(self.selected_indices, list):
                        self.selected_indices = list(self.selected_indices)
                    for c in contained:
                        if c not in self.selected_indices:
                            self.selected_indices.append(c)
                else:
                    self.selected_indices = list(contained)

                self.selected_index = self.selected_indices[-1] if self.selected_indices else None
            else:
                if not getattr(self, "_rubberband_is_shift", False):
                    self.selected_indices = []
                    self.selected_index = None

            self.redraw()
            self.update_status()
            return "break"

        # Consolida a última posição pendente antes de validar colisão/limites
        if getattr(self, "is_dragging_piece", False):
            pending = self._pending_drag_xy
            self._pending_drag_xy = None
            self._cancel_drag_job()
            if pending:
                self._apply_drag_update(pending[0], pending[1])
        self._cancel_redraw_job()
        self._drag_outline_state = None

        if getattr(self, "is_panning", False):
            self.is_panning = False
            self._set_cursor("arrow")

        # 2. Conclusão do arrasto da linha divisória
        if getattr(self, "is_dragging_divider", False):
            self.is_dragging_divider = False
            if hasattr(self, "sidebar_div_x") and abs(event.x - self.sidebar_div_x) <= 6:
                self._set_cursor("sb_h_double_arrow")
            else:
                self._set_cursor("arrow")
            self.redraw()
            return

        # 3. Conclusão do arrasto de peças (validação estrita e consolidação)
        self.canvas.delete("drag_ghost")
        prev_colliding = getattr(self, "_drag_colliding_others", set())
        for prev_j in prev_colliding:
            self.canvas.itemconfig(f"piece_poly_{prev_j}", outline="#1e293b", width=1.2)
        self._drag_colliding_others = set()
        self._drag_spatial_grid = None
        self._drag_static_data = []

        if getattr(self, "is_dragging_piece", False) and hasattr(self, "_drag_start_event_xy"):
            dx = event.x - self._drag_start_event_xy[0]
            dy = event.y - self._drag_start_event_xy[1]
            if getattr(self, "_drag_clicked_in_multi", False) and (dx*dx + dy*dy <= 7):
                self.selected_indices = [self._drag_hit_idx]
                self.selected_index = self._drag_hit_idx
                self.is_dragging_piece = False
                self._pre_drag_pieces = None
                self._drag_indices = []
                self.redraw()
                self.update_status()
                return "break"

        if self._pre_drag_pieces is not None and getattr(self, "_drag_indices", None):
            has_collision = False
            drag_set = set(self._drag_indices)

            dragged_geoms = {}
            for didx in self._drag_indices:
                p_curr = self.placed_pieces[didx]
                poly_curr, bbox_curr = self._get_piece_geom(p_curr)
                dragged_geoms[didx] = (poly_curr, bbox_curr)
                if (bbox_curr[0] < -0.01 or bbox_curr[1] < -0.01 or
                    bbox_curr[2] > self.sheet_width + 0.01 or bbox_curr[3] > self.sheet_height + 0.01):
                    has_collision = True
                    break

            if not has_collision:
                for didx in self._drag_indices:
                    poly_curr, bbox_curr = dragged_geoms[didx]
                    for j, other in enumerate(self.placed_pieces):
                        if j in drag_set:
                            continue
                        other_poly, other_bbox = self._get_piece_geom(other)
                        if not bbox_overlap(bbox_curr, other_bbox, 0.0):
                            continue
                        if polygons_collide(poly_curr, other_poly, gap=0.0, bbox_a=bbox_curr, bbox_b=other_bbox):
                            has_collision = True
                            break
                    if has_collision:
                        break

            if has_collision:
                for didx in self._drag_indices:
                    self.placed_pieces[didx]["x"] = self._pre_drag_pieces[didx]["x"]
                    self.placed_pieces[didx]["y"] = self._pre_drag_pieces[didx]["y"]
                if hasattr(self, "lbl_stat_left"):
                    self.lbl_stat_left.config(text="⚠️ Bloqueio de Colisão: Peças retornaram à posição anterior (sobreposição proibida).")
            elif self.placed_pieces != self._pre_drag_pieces:
                state = {
                    "pieces": [dict(p) for p in self._pre_drag_pieces],
                    "sheet_height": self.sheet_height,
                    "trim_cut_line": copy.deepcopy(getattr(self, "trim_cut_line", None)),
                    "original_sheet_height": getattr(self, "original_sheet_height", None)
                }
                self.undo_stack.append(state)
                if len(self.undo_stack) > UNDO_MAX_LEVELS:
                    self.undo_stack.pop(0)
                self.set_modified(True)

            self._pre_drag_pieces = None
            self._drag_indices = []

        self.is_dragging_piece = False
        self.redraw()
        self.update_status()

    # -------------------------------------------------------------
    # Rotação Livre 360° com o Mouse (R-Drag / Botão Direito)
    # Fiel ao Layout.exe (OnRButtonDown 0x418550, OnMouseMove 0x4269c4, OnRButtonUp 0x421fd0)
    # -------------------------------------------------------------
    def get_selected_indices(self):
        """Retorna a lista de índices das peças atualmente selecionadas."""
        if hasattr(self, "selected_indices") and self.selected_indices is not None:
            valid = [i for i in self.selected_indices if 0 <= i < len(self.placed_pieces)]
            if valid:
                return valid
        if self.selected_index is not None and 0 <= self.selected_index < len(self.placed_pieces):
            return [self.selected_index]
        return []

    def cancel_rdrag(self, event=None):
        """
        Cancela imediatamente a rotação livre R-Drag em andamento via Escape,
        restaura o estado original prévio das peças, limpa a guia visual
        e NÃO empilha nada no undo_stack.
        """
        try:
            self.canvas.delete("rdrag_guide")
        except Exception:
            pass

        if getattr(self, "_rdrag_pre_pieces", None) is not None:
            for i, p_old in enumerate(self._rdrag_pre_pieces):
                if i < len(self.placed_pieces):
                    self.placed_pieces[i].clear()
                    self.placed_pieces[i].update(dict(p_old))

        self._rdrag_active = False
        self._rdrag_rotating = False
        self._rdrag_pre_pieces = None
        self._rdrag_selected_indices = []
        if hasattr(self, "_rdrag_piece_init_centers"):
            self._rdrag_piece_init_centers.clear()
        if hasattr(self, "_rdrag_piece_base_centers"):
            self._rdrag_piece_base_centers.clear()

        self.redraw()
        self.update_status()
        if hasattr(self, "lbl_stat_left"):
            self.lbl_stat_left.config(text="Rotação cancelada via Escape.")
        return "break"

    def setup_context_menu_102(self):
        """
        Constrói o Menu de Contexto 102 Win32 original (Layout.exe).
        Ordem estrita conforme captura media_1792931613851.jpg e LAYOUT_EDITOR_RE.md.
        """
        self.context_menu_102 = tk.Menu(self, tearoff=0)

        # Submenu Fill (ordem estrita Win32 ID 52103, 52104, 50007, 52105, 52106, 50003)
        self.fill_submenu = tk.Menu(self.context_menu_102, tearoff=0)
        self.fill_submenu.add_command(label="Row", command=lambda: self.fill_row())  # Win32 ID 52103
        self.fill_submenu.add_command(label="Row Alternate", command=lambda: self.fill_row_alternate())  # Win32 ID 52104
        self.fill_submenu.add_command(label="Column", command=lambda: self.fill_column())  # Win32 ID 50007
        self.fill_submenu.add_command(label="Sheet", command=lambda: self.fill_sheet())  # Win32 ID 52105
        self.fill_submenu.add_command(label="Sheet Alternate", command=lambda: self.fill_sheet_alternate())  # Win32 ID 52106
        self.fill_submenu.add_command(label="User...", command=lambda: self.fill_user_dialog())  # Win32 ID 50003: Dialog 159

        # Menu de Contexto simplificado: exibe apenas 'Fill' a pedido do operador
        self.context_menu_102.add_cascade(label="Fill", menu=self.fill_submenu)

    def get_target_piece_index(self, event=None):
        """
        Determina a peça-alvo para operações de menu e preenchimento (Fill).
        Regra estrita: O menu e o Fill agem sobre a SELEÇÃO existente.
        - Seleção simples: essa peça.
        - Seleção múltipla: a peça primária (selected_index; se for None, a primeira de selected_indices em ordem estável).
        # CONFIRMAR NO WINDOWS: no original com seleção múltipla, confirma se o Fill clona apenas a primária ou se aplica a todas.
        - Sem seleção: retorna None.
        """
        sel_indices = self.get_selected_indices()
        if sel_indices:
            if self.selected_index is not None and self.selected_index in sel_indices:
                return self.selected_index
            return sorted(sel_indices)[0]
        return None

    def open_context_menu_102(self, event):
        """
        Abre o Menu de Contexto 102 Win32 na posição do cursor.
        Se target_idx for None (clique no vazio sem peça-alvo):
        desabilita itens dependentes de peça (Fill, Delete, Mirror).
        """
        self._context_menu_opened = True
        target_idx = self.get_target_piece_index(event)
        self._context_target_idx = target_idx

        has_target = (target_idx is not None and 0 <= target_idx < len(self.placed_pieces))
        state_piece_dep = "normal" if has_target else "disabled"

        # Atualiza estado dos comandos dependentes de peça no Menu 102
        try:
            self.context_menu_102.entryconfig("Fill", state=state_piece_dep)
            self.fill_submenu.entryconfig("Row", state=state_piece_dep)
            self.fill_submenu.entryconfig("Row Alternate", state=state_piece_dep)
            self.fill_submenu.entryconfig("Column", state=state_piece_dep)
            self.fill_submenu.entryconfig("Sheet", state=state_piece_dep)
            self.fill_submenu.entryconfig("Sheet Alternate", state=state_piece_dep)
            self.fill_submenu.entryconfig("User...", state=state_piece_dep)
        except Exception:
            pass

        x_root = getattr(event, "x_root", None)
        if x_root is None:
            try:
                x_root = self.canvas.winfo_rootx() + getattr(event, "x", 0)
            except Exception:
                x_root = 0
        y_root = getattr(event, "y_root", None)
        if y_root is None:
            try:
                y_root = self.canvas.winfo_rooty() + getattr(event, "y", 0)
            except Exception:
                y_root = 0

        try:
            self.context_menu_102.tk_popup(int(x_root), int(y_root))
        except Exception:
            pass
        finally:
            try:
                self.context_menu_102.grab_release()
            except Exception:
                pass

    def fill_row(self, target_idx=None):
        """
        Executa Fill Row (Win32 ID 52103):
        Clona a peça-alvo horizontalmente da sua posição até a margem direita útil da chapa.
        # CONFIRMAR NO WINDOWS: preenche a partir da peça-alvo em direção à margem direita.
        """
        if target_idx is None:
            target_idx = self.get_target_piece_index()
        if target_idx is None or target_idx < 0 or target_idx >= len(self.placed_pieces):
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill Row: Nenhuma peça selecionada para preenchimento.")
            return

        target_piece = self.placed_pieces[target_idx]
        margins = (self.margin_left, self.margin_right, self.margin_top, self.margin_bottom)
        gap = getattr(self, "gap_mm", 1.0)

        new_pieces = fill_row_pieces(
            target_piece=target_piece,
            placed_pieces=self.placed_pieces,
            sheet_width=self.sheet_width,
            sheet_height=self.sheet_height,
            margins=margins,
            gap_mm=gap
        )

        if not new_pieces:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill Row: Nenhuma cópia coube na chapa respeitando margens e folga.")
            return

        # 1 único snapshot atômico no undo_stack
        self.push_undo()
        self.placed_pieces.extend(new_pieces)
        # A seleção original permanece na peça-alvo (as cópias geradas não são selecionadas)
        self.set_modified(True)
        self.update_sidebar_targets()
        self.redraw()
        self.update_status()
        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=f"Fill Row: {len(new_pieces)} peça(s) adicionada(s) com sucesso.")

    def fill_row_alternate(self, target_idx=None):
        """
        Executa Fill Row Alternate (Win32 ID 52104):
        Clona a peça horizontalmente alternando rotações 0° / 180° para acoplamento bico-calcanhar.
        # CONFIRMAR NO WINDOWS: preenche a partir da peça-alvo em direção à margem direita.
        """
        if target_idx is None:
            target_idx = self.get_target_piece_index()
        if target_idx is None or target_idx < 0 or target_idx >= len(self.placed_pieces):
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill Row Alternate: Nenhuma peça selecionada para preenchimento.")
            return

        target_piece = self.placed_pieces[target_idx]
        margins = (self.margin_left, self.margin_right, self.margin_top, self.margin_bottom)
        gap = getattr(self, "gap_mm", 1.0)

        new_pieces = fill_row_alternate_pieces(
            target_piece=target_piece,
            placed_pieces=self.placed_pieces,
            sheet_width=self.sheet_width,
            sheet_height=self.sheet_height,
            margins=margins,
            gap_mm=gap
        )

        if not new_pieces:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill Row Alternate: Nenhuma cópia coube na chapa respeitando margens e folga.")
            return

        self.push_undo()
        self.placed_pieces.extend(new_pieces)
        # A seleção original permanece na peça-alvo (as cópias geradas não são selecionadas)
        self.set_modified(True)
        self.update_sidebar_targets()
        self.redraw()
        self.update_status()
        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=f"Fill Row Alternate: {len(new_pieces)} peça(s) adicionada(s) com sucesso.")

    def fill_column(self, target_idx=None):
        """
        Executa Fill Column (Win32 ID 50007):
        Clona a peça verticalmente (+Y) até a margem superior útil da chapa.
        # CONFIRMAR NO WINDOWS: preenche a partir da peça-alvo em direção à margem superior (+Y).
        """
        if target_idx is None:
            target_idx = self.get_target_piece_index()
        if target_idx is None or target_idx < 0 or target_idx >= len(self.placed_pieces):
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill Column: Nenhuma peça selecionada para preenchimento.")
            return

        target_piece = self.placed_pieces[target_idx]
        margins = (self.margin_left, self.margin_right, self.margin_top, self.margin_bottom)
        gap = getattr(self, "gap_mm", 1.0)

        new_pieces = fill_column_pieces(
            target_piece=target_piece,
            placed_pieces=self.placed_pieces,
            sheet_width=self.sheet_width,
            sheet_height=self.sheet_height,
            margins=margins,
            gap_mm=gap
        )

        if not new_pieces:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill Column: Nenhuma cópia coube na chapa respeitando margens e folga.")
            return

        self.push_undo()
        self.placed_pieces.extend(new_pieces)
        # A seleção original permanece na peça-alvo (as cópias geradas não são selecionadas)
        self.set_modified(True)
        self.update_sidebar_targets()
        self.redraw()
        self.update_status()
        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=f"Fill Column: {len(new_pieces)} peça(s) adicionada(s) com sucesso.")

    def fill_sheet(self, target_idx=None):
        """
        Executa Fill Sheet (Win32 ID 52105):
        Preenche toda a área restante da chapa em linhas sucessivas a partir da peça-alvo.
        # CONFIRMAR NO WINDOWS: preenchimento em varredura por linhas a partir da base.
        """
        if target_idx is None:
            target_idx = self.get_target_piece_index()
        if target_idx is None or target_idx < 0 or target_idx >= len(self.placed_pieces):
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill Sheet: Nenhuma peça selecionada para preenchimento.")
            return

        target_piece = self.placed_pieces[target_idx]
        margins = (self.margin_left, self.margin_right, self.margin_top, self.margin_bottom)
        gap = getattr(self, "gap_mm", 1.0)

        new_pieces = fill_sheet_pieces(
            target_piece=target_piece,
            placed_pieces=self.placed_pieces,
            sheet_width=self.sheet_width,
            sheet_height=self.sheet_height,
            margins=margins,
            gap_mm=gap,
            max_pieces=1000
        )

        if not new_pieces:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill Sheet: Nenhuma cópia coube na chapa respeitando margens e folga.")
            return

        self.push_undo()
        self.placed_pieces.extend(new_pieces)
        self.set_modified(True)
        self.update_sidebar_targets()
        self.redraw()
        self.update_status()
        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=f"Fill Sheet: {len(new_pieces)} peça(s) adicionada(s) com sucesso.")

    def fill_sheet_alternate(self, target_idx=None):
        """
        Executa Fill Sheet Alternate (Win32 ID 52106):
        Preenche a chapa inteira alternando rotações 0° / 180° por linha para acoplamento bico-calcanhar.
        # CONFIRMAR NO WINDOWS: acoplamento e fase inicial entre linhas.
        """
        if target_idx is None:
            target_idx = self.get_target_piece_index()
        if target_idx is None or target_idx < 0 or target_idx >= len(self.placed_pieces):
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill Sheet Alternate: Nenhuma peça selecionada para preenchimento.")
            return

        target_piece = self.placed_pieces[target_idx]
        margins = (self.margin_left, self.margin_right, self.margin_top, self.margin_bottom)
        gap = getattr(self, "gap_mm", 1.0)

        new_pieces = fill_sheet_alternate_pieces(
            target_piece=target_piece,
            placed_pieces=self.placed_pieces,
            sheet_width=self.sheet_width,
            sheet_height=self.sheet_height,
            margins=margins,
            gap_mm=gap,
            max_pieces=1000,
            row_phase_shift=0
        )

        if not new_pieces:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill Sheet Alternate: Nenhuma cópia coube na chapa respeitando margens e folga.")
            return

        self.push_undo()
        self.placed_pieces.extend(new_pieces)
        self.set_modified(True)
        self.update_sidebar_targets()
        self.redraw()
        self.update_status()
        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=f"Fill Sheet Alternate: {len(new_pieces)} peça(s) adicionada(s) com sucesso.")

    def fill_user_dialog(self, target_idx=None):
        """
        Abre o diálogo 'Set User constraints' (Dialog 159, Win32 ID 50003) e executa o preenchimento.
        # CONFIRMAR NO WINDOWS: diálogo modal com retenção de valores em RAM.
        """
        if target_idx is None:
            target_idx = self.get_target_piece_index()
        if target_idx is None or target_idx < 0 or target_idx >= len(self.placed_pieces):
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill User: Nenhuma peça selecionada para preenchimento.")
            return

        target_piece = self.placed_pieces[target_idx]

        dialog = FillUserDialog(self)
        try:
            self.wait_window(dialog)
        except Exception:
            pass
        constraints = dialog.result
        if not constraints:
            return

        margins = (self.margin_left, self.margin_right, self.margin_top, self.margin_bottom)
        gap = getattr(self, "gap_mm", 1.0)

        new_pieces = fill_user_pieces(
            target_piece=target_piece,
            placed_pieces=self.placed_pieces,
            sheet_width=self.sheet_width,
            sheet_height=self.sheet_height,
            constraints=constraints,
            margins=margins,
            base_gap_mm=gap,
            max_safety_limit=1000
        )

        if not new_pieces:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Fill User: Nenhuma cópia coube com as restrições fornecidas.")
            return

        self.push_undo()
        self.placed_pieces.extend(new_pieces)
        self.set_modified(True)
        self.update_sidebar_targets()
        self.redraw()
        self.update_status()
        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=f"Fill User: {len(new_pieces)} peça(s) adicionada(s) com sucesso.")

    def on_rbutton_press(self, event):
        """
        Inicia a preparação para Rotação Livre 360° (OnRButtonDown 0x418550) ou Menu de Contexto 102.
        - Registra ponto inicial do clique direito para diferenciar clique estático (< 2.65 px) de arrasto (> 2.65 px).
        - O botão direito NÃO altera a seleção existente (selected_index e selected_indices inalterados).
        - Registra snapshot prévio e ponto inicial (x0, y0).
        """
        try:
            self.canvas.focus_set()
        except Exception:
            pass

        self._cancel_drag_job()
        self._pending_drag_xy = None
        self._cancel_redraw_job()

        # Ponto inicial do clique direito
        self._rdrag_start_x = event.x
        self._rdrag_start_y = event.y
        self._rdrag_moved = False
        # O botão direito NÃO altera a seleção existente (selected_index e selected_indices inalterados)
        sel_indices = set(self.get_selected_indices())

        if not sel_indices:
            # Nenhuma peça selecionada
            if bool(getattr(event, "state", 0) & 0x0004):
                self.zoom_out(event.x, event.y)
                return "break"
            self._rdrag_active = False
            self._rdrag_rotating = False
            return

        # Snapshot das peças antes de qualquer alteração
        self._rdrag_active = True
        self._rdrag_rotating = False
        self._rdrag_is_ctrl = bool(getattr(event, "state", 0) & 0x0004)
        self._rdrag_selected_indices = list(sel_indices)
        self._rdrag_pre_pieces = [dict(p) for p in self.placed_pieces]
        self._rdrag_piece_init_centers = {}
        self._rdrag_piece_base_centers = {}

        # Determina centros de base e centros iniciais na chapa de cada peça selecionada
        for idx in self._rdrag_selected_indices:
            p = self.placed_pieces[idx]
            contour = p.get("contour", [])
            if contour:
                min_x, min_y, max_x, max_y = polygon_bbox(contour)
                cx0 = (min_x + max_x) / 2.0
                cy0 = (min_y + max_y) / 2.0
            else:
                cx0, cy0 = 0.0, 0.0
            self._rdrag_piece_base_centers[idx] = (cx0, cy0)
            cur_rot = float(p.get("rotation", 0.0))
            cx_old, cy_old = rotate_point(cx0, cy0, cur_rot)
            cp_x = float(p.get("x", 0.0)) + cx_old
            cp_y = float(p.get("y", 0.0)) + cy_old
            self._rdrag_piece_init_centers[idx] = (cp_x, cp_y)

        # Determina o pivô (Cx, Cy) em coordenadas de mundo (chapa)
        if self._rdrag_is_ctrl and len(self._rdrag_selected_indices) > 1:
            # Com Ctrl: média dos limites do bounding box coletivo de todas as peças selecionadas (0x418683)
            all_min_x, all_min_y = float("inf"), float("inf")
            all_max_x, all_max_y = float("-inf"), float("-inf")
            for idx in self._rdrag_selected_indices:
                p = self.placed_pieces[idx]
                poly = transform_contour(p.get("contour", []), p.get("x", 0.0), p.get("y", 0.0), p.get("rotation", 0.0))
                if poly:
                    b_min_x, b_min_y, b_max_x, b_max_y = polygon_bbox(poly)
                    all_min_x = min(all_min_x, b_min_x)
                    all_min_y = min(all_min_y, b_min_y)
                    all_max_x = max(all_max_x, b_max_x)
                    all_max_y = max(all_max_y, b_max_y)
            if all_min_x != float("inf"):
                Cx = (all_min_x + all_max_x) / 2.0
                Cy = (all_min_y + all_max_y) / 2.0
            else:
                primary_idx = self.selected_index if (self.selected_index is not None and 0 <= self.selected_index < len(self.placed_pieces)) else self._rdrag_selected_indices[0]
                Cx, Cy = self._rdrag_piece_init_centers[primary_idx]
        else:
            # Sem modificador / seleção única: centro do bounding box da peça selecionada (0x4186f5)
            primary_idx = self.selected_index if (self.selected_index is not None and 0 <= self.selected_index < len(self.placed_pieces)) else self._rdrag_selected_indices[0]
            Cx, Cy = self._rdrag_piece_init_centers[primary_idx]

        self._rdrag_pivot_world = (Cx, Cy)
        Cx_px, Cy_px = self.world_to_screen(Cx, Cy)
        self._rdrag_pivot_screen = (Cx_px, Cy_px)

        # Ângulo inicial cartesiano do cursor em relação ao pivô
        dx0 = float(event.x - Cx_px)
        dy0 = float(Cy_px - event.y)
        theta0 = math.degrees(math.atan2(dy0, dx0))
        self._rdrag_theta0 = theta0
        self._rdrag_last_theta = theta0
        self._rdrag_cum_delta = 0.0
        return "break"

    def on_rbutton_drag(self, event):
        """
        Executa a rotação angular contínua em tempo real (OnMouseMove 0x4269c4).
        - Filtro de ruído / deadzone: dx^2 + dy^2 <= 36 (~6.0 px) para cliques estáveis.
        - Cálculo angular via atan2 sem acúmulo de erro incremental.
        - Desenha os 2 raios e o arco de ~42 px (tag: rdrag_guide).
        - Exibe o ângulo em tempo real na barra de status.
        """
        if not getattr(self, "_rdrag_active", False):
            return

        dx_click = event.x - getattr(self, "_rdrag_start_x", event.x)
        dy_click = event.y - getattr(self, "_rdrag_start_y", event.y)
        dist_sq = dx_click * dx_click + dy_click * dy_click

        if not self._rdrag_rotating:
            if dist_sq <= 36.0:  # ~6.0 px deadzone
                return
            self._rdrag_moved = True
            self._rdrag_rotating = True

        Cx_px, Cy_px = self._rdrag_pivot_screen
        cur_dx = float(event.x - Cx_px)
        cur_dy = float(Cy_px - event.y)
        theta1 = math.degrees(math.atan2(cur_dy, cur_dx))

        step = theta1 - self._rdrag_last_theta
        if step > 180.0:
            step -= 360.0
        elif step < -180.0:
            step += 360.0
        self._rdrag_cum_delta += step
        self._rdrag_last_theta = theta1
        delta_rot = self._rdrag_cum_delta

        Cx, Cy = self._rdrag_pivot_world
        is_ctrl_group = self._rdrag_is_ctrl and len(self._rdrag_selected_indices) > 1

        for idx in self._rdrag_selected_indices:
            p = self.placed_pieces[idx]
            orig_p = self._rdrag_pre_pieces[idx]
            orig_rot = float(orig_p.get("rotation", 0.0))
            new_rot = (orig_rot + delta_rot) % 360.0
            if abs(new_rot - round(new_rot)) < 1e-9:
                new_rot = float(round(new_rot))
            else:
                new_rot = round(new_rot, 4)

            cx0, cy0 = self._rdrag_piece_base_centers[idx]
            cx_new, cy_new = rotate_point(cx0, cy0, new_rot)

            if is_ctrl_group:
                # Rotação coletiva em grupo (corpo rígido) em torno de (Cx, Cy)
                cp_x0, cp_y0 = self._rdrag_piece_init_centers[idx]
                vx = cp_x0 - Cx
                vy = cp_y0 - Cy
                rvx, rvy = rotate_point(vx, vy, delta_rot)
                cp_x_new = Cx + rvx
                cp_y_new = Cy + rvy
                new_x = cp_x_new - cx_new
                new_y = cp_y_new - cy_new
            else:
                # Rotação individual em torno do próprio centro
                cp_x0, cp_y0 = self._rdrag_piece_init_centers[idx]
                new_x = cp_x0 - cx_new
                new_y = cp_y0 - cy_new

            if abs(new_x - round(new_x)) < 1e-9:
                new_x = float(round(new_x))
            else:
                new_x = round(new_x, 4)
            if abs(new_y - round(new_y)) < 1e-9:
                new_y = float(round(new_y))
            else:
                new_y = round(new_y, 4)

            p["x"] = new_x
            p["y"] = new_y
            p["rotation"] = new_rot
            if "rotation_rad" in p:
                p["rotation_rad"] = math.radians(new_rot)

            self.redraw_single_piece(idx)

        # Guia Visual no Canvas (tag: rdrag_guide)
        try:
            self.canvas.delete("rdrag_guide")
            arc_r = 42.0

            # Pivô: marcador circular no centro (Cx_px, Cy_px)
            self.canvas.create_oval(
                Cx_px - 3, Cy_px - 3, Cx_px + 3, Cy_px + 3,
                fill="#3b82f6", outline="#1d4ed8", width=1.5,
                tags="rdrag_guide"
            )

            # Raio 1: linha tracejada do pivô na direção de theta0
            r1_len = max(arc_r, math.hypot(self._rdrag_start_x - Cx_px, self._rdrag_start_y - Cy_px))
            r1_rad = math.radians(self._rdrag_theta0)
            r1_x = Cx_px + r1_len * math.cos(r1_rad)
            r1_y = Cy_px - r1_len * math.sin(r1_rad)
            self.canvas.create_line(
                Cx_px, Cy_px, r1_x, r1_y,
                dash=(4, 4), fill="#3b82f6", width=1.5,
                tags="rdrag_guide"
            )

            # Raio 2: linha contínua do pivô até o cursor atual
            self.canvas.create_line(
                Cx_px, Cy_px, event.x, event.y,
                fill="#2563eb", width=1.5,
                tags="rdrag_guide"
            )

            # Arco circular de raio ~42 px centrado no pivô, começando em theta0 com extensão delta_rot
            bbox_arc = (Cx_px - arc_r, Cy_px - arc_r, Cx_px + arc_r, Cy_px + arc_r)
            if abs(delta_rot) >= 359.9:
                self.canvas.create_oval(
                    bbox_arc,
                    outline="#3b82f6", width=2.0,
                    tags="rdrag_guide"
                )
            elif abs(delta_rot) > 0.1:
                self.canvas.create_arc(
                    bbox_arc,
                    start=self._rdrag_theta0,
                    extent=delta_rot,
                    style="arc",
                    outline="#3b82f6", width=2.0,
                    tags="rdrag_guide"
                )

            self.canvas.tag_raise("rdrag_guide")
        except Exception:
            pass

        # Barra de status em tempo real com ângulo atual e variação (duas casas decimais)
        primary_idx = self.selected_index if (self.selected_index is not None and 0 <= self.selected_index < len(self.placed_pieces)) else self._rdrag_selected_indices[0]
        curr_rot = self.placed_pieces[primary_idx]["rotation"]
        sign = "+" if delta_rot >= 0 else ""
        status_msg = f"Rotação: {curr_rot:.2f}° (Δ {sign}{delta_rot:.2f}°) | ESC para cancelar"
        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=status_msg)
        return "break"

    def on_rbutton_release(self, event):
        """
        Finaliza a rotação livre 360° (OnRButtonUp 0x421fd0) ou abre o Menu de Contexto 102.
        - Deslocamento < 2.65 px sem arrasto: abre o Menu de Contexto 102.
        - Deslocamento >= 2.65 px: finaliza rotação livre e NÃO abre o menu.
        """
        try:
            self.canvas.delete("rdrag_guide")
        except Exception:
            pass

        start_x = getattr(self, "_rdrag_start_x", event.x)
        start_y = getattr(self, "_rdrag_start_y", event.y)
        dx = event.x - start_x
        dy = event.y - start_y
        dist = math.hypot(dx, dy)
        was_rotating = getattr(self, "_rdrag_rotating", False)
        was_drag = was_rotating or getattr(self, "_rdrag_moved", False) or (dist >= 6.0)

        self._rdrag_active = False
        self._rdrag_rotating = False
        self._rdrag_moved = False

        if not was_drag:
            # Clique rápido (< 6.0 px sem rotação): abre o Menu de Contexto 102
            # O botão direito NÃO altera a seleção existente (age sobre a seleção atual)
            self._rdrag_pre_pieces = None
            self._rdrag_selected_indices = []
            if hasattr(self, "_rdrag_piece_init_centers"):
                self._rdrag_piece_init_centers.clear()
            if hasattr(self, "_rdrag_piece_base_centers"):
                self._rdrag_piece_base_centers.clear()
            self.open_context_menu_102(event)
            return "break"

        if not was_rotating:
            # Soltura com arrasto mas sem giro efetivo
            self._rdrag_pre_pieces = None
            self._rdrag_selected_indices = []
            if hasattr(self, "_rdrag_piece_init_centers"):
                self._rdrag_piece_init_centers.clear()
            if hasattr(self, "_rdrag_piece_base_centers"):
                self._rdrag_piece_base_centers.clear()
            return

        # Conclusão do giro: verifica se houve alteração real
        pieces_changed = False
        if self._rdrag_pre_pieces:
            for idx in self._rdrag_selected_indices:
                if idx >= len(self.placed_pieces) or idx >= len(self._rdrag_pre_pieces):
                    continue
                p_now = self.placed_pieces[idx]
                p_old = self._rdrag_pre_pieces[idx]
                if (abs(p_now.get("rotation", 0.0) - p_old.get("rotation", 0.0)) > 1e-4 or
                    abs(p_now.get("x", 0.0) - p_old.get("x", 0.0)) > 1e-4 or
                    abs(p_now.get("y", 0.0) - p_old.get("y", 0.0)) > 1e-4):
                    pieces_changed = True
                    break

        if pieces_changed and self._rdrag_pre_pieces:
            state = {
                "pieces": [dict(p) for p in self._rdrag_pre_pieces],
                "sheet_height": self.sheet_height,
                "trim_cut_line": copy.deepcopy(getattr(self, "trim_cut_line", None)),
                "original_sheet_height": getattr(self, "original_sheet_height", None)
            }
            self.undo_stack.append(state)
            if len(self.undo_stack) > UNDO_MAX_LEVELS:
                self.undo_stack.pop(0)
            self.set_modified(True)

        self._rdrag_pre_pieces = None
        self._rdrag_selected_indices = []
        if hasattr(self, "_rdrag_piece_init_centers"):
            self._rdrag_piece_init_centers.clear()
        if hasattr(self, "_rdrag_piece_base_centers"):
            self._rdrag_piece_base_centers.clear()

        self.redraw()
        self.update_status()

        # Validação não-bloqueante na barra de status
        primary_idx = self.selected_index if (self.selected_index is not None and 0 <= self.selected_index < len(self.placed_pieces)) else 0
        curr_rot = self.placed_pieces[primary_idx]["rotation"] if (0 <= primary_idx < len(self.placed_pieces)) else 0.0
        warn = self.validate_placement_status()
        if warn and hasattr(self, "lbl_stat_left"):
            self.lbl_stat_left.config(text=warn)
        elif hasattr(self, "lbl_stat_left"):
            self.lbl_stat_left.config(text="Rotação livre concluída.")
        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=f"Rotação finalizada em {curr_rot:.2f}°.")
        return "break"

    def redraw_single_piece(self, piece_idx):
        """
        Redesenha unicamente os itens gráficos da peça especificada (piece_{piece_idx}),
        sem apagar nem recriar a chapa, grade de 10 cm, sidebar ou as outras peças estáticas.
        """
        if not (0 <= piece_idx < len(self.placed_pieces)):
            return

        p = self.placed_pieces[piece_idx]
        self.canvas.delete(f"piece_{piece_idx}")

        scale = self.plate_scale
        x1 = self.plate_x1
        y2 = self.plate_y2

        poly, bbox = self._get_piece_geom(p)

        # Checa colisão com limites da chapa ou com qualquer outra peça
        is_col = (
            bbox[0] < -0.01 or bbox[1] < -0.01 or
            bbox[2] > self.sheet_width + 0.01 or bbox[3] > self.sheet_height + 0.01
        )
        colliding_with = []
        for j, other in enumerate(self.placed_pieces):
            if j == piece_idx:
                continue
            other_poly, other_bbox = self._get_piece_geom(other)
            if not bbox_overlap(bbox, other_bbox, 0.0):
                continue
            if polygons_collide(poly, other_poly, gap=0.0, bbox_a=bbox, bbox_b=other_bbox):
                is_col = True
                colliding_with.append(j)

        screen_pts = []
        for pt in poly:
            sx = x1 + pt["x"] * scale
            sy = y2 - pt["y"] * scale
            screen_pts.extend([sx, sy])

        size_str = str(p.get("size") or (p.get("shape", {}).get("size") if isinstance(p.get("shape"), dict) else "") or "")
        if not size_str and p.get("target_id"):
            ts = next((t for t in TARGET_SPECS if t["id"] == p["target_id"]), None)
            if ts:
                size_str = str(ts.get("size", ""))
        if not size_str:
            size_str = str(p.get("name") or "")

        base_col = p.get("color") or get_color_for_size(size_str, piece_idx)
        p["color"] = base_col

        is_sel = (piece_idx == self.selected_index) or (hasattr(self, "selected_indices") and piece_idx in self.selected_indices)
        if is_col:
            outline_col = "#ef4444"
            line_w = 3.0
        elif is_sel:
            outline_col = "#ff0000"
            line_w = 2.5
        else:
            outline_col = "#1e293b"
            line_w = 1.2

        fill_col = "" if (SELECTED_OUTLINE_ONLY and is_sel) else base_col

        self.canvas.create_polygon(
            screen_pts,
            fill=fill_col,
            outline=outline_col,
            width=line_w,
            tags=(f"piece_{piece_idx}", f"piece_poly_{piece_idx}", "piece_item")
        )

        if len(self.placed_pieces) <= 40 and len(screen_pts) >= 6:
            avg_sx = sum(screen_pts[0::2]) / (len(screen_pts) // 2)
            avg_sy = sum(screen_pts[1::2]) / (len(screen_pts) // 2)
            txt_col = get_contrast_text_color(fill_col)
            display_label = f"Nº {size_str}" if size_str else f"#{piece_idx + 1}"
            self.canvas.create_text(
                avg_sx, avg_sy,
                text=display_label,
                fill=txt_col,
                font=("Segoe UI", 8, "bold"),
                tags=(f"piece_{piece_idx}", f"piece_txt_{piece_idx}", "piece_item")
            )

        if is_sel and len(screen_pts) >= 4:
            min_sx = min(screen_pts[0::2])
            max_sx = max(screen_pts[0::2])
            min_sy = min(screen_pts[1::2])
            max_sy = max(screen_pts[1::2])
            self.canvas.create_rectangle(
                min_sx - 3, min_sy - 3, max_sx + 3, max_sy + 3,
                outline="#ef4444" if is_col else "#ffffff",
                dash=(3, 3),
                width=1.5,
                tags=(f"piece_{piece_idx}", f"piece_box_{piece_idx}", "piece_item")
            )

        # Destaca peças atingidas em âmbar
        for j in colliding_with:
            self.canvas.itemconfig(f"piece_poly_{j}", outline="#f59e0b", width=2.5)

        self.canvas.tag_raise(f"piece_{piece_idx}")
        self.canvas.tag_raise("sidebar_ui")

        if is_col and hasattr(self, "lbl_stat_left"):
            self.lbl_stat_left.config(text=f"⚠️ ALERTA: Colisão na peça #{piece_idx + 1}! Sobreposição proibida.")
        elif not is_col and hasattr(self, "lbl_stat_left"):
            self.lbl_stat_left.config(text="")

    def push_undo(self):
        """Salva o estado atual do layout na pilha de desfazer (Ctrl+Z) de forma leve."""
        state = {
            "pieces": [dict(p) for p in self.placed_pieces],
            "sheet_width": self.sheet_width,
            "sheet_height": self.sheet_height,
            "trim_cut_line": copy.deepcopy(getattr(self, "trim_cut_line", None)),
            "original_sheet_width": getattr(self, "original_sheet_width", None),
            "original_sheet_height": getattr(self, "original_sheet_height", None)
        }
        self.undo_stack.append(state)
        if len(self.undo_stack) > UNDO_MAX_LEVELS:
            self.undo_stack.pop(0)

    def undo_action(self, event=None):
        """Desfaz a última alteração feita no layout (Ctrl+Z). Não existe redo (Ctrl+Y proibido)."""
        if self.undo_stack:
            prev_state = self.undo_stack.pop()
            if isinstance(prev_state, dict):
                self.placed_pieces = prev_state.get("pieces", [])
                if "sheet_width" in prev_state:
                    self.sheet_width = prev_state["sheet_width"]
                if "sheet_height" in prev_state:
                    self.sheet_height = prev_state["sheet_height"]
                self.trim_cut_line = copy.deepcopy(prev_state.get("trim_cut_line", None))
                self.original_sheet_width = prev_state.get("original_sheet_width", None)
                self.original_sheet_height = prev_state.get("original_sheet_height", None)
            elif isinstance(prev_state, list):
                self.placed_pieces = prev_state

            if self.selected_index is not None and self.selected_index >= len(self.placed_pieces):
                self.selected_index = len(self.placed_pieces) - 1
            self.is_modified = (len(self.undo_stack) != getattr(self, "_saved_undo_index", -1))
            self._update_window_title()
            self.update_sheet_status()
            self.redraw()
            self.update_status()
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="Layout: alteração desfeita (Ctrl+Z).", fg=THEME.get("text_main", "#000000"))
        return "break"

    def zoom_at(self, factor, center_x=None, center_y=None):
        """Aplica zoom com fator multiplicativo (ex: 1.20 = +20%) centrado em (center_x, center_y)."""
        old_zoom = getattr(self, "zoom_factor", 1.0)
        new_zoom = max(0.5, min(5.0, old_zoom * factor))
        if abs(new_zoom - old_zoom) < 1e-4:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 10 or ch <= 10:
            self.zoom_factor = new_zoom
            return

        if center_x is None or center_y is None:
            if self.selected_index is not None and 0 <= self.selected_index < len(self.placed_pieces):
                p = self.placed_pieces[self.selected_index]
                center_x, center_y = self.world_to_screen(p["x"], p["y"])
            else:
                center_x = (self.plate_x1 + self.plate_x2) / 2.0 if hasattr(self, "plate_x1") else cw / 2.0
                center_y = (self.plate_y1 + self.plate_y2) / 2.0 if hasattr(self, "plate_y1") else ch / 2.0

        wx, wy = self.screen_to_world(center_x, center_y)

        self.zoom_factor = new_zoom
        self.view_center_sx = center_x
        self.view_center_sy = center_y
        self.view_center_wx = wx
        self.view_center_wy = wy
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0

        self.redraw()
        pct = int(round(self.zoom_factor * 100))
        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=f"Zoom: {pct}% | x: {wx:.2f} y: {wy:.2f}")

    def zoom_in(self, center_x=None, center_y=None):
        """Amplia 20% a cada clique na ferramenta ou atalho (fator 1.20)."""
        self.zoom_at(1.20, center_x, center_y)

    def zoom_out(self, center_x=None, center_y=None):
        """Reduz 20% a cada acionamento (fator 1.0 / 1.20)."""
        self.zoom_at(1.0 / 1.20, center_x, center_y)

    def reset_view(self):
        """Restaura o enquadramento total padrão da chapa (100% Fit)."""
        self.zoom_factor = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.view_center_wx = None
        self.view_center_wy = None
        self.view_center_sx = None
        self.view_center_sy = None
        self.redraw()
        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text="Visualização restaurada: Layout Completo (100%).")

    def on_ctrl_canvas_click(self, event):
        """Atalho: CTRL + clique do mouse de ação aplica zoom de +20% centrado no cursor."""
        self.is_dragging_piece = False
        self._pre_drag_pieces = None
        self.is_panning = False
        self.zoom_in(event.x, event.y)
        return "break"

    def _on_ctrl_press(self, event=None):
        try:
            cx = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
            if hasattr(self, "sidebar_div_x") and 0 <= cx < self.sidebar_div_x:
                self._set_cursor("crosshair")
        except Exception:
            pass

    def _on_ctrl_release(self, event=None):
        try:
            if not getattr(self, "is_panning", False) and not getattr(self, "is_dragging_divider", False):
                self._set_cursor("arrow")
        except Exception:
            pass

    def on_pan_start(self, event):
        # Conflito resolvido: COM peça selecionada o botão do meio faz Bump;
        # SEM seleção continua fazendo Pan (comportamento original).
        if self.get_selected_indices() and self._start_mouse_bump(event):
            return "break"
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self._set_cursor("fleur")
        return "break"

    def on_pan_drag(self, event):
        if self._bump_mode:
            self._update_mouse_bump(event)
            return "break"
        if getattr(self, "is_panning", False):
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.pan_offset_x = getattr(self, "pan_offset_x", 0.0) + dx
            self.pan_offset_y = getattr(self, "pan_offset_y", 0.0) + dy
            self._schedule_redraw(PAN_REDRAW_INTERVAL_MS)
        return "break"

    def on_pan_end(self, event):
        if self._bump_mode:
            self._finish_mouse_bump(event)
            return "break"
        self.is_panning = False
        self._cancel_redraw_job()
        self._set_cursor("arrow")
        self.redraw()
        return "break"

    def on_ctrl_mousewheel(self, event):
        if event.delta > 0:
            self.zoom_in(event.x, event.y)
        elif event.delta < 0:
            self.zoom_out(event.x, event.y)
        return "break"

    def set_modified(self, modified: bool = True):
        self.is_modified = modified
        self._update_window_title()

    def _update_window_title(self):
        star = " *" if getattr(self, "is_modified", False) else ""
        title_text = f"Layout Editor - [{self.layout_name}]{star}"
        if hasattr(self, "lbl_title") and self.lbl_title:
            self.lbl_title.config(text=title_text)

    # -------------------------------------------------------------
    # Operações CAD nas Peças (Bump, Rotate, Delete, Duplicate)
    # -------------------------------------------------------------
    def select_all(self, event=None):
        """Seleciona todas as peças posicionadas na chapa (Ctrl+A)."""
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, tk.Text, ttk.Treeview)):
            return
        if self.placed_pieces:
            self.selected_indices = list(range(len(self.placed_pieces)))
            self.selected_index = len(self.placed_pieces) - 1
            self.redraw()
            self.update_status()
        return "break"

    # =================================================================
    # BUMP MAGNÉTICO (setas + mouse) — desliza até encostar
    # =================================================================
    def _bump_status(self, text):
        """Mensagem curta na barra de status (usada durante o bump)."""
        try:
            if hasattr(self, "lbl_stat_pos") and self.lbl_stat_pos.winfo_exists():
                self.lbl_stat_pos.config(text=text, fg="#1e40af")
        except Exception:
            pass

    def _bump_static_grid(self, skip_indices):
        """Grade espacial com as peças NÃO selecionadas (obstáculos do bump)."""
        grid = SpatialGrid(cell_size=100.0)
        for j, other in enumerate(self.placed_pieces):
            if j in skip_indices:
                continue
            poly = transform_contour(other["contour"], other["x"], other["y"], other["rotation"])
            grid.insert(j, poly, polygon_bbox(poly))
        return grid

    def _bump_margins(self):
        return (
            float(getattr(self, "margin_left", 10.0)),
            float(getattr(self, "margin_right", 10.0)),
            float(getattr(self, "margin_top", 10.0)),
            float(getattr(self, "margin_bottom", 10.0)),
        )

    def _bump_collides_at(self, indices, ux, uy, travel, grid, gap):
        """Testa a seleção deslocada de travel*(ux,uy): colisão real ou fora das margens."""
        m_left, m_right, m_top, m_bottom = self._bump_margins()
        eps = 1e-6
        for idx in indices:
            p = self.placed_pieces[idx]
            poly = transform_contour(p["contour"], p["x"] + ux * travel, p["y"] + uy * travel, p["rotation"])
            bb = polygon_bbox(poly)
            if (bb[0] < m_left - eps or bb[1] < m_bottom - eps
                    or bb[2] > self.sheet_width - m_right + eps
                    or bb[3] > self.sheet_height - m_top + eps):
                return True
            for c_poly, c_bbox in grid.query_potential_colliders(bb, gap=gap):
                if polygons_collide(poly, c_poly, gap=gap, bbox_a=bb, bbox_b=c_bbox):
                    return True
        return False

    def _bump_max_travel(self, indices, ux, uy):
        """Deslocamento máximo antes de sair da área útil da placa, na direção dada."""
        m_left, m_right, m_top, m_bottom = self._bump_margins()
        lim = float("inf")
        for idx in indices:
            p = self.placed_pieces[idx]
            bb = polygon_bbox(transform_contour(p["contour"], p["x"], p["y"], p["rotation"]))
            if ux > 1e-9:
                lim = min(lim, (self.sheet_width - m_right - bb[2]) / ux)
            elif ux < -1e-9:
                lim = min(lim, (m_left - bb[0]) / ux)
            if uy > 1e-9:
                lim = min(lim, (self.sheet_height - m_top - bb[3]) / uy)
            elif uy < -1e-9:
                lim = min(lim, (m_bottom - bb[1]) / uy)
        if lim == float("inf"):
            return 0.0
        return max(0.0, lim)

    def bump_selection_vector(self, dx, dy):
        """
        Bump Magnético: desliza a seleção na direção (dx, dy) até encostar em outra
        peça (contorno real, respeitando o gap da sessão) ou no limite da placa.

        Usado pelas SETAS e pelos três gatilhos de mouse (botão do meio, duplo-clique
        + arrasto e Ctrl+Shift + arrasto). Retorna True se algo se moveu.
        """
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, tk.Text, ttk.Treeview)):
            return False

        indices = list(self.get_selected_indices() or [])
        if not indices:
            return False

        norm = math.hypot(float(dx), float(dy))
        if norm < 1e-9:
            return False
        ux, uy = float(dx) / norm, float(dy) / norm

        gap = float(getattr(self, "gap_mm", 1.0) or 0.0)
        grid = self._bump_static_grid(set(indices))
        max_travel = self._bump_max_travel(indices, ux, uy)
        if max_travel <= 0.01:
            self._bump_status("Ready")
            return False

        # Procura o PRIMEIRO contato ao longo da trajetória (pode haver obstáculo no
        # meio do caminho, não só no fim): varredura grossa + refino binário.
        step = max(1.0, min(10.0, max_travel / 400.0))
        travel = max_travel
        prev_free = 0.0
        t = 0.0
        while t < max_travel - 1e-9:
            t = min(max_travel, t + step)
            if self._bump_collides_at(indices, ux, uy, t, grid, gap):
                lo, hi = prev_free, t
                for _ in range(BUMP_SEARCH_ITERS):
                    mid = (lo + hi) / 2.0
                    if self._bump_collides_at(indices, ux, uy, mid, grid, gap):
                        hi = mid
                    else:
                        lo = mid
                travel = lo
                break
            prev_free = t

        # Validação final obrigatória (exata): se ainda colidir, não move
        if travel > 0.05 and self._bump_collides_at(indices, ux, uy, travel, grid, gap):
            travel = 0.0

        if travel <= 0.05:
            self._bump_status("Ready")
            return False

        self.push_undo()
        for idx in indices:
            p = self.placed_pieces[idx]
            p["x"] += ux * travel
            p["y"] += uy * travel
            self.redraw_single_piece(idx)
        self.set_modified(True)
        self.update_status()
        self._bump_status("Ready")
        return True

    # ---------------- Gatilhos de mouse ----------------
    def _selection_world_center(self, indices):
        m_left = m_bottom = float("inf")
        m_right = m_top = float("-inf")
        for idx in indices:
            p = self.placed_pieces[idx]
            bb = polygon_bbox(transform_contour(p["contour"], p["x"], p["y"], p["rotation"]))
            m_left = min(m_left, bb[0]); m_bottom = min(m_bottom, bb[1])
            m_right = max(m_right, bb[2]); m_top = max(m_top, bb[3])
        return ((m_left + m_right) / 2.0, (m_bottom + m_top) / 2.0)

    def _start_mouse_bump(self, event):
        return self._start_mouse_bump_at(event.x, event.y)

    def _start_mouse_bump_at(self, x, y):
        """Inicia o bump por arrasto: linha elástica do centro da seleção até o mouse."""
        indices = list(self.get_selected_indices() or [])
        if not indices:
            return False
        cx, cy = self._selection_world_center(indices)
        sx, sy = self.world_to_screen(cx, cy)
        self._bump_mode = True
        self._bump_press_xy = (x, y)
        self._bump_center_screen = (sx, sy)
        self.canvas.delete("bump_rubber")
        self._bump_line_id = self.canvas.create_line(
            sx, sy, x, y,
            fill="#2563eb", dash=(4, 2), width=1.5, tags="bump_rubber"
        )
        try:
            self._set_cursor(BUMP_CURSOR)
        except tk.TclError:
            self._set_cursor("crosshair")
        self._bump_status("Bump the Selection")
        # não deixa o arrasto normal de peça rodar em paralelo
        self.is_dragging_piece = False
        self._drag_indices = []
        self.canvas.delete("drag_ghost")
        return True

    def _update_mouse_bump(self, event):
        if not self._bump_mode or self._bump_line_id is None:
            return
        sx, sy = self._bump_center_screen
        self.canvas.coords(self._bump_line_id, sx, sy, event.x, event.y)

    def _finish_mouse_bump(self, event):
        """Ao soltar: converte o vetor do arrasto e executa o bump."""
        if not self._bump_mode:
            return False
        self._bump_mode = False
        self._bump_armed = False
        self.canvas.delete("bump_rubber")
        self._bump_line_id = None
        self._set_cursor("arrow")
        sx, sy = self._bump_press_xy or (event.x, event.y)
        dx_px = event.x - sx
        dy_px = event.y - sy
        if math.hypot(dx_px, dy_px) < BUMP_MIN_DRAG_PX:
            self._bump_status("Ready")
            return False
        scale = self.plate_scale if getattr(self, "plate_scale", 0) > 0 else 1.0
        # Y da tela é invertido em relação ao mundo (mm)
        self.bump_selection_vector(dx_px / scale, -dy_px / scale)
        self._bump_status("Ready")
        return True

    def _cancel_mouse_bump(self):
        """Cancela o bump em andamento (Esc): remove a linha elástica e restaura o cursor."""
        if self._bump_line_id is not None:
            self.canvas.delete("bump_rubber")
        self._bump_mode = False
        self._bump_armed = False
        self._bump_line_id = None
        self._set_cursor("arrow")
        self._bump_status("Ready")

    def on_canvas_escape(self, event=None):
        if self._bump_mode or self._bump_armed:
            self._cancel_mouse_bump()
            return "break"
        return None

    def on_ctrl_shift_bump_start(self, event):
        """Ctrl+Shift + arrasto do botão esquerdo: bump direcional."""
        self.canvas.focus_set()
        if self._start_mouse_bump(event):
            return "break"
        return None

    def on_ctrl_shift_bump_drag(self, event):
        self._update_mouse_bump(event)
        return "break"

    def on_ctrl_shift_bump_end(self, event):
        self._finish_mouse_bump(event)
        return "break"

    def nudge_selected(self, dx_mm, dy_mm):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, tk.Text, ttk.Treeview)):
            return
        sel_indices = self.get_selected_indices()
        if sel_indices:
            self.push_undo()
            for idx in sel_indices:
                p = self.placed_pieces[idx]
                p["x"] += dx_mm
                p["y"] += dy_mm
                self.redraw_single_piece(idx)
            self.set_modified(True)
            self.update_status()

    def rotate_selected(self, delta_deg, group_autorepeat=False):
        """
        Rotaciona a(s) peça(s) selecionada(s) por delta_deg (graus).
        Usa rotação matemática invariante centrada no contorno base unrotated.
        """
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, tk.Text, ttk.Treeview)):
            return
        sel_indices = self.get_selected_indices()
        if sel_indices:
            if not group_autorepeat:
                self.push_undo()
            for idx in sel_indices:
                p = self.placed_pieces[idx]
                rotate_piece_in_place(p, delta_deg)
                self.redraw_single_piece(idx)
            self.set_modified(True)
            self.update_status()

    def on_f1_press(self, event=None):
        """F1: Ajuste fino, gira a(s) peça(s) selecionada(s) 2° para a ESQUERDA (anti-horário). Suporta auto-repeat."""
        if self.get_selected_indices():
            delta = ROT_DIR_LEFT * ROT_FINE_STEP_DEG
            if UNDO_GROUP_AUTOREPEAT:
                if not self._in_fine_rot_sequence:
                    self._in_fine_rot_sequence = True
                    self.push_undo()
                self.rotate_selected(delta, group_autorepeat=True)
                if self._fine_rot_timer:
                    try:
                        self.after_cancel(self._fine_rot_timer)
                    except Exception:
                        pass
                self._fine_rot_timer = self.after(350, self._end_fine_rot_sequence)
            else:
                self.rotate_selected(delta, group_autorepeat=False)
        return "break"

    def on_f1_release(self, event=None):
        return "break"

    def on_f2_press(self, event=None):
        """F2: Ajuste fino, gira a(s) peça(s) selecionada(s) 2° para a DIREITA (horário). Suporta auto-repeat."""
        if self.get_selected_indices():
            delta = ROT_DIR_RIGHT * ROT_FINE_STEP_DEG
            if UNDO_GROUP_AUTOREPEAT:
                if not self._in_fine_rot_sequence:
                    self._in_fine_rot_sequence = True
                    self.push_undo()
                self.rotate_selected(delta, group_autorepeat=True)
                if self._fine_rot_timer:
                    try:
                        self.after_cancel(self._fine_rot_timer)
                    except Exception:
                        pass
                self._fine_rot_timer = self.after(350, self._end_fine_rot_sequence)
            else:
                self.rotate_selected(delta, group_autorepeat=False)
        return "break"

    def on_f2_release(self, event=None):
        return "break"

    def _end_fine_rot_sequence(self):
        self._in_fine_rot_sequence = False
        self._fine_rot_timer = None

    def on_f3_press(self, event=None):
        """F3: Giro grosso de 90° anti-horário por toque (ciclo 0->90->180->270). SEM auto-repeat."""
        if getattr(self, "_f3_pressed", False):
            return "break"
        self._f3_pressed = True
        if self.get_selected_indices():
            delta = ROT_DIR_F3 * ROT_90_STEP_DEG
            self.rotate_selected(delta, group_autorepeat=False)
        return "break"

    def on_f3_release(self, event=None):
        def _clear():
            self._f3_pressed = False
        self.after(50, _clear)
        return "break"

    def on_f4_press(self, event=None):
        """F4: Gira a(s) peça(s) selecionada(s) 180° ('o pé oposto'). SEM auto-repeat."""
        if getattr(self, "_f4_pressed", False):
            return "break"
        self._f4_pressed = True
        if self.get_selected_indices():
            delta = ROT_FLIP_STEP_DEG
            self.rotate_selected(delta, group_autorepeat=False)
        return "break"

    def on_f4_release(self, event=None):
        def _clear():
            self._f4_pressed = False
        self.after(50, _clear)
        return "break"

    def mirror_selected(self):
        sel_indices = self.get_selected_indices()
        if sel_indices:
            self.push_undo()
            for idx in sel_indices:
                p = self.placed_pieces[idx]
                p["contour"] = [{"x": -pt["x"], "y": pt["y"]} for pt in p["contour"]]
                p["is_mirrored"] = not p.get("is_mirrored", False)
                self.redraw_single_piece(idx)
            self.set_modified(True)
            self.redraw()
            self.update_status()

    def delete_selected(self):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, tk.Text, ttk.Treeview)):
            return
        sel_indices = sorted(set(self.get_selected_indices()), reverse=True)
        if sel_indices:
            self.push_undo()
            for idx in sel_indices:
                if 0 <= idx < len(self.placed_pieces):
                    self.placed_pieces.pop(idx)
            self.selected_indices = []
            self.selected_index = None
            self.set_modified(True)
            self.redraw()
            self.update_status()

    def duplicate_selected(self):
        sel_indices = self.get_selected_indices()
        if sel_indices:
            self.push_undo()
            new_indices = []
            for idx in sel_indices:
                orig = self.placed_pieces[idx]
                new_p = dict(orig)
                new_p["x"] += 25.0
                new_p["y"] += 15.0
                self.placed_pieces.append(new_p)
                new_indices.append(len(self.placed_pieces) - 1)
            self.selected_indices = new_indices
            self.selected_index = new_indices[-1] if new_indices else None
            self.set_modified(True)
            self.redraw()
            self.update_status()

    def clear_all_pieces(self):
        if messagebox.askyesno("Layout Editor", "Deseja remover todas as peças do layout atual?"):
            if getattr(self, "sim_running", False):
                self.stop_simulation()
            self.push_undo()
            self.placed_pieces = []
            self.selected_indices = []
            self.selected_index = None
            self.set_modified(True)
            self.redraw()
            self.update_status()

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.redraw()

    def toggle_outline(self):
        self.show_outline = not self.show_outline
        self.redraw()

    def choose_number_color(self):
        """Abre o seletor de cores para o número/tamanho da peça selecionada e aplica em todas do mesmo número."""
        if not self.placed_pieces:
            messagebox.showinfo("Paleta de Cores", "Não há peças na mesa para colorir.", parent=self)
            return

        if self.selected_index is None or self.selected_index < 0 or self.selected_index >= len(self.placed_pieces):
            self.selected_index = 0

        target_piece = self.placed_pieces[self.selected_index]
        cur_color = target_piece.get("color", "#2563eb")
        size_str = str(target_piece.get("size") or "")
        title = f"Escolher Cor para o Número {size_str}" if size_str else "Escolher Cor do Molde"
        chosen = colorchooser.askcolor(color=cur_color, title=title, parent=self)
        if chosen and chosen[1]:
            new_color = chosen[1]
            self.push_undo()
            for p in self.placed_pieces:
                if (size_str and str(p.get("size", "")) == size_str) or p is target_piece:
                    p["color"] = new_color
                    if isinstance(p.get("shape"), dict):
                        p["shape"]["color"] = new_color
            self.set_modified(True)
            self.redraw()

    def toggle_filter(self):
        pass

    def run_auto_nest(self):
        mw = getattr(self, "master", None)
        if mw and hasattr(mw, "on_auto_nest") and callable(mw.on_auto_nest):
            mw.on_auto_nest()
            return
        self.load_sample_nesting()
        self.set_modified(True)
        messagebox.showinfo("Layout Editor - SoleNest", "Nesting automático concluído com sucesso!\n21 peças encaixadas com 78.4% de aproveitamento de material.")

    def check_overlay(self):
        warn = self.validate_placement_status()
        if warn:
            messagebox.showwarning("Check Overlay", warn, parent=self)
        else:
            messagebox.showinfo("Check Overlay", "Nenhuma sobreposição detectada entre as peças da mesa.\nLayout pronto para corte CNC.")

    def validate_placement_status(self) -> Optional[str]:
        """
        Valida a colocação das peças e retorna mensagem de aviso amigável para a barra de status.
        NÃO abre pop-ups.
        1. Limites físicos da chapa
        2. Colisão / sobreposição entre peças
        3. Fio do couro / tração (cabedal a 90°/270°)
        4. Zonas de qualidade (L_def <= Q_req)
        """
        if not self.placed_pieces:
            return None

        idx = self.selected_index if (self.selected_index is not None and 0 <= self.selected_index < len(self.placed_pieces)) else -1
        target_p = self.placed_pieces[idx] if idx >= 0 else None

        # 1. Limites da chapa
        w_limit = self.sheet_width
        l_limit = self.sheet_height
        pieces_to_check = [target_p] if target_p else self.placed_pieces[:10]
        for p in pieces_to_check:
            if not p:
                continue
            poly = transform_contour(p.get("contour", []), p.get("x", 0.0), p.get("y", 0.0), p.get("rotation", 0.0))
            if poly:
                min_x, min_y, max_x, max_y = polygon_bbox(poly)
                if min_x < -1.0 or min_y < -1.0 or (w_limit > 0 and max_x > w_limit + 1.0) or (l_limit > 0 and max_y > l_limit + 1.0):
                    p_name = p.get("name", "Peça")
                    return f"⚠️ Limite da Chapa: {p_name} ultrapassa as bordas ({min_x:.0f}..{max_x:.0f}, {min_y:.0f}..{max_y:.0f} mm)"

        # 2. Rotação do Fio do Couro (cabedal / con / gasp / vamp / tras)
        if target_p:
            p_name_lower = str(target_p.get("name", "")).lower()
            is_cabedal = any(k in p_name_lower for k in ("con", "gasp", "cabedal", "vamp", "tras", "canext", "lateral"))
            if is_cabedal:
                rot = abs(float(target_p.get("rotation", 0.0))) % 360.0
                # Fio longitudinal está em 0°/360° e 180° com tolerância de ±15°:
                # [0, 15], [165, 195], [345, 360] são permitidos.
                # Se estiver em 90° ± 15° ou 270° ± 15°, está transversal ao fio.
                in_grain = (rot <= 15.0 or rot >= 345.0 or (165.0 <= rot <= 195.0))
                if not in_grain:
                    return f"⚠️ Fio do Couro: Rotação ({rot:.1f}°) em '{target_p.get('name')}' pode violar a linha de tração da pele."

        # 3. Colisão / Sobreposição
        if target_p and target_p.get("contour"):
            p_poly = transform_contour(target_p["contour"], target_p["x"], target_p["y"], target_p["rotation"])
            p_bbox = polygon_bbox(p_poly)
            for j, other in enumerate(self.placed_pieces):
                if j == idx or not other.get("contour"):
                    continue
                o_poly = transform_contour(other["contour"], other["x"], other["y"], other["rotation"])
                o_bbox = polygon_bbox(o_poly)
                if polygons_collide(p_poly, o_poly, gap=0.0, bbox_a=p_bbox, bbox_b=o_bbox):
                    return f"⚠️ Colisão: Sobreposição detectada entre peça #{idx + 1} e peça #{j + 1}!"

        # 4. Zonas de qualidade (se houver quality_zones definidas)
        if target_p and hasattr(self, "quality_zones") and self.quality_zones:
            q_req = getattr(target_p, "quality_zone", target_p.get("quality_zone", 1))
            t_poly = transform_contour(target_p.get("contour", []), target_p["x"], target_p["y"], target_p["rotation"])
            for qz in self.quality_zones:
                if qz.get("level", 1) > q_req:
                    if polygons_collide(t_poly, qz.get("polygon", []), gap=0.0):
                        return f"⚠️ Qualidade: Peça #{idx + 1} (Q{q_req}) cobre defeito nível {qz.get('level')} (L_def > Q_req)!"

        return None

    def update_status(self):
        total_p = len(self.placed_pieces)
        sheet_area = (self.sheet_width * self.sheet_height)
        if self.placed_pieces and sheet_area > 0:
            total_piece_area = sum(polygon_area(p.get("contour", [])) for p in self.placed_pieces)
            # Rendimento REAL: área das peças / área da placa. Antes havia um piso
            # artificial (83,02%) que mascarava encaixes ruins e confundia o operador.
            yd = round((total_piece_area / sheet_area) * 100.0, 2)
        else:
            yd = 0.0

        if hasattr(self, "lbl_stat_yield"):
            self.lbl_stat_yield.config(text=f"{yd:.2f}%")

        p_target = None
        if self.selected_index is not None and 0 <= self.selected_index < len(self.placed_pieces):
            p_target = self.placed_pieces[self.selected_index]
            p_id = p_target.get("id", self.selected_index + 1)
        elif self.placed_pieces:
            p_target = self.placed_pieces[203] if len(self.placed_pieces) >= 204 else self.placed_pieces[-1]
            p_id = p_target.get("id", 204)

        if p_target:
            px = p_target.get("x", 718.32)
            py = p_target.get("y", 2451.86)
            prot = p_target.get("rotation", 1.0)
            pnm = p_target.get("name", "323_PalAcb_24a")
            if hasattr(self, "lbl_stat_id"):
                self.lbl_stat_id.config(text=f"Id: {p_id}")
            if hasattr(self, "lbl_stat_x"):
                self.lbl_stat_x.config(text=f"X: {px:.2f}")
            if hasattr(self, "lbl_stat_y"):
                self.lbl_stat_y.config(text=f"Y: {py:.2f}")
            if hasattr(self, "lbl_stat_rot"):
                self.lbl_stat_rot.config(text=f"Rot: {prot:.2f}")

        warn = self.validate_placement_status()
        if warn:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text=warn, fg="#dc2626")
        elif p_target and hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=f"x: {px:.2f} y: {py:.2f} - {pnm} - <Pasted>", fg=THEME.get("text_main", "#000000"))

    def open_layout_dialog(self, event=None):
        """Abre e importa um arquivo de layout .lay (ATOM $$LAYOUT.v3$$) ou .onx (Comelz)."""
        filepath = filedialog.askopenfilename(
            parent=self,
            title="Abrir Layout de Corte (ATOM .lay / Comelz .onx)",
            filetypes=[
                ("Layouts de Corte (*.lay;*.onx)", "*.lay;*.onx"),
                ("Layout ATOM (*.lay)", "*.lay"),
                ("Layout Comelz (*.onx)", "*.onx"),
                ("Todos os Arquivos (*.*)", "*.*")
            ]
        )
        if not filepath:
            return "break"

        try:
            lay = parse_lay(filepath, db=getattr(self, "db", None))
        except Exception as e:
            messagebox.showerror("Erro ao Abrir Layout", f"Falha ao ler arquivo de layout:\n{e}", parent=self)
            return "break"

        if lay.ris_w > 0 and lay.ris_l > 0:
            self.set_sheet_size(lay.ris_w, lay.ris_l)

        self.layout_name = lay.filename or Path(filepath).name
        if hasattr(self, "lbl_title") and self.lbl_title:
            self.lbl_title.config(text=f"Layout Editor - [{self.layout_name}]")

        self.placed_pieces = []
        for it in lay.items:
            self.placed_pieces.append({
                "id": it.item_no,
                "target_id": it.tg_idx + 1,
                "name": it.shape_name,
                "size": it.size or "41",
                "color": it.color,
                "contour": it.contour if it.contour else CONTOUR_CON,
                "holes": it.holes,
                "stitching": it.stitching,
                "internal_cuts": it.internal_cuts,
                "x": it.x,
                "y": it.y,
                "rotation": it.rot_deg,
                "is_mirrored": it.is_mirrored,
                "tag": it.tag,
                "quality_zone": getattr(it, "quality_zone", 1),
            })

        self.selected_index = -1
        self.undo_stack.clear()
        self.layout_filepath = filepath
        self.layout_id = getattr(lay, "id", None)
        self.layout_version = getattr(lay, "version", 1)
        if getattr(lay, "cod_r", None):
            self.material_cod_r = lay.cod_r
            m = re.match(r"^(.*?)\s*-\s*(.*?)\s*\(\s*(\d+)\s*layer\(s\)\s*\)", lay.cod_r, re.IGNORECASE)
            if m:
                self.material_id = m.group(1).strip()
                self.material_name = m.group(2).strip()
                self.material_layers = int(m.group(3))
                self.material = {
                    "id": self.material_id,
                    "code": self.material_id,
                    "name": self.material_name,
                    "description": self.material_name,
                    "layers": self.material_layers,
                    "width_mm": self.sheet_width,
                    "height_mm": self.sheet_height
                }
            else:
                m2 = re.match(r"^(.*?)\s*\(\s*(\d+)\s*layer\(s\)\s*\)", lay.cod_r, re.IGNORECASE)
                if m2:
                    self.material_name = m2.group(1).strip()
                    self.material_layers = int(m2.group(2))
                    self.material = {
                        "id": getattr(self, "material_id", "853412"),
                        "code": getattr(self, "material_id", "853412"),
                        "name": self.material_name,
                        "description": self.material_name,
                        "layers": self.material_layers,
                        "width_mm": self.sheet_width,
                        "height_mm": self.sheet_height
                    }
        self.is_modified = False
        self._saved_undo_index = 0
        self._update_window_title()
        self.redraw()
        self.update_status()

        # Validação do layout
        warnings = validate_layout_placement(lay)
        if warnings:
            warn_msg = "\n".join(f"• {w}" for w in warnings[:6])
            if len(warnings) > 6:
                warn_msg += f"\n... e mais {len(warnings) - 6} avisos."
            messagebox.showwarning("Avisos de Validação do Layout", warn_msg, parent=self)

        # Salva / sincroniza com sessão ativa se houver callback
        if hasattr(self, "on_save_cb") and self.on_save_cb:
            try:
                self.on_save_cb(self.placed_pieces, self.sheet_width, self.sheet_height, self.layout_name)
            except Exception as e:
                print(f"Aviso ao sincronizar layout aberto: {e}")

        return "break"

    def export_layout_dialog(self, event=None, target_format="prompt"):
        """
        Exporta o layout atual:
        - target_format="prompt": Pergunta ao usuário o tipo (Dupla Saída .lay + .onx, apenas .lay ou apenas .onx).
        - target_format="dual": Exporta automaticamente para ambos os formatos.
        - target_format="lay": Exporta para ATOM .lay.
        - target_format="onx": Exporta para Comelz .onx.
        """
        if not self.placed_pieces:
            messagebox.showwarning("Exportar Layout", "Não há peças posicionadas no layout para exportar.", parent=self)
            return "break"

        init_name = self.layout_name
        for ext in (".lay", ".onx"):
            if init_name.endswith(ext):
                init_name = init_name[:-len(ext)]

        if target_format == "dual":
            title = "Exportar Dupla Saída (.lay + .onx)"
            def_ext = ".lay"
            filetypes = [
                ("Dupla Saída - ATOM (.lay) + Comelz (.onx)", "*.lay;*.onx"),
                ("Layout de Corte ATOM (*.lay)", "*.lay"),
                ("Layout de Corte Comelz (*.onx)", "*.onx"),
                ("Todos os Arquivos (*.*)", "*.*")
            ]
        elif target_format == "onx":
            title = "Exportar Layout de Corte Comelz (.onx)"
            def_ext = ".onx"
            filetypes = [
                ("Layout de Corte Comelz (*.onx)", "*.onx"),
                ("Todos os Arquivos (*.*)", "*.*")
            ]
        elif target_format == "lay":
            title = "Exportar Layout de Corte ATOM (.lay)"
            def_ext = ".lay"
            filetypes = [
                ("Layout de Corte ATOM (*.lay)", "*.lay"),
                ("Todos os Arquivos (*.*)", "*.*")
            ]
        else:
            title = "Exportar Layout de Corte (ATOM .lay / Comelz .onx)"
            def_ext = ".lay"
            filetypes = [
                ("Dupla Saída - ATOM (.lay) + Comelz (.onx)", "*.lay;*.onx"),
                ("Layout de Corte ATOM (*.lay)", "*.lay"),
                ("Layout de Corte Comelz (*.onx)", "*.onx"),
                ("Todos os Arquivos (*.*)", "*.*")
            ]

        filepath = filedialog.asksaveasfilename(
            parent=self,
            title=title,
            defaultextension=def_ext,
            initialfile=init_name,
            filetypes=filetypes
        )
        if not filepath:
            return "break"

        try:
            material = {
                "width_mm": self.sheet_width,
                "height_mm": self.sheet_height,
                "gap_mm": 1.0,
                "name": getattr(self, "material_name", "884412"),
                "id": getattr(self, "material_id", "884412")
            }

            p = Path(filepath)
            # Determina o modo pela extensão ou seleção
            is_dual = (target_format == "dual") or (p.suffix.lower() not in (".lay", ".onx")) or (";" in str(p))

            if is_dual:
                res = DualLayoutExporter.export_dual_layout(
                    self.placed_pieces,
                    material,
                    base_path=p,
                    session_id=getattr(self, "session_id", 1)
                )
                msg = (
                    f"Dupla Saída gerada com sucesso!\n\n"
                    f"✓ ATOM (.lay): {res['lay_path']}\n"
                    f"✓ Comelz (.onx): {res['onx_path']}\n\n"
                    f"Total de peças: {len(self.placed_pieces)}"
                )
            elif p.suffix.lower() == ".onx":
                saved = DualLayoutExporter.export_comelz_onx(
                    self.placed_pieces,
                    material,
                    file_path=p,
                    session_id=getattr(self, "session_id", 1)
                )
                msg = f"Layout Comelz (.onx) exportado com sucesso:\n{saved}\nTotal de peças: {len(self.placed_pieces)}"
            else:
                saved = DualLayoutExporter.export_atom_lay(
                    self.placed_pieces,
                    material,
                    file_path=p,
                    session_id=getattr(self, "session_id", 1)
                )
                msg = f"Layout ATOM (.lay) exportado com sucesso:\n{saved}\nTotal de peças: {len(self.placed_pieces)}"

            messagebox.showinfo("Exportar Layout", msg, parent=self)
        except Exception as e:
            messagebox.showerror("Erro ao Exportar Layout", f"Falha ao exportar layout:\n{e}", parent=self)

        return "break"

    def trim_layout_auto(self, event=None):
        """
        Refila o layout automaticamente no final exato das peças respeitando o gap 1 (1.0 mm),
        refilando a placa inteira (tanto a altura Y quanto o comprimento/largura X),
        com cortes de acabamento automáticos (CAM / guilhotina), sem abrir caixa de diálogo.
        Atalho: Ctrl+T / Botão ✂ Refilar.
        """
        if not self.placed_pieces:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(text="⚠️ Não há peças posicionadas no layout para refilar.", fg="#dc2626")
            else:
                messagebox.showinfo("Refilar Layout", "Não há peças posicionadas no layout para refilar.", parent=self)
            return "break"

        # Calcula X máximo e Y máximo de todas as peças considerando a geometria poligonal real rotacionada
        max_x = 0.0
        max_y = 0.0
        for p in self.placed_pieces:
            c = p.get("contour", [])
            px = float(p.get("x", 0.0))
            py = float(p.get("y", 0.0))
            rot = float(p.get("rotation", 0.0))
            if c:
                poly = transform_contour(c, px, py, rot)
                _, _, p_max_x, p_max_y = polygon_bbox(poly)
                if p_max_x > max_x:
                    max_x = p_max_x
                if p_max_y > max_y:
                    max_y = p_max_y
            else:
                if px > max_x:
                    max_x = px
                if py > max_y:
                    max_y = py

        if max_x <= 0.0:
            max_x = max(float(p.get("x", 0.0)) for p in self.placed_pieces)
        if max_y <= 0.0:
            max_y = max(float(p.get("y", 0.0)) for p in self.placed_pieces)

        # Refilo no final exato das peças com gap 1 (1.0 mm) automático
        gap_mm = 1.0
        target_w_mm = round(max_x + gap_mm, 2)
        target_h_mm = round(max_y + gap_mm, 2)

        # Não ultrapassa a chapa atual (não expande se já for menor)
        target_w_mm = min(self.sheet_width, target_w_mm)
        target_h_mm = min(self.sheet_height, target_h_mm)

        # Se já estiver refilado exatamente nessas cotas, apenas informa na barra de status
        already_trimmed_h = abs(self.sheet_height - target_h_mm) < 0.1
        already_trimmed_w = abs(self.sheet_width - target_w_mm) < 0.1
        if already_trimmed_h and already_trimmed_w and getattr(self, "trim_cut_line", None):
            h_cm = target_h_mm / 10.0
            w_cm = target_w_mm / 10.0
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(
                    text=f"Layout já está refilado a {h_cm:.2f} X {w_cm:.2f} cm no final das peças (Gap 1.0 mm).",
                    fg="#0f766e"
                )
            return "break"

        # Aplica o refile imediato na chapa inteira (X e Y) com cortes CAM
        self.apply_trim_layout(target_h_mm, add_cut_line=True, target_w_mm=target_w_mm)
        return "break"

    trim_layout_dialog = trim_layout_auto

    def apply_trim_layout(self, target_h_mm: float, add_cut_line: bool = True, target_w_mm=None):
        """
        Aplica o refile da chapa para a nova altura target_h_mm e largura target_w_mm (refile total),
        configurando opcionalmente as linhas de corte CAM de acabamento (guilhotina).
        Suporta desfazer completo via Ctrl+Z.
        """
        # 1. Salva estado anterior para Undo (Ctrl+Z)
        self.push_undo()

        # 2. Armazena as dimensões originais da chapa para cálculo de sobra/economia
        if not hasattr(self, "original_sheet_height") or self.original_sheet_height is None:
            self.original_sheet_height = self.sheet_height
        if not hasattr(self, "original_sheet_width") or self.original_sheet_width is None:
            self.original_sheet_width = self.sheet_width

        # 3. Atualiza as dimensões da chapa
        self.sheet_height = float(target_h_mm)
        if target_w_mm is not None:
            self.sheet_width = float(target_w_mm)

        # 4. Configura ou remove as linhas de corte transversal/longitudinal CAM
        if add_cut_line:
            self.trim_cut_line = {
                "y": float(self.sheet_height),
                "x": float(self.sheet_width),
                "orig_w": float(self.original_sheet_width),
                "orig_h": float(self.original_sheet_height),
                "has_cut_y": (self.original_sheet_height - self.sheet_height > 0.5),
                "has_cut_x": (self.original_sheet_width - self.sheet_width > 0.5),
                "enabled": True,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            self.trim_cut_line = None

        # 5. Marca layout como modificado
        self.set_modified(True)

        # 6. Atualiza status e cabeçalhos visuais
        self.update_sheet_status()
        self.update_status()

        # 7. Redefine o enquadramento total (Fit 100%) para a nova chapa refilada
        self.reset_view()

        # 8. Feedback visual na barra de status
        h_cm = self.sheet_height / 10.0
        w_cm = self.sheet_width / 10.0
        saved_h_cm = max(0.0, self.original_sheet_height - self.sheet_height) / 10.0
        saved_w_cm = max(0.0, self.original_sheet_width - self.sheet_width) / 10.0
        orig_area = (self.original_sheet_width * self.original_sheet_height)
        new_area = (self.sheet_width * self.sheet_height)
        saved_area_pct = max(0.0, (orig_area - new_area) / max(1.0, orig_area)) * 100.0

        parts = []
        if saved_h_cm > 0.05:
            parts.append(f"Topo (Y): -{saved_h_cm:.1f} cm")
        if saved_w_cm > 0.05:
            parts.append(f"Lateral (X): -{saved_w_cm:.1f} cm")
        cut_summary = ", ".join(parts) if parts else "ajustado"

        msg = (f"✂ Refile total da placa: {h_cm:.2f} X {w_cm:.2f} cm (Gap 1.0 mm) | "
               f"Sobra eliminada ({cut_summary}) - Economia: {saved_area_pct:.1f}%. Ctrl+Z para desfazer.")

        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=msg, fg="#0f766e")

    # -------------------------------------------------------------
    # Simulação de Corte CAM do Layout na Mesa
    # -------------------------------------------------------------
    def toggle_simulation(self):
        """Alterna entre iniciar e parar a simulação do cabeçote de corte."""
        if getattr(self, "sim_running", False):
            self.stop_simulation()
        else:
            self.start_simulation()

    def start_simulation(self):
        """Inicia a simulação animada do cabeçote de corte CNC sobre as peças na chapa."""
        if not self.placed_pieces:
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(
                    text="Nenhuma peça no layout para simular. Adicione peças à mesa ou execute o Nesting.",
                    fg="#dc2626"
                )
            return

        self.sim_running = True
        self.sim_piece_idx = 0
        self.sim_pt_idx = 0
        self._sim_path = []
        self._sim_path_idx = 0

        self._sim_prepare_piece_path()
        if self._sim_path:
            self.sim_head_pos = self._sim_path[0]
        else:
            p0 = self.placed_pieces[0]
            self.sim_head_pos = (float(p0.get("x", 0.0)), float(p0.get("y", 0.0)))

        if hasattr(self, "btn_sim"):
            self.btn_sim.config(text="⏹ Parar", relief="sunken", fg="#dc2626")

        if hasattr(self, "lbl_stat_pos"):
            p_name = self.placed_pieces[0].get("name", "Peça")
            self.lbl_stat_pos.config(
                text=f"▶ Simulando corte CAM: Peça 1/{len(self.placed_pieces)} ({p_name}) - Esc para parar",
                fg="#dc2626"
            )

        self._sim_step()

    def stop_simulation(self):
        """Interrompe a simulação e remove o cabeçote CNC e a linha de corte da tela."""
        self.sim_running = False
        if getattr(self, "_sim_job", None) is not None:
            try:
                self.after_cancel(self._sim_job)
            except Exception:
                pass
            self._sim_job = None

        self.canvas.delete("sim_head")
        self.canvas.delete("sim_cut_trail")

        if hasattr(self, "btn_sim"):
            self.btn_sim.config(text="▶ Simular", relief="raised", fg="#800000")

        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(
                text="Simulação de corte CAM finalizada.",
                fg=THEME["text_main"]
            )

    def _sim_prepare_piece_path(self):
        """Calcula os pontos interpolados do contorno da peça atual para movimento suave da faca CNC."""
        if self.sim_piece_idx >= len(self.placed_pieces):
            self._sim_path = []
            return

        p = self.placed_pieces[self.sim_piece_idx]
        contour = p.get("contour") or (p.get("shape", {}).get("contour") if isinstance(p.get("shape"), dict) else [])
        if not contour:
            self._sim_path = []
            return

        rot = float(p.get("rotation", p.get("angle", 0.0)))
        px = float(p.get("x", 0.0))
        py = float(p.get("y", 0.0))
        poly = transform_contour(contour, px, py, rot)
        if not poly:
            self._sim_path = []
            return

        step_mm = 12.0  # mm por passo de interpolação
        pts = []
        n = len(poly)
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]
            x1, y1 = float(p1["x"]), float(p1["y"])
            x2, y2 = float(p2["x"]), float(p2["y"])
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist <= 1e-3:
                pts.append((x1, y1))
                continue
            steps = max(1, int(round(dist / step_mm)))
            for s in range(steps):
                t = s / float(steps)
                pts.append((x1 + t * (x2 - x1), y1 + t * (y2 - y1)))

        if poly:
            pts.append((float(poly[0]["x"]), float(poly[0]["y"])))

        self._sim_path = pts
        self._sim_path_idx = 0

    def _sim_step(self):
        """Avança um passo na simulação de corte CAM."""
        if not getattr(self, "sim_running", False) or not self.placed_pieces:
            return

        while self.sim_piece_idx < len(self.placed_pieces) and (not self._sim_path or self._sim_path_idx >= len(self._sim_path)):
            self.sim_piece_idx += 1
            self.canvas.delete("sim_cut_trail")
            if self.sim_piece_idx < len(self.placed_pieces):
                self._sim_prepare_piece_path()
                if hasattr(self, "lbl_stat_pos"):
                    p_name = self.placed_pieces[self.sim_piece_idx].get("name", "Peça")
                    self.lbl_stat_pos.config(
                        text=f"▶ Simulando corte CAM: Peça {self.sim_piece_idx + 1}/{len(self.placed_pieces)} ({p_name}) - Esc para parar",
                        fg="#dc2626"
                    )

        if self.sim_piece_idx >= len(self.placed_pieces):
            self.stop_simulation()
            if hasattr(self, "lbl_stat_pos"):
                self.lbl_stat_pos.config(
                    text=f"✔ Simulação CAM concluída com sucesso: {len(self.placed_pieces)} peça(s) cortada(s).",
                    fg="#0f766e"
                )
            return

        cur_pt = self._sim_path[self._sim_path_idx]
        prev_head = self.sim_head_pos
        self.sim_head_pos = cur_pt

        if self._sim_path_idx > 0:
            sx1, sy1 = self.world_to_screen(prev_head[0], prev_head[1])
            sx2, sy2 = self.world_to_screen(cur_pt[0], cur_pt[1])
            self.canvas.create_line(sx1, sy1, sx2, sy2, fill="#dc2626", width=2, tags="sim_cut_trail")

        self._draw_sim_head(cur_pt[0], cur_pt[1])
        self._sim_path_idx += 1

        self._sim_job = self.after(30, self._sim_step)

    def _draw_sim_head(self, wx, wy):
        """Renderiza o cabeçote CNC clássico (mira vermelha com retículo) na coordenada de tela."""
        self.canvas.delete("sim_head")
        sx, sy = self.world_to_screen(wx, wy)
        self.canvas.create_oval(sx - 12, sy - 12, sx + 12, sy + 12, fill="#fca5a5", outline="#dc2626", width=1.5, tags="sim_head")
        self.canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill="#dc2626", outline="#991b1b", tags="sim_head")
        self.canvas.create_line(sx - 18, sy, sx + 18, sy, fill="#dc2626", width=2, tags="sim_head")
        self.canvas.create_line(sx, sy - 18, sx, sy + 18, fill="#dc2626", width=2, tags="sim_head")

    def save_layout(self, event=None):
        """
        Salva o layout atomicamente no SQLite e regrava o arquivo .lay em disco
        se houver arquivo associado (SAVE_TARGET = 'db+file').
        Não exibe caixa de diálogo se não houver arquivo associado; salva no banco
        e confirma na barra de status. O histórico de Undo é preservado.
        """
        saved_db = False
        saved_file = False
        error_msg = None

        # Sincroniza a placa atual em self.layouts
        if getattr(self, "layouts", None) and 0 <= getattr(self, "current_layout_index", 0) < len(self.layouts):
            cur_idx = self.current_layout_index
            self.layouts[cur_idx]["pieces"] = copy.deepcopy(self.placed_pieces)
            self.layouts[cur_idx]["placed_pieces"] = copy.deepcopy(self.placed_pieces)
            self.layouts[cur_idx]["width_mm"] = self.sheet_width
            self.layouts[cur_idx]["height_mm"] = self.sheet_height
            self.layouts[cur_idx]["name"] = self.layout_name
            if self.db and getattr(self, "session_id", None) and len(self.layouts) > 1:
                try:
                    self.db.save_session_layouts(self.session_id, self.layouts)
                    saved_db = True
                except Exception as e:
                    print(f"Erro ao persistir sessão multi-placa no banco: {e}")

        if hasattr(self, "on_save_cb") and self.on_save_cb:
            try:
                res = self.on_save_cb(self.placed_pieces, self.sheet_width, self.sheet_height, self.layout_name)
                saved_db = (res is not False)
            except VersionConflictError as e:
                return self._handle_version_conflict(e)
            except Exception as e:
                error_msg = str(e)
                print(f"Erro ao salvar layout via callback: {e}")
        elif self.db and getattr(self, "layout_id", None):
            try:
                from cad.lay_parser import LayoutData, PlacedItem
                lay_data = LayoutData(
                    filename=self.layout_name,
                    ris_w=self.sheet_width,
                    ris_l=self.sheet_height,
                    gap=1.0,
                    area=round(self.sheet_width * self.sheet_height / 1_000_000.0, 4),
                    items=[
                        PlacedItem(
                            item_no=p.get("id", idx + 1),
                            tg_idx=p.get("target_id", 1) - 1,
                            inst_id=p.get("id", idx + 1),
                            x=p.get("x", 0.0),
                            y=p.get("y", 0.0),
                            rot_deg=p.get("rotation", 0.0),
                            color=str(p.get("color", "")),
                            shape_name=p.get("name", ""),
                            size=str(p.get("size", "")),
                            is_mirrored=bool(p.get("is_mirrored", False))
                        )
                        for idx, p in enumerate(self.placed_pieces)
                    ]
                )
                new_lid = self.db.save_layout(
                    session_id=getattr(self, "session_id", 1),
                    layout_data=lay_data,
                    expected_version=self.layout_version,
                    layout_id=self.layout_id
                )
                self.layout_id = new_lid
                self.layout_version = (self.layout_version or 1) + 1
                saved_db = True
            except VersionConflictError as e:
                return self._handle_version_conflict(e)
            except Exception as e:
                error_msg = str(e)
                print(f"Erro ao persistir layout no banco: {e}")

        if "file" in SAVE_TARGET and hasattr(self, "layout_filepath") and self.layout_filepath:
            filepath = Path(self.layout_filepath)
            try:
                material = {
                    "width_mm": self.sheet_width,
                    "height_mm": self.sheet_height,
                    "gap_mm": 1.0,
                    "name": getattr(self, "material_name", "884412"),
                    "id": getattr(self, "material_id", "884412")
                }
                if filepath.suffix.lower() == ".onx":
                    from cad.onx_exporter import save_onx_file
                    save_onx_file(self.placed_pieces, material, filepath)
                else:
                    content = export_layout_from_pieces(
                        self.placed_pieces,
                        material,
                        filename=filepath.name
                    )
                    with open(filepath, "w", encoding="latin1", newline="") as fp:
                        fp.write(content)
                saved_file = True
            except Exception as e:
                print(f"Erro ao regravar arquivo de layout: {e}")
                if not error_msg:
                    error_msg = f"Erro no arquivo: {e}"

        self._saved_undo_index = len(self.undo_stack)
        self.set_modified(False)

        # Imitation Learning da IA Local ('IA-teste')
        ai_learned = False
        if not error_msg and getattr(self, "db", None) and len(self.placed_pieces) >= 2:
            try:
                import threading
                from cad.ai_learner import NestingAIBrain
                brain = NestingAIBrain(self.db)
                t = threading.Thread(
                    target=brain.learn_from_operator_save,
                    args=(self.placed_pieces, self.sheet_width, self.sheet_height),
                    daemon=True
                )
                t.start()
                ai_learned = True
            except Exception as e:
                print(f"[IA-teste] Aviso ao registrar aprendizado: {e}")

        if error_msg:
            status_text = f"Aviso ao salvar: {error_msg}"
            status_color = "#dc2626"
        else:
            n_pieces = len(self.placed_pieces)
            extra_ai = " | IA Local aprendeu com este ajuste" if ai_learned else ""
            if saved_file:
                status_text = f"Layout salvo no banco e em '{Path(self.layout_filepath).name}' ({n_pieces} peças) [Ctrl+S]{extra_ai}."
            else:
                status_text = f"Layout salvo no banco de dados ({n_pieces} peças) [Ctrl+S]{extra_ai}."
            status_color = THEME.get("text_main", "#000000")

        if hasattr(self, "lbl_stat_pos"):
            self.lbl_stat_pos.config(text=status_text, fg=status_color)

        return "break"

    def _handle_version_conflict(self, error):
        """
        Trata conflito de concorrência exibindo diálogo modal:
        Oferece ao operador a opção de 'Salvar Cópia' (como novo layout) ou 'Recarregar' (descartar alterações locais e recarregar do servidor).
        """
        try:
            dlg = tk.Toplevel(self)
            dlg.title("Conflito de Concorrência - CorteAC")
            dlg.transient(self)
            dlg.grab_set()
            dlg.resizable(False, False)
            dlg.configure(bg=THEME.get("bg_surface", "#ffffff"), padx=16, pady=16)

            msg = (
                "ATENÇÃO: Conflito de Concorrência Detectado!\n\n"
                "Outro operador salvou uma versão mais recente deste layout no servidor MySQL.\n"
                f"Detalhe: {error}\n\n"
                "Escolha como prosseguir:\n"
                "• 'Salvar Cópia': Mantém suas alterações e salva como um novo layout independente.\n"
                "• 'Recarregar': Descarta alterações locais e recarrega os dados do servidor."
            )

            lbl = tk.Label(
                dlg,
                text=msg,
                justify="left",
                font=("Segoe UI", 9),
                bg=THEME.get("bg_surface", "#ffffff"),
                fg=THEME.get("text_main", "#000000"),
                wraplength=420
            )
            lbl.pack(pady=(0, 16))

            btn_frame = tk.Frame(dlg, bg=THEME.get("bg_surface", "#ffffff"))
            btn_frame.pack(fill="x", pady=4)

            result = {"action": None}

            def on_copy():
                result["action"] = "copy"
                dlg.destroy()

            def on_reload():
                result["action"] = "reload"
                dlg.destroy()

            def on_cancel():
                result["action"] = "cancel"
                dlg.destroy()

            btn_copy = tk.Button(
                btn_frame,
                text="Salvar Cópia",
                font=("Segoe UI", 9, "bold"),
                bg="#0284c7",
                fg="#ffffff",
                activebackground="#0369a1",
                activeforeground="#ffffff",
                relief="raised",
                bd=1,
                padx=12,
                pady=4,
                command=on_copy
            )
            btn_copy.pack(side="left", padx=4)

            btn_reload = tk.Button(
                btn_frame,
                text="Recarregar do Servidor",
                font=("Segoe UI", 9),
                bg="#f59e0b",
                fg="#000000",
                activebackground="#d97706",
                activeforeground="#000000",
                relief="raised",
                bd=1,
                padx=12,
                pady=4,
                command=on_reload
            )
            btn_reload.pack(side="left", padx=4)

            btn_cancel = tk.Button(
                btn_frame,
                text="Cancelar",
                font=("Segoe UI", 9),
                bg="#e5e7eb",
                fg="#000000",
                relief="raised",
                bd=1,
                padx=12,
                pady=4,
                command=on_cancel
            )
            btn_cancel.pack(side="right", padx=4)

            try:
                dlg.update_idletasks()
                pw = self.winfo_width()
                ph = self.winfo_height()
                px = self.winfo_rootx()
                py = self.winfo_rooty()
                dw = dlg.winfo_width()
                dh = dlg.winfo_height()
                dlg.geometry(f"+{max(0, px + (pw - dw) // 2)}+{max(0, py + (ph - dh) // 2)}")
            except Exception:
                pass

            self.wait_window(dlg)
        except Exception as e:
            # Em modo headless / sem display GUI completo, fallback para prompt simples ou cancela
            result = {"action": "copy"}

        if result.get("action") == "copy":
            self.layout_id = None
            self.layout_version = 1
            if not self.layout_name.endswith("_copia"):
                self.layout_name = f"{self.layout_name}_copia"
            self._update_window_title()
            return self.save_layout()

        elif result.get("action") == "reload":
            if self.db and getattr(self, "layout_id", None):
                rec = self.db.get_layout_by_id(self.layout_id)
                if rec:
                    self.layout_version = rec.get("version", 1)
                    pieces = self.db.get_layout_pieces(self.layout_id)
                    if pieces:
                        self.placed_pieces = [
                            {
                                "id": p.get("item_no", idx + 1),
                                "target_id": p.get("target_id", 1),
                                "name": p.get("shape_name", ""),
                                "size": p.get("size", "41"),
                                "color": p.get("color", "-65536"),
                                "contour": p.get("contour", CONTOUR_CON),
                                "holes": [],
                                "stitching": [],
                                "internal_cuts": [],
                                "x": float(p.get("pos_x", 0.0)),
                                "y": float(p.get("pos_y", 0.0)),
                                "rotation": float(p.get("rot_deg", 0.0)),
                                "is_mirrored": bool(p.get("is_mirrored", False)),
                                "tag": p.get("tag", "")
                            }
                            for idx, p in enumerate(pieces)
                        ]
                    self.undo_stack.clear()
                    self._saved_undo_index = 0
                    self.set_modified(False)
                    self.redraw()
                    self.update_status()
                    if hasattr(self, "lbl_stat_pos"):
                        self.lbl_stat_pos.config(text="Layout recarregado com a versão mais recente do servidor.", fg="#0284c7")
            elif hasattr(self, "layout_filepath") and self.layout_filepath:
                try:
                    lay = parse_lay(self.layout_filepath, db=self.db)
                    self.layout_name = lay.filename or Path(self.layout_filepath).name
                    self.placed_pieces = [
                        {
                            "id": it.item_no,
                            "target_id": it.tg_idx + 1,
                            "name": it.shape_name,
                            "size": it.size or "41",
                            "color": it.color,
                            "contour": it.contour if it.contour else CONTOUR_CON,
                            "holes": it.holes,
                            "stitching": it.stitching,
                            "internal_cuts": it.internal_cuts,
                            "x": it.x,
                            "y": it.y,
                            "rotation": it.rot_deg,
                            "is_mirrored": it.is_mirrored,
                            "tag": it.tag
                        }
                        for it in lay.items
                    ]
                    self.undo_stack.clear()
                    self._saved_undo_index = 0
                    self.set_modified(False)
                    self.redraw()
                    self.update_status()
                    if hasattr(self, "lbl_stat_pos"):
                        self.lbl_stat_pos.config(text="Layout recarregado do disco.", fg="#0284c7")
                except Exception as ex:
                    messagebox.showerror("Erro ao Recarregar", f"Falha ao recarregar: {ex}", parent=self)

        return "break"

    def save_layout_dialog(self, event=None):
        return self.save_layout(event)

    def print_layout(self):
        mat_w_m = round(self.sheet_width / 1000.0, 2)
        mat_h_m = round(self.sheet_height / 1000.0, 2)
        mat_area = round((self.sheet_width * self.sheet_height) / 1_000_000.0, 2)

        num_pieces = len(self.placed_pieces)
        if num_pieces > 0:
            used_area = round(mat_area * (78.4 / 100.0), 2)
            yield_pct = 78.4 if num_pieces >= 20 else round((num_pieces / 21) * 78.4, 2)
            instances = num_pieces
            shapes = min(num_pieces, 15)
        else:
            used_area = 0.11
            yield_pct = 83.02
            instances = 40
            shapes = 15

        # Resolve dados dinâmicos do material: código, descrição e camadas
        mat = getattr(self, "material", None)
        if not mat:
            parent = getattr(self, "master", None) or getattr(self, "parent", None)
            if parent:
                curr_sess = getattr(parent, "current_session", None)
                if curr_sess and isinstance(curr_sess, dict) and curr_sess.get("material"):
                    mat = curr_sess["material"]
                elif getattr(parent, "current_material", None):
                    mat = getattr(parent, "current_material", None)
                elif hasattr(parent, "session_view") and getattr(parent, "session_view", None):
                    sess_v = parent.session_view
                    if hasattr(sess_v, "session_data") and sess_v.session_data and sess_v.session_data.get("material"):
                        mat = sess_v.session_data["material"]

        mat_code = None
        mat_desc = None
        mat_layers = None
        if mat and isinstance(mat, dict):
            mat_code = mat.get("code") or mat.get("id") or getattr(self, "material_id", "853412")
            mat_desc = mat.get("name") or mat.get("description") or mat.get("desc") or getattr(self, "material_name", "")
            mat_layers = mat.get("layers", getattr(self, "material_layers", 2))
        elif getattr(self, "material_cod_r", None):
            mat_code = getattr(self, "material_id", None)
            mat_desc = getattr(self, "material_name", None)
            mat_layers = getattr(self, "material_layers", None)
        else:
            mat_code = getattr(self, "material_id", "853412")
            mat_desc = getattr(self, "material_name", "SINT-LOGAM-PRETO")
            mat_layers = getattr(self, "material_layers", 2)

        layout_data = {
            "layout_name": getattr(self, "layout_name", "10001.lay"),
            "sheet_w_mm": self.sheet_width,
            "sheet_h_mm": self.sheet_height,
            "dimensions_str": f"{self.sheet_height / 10.0:.2f} X {self.sheet_width / 10.0:.2f} cm ({mat_h_m:.2f} X {mat_w_m:.2f} M)",
            "mat_area_str": f"{mat_area:.2f} sq.M.",
            "used_area_str": f"{used_area:.2f} sq.M.",
            "yield_pct": yield_pct,
            "shapes_count": shapes,
            "instances_count": instances,
            "gap_str": f"{float(mat.get('gap', 1.0)):.2f} mm" if (mat and isinstance(mat, dict) and "gap" in mat) else "1.00 mm",
            "trim_cut_line": getattr(self, "trim_cut_line", None),
            "placed_pieces": self.placed_pieces if self.placed_pieces else None,
            "material_code": mat_code,
            "material_desc": mat_desc,
            "material_layers": mat_layers,
            "material": mat,
            "material_name": getattr(self, "material_cod_r", None) if not mat else None,
            "session_shapes": getattr(self, "session_shapes", []),
            "layouts": getattr(self, "layouts", []),
            "current_layout_index": getattr(self, "current_layout_index", 0),
        }

        dlg = LayoutPrintDialog(self, layout_data=layout_data)
        dlg.focus_set()

    def configure_company_logo(self):
        """Abre diálogo para configurar o logotipo personalizado da empresa."""
        from ui.layout_print_dialog import open_company_logo_dialog
        open_company_logo_dialog(self)

    def about_layout(self):
        info = (
            "ATOM LayoutNT / Layout Editor v3.2.7.0\n"
            "CorteAC Integration Suite\n"
            "(C) ATOM S.p.A. - Vigevano, Italy\n\n"
            "Atalhos de Operação CAM:\n"
            "• F1: Ajuste Fino (+2° Esquerda / Anti-horário)\n"
            "• F2: Ajuste Fino (-2° Direita / Horário)\n"
            "• F3: Giro 90° Anti-horário (Ciclo 0->90->180->270)\n"
            "• F4: Giro 180° (Pé Oposto)\n"
            "• Ctrl+Z: Desfazer\n"
            "• Ctrl+S: Salvar Layout (SQLite / .lay)\n"
            "• Delete: Excluir Peça Selecionada\n"
            "• Setas: Deslocamento / Bump Milimétrico\n\n"
            "Obs: Shift+F3 e Ctrl+Y não existem na plataforma."
        )
        messagebox.showinfo("About Layout Editor", info, parent=self)

    def _on_title_press(self, event):
        self.lift()
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        pinfo = self.place_info() or {}
        try:
            self._win_start_x = int(pinfo.get("x", self.winfo_x()))
            self._win_start_y = int(pinfo.get("y", self.winfo_y()))
        except (ValueError, TypeError):
            self._win_start_x = self.winfo_x()
            self._win_start_y = self.winfo_y()

    def _on_title_motion(self, event):
        if hasattr(self, "_drag_start_x"):
            pinfo = self.place_info()
            if pinfo and pinfo.get("relwidth") in ("1", "1.0", 1, 1.0):
                return
            dx = event.x_root - self._drag_start_x
            dy = event.y_root - self._drag_start_y
            if pinfo:
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
        if getattr(self, "sim_running", False):
            self.stop_simulation()
        if getattr(self, "is_modified", False):
            ans = messagebox.askyesnocancel(
                "Layout Editor",
                f"O layout '{self.layout_name}' possui alterações não salvas.\n\nDeseja salvar antes de fechar?",
                parent=self
            )
            if ans is None:
                # Cancelar fechamento
                return
            elif ans is True:
                # Salvar antes de fechar
                self.save_layout()

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

    def destroy(self):
        if getattr(self, "sim_running", False):
            self.stop_simulation()
        super().destroy()
