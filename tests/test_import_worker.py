from io import BytesIO
from zipfile import ZipFile

import pytest

from photolab import import_worker


def zip_bytes():
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('fixture.ies', b'photometry')
        archive.writestr('fixture.jpg', b'image')
        archive.writestr('fixture.json', b'{}')
    return stream.getvalue()


def test_worker_resumes_and_retries_failed_archives(tmp_path, monkeypatch):
    source = tmp_path / 'source' / 'producer'
    source.mkdir(parents=True)
    (source / 'a.zip').write_bytes(zip_bytes())
    (source / 'b.zip').write_bytes(b'broken')
    calls = []
    monkeypatch.setattr(import_worker, 'import_batch',
                        lambda url, files, root, description, version: (calls.append(description) or 42, [{'outcome': 'new'}]))
    monkeypatch.setattr(import_worker, 'save_assets', lambda *args: None)
    args = (source.parent, 'database', tmp_path / 'artifacts', 'source', tmp_path / 'state.sqlite3')
    assert import_worker.run(*args) == (1, 1)
    assert import_worker.run(*args) == (0, 1)
    assert len(calls) == 1
    (source / 'b.zip').write_bytes(zip_bytes())
    assert import_worker.run(*args) == (1, 0)
    assert len(calls) == 2
    with pytest.raises(ValueError, match='different source'):
        import_worker.run(source.parent, 'other database', *args[2:])


def test_worker_does_not_mark_failed_batch_complete(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'a.zip').write_bytes(zip_bytes())
    calls = []
    monkeypatch.setattr(import_worker, 'import_batch',
                        lambda *args: (calls.append(1) or 1, [{'outcome': 'error'}]))
    args = (source, 'db', tmp_path / 'artifacts', 'source', tmp_path / 'state.sqlite3')
    assert import_worker.run(*args) == (0, 1)
    assert import_worker.run(*args) == (0, 1)
    assert len(calls) == 2


def test_companion_files_are_persisted_with_names_and_hashes(tmp_path, monkeypatch):
    saved = []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query, params):
            saved.append((query, params))
            return self
        def fetchone(self): return (7,)
    monkeypatch.setattr(import_worker.psycopg, 'connect', lambda *args, **kwargs: Connection())
    monkeypatch.setattr(import_worker, 'save_source', lambda root, data: 'key-' + str(len(data)))
    import_worker.save_assets('db', tmp_path, 5, zip_bytes(), [{'filename': 'fixture.ies', 'file_id': 42}])
    bundle_inserts = [params for query, params in saved if 'INSERT INTO photolab.zip_product_bundles' in query]
    assets = [params for query, params in saved if 'INSERT INTO photolab.zip_bundle_assets' in query]
    assert bundle_inserts == [(5, 'fixture')]
    assert [row[1] for row in assets] == ['fixture.ies', 'fixture.jpg', 'fixture.json']
    assert assets[0][-1] == 42
    assert assets[1][3] == '6105d6cc76af400325e94d588ce511be5bfdbb73b437dc51eca43917d7a43e3d'
    assert any('UPDATE photolab.zip_product_bundles' in query for query, _ in saved)
