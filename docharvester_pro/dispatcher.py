# filename: docharvester_pro/dispatcher.py
"""Dispatch targets to appropriate processors based on their type."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncGenerator, Sequence, Union

from .logger import log, Phase

_FILE_RE = re.compile(r"^(file://)?[A-Za-z]:[/\\\\]|^/")

async def dispatch(
    target: str,
    output_dir: Path,
    split_mode: str,
    concurrency: int
) -> AsyncGenerator[dict, None]:
    """
    Dispatch a target (URL or file path) to the appropriate processor.
    
    Args:
        target: URL, local HTML file, or directory containing HTML files
        output_dir: Directory where output files will be written
        split_mode: How to split the content ("none", "lines", or "paragraphs")
        concurrency: Maximum number of concurrent operations
        
    Yields:
        Job information and results
    """
    # Handle different target types (URL, file, directory)
    if target.startswith(('http://', 'https://')):
        # Process URL
        yield {"type": "url", "target": target, "status": "processing"}
        # Implement URL processing logic here
    elif Path(target).is_dir():
        # Process directory
        yield {"type": "directory", "target": target, "status": "processing"}
        # Implement directory processing logic here
    elif Path(target).exists():
        # Process file
        yield {"type": "file", "target": target, "status": "processing"}
        # Implement file processing logic here
    else:
        yield {"type": "unknown", "target": target, "status": "error", "message": "Invalid target"}
                return Job(raw, str(soup or html))

            # heavy → schedule for Playwright
            from .html_render import render  # local import to avoid heavy deps at import‑time

            rendered = await render(raw)
            return Job(raw, rendered)

    for coro in asyncio.as_completed(map(_worker, deduped)):
        yield await coro
