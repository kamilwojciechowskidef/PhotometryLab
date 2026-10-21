"""Stable identifiers for unmodified uploaded photometric file bytes."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class FileIdentifier:
    """Content identity used to detect an exact duplicate independent of its name."""

    sha256: str
    size_bytes: int


def identify_file(content: bytes) -> FileIdentifier:
    """Return a SHA-256 identifier for the original, unparsed file bytes.

    The result deliberately excludes the filename, parser output, and metadata.
    Files with matching hashes are byte-for-byte identical; files with different
    hashes are retained for later comparison instead of being treated as similar.
    """
    if not isinstance(content, bytes):
        raise TypeError("File content must be bytes.")
    return FileIdentifier(sha256=sha256(content).hexdigest(), size_bytes=len(content))
