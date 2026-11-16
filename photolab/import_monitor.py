"""Read-only snapshot of archive checkpoints and existing PostgreSQL reports."""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import sqlite3

import psycopg

from .database import DatabaseError


class ImportMonitorError(RuntimeError):
    """The checkpoint cannot safely be read or has an unsupported schema."""


@dataclass(frozen=True)
class ImportSnapshot:
    status_counts: dict[str, int]
    outcome_counts: dict[str, int]
    summarized_archives: int
    unsummarized_finished: int
    recent: list[dict]


def open_checkpoint_readonly(path: Path):
    """Open an existing SQLite file without creating or modifying it."""
    # as_uri percent-encodes spaces, # and ? on Windows as well as POSIX.
    uri = Path(path).resolve().as_uri() + '?mode=ro'
    connection = sqlite3.connect(uri, uri=True, timeout=1)
    connection.execute('PRAGMA query_only = ON')
    return connection


_SUMMARY = re.compile(r'^new=(\d+) duplicate=(\d+) errors=(\d+)$')


def read_checkpoint(path: Path, target: str, *, limit: int = 50) -> ImportSnapshot | None:
    """Return recorded archives for one DB target; None means no checkpoint file.

    Counts are archive checkpoint states, not a total number of discovered ZIPs.
    The stored worker summary is parsed only when its full format is recognized.
    """
    if not 1 <= limit <= 100:
        raise ValueError('Recent archive limit must be between 1 and 100.')
    path = Path(path)
    if not path.is_file():
        return None
    connection = None
    try:
        connection = open_checkpoint_readonly(path)
        # A consistent snapshot avoids mixing statuses from different moments.
        connection.execute('BEGIN')
        statuses, outcomes = Counter(), Counter()
        summarized = unsummarized = 0
        rows = connection.execute('SELECT status, message FROM archives WHERE target = ?', (target,))
        for status, message in rows:
            statuses[status] += 1
            if status not in ('completed', 'completed_with_errors'):
                continue
            match = _SUMMARY.fullmatch(message or '')
            if match is None:
                unsummarized += 1
                continue
            summarized += 1
            for name, value in zip(('new', 'duplicate', 'errors'), match.groups()):
                outcomes[name] += int(value)
        recent_rows = connection.execute('''SELECT path, sha256, status, batch_id, message, updated_at
            FROM archives WHERE target = ? ORDER BY updated_at DESC, rowid DESC LIMIT ?''',
            (target, limit)).fetchall()
        recent = [dict(archive=PurePosixPath(source.replace('\\', '/')).name,
                       sha256_prefix=digest[:12], status=status, batch_id=batch,
                       message=message, updated_utc=updated)
                  for source, digest, status, batch, message, updated in recent_rows]
        return ImportSnapshot(dict(statuses), dict(outcomes), summarized, unsummarized, recent)
    except (sqlite3.Error, OSError, ValueError, TypeError) as error:
        raise ImportMonitorError('Cannot read the checkpoint; it may be busy, inaccessible, or incompatible.') from error
    finally:
        if connection is not None:
            connection.close()


def read_batch_report(url: str, batch_id: int) -> dict | None:
    """Read one existing import report in a server-enforced read-only session."""
    if batch_id < 1:
        raise ValueError('Invalid batch ID.')
    try:
        with psycopg.connect(url, connect_timeout=5, autocommit=True,
                             options='-c default_transaction_read_only=on') as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT id, status, expected_files, report
                    FROM photolab.import_batches WHERE id = %s''', (batch_id,))
                row = cursor.fetchone()
    except psycopg.Error as error:
        raise DatabaseError('Cannot read the import batch report.') from error
    if row is None:
        return None
    if not isinstance(row[3], list):
        raise DatabaseError('The stored import report is invalid.')
    return dict(id=row[0], status=row[1], expected_files=row[2], report=row[3])
