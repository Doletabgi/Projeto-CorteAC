"""Learning is isolated by material code; tests never open the production database."""
import json
import sqlite3
from unittest.mock import patch

from cad.ai_learner import NestingAIBrain
from cad.macro_engine import nest_ia_teste_engine


class MemoryDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)')

    def get_connection(self):
        return self.conn

    def get_setting(self, key, default=None):
        row = self.conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.conn.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, value))
        self.conn.commit()

    def get_all_settings(self):
        return dict(self.conn.execute('SELECT key, value FROM settings'))


def pieces():
    contour = [{'x': 0, 'y': 0}, {'x': 20, 'y': 0}, {'x': 20, 'y': 20}, {'x': 0, 'y': 20}]
    return [dict(name=name, contour=contour, x=x, y=0, rotation=0)
            for name, x in [('A', 0), ('B', 30)]]


def train(brain):
    brain.record_feedback('TIRA_LONGA', 2, 80)
    assert brain.learn_from_operator_save(pieces(), 500, 500) == 1


def test_materials_and_legacy_are_isolated_and_reset_is_scoped():
    db = MemoryDB()
    db.set_setting('ai_operator_habits', '[{"legacy": true}]')
    db.set_setting('ai_bandit_TIRA_LONGA', '{"total_trials": 100}')
    a, b = NestingAIBrain(db, '001'), NestingAIBrain(db, '002')
    assert a.get_memory_status()['total_runs'] == 0
    assert a.get_learned_habits() == []
    train(a)
    assert NestingAIBrain(db, '001').get_memory_status()['total_runs'] == 1
    assert b.get_memory_status()['total_runs'] == 0
    assert b.get_learned_habits() == []
    train(b)
    a.reset_learning()
    assert a.get_memory_status()['habits_count'] == 0
    assert a.get_memory_status()['total_runs'] == 0
    assert b.get_memory_status()['habits_count'] == 1
    assert b.get_memory_status()['total_runs'] == 1
    assert json.loads(db.get_setting('ai_bandit_TIRA_LONGA'))['total_trials'] == 100


def test_disabled_learning_blocks_both_writes_but_retains_learned_choice():
    db = MemoryDB()
    brain = NestingAIBrain(db, '001')
    train(brain)
    db.set_setting('ai_continuous_learning', '0')
    before = db.get_all_settings()
    brain.record_feedback('TIRA_LONGA', 0, 99)
    assert brain.learn_from_operator_save(pieces(), 500, 500) == 0
    assert brain.select_arm('TIRA_LONGA')[0] == 2
    assert db.get_all_settings() == before
    db.set_setting('ai_continuous_learning', '1')
    train(brain)
    assert brain.get_memory_status()['total_runs'] == 2


def test_missing_code_never_reads_or_records_unassigned_learning():
    db = MemoryDB()
    brain = NestingAIBrain(db)
    brain.record_feedback('TIRA_LONGA', 0, 90)
    assert brain.learn_from_operator_save(pieces(), 500, 500) == 0
    assert db.get_all_settings() == {}
    assert brain.get_memory_status()['total_runs'] == 0


def test_material_code_keeps_leading_zeroes_and_separator_codes_separate():
    db = MemoryDB()
    for code in ('01', '1', '01__bandit_X', 'A/B', ' A/B '):
        NestingAIBrain(db, code).record_feedback('TIRA_LONGA', 0, 70)
    assert NestingAIBrain(db, '01').get_memory_status()['total_runs'] == 1
    assert NestingAIBrain(db, 'A/B').get_memory_status()['total_runs'] == 2


def test_engine_uses_material_context_from_runtime_parameters():
    db = MemoryDB()
    with patch('cad.macro_engine.NestingAIBrain', wraps=NestingAIBrain) as brain:
        nest_ia_teste_engine(pieces(), 500, 500, db=db, target_count=2,
                             deterministic=True, dieproc_params={'material_code': '001'})
        assert any(call.kwargs.get('material_code') == '001' for call in brain.call_args_list)


def test_real_engine_records_only_active_material_and_respects_pause():
    db = MemoryDB()
    for code in ('001', '002'):
        result = nest_ia_teste_engine(
            pieces(), 500, 500, db=db, target_count=2,
            dieproc_params={'material_code': code},
        )
        assert result
        assert NestingAIBrain(db, code).get_memory_status()['total_runs'] == 1
    db.set_setting('ai_continuous_learning', '0')
    before = db.get_all_settings()
    nest_ia_teste_engine(pieces(), 500, 500, db=db, target_count=2,
                         dieproc_params={'material_code': '001'})
    # Usage counters continue to report calculations while learning is paused.
    assert {k: v for k, v in db.get_all_settings().items() if not k.endswith("__activity")} == {
        k: v for k, v in before.items() if not k.endswith("__activity")}
    assert NestingAIBrain(db, '001').get_memory_status()['total_runs'] == 1


def test_panel_switches_status_to_selected_material_and_disables_reset_without_code():
    from unittest.mock import Mock
    from ui.macro_panel import MacroPanel
    db = MemoryDB()
    train(NestingAIBrain(db, '001'))
    panel = MacroPanel.__new__(MacroPanel)
    panel.db = db
    panel.lbl_status = Mock()
    panel.btn_reset = Mock()
    panel.set_material_code('001')
    assert 'Material 001' in panel.lbl_status.config.call_args.kwargs['text']
    assert '1 execuções' in panel.lbl_status.config.call_args.kwargs['text']
    panel.set_material_code('002')
    assert '0 execuções' in panel.lbl_status.config.call_args.kwargs['text']
    panel.set_material_code(None)
    assert panel.btn_reset.config.call_args.kwargs['state'] == 'disabled'


def test_material_keys_fit_mysql_limit_even_with_long_unicode_codes():
    brain = NestingAIBrain(MemoryDB(), 'á' * 100)
    brain.record_feedback('COMPACTA_SOLA_CALCANHAR', 0, 70)
    assert all(len(key) <= 100 for key in brain.db.get_all_settings())
