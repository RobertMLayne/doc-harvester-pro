# filename: docharvester_pro/splitters.py
"""Markdown splitting utilities."""
from __future__ import annotations
import enum, itertools
from typing import Iterable, List

class SplitMode(str, enum.Enum):
    NONE = "none"
    LINES = "lines"
    PARAGRAPHS = "paragraphs"

def split(text: str, mode: SplitMode, parts: int) -> List[str]:
    """Return *parts* slices of *text* using the requested strategy."""
    if mode == SplitMode.NONE:
        chunk = len(text) // parts or len(text)
        return [text[i : i + chunk] for i in range(0, len(text), chunk)]

    if mode == SplitMode.LINES:
        units: Iterable[str] = text.split("\n")
    else:  # paragraphs
        units = text.split("\n\n")

    groups = _round_robin(units, parts)
    return ["\n".join(group).strip() for group in groups if group]

def _round_robin(units: Iterable[str], parts: int) -> List[List[str]]:
    buckets = [[] for _ in range(parts)]
    for idx, val in enumerate(units):
        buckets[idx % parts].append(val)
    return buckets
