"""Controles com ícones uniformes, sem alterar classes globais do Tkinter.

config()/configure() também resolvem o ícone (por exemplo Simular/Parar).
Imagens explícitas e textos sem símbolos continuam aceitos normalmente.
"""
import tkinter as tk
from tkinter import ttk, font as tkfont
from ui.icons import get_icon, icon_size, split_icon_text


class _IconText:
    _managed_icon = False

    def _icon_options(self, options):
        options = dict(options)
        explicit = options.pop("icon", None)
        if "text" not in options and explicit is None:
            return options
        name, label = split_icon_text(options.get("text", ""))
        name = explicit or name
        if options.get("image"):
            self._managed_icon = False
            return options
        if name:
            if name == "zoom" and isinstance(label, str):
                if "Zoom +" in label:
                    name = "zoom_in"
                elif "Zoom -" in label:
                    name = "zoom_out"
            if name == "save" and "Todos" in str(label):
                name = "save_all"
            self._managed_icon = True
            options.update(text=label, image=get_icon(self, name), compound="left")
        elif self._managed_icon:
            options.update(image="", compound="none")
            self._managed_icon = False
        return options

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, str) or (cnf is None and not kw):
            return super().configure(cnf, **kw)
        return super().configure(self._icon_options({**(cnf or {}), **kw}))

    config = configure


class IconButton(_IconText, tk.Button):
    def __init__(self, master=None, cnf=None, **kw):
        # Inicializa o widget antes de resolver master/scaling.
        super().__init__(master)
        options = self._icon_options({**(cnf or {}), **kw})
        if self._managed_icon:
            label = options.get("text", "")
            if not label:
                # Com imagem, width/height são pixels em vez de caracteres.
                options["width"] = icon_size(self, 20)
                options["height"] = icon_size(self, 20)
                options.setdefault("padx", 2)
                options.setdefault("pady", 2)
            else:
                font = tkfont.Font(self, font=options.get("font", "TkDefaultFont"))
                if options.get("width"):
                    options["width"] = max(font.measure("0") * int(options["width"]),
                                           font.measure(label) + icon_size(self, 24))
                if options.get("height"):
                    options["height"] = font.metrics("linespace") * int(options["height"])
                options.setdefault("padx", 6)
        tk.Button.configure(self, options)


class IconLabel(_IconText, tk.Label):
    def __init__(self, master=None, cnf=None, **kw):
        super().__init__(master)
        tk.Label.configure(self, self._icon_options({**(cnf or {}), **kw}))


class IconCheckbutton(_IconText, tk.Checkbutton):
    def __init__(self, master=None, cnf=None, **kw):
        super().__init__(master)
        tk.Checkbutton.configure(self, self._icon_options({**(cnf or {}), **kw}))


class IconRadiobutton(_IconText, tk.Radiobutton):
    def __init__(self, master=None, cnf=None, **kw):
        super().__init__(master)
        tk.Radiobutton.configure(self, self._icon_options({**(cnf or {}), **kw}))


class IconTtkButton(_IconText, ttk.Button):
    def __init__(self, master=None, **kw):
        super().__init__(master)
        ttk.Button.configure(self, self._icon_options(kw))


class IconMenu(tk.Menu):
    def _entry_options(self, options):
        options = dict(options)
        explicit = options.pop("icon", None)
        name, label = split_icon_text(options.get("label", ""))
        name = explicit or name
        if name and not options.get("image"):
            options.update(label=label, image=get_icon(self, name, 16), compound="left")
        return options

    def add(self, itemType, cnf=None, **kw):
        return super().add(itemType, self._entry_options({**(cnf or {}), **kw}))

    def insert(self, index, itemType, cnf=None, **kw):
        return super().insert(index, itemType, self._entry_options({**(cnf or {}), **kw}))

    def entryconfigure(self, index, cnf=None, **kw):
        if isinstance(cnf, str) or (cnf is None and not kw):
            return super().entryconfigure(index, cnf, **kw)
        options = self._entry_options({**(cnf or {}), **kw})
        if "label" in options and "image" not in options:
            options.update(image="", compound="none")
        return super().entryconfigure(index, options)

    entryconfig = entryconfigure


class IconNotebook(ttk.Notebook):
    def _tab_options(self, options):
        options = dict(options)
        name, label = split_icon_text(options.get("text", ""))
        if name and not options.get("image"):
            options.update(text=label, image=get_icon(self, name, 16), compound="left")
        elif "text" in options and "image" not in options:
            options.update(image="")
        return options

    def add(self, child, **kw):
        return super().add(child, **self._tab_options(kw))

    def insert(self, pos, child, **kw):
        return super().insert(pos, child, **self._tab_options(kw))

    def tab(self, tab_id, option=None, **kw):
        return super().tab(tab_id, option, **self._tab_options(kw))
