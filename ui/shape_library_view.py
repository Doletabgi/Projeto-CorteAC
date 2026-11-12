"""Biblioteca visual de moldes e preparação da seleção para uma sessão."""
import math
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont, ttk

from cad.shape_library import add_shapes_to_session, contour_points, filter_shapes, shape_folder, validate_pairs
from ui.icon_widgets import IconButton, IconLabel
from ui.icons import get_icon
from ui.library_presentations import DETAIL_COLUMNS, VIEW_MODES, shape_metrics, sort_value
from ui.sort_utils import natural_sort_key, size_sort_key
from ui.tooltip import ToolTip

BG = '#f3f6fb'
WHITE = '#ffffff'
INK = '#172554'
MUTED = '#64748b'
BLUE = '#2563eb'
BORDER = '#d9e1ec'


class ShapeLibraryView(tk.Frame):
    def __init__(self, parent, db, on_close=None, on_minimize=None, on_maximize=None,
                 on_edit_shape=None, on_session_updated=None, on_new_session=None, **kwargs):
        super().__init__(parent, bg=BG, **kwargs)
        self.db = db
        self.on_close_cb = on_close
        self.on_minimize_cb = on_minimize
        self.on_maximize_cb = on_maximize
        self.on_edit_shape_cb = on_edit_shape
        self.on_session_updated_cb = on_session_updated
        self.on_new_session_cb = on_new_session
        self.scale = max(1.0, float(self.tk.call('tk', 'scaling')) / (96 / 72))
        self.shapes_list = []
        self.shapes_by_id = {}
        self._valid_ids = set()
        self.filtered_shapes = []
        self.filtered_ids = set()
        self.selected_pairs = {}  # id -> texto; preserva edição incompleta até validar.
        self.folder_filter = None
        self.article_filter = None
        self.focused_id = None
        self.existing_ids = set()
        self.sessions = []
        self.destination_id = None
        self._destination_chosen = False
        self.active_session_id = None
        self._session_labels = {}
        self._folder_keys = {}
        self._session_error = False
        self._loading = False
        self._adding = False
        self._destroyed = False
        self._filter_job = None
        self._render_job = None
        self._poll_job = None
        self._results = queue.Queue()
        self._basket_page = 0
        self._pair_vars = {}
        self._pair_entries = {}
        self._pair_traces = []
        self._card_columns = 1
        self._last_width = 0
        self.view_mode = 'cards'
        self.view_choice = tk.StringVar(self, VIEW_MODES[self.view_mode])
        self._sort_column = None
        self._sort_reverse = False
        self._metrics_cache = {}
        self.query = tk.StringVar(self)
        self.size_filter = tk.StringVar(self, 'Todos')
        self.destination = tk.StringVar(self)
        self.default_pairs = tk.StringVar(self, '12')
        self.select_all_var = tk.BooleanVar(self, False)
        self.folder_label = tk.StringVar(self, 'Todas as pastas')
        self.status = tk.StringVar(self, 'Escolha os moldes para montar sua sessão.')
        self._build()
        self.query.trace_add('write', self._queue_filter)
        self.bind('<Configure>', self._on_resize, add='+')
        self.reload_data()

    def u(self, value):
        return round(value * self.scale)

    def _label(self, parent, text, size=9, bold=False, **kw):
        return tk.Label(parent, text=text, bg=WHITE, fg=INK if bold else MUTED,
                        font=('Segoe UI', size, 'bold' if bold else 'normal'), **kw)

    def _button(self, parent, text, command, icon=None, primary=False, **kw):
        return IconButton(parent, text=text, icon=icon, command=command,
                          image=get_icon(self, icon, color=WHITE) if primary and icon else '', compound='left',
                          bg=BLUE if primary else WHITE, fg=WHITE if primary else INK,
                          activebackground='#1d4ed8' if primary else '#eaf1ff',
                          activeforeground=WHITE if primary else INK, bd=0, relief='flat',
                          highlightbackground=BLUE if primary else BORDER, highlightthickness=1, highlightcolor=BLUE,
                          font=('Segoe UI', 9, 'bold' if primary else 'normal'), padx=8, pady=4, **kw)

    def _build(self):
        self.title_bar = tk.Frame(self, bg=WHITE, padx=14, pady=10)
        self.title_bar.pack(fill='x')
        IconLabel(self.title_bar, text='Catálogo de Moldes', icon='catalog', bg=WHITE,
                  fg=INK, font=('Segoe UI', 18, 'bold')).pack(side='left')
        self.lbl_title = self.title_bar.winfo_children()[0]
        controls = tk.Frame(self.title_bar, bg=WHITE)
        controls.pack(side='right')
        self.btn_min = self._button(controls, '_', lambda: self._window_action(self.on_minimize_cb))
        self.btn_min.pack(side='left', padx=2)
        self.btn_max = self._button(controls, '□', lambda: self._window_action(self.on_maximize_cb))
        self.btn_max.pack(side='left', padx=2)
        self.btn_close = self._button(controls, '✕', self.on_close_click)
        self.btn_close.pack(side='left', padx=2)
        self.active_badge = self._label(controls, 'Sem sessão ativa', 9, True, padx=10)
        self.active_badge.pack(side='left', before=self.btn_min, padx=8)
        self.title_bar.bind('<ButtonPress-1>', self._title_press)
        self.title_bar.bind('<B1-Motion>', self._title_drag)
        self.lbl_title.bind('<ButtonPress-1>', self._title_press)
        self.lbl_title.bind('<B1-Motion>', self._title_drag)
        tk.Label(self, text='Encontre moldes, escolha os tamanhos e adicione à sessão.',
                 bg=WHITE, fg=MUTED, font=('Segoe UI', 10), anchor='w', padx=16).pack(fill='x', pady=(0, 8))
        self.content = tk.Frame(self, bg=BG, padx=8, pady=6)
        self.content.pack(fill='both', expand=True)
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(1, weight=1)
        self.left_panel = tk.Frame(self.content, bg=WHITE, width=self.u(185),
                                    highlightbackground=BORDER, highlightthickness=1, padx=10, pady=12)
        self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        self.left_panel.pack_propagate(False)
        self._label(self.left_panel, 'Pastas', 12, True).pack(anchor='w', pady=(0, 8))
        style = ttk.Style(self)
        style.configure('Library.Treeview', background=WHITE, fieldbackground=WHITE,
                        foreground=INK, rowheight=self.u(29), borderwidth=0, font=('Segoe UI', 9))
        style.map('Library.Treeview', background=[('selected', '#dbeafe')], foreground=[('selected', INK)])
        style.configure('Library.TCombobox', fieldbackground=WHITE, background=WHITE, foreground=INK)
        style.map('Library.TCombobox', fieldbackground=[('readonly', WHITE)], foreground=[('readonly', INK)])
        folders_box = tk.Frame(self.left_panel, bg=WHITE)
        folders_box.pack(fill='both', expand=True)
        self.folder_tree = ttk.Treeview(folders_box, show='tree', selectmode='browse', style='Library.Treeview')
        self.folder_tree.column('#0', width=self.u(145), minwidth=80, stretch=True)
        folder_scroll = ttk.Scrollbar(folders_box, orient='vertical', command=self.folder_tree.yview)
        self.folder_tree.configure(yscrollcommand=folder_scroll.set)
        folder_scroll.pack(side='right', fill='y')
        self.folder_tree.pack(fill='both', expand=True)
        self.folder_tree.bind('<<TreeviewSelect>>', self._folder_selected)
        self._label(self.left_panel, 'Filtrar por tamanho', 10, True).pack(anchor='w', pady=(16, 6))
        self.size_combo = ttk.Combobox(self.left_panel, textvariable=self.size_filter, state='readonly', width=14, style='Library.TCombobox')
        self.size_combo.pack(fill='x')
        self.size_combo.bind('<<ComboboxSelected>>', lambda event: self.apply_filters())
        self._button(self.left_panel, 'Limpar filtros', self.clear_filters, 'refresh').pack(fill='x', pady=(10, 0))

        self.center_panel = tk.Frame(self.content, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        self.center_panel.grid(row=0, column=1, sticky='nsew')
        search_row = tk.Frame(self.center_panel, bg=WHITE, padx=12, pady=12)
        search_row.pack(fill='x')
        IconLabel(search_row, icon='zoom', text='', bg=WHITE).pack(side='left', padx=(0, 6))
        self.search_entry = ttk.Entry(search_row, textvariable=self.query, font=('Segoe UI', 11))
        self.search_entry.pack(side='left', fill='x', expand=True, ipady=4)
        ToolTip(self.search_entry, 'Buscar por nome, modelo, pasta, tamanho ou código. A busca ignora acentos.')
        refresh = self._button(search_row, '', self.reload_data, 'refresh')
        refresh.pack(side='left', padx=(6, 0))
        ToolTip(refresh, 'Atualizar moldes e sessões do banco de dados')
        self._label(self.center_panel, 'Buscar por nome, modelo ou pasta', 8).pack(anchor='w', padx=12)
        self.compact_filters = tk.Frame(self.center_panel, bg=WHITE, padx=12, pady=6)
        self.compact_folder = ttk.Combobox(self.compact_filters, textvariable=self.folder_label, state='readonly', width=18, style='Library.TCombobox')
        self.compact_folder.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.compact_folder.bind('<<ComboboxSelected>>', self._compact_folder_selected)
        self._label(self.compact_filters, 'Tamanho', 8).pack(side='left', padx=4)
        compact_size = ttk.Combobox(self.compact_filters, textvariable=self.size_filter, state='readonly', width=8, style='Library.TCombobox')
        compact_size.pack(side='left')
        compact_size.bind('<<ComboboxSelected>>', lambda event: self.apply_filters())
        self.compact_size = compact_size
        self.count_label = self._label(self.center_panel, 'Carregando moldes...', 10, True, anchor='w')
        self.count_label.pack(fill='x', padx=12, pady=(9, 5))
        self.view_controls = tk.Frame(self.center_panel, bg=WHITE, padx=12, pady=4)
        self.view_controls.pack(fill='x')
        self._label(self.view_controls, 'Visualização:', 9, True).pack(side='left', padx=(0, 8))
        self.view_combo = ttk.Combobox(self.view_controls, textvariable=self.view_choice,
                                       values=list(VIEW_MODES.values()), state='readonly',
                                       width=22, style='Library.TCombobox')
        self.view_combo.pack(side='left')
        self.view_combo.bind('<<ComboboxSelected>>', self._view_changed)
        ToolTip(self.view_combo, 'Troque entre cartões grandes, cartões compactos, lista com prévias e tabela de detalhes.')
        actions = tk.Frame(self.center_panel, bg=WHITE, padx=10, pady=6)
        actions.pack(fill='x')
        self.select_all_button = tk.Checkbutton(actions, text='Selecionar todos', variable=self.select_all_var,
                                                command=self.toggle_all_visible, bg=WHITE, activebackground=WHITE,
                                                fg=INK, font=('Segoe UI', 9))
        self.select_all_button.pack(side='left')
        self.edit_button = self._button(actions, 'Editar molde', self.edit_focused, 'edit')
        self.edit_button.pack(side='right')
        self.edit_button.config(state='disabled')
        self.viewer = tk.Frame(self.center_panel, bg=WHITE)
        self.viewer.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self.viewer.columnconfigure(0, weight=1)
        self.viewer.rowconfigure(1, weight=1)
        self.details_header = tk.Canvas(self.viewer, bg='#eaf0f9', height=self.u(34), highlightthickness=0)
        self.details_header.grid(row=0, column=0, sticky='ew')
        self.details_header.grid_remove()
        self.details_header.bind('<Button-1>', self._header_clicked)
        ToolTip(self.details_header, 'Clique em uma coluna para ordenar. A área corresponde ao contorno externo, sem descontar furos.')
        self.cards_canvas = tk.Canvas(self.viewer, bg=WHITE, highlightthickness=0, takefocus=True)
        self.card_scroll = ttk.Scrollbar(self.viewer, orient='vertical', command=self._scroll_cards)
        self.card_scroll.grid(row=1, column=1, sticky='ns')
        self.cards_canvas.grid(row=1, column=0, sticky='nsew')
        self.horizontal_scroll = ttk.Scrollbar(self.viewer, orient='horizontal', command=self._scroll_horizontal)
        self.horizontal_scroll.grid(row=2, column=0, sticky='ew')
        self.horizontal_scroll.grid_remove()
        self.cards_canvas.configure(xscrollcommand=self.horizontal_scroll.set)
        self.cards_canvas.config(yscrollcommand=self.card_scroll.set)
        self.cards_canvas.bind('<Configure>', lambda event: self._queue_render())
        self.cards_canvas.bind('<Button-1>', self._card_clicked)
        self.cards_canvas.bind('<Double-Button-1>', lambda event: self.edit_focused())
        self.cards_canvas.bind('<MouseWheel>', self._wheel_cards)
        self.cards_canvas.bind('<Button-4>', lambda event: self._scroll_cards('scroll', -3, 'units'))
        self.cards_canvas.bind('<Button-5>', lambda event: self._scroll_cards('scroll', 3, 'units'))
        self.cards_canvas.bind('<space>', lambda event: self.toggle_shape(self.focused_id))
        self.cards_canvas.bind('<Return>', lambda event: self.edit_focused())
        self.cards_canvas.bind('<Control-a>', self._select_all_key)
        self.cards_canvas.bind('<Control-f>', lambda event: self.search_entry.focus_set())
        for key, dx, dy in (('Left', -1, 0), ('Right', 1, 0), ('Up', 0, -1), ('Down', 0, 1)):
            self.cards_canvas.bind(f'<{key}>', lambda event, x=dx, y=dy: self._navigate(x, y))
        self._build_basket()
        footer = tk.Frame(self, bg=WHITE, padx=14, pady=8)
        footer.pack(fill='x')
        self.status_label = tk.Label(footer, textvariable=self.status, bg=WHITE, fg=MUTED,
                                     font=('Segoe UI', 9), anchor='w', justify='left', wraplength=self.u(800))
        self.status_label.pack(side='left', fill='x', expand=True)
        self.connection_label = self._label(footer, 'Banco de dados', 8)
        self.connection_label.pack(side='right', padx=(10, 0))

    def _build_basket(self):
        self.right_panel = tk.Frame(self.content, bg=WHITE, width=self.u(310),
                                     highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        self.right_panel.grid(row=0, column=2, sticky='nsew', padx=(8, 0))
        self.right_panel.grid_propagate(False)
        self.right_panel.columnconfigure(0, weight=1)
        self.right_panel.rowconfigure(5, weight=1)
        self._label(self.right_panel, 'Adicionar à sessão', 13, True).grid(row=0, column=0, sticky='w')
        self._label(self.right_panel, 'Confira os moldes e as quantidades.', 9).grid(row=1, column=0, sticky='w', pady=(4, 14))
        self._label(self.right_panel, 'Sessão de destino', 9, True).grid(row=2, column=0, sticky='w')
        self.session_combo = ttk.Combobox(self.right_panel, textvariable=self.destination,
                                          state='readonly', font=('Segoe UI', 9), style='Library.TCombobox')
        self.session_combo.grid(row=3, column=0, sticky='ew', pady=(6, 10), ipady=3)
        self.session_combo.bind('<<ComboboxSelected>>', self._destination_changed)
        self.selection_label = self._label(self.right_panel, '0 moldes selecionados', 10, True, anchor='w')
        self.selection_label.grid(row=4, column=0, sticky='ew', pady=(0, 8))
        basket_box = tk.Frame(self.right_panel, bg=WHITE)
        basket_box.grid(row=5, column=0, sticky='nsew')
        self.basket_canvas = tk.Canvas(basket_box, bg=WHITE, highlightthickness=0)
        basket_scroll = ttk.Scrollbar(basket_box, orient='vertical', command=self.basket_canvas.yview)
        self.basket_canvas.configure(yscrollcommand=basket_scroll.set)
        basket_scroll.pack(side='right', fill='y')
        self.basket_canvas.pack(fill='both', expand=True)
        self.basket_rows = tk.Frame(self.basket_canvas, bg=WHITE)
        self._basket_window = self.basket_canvas.create_window((0, 0), window=self.basket_rows, anchor='nw')
        self.basket_canvas.bind('<Configure>', lambda event: self.basket_canvas.itemconfigure(self._basket_window, width=event.width))
        self.basket_rows.bind('<Configure>', lambda event: self.basket_canvas.configure(scrollregion=self.basket_canvas.bbox('all')))
        self.basket_canvas.bind('<MouseWheel>', self._wheel_basket)
        self.basket_canvas.bind('<Button-4>', lambda event: self.basket_canvas.yview_scroll(-2, 'units'))
        self.basket_canvas.bind('<Button-5>', lambda event: self.basket_canvas.yview_scroll(2, 'units'))
        self.page_bar = tk.Frame(self.right_panel, bg=WHITE)
        self.page_bar.grid(row=6, column=0, sticky='ew', pady=4)
        self.page_label = self._label(self.page_bar, '', 8)
        self.page_label.pack(side='left')
        self.page_prev = self._button(self.page_bar, '', lambda: self._change_page(-1), 'left')
        self.page_next = self._button(self.page_bar, '', lambda: self._change_page(1), 'right')
        self.page_next.pack(side='right')
        self.page_prev.pack(side='right', padx=3)
        self._label(self.right_panel, 'Mesma quantidade para selecionados', 8).grid(row=7, column=0, sticky='w', pady=(8, 4))
        quantity = tk.Frame(self.right_panel, bg=WHITE)
        quantity.grid(row=8, column=0, sticky='ew')
        ttk.Spinbox(quantity, from_=1, to=9999, textvariable=self.default_pairs, width=6,
                    font=('Segoe UI', 10)).pack(side='left', ipady=3)
        self.apply_pairs_button = self._button(quantity, 'Aplicar a todos', self.apply_pairs)
        self.apply_pairs_button.pack(side='right')
        self.add_button = self._button(self.right_panel, 'Adicionar à sessão', self.add_to_session, 'add', primary=True)
        self.add_button.grid(row=9, column=0, sticky='ew', pady=(14, 6), ipady=5)
        self.clear_selection_button = self._button(self.right_panel, 'Limpar seleção', self.clear_selection)
        self.clear_selection_button.grid(row=10, column=0, sticky='ew')
        if self.on_new_session_cb:
            self.new_session_button = self._button(self.right_panel, 'Nova sessão', self.on_new_session_cb, 'new')
            self.new_session_button.grid(row=11, column=0, sticky='ew', pady=(8, 0))

    def reload_data(self):
        if self._adding or self._destroyed:
            return
        self._loading = True
        try:
            shapes = self.db.get_all_shapes()
            sessions = self.db.get_catalog_sessions()
        except Exception:
            self._set_status('Não foi possível carregar o catálogo. Confira a conexão com o banco e clique em Atualizar.', error=True)
            self.connection_label.config(text='Banco indisponível', fg='#b91c1c')
            self._session_error = True
            self._update_actions()
            self._loading = False
            return
        self.shapes_list = shapes
        self._metrics_cache.clear()
        self.shapes_by_id = {str(shape['id']): shape for shape in shapes if shape.get('id') is not None}
        self._valid_ids = {key for key, shape in self.shapes_by_id.items() if contour_points(shape)}
        self.selected_pairs = {key: value for key, value in self.selected_pairs.items() if key in self.shapes_by_id}
        self._build_folders()
        sizes = sorted({str(shape.get('size') or '') for shape in shapes if shape.get('size')}, key=size_sort_key)
        self.size_combo.config(values=['Todos'] + sizes)
        self.compact_size.config(values=['Todos'] + sizes)
        if self.size_filter.get() != 'Todos' and self.size_filter.get() not in sizes:
            self.size_filter.set('Todos')
        self.set_session_context(sessions, self.active_session_id)
        self.connection_label.config(text='● Banco conectado', fg='#0f766e')
        self._loading = False
        self.apply_filters()
        self._set_status('Escolha os moldes, confira os pares e adicione à sessão.')

    def _build_folders(self):
        self.folder_tree.delete(*self.folder_tree.get_children())
        self._folder_keys = {'all': None, 'root': ''}
        self.folder_tree.insert('', 'end', iid='all', text=' Todos os moldes', image=get_icon(self, 'catalog', 16))
        self.folder_tree.insert('', 'end', iid='root', text=' Sem pasta', image=get_icon(self, 'folder', 16))
        folders = set()
        for shape in self.shapes_list:
            path = shape_folder(shape)
            parts = path.split('/') if path else []
            folders.update('/'.join(parts[:index]) for index in range(1, len(parts)+1))
        nodes = {}
        for index, path in enumerate(sorted(folders, key=natural_sort_key)):
            node = f'folder_{index}'
            parent = nodes.get(path.rpartition('/')[0], '')
            self.folder_tree.insert(parent, 'end', iid=node, text=' ' + path.rsplit('/', 1)[-1],
                                    image=get_icon(self, 'folder', 16), open=True)
            self._folder_keys[node] = path
            nodes[path] = node
        if self.folder_filter not in (None, '') and self.folder_filter not in folders:
            self.folder_filter = None
        node = next((key for key, value in self._folder_keys.items() if value == self.folder_filter), 'all')
        self.folder_tree.selection_set(node)
        self.compact_folder.config(values=['Todas as pastas', 'Sem pasta'] + sorted(folders, key=natural_sort_key))
        self.folder_label.set('Todas as pastas' if self.folder_filter is None else self.folder_filter or 'Sem pasta')

    def set_session_context(self, sessions, active_session_id=None, prefer_active=False):
        self.active_session_id = active_session_id
        self.active_badge.config(text=f'Sessão ativa: #{active_session_id}' if active_session_id is not None else 'Sem sessão ativa')
        if self._adding:
            return
        self.sessions = list(sessions)
        self._session_labels = {f"#{session['id']} · {session.get('name') or session.get('code') or 'Sessão'}": session['id']
                                for session in self.sessions}
        ids = {str(value) for value in self._session_labels.values()}
        if (prefer_active or not self._destination_chosen) and active_session_id is not None and str(active_session_id) in ids:
            self.destination_id = active_session_id
        elif str(self.destination_id) not in ids:
            self.destination_id = active_session_id if str(active_session_id) in ids else next(iter(self._session_labels.values()), None)
        self.session_combo.config(values=list(self._session_labels), state='disabled' if self._adding or not ids else 'readonly')
        label = next((label for label, value in self._session_labels.items() if str(value) == str(self.destination_id)), '')
        self.destination.set(label if label else 'Nenhuma sessão disponível')
        self._load_existing()

    def _load_existing(self):
        self._session_error = False
        try:
            shapes = self.db.get_session_shapes(self.destination_id) if self.destination_id is not None else []
            self.existing_ids = {str(shape['id']) for shape in shapes if shape.get('id') is not None}
        except Exception:
            self._session_error = True
            self._set_status('Não foi possível conferir os moldes da sessão. Atualize o catálogo antes de adicionar.', error=True)
        self._rebuild_basket()
        self._queue_render()

    def _destination_changed(self, event=None):
        if self._adding:
            return
        self._destination_chosen = True
        self.destination_id = self._session_labels.get(self.destination.get())
        self._load_existing()
        if not self._session_error:
            self._set_status('Sessão de destino alterada. Os moldes que já estão nela serão preservados.')

    def select_destination(self, session_id):
        label = next((label for label, value in self._session_labels.items() if str(value) == str(session_id)), None)
        if label is not None and not self._adding:
            self.destination.set(label)
            self._destination_changed()

    def _folder_selected(self, event=None):
        selected = self.folder_tree.selection()
        if not selected or self._loading:
            return
        if self._folder_keys[selected[0]] == self.folder_filter:
            return
        self.folder_filter = self._folder_keys[selected[0]]
        self.article_filter = None
        self.folder_label.set('Todas as pastas' if self.folder_filter is None else self.folder_filter or 'Sem pasta')
        self.apply_filters()

    def _compact_folder_selected(self, event=None):
        value = self.folder_label.get()
        self.folder_filter = None if value == 'Todas as pastas' else '' if value == 'Sem pasta' else value
        self.article_filter = None
        self.apply_filters()

    def clear_filters(self):
        self.query.set('')
        self.size_filter.set('Todos')
        self.folder_filter = None
        self.article_filter = None
        self.folder_label.set('Todas as pastas')
        self.folder_tree.selection_set('all')
        self.apply_filters()

    def show_article(self, article_id=None):
        self.article_filter = article_id
        self.folder_filter = None
        self.query.set('')
        self.size_filter.set('Todos')
        self.apply_filters()

    def _queue_filter(self, *args):
        if self._filter_job:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(150, self.apply_filters)

    def apply_filters(self):
        if self._filter_job:
            self.after_cancel(self._filter_job)
            self._filter_job = None
        size = '' if self.size_filter.get() == 'Todos' else self.size_filter.get()
        self.filtered_shapes = filter_shapes(self.shapes_list, self.query.get(), self.folder_filter, size, self.article_filter)
        self._sort_filtered()
        self.filtered_ids = {str(shape['id']) for shape in self.filtered_shapes}
        scope = 'Todos os moldes' if self.folder_filter is None else self.folder_filter or 'Sem pasta'
        if self.article_filter is not None:
            scope = f'Artigo #{self.article_filter}'
        self.count_label.config(text=f'{scope} · {len(self.filtered_shapes)} moldes encontrados')
        self.cards_canvas.yview_moveto(0)
        self._update_actions()
        self._queue_render()

    def _on_resize(self, event):
        if event.widget is not self or event.width == self._last_width:
            return
        self._last_width = event.width
        if event.width < self.u(1040):
            self.left_panel.grid_remove()
            if not self.compact_filters.winfo_manager():
                self.compact_filters.pack(fill='x', before=self.count_label)
        else:
            self.left_panel.grid()
            self.compact_filters.pack_forget()
        self.status_label.config(wraplength=max(self.u(250), event.width-self.u(180)))
        self._queue_render()

    def _queue_render(self):
        if not self._destroyed and self._render_job is None:
            self._render_job = self.after_idle(self._render_cards)

    def _scroll_cards(self, *args):
        self.cards_canvas.yview(*args)
        self._queue_render()

    def _scroll_horizontal(self, *args):
        self.cards_canvas.xview(*args)
        self.details_header.xview(*args)

    def _view_changed(self, event=None):
        mode = next((key for key, label in VIEW_MODES.items() if label == self.view_choice.get()), 'cards')
        self.set_view_mode(mode)

    def set_view_mode(self, mode):
        if mode not in VIEW_MODES:
            raise ValueError('Visualização desconhecida')
        self.view_mode = mode
        self.view_choice.set(VIEW_MODES[mode])
        if mode == 'details':
            self.details_header.grid()
            self.horizontal_scroll.grid()
        else:
            self.details_header.grid_remove()
            self.horizontal_scroll.grid_remove()
        self._scroll_horizontal('moveto', 0)
        self.cards_canvas.yview_moveto(0)
        if not self.selected_pairs:
            self._rebuild_basket()
        self._queue_render()

    def _metrics(self, shape):
        key = str(shape['id'])
        if key not in self._metrics_cache:
            self._metrics_cache[key] = shape_metrics(shape)
        return self._metrics_cache[key]

    def _shape_status(self, key):
        if key in self.existing_ids:
            return 'Já na sessão'
        if key not in self._valid_ids:
            return 'Sem contorno válido'
        return 'Selecionado' if key in self.selected_pairs else 'Disponível'

    def _sort_filtered(self):
        if self._sort_column:
            self.filtered_shapes.sort(key=lambda shape: sort_value(
                shape, self._sort_column, self._metrics(shape) if self._sort_column in ('width', 'height', 'area') else None,
                self._shape_status(str(shape['id']))), reverse=self._sort_reverse)

    def sort_details(self, column):
        if column not in {key for key, title, width, anchor in DETAIL_COLUMNS}:
            return
        self._sort_reverse = not self._sort_reverse if self._sort_column == column else False
        self._sort_column = column
        self._sort_filtered()
        self.cards_canvas.yview_moveto(0)
        self._queue_render()

    def _detail_columns(self):
        x = self.u(36)
        factor = (self._table_width()-x)/self.u(sum(column[2] for column in DETAIL_COLUMNS))
        result = []
        for index, (key, title, width, anchor) in enumerate(DETAIL_COLUMNS):
            column_width = round(self.u(width)*factor) if index < len(DETAIL_COLUMNS)-1 else self._table_width()-x
            result.append((key, title, x, column_width, anchor))
            x += column_width
        return result

    def _table_width(self):
        return max(self.cards_canvas.winfo_width(), self.u(850))

    def _header_clicked(self, event):
        x = self.details_header.canvasx(event.x)
        for key, title, left, width, anchor in self._detail_columns():
            if left <= x < left+width:
                self.sort_details(key)
                return

    def _wheel_cards(self, event):
        self._scroll_cards('scroll', -max(1, abs(event.delta)//120) if event.delta > 0 else max(1, abs(event.delta)//120), 'units')
        return 'break'

    def _wheel_basket(self, event):
        self.basket_canvas.yview_scroll(-2 if event.delta > 0 else 2, 'units')
        return 'break'

    def _card_layout(self):
        width = self.cards_canvas.winfo_width()
        if self.view_mode == 'details':
            return 1, self._table_width(), self.u(38), 0
        if self.view_mode == 'list':
            gap = self.u(6)
            return 1, max(self.u(100), width-2*gap), self.u(96), gap
        gap = self.u(12)
        columns = max(1, (width-gap)//self.u(155 if self.view_mode == 'compact' else 235))
        card_width = max(self.u(100), (width-gap*(columns+1))/columns)
        return columns, card_width, self.u(172 if self.view_mode == 'compact' else 218), gap

    def _render_cards(self):
        self._render_job = None
        if self._sort_column == 'status':
            self._sort_filtered()
        cv = self.cards_canvas
        if cv.winfo_width() <= 1:
            return
        cv.delete('all')
        columns, card_width, height, gap = self._card_layout()
        self._card_columns = columns
        rows = math.ceil(len(self.filtered_shapes)/columns)
        total_height = rows*(height+gap)+gap
        canvas_width = max(cv.winfo_width(), card_width+2*gap)
        cv.config(scrollregion=(0, 0, canvas_width, total_height), yscrollincrement=self.u(25))
        if self.view_mode == 'details':
            self._draw_details_header(canvas_width)
        if not self.filtered_shapes:
            cv.create_text(cv.winfo_width()/2, self.u(80), text='Nenhum molde encontrado.\nLimpe os filtros ou importe moldes pelo menu Arquivo.',
                           width=max(100, cv.winfo_width()-30), justify='center', fill=MUTED, font=('Segoe UI', 11))
            return
        start = max(0, int(cv.canvasy(0)//(height+gap))-1)
        end = min(rows, int(cv.canvasy(cv.winfo_height())//(height+gap))+2)
        for row in range(start, end):
            for col in range(columns):
                index = row*columns+col
                if index >= len(self.filtered_shapes):
                    break
                shape = self.filtered_shapes[index]
                x, y = gap+col*(card_width+gap), gap+row*(height+gap)
                if self.view_mode == 'details':
                    self._draw_detail_row(shape, x, y, card_width, height, index)
                elif self.view_mode == 'list':
                    self._draw_list_row(shape, x, y, card_width, height)
                else:
                    self._draw_card(shape, x, y, card_width, height)

    def _draw_check(self, x, y, key):
        cv = self.cards_canvas
        selected = key in self.selected_pairs
        size = self.u(17)
        cv.create_rectangle(x, y, x+size, y+size, fill=BLUE if selected else WHITE,
                            outline=BLUE if selected else '#94a3b8', width=1)
        if selected:
            cv.create_line(x+self.u(4), y+self.u(9), x+self.u(7), y+self.u(12),
                           x+self.u(14), y+self.u(5), fill=WHITE, width=2)

    def _draw_list_row(self, shape, x, y, width, height):
        cv = self.cards_canvas
        key = str(shape['id'])
        selected = key in self.selected_pairs
        color = BLUE if selected else '#94a3b8' if key == self.focused_id else BORDER
        cv.create_rectangle(x, y, x+width, y+height, fill='#eff6ff' if selected else WHITE, outline=color)
        self._draw_check(x+self.u(10), y+(height-self.u(17))/2, key)
        box = (x+self.u(39), y+self.u(8), x+self.u(113), y+height-self.u(8))
        cv.create_rectangle(*box, fill='#f5f9ff', outline='#e1eaf6')
        points = contour_points(shape)
        if points:
            self._draw_preview(shape, points, (box[0]+5, box[1]+5, box[2]-5, box[3]-5))
        text_x = x+self.u(125)
        text_width = max(20, width-self.u(137))
        status = self._shape_status(key)
        cv.create_text(text_x, y+self.u(18), text=self._shorten(shape.get('name') or 'Molde', text_width),
                       anchor='w', font=('Segoe UI', 10, 'bold'), fill=INK)
        metrics = self._metrics(shape)
        dimensions = f'{metrics[0]:.0f} × {metrics[1]:.0f} mm' if metrics else 'Sem medidas'
        for offset, text in ((40, f"Tamanho {shape.get('size') or '—'} · {dimensions}"),
                             (60, shape_folder(shape) or 'Sem pasta'), (80, status)):
            cv.create_text(text_x, y+self.u(offset), text=self._shorten(text, text_width, ('Segoe UI', 9)),
                           anchor='w', font=('Segoe UI', 9), fill=BLUE if offset == 80 and selected else MUTED)

    def _draw_details_header(self, width):
        cv = self.details_header
        cv.delete('all')
        height = self.u(34)
        cv.config(scrollregion=(0, 0, width, height))
        cv.create_rectangle(0, 0, width, height, fill='#eaf0f9', outline=BORDER)
        cv.create_text(self.u(18), height/2, text='✓', fill=INK, font=('Segoe UI', 9, 'bold'))
        for key, title, left, column_width, anchor in self._detail_columns():
            title = {'width': 'Largura\n(mm)', 'height': 'Altura\n(mm)',
                     'area': 'Área externa\n(cm²)'}.get(key, title)
            if key == self._sort_column:
                title += ' ▼' if self._sort_reverse else ' ▲'
            title = '\n'.join(self._shorten(line, column_width-self.u(15), ('Segoe UI', 9, 'bold'))
                              for line in title.splitlines())
            cv.create_line(left, 0, left, height, fill=BORDER)
            cv.create_text(left+self.u(8), height/2, text=title, justify='left',
                           anchor='w', font=('Segoe UI', 9, 'bold'), fill=INK)
        cv.xview_moveto(self.cards_canvas.xview()[0])

    def _draw_detail_row(self, shape, x, y, width, height, index):
        cv = self.cards_canvas
        key = str(shape['id'])
        selected = key in self.selected_pairs
        bg = '#dbeafe' if selected else WHITE if index % 2 == 0 else '#f7f9fc'
        cv.create_rectangle(x, y, x+width, y+height, fill=bg,
                            outline=BLUE if key == self.focused_id else '#e9eef5')
        self._draw_check(self.u(10), y+(height-self.u(17))/2, key)
        metrics = self._metrics(shape)
        values = {'name': shape.get('name') or 'Molde', 'size': shape.get('size') or '—',
                  'folder': shape_folder(shape) or 'Sem pasta', 'status': self._shape_status(key)}
        for position, name in enumerate(('width', 'height', 'area')):
            values[name] = f'{metrics[position]:.{2 if name == "area" else 1}f}'.replace('.', ',') if metrics else '—'
        for name, title, left, column_width, anchor in self._detail_columns():
            text_x = left+column_width-self.u(8) if anchor == 'e' else left+self.u(8)
            color = BLUE if name == 'status' and selected else INK if name == 'name' else '#475569'
            cv.create_text(text_x, y+height/2, text=self._shorten(values[name], column_width-self.u(15), ('Segoe UI', 9)),
                           anchor=anchor, font=('Segoe UI', 9), fill=color)

    def _draw_card(self, shape, x, y, width, height):
        cv = self.cards_canvas
        key = str(shape['id'])
        selected = key in self.selected_pairs
        points = contour_points(shape)
        color = BLUE if selected else '#94a3b8' if key == self.focused_id else BORDER
        cv.create_rectangle(x, y, x+width, y+height, fill=WHITE, outline=color, width=2 if selected else 1)
        preview_bottom = y+height-self.u(65)
        cv.create_rectangle(x+2, y+2, x+width-2, preview_bottom, fill='#f5f9ff', outline='')
        for grid_x in range(round(x+self.u(16)), round(x+width), self.u(16)):
            cv.create_line(grid_x, y+2, grid_x, preview_bottom, fill='#e7eef8')
        for grid_y in range(round(y+self.u(16)), round(preview_bottom), self.u(16)):
            cv.create_line(x+2, grid_y, x+width-2, grid_y, fill='#e7eef8')
        if points:
            self._draw_preview(shape, points, (x+self.u(14), y+self.u(33), x+width-self.u(14), preview_bottom-self.u(10)))
        else:
            cv.create_text(x+width/2, y+self.u(85), text='Sem contorno válido', width=width-20,
                           fill=MUTED, font=('Segoe UI', 9))
        box_x, box_y, box_size = x+self.u(10), y+self.u(10), self.u(17)
        cv.create_rectangle(box_x, box_y, box_x+box_size, box_y+box_size,
                            fill=BLUE if selected else WHITE, outline=BLUE if selected else '#94a3b8', width=1)
        if selected:
            cv.create_line(box_x+self.u(4), box_y+self.u(9), box_x+self.u(7), box_y+self.u(12),
                           box_x+self.u(14), box_y+self.u(5), fill=WHITE, width=2)
        if key in self.existing_ids:
            badge_w = self.u(86)
            cv.create_rectangle(x+width-badge_w-5, y+8, x+width-5, y+self.u(29), fill='#e2e8f0', outline='')
            cv.create_text(x+width-badge_w/2-5, y+self.u(18), text='Já na sessão', fill='#475569', font=('Segoe UI', 8))
        cv.create_text(x+self.u(10), preview_bottom+self.u(15), text=self._shorten(shape.get('name') or 'Molde', width-self.u(20)),
                       fill=INK, font=('Segoe UI', 10, 'bold'), anchor='w')
        cv.create_text(x+self.u(10), preview_bottom+self.u(35), text=f"Tamanho {shape.get('size') or '—'}",
                       fill='#475569', font=('Segoe UI', 9), anchor='w')
        if points:
            w = max(p[0] for p in points)-min(p[0] for p in points)
            h = max(p[1] for p in points)-min(p[1] for p in points)
            cv.create_text(x+self.u(10), preview_bottom+self.u(51), text=f'{w:.0f} × {h:.0f} mm',
                           fill=MUTED, font=('Segoe UI', 8), anchor='w')

    def _draw_preview(self, shape, points, box):
        x1, y1, x2, y2 = box
        low_x, low_y = min(p[0] for p in points), min(p[1] for p in points)
        high_x, high_y = max(p[0] for p in points), max(p[1] for p in points)
        scale = min((x2-x1)/max(high_x-low_x, 1), (y2-y1)/max(high_y-low_y, 1))
        off_x = (x1+x2-(high_x-low_x)*scale)/2
        off_y = (y1+y2-(high_y-low_y)*scale)/2
        def screen(x, y):
            if not math.isfinite(float(x)) or not math.isfinite(float(y)):
                raise ValueError('Coordenada inválida')
            return off_x+(float(x)-low_x)*scale, off_y+(float(y)-low_y)*scale
        vertices = [coord for x, y in points for coord in screen(x, y)]
        self.cards_canvas.create_polygon(vertices, fill='#dbeafe', outline='#1e3a5f', width=1.5)
        for line in shape.get('stitching') or []:
            try:
                vertices = [coord for p in line for coord in screen(p['x'], p['y'])]
                if len(vertices) >= 4:
                    self.cards_canvas.create_line(vertices, fill='#475569', width=1, dash=(4, 3))
            except (KeyError, TypeError, ValueError):
                continue
        for hole in shape.get('holes') or []:
            try:
                x, y = screen(hole['x'], hole['y'])
                radius = max(1.5, min(self.u(5), float(hole.get('r', 1))*scale))
                self.cards_canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill=WHITE, outline='#334155')
            except (KeyError, TypeError, ValueError):
                continue

    def _shorten(self, text, width, font=None):
        font = tkfont.Font(self, font=font or ('Segoe UI', 10, 'bold'))
        text = str(text)
        if font.measure(text) <= width:
            return text
        while text and font.measure(text+'…') > width:
            text = text[:-1]
        return text+'…'

    def _card_clicked(self, event):
        cv = self.cards_canvas
        columns, width, height, gap = self._card_layout()
        x, y = cv.canvasx(event.x)-gap, cv.canvasy(event.y)-gap
        if x < 0 or y < 0:
            return
        col, row = int(x//(width+gap)), int(y//(height+gap))
        index = row*columns+col
        if col >= columns or index >= len(self.filtered_shapes) or x%(width+gap) > width or y%(height+gap) > height:
            return
        self.cards_canvas.focus_set()
        self.toggle_shape(str(self.filtered_shapes[index]['id']))

    def toggle_shape(self, key):
        if key is None or self._adding:
            return
        key = str(key)
        shape = self.shapes_by_id.get(key)
        if not shape:
            return
        self.focused_id = key
        self.edit_button.config(state='normal')
        if key in self.selected_pairs:
            del self.selected_pairs[key]
        elif key in self.existing_ids:
            self._set_status('Este molde já está na sessão. Sua quantidade atual será preservada.')
        elif key not in self._valid_ids:
            self._set_status('Este molde precisa de um contorno válido. Use Editar molde para conferir.', error=True)
        else:
            try:
                self.selected_pairs[key] = str(validate_pairs(self.default_pairs.get()))
            except ValueError as exc:
                self._set_status(str(exc), error=True)
        self._rebuild_basket()
        self._queue_render()

    def _select_all_key(self, event):
        self.select_all_var.set(True)
        self.toggle_all_visible()
        return 'break'

    def toggle_all_visible(self):
        if self._adding:
            return
        try:
            pairs = str(validate_pairs(self.default_pairs.get()))
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        for shape in self.filtered_shapes:
            key = str(shape['id'])
            if self.select_all_var.get():
                if key not in self.existing_ids and key in self._valid_ids:
                    self.selected_pairs.setdefault(key, pairs)
            else:
                self.selected_pairs.pop(key, None)
        self._rebuild_basket()
        self._queue_render()

    def _navigate(self, dx, dy):
        if not self.filtered_shapes:
            return 'break'
        ids = [str(shape['id']) for shape in self.filtered_shapes]
        columns, _, height, gap = self._card_layout()
        index = ids.index(self.focused_id) if self.focused_id in ids else 0
        index = max(0, min(len(ids)-1, index+dx+dy*columns))
        self.focused_id = ids[index]
        y = (index//columns)*(height+gap)
        total = max(1, math.ceil(len(ids)/columns)*(height+gap)+gap)
        top = self.cards_canvas.canvasy(0)
        if y < top or y+height > top+self.cards_canvas.winfo_height():
            self.cards_canvas.yview_moveto(y/total)
        self.edit_button.config(state='normal')
        self._queue_render()
        return 'break'

    def edit_focused(self):
        shape = self.shapes_by_id.get(str(self.focused_id))
        if shape and str(self.focused_id) in self.filtered_ids and self.on_edit_shape_cb and not self._adding:
            self.on_edit_shape_cb(shape['id'])

    def clear_selection(self):
        if not self._adding:
            self.selected_pairs.clear()
            self._rebuild_basket()
            self._queue_render()

    def _remove_selection(self, key):
        if not self._adding:
            self.selected_pairs.pop(key, None)
            self._rebuild_basket()
            self._queue_render()

    def _change_page(self, direction):
        self._basket_page += direction
        self._rebuild_basket()
        self.basket_canvas.yview_moveto(0)

    def _rebuild_basket(self):
        self._clear_pair_traces()
        for widget in self.basket_rows.winfo_children():
            widget.destroy()
        self._pair_vars.clear()
        self._pair_entries.clear()
        keys = list(self.selected_pairs)
        self._basket_page = max(0, min(self._basket_page, max(0, (len(keys)-1)//12)))
        page = keys[self._basket_page*12:(self._basket_page+1)*12]
        self.selection_label.config(text=f'{len(keys)} moldes selecionados')
        if not keys:
            items = 'linhas' if self.view_mode in ('list', 'details') else 'cartões'
            text = f'Clique nas {items} para selecionar os moldes.' if items == 'linhas' else 'Clique nos cartões para selecionar os moldes.'
            if not self.sessions:
                text = 'Crie uma sessão para começar a adicionar moldes.'
            self._label(self.basket_rows, text, 10, wraplength=self.u(245), justify='left').pack(anchor='w', pady=20)
        for key in page:
            shape = self.shapes_by_id.get(key)
            if not shape:
                continue
            row = tk.Frame(self.basket_rows, bg=WHITE, pady=8)
            row.pack(fill='x')
            row.columnconfigure(0, weight=1)
            name = self._shorten(shape.get('name') or 'Molde', self.u(145), ('Segoe UI', 9))
            label = self._label(row, name, 9, anchor='w')
            label.grid(row=0, column=0, sticky='ew')
            ToolTip(label, f"{shape.get('name')} · Tamanho {shape.get('size') or '—'}")
            self._label(row, 'Já na sessão' if key in self.existing_ids else f"Tamanho {shape.get('size') or '—'} · Pares", 8).grid(row=1, column=0, sticky='w')
            variable = tk.StringVar(self, self.selected_pairs[key])
            self._pair_vars[key] = variable
            def changed(*args, shape_id=key, value=variable):
                self.selected_pairs[shape_id] = value.get()
            self._pair_traces.append((variable, variable.trace_add('write', changed)))
            spinner = ttk.Spinbox(row, from_=1, to=9999, textvariable=variable, width=5, font=('Segoe UI', 10),
                                  state='disabled' if self._adding or key in self.existing_ids else 'normal')
            spinner.grid(row=0, column=1, rowspan=2, padx=4)
            self._pair_entries[key] = spinner
            remove = self._button(row, '', lambda item=key: self._remove_selection(item), 'close')
            remove.grid(row=0, column=2, rowspan=2)
            if self._adding:
                remove.config(state='disabled')
            tk.Frame(self.basket_rows, bg=BORDER, height=1).pack(fill='x')
        self.page_label.config(text=f'{self._basket_page*12+1}–{min(len(keys), (self._basket_page+1)*12)} de {len(keys)}' if keys else '')
        if len(keys) > 12:
            self.page_bar.grid()
        else:
            self.page_bar.grid_remove()
        self.page_prev.config(state='normal' if self._basket_page > 0 and not self._adding else 'disabled')
        self.page_next.config(state='normal' if (self._basket_page+1)*12 < len(keys) and not self._adding else 'disabled')
        self._update_actions()

    def _update_actions(self):
        new_keys = set(self.selected_pairs)-self.existing_ids
        enabled = bool(new_keys) and self.destination_id is not None and not self._session_error and not self._adding
        self.add_button.config(state='normal' if enabled else 'disabled')
        self.clear_selection_button.config(state='disabled' if self._adding or not self.selected_pairs else 'normal')
        self.apply_pairs_button.config(state='disabled' if self._adding or not new_keys else 'normal')
        if hasattr(self, 'new_session_button'):
            self.new_session_button.config(state='disabled' if self._adding else 'normal')
        self.edit_button.config(state='normal' if self.focused_id in self.filtered_ids and not self._adding else 'disabled')
        available = {str(shape['id']) for shape in self.filtered_shapes
                     if str(shape['id']) not in self.existing_ids and str(shape['id']) in self._valid_ids}
        self.select_all_var.set(bool(available) and available.issubset(self.selected_pairs))
        self.select_all_button.config(state='disabled' if self._adding or not self.filtered_shapes else 'normal')

    def apply_pairs(self):
        if self._adding:
            return
        try:
            pairs = str(validate_pairs(self.default_pairs.get()))
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        for key in self.selected_pairs:
            if key not in self.existing_ids:
                self.selected_pairs[key] = pairs
        self._rebuild_basket()
        self._set_status(f'Quantidade de {pairs} pares aplicada aos moldes selecionados disponíveis.')

    def add_to_session(self):
        if self._adding or self._session_error:
            return
        if self.destination_id is None:
            self._set_status('Crie ou escolha uma sessão de destino antes de adicionar.', error=True)
            return
        try:
            selection = []
            for key, value in self.selected_pairs.items():
                if key in self.existing_ids:
                    continue
                try:
                    pairs = validate_pairs(value)
                except ValueError:
                    self._basket_page = list(self.selected_pairs).index(key)//12
                    self._rebuild_basket()
                    self._pair_entries[key].focus_set()
                    self.basket_canvas.yview_moveto(0)
                    name = self.shapes_by_id[key].get('name', 'Molde')
                    raise ValueError(f'{name}: informe uma quantidade de pares entre 1 e 9999.')
                selection.append({'id': key, 'pairs': pairs})
            if not selection:
                raise ValueError('Selecione moldes que ainda não estão na sessão de destino.')
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        self._adding = True
        self._adding_destination = self.destination_id
        self.session_combo.config(state='disabled')
        self._rebuild_basket()
        self._set_status('Adicionando moldes à sessão...')
        if getattr(self.db, '_memory_conn', None) is not None:
            _add_worker(self.db, self.destination_id, selection, self._results)
        else:
            threading.Thread(target=_add_worker, args=(self.db, self.destination_id, selection, self._results), daemon=True).start()
        self._poll_job = self.after(80, self._poll_addition)

    def _poll_addition(self):
        self._poll_job = None
        try:
            success, result = self._results.get_nowait()
        except queue.Empty:
            self._poll_job = self.after(80, self._poll_addition)
            return
        self._adding = False
        self.session_combo.config(state='readonly' if self.sessions else 'disabled')
        if success:
            self.existing_ids = {str(shape['id']) for shape in result.shapes if shape.get('id') is not None}
            if self.on_session_updated_cb:
                try:
                    self.on_session_updated_cb(self._adding_destination, result)
                except Exception:
                    self._set_status('Moldes salvos. Reabra a sessão para atualizar a visualização.', error=True)
                    self._rebuild_basket()
                    self._queue_render()
                    return
            text = f'{result.added} molde(s) adicionado(s) à sessão #{self._adding_destination}.'
            if result.skipped:
                text += f' {result.skipped} já estavam na sessão e foram preservados.'
            self._set_status(text, success=True)
        else:
            self._set_status(str(result), error=True)
        self._rebuild_basket()
        self._queue_render()

    def _set_status(self, text, error=False, success=False):
        self.status.set(text)
        self.status_label.config(fg='#b91c1c' if error else '#0f766e' if success else MUTED)

    def _window_action(self, callback):
        if callback:
            callback()

    def on_close_click(self):
        if self.on_close_cb:
            self.on_close_cb()
        else:
            self.pack_forget()
            self.place_forget()

    def _title_press(self, event):
        self._drag_origin = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())

    def _title_drag(self, event):
        if self.place_info() and hasattr(self, '_drag_origin'):
            x, y, start_x, start_y = self._drag_origin
            self.place_configure(x=max(0, start_x+event.x_root-x), y=max(0, start_y+event.y_root-y), relx=0, rely=0)

    def destroy(self):
        self._destroyed = True
        self._clear_pair_traces()
        for name in ('_filter_job', '_render_job', '_poll_job'):
            job = getattr(self, name, None)
            if job:
                self.after_cancel(job)
                setattr(self, name, None)
        super().destroy()

    def _clear_pair_traces(self):
        for variable, trace in self._pair_traces:
            variable.trace_remove('write', trace)
        self._pair_traces.clear()


def _add_worker(db, session_id, selection, results):
    try:
        results.put((True, add_shapes_to_session(db, session_id, selection)))
    except ValueError as exc:
        results.put((False, exc))
    except Exception:
        results.put((False, ValueError('Não foi possível adicionar os moldes. Confira a conexão com o banco e tente novamente.')))
