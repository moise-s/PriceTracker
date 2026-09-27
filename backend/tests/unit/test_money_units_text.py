from decimal import Decimal as D

import pytest

from pricetracker.domain.money import format_brl, parse_brl, to_money
from pricetracker.domain.text import normalize, phrase_in, tokens
from pricetracker.domain.units import describe_quantity, parse_package, to_base, within_tolerance
from pricetracker.models.enums import Unit


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("R$ 1.234,56", D("1234.56")),
        ("7,79", D("7.79")),
        ("R$\xa012,90", D("12.90")),
        ("R$12", D("12")),
        ("12.90", D("12.90")),
        ("1.234", D("1234")),
        ("1,234.56", D("1234.56")),
        ("por R$ 29,90/kg", D("29.90")),
        ("0,99", D("0.99")),
        ("", None),
        ("sem preço", None),
    ],
)
def test_parse_brl(text: str, expected: D | None) -> None:
    assert parse_brl(text) == expected


def test_to_money_converts_floats_exactly() -> None:
    assert to_money(7.79) == D("7.79")
    assert to_money(0.1 + 0.2) == D("0.30")
    assert to_money(19) == D("19.00")
    assert to_money(None) is None
    assert to_money(True) is None
    assert to_money(float("nan")) is None


def test_format_brl() -> None:
    assert format_brl(D("1234.5")) == "R$ 1.234,50"
    assert format_brl(D("0.994")) == "R$ 0,99"
    assert format_brl(D("-3")) == "-R$ 3,00"
    assert format_brl(None) == "—"


def test_normalize_and_tokens() -> None:
    assert normalize("Café 3 Corações 250g") == "cafe 3 coracoes 250 g"
    assert tokens("Ovos Brancos com 30 unidades") == ["ovo", "branco", "30", "unidade"]
    assert phrase_in("três corações", normalize("Café Tres Coracoes Gourmet"))
    assert not phrase_in("sul de minas", normalize("Café Gourmet Cerrado Mineiro"))
    assert phrase_in("ovo", normalize("OVOS VERMELHOS"))


@pytest.mark.parametrize(
    ("title", "quantity", "unit", "count", "per_kg"),
    [
        ("Arroz Branco Tio João Tipo 1 1kg", D("1"), Unit.KG, None, False),
        ("Arroz Tio João 5kg", D("5"), Unit.KG, None, False),
        ("Lentilha Caldão 400g", D("0.4"), Unit.KG, None, False),
        ("Açúcar 1.000g", D("1"), Unit.KG, None, False),
        ("Leite Integral 12 x 1 L", D("12"), Unit.L, 12, False),
        ("Ovos Brancos Grandes com 30 Unidades", None, None, 30, False),
        ("Ovo Vermelho Tipo Grande C/30", None, None, 30, False),
        ("Filtro de Papel Melitta 102 com 30 Unidades", None, None, 30, False),
        ("Alcatra Bovina Resfriada Kg", None, None, None, True),
        ("Maçã Fuji Nacional Granel", None, None, None, True),
        ("Café 7 grãos 500 g", D("0.5"), Unit.KG, None, False),
    ],
)
def test_parse_package(
    title: str, quantity: D | None, unit: Unit | None, count: int | None, per_kg: bool
) -> None:
    info = parse_package(title)
    if quantity is None:
        assert info.measure is None
    else:
        assert info.measure is not None
        assert info.measure.quantity == quantity
        assert info.measure.unit == unit
    assert info.count == count
    assert info.per_kg is per_kg


def test_parse_package_flags() -> None:
    assert parse_package("Maminha Resfriada a Vácuo Aprox. 1,2 Kg").approximate
    assert parse_package("Mamão Papaia Unidade").single_unit
    assert not parse_package("").has_size


def test_conversions() -> None:
    assert to_base(D("500"), Unit.G).quantity == D("0.500")
    assert to_base(D("2"), Unit.L).unit == Unit.L
    assert describe_quantity(D("0.25"), Unit.KG) == "250 g"
    assert describe_quantity(D("1.5"), Unit.KG) == "1,5 kg"
    assert within_tolerance(D("0.5"), D("0.4"), D("25"))
    assert not within_tolerance(D("0.5"), D("0.4"), D("20"))
