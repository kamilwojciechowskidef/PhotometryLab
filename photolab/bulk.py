"""Bounded batch ingestion with explicit outcomes and persistent reports."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath, PureWindowsPath
import stat
from zipfile import ZipFile, BadZipFile

import psycopg
from psycopg.types.json import Jsonb

from .database import DatabaseError, register_file_import
from .parsers import load_photometry, PhotometryError
from .quality import assess_quality, rejected_file_report

MAX_FILES = 500
MAX_FILE_BYTES = 5_000_000
MAX_TOTAL_BYTES = 100_000_000


@dataclass(frozen=True)
class BatchFile:
    name: str
    content: bytes | None
    error: str = ''


def validate_name(name: str) -> None:
    windows = PureWindowsPath(name)
    if (not name or '\\' in name or windows.drive or name.startswith('/')
            or '..' in PurePosixPath(name).parts or '\x00' in name):
        raise ValueError('Unsafe archive entry name.')


def prepare_files(files: list[tuple[str, bytes]]) -> list[BatchFile]:
    """Validate the complete input before any database or filesystem mutation."""
    if not files or len(files) > MAX_FILES:
        raise ValueError('Select between 1 and 500 files.')
    if sum(len(content) for _, content in files) > MAX_TOTAL_BYTES:
        raise ValueError('Batch exceeds the 100 MB total limit.')
    names = set()
    prepared = []
    for name, content in files:
        validate_name(name)
        if name in names:
            raise ValueError('Duplicate entry names are not supported; rename files before import.')
        names.add(name)
        error = ''
        if len(content) > MAX_FILE_BYTES:
            error = 'File exceeds the 5 MB limit.'
        elif PurePosixPath(name).suffix.lower() not in {'.ies', '.ldt'}:
            error = 'Unsupported file extension.'
        prepared.append(BatchFile(name, None if error else content, error))
    return prepared


def prepare_zip(content: bytes) -> list[BatchFile]:
    """Read ZIP members in memory, never extract paths to disk."""
    if len(content) > MAX_TOTAL_BYTES:
        raise ValueError('ZIP exceeds the 100 MB limit.')
    try:
        with ZipFile(BytesIO(content)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES:
                raise ValueError('ZIP exceeds the 500 entry limit.')
            if sum(info.file_size for info in infos) > MAX_TOTAL_BYTES:
                raise ValueError('Expanded ZIP exceeds the 100 MB limit.')
            names = set()
            prepared = []
            for info in infos:
                # ZipInfo normalizes backslashes on Windows and truncates NULs.
                # Validate the original header name before using its normalized form.
                validate_name(info.orig_filename)
                validate_name(info.filename)
                if info.filename in names:
                    raise ValueError('Duplicate ZIP entry names are not supported.')
                names.add(info.filename)
                if stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
                    raise ValueError('Encrypted entries and symbolic links are not supported.')
                if info.is_dir():
                    continue
                if info.file_size > MAX_FILE_BYTES:
                    prepared.append(BatchFile(info.filename, None, 'File exceeds the 5 MB limit.'))
                    continue
                if PurePosixPath(info.filename).suffix.lower() not in {'.ies', '.ldt'}:
                    prepared.append(BatchFile(info.filename, None, 'Unsupported file extension.'))
                    continue
                if info.file_size > max(info.compress_size, 1) * 200:
                    raise ValueError('ZIP compression ratio exceeds the safety limit.')
                with archive.open(info) as stream:
                    data = stream.read(MAX_FILE_BYTES + 1)
                if len(data) != info.file_size or len(data) > MAX_FILE_BYTES:
                    raise ValueError('ZIP entry size is invalid.')
                prepared.append(BatchFile(info.filename, data))
            if not prepared:
                raise ValueError('ZIP contains no files.')
            return prepared
    except (BadZipFile, NotImplementedError, RuntimeError) as error:
        raise ValueError('ZIP is damaged or uses unsupported compression.') from error


def create_batch(url, description, version, count):
    try:
        with psycopg.connect(url, connect_timeout=5) as connection:
            row = connection.execute('''INSERT INTO photolab.import_batches
                (source_description, application_version, status, expected_files)
                VALUES (%s, %s, 'running', %s) RETURNING id''', (description, version, count)).fetchone()
            return row[0]
    except psycopg.Error:
        raise DatabaseError('Cannot create batch. Check connection and migration 004.') from None


def update_batch(url, batch_id, report, finished=False):
    status = ('completed_with_errors' if any(r['outcome'] in ('error', 'skipped', 'rejected') for r in report)
              else 'completed') if finished else 'running'
    try:
        with psycopg.connect(url, connect_timeout=5) as connection:
            connection.execute('''UPDATE photolab.import_batches SET report=%s, status=%s,
                finished_at=CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=%s''',
                (Jsonb(report), status, finished, batch_id))
    except psycopg.Error:
        raise DatabaseError(f'Cannot persist report for batch #{batch_id}. Import stopped; some files may already be saved.') from None


def import_batch(url, files, source_root, description, version, progress=None):
    """Process a prepared batch; each file commits separately, no automatic retry."""
    if not files or len(files) > MAX_FILES:
        raise ValueError('Invalid batch size.')
    batch_id = create_batch(url, description, version, len(files))
    report = []
    for index, entry in enumerate(files):
        row = dict(filename=entry.name, outcome='skipped', quality='', duplicate=False,
                   file_id=None, message=entry.error)
        if entry.content is not None:
            try:
                try:
                    item = load_photometry(entry.name, entry.content)
                    quality = assess_quality(item)
                except PhotometryError as error:
                    item = None
                    quality = rejected_file_report(entry.name, str(error))
                stored = register_file_import(url, original_filename=entry.name, content=entry.content,
                    format_name=item.format if item else None, quality_report=quality,
                    application_version=version, photometry=item, source_root=source_root, batch_id=batch_id)
                row.update(outcome='rejected' if item is None else ('duplicate' if stored.duplicate else 'new'),
                           quality=quality.status, duplicate=stored.duplicate, file_id=stored.file_id,
                           message=' | '.join(quality.issues))
            except (DatabaseError, ValueError, OSError):
                row.update(outcome='error', message='File import failed. Check database and source archive access.')
        report.append(row)
        update_batch(url, batch_id, report, finished=index == len(files) - 1)
        if progress:
            progress(index + 1, len(files))
    return batch_id, report


def batch_history(url, offset=0):
    if offset < 0:
        raise ValueError('Invalid history page.')
    try:
        with psycopg.connect(url, connect_timeout=5) as connection:
            rows = connection.execute('''SELECT id, imported_at, source_description, status, expected_files, report
                FROM photolab.import_batches WHERE status <> 'legacy'
                ORDER BY id DESC LIMIT 20 OFFSET %s''', (offset,)).fetchall()
            return [dict(zip(('id', 'imported_at', 'source', 'status', 'expected_files', 'report'), row)) for row in rows]
    except psycopg.Error:
        raise DatabaseError('Cannot read batch history. Check migration 004.') from None
