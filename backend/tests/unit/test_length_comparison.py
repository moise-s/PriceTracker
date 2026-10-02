from decimal import Decimal as D

import pytest

from pricetracker.domain.listing import Listing, SaleUnit
from pricetracker.domain.matching import MatchSpec, Pins, evaluate, select_best
from pricetracker.domain.pricing import OfferPricing, line_cost
from pricetracker.domain.units import Measure, parse_package
from pricetracker.models.enums import Availability, ExtractionMethod, Unit


@pytest.mark.parametrize(
    ("title", "metres"),
    [
        ("Papel higiênico folha dupla 4 rolos de 30 m", "120"),
        ("Papel higiênico folha dupla 30m com 12 rolos", "360"),
        ("Papel higiênico folha dupla 12 x 30m", "360"),
        ("Papel higiênico 2 folhas 30m c/4", "120"),
        ("Papel higiênico folha dupla leve 12 pague 11 30m", "360"),
        ("Toilet paper double ply 4 rolls 30 metres", "120"),
        ("Papel higiênico folha dupla 30m largura 10cm 4 rolos", "120"),
        ("Papel higiênico folha dupla 120m total 4 rolos", "120"),
        ("Papel higiênico folha dupla 30m 12un", "360"),
        ("Papel higiênico folha dupla 30m", None),
        ("Papel higiênico 2 folhas 30m", None),
        ("Papel higiênico folha dupla 4 rolos", None),
        ("Fita adesiva 30m", "30"),
    ],
)
def test_roll_length_is_total_not_ply_count(title: str, metres: str | None) -> None:
    package = parse_package(title)
    assert package.measure == (Measure(D(metres), Unit.M) if metres else None)


SPEC = MatchSpec(
    search_terms=["papel higienico folha dupla"],
    required=[["papel higienico", "toilet paper"], ["folha dupla", "double ply"]],
    excluded=["folha simples", "papel toalha"],
    comparison_unit="m",
)


def offer(title: str, price: str) -> Listing:
    return Listing(
        title=title,
        price=D(price),
        method=ExtractionMethod.JSON_LD,
        availability=Availability.IN_STOCK,
    )


def test_cheapest_per_metre_not_cheapest_pack_and_only_double_ply() -> None:
    listings = [
        offer("Papel higienico folha dupla 4 rolos 30m", "10"),
        offer("Papel higienico folha dupla 12 rolos 30m", "24"),
        offer("Papel higienico folha simples 12 rolos 30m", "12"),
        offer("Papel higienico folha dupla 30m", "1"),
    ]
    evaluations, selected = select_best(listings, SPEC)
    assert selected == 1  # 24/360 < 10/120; cheaper pack is not the winner.
    assert not evaluations[2][1].accepted
    assert not evaluations[3][1].accepted
    assert not evaluate(
        listings[3], SPEC, Pins(accepted=frozenset({listings[3].listing_key}))
    ).accepted
    pricing = OfferPricing(
        sale_unit=SaleUnit.PACKAGE, price=D("24"), package_measure=Measure(D("360"), Unit.M)
    )
    line = line_cost(pricing, D("120"), Unit.M)
    assert line.cost == D("24.00") and line.sale_units == 1
    assert line.unit_price == D("0.0667") and line.unit_price_unit == Unit.M
    assert "360 m" in line.notes[0]  # Explain buying extra metres in a whole pack.
    assert line_cost(pricing, D("400"), Unit.M).cost == D("48.00")
