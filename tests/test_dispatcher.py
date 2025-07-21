# filename: tests/test_dispatcher.py
import asyncio, builtins, types
import pytest
from docharvester_pro.dispatcher import _looks_heavy

def test_looks_heavy():
    light = "<html><script></script></html>"
    heavy = "<html>" + "<script></script>" * 20 + "</html>"
    assert not _looks_heavy(light)
    assert _looks_heavy(heavy)

@pytest.mark.asyncio
async def test_local_file(tmp_path, monkeypatch):
    fp = tmp_path / "hello.html"
    fp.write_text("<main>hi</main>")
    out = []
    async for job in __import__("docharvester_pro.dispatcher").dispatcher.dispatch(
        [str(fp)], snapshot=False, no_render=True, concurrency=1
    ):
        out.append(job)
    assert out[0].content == "<main>hi</main>"
