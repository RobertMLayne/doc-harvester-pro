#!/usr/bin/env python3
"""Split a ChatGPT exported conversation HTML into Markdown chunks.

Usage:
    python docharvester_pro/utils/chat_export_splitter.py chat.html ./md --date-folders
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify as md


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _date_folder(stamp: str) -> str:
    """Construct a single directory component from an actual calendar date."""
    error = "data-timestamp must start with a valid YYYY-MM-DD calendar date"
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", stamp) is None:
        raise ValueError(error)
    try:
        # Imported HTML must not supply an absolute path or parent traversal.
        # Reconstruct the component instead of returning the untrusted text.
        return date.fromisoformat(stamp).isoformat()
    except ValueError:
        raise ValueError(error) from None


def split_chat_export(html_file: Path, out_dir: Path, *, date_folders=False) -> None:
    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "lxml")
    for div in soup.select("div.chat-item"):
        title = div.select_one("h3").text.strip() or "untitled"
        stamp = div["data-timestamp"][:10]  # YYYY-MM-DD
        sub = out_dir / (_date_folder(stamp) if date_folders else "")
        sub.mkdir(parents=True, exist_ok=True)
        md_text = md(str(div), heading_style="ATX")
        (sub / f"{slugify(title)}.md").write_text(md_text, encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("out_dir")
    ap.add_argument("--date-folders", action="store_true")
    args = ap.parse_args()
    split_chat_export(
        Path(args.html), Path(args.out_dir), date_folders=args.date_folders
    )
