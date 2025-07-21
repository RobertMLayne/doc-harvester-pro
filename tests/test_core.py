import hashlib, textwrap
from scrape_to_markdown import (
    slugify, split_markdown, html_to_markdown, HashDB
)

def test_slugify():
    assert slugify("Hello World?") == "hello-world"

def test_split_markdown_paragraphs():
    md = textwrap.dedent("""\
        Para1.

        Para2.

        Para3.

        Para4.
    """)
    parts = split_markdown(md, "paragraphs", 2)
    assert len(parts) == 2
    assert parts[0].startswith("Para1")

def test_hashdb_roundtrip(tmp_path):
    db_file = tmp_path / "state.db"
    db = HashDB(str(db_file))
    assert not db.is_unchanged("u", "h1")
    assert db.is_unchanged("u", "h1")
    assert not db.is_unchanged("u", "h2")

HTML = "<main><h1>Hello</h1><p>Body</p></main>"
def test_html_to_markdown():
    md = html_to_markdown(HTML)
    assert md.startswith("# Hello")
