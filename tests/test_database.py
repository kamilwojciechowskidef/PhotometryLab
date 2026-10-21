from pathlib import Path

import pytest

from photolab.database import DatabaseError, database_url, migration_files, register_file_import
from photolab.quality import QualityReport


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
