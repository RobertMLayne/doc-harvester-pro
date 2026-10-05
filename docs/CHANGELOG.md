# docs/CHANGELOG.md
## Unreleased
* Validate imported conversation timestamps before creating date folders.
  With `--date-folders`, the first ten characters must be an ASCII
  `YYYY-MM-DD` date that exists in the calendar. Absolute paths, traversal,
  malformed dates, and invalid calendar dates fail before that conversation's
  output is created. Valid dates and timestamp prefixes retain their existing
  Markdown location; flat exports retain their existing behavior.
* Add synthetic pytest regressions for refused paths/dates and actual CLI
  timestamp exports. Existing developer-selected input/output paths and
  pre-existing output-directory links remain trusted local configuration.

## 0.1.0 – 2025‑06‑26
* Initial public release:
  * Async fetchers (`aiohttp`, `Playwright`)
  * Pluggable splitter / converter pipelines
  * Rich JSON logging & 90 %+ test coverage
  * Fully automated CI (lint, type‑check, tests)
