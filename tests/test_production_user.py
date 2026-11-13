"""O responsável pertence à produção, não ao usuário que imprime depois."""
from database import DatabaseManager
from cad.lay_parser import LayoutData
from test_production_sheet import fixture
from ui.production_sheet import render_sheet


def test_responsavel_persistido_nao_muda_ao_trocar_ou_excluir_usuario():
    db = DatabaseManager(':memory:')
    db.add_user('Ana')
    sid = db.create_session(name='Produção Ana')
    layouts = [{'name': 'lay0000', 'pieces': [], 'layers': 2}]
    db.save_session_layouts(sid, layouts)
    assert layouts[0]['production_user'] == 'Ana'
    db.add_user('Bruno', set_active=True)
    db.delete_user('Ana')
    saved = db.get_session_layouts(sid)[0]
    assert saved['production_user'] == 'Ana'
    dialog = fixture(100)
    dialog.current_layout = saved
    dialog.active_user = 'Bruno'
    pages = render_sheet(dialog, 72)
    assert dialog.print_texts.count('Usuário responsável pela produção: Ana') == len(pages)
    assert not any('Bruno' in text for text in dialog.print_texts)


def test_sem_responsavel_nao_atribui_producao_antiga_ao_usuario_atual():
    dialog = fixture()
    dialog.active_user = 'Bruno'
    render_sheet(dialog, 72)
    assert 'Usuário responsável pela produção: não informado' in dialog.print_texts
    assert not any('Bruno' in text for text in dialog.print_texts)


def test_save_layout_tambem_registra_usuario():
    db = DatabaseManager(':memory:')
    db.add_user('Ana')
    sid = db.create_session(name='Produção')
    lid = db.save_layout(sid, LayoutData())
    assert db.get_layout_by_id(lid)['production_user'] == 'Ana'


def test_migracao_de_banco_existente_e_idempotente(tmp_path):
    path = tmp_path / 'producao.db'
    db = DatabaseManager(path)
    sid = db.create_session(name='Legada')
    db.save_session_layouts(sid, [{'pieces': []}])
    with db.get_connection() as conn:
        conn.cursor().execute('ALTER TABLE layouts DROP COLUMN production_user')
        conn.commit()
    migrated = DatabaseManager(path)
    migrated.init_db()
    assert migrated.get_session_layouts(sid)[0]['production_user'] == ''
