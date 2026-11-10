from types import SimpleNamespace

import pytest

from photolab import bulk_ui


@pytest.mark.parametrize('outcome,expected', [('new', 'success'), ('rejected', 'warning')])
def test_zip_save_button_reports_success_only_when_archive_has_no_errors(monkeypatch, tmp_path, outcome, expected):
    messages, buttons, calls = [], [], []
    upload = SimpleNamespace(name='source.zip', size=3, getvalue=lambda: b'zip')
    stub = SimpleNamespace(
        subheader=lambda *a, **k: None,
        caption=lambda *a, **k: None,
        file_uploader=lambda label, **k: [upload] if k.get('key') == 'batch_zips' else [],
        text_input=lambda *a, **k: 'source',
        button=lambda label, **k: buttons.append((label, k)) or True,
        write=lambda *a, **k: None,
        dataframe=lambda *a, **k: None,
        download_button=lambda *a, **k: None,
        success=lambda message: messages.append(('success', message)),
        warning=lambda message: messages.append(('warning', message)),
        error=lambda message: messages.append(('error', message)),
        checkbox=lambda *a, **k: False,
    )
    monkeypatch.setattr(bulk_ui, 'st', stub)
    monkeypatch.setattr(bulk_ui, 'database_url', lambda: 'unused')
    monkeypatch.setattr(bulk_ui, 'artifact_root', lambda: tmp_path)
    monkeypatch.setattr(bulk_ui, 'invalidate_catalogue_cache', lambda: calls.append('cache cleared'))
    monkeypatch.setattr(bulk_ui, 'import_product_zip', lambda *args: (
        7, [{'outcome': outcome}], [object()], []))
    bulk_ui.render_bulk_import('test')
    assert buttons[0][0] == 'Import and save to catalogue'
    assert buttons[0][1]['type'] == 'primary'
    assert [kind for kind, _ in messages] == [expected]
    assert calls == ['cache cleared']


def test_browser_can_import_multiple_archives_above_previous_100mb_limit(monkeypatch, tmp_path):
    uploads = [SimpleNamespace(name=f'{i}.zip', size=10_000_000, getvalue=lambda: b'zip') for i in range(22)]
    calls, notices = [], []
    stub = SimpleNamespace(
        subheader=lambda *a, **k: None, caption=lambda *a, **k: None,
        file_uploader=lambda label, **k: uploads if k.get('key') == 'batch_zips' else [],
        text_input=lambda *a, **k: 'source', button=lambda *a, **k: True,
        write=lambda *a, **k: None, dataframe=lambda *a, **k: None,
        download_button=lambda *a, **k: None, success=lambda message: notices.append(message),
        warning=lambda message: pytest.fail(message), error=lambda message: pytest.fail(message),
        checkbox=lambda *a, **k: False,
    )
    monkeypatch.setattr(bulk_ui, 'st', stub)
    monkeypatch.setattr(bulk_ui, 'database_url', lambda: 'unused')
    monkeypatch.setattr(bulk_ui, 'artifact_root', lambda: tmp_path)
    monkeypatch.setattr(bulk_ui, 'invalidate_catalogue_cache', lambda: None)
    monkeypatch.setattr(bulk_ui, 'import_product_zip', lambda *args: (
        calls.append(args[3]) or len(calls), [{'outcome': 'new'}], [object()], []))
    bulk_ui.render_bulk_import('test')
    assert len(calls) == 22
    assert len(notices) == 1
