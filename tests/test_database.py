from pathlib import Path

import pytest

from photolab.database import DatabaseError, database_url, migration_files, register_file_import
from photolab.quality import QualityReport
from photolab.database import load_stored_photometry
from photolab.demo import make_ies
from photolab.parsers import load_photometry
from photolab.storage import photometry_to_data
from photolab.artifacts import read_source
from photolab.database import list_catalogue


class FakeCursor:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, parameters=None):
        self.calls.append((statement, parameters))

    def fetchone(self):
        return next(self.responses)

    def fetchall(self):
        return list(self.responses)


def test_catalogue_filters_are_parameters_and_results_are_bounded(monkeypatch):
    cursor = FakeCursor([(5, 'same.ies', 'Example', 'Lamp', 'IES', 'a' * 64)])
    monkeypatch.setattr('photolab.database.psycopg.connect', lambda *a, **k: FakeConnection(cursor))
    rows = list_catalogue('unused', manufacturer="O'Reilly", model='100%', offset=50)
    assert rows[0]['file_id'] == 5
    sql, params = cursor.calls[0]
    assert params == ("O'Reilly", '100%', 50, 50)
    assert "O'Reilly" not in sql
    assert 'LIMIT %s OFFSET %s' in sql


def test_catalogue_rejects_unbounded_request():
    with pytest.raises(ValueError):
        list_catalogue('unused', limit=10000)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True


def test_import_uses_existing_batch_without_creating_another(monkeypatch):
    cursor = FakeCursor([(20,), (30,)])
    connection = FakeConnection(cursor)
    monkeypatch.setattr('photolab.database.psycopg.connect', lambda url: connection)
    result = register_file_import('unused', original_filename='bad.ies', content=b'bad',
                                 format_name=None, quality_report=QualityReport('bad.ies', 'damaged', False, False, ()),
                                 application_version='test', batch_id=42)
    assert result.import_batch_id == 42
    assert not any('INSERT INTO photolab.import_batches' in sql for sql, _ in cursor.calls)
    assert cursor.calls[-1][1] == (20, 42, 'bad.ies')
    assert connection.committed


def test_duplicate_import_backfills_source_reference(tmp_path, monkeypatch):
    cursor = FakeCursor([(10,), None, (20,), (30,)])
    connection = FakeConnection(cursor)
    monkeypatch.setattr('photolab.database.psycopg.connect', lambda url: connection)
    result = register_file_import('unused', original_filename='bad.ies', content=b'bad',
                                 format_name=None, quality_report=QualityReport('bad.ies', 'damaged', False, False, ()),
                                 application_version='test', source_root=tmp_path)
    statement, params = cursor.calls[-1]
    assert 'UPDATE photolab.photometry_files' in statement
    assert params == (f'{result.identifier.sha256[:2]}/{result.identifier.sha256}', 20)
    assert read_source(tmp_path, result.identifier.sha256, 3) == b'bad'
    assert connection.committed


@pytest.mark.parametrize('duplicate', [False, True])
def test_import_persists_photometry_for_new_and_existing_files(monkeypatch, duplicate):
    cursor = FakeCursor([(10,), None, (20,), (30,)] if duplicate else [(10,), (20,), (30,)])
    connection = FakeConnection(cursor)
    monkeypatch.setattr('photolab.database.psycopg.connect', lambda url: connection)
    content = make_ies('Test', 'oval')
    item = load_photometry('test.ies', content)
    result = register_file_import(
        'unused', original_filename='test.ies', content=content,
        format_name=item.format, quality_report=QualityReport('test.ies', 'valid', True, True, ()),
        application_version='test', photometry=item,
    )
    assert result.duplicate == duplicate
    assert connection.committed
    statement, params = cursor.calls[-2]
    assert 'ON CONFLICT (file_id) DO NOTHING' in statement
    assert params[0] == 20
    assert params[2].obj == photometry_to_data(item)
    feature_statement, feature_params = cursor.calls[-1]
    assert 'INSERT INTO photolab.feature_sets' in feature_statement
    assert feature_params[0] == 20
    assert feature_params[2] == 684
    assert len(feature_params[3]) == 684


def test_load_stored_photometry(monkeypatch):
    item = load_photometry('test.ies', make_ies('Test', 'oval'))
    cursor = FakeCursor([(1, photometry_to_data(item)), None])
    monkeypatch.setattr('photolab.database.psycopg.connect', lambda url: FakeConnection(cursor))
    assert photometry_to_data(load_stored_photometry('unused', 20)) == photometry_to_data(item)
    assert load_stored_photometry('unused', 21) is None


def test_photometry_write_failure_does_not_commit(monkeypatch):
    import psycopg
    cursor = FakeCursor([(10,), (20,), (30,)])
    execute = cursor.execute
    def fail_on_photometry(statement, parameters=None):
        if 'INSERT INTO photolab.photometries' in statement:
            raise psycopg.DatabaseError('write failed')
        execute(statement, parameters)
    cursor.execute = fail_on_photometry
    connection = FakeConnection(cursor)
    monkeypatch.setattr('photolab.database.psycopg.connect', lambda url: connection)
    content = make_ies('Test', 'oval')
    item = load_photometry('test.ies', content)
    with pytest.raises(DatabaseError):
        register_file_import('unused', original_filename='test.ies', content=content,
                             format_name=item.format, quality_report=QualityReport('test.ies', 'valid', True, True, ()),
                             application_version='test', photometry=item)
    assert not connection.committed


def test_database_url_reads_dotenv_and_environment_takes_priority(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text("DATABASE_URL=postgresql://from-file\n", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url(dotenv) == "postgresql://from-file"

    monkeypatch.setenv("DATABASE_URL", "postgresql://from-environment")
    assert database_url(dotenv) == "postgresql://from-environment"


def test_database_url_requires_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseError, match="not configured"):
        database_url(tmp_path / "missing.env")


def test_migration_files_are_sorted_and_versions_must_be_unique(tmp_path):
    (tmp_path / "002_second.sql").write_text("SELECT 2", encoding="utf-8")
    (tmp_path / "001_first.sql").write_text("SELECT 1", encoding="utf-8")
    assert [path.name for path in migration_files(tmp_path)] == [
        "001_first.sql",
        "002_second.sql",
    ]

    (tmp_path / "001_duplicate.sql").write_text("SELECT 3", encoding="utf-8")
    with pytest.raises(DatabaseError, match="versions must be unique"):
        migration_files(tmp_path)


def test_register_file_import_validates_required_metadata():
    report = QualityReport("fixture.ies", "valid", True, True, ())
    with pytest.raises(ValueError, match="filename must not be blank"):
        register_file_import(
            "postgresql://unused", original_filename=" ", content=b"file",
            format_name="IES", quality_report=report, application_version="0.1",
        )
    with pytest.raises(ValueError, match="version must not be blank"):
        register_file_import(
            "postgresql://unused", original_filename="fixture.ies", content=b"file",
            format_name="IES", quality_report=report, application_version=" ",
        )


def test_register_file_import_creates_file_and_alias_in_one_transaction(monkeypatch):
    cursor = FakeCursor([(10,), (20,), (30,)])
    connection = FakeConnection(cursor)
    monkeypatch.setattr("photolab.database.psycopg.connect", lambda url: connection)
    report = QualityReport("fixture.ies", "valid", True, True, ("source warning",))

    result = register_file_import(
        "postgresql://unused", original_filename="fixture.ies", content=b"file",
        format_name="IES", quality_report=report, application_version="0.1",
        provenance={"source": "test"},
    )

    assert (result.file_id, result.import_batch_id, result.alias_id) == (20, 10, 30)
    assert not result.duplicate
    assert connection.committed
    assert len(cursor.calls) == 3
    assert cursor.calls[1][1][0] == result.identifier.sha256
    assert cursor.calls[1][1][4].obj["issues"] == ["source warning"]


def test_register_file_import_adds_alias_for_an_existing_hash(monkeypatch):
    cursor = FakeCursor([(10,), None, (20,), (30,)])
    connection = FakeConnection(cursor)
    monkeypatch.setattr("photolab.database.psycopg.connect", lambda url: connection)
    report = QualityReport("renamed.ies", "valid", True, True, ())

    result = register_file_import(
        "postgresql://unused", original_filename="renamed.ies", content=b"file",
        format_name="IES", quality_report=report, application_version="0.1",
    )

    assert result.file_id == 20
    assert result.duplicate
    assert len(cursor.calls) == 4
    assert "SELECT id FROM photolab.photometry_files" in cursor.calls[2][0]
