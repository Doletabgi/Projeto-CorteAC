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
        self.geometry("860x780")
        self.minsize(680, 500)
        self.transient(parent)

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

        # Se não foram fornecidas peças reais encaixadas, usa a configuração padrão 100% autêntica
        if not self.placed_pieces:
            self.sheet_w_mm = 1500.0
            self.sheet_h_mm = 90.0
            self.dimensions_str = "1.50 X 0.09 M"
            self.mat_area_str = "0.13 sq.M."
            self.used_area_str = "0.11 sq.M."
            self.yield_pct = 83.02
            self.shapes_count = 15
            self.instances_count = 40
            self.init_sample_pieces()
        else:
            self.sheet_w_mm = float(self.layout_data.get("sheet_w_mm", 1500.0))
            self.sheet_h_mm = float(self.layout_data.get("sheet_h_mm", 90.0))

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

        self.canvas.bind("<Configure>", lambda e: self.redraw())

        # Interações de rolagem e zoom
        self.bind("<Control-MouseWheel>", self._on_ctrl_wheel)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))

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
        # 3. Gráfico do Encaixe / Chapa de Corte (como no print do usuário)
        # =====================================================================
        bed_area_y = py + int(page_h * 0.82)
        bed_max_w = int(page_w - 72 * self.zoom)
        bed_max_h = int(60 * self.zoom)

        scale_bed_x = bed_max_w / max(100.0, self.sheet_w_mm)
        scale_bed_y = bed_max_h / max(20.0, self.sheet_h_mm)
        bed_scale = min(scale_bed_x, scale_bed_y)

        bed_w = int(self.sheet_w_mm * bed_scale)
        bed_h = max(int(24 * self.zoom), int(self.sheet_h_mm * bed_scale))
        bed_x = margin_left
        bed_y = bed_area_y

        # Retângulo do Material / Chapa
        self.canvas.create_rectangle(
            bed_x, bed_y, bed_x + bed_w, bed_y + bed_h,
            fill="#ffffff", outline="#000000", width=1
        )

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
                rx = pt["x"] * cos_r - pt["y"] * sin_r + cx
                ry = pt["x"] * sin_r + pt["y"] * cos_r + cy

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
        except Exception:
            f_mono = ImageFont.load_default()
            f_mono_bold = f_mono
            f_title = f_mono
            f_small = f_mono

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

        # Gráfico do Encaixe
        bed_area_y = int(ph * 0.82)
        bed_max_w = pw - int(72 * scale)
        bed_max_h = int(60 * scale)

        scale_bed = min(bed_max_w / max(100.0, self.sheet_w_mm), bed_max_h / max(20.0, self.sheet_h_mm))
        bed_w = int(self.sheet_w_mm * scale_bed)
        bed_h = max(int(24 * scale), int(self.sheet_h_mm * scale_bed))
        bed_x = m_left
        bed_y = bed_area_y

        draw.rectangle([bed_x, bed_y, bed_x + bed_w, bed_y + bed_h], outline="black", width=max(1, int(scale)))

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
                rx = pt["x"] * cos_r - pt["y"] * sin_r + cx
                ry = pt["x"] * sin_r + pt["y"] * cos_r + cy
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
