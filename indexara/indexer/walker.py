"""Filesystem traversal with exclusion support."""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Callable, Iterator

import pathspec

from ..config.defaults import BUILTIN_EXCLUSIONS

logger = logging.getLogger(__name__)


def _load_indexignore(directory: Path) -> pathspec.PathSpec | None:
    ignore_file = directory / ".indexignore"
    if ignore_file.exists():
        try:
            with open(ignore_file) as f:
                lines = f.readlines()
            return pathspec.PathSpec.from_lines("gitwildmatch", lines)
        except Exception:
            return None
    return None


def build_exclusion_matcher(
    root: Path, extra_patterns: list[str] | None = None
) -> Callable[[Path], bool]:
    """Return a function that returns True if a path should be excluded."""
    patterns = list(BUILTIN_EXCLUSIONS)
    if extra_patterns:
        patterns.extend(extra_patterns)
    global_spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def should_exclude(path: Path) -> bool:
        rel = str(path.relative_to(root))
        if global_spec.match_file(rel):
            return True
        # Check per-directory .indexignore files
        for parent in path.parents:
            if parent == root or root in parent.parents or parent == root.parent:
                spec = _load_indexignore(parent)
                if spec:
                    try:
                        rel_to_parent = str(path.relative_to(parent))
                        if spec.match_file(rel_to_parent):
                            return True
                    except ValueError:
                        pass
            if parent == root:
                break
        return False

    return should_exclude


def walk_directory(
    root: Path,
    exclusion_fn: Callable[[Path], bool],
    follow_symlinks: bool = False,
) -> Iterator[Path]:
    """Yield non-excluded file paths under root."""
    visited_inodes: set[tuple[int, int]] = set()

    def _walk(directory: Path) -> Iterator[Path]:
        try:
            entries = list(os.scandir(str(directory)))
        except PermissionError:
            logger.warning("Permission denied: %s", directory)
            return

        for entry in entries:
            path = Path(entry.path)
            try:
                if exclusion_fn(path):
                    continue

                if entry.is_symlink():
                    if not follow_symlinks:
                        continue
                    real = path.resolve()
                    try:
                        st = real.stat()
                        inode = (st.st_dev, st.st_ino)
                        if inode in visited_inodes:
                            continue
                        visited_inodes.add(inode)
                    except OSError:
                        continue

                if entry.is_dir(follow_symlinks=follow_symlinks):
                    yield from _walk(path)
                elif entry.is_file(follow_symlinks=follow_symlinks):
                    yield path
            except PermissionError:
                logger.warning("Permission denied: %s", path)
            except OSError as e:
                logger.warning("OS error on %s: %s", path, e)

    yield from _walk(root)
