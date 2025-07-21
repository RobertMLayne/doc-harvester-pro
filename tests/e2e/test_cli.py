# tests/e2e/test_cli.py
import asyncio
from pathlib import Path

import docharvester_pro.cli as cli


class _DummyDispatch:
    """Simulate dispatcher without touching network."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path

    async def __call__(self, target, output_dir, split):
        md_file = output_dir / f"{Path(target).stem}.md"
        md_file.write_text(f"# Dummy for {target}\n")
        return 0


def test_cli_smoke(monkeypatch, tmp_path):
    stub = _DummyDispatch(tmp_path)
    monkeypatch.setattr(cli, "dispatch", stub)  # type: ignore[attr-defined]

    argv = ["foo.html", "bar.html", "-o", str(tmp_path)]
    # run in subprocess‑style to exercise argument parsing
    asyncio.run(cli._run_async(cli._build_parser().parse_args(argv)))

    expected = {tmp_path / "foo.md", tmp_path / "bar.md"}
    assert {p for p in tmp_path.iterdir()} == expected
