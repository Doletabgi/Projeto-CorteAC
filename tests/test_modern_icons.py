"""Valida o ciclo de vida dos ícones nos controles reais do Tk."""
import gc
import tkinter as tk
from tkinter import font as tkfont

import pytest

from ui.icon_art import ICON_NAMES
from ui.icons import ASSETS_DIR, get_icon, split_icon_text
from ui.icon_widgets import IconButton, IconCheckbutton, IconMenu, IconNotebook


@pytest.fixture
def root():
    window = tk.Tk()
    window.withdraw()
    window.tk.call('tk', 'scaling', 96 / 72)
    yield window
    window.destroy()


def test_all_distributed_icons_are_present(root):
    for name in ICON_NAMES:
        assert (ASSETS_DIR / 'icons' / f'{name}.png').is_file()
        icon = get_icon(root, name)
        assert (icon.width(), icon.height()) == (18, 18)


def test_button_updates_icon_without_changing_callback_or_state(root):
    calls = []
    button = IconButton(root, text='▶ Simular', command=lambda: calls.append('run'))
    first_image = button.cget('image')
    button.config(text='⏹ Parar', state='disabled')
    assert button.cget('text') == 'Parar'
    assert button.cget('image') != first_image
    assert button.cget('state') == 'disabled'
    button.config(state='normal')
    button.invoke()
    assert calls == ['run']
    button.config(text='Pronto')
    assert button.cget('image') == ''
    assert button.configure('text')[-1] == 'Pronto'


def test_explicit_image_and_plain_text_are_preserved(root):
    image = get_icon(root, 'save')
    button = IconButton(root, image=image, text='Arquivo', width=22)
    assert button.cget('image') == str(image)
    assert button.cget('text') == 'Arquivo'
    plain = IconButton(root, text='Cancelar', width=12)
    assert plain.cget('image') == ''
    assert int(plain.cget('width')) == 12


def test_icon_only_and_fixed_width_labels_fit(root):
    only = IconButton(root, text='✕', width=2, height=1)
    assert 18 <= int(only.cget('width')) < 40
    assert only.cget('text') == ''
    labeled = IconButton(root, text='💾 Salvar configurações', width=4)
    font = tkfont.Font(root, font=labeled.cget('font'))
    assert int(labeled.cget('width')) >= font.measure(labeled.cget('text')) + 18


def test_menu_insert_and_updates_preserve_behavior(root):
    calls = []
    menu = IconMenu(root, tearoff=0)
    menu.add_command(label='📂 Abrir', command=lambda: calls.append('open'))
    menu.insert_command(0, label='💾 Salvar', state='disabled')
    assert menu.entrycget(0, 'label') == 'Salvar'
    assert menu.entrycget(0, 'state') == 'disabled'
    assert menu.entrycget(1, 'image')
    menu.invoke(1)
    assert calls == ['open']
    menu.entryconfig(1, label='⏹ Parar')
    assert menu.entrycget(1, 'label') == 'Parar'
    assert menu.entrycget(1, 'image') == str(get_icon(root, 'stop', 16))
    menu.entryconfig(1, label='Pronto')
    assert menu.entrycget(1, 'image') == ''


def test_notebook_and_checkbutton_keep_selection(root):
    notebook = IconNotebook(root)
    frame = tk.Frame(notebook)
    notebook.add(frame, text='  💾 Criar Backup  ')
    assert notebook.tab(0, 'text') == 'Criar Backup'
    assert notebook.tab(0, 'image')
    notebook.tab(0, text='Restaurar')
    assert not notebook.tab(0, 'image')
    value = tk.BooleanVar(root, False)
    check = IconCheckbutton(root, text='✂ Refile automático', variable=value)
    check.invoke()
    assert value.get()
    assert check.cget('image')


def test_cache_survives_gc_and_is_scoped_to_tcl_interpreter(root):
    icon = get_icon(root, 'open')
    assert icon is get_icon(root, 'open')
    name = str(icon)
    del icon
    gc.collect()
    assert root.tk.call('image', 'width', name) == 18
    other = tk.Tk()
    other.withdraw()
    try:
        second = get_icon(other, 'open')
        assert second.tk is other.tk
        assert second.tk is not root.tk
    finally:
        other.destroy()


def test_hidpi_uses_larger_source_without_changing_previous_images(root):
    normal = get_icon(root, 'save')
    root.tk.call('tk', 'scaling', 2 * 96 / 72)
    larger = get_icon(root, 'save')
    assert larger.width() == 36
    assert normal.width() == 18
    assert larger is not normal


def test_text_symbols_inside_sentences_are_not_removed():
    text = "Clique em '➕ Adicionar Molde...' para continuar."
    assert split_icon_text(text) == (None, text)
    assert split_icon_text('Próxima ▶') == ('right', 'Próxima')
