"""Assistente visual para criar um perfil real de encaixe, com teste isolado."""
import copy
import math
import multiprocessing
import queue
import tkinter as tk
from tkinter import ttk

from cad.nesting_wizard import MATERIALS, GOALS, ROTATIONS, build_profile, validate_gap, preview_worker


BG, INK, MUTED, BLUE = '#f3f6fb', '#172b4d', '#52647b', '#215eea'
STEPS = ('Material', 'Prioridade', 'Rotação', 'Distância', 'Revisão')


class NestingWizard(tk.Toplevel):
    def __init__(self, parent, db, *, context, on_created):
        super().__init__(parent)
        self.title('Criar encaixe com assistente')
        width, height = min(1080, max(980, self.winfo_screenwidth() - 80)), min(720, max(680, self.winfo_screenheight() - 100))
        self.geometry(f'{width}x{height}')
        self.minsize(980, 680)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()
        self.db, self.context, self.on_created = db, copy.deepcopy(context), on_created
        self.step = 0
        self.values = {key: tk.StringVar(self, value) for key, value in {
            'material': 'synthetic', 'goal': 'balanced', 'rotation': 'half',
            'gap': str(context.get('gap', 1.0)), 'name': '',
        }.items()}
        self._process = self._queue = self._poll_job = self._animation_job = None
        self._result = self._saved_profile = None
        self._angle = 0
        self._closed = False
        self._build()
        for key in ('material', 'goal', 'rotation', 'gap'):
            self.values[key].trace_add('write', self._changed)
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.bind('<Escape>', lambda e: self.destroy())
        self.show_step(0)

    def _label(self, parent, text, size=10, color=INK, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color,
                        font=('Segoe UI', size, 'bold' if bold else 'normal'), **kwargs)

    def _button(self, parent, text, command, primary=False, **kwargs):
        return tk.Button(parent, text=text, command=command, cursor='hand2',
                         font=('Segoe UI', 10, 'bold'), relief='flat', bd=0, padx=16, pady=9,
                         bg=BLUE if primary else '#e7edf6', fg='white' if primary else INK,
                         activebackground='#194bc0' if primary else '#dbe5f3',
                         activeforeground='white' if primary else INK, **kwargs)

    def _build(self):
        header = tk.Frame(self, bg='white', padx=24, pady=16)
        header.pack(fill='x')
        self._label(header, 'Vamos criar seu próximo encaixe', 19, bold=True).pack(anchor='w')
        self._label(header, 'Você escolhe como trabalhar. O assistente prepara os parâmetros.', color=MUTED).pack(anchor='w', pady=(5, 0))
        footer = tk.Frame(self, bg='white', padx=20, pady=12)
        footer.pack(side='bottom', fill='x')
        self.status = self._label(footer, '', 9, MUTED, anchor='w', justify='left', wraplength=940)
        self.status.pack(fill='x', pady=(0, 8))
        actions = tk.Frame(footer, bg='white')
        actions.pack(fill='x')
        self._button(actions, 'Cancelar', self.destroy).pack(side='left')
        self.back_button = self._button(actions, 'Voltar', lambda: self.show_step(self.step - 1))
        self.back_button.pack(side='left', padx=8)
        self.next_button = self._button(actions, 'Continuar →', lambda: self.show_step(self.step + 1), True)
        self.next_button.pack(side='right')
        self.save_button = self._button(actions, 'Só salvar perfil', lambda: self.finish(False))
        self.apply_button = self._button(actions, 'Salvar e usar na sessão', lambda: self.finish(True), True)

        body = tk.Frame(self, bg=BG, padx=16, pady=16)
        body.pack(fill='both', expand=True)
        rail = tk.Frame(body, bg=BG, width=150)
        rail.pack(side='left', fill='y', padx=(0, 14))
        rail.pack_propagate(False)
        self.step_buttons = []
        for index, label in enumerate(STEPS):
            button = tk.Button(rail, text=f'{index + 1:02d}   {label}', anchor='w', relief='flat',
                               font=('Segoe UI', 11), padx=12, pady=12, cursor='hand2',
                               command=lambda i=index: self.show_step(i))
            button.pack(fill='x', pady=3)
            self.step_buttons.append(button)
        self._label(rail, 'PASSO A PASSO\n\nSuas escolhas podem\nser revistas antes\nde salvar.', 9, MUTED, justify='left').pack(anchor='w', pady=24)

        right = tk.Frame(body, bg='white', width=330, padx=16, pady=16)
        right.pack(side='right', fill='y', padx=(14, 0))
        right.pack_propagate(False)
        self._label(right, 'Suas escolhas ganham forma', 11, bold=True).pack(anchor='w')
        self.preview_caption = self._label(right, 'Ilustração das opções', 9, MUTED, wraplength=290, justify='left')
        self.preview_caption.pack(anchor='w', pady=(6, 8))
        self.canvas = tk.Canvas(right, bg='#eef3fb', height=230, highlightthickness=0)
        self.canvas.bind('<Configure>', lambda e: self.draw_preview())
        self.choice_summary = self._label(right, '', 10, MUTED, justify='left', anchor='nw', wraplength=290)
        self.test_button = self._button(right, 'Testar na sessão atual', self.run_preview)
        self.progress = ttk.Progressbar(right, mode='indeterminate')
        self.test_status = self._label(right, '', 9, MUTED, justify='left', wraplength=290)
        self.test_status.pack(side='bottom', fill='x', pady=4)
        self.test_button.pack(side='bottom', fill='x', pady=(4, 6))
        self.choice_summary.pack(side='bottom', fill='x', pady=12)
        self.canvas.pack(fill='both', expand=True)
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side='left', fill='both', expand=True)

    def _picked(self, key):
        if key == 'material':
            self.values['rotation'].set(MATERIALS[self.values['material'].get()][1])

    def _card(self, parent, key, value, title, description, row, column=0):
        card = tk.Radiobutton(
            parent, text=f'{title}\n{description}', variable=self.values[key], value=value,
            command=lambda: self._picked(key), indicatoron=False, anchor='w', justify='left',
            font=('Segoe UI', 10), bg='white', fg=INK, selectcolor='#dce8ff',
            activebackground='#e8f0ff', relief='flat', bd=1, padx=14, pady=14,
            highlightthickness=1, highlightbackground='#d4deed', cursor='hand2',
            wraplength=350,
        )
        card.grid(row=row, column=column, sticky='ew', pady=5)
        parent.columnconfigure(column, weight=1)
        return card

    def show_step(self, index):
        if not 0 <= index < len(STEPS):
            return
        if index >= 4:
            try:
                validate_gap(self.values['gap'].get())
            except ValueError as exc:
                self.status.config(text=str(exc), fg='#b42318')
                return
        self._stop_process()
        self._stop_animation()
        self.step = index
        self.status.config(text=f'Etapa {index + 1} de 5 · {STEPS[index]}', fg=MUTED)
        for i, button in enumerate(self.step_buttons):
            button.config(bg='#dce8ff' if i == index else BG,
                          fg=BLUE if i == index else MUTED,
                          text=f'{"✓" if i < index else f"{i + 1:02d}"}   {STEPS[i]}')
        for child in self.content.winfo_children():
            child.destroy()
        self.back_button.config(state='normal' if index else 'disabled')
        for button in (self.next_button, self.save_button, self.apply_button):
            button.pack_forget()
        if index == 4:
            if self.context.get('can_apply'):
                self.apply_button.pack(side='right')
                self.save_button.pack(side='right', padx=8)
            else:
                self.save_button.pack(side='right')
        else:
            self.next_button.pack(side='right')
        getattr(self, f'_step_{index}')()
        self.draw_preview()
        if index == 2:
            self._animate()
        self._update_test_button()

    def _heading(self, title, subtitle):
        self._label(self.content, title, 16, bold=True, anchor='w', justify='left', wraplength=390).pack(fill='x', pady=(4, 7))
        self._label(self.content, subtitle, 10, MUTED, justify='left', anchor='w', wraplength=390).pack(fill='x', pady=(0, 12))

    def _step_0(self):
        self._heading('Qual material você vai cortar?', 'O tipo de material ajuda a sugerir os giros. Confirme sempre o sentido da fibra ou da estampa.')
        cards = tk.Frame(self.content, bg=BG)
        cards.pack(fill='x')
        for row, (value, title, note) in enumerate((
            ('synthetic', 'Sintético', 'Chapas e materiais sintéticos.'),
            ('fabric', 'Tecido', 'Atenção ao sentido do fio e da estampa.'),
            ('leather', 'Couro', 'Confirme a direção e a área útil da chapa.'),
            ('other', 'Outro material', 'Você define os giros na próxima etapa.'),
        )):
            self._card(cards, 'material', value, title, note, row)

    def _step_1(self):
        self._heading('O que importa mais agora?', 'A prioridade muda a busca e a organização das fileiras. O resultado depende dos moldes.')
        cards = tk.Frame(self.content, bg=BG)
        cards.pack(fill='x')
        for row, (value, title, note) in enumerate((
            ('fast', 'Mais rapidez', 'Busca direta, com fileiras regulares.'),
            ('balanced', 'Equilíbrio', 'Intercala as fileiras e busca ajustes moderados.'),
            ('quality', 'Mais aproveitamento', 'Busca ajustes mais finos quando o giro é livre. Pode levar mais tempo.'),
        )):
            self._card(cards, 'goal', value, title, note, row)

    def _step_2(self):
        self._heading('As peças podem girar?', 'Observe o desenho ao lado. Escolha apenas as posições permitidas para seu material.')
        cards = tk.Frame(self.content, bg=BG)
        cards.pack(fill='x')
        for row, (value, title, note) in enumerate((
            ('fixed', '↑ Manter o sentido', 'Somente 0°. Para materiais com direção única.'),
            ('half', '↑ ↓ Permitir inversão', '0° e 180°, sem pequenas inclinações.'),
            ('free', '↻ Girar livremente', 'Giros de 90° e ajustes de até 5°, conforme a prioridade.'),
        )):
            self._card(cards, 'rotation', value, title, note, row)

    def _step_3(self):
        self._heading('Qual espaço deixar entre peças?', 'Arraste o controle para ver a distância. Ao usar o perfil, este valor será aplicado à sessão.')
        panel = tk.Frame(self.content, bg='white', padx=16, pady=20)
        panel.pack(fill='x')
        self._label(panel, 'Distância entre peças', 11, bold=True).pack(anchor='w')
        row = tk.Frame(panel, bg='white')
        row.pack(fill='x', pady=16)
        self.gap_entry = tk.Entry(row, textvariable=self.values['gap'], font=('Segoe UI', 22), width=6,
                                  bg='#eef3fb', fg=INK, relief='flat', justify='center')
        self.gap_entry.pack(side='left')
        self._label(row, 'mm', 14, MUTED).pack(side='left', padx=8)
        try:
            initial_gap = validate_gap(self.values['gap'].get())
        except ValueError:
            initial_gap = 1.
        self._scale_value = tk.DoubleVar(self, min(10., initial_gap))
        self.gap_scale = tk.Scale(panel, from_=0, to=10, resolution=.1, orient='horizontal',
                                  variable=self._scale_value, command=self._scale_changed,
                                  bg='white', highlightthickness=0, showvalue=False, activebackground=BLUE)
        self.gap_scale.pack(fill='x')
        self._label(panel, '0 mm                                      10 mm', 9, MUTED).pack(fill='x')
        self._label(self.content, 'Também é possível digitar valores de até 50 mm.\nUse a distância adequada à ferramenta e ao material.', 10, MUTED,
                    justify='left', wraplength=390).pack(anchor='w', pady=18)

    def _step_4(self):
        self._heading('Seu perfil está pronto para revisar', 'Confira as escolhas, dê um nome e teste o encaixe antes de salvar.')
        if not self.values['name'].get():
            self.values['name'].set(f"{MATERIALS[self.values['material'].get()][0]} - {GOALS[self.values['goal'].get()]}")
        self._label(self.content, 'Nome da configuração', 10, bold=True).pack(anchor='w')
        self.name_entry = tk.Entry(self.content, textvariable=self.values['name'], font=('Segoe UI', 12),
                                   relief='solid', bd=1, bg='white', fg=INK)
        self.name_entry.pack(fill='x', ipady=9, pady=(7, 14))
        panel = tk.Frame(self.content, bg='white', padx=16, pady=14)
        panel.pack(fill='x')
        self.review_value_labels = []
        for label, value in self._summary_rows():
            self._label(panel, label.upper(), 8, MUTED).pack(anchor='w', pady=(5, 0))
            item = self._label(panel, value, 11, bold=True, wraplength=350, justify='left')
            item.pack(anchor='w', pady=(2, 5))
            self.review_value_labels.append(item)
        name = self.context.get('session_name')
        note = f'Sessão de destino: {name}\nO perfil usa o modo Personalizado em chapas.' if name else 'O perfil ficará disponível no DieProc para usar em uma sessão.'
        self._label(self.content, note, 9, MUTED, justify='left', wraplength=390).pack(anchor='w', pady=12)

    def _summary_rows(self):
        try:
            gap = f"{validate_gap(self.values['gap'].get()):.1f}".replace('.', ',') + ' mm'
        except ValueError:
            gap = 'Informe a distância'
        return [('Material de referência', MATERIALS[self.values['material'].get()][0]),
                ('Prioridade', GOALS[self.values['goal'].get()]),
                ('Rotação', ROTATIONS[self.values['rotation'].get()][0]), ('Distância', gap)]

    def _scale_changed(self, value):
        self.values['gap'].set(f'{float(value):.1f}')

    def _changed(self, *args):
        if self._closed:
            return
        self._stop_process()
        self._result = None
        self.test_status.config(text='')
        if self.step == 4 and hasattr(self, 'review_value_labels'):
            for label, (_, value) in zip(self.review_value_labels, self._summary_rows()):
                label.config(text=value)
        self.draw_preview()

    def _stop_animation(self):
        if self._animation_job is not None:
            self.after_cancel(self._animation_job)
            self._animation_job = None

    def _animate(self):
        self._angle += 1
        self.draw_preview()
        self._animation_job = self.after(850, self._animate)

    def draw_preview(self):
        cv = self.canvas
        cv.delete('all')
        w, h = max(280, cv.winfo_width()), max(80, cv.winfo_height())
        self.choice_summary.config(text='\n'.join(f'{key}: {value}' for key, value in self._summary_rows()))
        if self._result is not None:
            job = self.context['job']
            scale = min((w - 24) / job['width'], (h - 24) / job['height'])
            ox, oy = (w - job['width'] * scale) / 2, (h - job['height'] * scale) / 2
            cv.create_rectangle(ox, oy, ox + job['width'] * scale, oy + job['height'] * scale, fill='white', outline='#9fb3d5')
            for piece in self._result['pieces']:
                points = piece.get('poly') or []
                if points:
                    points = [(point['x'], point['y']) if isinstance(point, dict) else point for point in points]
                    cv.create_polygon([v for x, y in points for v in (ox + x * scale, oy + (job['height'] - y) * scale)], fill='#b5d1ff', outline=BLUE, tags='preview_piece')
            return
        self.preview_caption.config(text='Ilustração das opções · não é uma simulação')
        if self.step == 3:
            try:
                gap = validate_gap(self.values['gap'].get())
            except ValueError:
                gap = 0.
            distance = min(90, 8 + gap * 8)
            cx = w / 2
            cv.create_rectangle(cx - distance / 2 - 85, 55, cx - distance / 2, 170, fill='#b5d1ff', outline=BLUE, width=2)
            cv.create_rectangle(cx + distance / 2, 55, cx + distance / 2 + 85, 170, fill='#b5d1ff', outline=BLUE, width=2)
            cv.create_line(cx - distance / 2, 195, cx + distance / 2, 195, arrow='both', fill=BLUE, width=2)
            cv.create_text(cx, 212, text=self._summary_rows()[-1][1], fill=INK, font=('Segoe UI', 12, 'bold'))
        else:
            angles = {'fixed': [0], 'half': [0, 180], 'free': [0, 90, 180, 270]}[self.values['rotation'].get()]
            angle = angles[self._angle % len(angles)] if self.step == 2 else angles[0]
            a = math.radians(angle)
            points = [(-45, -62), (12, -62), (12, -8), (45, -8), (45, 62), (-45, 62)]
            cv.create_polygon([v for x, y in points for v in (w / 2 + x * math.cos(a) - y * math.sin(a), 104 + x * math.sin(a) + y * math.cos(a))],
                              fill='#b5d1ff', outline=BLUE, width=2)
            cv.create_text(w / 2, 104, text=f'{angle}°', fill=INK, font=('Segoe UI', 16, 'bold'))
            cv.create_text(w / 2, 205, text='  ·  '.join(f'{value}°' for value in angles), fill=MUTED, font=('Segoe UI', 11))
        scale = min(1., h / 230)
        cv.scale('all', w / 2, 0, scale, scale)
        cv.move('all', 0, (h - 230 * scale) / 2)

    def _update_test_button(self):
        available = bool(self.context.get('job'))
        self.test_button.config(state='normal' if available else 'disabled')
        if not available:
            self.test_status.config(text=self.context.get('test_unavailable', 'Abra uma sessão com material e moldes para testar.'))

    def run_preview(self):
        if self._process is not None:
            self._stop_process()
            self.test_status.config(text='Teste cancelado. A produção foi preservada.')
            return
        if not self.context.get('job'):
            return
        try:
            profile = build_profile('Prévia do assistente', *(self.values[k].get() for k in ('material', 'goal', 'rotation', 'gap')))
        except ValueError as exc:
            self.status.config(text=str(exc), fg='#b42318')
            return
        job = copy.deepcopy(self.context['job'])
        job['profile'] = profile
        self._result = None
        self.draw_preview()
        self._stop_animation()
        ctx = multiprocessing.get_context('spawn')
        self._queue = ctx.Queue()
        self._process = ctx.Process(target=preview_worker, args=(self._queue, job), daemon=True)
        try:
            self._process.start()
        except Exception as exc:
            self._stop_process()
            self.test_status.config(text=f'Não foi possível iniciar o teste: {exc}')
            return
        self.test_button.config(text='Cancelar teste')
        self.progress.pack(side='bottom', fill='x', before=self.test_button)
        self.progress.start(15)
        self.test_status.config(text=f"Calculando uma placa com até {job['limit']} peças…")
        self._poll_job = self.after(100, self._poll)

    def _poll(self):
        self._poll_job = None
        try:
            result = self._queue.get_nowait()
        except queue.Empty:
            if self._process.is_alive():
                self._poll_job = self.after(100, self._poll)
                return
            self._stop_process()
            self.test_status.config(text='O teste foi interrompido. Você pode tentar novamente.')
            return
        self._stop_process()
        if 'error' in result:
            self.test_status.config(text=f"Não foi possível testar: {result['error']}")
            return
        self._result = result
        self.draw_preview()
        self.preview_caption.config(text='Teste real · amostra de uma placa')
        self.test_status.config(text=f"{len(result['pieces'])} peças posicionadas\nAproveitamento: {result['yield_pct']:.1f}%\nAmostra limitada a {self.context['job']['limit']} peças. A sessão não foi alterada.")

    def _stop_process(self):
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        if self._process is not None:
            if self._process.pid is not None:
                if self._process.is_alive():
                    self._process.terminate()
                self._process.join(timeout=.3)
                if self._process.is_alive():
                    self._process.kill()
                    self._process.join(timeout=.3)
            self._process = None
        if self._queue is not None:
            self._queue.cancel_join_thread()
            self._queue.close()
            self._queue = None
        if hasattr(self, 'progress'):
            self.progress.stop()
            self.progress.pack_forget()
            self.test_button.config(text='Testar na sessão atual')

    def finish(self, apply):
        if apply and not self.context.get('can_apply'):
            self.status.config(text='Abra uma sessão para usar a configuração.', fg='#b42318')
            return
        try:
            profile = build_profile(*(self.values[k].get() for k in ('name', 'material', 'goal', 'rotation', 'gap')))
            if self._saved_profile != profile:
                names = self.db.get_dieproc_presets()
                if any(name.casefold() == profile['name'].casefold() for name in names):
                    raise ValueError('Esse nome já existe. Escolha outro nome para criar seu perfil.')
                self.db.save_dieproc_preset(profile)
                self._saved_profile = profile
        except Exception as exc:
            self.status.config(text=str(exc), fg='#b42318')
            return
        try:
            self.on_created(profile, apply)
        except Exception as exc:
            self.status.config(text=f'Perfil salvo, mas não foi possível usá-lo agora: {exc}', fg='#b42318')
            return
        self.destroy()

    def destroy(self):
        if self._closed:
            return
        self._closed = True
        self._stop_process()
        self._stop_animation()
        try:
            super().destroy()
        finally:
            try:
                if self.master.winfo_exists():
                    self.master.grab_set()
            except tk.TclError:
                pass
