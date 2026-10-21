"""Private, content-addressed archive of original file bytes."""
import os
from pathlib import Path
import re
import stat
import tempfile

from .identifiers import identify_file

MAX_SOURCE_BYTES = 5 * 1024 * 1024
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ArtifactError(ValueError):
    """Source is missing, corrupt or inaccessible."""


def artifact_root() -> Path:
    value = os.environ.get('PHOTOLAB_ARTIFACT_DIR', '').strip()
    if not value:
        dotenv = PROJECT_ROOT / '.env'
        if dotenv.is_file():
            for line in dotenv.read_text(encoding='utf-8').splitlines():
                key, separator, entry = line.partition('=')
                if separator and key.strip() == 'PHOTOLAB_ARTIFACT_DIR':
                    value = entry.strip().strip('\"').strip("'")
    path = Path(value or 'data/private/sources')
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def _path(root: Path, digest: str) -> Path:
    if not re.fullmatch('[0-9a-f]{64}', digest):
        raise ArtifactError('Invalid source identifier.')
    root = Path(root).resolve()
    target = root / digest[:2] / digest
    # Do not resolve a hard link concurrently published by another writer.
    for component in (target.parent, target):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, 'st_file_attributes', 0) & 0x400):
            raise ArtifactError('Source path contains a symbolic link or reparse point.')
    return target


def read_source(root: Path, digest: str, size_bytes: int) -> bytes:
    try:
        target = _path(root, digest)
        with target.open('rb') as stream:
            content = stream.read(MAX_SOURCE_BYTES + 1)
    except OSError:
        raise ArtifactError('Source file is missing or unreadable. Restore it from backup.') from None
    if len(content) > MAX_SOURCE_BYTES or len(content) != size_bytes or identify_file(content).sha256 != digest:
        raise ArtifactError('Source integrity check failed (SHA-256 or size mismatch).')
    return content


def save_source(root: Path, content: bytes) -> str:
    identifier = identify_file(content)
    if len(content) > MAX_SOURCE_BYTES:
        raise ArtifactError('Source exceeds the 5 MB limit.')
    temporary = None
    try:
        target = _path(root, identifier.sha256)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = _path(root, identifier.sha256)
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
        read_source(root, identifier.sha256, identifier.size_bytes)
    except OSError:
        raise ArtifactError('Cannot write the source archive. Check directory permissions and free space.') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return f'{identifier.sha256[:2]}/{identifier.sha256}'
