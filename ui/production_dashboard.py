"""Painel gerencial: dados de planejamento, sem inferir execução de corte."""
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import date
from analytics.production_dashboard import fetch_data, summarize
from config import THEME


class ProductionDashboard(tk.Toplevel):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.title('Painel de Produção — Planejamento')
        self.geometry('1020x700')
        self.minsize(820, 560)
        self.configure(bg=THEME['bg_main'])
        self.start = tk.StringVar()
        self.end = tk.StringVar()
        self.material = tk.StringVar(value='Todos')
        self.summary = tk.StringVar()
        self.notice = tk.StringVar()
        self._materials = {'Todos': None}
        self._build()
        self.refresh()

    def _build(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill='both', expand=True)
        ttk.Label(root, text='Painel de Produção', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        ttk.Label(root, text='Planejamento salvo • período pela data de criação da sessão').pack(anchor='w', pady=(0, 8))
        filters = ttk.Frame(root)
        filters.pack(fill='x', pady=4)
        for label, var in [('De (AAAA-MM-DD)', self.start), ('Até (AAAA-MM-DD)', self.end)]:
            ttk.Label(filters, text=label).pack(side='left', padx=(0, 4))
            ttk.Entry(filters, textvariable=var, width=12).pack(side='left', padx=(0, 12))
        ttk.Label(filters, text='Material').pack(side='left')
        self.material_box = ttk.Combobox(filters, textvariable=self.material, state='readonly', width=25)
        self.material_box.pack(side='left', padx=6)
        ttk.Button(filters, text='Atualizar', command=self.refresh).pack(side='left', padx=5)
        ttk.Label(root, textvariable=self.summary, justify='left', font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=10)
        ttk.Label(root, textvariable=self.notice, justify='left', wraplength=970).pack(anchor='w', pady=(0, 8))
        notebook = ttk.Notebook(root)
        notebook.pack(fill='both', expand=True)
        self.material_tree = self._table(notebook, 'Por material', ('Material', 'Layouts válidos', 'Área por camada (m²)', 'Aproveitamento (%)', 'Área não ocupada (m²)'))
        self.day_tree = self._table(notebook, 'Evolução por dia', ('Data da sessão', 'Layouts válidos', 'Área por camada (m²)', 'Aproveitamento (%)', 'Área não ocupada (m²)'))
        ttk.Label(root, text='Fonte: sessões e layouts persistidos. Área não ocupada é estimativa geométrica por camada; não é desperdício medido.', wraplength=970).pack(anchor='w', pady=(8, 0))
        ttk.Label(root, text='Produção efetiva, corte concluído, tempo de processamento e filtro por operador: indisponíveis até haver registros confiáveis.', wraplength=970).pack(anchor='w')

    def _table(self, notebook, title, columns):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=170, stretch=True, anchor='w')
        scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        return tree

    def refresh(self):
        try:
            start = date.fromisoformat(self.start.get().strip()) if self.start.get().strip() else None
            end = date.fromisoformat(self.end.get().strip()) if self.end.get().strip() else None
            if start and end and start > end:
                raise ValueError('A data inicial deve ser anterior ou igual à final.')
            sessions, layouts = fetch_data(self.db)
            self._materials = {'Todos': None}
            for s in sessions:
                if s.get('material_id'):
                    label = f"{s['material_id']} — {s.get('material_name') or 'Sem nome'}"
                    self._materials[label] = str(s['material_id'])
            self.material_box['values'] = list(self._materials)
            if self.material.get() not in self._materials:
                self.material.set('Todos')
            data = summarize(sessions, layouts, start, end, self._materials[self.material.get()])
        except Exception as exc:
            messagebox.showerror('Painel de Produção', f'Não foi possível carregar o painel: {exc}', parent=self)
            return
        rate = f"{data['yield_pct']:.2f}%" if data['yield_pct'] is not None else 'Indisponível'
        area = f"{data['area_m2_per_layer']:.2f} m²" if data['yield_pct'] is not None else 'Indisponível'
        pairs = f"{data['pairs_planned']}" if not data['sessions_missing_pairs'] else f"{data['pairs_planned']} (parcial)"
        self.summary.set(f"Ordens com sessões: {data['orders']}     Sessões: {data['sessions']}     Pares planejados: {pairs}\n"
                         f"Layouts salvos: {data['layouts']}     Aproveitamento ponderado: {rate}     Área por camada: {area}")
        self.notice.set(f"Layouts sem dimensões ou rendimento válidos: {data['invalid_layouts']} • Sessões com quantidades inválidas: {data['sessions_missing_pairs']} • Sessões sem data: {data['undated_sessions']}")
        for tree, rows, material in ((self.material_tree, data['materials'], True), (self.day_tree, data['days'], False)):
            tree.delete(*tree.get_children())
            for key, row in rows:
                name = f'{key[0]} — {key[1]}' if material else key or 'Sem data'
                rate = f"{row['yield_pct']:.2f}" if row['yield_pct'] is not None else 'Indisponível'
                tree.insert('', 'end', values=(name, row['layouts'], f"{row['area']:.2f}", rate, f"{max(0, row['area'] - row['used']):.2f}"))
