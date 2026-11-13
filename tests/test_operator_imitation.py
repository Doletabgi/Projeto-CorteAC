from copy import deepcopy
from unittest.mock import patch

from cad.ai_learner import NestingAIBrain
from cad.macro_engine import nest_ia_teste_engine
from cad.geometry import transform_contour, polygon_bbox, polygons_collide
from test_material_learning import MemoryDB

SCRIPT = 'CLUSTER PAIR angles(0, 90) sweep(0, 0, 1)\nGRAVITY VECTOR(0, 0) steps(1)'
MARGINS = dict(left=10, right=10, top=10, bottom=10)


def samples():
    contour = [dict(x=0, y=0), dict(x=20, y=0), dict(x=20, y=10), dict(x=0, y=10)]
    return [dict(name='A', contour=deepcopy(contour), target_pieces=1, x=10, y=10, rotation=0),
            dict(name='B', contour=deepcopy(contour), target_pieces=1, x=31, y=10, rotation=0)]


def run(db, code='001', shapes=None, **kwargs):
    return nest_ia_teste_engine(shapes or samples(), 150, 100, target_count=2, db=db,
                                macro_script=SCRIPT, dieproc_params=dict(material_code=code),
                                deterministic=True, margins=MARGINS, gap_mm=1, **kwargs)


def boxes(result):
    return [polygon_bbox(transform_contour(p['contour'], p['x'], p['y'], p['rotation'])) for p in result]


def area(result):
    b = boxes(result)
    return (max(x[2] for x in b) - min(x[0] for x in b)) * (max(x[3] for x in b) - min(x[1] for x in b))


def test_saved_manual_example_changes_next_macro_and_improves_footprint():
    db = MemoryDB()
    baseline = run(db)
    assert baseline[1]['rotation'] == 90
    assert NestingAIBrain(db, '001').learn_from_operator_save(samples(), 150, 100) == 1
    learned = run(db)
    assert len(learned) == len(baseline) == 2
    assert learned[1]['rotation'] == 0
    assert area(learned) < area(baseline)
    assert run(db, '002') == baseline
    # Pausing prevents new examples, while existing knowledge remains usable.
    db.set_setting('ai_continuous_learning', '0')
    assert run(db) == learned


def test_reversed_names_and_rotated_centers_are_preserved():
    db = MemoryDB()
    manual = samples()
    manual[0].update(name='Z', rotation=90, x=30, y=10)
    manual[1].update(name='A', rotation=180, x=60, y=20)
    brain = NestingAIBrain(db, '001')
    assert brain.learn_from_operator_save(manual, 150, 100) == 1
    h = brain.get_learned_habits()[0]
    assert h['source'][0] == 'Z'
    b = boxes(manual)
    assert h['dx'] == (b[1][0] + b[1][2] - b[0][0] - b[0][2]) / 2
    assert h['dy'] == (b[1][1] + b[1][3] - b[0][1] - b[0][3]) / 2


def test_colliding_outside_or_mirrored_manual_pairs_are_not_recorded():
    for update in (dict(x=15), dict(x=-1), dict(is_mirrored=True)):
        db = MemoryDB()
        manual = samples()
        manual[1].update(update)
        assert NestingAIBrain(db, '001').learn_from_operator_save(manual, 150, 100) == 0


def test_learned_candidates_reject_gap_violations_bounds_and_forbidden_angles():
    for changes in (dict(dx=20), dict(dy=100), dict(rot2=45)):
        db = MemoryDB()
        baseline = run(db)
        brain = NestingAIBrain(db, '001')
        brain.learn_from_operator_save(samples(), 150, 100)
        h = brain.get_learned_habits()[0]
        h.update(changes)
        with patch.object(NestingAIBrain, 'get_learned_habits', return_value=[h]):
            assert run(db) == baseline


def test_different_geometry_is_not_matched_and_failures_do_not_claim_success():
    db = MemoryDB()
    brain = NestingAIBrain(db, '001')
    brain.learn_from_operator_save(samples(), 150, 100)
    shapes = samples()
    shapes[1]['contour'][1]['x'] = 22
    assert run(db, shapes=shapes) == run(MemoryDB(), shapes=shapes)
    with patch.object(db, 'set_setting', side_effect=RuntimeError('disk full')):
        assert brain.learn_from_operator_save(samples(), 150, 100) == 0


def test_candidate_is_checked_against_every_other_piece():
    db = MemoryDB()
    brain = NestingAIBrain(db, '001')
    brain.learn_from_operator_save(samples(), 150, 100)
    shapes = samples()
    third = deepcopy(shapes[0])
    third['name'] = 'C'
    shapes.append(third)
    result = nest_ia_teste_engine(shapes, 150, 100, target_count=3, db=db,
                                  macro_script=SCRIPT, dieproc_params=dict(material_code='001'),
                                  deterministic=True, margins=MARGINS, gap_mm=1)
    assert len(result) == 3
    # The saved position for B would overlap C in this different job.
    assert next(p for p in result if p['name'] == 'B')['rotation'] == 90
    polys = [transform_contour(p['contour'], p['x'], p['y'], p['rotation']) for p in result]
    assert all(not polygons_collide(a, b, gap=1) for i, a in enumerate(polys) for b in polys[i+1:])


def test_visible_history_distinguishes_learning_consultation_and_actual_changes():
    db = MemoryDB()
    brain = NestingAIBrain(db, '001')
    brain.learn_from_operator_save(samples(), 150, 100)
    rows = NestingAIBrain.material_activity(db)
    assert rows[0]['material_code'] == '001'
    assert rows[0]['habits_count'] == 1
    assert rows[0].get('macro_runs', 0) == 0
    run(db)
    run(db, '002')
    rows = {r['material_code']: r for r in NestingAIBrain.material_activity(db)}
    assert rows['001']['macro_runs'] == rows['001']['applied_runs'] == 1
    assert rows['002']['macro_runs'] == 1
    assert rows['002']['applied_runs'] == rows['002']['habits_count'] == 0
    assert rows['002']['last_result'] == 'Sem exemplos salvos'
    # Replay an already identical baseline: consult, but do not claim an adjustment.
    from cad.macro_engine import OmniNestMacroEngine, MacroCompiler
    placed = deepcopy(samples())
    for index, piece in enumerate(placed, 1):
        piece['id'] = index
        piece['poly'] = transform_contour(piece['contour'], piece['x'], piece['y'], piece['rotation'])
        piece['bbox'] = polygon_bbox(piece['poly'])
    engine = OmniNestMacroEngine(db)
    engine.ai_brain = brain
    applied = engine._apply_operator_habits(placed, MacroCompiler.compile(SCRIPT), 150, 100, MARGINS, 1)
    assert applied == 0
    brain.record_activity(applied=applied)
    row = next(r for r in NestingAIBrain.material_activity(db) if r['material_code'] == '001')
    assert row['macro_runs'] == 2
    assert row['applied_runs'] == 1
    assert row['last_result'] == 'Consultou; sem ajuste aplicável'
    brain.reset_learning()
    assert [r['material_code'] for r in NestingAIBrain.material_activity(db)] == ['002']


def test_old_material_scoped_history_is_visible_without_inventing_usage():
    db = MemoryDB()
    brain = NestingAIBrain(db, '001')
    brain.learn_from_operator_save(samples(), 150, 100)
    db.conn.execute('DELETE FROM settings WHERE key=?', (brain._key('activity'),))
    db.get_materials = lambda: [dict(code='001')]
    row = NestingAIBrain.material_activity(db)[0]
    assert row['habits_count'] == 1
    assert 'macro_runs' not in row
