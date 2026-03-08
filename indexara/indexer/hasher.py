"""Content hashing utilities."""
from __future__ import annotations
import hashlib
from pathlib import Path

CHUNK_SIZE = 65536


def compute_hash(path: Path) -> str | None:
    """Compute SHA256 hex digest of a file, streaming in chunks."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def hash_changed(path: Path, known_hash: str) -> bool:
    current = compute_hash(path)
    return current is not None and current != known_hash
