"""Polite, safe HTTP client shared by all market adapters.

Guarantees, enforced in code rather than by convention:

* every URL is checked against the host's robots.txt (cached) before fetching;
* only https URLs on the market's domain allowlist are fetched, and every redirect
  hop is validated against the same allowlist;
* per-host concurrency limit and minimum interval between requests;
* timeouts, retries with exponential backoff + jitter (honouring Retry-After);
* a per-market circuit breaker that stops hammering a failing source;
* anti-bot challenges, 401/403/429 are surfaced as ``Blocked`` and never bypassed.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from pricetracker.adapters.robots import RobotsPolicy, parse_robots
from pricetracker.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# Strong, interstitial-only signals. Plain "recaptcha" is NOT a signal: many normal
# storefront pages embed it for newsletter forms.
CHALLENGE_MARKERS = (
    "cf-chl-",
    "/cdn-cgi/challenge-platform",
    "just a moment...",
    "attention required! | cloudflare",
    "_incapsula_resource",
    "request unsuccessful. incapsula",
    "px-captcha",
    "<title>access denied</title>",
)


class FetchError(Exception):
    """Base class for typed fetch failures."""

    error_type = "adapter_error"

    def __init__(self, message: str, *, url: str | None = None, status: int | None = None):
        super().__init__(message)
        self.url = url
        self.status = status


class Blocked(FetchError):
    error_type = "blocked"


class RobotsDisallowed(Blocked):
    error_type = "blocked_by_robots"


class FetchTimeout(FetchError):
    error_type = "timeout"


class UpstreamError(FetchError):
    error_type = "upstream_error"


class NotAllowedHost(FetchError):
    error_type = "host_not_allowed"


class CircuitOpen(Blocked):
    error_type = "circuit_open"


@dataclass
class FetchResult:
    url: str
    status: int
    text: str
    headers: dict[str, str]
    elapsed_ms: int

    def json(self) -> Any:
        import json

        return json.loads(self.text)


@dataclass
class _HostState:
    semaphore: asyncio.Semaphore
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_request: float = 0.0


@dataclass
class CircuitBreaker:
    threshold: int
    failures: int = 0
    opened_at: float | None = None
    cooldown_seconds: float = 300.0

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()

    @property
    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at > self.cooldown_seconds:
            self.opened_at = None  # half-open: allow a trial request
            self.failures = self.threshold - 1
            return False
        return True


def host_allowed(host: str, allowed_domains: Iterable[str]) -> bool:
    host = host.lower().rstrip(".")
    for domain in allowed_domains:
        domain = domain.lower().lstrip(".")
        if host == domain or host.endswith("." + domain):
            return True
    return False


class PoliteClient:
    def __init__(
        self,
        *,
        allowed_domains: Iterable[str],
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        robots_loader: Callable[[str], RobotsPolicy | None] | None = None,
        robots_saver: Callable[[str, RobotsPolicy, int, str], None] | None = None,
        sleep: Callable[[float], Any] = asyncio.sleep,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.allowed_domains = [d.lower() for d in allowed_domains]
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.http_timeout_seconds, connect=10.0),
            follow_redirects=False,
            transport=transport,
            headers={
                "User-Agent": self.settings.http_user_agent,
                "Accept-Language": "pt-BR,pt;q=0.9",
                **(extra_headers or {}),
            },
        )
        self._hosts: dict[str, _HostState] = {}
        self._robots: dict[str, RobotsPolicy] = {}
        self._robots_lock = asyncio.Lock()
        self._robots_loader = robots_loader
        self._robots_saver = robots_saver
        self._sleep = sleep
        self.breaker = CircuitBreaker(threshold=self.settings.circuit_breaker_threshold)
        self.request_count = 0
        self.urls: list[str] = []

    async def __aenter__(self) -> PoliteClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- policy checks ---------------------------------------------------------------

    def _check_url(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme != "https":
            raise NotAllowedHost(f"only https is allowed: {url}", url=url)
        if not parts.hostname or not host_allowed(parts.hostname, self.allowed_domains):
            raise NotAllowedHost(f"host outside the market allowlist: {parts.hostname}", url=url)

    async def robots_for(self, host: str) -> RobotsPolicy:
        async with self._robots_lock:
            if host in self._robots:
                return self._robots[host]
            policy = self._robots_loader(host) if self._robots_loader else None
            if policy is None:
                robots_url = f"https://{host}/robots.txt"
                status, text = 0, ""
                try:
                    status, text = await self._fetch_robots(robots_url)
                except FetchError as exc:
                    logger.warning("robots.txt fetch failed for %s: %s", host, exc)
                policy = parse_robots(text, status)
                if self._robots_saver and status:
                    self._robots_saver(host, policy, status, text)
            self._robots[host] = policy
            return policy

    async def _fetch_robots(self, url: str) -> tuple[int, str]:
        current = url
        for _ in range(5):
            self._check_url(current)
            try:
                response = await self._client.get(current)
            except httpx.TimeoutException as exc:
                raise FetchTimeout("robots.txt timeout", url=current) from exc
            except httpx.HTTPError as exc:
                raise UpstreamError(f"robots.txt network error: {exc}", url=current) from exc
            if response.status_code in (301, 302, 303, 307, 308) and "location" in response.headers:
                current = urljoin(current, response.headers["location"])
                parts = urlsplit(current)
                if not parts.hostname or not host_allowed(parts.hostname, self.allowed_domains):
                    raise NotAllowedHost(
                        "robots.txt redireciona para fora do domínio permitido.", url=current
                    )
                continue
            return response.status_code, response.text[:500_000]
        return 404, ""

    async def ensure_allowed(self, url: str) -> None:
        self._check_url(url)
        host = urlsplit(url).hostname or ""
        policy = await self.robots_for(host)
        if not policy.is_allowed(url, self.settings.http_user_agent):
            rule = policy.matching_rule(url, self.settings.http_user_agent)
            raise RobotsDisallowed(f"robots.txt disallows this URL ({rule})", url=url)

    # --- fetching ----------------------------------------------------------------------

    def _host_state(self, host: str) -> _HostState:
        state = self._hosts.get(host)
        if state is None:
            state = _HostState(asyncio.Semaphore(self.settings.http_per_host_concurrency))
            self._hosts[host] = state
        return state

    async def _pace(self, state: _HostState) -> None:
        async with state.lock:
            wait = state.last_request + self.settings.http_min_interval_seconds - time.monotonic()
            if wait > 0:
                await self._sleep(wait + random.uniform(0, 0.25))
            state.last_request = time.monotonic()

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        accept: str = "text/html,application/json;q=0.9,*/*;q=0.8",
    ) -> FetchResult:
        return await self.request("GET", url, headers=headers, cookies=cookies, accept=accept)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        json_body: Any = None,
        accept: str = "application/json",
    ) -> FetchResult:
        if self.breaker.is_open:
            raise CircuitOpen("circuit breaker open after repeated failures", url=url)
        attempts = max(1, self.settings.http_max_retries)
        last_error: FetchError | None = None
        for attempt in range(1, attempts + 1):
            try:
                result = await self._request_once(method, url, headers, cookies, json_body, accept)
                self.breaker.record_success()
                return result
            except (Blocked, NotAllowedHost):
                self.breaker.record_failure()
                raise
            except (FetchTimeout, UpstreamError) as exc:
                last_error = exc
                if attempt == attempts:
                    break
                retry_after = getattr(exc, "retry_after", None)
                delay = (
                    retry_after if retry_after is not None else min(20.0, 1.5 * 2 ** (attempt - 1))
                )
                await self._sleep(delay + random.uniform(0, delay / 2))
        self.breaker.record_failure()
        assert last_error is not None
        raise last_error

    async def _request_once(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None,
        cookies: dict[str, str] | None,
        json_body: Any,
        accept: str,
    ) -> FetchResult:
        current = url
        for _hop in range(6):
            await self.ensure_allowed(current)
            host = urlsplit(current).hostname or ""
            state = self._host_state(host)
            async with state.semaphore:
                await self._pace(state)
                started = time.monotonic()
                request_headers = {"Accept": accept, **(headers or {})}
                if cookies:
                    # Explicit per-request cookies; the client never persists site cookies, so
                    # one store's context can never leak into another request.
                    request_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
                try:
                    response = await self._client.request(
                        method,
                        current,
                        headers=request_headers,
                        json=json_body,
                    )
                except httpx.TimeoutException as exc:
                    raise FetchTimeout(f"timeout fetching {host}", url=current) from exc
                except httpx.HTTPError as exc:
                    raise UpstreamError(
                        f"network error: {type(exc).__name__}", url=current
                    ) from exc
                elapsed = int((time.monotonic() - started) * 1000)
            self._client.cookies.clear()
            self.request_count += 1
            self.urls.append(_redact_url(current))
            status = response.status_code
            if status in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    raise UpstreamError("redirect without location", url=current, status=status)
                current = urljoin(current, location)
                if status == 303:
                    method, json_body = "GET", None
                continue  # the next loop iteration validates host allowlist and robots
            text = response.text
            if status in (401, 403, 407, 451) or _looks_like_challenge(status, text):
                raise Blocked(f"access blocked (HTTP {status})", url=current, status=status)
            if status == 429:
                error = UpstreamError("rate limited (HTTP 429)", url=current, status=status)
                error.retry_after = _retry_after(response.headers.get("retry-after"))  # type: ignore[attr-defined]
                raise error
            if status >= 500:
                raise UpstreamError(f"upstream error (HTTP {status})", url=current, status=status)
            return FetchResult(
                url=current,
                status=status,
                text=text,
                headers={k.lower(): v for k, v in response.headers.items()},
                elapsed_ms=elapsed,
            )
        raise UpstreamError("too many redirects", url=url)


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return min(60.0, float(value))
    except ValueError:
        return None


def _looks_like_challenge(status: int, text: str) -> bool:
    if status not in (200, 202, 403, 503) or len(text) > 80_000:
        return False
    head = text[:10_000].lower()
    return any(marker in head for marker in CHALLENGE_MARKERS)


def _redact_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}" + ("?…" if parts.query else "")
