# tests/unit/test_md_tools.py
import textwrap

import pytest

from docharvester_pro.md_tools import convert_html_to_markdown, get_splitter


HTML_SAMPLE = """
<!doctype html><html><body>
<h1>Title</h1><p>Hello <b>world</b>!</p>
<!-- comment should vanish --><p>Second ¶.</p>
</body></html>
"""


def test_convert_basic():
    md = convert_html_to_markdown(HTML_SAMPLE)
    expected = textwrap.dedent("""\
        # Title

        Hello **world**!

        Second ¶.
        """)
    assert md == expected


@pytest.mark.parametrize("mode,expect", [
    ("none", 1),
    ("lines", 3),
    ("paragraphs", 2),
])
def test_splitters(mode, expect):
    splitter = get_splitter(mode)
    parts = splitter("L1\n\nL2\nL3\n")
    assert len(parts) == expect


def test_unknown_splitter():
    with pytest.raises(KeyError):
        get_splitter("bogus")
