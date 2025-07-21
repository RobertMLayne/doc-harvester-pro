# tests/unit/test_aiohttp_fetch.py
from unittest import mock

import aiohttp
import pytest

from docharvester_pro.fetchers.aiohttp_fetch import AioHttpFetcher


@pytest.mark.asyncio
async def test_aiohttp_fetcher_success(monkeypatch):
    html_body = "<html><main><h1>Hi!</h1></main></html>"

    async def _fake_get(*_, **__):
        class _Resp:
            status = 200

            async def text(self):
                return html_body

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            def raise_for_status(self):
                pass

        return _Resp()

    with mock.patch("aiohttp.ClientSession.get", new=_fake_get):
        with mock.patch("aiohttp.ClientSession.__aenter__") as _enter, mock.patch(
            "aiohttp.ClientSession.__aexit__"
        ):
            _enter.return_value = aiohttp.ClientSession()
            fetcher = AioHttpFetcher()
            content = await fetcher.fetch("https://example.com")
            assert "<main" in content and "Hi!" in content
