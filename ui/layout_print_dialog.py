"""
JobManager 2000 (Python Edition)
Visualizador e Emissor de Relatório de Impressão do Layout (.lay)
Reprodução idêntica ao modelo original ATOM FlashCut (media_1792071945871.jpg)
"""

import sys
import os
import io
import math
import re
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
from PIL import Image, ImageDraw, ImageFont

from config import THEME
from cad.colors import get_color_for_size


def get_company_logo_path(create_parent=False):
    """
    Retorna o caminho do arquivo de logotipo personalizado da empresa.
    Prioriza diretório de assets da aplicação ou diretório base persistente.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent

    assets_dir = base / "assets"
    if create_parent and not assets_dir.exists():
        try:
            assets_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    p_assets = assets_dir / "company_logo.png"
    if p_assets.exists() or create_parent:
        return p_assets

    p_base = base / "company_logo.png"
    if p_base.exists():
        return p_base

    return p_assets


def open_company_logo_dialog(parent_window, on_update_callback=None):
    """Abre diálogo para o usuário definir, visualizar ou remover a logo personalizada da empresa."""
    dlg = tk.Toplevel(parent_window)
    dlg.title("Logotipo Personalizado da Empresa")
    dlg.geometry("480x360")
    dlg.minsize(420, 320)
    dlg.transient(parent_window)
    dlg.grab_set()
    dlg.configure(bg=THEME["bg_surface"], padx=16, pady=16)

    # Cabeçalho
    tk.Label(
        dlg, text="🏢 Logotipo da Empresa para Relatórios",
        font=("Segoe UI", 11, "bold"), bg=THEME["bg_surface"], fg=THEME["text_main"]
    ).pack(anchor="w", pady=(0, 4))

    tk.Label(
        dlg,
        text="Personalize o cabeçalho das impressões e relatórios A4 substituindo o logotipo.",
        font=("Segoe UI", 8), bg=THEME["bg_surface"], fg="#555555"
    ).pack(anchor="w", pady=(0, 12))

    # Quadro de visualização da logo atual
    preview_box = tk.LabelFrame(
        dlg, text="Prévia Atual da Logo", font=("Segoe UI", 8, "bold"),
        bg="#ffffff", relief="groove", bd=1, padx=10, pady=10
    )
    preview_box.pack(fill="both", expand=True, pady=(0, 12))

    lbl_logo_preview = tk.Label(preview_box, bg="#ffffff")
    lbl_logo_preview.pack(expand=True)

    lbl_info = tk.Label(preview_box, text="", font=("Segoe UI", 8), bg="#ffffff", fg="#666666")
    lbl_info.pack(side="bottom")

    btn_remove = [None]

    def refresh_dialog_preview():
        logo_path = get_company_logo_path()
        if logo_path.exists():
            try:
                raw = Image.open(str(logo_path)).convert("RGBA")
                ow, oh = raw.size
                ratio = min(260 / max(1, ow), 90 / max(1, oh))
                pw, ph = max(1, int(ow * ratio)), max(1, int(oh * ratio))
                res = raw.resize((pw, ph), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                res.save(buf, format="PNG")
                photo = tk.PhotoImage(data=buf.getvalue())
                lbl_logo_preview.config(image=photo, text="")
                lbl_logo_preview.image = photo
                lbl_info.config(text=f"Resolução original: {ow} × {oh} px")
                if btn_remove[0]:
                    btn_remove[0].config(state="normal")
                return
            except Exception:
                pass
        lbl_logo_preview.config(
            image="",
            text="[Nenhum logotipo configurado]\nO cabeçalho dos relatórios será emitido limpo.",
            font=("Segoe UI", 9, "italic"),
            fg="#888888"
        )
        lbl_info.config(text="")
        if btn_remove[0]:
            btn_remove[0].config(state="disabled")

    def on_choose_logo():
        fpath = filedialog.askopenfilename(
            title="Selecionar Logotipo da Empresa",
            parent=dlg,
            filetypes=[
                ("Imagens Suportadas", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"),
                ("Imagens PNG", "*.png"),
                ("Imagens JPEG", "*.jpg *.jpeg"),
                ("Todos os Arquivos", "*.*")
            ]
        )
        if not fpath:
            return
        try:
            im = Image.open(fpath).convert("RGBA")
            target = get_company_logo_path(create_parent=True)
            im.save(str(target), format="PNG")
            refresh_dialog_preview()
            if callable(on_update_callback):
                on_update_callback()
            messagebox.showinfo(
                "Logotipo da Empresa",
                "Logotipo atualizado com sucesso!\nEle será exibido em todas as impressões e relatórios.",
                parent=dlg
            )
        except Exception as ex:
            messagebox.showerror("Erro ao Carregar Imagem", f"Não foi possível carregar a imagem:\n{ex}", parent=dlg)

    def on_remove_logo():
        if messagebox.askyesno("Remover Logotipo", "Deseja remover o logotipo personalizado da empresa?", parent=dlg):
            target = get_company_logo_path()
            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass
            alt = Path(__file__).resolve().parent.parent / "company_logo.png"
            if alt.exists():
                try:
                    alt.unlink()
                except Exception:
                    pass
            refresh_dialog_preview()
            if callable(on_update_callback):
                on_update_callback()
            messagebox.showinfo("Logotipo Removido", "O logotipo foi removido. Os relatórios serão emitidos limpos.", parent=dlg)

    btn_bar = tk.Frame(dlg, bg=THEME["bg_surface"])
    btn_bar.pack(fill="x")

    tk.Button(
        btn_bar, text="📂 Escolher Nova Logo...",
        bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff",
        font=("Segoe UI", 9, "bold"), relief="raised", bd=1, padx=10, pady=4, cursor="hand2",
        command=on_choose_logo
    ).pack(side="left", padx=(0, 6))

    btn_remove[0] = tk.Button(
        btn_bar, text="🗑️ Remover Logo",
        bg=THEME["bg_surface"], fg="#dc2626", font=("Segoe UI", 9),
        relief="raised", bd=1, padx=8, pady=4, cursor="hand2",
        command=on_remove_logo
    )
    btn_remove[0].pack(side="left", padx=2)

    tk.Button(
        btn_bar, text="✓ Concluir",
        bg=THEME["bg_surface"], fg=THEME["text_main"],
        font=("Segoe UI", 9), relief="raised", bd=1, padx=12, pady=4, cursor="hand2",
        command=dlg.destroy
    ).pack(side="right")

    refresh_dialog_preview()
    return dlg


def format_size(size_val) -> str:
    """
    Formata o tamanho para exibição industrial na legenda:
    - Tamanho inteiro sem decimais (ex: 28)
    - Meio número com uma casa decimal (ex: 35.5)
    - Suporta floats, inteiros e strings (ex: '28.00', '35.50', '33_5a', '28a')
    """
    if size_val is None:
        return ""
    s = str(size_val).strip()
    if not s or s.lower() in ("none", "null", ""):
        return ""
    s_norm = s.replace("_", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", s_norm)
    if m:
        try:
            val = float(m.group(1))
            if val.is_integer():
                return str(int(val))
            if (val * 2).is_integer():
                return f"{val:.1f}"
            return f"{val:.2f}".rstrip("0").rstrip(".")
        except (ValueError, TypeError):
            pass
    return s


def extract_molde_base_name(raw_name: str, raw_size: str = "") -> str:
    """
    Extrai o nome base canônico do molde, removendo caminhos, extensões .die
    e sufixos de numeração (ex: '129_187_Tras_28a' -> '129_187_Tras').
    """
    if not raw_name:
        return "Molde"
    name = str(raw_name).strip()
    for ext in (".die", ".Die", ".DIE", ".shp", ".SHP", ".d", ".D"):
        if name.endswith(ext):
            name = name[:-len(ext)]
    if raw_size:
        clean_sz = str(raw_size).strip()
        fmt_sz = format_size(clean_sz)
        variations = {clean_sz, fmt_sz, clean_sz.replace(".", "_"), clean_sz.replace("_", ".")}
        for v in sorted(variations, key=len, reverse=True):
            if not v:
                continue
            pat = rf"[\s_\-]+{re.escape(v)}[a-zA-Z]?$"
            subbed = re.sub(pat, "", name, flags=re.IGNORECASE)
            if subbed != name and subbed.strip():
                name = subbed
                break
    m = re.search(r"^(.*?)(?:[\s_\-]+(\d+(?:[_\.]\d+)?[a-zA-Z]?))$", name)
    if m and m.group(1) and not m.group(1).endswith("_"):
        candidate_num = re.findall(r"\d+", m.group(2))
        if candidate_num and 15 <= int(candidate_num[0]) <= 55:
            name = m.group(1)
    return name.strip() or str(raw_name).strip()


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
        # Metadados do Material: Código, Descrição e Camadas dinâmicos
        raw_mat_name = self.layout_data.get("material_name")
        mat_code = self.layout_data.get("material_code")
        mat_desc = self.layout_data.get("material_desc") or self.layout_data.get("material_description")
        mat_layers = self.layout_data.get("material_layers")
        if mat_layers is None:
            mat_layers = self.layout_data.get("layers")

        mat_obj = self.layout_data.get("material")
        if isinstance(mat_obj, dict):
            if mat_code is None:
                mat_code = mat_obj.get("code") or mat_obj.get("id")
            if mat_desc is None:
                mat_desc = mat_obj.get("name") or mat_obj.get("description") or mat_obj.get("desc")
            if mat_layers is None:
                mat_layers = mat_obj.get("layers")

        if mat_code is not None or mat_desc is not None or mat_layers is not None:
            c_str = str(mat_code).strip() if mat_code is not None else ""
            d_str = str(mat_desc).strip() if mat_desc is not None else ""
            l_val = int(mat_layers) if mat_layers is not None else 1

            if d_str and c_str:
                if d_str.startswith(f"{c_str} -") or d_str == c_str:
                    base_mat = d_str
                else:
                    base_mat = f"{c_str} - {d_str}"
            elif d_str:
                base_mat = d_str
            elif c_str:
                base_mat = c_str
            else:
                base_mat = "853412 - SINT-LOGAM-PRETO"

            if "layer(s)" in base_mat.lower():
                if mat_layers is not None:
                    self.material_name = re.sub(r"\(\s*\d+\s*layer\(s\)\s*\)", f"( {l_val} layer(s) )", base_mat, flags=re.IGNORECASE)
                else:
                    self.material_name = base_mat
            else:
                self.material_name = f"{base_mat} ( {l_val} layer(s) )"
        elif raw_mat_name:
            if "layer(s)" not in raw_mat_name.lower():
                self.material_name = f"{raw_mat_name} ( 1 layer(s) )"
            else:
                self.material_name = raw_mat_name
        else:
            self.material_name = "132011 - VELCRO 4'' ARGOLA - PRETO ( 4 layer(s) )"

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

        # Metadados de sessão e moldes para legenda
        self.session_shapes = self.layout_data.get("session_shapes") or self.layout_data.get("shapes") or []
        self.layouts = self.layout_data.get("layouts", [])
        self.current_layout_index = self.layout_data.get("current_layout_index", 0)
        self.material_layers = int(mat_layers) if mat_layers is not None else 2

        # Orientação da folha (retrato ou paisagem)
        self.orientation = self.layout_data.get("orientation", "portrait")
        if self.orientation == "landscape":
            self.page_w_base = 842
            self.page_h_base = 595
        else:
            self.page_w_base = 595
            self.page_h_base = 842

        # Legenda calculada
        self.legend_data = self.layout_data.get("legend_data")
        if self.legend_data is None:
            self.legend_data = self.build_legend_data()

        # Carrega logotipo da empresa
        self.load_company_logo()

        # Monta a barra de ferramentas superior e a área de rolagem da folha
        self.setup_ui()

        # Renderiza a página inicialmente
        self.redraw()
        self.after(50, self.fit_to_page)

    def load_company_logo(self):
        """Carrega a imagem de logotipo customizada da empresa se configurada."""
        self.company_logo_raw = None
        self.logo_img = None
        self._logo_photo_cache = {}

        logo_path = get_company_logo_path()
        if logo_path.exists():
            try:
                self.company_logo_raw = Image.open(str(logo_path)).convert("RGBA")
            except Exception:
                self.company_logo_raw = None

    def load_atom_logo(self):
        """Compatibilidade com código legado."""
        self.load_company_logo()

    def get_scaled_logo_photo(self, max_w, max_h):
        """Redimensiona a logo da empresa proporcionalmente e retorna tk.PhotoImage via memória."""
        if not getattr(self, "company_logo_raw", None):
            return None
        try:
            ow, oh = self.company_logo_raw.size
            if ow <= 0 or oh <= 0:
                return None
            ratio = min(max_w / ow, max_h / oh)
            nw = max(1, int(ow * ratio))
            nh = max(1, int(oh * ratio))

            cache_key = (nw, nh)
            if hasattr(self, "_logo_photo_cache") and self._logo_photo_cache.get("key") == cache_key:
                return self._logo_photo_cache["photo"]

            resized = self.company_logo_raw.resize((nw, nh), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, format="PNG")
            photo = tk.PhotoImage(data=buf.getvalue())
            self._logo_photo_cache = {"key": cache_key, "photo": photo}
            return photo
        except Exception:
            return None

    def open_logo_manager_dialog(self):
        """Abre diálogo para o usuário definir, visualizar ou remover a logo personalizada da empresa."""
        open_company_logo_dialog(self, on_update_callback=self._on_logo_updated)

    def _on_logo_updated(self):
        self.load_company_logo()
        self.redraw()

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
                    "rotation": 0.0,
                    "name": "Velcro",
                    "size": "36"
                })

    def build_legend_data(self):
        """
        Constrói a lista estruturada da legenda por molde:
        [
            {
                "molde_name": str,
                "shape_id": int/str or None,
                "sizes": [
                    {"size": str, "n": int, "m": int, "is_error": bool},
                    ...
                ]
            }, ...
        ]
        """
        if self.layout_data.get("legend_data"):
            return self.layout_data.get("legend_data")

        session_shapes = self.session_shapes or []
        placed_pieces = self.placed_pieces or []
        layouts = self.layouts or []
        layers = max(1, getattr(self, "material_layers", 2) or 2)
        is_multi_plate = (len(layouts) > 1)

        # 1. Mapeamento de demanda da sessão e ShapeId a partir de session_shapes
        session_m = {}         # (molde_name, fmt_size) -> int
        molde_shape_ids = {}   # molde_name -> shape_id
        moldes_order = []      # [molde_name, ...]
        sizes_by_molde = {}    # molde_name -> set(fmt_size)

        for shp in session_shapes:
            if not isinstance(shp, dict):
                continue
            s_name = shp.get("name") or "Molde"
            s_size_raw = shp.get("size") or ""
            m_name = extract_molde_base_name(s_name, s_size_raw)
            fmt_sz = format_size(s_size_raw)
            s_id = shp.get("shape_id") if shp.get("shape_id") is not None else shp.get("id")
            m_pairs = int(shp.get("pairs") or shp.get("required_qty", 0) or shp.get("required", 0) or 0)

            if m_name not in moldes_order:
                moldes_order.append(m_name)
            if m_name not in molde_shape_ids and s_id is not None and str(s_id).strip():
                molde_shape_ids[m_name] = str(s_id).strip()
            if m_name not in sizes_by_molde:
                sizes_by_molde[m_name] = set()
            if fmt_sz:
                sizes_by_molde[m_name].add(fmt_sz)
                session_m[(m_name, fmt_sz)] = m_pairs

        # 2. Contagem de peças/pares na placa atual (placed_pieces)
        placed_counts = {}   # (molde_name, fmt_size) -> piece count
        explicit_pairs = {}  # (molde_name, fmt_size) -> explicit pair count if provided

        for p in placed_pieces:
            if not isinstance(p, dict):
                continue
            p_name = p.get("name") or p.get("shape_name") or (p.get("shape", {}).get("name") if isinstance(p.get("shape"), dict) else "") or "Molde"
            p_size_raw = p.get("size") or (p.get("shape", {}).get("size") if isinstance(p.get("shape"), dict) else "")
            m_name = extract_molde_base_name(p_name, p_size_raw)
            fmt_sz = format_size(p_size_raw)
            if not fmt_sz and "size" in p:
                fmt_sz = format_size(p["size"])
            if not fmt_sz:
                fmt_sz = "41"

            if m_name not in moldes_order:
                moldes_order.append(m_name)
            if m_name not in sizes_by_molde:
                sizes_by_molde[m_name] = set()
            sizes_by_molde[m_name].add(fmt_sz)

            p_sid = p.get("shape_id") or p.get("target_id") or (p.get("shape", {}).get("id") if isinstance(p.get("shape"), dict) else None)
            if m_name not in molde_shape_ids and p_sid is not None and str(p_sid).strip():
                molde_shape_ids[m_name] = str(p_sid).strip()

            k = (m_name, fmt_sz)
            if "pairs" in p and p["pairs"] is not None:
                explicit_pairs[k] = explicit_pairs.get(k, 0) + int(p["pairs"])
            else:
                placed_counts[k] = placed_counts.get(k, 0) + 1

        # 3. Em multi-placa, calcula somatório total entre placas se session_m não estiver presente
        multi_plate_totals = {}
        if is_multi_plate and not session_m:
            for ly in layouts:
                ly_pcs = ly.get("pieces") or ly.get("placed_pieces") or []
                for p in ly_pcs:
                    if not isinstance(p, dict):
                        continue
                    p_name = p.get("name") or p.get("shape_name") or (p.get("shape", {}).get("name") if isinstance(p.get("shape"), dict) else "") or "Molde"
                    p_size_raw = p.get("size") or (p.get("shape", {}).get("size") if isinstance(p.get("shape"), dict) else "")
                    m_name = extract_molde_base_name(p_name, p_size_raw)
                    fmt_sz = format_size(p_size_raw) or "41"
                    k = (m_name, fmt_sz)
                    if "pairs" in p and p["pairs"] is not None:
                        multi_plate_totals[k] = multi_plate_totals.get(k, 0) + int(p["pairs"])
                    else:
                        multi_plate_totals[k] = multi_plate_totals.get(k, 0) + 1

            for k in list(multi_plate_totals.keys()):
                if k not in explicit_pairs:
                    multi_plate_totals[k] = (multi_plate_totals[k] * layers) // 2

        # 4. Monta lista consolidada de moldes e tamanhos
        legend_result = []

        def _size_key(sz_str):
            m = re.search(r"(\d+(?:\.\d+)?)", str(sz_str))
            return float(m.group(1)) if m else 0.0

        for m_name in moldes_order:
            all_szs = sorted(list(sizes_by_molde.get(m_name, [])), key=_size_key)
            size_list = []

            for sz in all_szs:
                k = (m_name, sz)
                if k in explicit_pairs:
                    n = explicit_pairs[k]
                elif k in placed_counts:
                    n = (placed_counts[k] * layers) // 2
                else:
                    n = 0

                if k in session_m and session_m[k] > 0:
                    m = session_m[k]
                elif is_multi_plate and k in multi_plate_totals and multi_plate_totals[k] > 0:
                    m = multi_plate_totals[k]
                else:
                    m = n

                # Não lista tamanhos com 0 peças na placa atual se não foram solicitados
                if n == 0 and (k not in session_m or session_m[k] == 0):
                    continue

                # Se n == 0 nesta placa em multi-placa e há outras peças deste molde aqui:
                if n == 0 and is_multi_plate:
                    has_other_placed = any(placed_counts.get((m_name, other_sz), 0) > 0 or explicit_pairs.get((m_name, other_sz), 0) > 0 for other_sz in all_szs)
                    if has_other_placed:
                        continue

                is_error = (n > m)
                size_list.append({
                    "size": sz,
                    "n": n,
                    "m": m,
                    "is_error": is_error
                })

            if size_list:
                legend_result.append({
                    "molde_name": m_name,
                    "shape_id": molde_shape_ids.get(m_name),
                    "sizes": size_list
                })

        return legend_result

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

        tk.Button(
            tb, text="🏢 Logotipo...", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9, "bold"), padx=6, command=self.open_logo_manager_dialog
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

        # Logotipo da Empresa no canto superior esquerdo (se configurado)
        logo_y = margin_top + int(12 * self.zoom)
        max_logo_w = int(140 * self.zoom)
        max_logo_h = int(36 * self.zoom)
        logo_photo = self.get_scaled_logo_photo(max_logo_w, max_logo_h)
        if logo_photo:
            self.canvas.create_image(margin_left, logo_y, image=logo_photo, anchor="nw")

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
        # 2.5. Tabela de Legenda por Molde (com ShapeId e contagem n/m)
        # =====================================================================
        meta_end_y = meta_y + int(18 * self.zoom)
        footer_y = py + page_h - int(24 * self.zoom)

        legend_rows = getattr(self, "legend_data", None)
        if legend_rows is None:
            self.legend_data = self.build_legend_data()
            legend_rows = self.legend_data

        f_legend_name = ("Courier", f_size_md, "bold")
        f_size_sub = max(5, int(f_size_md * 0.72))
        f_legend_sub = ("Courier", f_size_sub)
        f_footnote = ("Courier", max(5, int(f_size_sub * 0.92)))
        line_step = max(10, int(13 * self.zoom))

        table_end_y = meta_end_y
        if legend_rows:
            table_y = meta_end_y + int(6 * self.zoom)

            # Fonte Tkinter para medição precisa de texto
            try:
                tk_sub_font = tkfont.Font(family="Courier", size=f_size_sub)
                tk_name_font = tkfont.Font(family="Courier", size=f_size_md, weight="bold")
            except Exception:
                tk_sub_font = None
                tk_name_font = None

            def _measure_sub(txt):
                if tk_sub_font:
                    try:
                        return tk_sub_font.measure(txt)
                    except Exception:
                        pass
                return int(len(txt) * max(3.5, f_size_sub * 0.62))

            def _measure_name(txt):
                if tk_name_font:
                    try:
                        return tk_name_font.measure(txt)
                    except Exception:
                        pass
                return int(len(txt) * max(4.0, f_size_md * 0.62))

            max_left_w = 0
            for row in legend_rows:
                m_name = row.get("molde_name", "")
                s_id = row.get("shape_id")
                w_est = _measure_name(m_name)
                if s_id is not None and str(s_id).strip():
                    w_est += _measure_sub(f"  #{str(s_id).strip()}")
                if w_est > max_left_w:
                    max_left_w = w_est

            left_col_w = max(int(140 * self.zoom), min(int(240 * self.zoom), max_left_w + int(12 * self.zoom)))
            col2_x = margin_left + left_col_w
            avail_right_w = max(50, margin_right - col2_x)

            for row in legend_rows:
                m_name = row.get("molde_name", "")
                s_id = row.get("shape_id")
                row_start_y = table_y

                # Coluna Esquerda: Nome do Molde
                self.canvas.create_text(
                    margin_left, row_start_y,
                    text=m_name, anchor="nw",
                    font=f_legend_name, fill="#000000",
                    tags="print_legend_name"
                )

                # ShapeId ao lado em fonte menor e cinza escuro
                if s_id is not None and str(s_id).strip():
                    name_w = _measure_name(m_name)
                    self.canvas.create_text(
                        margin_left + name_w + int(4 * self.zoom), row_start_y + int(1.5 * self.zoom),
                        text=f"  #{str(s_id).strip()}", anchor="nw",
                        font=f_legend_sub, fill="#555555",
                        tags="print_legend_shape_id"
                    )

                # Coluna Direita: Lista por tamanho no formato tamanho: n/m
                size_items = row.get("sizes", [])
                tokens = []
                for s_item in size_items:
                    sz_str = str(s_item["size"])
                    n_val = s_item["n"]
                    m_val = s_item["m"]
                    tokens.append((f"{sz_str}: {n_val}/{m_val}", bool(s_item.get("is_error", n_val > m_val))))

                # Quebra de linha entre tamanhos (nunca no meio de um token)
                lines_of_tokens = []
                cur_line = []
                cur_w = 0
                sep_w = _measure_sub(", ")

                for tok_txt, is_err in tokens:
                    tok_w = _measure_sub(tok_txt)
                    extra = sep_w if cur_line else 0
                    if cur_line and (cur_w + extra + tok_w > avail_right_w):
                        lines_of_tokens.append(cur_line)
                        cur_line = [(tok_txt, is_err)]
                        cur_w = tok_w
                    else:
                        cur_line.append((tok_txt, is_err))
                        cur_w += extra + tok_w

                if cur_line:
                    lines_of_tokens.append(cur_line)

                # Renderiza linhas da coluna direita
                cur_y = row_start_y
                for tok_line in lines_of_tokens:
                    cur_x = col2_x
                    for t_idx, (tok_txt, is_err) in enumerate(tok_line):
                        if t_idx > 0:
                            self.canvas.create_text(
                                cur_x, cur_y + int(1.5 * self.zoom),
                                text=", ", anchor="nw",
                                font=f_legend_sub, fill="#444444",
                                tags="print_legend_size"
                            )
                            cur_x += sep_w

                        tok_fill = "#dc2626" if is_err else "#333333"
                        self.canvas.create_text(
                            cur_x, cur_y + int(1.5 * self.zoom),
                            text=tok_txt, anchor="nw",
                            font=f_legend_sub, fill=tok_fill,
                            tags="print_legend_size"
                        )
                        cur_x += _measure_sub(tok_txt)

                    cur_y += line_step

                row_h = max(line_step, len(lines_of_tokens) * line_step)
                table_y += row_h + int(2 * self.zoom)

            # Rodapé explicativo da legenda
            self.canvas.create_text(
                margin_left, table_y,
                text="n/m = pares nesta placa / pedido total",
                anchor="nw", font=f_footnote, fill="#666666",
                tags="print_legend_footnote"
            )
            table_y += int(11 * self.zoom)
            table_end_y = table_y

        # =====================================================================
        # 3. Gráfico do Encaixe / Chapa de Corte (Proporcional à Folha A4)
        # =====================================================================
        avail_top = table_end_y + int(10 * self.zoom)
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

        # Linha de Corte de Refile (CAM) se configurada
        trim_cut = self.layout_data.get("trim_cut_line")
        if trim_cut and trim_cut.get("enabled", True):
            cut_y = float(trim_cut.get("y", self.sheet_h_mm))
            cut_sy = bed_y + (self.sheet_h_mm - cut_y) * bed_scale
            self.canvas.create_line(
                bed_x - 4, cut_sy, bed_x + bed_w + 4, cut_sy,
                fill="#dc2626",
                dash=(6, 3),
                width=2,
                tags="print_trim_line"
            )
            self.canvas.create_text(
                bed_x + bed_w / 2, max(bed_y + 8, cut_sy - 8),
                text=f"✂ CORTE DE REFILE: {cut_y / 10.0:.1f} cm",
                font=f_ruler,
                fill="#dc2626",
                tags="print_trim_text"
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
        # A4 em polegadas: 8.27 x 11.69 polegadas (retrato ou paisagem)
        if getattr(self, "orientation", "portrait") == "landscape":
            pw = int(11.69 * dpi)
            ph = int(8.27 * dpi)
        else:
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
            f_legend_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", max(6, int(6.8 * scale)))
            f_footnote = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", max(5, int(6.2 * scale)))
        except Exception:
            f_mono = ImageFont.load_default()
            f_mono_bold = f_mono
            f_title = f_mono
            f_small = f_mono
            f_ruler = f_mono
            f_legend_sub = f_mono
            f_footnote = f_mono

        m_left = int(36 * scale)
        m_right = pw - int(36 * scale)
        m_top = int(30 * scale)

        # Topo
        draw.text((m_left, m_top), self.unc_prefix + "\\", fill="black", font=f_small)

        # Logotipo da Empresa (se configurado)
        if getattr(self, "company_logo_raw", None):
            try:
                max_w = int(140 * scale)
                max_h = int(36 * scale)
                ow, oh = self.company_logo_raw.size
                if ow > 0 and oh > 0:
                    ratio = min(max_w / ow, max_h / oh)
                    lw = max(1, int(ow * ratio))
                    lh = max(1, int(oh * ratio))
                    logo_resized = self.company_logo_raw.resize((lw, lh), Image.Resampling.LANCZOS)
                    im.paste(logo_resized, (m_left, m_top + int(12 * scale)), logo_resized)
            except Exception:
                pass

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

        # =====================================================================
        # 2.5. Tabela de Legenda por Molde no Pillow (com ShapeId e n/m)
        # =====================================================================
        meta_end_y = meta_y + int(18 * scale)
        footer_y = ph - int(36 * scale)

        legend_rows = getattr(self, "legend_data", None)
        if legend_rows is None:
            self.legend_data = self.build_legend_data()
            legend_rows = self.legend_data

        table_end_y = meta_end_y
        line_step = max(11, int(13 * scale))

        if legend_rows:
            table_y = meta_end_y + int(6 * scale)

            def _measure_pillow(txt, font):
                bb = draw.textbbox((0, 0), txt, font=font)
                return bb[2] - bb[0]

            max_left_w = 0
            for row in legend_rows:
                m_name = row.get("molde_name", "")
                s_id = row.get("shape_id")
                w_est = _measure_pillow(m_name, f_mono_bold)
                if s_id is not None and str(s_id).strip():
                    w_est += _measure_pillow(f"  #{str(s_id).strip()}", f_legend_sub)
                if w_est > max_left_w:
                    max_left_w = w_est

            left_col_w = max(int(140 * scale), min(int(240 * scale), max_left_w + int(12 * scale)))
            col2_x = m_left + left_col_w
            avail_right_w = max(50, m_right - col2_x)

            sep_w = _measure_pillow(", ", f_legend_sub)

            for row in legend_rows:
                m_name = row.get("molde_name", "")
                s_id = row.get("shape_id")
                row_start_y = table_y

                # Coluna Esquerda: Nome do Molde
                draw.text((m_left, row_start_y), m_name, fill="black", font=f_mono_bold)

                # ShapeId ao lado em fonte menor e cinza escuro
                if s_id is not None and str(s_id).strip():
                    name_w = _measure_pillow(m_name, f_mono_bold)
                    draw.text(
                        (m_left + name_w + int(4 * scale), row_start_y + int(1.5 * scale)),
                        f"  #{str(s_id).strip()}", fill="#555555", font=f_legend_sub
                    )

                # Coluna Direita: Lista por tamanho
                size_items = row.get("sizes", [])
                tokens = []
                for s_item in size_items:
                    sz_str = str(s_item["size"])
                    n_val = s_item["n"]
                    m_val = s_item["m"]
                    tokens.append((f"{sz_str}: {n_val}/{m_val}", bool(s_item.get("is_error", n_val > m_val))))

                lines_of_tokens = []
                cur_line = []
                cur_w = 0

                for tok_txt, is_err in tokens:
                    tok_w = _measure_pillow(tok_txt, f_legend_sub)
                    extra = sep_w if cur_line else 0
                    if cur_line and (cur_w + extra + tok_w > avail_right_w):
                        lines_of_tokens.append(cur_line)
                        cur_line = [(tok_txt, is_err)]
                        cur_w = tok_w
                    else:
                        cur_line.append((tok_txt, is_err))
                        cur_w += extra + tok_w

                if cur_line:
                    lines_of_tokens.append(cur_line)

                cur_y = row_start_y
                for tok_line in lines_of_tokens:
                    cur_x = col2_x
                    for t_idx, (tok_txt, is_err) in enumerate(tok_line):
                        if t_idx > 0:
                            draw.text((cur_x, cur_y + int(1.5 * scale)), ", ", fill="#444444", font=f_legend_sub)
                            cur_x += sep_w

                        tok_fill = "#dc2626" if is_err else "#333333"
                        draw.text((cur_x, cur_y + int(1.5 * scale)), tok_txt, fill=tok_fill, font=f_legend_sub)
                        cur_x += _measure_pillow(tok_txt, f_legend_sub)

                    cur_y += line_step

                row_h = max(line_step, len(lines_of_tokens) * line_step)
                table_y += row_h + int(2 * scale)

            draw.text((m_left, table_y), "n/m = pares nesta placa / pedido total", fill="#666666", font=f_footnote)
            table_y += int(11 * scale)
            table_end_y = table_y

        # =====================================================================
        # 3. Gráfico do Encaixe Proporcional à Folha A4
        # =====================================================================
        avail_top = table_end_y + int(10 * scale)
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

        # Linha de Corte de Refile (CAM) se configurada
        trim_cut = self.layout_data.get("trim_cut_line")
        if trim_cut and trim_cut.get("enabled", True):
            cut_y = float(trim_cut.get("y", self.sheet_h_mm))
            cut_sy = bed_y + (self.sheet_h_mm - cut_y) * scale_bed
            draw.line([(bed_x - int(4 * scale), cut_sy), (bed_x + bed_w + int(4 * scale), cut_sy)], fill="#dc2626", width=max(2, int(2 * scale)))
            draw.text((bed_x + bed_w / 2 - int(50 * scale), max(bed_y + 4, cut_sy - int(12 * scale))), f"CORTE DE REFILE: {cut_y / 10.0:.1f} cm", fill="#dc2626", font=f_ruler)

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
