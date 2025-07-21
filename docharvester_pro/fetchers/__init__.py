# docharvester_pro/fetchers/__init__.py
from __future__ import annotations

from types import TracebackType
from typing import Any, AsyncIterator, Optional, Type

_FETCHERS_REGISTRY: dict[str, "BaseFetcher"] = {}


def register_fetcher(scheme: str) -> Any:  # decorator
    def _decorator(cls: Type["BaseFetcher"]) -> Type["BaseFetcher"]:
        _FETCHERS_REGISTRY[scheme] = cls()  # singleton per fetcher type
        return cls

    return _decorator


class BaseFetcher:
    """Simple interface all concrete fetchers must implement."""

    async def fetch(self, url: str) -> str:  # pragma: no cover
        raise NotImplementedError

    # optional async‑context‑manager cleanup for pooled resources
    async def __aenter__(self) -> "BaseFetcher":  # noqa: D401
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> bool:
        return False

    # -- helpers --------------------------------------------------------- #
    @staticmethod
    def get_for_url(url: str) -> "BaseFetcher":
        scheme = url.split(":", 1)[0] if "://" in url else "file"
        return _FETCHERS_REGISTRY.get(scheme) or _FETCHERS_REGISTRY["file"]


__all__ = ["BaseFetcher", "register_fetcher"]
