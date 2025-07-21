# filename: tests/test_splitters.py
import pytest
from docharvester_pro.splitters import split, SplitMode

@pytest.mark.parametrize("mode", [SplitMode.LINES, SplitMode.PARAGRAPHS])
def test_even_split(mode):
    txt = "l1\nl2\nl3\nl4\nl5\n"
    parts = split(txt, mode, 5)
    assert len(parts) == 5
    assert all(parts)  # no empty chunks

def test_none_mode():
    txt = "abc" * 100
    pieces = split(txt, SplitMode.NONE, 4)
    assert "".join(pieces) == txt
