"""
JobManager 2000 (Python Edition)
Order View Form - Recriação fiel das telas frmOrderGeneral.gif e frmOrderArticle.gif
"""

import tkinter as tk
from tkinter import ttk
from config import THEME

class OrderView(tk.Frame):
    def __init__(self, parent, order_data=None, on_close=None, on_minimize=None, on_maximize=None, **kwargs):
        super().__init__(parent, bg=THEME["bg_surface"], relief="ridge", bd=2, **kwargs)
        self.order_data = order_data or {
            "code": "ORD-2026-001",
            "customer": "Calçados Elite S/A",
            "date": "14/01/2026",
            "status": "Em Produção"
        }
        self.on_close_cb = on_close
        self.on_minimize_cb = on_minimize
        self.on_maximize_cb = on_maximize
        self.setup_ui()

    def setup_ui(self):
        # Barra de Título interna no estilo MDI da época
        title_bar = tk.Frame(self, bg=THEME["title_bar_bg"], height=24, padx=4, pady=2)
        title_bar.pack(fill="x")
        self.lbl_title = tk.Label(
            title_bar,
            text=f"📁 Order [{self.order_data.get('code', 'New Order')}] - {self.order_data.get('customer', '')}",
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

        # Notebook com as 5 abas idênticas ao print frmOrderGeneral.gif
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=3, pady=3)

        tab_general = tk.Frame(notebook, bg=THEME["bg_card"], padx=16, pady=16)
        tab_articles = tk.Frame(notebook, bg=THEME["bg_card"], padx=6, pady=6)
        tab_art_by_size = tk.Frame(notebook, bg=THEME["bg_card"], padx=6, pady=6)
        tab_parts = tk.Frame(notebook, bg=THEME["bg_card"], padx=6, pady=6)
        tab_all_parts = tk.Frame(notebook, bg=THEME["bg_card"], padx=6, pady=6)

        notebook.add(tab_general, text="General")
        notebook.add(tab_articles, text="Articles")
        notebook.add(tab_art_by_size, text="Articles by size")
        notebook.add(tab_parts, text="Parts")
        notebook.add(tab_all_parts, text="All parts")

        # -----------------------------------------------------------------
        # Aba 1: General (como em frmOrderGeneral.gif)
        # -----------------------------------------------------------------
        row1 = tk.Frame(tab_general, bg=THEME["bg_card"])
        row1.pack(fill="x", pady=8)
        tk.Label(row1, text="Customer", width=12, anchor="w", bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 9)).pack(side="left")
        self.entry_cust = tk.Entry(row1, bg=THEME["bg_input"], fg=THEME["text_main"], relief="sunken", bd=2, width=40)
        self.entry_cust.insert(0, self.order_data.get("customer", ""))
        self.entry_cust.pack(side="left", padx=8)

        row2 = tk.Frame(tab_general, bg=THEME["bg_card"])
        row2.pack(fill="x", pady=8)
        tk.Label(row2, text="Order date", width=12, anchor="w", bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 9)).pack(side="left")
        self.entry_date = tk.Entry(row2, bg=THEME["bg_input"], fg=THEME["text_main"], relief="sunken", bd=2, width=16)
        self.entry_date.insert(0, self.order_data.get("date", "14/01/2026"))
        self.entry_date.pack(side="left", padx=8)

        # -----------------------------------------------------------------
        # Aba 2: Articles (como em frmOrderArticle.gif)
        # -----------------------------------------------------------------
        grp_bar = tk.Frame(tab_articles, bg="#808080", height=24, padx=6, relief="sunken", bd=1)
        grp_bar.pack(fill="x", pady=(0, 4))
        tk.Label(grp_bar, text="Article ▲ (Arrastar coluna para agrupar)", bg="#808080", fg="#ffffff", font=("Segoe UI", 8)).pack(side="left")

        art_frame = tk.Frame(tab_articles, bg=THEME["bg_card"], relief="sunken", bd=2)
        art_frame.pack(fill="both", expand=True)

        cols_art = ("row", "size", "qty", "filler")
        self.tree_art = ttk.Treeview(art_frame, columns=cols_art, show="headings", height=8)
        self.tree_art.heading("row", text="Row")
        self.tree_art.heading("size", text="Size")
        self.tree_art.heading("qty", text="Quantity")
        self.tree_art.heading("filler", text="Filler")
        self.tree_art.column("row", width=60, anchor="center")
        self.tree_art.column("size", width=80, anchor="center")
        self.tree_art.column("qty", width=100, anchor="center")
        self.tree_art.column("filler", width=80, anchor="center")
        self.tree_art.pack(fill="both", expand=True)

        sample_rows = [
            ("1", "39", "6 pares", "Não"),
            ("2", "40", "12 pares", "Não"),
            ("3", "41", "18 pares", "Sim"),
            ("4", "42", "12 pares", "Não"),
            ("5", "43", "6 pares", "Não")
        ]
        for r in sample_rows:
            self.tree_art.insert("", "end", values=r)

        # -----------------------------------------------------------------
        # Aba 3: Articles by size
        # -----------------------------------------------------------------
        size_frame = tk.Frame(tab_art_by_size, bg=THEME["bg_card"], relief="sunken", bd=2)
        size_frame.pack(fill="both", expand=True)

        cols_size = ("art", "s38", "s39", "s40", "s41", "s42", "s43", "total")
        self.tree_size = ttk.Treeview(size_frame, columns=cols_size, show="headings")
        self.tree_size.heading("art", text="Artigo")
        self.tree_size.heading("s38", text="38")
        self.tree_size.heading("s39", text="39")
        self.tree_size.heading("s40", text="40")
        self.tree_size.heading("s41", text="41")
        self.tree_size.heading("s42", text="42")
        self.tree_size.heading("s43", text="43")
        self.tree_size.heading("total", text="Total")
        self.tree_size.pack(fill="both", expand=True)
        self.tree_size.insert("", "end", values=("Derby Masculino", "2", "6", "12", "18", "12", "6", "56"))

        # -----------------------------------------------------------------
        # Aba 4: Parts & All Parts
        # -----------------------------------------------------------------
        parts_frame = tk.Frame(tab_parts, bg=THEME["bg_card"], relief="sunken", bd=2)
        parts_frame.pack(fill="both", expand=True)

        cols_parts = ("part_id", "part_name", "category", "qty_per_pair")
        self.tree_parts = ttk.Treeview(parts_frame, columns=cols_parts, show="headings")
        self.tree_parts.heading("part_id", text="ID Peça")
        self.tree_parts.heading("part_name", text="Nome da Peça")
        self.tree_parts.heading("category", text="Categoria")
        self.tree_parts.heading("qty_per_pair", text="Qtd/Par")
        self.tree_parts.pack(fill="both", expand=True)

        self.tree_parts.insert("", "end", values=("P01", "Gáspea (Vamp)", "Couro Externo", "2"))
        self.tree_parts.insert("", "end", values=("P02", "Biqueira (Toe Cap)", "Couro Externo", "2"))
        self.tree_parts.insert("", "end", values=("P03", "Quarteirão (Quarter)", "Couro Externo", "4"))
        self.tree_parts.insert("", "end", values=("P04", "Talonete (Heel Counter)", "Reforço", "2"))

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

    def load_order(self, order_data):
        self.order_data = order_data
        code = order_data.get("code", "New Order")
        cust = order_data.get("customer", "")
        name = order_data.get("name", "")
        self.lbl_title.config(text=f"📁 Order [{code}] - {name or cust}")
        if hasattr(self, "entry_cust"):
            self.entry_cust.delete(0, "end")
            self.entry_cust.insert(0, cust)
