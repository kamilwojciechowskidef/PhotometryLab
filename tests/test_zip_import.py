from photolab import zip_import
from photolab.bulk import BatchFile


def test_directory_import_processes_each_archive_separately(tmp_path, monkeypatch):
    (tmp_path / 'a.zip').write_bytes(b'a')
    (tmp_path / 'b.zip').write_bytes(b'b')
    calls = []
    monkeypatch.setattr(zip_import, 'prepare_zip', lambda data: [BatchFile('x.ies', data)])
    def store(url, files, root, description, version):
        calls.append((files[0].content, description))
        return 1, [{}]
    monkeypatch.setattr(zip_import, 'import_batch', store)
    zip_import.import_directory(tmp_path, 'unused', tmp_path, 'test source')
    assert {data for data, _ in calls} == {b'a', b'b'}
    assert all('test source / ' in description for _, description in calls)


def test_directory_import_includes_producer_subfolders(tmp_path, monkeypatch):
    for name in ('Brand A', 'Brand B'):
        folder = tmp_path / name
        folder.mkdir()
        (folder / 'page.ZIP').write_bytes(name.encode())
    calls = []
    monkeypatch.setattr(zip_import, 'prepare_zip', lambda data: [BatchFile('x.ies', data)])
    def store(url, files, root, description, version):
        calls.append(description)
        return 1, [{}]
    monkeypatch.setattr(zip_import, 'import_batch', store)
    zip_import.import_directory(tmp_path, 'unused', tmp_path, 'source')
    assert calls == ['source / Brand A/page.ZIP', 'source / Brand B/page.ZIP']
