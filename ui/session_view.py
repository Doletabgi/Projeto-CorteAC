"""
JobManager 2000 (Python Edition)
Session View Form - Recriação fiel de Session #91 [Stand by]
Telas frmSessionGeneral, frmSessionShapes, frmSessionMats, frmSessionLays, frmSessionSummary
"""

import math
import json
from typing import Dict, Any, Optional, List
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser, filedialog
from pathlib import Path
from config import THEME
from ui.cad_canvas import CADCanvas
from cad.geometry import rotate_point, transform_contour, polygon_area
from cad.colors import get_color_for_size, get_color_emoji, get_contrast_text_color
from ui.add_shapes_dialog import AddShapesDialog
from ui.dieproc_dialog import DieProcDialog
from ui.edit_shape_in_session_dialog import EditShapeInSessionDialog
from ui.nesting_mode_widget import NestingModeWidget, MODES
from ui.macro_panel import MacroPanel
from ui.debug_panel import DebugPanel
from cad.lay_parser import parse_lay, export_layout_from_pieces, validate_layout_placement
from cad.dual_exporter import DualLayoutExporter
from cad.layers_rule import calc_resto
from ui.sort_utils import natural_sort_key, size_sort_key, shape_area_sort_key, clean_session_display_name, resto_sort_key

RECOMMENDED_COMBINATIONS = [
    {
        "objetivo": "Solados / Palmilhas em chapa sintética (pedido exato)",
        "estrategia": "sint",
        "parametro": "stdNOTFill",
        "resultado": "Fileiras niveladas, geminação 0°/180°, gap estrito 1.0 mm e parada exata na cota."
    },
    {
        "objetivo": "Corte de solas para estoque (lotação total da placa)",
        "estrategia": "sint",
        "parametro": "stdFill",
        "resultado": "Fileiras contínuas preenchendo 100% da chapa física até o fim para estoque."
    },
    {
        "objetivo": "Placas de EVA, Borracha, Recouro (DieProc dp98)",
        "estrategia": "flashnestsheet",
        "parametro": "ALTERNADO",
        "resultado": "Grade DieProc clássica com intertravamento macho-fêmea (0°/180°) e preenchimento de cavidades."
    },
    {
        "objetivo": "Material com estampa, verniz ou textura orientada",
        "estrategia": "flashnestsheet",
        "parametro": "DIREITA",
        "resultado": "Trava o corte em sentido único (0°/0°); nenhuma peça fica invertida de cabeça para baixo."
    },
    {
        "objetivo": "Preset clássico de fábrica ATOM para sintéticos direcionais",
        "estrategia": "flashnestsheet",
        "parametro": "PrmSss_35",
        "resultado": "Acoplamento unidirecional 0°/0° preservando trama e fio da matéria-prima."
    },
    {
        "objetivo": "Tiras finas, debruns, correias e atacadores estreitos",
        "estrategia": "tape_a",
        "parametro": "stdNOTFill",
        "resultado": "Alinhamento longitudinal paralelo linear em passo fixo sem distorção por arrasto."
    },
    {
        "objetivo": "Aproveitar sobras e retalhos com moldes sortidos",
        "estrategia": "freenest",
        "parametro": "stdNOTFill",
        "resultado": "Encaixe orgânico livre por atração de gravidade espacial em retalhos e geometrias mistas."
    },
    {
        "objetivo": "Otimização avançada por macros com IA local adaptativa",
        "estrategia": "IA-teste",
        "parametro": "FastNest",
        "resultado": "Motor híbrido inteligente por macros declarativas com aprendizado por imitação e auto-tune UCB1."
    },
]

class SessionView(tk.Frame):
    def __init__(self, parent, session_data=None, canvas_ref=None, on_close=None, on_minimize=None, on_maximize=None, on_edit_shape=None, on_delete_shape=None, on_import_die=None, on_open_layout_editor=None, on_material_change=None, on_nest=None, on_standby=None, on_rewind=None, on_cut=None, on_strategy_change=None, on_add_shapes=None, all_shapes_catalog=None, db=None, on_open_dieproc=None, **kwargs):
        super().__init__(parent, bg=THEME["bg_surface"], relief="ridge", bd=2, **kwargs)
        self.session_data = session_data or {
            "id": 91,
            "job": "Artigo Derby",
            "name": "Sessão Principal #91",
            "status": "Stand by",
            "strategy": "flashnestsheet",
            "params": "stdNOTFill",
            "machine": "ATOM FlashCut Flex 3020",
            "shapes": []
        }
        self.canvas_ref = canvas_ref
        self.on_close_cb = on_close
        self.on_minimize_cb = on_minimize
        self.on_maximize_cb = on_maximize
        self.on_edit_shape_cb = on_edit_shape
        self.on_delete_shape_cb = on_delete_shape
        self.on_import_die_cb = on_import_die
        self.on_open_layout_editor_cb = on_open_layout_editor
        self.on_material_change_cb = on_material_change
        self.on_nest_cb = on_nest
        self.on_standby_cb = on_standby
        self.on_rewind_cb = on_rewind
        self.on_cut_cb = on_cut
        self.on_strategy_change_cb = on_strategy_change
        self.on_add_shapes_cb = on_add_shapes
        self.all_shapes_catalog = all_shapes_catalog or []
        self.shapes_list = list(self.session_data.get("shapes", []))
        self.selected_shape = None
        self._active_cell_entry = None
        self._inline_editor = None
        self.db = db or kwargs.get("database")
        self.on_open_dieproc_cb = on_open_dieproc
        self.active_dieproc_params = None
        self.shape_sort_col = None
        self.shape_sort_desc = True
        self.current_mode = self.session_data.get("nesting_mode") or "custom"
        self._suppress_auto_promote = False
        self.setup_ui()

    def setup_ui(self):
        # Barra de Título MDI interna no estilo original clássico Win2000
        title_bar = tk.Frame(self, bg=THEME["title_bar_bg"], height=24, padx=4, pady=2)
        title_bar.pack(fill="x")

        # Ícone de 4 cores e título em negrito branco
        self.lbl_title = tk.Label(
            title_bar,
            text=f"🗂️ Session #{self.session_data.get('id', '')} [{self.session_data.get('status', 'Stand by')}]",
            bg=THEME["title_bar_bg"], fg=THEME["title_bar_fg"], font=("Segoe UI", 9, "bold")
        )
        self.lbl_title.pack(side="left")

        # Botões de janela clássicos: Minimizar, Maximizar, Fechar
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
        self.lbl_title.bind("<ButtonPress-1>", self._on_title_press)
        self.lbl_title.bind("<B1-Motion>", self._on_title_motion)
        self.bind("<Button-1>", lambda e: self.lift(), add="+")

        # Notebook com as 5 abas originais do print
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=3, pady=3)

        tab_gen = tk.Frame(self.notebook, bg=THEME["bg_card"], padx=14, pady=12)
        self.tab_gen = tab_gen
        tab_shapes = tk.Frame(self.notebook, bg=THEME["bg_card"], padx=6, pady=6)
        self.tab_mat = tk.Frame(self.notebook, bg=THEME["bg_card"], padx=2, pady=2)
        tab_mat = self.tab_mat
        self.tab_lays = tk.Frame(self.notebook, bg=THEME["canvas_bg"])
        tab_summary = tk.Frame(self.notebook, bg=THEME["bg_card"], padx=8, pady=8)

        self.notebook.add(tab_gen, text="Geral")
        self.notebook.add(tab_shapes, text="Moldes")
        self.notebook.add(tab_mat, text="Materiais")
        self.notebook.add(self.tab_lays, text="Layout")
        self.notebook.add(tab_summary, text="Resumo")

        # -----------------------------------------------------------------
        # Aba 1: General (Estratégia de Corte & Parâmetros de Nesting)
        # Recriação autêntica dos prints media_1792035929049.png e frmSessionGeneral.gif
        # -----------------------------------------------------------------
        gen_container = tk.Frame(tab_gen, bg=THEME["bg_card"])
        gen_container.pack(fill="both", expand=True)

        # -------------------------------------------------------------
        # Camada 1: Modo de Encaixe (NestingModeWidget)
        # -------------------------------------------------------------
        self.mode_widget = NestingModeWidget(
            gen_container,
            current_mode=self.current_mode,
            on_mode_change=self._on_nesting_mode_changed,
            bg=THEME["bg_card"]
        )
        self.mode_widget.pack(fill="x", pady=(2, 6))

        # -------------------------------------------------------------
        # Camada 2: Avançado (Parâmetros de Corte)
        # -------------------------------------------------------------
        self.box_advanced = tk.LabelFrame(
            gen_container,
            text="Avançado (Parâmetros de Corte)",
            bg=THEME["bg_card"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            padx=8,
            pady=4
        )
        self.box_advanced.pack(fill="x", pady=(2, 6))

        # Grade de 2 colunas para Estratégia, Parâmetros, Códigos materiais e Máquina
        grid_params = tk.Frame(self.box_advanced, bg=THEME["bg_card"])
        grid_params.pack(fill="x", pady=(2, 4))

        # Coluna 1 (Esquerda): Estratégia e Parâmetros
        col_left = tk.Frame(grid_params, bg=THEME["bg_card"])
        col_left.pack(side="left", fill="x", expand=True, padx=(0, 16))

        # 1. Estratégia
        self.lbl_strat_title = tk.Label(
            col_left,
            text="A Estratégia define a geometria física do corte e do material:",
            anchor="w",
            bg=THEME["bg_card"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9)
        )
        self.lbl_strat_title.pack(fill="x", pady=(0, 2))

        self.lbl_strat_badge = tk.Label(
            col_left,
            text="(auto)",
            bg="#e8f5e9",
            fg="#2e7d32",
            font=("Segoe UI", 8, "bold"),
            relief="solid",
            bd=1,
            padx=4,
            pady=0
        )

        self.cb_strategy = ttk.Combobox(
            col_left,
            values=["sint", "tape_a", "flashnestsheet", "freenest", "IA-teste"],
            state="readonly",
            font=("Segoe UI", 9),
            height=8
        )
        initial_strat = self.session_data.get("strategy") or "sint"
        if initial_strat == "flashnestroll":
            initial_strat = "flashnestsheet"
            self.session_data["strategy"] = initial_strat
        self.cb_strategy.set(initial_strat)
        self.cb_strategy.pack(fill="x", pady=(0, 10))
        self.cb_strategy.bind("<<ComboboxSelected>>", self.on_strategy_selected)

        # 2. Parâmetros & Configuração DieProc (dp98)
        params_header = tk.Frame(col_left, bg=THEME["bg_card"])
        params_header.pack(fill="x", pady=(0, 2))

        self.btn_dieproc_cfg = tk.Button(
            params_header,
            text="⚙️ Configurar...",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8),
            relief="raised",
            bd=1,
            cursor="hand2",
            padx=4,
            pady=0,
            command=self.open_dieproc_configuration
        )
        self.btn_dieproc_cfg.pack(side="right")

        self.lbl_params_badge = tk.Label(
            params_header,
            text="(auto)",
            bg="#e8f5e9",
            fg="#2e7d32",
            font=("Segoe UI", 8, "bold"),
            relief="solid",
            bd=1,
            padx=4,
            pady=0
        )

        tk.Label(
            params_header,
            text="O Parâmetro define o comportamento das rotações, folgas e preenchimento da chapa:",
            anchor="w",
            bg=THEME["bg_card"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9)
        ).pack(side="left")

        self.cb_params = ttk.Combobox(
            col_left,
            values=self._get_available_params_list(),
            state="readonly",
            font=("Segoe UI", 9),
            height=8
        )
        init_p = self.session_data.get("params") or "ALTERNADO"
        available_p = list(self.cb_params["values"])
        if init_p == "GAP 2" or (available_p and init_p not in available_p):
            init_p = available_p[0] if available_p else "ALTERNADO"
            self.session_data["params"] = init_p
        self.cb_params.set(init_p)
        self.cb_params.pack(fill="x", pady=(0, 4))
        self.cb_params.bind("<<ComboboxSelected>>", self.on_params_selected)

        # Coluna 2 (Direita): Códigos materiais e Máquina de corte
        col_right = tk.Frame(grid_params, bg=THEME["bg_card"])
        col_right.pack(side="left", fill="x", expand=True, padx=(16, 0))

        # 3. Códigos materiais
        tk.Label(
            col_right,
            text="Códigos materiais:",
            anchor="w",
            bg=THEME["bg_card"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9)
        ).pack(fill="x", pady=(0, 2))

        self.cb_mat_code = ttk.Combobox(
            col_right,
            values=["(unspecified)"],
            state="readonly",
            font=("Segoe UI", 9),
            height=6
        )
        self.cb_mat_code.set("(unspecified)")
        self.cb_mat_code.pack(fill="x", pady=(0, 4))
        self.cb_mat_code.bind("<<ComboboxSelected>>", self.on_material_code_selected)

        # 4. Distância peças (mm) (Gap / Folga entre peças)
        tk.Label(
            col_right,
            text="Distância peças (mm):",
            anchor="w",
            bg=THEME["bg_card"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9)
        ).pack(fill="x", pady=(4, 2))

        gap_spin_frame = tk.Frame(col_right, bg=THEME["bg_card"])
        gap_spin_frame.pack(anchor="w", pady=(0, 4))

        self.btn_gap_minus = tk.Button(
            gap_spin_frame,
            text="-",
            width=3,
            relief="raised",
            bd=1,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            command=self._on_gap_minus
        )
        self.btn_gap_minus.pack(side="left")

        initial_gap = f"{float(self.session_data.get('gap_mm', 1.0)):.1f}"
        self.entry_gap = tk.Entry(
            gap_spin_frame,
            width=6,
            justify="center",
            font=("Tahoma", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            insertbackground=THEME["text_main"]
        )
        self.entry_gap.insert(0, initial_gap)
        self.entry_gap.pack(side="left", padx=4)
        self.entry_gap.bind("<FocusOut>", self._on_gap_entry_change)
        self.entry_gap.bind("<Return>", self._on_gap_entry_change)

        self.btn_gap_plus = tk.Button(
            gap_spin_frame,
            text="+",
            width=3,
            relief="raised",
            bd=1,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            command=self._on_gap_plus
        )
        self.btn_gap_plus.pack(side="left")

        # 5. Margem de Segurança da Placa (mm) (Botões de seleção rápida 10, 15 mm)
        box_margins = tk.LabelFrame(
            col_right,
            text="Margem de Segurança da Placa (mm):",
            bg=THEME["bg_card"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            padx=10,
            pady=6
        )
        box_margins.pack(fill="x", pady=(6, 4))

        self.margin_choice_var = tk.StringVar(value="10.0")
        init_m = float(self.session_data.get("margin_left", 10.0))
        for opt_val in ["10.0", "15.0"]:
            if abs(float(opt_val) - init_m) < 0.05:
                self.margin_choice_var.set(opt_val)
                break
        else:
            self.margin_choice_var.set(f"{init_m:.1f}")

        row_radios = tk.Frame(box_margins, bg=THEME["bg_card"])
        row_radios.pack(anchor="w", fill="x", pady=2)

        self.rb_margins = {}
        for val_str, label_text in [("10.0", "10 mm"), ("15.0", "15 mm")]:
            rb = tk.Radiobutton(
                row_radios,
                text=label_text,
                variable=self.margin_choice_var,
                value=val_str,
                bg=THEME["bg_card"],
                fg=THEME["text_main"],
                selectcolor="#ffffff",
                activebackground=THEME["bg_card"],
                activeforeground=THEME["text_main"],
                font=("Segoe UI", 9, "bold"),
                command=self._on_margin_radio_selected
            )
            rb.pack(side="left", padx=(0, 14))
            self.rb_margins[val_str] = rb

        # Máquina de corte padrão fixa (ATOM FlashCut Flex 3020) mantida nos dados da sessão sem exibir opção no editor
        self.session_data["machine"] = self.session_data.get("machine") or "ATOM FlashCut Flex 3020"

        # -------------------------------------------------------------
        # Camada 3: Macro / Aprendizado (IA Local)
        # -------------------------------------------------------------
        self.macro_panel = MacroPanel(
            gen_container,
            db=self.db,
            on_macro_changed=self._on_macro_changed_from_panel,
            on_open_editor=self.open_dieproc_configuration,
            bg=THEME["bg_card"]
        )
        self.macro_panel.pack(fill="x", pady=(2, 6))

        # -------------------------------------------------------------
        # Camada 4: Debug / Diagnóstico
        # -------------------------------------------------------------
        self.debug_panel = DebugPanel(
            gen_container,
            on_engine_change=self._on_debug_engine_changed,
            bg=THEME["bg_card"]
        )
        self.debug_panel.pack(fill="x", pady=(2, 6))

        # Linha de Botões de Ação estilo Windows XP
        btn_action_box = tk.Frame(gen_container, bg=THEME["bg_card"])
        btn_action_box.pack(fill="x", pady=(6, 10))

        row_btn1 = tk.Frame(btn_action_box, bg=THEME["bg_card"])
        row_btn1.pack(fill="x", pady=(0, 4))

        self.btn_action_nest = tk.Button(
            row_btn1,
            text="Gerar",
            width=11,
            relief="raised",
            bd=2,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            command=self.on_nest_button_click
        )
        self.btn_action_nest.pack(side="left", padx=(0, 6))

        self.btn_action_standby = tk.Button(
            row_btn1,
            text="Em espera",
            width=12,
            relief="raised",
            bd=2,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9),
            command=self.on_standby_button_click
        )
        self.btn_action_standby.pack(side="left", padx=4)

        self.btn_action_rewind = tk.Button(
            row_btn1,
            text="Refazer",
            width=12,
            relief="raised",
            bd=2,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9),
            command=self.on_rewind_button_click
        )
        self.btn_action_rewind.pack(side="left", padx=4)

        # Botão Cut removido conforme solicitação
        self.btn_action_cut = None

        # Feedback visual de Nesting (Barra de progresso indeterminada e texto)
        self.frame_progress = tk.Frame(btn_action_box, bg=THEME["bg_card"])
        # Por padrão, fica oculto (sem pack no init)
        self.progress_bar = ttk.Progressbar(
            self.frame_progress,
            mode="indeterminate",
            length=180
        )
        self.progress_bar.pack(side="left", padx=(0, 8))

        self.lbl_progress = tk.Label(
            self.frame_progress,
            text="Calculando encaixe... Por favor aguarde.",
            bg=THEME["bg_card"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8, "italic")
        )
        self.lbl_progress.pack(side="left")

        # Moldura clássica para dados da sessão (Nome e Status)
        info_frame = tk.LabelFrame(
            gen_container,
            text="Informações da Sessão",
            bg=THEME["bg_card"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8),
            relief="groove",
            padx=10,
            pady=8
        )
        info_frame.pack(fill="x", pady=(4, 2))

        row_info = tk.Frame(info_frame, bg=THEME["bg_card"])
        row_info.pack(fill="x", pady=2)

        tk.Label(
            row_info,
            text="Nome da sessão:",
            anchor="w",
            bg=THEME["bg_card"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 6))

        self.entry_sname = tk.Entry(
            row_info,
            bg=THEME["bg_input"],
            fg=THEME["text_main"],
            relief="sunken",
            bd=2,
            width=26,
            font=("Segoe UI", 9)
        )
        initial_name = clean_session_display_name(self.session_data.get("name", f"Sessão #{self.session_data['id']}")) or f"Sessão #{self.session_data['id']}"
        self.entry_sname.insert(0, initial_name)
        self.entry_sname.pack(side="left", padx=(0, 18))
        self.entry_sname.bind("<Return>", self._on_entry_sname_commit)
        self.entry_sname.bind("<FocusOut>", self._on_entry_sname_commit)

        tk.Label(
            row_info,
            text="Status:",
            anchor="w",
            bg=THEME["bg_card"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 6))

        self.lbl_status_val = tk.Label(
            row_info,
            text=self.session_data.get("status", "Stand by"),
            font=("Segoe UI", 9, "bold"),
            fg="#006400",
            bg=THEME["bg_card"]
        )
        self.lbl_status_val.pack(side="left")

        # Texto explicativo da estratégia selecionada
        self.lbl_strategy_desc = tk.Label(
            info_frame,
            text="",
            anchor="w",
            justify="left",
            bg=THEME["bg_card"],
            fg="#444444",
            font=("Segoe UI", 8, "italic")
        )
        self.lbl_strategy_desc.pack(fill="x", pady=(6, 0))
        self.update_strategy_description(self.cb_strategy.get())

        self._refresh_layer_2_widgets()


        # -----------------------------------------------------------------
        # Aba 2: Shapes (como em frmSessionShapes.gif) - Tabela + Preview à direita
        # -----------------------------------------------------------------
        shp_container = tk.Frame(tab_shapes, bg=THEME["bg_card"])
        shp_container.pack(fill="both", expand=True)

        # Tabela à esquerda com borda rebaixada clássica (conforme media_1792070997258.jpg)
        table_frame = tk.Frame(shp_container, bg="#ffffff", relief="sunken", bd=2)
        table_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        cols_shp = ("shape_id", "percurso", "tamanho", "molde", "pares", "resto", "sequencia")
        self.tree_shapes = ttk.Treeview(table_frame, columns=cols_shp, show="headings", height=8)
        self.tree_shapes.heading("shape_id", text="ShapeId", command=lambda: self.sort_shapes_by("shape_id"))
        self.tree_shapes.heading("percurso", text="Percurso", command=lambda: self.sort_shapes_by("percurso"))
        self.tree_shapes.heading("tamanho", text="Tama...", command=lambda: self.sort_shapes_by("tamanho"))
        self.tree_shapes.heading("molde", text="Molde", command=lambda: self.sort_shapes_by("molde"))
        self.tree_shapes.heading("pares", text="Pares...", command=lambda: self.sort_shapes_by("pares"))
        self.tree_shapes.heading("resto", text="Resto", command=lambda: self.sort_shapes_by("resto"))
        self.tree_shapes.heading("sequencia", text="Sequência /", command=lambda: self.sort_shapes_by("sequencia"))

        self.tree_shapes.column("shape_id", width=55, anchor="center")
        self.tree_shapes.column("percurso", width=180, anchor="w")
        self.tree_shapes.column("tamanho", width=55, anchor="center")
        self.tree_shapes.column("molde", width=145, anchor="w")
        self.tree_shapes.column("pares", width=55, anchor="center")
        self.tree_shapes.column("resto", width=45, anchor="e")
        self.tree_shapes.column("sequencia", width=65, anchor="center")

        sb_shp_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_shapes.yview)
        sb_shp_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree_shapes.xview)
        self.tree_shapes.configure(yscrollcommand=sb_shp_y.set, xscrollcommand=sb_shp_x.set)

        sb_shp_y.pack(side="right", fill="y")
        sb_shp_x.pack(side="bottom", fill="x")
        self.tree_shapes.pack(fill="both", expand=True)

        self.tree_shapes.bind("<<TreeviewSelect>>", self.on_shape_selected)
        self.tree_shapes.bind("<Button-1>", self.on_tree_shape_cell_click, add="+")
        self.tree_shapes.bind("<Double-1>", self.on_tree_shape_double_click)
        self.tree_shapes.bind("<Button-3>", self.show_shapes_context_menu)
        self.tree_shapes.bind("<Delete>", lambda e: self._on_tree_shapes_delete())
        self.tree_shapes.bind("<BackSpace>", lambda e: self._on_tree_shapes_delete())
        self.tree_shapes.bind("<Return>", self.on_tree_shape_enter)
        self.tree_shapes.bind("<KP_Enter>", self.on_tree_shape_enter)
        self.tree_shapes.bind("<F2>", self.on_tree_shape_f2)
        self.tree_shapes.bind("<Key>", self.on_tree_shape_key)

        # Painel lateral direito: Pré-visualizador da peça CAD conforme media_1792070997258.jpg
        # Fundo branco puro #ffffff, moldura sunken clássica de 2px, sem cabeçalho e sem botões
        preview_box = tk.Frame(shp_container, bg="#ffffff", width=310, relief="sunken", bd=2)
        preview_box.pack(side="right", fill="both", padx=(4, 0))
        preview_box.pack_propagate(False)

        self.preview_canvas = tk.Canvas(preview_box, bg="#ffffff", highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True)
        self.preview_canvas.bind("<Configure>", lambda e: self._on_preview_resize())
        self.preview_canvas.bind("<Double-1>", self.on_tree_shape_double_click)
        self.preview_canvas.bind("<Button-3>", self.show_shapes_context_menu)

        # Barra inferior com botões de ação da Aba Moldes (Edição de Pares e Sequência de Geração)
        shp_bot_bar = tk.Frame(tab_shapes, bg=THEME["bg_surface"], pady=4, padx=6)
        shp_bot_bar.pack(side="bottom", fill="x")

        tk.Button(
            shp_bot_bar, text="➕ Adicionar Molde...",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"), command=self.on_add_shape_click
        ).pack(side="left", padx=2)

        tk.Button(
            shp_bot_bar, text="📂 Importar .die...",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), command=self.on_import_button_click
        ).pack(side="left", padx=2)

        tk.Button(
            shp_bot_bar, text="🗑️ Remover",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), command=self.delete_selected_shape
        ).pack(side="left", padx=2)

        tk.Button(
            shp_bot_bar, text="✏️ Pares...",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"), command=self.change_selected_shape_pairs
        ).pack(side="left", padx=2)

        tk.Button(
            shp_bot_bar, text="🔢 Sequência...",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"), command=self.change_selected_shape_sequence
        ).pack(side="left", padx=2)

        tk.Button(
            shp_bot_bar, text="⬆️ Subir",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), command=self.move_selected_shape_up
        ).pack(side="left", padx=2)

        tk.Button(
            shp_bot_bar, text="⬇️ Descer",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), command=self.move_selected_shape_down
        ).pack(side="left", padx=2)

        self.btn_sort = tk.Button(
            shp_bot_bar, text="🔽 Classificar ▾",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"), command=self.show_sort_menu
        )
        self.btn_sort.pack(side="left", padx=2)

        tk.Button(
            shp_bot_bar, text="⚙️ Configurar...",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), command=self.open_edit_selected_shape_dialog
        ).pack(side="left", padx=2)

        tk.Button(
            shp_bot_bar, text="🎨 Cor...",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"), command=self.change_selected_shape_color
        ).pack(side="left", padx=2)

        # -----------------------------------------------------------------
        # Aba 3: Materiais (media_1791991495197.jpg / frmSessionMats)
        # -----------------------------------------------------------------
        tree_mat_frame = tk.Frame(tab_mat, bg="#ffffff", relief="sunken", bd=2)
        tree_mat_frame.pack(fill="both", expand=True)

        cols_mat = ("sel", "code", "desc", "defn", "width", "len", "layers", "thick", "gap", "qty")
        self.tree_mat = ttk.Treeview(tree_mat_frame, columns=cols_mat, show="headings", height=10, style="Layout.Treeview")
        self.tree_mat.heading("sel", text="", anchor="center")
        self.tree_mat.heading("code", text="Cod. Mat.", anchor="w")
        self.tree_mat.heading("desc", text="Descrição", anchor="w")
        self.tree_mat.heading("defn", text="Definição", anchor="w")
        self.tree_mat.heading("width", text="Largura (m)", anchor="w")
        self.tree_mat.heading("len", text="Comprime...", anchor="w")
        self.tree_mat.heading("layers", text="Camadas", anchor="w")
        self.tree_mat.heading("thick", text="Espessura (%1)", anchor="w")
        self.tree_mat.heading("gap", text="Gap (mm)", anchor="w")
        self.tree_mat.heading("qty", text="Quantidade", anchor="w")

        self.tree_mat.column("sel", width=24, anchor="center", stretch=False)
        self.tree_mat.column("code", width=85, anchor="w", stretch=False)
        self.tree_mat.column("desc", width=160, anchor="w", stretch=False)
        self.tree_mat.column("defn", width=95, anchor="w", stretch=False)
        self.tree_mat.column("width", width=85, anchor="e", stretch=False)
        self.tree_mat.column("len", width=80, anchor="e", stretch=False)
        self.tree_mat.column("layers", width=65, anchor="e", stretch=False)
        self.tree_mat.column("thick", width=100, anchor="e", stretch=False)
        self.tree_mat.column("gap", width=75, anchor="e", stretch=False)
        self.tree_mat.column("qty", width=90, anchor="e", stretch=True)
        self.tree_mat.pack(fill="both", expand=True)

        # Barra inferior com botão de edição, remoção e dica de uso
        mat_bot_bar = tk.Frame(self.tab_mat, bg=THEME["bg_surface"], pady=4, padx=6)
        mat_bot_bar.pack(fill="x")
        btn_edit_mat = tk.Button(
            mat_bot_bar,
            text="✏️ Editar Parâmetros do Material...",
            relief="raised",
            bd=2,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9),
            command=self.open_material_edit_dialog
        )
        btn_edit_mat.pack(side="left", padx=2)

        self.btn_remove_mat = tk.Button(
            mat_bot_bar,
            text="🗑️ Remover Material (Del)",
            relief="raised",
            bd=2,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9),
            command=self.remove_session_material
        )
        self.btn_remove_mat.pack(side="left", padx=2)

        lbl_hint = tk.Label(
            mat_bot_bar,
            text="💡 Dica: Clique na célula para editar ou tecle Delete para remover o material (disponível quando sem layout calculado).",
            bg=THEME["bg_surface"],
            fg=THEME["text_muted"],
            font=("Segoe UI", 8, "italic")
        )
        lbl_hint.pack(side="left", padx=10)

        # Eventos para edição interativa de Largura, Comprimento/Altura, Camadas e Remoção via Delete
        self.tree_mat.bind("<Double-1>", self.on_mat_double_click)
        self.tree_mat.bind("<Button-1>", self.on_mat_single_click)
        self.tree_mat.bind("<Return>", self.on_mat_enter_key)
        self.tree_mat.bind("<F2>", self.on_mat_f2_key)
        self.tree_mat.bind("<KeyPress>", self.on_mat_key_press)
        self.tree_mat.bind("<Button-3>", self.show_mat_context_menu)
        for w in (self.tree_mat, self.tab_mat):
            w.bind("<Delete>", self.remove_session_material)
            w.bind("<Key-Delete>", self.remove_session_material)
            w.bind("<BackSpace>", self.remove_session_material)
            w.bind("<Key-BackSpace>", self.remove_session_material)

        # -----------------------------------------------------------------
        # Aba 4: Layout (frmSessionLays.gif / media_1791990326629.jpg)
        # -----------------------------------------------------------------
        lays_container = tk.Frame(self.tab_lays, bg=THEME["bg_card"])
        lays_container.pack(fill="both", expand=True)

        # Lado Esquerdo: Tabela com fundo branco e moldura rebaixada
        lays_table_frame = tk.Frame(lays_container, bg="#ffffff", relief="sunken", bd=2)
        lays_table_frame.pack(side="left", fill="both", expand=True, padx=(2, 2), pady=2)

        # Estilo da Treeview de Layout para manter linha selecionada em cinza claro com texto preto (estilo Win2000 clássico)
        style = ttk.Style()
        style.configure("Layout.Treeview", background="#ffffff", foreground="#000000", fieldbackground="#ffffff", rowheight=20)
        style.map("Layout.Treeview",
            background=[("selected", "#e0e0e0")],
            foreground=[("selected", "#000000")]
        )

        cols_lay = ("sel", "n", "eff", "todo", "done", "time", "inst", "area")
        self.tree_lays = ttk.Treeview(lays_table_frame, columns=cols_lay, show="headings", height=10, style="Layout.Treeview")
        self.tree_lays.heading("sel", text="", anchor="center")
        self.tree_lays.heading("n", text="N.", anchor="w")
        self.tree_lays.heading("eff", text="Eficiência", anchor="w")
        self.tree_lays.heading("todo", text="Cortes a executar", anchor="w")
        self.tree_lays.heading("done", text="Cortes executados", anchor="w")
        self.tree_lays.heading("time", text="Tempo de encaixe", anchor="w")
        self.tree_lays.heading("inst", text="Instâncias", anchor="w")
        self.tree_lays.heading("area", text="Área instâncias (m²)", anchor="w")

        self.tree_lays.column("sel", width=24, anchor="center", stretch=False)
        self.tree_lays.column("n", width=36, anchor="center", stretch=False)
        self.tree_lays.column("eff", width=95, anchor="e", stretch=False)
        self.tree_lays.column("todo", width=110, anchor="e", stretch=False)
        self.tree_lays.column("done", width=110, anchor="e", stretch=False)
        self.tree_lays.column("time", width=110, anchor="e", stretch=False)
        self.tree_lays.column("inst", width=80, anchor="e", stretch=False)
        self.tree_lays.column("area", width=125, anchor="e", stretch=True)

        # Barra inferior com botões de ação da Aba Layout (.lay)
        lays_bot_bar = tk.Frame(lays_table_frame, bg=THEME["bg_surface"], pady=3, padx=4)
        lays_bot_bar.pack(side="bottom", fill="x")

        tk.Button(
            lays_bot_bar, text="📂 Abrir .lay...",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"), command=self.import_lay_file
        ).pack(side="left", padx=2)

        tk.Button(
            lays_bot_bar, text="💾 Exportar .lay...",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), command=self.export_lay_file
        ).pack(side="left", padx=2)

        self.btn_open_editor = tk.Button(
            lays_bot_bar, text="✏️ Editor...",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), command=self.on_layout_row_double_click
        )
        self.btn_open_editor.pack(side="left", padx=2)
        has_pieces = bool(self.session_data.get("placed_pieces") or self.session_data.get("layouts")) if isinstance(self.session_data, dict) else False
        self.btn_open_editor.config(state="normal" if has_pieces else "disabled")

        self.btn_print_layout = tk.Button(
            lays_bot_bar, text="🖨️ Imprimir...",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), command=self.print_current_layout
        )
        self.btn_print_layout.pack(side="left", padx=2)
        self.btn_print_layout.config(state="normal" if has_pieces else "disabled")

        tk.Button(
            lays_bot_bar, text="🗑️ Limpar",
            relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9), command=self.clear_current_layout
        ).pack(side="left", padx=2)

        self.tree_lays.pack(fill="both", expand=True)

        # Menu de contexto com clique direito
        self.lay_menu = tk.Menu(self, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"])
        self.lay_menu.add_command(label="📂 Abrir / Importar .lay...", command=self.import_lay_file)
        self.lay_menu.add_command(label="💾 Exportar para .lay...", command=self.export_lay_file)
        self.lay_menu.add_separator()
        self.lay_menu.add_command(label="✏️ Abrir no Layout Editor", command=self.on_layout_row_double_click)
        self.lay_menu.add_command(label="🖨️ Visualizar / Imprimir Layout (Ctrl+P)", command=self.print_current_layout)
        self.lay_menu.add_command(label="🗑️ Limpar Layout", command=self.clear_current_layout)
        self.tree_lays.bind("<Button-3>", self.show_lays_context_menu)
        self.tree_lays.bind("<Control-p>", lambda e: (self.print_current_layout(), "break")[1])
        self.tree_lays.bind("<Control-P>", lambda e: (self.print_current_layout(), "break")[1])

        # A tabela de Layout inicia em branco e só exibe linhas após a execução do encaixe (Nesting)
        self.tree_lays.bind("<Double-1>", self.on_layout_row_double_click)
        self.tree_lays.bind("<Return>", self.on_layout_row_double_click)
        self.tree_lays.bind("<<TreeviewSelect>>", self.on_layout_selected)
        self.tree_lays.bind("<ButtonRelease-1>", self.on_layout_selected)

        # Lado Direito: Visualizador de Layout com pré-visualização proporcional em pé (Portrait)
        preview_box_lay = tk.Frame(lays_container, bg="#ece9d8", width=300, relief="sunken", bd=2)
        preview_box_lay.pack(side="right", fill="both", padx=(0, 2), pady=2)
        preview_box_lay.pack_propagate(False)

        self.btn_preview_open_editor = tk.Button(
            preview_box_lay,
            text="🔍 Abrir Placa Selecionada no Editor",
            relief="raised", bd=1, bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 8, "bold"), command=self.on_layout_row_double_click
        )
        self.btn_preview_open_editor.pack(side="bottom", fill="x", padx=4, pady=(0, 4))
        self.btn_preview_open_editor.config(state="normal" if has_pieces else "disabled")

        self.mini_layout_canvas = tk.Canvas(preview_box_lay, bg="#ece9d8", highlightthickness=0, cursor="hand2")
        self.mini_layout_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.mini_layout_canvas.bind("<Double-1>", self.on_layout_row_double_click)
        self.mini_layout_canvas.bind("<Configure>", lambda e: self.draw_mini_layout_preview())

        self.draw_mini_layout_preview()

        # -----------------------------------------------------------------
        # Aba 5: Summary (como em frmSessionSummary.gif com duas caixas rebaixadas)
        # -----------------------------------------------------------------
        summary_top_frame = tk.Frame(tab_summary, relief="sunken", bd=2, bg=THEME["bg_input"])
        summary_top_frame.pack(fill="both", expand=True, pady=(0, 6))

        self.txt_summary = tk.Text(summary_top_frame, bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 9), relief="flat", borderwidth=0)
        self.txt_summary.pack(fill="both", expand=True, padx=4, pady=4)

        notes_box = tk.Frame(tab_summary, relief="sunken", bd=2, bg=THEME["bg_input"], height=90)
        notes_box.pack(fill="x")
        tk.Label(notes_box, text="Notes:", bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=4, pady=4)

        self.update_summary_text(0, 0, 0)

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
            self.on_minimize_cb(self)

    def on_maximize_click(self):
        if hasattr(self, "on_maximize_cb") and self.on_maximize_cb:
            self.on_maximize_cb(self)

    def on_close_click(self):
        if hasattr(self, "on_close_cb") and self.on_close_cb:
            self.on_close_cb(self)
        elif self.on_close_cb:
            self.on_close_cb()

    def on_layout_selected(self, event=None):
        """Atualiza o indicador de seleção ▶ na tabela de layouts e redesenha o mini-preview."""
        if not hasattr(self, "tree_lays"):
            return
        sel = self.tree_lays.selection()
        if not sel:
            return
        selected_iid = sel[0]
        for item in self.tree_lays.get_children():
            cur_vals = list(self.tree_lays.item(item, "values"))
            if cur_vals:
                cur_vals[0] = "▶" if item == selected_iid else ""
                self.tree_lays.item(item, values=cur_vals)
        self.draw_mini_layout_preview()

    def on_layout_row_double_click(self, event=None):
        placed = self.session_data.get("placed_pieces", []) if isinstance(self.session_data, dict) else []
        layouts = self.session_data.get("layouts", []) if isinstance(self.session_data, dict) else []
        if not placed and not layouts:
            messagebox.showwarning(
                "Layout Editor",
                "Não há layout calculado para esta sessão.\nExecute o cálculo de encaixe (Gerar) primeiro.",
                parent=self
            )
            return

        target_name = None
        if hasattr(self, "tree_lays"):
            sel = self.tree_lays.selection()
            if sel:
                item_iid = sel[0]
                if item_iid.startswith("lay_"):
                    try:
                        idx = int(item_iid.replace("lay_", ""))
                        if layouts and 0 <= idx < len(layouts):
                            target_name = layouts[idx].get("name") or f"lay{idx:04d}"
                        else:
                            target_name = f"lay{idx:04d}"
                    except ValueError:
                        pass

        if self.on_open_layout_editor_cb:
            name = target_name or (layouts[0].get("name") if layouts else None) or self.session_data.get("layout_name") or "lay0000"
            self.on_open_layout_editor_cb(name)

    def print_current_layout(self):
        """Abre a visualização de impressão A4 do layout da sessão ativa com o material configurado."""
        placed = self.session_data.get("placed_pieces", []) if isinstance(self.session_data, dict) else []
        layouts = self.session_data.get("layouts", []) if isinstance(self.session_data, dict) else []

        target_pieces = placed
        target_layout = None
        target_layout_idx = 0
        if hasattr(self, "tree_lays"):
            sel = self.tree_lays.selection()
            if sel and layouts:
                item_iid = sel[0]
                if item_iid.startswith("lay_"):
                    try:
                        idx = int(item_iid.replace("lay_", ""))
                        if 0 <= idx < len(layouts):
                            target_layout = layouts[idx]
                            target_layout_idx = idx
                            target_pieces = target_layout.get("pieces") or target_layout.get("placed_pieces") or target_pieces
                    except ValueError:
                        pass
        if not target_pieces and layouts:
            target_layout = layouts[0]
            target_layout_idx = 0
            target_pieces = target_layout.get("pieces") or target_layout.get("placed_pieces") or []

        if not target_pieces:
            messagebox.showwarning(
                "Imprimir Layout",
                "Não há layout calculado para esta sessão.\nExecute o cálculo de encaixe (Gerar) primeiro.",
                parent=self
            )
            return

        from ui.layout_print_dialog import LayoutPrintDialog

        mat = (self.session_data.get("material") or {}) if isinstance(self.session_data, dict) else {}
        sheet_w = float(target_layout.get("width_mm") if target_layout else mat.get("width_mm", 1380.0))
        sheet_h = float(target_layout.get("height_mm") if target_layout else mat.get("height_mm", 1080.0))
        mat_w_m = round(sheet_w / 1000.0, 2)
        mat_h_m = round(sheet_h / 1000.0, 2)
        mat_area = round((sheet_w * sheet_h) / 1_000_000.0, 2)
        eff = float(target_layout.get("yield_percent", self.session_data.get("yield_percent", 78.4)) if target_layout else self.session_data.get("yield_percent", 78.4))
        used_area = round(mat_area * (eff / 100.0), 2)

        # Lê dados de material diretamente da aba Materiais (tree_mat) se disponíveis
        code_val = mat.get("code") or mat.get("id")
        desc_val = mat.get("name") or mat.get("description") or mat.get("desc")
        layers_val = mat.get("layers", 2)
        if hasattr(self, "tree_mat"):
            m_items = self.tree_mat.get_children()
            if m_items:
                r_vals = self.tree_mat.item(m_items[0], "values")
                if len(r_vals) >= 7:
                    code_val = r_vals[1] or code_val
                    desc_val = r_vals[2] or desc_val
                    try:
                        layers_val = int(r_vals[6])
                    except (ValueError, TypeError):
                        pass

        session_shapes_val = getattr(self, "shapes_list", []) or (self.session_data.get("shapes", []) if isinstance(self.session_data, dict) else [])
        layout_name_val = (
            (target_layout.get("name") if target_layout else None)
            or self.session_data.get("layout_name")
            or f"{self.session_data.get('id', 10001)}.lay"
        )

        layout_data = {
            "layout_name": layout_name_val,
            "sheet_w_mm": sheet_w,
            "sheet_h_mm": sheet_h,
            "dimensions_str": f"{sheet_h / 10.0:.2f} X {sheet_w / 10.0:.2f} cm ({mat_h_m:.2f} X {mat_w_m:.2f} M)",
            "mat_area_str": f"{mat_area:.2f} sq.M.",
            "used_area_str": f"{used_area:.2f} sq.M.",
            "yield_pct": eff,
            "shapes_count": len(session_shapes_val) or min(len(target_pieces), 15),
            "instances_count": len(target_pieces),
            "gap_str": f"{float(mat.get('gap', 1.0)):.2f} mm" if (mat and 'gap' in mat) else "1.00 mm",
            "placed_pieces": target_pieces,
            "material_code": code_val,
            "material_desc": desc_val,
            "material_layers": layers_val,
            "material": mat,
            "session_shapes": session_shapes_val,
            "layouts": layouts,
            "current_layout_index": target_layout_idx,
        }
        dlg = LayoutPrintDialog(self, layout_data=layout_data)
        dlg.focus_set()

    def import_lay_file(self):
        """Importa um arquivo de layout .lay (ATOM $$LAYOUT.v3$$) para a sessão ativa."""
        filepath = filedialog.askopenfilename(
            parent=self,
            title="Importar Layout de Corte ATOM (.lay)",
            filetypes=[("Layout de Corte ATOM (*.lay)", "*.lay"), ("Todos os Arquivos (*.*)", "*.*")]
        )
        if not filepath:
            return

        try:
            lay = parse_lay(filepath, db=self.db)
        except Exception as e:
            messagebox.showerror("Erro ao Importar Layout", f"Falha ao ler arquivo .lay:\n{e}", parent=self)
            return

        placed_pieces = []
        for it in lay.items:
            placed_pieces.append({
                "id": it.item_no,
                "target_id": it.tg_idx + 1,
                "name": it.shape_name,
                "size": it.size or "41",
                "color": it.color,
                "contour": it.contour if it.contour else [],
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

        eff = lay.calculate_yield()
        self.session_data["placed_pieces"] = placed_pieces
        self.session_data["yield_percent"] = eff
        self.session_data["status"] = "Nested"
        self.session_data["layout_name"] = lay.filename

        # Atualiza dimensões do material se vierem no layout
        if lay.ris_w > 0 and lay.ris_l > 0:
            if not self.session_data.get("material"):
                self.session_data["material"] = {
                    "id": lay.cod_r or "884412",
                    "name": "Material da Chapa",
                    "type": "como placa",
                    "width_mm": lay.ris_w,
                    "height_mm": lay.ris_l,
                    "gap_mm": lay.gap or 1.0
                }
            else:
                self.session_data["material"]["width_mm"] = lay.ris_w
                self.session_data["material"]["height_mm"] = lay.ris_l
                if "id" not in self.session_data["material"]:
                    self.session_data["material"]["id"] = lay.cod_r or "884412"
                if "name" not in self.session_data["material"]:
                    self.session_data["material"]["name"] = "Material da Chapa"

        # Salva no banco de dados SQLite
        if self.db and self.session_data.get("id"):
            try:
                self.db.save_layout(self.session_data["id"], lay)
            except Exception as e:
                print(f"Aviso ao persistir layout no banco: {e}")

        # Atualiza a interface da sessão
        self.load_session(self.session_data)

        # Validação do layout
        warnings = validate_layout_placement(lay)
        if warnings:
            warn_msg = "\n".join(f"• {w}" for w in warnings[:6])
            if len(warnings) > 6:
                warn_msg += f"\n... e mais {len(warnings) - 6} avisos."
            messagebox.showwarning("Avisos de Validação do Layout", warn_msg, parent=self)
        else:
            messagebox.showinfo(
                "Layout Importado",
                f"Layout '{lay.filename}' importado com sucesso!\n{len(placed_pieces)} peças carregadas.\nAproveitamento: {eff:.2f}%",
                parent=self
            )

    def export_lay_file(self):
        """
        Exporta o layout atual da sessão com suporte à Dupla Saída:
        - ATOM (.lay)
        - Comelz (.onx)
        - Ambos (.lay + .onx)
        """
        placed_pieces = self.session_data.get("placed_pieces", [])
        if not placed_pieces:
            messagebox.showwarning("Exportar Layout", "Não há peças posicionadas no layout para exportar.", parent=self)
            return

        sess_id = self.session_data.get("id", 1)
        init_name = self.session_data.get("layout_name") or f"layout_sessao_{sess_id}"
        for ext in (".lay", ".onx"):
            if init_name.endswith(ext):
                init_name = init_name[:-len(ext)]

        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar Layout de Corte (ATOM .lay / Comelz .onx)",
            defaultextension=".lay",
            initialfile=init_name,
            filetypes=[
                ("Dupla Saída - ATOM (.lay) + Comelz (.onx)", "*.lay;*.onx"),
                ("Layout de Corte ATOM (*.lay)", "*.lay"),
                ("Layout de Corte Comelz (*.onx)", "*.onx"),
                ("Todos os Arquivos (*.*)", "*.*")
            ]
        )
        if not filepath:
            return

        try:
            material = self.session_data.get("material") or {
                "width_mm": 1350.0,
                "height_mm": 2553.38,
                "gap_mm": 1.0,
                "name": "884412"
            }
            p = Path(filepath)
            is_dual = (p.suffix.lower() not in (".lay", ".onx")) or (";" in str(p))

            if is_dual:
                res = DualLayoutExporter.export_dual_layout(
                    placed_pieces,
                    material,
                    base_path=p,
                    session_id=sess_id
                )
                msg = (
                    f"Dupla Saída concluída com sucesso!\n\n"
                    f"✓ ATOM (.lay): {res['lay_path']}\n"
                    f"✓ Comelz (.onx): {res['onx_path']}\n\n"
                    f"Total de peças: {len(placed_pieces)}"
                )
            elif p.suffix.lower() == ".onx":
                saved = DualLayoutExporter.export_comelz_onx(
                    placed_pieces,
                    material,
                    file_path=p,
                    session_id=sess_id
                )
                msg = f"Layout Comelz (.onx) exportado com sucesso:\n{saved}\nTotal de peças: {len(placed_pieces)}"
            else:
                saved = DualLayoutExporter.export_atom_lay(
                    placed_pieces,
                    material,
                    file_path=p,
                    session_id=sess_id
                )
                msg = f"Layout ATOM (.lay) exportado com sucesso:\n{saved}\nTotal de peças: {len(placed_pieces)}"

            messagebox.showinfo("Exportar Layout", msg, parent=self)
        except Exception as e:
            messagebox.showerror("Erro ao Exportar Layout", f"Falha ao exportar layout:\n{e}", parent=self)

    def clear_current_layout(self, ask_confirm=True):
        """Limpa as peças posicionadas e todos os layouts da sessão."""
        if not self.has_calculated_layout():
            return
        if ask_confirm and not messagebox.askyesno("Limpar Layout", "Deseja realmente limpar as peças posicionadas deste layout?", parent=self):
            return
        sess_id = self.session_data.get("id") if isinstance(self.session_data, dict) else None
        self.session_data["placed_pieces"] = []
        self.session_data["layouts"] = []
        self.session_data["yield_percent"] = 0.0
        self.session_data["cutting_time_sec"] = 0.0
        self.session_data["used_area_m2"] = 0.0
        self.session_data["status"] = "Stand by"

        layers = int(self.session_data.get("layers", 1)) if self.session_data else 1
        if self.session_data.get("shapes"):
            for s in self.session_data["shapes"]:
                req_p = int(s.get("pairs", 0))
                s["rest"] = req_p
                s["resto"] = calc_resto(req_p, layers)

        if self.db and sess_id:
            self.db.delete_session_layouts(sess_id)
            if self.session_data.get("shapes"):
                self.db.update_session_shapes(sess_id, self.session_data["shapes"])

        if self.canvas_ref and hasattr(self.canvas_ref, "clear_bed"):
            self.canvas_ref.clear_bed()

        top = self.winfo_toplevel()
        if hasattr(top, "current_session") and top.current_session and top.current_session.get("id") == sess_id:
            top.current_session["placed_pieces"] = []
            top.current_session["layouts"] = []
            top.current_session["yield_percent"] = 0.0
            top.current_session["cutting_time_sec"] = 0.0
            top.current_session["used_area_m2"] = 0.0
            top.current_session["status"] = "Stand by"
            if hasattr(top, "canvas") and hasattr(top.canvas, "clear_bed"):
                top.canvas.clear_bed()
        if hasattr(top, "sessions"):
            for s in top.sessions:
                if s.get("id") == sess_id:
                    s["placed_pieces"] = []
                    s["layouts"] = []
                    s["yield_percent"] = 0.0
                    s["cutting_time_sec"] = 0.0
                    s["used_area_m2"] = 0.0
                    s["status"] = "Stand by"
                    if self.session_data.get("shapes"):
                        s["shapes"] = self.session_data["shapes"]
                    break
        if hasattr(top, "layout_editor_view") and top.layout_editor_view:
            if hasattr(top.layout_editor_view, "set_session_layouts"):
                top.layout_editor_view.set_session_layouts([], initial_index=0)
            if hasattr(top.layout_editor_view, "set_pieces"):
                top.layout_editor_view.set_pieces([])

        self.load_session(self.session_data)

    def show_lays_context_menu(self, event):
        if hasattr(self, "lay_menu"):
            self.lay_menu.tk_popup(event.x_root, event.y_root)

    def _resolve_piece_contour(self, piece: dict) -> list:
        """Resolve o contorno geométrico de uma peça caso não esteja embutido diretamente."""
        if not piece or not isinstance(piece, dict):
            return []

        # 1. Contorno direto na peça
        c = piece.get("contour")
        if c and isinstance(c, (list, tuple)) and len(c) >= 3:
            return list(c)

        # 2. Contorno no objeto shape embutido
        shp = piece.get("shape")
        if isinstance(shp, dict):
            c = shp.get("contour")
            if c and isinstance(c, (list, tuple)) and len(c) >= 3:
                return list(c)
            if shp.get("contour_json"):
                try:
                    c = json.loads(shp["contour_json"])
                    if c and len(c) >= 3:
                        return c
                except Exception:
                    pass

        # 3. Busca nas listas de moldes da sessão e catálogo
        target_id = str(piece.get("target_id") or piece.get("shape_id") or piece.get("mold_id") or "").strip()
        piece_name = str(piece.get("name") or piece.get("piece_name") or "").strip().lower()
        piece_size = str(piece.get("size") or "").strip().lower()

        candidates = []
        if hasattr(self, "shapes_list") and self.shapes_list:
            candidates.extend(self.shapes_list)
        if isinstance(self.session_data, dict) and self.session_data.get("shapes"):
            candidates.extend(self.session_data["shapes"])
        if hasattr(self, "all_shapes_catalog") and self.all_shapes_catalog:
            candidates.extend(self.all_shapes_catalog)

        # 3a. Busca exata por ID
        if target_id:
            for s in candidates:
                s_id = str(s.get("id") or s.get("shape_id") or "").strip()
                if s_id and s_id == target_id:
                    sc = s.get("contour")
                    if sc and len(sc) >= 3:
                        return list(sc)
                    if s.get("contour_json"):
                        try:
                            sc = json.loads(s["contour_json"])
                            if sc and len(sc) >= 3:
                                return sc
                        except Exception:
                            pass

        # 3b. Busca por Nome + Tamanho
        if piece_name:
            for s in candidates:
                s_name = str(s.get("name", "")).strip().lower()
                s_size = str(s.get("size", "")).strip().lower()
                if s_name == piece_name and (not piece_size or s_size == piece_size):
                    sc = s.get("contour")
                    if sc and len(sc) >= 3:
                        return list(sc)
                    if s.get("contour_json"):
                        try:
                            sc = json.loads(s["contour_json"])
                            if sc and len(sc) >= 3:
                                return sc
                        except Exception:
                            pass

        # 3c. Busca no banco de dados se disponível
        if getattr(self, "db", None) and target_id and target_id.isdigit():
            try:
                db_shp = self.db.get_shape_by_id(int(target_id))
                if db_shp:
                    sc = db_shp.get("contour")
                    if sc and len(sc) >= 3:
                        return list(sc)
                    if db_shp.get("contour_json"):
                        sc = json.loads(db_shp["contour_json"])
                        if sc and len(sc) >= 3:
                            return sc
            except Exception:
                pass

        # 4. Fallback padrão retangular para garantir visibilidade
        return [
            {"x": 0.0, "y": 0.0},
            {"x": 75.0, "y": 0.0},
            {"x": 75.0, "y": 45.0},
            {"x": 0.0, "y": 45.0}
        ]

    def draw_mini_layout_preview(self):
        if not hasattr(self, "mini_layout_canvas"):
            return
        cv = self.mini_layout_canvas
        cv.delete("all")

        cw = cv.winfo_width()
        ch = cv.winfo_height()
        if cw < 50:
            cw = 290
        if ch < 50:
            ch = 380

        # Obtém layouts da sessão (se houver)
        sess_layouts = self.session_data.get("layouts", []) if isinstance(self.session_data, dict) else []
        if not sess_layouts and isinstance(self.session_data, dict) and self.session_data.get("placed_pieces"):
            sess_layouts = [{
                "layout_index": 0,
                "name": self.session_data.get("layout_name") or "lay0000",
                "pieces": self.session_data.get("placed_pieces", []),
                "width_mm": float(self.session_data.get("sheet_width", 1380.0)),
                "height_mm": float(self.session_data.get("sheet_height", 1080.0)),
                "yield_percent": self.session_data.get("yield_percent", 0.0),
                "cutting_time_sec": self.session_data.get("cutting_time_sec", 0.0),
                "used_area_m2": self.session_data.get("used_area_m2", 0.0)
            }]

        # Identifica a placa selecionada na tabela tree_lays
        selected_idx = 0
        target_layout = None
        if hasattr(self, "tree_lays"):
            sel = self.tree_lays.selection()
            if sel:
                item_iid = sel[0]
                if item_iid.startswith("lay_"):
                    try:
                        selected_idx = int(item_iid.replace("lay_", ""))
                    except ValueError:
                        selected_idx = 0

        if sess_layouts:
            if 0 <= selected_idx < len(sess_layouts):
                target_layout = sess_layouts[selected_idx]
            else:
                target_layout = sess_layouts[0]
                selected_idx = 0

        sheet_w = 1350.0
        sheet_h = 2553.38
        if target_layout:
            sheet_w = float(target_layout.get("width_mm") or target_layout.get("ris_w") or sheet_w)
            sheet_h = float(target_layout.get("height_mm") or target_layout.get("ris_l") or sheet_h)
            placed_pieces = target_layout.get("pieces") or target_layout.get("placed_pieces") or []
            ly_name = target_layout.get("name") or f"lay{selected_idx:04d}"
        else:
            mat = self.session_data.get("material") if isinstance(self.session_data, dict) else None
            if mat:
                sheet_w = float(mat.get("width_mm", 1350.0))
                sheet_h = float(mat.get("height_mm", 2553.38))
            if isinstance(self.session_data, dict):
                if "sheet_width" in self.session_data:
                    sheet_w = float(self.session_data["sheet_width"])
                if "sheet_height" in self.session_data:
                    sheet_h = float(self.session_data["sheet_height"])
            placed_pieces = self.session_data.get("placed_pieces", []) if isinstance(self.session_data, dict) else []
            ly_name = self.session_data.get("layout_name") or "lay0000" if isinstance(self.session_data, dict) else "lay0000"

        pad = 10
        top_lbl_h = 16
        avail_w = max(40.0, cw - pad * 2)
        avail_h = max(40.0, ch - pad * 2 - top_lbl_h)
        sc = min(avail_w / max(1.0, sheet_w), avail_h / max(1.0, sheet_h))
        plate_w = sheet_w * sc
        plate_h = sheet_h * sc

        x1 = (cw - plate_w) / 2.0
        x2 = x1 + plate_w
        y1 = (ch - plate_h - top_lbl_h) / 2.0 + top_lbl_h
        y2 = y1 + plate_h

        if not placed_pieces:
            cv.config(cursor="")
            # Sessão em branco / sem encaixe: exibe a chapa vazia limpa sem peças falsas
            cv.create_rectangle(x1, y1, x2, y2, fill="#d4d0c8", outline="#808080", width=1)
            cv.create_text(
                cw / 2, ch / 2,
                text="Sem layout de corte\n(Adicione os moldes na aba Moldes)",
                fill="#666666",
                font=("Segoe UI", 8),
                justify="center"
            )
            return

        cv.config(cursor="hand2")

        # Fundo da chapa de corte cinza (#9b9b9b) com borda preta nítida (em pé/portrait)
        cv.create_rectangle(x1, y1, x2, y2, fill="#9b9b9b", outline="#000000", width=1.5)

        # Grade milimétrica sutil
        gx = 0.0
        while gx <= sheet_w:
            sx = x1 + gx * sc
            cv.create_line(sx, y1, sx, y2, fill="#8c8c8c", width=1)
            gx += 300.0

        gy = 0.0
        while gy <= sheet_h:
            sy = y2 - gy * sc
            cv.create_line(x1, sy, x2, sy, fill="#8c8c8c", width=1)
            gy += 300.0

        # Rótulo com dimensões no topo da chapa (estilo Placa (298.00 X 138.00 cm) ou Placa 0 - lay0000 (...))
        h_cm = sheet_h / 10.0
        w_cm = sheet_w / 10.0
        header_text = f"Placa {selected_idx} - {ly_name} ({h_cm:.2f} X {w_cm:.2f} cm)" if len(sess_layouts) > 1 else f"Placa ({h_cm:.2f} X {w_cm:.2f} cm)"
        cv.create_text(
            cw / 2,
            max(8, y1 - 8),
            text=header_text,
            fill="#000000",
            font=("Segoe UI", 8, "bold")
        )

        # Desenha as peças reais posicionadas exatamente com a orientação e cores do Layout Editor
        for idx, p in enumerate(placed_pieces):
            contour = self._resolve_piece_contour(p)
            if not contour:
                continue
            cx = float(p.get("x", 0.0))
            cy = float(p.get("y", 0.0))
            rot = float(p.get("rotation", p.get("angle", p.get("rotation_deg", 0.0))))
            size_str = str(p.get("size") or (p.get("shape", {}).get("size") if isinstance(p.get("shape"), dict) else "") or p.get("piece_name") or p.get("name") or "41")
            col = p.get("color") or get_color_for_size(size_str, idx)

            poly = transform_contour(contour, cx, cy, rot)
            scr = []
            for pt in poly:
                sx = x1 + pt["x"] * sc
                sy = y2 - pt["y"] * sc
                scr.extend([sx, sy])
            if len(scr) >= 6:
                cv.create_polygon(scr, fill=col, outline="#000000", width=1)

        # Linha de Corte de Refile (CAM) se configurada
        trim_cut = self.session_data.get("trim_cut_line") if isinstance(self.session_data, dict) else None
        if trim_cut and trim_cut.get("enabled", True):
            cut_y = float(trim_cut.get("y", sheet_h))
            sy_cut = y2 - cut_y * sc
            cv.create_line(x1 - 2, sy_cut, x2 + 2, sy_cut, fill="#dc2626", dash=(4, 2), width=2)
            cv.create_text(
                (x1 + x2) / 2.0,
                max(y1 + 8, sy_cut - 7),
                text=f"✂ Refile: {cut_y / 10.0:.1f} cm",
                fill="#dc2626",
                font=("Segoe UI", 7, "bold")
            )

    def update_strategy_description(self, strategy):
        descs = {
            "sint": "A Estratégia define a geometria física do corte e do material. Sint (Sintéticos): Nesting contínuo para chapas e placas com geminação 0°/180° e colmeia.",
            "tape_a": "A Estratégia define a geometria física do corte e do material. Tape A (Tiras & Fitas): Nesting linear para faixas estreitas com passo compacto.",
            "flashnestsheet": "A Estratégia define a geometria física do corte e do material. Placa: Otimização bidimensional para placas retangulares com interlocking.",
            "freenest": "A Estratégia define a geometria física do corte e do material. FreeNest: Algoritmo livre de alta densidade visando máximo aproveitamento percentual (Yield %).",
            "IA-teste": "A Estratégia define a geometria física do corte e do material. IA-teste: Motor híbrido por macros declarativas com IA local embarcada e Auto-Tune."
        }
        if hasattr(self, "lbl_strategy_desc"):
            self.lbl_strategy_desc.config(text=descs.get(strategy, ""))

    def highlight_guide_matching(self):
        if not hasattr(self, "tree_guide"):
            return
        curr_strat = self.cb_strategy.get() if hasattr(self, "cb_strategy") else ""
        curr_param = self.cb_params.get() if hasattr(self, "cb_params") else ""
        for item in self.tree_guide.get_children():
            vals = self.tree_guide.item(item, "values")
            if len(vals) >= 3 and str(vals[1]) == curr_strat and str(vals[2]) == curr_param:
                self.tree_guide.selection_set(item)
                self.tree_guide.see(item)
                return
        sel = self.tree_guide.selection()
        if sel:
            self.tree_guide.selection_remove(sel)

    def on_guide_apply_clicked(self):
        if not hasattr(self, "tree_guide"):
            return
        sel = self.tree_guide.selection()
        if not sel:
            return
        vals = self.tree_guide.item(sel[0], "values")
        if vals and len(vals) >= 3:
            strat = str(vals[1])
            param = str(vals[2])
            if hasattr(self, "cb_strategy") and strat in self.cb_strategy["values"]:
                self.cb_strategy.set(strat)
                self.on_strategy_selected()
            if hasattr(self, "cb_params") and param in self.cb_params["values"]:
                self.cb_params.set(param)
                self.on_params_selected()

    def on_guide_double_click(self, event=None):
        self.on_guide_apply_clicked()

    def on_strategy_selected(self, event=None):
        strat = self.cb_strategy.get()
        self.session_data["strategy"] = strat
        self.update_strategy_description(strat)
        self.highlight_guide_matching()
        self._on_decision_changed("Estratégia")
        if self.on_strategy_change_cb:
            self.on_strategy_change_cb(strat)

    def on_params_selected(self, event=None):
        params = self.cb_params.get()
        self.session_data["params"] = params
        self.active_dieproc_params = None
        if self.db:
            p = self.db.get_dieproc_preset(params)
            if p:
                self.active_dieproc_params = p
        self.highlight_guide_matching()
        self._on_decision_changed("Parâmetros")
        if self.on_strategy_change_cb:
            self.on_strategy_change_cb(self.get_strategy(), params)

    def _on_macro_changed_from_panel(self, macro_name: str):
        self._on_decision_changed("Macro")

    def _on_debug_engine_changed(self, engine_name: str):
        self._on_decision_changed("Engine")

    def _on_decision_changed(self, decision_name: str):
        """Disparado quando usuário altera Strategy, Params, Engine ou Macro."""
        if getattr(self, "_suppress_auto_promote", False):
            return
        if getattr(self, "current_mode", "custom") != "custom":
            self.current_mode = "custom"
            if hasattr(self, "mode_widget"):
                self.mode_widget.set_mode("custom", notify=False)
            self._show_toast(f"Modo alterado para Personalizado (você sobrepôs: {decision_name})")
            self._refresh_layer_2_widgets()
            if self.db and self.session_data.get("id"):
                try:
                    self.db.update_session(self.session_data["id"], nesting_mode="custom")
                except Exception:
                    pass

    def _show_toast(self, message: str):
        """Exibe mensagem informativa na interface."""
        if hasattr(self, "lbl_strategy_desc"):
            self.lbl_strategy_desc.config(text=f"📢 {message}", fg="#b71c1c")
            self.after(5000, lambda: self.update_strategy_description(self.get_strategy()) if hasattr(self, "lbl_strategy_desc") else None)
        print(f"[JobManager UX] {message}")

    def _on_nesting_mode_changed(self, mode_key: str, mode_info: dict):
        self.current_mode = mode_key
        self._suppress_auto_promote = True
        try:
            strat = mode_info.get("strategy")
            params = mode_info.get("params")
            engine = mode_info.get("engine")

            if strat and hasattr(self, "cb_strategy"):
                vals = list(self.cb_strategy["values"])
                if strat not in vals:
                    self.cb_strategy["values"] = vals + [strat]
                self.cb_strategy.set(strat)
                self.session_data["strategy"] = strat
                self.update_strategy_description(strat)
                if self.on_strategy_change_cb:
                    self.on_strategy_change_cb(strat)

            if params and hasattr(self, "cb_params"):
                vals = list(self.cb_params["values"])
                if params not in vals:
                    self.cb_params["values"] = vals + [params]
                self.cb_params.set(params)
                self.session_data["params"] = params
                if self.db:
                    p = self.db.get_dieproc_preset(params)
                    if p:
                        self.active_dieproc_params = p

            if engine and hasattr(self, "debug_panel"):
                self.debug_panel.set_engine(engine)

            self.highlight_guide_matching()
            self._refresh_layer_2_widgets()

            if self.db and self.session_data.get("id"):
                try:
                    self.db.update_session(
                        self.session_data["id"],
                        nesting_mode=mode_key,
                        strategy=self.get_strategy(),
                        params=self.get_params(),
                    )
                except Exception:
                    pass
        finally:
            self._suppress_auto_promote = False

    def _refresh_layer_2_widgets(self):
        mode = getattr(self, "current_mode", "custom")
        is_auto = (mode == "auto")

        # Estratégia
        if hasattr(self, "cb_strategy"):
            if is_auto:
                self.cb_strategy.config(state="disabled")
                if hasattr(self, "lbl_strat_badge"):
                    self.lbl_strat_badge.pack(anchor="e", pady=(0, 2), before=self.cb_strategy)
            else:
                self.cb_strategy.config(state="readonly")
                if hasattr(self, "lbl_strat_badge"):
                    self.lbl_strat_badge.pack_forget()

        # Parâmetros
        if hasattr(self, "cb_params"):
            if is_auto:
                self.cb_params.config(state="disabled")
                if hasattr(self, "lbl_params_badge"):
                    self.lbl_params_badge.pack(side="right", padx=2)
            else:
                self.cb_params.config(state="readonly")
                if hasattr(self, "lbl_params_badge"):
                    self.lbl_params_badge.pack_forget()

        # Gap e Margens permanecem SEMPRE ativos e operáveis
        if hasattr(self, "entry_gap"):
            self.entry_gap.config(state="normal")
        if hasattr(self, "btn_gap_minus"):
            self.btn_gap_minus.config(state="normal")
        if hasattr(self, "btn_gap_plus"):
            self.btn_gap_plus.config(state="normal")
        if hasattr(self, "rb_margins"):
            for rb in self.rb_margins.values():
                rb.config(state="normal")

        # Atualiza Camada 3 e 4
        if hasattr(self, "macro_panel"):
            self.macro_panel.set_mode(mode)
        if hasattr(self, "debug_panel"):
            self.debug_panel.set_mode(mode)

    def get_nesting_mode(self) -> str:
        return getattr(self, "current_mode", "custom")

    def set_nesting_mode(self, mode: str):
        if hasattr(self, "mode_widget"):
            self.mode_widget.set_mode(mode, notify=True)
        else:
            self.current_mode = mode

    def _get_available_params_list(self) -> list:
        params_list = []
        if self.db:
            try:
                db_presets = self.db.get_dieproc_presets()
                if db_presets:
                    for k in sorted(db_presets.keys()):
                        if k != "GAP 2":
                            params_list.append(k)
            except Exception:
                pass
        builtins = ["ALTERNADO", "DIREITA", "ESQUERDA", "FastNest", "HighYield", "stdNOTFill", "stdFill", "PrmSss_35"]
        for b in builtins:
            if b not in params_list and b != "GAP 2":
                params_list.append(b)
        return params_list

    def refresh_params_list(self):
        """Atualiza a lista de valores da combobox cb_params consultando o banco de dados."""
        if not hasattr(self, "cb_params"):
            return
        available = self._get_available_params_list()
        self.cb_params["values"] = available
        curr = self.cb_params.get()
        if curr == "GAP 2" or (curr and curr not in available):
            new_val = available[0] if available else "ALTERNADO"
            self.cb_params.set(new_val)
            self.session_data["params"] = new_val
            if self.on_strategy_change_cb:
                self.on_strategy_change_cb(self.get_strategy(), new_val)
        self.highlight_guide_matching()

    def remove_param_from_list(self, name: str):
        """Remove um parâmetro da combobox e atualiza a seleção se necessário."""
        self.refresh_params_list()
        if hasattr(self, "cb_params"):
            cur_vals = [p for p in self.cb_params["values"] if p != name]
            self.cb_params["values"] = cur_vals
            if self.cb_params.get() == name:
                new_val = cur_vals[0] if cur_vals else "ALTERNADO"
                self.cb_params.set(new_val)
                self.session_data["params"] = new_val
                if self.on_strategy_change_cb:
                    self.on_strategy_change_cb(self.get_strategy(), new_val)
            self.highlight_guide_matching()

    def open_dieproc_configuration(self):
        if self.on_open_dieproc_cb:
            self.on_open_dieproc_cb(initial_preset=self.cb_params.get(), callback=self.on_dieproc_preset_selected)
        elif self.db:
            DieProcDialog(self, self.db, initial_preset=self.cb_params.get(), on_select=self.on_dieproc_preset_selected)

    def on_dieproc_preset_selected(self, preset_data):
        if not preset_data:
            return
        name = preset_data.get("name", "ALTERNADO")
        self.active_dieproc_params = preset_data
        self.refresh_params_list()
        cur_vals = list(self.cb_params["values"])
        if name not in cur_vals:
            cur_vals.insert(0, name)
            self.cb_params["values"] = cur_vals
        self.cb_params.set(name)
        self.session_data["params"] = name
        if self.on_strategy_change_cb:
            self.on_strategy_change_cb(self.get_strategy(), name)

    def get_dieproc_params(self):
        params = None
        if self.active_dieproc_params:
            params = dict(self.active_dieproc_params)
        elif self.db:
            preset_name = self.cb_params.get()
            preset = self.db.get_dieproc_preset(preset_name)
            if preset:
                params = dict(preset)
        if params is not None:
            params["gap1"] = self.get_gap_mm()
        return params

    def get_gap_mm(self) -> float:
        """Retorna o valor atual configurado no controle Distância peças (mm)."""
        if hasattr(self, "entry_gap"):
            try:
                val = float(str(self.entry_gap.get()).strip().replace(",", "."))
                return max(0.0, val)
            except Exception:
                pass
        return float(self.session_data.get("gap_mm", 1.0))

    def set_gap_mm(self, val: float):
        """Atualiza o controle visual e o session_data com o novo valor de gap."""
        try:
            v = max(0.0, float(val))
            if hasattr(self, "entry_gap"):
                self.entry_gap.delete(0, tk.END)
                self.entry_gap.insert(0, f"{v:.1f}")
            self.session_data["gap_mm"] = v
            if getattr(self, "db", None) and self.session_data.get("id"):
                try:
                    self.db.update_session(self.session_data["id"], gap_mm=v)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_gap_minus(self):
        cur = self.get_gap_mm()
        new_val = max(0.0, round(cur - 0.5, 1))
        self.set_gap_mm(new_val)

    def _on_gap_plus(self):
        cur = self.get_gap_mm()
        new_val = round(cur + 0.5, 1)
        self.set_gap_mm(new_val)

    def _on_gap_entry_change(self, event=None):
        val = self.get_gap_mm()
        self.set_gap_mm(val)

    def get_margins(self) -> Dict[str, float]:
        """Retorna os valores atuais configurados para as margens da placa (mm)."""
        default_val = 10.0
        if hasattr(self, "margin_choice_var"):
            try:
                default_val = float(self.margin_choice_var.get())
            except Exception:
                default_val = 10.0

        margins = {}
        for side in ["left", "right", "top", "bottom"]:
            val = self.session_data.get(f"margin_{side}")
            if val is None:
                val = default_val
            try:
                margins[side] = max(0.0, float(val))
            except Exception:
                margins[side] = max(0.0, default_val)
        return margins

    def set_margins(self, left: Optional[float] = None, right: Optional[float] = None, top: Optional[float] = None, bottom: Optional[float] = None):
        """Atualiza o session_data, os botões de seleção de margem e persiste no banco se disponível."""
        updates = {}
        for side, val in [("left", left), ("right", right), ("top", top), ("bottom", bottom)]:
            if val is not None:
                try:
                    v = max(0.0, float(val))
                    self.session_data[f"margin_{side}"] = v
                    updates[f"margin_{side}"] = v
                except Exception:
                    pass

        # Sincroniza a variável do radio button com o valor de referência
        ref_val = float(self.session_data.get("margin_left", 10.0))
        matched = False
        for opt_val in ["10.0", "15.0"]:
            if abs(float(opt_val) - ref_val) < 0.05:
                if hasattr(self, "margin_choice_var"):
                    self.margin_choice_var.set(opt_val)
                matched = True
                break
        if not matched and hasattr(self, "margin_choice_var"):
            self.margin_choice_var.set(f"{ref_val:.1f}")

        if updates and getattr(self, "db", None) and self.session_data.get("id"):
            try:
                self.db.update_session(self.session_data["id"], **updates)
            except Exception:
                pass

    def _on_margin_radio_selected(self):
        try:
            val = float(self.margin_choice_var.get())
        except Exception:
            val = 10.0
        self.set_margins(left=val, right=val, top=val, bottom=val)

    def on_machine_selected(self, event=None):
        machine = self.cb_machine.get() if hasattr(self, "cb_machine") else (self.session_data.get("machine") or "ATOM FlashCut Flex 3020")
        self.session_data["machine"] = machine

    def on_material_code_selected(self, event=None):
        if self.has_calculated_layout():
            messagebox.showwarning(
                "Material Bloqueado",
                "Não é possível trocar o material enquanto o layout estiver calculado.\n\n"
                "Para liberar a troca do material, limpe o layout atual (aba 'Layout' -> botão '🗑️ Limpar') ou refaça o cálculo.",
                parent=self
            )
            mat = self.session_data.get("material") if isinstance(self.session_data, dict) else None
            if mat:
                self.cb_mat_code.set(f"{mat.get('id', '')} - {mat.get('name', mat.get('code', ''))}")
            else:
                self.cb_mat_code.set("(unspecified)")
            return

        val = self.cb_mat_code.get()
        if val == "(unspecified)":
            self.remove_session_material()
            return
        if " - " in val:
            mat_id = val.split(" - ")[0].strip()
            if self.on_material_change_cb:
                self.on_material_change_cb(mat_id)

    def on_nest_button_click(self):
        self.show_progress()
        if self.on_nest_cb:
            self.on_nest_cb()

    def update_progress_text(self, current: int, total: int):
        """Atualiza o texto da barra de progresso para: Calculando chapa {current} de {total}..."""
        display_current = current + 1 if current == 0 else current
        text = f"Calculando chapa {display_current} de {total}..."
        if hasattr(self, "lbl_progress") and self.lbl_progress.winfo_exists():
            self.lbl_progress.config(text=text)
        if hasattr(self, "frame_progress") and self.frame_progress.winfo_exists():
            if not self.frame_progress.winfo_ismapped():
                self.frame_progress.pack(fill="x", pady=(4, 2))
        if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
            try:
                self.progress_bar.start(10)
            except Exception:
                pass

    def show_progress(self, text: str = "Calculando encaixe... Por favor aguarde."):
        """Exibe a barra de progresso indeterminada e desabilita botões de ação para evitar concorrência."""
        if hasattr(self, "lbl_status_val") and self.lbl_status_val.winfo_exists():
            self._prev_status_text = self.lbl_status_val.cget("text")
            self.lbl_status_val.config(text="Calculando...", fg="#B8860B")

        if hasattr(self, "lbl_progress") and self.lbl_progress.winfo_exists():
            self.lbl_progress.config(text=text)

        if hasattr(self, "frame_progress") and self.frame_progress.winfo_exists():
            if not self.frame_progress.winfo_ismapped():
                self.frame_progress.pack(fill="x", pady=(4, 2))

        if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
            try:
                self.progress_bar.start(10)
            except Exception:
                pass

        try:
            self.config(cursor="watch")
        except Exception:
            pass

        # Desabilita botões de ação para evitar cliques duplos e concorrência
        for btn in (getattr(self, "btn_action_nest", None),
                    getattr(self, "btn_action_standby", None),
                    getattr(self, "btn_action_rewind", None)):
            if btn and btn.winfo_exists():
                try:
                    btn.config(state="disabled")
                except Exception:
                    pass

    def hide_progress(self):
        """Para e oculta a barra de progresso e reabilita os botões de ação."""
        if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
            try:
                self.progress_bar.stop()
            except Exception:
                pass

        if hasattr(self, "frame_progress") and self.frame_progress.winfo_exists():
            try:
                self.frame_progress.pack_forget()
            except Exception:
                pass

        if hasattr(self, "lbl_status_val") and self.lbl_status_val.winfo_exists():
            if getattr(self, "_prev_status_text", None) and self.lbl_status_val.cget("text") == "Calculando...":
                self.lbl_status_val.config(text=self._prev_status_text, fg="#006400")

        try:
            self.config(cursor="")
        except Exception:
            pass

        # Reabilita botões de ação
        for btn in (getattr(self, "btn_action_nest", None),
                    getattr(self, "btn_action_standby", None),
                    getattr(self, "btn_action_rewind", None)):
            if btn and btn.winfo_exists():
                try:
                    btn.config(state="normal")
                except Exception:
                    pass

    def on_standby_button_click(self):
        if self.on_standby_cb:
            self.on_standby_cb()

    def on_rewind_button_click(self):
        if self.on_rewind_cb:
            self.on_rewind_cb()
        else:
            self.clear_current_layout(ask_confirm=False)

    def on_cut_button_click(self):
        if self.on_cut_cb:
            self.on_cut_cb()

    def get_strategy(self):
        return self.cb_strategy.get() if hasattr(self, "cb_strategy") else "flashnestsheet"

    def get_params(self):
        return self.cb_params.get() if hasattr(self, "cb_params") else "stdNOTFill"

    def get_machine(self):
        if hasattr(self, "cb_machine"):
            return self.cb_machine.get()
        return self.session_data.get("machine") or "ATOM FlashCut Flex 3020"

    def set_materials_list(self, materials):
        if hasattr(self, "cb_mat_code"):
            vals = ["(unspecified)"] + [f"{m['id']} - {m['name']}" for m in materials]
            self.cb_mat_code["values"] = vals

    def load_session(self, session_data):
        """Carrega e exibe os dados da sessão selecionada."""
        self.session_data = session_data
        status = session_data.get("status", "Stand by")
        self.lbl_title.config(text=f"🗂️ Session #{session_data['id']} [{status}]")
        self.entry_sname.delete(0, "end")
        clean_name = clean_session_display_name(session_data.get("name", f"Sessão #{session_data['id']}")) or f"Sessão #{session_data['id']}"
        self.entry_sname.insert(0, clean_name)
        if hasattr(self, "lbl_status_val"):
            self.lbl_status_val.config(text=status)

        # Carrega nesting_mode (sessões legadas -> 'custom', novas -> 'auto')
        mode = session_data.get("nesting_mode") or "custom"
        self.current_mode = mode
        if hasattr(self, "mode_widget"):
            self.mode_widget.set_mode(mode, notify=False)

        strat = session_data.get("strategy") or "flashnestsheet"
        if strat == "flashnestroll":
            strat = "flashnestsheet"
            session_data["strategy"] = strat
        if hasattr(self, "cb_strategy"):
            self.cb_strategy.set(strat)
            self.update_strategy_description(strat)
        if hasattr(self, "cb_params"):
            self.refresh_params_list()
            cur_p = session_data.get("params") or "ALTERNADO"
            available_p = list(self.cb_params["values"])
            if cur_p == "GAP 2" or (available_p and cur_p not in available_p):
                cur_p = available_p[0] if available_p else "ALTERNADO"
                session_data["params"] = cur_p
                if self.db and session_data.get("id"):
                    try:
                        self.db.update_session(session_data["id"], params=cur_p)
                    except Exception:
                        pass
            self.cb_params.set(cur_p)
        self.highlight_guide_matching()
        if hasattr(self, "cb_machine"):
            self.cb_machine.set(session_data.get("machine") or "ATOM FlashCut Flex 3020")
        if hasattr(self, "cb_mat_code"):
            mat = session_data.get("material")
            if mat:
                self.cb_mat_code.set(f"{mat['id']} - {mat['name']}")
            else:
                self.cb_mat_code.set("(unspecified)")

        if hasattr(self, "set_gap_mm"):
            gap_val = session_data.get("gap_mm")
            if gap_val is None and isinstance(session_data.get("material"), dict):
                gap_val = session_data["material"].get("gap_mm")
            if gap_val is None:
                gap_val = 1.0
            self.set_gap_mm(gap_val)

        if hasattr(self, "set_margins"):
            ml = session_data.get("margin_left", 10.0)
            mr = session_data.get("margin_right", 10.0)
            mt = session_data.get("margin_top", 10.0)
            mb = session_data.get("margin_bottom", 10.0)
            self.set_margins(left=ml, right=mr, top=mt, bottom=mb)

        self._refresh_layer_2_widgets()
        if hasattr(self, "macro_panel"):
            self.macro_panel.refresh_presets()
            self.macro_panel.refresh_status()

        # Atualiza a tabela da aba Moldes
        session_shapes = session_data.get("shapes", [])
        self.set_shapes_data(session_shapes)

        layouts_cnt = len(session_data.get("placed_pieces", []))
        self.update_summary_text(
            layouts_cnt,
            session_data.get("yield_percent", 0.0),
            session_data.get("cutting_time_sec", 0.0)
        )

        # Atualiza a tabela da aba Layouts (em branco caso não haja encaixe)
        if hasattr(self, "tree_lays"):
            self.tree_lays.delete(*self.tree_lays.get_children())
            sess_layouts = session_data.get("layouts", [])
            if not sess_layouts and session_data.get("id") and hasattr(self, "db") and self.db:
                try:
                    res = self.db.get_session_layouts(session_data["id"])
                    if isinstance(res, list) and res:
                        sess_layouts = res
                        session_data["layouts"] = sess_layouts
                except Exception:
                    pass

            if not sess_layouts and session_data.get("placed_pieces"):
                sess_layouts = [{
                    "layout_index": 0,
                    "name": session_data.get("layout_name") or "lay0000",
                    "pieces": session_data.get("placed_pieces", []),
                    "yield_percent": session_data.get("yield_percent", 0.0),
                    "cutting_time_sec": session_data.get("cutting_time_sec", 0.0),
                    "used_area_m2": session_data.get("used_area_m2", 0.0)
                }]
                session_data["layouts"] = sess_layouts

            for ly_idx, ly in enumerate(sess_layouts):
                ly_pieces = ly.get("pieces") or ly.get("placed_pieces") or []
                if not ly_pieces and ly_idx == 0 and session_data.get("placed_pieces"):
                    ly_pieces = session_data.get("placed_pieces") or []
                    ly["pieces"] = ly_pieces
                    ly["placed_pieces"] = ly_pieces

                eff = float(ly.get("yield_percent", ly.get("yield_pct", 0.0)))
                eff_str = f"{eff:.2f}%".replace('.', ',')

                cnt = len(ly_pieces)
                if cnt == 0 and ly.get("num_items"):
                    try:
                        cnt = int(ly.get("num_items") or 0)
                    except (ValueError, TypeError):
                        cnt = 0
                pieces_cnt = str(cnt)

                time_s = float(ly.get("cutting_time_sec", 0.0))
                time_str = f"{int(time_s // 60):02d}:{int(time_s % 60):02d}"
                area_m2 = ly.get("used_area_m2", 0.0)
                if not area_m2 and ly_pieces:
                    tot_mm2 = sum(polygon_area(self._resolve_piece_contour(p)) for p in ly_pieces)
                    area_m2 = tot_mm2 / 1000000.0
                area_str = f"{area_m2:.2f}".replace('.', ',') if area_m2 else "0,08"
                indicator = "▶" if ly_idx == 0 else ""
                row_iid = f"lay_{ly_idx}"
                self.tree_lays.insert("", "end", iid=row_iid, values=(indicator, str(ly_idx), eff_str, "1", "0", time_str, pieces_cnt, area_str))

            if isinstance(sess_layouts, list) and sess_layouts:
                if self.tree_lays.exists("lay_0"):
                    try:
                        self.tree_lays.selection_set("lay_0")
                    except Exception:
                        pass
                if not session_data.get("placed_pieces"):
                    session_data["placed_pieces"] = sess_layouts[0].get("pieces") or sess_layouts[0].get("placed_pieces") or []

        has_pieces = bool(session_data.get("placed_pieces") or session_data.get("layouts")) if isinstance(session_data, dict) else False
        if hasattr(self, "btn_open_editor"):
            self.btn_open_editor.config(state="normal" if has_pieces else "disabled")
        if hasattr(self, "btn_print_layout"):
            self.btn_print_layout.config(state="normal" if has_pieces else "disabled")
        if hasattr(self, "btn_preview_open_editor"):
            self.btn_preview_open_editor.config(state="normal" if has_pieces else "disabled")

        # Atualiza a tabela da aba Materiais
        if hasattr(self, "tree_mat"):
            self.set_material_data(session_data.get("material"))

        self.draw_mini_layout_preview()

    def _on_entry_sname_commit(self, event=None):
        if not self.session_data:
            return
        new_val = self.entry_sname.get().strip()
        if not new_val:
            return
        clean_val = clean_session_display_name(new_val)
        if clean_val != new_val:
            self.entry_sname.delete(0, "end")
            self.entry_sname.insert(0, clean_val)
        sess_id = self.session_data.get("id")
        if clean_val and self.session_data.get("name") != clean_val:
            self.session_data["name"] = clean_val
            if self.db and sess_id:
                try:
                    self.db.update_session(sess_id, name=clean_val)
                except Exception:
                    pass
            top = self.winfo_toplevel()
            if hasattr(top, "sessions"):
                for s in top.sessions:
                    if s.get("id") == sess_id:
                        s["name"] = clean_val
                        break
            if hasattr(top, "populate_tree"):
                top.populate_tree(mode=getattr(top, "current_mode", "jobs"))


    def has_calculated_layout(self):
        """Verifica se a sessão possui um layout de corte calculado com peças posicionadas."""
        if not self.session_data or not isinstance(self.session_data, dict):
            return False
        return bool(self.session_data.get("placed_pieces") or self.session_data.get("layouts"))

    def remove_session_material(self, event=None):
        """Remove o material da sessão caso o layout NÃO esteja calculado.
        Se o layout já estiver calculado com peças encaixadas, bloqueia a remoção e
        orienta o usuário a limpar ou refazer o layout para liberar a troca.
        """
        # Se estiver em edição inline de célula (Entry ativo), deixa a tecla Delete apagar o caractere
        if hasattr(self, "_active_cell_entry") and self._active_cell_entry:
            return None

        # 1. Bloqueia se houver layout calculado
        if self.has_calculated_layout():
            messagebox.showwarning(
                "Material Bloqueado",
                "Não é possível remover ou trocar o material enquanto o layout estiver calculado.\n\n"
                "Para liberar a troca do material, limpe o layout atual (aba 'Layout' -> botão '🗑️ Limpar') ou refaça o cálculo.",
                parent=self
            )
            return "break"

        # 2. Verifica se há material atribuído
        has_mat = bool(self.session_data.get("material")) if isinstance(self.session_data, dict) else False
        if not has_mat and not self.tree_mat.get_children():
            return "break"

        # 3. Confirmação
        if not messagebox.askyesno(
            "Remover Material da Sessão",
            "Deseja realmente remover o material desta sessão?",
            parent=self
        ):
            return "break"

        # 4. Remove o material da sessão
        if isinstance(self.session_data, dict):
            self.session_data["material"] = None
            self.session_data["material_id"] = None
            if self.db and self.session_data.get("id"):
                try:
                    self.db.update_session(self.session_data["id"], material_id=None, clear_material=True)
                except Exception as e:
                    print(f"Aviso ao persistir remoção do material no banco: {e}")

        # 5. Limpa a Treeview e o combobox
        self.tree_mat.delete(*self.tree_mat.get_children())
        if hasattr(self, "cb_mat_code"):
            self.cb_mat_code.set("(unspecified)")

        # 6. Notifica o MainWindow
        if self.on_material_change_cb:
            self.on_material_change_cb(None)

        # 7. Redesenha mini preview e sumário
        self.draw_mini_layout_preview()
        layouts_cnt = len(self.session_data.get("placed_pieces", [])) if isinstance(self.session_data, dict) else 0
        yield_pct = self.session_data.get("yield_percent", 0.0) if isinstance(self.session_data, dict) else 0.0
        est_sec = self.session_data.get("cutting_time_sec", 0.0) if isinstance(self.session_data, dict) else 0.0
        self.update_summary_text(layouts_cnt, yield_pct, est_sec)

        return "break"

    def set_material_data(self, material=None):
        if not hasattr(self, "tree_mat"):
            return
        self.tree_mat.delete(*self.tree_mat.get_children())
        if material:
            if hasattr(self, "cb_mat_code"):
                mat_id_str = str(material.get("id", ""))
                mat_name_str = str(material.get("name", material.get("code", "")))
                if mat_id_str and mat_name_str and mat_id_str != mat_name_str:
                    self.cb_mat_code.set(f"{mat_id_str} - {mat_name_str}")
                elif mat_name_str:
                    self.cb_mat_code.set(mat_name_str)
                elif mat_id_str:
                    self.cb_mat_code.set(mat_id_str)
            defn = material.get("type_desc", material.get("type", "como placa"))
            if defn in ("sheet", "placa", "como placa"):
                defn = "como placa"
            elif defn in ("leather", "couro", "como couro"):
                defn = "como couro"
            code = str(material.get("id") if material.get("id") is not None else material.get("code", "853412"))
            desc = str(material.get("name") or material.get("desc") or material.get("description") or "")
            if not desc and material.get("code") and material.get("id") and str(material.get("code")) != str(material.get("id")):
                desc = str(material.get("code"))
            w_m = f"{material.get('width_mm', 1380) / 1000.0:.2f}".replace('.', ',')
            l_m = f"{material.get('height_mm', 1080) / 1000.0:.2f}".replace('.', ',')
            layers = str(material.get("layers", 2))
            thick = str(material.get("thickness", material.get("thickness_mm", 0)))
            gap = str(material.get("gap", material.get("gap_mm", 1)))
            qty = str(material.get("quantity", 0))
            self.tree_mat.insert("", "end", iid="mat_0", values=("▶", code, desc, defn, w_m, l_m, layers, thick, gap, qty))
            self.tree_mat.selection_set("mat_0")
        else:
            if hasattr(self, "cb_mat_code"):
                self.cb_mat_code.set("(unspecified)")
        self.refresh_shapes_resto_column()

    def on_mat_key_press(self, event):
        if event.char and (event.char.isdigit() or event.char in ".,"):
            sel = self.tree_mat.selection()
            row_id = sel[0] if sel else "mat_0"
            self.start_cell_edit(row_id, "width", initial_char=event.char)

    def on_mat_single_click(self, event):
        if hasattr(self, "_active_commit_cb") and self._active_commit_cb:
            cb = self._active_commit_cb
            self._active_commit_cb = None
            try:
                cb()
            except Exception:
                pass

        row_id = self.tree_mat.identify_row(event.y)
        col_id = self.tree_mat.identify_column(event.x)
        if not row_id or not col_id:
            return

        if col_id in ("#0", "#1"):
            return

        self.tree_mat.selection_set(row_id)
        self.after(20, lambda: self.start_cell_edit(row_id, col_id))

    def on_mat_double_click(self, event):
        row_id = self.tree_mat.identify_row(event.y)
        col_id = self.tree_mat.identify_column(event.x)
        if not row_id:
            return
        if col_id in ("#0", "#1"):
            self.open_material_edit_dialog()
            return

        self.start_cell_edit(row_id, col_id)

    def on_mat_enter_key(self, event):
        sel = self.tree_mat.selection()
        row_id = sel[0] if sel else "mat_0"
        self.start_cell_edit(row_id, "width")

    def on_mat_f2_key(self, event):
        sel = self.tree_mat.selection()
        row_id = sel[0] if sel else "mat_0"
        self.start_cell_edit(row_id, "width")

    def dismiss_context_menu(self, event=None):
        if hasattr(self, "_active_mat_menu") and self._active_mat_menu:
            try:
                self._active_mat_menu.grab_release()
            except Exception:
                pass
            try:
                self._active_mat_menu.unpost()
            except Exception:
                pass
            self._active_mat_menu = None

    def show_mat_context_menu(self, event):
        row_id = self.tree_mat.identify_row(event.y)
        if row_id:
            self.tree_mat.selection_set(row_id)
        self.dismiss_context_menu()
        menu = tk.Menu(self, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9))
        menu.add_command(label="📝 Editar Todos os Parâmetros... (Propriedades)", command=self.open_material_edit_dialog)
        menu.add_command(label="🗑️ Remover Material da Sessão (Del)", command=self.remove_session_material)
        menu.add_separator()
        menu.add_command(label="📐 Editar Largura (m)", command=lambda: self.start_cell_edit("mat_0", "width"))
        menu.add_command(label="📏 Editar Comprimento / Altura (m)", command=lambda: self.start_cell_edit("mat_0", "len"))
        menu.add_command(label="📑 Editar Camadas", command=lambda: self.start_cell_edit("mat_0", "layers"))
        menu.add_command(label="↔️ Editar Gap (mm)", command=lambda: self.start_cell_edit("mat_0", "gap"))
        menu.add_command(label="🔢 Editar Quantidade", command=lambda: self.start_cell_edit("mat_0", "qty"))
        self._active_mat_menu = menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass

    def update_material_cell(self, col_key_or_idx, new_val):
        """Atualiza programaticamente o valor de uma coluna do material e propaga."""
        items = self.tree_mat.get_children()
        if not items:
            return
        row_id = items[0]
        cols_mat = ("sel", "code", "desc", "defn", "width", "len", "layers", "thick", "gap", "qty")
        if isinstance(col_key_or_idx, str):
            if col_key_or_idx in cols_mat:
                col_index = cols_mat.index(col_key_or_idx)
                col_key = col_key_or_idx
            elif col_key_or_idx.startswith("#"):
                try:
                    col_index = int(col_key_or_idx[1:]) - 1
                    col_key = cols_mat[col_index] if 0 <= col_index < len(cols_mat) else ""
                except ValueError:
                    return
            else:
                return
        else:
            col_index = int(col_key_or_idx)
            col_key = cols_mat[col_index] if 0 <= col_index < len(cols_mat) else ""

        curr_vals = list(self.tree_mat.item(row_id, "values"))
        new_val_str = str(new_val).strip()
        if col_key in ("width", "len") or col_index in (4, 5):
            try:
                f = float(new_val_str.replace(",", "."))
                new_val_str = f"{f:.2f}".replace(".", ",")
            except ValueError:
                pass
        elif col_key in ("layers", "qty") or col_index in (6, 9):
            try:
                new_val_str = str(int(new_val_str))
            except ValueError:
                pass
        elif col_key in ("thick", "gap") or col_index in (7, 8):
            try:
                f = float(new_val_str.replace(",", "."))
                new_val_str = f"{f:g}".replace(".", ",")
            except ValueError:
                pass

        if 0 <= col_index < len(curr_vals):
            curr_vals[col_index] = new_val_str
            self.tree_mat.item(row_id, values=curr_vals)
            self.notify_material_changed()

    def start_cell_edit(self, row_id=None, col_id=None, initial_char=None):
        if self.has_calculated_layout():
            messagebox.showwarning(
                "Material Bloqueado",
                "Não é possível editar as medidas do material enquanto o layout estiver calculado.\n\n"
                "Para alterar o material, limpe o layout atual (aba 'Layout' -> botão '🗑️ Limpar') ou refaça o cálculo.",
                parent=self
            )
            return

        if hasattr(self, "_active_commit_cb") and self._active_commit_cb:
            cb = self._active_commit_cb
            self._active_commit_cb = None
            try:
                cb()
            except Exception:
                pass

        if hasattr(self, "_active_cell_entry") and self._active_cell_entry:
            try:
                self._active_cell_entry.destroy()
            except Exception:
                pass
            self._active_cell_entry = None

        if not row_id:
            items = self.tree_mat.get_children()
            if not items:
                return
            row_id = items[0]

        cols_mat = ("sel", "code", "desc", "defn", "width", "len", "layers", "thick", "gap", "qty")
        if not col_id:
            col_id = "width"

        if isinstance(col_id, str) and col_id in cols_mat:
            col_index = cols_mat.index(col_id)
            col_key = col_id
            col_tree_id = f"#{col_index + 1}"
        elif isinstance(col_id, str) and col_id.startswith("#"):
            try:
                col_index = int(col_id[1:]) - 1
                col_key = cols_mat[col_index] if 0 <= col_index < len(cols_mat) else col_id
                col_tree_id = col_id
            except ValueError:
                return
        else:
            return

        if col_index <= 0 or col_index >= len(cols_mat):
            return

        self.update_idletasks()
        bbox = self.tree_mat.bbox(row_id, col_tree_id)
        if not bbox:
            x = 0
            for c in cols_mat[:col_index]:
                x += self.tree_mat.column(c, "width")
            w = self.tree_mat.column(col_key, "width")
            y = 22
            h = 20
        else:
            x, y, w, h = bbox

        current_values = list(self.tree_mat.item(row_id, "values"))
        if col_index >= len(current_values):
            return

        val = current_values[col_index]

        entry = tk.Entry(
            self.tree_mat,
            font=("Segoe UI", 9),
            relief="solid",
            bd=1,
            bg="#ffffd0",
            fg="#000000"
        )
        if initial_char is not None:
            entry.insert(0, str(initial_char))
            entry.icursor("end")
        else:
            entry.insert(0, str(val))
            entry.select_range(0, "end")

        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        self._active_cell_entry = entry

        committed = False

        def commit(evt=None, next_col=None):
            nonlocal committed
            if committed:
                return
            committed = True
            self._active_commit_cb = None
            if not hasattr(self, "_active_cell_entry") or self._active_cell_entry != entry:
                return

            new_val = entry.get().strip()
            self._active_cell_entry = None
            try:
                entry.destroy()
            except Exception:
                pass

            curr_vals = list(self.tree_mat.item(row_id, "values"))
            if col_key in ("width", "len") or col_index in (4, 5):
                try:
                    f = float(new_val.replace(",", "."))
                    new_val = f"{f:.2f}".replace(".", ",")
                except ValueError:
                    pass
            elif col_key in ("layers", "qty") or col_index in (6, 9):
                try:
                    new_val = str(int(new_val))
                except ValueError:
                    pass
            elif col_key in ("thick", "gap") or col_index in (7, 8):
                try:
                    f = float(new_val.replace(",", "."))
                    new_val = f"{f:g}".replace(".", ",")
                except ValueError:
                    pass

            if col_index < len(curr_vals):
                curr_vals[col_index] = new_val
                self.tree_mat.item(row_id, values=curr_vals)
                self.notify_material_changed()

            if next_col:
                self.after(20, lambda: self.start_cell_edit(row_id, next_col))

        def cancel(evt=None):
            nonlocal committed
            if committed:
                return
            committed = True
            self._active_commit_cb = None
            if hasattr(self, "_active_cell_entry") and self._active_cell_entry == entry:
                self._active_cell_entry = None
                try:
                    entry.destroy()
                except Exception:
                    pass

        def on_tab(evt):
            editable_cols = ["width", "len", "layers", "thick", "gap", "qty"]
            if col_key in editable_cols:
                curr_e_idx = editable_cols.index(col_key)
                next_col = editable_cols[(curr_e_idx + 1) % len(editable_cols)]
            else:
                next_col = "width"
            commit(next_col=next_col)
            return "break"

        def on_shift_tab(evt):
            editable_cols = ["width", "len", "layers", "thick", "gap", "qty"]
            if col_key in editable_cols:
                curr_e_idx = editable_cols.index(col_key)
                prev_col = editable_cols[(curr_e_idx - 1) % len(editable_cols)]
            else:
                prev_col = "qty"
            commit(next_col=prev_col)
            return "break"

        self._active_commit_cb = commit

        entry.bind("<Return>", lambda e: commit())
        entry.bind("<FocusOut>", lambda e: commit())
        entry.bind("<Escape>", cancel)
        entry.bind("<Tab>", on_tab)
        entry.bind("<Shift-Tab>", on_shift_tab)

    def open_material_edit_dialog(self):
        if self.has_calculated_layout():
            messagebox.showwarning(
                "Material Bloqueado",
                "Não é possível editar os parâmetros do material enquanto o layout estiver calculado.\n\n"
                "Para alterar o material, limpe o layout atual (aba 'Layout' -> botão '🗑️ Limpar') ou refaça o cálculo.",
                parent=self
            )
            return

        items = self.tree_mat.get_children()
        if not items:
            return
        row_id = items[0]
        vals = list(self.tree_mat.item(row_id, "values"))
        cols_mat = ("sel", "code", "desc", "defn", "width", "len", "layers", "thick", "gap", "qty")
        val_map = {cols_mat[i]: vals[i] for i in range(min(len(cols_mat), len(vals)))}

        dialog = tk.Toplevel(self)
        dialog.title("Propriedades do Material da Sessão")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("400x390")
        dialog.resizable(False, False)
        dialog.configure(bg=THEME["bg_card"])

        self.update_idletasks()
        rx = self.winfo_rootx() + (self.winfo_width() - 400) // 2
        ry = self.winfo_rooty() + (self.winfo_height() - 390) // 2
        dialog.geometry(f"+{max(10, rx)}+{max(10, ry)}")

        hdr = tk.Frame(dialog, bg=THEME["title_bar_bg"], height=28, padx=8, pady=4)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Definição de Material e Dimensões do Layout", bg=THEME["title_bar_bg"], fg=THEME["title_bar_fg"], font=("Segoe UI", 9, "bold")).pack(side="left")

        body = tk.Frame(dialog, bg=THEME["bg_card"], padx=14, pady=12)
        body.pack(fill="both", expand=True)

        fields = [
            ("Código do Material:", val_map.get("code", "853412")),
            ("Descrição:", val_map.get("desc", "SINT-LOGAM-PRETO")),
            ("Definição / Tipo:", val_map.get("defn", "como placa")),
            ("Largura (m):", val_map.get("width", "1,38")),
            ("Comprimento / Altura (m):", val_map.get("len", "1,08")),
            ("Camadas de corte:", val_map.get("layers", "2")),
            ("Espessura (%1):", val_map.get("thick", "0")),
            ("Gap / Distância entre peças (mm):", val_map.get("gap", "1")),
            ("Quantidade:", val_map.get("qty", "0")),
        ]

        entries = {}
        for row_idx, (lbl_txt, init_val) in enumerate(fields):
            tk.Label(body, text=lbl_txt, bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").grid(row=row_idx, column=0, sticky="w", pady=3)
            ent = tk.Entry(body, font=("Segoe UI", 9), relief="sunken", bd=2, width=20)
            ent.insert(0, str(init_val))
            ent.grid(row=row_idx, column=1, sticky="e", pady=3, padx=(10, 0))
            entries[row_idx] = ent

        btn_box = tk.Frame(dialog, bg=THEME["bg_card"], pady=8)
        btn_box.pack(fill="x", padx=14)

        def save():
            new_vals = [
                "▶",
                entries[0].get().strip(),
                entries[1].get().strip(),
                entries[2].get().strip(),
                entries[3].get().strip().replace(".", ","),
                entries[4].get().strip().replace(".", ","),
                entries[5].get().strip(),
                entries[6].get().strip(),
                entries[7].get().strip(),
                entries[8].get().strip(),
            ]
            self.tree_mat.item(row_id, values=new_vals)
            self.notify_material_changed()
            dialog.destroy()

        btn_ok = tk.Button(btn_box, text="OK", width=10, relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9, "bold"), command=save)
        btn_ok.pack(side="right", padx=4)
        btn_can = tk.Button(btn_box, text="Cancelar", width=10, relief="raised", bd=2, bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), command=dialog.destroy)
        btn_can.pack(side="right", padx=4)

        dialog.bind("<Return>", lambda e: save())
        dialog.bind("<Escape>", lambda e: dialog.destroy())

    def notify_material_changed(self):
        items = self.tree_mat.get_children()
        if not items:
            return
        row_vals = self.tree_mat.item(items[0], "values")
        cols_mat = ("sel", "code", "desc", "defn", "width", "len", "layers", "thick", "gap", "qty")
        val_map = {cols_mat[i]: row_vals[i] for i in range(min(len(cols_mat), len(row_vals)))}
        try:
            code = str(val_map.get("code", "853412"))
            desc = str(val_map.get("desc", ""))
            defn = str(val_map.get("defn", "como placa"))
            w_m = float(str(val_map.get("width", "1,38")).replace(",", "."))
            l_m = float(str(val_map.get("len", "1,08")).replace(",", "."))
            layers = int(str(val_map.get("layers", 2)))
            thick = float(str(val_map.get("thick", 0)).replace(",", "."))
            gap = float(str(val_map.get("gap", 1)).replace(",", "."))
            qty = int(str(val_map.get("qty", 0)))
        except (ValueError, IndexError):
            return

        mat_dict = {
            "type": defn,
            "code": code,
            "id": code,
            "name": desc,
            "description": desc,
            "width_m": w_m,
            "length_m": l_m,
            "width_mm": w_m * 1000.0,
            "height_mm": l_m * 1000.0,
            "layers": layers,
            "thickness": thick,
            "gap": gap,
            "quantity": qty,
            "area_m2": round(w_m * l_m, 4)
        }

        if hasattr(self, "session_data") and self.session_data:
            self.session_data["material"] = mat_dict
            layouts_cnt = len(self.session_data.get("placed_pieces", []))
            yield_pct = self.session_data.get("yield_percent", 0.0)
            est_sec = self.session_data.get("cutting_time_sec", 0.0)
            self.update_summary_text(layouts_cnt, yield_pct, est_sec)

        if self.on_material_change_cb:
            self.on_material_change_cb(mat_dict)

        self.refresh_shapes_resto_column()

    def get_session_layers(self) -> int:
        """Retorna o número de camadas de corte do material da sessão.
        Lê da tabela de Materiais ou dos dados da sessão. Se indefinido ou <= 0, retorna 0."""
        if hasattr(self, "tree_mat"):
            items = self.tree_mat.get_children()
            if items:
                vals = self.tree_mat.item(items[0], "values")
                if len(vals) >= 7:
                    try:
                        v = str(vals[6]).strip()
                        if v:
                            return max(0, int(v))
                    except (ValueError, TypeError):
                        pass
        if hasattr(self, "session_data") and isinstance(self.session_data, dict):
            mat = self.session_data.get("material")
            if isinstance(mat, dict):
                try:
                    v = mat.get("layers")
                    if v is not None and str(v).strip():
                        return max(0, int(v))
                except (ValueError, TypeError):
                    pass
        return 0

    def refresh_shapes_resto_column(self):
        """Recalcula e atualiza a coluna Resto de todas as linhas de moldes na grade."""
        if not hasattr(self, "tree_shapes") or not hasattr(self, "shapes_list"):
            return
        layers = self.get_session_layers()
        for idx, s in enumerate(self.shapes_list):
            row_id = str(idx)
            try:
                p = int(s.get("pairs", 16))
            except Exception:
                p = 16
            r_val = calc_resto(p, layers)
            try:
                self.tree_shapes.set(row_id, "resto", str(r_val))
            except Exception:
                pass


    def set_shapes_data(self, shapes, preserve_id=None):
        self.shapes_list = list(shapes or [])

        # Garante atributos numéricos sequence, pairs e color em cada molde
        for i, s in enumerate(self.shapes_list, start=1):
            s_size = str(s.get("size") or s.get("name") or "41")
            s["color"] = get_color_for_size(s_size, i)

            if "sequence" not in s or s["sequence"] is None:
                s["sequence"] = i
            else:
                try:
                    s["sequence"] = int(s["sequence"])
                except Exception:
                    s["sequence"] = i

            if "pairs" not in s or s["pairs"] is None:
                s["pairs"] = 16
            else:
                try:
                    s["pairs"] = int(s["pairs"])
                except Exception:
                    s["pairs"] = 16

        # Ordena estritamente pela sequência de geração
        self.shapes_list.sort(key=lambda s: int(s.get("sequence", 999)))

        self.tree_shapes.delete(*self.tree_shapes.get_children())
        layers = self.get_session_layers()
        for idx, s in enumerate(self.shapes_list, start=1):
            s_id = str(s.get("id", idx))
            percurso = str(s.get("folder") or "Externo")
            s_size = str(s.get("size", "41"))
            clr = s.get("color") or get_color_for_size(s_size, idx)
            color_badge = get_color_emoji(clr)
            tamanho = f"{color_badge} {s_size}"
            molde_nome = str(s.get("name", f"Shape #{idx}"))
            pares = str(s.get("pairs", 16))
            resto = str(calc_resto(s.get("pairs", 16), layers))
            seq = str(s.get("sequence", idx))
            self.tree_shapes.insert(
                "", "end", iid=str(idx - 1),
                values=(s_id, percurso, tamanho, molde_nome, pares, resto, seq)
            )

        if self.shapes_list:
            sel_idx = 0
            if preserve_id is not None:
                for i, s in enumerate(self.shapes_list):
                    if s.get("id") == preserve_id:
                        sel_idx = i
                        break
            self.tree_shapes.selection_set(str(sel_idx))
            self.tree_shapes.focus(str(sel_idx))
            self.tree_shapes.see(str(sel_idx))
            self.draw_preview_shape(self.shapes_list[sel_idx])
        else:
            self.preview_canvas.delete("all")
            # Mensagem suave quando a sessão estiver sem moldes
            cw = self.preview_canvas.winfo_width()
            ch = self.preview_canvas.winfo_height()
            if cw < 50: cw = 310
            if ch < 50: ch = 360
            self.preview_canvas.create_text(
                cw // 2, ch // 2,
                text="Aba Moldes em branco.\n\nClique em '➕ Adicionar Molde...'\nou '📂 Importar .die...'\npara adicionar moldes a esta sessão.",
                fill="#9ca3af",
                font=("Segoe UI", 9, "italic"),
                justify="center"
            )

    def spawn_tree_inline_editor(self, row_id, col, initial_char=None):
        """Abre uma caixa de edição inline diretamente sobre a célula do Treeview (Pares ou Sequência),
        com suporte a navegação contínua por setas (Cima/Baixo), Enter e substituição imediata."""
        if not row_id or col not in ("#5", "#7"):
            return

        try:
            idx = int(row_id)
            if idx < 0 or idx >= len(self.shapes_list):
                return
            target = self.shapes_list[idx]
        except (ValueError, IndexError):
            return

        # Garante que a linha esteja visível no viewport antes de calcular a geometria
        self.tree_shapes.see(row_id)
        self.tree_shapes.update_idletasks()

        bbox = self.tree_shapes.bbox(row_id, col)
        if not bbox:
            return
        x, y, w, h = bbox

        # Se já existir um editor aberto, destrói com segurança
        if hasattr(self, "_inline_editor") and self._inline_editor:
            try:
                self._inline_editor.destroy()
            except Exception:
                pass
            self._inline_editor = None

        is_pairs = (col == "#5")
        col_key = "pares" if is_pairs else "sequencia"
        initial_val = str(target.get("pairs", 16)) if is_pairs else str(target.get("sequence", idx + 1))

        entry = tk.Entry(
            self.tree_shapes,
            justify="center",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#000080",
            relief="solid",
            bd=1
        )
        if initial_char is not None and str(initial_char).isdigit():
            entry.insert(0, str(initial_char))
            entry.icursor("end")
        else:
            entry.insert(0, initial_val)
            entry.select_range(0, "end")
            entry.icursor("end")

        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        self._inline_editor = entry

        state = {"navigating": False, "saved": False}

        def save_current_value():
            if state["saved"]:
                return
            val_str = entry.get().strip()
            cleaned = "".join(ch for ch in val_str if ch.isdigit())
            try:
                val_int = max(1, int(cleaned)) if cleaned else max(1, int(initial_val))
            except Exception:
                val_int = 16 if is_pairs else 1

            if is_pairs:
                target["pairs"] = val_int
            else:
                target["sequence"] = val_int

            try:
                self.tree_shapes.set(row_id, col_key, str(val_int))
                if is_pairs:
                    layers = self.get_session_layers()
                    r_val = calc_resto(val_int, layers)
                    self.tree_shapes.set(row_id, "resto", str(r_val))
            except Exception:
                pass

            if self.on_add_shapes_cb and self.session_data:
                try:
                    self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)
                except Exception:
                    pass
            state["saved"] = True

        def close_editor():
            if hasattr(self, "_inline_editor") and self._inline_editor == entry:
                self._inline_editor = None
            try:
                entry.destroy()
            except Exception:
                pass

        def move_down(event=None):
            if state["navigating"]:
                return "break"
            state["navigating"] = True
            save_current_value()
            close_editor()

            children = list(self.tree_shapes.get_children())
            if row_id in children:
                pos = children.index(row_id)
                if pos + 1 < len(children):
                    next_row_id = children[pos + 1]
                    self.tree_shapes.selection_set(next_row_id)
                    self.tree_shapes.focus(next_row_id)
                    self.tree_shapes.see(next_row_id)
                    try:
                        self.draw_preview_shape(self.shapes_list[int(next_row_id)])
                    except Exception:
                        pass
                    self.after(30, lambda: self.spawn_tree_inline_editor(next_row_id, col))
                else:
                    self.tree_shapes.selection_set(row_id)
                    self.tree_shapes.focus(row_id)
            return "break"

        def move_up(event=None):
            if state["navigating"]:
                return "break"
            state["navigating"] = True
            save_current_value()
            close_editor()

            children = list(self.tree_shapes.get_children())
            if row_id in children:
                pos = children.index(row_id)
                if pos - 1 >= 0:
                    prev_row_id = children[pos - 1]
                    self.tree_shapes.selection_set(prev_row_id)
                    self.tree_shapes.focus(prev_row_id)
                    self.tree_shapes.see(prev_row_id)
                    try:
                        self.draw_preview_shape(self.shapes_list[int(prev_row_id)])
                    except Exception:
                        pass
                    self.after(30, lambda: self.spawn_tree_inline_editor(prev_row_id, col))
                else:
                    self.tree_shapes.selection_set(row_id)
                    self.tree_shapes.focus(row_id)
            return "break"

        def move_next_col(event=None):
            if state["navigating"]:
                return "break"
            state["navigating"] = True
            save_current_value()
            close_editor()

            children = list(self.tree_shapes.get_children())
            if row_id in children:
                pos = children.index(row_id)
                if col == "#5":
                    # Pula Resto (#6) e vai direto para Sequência (#7) na mesma linha
                    self.tree_shapes.selection_set(row_id)
                    self.tree_shapes.focus(row_id)
                    self.after(30, lambda: self.spawn_tree_inline_editor(row_id, "#7"))
                else:
                    # De Sequência (#7), avança para Pares (#5) da próxima linha
                    if pos + 1 < len(children):
                        next_row_id = children[pos + 1]
                        self.tree_shapes.selection_set(next_row_id)
                        self.tree_shapes.focus(next_row_id)
                        self.tree_shapes.see(next_row_id)
                        try:
                            self.draw_preview_shape(self.shapes_list[int(next_row_id)])
                        except Exception:
                            pass
                        self.after(30, lambda: self.spawn_tree_inline_editor(next_row_id, "#5"))
                    else:
                        self.tree_shapes.selection_set(row_id)
                        self.tree_shapes.focus(row_id)
            return "break"

        def move_prev_col(event=None):
            if state["navigating"]:
                return "break"
            state["navigating"] = True
            save_current_value()
            close_editor()

            children = list(self.tree_shapes.get_children())
            if row_id in children:
                pos = children.index(row_id)
                if col == "#7":
                    # Volta de Sequência (#7) direto para Pares (#5) na mesma linha (pula #6)
                    self.tree_shapes.selection_set(row_id)
                    self.tree_shapes.focus(row_id)
                    self.after(30, lambda: self.spawn_tree_inline_editor(row_id, "#5"))
                else:
                    # De Pares (#5), volta para Sequência (#7) da linha anterior
                    if pos - 1 >= 0:
                        prev_row_id = children[pos - 1]
                        self.tree_shapes.selection_set(prev_row_id)
                        self.tree_shapes.focus(prev_row_id)
                        self.tree_shapes.see(prev_row_id)
                        try:
                            self.draw_preview_shape(self.shapes_list[int(prev_row_id)])
                        except Exception:
                            pass
                        self.after(30, lambda: self.spawn_tree_inline_editor(prev_row_id, "#7"))
                    else:
                        self.tree_shapes.selection_set(row_id)
                        self.tree_shapes.focus(row_id)
            return "break"

        def adjust_number(delta):
            val_str = entry.get().strip()
            cleaned = "".join(ch for ch in val_str if ch.isdigit())
            try:
                cur = int(cleaned) if cleaned else (16 if is_pairs else 1)
            except Exception:
                cur = 16 if is_pairs else 1
            new_val = max(1, cur + delta)
            entry.delete(0, "end")
            entry.insert(0, str(new_val))
            entry.select_range(0, "end")
            return "break"

        def on_focus_out(event=None):
            if state["navigating"]:
                return
            save_current_value()
            close_editor()

        def cancel_edit(event=None):
            state["navigating"] = True
            close_editor()
            self.tree_shapes.selection_set(row_id)
            self.tree_shapes.focus(row_id)
            return "break"

        # Atalhos do editor inline: Down e Up navegam entre linhas para digitação contínua
        entry.bind("<Down>", move_down)
        entry.bind("<KP_Down>", move_down)
        entry.bind("<Up>", move_up)
        entry.bind("<KP_Up>", move_up)
        entry.bind("<Return>", move_down)
        entry.bind("<KP_Enter>", move_down)
        entry.bind("<Shift-Return>", move_up)
        entry.bind("<Tab>", move_next_col)
        entry.bind("<Shift-Tab>", move_prev_col)
        entry.bind("<ISO_Left_Tab>", move_prev_col)
        entry.bind("<Escape>", cancel_edit)
        entry.bind("<FocusOut>", on_focus_out)

        # Teclas de ajuste rápido (incremento/decremento com Ctrl/Alt)
        entry.bind("<Control-Up>", lambda e: adjust_number(+1))
        entry.bind("<Control-Down>", lambda e: adjust_number(-1))
        entry.bind("<Alt-Up>", lambda e: adjust_number(+1))
        entry.bind("<Alt-Down>", lambda e: adjust_number(-1))

    def on_tree_shape_enter(self, event=None):
        sel = self.tree_shapes.selection()
        if sel:
            self.spawn_tree_inline_editor(sel[0], "#5")
            return "break"

    def on_tree_shape_f2(self, event=None):
        sel = self.tree_shapes.selection()
        if sel:
            self.spawn_tree_inline_editor(sel[0], "#5")
            return "break"

    def on_tree_shape_key(self, event):
        if event.char and event.char.isdigit():
            sel = self.tree_shapes.selection()
            if sel:
                self.spawn_tree_inline_editor(sel[0], "#5", initial_char=event.char)
                return "break"

    def on_tree_shape_cell_click(self, event):
        """Ao clicar diretamente na célula de Pares (#5) ou Sequência (#7), abre a edição inline."""
        region = self.tree_shapes.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree_shapes.identify_column(event.x)
        row_id = self.tree_shapes.identify_row(event.y)
        if row_id and col in ("#5", "#7"):
            self.after(60, lambda: self.spawn_tree_inline_editor(row_id, col))

    def on_tree_shape_double_click(self, event):
        """Duplo clique: se for na célula de pares/sequência edita inline, senão abre a janela completa de configuração."""
        col = self.tree_shapes.identify_column(event.x)
        row_id = self.tree_shapes.identify_row(event.y)
        if row_id and col in ("#5", "#7"):
            self.spawn_tree_inline_editor(row_id, col)
            return "break"
        elif row_id:
            try:
                idx = int(row_id)
                self.open_edit_selected_shape_dialog(idx)
            except Exception:
                pass
            return "break"

    def change_selected_shape_pairs(self):
        sel = self.tree_shapes.selection()
        if not sel or not self.shapes_list:
            return
        try:
            idx = int(sel[0])
            target = self.shapes_list[idx]
            curr_p = target.get("pairs", 16)
            new_p = simpledialog.askinteger(
                "Pares a Cortar",
                f"Definir quantidade de pares para '{target.get('name')}':",
                initialvalue=curr_p,
                minvalue=1,
                maxvalue=9999,
                parent=self
            )
            if new_p is not None:
                target["pairs"] = new_p
                self.set_shapes_data(self.shapes_list)
                self.tree_shapes.selection_set(str(idx))
                if self.on_add_shapes_cb:
                    self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)
        except Exception:
            pass

    def change_selected_shape_sequence(self):
        sel = self.tree_shapes.selection()
        if not sel or not self.shapes_list:
            return
        try:
            idx = int(sel[0])
            target = self.shapes_list[idx]
            curr_seq = target.get("sequence", idx + 1)
            new_seq = simpledialog.askinteger(
                "Sequência de Geração",
                f"Definir ordem/sequência de geração para '{target.get('name')}':\n(1 = prioridade máxima)",
                initialvalue=curr_seq,
                minvalue=1,
                maxvalue=999,
                parent=self
            )
            if new_seq is not None:
                target["sequence"] = new_seq
                self.shapes_list.sort(key=lambda s: int(s.get("sequence", 999)))
                self.set_shapes_data(self.shapes_list)
                if self.on_add_shapes_cb:
                    self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)
        except Exception:
            pass

    def change_selected_shape_color(self):
        sel = self.tree_shapes.selection()
        if not sel or not self.shapes_list:
            return
        try:
            idx = int(sel[0])
            target = self.shapes_list[idx]
            s_size = str(target.get("size", "41"))
            cur_col = target.get("color") or get_color_for_size(s_size, idx)
            chosen = colorchooser.askcolor(
                color=cur_col,
                title=f"Escolher Cor para o Número {s_size} ({target.get('name')})",
                parent=self
            )
            if chosen and chosen[1]:
                target["color"] = chosen[1]
                self.set_shapes_data(self.shapes_list)
                self.tree_shapes.selection_set(str(idx))
                self.tree_shapes.focus(str(idx))
                if self.on_add_shapes_cb:
                    self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)
        except Exception:
            pass

    def move_selected_shape_up(self):
        sel = self.tree_shapes.selection()
        if not sel or not self.shapes_list:
            return
        try:
            idx = int(sel[0])
            if idx <= 0:
                return
            s_curr = self.shapes_list[idx]
            s_prev = self.shapes_list[idx - 1]
            seq_curr = s_curr.get("sequence", idx + 1)
            seq_prev = s_prev.get("sequence", idx)

            if seq_curr == seq_prev:
                s_curr["sequence"] = idx
                s_prev["sequence"] = idx + 1
            else:
                s_curr["sequence"] = seq_prev
                s_prev["sequence"] = seq_curr

            self.shapes_list[idx], self.shapes_list[idx - 1] = self.shapes_list[idx - 1], self.shapes_list[idx]
            self.set_shapes_data(self.shapes_list)
            self.tree_shapes.selection_set(str(idx - 1))
            self.tree_shapes.focus(str(idx - 1))
            if self.on_add_shapes_cb:
                self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)
        except Exception:
            pass

    def move_selected_shape_down(self):
        sel = self.tree_shapes.selection()
        if not sel or not self.shapes_list:
            return
        try:
            idx = int(sel[0])
            if idx >= len(self.shapes_list) - 1:
                return
            s_curr = self.shapes_list[idx]
            s_next = self.shapes_list[idx + 1]
            seq_curr = s_curr.get("sequence", idx + 1)
            seq_next = s_next.get("sequence", idx + 2)

            if seq_curr == seq_next:
                s_curr["sequence"] = idx + 2
                s_next["sequence"] = idx + 1
            else:
                s_curr["sequence"] = seq_next
                s_next["sequence"] = seq_curr

            self.shapes_list[idx], self.shapes_list[idx + 1] = self.shapes_list[idx + 1], self.shapes_list[idx]
            self.set_shapes_data(self.shapes_list)
            self.tree_shapes.selection_set(str(idx + 1))
            self.tree_shapes.focus(str(idx + 1))
            if self.on_add_shapes_cb:
                self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)
        except Exception:
            pass

    def show_sort_menu(self, event=None):
        """Exibe menu dropdown/popup com opções rápidas de classificação de moldes e tamanhos."""
        menu = tk.Menu(self, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
        menu.add_command(
            label="🔽 Tamanho: Maior → Menor (ex: 36a → 22a)",
            command=lambda: self.sort_shapes_by("tamanho", force_desc=True)
        )
        menu.add_command(
            label="🔼 Tamanho: Menor → Maior (ex: 22a → 36a)",
            command=lambda: self.sort_shapes_by("tamanho", force_desc=False)
        )
        menu.add_separator()
        menu.add_command(
            label="🔽 Molde: Maior → Menor (Z → A)",
            command=lambda: self.sort_shapes_by("molde", force_desc=True)
        )
        menu.add_command(
            label="🔼 Molde: Menor → Maior (A → Z)",
            command=lambda: self.sort_shapes_by("molde", force_desc=False)
        )
        menu.add_separator()
        menu.add_command(
            label="📐 Área da Peça: Maior → Menor (peças maiores primeiro)",
            command=lambda: self.sort_shapes_by("area", force_desc=True)
        )
        menu.add_command(
            label="📐 Área da Peça: Menor → Maior (peças menores primeiro)",
            command=lambda: self.sort_shapes_by("area", force_desc=False)
        )
        menu.add_separator()
        menu.add_command(
            label="🔢 Sequência: 1 → N",
            command=lambda: self.sort_shapes_by("sequencia", force_desc=False)
        )

        if event:
            x, y = event.x_root, event.y_root
        elif hasattr(self, "btn_sort") and self.btn_sort.winfo_ismapped():
            x = self.btn_sort.winfo_rootx()
            y = self.btn_sort.winfo_rooty() - 210
            if y < 10:
                y = self.btn_sort.winfo_rooty() + self.btn_sort.winfo_height()
        else:
            x = self.winfo_rootx() + 50
            y = self.winfo_rooty() + 50

        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def sort_shapes_by(self, col, force_desc=None):
        """Classifica os moldes da sessão pelo campo especificado e atualiza a sequência de corte/produção."""
        if not self.shapes_list:
            return

        if force_desc is not None:
            desc = force_desc
        elif self.shape_sort_col == col:
            desc = not self.shape_sort_desc
        else:
            # Padrão: maior para o menor para tamanho, molde, pares, resto e área
            desc = True if col in ("tamanho", "molde", "pares", "resto", "area") else False

        self.shape_sort_col = col
        self.shape_sort_desc = desc

        # Preserva ID do molde selecionado
        selected_shape_id = None
        sel = self.tree_shapes.selection()
        if sel:
            try:
                selected_shape_id = self.shapes_list[int(sel[0])].get("id")
            except Exception:
                pass

        if col == "tamanho":
            self.shapes_list.sort(key=lambda s: size_sort_key(s.get("size"), s.get("name")), reverse=desc)
        elif col == "molde":
            self.shapes_list.sort(key=lambda s: natural_sort_key(s.get("name")), reverse=desc)
        elif col == "pares":
            self.shapes_list.sort(key=lambda s: int(s.get("pairs", 0)), reverse=desc)
        elif col == "resto":
            layers = self.get_session_layers()
            self.shapes_list.sort(key=lambda s: resto_sort_key(calc_resto(s.get("pairs", 16), layers)), reverse=desc)
        elif col == "area":
            self.shapes_list.sort(key=lambda s: shape_area_sort_key(s), reverse=desc)
        elif col == "percurso":
            self.shapes_list.sort(key=lambda s: natural_sort_key(s.get("folder") or "Externo"), reverse=desc)
        elif col == "shape_id":
            self.shapes_list.sort(key=lambda s: int(s.get("id", 0)) if str(s.get("id", "")).isdigit() else natural_sort_key(s.get("id")), reverse=desc)
        elif col == "sequencia":
            self.shapes_list.sort(key=lambda s: int(s.get("sequence", 999)), reverse=desc)
        else:
            self.shapes_list.sort(key=lambda s: natural_sort_key(s.get(col, "")), reverse=desc)

        # Atualiza a numeração de sequência de geração (1, 2, 3...)
        for i, s in enumerate(self.shapes_list, start=1):
            s["sequence"] = i

        # Atualiza os cabeçalhos com o indicador visual de seta ▲ / ▼
        arrow = " ▼" if desc else " ▲"
        headers = {
            "shape_id": "ShapeId",
            "percurso": "Percurso",
            "tamanho": "Tama...",
            "molde": "Molde",
            "pares": "Pares...",
            "resto": "Resto",
            "sequencia": "Sequência /"
        }
        for c_name, c_text in headers.items():
            if c_name == col:
                self.tree_shapes.heading(c_name, text=c_text + arrow)
            else:
                self.tree_shapes.heading(c_name, text=c_text)

        # Renderiza a lista na treeview preservando o item selecionado
        self.set_shapes_data(self.shapes_list, preserve_id=selected_shape_id)

        # Persiste a ordem atualizada na sessão (MySQL / SQLite)
        if self.on_add_shapes_cb and self.session_data:
            self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)

    def open_edit_selected_shape_dialog(self, shape_idx=None):
        if shape_idx is None:
            sel = self.tree_shapes.selection()
            if not sel or not self.shapes_list:
                return
            try:
                shape_idx = int(sel[0])
            except Exception:
                return

        if 0 <= shape_idx < len(self.shapes_list):
            target = self.shapes_list[shape_idx]

            def on_save_cb(updated_shape):
                self.shapes_list.sort(key=lambda s: int(s.get("sequence", 999)))
                self.set_shapes_data(self.shapes_list)
                if self.on_add_shapes_cb:
                    self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)

            def on_open_editor_cb(shp):
                if self.on_edit_shape_cb:
                    self.on_edit_shape_cb(shp)

            EditShapeInSessionDialog(self, target, on_save_callback=on_save_cb, on_open_editor_callback=on_open_editor_cb)

    def on_add_shape_click(self):
        catalog = getattr(self, "all_shapes_catalog", [])
        AddShapesDialog(
            self,
            all_shapes=catalog,
            current_session_shapes=self.shapes_list,
            on_add_callback=self.on_shapes_added_from_dialog
        )

    def on_shapes_added_from_dialog(self, new_shapes):
        existing_ids = {s.get("id") for s in self.shapes_list if s.get("id")}
        for s in new_shapes:
            if s.get("id") not in existing_ids:
                if "sequence" not in s:
                    s["sequence"] = len(self.shapes_list) + 1
                self.shapes_list.append(s)
                existing_ids.add(s.get("id"))
            else:
                for i, curr in enumerate(self.shapes_list):
                    if curr.get("id") == s.get("id"):
                        self.shapes_list[i]["pairs"] = s.get("pairs", curr.get("pairs", 16))
                        break

        self.set_shapes_data(self.shapes_list)
        if self.on_add_shapes_cb:
            self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)

    def add_shape(self, shape_dict):
        """Adiciona um único molde diretamente à sessão (ex: via Drag & Drop ou Import)."""
        if not shape_dict:
            return
        self.add_shapes([shape_dict])

    def add_shapes(self, shapes_list):
        """Adiciona múltiplos moldes de uma só vez (ex: arrastar grade completa de numerações)."""
        if not shapes_list:
            return
        existing_ids = {s.get("id") for s in self.shapes_list if s.get("id")}
        for shape_dict in shapes_list:
            if not shape_dict:
                continue
            s_copy = dict(shape_dict)
            if s_copy.get("id") not in existing_ids:
                if "sequence" not in s_copy:
                    s_copy["sequence"] = len(self.shapes_list) + 1
                self.shapes_list.append(s_copy)
                existing_ids.add(s_copy.get("id"))
            else:
                for i, curr in enumerate(self.shapes_list):
                    if curr.get("id") == s_copy.get("id"):
                        self.shapes_list[i] = s_copy
                        break
        self.set_shapes_data(self.shapes_list)
        if self.on_add_shapes_cb:
            self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)

    def on_shape_selected(self, event):
        sel = self.tree_shapes.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
            if 0 <= idx < len(self.shapes_list):
                self.draw_preview_shape(self.shapes_list[idx])
        except (ValueError, IndexError):
            pass

    def on_edit_button_click(self):
        sel = self.tree_shapes.selection()
        if not sel or not self.shapes_list:
            return
        try:
            idx = int(sel[0])
            if 0 <= idx < len(self.shapes_list) and self.on_edit_shape_cb:
                self.on_edit_shape_cb(self.shapes_list[idx])
        except (ValueError, IndexError):
            pass

    def on_import_button_click(self):
        if self.on_import_die_cb:
            self.on_import_die_cb()

    def _on_tree_shapes_delete(self):
        self.delete_selected_shape()
        return "break"

    def show_shapes_context_menu(self, event):
        if event.widget == self.tree_shapes:
            iid = self.tree_shapes.identify_row(event.y)
            if iid:
                curr_sel = self.tree_shapes.selection()
                if iid not in curr_sel:
                    self.tree_shapes.selection_set(iid)
        menu = tk.Menu(self, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
        menu.add_command(label="➕ Adicionar Molde do Catálogo...", command=self.on_add_shape_click)
        menu.add_command(label="📂 Importar .die...", command=self.on_import_button_click)
        if self.tree_shapes.selection() and self.shapes_list:
            menu.add_separator()
            menu.add_command(label="✏️ Alterar Quantidade de Pares...", command=self.change_selected_shape_pairs)
            menu.add_command(label="🔢 Alterar Sequência de Geração...", command=self.change_selected_shape_sequence)
            menu.add_command(label="⬆️ Mover Sequência para Cima", command=self.move_selected_shape_up)
            menu.add_command(label="⬇️ Mover Sequência para Baixo", command=self.move_selected_shape_down)
            menu.add_separator()
            menu.add_command(label="🎨 Alterar Cor do Número...", command=self.change_selected_shape_color)
            menu.add_command(label="⚙️ Configurar Molde na Sessão...", command=self.open_edit_selected_shape_dialog)
            menu.add_command(label="📐 Abrir no Shape Editor", command=self.on_edit_button_click)
            menu.add_separator()
            sort_sub = tk.Menu(menu, tearoff=0, bg=THEME["bg_surface"], fg=THEME["text_main"], activebackground=THEME["select_bg"], activeforeground=THEME["select_fg"])
            sort_sub.add_command(label="🔽 Tamanho: Maior → Menor (ex: 36a → 22a)", command=lambda: self.sort_shapes_by("tamanho", force_desc=True))
            sort_sub.add_command(label="🔼 Tamanho: Menor → Maior (ex: 22a → 36a)", command=lambda: self.sort_shapes_by("tamanho", force_desc=False))
            sort_sub.add_separator()
            sort_sub.add_command(label="🔽 Molde: Maior → Menor (Z → A)", command=lambda: self.sort_shapes_by("molde", force_desc=True))
            sort_sub.add_command(label="🔼 Molde: Menor → Maior (A → Z)", command=lambda: self.sort_shapes_by("molde", force_desc=False))
            sort_sub.add_separator()
            sort_sub.add_command(label="📐 Área da Peça: Maior → Menor", command=lambda: self.sort_shapes_by("area", force_desc=True))
            sort_sub.add_command(label="📐 Área da Peça: Menor → Maior", command=lambda: self.sort_shapes_by("area", force_desc=False))
            sort_sub.add_separator()
            sort_sub.add_command(label="🔢 Sequência: 1 → N", command=lambda: self.sort_shapes_by("sequencia", force_desc=False))
            menu.add_cascade(label="📊 Classificar Moldes...", menu=sort_sub)
            menu.add_separator()
            sel_count = len(self.tree_shapes.selection())
            del_label = f"🗑️ Remover {sel_count} Moldes da Sessão" if sel_count > 1 else "🗑️ Remover Molde da Sessão"
            menu.add_command(label=del_label, command=self.delete_selected_shape)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def delete_selected_shape(self):
        sel = self.tree_shapes.selection()
        if not sel or not self.shapes_list:
            return
        try:
            # Coleta todos os índices válidos da seleção
            indices_to_remove = set()
            for item in sel:
                try:
                    idx = int(item)
                    if 0 <= idx < len(self.shapes_list):
                        indices_to_remove.add(idx)
                except (ValueError, TypeError):
                    vals = self.tree_shapes.item(item, "values")
                    if vals and len(vals) > 0:
                        sid = str(vals[0])
                        for i, s in enumerate(self.shapes_list):
                            if str(s.get("id")) == sid:
                                indices_to_remove.add(i)
                                break

            if not indices_to_remove:
                return

            count = len(indices_to_remove)
            if count == 1:
                idx = next(iter(indices_to_remove))
                target = self.shapes_list[idx]
                shp_name = target.get("name", "Molde")
                msg = (
                    f"Deseja remover o molde '{shp_name}' desta sessão de corte?\n\n"
                    f"(O molde continuará disponível no catálogo geral)"
                )
                title = "Remover Molde da Sessão"
            else:
                msg = (
                    f"Deseja remover os {count} moldes selecionados desta sessão de corte?\n\n"
                    f"(Os moldes continuarão disponíveis no catálogo geral)"
                )
                title = "Remover Moldes da Sessão"

            if messagebox.askyesno(title, msg, parent=self):
                # Filtra mantendo apenas os moldes não removidos
                self.shapes_list = [s for i, s in enumerate(self.shapes_list) if i not in indices_to_remove]

                # Reatribui sequência ordenada 1..N
                for i, s in enumerate(self.shapes_list, start=1):
                    s["sequence"] = i

                self.set_shapes_data(self.shapes_list)
                if not self.shapes_list:
                    self.draw_preview_shape(None)

                if self.on_add_shapes_cb:
                    self.on_add_shapes_cb(self.session_data.get("id"), self.shapes_list)
        except Exception:
            pass

    def draw_preview_shape(self, shape):
        self.current_preview_shape = shape
        self.preview_canvas.delete("all")
        if not shape:
            return

        contour = shape.get("contour", [])
        if not contour or len(contour) < 3:
            return

        w = self.preview_canvas.winfo_width()
        h = self.preview_canvas.winfo_height()
        if w < 50:
            w = 310
        if h < 50:
            h = 360

        xs = [pt["x"] for pt in contour]
        ys = [pt["y"] for pt in contour]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cw = max(1.0, max_x - min_x)
        ch = max(1.0, max_y - min_y)

        # Margens confortáveis para visualização ampla e limpa (como em media_1792070997258.jpg)
        pad = 25
        scale = min((w - pad * 2) / cw, (h - pad * 2) / ch)
        ox = (w - cw * scale) / 2 - min_x * scale
        oy = (h - ch * scale) / 2 - min_y * scale

        coords = []
        for pt in contour:
            coords.extend([pt["x"] * scale + ox, pt["y"] * scale + oy])

        # Fundo do molde preenchido com a cor do seu número/tamanho
        shape_color = get_color_for_size(shape.get("size") or shape.get("name") or "41")

        self.preview_canvas.create_polygon(
            coords,
            fill=shape_color,
            outline="#000000",
            width=1.5
        )

        # Furações no preview (fundo branco #ffffff vazado com borda preta)
        for hole in shape.get("holes", []):
            hx = hole["x"] * scale + ox
            hy = hole["y"] * scale + oy
            hr = max(2, min(5, int(hole.get("r", 3.0) * scale)))
            self.preview_canvas.create_oval(
                hx - hr, hy - hr, hx + hr, hy + hr,
                fill="#ffffff",
                outline="#000000",
                width=1
            )

    def _on_preview_resize(self):
        if hasattr(self, "current_preview_shape") and self.current_preview_shape:
            self.draw_preview_shape(self.current_preview_shape)

    def update_summary_text(self, layouts_count, yield_pct, est_sec):
        sess_id = self.session_data.get("id", 1) if hasattr(self, "session_data") and self.session_data else 1
        sess_job = self.session_data.get("job", "Job") if hasattr(self, "session_data") and self.session_data else "Job"
        mat = (self.session_data.get("material") or {}) if hasattr(self, "session_data") and self.session_data else {}
        if not mat:
            text = f"""Summary information for session #{sess_id} of job {sess_job}

Material / Layout:
- Código do Material: (nenhum material atribuído)
- Dimensões do Layout: Não definido
- Camadas de corte (Layers): 0
- Gap entre peças: 1.0 mm
- Área total da placa: 0.0000 m²

Layouts:
- Calculated Layouts: {layouts_count}
- Material Yield (Aproveitamento Útil): {yield_pct:.1f}%
- Estimated ATOM Cycle Time: {int(est_sec // 60)}m {int(est_sec % 60):02d}s
"""
            self.txt_summary.delete("1.0", "end")
            self.txt_summary.insert("1.0", text)
            return

        w_m = mat.get("width_m", mat.get("width_mm", 1380) / 1000.0)
        l_m = mat.get("length_m", mat.get("height_mm", 1080) / 1000.0)
        layers = mat.get("layers", 2)
        gap = mat.get("gap", 1.0)
        area = mat.get("area_m2", round(w_m * l_m, 4))
        mat_code = mat.get("code", "853412")
        w_cm = w_m * 100.0
        l_cm = l_m * 100.0

        text = f"""Summary information for session #{sess_id} of job {sess_job}

Material / Layout:
- Código do Material: {mat_code}
- Dimensões do Layout: {l_cm:.2f} X {w_cm:.2f} cm [{w_m:.2f}m x {l_m:.2f}m]
- Camadas de corte (Layers): {layers}
- Gap entre peças: {gap} mm
- Área total da placa: {area:.4f} m²

Layouts:
- Calculated Layouts: {layouts_count}
- Material Yield (Aproveitamento Útil): {yield_pct:.1f}%
- Estimated ATOM Cycle Time: {int(est_sec // 60)}m {int(est_sec % 60):02d}s
"""
        shapes = getattr(self, "shapes_list", None) or (self.session_data.get("shapes", []) if hasattr(self, "session_data") and self.session_data else [])
        layouts = (self.session_data.get("layouts", []) if hasattr(self, "session_data") and self.session_data else [])
        if layouts and shapes:
            from cad.nesting_engine import piece_matches_shape, sort_shapes_by_sequence, parse_sequence_num
            text += "\nSequência de Encaixe por Placa:\n"
            sorted_s, _ = sort_shapes_by_sequence(shapes)
            for s in sorted_s:
                name = s.get("name") or s.get("id") or "Molde"
                seq = parse_sequence_num(s.get("sequence"))
                seq_label = f"seq {seq}" if seq is not None else "sem seq"
                sheets = [f"lay{i:04d}" for i, ly in enumerate(layouts) if any(piece_matches_shape(p, s) for p in ly.get("pieces", []))]
                if sheets:
                    start_lay = sheets[0]
                    end_lay = sheets[-1]
                    span_str = start_lay if start_lay == end_lay else f"{start_lay} → {end_lay}"
                    text += f"- Molde {name} ({seq_label}): {span_str}\n"
                else:
                    text += f"- Molde {name} ({seq_label}): Não encaixado\n"

        self.txt_summary.delete("1.0", "end")
        self.txt_summary.insert("1.0", text)
