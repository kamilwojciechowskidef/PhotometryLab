"""PostgreSQL configuration, health checks, and ordered SQL migrations."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable, Mapping

import psycopg
from psycopg.types.json import Jsonb

from .identifiers import FileIdentifier, identify_file
from .quality import QualityReport


class DatabaseError(RuntimeError):
    """Raised when the local database configuration or connection is invalid."""


@dataclass(frozen=True)
class DatabaseHealth:
    """Non-sensitive details returned by a successful connection check."""

    database: str
    user: str
    server_version: str


@dataclass(frozen=True)
class StoredImport:
    """Database references created when one uploaded file is registered."""

    file_id: int
    import_batch_id: int
    alias_id: int
    identifier: FileIdentifier
    duplicate: bool


def database_url(env_path: Path | str = ".env") -> str:
    """Return ``DATABASE_URL`` from the environment or a local dotenv file.

    Environment variables take precedence, which permits a dedicated test database
    without changing the developer's local ``.env`` file.
    """
    configured = os.environ.get("DATABASE_URL", "").strip()
    if configured:
        return configured

    path = Path(env_path)
    if path.is_file():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "DATABASE_URL":
                configured = value.strip().strip('"').strip("'")
                if configured:
                    return configured

    raise DatabaseError("DATABASE_URL is not configured.")


def check_connection(url: str) -> DatabaseHealth:
    """Connect to PostgreSQL and return only non-sensitive server information."""
    try:
        with psycopg.connect(url, connect_timeout=5, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user, version()")
                database, user, server_version = cursor.fetchone()
    except psycopg.Error as error:
        raise DatabaseError("PostgreSQL connection check failed.") from error

    return DatabaseHealth(database=database, user=user, server_version=server_version)


def migration_files(directory: Path | str) -> list[Path]:
    """Return numbered migration files in order and reject duplicate versions."""
    files = sorted(Path(directory).glob("[0-9][0-9][0-9]_*.sql"))
    versions = [path.name.split("_", 1)[0] for path in files]
    if len(versions) != len(set(versions)):
        raise DatabaseError("Migration versions must be unique.")
    return files


def apply_migrations(url: str, migrations: Iterable[Path]) -> list[str]:
    """Apply each trusted local migration once and return applied versions.

    Migration files are repository-controlled SQL, never user-uploaded content.
    """
    applied: list[str] = []
    try:
        with psycopg.connect(url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE SCHEMA IF NOT EXISTS photolab")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS photolab.schema_migrations (
                        version varchar(3) PRIMARY KEY,
                        applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                for migration in migrations:
                    version = migration.name.split("_", 1)[0]
                    cursor.execute(
                        "SELECT 1 FROM photolab.schema_migrations WHERE version = %s",
                        (version,),
                    )
                    if cursor.fetchone() is not None:
                        continue
                    cursor.execute(migration.read_text(encoding="utf-8"))
                    cursor.execute(
                        "INSERT INTO photolab.schema_migrations (version) VALUES (%s)",
                        (version,),
                    )
                    applied.append(version)
            connection.commit()
    except (OSError, psycopg.Error) as error:
        raise DatabaseError("PostgreSQL migration failed.") from error
    return applied


def register_file_import(
    url: str,
    *,
    original_filename: str,
    content: bytes,
    format_name: str | None,
    quality_report: QualityReport,
    application_version: str,
    source_description: str | None = None,
    private_artifact_path: str | None = None,
    provenance: Mapping[str, object] | None = None,
) -> StoredImport:
    """Register one imported file and its alias in a single database transaction.

    The function stores metadata only. The original bytes remain in the private
    artifact store; ``private_artifact_path`` may point to that store once it is
    implemented. An existing SHA-256 record is retained and receives a new alias
    for this import, without deleting or overwriting prior provenance.
    """
    if not original_filename.strip():
        raise ValueError("The original filename must not be blank.")
    if not application_version.strip():
        raise ValueError("The application version must not be blank.")

    identifier = identify_file(content)
    report_payload = {
        "status": quality_report.status,
        "comparison_ready": quality_report.comparison_ready,
        "downward_flux_ready": quality_report.downward_flux_ready,
        "issues": list(quality_report.issues),
    }
    try:
        with psycopg.connect(url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO photolab.import_batches (source_description, application_version)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (source_description, application_version),
                )
                import_batch_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO photolab.photometry_files
                        (sha256, size_bytes, format, quality_status, quality_report,
                         private_artifact_path, provenance)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sha256) DO NOTHING
                    RETURNING id
                    """,
                    (
                        identifier.sha256,
                        identifier.size_bytes,
                        format_name,
                        quality_report.status,
                        Jsonb(report_payload),
                        private_artifact_path,
                        Jsonb(dict(provenance or {})),
                    ),
                )
                inserted = cursor.fetchone()
                duplicate = inserted is None
                if duplicate:
                    cursor.execute(
                        "SELECT id FROM photolab.photometry_files WHERE sha256 = %s",
                        (identifier.sha256,),
                    )
                    existing = cursor.fetchone()
                    if existing is None:
                        raise DatabaseError("The duplicate file record could not be retrieved.")
                    file_id = existing[0]
                else:
                    file_id = inserted[0]

                cursor.execute(
                    """
                    INSERT INTO photolab.file_aliases
                        (file_id, import_batch_id, original_filename)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (file_id, import_batch_id, original_filename),
                )
                alias_id = cursor.fetchone()[0]
            connection.commit()
    except psycopg.Error as error:
        raise DatabaseError("PostgreSQL file registration failed.") from error

    return StoredImport(
        file_id=file_id,
        import_batch_id=import_batch_id,
        alias_id=alias_id,
        identifier=identifier,
        duplicate=duplicate,
    )


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    applied_versions = apply_migrations(
        database_url(root / ".env"),
        migration_files(root / "database" / "migrations"),
    )
    print("Applied migrations: " + (", ".join(applied_versions) or "none"))
