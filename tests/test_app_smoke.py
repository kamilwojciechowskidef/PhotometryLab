"""Exercise the UI script's default demo flow without requiring Streamlit on CI.

This is a mock smoke test; it does not replace testing in a real browser.
"""
import runpy
import sys
import pytest
from contextlib import nullcontext
from types import ModuleType, SimpleNamespace


@pytest.fixture(autouse=True)
def catalogue_statistics_without_database(monkeypatch):
    import photolab.catalogue_controls as controls
    monkeypatch.setattr(controls, 'get_count', lambda *args, **kwargs: 100)
    monkeypatch.setattr(controls, 'get_brands', lambda *args, **kwargs: ('Example',))


@pytest.mark.parametrize('unavailable', [False, True])
def test_catalogue_comparison_with_same_filenames(monkeypatch, unavailable):
    from photolab.demo import make_ies
    from photolab.parsers import load_photometry
    import photolab.database as database
    stub = ModuleType('streamlit')
    noop = lambda *a, **k: None
    errors, tables = [], []
    for method in ['set_page_config', 'title', 'caption', 'write', 'header', 'divider',
                   'warning', 'info', 'success', 'download_button', 'plotly_chart', 'subheader']:
        setattr(stub, method, noop)
    stub.error = errors.append
    stub.dataframe = lambda data, **k: tables.append(data)
    stub.sidebar = nullcontext()
    stub.file_uploader = lambda *a, **k: []
    stub.checkbox = lambda *a, **k: k.get('key') == 'browse_catalogue'
    stub.button = lambda label, **k: label == 'Add selected to comparison'
    stub.text_input = lambda *a, **k: ''
    stub.number_input = lambda *a, **k: 1
    stub.multiselect = lambda label, options, **k: options
    stub.expander = lambda *a, **k: nullcontext()
    stub.tabs = lambda labels: [nullcontext() for _ in labels]
    stub.columns = lambda count: [SimpleNamespace(metric=noop) for _ in range(count)]
    stub.selectbox = lambda label, options, **k: list(options)[0]
    stub.slider = lambda *a, **k: k['value']
    monkeypatch.setitem(sys.modules, 'streamlit', stub)
    monkeypatch.setattr(database, 'database_url', lambda: 'unused')
    def listing(*a, **k):
        if unavailable:
            raise database.DatabaseError('Catalogue unavailable')
        return [dict(file_id=i, filename='same.ies', manufacturer='Example', model='Lamp',
                     format='IES', sha256=str(i) * 64) for i in (1, 2)]
    monkeypatch.setattr(database, 'list_catalogue', listing)
    monkeypatch.setattr(database, 'load_stored_photometries',
                        lambda url, ids: {i: load_photometry('same.ies', make_ies('Test', 'oval')) for i in ids})
    runpy.run_path('app.py', run_name='__main__')
    if unavailable:
        assert errors == ['Catalogue unavailable']
    else:
        ranking = next(table for table in tables if 'Candidate' in table.columns)
        assert ranking['Candidate'].tolist() == ['[DB 2] same.ies']
        assert ranking['Brand'].tolist() == ['SYNTHETIC SAMPLES / NOT A MANUFACTURER']
        assert ranking['Catalogue number'].tolist() == ['Test']
        assert not errors


@pytest.mark.parametrize('include_rejected', [False, True])
def test_app_demo_flow(monkeypatch, include_rejected):
    import pyarrow as pa
    quality_tables = []
    def check_arrow(data, **kwargs):
        arrow = pa.Table.from_pandas(data, preserve_index=False)
        if 'Header flux [lm]' in data.columns:
            quality_tables.append(data)
            assert pa.types.is_floating(arrow.schema.field('Header flux [lm]').type)
            assert pa.types.is_integer(arrow.schema.field('C planes').type)
            assert data['Header flux [lm]'].isna().any()
            assert data['Header flux [lm]'].notna().any()
            if include_rejected:
                assert data.loc[data['File'] == 'damaged.ies', 'C planes'].isna().all()

    stub = ModuleType('streamlit')
    stub.sidebar = nullcontext()
    noop = lambda *args, **kwargs: None
    for method in ['set_page_config', 'title', 'caption', 'write', 'header', 'divider',
                   'warning', 'info', 'error', 'success', 'dataframe', 'download_button', 'plotly_chart', 'subheader']:
        setattr(stub, method, noop)
    stub.dataframe = check_arrow
    stub.file_uploader = lambda *a, **k: ([SimpleNamespace(name='damaged.ies', getvalue=lambda: b'bad')]
                                        if include_rejected else [])
    stub.checkbox = lambda *a, **k: False if k.get('key') in ('browse_catalogue', 'browse_sources', 'open_bulk', 'catalogue_assets') else True
    stub.button = lambda *a, **k: False
    stub.expander = lambda *a, **k: nullcontext()
    stub.tabs = lambda labels: [nullcontext() for _ in labels]
    stub.columns = lambda count: [SimpleNamespace(metric=noop) for _ in range(count)]
    stub.metric = noop
    stub.selectbox = lambda label, options, **k: list(options)[0]
    stub.slider = lambda *args, **kwargs: kwargs['value']
    stub.number_input = lambda *args, **kwargs: kwargs.get('value', 1)
    stub.stop = lambda: (_ for _ in ()).throw(AssertionError('Unexpected empty demo'))
    monkeypatch.setitem(sys.modules, 'streamlit', stub)
    runpy.run_path('app.py', run_name='__main__')
    assert len(quality_tables) == 1


def test_app_exports_quality_report_for_rejected_file(monkeypatch):
    stub = ModuleType('streamlit')
    stub.sidebar = nullcontext()
    noop = lambda *args, **kwargs: None
    downloaded = []
    for method in ['set_page_config', 'title', 'caption', 'write', 'header', 'divider',
                   'warning', 'info', 'error', 'success', 'dataframe', 'plotly_chart', 'subheader']:
        setattr(stub, method, noop)
    stub.download_button = lambda *args, **kwargs: downloaded.append(kwargs.get('file_name'))
    stub.file_uploader = lambda *a, **k: [SimpleNamespace(name='damaged.ies', getvalue=lambda: b'not an ies')]
    stub.checkbox = lambda *a, **k: False
    stub.button = lambda *a, **k: False
    stub.expander = lambda *a, **k: nullcontext()
    stub.tabs = lambda labels: [nullcontext() for _ in labels]
    stub.columns = lambda count: [SimpleNamespace(metric=noop) for _ in range(count)]
    stub.metric = noop
    stub.selectbox = lambda label, options, **k: list(options)[0]
    stub.slider = lambda *args, **kwargs: kwargs['value']
    stub.number_input = lambda *args, **kwargs: kwargs.get('value', 1)
    stub.stop = lambda: (_ for _ in ()).throw(AssertionError('The application must not stop the quality report'))
    monkeypatch.setitem(sys.modules, 'streamlit', stub)
    runpy.run_path('app.py', run_name='__main__')
    assert 'import_quality_report.csv' in downloaded


def test_app_saves_uploaded_file_to_catalogue(monkeypatch):
    from photolab.demo import make_ies
    import photolab.database as database

    stub = ModuleType('streamlit')
    stub.sidebar = nullcontext()
    notices = []
    noop = lambda *args, **kwargs: None
    for method in ['set_page_config', 'title', 'caption', 'write', 'header', 'divider',
                   'warning', 'info', 'error', 'dataframe', 'download_button', 'plotly_chart', 'subheader']:
        setattr(stub, method, noop)
    stub.success = lambda message: notices.append(message)
    stub.file_uploader = lambda *a, **k: [
        SimpleNamespace(name='fixture.ies', getvalue=lambda: make_ies('Fixture', 'narrow')),
    ]
    stub.checkbox = lambda *a, **k: False
    stub.button = lambda label, **k: label == 'Save uploaded files to PostgreSQL'
    stub.expander = lambda *a, **k: nullcontext()
    stub.tabs = lambda labels: [nullcontext() for _ in labels]
    stub.columns = lambda count: [SimpleNamespace(metric=noop) for _ in range(count)]
    stub.metric = noop
    stub.selectbox = lambda label, options, **k: list(options)[0]
    stub.slider = lambda *args, **kwargs: kwargs['value']
    stub.number_input = lambda *args, **kwargs: kwargs.get('value', 1)
    stub.stop = lambda: (_ for _ in ()).throw(AssertionError('Unexpected stop'))
    registered = []
    monkeypatch.setattr(database, 'database_url', lambda: 'postgresql://test')
    monkeypatch.setattr(database, 'register_file_import',
                        lambda *args, **kwargs: registered.append(kwargs) or SimpleNamespace(duplicate=False))
    monkeypatch.setitem(sys.modules, 'streamlit', stub)

    runpy.run_path('app.py', run_name='__main__')

    assert registered[0]['original_filename'] == 'fixture.ies'
    assert registered[0]['source_description'] == 'Streamlit upload'
    assert registered[0]['photometry'].filename == 'fixture.ies'
    assert notices == ['Added 1 new file(s) to the catalogue.']


def test_app_searches_indexed_catalogue_with_one_uploaded_reference(monkeypatch):
    from photolab.demo import make_ies
    import photolab.indexing as indexing

    stub = ModuleType('streamlit')
    stub.sidebar = nullcontext()
    calls = []
    noop = lambda *args, **kwargs: None
    for method in ['set_page_config', 'title', 'caption', 'write', 'header', 'divider',
                   'warning', 'error', 'success', 'dataframe', 'download_button', 'plotly_chart', 'subheader']:
        setattr(stub, method, noop)
    stub.info = lambda message: calls.append(('info', message))
    stub.file_uploader = lambda *a, **k: [
        SimpleNamespace(name='reference.ies', getvalue=lambda: make_ies('Reference', 'narrow')),
    ]
    stub.checkbox = lambda *a, **k: False
    stub.button = lambda label, **k: label == 'Search indexed catalogue'
    stub.expander = lambda *a, **k: nullcontext()
    stub.tabs = lambda labels: [nullcontext() for _ in labels]
    stub.columns = lambda count: [SimpleNamespace(metric=noop) for _ in range(count)]
    stub.metric = noop
    stub.selectbox = lambda label, options, **k: list(options)[0]
    stub.slider = lambda *args, **kwargs: kwargs['value']
    stub.number_input = lambda *args, **kwargs: kwargs.get('value', 1)
    monkeypatch.setitem(sys.modules, 'streamlit', stub)
    monkeypatch.setattr(indexing, 'rank_catalogue',
                        lambda *args, **kwargs: calls.append(('search', args[1].filename)) or
                        SimpleNamespace(candidates_examined=0, results=[]))

    runpy.run_path('app.py', run_name='__main__')

    assert ('search', 'reference.ies') in calls
    assert any('No indexed candidates' in message for kind, message in calls if kind == 'info')


def test_saved_selection_persists_between_pages_and_becomes_reference(monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    from photolab.demo import make_ies
    from photolab.parsers import load_photometry
    import photolab.database as database

    monkeypatch.setattr(database, 'database_url', lambda: 'unused')
    def listing(url, *, offset=0, **kwargs):
        number = 10 if offset == 0 else 20
        return [dict(file_id=number, filename=f'{number}.ies', manufacturer='Example',
                     model=f'Model {number}', catalogue_number=f'CAT-{number}',
                     format='IES', sha256=f'{number:064x}')]
    monkeypatch.setattr(database, 'list_catalogue', listing)
    monkeypatch.setattr(database, 'load_stored_photometries',
                        lambda url, ids: {i: load_photometry(f'{i}.ies', make_ies(f'CAT-{i}', 'narrow'))
                                          for i in ids})

    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py').run(timeout=30)
    app.checkbox(key='browse_catalogue').check().run(timeout=30)
    app.multiselect[0].select(app.multiselect[0].options[0]).run(timeout=30)
    app.button(key='add_catalogue_selection').click().run(timeout=30)
    assert app.selectbox(key='ref_file').value.startswith('[DB 10]')
    assert list(app.session_state['selected_catalogue_files']) == [10]
    app.selectbox(key='sidebar_page_None__1').select(2).run(timeout=30)
    assert list(app.session_state['selected_catalogue_files']) == [10]
    app.multiselect[0].select(app.multiselect[0].options[0]).run(timeout=30)
    app.button(key='add_catalogue_selection').click().run(timeout=30)
    assert list(app.session_state['selected_catalogue_files']) == [10, 20]
    assert app.selectbox(key='ref_file').value.startswith('[DB 20]')
    app.checkbox(key='browse_catalogue').uncheck().run(timeout=30)
    assert list(app.session_state['selected_catalogue_files']) == [10, 20]
    assert not app.exception
