"""Composições alternativas da sessão, sem recriar controles ou callbacks."""
import tkinter as tk
from config import THEME
from ui.icon_widgets import IconButton


class SessionLayouts:
    def __init__(self, view):
        self.view = view
        self.name = None
        self.container = view.gen_container
        self.original = [(w, w.pack_info()) for w in
                         (view.mode_widget, view.box_advanced, view.macro_panel,
                          view.action_box, view.info_frame)]
        self.original_columns = [(w, w.pack_info()) for w in
                                 (view.cut_controls, view.material_controls)]
        self.viewport = tk.Canvas(view.tab_gen, highlightthickness=0, bg=THEME['bg_card'])
        self.viewport_bar = tk.Scrollbar(view.tab_gen, command=self.viewport.yview)
        self.viewport.configure(yscrollcommand=self.viewport_bar.set)
        self.viewport_window = None
        self.viewport.bind('<Configure>', self._sync_viewport)
        self.container.bind('<Configure>', self._sync_viewport, add='+')
        self.compacted = []
        self.labels = []
        self.body = tk.Frame(self.container, bg=THEME['bg_card'])
        self.material = tk.LabelFrame(self.container, text='Material e segurança',
                                     bg=THEME['bg_card'], fg=THEME['text_main'],
                                     padx=10, pady=8, font=('Segoe UI', 9, 'bold'))
        self.preview_box = tk.LabelFrame(self.body, text='Prévia do encaixe',
                                        bg=THEME['bg_card'], fg=THEME['text_main'])
        toolbar = tk.Frame(self.preview_box, bg=THEME['bg_card'])
        toolbar.pack(fill='x')
        IconButton(toolbar, text='✏ Abrir no Layout Editor',
                   command=view.on_layout_row_double_click).pack(side='right')
        self.preview = tk.Canvas(self.preview_box, bg=THEME['canvas_bg'],
                                 highlightthickness=0, width=240, height=220)
        self.preview.pack(fill='both', expand=True)
        self.preview.bind('<Configure>', lambda e: view.draw_mini_layout_preview(self.preview))
        self.preview.bind('<Double-1>', view.on_layout_row_double_click)
        self.sidebar = tk.Frame(self.body, bg=THEME['bg_card'])
        self.scroll = tk.Canvas(self.sidebar, width=460, highlightthickness=0,
                                bg=THEME['bg_card'])
        bar = tk.Scrollbar(self.sidebar, orient='vertical', command=self.scroll.yview)
        bar.pack(side='right', fill='y')
        self.scroll.pack(side='left', fill='both', expand=True)
        self.scroll.configure(yscrollcommand=bar.set)
        self.inspector = tk.Frame(self.scroll, bg=THEME['bg_card'])
        self.window = self.scroll.create_window(0, 0, window=self.inspector, anchor='nw')
        self.inspector.bind('<Configure>', lambda e: self.scroll.configure(scrollregion=self.scroll.bbox('all')))
        self.scroll.bind('<Configure>', lambda e: self.scroll.itemconfigure(self.window, width=e.width))
        # Rolagem restrita ao inspetor: não interfere com zoom dos canvases CAD.
        self._bind_wheel()
        self.container.bind('<Configure>', self._resize, add='+')
        self.wide = None

    def _sync_viewport(self, event=None):
        if self.viewport_window is not None:
            width = max(1, self.viewport.winfo_width())
            height = max(self.container.winfo_reqheight(), self.viewport.winfo_height())
            self.viewport.itemconfigure(self.viewport_window, width=width, height=height)
            self.viewport.configure(scrollregion=(0, 0, width, height))

    def _set_viewport(self, enabled):
        if enabled and self.viewport_window is None:
            self.container.pack_forget()
            self.viewport_bar.pack(side='right', fill='y')
            self.viewport.pack(fill='both', expand=True)
            self.viewport_window = self.viewport.create_window(0, 0, window=self.container, anchor='nw')
        elif not enabled and self.viewport_window is not None:
            self.viewport.delete(self.viewport_window)
            self.viewport_window = None
            self.viewport.pack_forget()
            self.viewport_bar.pack_forget()
            self.container.pack(fill='both', expand=True)

    def _bind_wheel(self):
        groups = (self.viewport, self.container, self.view.mode_widget,
                  self.view.cut_controls, self.view.material_controls,
                  self.view.macro_panel)
        widgets = {widget for group in groups for widget in self._descendants(group)}
        for widget in widgets:
            # Menus de combobox e editores mantêm seus próprios eventos.
            if widget.winfo_class() not in ('TCombobox', 'Entry', 'Spinbox'):
                widget.bind('<MouseWheel>', self._wheel)
                widget.bind('<Button-4>', self._wheel)
                widget.bind('<Button-5>', self._wheel)

    def _wheel(self, event):
        if self.name not in ("modern", "technical", "compact"):
            return
        amount = -1 if getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0 else 1
        target = self.scroll if self.name == "technical" else self.viewport
        target.yview_scroll(amount, 'units')
        return 'break'

    def _descendants(self, widget):
        yield widget
        for child in widget.winfo_children():
            yield from self._descendants(child)

    def _resize(self, event):
        wide = event.width >= 1250
        if self.name in ('modern', 'compact') and wide != self.wide:
            self.apply(self.name, force=True)

    def _restore(self):
        for widget, options in self.compacted:
            widget.pack_forget()
            widget.pack(**options)
            if hasattr(widget, '_layout_anchor'):
                widget.configure(anchor=widget._layout_anchor)
        self.compacted.clear()
        for widget, wrap in self.labels:
            widget.configure(wraplength=wrap)
        self.labels.clear()
        for widget in (self.body, self.material, self.preview_box, self.sidebar,
                       *(w for w, _ in self.original), self.view.cut_controls,
                       self.view.material_controls):
            widget.pack_forget()
            widget.grid_forget()
        for column in range(3):
            self.body.grid_columnconfigure(column, weight=0, minsize=0)
            self.container.grid_columnconfigure(column, weight=0)
        for row in range(6):
            self.container.grid_rowconfigure(row, weight=0)
        for widget, options in self.original_columns:
            widget.pack(**options)
        self.view.box_advanced.configure(text='Avançado (Parâmetros de Corte)')

    def _stack_controls(self, frame):
        for widget in frame.pack_slaves():
            info = widget.pack_info()
            self.compacted.append((widget, info))
            widget.pack_configure(side='top', fill='x', anchor='w', padx=0, pady=2)
            if isinstance(widget, tk.Checkbutton):
                if not hasattr(widget, '_layout_anchor'):
                    widget._layout_anchor = widget.cget('anchor')
                widget.configure(anchor='w')

    def apply(self, name, force=False):
        if self.name == name and not force:
            return
        self._restore()
        self.name = name
        self._set_viewport(name in ("modern", "compact"))
        self.wide = self.container.winfo_width() >= 1250
        view = self.view
        if name not in ('modern', 'technical', 'compact'):
            for widget, options in self.original:
                widget.pack(**options)
            return
        for frame in (view.box_advanced, self.material, view.cut_controls, view.material_controls, view.macro_panel):
            for widget in self._descendants(frame):
                widget._layout_card = True
                if isinstance(widget, tk.Label):
                    self.labels.append((widget, widget.cget('wraplength')))
                    widget.configure(wraplength=320 if name == 'technical' else 390,
                                     justify='left')
        self._stack_controls(view.frame_checks)
        if name in ('technical', 'compact'):
            for row in view.macro_panel.winfo_children():
                if isinstance(row, tk.Frame):
                    self._stack_controls(row)
        self.container.grid_columnconfigure(0, weight=1)
        view.material_controls.pack_forget()
        view.material_controls.pack(in_=self.material, fill='x', expand=True)
        view.box_advanced.configure(text='Parâmetros de corte')
        if name == "modern":
            self.container.grid_rowconfigure(3, weight=1)
        view.info_frame.grid(row=4, column=0, sticky='ew', pady=6)
        view.action_box.grid(row=5, column=0, sticky='ew', pady=6)
        if name == 'technical':
            self.container.grid_rowconfigure(0, weight=1)
            self.body.grid(row=0, column=0, sticky='nsew')
            self.body.grid_rowconfigure(0, weight=1)
            self.body.grid_columnconfigure(0, weight=1)
            self.preview_box.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
            self.sidebar.grid(row=0, column=1, sticky='nsew')
            for widget in (view.mode_widget, view.box_advanced, self.material, view.macro_panel):
                widget.pack(in_=self.inspector, fill='x', padx=6, pady=6)
        else:
            view.mode_widget.grid(row=0, column=0, sticky='ew', pady=(0, 8))
            self.body.grid(row=1, column=0, sticky='nsew')
            self.body.grid_columnconfigure(0, weight=3)
            self.body.grid_columnconfigure(1, weight=2)
            view.box_advanced.grid(in_=self.body, row=0, column=0, sticky='new', padx=(0, 8))
            self.material.grid(in_=self.body, row=0, column=1, sticky='new')
            if name == 'compact' and self.wide:
                self.body.grid_columnconfigure(2, weight=2)
                view.macro_panel.grid(in_=self.body, row=0, column=2, sticky='new', padx=(8, 0))
            else:
                view.macro_panel.grid(row=2, column=0, sticky='ew', pady=8)
            if name == 'compact':
                self.preview_box.grid(in_=self.body, row=1, column=0, columnspan=3,
                                      sticky='nsew', pady=8)
                self.preview.configure(height=140)
        # Os grupos mantêm o pai original para preservar suas variáveis. Tk exige
        # elevá-los sobre os novos contêineres usados por grid(in_=)/pack(in_=).
        for widget in (view.mode_widget, view.box_advanced, self.material,
                       view.macro_panel, view.info_frame, view.action_box,
                       view.cut_controls, view.material_controls):
            widget.lift()
        self._sync_viewport()
        view.draw_mini_layout_preview(self.preview)
