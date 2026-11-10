"""Import one bounded ZIP as archive-scoped product bundles and original assets."""
from dataclasses import dataclass, field
from io import BytesIO
import json
from pathlib import PurePosixPath

import psycopg
from psycopg.types.json import Jsonb

from .artifacts import ArtifactError, read_source, save_source
from .bulk import BatchFile, import_batch, prepare_zip, update_batch
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
    # Persist skipped entries in the existing per-file batch report too.
    batch_id, report = import_batch(url, photometry + skipped, source_root, description, version, progress)
    # Keep the batch visibly unfinished during the separate attachment phase.
    # A process crash immediately after import_batch returns remains a known gap.
    update_batch(url, batch_id, report, finished=False)
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
                status = ('completed_with_errors' if any(
                    row['outcome'] in ('error', 'skipped', 'rejected') for row in report
                ) else 'completed')
                cursor.execute('''UPDATE photolab.import_batches SET status = %s,
                                  finished_at = CURRENT_TIMESTAMP WHERE id = %s''',
                               (status, batch_id))
    except (psycopg.Error, OSError, ValueError) as error:
        raise DatabaseError(f'Bundle save failed for batch #{batch_id}; photometry may already be saved. '
                            'Check migration 006 and source archive access before retrying.') from error
    return batch_id, report, groups, skipped


def list_related_bundles(url, file_id, limit=20):
    """List bounded archive-scoped groups, without selecting a canonical product."""
    if not 1 <= limit <= 100:
        raise ValueError('Bundle limit must be between 1 and 100.')
    try:
        with psycopg.connect(url, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT DISTINCT b.id, b.source_stem
                    FROM photolab.zip_product_bundles b
                    JOIN photolab.zip_bundle_assets a ON a.bundle_id = b.id
                    WHERE a.photometry_file_id = %s ORDER BY b.id DESC LIMIT %s''',
                    (file_id, limit))
                return cursor.fetchall()
    except psycopg.Error as error:
        raise DatabaseError('Cannot read ZIP bundles. Check migration 006.') from error


def load_bundle(url, bundle_id):
    """Read metadata and bounded asset references for one archive group."""
    try:
        with psycopg.connect(url, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT b.metadata, a.original_filename, a.kind,
                                         a.sha256, a.size_bytes
                    FROM photolab.zip_product_bundles b
                    JOIN photolab.zip_bundle_assets a ON a.bundle_id = b.id
                    WHERE b.id = %s ORDER BY a.original_filename LIMIT 500''', (bundle_id,))
                rows = cursor.fetchall()
    except psycopg.Error as error:
        raise DatabaseError('Cannot read ZIP bundle assets.') from error
    if not rows:
        raise DatabaseError('ZIP bundle not found or has no assets.')
    return rows[0][0], [dict(zip(('filename', 'kind', 'sha256', 'size'), row[1:])) for row in rows]


def preview_image(root, asset):
    """Verify stored bytes and safely decode one bounded JPEG or PNG preview."""
    from PIL import Image, UnidentifiedImageError

    if asset['kind'] not in ('jpg', 'png'):
        raise ArtifactError('This asset is not a supported image.')
    content = read_source(root, asset['sha256'], asset['size'])
    try:
        with Image.open(BytesIO(content)) as image:
            expected = 'JPEG' if asset['kind'] == 'jpg' else 'PNG'
            if image.format != expected or image.width * image.height > 16_000_000:
                raise ArtifactError('Image format or dimensions are not supported for preview.')
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image.thumbnail((1200, 1200))
            return image.copy()
    except ArtifactError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as error:
        raise ArtifactError('Image cannot be safely decoded for preview.') from error
