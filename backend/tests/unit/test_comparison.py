"""Comparison engine, including the E2E scenarios expressed at the domain level:
missing item, travel changes the winner, stale prices and fair common basket."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

from pricetracker.domain.comparison import (
    ComparisonOptions,
    DistanceModel,
    LineRequest,
    OfferInput,
    StoreOption,
    compare,
)
from pricetracker.domain.listing import SaleUnit
from pricetracker.domain.pricing import OfferPricing
from pricetracker.domain.travel import VehicleSpec
from pricetracker.domain.units import Measure
from pricetracker.models.enums import Availability, ReviewStatus, Unit

NOW = datetime(2026, 9, 27, 15, tzinfo=UTC)
A = StoreOption("A", "angeloni", "Angeloni", "Centro")
B = StoreOption("B", "bistek", "Bistek", "Trindade")
C = StoreOption("C", "fort", "Fort Atacadista", "São José")

ITEMS = [
    LineRequest("i-rice", "rice", "Arroz 1 kg", D("2"), Unit.PCT),
    LineRequest("i-beans", "beans", "Feijão 1 kg", D("1"), Unit.PCT),
    LineRequest("i-eggs", "eggs", "Ovos 30 un", D("1"), Unit.PCT),
    LineRequest("i-coffee", "coffee", "Café 250 g", D("1"), Unit.PCT),
]


def offer(product: str, store: str, price: str, *, days_old: float = 1, **kw: object) -> OfferInput:
    pricing = OfferPricing(
        sale_unit=SaleUnit.PACKAGE, price=D(price), package_measure=Measure(D("1"), Unit.KG)
    )
    return OfferInput(
        product_id=product,
        store_id=store,
        observation_id=f"{product}-{store}",
        title=f"{product} @ {store}",
        url=None,
        observed_at=NOW - timedelta(days=days_old),
        pricing=pricing,
        **kw,  # type: ignore[arg-type]
    )


def options(**kw: object) -> ComparisonOptions:
    return ComparisonOptions(now=NOW, include_travel=False, **kw)  # type: ignore[arg-type]


def test_weekly_basket_common_winner_and_savings() -> None:
    offers = [
        offer("rice", "A", "6.00"), offer("beans", "A", "8.00"), offer("eggs", "A", "20.00"), offer("coffee", "A", "18.00"),
        offer("rice", "B", "6.50"), offer("beans", "B", "7.00"), offer("eggs", "B", "22.00"), offer("coffee", "B", "17.00"),
    ]  # fmt: skip
    result = compare(ITEMS, [A, B], offers, options())
    # A: 12 + 8 + 20 + 18 = 58 ; B: 13 + 7 + 22 + 17 = 59
    assert result.common.comparable and result.common.winner_store_id == "A"
    assert result.common.savings_vs_runner_up == D("1.00")
    assert result.recommendation.kind == "single"
    assert result.recommendation.store_ids == ["A"]
    assert result.recommendation.covered == 4 and result.recommendation.total_items == 4
    assert result.recommendation.confidence == "alta"


def test_missing_item_partial_basket_is_not_announced_as_winner() -> None:
    # B lacks coffee. B looks cheaper in total only because it is incomplete.
    offers = [
        offer("rice", "A", "6.00"), offer("beans", "A", "8.00"), offer("eggs", "A", "20.00"), offer("coffee", "A", "18.00"),
        offer("rice", "B", "5.50"), offer("beans", "B", "7.50"), offer("eggs", "B", "19.50"),
    ]  # fmt: skip
    result = compare(ITEMS, [A, B], offers, options(max_stops=1))
    coverage = {t.store_id: t for t in result.coverage.stores}
    assert coverage["A"].covered == 4 and coverage["B"].covered == 3
    assert coverage["B"].products_total < coverage["A"].products_total  # 38.00 < 58.00
    assert result.coverage.best_store_id == "A"  # only the complete basket can lead
    assert coverage["B"].missing_item_ids == ["i-coffee"]
    # Common basket compares only the intersection (rice, beans, eggs): B is cheaper there.
    assert result.common.item_ids == ["i-rice", "i-beans", "i-eggs"]
    assert result.common.excluded_item_ids == ["i-coffee"]
    assert result.common.winner_store_id == "B"
    # The single-stop plan maximises coverage first.
    assert result.recommendation.store_ids == ["A"]


def test_split_plan_when_it_saves_enough() -> None:
    offers = [
        offer("rice", "A", "6.00"), offer("beans", "A", "8.00"), offer("eggs", "A", "20.00"), offer("coffee", "A", "18.00"),
        offer("rice", "B", "5.50"), offer("beans", "B", "7.50"), offer("eggs", "B", "19.50"),
    ]  # fmt: skip
    result = compare(ITEMS, [A, B], offers, options(max_stops=2))
    # split: rice/beans/eggs at B (38.00) + coffee at A (18.00) = 56.00 vs A alone 58.00 -> saves 2 < 5
    assert result.plan.split_savings == D("2.00")
    assert result.recommendation.kind == "single"


def test_travel_cost_changes_the_winner() -> None:
    offers = [
        offer("rice", "A", "6.00"), offer("beans", "A", "8.00"), offer("eggs", "A", "20.00"), offer("coffee", "A", "18.00"),
        offer("rice", "C", "5.00"), offer("beans", "C", "7.00"), offer("eggs", "C", "18.00"), offer("coffee", "C", "16.00"),
    ]  # fmt: skip
    distances = {"A": D("3"), "C": D("30")}
    model = DistanceModel(
        distance=lambda x, y: distances[y if x == "home" else x],
        method="osrm",
        description="Distâncias rodoviárias calculadas pelo OSRM.",
    )
    vehicle = VehicleSpec(km_per_liter=D("10"), fuel_price_per_liter=D("6.00"))
    without = compare(ITEMS, [A, C], offers, options(max_stops=1))
    assert without.recommendation.store_ids == ["C"]  # C products: 10+7+18+16 = 51 vs A 58
    result = compare(
        ITEMS, [A, C], offers,
        ComparisonOptions(now=NOW, include_travel=True, max_stops=1, vehicle=vehicle, distances=model),
    )  # fmt: skip
    travel = result.travel_by_store
    assert travel["A"] is not None and travel["A"].total == D("3.60")  # 6 km / 10 * 6.00
    assert travel["C"] is not None and travel["C"].total == D("36.00")  # 60 km / 10 * 6.00
    rec = result.recommendation
    assert rec.store_ids == ["A"]
    assert rec.products_total == D("58.00") and rec.travel_total == D("3.60")
    assert rec.effective_total == D("61.60")
    assert rec.savings == D("25.40")  # C: 51 + 36 = 87.00


def test_stale_prices_do_not_win_silently() -> None:
    offers = [
        offer("rice", "A", "6.00"), offer("beans", "A", "8.00"), offer("eggs", "A", "20.00"), offer("coffee", "A", "18.00"),
        offer("rice", "B", "1.00", days_old=20), offer("beans", "B", "1.00", days_old=20),
        offer("eggs", "B", "1.00", days_old=20), offer("coffee", "B", "1.00", days_old=20),
    ]  # fmt: skip
    result = compare(ITEMS, [A, B], offers, options())
    assert result.recommendation.store_ids == ["A"]
    assert any("dias foram ignorados" in w for w in result.recommendation.warnings)
    stale_cell = result.items[0].cells["B"]
    assert stale_cell.status == "stale" and not stale_cell.usable
    consented = compare(ITEMS, [A, B], offers, options(allow_stale=True))
    assert consented.recommendation.store_ids == ["B"]
    assert consented.recommendation.confidence == "baixa"  # every price used is stale


def test_partly_stale_consented_basket_has_medium_confidence() -> None:
    offers = [
        offer("rice", "A", "6.00"), offer("beans", "A", "8.00"), offer("eggs", "A", "20.00"), offer("coffee", "A", "18.00"),
        offer("rice", "B", "1.00", days_old=20), offer("beans", "B", "1.00"),
        offer("eggs", "B", "1.00"), offer("coffee", "B", "1.00"),
    ]  # fmt: skip
    consented = compare(ITEMS, [A, B], offers, options(allow_stale=True))
    assert consented.recommendation.store_ids == ["B"]
    assert consented.recommendation.confidence == "media"
    assert any(
        "1 preço(s) desatualizado(s)" in r for r in consented.recommendation.confidence_reasons
    )


def test_flagged_outlier_and_unavailable_are_not_used() -> None:
    offers = [
        offer("rice", "A", "6.00"),
        offer("rice", "B", "0.60", review_status=ReviewStatus.FLAGGED),
        offer("beans", "B", "7.00", availability=Availability.OUT_OF_STOCK),
        offer("beans", "A", "8.00"),
    ]
    result = compare(ITEMS[:2], [A, B], offers, options())
    assert result.items[0].cells["B"].status == "flagged"
    assert result.items[1].cells["B"].status == "unavailable"
    assert result.recommendation.store_ids == ["A"]
    assert any("sinalizado" in r for r in result.recommendation.confidence_reasons)


def test_no_data_recommendation() -> None:
    result = compare(ITEMS, [A, B], [], options())
    assert result.recommendation.kind == "none"
    assert result.common.winner_store_id is None
    assert result.coverage.best_store_id is None
