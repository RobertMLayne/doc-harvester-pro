# tests/unit/test_dispatcher.py
import asyncio
from pathlib import Path

import pytest

from docharvester_pro import dispatcher
from docharvester_pro.fetchers import aiohttp_fetch


@pytest.mark.asyncio
async def test_dispatcher_local_file(tmp_path, monkeypatch):
    # create temp file
    p = tmp_path / "x.html"
    p.write_text("<html>file ok</html>")
    html = await dispatcher.get_html(str(p))
    assert "file ok" in html

@pytest.mark.asyncio
async def test_dispatcher_fallback(monkeypatch):
    async def _boom(url: str):
        raise RuntimeError("fail")

    monkeypatch.setattr(aiohttp_fetch, "fetch", _boom)
    # monkeypatch heavy fetcher to cheap stub to avoid real Playwright
    monkeypatch.setattr(
        dispatcher.playwright_async, "fetch", lambda url, timeout=30.0: asyncio.sleep(0, result="heavy ok")
    )
    html = await dispatcher.get_html("https://example.com")
    assert "heavy ok" == html
