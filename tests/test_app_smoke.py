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
                   'warning', 'info', 'dataframe', 'download_button', 'plotly_chart', 'subheader']:
        setattr(stub, method, noop)
    stub.file_uploader = lambda *a, **k: []
    stub.checkbox = lambda *a, **k: True
    stub.expander = lambda *a, **k: nullcontext()
    stub.tabs = lambda labels: [nullcontext() for _ in labels]
    stub.columns = lambda count: [SimpleNamespace(metric=noop) for _ in range(count)]
    stub.metric = noop
    stub.selectbox = lambda label, options, **k: list(options)[0]
    stub.slider = lambda *args, **kwargs: kwargs['value']
    stub.stop = lambda: (_ for _ in ()).throw(AssertionError('Unexpected empty demo'))
    monkeypatch.setitem(sys.modules, 'streamlit', stub)
    runpy.run_path('app.py', run_name='__main__')
