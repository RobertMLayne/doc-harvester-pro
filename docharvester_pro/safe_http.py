"""Public, seed-scoped HTTP for the standalone sitemap crawler.

This transport does not control Playwright or external PDF renderers. URL
validation alone also cannot constrain a machine's routing table or sandbox a
process. Keep those boundaries separate from this HTTP discovery policy.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from ipaddress import IPv4Address, IPv6Address, IPv6Network, ip_address
import socket
from urllib.parse import urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver
from aiohttp.resolver import ThreadedResolver
from yarl import URL


class UnsafeDestination(ValueError):
    """The destination was rejected before an HTTP request was sent."""


def public_address(value: str) -> str:
    """Accept only global unicast addresses, including embedded IPv4 checks."""
    try:
        address = ip_address(value)
    except ValueError as exc:
        raise UnsafeDestination("DNS answer is not a numeric IP address") from exc
    if (
        not address.is_global
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or address.is_loopback
        or address.is_link_local
    ):
        raise UnsafeDestination("Destination address is not public unicast")
    if isinstance(address, IPv6Address):
        if address.scope_id:
            raise UnsafeDestination("Scoped IPv6 destinations are not supported")
        if address.ipv4_mapped is not None:
            public_address(str(address.ipv4_mapped))
        if address.sixtofour is not None:
            public_address(str(address.sixtofour))
        if address in IPv6Network("64:ff9b::/96"):
            # The well-known NAT64 prefix routes its low 32 bits as IPv4.
            # A globally classified IPv6 literal can still target private IPv4.
            public_address(str(IPv4Address(int(address) & 0xFFFFFFFF)))
        if address in IPv6Network("64:ff9b:1::/48"):
            raise UnsafeDestination("Local-use NAT64 destinations are not public")
        if address.teredo is not None:
            # Teredo introduces two extra IPv4 routing identities, outside
            # this direct public-address policy; do not silently accept it.
            raise UnsafeDestination("Teredo destinations are not supported")
    return str(address)


def http_url(value: str) -> URL:
    if not isinstance(value, str) or not value:
        raise UnsafeDestination("Destination must be an HTTP(S) URL")
    if "\\" in value or any(ord(char) <= 32 or ord(char) == 127 for char in value):
        raise UnsafeDestination("Destination contains ambiguous URL characters")
    try:
        authority = urlsplit(value).netloc
        if "@" in authority or "%" in authority:
            raise UnsafeDestination("Encoded or credential-bearing hosts are denied")
        target = URL(value)
        host = target.raw_host
        if target.scheme not in {"http", "https"} or not host:
            raise UnsafeDestination("Destination must have an HTTP(S) origin")
        if target.user is not None or target.password is not None:
            raise UnsafeDestination("URL credentials are not permitted")
        if "%" in host or "@" in target.raw_authority:
            raise UnsafeDestination("Encoded or credential-bearing hosts are denied")
        port = target.port
        if port is None or not 1 <= port <= 65535:
            raise UnsafeDestination("Destination port is invalid")
        try:
            address = ip_address(host)
        except ValueError:
            address = None
        if address is not None:
            public_address(str(address))
        return target.with_fragment(None)
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, UnsafeDestination):
            raise
        raise UnsafeDestination("Destination URL is invalid") from exc


class SeedScope:
    """Exact scheme/host/port origins selected by the operator's seed list."""

    def __init__(self, seeds: list[str]):
        self.origins = frozenset(http_url(seed).origin() for seed in seeds)
        if not self.origins:
            raise UnsafeDestination("At least one explicit seed origin is required")
        self.host_ports = frozenset((url.raw_host, url.port) for url in self.origins)

    def require_url(self, value: str) -> str:
        target = http_url(value)
        if target.origin() not in self.origins:
            raise UnsafeDestination("Destination leaves the explicit seed origins")
        return str(target)

    def origin_url(self, value: str) -> str:
        return str(URL(self.require_url(value)).origin())

    def resolve_url(self, base: str, reference: str) -> str:
        if (
            not isinstance(reference, str)
            or "\\" in reference
            or any(ord(char) <= 32 or ord(char) == 127 for char in reference)
        ):
            raise UnsafeDestination("Reference contains ambiguous URL characters")
        try:
            authority = urlsplit(reference).netloc
            if "@" in authority or "%" in authority:
                raise UnsafeDestination(
                    "Encoded or credential-bearing reference hosts are denied"
                )
            target = URL(self.require_url(base)).join(URL(reference))
        except (ValueError, UnicodeError) as exc:
            raise UnsafeDestination("Reference URL is invalid") from exc
        return self.require_url(str(target))


class PublicResolver(AbstractResolver):
    """Return checked numeric answers to the connector, avoiding a second DNS lookup."""

    def __init__(self, scope: SeedScope, resolver: AbstractResolver | None = None):
        self.scope = scope
        self.resolver = resolver if resolver is not None else ThreadedResolver()

    async def resolve(self, host, port=0, family=socket.AF_INET):
        if (host, port) not in self.scope.host_ports:
            raise UnsafeDestination("DNS resolution leaves the explicit seed origins")
        answers = await self.resolver.resolve(host, port, family)
        if not answers:
            raise UnsafeDestination("Destination has no DNS addresses")
        checked = []
        for answer in answers:
            address = public_address(answer["host"])
            expected_family = (
                socket.AF_INET
                if isinstance(ip_address(address), IPv4Address)
                else socket.AF_INET6
            )
            if answer["family"] != expected_family:
                raise UnsafeDestination("DNS answer family does not match its address")
            checked.append(
                {
                    "hostname": host,
                    "host": address,
                    "port": port,
                    "family": expected_family,
                    "proto": socket.IPPROTO_TCP,
                    "flags": socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
                }
            )
        # Reject a mixed public/private set in full. The connector's fallback
        # addresses must all satisfy the same policy before any connection.
        return checked

    async def close(self):
        await self.resolver.close()


class BoundedResponse:
    def __init__(self, response, max_bytes: int):
        self.response = response
        self.status = response.status
        self.headers = response.headers
        self.max_bytes = max_bytes

    async def text(self, *, errors="strict"):
        body = bytearray()
        async for chunk in self.response.content.iter_chunked(65536):
            body.extend(chunk)
            if len(body) > self.max_bytes:
                raise RuntimeError("HTTP response exceeds the crawler byte limit")
        return body.decode(self.response.charset or "utf-8", errors=errors)


class PublicHttpSession:
    """Owned aiohttp session with checked redirects and connection-time DNS.

    The resolver validates the addresses actually supplied to TCPConnector,
    rather than validating a DNS lookup and then asking HTTP to resolve again.
    Numeric URL hosts are checked by SeedScope because aiohttp bypasses the
    resolver for them. Ambient proxies/netrc and TLS overrides are not accepted.
    """

    def __init__(self, seeds, *, headers=None, max_redirects=5, max_bytes=20_000_000):
        self.scope = SeedScope(seeds)
        self.headers = dict(headers or {})
        if not 0 <= max_redirects <= 10 or max_bytes < 1:
            raise ValueError("Invalid redirect or response byte limit")
        self.max_redirects = max_redirects
        self.max_bytes = max_bytes
        self.robots_cache = {}
        self.session = None
        self.resolver = None

    def require_url(self, value):
        return self.scope.require_url(value)

    async def __aenter__(self):
        self.resolver = PublicResolver(self.scope)
        connector = aiohttp.TCPConnector(
            resolver=self.resolver,
            use_dns_cache=False,
            limit=32,
            limit_per_host=8,
        )
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=30),
            trust_env=False,
        )
        return self

    async def __aexit__(self, *args):
        if self.session is not None:
            await self.session.close()
        if self.resolver is not None:
            await self.resolver.close()

    @asynccontextmanager
    async def get(self, url, *, headers=None, timeout=None):
        if self.session is None:
            raise RuntimeError("HTTP session is not open")
        current = self.require_url(url)
        seen = {current}
        options = {"headers": headers, "allow_redirects": False}
        if timeout is not None:
            options["timeout"] = timeout
        for hop in range(self.max_redirects + 1):
            async with self.session.get(current, **options) as response:
                if response.status not in {301, 302, 303, 307, 308}:
                    yield BoundedResponse(response, self.max_bytes)
                    return
                location = response.headers.get("Location")
                if not location:
                    raise UnsafeDestination("Redirect has no destination")
                target = self.scope.resolve_url(current, location)
                if target in seen or hop == self.max_redirects:
                    raise UnsafeDestination("Redirect loop or limit reached")
                seen.add(target)
                current = target
