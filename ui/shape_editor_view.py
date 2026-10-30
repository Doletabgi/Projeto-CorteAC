"""
JobManager 2000 (Python Edition)
Shape Editor (ShedNt.exe Replica)
CAD Shape Editor com suporte a edição de contornos, furos, vértices e cálculo de áreas.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import math
import copy
from pathlib import Path
from config import THEME
from cad.geometry import (
    polygon_area, polygon_perimeter, polygon_bbox,
    rotate_point, point_in_polygon
)
from cad.die_parser import parse_die_file, save_die_file

class ShapeEditorView(tk.Frame):
    def __init__(self, parent, shape_data=None, on_close=None, on_minimize=None, on_maximize=None, on_save=None, on_import_die=None, **kwargs):
        super().__init__(parent, bg=THEME["bg_surface"], relief="ridge", bd=2, **kwargs)
        self.on_close_cb = on_close
        self.on_minimize_cb = on_minimize
        self.on_maximize_cb = on_maximize
        self.on_save_cb = on_save
        self.on_import_die_cb = on_import_die

        # Dados do molde (cópia profunda para permitir cancelamento/reversão)
        self.original_shape = shape_data or self._default_shape()
        self.shape = copy.deepcopy(self.original_shape)

        # Estado da edição CAD
        self.tool_mode = "select"  # "select", "add_point", "add_hole", "rotate"
        self.selected_vertex_idx = -1
        self.selected_hole_idx = -1
        self.drag_target = None  # ("vertex", idx) ou ("hole", idx)
        self.is_panning = False
        self.last_mouse = (0, 0)
        self._pre_drag_state = None

        # Histórico de Desfazer / Reverter (Ctrl+Z)
        self.undo_stack = []
        self.redo_stack = []

        # Viewport CAD
        self.zoom = 1.8
        self.pan_x = 220.0
        self.pan_y = 180.0

        # Opções de visualização (réplica dos botões de bdyInterface.htm / ATOM ShedNt)
        self.show_contour = tk.BooleanVar(value=True)
        self.show_holes = tk.BooleanVar(value=True)
        self.show_vertices = tk.BooleanVar(value=True)
        self.show_indices = tk.BooleanVar(value=True)
        self.show_coords = tk.BooleanVar(value=False)
        self.show_grid = tk.BooleanVar(value=True)
        self.show_info_panel = tk.BooleanVar(value=True)
        self.var_show_stitching = tk.BooleanVar(value=True)
        self.show_stitching_enabled = self.var_show_stitching

        # Modo Seguro / Trava de Geometria (Padrão: Bloqueado)
        self.geometry_locked = tk.BooleanVar(value=True)
        self.btn_lock = None

        self._initial_fit_needed = True
        self._last_canvas_w = 0
        self._last_canvas_h = 0

        self.setup_ui()
        self._update_lock_ui()
        self.reset_view()

    def _default_shape(self):
        return {
            "id": 1,
            "name": "Gaspea_Nova",
            "article_id": 1,
            "color": "#2563eb",
            "contour": [
                {"x": 0, "y": 0},
                {"x": 180, "y": 0},
                {"x": 210, "y": 40},
                {"x": 195, "y": 110},
                {"x": 75, "y": 125},
                {"x": 10, "y": 80},
                {"x": 0, "y": 20}
            ],
            "holes": [
                {"x": 50, "y": 50, "r": 3.0},
                {"x": 130, "y": 50, "r": 3.0}
            ],
            "stitching": []
        }

    def load_shape(self, shape_data):
        """Carrega um novo molde no editor."""
        self.original_shape = copy.deepcopy(shape_data)
        self.shape = copy.deepcopy(shape_data)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._pre_drag_state = None
        self.selected_vertex_idx = -1
        self.selected_hole_idx = -1
        self._initial_fit_needed = True
        self.lbl_title.config(text=f"📐 Shape Editor - [{self.shape.get('name', 'Novo')}.die]")
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, self.shape.get("name", ""))
        self.reset_view()
        self.geometry_locked.set(True)
        self._update_lock_ui()
        self.update_info_panel()
        self.redraw()

    def setup_ui(self):
        # 1. Barra de Título MDI Clássica Windows XP (#0a246a)
        title_bar = tk.Frame(self, bg=THEME["title_bar_bg"], height=24, padx=4, pady=2)
        title_bar.pack(fill="x")

        shape_name = self.shape.get("name", "Molde")
        self.lbl_title = tk.Label(
            title_bar,
            text=f"📐 Shape Editor - [{shape_name}.die]",
            bg=THEME["title_bar_bg"], fg=THEME["title_bar_fg"],
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_title.pack(side="left")

        btn_box = tk.Frame(title_bar, bg=THEME["title_bar_bg"])
        btn_box.pack(side="right")
        self.btn_min = tk.Button(btn_box, text="_", relief="raised", bd=1, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0, command=self.on_minimize_click)
        self.btn_min.pack(side="left", padx=1)
        self.btn_max = tk.Button(btn_box, text="□", relief="raised", bd=1, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0, command=self.on_maximize_click)
        self.btn_max.pack(side="left", padx=1)
        self.btn_close = tk.Button(btn_box, text="✕", relief="raised", bd=1, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 7, "bold"), width=2, height=1, padx=0, pady=0, command=self.on_close_click)
        self.btn_close.pack(side="left", padx=1)

        # Arrastar janela pelo título em modo flutuante/lado a lado
        title_bar.bind("<ButtonPress-1>", self._on_title_press)
        title_bar.bind("<B1-Motion>", self._on_title_motion)
        title_bar.bind("<Double-1>", lambda e: self.on_maximize_click())
        self.lbl_title.bind("<ButtonPress-1>", self._on_title_press)
        self.lbl_title.bind("<B1-Motion>", self._on_title_motion)
        self.lbl_title.bind("<Double-1>", lambda e: self.on_maximize_click())
        self.bind("<Button-1>", lambda e: self.lift(), add="+")

        # 2. Barra de Ferramentas CAD (Clássica ATOM ShedNt)
        toolbar = tk.Frame(self, bg=THEME["bg_surface"], height=32, padx=4, pady=2, relief="raised", bd=1)
        toolbar.pack(fill="x")

        # Ações de Arquivo
        tk.Button(toolbar, text="💾 Salvar", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, font=("Segoe UI", 8, "bold"), command=self.save_changes).pack(side="left", padx=1)
        tk.Button(toolbar, text="🔄 Reverter (Ctrl+Z)", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.undo_or_revert).pack(side="left", padx=1)
        tk.Button(toolbar, text="📂 Importar .die", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.import_die_file).pack(side="left", padx=1)
        tk.Button(toolbar, text="📤 Exportar .die", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.export_die_file).pack(side="left", padx=1)

        # Separador vertical
        tk.Frame(toolbar, width=2, bg="#a0a0a0", relief="sunken", bd=1).pack(side="left", fill="y", padx=3, pady=2)

        # Modos de Ferramenta (Seleção, Ponto, Furo)
        self.btn_tool_select = tk.Button(toolbar, text="↖ Selecionar", bg=THEME["bg_hover"], fg=THEME["text_main"], relief="sunken", bd=2, font=("Segoe UI", 8), command=lambda: self.set_tool_mode("select"))
        self.btn_tool_select.pack(side="left", padx=1)

        self.btn_tool_point = tk.Button(toolbar, text="➕ Ponto", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=1, font=("Segoe UI", 8), command=lambda: self.set_tool_mode("add_point"))
        self.btn_tool_point.pack(side="left", padx=1)

        self.btn_tool_hole = tk.Button(toolbar, text="⭕ Furo", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=1, font=("Segoe UI", 8), command=lambda: self.set_tool_mode("add_hole"))
        self.btn_tool_hole.pack(side="left", padx=1)

        self.btn_tool_rotate = tk.Button(toolbar, text="🔄 Girar", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=1, font=("Segoe UI", 8), command=lambda: self.set_tool_mode("rotate"))
        self.btn_tool_rotate.pack(side="left", padx=1)

        self.btn_lock = tk.Button(toolbar, text="🔒 Editar Geometria", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, font=("Segoe UI", 8, "bold"), command=self.toggle_geometry_lock)
        self.btn_lock.pack(side="left", padx=2)

        tk.Button(toolbar, text="🗑️ Excluir", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.delete_selected).pack(side="left", padx=1)

        # Separador vertical
        tk.Frame(toolbar, width=2, bg="#a0a0a0", relief="sunken", bd=1).pack(side="left", fill="y", padx=4, pady=2)

        # Alternadores de Visualização (Checkboxes estilo WinXP)
        tk.Checkbutton(toolbar, text="Contorno", variable=self.show_contour, bg=THEME["bg_surface"], font=("Segoe UI", 8), command=self.redraw).pack(side="left", padx=1)
        tk.Checkbutton(toolbar, text="Costuras", variable=self.var_show_stitching, bg=THEME["bg_surface"], font=("Segoe UI", 8), command=self.redraw).pack(side="left", padx=1)
        tk.Checkbutton(toolbar, text="Furos", variable=self.show_holes, bg=THEME["bg_surface"], font=("Segoe UI", 8), command=self.redraw).pack(side="left", padx=1)
        tk.Checkbutton(toolbar, text="Vértices", variable=self.show_vertices, bg=THEME["bg_surface"], font=("Segoe UI", 8), command=self.redraw).pack(side="left", padx=1)
        tk.Checkbutton(toolbar, text="Índices", variable=self.show_indices, bg=THEME["bg_surface"], font=("Segoe UI", 8), command=self.redraw).pack(side="left", padx=1)
        tk.Checkbutton(toolbar, text="Coords", variable=self.show_coords, bg=THEME["bg_surface"], font=("Segoe UI", 8), command=self.redraw).pack(side="left", padx=1)
        tk.Checkbutton(toolbar, text="Grade", variable=self.show_grid, bg=THEME["bg_surface"], font=("Segoe UI", 8), command=self.redraw).pack(side="left", padx=1)

        # Separador vertical
        tk.Frame(toolbar, width=2, bg="#a0a0a0", relief="sunken", bd=1).pack(side="left", fill="y", padx=3, pady=2)

        # Zoom e Enquadramento
        tk.Button(toolbar, text="🔍 Total", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.reset_view).pack(side="left", padx=1)
        tk.Button(toolbar, text="➕", width=2, bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=1, font=("Segoe UI", 8, "bold"), command=lambda: self.zoom_step(1.25)).pack(side="left", padx=1)
        tk.Button(toolbar, text="➖", width=2, bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=1, font=("Segoe UI", 8, "bold"), command=lambda: self.zoom_step(0.8)).pack(side="left", padx=1)

        # Botão para alternar painel de informações
        tk.Checkbutton(toolbar, text="📋 Info", variable=self.show_info_panel, bg=THEME["bg_surface"], font=("Segoe UI", 8), command=self.toggle_info_panel).pack(side="right", padx=2)

        # 3. Área de Trabalho Principal (Canvas CAD à esquerda, Painel de Info à direita)
        self.work_split = tk.PanedWindow(self, orient="horizontal", bg=THEME["bg_workspace"], bd=0, sashwidth=4, sashrelief="raised")
        self.work_split.pack(fill="both", expand=True)

        # Container do Canvas CAD
        canvas_frame = tk.Frame(self.work_split, bg="#ffffff", relief="sunken", bd=2)
        self.work_split.add(canvas_frame, stretch="always", minsize=400)

        self.canvas = tk.Canvas(canvas_frame, bg="#ffffff", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)

        # Bindings do Canvas
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_motion)
        self.canvas.bind("<ButtonRelease-2>", self.on_pan_end)

        self.canvas.bind("<ButtonPress-3>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.on_pan_motion)
        self.canvas.bind("<ButtonRelease-3>", self.on_pan_end)

        self.canvas.bind("<Motion>", self.on_canvas_mouse_move)
        self.canvas.bind("<MouseWheel>", self.on_zoom_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_step(1.15, e.x, e.y))
        self.canvas.bind("<Button-5>", lambda e: self.zoom_step(0.85, e.x, e.y))

        # Atalhos de Teclado para Voltar / Reverter (Ctrl+Z)
        self.bind("<Control-z>", self.undo_or_revert)
        self.bind("<Control-Z>", self.undo_or_revert)
        self.bind("<Control-Key-z>", self.undo_or_revert)
        self.bind("<Control-Key-Z>", self.undo_or_revert)
        self.canvas.bind("<Control-z>", self.undo_or_revert)
        self.canvas.bind("<Control-Z>", self.undo_or_revert)
        self.canvas.bind("<Control-Key-z>", self.undo_or_revert)
        self.canvas.bind("<Control-Key-Z>", self.undo_or_revert)

        # Atalhos para Tela Cheia e Escape
        self.bind("<F11>", self.on_f11_fullscreen)
        self.canvas.bind("<F11>", self.on_f11_fullscreen)
        self.bind("<Escape>", self.on_escape_key)
        self.canvas.bind("<Escape>", self.on_escape_key)

        # Atalhos de Exclusão (Delete / Backspace)
        self.bind("<Delete>", lambda e: self.delete_selected())
        self.bind("<BackSpace>", lambda e: self.delete_selected())
        self.canvas.bind("<Delete>", lambda e: self.delete_selected())
        self.canvas.bind("<BackSpace>", lambda e: self.delete_selected())

        # Menu de Contexto CAD (Botão Direito)
        self.ctx_menu = tk.Menu(self, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"])
        self.ctx_menu.add_command(label="🔄 Voltar / Reverter\tCtrl+Z", command=self.undo_or_revert)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Definir como Ponto Inicial 0", command=self.set_as_start_point)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Inserir Vértice Aqui", command=self.ctx_add_vertex)
        self.ctx_menu.add_command(label="Inserir Furo Aqui", command=self.ctx_add_hole)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Excluir Selecionado", command=self.delete_selected)
        self.ctx_menu.add_command(label="Zoom Total", command=self.reset_view)

        # 4. Painel de Informações e Inspeção (Réplica fiel de dlgInformations.gif)
        self.panel_info = tk.Frame(self.work_split, bg=THEME["bg_surface"], width=260, relief="raised", bd=2, padx=6, pady=6)
        self.info_panel = self.panel_info
        self.work_split.add(self.panel_info, stretch="never", width=260, minsize=220)

        self.setup_info_panel_widgets()

        # 5. Barra de Status Inferior do Shape Editor
        self.sbar = tk.Frame(self, bg=THEME["bg_surface"], height=22, relief="sunken", bd=1, padx=2, pady=1)
        self.sbar.pack(side="bottom", fill="x")

        p_coords = tk.Frame(self.sbar, relief="sunken", bd=1, bg=THEME["bg_surface"], padx=6)
        p_coords.pack(side="left", padx=1)
        self.lbl_sbar_coords = tk.Label(p_coords, text="X: 0.0 mm | Y: 0.0 mm", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8))
        self.lbl_sbar_coords.pack()

        p_zoom = tk.Frame(self.sbar, relief="sunken", bd=1, bg=THEME["bg_surface"], padx=6)
        p_zoom.pack(side="left", padx=1)
        self.lbl_sbar_zoom = tk.Label(p_zoom, text="Zoom: 100%", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8))
        self.lbl_sbar_zoom.pack()

        p_info = tk.Frame(self.sbar, relief="sunken", bd=1, bg=THEME["bg_surface"], padx=8)
        p_info.pack(side="left", fill="x", expand=True, padx=1)
        self.lbl_sbar_status = tk.Label(p_info, text="Shape Editor pronto", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), anchor="w")
        self.lbl_sbar_status.pack(fill="x")

        self.update_info_panel()

    def setup_info_panel_widgets(self):
        """Cria os controles do painel dlgInformations."""
        # Título do Painel
        tk.Label(
            self.panel_info,
            text="Shape Information (ATOM ShedNt)",
            bg=THEME["title_bar_bg"], fg="#ffffff",
            font=("Segoe UI", 8, "bold"), relief="raised", bd=1
        ).pack(fill="x", pady=(0, 3))

        # Grupo: Identificação do Molde
        grp_shape = tk.LabelFrame(self.panel_info, text="Propriedades do Molde", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8, "bold"), padx=5, pady=2)
        grp_shape.pack(fill="x", pady=2)

        r1 = tk.Frame(grp_shape, bg=THEME["bg_surface"])
        r1.pack(fill="x", pady=1)
        tk.Label(r1, text="Nome:", width=7, anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left")
        self.entry_name = tk.Entry(r1, bg=THEME["bg_input"], fg=THEME["text_main"], relief="sunken", bd=2, font=("Segoe UI", 8))
        self.entry_name.insert(0, self.shape.get("name", ""))
        self.entry_name.pack(side="left", fill="x", expand=True)
        self.entry_name.bind("<Return>", lambda e: self.on_name_change())
        self.entry_name.bind("<FocusOut>", lambda e: self.on_name_change())

        self.lbl_dim_w = tk.Label(grp_shape, text="Largura (X): 0.0 mm", anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8))
        self.lbl_dim_w.pack(fill="x")

        self.lbl_dim_h = tk.Label(grp_shape, text="Altura (Y): 0.0 mm", anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8))
        self.lbl_dim_h.pack(fill="x")

        self.lbl_perim = tk.Label(grp_shape, text="Perímetro: 0.0 mm", anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8))
        self.lbl_perim.pack(fill="x")

        self.lbl_area_gross = tk.Label(grp_shape, text="Área Bruta: 0.0 dm²", anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8))
        self.lbl_area_gross.pack(fill="x")

        self.lbl_area_net = tk.Label(grp_shape, text="Área Líquida: 0.0 dm²", anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold"), fg="#000080")
        self.lbl_area_net.pack(fill="x")

        self.lbl_counts = tk.Label(grp_shape, text="Vértices: 0 | Furos: 0 | Costuras: 0", anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8))
        self.lbl_counts.pack(fill="x")

        self.lbl_stitching = tk.Label(grp_shape, text="Costuras: 0 linhas", anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8))
        self.lbl_stitching.pack(fill="x")

        self.chk_stitching = tk.Checkbutton(
            grp_shape,
            text="Mostrar costuras",
            variable=self.var_show_stitching,
            bg=THEME["bg_surface"],
            font=("Segoe UI", 8),
            command=self.redraw
        )
        self.chk_stitching.pack(anchor="w")

        # Grupo: Vértice Selecionado
        grp_vertex = tk.LabelFrame(self.panel_info, text="Vértice Selecionado", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8, "bold"), padx=5, pady=2)
        grp_vertex.pack(fill="x", pady=2)

        self.lbl_sel_idx = tk.Label(grp_vertex, text="Índice: Nenhum", anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8, "bold"))
        self.lbl_sel_idx.pack(fill="x")

        rx = tk.Frame(grp_vertex, bg=THEME["bg_surface"])
        rx.pack(fill="x", pady=1)
        tk.Label(rx, text="X (mm):", width=7, anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left")
        self.entry_vx = tk.Entry(rx, bg=THEME["bg_input"], fg=THEME["text_main"], relief="sunken", bd=2, font=("Segoe UI", 8), width=8)
        self.entry_vx.pack(side="left")
        self.entry_vx.bind("<Return>", self.on_vertex_entry_change)

        tk.Label(rx, text=" Y:", width=3, anchor="w", bg=THEME["bg_surface"], font=("Segoe UI", 8)).pack(side="left")
        self.entry_vy = tk.Entry(rx, bg=THEME["bg_input"], fg=THEME["text_main"], relief="sunken", bd=2, font=("Segoe UI", 8), width=8)
        self.entry_vy.pack(side="left")
        self.entry_vy.bind("<Return>", self.on_vertex_entry_change)

        tk.Button(grp_vertex, text="Definir como Ponto 0", bg=THEME["bg_surface"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.set_as_start_point).pack(fill="x", pady=1)
        tk.Button(grp_vertex, text="Excluir Vértice", bg=THEME["bg_surface"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.delete_selected).pack(fill="x", pady=1)

        # Grupo: Operações Geométricas
        grp_ops = tk.LabelFrame(self.panel_info, text="Geometria & Transformação", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8, "bold"), padx=5, pady=2)
        grp_ops.pack(fill="x", pady=2)

        tk.Button(grp_ops, text="🔄 Inverter Sentido de Corte", bg=THEME["bg_surface"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.reverse_contour).pack(fill="x", pady=1)
        tk.Button(grp_ops, text="↔ Espelhar X", bg=THEME["bg_surface"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.flip_horizontal).pack(fill="x", pady=1)
        tk.Button(grp_ops, text="↕ Espelhar Y", bg=THEME["bg_surface"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.flip_vertical).pack(fill="x", pady=1)
        tk.Button(grp_ops, text="🎯 Centralizar na Origem", bg=THEME["bg_surface"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.center_to_origin).pack(fill="x", pady=1)

        r_io = tk.Frame(grp_ops, bg=THEME["bg_surface"])
        r_io.pack(fill="x", pady=1)
        tk.Button(r_io, text="📂 Importar .die", bg=THEME["bg_surface"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.import_die_file).pack(side="left", fill="x", expand=True, padx=(0, 1))
        tk.Button(r_io, text="📤 Exportar .die", bg=THEME["bg_surface"], relief="raised", bd=1, font=("Segoe UI", 8), command=self.export_die_file).pack(side="right", fill="x", expand=True, padx=(1, 0))

        # Botão de Ação Principal
        tk.Button(
            self.panel_info,
            text="💾 Salvar Molde no Banco",
            bg="#006400", fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="raised", bd=2,
            command=self.save_changes
        ).pack(fill="x", pady=(5, 2))

    # =========================================================================
    # Lógica de Ferramentas e Modos
    # =========================================================================
    def toggle_geometry_lock(self):
        """Alterna entre modo seguro (bloqueado) e liberado para edição direta de vértices."""
        is_locked = not self.geometry_locked.get()
        self.geometry_locked.set(is_locked)
        self._update_lock_ui()

    def _update_lock_ui(self):
        is_locked = self.geometry_locked.get()
        if hasattr(self, "btn_lock") and self.btn_lock:
            if is_locked:
                self.btn_lock.config(text="🔒 Editar Geometria", relief="raised", bg=THEME["bg_surface"])
                self.lbl_sbar_status.config(text="Modo Seguro: Geometria bloqueada contra alterações acidentais.")
            else:
                self.btn_lock.config(text="🔓 Geometria Liberada", relief="sunken", bg=THEME["bg_hover"])
                self.lbl_sbar_status.config(text="Modo Edição: Geometria liberada para edição de vértices.")

    def set_tool_mode(self, mode):
        self.tool_mode = mode
        self.btn_tool_select.config(relief="raised", bg=THEME["bg_surface"])
        self.btn_tool_point.config(relief="raised", bg=THEME["bg_surface"])
        self.btn_tool_hole.config(relief="raised", bg=THEME["bg_surface"])
        if hasattr(self, "btn_tool_rotate"):
            self.btn_tool_rotate.config(relief="raised", bg=THEME["bg_surface"])

        if mode == "select":
            self.btn_tool_select.config(relief="sunken", bg=THEME["bg_hover"])
            self.canvas.config(cursor="crosshair")
            if self.geometry_locked.get():
                self.lbl_sbar_status.config(text="Ferramenta: Selecionar e Inspecionar Vértices (Bloqueado)")
            else:
                self.lbl_sbar_status.config(text="Ferramenta: Selecionar e Mover Vértices")
        elif mode == "add_point":
            self.btn_tool_point.config(relief="sunken", bg=THEME["bg_hover"])
            self.canvas.config(cursor="plus")
            if self.geometry_locked.get():
                self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
            else:
                self.lbl_sbar_status.config(text="Ferramenta: Clique para Inserir Vértice")
        elif mode == "add_hole":
            self.btn_tool_hole.config(relief="sunken", bg=THEME["bg_hover"])
            self.canvas.config(cursor="circle")
            if self.geometry_locked.get():
                self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
            else:
                self.lbl_sbar_status.config(text="Ferramenta: Clique para Inserir Furo de Broca")
        elif mode == "rotate":
            if hasattr(self, "btn_tool_rotate"):
                self.btn_tool_rotate.config(relief="sunken", bg=THEME["bg_hover"])
            self.canvas.config(cursor="exchange")
            self.lbl_sbar_status.config(text="Ferramenta: Clique e arraste para Girar o molde")

    def toggle_info_panel(self):
        if self.show_info_panel.get():
            self.work_split.add(self.panel_info, stretch="never", width=260, minsize=220)
        else:
            self.work_split.forget(self.panel_info)
        self.after(30, self.reset_view)

    def on_name_change(self):
        new_name = self.entry_name.get().strip()
        if new_name:
            self.shape["name"] = new_name
            self.lbl_title.config(text=f"📐 Shape Editor - [{new_name}.die]")

    def _on_title_press(self, event):
        self.lift()
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._win_start_x = self.winfo_x()
        self._win_start_y = self.winfo_y()

    def _on_title_motion(self, event):
        if hasattr(self, "_drag_start_x"):
            pinfo = self.place_info()
            if pinfo and str(pinfo.get("relwidth", "")) in ("1", "1.0"):
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

    def on_f11_fullscreen(self, event=None):
        top = self.winfo_toplevel()
        if hasattr(top, "toggle_fullscreen"):
            top.toggle_fullscreen()
            self.after(60, self.reset_view)

    def on_escape_key(self, event=None):
        top = self.winfo_toplevel()
        try:
            if top and hasattr(top, "attributes") and top.attributes("-fullscreen"):
                top.attributes("-fullscreen", False)
                self.after(60, self.reset_view)
                return "break"
        except Exception:
            pass

    # =========================================================================
    # Transformações e Operações CAD
    # =========================================================================
    def save_changes(self):
        self.on_name_change()
        if self.on_save_cb:
            self.on_save_cb(self.shape)
        self.lbl_sbar_status.config(text=f"Molde '{self.shape.get('name')}' salvo com sucesso!")
        messagebox.showinfo("Shape Editor", f"Molde '{self.shape.get('name')}' salvo com sucesso!", parent=self)

    def push_undo(self):
        """Salva uma cópia do molde atual na pilha de desfazer (Ctrl+Z)."""
        self.undo_stack.append(copy.deepcopy(self.shape))
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo_or_revert(self, event=None):
        """Atalho Ctrl+Z: desfaz/reverte a última alteração ou volta o molde ao original."""
        if self.undo_stack:
            prev_state = self.undo_stack.pop()
            self.redo_stack.append(copy.deepcopy(self.shape))
            self.shape = prev_state
            self.selected_vertex_idx = -1
            self.selected_hole_idx = -1
            self.update_info_panel()
            self.redraw()
            self.lbl_sbar_status.config(text="Alteração desfeita (Ctrl+Z).")
        elif self.shape != self.original_shape:
            self.push_undo()
            self.shape = copy.deepcopy(self.original_shape)
            self.selected_vertex_idx = -1
            self.selected_hole_idx = -1
            self.update_info_panel()
            self.redraw()
            self.lbl_sbar_status.config(text="Molde revertido ao original (Ctrl+Z).")
        else:
            self.lbl_sbar_status.config(text="Nenhuma alteração para desfazer.")
        return "break"

    def revert_changes(self):
        """Descarta todas as alterações e recarrega o molde original."""
        if messagebox.askyesno("Reverter", "Deseja descartar as alterações e recarregar o molde original?", parent=self):
            if self.shape != self.original_shape:
                self.push_undo()
            self.shape = copy.deepcopy(self.original_shape)
            self.selected_vertex_idx = -1
            self.selected_hole_idx = -1
            self.update_info_panel()
            self.redraw()
            self.lbl_sbar_status.config(text="Alterações descartadas. Molde original recarregado.")

    def import_die_file(self):
        """Abre caixa de diálogo para importar um ou mais moldes .die externos para o editor."""
        if hasattr(self, "on_import_die_cb") and self.on_import_die_cb:
            self.on_import_die_cb()
            return

        file_paths = filedialog.askopenfilenames(
            title="Importar Shape(s) ATOM (.die)",
            filetypes=[
                ("Arquivos Shape ATOM (*.die, *.d)", ("*.die", "*.Die", "*.DIE", "*.d", "*.D")),
                ("Moldes ATOM (.die)", ("*.die", "*.Die", "*.DIE")),
                ("Arquivos Shape (*.die, *.d, *.shp, *.json)", ("*.die", "*.Die", "*.d", "*.D", "*.shp", "*.json")),
                ("Todos os Arquivos (*.*)", "*.*")
            ],
            parent=self
        )
        if not file_paths:
            return

        try:
            shape_data = parse_die_file(file_paths[0])
            if "article_id" in self.shape:
                shape_data["article_id"] = self.shape["article_id"]
            if "id" in self.shape:
                shape_data["id"] = self.shape["id"]

            self.load_shape(shape_data)
            self.lbl_sbar_status.config(text=f"Molde '{shape_data['name']}' importado com sucesso!")
            messagebox.showinfo(
                "Importar Shape",
                f"Molde '{shape_data['name']}' importado com sucesso a partir de:\n{Path(file_paths[0]).name}\n\n"
                f"Vértices: {len(shape_data['contour'])}\nFuros: {len(shape_data.get('holes', []))}",
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Erro na Importação", f"Falha ao importar o arquivo .die:\n{str(e)}", parent=self)

    def export_die_file(self):
        """Exporta o molde atual no formato oficial ATOM $$FUSTELLA.v3$$ (.die)."""
        file_path = filedialog.asksaveasfilename(
            title="Exportar Shape ATOM (.die)",
            defaultextension=".die",
            initialfile=f"{self.shape.get('name', 'molde')}.die",
            filetypes=[
                ("Arquivo Shape ATOM (*.die)", "*.die"),
                ("Todos os Arquivos (*.*)", "*.*")
            ],
            parent=self
        )
        if not file_path:
            return

        try:
            save_die_file(self.shape, file_path)
            self.lbl_sbar_status.config(text=f"Molde exportado para {Path(file_path).name}")
            messagebox.showinfo("Exportar Shape", f"Molde exportado com sucesso no formato ATOM:\n{Path(file_path).name}", parent=self)
        except Exception as e:
            messagebox.showerror("Erro na Exportação", f"Falha ao exportar arquivo .die:\n{str(e)}", parent=self)

    def set_as_start_point(self):
        """Define o vértice selecionado como Ponto 0 (início do corte CNC ATOM)."""
        if self.geometry_locked.get():
            self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
            return
        idx = self.selected_vertex_idx
        contour = self.shape.get("contour", [])
        if 0 <= idx < len(contour):
            self.push_undo()
            self.shape["contour"] = contour[idx:] + contour[:idx]
            self.selected_vertex_idx = 0
            self.update_info_panel()
            self.redraw()
            self.lbl_sbar_status.config(text=f"Ponto {idx} definido como Ponto Inicial 0.")

    def reverse_contour(self):
        """Inverte a direção da polyline (sentido horário / anti-horário)."""
        contour = self.shape.get("contour", [])
        if len(contour) > 2:
            self.push_undo()
            # Mantém o ponto 0 e inverte os demais
            pt0 = contour[0]
            rest = list(reversed(contour[1:]))
            self.shape["contour"] = [pt0] + rest
            self.selected_vertex_idx = 0
            self.update_info_panel()
            self.redraw()
            self.lbl_sbar_status.config(text="Sentido de corte invertido.")

    def flip_horizontal(self):
        """Espelha o molde no eixo X."""
        contour = self.shape.get("contour", [])
        if not contour:
            return
        self.push_undo()
        min_x, _, max_x, _ = polygon_bbox(contour)
        mid_x = (min_x + max_x) / 2.0
        for pt in contour:
            pt["x"] = mid_x - (pt["x"] - mid_x)
        for h in self.shape.get("holes", []):
            h["x"] = mid_x - (h["x"] - mid_x)
        self.update_info_panel()
        self.redraw()
        self.lbl_sbar_status.config(text="Molde espelhado horizontalmente.")

    def flip_vertical(self):
        """Espelha o molde no eixo Y."""
        contour = self.shape.get("contour", [])
        if not contour:
            return
        self.push_undo()
        _, min_y, _, max_y = polygon_bbox(contour)
        mid_y = (min_y + max_y) / 2.0
        for pt in contour:
            pt["y"] = mid_y - (pt["y"] - mid_y)
        for h in self.shape.get("holes", []):
            h["y"] = mid_y - (h["y"] - mid_y)
        self.update_info_panel()
        self.redraw()
        self.lbl_sbar_status.config(text="Molde espelhado verticalmente.")

    def center_to_origin(self):
        """Move o molde para que seu canto inferior esquerdo fique em (20, 20)."""
        contour = self.shape.get("contour", [])
        if not contour:
            return
        self.push_undo()
        min_x, min_y, _, _ = polygon_bbox(contour)
        dx = 20.0 - min_x
        dy = 20.0 - min_y
        for pt in contour:
            pt["x"] += dx
            pt["y"] += dy
        for h in self.shape.get("holes", []):
            h["x"] += dx
            h["y"] += dy
        self.update_info_panel()
        self.redraw()
        self.lbl_sbar_status.config(text="Molde alinhado na origem (20, 20).")

    def rotate_shape(self, angle_deg: float, center=None):
        """Aplica uma rotação em graus em torno do centro do molde (ou centro informado)."""
        contour = self.shape.get("contour", [])
        if not contour:
            return
        if center is None:
            min_x, min_y, max_x, max_y = polygon_bbox(contour)
            center = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
        cx, cy = center
        rad = math.radians(angle_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        self.push_undo()

        # Contorno
        for pt in self.shape.get("contour", []):
            dx = pt["x"] - cx
            dy = pt["y"] - cy
            pt["x"] = round(cx + dx * cos_a - dy * sin_a, 2)
            pt["y"] = round(cy + dx * sin_a + dy * cos_a, 2)

        # Furos
        for h in self.shape.get("holes", []):
            dx = h["x"] - cx
            dy = h["y"] - cy
            h["x"] = round(cx + dx * cos_a - dy * sin_a, 2)
            h["y"] = round(cy + dx * sin_a + dy * cos_a, 2)

        # Costuras
        for polyline in self.shape.get("stitching", []):
            if isinstance(polyline, list):
                for pt in polyline:
                    if isinstance(pt, dict) and "x" in pt and "y" in pt:
                        dx = pt["x"] - cx
                        dy = pt["y"] - cy
                        pt["x"] = round(cx + dx * cos_a - dy * sin_a, 2)
                        pt["y"] = round(cy + dx * sin_a + dy * cos_a, 2)
                    elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        dx = pt[0] - cx
                        dy = pt[1] - cy
                        pt[0] = round(cx + dx * cos_a - dy * sin_a, 2)
                        pt[1] = round(cy + dx * sin_a + dy * cos_a, 2)

        self.update_info_panel()
        self.redraw()
        self.lbl_sbar_status.config(text=f"Molde rotacionado em {angle_deg:.1f}°.")

    def delete_selected(self):
        """Exclui o vértice ou furo selecionado."""
        if self.geometry_locked.get():
            self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
            return

        contour = self.shape.get("contour", [])
        holes = self.shape.get("holes", [])

        if self.selected_vertex_idx >= 0 and len(contour) > 3:
            self.push_undo()
            del contour[self.selected_vertex_idx]
            self.lbl_sbar_status.config(text=f"Vértice {self.selected_vertex_idx} excluído.")
            self.selected_vertex_idx = -1
            self.update_info_panel()
            self.redraw()
        elif self.selected_hole_idx >= 0 and self.selected_hole_idx < len(holes):
            self.push_undo()
            del holes[self.selected_hole_idx]
            self.lbl_sbar_status.config(text=f"Furo {self.selected_hole_idx} excluído.")
            self.selected_hole_idx = -1
            self.update_info_panel()
            self.redraw()
        else:
            if len(contour) <= 3:
                messagebox.showwarning("Atenção", "Um contorno precisa ter no mínimo 3 vértices!", parent=self)

    def on_vertex_entry_change(self, event=None):
        """Atualiza a coordenada do vértice via caixa de texto."""
        idx = self.selected_vertex_idx
        contour = self.shape.get("contour", [])

        if self.geometry_locked.get():
            self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
            if 0 <= idx < len(contour):
                self.entry_vx.delete(0, tk.END)
                self.entry_vx.insert(0, f"{contour[idx]['x']:.1f}")
                self.entry_vy.delete(0, tk.END)
                self.entry_vy.insert(0, f"{contour[idx]['y']:.1f}")
            return

        if 0 <= idx < len(contour):
            try:
                nx = float(self.entry_vx.get())
                ny = float(self.entry_vy.get())
                if round(contour[idx]["x"], 1) != round(nx, 1) or round(contour[idx]["y"], 1) != round(ny, 1):
                    self.push_undo()
                    contour[idx]["x"] = nx
                    contour[idx]["y"] = ny
                    self.update_info_panel()
                    self.redraw()
                    self.lbl_sbar_status.config(text=f"Vértice {idx} atualizado para ({nx:.1f}, {ny:.1f}).")
            except ValueError:
                pass

    # =========================================================================
    # Conversão de Coordenadas e Viewport CAD
    # =========================================================================
    def world_to_screen(self, wx, wy):
        return (
            wx * self.zoom + self.pan_x,
            wy * self.zoom + self.pan_y
        )

    def screen_to_world(self, sx, sy):
        return (
            (sx - self.pan_x) / self.zoom,
            (sy - self.pan_y) / self.zoom
        )

    def _on_canvas_configure(self, event):
        if event.width <= 50 or event.height <= 50:
            return

        if getattr(self, "_initial_fit_needed", False):
            self._initial_fit_needed = False
            self.reset_view()
            return

        if hasattr(self, "_last_canvas_w") and self._last_canvas_w > 0:
            dw = (event.width - self._last_canvas_w) / 2.0
            dh = (event.height - self._last_canvas_h) / 2.0
            self.pan_x += dw
            self.pan_y += dh

        self._last_canvas_w = event.width
        self._last_canvas_h = event.height
        self.redraw()

    def reset_view(self):
        """Ajusta o zoom e pan para enquadrar perfeitamente o molde no centro exato da tela."""
        contour = self.shape.get("contour", [])
        if not contour:
            return
        min_x, min_y, max_x, max_y = polygon_bbox(contour)
        w = max(10, max_x - min_x)
        h = max(10, max_y - min_y)

        c_w = self.canvas.winfo_width()
        c_h = self.canvas.winfo_height()

        if c_w <= 50 or c_h <= 50:
            try:
                c_w = max(300, self.winfo_width())
                c_h = max(300, self.winfo_height() - 60)
            except Exception:
                c_w, c_h = 1000, 700

        scale_x = (c_w - 140) / w
        scale_y = (c_h - 140) / h
        self.zoom = min(scale_x, scale_y, 4.0)
        self.zoom = max(0.2, self.zoom)

        # Centraliza exatamente no meio do canvas
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        self.pan_x = (c_w / 2.0) - (center_x * self.zoom)
        self.pan_y = (c_h / 2.0) - (center_y * self.zoom)

        self._last_canvas_w = c_w
        self._last_canvas_h = c_h

        pct = int(self.zoom * 100)
        self.lbl_sbar_zoom.config(text=f"Zoom: {pct}%")
        self.redraw()

    def zoom_step(self, factor, center_sx=None, center_sy=None):
        if center_sx is None:
            center_sx = self.canvas.winfo_width() / 2.0
            center_sy = self.canvas.winfo_height() / 2.0

        wx, wy = self.screen_to_world(center_sx, center_sy)
        new_zoom = max(0.1, min(10.0, self.zoom * factor))
        self.zoom = new_zoom

        self.pan_x = center_sx - wx * self.zoom
        self.pan_y = center_sy - wy * self.zoom

        pct = int(self.zoom * 100)
        self.lbl_sbar_zoom.config(text=f"Zoom: {pct}%")
        self.redraw()

    def on_zoom_wheel(self, event):
        factor = 1.15 if event.delta > 0 else 0.85
        self.zoom_step(factor, event.x, event.y)

    # =========================================================================
    # Eventos do Mouse no Canvas
    # =========================================================================
    def on_canvas_mouse_move(self, event):
        wx, wy = self.screen_to_world(event.x, event.y)
        self.lbl_sbar_coords.config(text=f"X: {wx:.1f} mm | Y: {wy:.1f} mm")

    def on_canvas_click(self, event):
        wx, wy = self.screen_to_world(event.x, event.y)
        contour = self.shape.get("contour", [])
        holes = self.shape.get("holes", [])

        if self.tool_mode == "select":
            # Procura vértice próximo (raio de 8 pixels na tela)
            hit_vertex = -1
            for i, pt in enumerate(contour):
                sx, sy = self.world_to_screen(pt["x"], pt["y"])
                if math.hypot(sx - event.x, sy - event.y) <= 8:
                    hit_vertex = i
                    break

            if hit_vertex >= 0:
                self.selected_vertex_idx = hit_vertex
                self.selected_hole_idx = -1
                if self.geometry_locked.get():
                    self.drag_target = None
                    self._pre_drag_state = None
                    self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
                else:
                    self.drag_target = ("vertex", hit_vertex)
                    self._pre_drag_state = copy.deepcopy(self.shape)
                self.update_info_panel()
                self.redraw()
                return

            # Procura furo próximo
            hit_hole = -1
            for i, h in enumerate(holes):
                sx, sy = self.world_to_screen(h["x"], h["y"])
                if math.hypot(sx - event.x, sy - event.y) <= 10:
                    hit_hole = i
                    break

            if hit_hole >= 0:
                self.selected_hole_idx = hit_hole
                self.selected_vertex_idx = -1
                if self.geometry_locked.get():
                    self.drag_target = None
                    self._pre_drag_state = None
                    self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
                else:
                    self.drag_target = ("hole", hit_hole)
                    self._pre_drag_state = copy.deepcopy(self.shape)
                self.update_info_panel()
                self.redraw()
                return

            # Clique no vazio limpa seleção
            self.selected_vertex_idx = -1
            self.selected_hole_idx = -1
            self.drag_target = None
            self._pre_drag_state = None
            self.update_info_panel()
            self.redraw()

        elif self.tool_mode == "add_point":
            if self.geometry_locked.get():
                self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
                return
            # Insere vértice na aresta mais próxima ou no fim
            self.push_undo()
            insert_idx = self._find_best_edge_insertion(wx, wy)
            contour.insert(insert_idx, {"x": round(wx, 1), "y": round(wy, 1)})
            self.selected_vertex_idx = insert_idx
            self.update_info_panel()
            self.redraw()
            self.set_tool_mode("select")
            self.lbl_sbar_status.config(text=f"Novo vértice inserido no índice {insert_idx}.")

        elif self.tool_mode == "add_hole":
            if self.geometry_locked.get():
                self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
                return
            # Insere furo na coordenada do clique
            self.push_undo()
            holes.append({"x": round(wx, 1), "y": round(wy, 1), "r": 3.0})
            self.selected_hole_idx = len(holes) - 1
            self.update_info_panel()
            self.redraw()
            self.set_tool_mode("select")
            self.lbl_sbar_status.config(text=f"Novo furo de broca inserido em ({wx:.1f}, {wy:.1f}).")

        elif self.tool_mode == "rotate":
            if not contour:
                return
            min_x, min_y, max_x, max_y = polygon_bbox(contour)
            cx = (min_x + max_x) / 2.0
            cy = (min_y + max_y) / 2.0
            self._rotate_center = (cx, cy)
            self._rotate_base_shape = copy.deepcopy(self.shape)
            self._pre_drag_state = copy.deepcopy(self.shape)
            self._rotate_start_angle = math.atan2(wy - cy, wx - cx)
            self._rotate_current_deg = 0.0
            self.drag_target = ("rotate", 0)
            self.lbl_sbar_status.config(text="Rotação: 0.0°")

    def _find_best_edge_insertion(self, wx, wy):
        """Determina a melhor posição no array do contorno para inserir o novo ponto."""
        contour = self.shape.get("contour", [])
        n = len(contour)
        if n < 3:
            return n

        best_idx = n
        min_dist = float("inf")

        for i in range(n):
            j = (i + 1) % n
            p1 = contour[i]
            p2 = contour[j]

            # Distância de (wx, wy) ao segmento (p1, p2)
            dist = self._dist_point_to_segment(wx, wy, p1["x"], p1["y"], p2["x"], p2["y"])
            if dist < min_dist:
                min_dist = dist
                best_idx = j

        return best_idx

    def _dist_point_to_segment(self, px, py, x1, y1, x2, y2):
        dx = x2 - x1
        dy = y2 - y1
        l2 = dx*dx + dy*dy
        if l2 == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / l2))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def on_canvas_drag(self, event):
        if not self.drag_target:
            return

        wx, wy = self.screen_to_world(event.x, event.y)
        target_type, idx = self.drag_target

        if self.geometry_locked.get() and target_type in ("vertex", "hole"):
            self.drag_target = None
            self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
            return

        if target_type == "vertex":
            contour = self.shape.get("contour", [])
            if 0 <= idx < len(contour):
                contour[idx]["x"] = round(wx, 1)
                contour[idx]["y"] = round(wy, 1)
                self.update_info_panel()
                self.redraw()
        elif target_type == "hole":
            holes = self.shape.get("holes", [])
            if 0 <= idx < len(holes):
                holes[idx]["x"] = round(wx, 1)
                holes[idx]["y"] = round(wy, 1)
                self.update_info_panel()
                self.redraw()
        elif target_type == "rotate":
            if not hasattr(self, "_rotate_center") or not hasattr(self, "_rotate_base_shape"):
                return
            cx, cy = self._rotate_center
            curr_angle = math.atan2(wy - cy, wx - cx)
            delta_rad = curr_angle - self._rotate_start_angle
            delta_deg = math.degrees(delta_rad)
            self._rotate_current_deg = delta_deg

            cos_a = math.cos(delta_rad)
            sin_a = math.sin(delta_rad)

            # 1. Rotaciona contorno
            new_contour = []
            for pt in self._rotate_base_shape.get("contour", []):
                dx = pt["x"] - cx
                dy = pt["y"] - cy
                new_pt = copy.copy(pt)
                new_pt["x"] = round(cx + dx * cos_a - dy * sin_a, 2)
                new_pt["y"] = round(cy + dx * sin_a + dy * cos_a, 2)
                new_contour.append(new_pt)
            self.shape["contour"] = new_contour

            # 2. Rotaciona furos
            new_holes = []
            for h in self._rotate_base_shape.get("holes", []):
                dx = h["x"] - cx
                dy = h["y"] - cy
                new_h = copy.copy(h)
                new_h["x"] = round(cx + dx * cos_a - dy * sin_a, 2)
                new_h["y"] = round(cy + dx * sin_a + dy * cos_a, 2)
                new_holes.append(new_h)
            self.shape["holes"] = new_holes

            # 3. Rotaciona costuras
            new_stitching = []
            for polyline in self._rotate_base_shape.get("stitching", []):
                if not isinstance(polyline, list):
                    continue
                new_poly = []
                for pt in polyline:
                    if isinstance(pt, dict) and "x" in pt and "y" in pt:
                        dx = pt["x"] - cx
                        dy = pt["y"] - cy
                        new_pt = copy.copy(pt)
                        new_pt["x"] = round(cx + dx * cos_a - dy * sin_a, 2)
                        new_pt["y"] = round(cy + dx * sin_a + dy * cos_a, 2)
                        new_poly.append(new_pt)
                    elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        dx = pt[0] - cx
                        dy = pt[1] - cy
                        new_poly.append([
                            round(cx + dx * cos_a - dy * sin_a, 2),
                            round(cy + dx * sin_a + dy * cos_a, 2)
                        ])
                new_stitching.append(new_poly)
            self.shape["stitching"] = new_stitching

            self.lbl_sbar_status.config(text=f"Rotação: {delta_deg:.1f}°")
            self.update_info_panel()
            self.redraw()

    def on_canvas_release(self, event):
        is_rotate = self.drag_target and self.drag_target[0] == "rotate"
        final_deg = getattr(self, "_rotate_current_deg", 0.0)

        if self._pre_drag_state is not None:
            if self.shape != self._pre_drag_state:
                self.undo_stack.append(self._pre_drag_state)
                if len(self.undo_stack) > 50:
                    self.undo_stack.pop(0)
                self.redo_stack.clear()
            self._pre_drag_state = None
        self.drag_target = None
        if hasattr(self, "_rotate_base_shape"):
            del self._rotate_base_shape

        if is_rotate:
            self.lbl_sbar_status.config(text=f"Rotação aplicada: {final_deg:.1f}°")

    def on_pan_start(self, event):
        self.is_panning = True
        self.last_mouse = (event.x, event.y)

    def on_pan_motion(self, event):
        if self.is_panning:
            dx = event.x - self.last_mouse[0]
            dy = event.y - self.last_mouse[1]
            self.pan_x += dx
            self.pan_y += dy
            self.last_mouse = (event.x, event.y)
            self.redraw()

    def on_pan_end(self, event):
        self.is_panning = False

    def dismiss_context_menu(self, event=None):
        if hasattr(self, "ctx_menu") and self.ctx_menu:
            try:
                self.ctx_menu.grab_release()
            except Exception:
                pass
            try:
                self.ctx_menu.unpost()
            except Exception:
                pass

    def on_right_click(self, event):
        self.ctx_pos = self.screen_to_world(event.x, event.y)
        self.on_canvas_click(event)
        self.dismiss_context_menu()
        try:
            self.ctx_menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass

    def ctx_add_vertex(self):
        if self.geometry_locked.get():
            self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
            return
        self.push_undo()
        wx, wy = self.ctx_pos
        contour = self.shape.get("contour", [])
        idx = self._find_best_edge_insertion(wx, wy)
        contour.insert(idx, {"x": round(wx, 1), "y": round(wy, 1)})
        self.selected_vertex_idx = idx
        self.update_info_panel()
        self.redraw()

    def ctx_add_hole(self):
        if self.geometry_locked.get():
            self.lbl_sbar_status.config(text="Geometria bloqueada. Ative 'Editar Geometria' para modificar.")
            return
        self.push_undo()
        wx, wy = self.ctx_pos
        holes = self.shape.get("holes", [])
        holes.append({"x": round(wx, 1), "y": round(wy, 1), "r": 3.0})
        self.selected_hole_idx = len(holes) - 1
        self.update_info_panel()
        self.redraw()

    # =========================================================================
    # Atualização de Métricas e Painel Informativo
    # =========================================================================
    def update_info_panel(self):
        contour = self.shape.get("contour", [])
        holes = self.shape.get("holes", [])
        stitching = self.shape.get("stitching", [])
        n_stitching = len(stitching) if isinstance(stitching, list) else 0

        if contour and len(contour) >= 3:
            min_x, min_y, max_x, max_y = polygon_bbox(contour)
            w = max_x - min_x
            h = max_y - min_y
            perim = polygon_perimeter(contour)
            area_gross_mm2 = polygon_area(contour)
            area_gross_dm2 = area_gross_mm2 / 10000.0

            # Desconta área dos furos
            holes_area_mm2 = sum(math.pi * (h.get("r", 3.0)**2) for h in holes)
            area_net_dm2 = max(0.0, (area_gross_mm2 - holes_area_mm2) / 10000.0)

            self.lbl_dim_w.config(text=f"Largura (X): {w:.1f} mm")
            self.lbl_dim_h.config(text=f"Altura (Y): {h:.1f} mm")
            self.lbl_perim.config(text=f"Perímetro: {perim:.1f} mm")
            self.lbl_area_gross.config(text=f"Área Bruta: {area_gross_dm2:.2f} dm²")
            self.lbl_area_net.config(text=f"Área Líquida: {area_net_dm2:.2f} dm²")
            self.lbl_counts.config(text=f"Vértices: {len(contour)} | Furos: {len(holes)} | Costuras: {n_stitching}")
        else:
            self.lbl_counts.config(text=f"Vértices: {len(contour)} | Furos: {len(holes)} | Costuras: {n_stitching}")

        if hasattr(self, "lbl_stitching"):
            self.lbl_stitching.config(text=f"Costuras: {n_stitching} linhas")

        # Vértice selecionado
        v_idx = self.selected_vertex_idx
        if 0 <= v_idx < len(contour):
            pt = contour[v_idx]
            self.lbl_sel_idx.config(text=f"Índice: #{v_idx} {'(Ponto 0 - Início)' if v_idx == 0 else ''}")
            self.entry_vx.delete(0, tk.END)
            self.entry_vx.insert(0, f"{pt['x']:.1f}")
            self.entry_vy.delete(0, tk.END)
            self.entry_vy.insert(0, f"{pt['y']:.1f}")
        else:
            self.lbl_sel_idx.config(text="Índice: Nenhum selecionado")
            self.entry_vx.delete(0, tk.END)
            self.entry_vy.delete(0, tk.END)

    # =========================================================================
    # Renderização CAD Clássica no Canvas
    # =========================================================================
    def redraw(self):
        self.canvas.delete("all")

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        self._used_headless_fallback = False
        if w < 10:
            w = max(self.canvas.winfo_reqwidth(), 600)
            self._used_headless_fallback = True
        if h < 10:
            h = max(self.canvas.winfo_reqheight(), 400)
            self._used_headless_fallback = True

        # 1. Grade milimétrica (Grid 10mm / 50mm)
        if self.show_grid.get():
            self._draw_grid(w, h)

        contour = self.shape.get("contour", [])
        holes = self.shape.get("holes", [])

        # 2. Preenchimento e Contorno da Peça
        if self.show_contour.get() and len(contour) >= 3:
            pts_screen = []
            for pt in contour:
                sx, sy = self.world_to_screen(pt["x"], pt["y"])
                pts_screen.extend([sx, sy])

            # Preenchimento translúcido suave (estilo preview ATOM)
            color_fill = "#f0f4f8"
            self.canvas.create_polygon(pts_screen, fill=color_fill, outline="#0a246a", width=2)

            # Setas indicativas do sentido de corte ao longo das arestas
            n = len(contour)
            for i in range(n):
                j = (i + 1) % n
                p1_x, p1_y = self.world_to_screen(contour[i]["x"], contour[i]["y"])
                p2_x, p2_y = self.world_to_screen(contour[j]["x"], contour[j]["y"])

                # Ponto médio para desenhar pequena seta
                mx = (p1_x + p2_x) / 2.0
                my = (p1_y + p2_y) / 2.0
                ang = math.atan2(p2_y - p1_y, p2_x - p1_x)
                arrow_len = 6
                ax1 = mx - arrow_len * math.cos(ang - 0.5)
                ay1 = my - arrow_len * math.sin(ang - 0.5)
                ax2 = mx - arrow_len * math.cos(ang + 0.5)
                ay2 = my - arrow_len * math.sin(ang + 0.5)
                self.canvas.create_line(mx, my, ax1, ay1, fill="#000080", width=1)
                self.canvas.create_line(mx, my, ax2, ay2, fill="#000080", width=1)

        # 2.5 Costuras Internas (Stitching)
        if getattr(self, "var_show_stitching", None) and self.var_show_stitching.get():
            self.show_stitching()

        # 3. Furos de Broca (Drills)
        if self.show_holes.get():
            for i, hole in enumerate(holes):
                hx, hy = self.world_to_screen(hole["x"], hole["y"])
                hr = max(3, hole.get("r", 3.0) * self.zoom)

                is_sel = (i == self.selected_hole_idx)
                outline_color = "#dc2626" if is_sel else "#16a34a"
                fill_color = "#fca5a5" if is_sel else "#bbf7d0"

                self.canvas.create_oval(hx - hr, hy - hr, hx + hr, hy + hr, fill=fill_color, outline=outline_color, width=2, tags=("holes", "hole"))
                # Cruz no centro do furo
                self.canvas.create_line(hx - hr*0.7, hy, hx + hr*0.7, hy, fill=outline_color, width=1, tags=("holes",))
                self.canvas.create_line(hx, hy - hr*0.7, hx, hy + hr*0.7, fill=outline_color, width=1, tags=("holes",))

        # 4. Vértices e Indicadores (Índices e Coordenadas)
        if self.show_vertices.get():
            for i, pt in enumerate(contour):
                sx, sy = self.world_to_screen(pt["x"], pt["y"])
                is_sel = (i == self.selected_vertex_idx)
                is_start = (i == 0)

                # Ponto 0 tem destaque especial (quadrado azul maior - início da ferramenta ATOM)
                if is_start:
                    box_sz = 6
                    self.canvas.create_rectangle(sx - box_sz, sy - box_sz, sx + box_sz, sy + box_sz, fill="#38bdf8", outline="#0284c7", width=2, tags=("vertices", "vertex"))
                elif is_sel:
                    box_sz = 5
                    self.canvas.create_rectangle(sx - box_sz, sy - box_sz, sx + box_sz, sy + box_sz, fill="#ef4444", outline="#b91c1c", width=2, tags=("vertices", "vertex"))
                else:
                    box_sz = 3
                    self.canvas.create_rectangle(sx - box_sz, sy - box_sz, sx + box_sz, sy + box_sz, fill="#ffffff", outline="#333333", width=1, tags=("vertices", "vertex"))

                # Rótulo de Índice (0, 1, 2...)
                if self.show_indices.get():
                    lbl_text = f"{i}"
                    color_lbl = "#0284c7" if is_start else ("#b91c1c" if is_sel else "#000000")
                    font_lbl = ("Segoe UI", 8, "bold") if (is_start or is_sel) else ("Segoe UI", 7)
                    self.canvas.create_text(sx + 8, sy - 8, text=lbl_text, fill=color_lbl, font=font_lbl, anchor="sw")

                # Rótulo de Coordenadas
                if self.show_coords.get():
                    coord_str = f"({pt['x']:.0f},{pt['y']:.0f})"
                    self.canvas.create_text(sx + 8, sy + 10, text=coord_str, fill="#666666", font=("Segoe UI", 6), anchor="nw")

    def show_stitching(self):
        """
        Renderiza costuras internas (stitching) do molde.
        Cor: #ff00ff (magenta)
        Espessura: 1.5
        Tag: 'stitching'
        """
        stitching = self.shape.get("stitching", [])
        if not stitching or not isinstance(stitching, list):
            return

        STITCH_COLOR = "#ff00ff"
        STITCH_WIDTH = 1.5

        for polyline in stitching:
            if not isinstance(polyline, list) or len(polyline) < 2:
                continue
            screen_points = []
            for pt in polyline:
                if isinstance(pt, dict) and "x" in pt and "y" in pt:
                    sx, sy = self.world_to_screen(pt["x"], pt["y"])
                    screen_points.extend([sx, sy])
                elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    sx, sy = self.world_to_screen(pt[0], pt[1])
                    screen_points.extend([sx, sy])

            if len(screen_points) >= 4:
                self.canvas.create_line(
                    screen_points,
                    fill=STITCH_COLOR,
                    width=STITCH_WIDTH,
                    tags=("stitching",)
                )

    def _draw_stitching(self):
        """Alias para show_stitching(), mantendo compatibilidade."""
        self.show_stitching()

    def _draw_grid(self, w, h):
        """Desenha a grade de fundo milimétrica."""
        # Origem (0, 0) em tela
        ox, oy = self.world_to_screen(0, 0)

        # Limites do mundo visíveis
        w_min_x, w_min_y = self.screen_to_world(0, 0)
        w_max_x, w_max_y = self.screen_to_world(w, h)

        step_mm = 10.0
        major_step_mm = 50.0

        start_x = math.floor(w_min_x / step_mm) * step_mm
        end_x = math.ceil(w_max_x / step_mm) * step_mm

        start_y = math.floor(w_min_y / step_mm) * step_mm
        end_y = math.ceil(w_max_y / step_mm) * step_mm

        # Linhas verticais
        x = start_x
        while x <= end_x:
            sx, _ = self.world_to_screen(x, 0)
            is_major = (abs(x % major_step_mm) < 0.01)
            color = "#d4d4d8" if is_major else "#f0f0f0"
            self.canvas.create_line(sx, 0, sx, h, fill=color, width=1)
            x += step_mm

        # Linhas horizontais
        y = start_y
        while y <= end_y:
            _, sy = self.world_to_screen(0, y)
            is_major = (abs(y % major_step_mm) < 0.01)
            color = "#d4d4d8" if is_major else "#f0f0f0"
            self.canvas.create_line(0, sy, w, sy, fill=color, width=1)
            y += step_mm

        # Eixos principais da Origem (0, 0)
        if 0 <= ox <= w:
            self.canvas.create_line(ox, 0, ox, h, fill="#a1a1aa", width=1, dash=(3, 2))
        if 0 <= oy <= h:
            self.canvas.create_line(0, oy, w, oy, fill="#a1a1aa", width=1, dash=(3, 2))
