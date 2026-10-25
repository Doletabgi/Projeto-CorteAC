"""
Testes unitários e de integração para a coluna 'Resto' na grade de Moldes da SessionView.
Valida:
1. calc_resto com 4 camadas (print original da sessão 619955: 125, 109, 97 -> -1; 126, 62 -> 0).
2. calc_resto com 2 camadas (sempre 0), 1 camada ou None (0).
3. 0 pares e valores grandes sem erro.
4. Grade tree_shapes: coluna Resto entre Pares e Sequência, somente leitura, alinhada à direita e recalculada ao editar Pares.
5. Recálculo ao mudar camadas do material na aba Materiais.
6. Digitação contínua via Tab / Shift-Tab ignora a coluna Resto.
7. Ordenação numérica por Resto (negativos ordenados corretamente).
"""
import time
import unittest
import tkinter as tk

from cad.layers_rule import calc_resto
from ui.sort_utils import resto_sort_key
from ui.session_view import SessionView


class TestCalcRestoPure(unittest.TestCase):
    def test_01_calc_resto_4_layers_user_screenshot(self):
        """Com 4 camadas, pares ímpares dão -1 e pares dão 0 (dados reais do print)."""
        self.assertEqual(calc_resto(125, 4), -1)
        self.assertEqual(calc_resto(109, 4), -1)
        self.assertEqual(calc_resto(97, 4), -1)
        self.assertEqual(calc_resto(126, 4), 0)
        self.assertEqual(calc_resto(62, 4), 0)

    def test_02_calc_resto_2_layers_always_zero(self):
        """Com 2 camadas, peças = 2P é sempre múltiplo de 2, logo sobra é sempre 0."""
        for p in (1, 2, 15, 62, 97, 109, 125, 126, 200, 999):
            self.assertEqual(calc_resto(p, 2), 0, f'Pares {p} com 2 camadas deve ter resto 0')

    def test_03_calc_resto_1_layer_or_none(self):
        """Com 1 camada, indefinido ou inválido, retorna 0."""
        self.assertEqual(calc_resto(125, 1), 0)
        self.assertEqual(calc_resto(125, 0), 0)
        self.assertEqual(calc_resto(125, -1), 0)
        self.assertEqual(calc_resto(125, None), 0)
        self.assertEqual(calc_resto(125, 'invalid'), 0)

    def test_04_calc_resto_edge_cases_and_large_values(self):
        """0 pares, negativos ou valores grandes."""
        self.assertEqual(calc_resto(0, 4), 0)
        self.assertEqual(calc_resto(-5, 4), 0)
        self.assertEqual(calc_resto(None, 4), 0)
        self.assertEqual(calc_resto('abc', 4), 0)
        # Valores grandes
        self.assertEqual(calc_resto(1_000_000_001, 4), -1)
        self.assertEqual(calc_resto(1_000_000_000, 4), 0)

    def test_05_resto_sort_key_supports_negatives(self):
        """resto_sort_key converte valores numéricos com suporte a negativos."""
        self.assertEqual(resto_sort_key(-1), -1)
        self.assertEqual(resto_sort_key(0), 0)
        self.assertEqual(resto_sort_key('-1'), -1)
        self.assertEqual(resto_sort_key('0'), 0)
        self.assertEqual(resto_sort_key(None), 0)
        self.assertEqual(resto_sort_key('invalid'), 0)
        self.assertLess(resto_sort_key(-1), resto_sort_key(0))


class TestSessionViewShapesRestoGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.geometry('900x700')
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.root:
            self.skipTest('Display Tkinter não disponível')
        self.saved_sessions = []
        self.session_data = {
            'id': 619955,
            'name': 'Sessão 619955',
            'status': 'Stand by',
            'material': {
                'id': 'MAT_TEST',
                'name': 'Material Teste 4 Camadas',
                'layers': 4,
                'width_mm': 1380,
                'height_mm': 1080
            },
            'shapes': [
                {'id': 1, 'name': 'Molde_125', 'size': '41', 'pairs': 125, 'sequence': 1},
                {'id': 2, 'name': 'Molde_126', 'size': '42', 'pairs': 126, 'sequence': 2},
                {'id': 3, 'name': 'Molde_109', 'size': '43', 'pairs': 109, 'sequence': 3},
                {'id': 4, 'name': 'Molde_62', 'size': '40', 'pairs': 62, 'sequence': 4},
            ]
        }
        self.sv = SessionView(
            self.root,
            session_data=self.session_data,
            on_add_shapes=lambda sid, shapes: self.saved_sessions.append((sid, list(shapes)))
        )
        self.sv.pack(fill='both', expand=True)
        self.sv.load_session(self.session_data)
        self.sv.notebook.select(1)  # Aba Moldes
        self.root.update()

    def tearDown(self):
        try:
            self.sv.destroy()
        except Exception:
            pass

    def test_06_resto_column_position_alignment_and_readonly(self):
        """Coluna 'Resto' fica entre 'Pares' e 'Sequência', alinhada à direita e somente leitura."""
        cols = self.sv.tree_shapes['columns']
        # cols = ('shape_id', 'percurso', 'tamanho', 'molde', 'pares', 'resto', 'sequencia')
        idx_pares = cols.index('pares')
        idx_resto = cols.index('resto')
        idx_seq = cols.index('sequencia')

        self.assertEqual(idx_resto, idx_pares + 1, 'Resto deve estar imediatamente após Pares')
        self.assertEqual(idx_seq, idx_resto + 1, 'Sequência deve estar imediatamente após Resto')

        col_opts = self.sv.tree_shapes.column('resto')
        self.assertEqual(col_opts.get('anchor'), 'e', 'Coluna Resto deve estar alinhada à direita (e)')

        # Tentar abrir inline editor na coluna #6 (Resto) deve ser ignorado (somente leitura)
        self.sv.spawn_tree_inline_editor('0', '#6')
        self.root.update()
        self.assertIsNone(self.sv._inline_editor, 'Coluna Resto não deve permitir abertura de editor inline')

    def test_07_resto_calculated_on_display_and_updated_on_pairs_edit(self):
        """Verifica valores iniciais de Resto com 4 camadas e atualização imediata ao editar Pares."""
        # Molde_125 (pares=125, camadas=4) -> -1
        # Molde_126 (pares=126, camadas=4) -> 0
        val_row0 = self.sv.tree_shapes.set('0', 'resto')
        val_row1 = self.sv.tree_shapes.set('1', 'resto')
        self.assertEqual(val_row0, '-1', '125 pares com 4 camadas deve exibir -1')
        self.assertEqual(val_row1, '0', '126 pares com 4 camadas deve exibir 0')

        # Edita Molde_125 de 125 para 100 pares (100 % 2 == 0 -> resto 0 com 4 camadas: 200 % 4 == 0)
        self.sv.spawn_tree_inline_editor('0', '#5')
        self.root.update()
        entry = self.sv._inline_editor
        self.assertIsNotNone(entry)
        entry.delete(0, 'end')
        entry.insert(0, '100')
        entry.focus_force()
        entry.event_generate('<Return>', when='now')
        time.sleep(0.06)
        self.root.update()

        # Agora a linha 0 deve ter resto '0'
        new_val_row0 = self.sv.tree_shapes.set('0', 'resto')
        self.assertEqual(new_val_row0, '0', 'Após mudar para 100 pares, resto deve atualizar para 0')

    def test_08_resto_recalculated_when_material_layers_change(self):
        """Ao alterar as camadas do material na aba Materiais, a coluna Resto deve recalcular."""
        # Inicialmente 4 camadas: Molde_125 tem resto -1
        self.assertEqual(self.sv.tree_shapes.set('0', 'resto'), '-1')

        # Altera camadas para 2 via set_material_data
        new_mat = dict(self.session_data['material'])
        new_mat['layers'] = 2
        self.sv.set_material_data(new_mat)
        self.root.update()

        # Com 2 camadas, 125 pares dá resto 0
        self.assertEqual(self.sv.tree_shapes.set('0', 'resto'), '0')

        # Altera de volta para 4 camadas via tree_mat e notify_material_changed
        self.sv.tree_mat.item('mat_0', values=('▶', 'MAT_TEST', 'Desc', 'como placa', '1,38', '1,08', '4', '0', '1', '0'))
        self.sv.notify_material_changed()
        self.root.update()

        # Deve voltar para -1
        self.assertEqual(self.sv.tree_shapes.set('0', 'resto'), '-1')

    def test_09_continuous_typing_skips_resto_column(self):
        """Ao navegar por Tab ou Shift-Tab, a coluna Resto é ignorada (pula Pares <-> Sequência)."""
        # 1. Abre inline editor na linha 0, coluna #5 (Pares)
        self.sv.spawn_tree_inline_editor('0', '#5')
        self.root.update()
        entry_pares = self.sv._inline_editor
        self.assertIsNotNone(entry_pares)

        # 2. Pressiona Tab -> deve pular direto para Sequência (#7), ignorando Resto (#6)
        entry_pares.focus_force()
        entry_pares.event_generate('<Tab>', when='now')
        time.sleep(0.06)
        self.root.update()

        entry_seq = self.sv._inline_editor
        self.assertIsNotNone(entry_seq, 'Editor deve estar aberto na coluna Sequência após Tab')
        # Verifica se estamos na coluna Sequência da linha 0
        self.assertEqual(entry_seq.get(), '1', 'Deve ser o valor da sequência da linha 0')

        # 3. Pressiona Shift-Tab -> deve voltar diretamente para Pares (#5), ignorando Resto (#6)
        entry_seq.focus_force()
        entry_seq.event_generate('<Shift-Tab>', when='now')
        time.sleep(0.06)
        self.root.update()

        entry_back = self.sv._inline_editor
        self.assertIsNotNone(entry_back, 'Editor deve voltar para a coluna Pares após Shift-Tab')
        self.assertEqual(entry_back.get(), '125', 'Deve ser o valor de Pares da linha 0')

    def test_10_sorting_by_resto_is_numeric_with_negatives(self):
        """Ordenação por Resto trata -1 como menor que 0 tanto ascendente quanto descendente."""
        # Molde_125: resto -1
        # Molde_126: resto 0
        # Molde_109: resto -1
        # Molde_62:  resto 0

        # Ordenação Ascendente (force_desc=False): -1 deve vir antes de 0
        self.sv.sort_shapes_by('resto', force_desc=False)
        self.root.update()

        restos_asc = [int(self.sv.tree_shapes.set(str(i), 'resto')) for i in range(len(self.sv.shapes_list))]
        self.assertEqual(restos_asc, [-1, -1, 0, 0], 'Ascendente: -1 deve preceder 0')

        # Ordenação Descendente (force_desc=True): 0 deve vir antes de -1
        self.sv.sort_shapes_by('resto', force_desc=True)
        self.root.update()

        restos_desc = [int(self.sv.tree_shapes.set(str(i), 'resto')) for i in range(len(self.sv.shapes_list))]
        self.assertEqual(restos_desc, [0, 0, -1, -1], 'Descendente: 0 deve preceder -1')
