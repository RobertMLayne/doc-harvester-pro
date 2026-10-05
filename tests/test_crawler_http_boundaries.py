"""Offline counterexamples for remotely supplied crawler destinations."""

import asyncio
from contextlib import asynccontextmanager
import socket
from types import SimpleNamespace

import aiohttp
import pytest

from docharvester_pro import scrape_to_markdown as crawler
from docharvester_pro.safe_http import (
    PublicHttpSession,
    PublicResolver,
    SeedScope,
    UnsafeDestination,
    public_address,
)


class FakeBody:
    def __init__(self, chunks):
        self.chunks = chunks
        self.reads = 0

    async def iter_chunked(self, _size):
        self.reads += 1
        for chunk in self.chunks:
            yield chunk


class FakeResponse:
    def __init__(self, text="", *, status=200, headers=None, chunks=None):
        self.status = status
        self.headers = headers or {}
        self.charset = "utf-8"
        self.content = FakeBody(chunks if chunks is not None else [text.encode()])
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True


class FakeSession:
    def __init__(self, mapping, **options):
        self.mapping = mapping
        self.options = options
        self.calls = []
        self.closed = False

    def get(self, url, **options):
        self.calls.append((url, options))
        return self.mapping.get(url, FakeResponse(status=404))

    async def close(self):
        self.closed = True
        await self.options["connector"].close()


def fake_http(monkeypatch, mapping):
    sessions = []

    def factory(**options):
        session = FakeSession(mapping, **options)
        sessions.append(session)
        return session

    monkeypatch.setattr(aiohttp, "ClientSession", factory)
    return sessions


@pytest.mark.parametrize(
    "target",
    [
        "http://127.0.0.1/private.xml",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://100.64.0.1/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "file:///private.xml",
        "https://user:password@seed.example/private.xml",
        "https://@seed.example/private.xml",
        "https://seed.example:444/private.xml",
        "https://other.example/private.xml",
        "https://seed.example.evil.example/private.xml",
        "https://seed.example./private.xml",
        "https://%73eed.example/private.xml",
        "https://seed.example\\@127.0.0.1/private.xml",
        "https://seed.example/\nprivate.xml",
    ],
)
def test_untrusted_targets_cannot_expand_seed_scope(target):
    with pytest.raises(UnsafeDestination):
        SeedScope(["https://seed.example/start"]).require_url(target)


def test_explicit_secondary_origin_and_relative_paths_are_supported():
    scope = SeedScope(["https://seed.example/start", "https://cdn.example:8443/a"])
    assert scope.require_url("https://cdn.example:8443/b#section") == (
        "https://cdn.example:8443/b"
    )
    assert scope.resolve_url("https://seed.example/docs/a", "../b") == (
        "https://seed.example/b"
    )
    with pytest.raises(UnsafeDestination):
        scope.resolve_url("https://seed.example/a", "\n/hidden")


@pytest.mark.parametrize("target", ["http://127.1/", "http://2130706433/"])
def test_legacy_numeric_host_spellings_must_still_pass_connection_dns(target):
    scope = SeedScope([target])

    async def run():
        resolver = PublicResolver(scope, FakeResolver(["127.0.0.1"]))
        host, port = next(iter(scope.host_ports))
        with pytest.raises(UnsafeDestination):
            await resolver.resolve(host, port)

    asyncio.run(run())


class FakeResolver:
    def __init__(self, addresses):
        self.addresses = addresses
        self.calls = []
        self.closed = False

    async def resolve(self, host, port, family):
        self.calls.append((host, port, family))
        return [
            {
                "hostname": host,
                "host": address,
                "port": port,
                "family": socket.AF_INET6 if ":" in address else socket.AF_INET,
                "proto": 0,
                "flags": 0,
            }
            for address in self.addresses
        ]

    async def close(self):
        self.closed = True


@pytest.mark.parametrize(
    "answers",
    [
        ["127.0.0.1"],
        ["169.254.169.254"],
        ["::1"],
        ["1.1.1.1", "10.0.0.1"],
        ["seed.example"],
        [],
    ],
)
def test_all_dns_answers_are_checked_before_any_connector_receives_them(answers):
    async def run():
        resolver = PublicResolver(
            SeedScope(["https://seed.example/start"]), FakeResolver(answers)
        )
        with pytest.raises(UnsafeDestination):
            await resolver.resolve("seed.example", 443)

    asyncio.run(run())


def test_real_aiohttp_connector_receives_pinned_numeric_answers_and_rechecks_dns():
    async def run():
        delegate = FakeResolver(["1.1.1.1", "2606:4700:4700::1111"])
        resolver = PublicResolver(SeedScope(["https://seed.example"]), delegate)
        connector = aiohttp.TCPConnector(resolver=resolver, use_dns_cache=False)
        try:
            # Exercise aiohttp's actual resolver-to-connector boundary without
            # opening a socket. The checked addresses, not hostnames, are the
            # connection candidates. No second DNS lookup can select a new IP.
            answers = await connector._resolve_host("seed.example", 443)
            assert [answer["host"] for answer in answers] == delegate.addresses
            assert all(answer["flags"] & socket.AI_NUMERICHOST for answer in answers)
            assert all(answer["port"] == 443 for answer in answers)
            delegate.addresses = ["127.0.0.1"]
            with pytest.raises(UnsafeDestination):
                await connector._resolve_host("seed.example", 443)
            assert len(delegate.calls) == 2
        finally:
            await connector.close()
            await resolver.close()
        assert delegate.closed

    asyncio.run(run())


def test_resolver_refuses_unselected_host_and_port_before_dns():
    async def run():
        delegate = FakeResolver(["1.1.1.1"])
        resolver = PublicResolver(SeedScope(["https://seed.example"]), delegate)
        for host, port in [("other.example", 443), ("seed.example", 80)]:
            with pytest.raises(UnsafeDestination):
                await resolver.resolve(host, port)
        assert delegate.calls == []

    asyncio.run(run())


@pytest.mark.parametrize(
    "address",
    [
        "224.0.0.1",
        "ff02::1",
        "2002:7f00:1::1",
        "2002:0a00:0001::1",
        "64:ff9b::127.0.0.1",
        "64:ff9b::a00:1",
        "64:ff9b:1::a00:1",
        "2001:0000:4136:e378:8000:63bf:3fff:fdd2",
    ],
)
def test_multicast_and_private_embedded_addresses_are_denied(address):
    with pytest.raises(UnsafeDestination):
        public_address(address)


def test_relative_redirects_work_and_unused_redirect_entities_are_not_read(monkeypatch):
    redirect = FakeResponse(status=302, headers={"Location": "/target"})
    sessions = fake_http(
        monkeypatch,
        {
            "https://seed.example/start": redirect,
            "https://seed.example/target": FakeResponse("<main>Good</main>"),
        },
    )

    async def run():
        async with PublicHttpSession(["https://seed.example/start"]) as session:
            async with session.get("https://seed.example/start") as response:
                assert await response.text() == "<main>Good</main>"

    asyncio.run(run())
    assert [url for url, _ in sessions[0].calls] == [
        "https://seed.example/start",
        "https://seed.example/target",
    ]
    assert all(options["allow_redirects"] is False for _, options in sessions[0].calls)
    assert sessions[0].options["trust_env"] is False
    assert sessions[0].options["connector"]._ssl is True
    assert redirect.content.reads == 0 and redirect.closed
    assert sessions[0].closed


def test_main_retains_original_seed_scope_after_auto_discovery(monkeypatch):
    fake_http(monkeypatch, {})
    seed = "https://seed.example/start"
    untrusted = "https://other.example/from-discovery"
    args = SimpleNamespace(
        auto_discover=seed, urls=None, deduplicate=True, max_concurrency=8
    )
    monkeypatch.setattr(
        crawler,
        "build_arg_parser",
        lambda: SimpleNamespace(parse_args=lambda: args),
    )
    monkeypatch.setattr(crawler, "HashDB", lambda: object())

    async def discovered(_seeds):
        return [seed, untrusted]

    @asynccontextmanager
    async def context():
        yield object()

    observed = []

    async def process(url, session, *_args):
        observed.append(url)
        assert session.scope.origins == SeedScope([seed]).origins
        if url == untrusted:
            with pytest.raises(UnsafeDestination):
                session.require_url(url)

    monkeypatch.setattr(crawler, "discover_urls", discovered)
    monkeypatch.setattr(crawler, "playwright_context", context)
    monkeypatch.setattr(crawler, "process_url", process)
    crawler.main()
    assert observed == [seed, untrusted]


@pytest.mark.parametrize(
    "location",
    [
        "http://127.0.0.1/",
        "https://other.example/",
        "//169.254.169.254/",
        "file:///etc/passwd",
    ],
)
def test_forbidden_redirect_is_rejected_before_target_io(monkeypatch, location):
    sessions = fake_http(
        monkeypatch,
        {
            "https://seed.example/start": FakeResponse(
                status=302, headers={"Location": location}
            )
        },
    )

    async def run():
        async with PublicHttpSession(["https://seed.example/start"]) as session:
            with pytest.raises(UnsafeDestination):
                async with session.get("https://seed.example/start"):
                    pytest.fail("Unsafe redirect produced a response")

    asyncio.run(run())
    assert len(sessions[0].calls) == 1


@pytest.mark.parametrize("cycle", [True, False])
def test_redirect_loop_and_hop_limit_stop_before_the_next_request(monkeypatch, cycle):
    sessions = fake_http(
        monkeypatch,
        {
            "https://seed.example/a": FakeResponse(
                status=302, headers={"Location": "/a" if cycle else "/b"}
            ),
            "https://seed.example/b": FakeResponse(
                status=302, headers={"Location": "/c"}
            ),
        },
    )

    async def run():
        async with PublicHttpSession(
            ["https://seed.example/a"], max_redirects=1
        ) as session:
            with pytest.raises(UnsafeDestination):
                async with session.get("https://seed.example/a"):
                    pytest.fail("Redirect bound produced a response")

    asyncio.run(run())
    assert len(sessions[0].calls) == (1 if cycle else 2)


def test_body_limit_stops_stream_and_closes_response(monkeypatch):
    response = FakeResponse(chunks=[b"1234", b"5678"])
    sessions = fake_http(monkeypatch, {"https://seed.example/a": response})

    async def run():
        async with PublicHttpSession(
            ["https://seed.example/a"], max_bytes=5
        ) as session:
            with pytest.raises(RuntimeError, match="byte limit"):
                async with session.get("https://seed.example/a") as result:
                    await result.text()

    asyncio.run(run())
    assert response.closed and sessions[0].closed


def test_remote_robots_and_xml_targets_never_enter_queue_or_reach_request(monkeypatch):
    sessions = fake_http(
        monkeypatch,
        {
            "https://seed.example/robots.txt": FakeResponse(
                "Sitemap: http://127.0.0.1/private.xml\n"
                "Sitemap: https://other.example/remote.xml\n"
                "Sitemap: /catalog.xml"
            ),
            "https://seed.example/catalog.xml": FakeResponse(
                "<loc>http://169.254.169.254/metadata.xml</loc>"
                "<loc>https://seed.example/docs/page</loc>"
                "<loc>https://seed.example/catalog.xml</loc>"
            ),
        },
    )
    discovered = asyncio.run(crawler.discover_urls(["https://seed.example/start"]))
    assert "https://seed.example/docs/page" in discovered
    assert "https://seed.example/catalog.xml" in discovered
    assert not any(
        "127.0.0.1" in url or "169.254" in url or "other.example" in url
        for url in discovered
    )
    calls = sessions[0].calls
    assert all(url.startswith("https://seed.example/") for url, _ in calls)
    assert [url for url, _ in calls].count("https://seed.example/robots.txt") == 1
    assert [url for url, _ in calls].count("https://seed.example/catalog.xml") == 1


def test_http_seed_scheme_and_nondefault_port_are_preserved_for_robots(monkeypatch):
    sessions = fake_http(monkeypatch, {})
    asyncio.run(crawler.discover_urls(["http://seed.example:8080/start"]))
    assert sessions[0].calls[0][0] == "http://seed.example:8080/robots.txt"
    assert all(
        url.startswith("http://seed.example:8080/") for url, _ in sessions[0].calls
    )


def test_discovery_queue_bound_prevents_remote_fanout(monkeypatch):
    sessions = fake_http(
        monkeypatch,
        {
            "https://seed.example/robots.txt": FakeResponse("Sitemap: /catalog.xml"),
            "https://seed.example/catalog.xml": FakeResponse(
                "".join(
                    f"<loc>https://seed.example/{number}.xml</loc>"
                    for number in range(100)
                )
            ),
        },
    )
    discovered = asyncio.run(
        crawler.discover_urls(["https://seed.example/start"], max_urls=5)
    )
    assert len(discovered) == 5
    assert len(sessions[0].calls) <= 6


def test_static_probe_and_fetch_use_the_same_redirect_policy(monkeypatch):
    sessions = fake_http(
        monkeypatch,
        {
            "https://seed.example/page": FakeResponse(
                status=302, headers={"Location": "http://127.0.0.1/private"}
            )
        },
    )

    async def run():
        async with PublicHttpSession(["https://seed.example/page"]) as session:
            with pytest.raises(UnsafeDestination):
                await crawler.likely_static(session, "https://seed.example/page")
            with pytest.raises(UnsafeDestination):
                await crawler.fetch_static(session, "https://seed.example/page")

    asyncio.run(run())
    assert len(sessions[0].calls) == 2
    assert all(url == "https://seed.example/page" for url, _ in sessions[0].calls)


def test_static_response_metadata_and_304_behavior_are_preserved(monkeypatch):
    fake_http(
        monkeypatch,
        {
            "https://seed.example/page": FakeResponse(
                "<main>Page</main>", headers={"ETag": "v1"}
            ),
            "https://seed.example/unchanged": FakeResponse(status=304),
        },
    )

    async def run():
        async with PublicHttpSession(["https://seed.example/page"]) as session:
            assert await crawler.likely_static(session, "https://seed.example/page")
            assert await crawler.fetch_static(session, "https://seed.example/page") == (
                "<main>Page</main>",
                "v1",
            )
            assert await crawler.fetch_static(
                session, "https://seed.example/unchanged"
            ) == ("", "not-modified")

    asyncio.run(run())
