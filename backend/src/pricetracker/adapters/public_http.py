"""Bounded HTTPS transport for administrator-supplied public websites.

Resolve every destination and pin the socket to a public IP, retaining the
original Host and TLS SNI. Redirects use the same transport and validation.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlsplit, urlunsplit

import httpx

from pricetracker.adapters.http import NotAllowedHost, UpstreamError
from pricetracker.services.images import UnsafeUrl, resolve_public_host

MAX_DOCUMENT_BYTES = 4 * 1024 * 1024


def public_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.port not in (None, 443)
        ):
            raise ValueError
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if ":" in host:
            host = f"[{host}]"
        return urlunsplit(("https", host, parts.path or "/", parts.query, ""))
    except (ValueError, UnicodeError) as exc:
        raise NotAllowedHost("Use uma URL HTTPS pública, sem credenciais, na porta 443.") from exc


class PublicHttpsTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport | None = None):
        self.inner = inner or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = httpx.URL(public_url(str(request.url)))
        try:
            address = await asyncio.to_thread(resolve_public_host, url.host, 443)
        except (UnsafeUrl, OSError) as exc:
            # No request is issued until all DNS answers are known to be public.
            raise NotAllowedHost("O site precisa resolver para uma rede pública.") from exc
        headers = request.headers.copy()
        headers["Host"] = url.host
        pinned = httpx.Request(
            request.method,
            url.copy_with(host=address),
            headers=headers,
            stream=request.stream,
            extensions={**request.extensions, "sni_hostname": url.host},
        )
        response = await self.inner.handle_async_request(pinned)
        try:
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > MAX_DOCUMENT_BYTES:
                    raise UpstreamError("A página excede o limite de 4 MB.")
                body.extend(chunk)
            result_headers = response.headers.copy()
            for name in ("content-encoding", "content-length", "transfer-encoding"):
                result_headers.pop(name, None)
            return httpx.Response(response.status_code, headers=result_headers, content=bytes(body))
        finally:
            await response.aclose()

    async def aclose(self) -> None:
        await self.inner.aclose()
