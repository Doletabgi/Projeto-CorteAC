"""
JobManager 2000 (Python Edition)
Nesting Parameters Dialog - Recriação fiel da tela dlgParamsFlashNest.gif
"""

import tkinter as tk
from tkinter import ttk
from config import THEME

class NestingParamsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Nesting Parameters")
        self.geometry("640x360")
        self.resizable(False, False)
        self.configure(bg=THEME["bg_surface"])
        self.transient(parent)
        self.grab_set()

        self.setup_ui()

    def setup_ui(self):
        # Container principal com divisão esquerda (lista) e direita (abas)
        main_box = tk.Frame(self, bg=THEME["bg_surface"], padx=8, pady=8)
        main_box.pack(fill="both", expand=True)

        # Painel esquerdo: Lista de Predefinições (Name) com borda rebaixada clássica
        left_box = tk.Frame(main_box, bg=THEME["bg_surface"], width=130)
        left_box.pack(side="left", fill="y", padx=(0, 8))
        left_box.pack_propagate(False)

        tk.Label(left_box, text="Name", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8, "bold"), relief="raised", bd=1).pack(fill="x")
        self.preset_list = tk.Listbox(left_box, bg=THEME["bg_input"], fg=THEME["text_main"], selectbackground=THEME["select_bg"], selectforeground=THEME["select_fg"], borderwidth=2, relief="sunken")
        self.preset_list.pack(fill="both", expand=True)
        for name in ["PrmSss_35", "stdNOTFill", "std", "FastNest", "HighYield"]:
            self.preset_list.insert("end", name)
        self.preset_list.selection_set(0)

        # Painel direito: Abas (Free Nest, Flash Nest, Remainder Nest, User Defined)
        right_box = tk.Frame(main_box, bg=THEME["bg_surface"])
        right_box.pack(side="left", fill="both", expand=True)

        notebook = ttk.Notebook(right_box)
        notebook.pack(fill="both", expand=True)

        tab_flash = tk.Frame(notebook, bg=THEME["bg_card"], padx=10, pady=10)
        tab_free = tk.Frame(notebook, bg=THEME["bg_card"], padx=10, pady=10)
        tab_remainder = tk.Frame(notebook, bg=THEME["bg_card"], padx=10, pady=10)
        tab_user = tk.Frame(notebook, bg=THEME["bg_card"], padx=10, pady=10)

        notebook.add(tab_free, text="Free Nest")
        notebook.add(tab_flash, text="Flash Nest")
        notebook.add(tab_remainder, text="Remainder Nest")
        notebook.add(tab_user, text="User Defined")

        # Conteúdo da aba Flash Nest (idêntico ao print dlgParamsFlashNest.gif)
        # 1. Rolls Only & Explode last layout
        grp1 = tk.Frame(tab_flash, bg=THEME["bg_card"])
        grp1.pack(fill="x", pady=4)

        box_rolls = tk.LabelFrame(grp1, text="Rolls Only", bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 8), relief="groove")
        box_rolls.pack(side="left", fill="both", expand=True, padx=(0, 4))
        tk.Checkbutton(box_rolls, text="Last die by len", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(anchor="w", padx=4, pady=4)

        box_explode = tk.LabelFrame(grp1, text="Explode last layout from", bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 8), relief="groove")
        box_explode.pack(side="left", fill="both", expand=True, padx=(4, 0))
        r_box = tk.Frame(box_explode, bg=THEME["bg_card"])
        r_box.pack(anchor="w", padx=4, pady=4)
        v_exp = tk.StringVar(value="Never")
        tk.Radiobutton(r_box, text="Never", variable=v_exp, value="Never", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="left", padx=2)
        tk.Radiobutton(r_box, text="If qty > half", variable=v_exp, value="Half", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="left", padx=2)
        tk.Radiobutton(r_box, text="Always", variable=v_exp, value="Always", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="left", padx=2)

        # 2. Fill Layout & Rolls / Sheets
        grp2 = tk.Frame(tab_flash, bg=THEME["bg_card"])
        grp2.pack(fill="x", pady=4)

        box_fill = tk.LabelFrame(grp2, text="Fill Layout", bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 8), relief="groove")
        box_fill.pack(side="left", fill="both", expand=True, padx=(0, 4))
        f_box = tk.Frame(box_fill, bg=THEME["bg_card"])
        f_box.pack(anchor="w", padx=4, pady=4)
        v_fill = tk.StringVar(value="None")
        tk.Radiobutton(f_box, text="None", variable=v_fill, value="None", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="left", padx=4)
        tk.Radiobutton(f_box, text="Last", variable=v_fill, value="Last", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="left", padx=4)
        tk.Radiobutton(f_box, text="Always", variable=v_fill, value="Always", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="left", padx=4)

        box_rs = tk.LabelFrame(grp2, text="Rolls / Sheets", bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 8), relief="groove")
        box_rs.pack(side="left", fill="both", expand=True, padx=(4, 0))
        tk.Checkbutton(box_rs, text="Last layout by len", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(anchor="w", padx=4, pady=4)

        # 3. Standard Layouts
        box_std = tk.LabelFrame(tab_flash, text="Standard layouts", bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 8), relief="groove")
        box_std.pack(fill="x", pady=4)
        s_box = tk.Frame(box_std, bg=THEME["bg_card"])
        s_box.pack(fill="x", padx=4, pady=4)
        v_std = tk.StringVar(value="Never")
        tk.Radiobutton(s_box, text="Never", variable=v_std, value="Never", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="left", padx=4)
        tk.Radiobutton(s_box, text="Existent", variable=v_std, value="Existent", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="left", padx=4)
        tk.Radiobutton(s_box, text="Always", variable=v_std, value="Always", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="left", padx=4)
        tk.Checkbutton(s_box, text="Save", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="left", padx=12)
        tk.Checkbutton(s_box, text="Row interlock", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="right", padx=4)
        tk.Checkbutton(s_box, text="Use Mix Nest", bg=THEME["bg_card"], fg=THEME["text_main"], selectcolor="#ffffff", activebackground=THEME["bg_card"]).pack(side="right", padx=4)

        # 4. Botões inferiores clássicos com relevo 3D
        btn_bar = tk.Frame(right_box, bg=THEME["bg_surface"], pady=6)
        btn_bar.pack(fill="x")
        tk.Button(btn_bar, text="Used by ...", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, padx=8).pack(side="left", padx=2)
        tk.Button(btn_bar, text="Update", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, padx=8).pack(side="left", padx=2)
        tk.Button(btn_bar, text="Remove", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, padx=8).pack(side="left", padx=2)
        tk.Button(btn_bar, text="Clear", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, padx=8).pack(side="left", padx=2)

        # Campo de texto como no print
        entry_val = tk.Entry(btn_bar, bg=THEME["bg_input"], fg=THEME["text_main"], relief="sunken", bd=2, width=8)
        entry_val.pack(side="left", padx=4)

        tk.Button(btn_bar, text="OK", bg=THEME["bg_surface"], fg=THEME["text_main"], relief="raised", bd=2, padx=12, command=self.destroy).pack(side="right", padx=4)

        notebook.select(tab_flash)
