"""Content-derived identifiers for one in-memory import batch."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping


@dataclass(frozen=True)
class FileIdentity:
    """Stable identity of uploaded bytes, independent of a filename."""

    filename: str
    sha256: str
    size_bytes: int
    duplicate_of: str | None = None

    @property
    def is_duplicate(self) -> bool:
        return self.duplicate_of is not None


def identify_files(files: Mapping[str, bytes]) -> list[FileIdentity]:
    """Hash files and flag later occurrences of identical byte content.

    The first filename with a given digest is retained as the batch reference.
    No filesystem or database state is read or written.
    """
    first_filename_by_digest: dict[str, str] = {}
    identities = []
    for filename, content in files.items():
        digest = sha256(content).hexdigest()
        original = first_filename_by_digest.setdefault(digest, filename)
        identities.append(FileIdentity(
            filename=filename,
            sha256=digest,
            size_bytes=len(content),
            duplicate_of=None if original == filename else original,
        ))
    return identities
