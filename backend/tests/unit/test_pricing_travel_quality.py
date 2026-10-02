from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from pricetracker.domain.listing import SaleUnit
from pricetracker.domain.pricing import IncompatibleQuantity, OfferPricing, line_cost
from pricetracker.domain.quality import assess_outlier, is_stale
from pricetracker.domain.travel import GeoPoint, VehicleSpec, best_route, haversine_km, travel_cost
from pricetracker.domain.units import Measure
from pricetracker.models.enums import PriceKind, Unit

RICE_1KG = OfferPricing(
    sale_unit=SaleUnit.PACKAGE, price=D("6.49"), regular_price=D("7.99"),
    package_measure=Measure(D("1"), Unit.KG),
)  # fmt: skip


def test_two_packages_cost_twice_the_offer() -> None:
    line = line_cost(RICE_1KG, D("2"), Unit.PCT)
    assert line.cost == D("12.98")
    assert line.sale_units == D("2")
    assert line.price_kind == PriceKind.PROMO
    assert line.unit_price == D("6.4900") and line.unit_price_unit == Unit.KG


def test_mass_request_rounds_up_to_whole_packages() -> None:
    line = line_cost(RICE_1KG, D("1.5"), Unit.KG)
    assert line.sale_units == D("2")
    assert line.cost == D("12.98")
    assert line.notes


def test_per_kg_offer_respects_requested_kilos() -> None:
    apples = OfferPricing(sale_unit=SaleUnit.KG, price=D("9.98"))
    assert line_cost(apples, D("1.5"), Unit.KG).cost == D("14.97")
    assert line_cost(apples, D("750"), Unit.G).cost == D("7.49")
    with pytest.raises(IncompatibleQuantity):
        line_cost(apples, D("2"), Unit.UN)
    estimated = line_cost(apples, D("2"), Unit.UN, approx_unit_weight_kg=D("0.2"))
    assert estimated.cost == D("3.99") and estimated.approximate


def test_piece_offer() -> None:
    papaya = OfferPricing(sale_unit=SaleUnit.PIECE, price=D("5.39"), piece_weight_kg=D("0.45"))
    line = line_cost(papaya, D("2"), Unit.UN)
    assert line.cost == D("10.78") and line.approximate
    assert line.unit_price == D("11.9778") and line.unit_price_unit == Unit.KG
    by_weight = line_cost(papaya, D("1"), Unit.KG)
    assert by_weight.sale_units == D("3")


def test_egg_pack_by_units() -> None:
    eggs = OfferPricing(sale_unit=SaleUnit.PACKAGE, price=D("22.90"), package_count=30)
    assert line_cost(eggs, D("60"), Unit.UN).cost == D("45.80")
    assert line_cost(eggs, D("1"), Unit.PCT).cost == D("22.90")


def test_quantity_and_club_prices() -> None:
    offer = OfferPricing(
        sale_unit=SaleUnit.PACKAGE, price=D("5.00"), club_price=D("4.50"),
        quantity_min=6, quantity_price=D("4.20"), package_measure=Measure(D("1"), Unit.KG),
    )  # fmt: skip
    assert line_cost(offer, D("2"), Unit.PCT).price_kind == PriceKind.REGULAR
    assert line_cost(offer, D("2"), Unit.PCT, use_club=True).cost == D("9.00")
    six = line_cost(offer, D("6"), Unit.PCT)
    assert six.cost == D("25.20") and six.price_kind == PriceKind.QUANTITY


def test_no_price_is_incompatible() -> None:
    with pytest.raises(IncompatibleQuantity):
        line_cost(OfferPricing(sale_unit=SaleUnit.KG, price=None), D("1"), Unit.KG)


def test_travel_formula_is_transparent() -> None:
    vehicle = VehicleSpec(km_per_liter=D("12"), fuel_price_per_liter=D("6.30"))
    cost = travel_cost(D("24"), vehicle, tolls=D("0"), method="osrm", route=["home", "s", "home"])
    assert cost.liters == D("2.00")
    assert cost.fuel_cost == D("12.60")
    assert cost.total == D("12.60")
    assert cost.formula == "24,0 km ÷ 12 km/l × R$ 6,3/l + R$ 0,00 de pedágio = R$ 12,60"
    with_toll = travel_cost(
        D("24"), vehicle, tolls=D("8.40"), method="osrm", route=["home", "s", "home"]
    )
    assert with_toll.total == D("21.00")


def test_haversine_and_best_route() -> None:
    floripa = GeoPoint(D("-27.5954"), D("-48.5480"))
    sao_jose = GeoPoint(D("-27.6136"), D("-48.6366"))
    assert D("8") < haversine_km(floripa, sao_jose) < D("10")
    distances = {
        ("home", "a"): 5,
        ("a", "b"): 2,
        ("b", "home"): 6,
        ("home", "b"): 6,
        ("b", "a"): 2,
        ("a", "home"): 5,
    }
    route, total = best_route(["a", "b"], lambda x, y: D(distances[(x, y)]))
    assert total == D("13") and route[0] == route[-1] == "home"


def test_staleness() -> None:
    now = datetime(2026, 9, 27, 12, tzinfo=UTC)
    assert not is_stale(now - timedelta(days=6, hours=23), now, 7)
    assert is_stale(now - timedelta(days=7, hours=1), now, 7)


def test_outliers_are_flagged_with_reason() -> None:
    assert assess_outlier(D("0.05"), Unit.KG, [], []).is_outlier
    history = [D("6.5"), D("6.9"), D("7.1")]
    jump = assess_outlier(D("25"), Unit.KG, history, [])
    assert jump.is_outlier and "mediana histórica" in (jump.reason or "")
    assert not assess_outlier(D("7.4"), Unit.KG, history, []).is_outlier
    peers = assess_outlier(D("1.00"), Unit.KG, [], [D("6.5"), D("7.2")])
    assert peers.is_outlier


def test_group_promotion_is_exact_per_group() -> None:
    # "Mais por Menos": buy 2, the 2nd unit 40% off -> 0.8 x price per unit inside a pair.
    offer = OfferPricing(
        sale_unit=SaleUnit.PACKAGE, price=D("5.69"), quantity_min=2,
        quantity_price=D("4.552"), quantity_mode="per_group", package_measure=Measure(D("1"), Unit.KG),
    )  # fmt: skip
    assert line_cost(offer, D("1"), Unit.PCT).cost == D("5.69")
    assert line_cost(offer, D("2"), Unit.PCT).cost == D("9.10")  # 2 x 4.552 = 9.104
    three = line_cost(offer, D("3"), Unit.PCT)
    assert three.cost == D("14.79")  # one pair (9.104) + one full-price unit (5.69)
    assert three.price_kind == PriceKind.QUANTITY


def test_weight_based_pack_is_priced_per_kg() -> None:
    # Bistek sells "Alcatra 1,6kg" packs at R$ 110.03 -> R$ 68.77/kg.
    pack = OfferPricing(sale_unit=SaleUnit.PIECE, price=D("110.03"), piece_weight_kg=D("1.6"))
    line = line_cost(pack, D("1"), Unit.KG, weight_based=True)
    assert line.cost == D("68.77") and line.unit_price == D("68.7688") and line.approximate
    apples = OfferPricing(
        sale_unit=SaleUnit.PACKAGE, price=D("4.39"), package_measure=Measure(D("0.5"), Unit.KG)
    )
    assert line_cost(apples, D("1.5"), Unit.KG, weight_based=True).cost == D("13.17")
    # Without the flag the same pack is bought whole.
    assert line_cost(pack, D("1"), Unit.KG).cost == D("110.03")
