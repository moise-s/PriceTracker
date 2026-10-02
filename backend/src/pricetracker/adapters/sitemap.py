"""Sitemap-based product discovery for markets whose robots.txt disallows search.

The sitemap is the discovery channel sites publish explicitly for automated
clients. Product URLs are indexed by the words in their slug, and candidates are
pre-selected deterministically with the product's matching rules. The slug is
only a hint: equivalence is decided later from the product page's structured data
(slugs can be lossy or stale, e.g. ``12kg`` for 1,2 kg).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta

from defusedxml import ElementTree

from pricetracker.adapters.base import DocumentCache
from pricetracker.adapters.http import FetchError, PoliteClient
from pricetracker.domain.matching import MatchSpec
from pricetracker.domain.text import normalize, phrase_in, stem, tokens

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_TRAILING_ID = re.compile(r"-(\d{5,})$")


@dataclass(frozen=True)
class SitemapEntry:
    url: str
    slug: str
    text: str  # normalised words of the slug, product id removed

    @property
    def product_id(self) -> str | None:
        match = _TRAILING_ID.search(self.slug)
        return match.group(1) if match else None


def parse_urlset(xml_text: str) -> tuple[list[str], list[str]]:
    """Return (page urls, child sitemap urls) from a sitemap or sitemap index."""
    root = ElementTree.fromstring(xml_text.encode() if isinstance(xml_text, str) else xml_text)
    tag = root.tag.split("}")[-1]
    locs = [
        el.text.strip()
        for el in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        if el.text
    ]
    if not locs:
        locs = [el.text.strip() for el in root.iter("loc") if el.text]
    if tag == "sitemapindex":
        return [], locs
    return locs, []


def entry_from_url(url: str, slug: str) -> SitemapEntry:
    text = normalize(_TRAILING_ID.sub("", slug).replace("-", " "))
    return SitemapEntry(url=url, slug=slug, text=text)


class SitemapIndex:
    def __init__(self, entries: list[SitemapEntry]):
        self.entries = entries

    def __len__(self) -> int:
        return len(self.entries)

    def candidates(self, spec: MatchSpec, limit: int) -> list[SitemapEntry]:
        scored: list[tuple[float, int, str, SitemapEntry]] = []
        wanted = [t for t in tokens(spec.search_terms[0]) if not t.isdigit()]
        size_hints = _size_hints(spec)
        for entry in self.entries:
            text = entry.text
            if any(phrase_in(word, text) for word in spec.excluded):
                continue
            if not all(any(phrase_in(option, text) for option in group) for group in spec.required):
                continue
            if (
                spec.strict_brand
                and spec.brands
                and not any(phrase_in(b, text) for b in spec.brands)
            ):
                continue
            slug_tokens = set(tokens(text))
            overlap = sum(1 for word in wanted if stem(word) in slug_tokens)
            score = float(overlap)
            if any(phrase_in(hint, text) for hint in size_hints):
                score += 1.5
            if spec.brands and any(phrase_in(b, text) for b in spec.brands):
                score += 1.0
            extra = max(0, len(slug_tokens) - len(wanted) - 2)
            score -= 0.15 * extra
            scored.append((-score, len(entry.slug), entry.slug, entry))
        scored.sort()
        return [item[3] for item in scored[:limit]]


def _size_hints(spec: MatchSpec) -> list[str]:
    if spec.size is None:
        return ["kg"] if spec.sold_by == "weight" else []
    quantity = spec.size.quantity.normalize()
    unit = spec.size.unit.value
    text = f"{quantity:f}".rstrip("0").rstrip(".") if "." in f"{quantity:f}" else f"{quantity:f}"
    hints = [f"{text} {unit}"]
    if unit == "kg":
        grams = (spec.size.quantity * 1000).normalize()
        hints.append(f"{grams:f} g")
    if unit == "g" and spec.size.quantity >= 1000:
        hints.append(f"{(spec.size.quantity / 1000).normalize():f} kg")
    if unit == "un":
        hints.extend([f"{text} unidades", f"c {text}", f"com {text}"])
    return hints


async def load_index(
    client: PoliteClient,
    cache: DocumentCache,
    *,
    cache_key: str,
    sitemap_urls: list[str],
    probe_pattern: str | None,
    url_filter: re.Pattern[str],
    slug_of: re.Pattern[str],
    canonical: str | None = None,
    ttl: timedelta = timedelta(days=3),
    max_probe: int = 12,
) -> SitemapIndex:
    """Build (or load from cache) the product index of a market.

    ``probe_pattern`` (e.g. ``https://host/sitemap/product-{n}.xml``) is used for
    VTEX stores that publish product sitemaps without listing them in the index.
    """
    cached = cache.get_json("sitemap-index", cache_key)
    if cached:
        return SitemapIndex([SitemapEntry(**row) for row in cached])
    pages: list[str] = []
    queue = list(sitemap_urls)
    seen: set[str] = set()
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        result = await client.get(url, accept="application/xml,text/xml")
        if result.status != 200:
            continue
        found, children = parse_urlset(result.text)
        pages.extend(found)
        queue.extend(children)
    if probe_pattern:
        for n in range(max_probe):
            url = probe_pattern.format(n=n)
            if url in seen:
                continue
            try:
                result = await client.get(url, accept="application/xml,text/xml")
            except FetchError:
                break
            if result.status != 200:
                break
            found, _ = parse_urlset(result.text)
            pages.extend(found)
            if len(found) < 5000:
                break
    entries: dict[str, SitemapEntry] = {}
    for page in pages:
        if not url_filter.search(page):
            continue
        match = slug_of.search(page)
        if not match:
            continue
        url = page if canonical is None else canonical.format(path=match.group(0))
        entries[url] = entry_from_url(url, match.group("slug"))
    index = SitemapIndex(list(entries.values()))
    cache.put_json(
        "sitemap-index",
        cache_key,
        [{"url": e.url, "slug": e.slug, "text": e.text} for e in index.entries],
        ttl,
    )
    return index
