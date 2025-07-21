# docharvester_pro/md_tools/splitters.py
"""Flexible splitter factory for post‑processed Markdown."""
from __future__ import annotations

from typing import Callable, List


def _split_none(text: str) -> List[str]:  # pragma: no cover
    """Return the whole document as a single part."""
    return [text]


def _split_lines(text: str) -> List[str]:
    """Individual non‑empty lines preserving original order."""
    return [ln for ln in text.splitlines() if ln.strip()]


def _split_paragraphs(text: str) -> List[str]:
    """Paragraphs are blocks separated by ≥1 blank line."""
    parts, buf = [], []
    for line in text.splitlines():
        if line.strip():
            buf.append(line)
        elif buf:
            parts.append("\n".join(buf).strip())
            buf = []
    if buf:
        parts.append("\n".join(buf).strip())
    return parts


_SPLITTERS = {
    "none": _split_none,
    "lines": _split_lines,
    "paragraphs": _split_paragraphs,
}


def get_splitter(mode: str = "none") -> Callable[[str], List[str]]:
    """
    Return a splitter callable.

    Raises
    ------
    KeyError – if *mode* unknown.
    """
    try:
        return _SPLITTERS[mode]
    except KeyError as exc:  # pragma: no cover
        raise KeyError(f"Unknown splitter mode '{mode}'. "
                       f"Expected one of {list(_SPLITTERS)}") from exc
