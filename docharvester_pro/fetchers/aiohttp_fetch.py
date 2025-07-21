# docharvester_pro/fetchers/aiohttp_fetch.py
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Final

import aiohttp
from aiohttp.client_exceptions import ClientError
from bs4.filter import SoupStrainer
from bs4 import BeautifulSoup
from aiohttp import ClientTimeout

from docharvester_pro.logging_utils import JSONLogger
from docharvester_pro.fetchers import BaseFetcher, register_fetcher

_LOGGER: Final = JSONLogger.get()
_MAIN_ONLY = SoupStrainer("main")  # lightweight server‑side filtering


@asynccontextmanager
async def _shared_session() -> aiohttp.ClientSession:  # pragma: no cover
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False, limit=10),
        headers={"User‑Agent": "docharvester-pro/0.1"},
    ) as sess:
        yield sess


_SHARED_SESSION: asyncio.Task[aiohttp.ClientSession] | None = None


async def _get_session() -> aiohttp.ClientSession:
    global _SHARED_SESSION  # noqa: PLW0603
    if _SHARED_SESSION is None:
        loop = asyncio.get_running_loop()
        _SHARED_SESSION = loop.create_task(_shared_session().__aenter__())
    return await _SHARED_SESSION


@register_fetcher("http")
@register_fetcher("https")
class AioHttpFetcher(BaseFetcher):
    """Fetches HTML over HTTP(S) with best‑effort simplification."""

    async def fetch(self, url: str) -> str:
        sess = await _get_session()
        _LOGGER.info(url=url, phase="fetch", status="pending", msg="GET request")

        try:
            timeout = ClientTimeout(total=30)
            async with sess.get(url, timeout=timeout) as resp:
                resp.raise_for_status()
                raw_html = await resp.text()
                # Pre‑filter to <main> to save parsing downstream
                html = str(BeautifulSoup(raw_html, "lxml", parse_only=_MAIN_ONLY))
                _LOGGER.info(url=url, phase="fetch", status="ok", msg="downloaded")
                return html
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error(
                url=url, phase="fetch", status="error", msg="request failed", details=str(err)
            )
            raise
