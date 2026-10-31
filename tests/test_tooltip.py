"""
tests/test_tooltip.py

Tooltips do Layout Editor: nome da ferramenta ao parar o mouse no ícone.
"""

import tkinter as tk
import unittest

from ui.tooltip import ToolTip


class TestToolTip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.has_display = True
        except tk.TclError:
            cls.root = None
            cls.has_display = False

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.has_display:
            self.skipTest("Tkinter display not available")

    def test_mostra_e_esconde_no_hover(self):
        btn = tk.Button(self.root, text="X")
        btn.pack()
        tip = ToolTip(btn, "Salvar Layout (Ctrl+S)", delay_ms=1)
        self.assertFalse(tip.is_visible())
        tip.show()
        self.assertTrue(tip.is_visible())
        tip.hide()
        self.assertFalse(tip.is_visible())

    def test_enter_agenda_e_leave_cancela(self):
        btn = tk.Button(self.root, text="Y")
        btn.pack()
        tip = ToolTip(btn, "Novo Layout", delay_ms=5000)
        # <Enter> agenda a exibição (handler direto: widget não mapeado em teste headless)
        tip._on_enter()
        self.assertIsNotNone(tip._after_id)
        tip._on_leave()
        self.assertIsNone(tip._after_id)
        self.assertFalse(tip.is_visible())

    def test_apenas_um_tooltip_visivel(self):
        b1 = tk.Button(self.root, text="A")
        b2 = tk.Button(self.root, text="B")
        b1.pack(); b2.pack()
        t1 = ToolTip(b1, "Ferramenta A", delay_ms=1)
        t2 = ToolTip(b2, "Ferramenta B", delay_ms=1)
        t1.show()
        t2.show()
        self.assertFalse(t1.is_visible())
        self.assertTrue(t2.is_visible())
        t2.hide()

    def test_destroy_do_widget_nao_quebra(self):
        btn = tk.Button(self.root, text="C")
        btn.pack()
        tip = ToolTip(btn, "Temporário", delay_ms=1)
        tip._on_enter()
        btn.destroy()
        self.root.update_idletasks()
        tip.hide()

    def test_todos_os_botoes_da_toolbar_tem_tooltip(self):
        from ui.layout_editor_view import LayoutEditorView

        view = LayoutEditorView(self.root, layout_name="[TIP]", load_sample=False)
        view.pack()
        view.update_idletasks()
        com_tip = 0
        for nome in dir(view):
            if nome.startswith("btn_"):
                w = getattr(view, nome, None)
                if isinstance(w, tk.Widget) and hasattr(w, "_tooltip"):
                    if w._tooltip.text:
                        com_tip += 1
        # Refilar + Simular + Zoom no mínimo
        self.assertGreaterEqual(com_tip, 3, "Botões do editor sem tooltip")
        self.assertTrue(hasattr(view.btn_trim, "_tooltip"))
        self.assertIn("Refilar", view.btn_trim._tooltip.text)
        view.destroy()


if __name__ == "__main__":
    unittest.main()
