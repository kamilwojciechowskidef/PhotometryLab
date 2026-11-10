"""Import one bounded ZIP as archive-scoped product bundles and original assets."""
from dataclasses import dataclass, field
import json
from pathlib import PurePosixPath

import psycopg
from psycopg.types.json import Jsonb

from .artifacts import save_source
from .bulk import BatchFile, import_batch, prepare_zip
from .database import DatabaseError
from .identifiers import identify_file

SUPPORTED = frozenset({'.ies', '.ldt', '.json', '.jpg', '.jpeg', '.png'})


@dataclass
class ProductBundle:
    stem: str
    files: list[BatchFile] = field(default_factory=list)
    metadata: dict | None = None


def prepare_product_zip(content: bytes) -> tuple[list[ProductBundle], list[BatchFile]]:
    """Validate the complete archive before any writes; never extract paths."""
    entries = prepare_zip(content, allowed_extensions=SUPPORTED)
    groups: dict[str, ProductBundle] = {}
    skipped = []
    for entry in entries:
        if entry.content is None:
            skipped.append(entry)
            continue
        path = PurePosixPath(entry.name)
        stem = str(path.with_suffix(''))
        group = groups.setdefault(stem, ProductBundle(stem))
        kind = path.suffix.lower()
        # Two files of the same kind within a group are ambiguous, including
        # case-only extension differences on case-sensitive archives.
        if any(PurePosixPath(previous.name).suffix.lower() == kind for previous in group.files):
            raise ValueError(f'Ambiguous duplicate asset type in ZIP bundle: {stem}')
        if kind == '.json':
            try:
                metadata = json.loads(entry.content.decode('utf-8-sig'))
            except (UnicodeError, ValueError, RecursionError) as error:
                raise ValueError(f'Invalid JSON in ZIP bundle: {entry.name}') from error
            if not isinstance(metadata, dict):
                raise ValueError(f'JSON metadata must be an object: {entry.name}')
            try:
                json.dumps(metadata, allow_nan=False)
            except (ValueError, TypeError, RecursionError) as error:
                raise ValueError(f'JSON metadata contains unsupported values: {entry.name}') from error
            source_id = metadata.get('hash')
            if source_id is not None and (not isinstance(source_id, str) or source_id != path.stem):
                raise ValueError(f'JSON hash does not match its filename: {entry.name}')
            group.metadata = metadata
        elif kind in ('.jpg', '.jpeg') and not entry.content.startswith(b'\xff\xd8\xff'):
            raise ValueError(f'Invalid JPEG signature: {entry.name}')
        elif kind == '.png' and not entry.content.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError(f'Invalid PNG signature: {entry.name}')
        group.files.append(entry)
    if not any(PurePosixPath(item.name).suffix.lower() in {'.ies', '.ldt'}
               for group in groups.values() for item in group.files):
        raise ValueError('ZIP must contain at least one supported photometric file.')
    return list(groups.values()), skipped


def import_product_zip(url, content, source_root, description, version, progress=None):
    """Save source photometry using existing importer, then attach ZIP bundles.

    Individual photometry imports commit separately. Sidecars and bundle links
    are saved in one later DB transaction. An interrupted run requires review;
    this function does not yet provide resumable or exactly-once imports.
    """
    if not description.strip():
        raise ValueError('A source description is required.')
    groups, skipped = prepare_product_zip(content)
    # Fail before the existing importer commits anything if migration 006 is missing.
    try:
        with psycopg.connect(url, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('photolab.zip_product_bundles'), "
                               "to_regclass('photolab.zip_bundle_assets')")
                if any(value is None for value in cursor.fetchone()):
                    raise DatabaseError('ZIP product import requires migration 006.')
    except psycopg.Error as error:
        raise DatabaseError('Cannot check ZIP product import schema.') from error
    photometry = [entry for group in groups for entry in group.files
                  if PurePosixPath(entry.name).suffix.lower() in {'.ies', '.ldt'}]
    batch_id, report = import_batch(url, photometry, source_root, description, version, progress)
    by_name = {row['filename']: row for row in report}
    try:
        with psycopg.connect(url, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                for group in groups:
                    cursor.execute('''INSERT INTO photolab.zip_product_bundles
                        (import_batch_id, source_stem, metadata) VALUES (%s, %s, %s)
                        RETURNING id''',
                        (batch_id, group.stem, Jsonb(group.metadata) if group.metadata is not None else None))
                    bundle_id = cursor.fetchone()[0]
                    for entry in group.files:
                        # Archive exact originals, including rejected IES/LDT.
                        path = save_source(source_root, entry.content)
                        identifier = identify_file(entry.content)
                        kind = PurePosixPath(entry.name).suffix.lower().lstrip('.')
                        kind = 'jpg' if kind == 'jpeg' else kind
                        file_id = by_name.get(entry.name, {}).get('file_id')
                        cursor.execute('''INSERT INTO photolab.zip_bundle_assets
                            (bundle_id, original_filename, kind, sha256, size_bytes,
                             artifact_path, photometry_file_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                            (bundle_id, entry.name, kind, identifier.sha256,
                             identifier.size_bytes, path, file_id))
    except (psycopg.Error, OSError, ValueError) as error:
        raise DatabaseError(f'Bundle save failed for batch #{batch_id}; photometry may already be saved. '
                            'Check migration 006 and source archive access before retrying.') from error
    return batch_id, report, groups, skipped
