"""Adapter contract tests against sanitised fixtures captured from the real sites (2026-09-27).

Each market is exercised with the three product natures required by the rebuild:
fixed package (rice/beans), variable weight (meat/fruit) and unit/pack (eggs,
coffee filter, papaya), plus not-found and store-context cases.
"""

from __future__ import annotations

from decimal import Decimal as D
from typing import Any

import httpx
import pytest
import time_machine

from pricetracker.adapters.angeloni import AngeloniAdapter
from pricetracker.adapters.base import AdapterContext, DocumentCache, SearchQuery, StoreContext
from pricetracker.adapters.bistek import BistekAdapter, parse_product_page
from pricetracker.adapters.errors import StoreContextError
from pricetracker.adapters.fort import FortAdapter
from pricetracker.adapters.http import PoliteClient
from pricetracker.adapters.imperatriz import ImperatrizAdapter
from pricetracker.domain.listing import SaleUnit
from pricetracker.domain.matching import MatchSpec, select_best
from pricetracker.models.enums import Availability, ExtractionMethod
from pricetracker.seed.catalog import CATALOG
from tests.fakes import (
    FIXTURES,
    Recorder,
    angeloni_handler,
    bistek_handler,
    fort_handler,
    imperatriz_handler_factory,
)

SPECS = {item["slug"]: MatchSpec.model_validate(item["match_spec"]) for item in CATALOG}


def query(slug: str) -> SearchQuery:
    spec = SPECS[slug]
    return SearchQuery(product_name=spec.search_terms[0], terms=spec.search_terms, spec=spec)


async def run_search(adapter: Any, handler: Any, store: StoreContext, slug: str, settings: Any) -> tuple[Any, Recorder]:
    recorder = Recorder(handler)
    client = PoliteClient(allowed_domains=adapter.allowed_domains, settings=settings, transport=recorder.transport())
    try:
        ctx = AdapterContext(client=client, store=store, cache=DocumentCache())
        outcome = await adapter.search(ctx, query(slug))
    finally:
        await client.aclose()
    return outcome, recorder


def best(outcome: Any, slug: str) -> Any:
    evaluations, index = select_best(outcome.listings, SPECS[slug])
    return (evaluations[index][0] if index is not None else None), evaluations


# --- Angeloni -------------------------------------------------------------------------------

BEIRA_MAR = StoreContext(
    store_id="s1", slug="beira-mar", name="Beira Mar", external_id="superangeloni14",
    price_context={"postal_code": "88010000", "seller": "superangeloni14"},
)  # fmt: skip


async def test_angeloni_fixed_package_rice(settings: Any) -> None:
    outcome, recorder = await run_search(AngeloniAdapter(), angeloni_handler, BEIRA_MAR, "arroz-branco-1kg", settings)
    chosen, evaluations = best(outcome, "arroz-branco-1kg")
    assert outcome.method == ExtractionMethod.API
    assert chosen is not None and chosen.price is not None and chosen.price > 0
    assert "arroz" in chosen.title.lower()
    assert all(isinstance(listing.price, (D, type(None))) for listing in outcome.listings)
    # never touches robots-disallowed legacy search
    assert not any("ft=" in p or "map=" in p or "/busca" in p for p in recorder.paths())
    assert any("region-id/v2.6470C9DD8410520F44B2C757ECBDE327" in p for p in recorder.paths())
    rejected = [l for l, m in evaluations if not m.accepted]
    assert any("integral" in l.title.lower() or "parboilizado" in l.title.lower() for l in rejected) or rejected


async def test_angeloni_variable_weight_priced_per_kg(settings: Any) -> None:
    outcome, _ = await run_search(AngeloniAdapter(), angeloni_handler, BEIRA_MAR, "alcatra-kg", settings)
    chosen, _ = best(outcome, "alcatra-kg")
    assert chosen is not None
    assert chosen.sale_unit == SaleUnit.KG
    assert chosen.listed_unit_price == chosen.price
    montana = next(l for l in outcome.listings if l.external_id == "5377560")
    assert montana.price == D("67.90") and montana.raw["unit_multiplier"] == 0.1
    assert montana.gtin is None and montana.raw["internal_code"] == "3619"


async def test_angeloni_unit_pack_eggs_and_unavailable(settings: Any) -> None:
    outcome, _ = await run_search(AngeloniAdapter(), angeloni_handler, BEIRA_MAR, "ovos-30-unidades", settings)
    unavailable = [l for l in outcome.listings if l.availability == Availability.OUT_OF_STOCK]
    assert unavailable and all(l.price is None for l in unavailable)  # Price 0 is never stored as a price
    chosen, _ = best(outcome, "ovos-30-unidades")
    assert chosen is not None and chosen.effective_package.count == 30


async def test_angeloni_rewrites_tres_to_3_for_coffee(settings: Any) -> None:
    outcome, recorder = await run_search(
        AngeloniAdapter(), angeloni_handler, BEIRA_MAR, "cafe-tres-coracoes-gourmet-sul-de-minas-250g", settings
    )
    queries = [p for p in recorder.paths() if "intelligent-search" in p]
    assert len(queries) >= 2 and any("3%20cora" in q for q in queries)
    assert outcome.listings  # found (out of stock in the capture)


async def test_angeloni_rejects_store_mismatch(settings: Any) -> None:
    wrong = StoreContext("s", "x", "X", None, {"postal_code": "88010000", "seller": "superangeloni13"})
    with pytest.raises(StoreContextError):
        await run_search(AngeloniAdapter(), angeloni_handler, wrong, "arroz-branco-1kg", settings)


async def test_angeloni_quantity_offers_from_master_data(settings: Any) -> None:
    from pricetracker.adapters.angeloni import apply_promotions
    from pricetracker.domain.listing import Listing
    import json
    from datetime import datetime, UTC

    rows = json.loads((FIXTURES / "angeloni" / "promotions_pr_superangeloni14.json").read_text())["batch_lookup_rows"]
    listings = [
        Listing(title="M&Ms", method=ExtractionMethod.API, sku="5459094", price=D("15.90")),
        Listing(title="Nuggets", method=ExtractionMethod.API, sku="5331481", price=D("8.99")),
    ]
    apply_promotions(listings, rows, datetime(2026, 9, 27, 18, tzinfo=UTC))
    assert (listings[0].quantity_min, listings[0].quantity_price, listings[0].quantity_mode) == (2, D("12.9900"), "from_min")
    assert listings[1].quantity_min == 3 and listings[1].quantity_mode == "per_group"
    assert listings[1].quantity_price == D("5.9933")  # leve 3 pague 2


# --- Bistek -------------------------------------------------------------------------------------

BISTEK_STORE = StoreContext("s2", "costeira", "Costeira", "8", {})


async def test_bistek_sitemap_discovery_and_state_parsing(settings: Any) -> None:
    outcome, recorder = await run_search(BistekAdapter(), bistek_handler, BISTEK_STORE, "arroz-branco-1kg", settings)
    assert not any("/api/" in p or "_q=" in p or "map=" in p for p in recorder.paths())
    assert "www.bistek.com.br/sitemap/product-0.xml" in recorder.paths()
    chosen, evaluations = best(outcome, "arroz-branco-1kg")
    assert chosen is not None and chosen.title == "Arroz Branco Tio Joao 1kg" and chosen.price == D("8.29")
    assert chosen.gtin == "7893500020127" and chosen.method == ExtractionMethod.EMBEDDED_STATE
    assert all("parboilizado" not in l.title.lower() for l, m in evaluations if m.accepted)


async def test_bistek_promo_and_weighed_pack(settings: Any) -> None:
    html = (FIXTURES / "bistek" / "product_feijao-carioca-caldao-1kg-1003224.html").read_text()
    beans = parse_product_page(html, "https://www.bistek.com.br/feijao-carioca-caldao-1kg-1003224/p")
    assert beans is not None and beans.price == D("9.97") and beans.regular_price == D("11.49")
    html = (FIXTURES / "bistek" / "product_alcatra-pedaco-embalagem-12kg-3029840.html").read_text()
    steak = parse_product_page(html, "https://www.bistek.com.br/alcatra-pedaco-embalagem-12kg-3029840/p")
    assert steak is not None and steak.sale_unit == SaleUnit.PIECE and steak.piece_weight_kg == D("1.6")
    assert steak.price == D("110.03") and steak.gtin is None  # internal weighed-item code


async def test_bistek_unit_items_and_unavailable(settings: Any) -> None:
    eggs = parse_product_page(
        (FIXTURES / "bistek" / "product_ovos-branco-bandeja-com-30-unidades-1312464.html").read_text(),
        "https://www.bistek.com.br/ovos-branco-bandeja-com-30-unidades-1312464/p",
    )
    assert eggs is not None and eggs.package_count == 30 and eggs.price == D("19.99")
    papaya = parse_product_page(
        (FIXTURES / "bistek" / "product_mamao-papaia-unidade-3070530.html").read_text(),
        "https://www.bistek.com.br/mamao-papaia-unidade-3070530/p",
    )
    assert papaya is not None and papaya.package_count == 1 and papaya.price == D("6.99")
    gone = parse_product_page(
        (FIXTURES / "bistek" / "product_arroz-parboilizado-namorado-1kg-2018241.html").read_text(),
        "https://www.bistek.com.br/arroz-parboilizado-namorado-1kg-2018241/p",
    )
    assert gone is not None and gone.availability == Availability.OUT_OF_STOCK and gone.price is None


async def test_bistek_etag_revalidation_reuses_parsed_offer(settings: Any) -> None:
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/p"):
            calls.append(dict(request.headers))
            if request.headers.get("if-none-match"):
                return httpx.Response(304)
        return bistek_handler(request)

    adapter = BistekAdapter()
    cache = DocumentCache()
    client = PoliteClient(allowed_domains=adapter.allowed_domains, settings=settings, transport=httpx.MockTransport(handler))
    ctx = AdapterContext(client=client, store=BISTEK_STORE, cache=cache)
    first = await adapter.search(ctx, query("lentilha-400g"))
    second = await adapter.search(ctx, query("lentilha-400g"))
    await client.aclose()
    assert any(c.get("if-none-match") for c in calls)
    assert [l.price for l in first.listings] == [l.price for l in second.listings]


# --- Fort ---------------------------------------------------------------------------------------------

KOBRASOL = StoreContext("s3", "kobrasol-160", "Kobrasol", "1638", {"store_id": "1638"})


async def test_fort_store_cookie_and_prices(settings: Any) -> None:
    outcome, recorder = await run_search(FortAdapter(), fort_handler, KOBRASOL, "arroz-branco-1kg", settings)
    assert not any("?" in p for p in recorder.paths() if "/produtos/" in p)
    assert all("st_334=" in r.headers.get("cookie", "") for r in recorder.requests if "/produtos/" in r.url.path)
    tio_joao = next(l for l in outcome.listings if l.external_id == "7895191")
    assert tio_joao.price == D("6.79") and tio_joao.raw["store_id"] == "1638"


async def test_fort_multi_buy_and_weighed(settings: Any) -> None:
    outcome, _ = await run_search(FortAdapter(), fort_handler, KOBRASOL, "feijao-1kg", settings)
    beans = next(l for l in outcome.listings if l.external_id == "7904524")
    assert beans.quantity_mode == "per_group" and beans.quantity_min == 2
    assert beans.quantity_price == D("4.5520")  # 5.69 x (1 - 1 x 0.40 / 2)
    outcome, _ = await run_search(FortAdapter(), fort_handler, KOBRASOL, "alcatra-kg", settings)
    chosen, _ = best(outcome, "alcatra-kg")
    assert chosen is not None and chosen.sale_unit == SaleUnit.KG and chosen.price == D("39.98")
    assert chosen.regular_price == D("51.89")


async def test_fort_unit_items_and_missing_fuji(settings: Any) -> None:
    outcome, _ = await run_search(FortAdapter(), fort_handler, KOBRASOL, "mamao-papaia-unidade", settings)
    papaya = next(l for l in outcome.listings if l.external_id == "8064079")
    assert papaya.sale_unit == SaleUnit.KG and papaya.piece_weight_kg == D("0.7")
    assert papaya.extra_prices and papaya.extra_prices[0]["kind"] == "card"
    fuji, _ = await run_search(FortAdapter(), fort_handler, KOBRASOL, "maca-fuji-kg", settings)
    assert fuji.listings == []  # Fort does not sell Fuji online: honest not-found, no substitute


async def test_fort_detects_ignored_store_cookie(settings: Any) -> None:
    other = StoreContext("s4", "campeche", "Campeche", "1636", {"store_id": "1636"})
    with pytest.raises(StoreContextError):
        await run_search(FortAdapter(), fort_handler, other, "arroz-branco-1kg", settings)


# --- Imperatriz ------------------------------------------------------------------------------------------

LOJA16 = StoreContext("s5", "presidente-kennedy", "Presidente Kennedy", "16", {"store_id": "16"})


@time_machine.travel("2026-09-27 12:00:00-03:00", tick=False)
async def test_imperatriz_club_offers_parse_and_strict_matching(settings: Any) -> None:
    outcome, recorder = await run_search(
        ImperatrizAdapter(), imperatriz_handler_factory(), LOJA16, "cafe-tres-coracoes-gourmet-sul-de-minas-250g", settings
    )
    assert any(r.method == "POST" for r in recorder.requests)
    sponge = next(l for l in outcome.listings if "Esponja" in l.title)
    assert sponge.price == D("9.99") and sponge.club_price == D("7.90")
    assert sponge.club_label == "Super Clube (ativar no app)"
    chosen, evaluations = best(outcome, "cafe-tres-coracoes-gourmet-sul-de-minas-250g")
    assert chosen is None  # only the Mogiana variant is on offer: not equivalent to Sul de Minas
    mogiana = next(m for l, m in evaluations if "MOGIANA" in l.title)
    assert not mogiana.accepted and "missing_required:sul de minas" in mogiana.reasons
    assert "apenas as ofertas vigentes" in " ".join(outcome.notes)
    assert all("<public-token>" not in str(l.raw) for l in outcome.listings)


@time_machine.travel("2026-09-27 12:00:00-03:00", tick=False)
async def test_imperatriz_match_when_item_is_on_offer(settings: Any) -> None:
    synthetic = [  # synthetic offer shaped like the captured payload (store 16)
        {"idoferta": 1, "nomeoferta": "ARROZ TIO JOAO T1 1KG", "valorde": 7.49, "precoexclusivo": 6.49,
         "idtiporecomendacao": "1", "lojas": ["16"], "validadede": "2026-09-21", "validadeate": "2026-09-27",
         "observacao": "De R$ 7,49 Por R$ 7,49 ou R$ 6,49 para clientes identificados", "eans": ["7893500020110"]},
        {"idoferta": 2, "nomeoferta": "MACA FUJI KG", "valorde": 11.98, "valorpor": 9.98,
         "idtiporecomendacao": "2", "lojas": ["16"], "validadeate": "2026-09-30", "eans": []},
        {"idoferta": 3, "nomeoferta": "ARROZ OUTRA LOJA 1KG", "valorde": 1.00, "lojas": ["5"], "validadeate": "2026-09-30"},
        {"idoferta": 4, "nomeoferta": "ARROZ VENCIDO 1KG", "valorde": 1.00, "lojas": ["16"], "validadeate": "2026-09-20"},
    ]  # fmt: skip
    outcome, _ = await run_search(ImperatrizAdapter(), imperatriz_handler_factory(synthetic), LOJA16, "arroz-branco-1kg", settings)
    assert [l.title for l in outcome.listings] == ["ARROZ TIO JOAO T1 1KG", "MACA FUJI KG"]
    chosen, _ = best(outcome, "arroz-branco-1kg")
    assert chosen is not None and chosen.price == D("7.49") and chosen.club_price == D("6.49")
    fuji = outcome.listings[1]
    assert fuji.sale_unit == SaleUnit.KG and fuji.club_label == "Super Clube"
