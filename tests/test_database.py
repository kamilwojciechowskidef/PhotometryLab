from pathlib import Path

import pytest

from photolab.database import DatabaseError, database_url, migration_files


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
