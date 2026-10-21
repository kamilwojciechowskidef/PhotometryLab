"""Exercise the UI script's default demo flow without requiring Streamlit on CI.

This is a mock smoke test; it does not replace testing in a real browser.
"""
import runpy
import sys
import pytest
from contextlib import nullcontext
from types import ModuleType, SimpleNamespace


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
    stub.button = lambda *a, **k: False
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
    monkeypatch.setattr(database, 'load_stored_photometry',
                        lambda *a: load_photometry('same.ies', make_ies('Test', 'oval')))
    runpy.run_path('app.py', run_name='__main__')
    if unavailable:
        assert errors == ['Catalogue unavailable']
    else:
        ranking = next(table for table in tables if 'Candidate' in table.columns)
        assert ranking['Candidate'].tolist() == ['[DB 2] same.ies']
        assert not errors


def test_app_demo_flow(monkeypatch):
    stub = ModuleType('streamlit')
    stub.sidebar = nullcontext()
    noop = lambda *args, **kwargs: None
    for method in ['set_page_config', 'title', 'caption', 'write', 'header', 'divider',
                   'warning', 'info', 'error', 'success', 'dataframe', 'download_button', 'plotly_chart', 'subheader']:
        setattr(stub, method, noop)
    stub.file_uploader = lambda *a, **k: []
    stub.checkbox = lambda *a, **k: False if k.get('key') in ('browse_catalogue', 'browse_sources') else True
    stub.button = lambda *a, **k: False
    stub.expander = lambda *a, **k: nullcontext()
    stub.tabs = lambda labels: [nullcontext() for _ in labels]
    stub.columns = lambda count: [SimpleNamespace(metric=noop) for _ in range(count)]
    stub.metric = noop
    stub.selectbox = lambda label, options, **k: list(options)[0]
    stub.slider = lambda *args, **kwargs: kwargs['value']
    stub.stop = lambda: (_ for _ in ()).throw(AssertionError('Unexpected empty demo'))
    monkeypatch.setitem(sys.modules, 'streamlit', stub)
    runpy.run_path('app.py', run_name='__main__')


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
    stub.button = lambda *a, **k: True
    stub.expander = lambda *a, **k: nullcontext()
    stub.tabs = lambda labels: [nullcontext() for _ in labels]
    stub.columns = lambda count: [SimpleNamespace(metric=noop) for _ in range(count)]
    stub.metric = noop
    stub.selectbox = lambda label, options, **k: list(options)[0]
    stub.slider = lambda *args, **kwargs: kwargs['value']
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
