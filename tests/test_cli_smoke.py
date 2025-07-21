# filename: tests/test_cli_smoke.py
import subprocess, sys, pathlib, textwrap, json, os, tempfile

def test_cli_help():
    ret = subprocess.run(
        [sys.executable, "-m", "docharvester_pro.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert ret.returncode == 0 and "scrape_to_markdown.py" in ret.stdout
