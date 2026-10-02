"""Basket comparison: common basket, coverage per store and the economic plan.

Pure functions over already-loaded offers. Rules that keep the result honest:

* incomplete baskets are never summed silently: every view reports X of Y items;
* the coverage view never declares a winner among stores with different coverage;
* stale prices (older than the freshness window) and flagged outliers are unusable
  unless the user explicitly allows stale prices / confirms the outlier;
* the economic plan maximises coverage first, then minimises products + travel.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from itertools import combinations

from pricetracker.domain.money import ZERO, format_brl, quantize_money
from pricetracker.domain.pricing import IncompatibleQuantity, LineCost, OfferPricing, line_cost
from pricetracker.domain.quality import age_days, is_stale
from pricetracker.domain.travel import TravelCost, VehicleSpec, best_route, travel_cost
from pricetracker.models.enums import Availability, ReviewStatus, Unit

SPLIT_MIN_SAVINGS = Decimal("5.00")  # below this, a single stop is simpler and recommended


@dataclass(frozen=True)
class LineRequest:
    item_id: str
    product_id: str
    name: str
    quantity: Decimal
    unit: Unit
    approx_unit_weight_kg: Decimal | None = None
    weight_based: bool = False


@dataclass(frozen=True)
class StoreOption:
    store_id: str
    market_slug: str
    market_name: str
    store_name: str
    use_club: bool = False
    tolls: Decimal = ZERO
    has_location: bool = True

    @property
    def label(self) -> str:
        return f"{self.market_name} {self.store_name}".strip()


@dataclass(frozen=True)
class OfferInput:
    product_id: str
    store_id: str
    observation_id: str
    title: str
    url: str | None
    observed_at: datetime
    pricing: OfferPricing
    availability: Availability = Availability.IN_STOCK
    review_status: ReviewStatus = ReviewStatus.OK
    confidence: Decimal = Decimal("1")
    method: str = "api"
    club_label: str | None = None


@dataclass(frozen=True)
class DistanceModel:
    """Distances in km between "home" and store ids."""

    distance: Callable[[str, str], Decimal]
    method: str  # "osrm" | "estimate"
    description: str


@dataclass(frozen=True)
class ComparisonOptions:
    now: datetime
    freshness_days: int = 7
    allow_stale: bool = False
    include_travel: bool = True
    max_stops: int = 2
    vehicle: VehicleSpec | None = None
    distances: DistanceModel | None = None


# Cell statuses
OK = "ok"
STALE = "stale"
FLAGGED = "flagged"
UNAVAILABLE = "unavailable"
MISSING = "missing"
INCOMPATIBLE = "incompatible"


@dataclass
class Cell:
    store_id: str
    status: str
    usable: bool
    offer: OfferInput | None = None
    line: LineCost | None = None
    age_days: Decimal | None = None
    reason: str | None = None


@dataclass
class ItemRow:
    request: LineRequest
    cells: dict[str, Cell]
    best_store_id: str | None = None
    best_cost: Decimal | None = None
    worst_cost: Decimal | None = None

    @property
    def usable_store_ids(self) -> list[str]:
        return [sid for sid, cell in self.cells.items() if cell.usable]


@dataclass
class StoreTotals:
    store_id: str
    covered: int
    total_items: int
    products_total: Decimal
    missing_item_ids: list[str]
    stale_used: int
    oldest_age_days: Decimal | None
    travel: TravelCost | None
    effective_total: Decimal
    travel_known: bool

    @property
    def complete(self) -> bool:
        return self.covered == self.total_items


@dataclass
class CommonBasket:
    item_ids: list[str]
    excluded_item_ids: list[str]
    stores: list[StoreTotals]
    winner_store_id: str | None
    savings_vs_runner_up: Decimal | None
    savings_vs_most_expensive: Decimal | None
    comparable: bool
    note: str


@dataclass
class CoverageView:
    stores: list[StoreTotals]
    max_coverage: int
    best_store_id: str | None
    note: str


@dataclass
class PlanStop:
    store_id: str
    item_ids: list[str]
    products_total: Decimal


@dataclass
class Plan:
    stops: list[PlanStop]
    covered: int
    missing_item_ids: list[str]
    products_total: Decimal
    travel: TravelCost | None
    effective_total: Decimal
    travel_known: bool

    @property
    def store_ids(self) -> list[str]:
        return [stop.store_id for stop in self.stops]

    @property
    def kind(self) -> str:
        return "single" if len(self.stops) == 1 else "split"


@dataclass
class EconomicPlanView:
    best: Plan | None
    best_single: Plan | None
    alternatives: list[Plan]
    split_savings: Decimal | None
    assumptions: list[str]


@dataclass
class Recommendation:
    kind: str  # "single" | "split" | "none"
    store_ids: list[str]
    headline: str
    explanation: list[str]
    products_total: Decimal | None
    travel_total: Decimal | None
    effective_total: Decimal | None
    savings: Decimal | None
    savings_reference_store_id: str | None
    covered: int
    total_items: int
    newest_observed_at: datetime | None
    oldest_observed_at: datetime | None
    confidence: str  # "alta" | "media" | "baixa"
    confidence_reasons: list[str]
    warnings: list[str]


@dataclass
class ComparisonResult:
    generated_at: datetime
    options: ComparisonOptions
    stores: list[StoreOption]
    items: list[ItemRow]
    common: CommonBasket
    coverage: CoverageView
    plan: EconomicPlanView
    recommendation: Recommendation
    travel_by_store: dict[str, TravelCost | None] = field(default_factory=dict)


def _cell_for(
    request: LineRequest, store: StoreOption, offer: OfferInput | None, options: ComparisonOptions
) -> Cell:
    if offer is None:
        return Cell(store.store_id, MISSING, usable=False, reason="sem observação")
    age = age_days(offer.observed_at, options.now)
    if offer.review_status in (ReviewStatus.FLAGGED, ReviewStatus.REJECTED):
        return Cell(
            store.store_id, FLAGGED, False, offer, None, age, "preço sinalizado para revisão"
        )
    if offer.availability == Availability.OUT_OF_STOCK:
        return Cell(store.store_id, UNAVAILABLE, False, offer, None, age, "indisponível")
    try:
        line = line_cost(
            offer.pricing,
            request.quantity,
            request.unit,
            use_club=store.use_club,
            approx_unit_weight_kg=request.approx_unit_weight_kg,
            weight_based=request.weight_based,
        )
    except IncompatibleQuantity as exc:
        return Cell(store.store_id, INCOMPATIBLE, False, offer, None, age, str(exc))
    stale = is_stale(offer.observed_at, options.now, options.freshness_days)
    if stale:
        return Cell(
            store.store_id,
            STALE,
            usable=options.allow_stale,
            offer=offer,
            line=line,
            age_days=age,
            reason=f"preço de {age} dias",
        )
    return Cell(store.store_id, OK, True, offer, line, age)


def build_rows(
    requests: Sequence[LineRequest],
    stores: Sequence[StoreOption],
    offers: Sequence[OfferInput],
    options: ComparisonOptions,
) -> list[ItemRow]:
    index: dict[tuple[str, str], OfferInput] = {}
    for offer in offers:
        key = (offer.product_id, offer.store_id)
        current = index.get(key)
        if current is None or offer.observed_at > current.observed_at:
            index[key] = offer
    rows: list[ItemRow] = []
    for request in requests:
        cells = {
            store.store_id: _cell_for(
                request, store, index.get((request.product_id, store.store_id)), options
            )
            for store in stores
        }
        row = ItemRow(request=request, cells=cells)
        usable = [(sid, c.line.cost) for sid, c in cells.items() if c.usable and c.line is not None]
        if usable:
            best = min(usable, key=lambda pair: (pair[1], pair[0]))
            row.best_store_id, row.best_cost = best
            row.worst_cost = max(cost for _, cost in usable)
        rows.append(row)
    return rows


def _travel_for(
    stop_ids: Sequence[str],
    stores_by_id: dict[str, StoreOption],
    options: ComparisonOptions,
) -> TravelCost | None:
    if not options.include_travel or options.vehicle is None or options.distances is None:
        return None
    if not stop_ids or any(not stores_by_id[s].has_location for s in stop_ids):
        return None
    route, distance = best_route(list(stop_ids), options.distances.distance)
    tolls = sum((stores_by_id[s].tolls for s in stop_ids), start=ZERO)
    return travel_cost(
        distance, options.vehicle, tolls=tolls, method=options.distances.method, route=route
    )


def _travel_expected(options: ComparisonOptions) -> bool:
    return options.include_travel and options.vehicle is not None and options.distances is not None


def _store_totals(
    store: StoreOption,
    rows: Sequence[ItemRow],
    item_ids: Sequence[str],
    stores_by_id: dict[str, StoreOption],
    options: ComparisonOptions,
    travel_cache: dict[str, TravelCost | None],
) -> StoreTotals:
    covered = 0
    total = ZERO
    missing: list[str] = []
    stale_used = 0
    oldest: Decimal | None = None
    wanted = set(item_ids)
    for row in rows:
        if row.request.item_id not in wanted:
            continue
        cell = row.cells[store.store_id]
        if cell.usable and cell.line is not None:
            covered += 1
            total += cell.line.cost
            if cell.status == STALE:
                stale_used += 1
            if cell.age_days is not None and (oldest is None or cell.age_days > oldest):
                oldest = cell.age_days
        else:
            missing.append(row.request.item_id)
    travel = travel_cache.get(store.store_id)
    travel_known = travel is not None or not _travel_expected(options)
    effective = total + (travel.total if travel else ZERO)
    return StoreTotals(
        store_id=store.store_id,
        covered=covered,
        total_items=len(wanted),
        products_total=quantize_money(total),
        missing_item_ids=missing,
        stale_used=stale_used,
        oldest_age_days=oldest,
        travel=travel,
        effective_total=quantize_money(effective),
        travel_known=travel_known,
    )


def _common_basket(
    rows: Sequence[ItemRow],
    stores: Sequence[StoreOption],
    stores_by_id: dict[str, StoreOption],
    options: ComparisonOptions,
    travel_cache: dict[str, TravelCost | None],
) -> CommonBasket:
    all_ids = {s.store_id for s in stores}
    common_ids = [r.request.item_id for r in rows if set(r.usable_store_ids) >= all_ids]
    excluded = [r.request.item_id for r in rows if r.request.item_id not in common_ids]
    totals = [
        _store_totals(s, rows, common_ids, stores_by_id, options, travel_cache) for s in stores
    ]
    comparable = bool(common_ids) and len(stores) >= 2
    winner = None
    runner_up_savings = None
    worst_savings = None
    if common_ids and stores:
        ranked = sorted(
            [t for t in totals if t.travel_known],
            key=lambda t: (t.effective_total, stores_by_id[t.store_id].label),
        )
        if ranked:
            winner = ranked[0].store_id
            if len(ranked) > 1:
                runner_up_savings = ranked[1].effective_total - ranked[0].effective_total
                worst_savings = ranked[-1].effective_total - ranked[0].effective_total
    if not common_ids:
        note = "Nenhum item foi encontrado em todos os mercados selecionados."
    elif excluded:
        note = (
            f"Comparação justa sobre {len(common_ids)} de {len(rows)} itens presentes em "
            "todos os mercados; os demais ficam de fora desta visão."
        )
    else:
        note = "Todos os itens foram encontrados em todos os mercados selecionados."
    return CommonBasket(
        item_ids=common_ids,
        excluded_item_ids=excluded,
        stores=totals,
        winner_store_id=winner if comparable else None,
        savings_vs_runner_up=runner_up_savings,
        savings_vs_most_expensive=worst_savings,
        comparable=comparable,
        note=note,
    )


def _coverage_view(
    rows: Sequence[ItemRow],
    stores: Sequence[StoreOption],
    stores_by_id: dict[str, StoreOption],
    options: ComparisonOptions,
    travel_cache: dict[str, TravelCost | None],
) -> CoverageView:
    item_ids = [r.request.item_id for r in rows]
    totals = [_store_totals(s, rows, item_ids, stores_by_id, options, travel_cache) for s in stores]
    totals.sort(key=lambda t: (-t.covered, t.effective_total, stores_by_id[t.store_id].label))
    max_cov = max((t.covered for t in totals), default=0)
    leaders = [t for t in totals if t.covered == max_cov and max_cov > 0 and t.travel_known]
    best = leaders[0].store_id if leaders else None
    if max_cov == 0:
        note = "Nenhum preço utilizável para os mercados selecionados."
    elif len({t.covered for t in totals}) > 1:
        note = (
            "Mercados com cobertura diferente não são comparáveis pelo total: "
            "o destaque vale apenas entre os que encontraram mais itens."
        )
    else:
        note = "Todos os mercados encontraram a mesma quantidade de itens."
    return CoverageView(stores=totals, max_coverage=max_cov, best_store_id=best, note=note)


def _plan_for(
    subset: Sequence[str],
    rows: Sequence[ItemRow],
    stores_by_id: dict[str, StoreOption],
    options: ComparisonOptions,
) -> Plan | None:
    assignment: dict[str, list[str]] = {sid: [] for sid in subset}
    totals: dict[str, Decimal] = {sid: ZERO for sid in subset}
    missing: list[str] = []
    for row in rows:
        choices = [
            (row.cells[sid].line.cost, stores_by_id[sid].label, sid)  # type: ignore[union-attr]
            for sid in subset
            if row.cells[sid].usable and row.cells[sid].line is not None
        ]
        if not choices:
            missing.append(row.request.item_id)
            continue
        cost, _, sid = min(choices)
        assignment[sid].append(row.request.item_id)
        totals[sid] += cost
    if any(not items for items in assignment.values()):
        return None  # a stop with nothing to buy is just a smaller plan
    travel = _travel_for(subset, stores_by_id, options)
    travel_known = travel is not None or not _travel_expected(options)
    products = quantize_money(sum(totals.values(), start=ZERO))
    stops = [PlanStop(sid, assignment[sid], quantize_money(totals[sid])) for sid in subset]
    if travel is not None:
        order = [s for s in travel.route if s != "home"]
        stops.sort(key=lambda stop: order.index(stop.store_id))
    return Plan(
        stops=stops,
        covered=len(rows) - len(missing),
        missing_item_ids=missing,
        products_total=products,
        travel=travel,
        effective_total=quantize_money(products + (travel.total if travel else ZERO)),
        travel_known=travel_known,
    )


def _plan_sort_key(plan: Plan, stores_by_id: dict[str, StoreOption]) -> tuple[object, ...]:
    return (
        -plan.covered,
        0 if plan.travel_known else 1,
        plan.effective_total,
        len(plan.stops),
        [stores_by_id[s].label for s in plan.store_ids],
    )


def _economic_plan(
    rows: Sequence[ItemRow],
    stores: Sequence[StoreOption],
    stores_by_id: dict[str, StoreOption],
    options: ComparisonOptions,
) -> EconomicPlanView:
    plans: list[Plan] = []
    ids = [s.store_id for s in stores]
    for size in range(1, min(options.max_stops, len(ids)) + 1):
        for subset in combinations(ids, size):
            plan = _plan_for(subset, rows, stores_by_id, options)
            if plan is not None and plan.covered > 0:
                plans.append(plan)
    plans.sort(key=lambda p: _plan_sort_key(p, stores_by_id))
    singles = [p for p in plans if p.kind == "single"]
    best_single = singles[0] if singles else None
    best = plans[0] if plans else None
    split_savings = None
    if best is not None and best.kind == "split" and best_single is not None:
        if best_single.covered == best.covered:
            split_savings = best_single.effective_total - best.effective_total
            if split_savings < SPLIT_MIN_SAVINGS:
                best = best_single  # not worth an extra stop
    assumptions: list[str] = []
    if options.distances is not None and _travel_expected(options):
        assumptions.append(options.distances.description)
    elif options.include_travel:
        assumptions.append(
            "Deslocamento não incluído: cadastre endereço (com localização) e veículo no perfil."
        )
    assumptions.append(f"Até {options.max_stops} parada(s) por compra.")
    assumptions.append(
        f"Divisão entre lojas só é sugerida se economizar pelo menos {format_brl(SPLIT_MIN_SAVINGS)}."
    )
    alternatives = [p for p in plans if p is not best][:4]
    return EconomicPlanView(
        best=best,
        best_single=best_single,
        alternatives=alternatives,
        split_savings=split_savings,
        assumptions=assumptions,
    )


def _confidence(
    rows: Sequence[ItemRow], plan: Plan | None, options: ComparisonOptions
) -> tuple[str, list[str]]:
    if plan is None:
        return "baixa", ["Não há preços utilizáveis."]
    reasons: list[str] = []
    level = 2  # 2 alta, 1 media, 0 baixa
    total = len(rows)
    coverage = plan.covered / total if total else 0
    if coverage < 0.7:
        level = min(level, 0)
        reasons.append(f"Cobertura baixa: {plan.covered} de {total} itens.")
    elif coverage < 1:
        level = min(level, 1)
        reasons.append(f"Cobertura parcial: {plan.covered} de {total} itens.")
    else:
        reasons.append("Todos os itens da lista têm preço.")
    used_cells = [
        row.cells[stop.store_id]
        for stop in plan.stops
        for row in rows
        if row.request.item_id in stop.item_ids
    ]
    stale = sum(1 for c in used_cells if c.status == STALE)
    if stale and stale == len(used_cells):
        level = min(level, 0)
        reasons.append("Todos os preços usados estão desatualizados (uso autorizado por você).")
    elif stale:
        level = min(level, 1)
        reasons.append(f"Inclui {stale} preço(s) desatualizado(s) que você autorizou.")
    else:
        reasons.append(f"Todos os preços usados têm até {options.freshness_days} dias.")
    if any(c.offer is not None and c.offer.method == "llm" for c in used_cells):
        level = min(level, 1)
        reasons.append("Algum preço foi extraído com ajuda de IA.")
    if any(c.line is not None and c.line.approximate for c in used_cells):
        level = min(level, 1)
        reasons.append("Há itens de peso variável com quantidade estimada.")
    if not plan.travel_known:
        level = min(level, 1)
        reasons.append("Deslocamento de alguma loja não pôde ser calculado.")
    flagged = sum(1 for r in rows for c in r.cells.values() if c.status == FLAGGED)
    if flagged:
        reasons.append(f"{flagged} preço(s) sinalizado(s) para revisão foram ignorados.")
    return {2: "alta", 1: "media", 0: "baixa"}[level], reasons


def _recommend(
    rows: Sequence[ItemRow],
    stores_by_id: dict[str, StoreOption],
    common: CommonBasket,
    coverage: CoverageView,
    plan_view: EconomicPlanView,
    options: ComparisonOptions,
) -> Recommendation:
    total_items = len(rows)
    warnings: list[str] = []
    missing_everywhere = [r.request.name for r in rows if not r.usable_store_ids]
    if missing_everywhere:
        warnings.append(
            "Sem preço utilizável em nenhum mercado: " + ", ".join(missing_everywhere) + "."
        )
    stale_blocked = sum(
        1 for r in rows for c in r.cells.values() if c.status == STALE and not c.usable
    )
    if stale_blocked:
        warnings.append(
            f"{stale_blocked} preço(s) com mais de {options.freshness_days} dias foram ignorados; "
            "atualize os preços ou autorize o uso de preços antigos."
        )
    plan = plan_view.best
    confidence, reasons = _confidence(rows, plan, options)
    if plan is None:
        return Recommendation(
            kind="none",
            store_ids=[],
            headline="Ainda não há preços suficientes para recomendar onde comprar.",
            explanation=["Busque preços para os mercados selecionados."],
            products_total=None,
            travel_total=None,
            effective_total=None,
            savings=None,
            savings_reference_store_id=None,
            covered=0,
            total_items=total_items,
            newest_observed_at=None,
            oldest_observed_at=None,
            confidence=confidence,
            confidence_reasons=reasons,
            warnings=warnings,
        )
    used = [
        row.cells[stop.store_id].offer
        for stop in plan.stops
        for row in rows
        if row.request.item_id in stop.item_ids
    ]
    observed = [o.observed_at for o in used if o is not None]
    labels = [stores_by_id[sid].label for sid in plan.store_ids]
    travel_total = plan.travel.total if plan.travel else None

    savings = None
    reference = None
    if plan.kind == "single":
        peers = [
            p
            for p in plan_view.alternatives
            if p.kind == "single" and p.covered == plan.covered and p.travel_known
        ]
        if peers:
            savings = peers[0].effective_total - plan.effective_total
            reference = peers[0].store_ids[0]
    elif plan_view.best_single is not None and plan_view.best_single.covered == plan.covered:
        savings = plan_view.best_single.effective_total - plan.effective_total
        reference = plan_view.best_single.store_ids[0]

    if plan.kind == "single":
        headline = f"Compre no {labels[0]}"
    else:
        markets = list(dict.fromkeys(stores_by_id[sid].market_name for sid in plan.store_ids))
        headline = "Divida a compra entre " + " e ".join(markets)
    explanation = [
        f"Produtos: {format_brl(plan.products_total)}"
        + (f" · deslocamento: {format_brl(travel_total)}" if travel_total is not None else "")
        + f" · total: {format_brl(plan.effective_total)}.",
        f"{plan.covered} de {total_items} itens encontrados.",
    ]
    if savings is not None and reference is not None and savings > 0:
        explanation.append(
            f"Economia estimada de {format_brl(savings)} em relação ao "
            f"{stores_by_id[reference].label} (mesma cobertura)."
        )
    if plan.missing_item_ids:
        names = [r.request.name for r in rows if r.request.item_id in plan.missing_item_ids]
        explanation.append("Faltam: " + ", ".join(names) + ".")
    if (
        plan_view.split_savings is not None
        and plan.kind == "single"
        and plan_view.split_savings > 0
    ):
        explanation.append(
            f"Dividir entre lojas economizaria só {format_brl(plan_view.split_savings)}; "
            "uma parada é mais simples."
        )
    if (
        common.comparable
        and common.winner_store_id
        and common.winner_store_id not in plan.store_ids
    ):
        explanation.append(
            f"Na cesta comum ({len(common.item_ids)} itens), o menor total é do "
            f"{stores_by_id[common.winner_store_id].label}."
        )
    return Recommendation(
        kind=plan.kind,
        store_ids=plan.store_ids,
        headline=headline,
        explanation=explanation,
        products_total=plan.products_total,
        travel_total=travel_total,
        effective_total=plan.effective_total,
        savings=savings,
        savings_reference_store_id=reference,
        covered=plan.covered,
        total_items=total_items,
        newest_observed_at=max(observed) if observed else None,
        oldest_observed_at=min(observed) if observed else None,
        confidence=confidence,
        confidence_reasons=reasons,
        warnings=warnings,
    )


def compare(
    requests: Sequence[LineRequest],
    stores: Sequence[StoreOption],
    offers: Sequence[OfferInput],
    options: ComparisonOptions,
) -> ComparisonResult:
    stores_by_id = {s.store_id: s for s in stores}
    rows = build_rows(requests, stores, offers, options)
    travel_cache = {s.store_id: _travel_for([s.store_id], stores_by_id, options) for s in stores}
    common = _common_basket(rows, stores, stores_by_id, options, travel_cache)
    coverage = _coverage_view(rows, stores, stores_by_id, options, travel_cache)
    plan_view = _economic_plan(rows, stores, stores_by_id, options)
    recommendation = _recommend(rows, stores_by_id, common, coverage, plan_view, options)
    return ComparisonResult(
        generated_at=options.now,
        options=options,
        stores=list(stores),
        items=rows,
        common=common,
        coverage=coverage,
        plan=plan_view,
        recommendation=recommendation,
        travel_by_store=travel_cache,
    )
