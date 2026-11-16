"""Sequential ZIP directory import without uploading the directory to Streamlit."""
import argparse
from collections import Counter
from hashlib import sha256
from pathlib import Path
import sqlite3
import stat

import psycopg

from .artifacts import artifact_root
from .bulk import MAX_TOTAL_BYTES
from .database import DatabaseError, database_url
from .zip_products import import_product_zip
from .zip_checkpoint import ZipCheckpoint


def database_target_key(url):
    """Identify the actual PostgreSQL target without storing credentials."""
    try:
        with psycopg.connect(url, connect_timeout=10, autocommit=True,
                             options='-c default_transaction_read_only=on') as connection:
            row = connection.execute("SELECT current_database(), inet_server_addr(), inet_server_port(), "
                "to_regclass('photolab.zip_product_bundles'), to_regclass('photolab.zip_bundle_assets')").fetchone()
    except psycopg.Error:
        raise DatabaseError('Cannot identify the PostgreSQL target. Check the connection settings.') from None
    if row[3] is None or row[4] is None:
        raise DatabaseError('ZIP product import requires migration 006; no archives have been imported.')
    return sha256(repr(tuple(str(value) for value in row[:3])).encode('utf-8')).hexdigest()


def import_directory(directory, url, root, description, version='zip-cli-v1', *,
                     checkpoint=None, target_key=None, recursive=False, retry_uncertain=False):
    directory = Path(directory)
    if not directory.is_dir() or not description.strip():
        raise ValueError('Provide an existing directory and source description.')
    if checkpoint is not None and not target_key:
        raise ValueError('A database target key is required when using checkpoints.')
    paths = sorted((p for p in (directory.rglob('*') if recursive else directory.iterdir())
                    if p.suffix.lower() == '.zip'), key=lambda p: str(p).casefold())
    if not paths:
        raise ValueError('No ZIP archives found. Use --recursive to include subdirectories.')
    counts = Counter()
    for number, path in enumerate(paths, 1):
        path_key = None
        relative_name = path.relative_to(directory).as_posix()
        digest = None
        claimed = False
        try:
            metadata = path.lstat()
            if (stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400
                    or not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_TOTAL_BYTES):
                raise ValueError('Archive is not a regular file or exceeds the per-ZIP limit.')
            path_key = str(path.resolve(strict=True))
            with path.open('rb') as stream:
                content = stream.read(MAX_TOTAL_BYTES + 1)
            if len(content) > MAX_TOTAL_BYTES:
                raise ValueError('Archive exceeds the per-ZIP limit.')
            digest = sha256(content).hexdigest()
            if checkpoint is not None:
                claimed, status = checkpoint.claim(target_key, path_key, digest,
                                                   retry_uncertain=retry_uncertain)
                if not claimed:
                    counts[f'skipped_{status}'] += 1
                    batch, message = checkpoint.details(target_key, path_key, digest)
                    print(f'[{number}/{len(paths)}] {relative_name}: skipped checkpoint={status} '
                          f'batch={batch if batch is not None else "unknown"} {message}', flush=True)
                    continue
            def progress(done, total):
                if done % 10 == 0 or done == total:
                    print(f'[{number}/{len(paths)}] {relative_name}: files {done}/{total}', flush=True)
            batch_id, rows, groups, skipped = import_product_zip(
                url, content, root, f'{description} / {relative_name}', version, progress=progress)
            outcomes = Counter(row.get('outcome', '') for row in rows)
            failures = sum(outcomes[key] for key in ('error', 'skipped', 'rejected'))
            status = 'completed_with_errors' if failures else 'completed'
            if checkpoint is not None:
                checkpoint.finish(target_key, path_key, digest, status=status, batch_id=batch_id,
                                  message=f'new={outcomes["new"]} duplicate={outcomes["duplicate"]} errors={failures}')
            counts[status] += 1
            print(f'[{number}/{len(paths)}] {relative_name}: batch={batch_id} bundles={len(groups)} '
                  f'new={outcomes["new"]} duplicate={outcomes["duplicate"]} errors={failures}', flush=True)
        except (ValueError, OSError, sqlite3.Error, psycopg.Error, DatabaseError) as error:
            counts['needs_review'] += 1
            if checkpoint is not None and digest is not None and claimed:
                checkpoint.finish(target_key, path_key, digest, status='needs_review', message=str(error))
            print(f'[{number}/{len(paths)}] {relative_name}: NEEDS REVIEW: {error}', flush=True)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source', required=True)
    parser.add_argument('--recursive', action='store_true', help='Include ZIP archives in subdirectories.')
    parser.add_argument('--state-file', type=Path, help='Persistent checkpoint file (default: alongside the source archive).')
    parser.add_argument('--retry-uncertain', action='store_true', help='Retry running/uncertain archives only after checking that no other worker is running and reviewing batch history.')
    args = parser.parse_args()
    try:
        if not args.directory.is_dir():
            raise ValueError('The ZIP directory does not exist or is not accessible.')
        url, root = database_url(), artifact_root()
        state_file = args.state_file or root.parent / 'zip-import-checkpoints.sqlite3'
        target = database_target_key(url)
        checkpoint = ZipCheckpoint(state_file)
        try:
            counts = import_directory(args.directory, url, root, args.source, checkpoint=checkpoint,
                                      target_key=target, recursive=args.recursive,
                                      retry_uncertain=args.retry_uncertain)
        finally:
            checkpoint.close()
    except (DatabaseError, OSError, sqlite3.Error, ValueError) as error:
        parser.exit(2, f'Cannot start or continue ZIP import: {error}\n')
    print(f'Archive summary: {dict(counts)}; checkpoint: {state_file}')
    if any(counts[key] for key in ('needs_review', 'completed_with_errors',
                                   'skipped_running', 'skipped_needs_review', 'skipped_completed_with_errors')):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
