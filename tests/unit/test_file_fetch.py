# tests/unit/test_file_fetch.py
import asyncio
from pathlib import Path

import pytest

from docharvester_pro.fetchers.file_fetch import FileFetcher


@pytest.mark.asyncio
async def test_file_fetcher_reads_content(tmp_path: Path):
    html_path = tmp_path / "sample.html"
    html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")

    fetcher = FileFetcher()
    result = await fetcher.fetch(str(html_path))
    assert "Hello" in result


@pytest.mark.asyncio
async def test_file_fetcher_missing_file(tmp_path: Path):
    fetcher = FileFetcher()
    with pytest.raises(FileNotFoundError):
        await fetcher.fetch(str(tmp_path / "nope.html"))
