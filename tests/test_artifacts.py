from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

<<<<<<< HEAD
from photolab.artifacts import ArtifactError, save_source, read_source, artifact_root
=======
from photolab.artifacts import ArtifactError, save_source, read_source
>>>>>>> origin/main
from photolab.identifiers import identify_file


def test_exact_bytes_and_duplicate_archive(tmp_path):
    content = b'IES\r\n\xff\x00'
    key = save_source(tmp_path, content)
    assert save_source(tmp_path, content) == key
    assert read_source(tmp_path, identify_file(content).sha256, len(content)) == content
<<<<<<< HEAD
=======
    assert len(list(tmp_path.rglob('*.*'))) == 0
>>>>>>> origin/main
    assert len([p for p in tmp_path.rglob('*') if p.is_file()]) == 1


def test_corruption_is_never_overwritten(tmp_path):
    key = save_source(tmp_path, b'original')
    (tmp_path / key).write_bytes(b'corrupted')
    with pytest.raises(ArtifactError, match='integrity'):
        save_source(tmp_path, b'original')
    assert (tmp_path / key).read_bytes() == b'corrupted'


def test_missing_source_and_path_traversal(tmp_path):
    with pytest.raises(ArtifactError, match='missing'):
        read_source(tmp_path, 'a' * 64, 3)
    with pytest.raises(ArtifactError, match='identifier'):
        read_source(tmp_path, '../outside', 3)


def test_concurrent_import_has_one_complete_copy(tmp_path):
    with ThreadPoolExecutor(max_workers=4) as pool:
        keys = list(pool.map(lambda _: save_source(tmp_path, b'concurrent'), range(8)))
    assert len(set(keys)) == 1
    assert (tmp_path / keys[0]).read_bytes() == b'concurrent'
    assert len([p for p in tmp_path.rglob('*') if p.is_file()]) == 1


def test_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr('photolab.artifacts.MAX_SOURCE_BYTES', 3)
    with pytest.raises(ArtifactError, match='limit'):
        save_source(tmp_path, b'1234')


def test_archive_does_not_resolve_concurrently_published_file(tmp_path, monkeypatch):
    original = Path.resolve
    def resolve(path, *args, **kwargs):
        if len(path.name) == 64:
            pytest.fail('Published artifact paths must not be resolved')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'resolve', resolve)
    key = save_source(tmp_path, b'concurrent')
    assert (tmp_path / key).read_bytes() == b'concurrent'


@pytest.mark.parametrize('component', ['directory', 'file'])
def test_archive_rejects_windows_reparse_points(tmp_path, monkeypatch, component):
    digest = identify_file(b'test').sha256
    blocked = tmp_path / digest[:2]
    if component == 'file':
        blocked = blocked / digest
    original = Path.lstat
    def lstat(path, *args, **kwargs):
        if path == blocked:
            return SimpleNamespace(st_mode=0, st_file_attributes=0x400)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', lstat)
    with pytest.raises(ArtifactError, match='reparse point'):
        save_source(tmp_path, b'test')


def test_failed_database_keeps_recoverable_source(tmp_path, monkeypatch):
    import psycopg
    from photolab.database import register_file_import, DatabaseError
    from photolab.quality import rejected_file_report
    def fail(*args, **kwargs):
        raise psycopg.OperationalError('offline')
    monkeypatch.setattr('photolab.database.psycopg.connect', fail)
    with pytest.raises(DatabaseError):
        register_file_import('unused', original_filename='bad.ies', content=b'bad',
                             format_name=None, quality_report=rejected_file_report('bad.ies', 'broken'),
                             application_version='test', source_root=tmp_path)
    assert read_source(tmp_path, identify_file(b'bad').sha256, 3) == b'bad'
<<<<<<< HEAD


def test_configuration_environment_overrides_dotenv(tmp_path, monkeypatch):
    monkeypatch.setattr('photolab.artifacts.PROJECT_ROOT', tmp_path)
    monkeypatch.delenv('PHOTOLAB_ARTIFACT_DIR', raising=False)
    (tmp_path / '.env').write_text('PHOTOLAB_ARTIFACT_DIR=private\n', encoding='utf-8')
    assert artifact_root() == (tmp_path / 'private').resolve()
    monkeypatch.setenv('PHOTOLAB_ARTIFACT_DIR', 'alternative')
    assert artifact_root() == (tmp_path / 'alternative').resolve()
=======
>>>>>>> origin/main
