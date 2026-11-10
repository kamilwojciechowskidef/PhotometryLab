from photolab import zip_import


def test_directory_import_processes_each_archive_separately(tmp_path, monkeypatch):
    (tmp_path / 'a.zip').write_bytes(b'a')
    (tmp_path / 'b.zip').write_bytes(b'b')
    calls = []
    def store(url, content, root, description, version):
        calls.append((content, description))
        return 1, [{}], [object()], []
    monkeypatch.setattr(zip_import, 'import_product_zip', store)
    zip_import.import_directory(tmp_path, 'unused', tmp_path, 'test source')
    assert {data for data, _ in calls} == {b'a', b'b'}
    assert all('test source / ' in description for _, description in calls)
