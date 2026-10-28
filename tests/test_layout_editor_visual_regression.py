"""
tests/test_layout_editor_visual_regression.py

Teste de regressão visual automatizado para LayoutEditorView.
Compara screenshots renderizados via canvas.postscript contra fixtures estáveis,
garantindo tolerância estrita de 0 pixels de divergência em zoom, pan, seleção e arraste.
"""

import unittest
from pathlib import Path
from tools.capture_layout_screenshots import run_scenarios, BASE_DIR

FIXTURES_DIR = BASE_DIR / "tests" / "fixtures" / "layout_screenshots"


class TestLayoutEditorVisualRegression(unittest.TestCase):
    def test_visual_regression_all_scenarios(self):
        """Valida que nenhum dos 6 cenários apresenta regressão visual (0 px de diferença)."""
        self.assertTrue(FIXTURES_DIR.exists(), f"Diretório de fixtures não encontrado: {FIXTURES_DIR}")
        passed = run_scenarios(compare_dir=FIXTURES_DIR)
        self.assertTrue(passed, "Regressão visual detectada em pelo menos um cenário do LayoutEditorView!")


if __name__ == "__main__":
    unittest.main()
