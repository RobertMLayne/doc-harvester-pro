# docharvester_pro/md_tools/convert.py
"""
HTML ➜ Markdown conversion powered by BeautifulSoup + markdownify.

Design goals
------------
* Deterministic output – strip scripts/ads, normalise whitespace.
* Footnote‑style links for cleaner diffs.
* Extensible via kwargs (see `CONVERT_OPTS` below).
"""
from __future__ import annotations

import re
from typing import Mapping, Any

from bs4 import BeautifulSoup
from bs4.filter import SoupStrainer
from markdownify import markdownify as _md

# ---- defaults ----------------------------------------------------------------

CONVERT_OPTS: Mapping[str, Any] = {
    "heading_style": "ATX",
    "bullets": "*",
    "strip": ["script", "style", "noscript"],
    "newline_style": "UNIX",
    "autolinks": False,
    "escape_asterisks": False,
}


def _clean_whitespace(md: str) -> str:
    """Collapse ≥3 consecutive blank lines to max 2 and strip trailing space."""
    md = re.sub(r"[ \t]+$", "", md, flags=re.MULTILINE)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


# ---- public API --------------------------------------------------------------

def convert_html_to_markdown(
    html: str,
    *,
    strainer: SoupStrainer | None = None,
    markdown_opts: Mapping[str, Any] | None = None,
) -> str:
    """
    Convert *html* to markdown.

    Parameters
    ----------
    html:
        Raw HTML string.
    strainer:
        Optional BeautifulSoup *SoupStrainer* limiting parsed subtree.
        Example: ``SoupStrainer("main")``.
    markdown_opts:
        Extra/override options passed to markdownify.

    Returns
    -------
    Markdown text (trailing LF guaranteed).
    """
    soup = BeautifulSoup(html, "lxml", parse_only=strainer)
    # strip comments
    for comment in soup(text=lambda t: isinstance(t, type(soup.string)) and t.startswith("<!--")):
        comment.extract()

    opt = {**CONVERT_OPTS, **(markdown_opts or {})}
    markdown = _md(str(soup), **opt)
    return _clean_whitespace(markdown)
