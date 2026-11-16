"""Mensagens e dicas não podem redimensionar a área de edição."""

import tkinter as tk
import unittest

from ui.layout_editor_view import LayoutEditorView


class TestStatusGeometry(unittest.TestCase):
    def test_status_and_toolbar_hover_preserve_editor_and_canvas_geometry(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tkinter display not available")
        try:
            root.geometry("1100x750+5000+5000")
            view = LayoutEditorView(root, load_sample=False)
            view.pack(fill="both", expand=True)
            root.update()

            def geometry():
                return (view.winfo_reqwidth(), view.winfo_reqheight(),
                        view.status_bar.winfo_height(), view.canvas.winfo_width(),
                        view.canvas.winfo_height(), view.plate_scale)

            baseline = geometry()
            configured = []
            view.canvas.bind("<Configure>", lambda e: configured.append((e.width, e.height)), add="+")
            for message in ("Pronto", "Molde: 2 peças. " * 40,
                            "Salvar sessão\nExportar layouts\nTodas as placas", ""):
                with self.subTest(message=message):
                    view.lbl_stat_pos.config(text=message)
                    root.update()
                    self.assertEqual(geometry(), baseline)
                    self.assertEqual(view.lbl_stat_pos.cget("text"), message)
            for sequence in ("<Enter>", "<Leave>") * 3:
                view.btn_machine.event_generate(sequence)
                root.update()
                self.assertEqual(geometry(), baseline)
            self.assertEqual(configured, [])
        finally:
            root.destroy()
