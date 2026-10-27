"""
JobManager 2000 (Python Edition)
Diálogo de Refilamento de Layout com Corte Automático (Trim Layout / Guillotine Cut).
Permite encurtar a placa de corte para a extensão real das peças com gap milimétrico
e aplicar uma linha de corte transversal de guilhotina na máquina de corte.
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox

from config import THEME
from cad.geometry import transform_contour, polygon_bbox


class TrimLayoutDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        placed_pieces=None,
        current_sheet_w=1380.0,
        current_sheet_h=2980.0,
        default_gap=1.0,
        on_apply=None,
        max_piece_y_mm=None,
        sheet_height_mm=None,
        sheet_width_mm=None
    ):
        super().__init__(parent, bg=THEME["bg_surface"])
        self.parent = parent
        self.placed_pieces = placed_pieces or []
        self.current_sheet_w = float(sheet_width_mm if sheet_width_mm is not None else current_sheet_w)
        self.current_sheet_h = float(sheet_height_mm if sheet_height_mm is not None else current_sheet_h)
        self.sheet_width_mm = self.current_sheet_w
        self.sheet_height_mm = self.current_sheet_h
        self.default_gap = float(default_gap)
        self.on_apply_cb = on_apply

        self.title("Refilar Layout - Corte Automático")
        self.resizable(False, False)
        self.transient(parent)
        try:
            self.grab_set()
        except Exception:
            pass

        # Calcula a cota máxima Y ocupada pelas peças
        if max_piece_y_mm is not None:
            self.max_y = float(max_piece_y_mm)
            self.min_y = 0.0
            self.max_x = self.current_sheet_w
            self.min_x = 0.0
        else:
            self.max_y, self.min_y, self.max_x, self.min_x = self._calc_pieces_bounds()
        self.max_piece_y_mm = self.max_y

        # Sugestão padrão inteligente:
        # Se max_y estiver entre 2000 e 2050 mm (ex: Session 3 com 2038.59 mm),
        # 2080.0 mm (2.08 m) é uma margem excelente e limpa.
        if 2000.0 <= self.max_y <= 2050.0:
            initial_target_h = 2080.0
            initial_gap = round(initial_target_h - self.max_y, 1)
        else:
            initial_gap = max(1.0, round(self.default_gap, 1))
            initial_target_h = round(self.max_y + initial_gap, 1)

        self.var_gap_mm = tk.DoubleVar(value=initial_gap)
        self.var_final_cm = tk.DoubleVar(value=round(initial_target_h / 10.0, 2))
        self.var_cut_line = tk.BooleanVar(value=True)

        self._updating_vars = False

        self.setup_ui()
        self._center_window(520, 420)

        self.bind("<Return>", lambda e: self.on_confirm())
        self.bind("<Escape>", lambda e: self.destroy())

    def _calc_pieces_bounds(self):
        max_y = 0.0
        min_y = float("inf")
        max_x = 0.0
        min_x = float("inf")
        for p in self.placed_pieces:
            contour = p.get("contour") or []
            if not contour and isinstance(p.get("shape"), dict):
                contour = p.get("shape", {}).get("contour") or []
            if not contour:
                continue
            poly = transform_contour(contour, p.get("x", 0.0), p.get("y", 0.0), p.get("rotation", 0.0))
            bx1, by1, bx2, by2 = polygon_bbox(poly)
            max_y = max(max_y, by2)
            min_y = min(min_y, by1)
            max_x = max(max_x, bx2)
            min_x = min(min_x, bx1)

        if min_y == float("inf"):
            min_y = 0.0
        if min_x == float("inf"):
            min_x = 0.0
        return max_y, min_y, max_x, min_x

    def _center_window(self, w, h):
        self.update_idletasks()
        rx = self.parent.winfo_rootx() + (self.parent.winfo_width() - w) // 2
        ry = self.parent.winfo_rooty() + (self.parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{max(20, rx)}+{max(20, ry)}")

    def setup_ui(self):
        main_frame = tk.Frame(self, bg=THEME["bg_surface"], padx=14, pady=12)
        main_frame.pack(fill="both", expand=True)

        # 1. Cabeçalho explicativo
        header_frame = tk.Frame(main_frame, bg=THEME["bg_surface"])
        header_frame.pack(fill="x", pady=(0, 10))

        tk.Label(
            header_frame,
            text="✂ Refilamento de Chapa e Corte Automático",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 11, "bold"),
            anchor="w"
        ).pack(fill="x")

        tk.Label(
            header_frame,
            text="Reduz a placa de corte para a extensão real das peças e adiciona a linha de corte da faca.",
            bg=THEME["bg_surface"],
            fg=THEME.get("text_muted", "#475569"),
            font=("Segoe UI", 8),
            anchor="w"
        ).pack(fill="x", pady=(2, 0))

        # 2. Painel de Status das Dimensões Atuais
        info_box = tk.LabelFrame(
            main_frame,
            text=" Dimensões e Extensão das Peças ",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            padx=10,
            pady=8
        )
        info_box.pack(fill="x", pady=(0, 10))

        cur_h_cm = self.current_sheet_h / 10.0
        cur_w_cm = self.current_sheet_w / 10.0
        max_y_cm = self.max_y / 10.0

        grid_info = tk.Frame(info_box, bg=THEME["bg_surface"])
        grid_info.pack(fill="x")

        tk.Label(grid_info, text="Placa Atual:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), anchor="w").grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(grid_info, text=f"{cur_h_cm:.2f} X {cur_w_cm:.2f} cm ({self.current_sheet_h/1000.0:.2f} X {self.current_sheet_w/1000.0:.2f} M)", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8, "bold"), anchor="w").grid(row=0, column=1, sticky="w", padx=(8, 0), pady=2)

        tk.Label(grid_info, text="Extensão Peças (Y_max):", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), anchor="w").grid(row=1, column=0, sticky="w", pady=2)
        tk.Label(grid_info, text=f"{max_y_cm:.2f} cm ({self.max_y/1000.0:.3f} M) — Total: {len(self.placed_pieces)} peças", bg=THEME["bg_surface"], fg="#0369a1", font=("Segoe UI", 8, "bold"), anchor="w").grid(row=1, column=1, sticky="w", padx=(8, 0), pady=2)

        # 3. Painel de Configuração do Refile
        cfg_box = tk.LabelFrame(
            main_frame,
            text=" Parâmetros de Refilamento ",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            padx=10,
            pady=8
        )
        cfg_box.pack(fill="x", pady=(0, 10))

        # Linha A: Gap no final das peças (mm)
        row_a = tk.Frame(cfg_box, bg=THEME["bg_surface"])
        row_a.pack(fill="x", pady=3)

        tk.Label(row_a, text="Gap no final das peças (mm):", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), width=26, anchor="w").pack(side="left")
        self.ent_gap = tk.Spinbox(
            row_a,
            from_=0.5,
            to=500.0,
            increment=0.5,
            textvariable=self.var_gap_mm,
            width=8,
            bg=THEME["bg_input"],
            fg=THEME["text_main"],
            relief="sunken",
            bd=2,
            font=("Segoe UI", 9)
        )
        self.ent_gap.pack(side="left", padx=(0, 8))
        self.ent_gap.bind("<KeyRelease>", self._on_gap_changed)
        self.ent_gap.bind("<<Increment>>", self._on_gap_changed)
        self.ent_gap.bind("<<Decrement>>", self._on_gap_changed)

        # Linha B: Comprimento final da placa (cm)
        row_b = tk.Frame(cfg_box, bg=THEME["bg_surface"])
        row_b.pack(fill="x", pady=3)

        tk.Label(row_b, text="Nova Altura da Placa (cm):", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), width=26, anchor="w").pack(side="left")
        self.ent_final_cm = tk.Spinbox(
            row_b,
            from_=round(max_y_cm, 1),
            to=round(cur_h_cm, 1),
            increment=1.0,
            textvariable=self.var_final_cm,
            width=8,
            bg=THEME["bg_input"],
            fg=THEME["text_main"],
            relief="sunken",
            bd=2,
            font=("Segoe UI", 9)
        )
        self.ent_final_cm.pack(side="left", padx=(0, 8))
        self.ent_final_cm.bind("<KeyRelease>", self._on_final_cm_changed)
        self.ent_final_cm.bind("<<Increment>>", self._on_final_cm_changed)
        self.ent_final_cm.bind("<<Decrement>>", self._on_final_cm_changed)

        self.lbl_meter = tk.Label(row_b, text=f"({self.var_final_cm.get()/100.0:.2f} M)", bg=THEME["bg_surface"], fg=THEME.get("text_muted", "#64748b"), font=("Segoe UI", 8))
        self.lbl_meter.pack(side="left")

        # Linha C: Botões de Atalho Rápido
        row_c = tk.Frame(cfg_box, bg=THEME["bg_surface"])
        row_c.pack(fill="x", pady=(6, 4))

        tk.Label(row_c, text="Ajustes Rápidos:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), width=14, anchor="w").pack(side="left")

        tk.Button(
            row_c,
            text=f"Gap {self.default_gap:.1f} mm",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            font=("Segoe UI", 8),
            relief="raised",
            bd=1,
            padx=4,
            command=lambda: self.set_preset_gap(self.default_gap)
        ).pack(side="left", padx=2)

        tk.Button(
            row_c,
            text="Margem 10 mm",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            font=("Segoe UI", 8),
            relief="raised",
            bd=1,
            padx=4,
            command=lambda: self.set_preset_gap(10.0)
        ).pack(side="left", padx=2)

        tk.Button(
            row_c,
            text="2,08 m (Sugerido)",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            font=("Segoe UI", 8, "bold"),
            relief="raised",
            bd=1,
            padx=4,
            command=lambda: self.set_preset_final_cm(208.0)
        ).pack(side="left", padx=2)

        # Linha D: Checkbox do corte de refile automático
        row_d = tk.Frame(cfg_box, bg=THEME["bg_surface"])
        row_d.pack(fill="x", pady=(6, 2))

        chk = tk.Checkbutton(
            row_d,
            text="Executar corte automático transversal no final das peças (linha de guilhotina)",
            variable=self.var_cut_line,
            bg=THEME["bg_surface"],
            fg="#047857",
            font=("Segoe UI", 8, "bold"),
            activebackground=THEME["bg_surface"],
            selectcolor="#ffffff"
        )
        chk.pack(anchor="w")

        # 4. Indicador de Economia de Material
        self.lbl_savings = tk.Label(
            main_frame,
            text="",
            bg="#f0fdf4",
            fg="#166534",
            font=("Segoe UI", 9, "bold"),
            relief="solid",
            bd=1,
            padx=8,
            pady=4
        )
        self.lbl_savings.pack(fill="x", pady=(0, 12))
        self._update_savings_label()

        # 5. Barra Inferior de Botões de Ação
        btn_bar = tk.Frame(main_frame, bg=THEME["bg_surface"])
        btn_bar.pack(fill="x", side="bottom")

        btn_cancel = tk.Button(
            btn_bar,
            text="Cancelar",
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            fg=THEME["text_main"],
            relief="raised",
            bd=1,
            font=("Segoe UI", 9),
            width=10,
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(6, 0))

        btn_apply = tk.Button(
            btn_bar,
            text="✂ Refilar Layout",
            bg="#0f766e",
            activebackground="#115e59",
            fg="#ffffff",
            relief="raised",
            bd=1,
            font=("Segoe UI", 9, "bold"),
            padx=12,
            command=self.on_confirm,
            cursor="hand2"
        )
        btn_apply.pack(side="right")
        btn_apply.focus_set()

    def _on_gap_changed(self, event=None):
        if self._updating_vars:
            return
        self._updating_vars = True
        try:
            gap_mm = float(self.var_gap_mm.get())
            final_h_mm = max(self.max_y, self.max_y + gap_mm)
            self.var_final_cm.set(round(final_h_mm / 10.0, 2))
            self.lbl_meter.config(text=f"({final_h_mm / 1000.0:.2f} M)")
            self._update_savings_label()
        except Exception:
            pass
        finally:
            self._updating_vars = False

    def _on_final_cm_changed(self, event=None):
        if self._updating_vars:
            return
        self._updating_vars = True
        try:
            final_cm = float(self.var_final_cm.get())
            final_h_mm = final_cm * 10.0
            gap_mm = max(0.0, final_h_mm - self.max_y)
            self.var_gap_mm.set(round(gap_mm, 1))
            self.lbl_meter.config(text=f"({final_cm / 100.0:.2f} M)")
            self._update_savings_label()
        except Exception:
            pass
        finally:
            self._updating_vars = False

    def set_preset_gap(self, gap_val):
        self._updating_vars = True
        try:
            self.var_gap_mm.set(float(gap_val))
            final_h_mm = self.max_y + float(gap_val)
            self.var_final_cm.set(round(final_h_mm / 10.0, 2))
            self.lbl_meter.config(text=f"({final_h_mm / 1000.0:.2f} M)")
            self._update_savings_label()
        finally:
            self._updating_vars = False

    def set_preset_final_cm(self, final_cm):
        self._updating_vars = True
        try:
            final_cm_f = float(final_cm)
            self.var_final_cm.set(final_cm_f)
            gap_mm = max(0.0, (final_cm_f * 10.0) - self.max_y)
            self.var_gap_mm.set(round(gap_mm, 1))
            self.lbl_meter.config(text=f"({final_cm_f / 100.0:.2f} M)")
            self._update_savings_label()
        finally:
            self._updating_vars = False

    def _update_savings_label(self):
        try:
            target_h_mm = float(self.var_final_cm.get()) * 10.0
            saved_mm = max(0.0, self.current_sheet_h - target_h_mm)
            saved_m = saved_mm / 1000.0
            saved_cm = saved_mm / 10.0
            pct_saved = (saved_mm / max(1.0, self.current_sheet_h)) * 100.0
            self.lbl_savings.config(
                text=f" Economia: {saved_cm:.1f} cm ({saved_m:.2f} M) de chapa poupada ({pct_saved:.1f}% do material)"
            )
        except Exception:
            pass

    def on_confirm(self):
        try:
            final_cm = float(self.var_final_cm.get())
            target_h_mm = round(final_cm * 10.0, 1)
        except Exception:
            messagebox.showerror("Valor Inválido", "Informe um valor numérico válido para o comprimento da placa.", parent=self)
            return

        if target_h_mm < self.max_y - 0.5:
            messagebox.showwarning(
                "Cota Menor que as Peças",
                f"O comprimento informado ({target_h_mm/10.0:.1f} cm) é menor que a altura das peças ({self.max_y/10.0:.1f} cm).\n"
                f"Ajuste para pelo menos {self.max_y/10.0:.1f} cm para evitar corte sobre as peças.",
                parent=self
            )
            return

        add_cut = bool(self.var_cut_line.get())
        if self.on_apply_cb:
            try:
                self.on_apply_cb(target_h_mm, add_cut_line=add_cut)
            except TypeError:
                self.on_apply_cb(target_h_mm, add_cut)

        self.destroy()

    def set_preset_height(self, height_mm_or_cm):
        val = float(height_mm_or_cm)
        if val > 500:  # mm (ex: 2080.0)
            self.set_preset_final_cm(val / 10.0)
        else:  # cm (ex: 208.0)
            self.set_preset_final_cm(val)

    def on_apply_click(self):
        return self.on_confirm()

    @property
    def var_height_cm(self):
        return self.var_final_cm

    @property
    def var_add_cut_line(self):
        return self.var_cut_line

    @property
    def var_height_m(self):
        class _MeterWrapper:
            def __init__(self, cm_var):
                self._cm = cm_var
            def get(self):
                return round(float(self._cm.get()) / 100.0, 2)
            def set(self, val):
                self._cm.set(round(float(val) * 100.0, 1))
        return _MeterWrapper(self.var_final_cm)
