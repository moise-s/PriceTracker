from decimal import Decimal as D

from pricetracker.domain.listing import Listing, SaleUnit
from pricetracker.domain.matching import MatchSpec, Pins, SizeSpec, evaluate, select_best
from pricetracker.models.enums import Availability, ExtractionMethod, SoldBy, Unit

API = ExtractionMethod.API


def listing(title: str, price: str | None = "10", **kw: object) -> Listing:
    return Listing(title=title, method=API, price=D(price) if price else None, **kw)  # type: ignore[arg-type]


RICE = MatchSpec(
    search_terms=["arroz 1kg"],
    required=[["arroz"]],
    excluded=["integral", "arboreo", "biscoito"],
    sold_by=SoldBy.PACKAGE,
    size=SizeSpec(quantity=D("1"), unit=Unit.KG),
)
EGGS = MatchSpec(
    search_terms=["ovos 30 unidades"],
    required=[["ovo"]],
    excluded=["codorna", "chocolate", "pascoa"],
    sold_by=SoldBy.PACKAGE,
    size=SizeSpec(quantity=D("30"), unit=Unit.UN),
)
COFFEE = MatchSpec(
    search_terms=["café três corações gourmet sul de minas 250g"],
    required=[["cafe"], ["gourmet"], ["sul de minas"]],
    brands=["três corações", "3 corações"],
    strict_brand=True,
    sold_by=SoldBy.PACKAGE,
    size=SizeSpec(quantity=D("250"), unit=Unit.G),
)
STEAK = MatchSpec(
    search_terms=["alcatra"],
    required=[["alcatra"]],
    excluded=["moida", "bife pronto"],
    sold_by=SoldBy.WEIGHT,
)
PAPAYA = MatchSpec(
    search_terms=["mamão papaia"],
    required=[["mamao"], ["papaia", "papaya"]],
    sold_by=SoldBy.UNIT,
    approx_unit_weight_kg=D("0.45"),
)


def test_rice_accepts_exact_size_and_rejects_others() -> None:
    assert evaluate(listing("Arroz Branco Tio João Tipo 1 1kg"), RICE).accepted
    five = evaluate(listing("Arroz Tio João 5kg"), RICE)
    assert not five.accepted and "size_mismatch:5 kg" in five.reasons
    integral = evaluate(listing("Arroz Integral Camil 1kg"), RICE)
    assert not integral.accepted and "excluded:integral" in integral.reasons
    unknown = evaluate(listing("Arroz Tio João Tipo 1"), RICE)
    assert not unknown.accepted and "size_unknown" in unknown.reasons
    beans = evaluate(listing("Feijão Preto 1kg"), RICE)
    assert not beans.accepted and "missing_required:arroz" in beans.reasons


def test_structured_package_overrides_title() -> None:
    from pricetracker.domain.units import Measure

    item = listing("Arroz Tio João Tipo 1", package_measure=Measure(D("1"), Unit.KG))
    assert evaluate(item, RICE).accepted


def test_eggs_count_rules() -> None:
    assert evaluate(listing("Ovos Brancos Grandes com 30 Unidades"), EGGS).accepted
    assert not evaluate(listing("Ovos Vermelhos c/20"), EGGS).accepted
    assert not evaluate(listing("Ovos de Codorna 30un"), EGGS).accepted
    tolerant = EGGS.model_copy(
        update={"size": SizeSpec(quantity=D("30"), unit=Unit.UN, tolerance_pct=D("35"))}
    )
    result = evaluate(listing("Ovos Vermelhos c/20"), tolerant)
    assert result.accepted and "size_within_tolerance:20 un" in result.reasons


def test_strict_brand_and_variant() -> None:
    ok = evaluate(listing("Café Torrado e Moído Três Corações Gourmet Sul de Minas 250g"), COFFEE)
    assert ok.accepted and "brand_preferred" in ok.reasons
    other_brand = evaluate(listing("Café Melitta Gourmet Sul de Minas 250g"), COFFEE)
    assert not other_brand.accepted and "brand_mismatch" in other_brand.reasons
    other_variant = evaluate(listing("Café Três Corações Gourmet Cerrado Mineiro 250g"), COFFEE)
    assert not other_variant.accepted
    via_brand_field = evaluate(
        listing("Café Gourmet Sul de Minas 250g", brand="3 Corações"), COFFEE
    )
    assert via_brand_field.accepted


def test_weight_rules() -> None:
    assert evaluate(listing("Alcatra Bovina Resfriada Kg", sale_unit=SaleUnit.KG), STEAK).accepted
    assert evaluate(listing("Alcatra Bovina Kg"), STEAK).accepted
    piece = evaluate(listing("Alcatra Peça Inteira Aprox 5kg"), STEAK)
    assert not piece.accepted and piece.reasons[-1].startswith("piece_too_large")
    assert not evaluate(listing("Carne Moída de Alcatra 500g"), STEAK).accepted
    assert evaluate(listing("Alcatra em Bife Bandeja 1kg"), STEAK).accepted


def test_unit_rules() -> None:
    assert evaluate(listing("Mamão Papaia Unidade"), PAPAYA).accepted
    per_kg = evaluate(listing("Mamão Papaya Kg", sale_unit=SaleUnit.KG), PAPAYA)
    assert per_kg.accepted and "per_kg_with_estimated_unit_weight" in per_kg.reasons
    no_weight = PAPAYA.model_copy(update={"approx_unit_weight_kg": None})
    assert not evaluate(listing("Mamão Papaya Kg", sale_unit=SaleUnit.KG), no_weight).accepted


def test_identity_and_pins() -> None:
    gtin_spec = RICE.model_copy(update={"gtins": ["07893500018520"]})
    item = listing("Produto com título estranho", gtin="7893500018520")
    result = evaluate(item, gtin_spec)
    assert result.accepted and result.identity and "gtin_match" in result.reasons
    rejected = listing("Arroz Branco 1kg", external_id="42")
    assert not evaluate(rejected, RICE, Pins(rejected=frozenset({"id:42"}))).accepted
    accepted = listing("Arroz qualquer", external_id="7")
    assert evaluate(accepted, RICE, Pins(accepted=frozenset({"id:7"}))).identity


def test_select_best_prefers_cheapest_equivalent_available() -> None:
    items = [
        listing("Arroz Tio João 1kg", "8.90"),
        listing("Arroz Prato Fino 1kg", "6.50", availability=Availability.OUT_OF_STOCK),
        listing("Arroz Camil 1kg", "7.20"),
        listing("Arroz Camil 5kg", "25.00"),  # cheaper per kg but different size
        listing("Arroz Integral 1kg", "5.00"),  # excluded
    ]
    evaluations, best = select_best(items, RICE)
    assert best == 2
    assert evaluations[3][1].accepted is False


def test_select_best_compares_unit_price_within_tolerance() -> None:
    spec = EGGS.model_copy(
        update={"size": SizeSpec(quantity=D("30"), unit=Unit.UN, tolerance_pct=D("35"))}
    )
    items = [listing("Ovos c/30", "21.00"), listing("Ovos c/20", "13.00")]  # 0.70 vs 0.65 per egg
    _, best = select_best(items, spec)
    assert best == 1
