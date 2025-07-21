# filename: docharvester_pro/html_render.py
"""Playwright rendering path (single browser)."""
from __future__ import annotations
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from bs4 import BeautifulSoup, SoupStrainer
from .logger import log, Phase

_BROWSER = None  # reused between calls

async def _ensure_browser():
    global _BROWSER
    if _BROWSER is None:
        pw = await async_playwright().start()
        _BROWSER = await pw.chromium.launch(headless=True, args=["--disable-images"])
    return _BROWSER

async def render(url: str) -> str:
    """Return rendered `<main>` (or `<body>` fallback)."""
    browser = await _ensure_browser()
    context = await browser.new_context()
    page = await context.new_page()
    try:
        await page.goto(url, timeout=30_000)
        await page.wait_for_load_state("networkidle", timeout=20_000)
        html = await page.content()
    except PWTimeout as err:
        log(url, Phase.RENDER, "timeout", "render_timeout", details=str(err))
        raise
    finally:
        await context.close()

    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main") or soup.body
    return str(main)
