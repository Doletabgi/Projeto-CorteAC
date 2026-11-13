"""Read-only consultation of material-scoped learning and actual macro usage."""
import tkinter as tk
from tkinter import ttk

from cad.ai_learner import NestingAIBrain
from config import THEME


class LearningHistoryDialog(tk.Toplevel):
    def __init__(self, parent, db, material_code=None):
        super().__init__(parent)
        self.db = db
        self.current_code = str(material_code).strip() if material_code is not None else ''
        self.rows = []
        self.title('Consultar aprendizado por material')
        self.geometry('1000x540')
        self.minsize(760, 400)
        self.configure(bg=THEME['bg_surface'])
        self.transient(parent)

        content = ttk.Frame(self, padding=12)
        content.pack(fill='both', expand=True)
        ttk.Label(content, text='Aprendizado e uso da macro por material',
                  font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(content, text='Consulte os exemplos salvos e os cálculos que realmente aplicaram ajustes aprendidos.').pack(anchor='w', pady=(3, 10))
        bar = ttk.Frame(content)
        bar.pack(fill='x', pady=(0, 8))
        ttk.Label(bar, text='Filtrar código:').pack(side='left')
        self.filter_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.filter_var, width=28)
        entry.pack(side='left', padx=6)
        self.filter_var.trace_add('write', lambda *_: self.render_rows())
        ttk.Button(bar, text='Atualizar', command=self.refresh).pack(side='right')

        table_frame = ttk.Frame(content)
        table_frame.pack(fill='both', expand=True)
        self.table = ttk.Treeview(table_frame, columns=('code', 'examples', 'runs', 'used', 'last'),
                                 show='headings', height=8, selectmode='browse')
        for name, title, width in (('code', 'Código do material', 130), ('examples', 'Padrões salvos', 110),
                                    ('runs', 'Cálculos da macro', 130), ('used', 'Cálculos com ajustes', 145),
                                    ('last', 'Último resultado', 280)):
            self.table.heading(name, text=title)
            self.table.column(name, width=width, minwidth=75, stretch=name == 'last')
        scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.table.bind('<<TreeviewSelect>>', self.show_details)
        self.summary = ttk.Label(content, text='')
        self.summary.pack(anchor='w', pady=(5, 8))
        ttk.Label(content, text='Exemplos do material selecionado', font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        details_frame = ttk.Frame(content)
        details_frame.pack(fill='both', expand=True, pady=4)
        self.details = tk.Text(details_frame, height=6, wrap='word', state='disabled', font=('Segoe UI', 9))
        details_scroll = ttk.Scrollbar(details_frame, orient='vertical', command=self.details.yview)
        self.details.configure(yscrollcommand=details_scroll.set)
        self.details.pack(side='left', fill='both', expand=True)
        details_scroll.pack(side='right', fill='y')
        ttk.Label(content, text='Sem registro = uso anterior sem contagem. Consultar padrões não significa que houve ajustes.').pack(anchor='w', pady=4)
        ttk.Button(content, text='Fechar', command=self.destroy).pack(anchor='e')
        self.bind('<Escape>', lambda _: self.destroy())
        self.refresh()
        entry.focus_set()

    def refresh(self):
        try:
            self.rows = NestingAIBrain.material_activity(self.db, self.current_code)
            self.render_rows()
        except Exception as exc:
            self.summary.config(text=f'Não foi possível consultar o histórico: {exc}')

    def render_rows(self):
        selected = self.table.selection()
        code = selected[0] if selected else self.current_code
        self.table.delete(*self.table.get_children())
        query = self.filter_var.get().strip().casefold()
        visible = [r for r in self.rows if query in r['material_code'].casefold()]
        for row in visible:
            self.table.insert('', 'end', iid=row['material_code'], values=(
                row['material_code'], row['habits_count'], row.get('macro_runs', 'Sem registro'),
                row.get('applied_runs', 'Sem registro'), row.get('last_result', 'Uso ainda não registrado')))
        self.summary.config(text=f'{len(visible)} materiais com histórico' if visible else 'Nenhum material com histórico para este filtro.')
        if visible:
            code = code if code in self.table.get_children() else visible[0]['material_code']
            self.table.selection_set(code)
            self.table.see(code)
        self.show_details()

    def show_details(self, event=None):
        selected = self.table.selection()
        text = 'Selecione um material para consultar seus exemplos.'
        if selected:
            code = selected[0]
            try:
                habits = NestingAIBrain(self.db, code).get_learned_habits()
                lines = [f'Material: {code}']
                for habit in habits:
                    source = habit.get('source', [None])[0]
                    target = habit.get('target', [None])[0]
                    pair = f'{source} → {target}' if source and target else habit.get('pair_key', 'Padrão anterior')
                    lines.append(f"{pair} | {habit.get('count', 1)} observações | "
                                 f"Rotações: {habit.get('rot1', '?')}° / {habit.get('rot2', '?')}°")
                if not habits:
                    lines.append('Nenhum exemplo manual salvo. Pode haver histórico de cálculos automáticos.')
                text = '\n'.join(lines)
            except Exception as exc:
                text = f'Não foi possível consultar os exemplos: {exc}'
        self.details.config(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', text)
        self.details.config(state='disabled')
