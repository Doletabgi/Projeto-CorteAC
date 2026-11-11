"""
Testes automatizados para a geração de código de barras Code 128 (Subset B)
e leitura automática de sessões via scanner USB no CorteAC.
"""

import time
import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from cad.barcode import (
    encode_code128_b,
    draw_code128_canvas,
    generate_code128_pillow,
    sanitize_code128_b_text,
    START_B_CODE,
    STOP_CODE,
    CODE128_PATTERNS,
)
from ui.layout_print_dialog import LayoutPrintDialog
from ui.main_window import MainWindow


class TestBarcodeEngine:
    """Testes do gerador Code 128 nativo em Python puro."""

    def test_sanitize_text(self):
        assert sanitize_code128_b_text("CAC:SESS:188") == "CAC:SESS:188"
        assert sanitize_code128_b_text("Teste com ácento") == "Teste com ?cento"
        assert sanitize_code128_b_text("") == ""

    def test_encode_code128_structure(self):
        payload = "CAC:SESS:188"
        bits = encode_code128_b(payload, quiet_zone_modules=10)

        # Deve começar e terminar com quiet zone de 10 zeros
        assert bits.startswith("0000000000")
        assert bits.endswith("0000000000")

        # Após a quiet zone, deve vir o Start Code B
        start_b_pattern = CODE128_PATTERNS[START_B_CODE]
        assert bits[10:10 + len(start_b_pattern)] == start_b_pattern

        # Antes da quiet zone final, deve vir o Stop Code (11 módulos) + termination bar ('11')
        stop_pattern = CODE128_PATTERNS[STOP_CODE] + "11"
        assert bits[-(10 + len(stop_pattern)):-10] == stop_pattern

        # Apenas '0' e '1'
        assert set(bits).issubset({"0", "1"})

    def test_generate_pillow_image(self):
        payload = "CAC:SESS:188"
        img = generate_code128_pillow(payload, height=30, module_width=2, show_text=True, label="Sessão #188")
        assert img is not None
        w, h = img.size
        assert w > 100
        assert h >= 30

    def test_draw_canvas(self):
        root = tk.Tk()
        root.withdraw()
        canvas = tk.Canvas(root, width=400, height=200)
        canvas.pack()

        bbox = draw_code128_canvas(
            canvas, x=20, y=20, text="CAC:SESS:188", height=25, module_width=1.0, show_text=True, label="Sessão #188", tags="my_barcode"
        )
        assert bbox[2] > bbox[0]
        assert bbox[3] > bbox[1]

        items = canvas.find_withtag("my_barcode")
        assert len(items) > 0
        root.destroy()


class TestLayoutPrintBarcodeIntegration:
    """Testes de integração do código de barras no diálogo de impressão A4."""

    def test_print_dialog_barcode_payload_and_canvas(self):
        root=tk.Tk();root.withdraw()
        try:
            dlg=LayoutPrintDialog(root,layout_data={'session_id':188,'sheet_w_mm':1380,'sheet_h_mm':1080,'layouts':[{'name':'lay0000','session_id':188},{'name':'lay0001','session_id':188}]})
            payload,label=dlg.get_barcode_payload_and_label()
            assert payload=='CAC:SESS:188:LAY:0'
            assert 'Sessão #188' in label
            assert dlg.canvas.find_withtag('print_page')
            # O mesmo gerador Code128 é chamado em cada folha da prévia/exportação.
            from unittest.mock import patch
            from ui.production_sheet import generate_code128_pillow as original
            with patch('ui.production_sheet.generate_code128_pillow', wraps=original) as barcode:
                pages=dlg.render_pillow_pages()
                assert barcode.call_count>=len(pages)
                assert barcode.call_args.args[0]==payload
            dlg.destroy()
        finally:
            root.destroy()



class TestMainWindowScannerListener:
    """Testes do listener global de leitor de código de barras USB."""

    def test_on_barcode_scanned_parses_session(self):
        fake_window = object.__new__(MainWindow)
        fake_window.sessions = [{"id": 188, "name": "Sessão 188"}]
        fake_window.show_session_window = MagicMock()
        fake_window.session_view = MagicMock()
        fake_window.lbl_status_msg = MagicMock()
        fake_window.focus_get = MagicMock(return_value=None)

        # 1. Testa payload completo com sessão e layout
        res = MainWindow.on_barcode_scanned(fake_window, "CAC:SESS:188:LAY:1")
        assert res is True
        fake_window.show_session_window.assert_called_with(188)

        # 2. Testa payload simples CAC:SESS:188
        fake_window.show_session_window.reset_mock()
        res2 = MainWindow.on_barcode_scanned(fake_window, "CAC:SESS:188")
        assert res2 is True
        fake_window.show_session_window.assert_called_with(188)

        # 3. Testa payload com prefixo SESS:188
        fake_window.show_session_window.reset_mock()
        res3 = MainWindow.on_barcode_scanned(fake_window, "SESS:188")
        assert res3 is True
        fake_window.show_session_window.assert_called_with(188)

        # 4. Testa payload numérico direto 188
        fake_window.show_session_window.reset_mock()
        res4 = MainWindow.on_barcode_scanned(fake_window, "188")
        assert res4 is True
        fake_window.show_session_window.assert_called_with(188)

    def test_global_key_scanner_burst_and_return(self):
        fake_window = object.__new__(MainWindow)
        fake_window._scanner_buffer = []
        fake_window._scanner_last_key_time = 0.0
        fake_window.on_barcode_scanned = MagicMock()

        # Simula rajada rápida de caracteres do leitor USB (intervalo < 20ms)
        barcode_str = "CAC:SESS:188"
        for ch in barcode_str:
            event = MagicMock()
            event.keysym = ch
            event.char = ch
            MainWindow._on_global_key_scanner(fake_window, event)

        assert "".join(fake_window._scanner_buffer) == "CAC:SESS:188"

        # Simula tecla Return enviada pelo leitor ao final
        ret_event = MagicMock()
        ret_event.keysym = "Return"
        ret_event.char = "\r"
        ret = MainWindow._on_global_key_scanner(fake_window, ret_event)

        assert ret == "break"
        fake_window.on_barcode_scanned.assert_called_once_with("CAC:SESS:188")
        assert len(fake_window._scanner_buffer) == 0
