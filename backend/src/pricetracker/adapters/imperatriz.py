"""Supermercados Imperatriz — official "Super Clube" offers (partial coverage).

The chain's website (superimperatriz.com.br) no longer has a catalogue, search or
prices. The only official, anonymous, machine-readable price source is the Super
Clube hotsite, whose public offers API lists the current club offers per store
with the shelf price and the club price. The anonymous bootstrap key is fetched
exactly as the public hotsite does, kept in memory only, and never logged or
stored. Coverage is limited to items currently on offer, so "not found" here means
"no current offer published", not "not sold".

Not used on purpose: the iFood marketplace API (a third party behind PerimeterX /
Cloudflare bot protection that blocked automated access during reconnaissance).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from pricetracker.adapters.base import AdapterContext, MarketAdapter, SearchOutcome, SearchQuery
from pricetracker.adapters.errors import ParseError
from pricetracker.domain.listing import Listing, SaleUnit
from pricetracker.domain.money import parse_brl, to_money
from pricetracker.domain.units import parse_package
from pricetracker.domain.validation import valid_gtin
from pricetracker.models.enums import Availability, ExtractionMethod

BOOTSTRAP = "https://api.zoombox.com.br/admin/v1/varejista"
OFFERS = (
    "https://9zli2drdqe.execute-api.us-east-1.amazonaws.com/v1/ofertas"
    "?lojas={store}&cpfcnpj=&inativar_motor_rock_conecta=false&idtiporecomendacao=1,2"
)
ORIGIN = "https://clube.superimperatriz.com.br"
HOTSITE = ORIGIN + "/hotsite"
COVERAGE_NOTE = (
    "a Imperatriz publica apenas as ofertas vigentes do Super Clube; item sem oferta não aparece"
)


def parse_offer(offer: dict[str, Any], store_id: str, today: date) -> Listing | None:
    name = str(offer.get("nomeoferta") or "").strip()
    if not name:
        return None
    valid_until = offer.get("validadeate")
    if valid_until:
        try:
            if date.fromisoformat(str(valid_until)[:10]) < today:
                return None
        except ValueError:
            pass
    stores = [str(s) for s in offer.get("lojas") or []]
    if stores and store_id not in stores:
        return None
    shelf = to_money(offer.get("valorde"))
    club = to_money(offer.get("precoexclusivo")) or to_money(offer.get("valorpor"))
    regular = None
    price = shelf
    observation = str(offer.get("observacao") or "")
    reference = _reference_price(observation)
    if reference is not None and shelf is not None and reference > shelf:
        regular = reference  # "De A Por B": a general promotion on top of the club price
    if club is not None and shelf is not None and club >= shelf:
        club = None
    per_kg = parse_package(name).per_kg  # "MACA FUJI KG" yes; "ARROZ 1KG" is a 1 kg package
    eans = [str(e) for e in offer.get("eans") or [] if str(e).strip()]
    single_gtin = eans[0] if len(eans) == 1 and valid_gtin(eans[0]) else None
    activation = str(offer.get("idtiporecomendacao") or offer.get("tipo")) == "1"
    return Listing(
        title=name,
        method=ExtractionMethod.API,
        url=HOTSITE,
        external_id=str(offer.get("idoferta")) if offer.get("idoferta") is not None else None,
        gtin=single_gtin,
        image_url=offer.get("imagem"),
        price=price,
        regular_price=regular,
        club_price=club,
        club_label=("Super Clube (ativar no app)" if activation else "Super Clube")
        if club is not None
        else None,
        sale_unit=SaleUnit.KG if per_kg else SaleUnit.PACKAGE,
        listed_unit_price=price if per_kg else None,
        availability=Availability.OUT_OF_STOCK if offer.get("esgotado") else Availability.IN_STOCK,
        confidence=Decimal("0.95"),
        raw={
            "source": "super_clube_offers",
            "store_id": store_id,
            "offer_id": offer.get("idoferta"),
            "valid_from": offer.get("validadede"),
            "valid_until": valid_until,
            "purchase_limit": offer.get("limitecompra"),
            "observation": observation[:200],
            "eans": eans[:10],
            "coverage": COVERAGE_NOTE,
        },
    )


def _reference_price(observation: str) -> Decimal | None:
    # "De R$ 9,99 Por R$ 9,99 ou R$ 7,90 para clientes identificados"
    lowered = observation.lower()
    if not lowered.startswith("de "):
        return None
    head = lowered.split(" por ", 1)[0]
    return parse_brl(head)


class ImperatrizAdapter(MarketAdapter):
    key = "imperatriz"
    version = "2026.09.27"
    strategy = "super_clube_offers_api"
    allowed_domains = (
        "api.zoombox.com.br",
        "9zli2drdqe.execute-api.us-east-1.amazonaws.com",
    )

    def __init__(self) -> None:
        self._credentials: dict[str, str] | None = None

    async def _headers(self, ctx: AdapterContext) -> dict[str, str]:
        if self._credentials is None:
            result = await ctx.client.request(
                "POST",
                BOOTSTRAP,
                headers={"aplicacao": "multitelas", "Origin": ORIGIN, "Referer": ORIGIN + "/"},
                json_body={},
            )
            data = result.json()
            token, retailer = data.get("token"), data.get("idvarejista")
            if not token or not retailer:
                raise ParseError("bootstrap do Super Clube sem chave pública")
            self._credentials = {"x-api-key": str(token), "idvarejista": str(retailer)}
        return dict(self._credentials)

    async def _offers(self, ctx: AdapterContext, store_id: str) -> list[dict[str, Any]]:
        cached = ctx.cache.get_json("imperatriz-offers", store_id)
        if cached is not None:
            return list(cached)
        headers = await self._headers(ctx)
        result = await ctx.client.get(
            OFFERS.format(store=store_id), headers=headers, accept="application/json"
        )
        payload = result.json()
        offers = payload.get("ofertas") if isinstance(payload, dict) else None
        if not isinstance(offers, list):
            raise ParseError("resposta de ofertas sem a lista 'ofertas'")
        ctx.cache.put_json("imperatriz-offers", store_id, offers, timedelta(hours=6))
        return offers

    async def search(self, ctx: AdapterContext, query: SearchQuery) -> SearchOutcome:
        store_id = str(ctx.store.price_context.get("store_id") or ctx.store.external_id or "")
        if not store_id:
            raise ParseError("loja Imperatriz sem identificador")
        offers = await self._offers(ctx, store_id)
        today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        outcome = SearchOutcome(
            method=ExtractionMethod.API, query_used=f"{len(offers)} ofertas vigentes da loja"
        )
        for offer in offers:
            listing = parse_offer(offer, store_id, today)
            if listing is not None:
                outcome.listings.append(listing)
        outcome.notes.append(COVERAGE_NOTE)
        return outcome
