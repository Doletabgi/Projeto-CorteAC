"""
JobManager 2000 (Python Edition)
Diálogo para Configuração de Molde na Sessão (Pares a cortar e Sequência de Geração)
"""

import tkinter as tk
from tkinter import ttk, colorchooser
from config import THEME
from cad.colors import get_color_for_size, get_contrast_text_color

class EditShapeInSessionDialog(tk.Toplevel):
    def __init__(self, parent, shape_data, on_save_callback=None, on_open_editor_callback=None):
        super().__init__(parent)
        self.shape_data = shape_data
        self.on_save_cb = on_save_callback
        self.on_open_editor_cb = on_open_editor_callback

        self.title("Configurar Molde na Sessão")
        self.geometry("450x420")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.configure(bg=THEME["bg_surface"])
        self.setup_ui()
        self.center_window(parent)

    def center_window(self, parent):
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        x = max(10, px + (pw - w) // 2)
        y = max(10, py + (ph - h) // 2)
        self.geometry(f"+{x}+{y}")

    def setup_ui(self):
        # Cabeçalho clássico
        hdr = tk.Frame(self, bg="#0a246a", pady=10, padx=14)
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="⚙️ Propriedades do Molde na Sessão",
            font=("Segoe UI", 11, "bold"), fg="#ffffff", bg="#0a246a"
        ).pack(anchor="w")
        tk.Label(
            hdr, text="Defina a quantidade de pares a cortar e a ordem/sequência de geração.",
            font=("Segoe UI", 8), fg="#dbeafe", bg="#0a246a"
        ).pack(anchor="w")

        # Conteúdo
        body = tk.Frame(self, bg=THEME["bg_surface"], padx=18, pady=14)
        body.pack(fill="both", expand=True)

        shp_name = self.shape_data.get("name", "Molde")
        shp_folder = self.shape_data.get("folder", "Externo")
        shp_size = self.shape_data.get("size", "25a")
        curr_pairs = self.shape_data.get("pairs", 16)
        curr_seq = self.shape_data.get("sequence", 1)

        # Informações do Molde
        info_frame = tk.LabelFrame(body, text=" Identificação do Molde ", bg=THEME["bg_surface"], font=("Segoe UI", 9, "bold"))
        info_frame.pack(fill="x", pady=(0, 12))

        row1 = tk.Frame(info_frame, bg=THEME["bg_surface"], padx=8, pady=4)
        row1.pack(fill="x")
        tk.Label(row1, text="Molde:", font=("Segoe UI", 9, "bold"), bg=THEME["bg_surface"], width=12, anchor="w").pack(side="left")
        tk.Label(row1, text=shp_name, font=("Segoe UI", 9, "bold"), bg=THEME["bg_surface"], fg="#003399").pack(side="left")

        row2 = tk.Frame(info_frame, bg=THEME["bg_surface"], padx=8, pady=4)
        row2.pack(fill="x")
        tk.Label(row2, text="Percurso:", font=("Segoe UI", 9, "bold"), bg=THEME["bg_surface"], width=12, anchor="w").pack(side="left")
        tk.Label(row2, text=shp_folder, font=("Segoe UI", 9), bg=THEME["bg_surface"]).pack(side="left")
        tk.Label(row2, text="    Tamanho:", font=("Segoe UI", 9, "bold"), bg=THEME["bg_surface"]).pack(side="left")
        tk.Label(row2, text=shp_size, font=("Segoe UI", 9), bg=THEME["bg_surface"]).pack(side="left")

        # Parâmetros de Produção
        prod_frame = tk.LabelFrame(body, text=" Parâmetros de Produção ", bg=THEME["bg_surface"], font=("Segoe UI", 9, "bold"))
        prod_frame.pack(fill="x", pady=(0, 12))

        # Quantidade de Pares
        p_row = tk.Frame(prod_frame, bg=THEME["bg_surface"], padx=8, pady=6)
        p_row.pack(fill="x")
        tk.Label(p_row, text="Pares a Cortar:", font=("Segoe UI", 9, "bold"), bg=THEME["bg_surface"], width=18, anchor="w").pack(side="left")
        self.spin_pairs = ttk.Spinbox(p_row, from_=1, to=9999, width=10, font=("Segoe UI", 10, "bold"))
        self.spin_pairs.set(str(curr_pairs))
        self.spin_pairs.pack(side="left", padx=4)
        tk.Label(p_row, text="pares (instâncias)", font=("Segoe UI", 8, "italic"), fg="#666666", bg=THEME["bg_surface"]).pack(side="left", padx=4)

        # Sequência de Geração
        s_row = tk.Frame(prod_frame, bg=THEME["bg_surface"], padx=8, pady=6)
        s_row.pack(fill="x")
        tk.Label(s_row, text="Sequência / Ordem:", font=("Segoe UI", 9, "bold"), bg=THEME["bg_surface"], width=18, anchor="w").pack(side="left")
        self.spin_seq = ttk.Spinbox(s_row, from_=1, to=999, width=10, font=("Segoe UI", 10, "bold"))
        self.spin_seq.set(str(curr_seq))
        self.spin_seq.pack(side="left", padx=4)
        tk.Label(s_row, text="(prioridade no aninhamento)", font=("Segoe UI", 8, "italic"), fg="#666666", bg=THEME["bg_surface"]).pack(side="left", padx=4)

        # Cor do Número / Molde
        c_row = tk.Frame(prod_frame, bg=THEME["bg_surface"], padx=8, pady=6)
        c_row.pack(fill="x")
        tk.Label(c_row, text="Cor do Número:", font=("Segoe UI", 9, "bold"), bg=THEME["bg_surface"], width=18, anchor="w").pack(side="left")

        self.current_color = self.shape_data.get("color") or get_color_for_size(shp_size)
        if not self.current_color or self.current_color in ("#000000", "black", "None"):
            self.current_color = get_color_for_size(shp_size)

        self.btn_color_swatch = tk.Button(
            c_row, text=f" {self.current_color} ", bg=self.current_color,
            fg=get_contrast_text_color(self.current_color), font=("Segoe UI", 9, "bold"),
            relief="groove", bd=2, width=12, command=self.on_pick_color
        )
        self.btn_color_swatch.pack(side="left", padx=4)

        tk.Button(
            c_row, text="🎨 Alterar Cor...", font=("Segoe UI", 8),
            relief="raised", bd=1, command=self.on_pick_color
        ).pack(side="left", padx=4)

        # Barra de Botões inferior
        btn_bar = tk.Frame(self, bg=THEME["bg_surface"], padx=14, pady=10)
        btn_bar.pack(side="bottom", fill="x")

        if self.on_open_editor_cb:
            tk.Button(
                btn_bar, text="📐 Abrir no Shape Editor...",
                font=("Segoe UI", 9), relief="raised", bd=2,
                command=self.on_open_editor
            ).pack(side="left")

        tk.Button(
            btn_bar, text="Cancelar",
            font=("Segoe UI", 9), relief="raised", bd=2, width=9,
            command=self.destroy
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            btn_bar, text="Salvar",
            font=("Segoe UI", 9, "bold"), relief="raised", bd=2, width=9,
            bg="#2563eb", fg="#ffffff",
            command=self.on_save
        ).pack(side="right")

        self.bind("<Return>", lambda e: self.on_save())
        self.bind("<Escape>", lambda e: self.destroy())

    def on_pick_color(self):
        chosen = colorchooser.askcolor(
            color=self.current_color,
            title=f"Escolher Cor para o Número {self.shape_data.get('size', '')}",
            parent=self
        )
        if chosen and chosen[1]:
            self.current_color = chosen[1]
            self.btn_color_swatch.config(
                bg=self.current_color,
                fg=get_contrast_text_color(self.current_color),
                text=f" {self.current_color} "
            )

    def on_save(self):
        try:
            new_pairs = max(1, int(self.spin_pairs.get().strip()))
        except ValueError:
            new_pairs = self.shape_data.get("pairs", 16)

        try:
            new_seq = max(1, int(self.spin_seq.get().strip()))
        except ValueError:
            new_seq = self.shape_data.get("sequence", 1)

        self.shape_data["pairs"] = new_pairs
        self.shape_data["sequence"] = new_seq
        self.shape_data["color"] = self.current_color

        if self.on_save_cb:
            self.on_save_cb(self.shape_data)
        self.destroy()

    def on_open_editor(self):
        self.destroy()
        if self.on_open_editor_cb:
            self.on_open_editor_cb(self.shape_data)
