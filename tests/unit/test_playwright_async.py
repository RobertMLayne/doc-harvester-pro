# tests/unit/test_playwright_async.py
import asyncio
from types import SimpleNamespace

import pytest

from docharvester_pro.fetchers import playwright_async


@pytest.mark.asyncio
async def test_playwright_fetch_monkeypatch(monkeypatch):
    """Simulate Playwright and ensure fetch returns expected HTML."""
    fake_html = "<html><body><h1>Hi</h1></body></html>"

    # --- stub Playwright API ---
    class _FakePage(SimpleNamespace):
        async def goto(self, *_a, **_kw):
            return None

        async def evaluate(self, *_a, **_kw):
            return None

        async def wait_for_timeout(self, *_a, **_kw):
            return None

        async def content(self):
            return fake_html

    class _FakeContext(SimpleNamespace):
        async def route(self, *_a, **_kw):
            return None

        async def new_page(self):
            return _FakePage()

        async def close(self):
            return None

    class _FakeBrowser(SimpleNamespace):
        async def new_context(self):
            return _FakeContext()

        async def close(self):
            return None

    class _FakePW(SimpleNamespace):
        async def start(self):
            return self

        async def stop(self):
            return None

        class chromium(SimpleNamespace):
            async def launch(*_a, **_kw):
                return _FakeBrowser()

    monkeypatch.setattr(
        playwright_async, "async_playwright", lambda: _FakePW()
    )

    # --- actual test ---
    html = await asyncio.wait_for(playwright_async.fetch("https://fake"), timeout=5)
    assert "<h1>Hi</h1>" in html
