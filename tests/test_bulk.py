from io import BytesIO
from zipfile import ZipFile, ZipInfo
from types import SimpleNamespace

import pytest

from photolab import bulk
from photolab.demo import make_ies


def zipped(entries):
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


def test_zip_preserves_bytes_and_reports_unsupported_entries():
    data = make_ies('Test', 'oval')
    result = bulk.prepare_zip(zipped([('folder/a.ies', data), ('notes.txt', b'notes')]))
    assert result[0].content == data
    assert result[0].name == 'folder/a.ies'
    assert result[1].content is None and result[1].error


@pytest.mark.parametrize('name', ['../a.ies', '/a.ies', 'C:/a.ies', 'folder\\a.ies'])
def test_zip_rejects_unsafe_paths(name):
    # Construct portable ZIP headers, then put the exact untrusted name into
    # both headers. ZipInfo would normalize backslashes when writing on Windows.
    portable = name.replace('\\', '/')
    content = zipped([(portable, b'x')])
    content = content.replace(portable.encode('ascii'), name.encode('ascii'))
    with ZipFile(BytesIO(content)) as archive:
        assert archive.infolist()[0].orig_filename == name
    with pytest.raises(ValueError, match='Unsafe'):
        bulk.prepare_zip(content)


def test_zip_rejects_null_in_original_header():
    content = zipped([('badX.ies', b'x')]).replace(b'badX.ies', b'bad\x00.ies')
    with pytest.raises(ValueError, match='Unsafe'):
        bulk.prepare_zip(content)


def test_zip_rejects_symlink():
    entry = ZipInfo('link.ies')
    entry.external_attr = 0o120777 << 16
    with pytest.raises(ValueError, match='symbolic'):
        bulk.prepare_zip(zipped([(entry, b'target')]))


def test_limits_and_duplicate_names(monkeypatch):
    monkeypatch.setattr(bulk, 'MAX_FILE_BYTES', 3)
    assert bulk.prepare_zip(zipped([('large.ies', b'1234')]))[0].error
    with pytest.raises(ValueError, match='Duplicate'):
        bulk.prepare_files([('a.ies', b'1'), ('a.ies', b'2')])
    monkeypatch.setattr(bulk, 'MAX_TOTAL_BYTES', 2)
    with pytest.raises(ValueError, match='total'):
        bulk.prepare_files([('a.ies', b'123')])


def test_batch_continues_after_file_error_and_uses_shared_batch(monkeypatch, tmp_path):
    calls, reports, progress = [], [], []
    monkeypatch.setattr(bulk, 'create_batch', lambda *args: 42)
    monkeypatch.setattr(bulk, 'update_batch', lambda url, key, rows, finished: reports.append((list(rows), finished)))
    def register(url, **kwargs):
        calls.append(kwargs)
        if kwargs['original_filename'] == 'fail.ies':
            raise bulk.DatabaseError('offline')
        return SimpleNamespace(file_id=5, duplicate=kwargs['original_filename'] == 'copy.ies')
    monkeypatch.setattr(bulk, 'register_file_import', register)
    valid = make_ies('Test', 'oval')
    files = bulk.prepare_files([('a.ies', valid), ('fail.ies', valid), ('copy.ies', valid), ('bad.ies', b'bad')])
    key, rows = bulk.import_batch('unused', files, tmp_path, 'synthetic tests', 'test',
                                  lambda done, total: progress.append((done, total)))
    assert key == 42
    assert [r['outcome'] for r in rows] == ['new', 'error', 'duplicate', 'rejected']
    assert all(c['batch_id'] == 42 for c in calls)
    assert calls[-1]['photometry'] is None
    assert reports[-1][1] is True
    assert progress[-1] == (4, 4)


def test_report_failure_stops_batch(monkeypatch, tmp_path):
    monkeypatch.setattr(bulk, 'create_batch', lambda *args: 42)
    def fail(*args, **kwargs):
        raise bulk.DatabaseError('report unavailable')
    monkeypatch.setattr(bulk, 'update_batch', fail)
    with pytest.raises(bulk.DatabaseError):
        bulk.import_batch('unused', [bulk.BatchFile('note.txt', None, 'unsupported')], tmp_path, 'test', 'test')
