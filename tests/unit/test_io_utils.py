# tests/unit/test_io_utils.py
from pathlib import Path

import pytest

from docharvester_pro.io_utils import dedup_path, ensure_parent, slugify


def test_slugify_basic():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("Über Café") == "uber-cafe"
    assert slugify("  spaces  ") == "spaces"


def test_dedup_path(tmp_path: Path):
    original = tmp_path / "file.md"
    original.write_text("x")
    second = dedup_path(original)
    assert second.name == "file (1).md"
    second.write_text("y")
    third = dedup_path(original)
    assert third.name == "file (2).md"


def test_ensure_parent(tmp_path: Path):
    target = tmp_path / "a" / "b" / "c.txt"
    ensure_parent(target)
    assert target.parent.exists()
