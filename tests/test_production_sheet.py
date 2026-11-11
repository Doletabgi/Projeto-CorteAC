"""Regressões industriais e de paginação da ficha, sem gravar no banco real."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from PIL import ImageDraw
from ui.production_sheet import production_rows, render_sheet


def piece(**kw):
    return {**dict(name='Molde', size='38', shape_id=12, x=0, y=0,
                contour=[(0,0),(10,0),(10,10),(0,10)]), **kw}


def test_degrau_e_sobras_4c_2c_nao_usam_demanda_como_producao():
    shapes = [dict(id=12, name='Molde', size='38', pairs=7, shape_format='4x1')]
    pcs = [piece(), piece(), piece(y=60, pairs=200)]
    layout = dict(layers=4, tip_zone=(0,50,100,100),layers_tip=2)
    snapshot=deepcopy((pcs,shapes,layout))
    row=production_rows(pcs,shapes,layout)[0]
    assert (row['instances'],row['physical'],row['pairs'],row['factor'],row['equivalent_pairs']) == (3,10,5,2,10)
    assert row['demand']==7
    assert (pcs,shapes,layout)==snapshot
    # A sobra em placa própria herda 2 camadas, sem multiplicar por 4.
    assert production_rows([piece()], shapes, {'layers':2})[0]['pairs']==1


def test_impar_preserva_peca_sem_par_e_nao_soma_pares_de_moldes():
    rows=production_rows([piece(),piece(name='Outro',shape_id=13)],[],{'layers':1})
    assert [r['pairs'] for r in rows]==[0,0]
    assert [r['unpaired'] for r in rows]==[1,1]
    assert all(r['demand'] is None for r in rows)


def test_fator_6x1_e_formato_na_instancia():
    r=production_rows([piece(shape_format='6x1')],[],{'layers':4})[0]
    assert (r['physical'],r['pairs'],r['factor'],r['equivalent_pairs'])==(4,2,3,6)


def fixture(rows=1,orientation='portrait'):
    return SimpleNamespace(current_layout={},layout_layers=4,tip_zone=None,layers_tip=2,
        placed_pieces=[piece(name='Molde '+str(i),shape_id=i) for i in range(rows)],session_shapes=[],
        layout_data={'session_id':188,'order_id':22},orientation=orientation,
        current_layout_index=0,date_str='11/11/2026 12:00',active_user='Operador',
        material_name='MAT - Material',dimensions_str='1,38 x 2,98 m',gap_str='1,00 mm',
        refile_display_str='Sem refile',mat_area_str='4.11 sq.M.',used_area_str='0.01 sq.M.',
        yield_pct=0.24,sheet_w_mm=1380,sheet_h_mm=2980,trim_cut_line=None,
        get_display_layout_name=lambda:'lay0000',get_barcode_payload_and_label=lambda:('CAC:SESS:188','Sessão #188'))


def test_paginacao_sem_cortar_linhas_e_identificacao_em_todas_as_folhas():
    d=fixture(100)
    texts=[]
    original=ImageDraw.ImageDraw.text
    def record(draw,xy,value,*args,**kw):
        box=draw.textbbox(xy,str(value),font=kw.get('font'))
        assert box[2] <= draw._image.width-20
        assert box[3] <= draw._image.height-15
        texts.append(str(value))
        return original(draw,xy,value,*args,**kw)
    with patch.object(ImageDraw.ImageDraw,'text',record):
        pages=render_sheet(d,110)
    assert len(pages)>2
    assert sum(t=='FICHA DE PRODUÇÃO' for t in texts)==len(pages)
    for i in range(100):
        assert any(f'38: 2/? #{i}' == t for t in texts)
    assert all(p.width<p.height for p in pages)


def test_paisagem_e_nome_longo_nao_estouram_margem():
    d=fixture(2,'landscape');d.placed_pieces[0]['name']='ModeloMuitoLongo'*30
    assert all(p.width>p.height for p in render_sheet(d,100))


def test_moldes_com_mesmo_nome_e_tamanhos_distintos_preservam_demanda():
    shapes=[dict(name='Solado',size='38',pairs=11,shape_format='4x1'),dict(name='Solado',size='39',pairs=13,shape_format='6x1')]
    pcs=[piece(name='Solado',shape_id=None,size='38'),piece(name='Solado',shape_id=None,size='39')]
    rows=production_rows(pcs,shapes,{'layers':2})
    assert [(r['size'],r['demand'],r['factor']) for r in rows]==[('38',11,2),('39',13,3)]


def test_export_pdf_preserva_continuacoes_e_restaura_placa(tmp_path):
    from unittest.mock import MagicMock
    from ui.layout_print_dialog import LayoutPrintDialog
    from PIL import Image
    target=tmp_path/'ficha.pdf'
    d=MagicMock()
    d.layouts=[{},{}];d.current_layout_index=1;d.layout_name='lay0001'
    d.render_pillow_pages.side_effect=[[Image.new('RGB',(30,40),'white')]*2,[Image.new('RGB',(30,40),'white')]*3]
    with patch('ui.layout_print_dialog.messagebox.askyesnocancel',return_value=True),patch('ui.layout_print_dialog.filedialog.asksaveasfilename',return_value=str(target)),patch('ui.layout_print_dialog.messagebox.showinfo'),patch('ui.layout_print_dialog.messagebox.showerror') as errors:
        LayoutPrintDialog.save_as_pdf(d)
    assert target.exists()
    assert not errors.called
    assert d.load_layout_index.call_args.args==(1,)
    assert d.render_pillow_pages.call_count==2
    # O arquivo contém cinco páginas, incluindo as continuações de cada placa.
    assert target.read_bytes().count(b'/Type /Page\n')==5


def test_spool_usa_argumentos_sem_shell_e_inclui_continuacoes(tmp_path):
    from unittest.mock import MagicMock
    from ui.layout_print_dialog import LayoutPrintDialog
    import os
    d=MagicMock();d.layouts=[{}];d.layout_name='lay0000'
    first,second=MagicMock(),MagicMock();d.render_pillow_pages.return_value=[first,second]
    target=tmp_path/'ficha com espaços.pdf';fd=os.open(target,os.O_CREAT|os.O_RDWR)
    with patch('tempfile.mkstemp',return_value=(fd,str(target))),patch('sys.platform','linux'),patch('shutil.which',return_value='/usr/bin/lp'),patch('subprocess.run',return_value=SimpleNamespace(returncode=0)) as spool,patch('ui.layout_print_dialog.messagebox.showinfo'),patch('ui.layout_print_dialog.messagebox.showerror') as errors:
        LayoutPrintDialog.do_print(d)
    assert not errors.called
    assert first.save.call_args.kwargs['append_images']==[second]
    assert spool.call_args.args[0]==['lp',str(target)]
    assert not spool.call_args.kwargs.get('shell',False)


def test_preparacao_em_metros_preserva_precisao_sem_milimetros():
    d = fixture()
    d.sheet_w_mm, d.sheet_h_mm = 1370.37, 2823.14
    d.trim_cut_line = dict(enabled=True, orig_w=1380, orig_h=2980)
    render_sheet(d, 100)
    text = ' '.join(d.print_texts)
    assert 'Medidas de corte:' not in text
    assert 'Placa:' not in text
    assert 'Referência antes do refile: 1,38 × 2,98 m' in text
    assert 'Separar 4 folhas de 1,38 x 2,98 m.' in text
    assert ' mm' not in text


def test_modelos_ao_lado_do_mapa_ampliado_em_todas_as_continuacoes():
    d = fixture(100)
    pages = render_sheet(d, 110)
    assert len(d.print_regions) == len(pages)
    for region in d.print_regions:
        gx, gy, right, bottom = region['map']
        tx, ty, tr, tb = region['models']
        assert tx > right
        assert gy >= ty and gy - ty < 50
        assert bottom - gy > 215  # antes o desenho era limitado a 215 pontos
        assert bottom < 841.89 - 65
    assert 'MAPA DE CORTE' not in d.print_texts
    assert 'Proporcional, sem escala' not in d.print_texts


def test_resumo_lateral_destaca_pares_efetivos_da_ponta_e_fator():
    d = fixture()
    d.tip_zone = (0, 0, 100, 100)
    d.tip_mode = 'canto'
    d.placed_pieces[0]['shape_format'] = '4x1'
    render_sheet(d, 110)
    assert any('38: 1/?' in t for t in d.print_texts)
    assert any('Fator ×2 | Equiv.: 2 pares' in t for t in d.print_texts)
    assert 'Inst.' not in d.print_texts


def test_resumo_duas_linhas_com_total_efetivo_incluindo_ponta():
    d = fixture(2)
    d.tip_zone = (0, 50, 100, 100)
    d.tip_mode = 'faixa'
    d.placed_pieces[1]['y'] = 60
    render_sheet(d, 110)
    start = d.print_texts.index('RESUMO DESTA PLACA')
    end = d.print_texts.index('MODELOS E QUANTIDADES')
    assert d.print_texts[start+1:end] == [
        'Aproveitamento geométrico: 0.24%', 'Total de pares da placa: 3']


def test_quadro_compacto_agrupa_tamanhos_sem_alterar_fracoes():
    d = fixture()
    d.placed_pieces = [piece(name=f'Modelo_{size}a', size=f'{size}a', shape_id=size) for size in (36,37,38)]
    d.session_shapes = [dict(id=size,name=f'Modelo_{size}a',size=f'{size}a',pairs=101) for size in (36,37,38)]
    render_sheet(d, 110)
    assert d.print_texts.count('Modelo') == 1
    for size in (36,37,38):
        assert any(f'{size}: 2/101 #{size}' in text for text in d.print_texts)
    region = d.print_regions[0]['models']
    assert region[3]-region[1] < 100


def test_cabecalho_placa_n_de_total_da_sessao_no_lote():
    d = fixture()
    d.layouts = [dict(session_id=99),dict(session_id=188),dict(session_id=188)]
    d.current_layout_index = 1
    render_sheet(d,110)
    assert any('Placa 1 de 2' in t for t in d.print_texts)
    d.current_layout_index = 2
    render_sheet(d,110)
    assert any('Placa 2 de 2' in t for t in d.print_texts)
