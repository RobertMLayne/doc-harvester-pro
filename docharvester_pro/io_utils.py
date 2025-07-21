# docharvester_pro/io_utils.py
"""Filesystem & string helpers (no I/O side‑effects except mkdir parents)."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_DUPLICATE_SUFFIX = re.compile(r" \((\d+)\)$")


def slugify(text: str, *, max_len: int = 80) -> str:
    """
    Convert arbitrary text to a filesystem‑safe slug.

    * Lower‑cases, removes diacritics, replaces non‑alnum with '-'.
    * Collapses repeated separators and trims to `max_len`.
    """
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = _SLUG_PATTERN.sub("-", norm.lower()).strip("-")
    return slug[:max_len] or "untitled"


def dedup_path(path: Path) -> Path:
    """
    Ensure *path* is unique by adding an auto‑incrementing suffix.

    Returns the first non‑existing sibling path:
    >>> dedup_path(Path('foo.md'))  # doctest: +SKIP
    PosixPath('foo (1).md')
    """
    if not path.exists():
        return path

    stem, suffix = path.stem, path.suffix
    match = _DUPLICATE_SUFFIX.search(stem)
    counter = int(match.group(1)) + 1 if match else 1
    base_stem = _DUPLICATE_SUFFIX.sub("", stem)

    while True:
        candidate = path.with_name(f"{base_stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def ensure_parent(path: Path) -> None:
    """Create *path.parent* idempotently."""
    path.parent.mkdir(parents=True, exist_ok=True)
