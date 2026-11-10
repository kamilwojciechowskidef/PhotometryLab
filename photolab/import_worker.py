"""Resume a bounded ZIP import from a local producer directory."""
import argparse
import hashlib
from io import BytesIO
import os
from pathlib import Path
import sqlite3
from zipfile import ZipFile

import psycopg

from .artifacts import artifact_root, save_source
from .bulk import MAX_FILE_BYTES, MAX_TOTAL_BYTES, import_batch, prepare_zip
from .database import database_url

ASSET_SUFFIXES = {'.jpg', '.jpeg', '.png', '.json'}


def archives(directory):
    for current, dirs, names in os.walk(directory, followlinks=False):
        dirs[:] = sorted(name for name in dirs if not (Path(current) / name).is_symlink())
        for name in sorted(names):
            if name.lower().endswith('.zip'):
                yield Path(current) / name


def save_assets(url, root, batch_id, content):
    """Save supported companion bytes; prepare_zip already validated ZIP structure."""
    with ZipFile(BytesIO(content)) as archive, psycopg.connect(url, connect_timeout=5) as connection:
        for info in archive.infolist():
            if info.is_dir() or Path(info.filename).suffix.lower() not in ASSET_SUFFIXES:
                continue
            if info.file_size > MAX_FILE_BYTES:
                raise ValueError(f'Companion file exceeds size limit: {info.filename}')
            if info.file_size > max(info.compress_size, 1) * 200:
                raise ValueError(f'Companion compression ratio exceeds limit: {info.filename}')
            with archive.open(info) as stream:
                asset = stream.read(MAX_FILE_BYTES + 1)
            if len(asset) != info.file_size:
                raise ValueError(f'Invalid companion size: {info.filename}')
            digest = hashlib.sha256(asset).hexdigest()
            key = save_source(root, asset)
            connection.execute('''INSERT INTO photolab.archive_assets
                (batch_id, member_name, sha256, size_bytes, private_artifact_path)
                VALUES (%s, %s, %s, %s, %s)''',
                (batch_id, info.filename, digest, len(asset), key))


def run(directory, url, root, description, checkpoint, limit=None):
    directory, root, checkpoint = Path(directory).resolve(), Path(root).resolve(), Path(checkpoint)
    if not directory.is_dir() or not description.strip() or (limit is not None and limit < 1):
        raise ValueError('Provide a directory, source description and positive limit.')
    # Bind checkpoints to source, destination and asset storage, without storing credentials.
    identity = hashlib.sha256((str(directory) + '\0' + url + '\0' + str(root)).encode()).hexdigest()
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    done = errors = attempted = 0
    with sqlite3.connect(checkpoint) as state:
        state.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        state.execute('''CREATE TABLE IF NOT EXISTS archives
            (path TEXT PRIMARY KEY, size INTEGER NOT NULL, mtime INTEGER NOT NULL,
             status TEXT NOT NULL, batch_id INTEGER, error TEXT NOT NULL)''')
        previous = state.execute("SELECT value FROM settings WHERE key='identity'").fetchone()
        if previous and previous[0] != identity:
            raise ValueError('Checkpoint belongs to a different source, database or archive directory.')
        state.execute("INSERT OR IGNORE INTO settings VALUES ('identity', ?)", (identity,))
        state.commit()
        for path in archives(directory):
            relative = path.relative_to(directory).as_posix()
            try:
                if path.is_symlink():
                    raise ValueError('ZIP is a symbolic link.')
                info = path.stat()
                previous = state.execute('SELECT size, mtime, status FROM archives WHERE path=?', (relative,)).fetchone()
                if previous == (info.st_size, info.st_mtime_ns, 'completed'):
                    continue
                if limit is not None and attempted >= limit:
                    break
                attempted += 1
                if info.st_size > MAX_TOTAL_BYTES:
                    raise ValueError('ZIP exceeds size limit.')
                with path.open('rb') as stream:
                    content = stream.read(MAX_TOTAL_BYTES + 1)
                files = prepare_zip(content)
                batch_id, report = import_batch(url, files, root, f'{description} / {relative}', 'zip-worker-v1')
                if any(row['outcome'] == 'error' for row in report):
                    raise RuntimeError('One or more photometry files could not be saved; see batch report.')
                save_assets(url, root, batch_id, content)
                after = path.stat()
                if (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError('ZIP changed during import; retry is required.')
                state.execute('INSERT OR REPLACE INTO archives VALUES (?, ?, ?, ?, ?, ?)',
                              (relative, info.st_size, info.st_mtime_ns, 'completed', batch_id, ''))
                done += 1
                print(f'OK {relative} batch={batch_id}', flush=True)
            except (OSError, ValueError, RuntimeError) as error:
                errors += 1
                # Failed archives are retried, including archives partially written before failure.
                state.execute('INSERT OR REPLACE INTO archives VALUES (?, ?, ?, ?, ?, ?)',
                              (relative, -1, -1, 'error', None, str(error)))
                print(f'ERROR {relative}: {error}', flush=True)
            state.commit()
    return done, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source', required=True)
    parser.add_argument('--checkpoint', type=Path, default=Path('data/private/import-checkpoint.sqlite3'))
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    url = database_url()
    with psycopg.connect(url, connect_timeout=5) as connection:
        if connection.execute("SELECT to_regclass('photolab.archive_assets')").fetchone()[0] is None:
            raise SystemExit('Apply database migration 006 before running the worker.')
    done, errors = run(args.directory, url, artifact_root(), args.source, args.checkpoint, args.limit)
    print(f'Finished: completed={done} errors={errors}', flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
