"""
JobManager 2000 (Python Edition)
Visualizador e Emissor de Relatório de Impressão do Layout (.lay)
Reprodução idêntica ao modelo original ATOM FlashCut (media_1792071945871.jpg)
"""

import sys
import os
import math
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageDraw, ImageFont

from config import THEME
from cad.colors import get_color_for_size


class LayoutPrintDialog(tk.Toplevel):
    """
    Janela modal de Visualização de Impressão (Print Preview) do Layout Editor.
    Exibe a folha A4 com cabeçalho oficial ATOM, metadados completos e o gráfico do encaixe.
    """
    def __init__(self, parent, layout_data=None, **kwargs):
        super().__init__(parent, bg=THEME["bg_surface"], **kwargs)
        self.title("Print Preview - Layout")
        self.geometry("1100x800")
        self.minsize(680, 500)

        # Inicia a tela de impressão maximizada ocupando a tela cheia do monitor
        try:
            self.attributes("-zoomed", True)
        except Exception:
            try:
                self.state("zoomed")
            except Exception:
                try:
                    sw = self.winfo_screenwidth()
                    sh = self.winfo_screenheight()
                    self.geometry(f"{sw}x{sh}+0+0")
                except Exception:
                    pass

        self._initial_fit_done = False
        self.layout_data = layout_data or {}
        self.zoom = 1.0
        self.logo_img = None

        # Carrega metadados e parâmetros padrão (conforme media_1792071945871.jpg)
        raw_name = self.layout_data.get("layout_name")
        if not raw_name or raw_name == "[I0000]":
            self.layout_name = "10001.lay"
        else:
            self.layout_name = raw_name if raw_name.lower().endswith(".lay") else f"{raw_name}.lay"

        self.title(f"Print Preview - [{self.layout_name}]")

        self.unc_prefix = self.layout_data.get("unc_prefix", r"\\Lab-inf\NSDATAv1")
        self.layout_path = self.layout_data.get(
            "layout_path",
            rf"{self.unc_prefix}\Compiti\SEM 46-UP046_2°\129.046\10100\{self.layout_name}"
        )
        self.description = self.layout_data.get("description", "fn98 - v1.2.36 - 12.09.2012")
        self.material_name = self.layout_data.get(
            "material_name",
            "132011 - VELCRO 4'' ARGOLA - PRETO ( 4 layer(s) )"
        )
        self.dimensions_str = self.layout_data.get("dimensions_str", "1.50 X 0.09 M")
        self.mat_area_str = self.layout_data.get("mat_area_str", "0.13 sq.M.")
        self.used_area_str = self.layout_data.get("used_area_str", "0.11 sq.M.")
        self.yield_pct = self.layout_data.get("yield_pct", 83.02)
        self.shapes_count = self.layout_data.get("shapes_count", 15)
        self.instances_count = self.layout_data.get("instances_count", 40)
        self.gap_str = self.layout_data.get("gap_str", "1.00 mm")
        self.date_str = self.layout_data.get("date_str") or datetime.now().strftime("%A, %d %B %Y")

        # Dados da chapa e peças
        self.placed_pieces = self.layout_data.get("placed_pieces", [])
        if self.placed_pieces is None:
            self.placed_pieces = []

        # Dimensões da chapa
        if "sheet_w_mm" in self.layout_data:
            self.sheet_w_mm = float(self.layout_data.get("sheet_w_mm", 1380.0))
            self.sheet_h_mm = float(self.layout_data.get("sheet_h_mm", 1080.0))
        elif not self.placed_pieces:
            self.sheet_w_mm = 1500.0
            self.sheet_h_mm = 90.0
        else:
            self.sheet_w_mm = 1380.0
            self.sheet_h_mm = 1080.0

        # Se não foram fornecidas peças nem dimensões customizadas, usa layout de exemplo (velcro)
        if not self.placed_pieces and "sheet_w_mm" not in self.layout_data:
            self.dimensions_str = "1.50 X 0.09 M"
            self.mat_area_str = "0.13 sq.M."
            self.used_area_str = "0.11 sq.M."
            self.yield_pct = 83.02
            self.shapes_count = 15
            self.instances_count = 40
            self.init_sample_pieces()

        # Dimensões da folha A4 em pontos de tela (base 100%): 595 x 842 pt
        self.page_w_base = 595
        self.page_h_base = 842

        # Carrega logotipo ATOM
        self.load_atom_logo()

        # Monta a barra de ferramentas superior e a área de rolagem da folha
        self.setup_ui()

        # Renderiza a página
        self.after(50, self.fit_to_page)

    def load_atom_logo(self):
        assets_dir = Path(__file__).resolve().parent.parent / "assets"
        logo_path = assets_dir / "atom_logo_print.png"
        if logo_path.exists():
            try:
                self.logo_img = tk.PhotoImage(file=str(logo_path))
            except Exception:
                self.logo_img = None

    def init_sample_pieces(self):
        """Gera a disposição autêntica das 40 peças mostrada no print do usuário."""
        self.placed_pieces = []
        cols = 20
        rows = 2
        pw = 71.0
        ph = 40.0
        margin_x = 12.0
        margin_y = 4.0
        spacing_x = (self.sheet_w_mm - margin_x * 2 - cols * pw) / max(1, cols - 1)
        spacing_y = (self.sheet_h_mm - margin_y * 2 - rows * ph) / max(1, rows - 1)

        # Contorno retangular com cantos chanfrados (tira/velcro)
        contour = [
            {"x": -pw/2 + 4, "y": -ph/2},
            {"x": pw/2 - 4, "y": -ph/2},
            {"x": pw/2, "y": -ph/2 + 4},
            {"x": pw/2, "y": ph/2 - 4},
            {"x": pw/2 - 4, "y": ph/2},
            {"x": -pw/2 + 4, "y": ph/2},
            {"x": -pw/2, "y": ph/2 - 4},
            {"x": -pw/2, "y": -ph/2 + 4},
        ]

        for col in range(cols):
            for row in range(rows):
                cx = margin_x + col * (pw + spacing_x) + pw / 2
                cy = margin_y + row * (ph + spacing_y) + ph / 2
                # As 2 peças da primeira coluna são laranjas (#f97316), as demais 38 são verdes (#22c55e)
                color = "#f97316" if col == 0 else "#22c55e"
                self.placed_pieces.append({
                    "contour": contour,
                    "x": cx,
                    "y": cy,
                    "color": color,
                    "rotation": 0.0
                })

    def setup_ui(self):
        # 1. Barra de Ferramentas Superior
        tb = tk.Frame(self, bg=THEME["bg_surface"], relief="raised", bd=1, padx=6, pady=4)
        tb.pack(side="top", fill="x")

        tk.Button(
            tb, text="🖨️ Imprimir...", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9, "bold"), padx=8, command=self.do_print
        ).pack(side="left", padx=2)

        tk.Button(
            tb, text="💾 Salvar PDF...", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9), padx=6, command=self.save_as_pdf
        ).pack(side="left", padx=2)

        tk.Button(
            tb, text="🖼️ Salvar Imagem...", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9), padx=6, command=self.save_as_png
        ).pack(side="left", padx=2)

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)

        tk.Button(
            tb, text="🔍 Zoom +", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9), padx=4, command=lambda: self.change_zoom(1.2)
        ).pack(side="left", padx=2)

        tk.Button(
            tb, text="🔍 Zoom -", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9), padx=4, command=lambda: self.change_zoom(0.833)
        ).pack(side="left", padx=2)

        tk.Button(
            tb, text="100%", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9), padx=4, command=lambda: self.set_zoom(1.0)
        ).pack(side="left", padx=2)

        tk.Button(
            tb, text="📐 Ajustar à Página", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9), padx=4, command=self.fit_to_page
        ).pack(side="left", padx=2)

        self.btn_fullscreen = tk.Button(
            tb, text="⛶ Tela Cheia", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9), padx=4, command=self.toggle_fullscreen
        )
        self.btn_fullscreen.pack(side="left", padx=2)

        tk.Button(
            tb, text="❌ Fechar", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9), padx=8, command=self.destroy
        ).pack(side="right", padx=4)

        # 2. Espaço de Trabalho Escuro com Folha A4 Centralizada
        workspace_frame = tk.Frame(self, bg="#585858")
        workspace_frame.pack(side="top", fill="both", expand=True)

        self.h_scroll = ttk.Scrollbar(workspace_frame, orient="horizontal")
        self.v_scroll = ttk.Scrollbar(workspace_frame, orient="vertical")

        self.canvas = tk.Canvas(
            workspace_frame,
            bg="#585858",
            highlightthickness=0,
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set
        )

        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.config(command=self.canvas.yview)

        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Interações de rolagem e zoom
        self.bind("<Control-MouseWheel>", self._on_ctrl_wheel)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))

        # Atalhos de teclado
        self.bind("<Control-p>", lambda e: self.do_print())
        self.bind("<Control-P>", lambda e: self.do_print())
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.on_escape)

    def _on_canvas_configure(self, event):
        if not getattr(self, "_initial_fit_done", False):
            if event.width > 200 and event.height > 200:
                self._initial_fit_done = True
                self.fit_to_page()
                return
        self.redraw()

    def toggle_fullscreen(self, event=None):
        try:
            self._is_fullscreen = not getattr(self, "_is_fullscreen", False)
            try:
                self.attributes("-fullscreen", self._is_fullscreen)
            except Exception:
                pass
            if hasattr(self, "btn_fullscreen"):
                self.btn_fullscreen.config(text="🗗 Restaurar" if self._is_fullscreen else "⛶ Tela Cheia")
            self.after(60, self.fit_to_page)
        except Exception:
            pass

    def on_escape(self, event=None):
        try:
            if getattr(self, "_is_fullscreen", False):
                self._is_fullscreen = False
                try:
                    self.attributes("-fullscreen", False)
                except Exception:
                    pass
                if hasattr(self, "btn_fullscreen"):
                    self.btn_fullscreen.config(text="⛶ Tela Cheia")
                self.after(60, self.fit_to_page)
                return "break"
        except Exception:
            pass
        self.destroy()
        return "break"

    def _on_wheel(self, event):
        delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta * 2, "units")

    def _on_ctrl_wheel(self, event):
        factor = 1.15 if event.delta > 0 else 0.85
        self.change_zoom(factor)

    def change_zoom(self, factor):
        new_z = max(0.4, min(3.0, self.zoom * factor))
        self.set_zoom(new_z)

    def set_zoom(self, z):
        self.zoom = z
        self.redraw()

    def fit_to_page(self):
        cv_w = self.canvas.winfo_width()
        cv_h = self.canvas.winfo_height()
        if cv_w < 100 or cv_h < 100:
            try:
                cv_w = int(self.canvas.cget("width"))
                cv_h = int(self.canvas.cget("height"))
            except Exception:
                cv_w, cv_h = 1000, 700
        if cv_w < 100 or cv_h < 100:
            self.zoom = 0.85
        else:
            scale_w = (cv_w - 60) / self.page_w_base
            scale_h = (cv_h - 60) / self.page_h_base
            self.zoom = max(0.4, min(2.0, min(scale_w, scale_h)))
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")

        page_w = int(self.page_w_base * self.zoom)
        page_h = int(self.page_h_base * self.zoom)

        cv_w = max(self.canvas.winfo_width(), page_w + 60)
        cv_h = max(self.canvas.winfo_height(), page_h + 60)

        # Centraliza a página no canvas
        px = max(30, (cv_w - page_w) // 2)
        py = max(30, (cv_h - page_h) // 2)

        # Sombra da folha de papel
        self.canvas.create_rectangle(
            px + 4, py + 4, px + page_w + 4, py + page_h + 4,
            fill="#2c2c2c", outline=""
        )

        # Folha de papel branca pura A4
        self.canvas.create_rectangle(
            px, py, px + page_w, py + page_h,
            fill="#ffffff", outline="#707070", width=1
        )

        # Fonte monoespaçada Courier escalada com zoom
        f_size_sm = max(6, int(8 * self.zoom))
        f_size_md = max(7, int(9 * self.zoom))
        f_size_lg = max(9, int(13 * self.zoom))

        f_mono = ("Courier", f_size_md)
        f_mono_bold = ("Courier", f_size_md, "bold")
        f_title = ("Courier", f_size_lg, "bold")
        f_path = ("Courier", max(6, int(7.5 * self.zoom)))
        f_date = ("Courier", max(6, int(8 * self.zoom)))

        margin_left = px + int(36 * self.zoom)
        margin_right = px + page_w - int(36 * self.zoom)
        margin_top = py + int(30 * self.zoom)

        # =====================================================================
        # 1. Cabeçalho Topo
        # =====================================================================
        # Linha de caminho de rede no canto superior esquerdo
        self.canvas.create_text(
            margin_left, margin_top,
            text=self.unc_prefix + "\\",
            anchor="nw", font=f_path, fill="#000000"
        )

        # Logotipo ATOM no canto superior esquerdo
        logo_y = margin_top + int(12 * self.zoom)
        if self.logo_img:
            self.canvas.create_image(margin_left, logo_y, image=self.logo_img, anchor="nw")
        else:
            self.canvas.create_text(
                margin_left, logo_y,
                text="Ψ ATOM", anchor="nw", font=("Segoe UI", max(10, int(15 * self.zoom)), "bold"), fill="#000000"
            )

        # Título centralizado e sublinhado: <layout_name>.lay
        title_x = px + page_w // 2
        title_y = margin_top + int(36 * self.zoom)
        t_id = self.canvas.create_text(
            title_x, title_y,
            text=self.layout_name,
            anchor="center", font=f_title, fill="#000000"
        )
        tb_box = self.canvas.bbox(t_id)
        if tb_box:
            self.canvas.create_line(
                tb_box[0] - 2, tb_box[3] + 1, tb_box[2] + 2, tb_box[3] + 1,
                fill="#000000", width=max(1, int(1.5 * self.zoom))
            )

        # Data alinhada à direita
        self.canvas.create_text(
            margin_right, margin_top + int(60 * self.zoom),
            text=self.date_str,
            anchor="ne", font=f_date, fill="#000000"
        )

        # =====================================================================
        # 2. Bloco de Metadados em Courier Monospace
        # =====================================================================
        meta_y = margin_top + int(82 * self.zoom)
        line_h = int(17 * self.zoom)

        lines = [
            f"Layout: {self.layout_path}",
            f"Description: {self.description}",
            f"Material: {self.material_name}",
            f"Dimensions:  {self.dimensions_str}",
            f"Material Area: {self.mat_area_str}",
            f"Used Area: {self.used_area_str} - Yield:  {self.yield_pct:.2f}%",
        ]

        for line_txt in lines:
            self.canvas.create_text(
                margin_left, meta_y,
                text=line_txt, anchor="nw",
                font=f_mono, fill="#000000"
            )
            meta_y += line_h

        # Linha inferior de metadados: Shapes, Instances e Gap
        col_w = (margin_right - margin_left) // 3
        self.canvas.create_text(
            margin_left, meta_y,
            text=f"Shapes: {self.shapes_count}",
            anchor="nw", font=f_mono, fill="#000000"
        )
        self.canvas.create_text(
            margin_left + col_w, meta_y,
            text=f"Instances: {self.instances_count}",
            anchor="nw", font=f_mono, fill="#000000"
        )
        self.canvas.create_text(
            margin_left + col_w * 2, meta_y,
            text=f"Gap: {self.gap_str}",
            anchor="nw", font=f_mono, fill="#000000"
        )

        # =====================================================================
        # 3. Gráfico do Encaixe / Chapa de Corte (Proporcional à Folha A4)
        # =====================================================================
        meta_end_y = meta_y + int(18 * self.zoom)
        footer_y = py + page_h - int(24 * self.zoom)

        avail_top = meta_end_y + int(15 * self.zoom)
        avail_bottom = footer_y - int(12 * self.zoom)
        avail_w = max(50.0, float(margin_right - margin_left))
        avail_h = max(50.0, float(avail_bottom - avail_top))

        scale_bed_x = avail_w / max(1.0, float(self.sheet_w_mm))
        scale_bed_y = avail_h / max(1.0, float(self.sheet_h_mm))
        bed_scale = min(scale_bed_x, scale_bed_y)

        bed_w = max(10, int(round(self.sheet_w_mm * bed_scale)))
        bed_h = max(10, int(round(self.sheet_h_mm * bed_scale)))

        bed_x = margin_left + (int(avail_w) - bed_w) // 2
        bed_y = avail_top + (int(avail_h) - bed_h) // 2

        # Retângulo do Material / Chapa
        self.canvas.create_rectangle(
            bed_x, bed_y, bed_x + bed_w, bed_y + bed_h,
            fill="#ffffff", outline="#000000", width=1,
            tags="print_bed"
        )

        # Grade Milimétrica e Marcações de 10 em 10 cm no Relatório (como no Editor)
        grid_step = 100.0  # 100 mm = 10 cm
        tick_len = max(2.0, 2.5 * self.zoom)
        f_ruler = ("Courier", max(5, int(6.0 * self.zoom)))

        cur_wx = 0.0
        while cur_wx <= self.sheet_w_mm + 0.1:
            gx = bed_x + cur_wx * bed_scale
            # Linha de grade vertical sutil interna
            if 0.5 < cur_wx < self.sheet_w_mm - 0.5:
                self.canvas.create_line(gx, bed_y, gx, bed_y + bed_h, fill="#d0d0d0", width=1, tags="print_grid")

            # Ticks superior e inferior
            self.canvas.create_line(gx, bed_y + bed_h - tick_len, gx, bed_y + bed_h + tick_len, fill="#000000", width=1, tags="print_tick")
            self.canvas.create_line(gx, bed_y - tick_len, gx, bed_y + tick_len, fill="#000000", width=1, tags="print_tick")

            # Numeração inferior em cm (10, 20, 30...)
            cm_x = int(round(cur_wx / 10.0))
            if cm_x > 0 and cur_wx < self.sheet_w_mm - 0.5:
                self.canvas.create_text(
                    gx, bed_y + bed_h + tick_len + 2,
                    text=str(cm_x),
                    font=f_ruler,
                    fill="#000000",
                    anchor="n",
                    tags="print_label"
                )

            cur_wx += grid_step

        cur_wy = 0.0
        while cur_wy <= self.sheet_h_mm + 0.1:
            gy = bed_y + bed_h - cur_wy * bed_scale
            # Linha de grade horizontal sutil interna
            if 0.5 < cur_wy < self.sheet_h_mm - 0.5:
                self.canvas.create_line(bed_x, gy, bed_x + bed_w, gy, fill="#d0d0d0", width=1, tags="print_grid")

            # Ticks esquerda e direita
            self.canvas.create_line(bed_x - tick_len, gy, bed_x + tick_len, gy, fill="#000000", width=1, tags="print_tick")
            self.canvas.create_line(bed_x + bed_w - tick_len, gy, bed_x + bed_w + tick_len, gy, fill="#000000", width=1, tags="print_tick")

            # Numeração direita em cm (10, 20, 30...)
            cm_y = int(round(cur_wy / 10.0))
            if cm_y > 0 and cur_wy < self.sheet_h_mm - 0.5:
                self.canvas.create_text(
                    bed_x + bed_w + tick_len + 3, gy,
                    text=str(cm_y),
                    font=f_ruler,
                    fill="#000000",
                    anchor="w",
                    tags="print_label"
                )

            cur_wy += grid_step

        # Desenha cada peça encaixada na chapa
        for piece in self.placed_pieces:
            c = piece.get("contour", [])
            if not c:
                continue
            cx = piece.get("x", 0.0)
            cy = piece.get("y", 0.0)
            rot = piece.get("rotation", 0.0)
            p_sz = str(piece.get("size") or (piece.get("shape", {}).get("size") if isinstance(piece.get("shape"), dict) else ""))
            color = piece.get("color") or (piece.get("shape", {}).get("color") if isinstance(piece.get("shape"), dict) else None) or get_color_for_size(p_sz)
            if not color or color in ("#000000", "black", "None", ""):
                color = get_color_for_size(p_sz)

            # Aplica rotação e escala aos vértices
            rad = math.radians(rot)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)

            scr_coords = []
            for pt in c:
                px_val = pt["x"] if isinstance(pt, dict) else pt[0]
                py_val = pt["y"] if isinstance(pt, dict) else pt[1]
                rx = px_val * cos_r - py_val * sin_r + cx
                ry = px_val * sin_r + py_val * cos_r + cy

                sx = bed_x + rx * bed_scale
                sy = bed_y + (self.sheet_h_mm - ry) * bed_scale
                scr_coords.extend([sx, sy])

            if len(scr_coords) >= 6:
                self.canvas.create_polygon(
                    scr_coords,
                    fill=color,
                    outline="#000000",
                    width=1
                )

        # =====================================================================
        # 4. Rodapé da Página: Pages 1-1
        # =====================================================================
        footer_y = py + page_h - int(24 * self.zoom)
        self.canvas.create_text(
            margin_left, footer_y,
            text="Pages 1-1", anchor="nw",
            font=f_mono, fill="#000000"
        )

        # Atualiza limites da área rolável
        self.canvas.config(scrollregion=(0, 0, max(cv_w, px + page_w + 30), max(cv_h, py + page_h + 30)))

    # =========================================================================
    # Exportação e Impressão de Alta Resolução (300 DPI / PDF / PNG)
    # =========================================================================
    def render_pillow_page(self, dpi=150):
        """Gera uma imagem de alta resolução da página A4 completa usando PIL."""
        # A4 em polegadas: 8.27 x 11.69 polegadas
        pw = int(8.27 * dpi)
        ph = int(11.69 * dpi)
        scale = dpi / 72.0

        im = Image.new("RGB", (pw, ph), "white")
        draw = ImageDraw.Draw(im)

        try:
            f_mono = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", int(9 * scale))
            f_mono_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", int(9 * scale))
            f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", int(14 * scale))
            f_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", int(7.5 * scale))
            f_ruler = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", max(6, int(6.0 * scale)))
        except Exception:
            f_mono = ImageFont.load_default()
            f_mono_bold = f_mono
            f_title = f_mono
            f_small = f_mono
            f_ruler = f_mono

        m_left = int(36 * scale)
        m_right = pw - int(36 * scale)
        m_top = int(30 * scale)

        # Topo
        draw.text((m_left, m_top), self.unc_prefix + "\\", fill="black", font=f_small)

        # Logo ATOM
        logo_path = Path(__file__).resolve().parent.parent / "assets" / "atom_logo_print.png"
        if logo_path.exists():
            try:
                logo_im = Image.open(logo_path).convert("RGBA")
                lw = int(logo_im.width * scale * 0.75)
                lh = int(logo_im.height * scale * 0.75)
                logo_resized = logo_im.resize((lw, lh), Image.Resampling.LANCZOS)
                im.paste(logo_resized, (m_left, m_top + int(12 * scale)), logo_resized)
            except Exception:
                draw.text((m_left, m_top + int(12 * scale)), "ATOM", fill="black", font=f_title)

        # Título
        title_bbox = draw.textbbox((0, 0), self.layout_name, font=f_title)
        tw = title_bbox[2] - title_bbox[0]
        tx = (pw - tw) // 2
        ty = m_top + int(36 * scale)
        draw.text((tx, ty), self.layout_name, fill="black", font=f_title)
        draw.line([tx - 4, ty + (title_bbox[3] - title_bbox[1]) + 2, tx + tw + 4, ty + (title_bbox[3] - title_bbox[1]) + 2], fill="black", width=int(1.5 * scale))

        # Data
        date_bbox = draw.textbbox((0, 0), self.date_str, font=f_small)
        dx = m_right - (date_bbox[2] - date_bbox[0])
        draw.text((dx, m_top + int(60 * scale)), self.date_str, fill="black", font=f_small)

        # Metadados
        meta_y = m_top + int(82 * scale)
        line_h = int(17 * scale)
        lines = [
            f"Layout: {self.layout_path}",
            f"Description: {self.description}",
            f"Material: {self.material_name}",
            f"Dimensions:  {self.dimensions_str}",
            f"Material Area: {self.mat_area_str}",
            f"Used Area: {self.used_area_str} - Yield:  {self.yield_pct:.2f}%",
        ]
        for l_txt in lines:
            draw.text((m_left, meta_y), l_txt, fill="black", font=f_mono)
            meta_y += line_h

        col_w = (m_right - m_left) // 3
        draw.text((m_left, meta_y), f"Shapes: {self.shapes_count}", fill="black", font=f_mono)
        draw.text((m_left + col_w, meta_y), f"Instances: {self.instances_count}", fill="black", font=f_mono)
        draw.text((m_left + col_w * 2, meta_y), f"Gap: {self.gap_str}", fill="black", font=f_mono)

        # Gráfico do Encaixe Proporcional à Folha A4
        meta_end_y = meta_y + int(18 * scale)
        footer_y = ph - int(36 * scale)

        avail_top = meta_end_y + int(15 * scale)
        avail_bottom = footer_y - int(12 * scale)
        avail_w = max(50.0, float(m_right - m_left))
        avail_h = max(50.0, float(avail_bottom - avail_top))

        scale_bed_x = avail_w / max(1.0, float(self.sheet_w_mm))
        scale_bed_y = avail_h / max(1.0, float(self.sheet_h_mm))
        scale_bed = min(scale_bed_x, scale_bed_y)

        bed_w = max(10, int(round(self.sheet_w_mm * scale_bed)))
        bed_h = max(10, int(round(self.sheet_h_mm * scale_bed)))

        bed_x = m_left + (int(avail_w) - bed_w) // 2
        bed_y = avail_top + (int(avail_h) - bed_h) // 2

        draw.rectangle([bed_x, bed_y, bed_x + bed_w, bed_y + bed_h], outline="black", width=max(1, int(scale)))

        # Grade e Marcações de 10 em 10 cm na Impressão/Exportação
        grid_step = 100.0  # 100 mm = 10 cm
        tick_px = max(2, int(2.5 * scale))
        line_w = max(1, int(0.75 * scale))

        cur_wx = 0.0
        while cur_wx <= self.sheet_w_mm + 0.1:
            gx = bed_x + int(round(cur_wx * scale_bed))
            # Linha de grade vertical interna sutil
            if 0.5 < cur_wx < self.sheet_w_mm - 0.5:
                draw.line([gx, bed_y, gx, bed_y + bed_h], fill="#d0d0d0", width=line_w)

            # Ticks superior e inferior
            draw.line([gx, bed_y + bed_h - tick_px, gx, bed_y + bed_h + tick_px], fill="black", width=line_w)
            draw.line([gx, bed_y - tick_px, gx, bed_y + tick_px], fill="black", width=line_w)

            # Numeração inferior em cm (10, 20, 30...)
            cm_x = int(round(cur_wx / 10.0))
            if cm_x > 0 and cur_wx < self.sheet_w_mm - 0.5:
                bbox = draw.textbbox((0, 0), str(cm_x), font=f_ruler)
                tw = bbox[2] - bbox[0]
                draw.text((gx - tw // 2, bed_y + bed_h + tick_px + 2), str(cm_x), fill="black", font=f_ruler)

            cur_wx += grid_step

        cur_wy = 0.0
        while cur_wy <= self.sheet_h_mm + 0.1:
            gy = bed_y + bed_h - int(round(cur_wy * scale_bed))
            # Linha de grade horizontal interna sutil
            if 0.5 < cur_wy < self.sheet_h_mm - 0.5:
                draw.line([bed_x, gy, bed_x + bed_w, gy], fill="#d0d0d0", width=line_w)

            # Ticks esquerda e direita
            draw.line([bed_x - tick_px, gy, bed_x + tick_px, gy], fill="black", width=line_w)
            draw.line([bed_x + bed_w - tick_px, gy, bed_x + bed_w + tick_px, gy], fill="black", width=line_w)

            # Numeração direita em cm (10, 20, 30...)
            cm_y = int(round(cur_wy / 10.0))
            if cm_y > 0 and cur_wy < self.sheet_h_mm - 0.5:
                bbox = draw.textbbox((0, 0), str(cm_y), font=f_ruler)
                th = bbox[3] - bbox[1]
                draw.text((bed_x + bed_w + tick_px + 3, gy - th // 2), str(cm_y), fill="black", font=f_ruler)

            cur_wy += grid_step

        for piece in self.placed_pieces:
            c = piece.get("contour", [])
            if not c:
                continue
            cx = piece.get("x", 0.0)
            cy = piece.get("y", 0.0)
            rot = piece.get("rotation", 0.0)
            p_sz = str(piece.get("size") or (piece.get("shape", {}).get("size") if isinstance(piece.get("shape"), dict) else ""))
            color = piece.get("color") or (piece.get("shape", {}).get("color") if isinstance(piece.get("shape"), dict) else None) or get_color_for_size(p_sz)
            if not color or color in ("#000000", "black", "None", ""):
                color = get_color_for_size(p_sz)

            rad = math.radians(rot)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)

            poly_pts = []
            for pt in c:
                px_val = pt["x"] if isinstance(pt, dict) else pt[0]
                py_val = pt["y"] if isinstance(pt, dict) else pt[1]
                rx = px_val * cos_r - py_val * sin_r + cx
                ry = px_val * sin_r + py_val * cos_r + cy
                sx = bed_x + rx * scale_bed
                sy = bed_y + (self.sheet_h_mm - ry) * scale_bed
                poly_pts.append((sx, sy))

            if len(poly_pts) >= 3:
                draw.polygon(poly_pts, fill=color, outline="black")

        # Rodapé
        footer_y = ph - int(36 * scale)
        draw.text((m_left, footer_y), "Pages 1-1", fill="black", font=f_mono)

        return im

    def save_as_pdf(self):
        file_path = filedialog.asksaveasfilename(
            title="Salvar Layout como PDF",
            defaultextension=".pdf",
            initialfile=f"{self.layout_name.replace('.lay', '')}_report.pdf",
            filetypes=[("Documento PDF (*.pdf)", "*.pdf"), ("Todos os Arquivos (*.*)", "*.*")],
            parent=self
        )
        if file_path:
            try:
                im = self.render_pillow_page(dpi=200)
                im.save(file_path, "PDF", resolution=200.0)
                messagebox.showinfo("Exportar PDF", f"Relatório do Layout exportado com sucesso para:\n{file_path}", parent=self)
            except Exception as e:
                messagebox.showerror("Erro ao Salvar PDF", f"Falha ao gerar arquivo PDF:\n{str(e)}", parent=self)

    def save_as_png(self):
        file_path = filedialog.asksaveasfilename(
            title="Salvar Layout como Imagem PNG",
            defaultextension=".png",
            initialfile=f"{self.layout_name.replace('.lay', '')}_report.png",
            filetypes=[("Imagem PNG (*.png)", "*.png"), ("Todos os Arquivos (*.*)", "*.*")],
            parent=self
        )
        if file_path:
            try:
                im = self.render_pillow_page(dpi=200)
                im.save(file_path, "PNG")
                messagebox.showinfo("Exportar Imagem", f"Imagem do Layout salva com sucesso em:\n{file_path}", parent=self)
            except Exception as e:
                messagebox.showerror("Erro ao Salvar Imagem", f"Falha ao salvar imagem:\n{str(e)}", parent=self)

    def do_print(self):
        """Dispara a impressão física ou salva em spooler de impressão."""
        try:
            im = self.render_pillow_page(dpi=200)
            tmp_pdf = Path("/tmp") / f"print_{self.layout_name.replace('.lay', '')}.pdf"
            im.save(str(tmp_pdf), "PDF", resolution=200.0)

            if sys.platform == "win32":
                try:
                    os.startfile(str(tmp_pdf), "print")
                    messagebox.showinfo("Imprimir Layout", "Documento enviado para a impressora padrão do Windows.", parent=self)
                    return
                except Exception:
                    pass
            else:
                ret = os.system(f"which lp > /dev/null 2>&1 && lp '{str(tmp_pdf)}'")
                if ret == 0:
                    messagebox.showinfo("Imprimir Layout", "Documento enviado para a fila de impressão (CUPS/lp).", parent=self)
                    return

            messagebox.showinfo("Imprimir Layout", f"Relatório de impressão gerado com sucesso em:\n{tmp_pdf}\n\nVocê também pode utilizar o botão 'Salvar PDF...' para salvar onde desejar.", parent=self)
        except Exception as e:
            messagebox.showerror("Erro ao Imprimir", f"Falha no processo de impressão:\n{str(e)}", parent=self)
