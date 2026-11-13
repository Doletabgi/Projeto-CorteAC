"""Prévia das mesmas páginas usadas para impressão e PDF do painel."""
import tkinter as tk
from io import BytesIO
from tkinter import ttk
from PIL import Image
from ui.icon_widgets import IconTtkButton


class ProductionReportPreview(tk.Toplevel):
    def __init__(self, parent, pages, *, on_print, on_save):
        super().__init__(parent)
        self.title('Pré-visualização — Painel de Produção')
        self.geometry('1100x780')
        self.minsize(700, 480)
        self.transient(parent)
        self.pages = pages
        self.page_index = 0
        self.zoom = None
        self._photo = None
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill='x')
        self.previous = IconTtkButton(bar, text='Anterior', icon='left', command=lambda: self.show_page(self.page_index - 1))
        self.previous.pack(side='left')
        self.page_label = ttk.Label(bar, width=19, anchor='center')
        self.page_label.pack(side='left', padx=5)
        self.next = IconTtkButton(bar, text='Próxima', icon='right', command=lambda: self.show_page(self.page_index + 1))
        self.next.pack(side='left')
        ttk.Label(bar, text='Zoom:').pack(side='left', padx=(15, 4))
        self.zoom_choice = ttk.Combobox(bar, state='readonly', width=12, values=('Ajustar página', '75%', '100%', '125%', '150%'))
        self.zoom_choice.set('Ajustar página')
        self.zoom_choice.pack(side='left')
        self.zoom_choice.bind('<<ComboboxSelected>>', self.change_zoom)
        IconTtkButton(bar, text='Fechar', command=self.destroy).pack(side='right')
        IconTtkButton(bar, text='Imprimir...', icon='print', command=on_print).pack(side='right', padx=6)
        IconTtkButton(bar, text='Salvar PDF...', icon='save', command=on_save).pack(side='right')
        area = ttk.Frame(self)
        area.pack(fill='both', expand=True)
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(area, bg='#737780', highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(area, orient='vertical', command=self.canvas.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(area, orient='horizontal', command=self.canvas.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.bind('<Configure>', lambda e: self.redraw())
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        self.canvas.bind('<Button-4>', lambda e: self.canvas.yview_scroll(-1, 'units'))
        self.canvas.bind('<Button-5>', lambda e: self.canvas.yview_scroll(1, 'units'))
        self.bind('<Left>', lambda e: self.show_page(self.page_index - 1))
        self.bind('<Right>', lambda e: self.show_page(self.page_index + 1))
        self.bind('<Escape>', lambda e: self.destroy())
        self.bind('<Destroy>', self._release, add='+')
        self.show_page(0)

    def show_page(self, index):
        if not 0 <= index < len(self.pages):
            return
        self.page_index = index
        self.page_label.config(text=f'Página {index + 1} de {len(self.pages)}')
        self.previous.config(state='normal' if index else 'disabled')
        self.next.config(state='normal' if index + 1 < len(self.pages) else 'disabled')
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.redraw()

    def change_zoom(self, event=None):
        value = self.zoom_choice.get()
        self.zoom = None if value == 'Ajustar página' else int(value.rstrip('%')) / 100
        self.redraw()

    def redraw(self):
        page = self.pages[self.page_index]
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width < 30 or height < 30:
            return
        factor = self.zoom if self.zoom is not None else min((width - 24) / page.width, (height - 24) / page.height)
        size = (max(1, round(page.width * factor)), max(1, round(page.height * factor)))
        scaled = page.resize(size, Image.Resampling.LANCZOS)
        with BytesIO() as buffer:
            scaled.save(buffer, format='PNG')
            self._photo = tk.PhotoImage(data=buffer.getvalue(), master=self)
        scaled.close()
        self.canvas.delete('all')
        x = max(12, (width - size[0]) // 2)
        self.canvas.create_image(x, 12, image=self._photo, anchor='nw')
        self.canvas.configure(scrollregion=(0, 0, max(width, size[0] + 24), max(height, size[1] + 24)))

    def _release(self, event):
        if event.widget is self:
            for page in self.pages:
                page.close()
            self._photo = None
