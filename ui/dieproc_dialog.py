"""
JobManager 2000 (Python Edition)
DieProc Configuration Dialog - Recriação autêntica da tela original ATOM dp98 (media_1792155368271.png)
Configuração de acoplamento de rotação (Coupling), varredura angular (Ranges),
folga entre peças (Gaps) e intertravamento entre linhas (Row interlock) para corte contínuo de sintéticos.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from config import THEME

class DieProcDialog(tk.Toplevel):
    def __init__(self, parent, db, initial_preset=None, on_select=None):
        super().__init__(parent)
        self.db = db
        self.on_select_cb = on_select
        self.title("DieProc configuration")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.configure(bg=THEME["bg_surface"])

        dlg_w, dlg_h = 620, 430
        self.geometry(f"{dlg_w}x{dlg_h}")

        # Centraliza sobre a janela pai
        self.update_idletasks()
        rx = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
        ry = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
        self.geometry(f"+{max(10, rx)}+{max(10, ry)}")

        self.presets = self.db.get_dieproc_presets()
        self.active_preset_name = initial_preset or "ALTERNADO"

        self.setup_ui()
        self.populate_presets()
        self.select_preset(self.active_preset_name)

        self.bind("<Escape>", lambda e: self.destroy())

    def setup_ui(self):
        main_box = tk.Frame(self, bg=THEME["bg_surface"], padx=8, pady=8)
        main_box.pack(fill="both", expand=True)

        content_frame = tk.Frame(main_box, bg=THEME["bg_surface"])
        content_frame.pack(fill="both", expand=True)

        # -------------------------------------------------------------
        # Painel Esquerdo: Lista de Predefinições com cabeçalho "Name"
        # -------------------------------------------------------------
        left_box = tk.Frame(content_frame, bg=THEME["bg_surface"], width=135)
        left_box.pack(side="left", fill="y", padx=(0, 10))
        left_box.pack_propagate(False)

        lbl_head = tk.Label(
            left_box,
            text="Name",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8, "bold"),
            relief="raised",
            bd=1,
            anchor="w",
            padx=4,
            pady=2
        )
        lbl_head.pack(fill="x")

        list_scroll = tk.Scrollbar(left_box, orient="vertical")
        self.preset_listbox = tk.Listbox(
            left_box,
            bg=THEME["bg_input"],
            fg=THEME["text_main"],
            selectbackground=THEME["select_bg"],
            selectforeground=THEME["select_fg"],
            borderwidth=2,
            relief="sunken",
            font=("Segoe UI", 9),
            yscrollcommand=list_scroll.set
        )
        list_scroll.config(command=self.preset_listbox.yview)
        list_scroll.pack(side="right", fill="y")
        self.preset_listbox.pack(side="left", fill="both", expand=True)
        self.preset_listbox.bind("<<ListboxSelect>>", self.on_listbox_select)

        # -------------------------------------------------------------
        # Painel Direito: Configuração detalhada do DieProc
        # -------------------------------------------------------------
        right_box = tk.Frame(content_frame, bg=THEME["bg_surface"])
        right_box.pack(side="left", fill="both", expand=True)

        # Linha 1: Name e Coupling
        row1 = tk.Frame(right_box, bg=THEME["bg_surface"])
        row1.pack(fill="x", pady=(0, 6))

        tk.Label(row1, text="Name:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), width=7, anchor="w").pack(side="left")
        self.ent_name = tk.Entry(row1, bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 9), relief="sunken", bd=2, width=14)
        self.ent_name.pack(side="left", padx=(0, 16))

        tk.Label(row1, text="Coupling:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(side="left")
        self.cb_coupling = ttk.Combobox(
            row1,
            values=["0/0 0/180", "0/0", "0/180", "0/90", "0/0 0/90 0/180", "0/0 0/90 0/180 0/270"],
            font=("Segoe UI", 9),
            width=16
        )
        self.cb_coupling.pack(side="left", padx=(6, 0))

        # Linha 2: Step e Solutions
        row2 = tk.Frame(right_box, bg=THEME["bg_surface"])
        row2.pack(fill="x", pady=(0, 8))

        tk.Label(row2, text="Step:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), width=7, anchor="w").pack(side="left")
        self.sp_step = tk.Spinbox(row2, from_=0, to=90, increment=1, bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 9), width=6, relief="sunken", bd=2)
        self.sp_step.pack(side="left", padx=(0, 24))

        tk.Label(row2, text="Solutions:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(side="left")
        self.sp_solutions = tk.Spinbox(row2, from_=1, to=200, increment=1, bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 9), width=6, relief="sunken", bd=2)
        self.sp_solutions.pack(side="left", padx=(6, 0))

        # Linha 3: 3 Caixas de Faixas Angulares (Range 1, Range 2, Range 3)
        row_ranges = tk.Frame(right_box, bg=THEME["bg_surface"])
        row_ranges.pack(fill="x", pady=(0, 8))

        # Range 1
        box_r1 = tk.LabelFrame(row_ranges, text="Range 1", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), relief="groove")
        box_r1.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self.ent_r1_from, self.ent_r1_to, self.ent_r1_step = self._build_range_fields(box_r1)

        # Range 2
        box_r2 = tk.LabelFrame(row_ranges, text="Range 2", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), relief="groove")
        box_r2.pack(side="left", fill="both", expand=True, padx=2)
        self.ent_r2_from, self.ent_r2_to, self.ent_r2_step = self._build_range_fields(box_r2)

        # Range 3
        box_r3 = tk.LabelFrame(row_ranges, text="Range 3", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), relief="groove")
        box_r3.pack(side="left", fill="both", expand=True, padx=(4, 0))
        self.ent_r3_from, self.ent_r3_to, self.ent_r3_step = self._build_range_fields(box_r3)

        # Linha 4: Gaps e Checkboxes (Row interlock, Diagonal)
        row4 = tk.Frame(right_box, bg=THEME["bg_surface"])
        row4.pack(fill="x", pady=(0, 8))

        box_gaps = tk.LabelFrame(row4, text="Gaps", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), relief="groove")
        box_gaps.pack(side="left", fill="both", expand=True, padx=(0, 6))

        gaps_inner = tk.Frame(box_gaps, bg=THEME["bg_surface"], padx=4, pady=4)
        gaps_inner.pack(fill="both", expand=True)

        self.sp_gap1 = tk.Spinbox(gaps_inner, from_=0, to=50, increment=0.5, bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 9), width=5, relief="sunken", bd=2)
        self.sp_gap1.pack(side="left", padx=2)

        self.sp_gap2 = tk.Spinbox(gaps_inner, from_=0, to=50, increment=0.5, bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 9), width=5, relief="sunken", bd=2)
        self.sp_gap2.pack(side="left", padx=2)

        self.sp_gap3 = tk.Spinbox(gaps_inner, from_=0, to=50, increment=0.5, bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 9), width=5, relief="sunken", bd=2)
        self.sp_gap3.pack(side="left", padx=2)

        box_checks = tk.Frame(row4, bg=THEME["bg_surface"], padx=6, pady=4)
        box_checks.pack(side="left", fill="both", expand=True)

        self.var_row_interlock = tk.BooleanVar(value=True)
        self.chk_row_interlock = tk.Checkbutton(
            box_checks,
            text="Row interlock",
            variable=self.var_row_interlock,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            selectcolor="#ffffff",
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 9)
        )
        self.chk_row_interlock.pack(anchor="w", pady=(2, 2))

        self.var_diagonal = tk.BooleanVar(value=False)
        self.chk_diagonal = tk.Checkbutton(
            box_checks,
            text="Diagonal",
            variable=self.var_diagonal,
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            selectcolor="#ffffff",
            activebackground=THEME["bg_surface"],
            font=("Segoe UI", 9)
        )
        self.chk_diagonal.pack(anchor="w", pady=(2, 2))

        # -------------------------------------------------------------
        # Barra Inferior de Botões de Ação
        # -------------------------------------------------------------
        bot_bar = tk.Frame(main_box, bg=THEME["bg_surface"], pady=4)
        bot_bar.pack(fill="x", side="bottom")

        # Botões à Esquerda: Update, Show usage, Clear, No Selection
        left_btns = tk.Frame(bot_bar, bg=THEME["bg_surface"])
        left_btns.pack(side="left")

        self.btn_update = tk.Button(
            left_btns,
            text="Update",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8),
            width=8,
            relief="raised",
            bd=2,
            command=self.on_update_clicked
        )
        self.btn_update.pack(side="left", padx=(0, 4))

        self.btn_show_usage = tk.Button(
            left_btns,
            text="Show usage",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8),
            width=10,
            relief="raised",
            bd=2,
            command=self.on_show_usage
        )
        self.btn_show_usage.pack(side="left", padx=4)

        self.btn_clear = tk.Button(
            left_btns,
            text="Clear",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8),
            width=7,
            relief="raised",
            bd=2,
            command=self.on_clear_clicked
        )
        self.btn_clear.pack(side="left", padx=4)

        self.btn_no_sel = tk.Button(
            left_btns,
            text="No Selection",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8),
            width=11,
            relief="raised",
            bd=2,
            command=self.on_no_selection
        )
        self.btn_no_sel.pack(side="left", padx=4)

        # Botões à Direita: Cancel, Select
        right_btns = tk.Frame(bot_bar, bg=THEME["bg_surface"])
        right_btns.pack(side="right")

        self.btn_cancel = tk.Button(
            right_btns,
            text="Cancel",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8),
            width=8,
            relief="raised",
            bd=2,
            command=self.destroy
        )
        self.btn_cancel.pack(side="left", padx=(0, 6))

        self.btn_select = tk.Button(
            right_btns,
            text="Select",
            bg=THEME["bg_surface"],
            fg=THEME["text_main"],
            font=("Segoe UI", 8, "bold"),
            width=8,
            relief="raised",
            bd=2,
            command=self.on_select_clicked
        )
        self.btn_select.pack(side="left")

    def _build_range_fields(self, parent_frame):
        grid = tk.Frame(parent_frame, bg=THEME["bg_surface"], padx=4, pady=4)
        grid.pack(fill="both", expand=True)

        tk.Label(grid, text="From:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), anchor="w").grid(row=0, column=0, sticky="w", pady=1)
        ent_from = tk.Entry(grid, bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 8), width=5, relief="sunken", bd=2)
        ent_from.grid(row=0, column=1, padx=2, pady=1)

        tk.Label(grid, text="To:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), anchor="w").grid(row=1, column=0, sticky="w", pady=1)
        ent_to = tk.Entry(grid, bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 8), width=5, relief="sunken", bd=2)
        ent_to.grid(row=1, column=1, padx=2, pady=1)

        tk.Label(grid, text="Step:", bg=THEME["bg_surface"], fg=THEME["text_main"], font=("Segoe UI", 8), anchor="w").grid(row=2, column=0, sticky="w", pady=1)
        ent_step = tk.Entry(grid, bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 8), width=5, relief="sunken", bd=2)
        ent_step.grid(row=2, column=1, padx=2, pady=1)

        return ent_from, ent_to, ent_step

    def populate_presets(self):
        self.preset_listbox.delete(0, "end")
        self.presets = self.db.get_dieproc_presets()
        for name in sorted(self.presets.keys()):
            self.preset_listbox.insert("end", name)

    def select_preset(self, name):
        self.presets = self.db.get_dieproc_presets()
        preset = self.presets.get(name)
        if not preset and self.presets:
            name = next(iter(self.presets.keys()))
            preset = self.presets[name]

        if not preset:
            return

        self.active_preset_name = name

        # Seleciona visualmente na listbox
        items = self.preset_listbox.get(0, "end")
        for i, item in enumerate(items):
            if item == name:
                self.preset_listbox.selection_clear(0, "end")
                self.preset_listbox.selection_set(i)
                self.preset_listbox.see(i)
                break

        # Carrega dados nos controles
        self._set_entry(self.ent_name, preset.get("name", ""))
        self.cb_coupling.set(preset.get("coupling", "0/0 0/180"))
        self._set_spin(self.sp_step, preset.get("step", 1.0))
        self._set_spin(self.sp_solutions, preset.get("solutions", 30))

        self._set_entry(self.ent_r1_from, preset.get("range1_from", -3.0))
        self._set_entry(self.ent_r1_to, preset.get("range1_to", 3.0))
        self._set_entry(self.ent_r1_step, preset.get("range1_step", 1.0))

        self._set_entry(self.ent_r2_from, preset.get("range2_from", 0.0))
        self._set_entry(self.ent_r2_to, preset.get("range2_to", 0.0))
        self._set_entry(self.ent_r2_step, preset.get("range2_step", 0.0))

        self._set_entry(self.ent_r3_from, preset.get("range3_from", 0.0))
        self._set_entry(self.ent_r3_to, preset.get("range3_to", 0.0))
        self._set_entry(self.ent_r3_step, preset.get("range3_step", 0.0))

        self._set_spin(self.sp_gap1, preset.get("gap1", 1.0))
        self._set_spin(self.sp_gap2, preset.get("gap2", 0.0))
        self._set_spin(self.sp_gap3, preset.get("gap3", 0.0))

        self.var_row_interlock.set(bool(preset.get("row_interlock", 1)))
        self.var_diagonal.set(bool(preset.get("diagonal", 0)))

    def _set_entry(self, entry, value):
        entry.delete(0, "end")
        val_str = f"{value:g}" if isinstance(value, (int, float)) else str(value)
        entry.insert(0, val_str)

    def _set_spin(self, spin, value):
        spin.delete(0, "end")
        val_str = f"{value:g}" if isinstance(value, (int, float)) else str(value)
        spin.insert(0, val_str)

    def _get_float(self, entry, default=0.0):
        try:
            return float(str(entry.get()).replace(",", ".").strip())
        except ValueError:
            return default

    def _get_int(self, entry, default=1):
        try:
            return int(float(str(entry.get()).strip()))
        except ValueError:
            return default

    def get_current_fields_dict(self):
        name = self.ent_name.get().strip() or "NOVO"
        return {
            "name": name,
            "coupling": self.cb_coupling.get().strip() or "0/0 0/180",
            "step": self._get_float(self.sp_step, 1.0),
            "solutions": self._get_int(self.sp_solutions, 30),
            "range1_from": self._get_float(self.ent_r1_from, -3.0),
            "range1_to": self._get_float(self.ent_r1_to, 3.0),
            "range1_step": self._get_float(self.ent_r1_step, 1.0),
            "range2_from": self._get_float(self.ent_r2_from, 0.0),
            "range2_to": self._get_float(self.ent_r2_to, 0.0),
            "range2_step": self._get_float(self.ent_r2_step, 0.0),
            "range3_from": self._get_float(self.ent_r3_from, 0.0),
            "range3_to": self._get_float(self.ent_r3_to, 0.0),
            "range3_step": self._get_float(self.ent_r3_step, 0.0),
            "gap1": self._get_float(self.sp_gap1, 1.0),
            "gap2": self._get_float(self.sp_gap2, 0.0),
            "gap3": self._get_float(self.sp_gap3, 0.0),
            "row_interlock": 1 if self.var_row_interlock.get() else 0,
            "diagonal": 1 if self.var_diagonal.get() else 0,
        }

    def on_listbox_select(self, event):
        sel = self.preset_listbox.curselection()
        if sel:
            name = self.preset_listbox.get(sel[0])
            self.select_preset(name)

    def on_update_clicked(self):
        data = self.get_current_fields_dict()
        self.db.save_dieproc_preset(data)
        self.populate_presets()
        self.select_preset(data["name"])
        messagebox.showinfo("DieProc", f"Predefinição '{data['name']}' atualizada com sucesso no banco de dados.", parent=self)

    def on_clear_clicked(self):
        self._set_entry(self.ent_name, "")
        self.cb_coupling.set("0/0 0/180")
        self._set_spin(self.sp_step, 1)
        self._set_spin(self.sp_solutions, 30)
        self._set_entry(self.ent_r1_from, 0)
        self._set_entry(self.ent_r1_to, 0)
        self._set_entry(self.ent_r1_step, 0)
        self._set_entry(self.ent_r2_from, 0)
        self._set_entry(self.ent_r2_to, 0)
        self._set_entry(self.ent_r2_step, 0)
        self._set_entry(self.ent_r3_from, 0)
        self._set_entry(self.ent_r3_to, 0)
        self._set_entry(self.ent_r3_step, 0)
        self._set_spin(self.sp_gap1, 1.0)
        self._set_spin(self.sp_gap2, 0.0)
        self._set_spin(self.sp_gap3, 0.0)
        self.var_row_interlock.set(False)
        self.var_diagonal.set(False)

    def on_no_selection(self):
        self.preset_listbox.selection_clear(0, "end")

    def on_show_usage(self):
        data = self.get_current_fields_dict()
        interlock_txt = "Ativado (linhas alternadas encaixadas)" if data["row_interlock"] else "Desativado (grade padrão)"
        diag_txt = "Ativado" if data["diagonal"] else "Desativado"
        info = (
            f"Predefinição: {data['name']}\n\n"
            f"• Acoplamento de Rotação (Coupling): {data['coupling']}\n"
            f"• Passo Angular (Step): {data['step']}° | Soluções: {data['solutions']}\n"
            f"• Tolerância Angular Range 1: {data['range1_from']}° até {data['range1_to']}° (passo {data['range1_step']}°)\n"
            f"• Espaçamento (Gap 1): {data['gap1']} mm\n"
            f"• Intertravamento de Linhas (Row interlock): {interlock_txt}\n"
            f"• Distribuição Diagonal: {diag_txt}\n\n"
            f"Este perfil é utilizado pelo motor de corte contínuo (dp98) nas estratégias flashnestsheet e flashnestroll."
        )
        messagebox.showinfo("DieProc Usage", info, parent=self)

    def on_select_clicked(self):
        data = self.get_current_fields_dict()
        self.db.save_dieproc_preset(data)
        if self.on_select_cb:
            self.on_select_cb(data)
        self.destroy()
