# docharvester_pro/fetchers/playwright_async.py
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError  # type: ignore

from ..logging_utils import log_json


__all__ = ["fetch"]

# ------------------------------ internal helpers -----------------------------


class _BrowserContextPool:
    """
    Lazily‑creates a single Playwright Chromium browser
    and hands out incognito contexts under a semaphore.
    """

    _lock = asyncio.Lock()
    _pw = None
    _browser: Optional[Browser] = None
    _sem: Optional[asyncio.Semaphore] = None

    def __init__(self, max_concurrency: int = 4) -> None:
        self.max_concurrency = max_concurrency

    async def _ensure_browser(self) -> None:
        async with self._lock:
            if self._browser is not None:
                return
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)
            self._sem = asyncio.Semaphore(self.max_concurrency)

    @asynccontextmanager
    async def context(self) -> AsyncIterator[BrowserContext]:
        """Yield a new incognito context with resource‑blocking rules."""
        await self._ensure_browser()
        assert self._browser and self._sem  # for mypy

        async with self._sem:
            context = await self._browser.new_context()
            await context.route(
                "**/*",
                lambda route, request: asyncio.create_task(
                    route.abort()
                    if request.resource_type in {"image", "media", "font", "stylesheet"}
                    else route.continue_()
                ),
            )
            try:
                yield context
            finally:
                await context.close()

    async def shutdown(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()


_pool = _BrowserContextPool()


COOKIE_BANNER_JS = """
[...document.querySelectorAll('button, a')].filter(e => {
  const text = (e.innerText || '').toLowerCase();
  return /accept|agree|got it|allow|close/.test(text);
}).slice(0,3).forEach(btn => btn.click());
"""


async def _render_page(page: Page, url: str, timeout: float) -> str:
    await page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
    # kill simple cookie banners & wait a tick
    await page.evaluate(COOKIE_BANNER_JS).catch(lambda _: None)
    await page.wait_for_timeout(300)
    html = await page.content()
    return html


# ------------------------------- public API ----------------------------------


async def fetch(url: str, timeout: float = 30.0) -> str:
    """
    Fully renders *url* in a headless Chromium page and returns the final
    DOM as HTML.  Raises any Playwright exceptions after logging.

    Parameters
    ----------
    url : str
    timeout : float
        Seconds before giving up (applied to `page.goto`).

    Returns
    -------
    str
        Final HTML.
    """
    async with _pool.context() as ctx:
        try:
            page = await ctx.new_page()
            html = await _render_page(page, url, timeout)
            log_json(url=url, phase="fetch", status="ok", details={"mode": "playwright"})
            return html
        except TimeoutError as exc:
            log_json(
                url=url,
                phase="fetch",
                status="error",
                msg="Timeout in Playwright",
                details={"timeout": timeout},
            )
            raise exc
        except Exception as exc:  # noqa: BLE001
            log_json(url=url, phase="fetch", status="error", msg=str(exc))
            raise


# graceful shutdown for test/cli
async def _shutdown() -> None:  # pragma: no cover
    await _pool.shutdown()
