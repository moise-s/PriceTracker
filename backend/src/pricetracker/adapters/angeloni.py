"""Angeloni (super.angeloni.com.br, VTEX IO).

Deterministic source: the public VTEX Intelligent Search REST API the storefront
uses, scoped to a store with the ``region-id`` path facet. The region comes from
the public regions endpoint for the store's postal code and is verified against
the store's white-label seller (``superangeloni<N>``), because prices differ per
store. robots.txt disallows the legacy ``ft=``/``fq=``/``map=`` search and
``/busca``; none of those are used. Quantity offers come from the public Master
Data entity ``PR`` that the storefront reads anonymously (optional enrichment).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from pricetracker.adapters.base import (
    AdapterContext,
    MarketAdapter,
    SearchOutcome,
    SearchQuery,
)
from pricetracker.adapters.errors import StoreContextError
from pricetracker.adapters.http import FetchError
from pricetracker.domain.listing import Listing, SaleUnit
from pricetracker.domain.matching import evaluate
from pricetracker.domain.money import to_money
from pricetracker.domain.units import parse_package, parse_unit, to_base
from pricetracker.domain.validation import valid_gtin
from pricetracker.models.enums import Availability, ExtractionMethod, Unit

logger = logging.getLogger(__name__)

BASE = "https://super.angeloni.com.br"
SEARCH = BASE + "/api/io/_v/api/intelligent-search/product_search/trade-policy/1/region-id/{region}"
REGIONS = BASE + "/api/checkout/pub/regions?country=BRA&postalCode={cep}&sc=1"
PROMOTIONS = BASE + "/api/dataentities/PR/search"
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")

# Catalogue vocabulary differs from everyday writing.
REWRITES = {"três": "3", "tres": "3", "papaia": "papaya"}


def rewrite(term: str) -> str:
    return " ".join(REWRITES.get(word.lower(), word) for word in term.split())


def parse_product(
    product: dict[str, Any], *, region_id: str | None, seller: str | None
) -> Listing | None:
    items = product.get("items") or []
    if not items:
        return None
    item = items[0]
    sellers = item.get("sellers") or []
    offer = (sellers[0].get("commertialOffer") if sellers else None) or {}
    price = to_money(offer.get("Price"))
    list_price = to_money(offer.get("ListPrice"))
    available_qty = offer.get("AvailableQuantity") or 0
    available = bool(price) and price is not None and price > 0 and available_qty > 0
    if price is not None and price <= 0:
        price = None
    if list_price is not None and list_price <= 0:
        list_price = None
    title = (product.get("productName") or item.get("name") or "").strip()
    if not title:
        return None
    measurement = (item.get("measurementUnit") or "un").lower()
    sale_unit = SaleUnit.KG if measurement == "kg" else SaleUnit.PACKAGE
    properties = {
        p.get("name"): (p.get("values") or [None])[0] for p in product.get("properties") or []
    }
    package_measure = None
    if sale_unit == SaleUnit.PACKAGE and not parse_package(title).has_size:
        package_measure = _property_measure(properties)
    images = item.get("images") or []
    ean = str(item.get("ean") or "").strip()
    link = product.get("link") or (f"/{product['linkText']}/p" if product.get("linkText") else None)
    return Listing(
        title=title,
        method=ExtractionMethod.API,
        url=BASE + link if link else None,
        brand=product.get("brand"),
        external_id=str(product.get("productId") or item.get("itemId")),
        sku=str(item.get("itemId")) if item.get("itemId") else None,
        gtin=ean if valid_gtin(ean) else None,
        image_url=images[0].get("imageUrl") if images else None,
        price=price,
        regular_price=list_price if list_price and price and list_price > price else None,
        sale_unit=sale_unit,
        package_measure=package_measure,
        listed_unit_price=price if sale_unit == SaleUnit.KG else None,
        listed_unit_price_unit=Unit.KG if sale_unit == SaleUnit.KG else None,
        availability=Availability.IN_STOCK if available else Availability.OUT_OF_STOCK,
        raw={
            "source": "vtex_intelligent_search",
            "product_id": product.get("productId"),
            "item_id": item.get("itemId"),
            "measurement_unit": measurement,
            "unit_multiplier": item.get("unitMultiplier"),
            "internal_code": None if valid_gtin(ean) else ean or None,
            "category": (product.get("categories") or [None])[0],
            "region_id": region_id,
            "seller": seller,
            "list_price": str(list_price) if list_price else None,
            "available_quantity": available_qty,
        },
    )


def _property_measure(properties: dict[str, Any]) -> Any:
    raw_qty = properties.get("Quantidade da embalagem")
    unit = parse_unit(properties.get("Unidade de medida"))
    if not raw_qty or unit is None:
        return None
    try:
        quantity = Decimal(str(raw_qty).replace(",", "."))
    except ArithmeticError:
        return None
    if quantity <= 0 or unit in (Unit.PCT,):
        return None
    return to_base(quantity, unit)


def apply_promotions(listings: list[Listing], rows: list[dict[str, Any]], now: datetime) -> None:
    """Attach quantity offers (Leve X Pague Y, N+ por R$ X, % na Nª unidade)."""
    by_sku: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_sku.setdefault(str(row.get("sku")), []).append(row)
    local_now = now.astimezone(LOCAL_TZ).replace(tzinfo=None)
    for listing in listings:
        if listing.price is None or listing.sku is None:
            continue
        for row in by_sku.get(listing.sku, []):
            try:
                begin = datetime.fromisoformat(str(row.get("beginDateUtc"))[:19])
                end = datetime.fromisoformat(str(row.get("endDateUtc"))[:19])
            except ValueError:
                continue
            if not (begin <= local_now < end):
                continue
            kind = row.get("promotionType")
            price = listing.price
            affect = int(row.get("quantityToAffect") or 0)
            minimum = int(row.get("minimumQuantity") or 0)
            pct = Decimal(str(row.get("percentualDiscount") or 0))
            offer: tuple[int, Decimal, str] | None = None
            if kind == "PM" and affect and row.get("maximumUnitPrice"):
                offer = (affect, Decimal(str(row["maximumUnitPrice"])), "from_min")
            elif kind == "PP" and affect and pct:
                offer = (affect, price * (1 - pct / 100), "from_min")
            elif kind == "LP" and minimum and affect and minimum > affect:
                offer = (minimum, price * Decimal(minimum - affect) / Decimal(minimum), "per_group")
            elif kind == "DU" and minimum and pct:
                offer = (
                    minimum,
                    price * (Decimal(minimum) - pct / 100) / Decimal(minimum),
                    "per_group",
                )
            if offer is None:
                continue
            min_qty, unit_price, mode = offer
            if listing.quantity_price is None or unit_price < listing.quantity_price:
                listing.quantity_min = min_qty
                listing.quantity_price = unit_price.quantize(Decimal("0.0001"))
                listing.quantity_mode = mode
                listing.raw["quantity_offer"] = {
                    "type": kind,
                    "name": row.get("name"),
                    "ends": row.get("endDateUtc"),
                }


class AngeloniAdapter(MarketAdapter):
    key = "angeloni"
    version = "2026.09.27"
    strategy = "vtex_intelligent_search+regions+pr"
    allowed_domains = ("super.angeloni.com.br",)

    async def _region(self, ctx: AdapterContext) -> tuple[str, str | None]:
        context = ctx.store.price_context
        cep = str(context.get("postal_code") or ctx.store.postal_code or "").replace("-", "")
        expected_seller = context.get("seller")
        if not cep:
            raise StoreContextError("filial sem CEP para resolver a região de preços")
        cached = ctx.cache.get_json("angeloni-region", cep)
        if cached is None:
            result = await ctx.client.get(REGIONS.format(cep=cep), accept="application/json")
            regions = result.json() or []
            cached = [
                {"id": r.get("id"), "sellers": [s.get("id") for s in r.get("sellers") or []]}
                for r in regions
            ]
            ctx.cache.put_json("angeloni-region", cep, cached, timedelta(hours=24))
        for region in cached:
            if region.get("id") and (
                expected_seller is None or expected_seller in region.get("sellers", [])
            ):
                return region["id"], expected_seller or (region["sellers"] or [None])[0]
        raise StoreContextError(
            f"o CEP {cep} não resolve para a filial esperada ({expected_seller}); preços não seriam desta loja"
        )

    async def search(self, ctx: AdapterContext, query: SearchQuery) -> SearchOutcome:
        region_id, seller = await self._region(ctx)
        outcome = SearchOutcome(method=ExtractionMethod.API)
        seen: set[str] = set()
        terms: list[str] = []
        for term in query.terms:
            for variant in (term, rewrite(term)):
                if variant not in terms:
                    terms.append(variant)
        for term in terms[:4]:
            url = (
                SEARCH.format(region=region_id)
                + f"?query={quote(term)}&page=1&count=40&locale=pt-BR"
                + "&hideUnavailableItems=false&operator=and&fuzzy=0"
            )
            data = (await ctx.client.get(url, accept="application/json")).json()
            for product in data.get("products") or []:
                listing = parse_product(product, region_id=region_id, seller=seller)
                if listing is None or listing.listing_key in seen:
                    continue
                seen.add(listing.listing_key)
                outcome.listings.append(listing)
            outcome.query_used = term
            if any(
                evaluate(item, query.spec).accepted and item.price is not None
                for item in outcome.listings
            ):
                break
        if outcome.listings and seller:
            await self._enrich_promotions(ctx, outcome, seller)
        outcome.notes.append(f"região {region_id} (seller {seller})")
        return outcome

    async def _enrich_promotions(
        self, ctx: AdapterContext, outcome: SearchOutcome, seller: str
    ) -> None:
        skus = sorted({i.sku for i in outcome.listings if i.sku and i.price is not None})[:100]
        if not skus:
            return
        fields = ",".join(
            [
                "sku", "quantityToAffect", "promotionType", "percentualDiscount", "name",
                "minimumQuantity", "maximumUnitPrice", "endDateUtc", "beginDateUtc",
            ]
        )  # fmt: skip
        where = (
            f"whiteLabelAccount={seller} AND isActive=true AND ("
            + " OR ".join(f"sku={s}" for s in skus)
            + ")"
        )
        url = f"{PROMOTIONS}?_fields={fields}&_where={quote(where)}"
        try:
            result = await ctx.client.get(
                url, headers={"REST-Range": "resources=0-99"}, accept="application/json"
            )
            rows = result.json()
        except (FetchError, ValueError) as exc:
            outcome.notes.append(f"promoções por quantidade indisponíveis ({type(exc).__name__})")
            return
        if isinstance(rows, list):
            from pricetracker.db.base import utcnow

            apply_promotions(outcome.listings, rows, utcnow())
