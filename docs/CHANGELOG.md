# docs/CHANGELOG.md
## Unreleased
* Constrain the standalone sitemap crawler's aiohttp requests to explicit seed
  origins and public connection addresses, check every redirect hop, and bound
  discovery queues and response bodies. This policy covers robots, sitemaps,
  static probes, and static page fetching. It does not control Playwright or
  pdfkit resource requests, the packaged CLI's separate fetchers, or historical
  crawler copies in other repositories.

## 0.1.0 – 2025‑06‑26
* Initial public release:
  * Async fetchers (`aiohttp`, `Playwright`)
  * Pluggable splitter / converter pipelines
  * Rich JSON logging & 90 %+ test coverage
  * Fully automated CI (lint, type‑check, tests)
