# docharvester_pro/cli.py
"""Command‑line interface for docharvester‑pro."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List

from docharvester_pro.dispatcher import dispatch
from .logging_utils import JSONLogger

_LOG = JSONLogger.get()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="docharvester-pro",
        description="Scrape one or more URLs/HTML files and emit Markdown.",
    )
    p.add_argument(
        "targets",
        metavar="TARGET",
        nargs="+",
        help="URL, local HTML file, or directory containing HTML files.",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("."),
        help="Destination directory (default: current working dir).",
    )
    p.add_argument(
        "--split",
        choices=("none", "lines", "paragraphs"),
        default="paragraphs",
        help="Granularity of Markdown splitting.",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=os.cpu_count() or 4,
        help="Max concurrent fetches (default: number of CPUs).",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per‑target timeout in seconds.",
    )
    return p


async def _run_async(args) -> int:
    tasks: List[asyncio.Task[int]] = []
    sem = asyncio.Semaphore(args.concurrency)

    async def _guarded(target: str) -> int:
        async with sem:
            try:
                async def consume_iterator(it):
                    result = 0
                    async for job in it:
                        # Process each job if needed
                        pass
                    return result  # Return appropriate value based on success/failure

                return await asyncio.wait_for(
                    consume_iterator(dispatch(target, args.output, args.split, args.concurrency)),
                    timeout=args.timeout
                )
            except Exception as exc:  # pylint: disable=broad-except
                _LOG.error("unhandled-error", url=target, details=str(exc))
                return 1

    for target in args.targets:
        tasks.append(asyncio.create_task(_guarded(target)))

    results = await asyncio.gather(*tasks)
    failures = sum(r for r in results)
    return 0 if failures == 0 else 1


def main(argv: List[str] | None = None) -> None:  # pragma: no cover
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        exit_code = asyncio.run(_run_async(args))
    except KeyboardInterrupt:
        _LOG.warning("user-interrupt")
        exit_code = 2
    sys.exit(exit_code)
