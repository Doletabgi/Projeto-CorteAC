"""Configuração guiada de banco local ou servidor MySQL."""
from dataclasses import replace
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from config import THEME
from db import config as db_config
from db.connection_settings import (
    ConnectionSettings, ENV_FIELDS, SettingsError, load_settings,
    probe_connection, save_settings, validate_settings,
)
from ui.icon_widgets import IconButton, IconLabel


class DatabaseConnectionDialog(tk.Toplevel):
    def __init__(self, parent, db=None, *, config_path=None, environ=None):
        super().__init__(parent)
        self.withdraw()
        self.title('Conexão com Banco de Dados')
        if parent.winfo_viewable():
            self.transient(parent)
        self.resizable(False, False)
        self.configure(bg=THEME['bg_surface'])
        self.config_path = Path(config_path) if config_path is not None else db_config.INI_FILE
        self.environ = os.environ if environ is None else environ
        self._environment_locked = any(key in self.environ for key in ENV_FIELDS.values())
        self._busy = False
        self._closed = False
        self._poll_job = None
        self._tested_settings = None
        self._results = queue.Queue()
        self._pending_save = False
        self._editable = []
        self.fields = {}
        self._load_error = None
        try:
            self.settings = load_settings(self.config_path, self.environ)
        except SettingsError as exc:
            self._load_error = str(exc)
            self.settings = ConnectionSettings(sqlite_path=str(db_config.APP_DIR / 'jobmanager.db'))
        self.backend = tk.StringVar(self, self.settings.backend)
        self.host = tk.StringVar(self, self.settings.host)
        self.port = tk.StringVar(self, str(self.settings.port))
        self.database = tk.StringVar(self, self.settings.database)
        self.user = tk.StringVar(self, self.settings.user)
        self.password = tk.StringVar(self, self.settings.password)
        self.sqlite_path = tk.StringVar(self, self.settings.sqlite_path)
        self.show_password = tk.BooleanVar(self, False)
        self.show_port = tk.BooleanVar(self, self.settings.port != 3306)
        self.status = tk.StringVar(self, 'Escolha uma opção e clique em Testar conexão.')
        self._build(db)
        self._mode_changed()
        if self._load_error:
            self._set_status(self._load_error, error=True)
            self.test_button.config(state='disabled')
            self.save_button.config(state='disabled')
        elif self._environment_locked:
            self._set_status('Esta instalação recebe configurações externas. Você pode testar; para alterá-las, peça ajuda ao responsável pelo sistema.')
            self.save_button.config(state='disabled')
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.bind('<Escape>', lambda event: self.destroy())
        self.bind('<Return>', lambda event: self.test_connection())
        self.deiconify()
        self.wait_visibility()
        self.grab_set()
        self.focus_set()

    def _build(self, db):
        header = tk.Frame(self, bg='#ffffff', padx=20, pady=16)
        header.pack(fill='x')
        IconLabel(header, icon='materials', text='Onde seus dados serão guardados?',
                  font=('Segoe UI', 14, 'bold'), bg='#ffffff', fg='#172554').pack(anchor='w')
        tk.Label(header, text='Escolha uma opção. O sistema ajuda você a conferir a conexão.',
                 font=('Segoe UI', 9), bg='#ffffff', fg='#475569').pack(anchor='w', pady=(6, 0))
        active = getattr(db, 'backend', self.settings.backend)
        current = 'no servidor da rede' if active == 'mysql' else 'neste computador'
        tk.Label(header, text=f'Em uso agora: {current}', font=('Segoe UI', 9, 'bold'),
                 bg='#ffffff', fg='#0f766e').pack(anchor='w', pady=(10, 0))

        body = tk.Frame(self, bg=THEME['bg_surface'], padx=20, pady=12)
        body.pack(fill='both', expand=True)
        for value, title, help_text in (
            ('sqlite', 'Somente neste computador', 'Para trabalhar aqui, sem precisar de um servidor.'),
            ('mysql', 'Compartilhado na rede (MySQL)', 'Para vários computadores usarem os mesmos dados.'),
        ):
            row = tk.Frame(body, bg=THEME['bg_surface'])
            row.pack(fill='x', pady=(0, 10))
            radio = tk.Radiobutton(row, text=title, variable=self.backend, value=value,
                                   command=self._mode_changed, bg=THEME['bg_surface'],
                                   activebackground=THEME['bg_surface'], font=('Segoe UI', 10, 'bold'), anchor='w')
            radio.pack(anchor='w')
            self._editable.append((radio, 'normal'))
            tk.Label(row, text=help_text, bg=THEME['bg_surface'], fg='#475569',
                     font=('Segoe UI', 9)).pack(anchor='w', padx=25)

        self.local_frame = tk.LabelFrame(body, text=' Banco local ', bg='#ffffff',
                                         padx=12, pady=10, font=('Segoe UI', 9, 'bold'))
        tk.Label(self.local_frame, text='Seu banco já está configurado. Normalmente você não precisa mudar nada.',
                 bg='#ffffff', fg='#334155', font=('Segoe UI', 9), wraplength=540, justify='left').pack(anchor='w')
        path_row = tk.Frame(self.local_frame, bg='#ffffff')
        path_row.pack(fill='x', pady=(10, 0))
        entry = ttk.Entry(path_row, textvariable=self.sqlite_path, state='readonly', width=46)
        entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
        self.fields['sqlite_path'] = entry
        self._editable.append((entry, 'readonly'))
        choose = IconButton(path_row, icon='open', text='Escolher arquivo...', command=self._choose_file,
                            bg='#ffffff', font=('Segoe UI', 9), bd=1)
        choose.pack(side='right')
        self._editable.append((choose, 'normal'))

        self.server_frame = tk.LabelFrame(body, text=' Dados do servidor ', bg='#ffffff',
                                          padx=12, pady=10, font=('Segoe UI', 9, 'bold'))
        tk.Label(self.server_frame, text='Peça estes dados a quem cuida do banco ou da rede da empresa.',
                 bg='#ffffff', fg='#475569', font=('Segoe UI', 9), wraplength=540, justify='left').grid(
                     row=0, column=0, columnspan=2, sticky='w', pady=(0, 12))
        self.server_frame.columnconfigure(1, weight=1)
        for row, (key, label, hint) in enumerate((
            ('host', 'Endereço do servidor', 'Ex.: 192.168.1.10 ou nome do servidor'),
            ('database', 'Nome do banco', 'Ex.: jobmanager'),
            ('user', 'Usuário', 'Usuário com acesso ao banco'),
            ('password', 'Senha', None),
        ), start=1):
            line = row * 2
            tk.Label(self.server_frame, text=label, bg='#ffffff', font=('Segoe UI', 9)).grid(
                row=line, column=0, sticky='w', padx=(0, 14), pady=(3, 0))
            entry = ttk.Entry(self.server_frame, textvariable=getattr(self, key),
                              show='•' if key == 'password' else '', width=35)
            entry.grid(row=line, column=1, sticky='ew', pady=(3, 0))
            self.fields[key] = entry
            self._editable.append((entry, 'normal'))
            if hint:
                tk.Label(self.server_frame, text=hint, bg='#ffffff', fg='#64748b',
                         font=('Segoe UI', 8)).grid(row=line+1, column=1, sticky='w', pady=(0, 5))
        show = tk.Checkbutton(self.server_frame, text='Mostrar senha', variable=self.show_password,
                              command=self._toggle_password, bg='#ffffff', font=('Segoe UI', 9))
        show.grid(row=10, column=1, sticky='w', pady=(2, 3))
        self._editable.append((show, 'normal'))
        advanced = tk.Checkbutton(self.server_frame, text='Alterar porta (opcional)', variable=self.show_port,
                                  command=self._toggle_port, bg='#ffffff', font=('Segoe UI', 9))
        advanced.grid(row=11, column=0, columnspan=2, sticky='w')
        self._editable.append((advanced, 'normal'))
        self.port_row = tk.Frame(self.server_frame, bg='#ffffff')
        tk.Label(self.port_row, text='Porta', bg='#ffffff', font=('Segoe UI', 9)).pack(side='left', padx=(0, 8))
        port_entry = ttk.Entry(self.port_row, textvariable=self.port, width=7)
        port_entry.pack(side='left')
        self.fields['port'] = port_entry
        self._editable.append((port_entry, 'normal'))
        tk.Label(self.port_row, text='Normalmente é 3306.', bg='#ffffff', fg='#64748b',
                 font=('Segoe UI', 8)).pack(side='left', padx=8)
        self._toggle_port(resize=False)

        self.status_label = tk.Label(body, textvariable=self.status, bg=THEME['bg_surface'],
                                     fg='#334155', font=('Segoe UI', 9), wraplength=575,
                                     justify='left', anchor='w')
        self.status_label.pack(side='bottom', fill='x', pady=(12, 0))
        footer = tk.Frame(self, bg='#ffffff', padx=20, pady=12)
        footer.pack(fill='x')
        tk.Label(footer, text='A mudança vale ao reabrir o CorteAC. Os dados existentes não serão transferidos.',
                 bg='#ffffff', fg='#475569', font=('Segoe UI', 8), wraplength=585,
                 justify='left').pack(anchor='w', pady=(0, 12))
        buttons = tk.Frame(footer, bg='#ffffff')
        buttons.pack(fill='x')
        self.test_button = IconButton(buttons, icon='check', text='Testar conexão',
                                      command=self.test_connection, bg='#ffffff', font=('Segoe UI', 9), padx=10, pady=5, bd=1)
        self.test_button.pack(side='left')
        self.save_button = IconButton(buttons, icon='save', text='Salvar configuração', command=self.save_configuration,
                                      bg='#2563eb', fg='#ffffff', activebackground='#1d4ed8', activeforeground='#ffffff',
                                      font=('Segoe UI', 9, 'bold'), padx=12, pady=5, bd=1)
        self.save_button.pack(side='right')
        self.close_button = IconButton(buttons, text='Fechar', command=self.destroy,
                                       bg='#ffffff', font=('Segoe UI', 9), padx=10, pady=5, bd=1)
        self.close_button.pack(side='right', padx=8)

    def _resize(self):
        self.update_idletasks()
        width = max(640, self.winfo_reqwidth())
        height = self.winfo_reqheight()
        x = max(0, self.master.winfo_rootx() + (self.master.winfo_width() - width) // 2)
        y = max(0, self.master.winfo_rooty() + (self.master.winfo_height() - height) // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def _mode_changed(self):
        self.local_frame.pack_forget()
        self.server_frame.pack_forget()
        target = self.server_frame if self.backend.get() == 'mysql' else self.local_frame
        target.pack(fill='x', before=self.status_label)
        if self._environment_locked:
            self._set_status('Esta instalação recebe configurações externas. Você pode testar; para alterá-las, peça ajuda ao responsável pelo sistema.')
        elif not self._load_error:
            self._set_status('Confira os dados e clique em Testar conexão.' if self.backend.get() == 'mysql'
                             else 'Tudo pronto para usar o banco deste computador. Você pode testar antes de salvar.')
        self._resize()

    def _toggle_password(self):
        self.fields['password'].config(show='' if self.show_password.get() else '•')

    def _toggle_port(self, resize=True):
        if self.show_port.get():
            self.port_row.grid(row=12, column=0, columnspan=2, sticky='w', pady=(5, 0))
        else:
            self.port_row.grid_remove()
        if resize:
            self._resize()

    def _choose_file(self):
        filename = filedialog.askopenfilename(parent=self, title='Escolher o banco local do CorteAC',
                                              initialdir=str(Path(self.sqlite_path.get()).parent),
                                              filetypes=[('Banco SQLite', '*.db *.sqlite *.sqlite3'), ('Todos os arquivos', '*.*')])
        if filename:
            self.sqlite_path.set(filename)
            self._set_status('Arquivo selecionado. Clique em Testar conexão para conferir.')

    def _collect_settings(self):
        port = self.settings.port
        if self.backend.get() == 'mysql':
            try:
                port = int(self.port.get().strip())
            except ValueError:
                raise SettingsError('A porta deve ser um número. Normalmente é 3306.', 'port')
        return validate_settings(replace(self.settings, backend=self.backend.get(),
                                         host=self.host.get(), port=port, database=self.database.get(),
                                         user=self.user.get(), password=self.password.get(),
                                         sqlite_path=self.sqlite_path.get()))

    def _set_status(self, text, error=False, success=False):
        self.status.set(text)
        self.status_label.config(fg='#b91c1c' if error else '#0f766e' if success else '#334155')

    def _show_error(self, error):
        self._set_status(str(error), error=True)
        field = self.fields.get(getattr(error, 'field_name', None))
        if field is not None:
            if field is self.fields.get('port'):
                self.show_port.set(True)
                self._toggle_port(resize=False)
            field.focus_set()
        self._resize()

    def _set_busy(self, busy):
        self._busy = busy
        for widget, normal_state in self._editable:
            widget.config(state='disabled' if busy else normal_state)
        self.test_button.config(state='disabled' if busy or self._load_error else 'normal')
        self.save_button.config(state='disabled' if busy or self._load_error or self._environment_locked else 'normal')

    def test_connection(self):
        self._start_test(save_after=False)

    def save_configuration(self):
        if self._environment_locked or self._load_error or self._busy:
            return
        try:
            settings = self._collect_settings()
        except SettingsError as exc:
            self._show_error(exc)
            return
        if settings == self._tested_settings:
            self._save(settings)
        else:
            self._start_test(save_after=True)

    def _start_test(self, save_after=False):
        if self._busy or self._load_error or self._closed:
            return
        try:
            settings = self._collect_settings()
        except SettingsError as exc:
            self._show_error(exc)
            return
        self._pending_save = save_after
        self._testing_settings = settings
        self._set_busy(True)
        self._set_status('Conferindo a conexão antes de salvar...' if save_after else 'Testando conexão... Aguarde alguns segundos.')
        self._resize()
        threading.Thread(target=_probe_worker, args=(settings, self._results), daemon=True).start()
        self._poll_job = self.after(80, self._poll_result)

    def _poll_result(self):
        self._poll_job = None
        if self._closed:
            return
        try:
            success, result = self._results.get_nowait()
        except queue.Empty:
            self._poll_job = self.after(80, self._poll_result)
            return
        self._set_busy(False)
        if success:
            self._tested_settings = self._testing_settings
            if self._pending_save:
                self._save(self._testing_settings)
            else:
                next_step = (' Para alterar a configuração externa, peça ajuda ao responsável pelo sistema.'
                             if self._environment_locked else ' Clique em Salvar configuração para usar esta opção.')
                self._set_status(result + next_step, success=True)
                self._resize()
        else:
            self._tested_settings = None
            self._show_error(result)

    def _save(self, settings):
        try:
            save_settings(settings, self.config_path)
        except SettingsError as exc:
            self._show_error(exc)
            return
        self.settings = settings
        self._set_status('Configuração salva! Feche e abra o CorteAC para começar a usar esta conexão.', success=True)
        self._resize()

    def destroy(self):
        if self._closed:
            return
        self._closed = True
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        if self.grab_current() == self:
            self.grab_release()
        super().destroy()


def _probe_worker(settings, results):
    # A thread só faz I/O; widgets e mensagens são atualizados pela thread do Tk.
    try:
        results.put((True, probe_connection(settings)))
    except SettingsError as exc:
        results.put((False, exc))
    except Exception:
        results.put((False, SettingsError('Não foi possível concluir o teste. Confira os dados e tente novamente.')))
