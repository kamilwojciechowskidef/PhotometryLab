import pytest

from photolab import zip_import
from photolab.zip_checkpoint import ZipCheckpoint


def test_directory_import_processes_each_archive_separately(tmp_path, monkeypatch):
    (tmp_path / 'a.zip').write_bytes(b'a')
    (tmp_path / 'b.zip').write_bytes(b'b')
    calls = []
    def store(url, content, root, description, version, progress=None):
        calls.append((content, description))
        return 1, [{}], [object()], []
    monkeypatch.setattr(zip_import, 'import_product_zip', store)
    zip_import.import_directory(tmp_path, 'unused', tmp_path, 'test source')
    assert {data for data, _ in calls} == {b'a', b'b'}
    assert all('test source / ' in description for _, description in calls)


def test_checkpoint_skips_completed_archives_and_detects_changed_content(tmp_path, monkeypatch):
    directory = tmp_path / 'zips'
    directory.mkdir()
    path = directory / 'a.zip'
    path.write_bytes(b'first')
    calls = []
    def store(url, content, root, description, version, progress=None):
        calls.append(content)
        return 9, [{'outcome': 'new'}], [object()], []
    monkeypatch.setattr(zip_import, 'import_product_zip', store)
    checkpoint = ZipCheckpoint(tmp_path / 'state.sqlite3')
    try:
        first = zip_import.import_directory(directory, 'unused', tmp_path, 'source',
                                            checkpoint=checkpoint, target_key='db1')
        second = zip_import.import_directory(directory, 'unused', tmp_path, 'source',
                                             checkpoint=checkpoint, target_key='db1')
        assert first['completed'] == second['skipped_completed'] == 1
        assert calls == [b'first']
        path.write_bytes(b'changed')
        zip_import.import_directory(directory, 'unused', tmp_path, 'source',
                                    checkpoint=checkpoint, target_key='db1')
        zip_import.import_directory(directory, 'unused', tmp_path, 'source',
                                    checkpoint=checkpoint, target_key='db2')
        assert calls == [b'first', b'changed', b'changed']
    finally:
        checkpoint.close()


def test_uncertain_archive_is_not_retried_automatically(tmp_path, monkeypatch):
    directory = tmp_path / 'zips'
    directory.mkdir()
    (directory / 'a.zip').write_bytes(b'bytes')
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise zip_import.DatabaseError('Some files may already be saved; batch #42.')
    monkeypatch.setattr(zip_import, 'import_product_zip', fail)
    checkpoint = ZipCheckpoint(tmp_path / 'state.sqlite3')
    try:
        first = zip_import.import_directory(directory, 'unused', tmp_path, 'source',
                                            checkpoint=checkpoint, target_key='db')
        second = zip_import.import_directory(directory, 'unused', tmp_path, 'source',
                                             checkpoint=checkpoint, target_key='db')
        assert first['needs_review'] == second['skipped_needs_review'] == 1
        assert len(calls) == 1
        assert 'batch #42' in checkpoint.connection.execute('SELECT message FROM archives').fetchone()[0]
        zip_import.import_directory(directory, 'unused', tmp_path, 'source',
                                    checkpoint=checkpoint, target_key='db', retry_uncertain=True)
        assert len(calls) == 2
    finally:
        checkpoint.close()


def test_interrupted_archive_remains_running_and_is_skipped(tmp_path, monkeypatch):
    directory = tmp_path / 'zips'
    directory.mkdir()
    (directory / 'a.zip').write_bytes(b'bytes')
    calls = []
    def interrupt(*args, **kwargs):
        calls.append(1)
        raise KeyboardInterrupt
    monkeypatch.setattr(zip_import, 'import_product_zip', interrupt)
    checkpoint = ZipCheckpoint(tmp_path / 'state.sqlite3')
    try:
        with pytest.raises(KeyboardInterrupt):
            zip_import.import_directory(directory, 'unused', tmp_path, 'source',
                                        checkpoint=checkpoint, target_key='db')
        result = zip_import.import_directory(directory, 'unused', tmp_path, 'source',
                                             checkpoint=checkpoint, target_key='db')
        assert result['skipped_running'] == 1
        assert len(calls) == 1
    finally:
        checkpoint.close()


def test_checkpoint_claim_is_exclusive_without_explicit_retry(tmp_path):
    one = ZipCheckpoint(tmp_path / 'state.sqlite3')
    two = ZipCheckpoint(tmp_path / 'state.sqlite3')
    try:
        assert one.claim('db', 'a.zip', 'hash') == (True, 'running')
        assert two.claim('db', 'a.zip', 'hash') == (False, 'running')
        one.finish('db', 'a.zip', 'hash', status='completed', batch_id=4)
        assert two.claim('db', 'a.zip', 'hash') == (False, 'completed')
    finally:
        one.close()
        two.close()


def test_empty_directory_is_reported(tmp_path):
    with pytest.raises(ValueError, match='No ZIP'):
        zip_import.import_directory(tmp_path, 'unused', tmp_path, 'source')
