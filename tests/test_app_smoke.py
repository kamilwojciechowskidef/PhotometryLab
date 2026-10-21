"""Exercise the UI script's default demo flow without requiring Streamlit on CI.

This is a mock smoke test; it does not replace testing in a real browser.
"""
import runpy
import sys
from contextlib import nullcontext
from types import ModuleType, SimpleNamespace


def test_app_demo_flow(monkeypatch):
    stub = ModuleType('streamlit')
    stub.sidebar = nullcontext()
    noop = lambda *args, **kwargs: None
    for method in ['set_page_config', 'title', 'caption', 'write', 'header', 'divider',
                   'warning', 'info', 'error', 'success', 'dataframe', 'download_button', 'plotly_chart', 'subheader']:
        setattr(stub, method, noop)
    stub.file_uploader = lambda *a, **k: []
    stub.checkbox = lambda *a, **k: True
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
    assert notices == ['Added 1 new file(s) to the catalogue.']
