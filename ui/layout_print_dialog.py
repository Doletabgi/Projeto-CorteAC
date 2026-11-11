"""
JobManager 2000 (Python Edition)
Visualizador e emissor da ficha de produção A4 do layout (.lay).
"""

import sys
import os
import io
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Tuple
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image

from config import THEME
from ui.units import format_m, format_dim_mm
from cad.colors import get_color_for_size
from cad.layers_rule import (
    resolve_layout_layers,
)
from cad.geometry import polygon_area, transform_contour


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


def format_shape_id_tag(s_id) -> str:
    """
    Formata o identificador do molde para a legenda:
    Retorna '  #{s_id}' se presente (evitando duplicar #), ou '' se ausente.
    """
    if s_id is None:
        return ""
    sid_str = str(s_id).strip()
    if not sid_str:
        return ""
    if sid_str.startswith("#"):
        return f"  {sid_str}"
    return f"  #{sid_str}"


def _clamp_tip_zone(tip_zone, sheet_w_mm, sheet_h_mm):
    """Alias para o clamp compartilhado (cad.layers_rule.clamp_tip_zone)."""
    from cad.layers_rule import clamp_tip_zone

    return clamp_tip_zone(tip_zone, sheet_w_mm, sheet_h_mm)


def _desenhar_retangulo_tracejado(draw, box, cor="#2563eb", largura=2, traco=6, vao=4):
    """Desenha um retângulo com linha TRACEJADA no Pillow (a API não tem dash nativo)."""
    x0, y0, x1, y1 = (int(round(v)) for v in box)

    def _linha_h(xa, xb, y):
        passo = traco + vao
        x = min(xa, xb)
        fim = max(xa, xb)
        while x < fim:
            draw.line([(x, y), (min(x + traco, fim), y)], fill=cor, width=largura)
            x += passo

    def _linha_v(ya, yb, x):
        passo = traco + vao
        y = min(ya, yb)
        fim = max(ya, yb)
        while y < fim:
            draw.line([(x, y), (x, min(y + traco, fim))], fill=cor, width=largura)
            y += passo

    _linha_h(x0, x1, y0)
    _linha_h(x0, x1, y1)
    _linha_v(y0, y1, x0)
    _linha_v(y0, y1, x1)


class LayoutPrintDialog(tk.Toplevel):
    """
    Janela modal de Visualização de Impressão (Print Preview) do Layout Editor.
    Exibe a ficha A4 com identificação, preparação, produção e mapa de corte.
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

        self.unc_prefix = self.layout_data.get("unc_prefix", r"\\Lab-inf\NSDATAv1")
        self.description = self.layout_data.get("description", "fn98 - v1.2.36 - 12.09.2012")
        self.date_str = self.layout_data.get("date_str") or datetime.now().strftime("%d/%m/%Y %H:%M")
        self.gap_str = self.layout_data.get("gap_str", "1.00 mm")

        # Metadados de sessão e moldes para legenda
        self.session_shapes = self.layout_data.get("session_shapes") or self.layout_data.get("shapes") or []

        # Descobre layouts disponíveis da sessão
        raw_layouts = self.layout_data.get("layouts")
        if not raw_layouts:
            if hasattr(parent, "layouts") and getattr(parent, "layouts", None):
                raw_layouts = list(parent.layouts)
            elif hasattr(parent, "session_data") and isinstance(parent.session_data, dict) and parent.session_data.get("layouts"):
                raw_layouts = list(parent.session_data.get("layouts", []))
            elif hasattr(parent, "current_session") and isinstance(parent.current_session, dict) and parent.current_session.get("layouts"):
                raw_layouts = list(parent.current_session.get("layouts", []))

        self.layouts = [dict(l) for l in raw_layouts] if raw_layouts else [dict(self.layout_data)]
        self.current_layout_index = int(self.layout_data.get("current_layout_index", 0) or 0)
        if self.current_layout_index < 0 or self.current_layout_index >= len(self.layouts):
            self.current_layout_index = 0

        # Metadados de material padrão
        self._setup_material_metadata()

        # Orientação da folha (retrato ou paisagem)
        self.orientation = self.layout_data.get("orientation", "portrait")
        if self.orientation == "landscape":
            self.page_w_base = 842
            self.page_h_base = 595
        else:
            self.page_w_base = 595
            self.page_h_base = 842

        # Carrega logotipo da empresa
        self.load_company_logo()

        # Conexão com banco e usuário ativo para impressão
        self.db = self.layout_data.get("db") or getattr(parent, "db", None)
        if self.db is None:
            try:
                from database import DatabaseManager
                self.db = DatabaseManager()
            except Exception:
                self.db = None

        self.active_user = self.layout_data.get("active_user")
        if self.active_user is None and self.db:
            try:
                self.active_user = self.db.get_active_user()
            except Exception:
                self.active_user = ""
        self.active_user = self.active_user or ""

        self.user_print_prefix = self.layout_data.get("user_print_prefix")
        if self.user_print_prefix is None and self.db:
            try:
                self.user_print_prefix = self.db.get_user_print_prefix()
            except Exception:
                self.user_print_prefix = "Usuário"
        if self.user_print_prefix is None:
            self.user_print_prefix = "Usuário"

        # Monta a barra de ferramentas superior e a área de rolagem da folha
        self.setup_ui()

        # Carrega a placa/layout ativo
        self.load_layout_index(self.current_layout_index, initial=True)

        # Renderiza a página inicialmente
        self.redraw()
        self.after(50, self.fit_to_page)

    def _setup_material_metadata(self, source=None):
        """Carrega e formata a descrição base do material."""
        src = source if isinstance(source, dict) else self.layout_data
        raw_mat_name = src.get("material_name")
        mat_code = src.get("material_code")
        mat_desc = src.get("material_desc") or src.get("material_description")
        mat_layers = src.get("material_layers")
        if mat_layers is None:
            mat_layers = src.get("layers")

        mat_obj = src.get("material")
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
                base_mat = "Material não informado"

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
            self.material_name = "Material não informado"

    def load_layout_index(self, index: int, initial: bool = False) -> bool:
        """
        Carrega todos os dados da placa/layout no índice especificado.
        Atualiza geometrias, metadados, legenda, título e controles de navegação.
        """
        if not getattr(self, "layouts", None) or index < 0 or index >= len(self.layouts):
            return False

        self.current_layout_index = index
        cur_layout = self.layouts[index]
        self.current_layout = cur_layout if isinstance(cur_layout, dict) else {}

        # 0. Sincroniza metadados específicos da sessão/placa (suporte a impressão em massa)
        cur_shapes = self.current_layout.get("session_shapes") or self.current_layout.get("shapes")
        if cur_shapes:
            self.session_shapes = cur_shapes
        elif self.current_layout.get("session_id") and self.current_layout.get("session_id") != self.layout_data.get("session_id"):
            self.session_shapes = []
        else:
            self.session_shapes = self.layout_data.get("session_shapes") or []

        if any(k in self.current_layout for k in ("material", "material_code", "material_name", "material_desc")):
            self._setup_material_metadata(source=self.current_layout)
        else:
            self._setup_material_metadata(source=self.layout_data)

        gap = self.current_layout.get("gap_mm")
        if gap is not None:
            self.gap_str = f"{float(gap):.2f} mm".replace(".", ",")
        else:
            self.gap_str = self.layout_data.get("gap_str", "não informado")

        # 1. Nome do layout e título da janela
        raw_name = self.current_layout.get("name") or self.current_layout.get("layout_name") or self.current_layout.get("code")
        if not raw_name and index == 0:
            raw_name = self.layout_data.get("layout_name")
        if not raw_name or raw_name == "[I0000]":
            self.layout_name = f"lay{index:04d}.lay"
        else:
            self.layout_name = raw_name if str(raw_name).lower().endswith(".lay") else f"{raw_name}.lay"

        sess_title = self.current_layout.get("session_title") or ""
        tot_lays = len(self.layouts) if self.layouts else 1
        if sess_title:
            self.title(f"Print Preview - [{sess_title} - {self.layout_name}] ({index + 1}/{tot_lays})")
        else:
            self.title(f"Print Preview - [{self.layout_name}]")

        if self.current_layout.get("layout_path"):
            self.layout_path = self.current_layout["layout_path"]
        elif sess_title:
            self.layout_path = rf"{self.unc_prefix}\Compiti\{sess_title}\{self.layout_name}"
        else:
            self.layout_path = self.current_layout.get(
                "layout_path",
                rf"{self.unc_prefix}\Compiti\SEM 46-UP046_2°\129.046\10100\{self.layout_name}"
            )

        # 2. Dimensões da chapa
        sheet_w = self.current_layout.get("width_mm") or self.current_layout.get("sheet_w_mm")
        if sheet_w is not None:
            self.sheet_w_mm = float(sheet_w)
        elif "sheet_w_mm" in self.layout_data:
            self.sheet_w_mm = float(self.layout_data["sheet_w_mm"])
        else:
            self.sheet_w_mm = 0.0

        sheet_h = self.current_layout.get("height_mm") or self.current_layout.get("sheet_h_mm")
        if sheet_h is not None:
            self.sheet_h_mm = float(sheet_h)
        elif "sheet_h_mm" in self.layout_data:
            self.sheet_h_mm = float(self.layout_data["sheet_h_mm"])
        else:
            self.sheet_h_mm = 0.0

        # 3. Peças colocadas
        pcs = self.current_layout.get("pieces") if self.current_layout.get("pieces") is not None else self.current_layout.get("placed_pieces")
        if pcs is not None:
            import copy
            self.placed_pieces = copy.deepcopy(pcs)
        elif index == 0 and "placed_pieces" in self.layout_data and self.layout_data["placed_pieces"] is not None:
            import copy
            self.placed_pieces = copy.deepcopy(self.layout_data["placed_pieces"])
        else:
            self.placed_pieces = []

        for p in self.placed_pieces:
            if not isinstance(p, dict):
                continue
            if not p.get("contour"):
                shp = p.get("shape") if isinstance(p.get("shape"), dict) else None
                if shp and shp.get("contour"):
                    p["contour"] = shp.get("contour")
                elif self.session_shapes:
                    sid = p.get("shape_id") or p.get("target_id") or p.get("name")
                    for s in self.session_shapes:
                        if isinstance(s, dict) and (s.get("id") == sid or s.get("name") == sid or s.get("shape_id") == sid):
                            if s.get("contour"):
                                p["contour"] = s.get("contour")
                                break

        # 4. Camadas / Enfesto
        mat_obj = self.current_layout.get("material") or self.layout_data.get("material")
        mat_layers = self.current_layout.get("material_layers") or self.layout_data.get("material_layers")
        if mat_layers is None and isinstance(mat_obj, dict):
            mat_layers = mat_obj.get("layers")

        self.layout_layers = resolve_layout_layers(
            layout=self.current_layout,
            session=self.current_layout.get("session") or self.layout_data.get("session"),
            material=mat_obj if isinstance(mat_obj, dict) else None,
            default=self.current_layout.get("layers") or mat_layers or 2
        )
        self.material_layers = self.layout_layers
        if hasattr(self, "material_name") and self.material_name:
            self.material_name = re.sub(r"\(\s*\d+\s*layer\(s\)\s*\)", f"( {self.layout_layers} layer(s) )", self.material_name, flags=re.IGNORECASE)

        # 5. Ponta de 2 camadas
        self.tip_zone = self.current_layout.get("tip_zone") if isinstance(self.current_layout, dict) else None
        if self.tip_zone is None and index == 0:
            self.tip_zone = self.layout_data.get("tip_zone")

        self.layers_tip = self.current_layout.get("layers_tip") if isinstance(self.current_layout, dict) else None
        if self.layers_tip is None and index == 0:
            self.layers_tip = self.layout_data.get("layers_tip")
        if self.layers_tip is None:
            self.layers_tip = 2

        self.tip_mode = self.current_layout.get("tip_mode") if isinstance(self.current_layout, dict) else None
        if self.tip_mode is None and index == 0:
            self.tip_mode = self.layout_data.get("tip_mode")
        if self.tip_mode is None:
            self.tip_mode = "canto"

        # 6. Refile (CAM)
        self.trim_cut_line = self.current_layout.get("trim_cut_line") if isinstance(self.current_layout, dict) else None
        if self.trim_cut_line is None and index == 0:
            self.trim_cut_line = self.layout_data.get("trim_cut_line")

        refile_parts = []
        if self.trim_cut_line and self.trim_cut_line.get("enabled", True):
            if self.trim_cut_line.get("has_cut_y", False):
                refile_parts.append(f"Y={format_m(self.trim_cut_line.get('y', self.sheet_h_mm))} m")
            if self.trim_cut_line.get("has_cut_x", False):
                refile_parts.append(f"X={format_m(self.trim_cut_line.get('x', self.sheet_w_mm))} m")
        self.refile_display_str = ("Refilado (" + ", ".join(refile_parts) + ")") if refile_parts else "Sem refile"

        # 7. Dimensões e Linhas de Dimensão
        self.dimensions_str = format_dim_mm(self.sheet_w_mm, self.sheet_h_mm) if self.sheet_w_mm > 0 and self.sheet_h_mm > 0 else "não informadas"
        if self.tip_zone:
            from cad.layers_rule import format_dimensions_folhas
            self.dimensions_lines = format_dimensions_folhas(
                self.current_layout or {}, sheet_w=self.sheet_w_mm, sheet_h=self.sheet_h_mm, layers=self.layout_layers
            )
        elif index == 0 and self.layout_data.get("dimensions_lines"):
            self.dimensions_lines = self.layout_data.get("dimensions_lines")
        else:
            self.dimensions_lines = None

        # 8. Placa N de M
        tot_lays = len(self.layouts) if self.layouts else 1
        cur_lay_idx = self.current_layout_index + 1
        if sess_title:
            self.placa_n_de_m = f"{sess_title} - Placa {cur_lay_idx} de {tot_lays}"
        else:
            self.placa_n_de_m = f"Placa {cur_lay_idx} de {tot_lays}"

        # 9. Rendimento e Áreas
        total_poly_area_mm2 = 0.0
        unique_shape_names = set()
        for p in self.placed_pieces:
            if not isinstance(p, dict):
                continue
            cntr = p.get("contour")
            if not cntr:
                shp = p.get("shape") if isinstance(p.get("shape"), dict) else None
                if isinstance(shp, dict):
                    cntr = shp.get("contour")
            px = float(p.get("x", 0.0))
            py = float(p.get("y", 0.0))
            rot = float(p.get("rotation", p.get("angle", 0.0)))
            p_nm = p.get("name", "Molde")
            unique_shape_names.add(p_nm)
            if cntr and len(cntr) >= 3:
                poly = transform_contour(cntr, px, py, rot)
                total_poly_area_mm2 += polygon_area(poly)

        plate_area_mm2 = float(self.sheet_w_mm) * float(self.sheet_h_mm)
        mat_m2 = plate_area_mm2 / 1_000_000.0
        self.mat_area_str = f"{mat_m2:.2f} sq.M."

        if total_poly_area_mm2 > 0:
            used_m2 = total_poly_area_mm2 / 1_000_000.0
            self.used_area_str = f"{used_m2:.2f} sq.M."
            self.yield_pct = round((used_m2 / max(1e-4, mat_m2)) * 100.0, 2)
            self.instances_count = len(self.placed_pieces)
            self.shapes_count = len(unique_shape_names)
        elif self.placed_pieces:
            eff = float(self.current_layout.get("yield_percent", 0.0) or self.current_layout.get("yield_pct", 0.0) or (self.layout_data.get("yield_pct", 0.0) if index == 0 else 0.0))
            if eff > 0:
                self.yield_pct = eff
                used_m2 = mat_m2 * (eff / 100.0)
                self.used_area_str = f"{used_m2:.2f} sq.M."
            else:
                self.used_area_str = self.layout_data.get("used_area_str", "0.00 sq.M.") if index == 0 else "0.00 sq.M."
                self.yield_pct = float(self.layout_data.get("yield_pct", 0.0)) if index == 0 else 0.0
            self.instances_count = len(self.placed_pieces)
            self.shapes_count = len(unique_shape_names)
        elif index == 0 and ("yield_pct" in self.layout_data or "used_area_str" in self.layout_data):
            self.used_area_str = self.layout_data.get("used_area_str", "0.00 sq.M.")
            self.mat_area_str = self.layout_data.get("mat_area_str", f"{mat_m2:.2f} sq.M.")
            self.yield_pct = float(self.layout_data.get("yield_pct", 0.0))
            self.instances_count = int(self.layout_data.get("instances_count", 0))
            self.shapes_count = int(self.layout_data.get("shapes_count", 0))
        else:
            self.used_area_str = "0.00 sq.M."
            self.yield_pct = 0.0
            self.instances_count = 0
            self.shapes_count = 0

        # 10. Legenda estruturada
        self.legend_data = self.build_legend_data()

        # 11. Atualiza controles de navegação
        self.update_nav_controls()

        if not initial:
            self.redraw()
            if hasattr(self, "canvas") and self.canvas.winfo_exists():
                self.canvas.yview_moveto(0)
                self.canvas.xview_moveto(0)
            if hasattr(self.master, "switch_to_layout") and callable(self.master.switch_to_layout):
                try:
                    self.master.switch_to_layout(index, save_current=True)
                except Exception:
                    pass

        return True

    def next_page(self, event=None):
        """Avança para a próxima página/placa de impressão."""
        if not getattr(self, "layouts", None):
            return "break"
        if self.current_layout_index + 1 < len(self.layouts):
            self.load_layout_index(self.current_layout_index + 1)
        return "break"

    def prev_page(self, event=None):
        """Retorna para a página/placa anterior de impressão."""
        if not getattr(self, "layouts", None):
            return "break"
        if self.current_layout_index - 1 >= 0:
            self.load_layout_index(self.current_layout_index - 1)
        return "break"

    def update_nav_controls(self):
        """Atualiza estado dos botões de navegação e texto do indicador de página."""
        tot = len(self.layouts) if getattr(self, "layouts", None) else 1
        cur = (self.current_layout_index + 1) if getattr(self, "layouts", None) else 1
        sess_title = getattr(self, "current_layout", {}).get("session_title") if hasattr(self, "current_layout") else ""

        if hasattr(self, "lbl_page") and self.lbl_page.winfo_exists():
            if sess_title:
                self.lbl_page.config(text=f"Página {cur} de {tot}  ({sess_title})")
            else:
                self.lbl_page.config(text=f"Página {cur} de {tot}")

        if hasattr(self, "btn_prev") and self.btn_prev.winfo_exists():
            self.btn_prev.config(state="normal" if cur > 1 else "disabled")

        if hasattr(self, "btn_next") and self.btn_next.winfo_exists():
            self.btn_next.config(state="normal" if cur < tot else "disabled")


    def get_barcode_payload_and_label(self) -> Tuple[str, str]:
        """
        Retorna (payload, label) para o código de barras Code 128.
        Formato do payload: 'CAC:SESS:<id>' ou 'CAC:SESS:<id>:LAY:<index>'
        """
        cur_layout = getattr(self, "current_layout", {}) or {}
        sid = (
            cur_layout.get("session_id")
            or self.layout_data.get("session_id")
            or getattr(self, "session_id", None)
            or getattr(self.master, "session_id", None)
            or (self.master.session_data.get("id") if hasattr(self.master, "session_data") and isinstance(self.master.session_data, dict) else None)
        )
        lay_idx = getattr(self, "current_layout_index", 0)
        tot_lays = len(self.layouts) if getattr(self, "layouts", None) else 1

        if sid is not None and str(sid).strip() and str(sid).strip().lower() not in ("none", "null"):
            sid_str = str(sid).strip()
            if tot_lays > 1:
                payload = f"CAC:SESS:{sid_str}:LAY:{lay_idx}"
                label = f"Sessão #{sid_str} (Placa {lay_idx + 1})"
            else:
                payload = f"CAC:SESS:{sid_str}"
                label = f"Sessão #{sid_str}"
        else:
            l_name = self.layout_name or "layout"
            payload = f"CAC:LAY:{l_name}"
            label = l_name

        return payload, label

    def get_display_layout_name(self) -> str:
        """Retorna o nome do layout sem a extensão .lay para exibição no título da folha de impressão."""
        name = str(self.layout_name or "").strip()
        if name.lower().endswith(".lay"):
            return name[:-4]
        return name

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

    def get_user_display_text(self) -> str:
        """Formata o texto do usuário ativo a ser exibido na folha de impressão."""
        user = str(getattr(self, "active_user", "") or "").strip()
        if not user:
            return ""
        pref = str(getattr(self, "user_print_prefix", "Usuário") or "").strip()
        if pref:
            if user.lower().startswith((pref.lower() + ":", "usuário:", "usuario:", "operador:")):
                return user
            return f"{pref}: {user}"
        return user

    def open_user_manager_dialog(self):
        """Abre diálogo para cadastrar ou selecionar o operador / usuário ativo."""
        from ui.user_dialog import open_user_management_dialog
        open_user_management_dialog(self, db=self.db, on_update_callback=self._on_user_updated)

    def _on_user_updated(self):
        """Callback executado ao cadastrar ou alterar o usuário ativo."""
        if self.db:
            try:
                self.active_user = self.db.get_active_user()
                self.user_print_prefix = self.db.get_user_print_prefix()
            except Exception:
                pass
        self.redraw()

    def build_legend_data(self):
        """Projeção compatível da contagem física usada pela ficha."""
        from ui.production_sheet import production_rows
        layout = dict(self.current_layout)
        layout.update(layers=self.layout_layers, tip_zone=self.tip_zone, layers_tip=self.layers_tip)
        grouped = {}
        for row in production_rows(self.placed_pieces, self.session_shapes, layout):
            name = extract_molde_base_name(row["name"], row["size"])
            entry = grouped.setdefault(name, {"molde_name": name,
                                             "shape_id": row["shape_id"], "sizes": []})
            entry["sizes"].append({"size": format_size(row["size"]), "n": row["pairs"],
                                   "m": row["demand"], "is_error": False})
        return list(grouped.values())

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

        tk.Button(
            tb, text="👤 Usuário...", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9, "bold"), padx=6, command=self.open_user_manager_dialog
        ).pack(side="left", padx=2)

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)

        # Navegação de Páginas / Placas de Impressão
        self.btn_prev = tk.Button(
            tb, text="◀ Anterior", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9), padx=6, command=self.prev_page
        )
        self.btn_prev.pack(side="left", padx=2)

        tot_lays = len(self.layouts) if getattr(self, "layouts", None) else 1
        cur_lay_idx = (getattr(self, "current_layout_index", 0) + 1) if getattr(self, "layouts", None) else 1
        self.lbl_page = tk.Label(
            tb, text=f"Página {cur_lay_idx} de {tot_lays}",
            bg=THEME["bg_surface"], fg=THEME["text_main"],
            font=("Segoe UI", 9, "bold"), padx=6
        )
        self.lbl_page.pack(side="left", padx=2)

        self.btn_next = tk.Button(
            tb, text="Próxima ▶", bg=THEME["bg_surface"], fg=THEME["text_main"],
            relief="raised", bd=2, font=("Segoe UI", 9, "bold"), padx=6, command=self.next_page
        )
        self.btn_next.pack(side="left", padx=2)

        try:
            from ui.tooltip import ToolTip
            ToolTip(self.btn_prev, "Página/Placa anterior (PageUp ou Alt+Esquerda)")
            ToolTip(self.btn_next, "Próxima página/placa de impressão (PageDown ou Alt+Direita)")
        except Exception:
            pass

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
        self.bind("<Next>", self.next_page)
        self.bind("<Prior>", self.prev_page)
        self.bind("<Alt-Right>", self.next_page)
        self.bind("<Alt-Left>", self.prev_page)

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
        """A prévia usa as mesmas páginas enviadas ao PDF e à impressora."""
        self.canvas.delete("all")
        self._sheet_photos = []
        y = 30
        for page in self.render_pillow_pages(dpi=200):
            width = max(1, round(self.page_w_base * self.zoom))
            height = max(1, round(page.height * width / page.width))
            buffer = io.BytesIO()
            page.resize((width, height), Image.Resampling.LANCZOS).save(buffer, format="PNG")
            photo = tk.PhotoImage(master=self.canvas, data=buffer.getvalue())
            self._sheet_photos.append(photo)
            x = max(30, (self.canvas.winfo_width() - width) // 2)
            self.canvas.create_image(x, y, anchor="nw", image=photo, tags=("print_page",))
            y += height + 30
        self.canvas.configure(scrollregion=(0, 0, max(self.page_w_base*self.zoom+60, self.canvas.winfo_width()), y))

    def render_pillow_pages(self, dpi=150):
        from ui.production_sheet import render_sheet
        return render_sheet(self, dpi)

    def render_pillow_page(self, dpi=150):
        """Compatibilidade: primeira folha. Exportação usa todas as continuações."""
        return self.render_pillow_pages(dpi)[0]

    def save_as_pdf(self):
        tot_lays = len(self.layouts) if getattr(self, "layouts", None) else 1
        save_all = False
        if tot_lays > 1:
            ans = messagebox.askyesnocancel(
                "Salvar PDF",
                f"A sessão possui {tot_lays} placas de impressão.\n\n"
                f"Deseja exportar TODAS as páginas em um único arquivo PDF?\n\n"
                f"• 'Sim': Exporta todas as {tot_lays} placas e suas continuações.\n"
                f"• 'Não': Exporta a placa atual e suas continuações ({self.layout_name}).\n"
                f"• 'Cancelar': Cancela a exportação.",
                parent=self
            )
            if ans is None:
                return
            save_all = ans

        default_file = (
            "relatorio_completo_sessao.pdf" if save_all
            else f"{self.layout_name.replace('.lay', '')}_report.pdf"
        )
        file_path = filedialog.asksaveasfilename(
            title="Salvar Layout como PDF",
            defaultextension=".pdf",
            initialfile=default_file,
            filetypes=[("Documento PDF (*.pdf)", "*.pdf"), ("Todos os Arquivos (*.*)", "*.*")],
            parent=self
        )
        if file_path:
            try:
                if save_all and tot_lays > 1:
                    orig_idx = self.current_layout_index
                    pages = []
                    try:
                        for i in range(tot_lays):
                            self.load_layout_index(i, initial=True)
                            pages.extend(self.render_pillow_pages(dpi=200))
                    finally:
                        self.load_layout_index(orig_idx, initial=True)
                        self.redraw()

                    if pages:
                        pages[0].save(file_path, "PDF", resolution=200.0, save_all=True, append_images=pages[1:])
                        messagebox.showinfo("Exportar PDF", f"Relatório completo ({len(pages)} folhas) exportado com sucesso para:\n{file_path}", parent=self)
                else:
                    pages = self.render_pillow_pages(dpi=200)
                    pages[0].save(file_path, "PDF", resolution=200.0, save_all=True, append_images=pages[1:])
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
                pages = self.render_pillow_pages(dpi=200)
                for i, im in enumerate(pages):
                    target = file_path if i == 0 else str(Path(file_path).with_name(f"{Path(file_path).stem}_{i+1}.png"))
                    im.save(target, "PNG")
                messagebox.showinfo("Exportar Imagem", f"Imagem do Layout salva com sucesso em:\n{file_path}", parent=self)
            except Exception as e:
                messagebox.showerror("Erro ao Salvar Imagem", f"Falha ao salvar imagem:\n{str(e)}", parent=self)

    def do_print(self):
        """Dispara a impressão física ou salva em spooler de impressão."""
        try:
            tot_lays = len(self.layouts) if getattr(self, "layouts", None) else 1
            print_all = False
            if tot_lays > 1:
                ans = messagebox.askyesnocancel(
                    "Imprimir Layout",
                    f"A sessão possui {tot_lays} placas de impressão.\n\n"
                    f"Deseja imprimir TODAS as páginas?\n\n"
                    f"• 'Sim': Imprime todas as {tot_lays} placas e suas continuações.\n"
                    f"• 'Não': Imprime a placa atual e suas continuações ({self.layout_name}).\n"
                    f"• 'Cancelar': Cancela a impressão.",
                    parent=self
                )
                if ans is None:
                    return
                print_all = ans

            import tempfile
            import subprocess
            fd, tmp_path = tempfile.mkstemp(prefix="ficha_producao_", suffix=".pdf")
            os.close(fd)
            tmp_pdf = Path(tmp_path)

            if print_all and tot_lays > 1:
                orig_idx = self.current_layout_index
                pages = []
                try:
                    for i in range(tot_lays):
                        self.load_layout_index(i, initial=True)
                        pages.extend(self.render_pillow_pages(dpi=200))
                finally:
                    self.load_layout_index(orig_idx, initial=True)
                    self.redraw()
                if pages:
                    pages[0].save(str(tmp_pdf), "PDF", resolution=200.0, save_all=True, append_images=pages[1:])
            else:
                pages = self.render_pillow_pages(dpi=200)
                pages[0].save(str(tmp_pdf), "PDF", resolution=200.0, save_all=True, append_images=pages[1:])

            if sys.platform == "win32":
                try:
                    os.startfile(str(tmp_pdf), "print")
                    messagebox.showinfo("Imprimir Layout", "Documento enviado para a impressora padrão do Windows.", parent=self)
                    return
                except Exception:
                    pass
            else:
                import shutil
                result = subprocess.run(["lp", str(tmp_pdf)], capture_output=True, text=True) if shutil.which("lp") else None
                if result is not None and result.returncode == 0:
                    messagebox.showinfo("Imprimir Layout", "Documento enviado para a fila de impressão (CUPS/lp).", parent=self)
                    return

            messagebox.showinfo("Imprimir Layout", f"Relatório de impressão gerado com sucesso em:\n{tmp_pdf}\n\nVocê também pode utilizar o botão 'Salvar PDF...' para salvar onde desejar.", parent=self)
        except Exception as e:
            messagebox.showerror("Erro ao Imprimir", f"Falha no processo de impressão:\n{str(e)}", parent=self)

