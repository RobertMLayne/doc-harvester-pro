# docs/README.md
# Docharvester‑Pro  – HTML → Markdown at scale
A modern, fully‑async utility that screenshots, harvests, and converts rich HTML
(including JavaScript‑rendered pages) into clean, split‑friendly Markdown.

## Quick‑start
```bash
# 1. Install the package (editable) and Playwright browsers
git clone https://github.com/your‑org/docharvester‑pro.git
cd docharvester‑pro
pip install -e .
python -m playwright install  # one‑off

# 2. Run the CLI
docharvester-pro https://docs.python.org --split paragraphs --out docs.md
````

| Flag                              | Description                          | Default      |
| --------------------------------- | ------------------------------------ | ------------ |
| `--split {none,lines,paragraphs}` | Markdown splitter strategy           | `paragraphs` |
| `--engine {aiohttp,playwright}`   | Force fetcher; otherwise auto‑chosen | *auto*       |
| `--concurrency N`                 | Max parallel network ops             | `8`          |
| `--out PATH`                      | Output file or directory             | `./out`      |

See `docs/CHANGELOG.md` for release history and `docs/CONTRIBUTING.md` for the
developer guide.