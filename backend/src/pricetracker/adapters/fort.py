"""Fort Atacadista (www.fortatacadista.com.br, OSuper platform).

robots.txt disallows ``/busca``, ``/search``, ``/lojas`` and every URL with a query
string, and allows ``/produtos/``. The compliant path is: discover products in the
public sitemap, then read candidate product pages ``/produtos/<id>/<slug>`` (no
query string) with the first-party store cookie ``st_334`` that the site's own
store picker writes. The page state (``window.APOLLO_STATE``) holds regular,
promotional, multi-buy, Clube Mais and card prices for the selected store. The
rendered store is verified; a mismatch fails loudly instead of returning another
store's prices.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from selectolax.parser import HTMLParser

from pricetracker.adapters.base import AdapterContext, MarketAdapter, SearchOutcome, SearchQuery
from pricetracker.adapters.errors import ParseError, StoreContextError
from pricetracker.adapters.sitemap import load_index
from pricetracker.domain.listing import Listing, SaleUnit
from pricetracker.domain.money import to_money
from pricetracker.models.enums import Availability, ExtractionMethod

WWW = "https://www.fortatacadista.com.br"
SITEMAP = "https://fortatacadista.com.br/sitemap.xml"
PRODUCT_URL = re.compile(r"^https://(?:www\.)?fortatacadista\.com\.br/produtos/\d+/[a-z0-9-]+$")
SLUG = re.compile(r"/produtos/(?P<id>\d+)/(?P<slug>[a-z0-9-]+)$")
STORE_COOKIE = "st_334"
CLUB_PERSONA = "669932"  # Clube Mais


def store_cookie(store_id: str) -> dict[str, str]:
    value = quote(
        json.dumps({"id": str(store_id), "userSelected": True}, separators=(",", ":")), safe=""
    )
    return {STORE_COOKIE: value}


def _js_object_after(source: str, marker: str) -> dict[str, Any]:
    index = source.find(marker)
    if index < 0:
        return {}
    start = source.index("{", index)
    try:
        value, _ = json.JSONDecoder().raw_decode(source, start)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        following = re.search(r"window\.[A-Z_]+\s*=", source[start:])
        chunk = source[start : start + following.start()] if following else source[start:]
        chunk = re.sub(r"(?<=[:\[,])\s*undefined(?=\s*[,}\]])", "null", chunk.strip().rstrip(";"))
        try:
            value = json.loads(chunk)
        except json.JSONDecodeError as exc:
            raise ParseError(f"cannot decode {marker}") from exc
        return value if isinstance(value, dict) else {}


def _resolve(apollo: dict[str, Any], value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"__ref"}:
        return apollo.get(value["__ref"])
    return value


def _field(product: dict[str, Any], prefix: str) -> Any:
    for key, value in product.items():
        if key == prefix or key.startswith(prefix + "("):
            return value
    return None


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def parse_product_page(html: str, url: str, requested_store: str | None) -> Listing | None:
    tree = HTMLParser(html)
    node = tree.css_first("script#main-states")
    states = node.text() if node else ""
    apollo = _js_object_after(states, "window.APOLLO_STATE")
    initial = _js_object_after(states, "window.INITIAL_STATE")
    id_match = re.search(r"/produtos/(\d+)/", url)
    if not id_match:
        raise ParseError("URL without a product id")
    product_id = id_match.group(1)
    selected = (initial.get("app") or {}).get("selectedStore") or {}
    rendered_store = str(selected.get("id")) if selected.get("id") is not None else None
    if requested_store and rendered_store != str(requested_store):
        raise StoreContextError(
            f"a página foi renderizada para a loja {rendered_store}, não para a loja {requested_store}"
        )
    json_ld: dict[str, Any] = {}
    for script in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            json_ld = data
    product = apollo.get(f"StorefrontProduct:{product_id}") or {}
    if not product:
        if not json_ld:
            return None
        offers = json_ld.get("offers") or {}
        price = to_money(offers.get("price"))
        return Listing(
            title=str(json_ld.get("name") or "").strip(),
            method=ExtractionMethod.JSON_LD,
            url=url,
            brand=(json_ld.get("brand") or {}).get("name"),
            external_id=product_id,
            price=price,
            availability=Availability.IN_STOCK
            if str(offers.get("availability", "")).endswith("InStock")
            else Availability.UNKNOWN,
            confidence=Decimal("0.6"),  # JSON-LD price may be the club price on this platform
            raw={
                "source": "json_ld",
                "store_id": rendered_store,
                "warning": "JSON-LD pode trazer preço de clube",
            },
        )

    name = (product.get("name") or json_ld.get("name") or "").strip()
    brand = (_resolve(apollo, product.get("brand")) or {}).get("name") or (
        json_ld.get("brand") or {}
    ).get("name")
    quantity = _field(product, "quantity") or {}
    configuration = _resolve(apollo, _field(product, "productConfiguration")) or {}
    active = configuration.get("active", True) and not configuration.get("salesSuspended", False)
    in_stock = (_dec(quantity.get("inStock")) or Decimal(0)) > 0
    pricing = _resolve(apollo, _field(product, "pricing")) or {}
    regular = to_money(pricing.get("price"))
    promo = None
    if (
        pricing.get("promotion")
        and pricing.get("promotionalPrice") is not None
        and regular is not None
    ):
        candidate = to_money(pricing.get("promotionalPrice"))
        if candidate is not None and Decimal(0) < candidate < regular:
            promo = candidate
    selling = promo or regular

    club_price: Decimal | None = None
    for row in [p for p in (_field(product, "productPersonaPromotions") or []) if p]:
        meta = _resolve(apollo, row.get("promotion")) or {}
        if (
            str(meta.get("personaId")) == CLUB_PERSONA
            and row.get("promotionPrice") is not None
            and not row.get("minQuantity")
        ):
            value = to_money(row["promotionPrice"])
            if value is not None and (club_price is None or value < club_price):
                club_price = value
    for persona in _field(product, "personas") or []:
        if (
            persona
            and str(persona.get("personaId")) == CLUB_PERSONA
            and persona.get("personaPrice")
        ):
            value = to_money(persona["personaPrice"])
            if value is not None and (club_price is None or value < club_price):
                club_price = value

    quantity_min = quantity_price = None
    quantity_mode = None
    promo_info: dict[str, Any] | None = None
    main = _field(product, "productPromotion")
    if main and selling is not None:
        meta = _resolve(apollo, main.get("promotion")) or {}
        kind = meta.get("type")
        if (
            kind == "MORE_FOR_LESS"
            and main.get("buy")
            and main.get("gift")
            and not meta.get("personaId")
        ):
            buy, gift = _dec(main["buy"]), _dec(main["gift"])
            if (
                buy
                and gift
                and main.get("discountType") == "PERCENTAGE"
                and main.get("percentageValue")
            ):
                pct = Decimal(str(main["percentageValue"])) / 100
                quantity_min, quantity_mode = int(buy), "per_group"
                quantity_price = (selling * (1 - gift * pct / buy)).quantize(Decimal("0.0001"))
        elif (
            kind == "REGULAR"
            and not meta.get("personaId")
            and main.get("minQuantity")
            and main.get("promotionPrice")
        ):
            quantity_min, quantity_mode = int(Decimal(str(main["minQuantity"]))), "from_min"
            quantity_price = Decimal(str(main["promotionPrice"]))
        elif kind == "PROGRESSIVE" and main.get("progressiveDiscount"):
            tiers = sorted(main["progressiveDiscount"], key=lambda t: t.get("asFrom", 0))
            first = tiers[0]
            value = Decimal(str(first.get("gift")))
            unit_mode = meta.get("progressiveDiscountType") == "UNIT_PRICE"
            quantity_min, quantity_mode = int(first.get("asFrom")), "from_min"
            quantity_price = (
                value if unit_mode else (selling * (1 - value / 100)).quantize(Decimal("0.0001"))
            )
        if kind:
            promo_info = {"type": kind, "name": meta.get("name"), "ends": meta.get("endDate")}

    extra_prices = []
    for row in _field(product, "paymentConditionalPrices") or []:
        row = _resolve(apollo, row)
        if row and row.get("price") is not None and not row.get("minQuantity"):
            extra_prices.append(
                {"label": f"Cartão {row.get('cardBrandName') or row.get('paymentType') or ''}".strip(),
                 "price": str(to_money(row["price"])), "kind": "card"}
            )  # fmt: skip

    sale_unit = SaleUnit.KG if str(product.get("saleUnit")).upper() == "KG" else SaleUnit.PACKAGE
    piece_weight = None
    if (
        sale_unit == SaleUnit.KG
        and quantity.get("sellByWeightAndUnit")
        and quantity.get("fraction")
    ):
        piece_weight = _dec(quantity.get("fraction"))
    image_list = json_ld.get("image") or []
    return Listing(
        title=name,
        method=ExtractionMethod.EMBEDDED_STATE,
        url=url,
        brand=brand,
        external_id=product_id,
        sku=str(product.get("iid")) if product.get("iid") else None,
        image_url=image_list[0] if isinstance(image_list, list) and image_list else None,
        price=selling,
        regular_price=regular if promo is not None else None,
        club_price=club_price,
        club_label="Clube Mais" if club_price is not None else None,
        quantity_min=quantity_min,
        quantity_price=quantity_price,
        quantity_mode=quantity_mode,
        extra_prices=extra_prices,
        sale_unit=sale_unit,
        piece_weight_kg=piece_weight,
        listed_unit_price=selling if sale_unit == SaleUnit.KG else None,
        availability=Availability.IN_STOCK if active and in_stock else Availability.OUT_OF_STOCK,
        raw={
            "source": "apollo_state",
            "store_id": rendered_store,
            "store_alias": selected.get("alias"),
            "sale_unit": product.get("saleUnit"),
            "type": product.get("type"),
            "min_quantity": quantity.get("min"),
            "step": quantity.get("fraction"),
            "promotion": promo_info,
        },
    )


class FortAdapter(MarketAdapter):
    key = "fort"
    version = "2026.09.27"
    strategy = "sitemap+product_page_apollo_state+store_cookie"
    allowed_domains = ("fortatacadista.com.br",)
    candidates_per_item = 8

    async def search(self, ctx: AdapterContext, query: SearchQuery) -> SearchOutcome:
        store_id = str(ctx.store.price_context.get("store_id") or ctx.store.external_id or "")
        if not store_id:
            raise StoreContextError("loja do Fort sem identificador (store_id)")
        index = await load_index(
            ctx.client,
            ctx.cache,
            cache_key="fort",
            sitemap_urls=[SITEMAP],
            probe_pattern=None,
            url_filter=PRODUCT_URL,
            slug_of=re.compile(r"/produtos/\d+/(?P<slug>[a-z0-9-]+)$"),
            canonical=WWW + "{path}",
            ttl=timedelta(days=3),
        )
        outcome = SearchOutcome(method=ExtractionMethod.EMBEDDED_STATE)
        urls = list(query.preferred_urls)
        for entry in index.candidates(query.spec, self.candidates_per_item):
            if entry.url not in urls:
                urls.append(entry.url)
        outcome.query_used = f"sitemap: {len(urls)} candidato(s) de {len(index)} produtos"
        cookies = store_cookie(store_id)
        for url in urls[: self.candidates_per_item + len(query.preferred_urls)]:
            result = await ctx.client.get(url, cookies=cookies)
            if result.status in (404, 410):
                continue
            listing = parse_product_page(result.text, url, store_id)
            if listing is not None:
                outcome.listings.append(listing)
        outcome.notes.append(f"loja Fort {store_id}")
        return outcome
