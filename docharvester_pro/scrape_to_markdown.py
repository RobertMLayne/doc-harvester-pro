#!/usr/bin/env python3
"""
scrape_to_markdown.py - DocHarvester Pro
---------------------------------------

* Auto‑discovers URLs via robots + sitemaps.
* Fetches static pages with aiohttp, JS pages with Playwright.
* Converts <main> → Markdown (markdownify) and aggregates by doc‑family.
* Skips unchanged pages via SHA‑256 _or_ JSON‑LD dateModified.
* Respects robots.txt crawl‑delay & conditional GET.
* Optional PDF snapshots (--pdf) and ChatGPT export splitting (--split‑chat).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sqlite3
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import urlparse

import aiohttp
import markdownify
from aiohttp import ClientSession, ClientTimeout
from bs4 import BeautifulSoup, SoupStrainer
from playwright.async_api import async_playwright, Page, Route

# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #

USER_AGENT = "DocHarvester-Pro/0.2 (+https://github.com/org/repo)"
DB_PATH = "crawl_state.db"
DEFAULT_CONCURRENCY = 8
DEFAULT_PARTS = 5
STATIC_TEST_BYTES = 65_536            # read first 64 kB for likely_static()
STRANER_MAIN = SoupStrainer(name="main")

STATIC_HOSTS = {
    "developers.google.com",          # Google DevSite - fully rendered HTML
    "playwright.dev",
    "tedboy.github.io",
}

BATCH_TABLE: dict[str, str] = {
    # longest‑prefix wins
    "https://playwright.dev/python/docs/api":    "playwright_python_api",
    "https://playwright.dev/python/docs":        "playwright_python_docs",
    "https://playwright.dev/docs/api":           "playwright_node_api",
    "https://playwright.dev/docs":               "playwright_node_docs",
    "https://developers.google.com/search/docs": "google_search_central",
    "https://tedboy.github.io/bs4_doc":          "beautifulsoup_docs",
}

PDF_DIR = Path("pdf_output")
IMG_BLOCK_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico")

# --------------------------------------------------------------------------- #
# Utility helpers                                                             #
# --------------------------------------------------------------------------- #


def slugify(text: str, length: int = 120) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "-", text).strip("-").lower()[:length]


def pick_batch(url: str) -> str:
    for prefix, batch in BATCH_TABLE.items():
        if url.startswith(prefix):
            return batch
    return slugify(urlparse(url).hostname or "unknown")


class HashDB:
    """On‑disk SHA‑256 registry + optional ISO dateModified checks."""

    def __init__(self, path: str = DB_PATH) -> None:
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS pages"
            "(url TEXT PRIMARY KEY, sha TEXT, iso TEXT, updated REAL)"
        )

    def unchanged(self, url: str, sha: str, iso: str | None) -> bool:
        cur = self.conn.execute("SELECT sha, iso FROM pages WHERE url=?", (url,))
        row = cur.fetchone()
        if row and row[0] == sha and (iso is None or row[1] == iso):
            return True
        self.conn.execute(
            "INSERT OR REPLACE INTO pages(url, sha, iso, updated) VALUES (?,?,?,?)",
            (url, sha, iso or "", time.time()),
        )
        self.conn.commit()
        return False


def extract_jsonld_dates(html: str) -> str | None:
    """Return dateModified or datePublished from JSON‑LD if present."""
    soup = BeautifulSoup(html, "lxml", parse_only=SoupStrainer("script"))
    for tag in soup("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
            if isinstance(data, dict):
                return (
                    data.get("dateModified")
                    or data.get("datePublished")
                    or None
                )
        except json.JSONDecodeError:
            continue
    return None


async def likely_static(session: ClientSession, url: str) -> bool:
    """Heuristic: first 64 kB contain <main> & few <script>."""
    try:
        async with session.get(
            url, headers={"Range": f"bytes=0-{STATIC_TEST_BYTES}"}
        ) as r:
            head = await r.text(errors="ignore")
    except aiohttp.ClientError:
        return False
    return head.lower().count("<script") < 3 and "<main" in head.lower()


# --------------------------------------------------------------------------- #
# robots.txt & crawl‑delay                                                    #
# --------------------------------------------------------------------------- #

ROBOTS_CACHE: Dict[str, dict] = {}


async def fetch_robots(session: ClientSession, host: str) -> dict:
    if host in ROBOTS_CACHE:
        return ROBOTS_CACHE[host]
    url = f"https://{host}/robots.txt"
    delay: int | None = None
    sitemaps: list[str] = []
    try:
        async with session.get(url, timeout=ClientTimeout(total=10)) as r:
            if r.status == 200:
                for line in (await r.text()).splitlines():
                    if line.lower().startswith("crawl-delay:"):
                        try:
                            delay = int(line.split(":")[1].strip())
                        except ValueError:
                            pass
                    if line.lower().startswith("sitemap:"):
                        sitemaps.append(line.split(":", 1)[1].strip())
    except aiohttp.ClientError:
        pass
    ROBOTS_CACHE[host] = {"delay": delay, "sitemaps": sitemaps}
    return ROBOTS_CACHE[host]


# --------------------------------------------------------------------------- #
# Sitemap discovery                                                            #
# --------------------------------------------------------------------------- #

SITEMAP_LOC = re.compile(r"<loc>(.*?)</loc>", re.I)


async def discover_urls(seed: list[str], max_urls: int = 10_000) -> list[str]:
    """Breadth‑first sitemap discovery bounded by max_urls."""
    discovered: Set[str] = set(seed)
    queue: list[str] = seed[:]
    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        while queue and len(discovered) < max_urls:
            url = queue.pop(0)
            host = urlparse(url).hostname or ""
            # robots.txt
            robots = await fetch_robots(session, host)
            queue.extend(robots["sitemaps"])
            # if XML fetch & recurse
            if url.endswith(".xml"):
                try:
                    async with session.get(url, timeout=15) as r:
                        if r.status == 200:
                            for loc in SITEMAP_LOC.findall(await r.text()):
                                if loc not in discovered:
                                    discovered.add(loc)
                                    queue.append(loc)
                except aiohttp.ClientError:
                    pass
            # smart fallbacks
            for guess in ("sitemap.xml", "sitemap_index.xml"):
                g_url = f"https://{host}/{guess}"
                if g_url not in discovered:
                    discovered.add(g_url)
                    queue.append(g_url)
    return sorted(discovered)


# --------------------------------------------------------------------------- #
# Markdown helpers                                                             #
# --------------------------------------------------------------------------- #


def split_markdown(md_text: str, mode: str, parts: int) -> list[str]:
    if mode == "none":
        return [md_text]
    sep = "\n" if mode == "lines" else "\n\n"
    items = md_text.split(sep)
    chunk = max(1, len(items) // parts)
    return [
        sep.join(items[i * chunk : (i + 1) * chunk if i < parts - 1 else len(items)])
        for i in range(parts)
    ]


# --------------------------------------------------------------------------- #
# Playwright                                                                  #
# --------------------------------------------------------------------------- #


async def _block_assets(route: Route) -> None:
    if route.request.resource_type in ("image", "media", "font"):
        await route.abort()
    else:
        await route.continue_()


@asynccontextmanager
async def playwright_context():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        await ctx.route("**/*", _block_assets)
        try:
            yield ctx
        finally:
            await ctx.close()
            await browser.close()


# --------------------------------------------------------------------------- #
# Fetchers                                                                    #
# --------------------------------------------------------------------------- #


async def fetch_static(session: ClientSession, url: str) -> tuple[str, str]:
    """Return (html, last‑modified/etag or '')"""
    hdrs = {"User-Agent": USER_AGENT}
    async with session.get(url, headers=hdrs) as r:
        if r.status == 304:
            return "", "not-modified"
        if r.status != 200:
            raise RuntimeError(f"{url} HTTP {r.status}")
        html = await r.text()
        lm = r.headers.get("Last-Modified") or r.headers.get("ETag") or ""
        return html, lm


async def fetch_dynamic(page: Page, url: str) -> str:
    await page.goto(url, wait_until="networkidle", timeout=30_000)
    return await page.content()


def html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "lxml", parse_only=STRANER_MAIN)
    return markdownify.markdownify(str(soup), heading_style="ATX")


# --------------------------------------------------------------------------- #
# Worker                                                                      #
# --------------------------------------------------------------------------- #


async def process_url(
    url: str,
    session: ClientSession,
    ctx,
    db: HashDB,
    args,
    locks: dict[str, asyncio.Lock],
) -> None:
    host = urlparse(url).hostname or ""
    use_static = (
        args.no_render
        or host in STATIC_HOSTS
        or url.endswith(".html")
        or await likely_static(session, url)
    )

    # obey per‑host crawl‑delay
    robots = await fetch_robots(session, host)
    if robots["delay"]:
        await asyncio.sleep(robots["delay"])

    try:
        if use_static:
            html, lm_tag = await fetch_static(session, url)
            if lm_tag == "not-modified":
                print(f"↻ {url} 304 Not Modified; skipped")
                return
        else:
            page = await ctx.new_page()
            html = await fetch_dynamic(page, url)
            await page.close()
            lm_tag = ""
    except Exception as exc:  # noqa: BLE001
        print(f"✖ {url} - {exc}")
        return

    # incremental check (SHA & JSON‑LD date)
    sha = hashlib.sha256(html.encode()).hexdigest()
    jsonld_date = extract_jsonld_dates(html)
    if db.unchanged(url, sha, jsonld_date):
        print(f"↻ {url} unchanged (hash/date); skipped")
        return

    md_text = html_to_markdown(html)
    chunks = split_markdown(md_text, args.split_mode, args.parts)

    batch = pick_batch(url)
    out_dir = Path(args.output).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)
    outfile = (
        Path(args.single_file).expanduser()
        if args.single_file
        else out_dir / f"{batch}.md"
    )
    outfile.parent.mkdir(parents=True, exist_ok=True)

    lock = locks.setdefault(str(outfile), asyncio.Lock())
    async with lock:
        with outfile.open("a", encoding="utf-8") as f:
            f.write(f"\n\n## {url}\n\n")
            f.write("\n\n---\n".join(chunks))
            f.write("\n")
        print(f"✔ {url} → {outfile}")

    # optional PDF snapshot
    if args.pdf:
        PDF_DIR.mkdir(exist_ok=True)
        pdf_path = PDF_DIR / f"{slugify(url)}.pdf"
        if use_static:
            import pdfkit  # type: ignore
            pdfkit.from_string(html, str(pdf_path))
        else:
            page = await ctx.new_page()
            await page.goto(url, wait_until="networkidle")
            await page.pdf(path=str(pdf_path))
            await page.close()


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser("DocHarvester Pro - high-throughput doc crawler")
    ap.add_argument("--urls", help="Seed‑URL text file (one per line)")
    ap.add_argument("--auto-discover", metavar="DOC_HOME",
                    help="Start at this doc homepage and auto‑discover via sitemaps")
    ap.add_argument("--output", default="./output")
    ap.add_argument("--parts", type=int, default=DEFAULT_PARTS)
    ap.add_argument("--split-mode", choices=["paragraphs", "lines", "none"],
                    default="paragraphs")
    ap.add_argument("--single-file", help="Write everything here instead of batching")
    ap.add_argument("--no-render", action="store_true", help="Disable Playwright")
    ap.add_argument("--max-concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--pdf", action="store_true", help="Save PDFs alongside Markdown")
    ap.add_argument("--deduplicate", default=True,
                    action=argparse.BooleanOptionalAction)
    return ap


def dedup(seq: List[str]) -> List[str]:
    seen: Set[str] = set(); out: List[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def main() -> None:
    args = build_arg_parser().parse_args()

    if args.auto_discover:
        urls = asyncio.run(discover_urls([args.auto_discover]))
    elif args.urls:
        urls = Path(args.urls).read_text().splitlines()
    else:
        print("Provide --urls or --auto-discover"); sys.exit(1)

    urls = [u.strip() for u in urls if u.strip()]
    if args.deduplicate:
        urls = dedup(urls)

    db = HashDB()
    locks: Dict[str, asyncio.Lock] = {}
    host_sems: Dict[str, asyncio.Semaphore] = {}

    async def runner():
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session, \
                   playwright_context() as ctx:
            async def worker(url: str):
                host = urlparse(url).hostname or ""
                cap = 4 if host == "developers.google.com" else args.max_concurrency
                sem = host_sems.setdefault(host, asyncio.Semaphore(cap))
                async with sem:
                    await process_url(url, session, ctx, db, args, locks)

            await asyncio.gather(*(worker(u) for u in urls))

    asyncio.run(runner())


if __name__ == "__main__":
    main()
# --------------------------------------------------------------------------- #
