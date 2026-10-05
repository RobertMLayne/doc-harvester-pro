"""Imported timestamps must not select arbitrary export directories."""

import html
import os
import subprocess
import sys
from pathlib import Path

import pytest

from docharvester_pro.utils.chat_export_splitter import split_chat_export


def _conversation(tmp_path: Path, timestamp: str) -> Path:
    source = tmp_path / "conversation.html"
    source.write_text(
        '<div class="chat-item" data-timestamp="'
        + html.escape(timestamp, quote=True)
        + '"><h3>A real conversation</h3><p>Fixture message</p></div>',
        encoding="utf-8",
    )
    return source


@pytest.mark.parametrize(
    "timestamp",
    [
        "../escape",
        "../../bad",
        "/absolute",
        "C:\\escape",
        "C:/escape",
        "\\\\host\\bad",
        "2026/10/05",
        "2026-2-03",
        "2026-10-5",
        "２０２６-１０-０５",
        "2026-02-29",
        "2024-02-30",
        "0000-01-01",
        "2026-13-01",
        "2026-00-05",
        "2026-01-00",
        "2026-04-31",
        "not-a-date",
        "",
        "2026-10-0",
    ],
)
def test_invalid_timestamp_rejects_before_any_output(tmp_path, monkeypatch, timestamp):
    # Write input before guarding every output operation, including on the base.
    source = _conversation(tmp_path, timestamp)
    root = tmp_path / "output"
    attempted = []
    original_mkdir = Path.mkdir
    original_write_text = Path.write_text

    def guard(path, operation):
        attempted.append((operation, path))
        try:
            # Lexical normalization blocks UNC/device escapes without probing
            # remote shares while reproducing the unpatched Windows behavior.
            normalized = Path(os.path.normpath(os.path.abspath(path)))
            normalized.relative_to(root.absolute())
        except ValueError:
            pytest.fail("Fixture blocked an attempted write outside its output")

    def mkdir(path, *args, **kwargs):
        guard(path, "mkdir")
        return original_mkdir(path, *args, **kwargs)

    def write_text(path, *args, **kwargs):
        guard(path, "write_text")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(Path, "write_text", write_text)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        split_chat_export(source, root, date_folders=True)
    assert attempted == []
    assert not root.exists()
    assert {entry.name for entry in tmp_path.iterdir()} == {source.name}


@pytest.mark.parametrize(
    ("timestamp", "folder"),
    [
        ("2024-02-29", "2024-02-29"),
        ("2026-10-05T00:14:24.411Z", "2026-10-05"),
        ("2026-10-05T08:00:00-04:00", "2026-10-05"),
        ("2026-10-05 08:00:00+00:00", "2026-10-05"),
        ("9999-12-31", "9999-12-31"),
    ],
)
def test_valid_dates_and_timestamps_keep_markdown_location(tmp_path, timestamp, folder):
    source = _conversation(tmp_path, timestamp)
    output = tmp_path / "output"
    split_chat_export(source, output, date_folders=True)
    exported = output / folder / "a-real-conversation.md"
    assert "Fixture message" in exported.read_text(encoding="utf-8")
    assert list(output.iterdir()) == [output / folder]


@pytest.mark.parametrize("timestamp", ["../escape", "2026-02-29"])
def test_flat_exports_do_not_use_the_timestamp_as_a_path(tmp_path, timestamp):
    source = _conversation(tmp_path, timestamp)
    output = tmp_path / "output"
    split_chat_export(source, output)
    exported = output / "a-real-conversation.md"
    assert "Fixture message" in exported.read_text(encoding="utf-8")
    assert list(output.iterdir()) == [exported]


def test_cli_preserves_date_folder_argument_and_markdown_output(tmp_path):
    source = _conversation(tmp_path, "2026-10-05T00:14:24.411Z")
    output = tmp_path / "output"
    script = (
        Path(__file__).resolve().parents[1]
        / "docharvester_pro"
        / "utils"
        / "chat_export_splitter.py"
    )
    result = subprocess.run(
        [sys.executable, "-B", str(script), str(source), str(output), "--date-folders"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    exported = output / "2026-10-05" / "a-real-conversation.md"
    assert "Fixture message" in exported.read_text(encoding="utf-8")
