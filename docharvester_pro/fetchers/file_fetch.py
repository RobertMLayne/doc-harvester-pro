# docharvester_pro/fetchers/file_fetch.py
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Final

from docharvester_pro.logging_utils import JSONLogger
from docharvester_pro.fetchers import BaseFetcher, register_fetcher

_LOGGER: Final = JSONLogger.get()


@register_fetcher("file")
class FileFetcher(BaseFetcher):
    """Reads an HTML file from local disk or `file://` URL."""

    async def fetch(self, url: str) -> str:
        path = Path(url.removeprefix("file://")).expanduser().resolve()
        _LOGGER.info(url=url, phase="fetch", status="pending", msg="read local file")

        def _read() -> str:
            return path.read_text(encoding="utf‑8")

        try:
            html = await asyncio.to_thread(_read)
            _LOGGER.info(url=url, phase="fetch", status="ok", msg="file read")
            return html
        except FileNotFoundError as err:
            _LOGGER.error(
                url=url, phase="fetch", status="error", msg="file not found", details=str(err)
            )
            raise
