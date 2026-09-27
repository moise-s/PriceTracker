"""API schemas. Money and quantities are ``Decimal`` and serialise as strings."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pricetracker.models.enums import Role, RunStatus, RunTrigger, SoldBy, TargetStatus, Unit


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Problem(Model):
    code: str
    message: str
    details: Any = None


class Ok(Model):
    ok: bool = True


# --- system -------------------------------------------------------------------------


class HealthOut(Model):
    status: Literal["ok", "degraded"]
    database: bool
    schema_version: str | None = None


class MetaOut(Model):
    version: str
    environment: str
    timezone: str
    default_freshness_days: int
    registration_enabled: bool
    needs_setup: bool
    requires_setup_code: bool
    geocoder: str
    router: str


# --- auth ------------------------------------------------------------------------------


class SetupStatus(Model):
    needs_setup: bool
    requires_code: bool


class SetupAdminIn(Model):
    username: str = Field(min_length=3, max_length=32)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)
    setup_code: str | None = Field(default=None, max_length=40)


class LoginIn(Model):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RegisterIn(Model):
    username: str = Field(min_length=3, max_length=32)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class RecoverIn(Model):
    username: str = Field(min_length=1, max_length=64)
    recovery_code: str = Field(min_length=6, max_length=40)
    new_password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(Model):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class PasswordConfirmIn(Model):
    password: str = Field(min_length=1, max_length=256)


class UserOut(Model):
    id: uuid.UUID
    username: str
    display_name: str
    role: Role
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None = None


class MeOut(Model):
    user: UserOut
    onboarding_completed: bool
    recovery_codes_remaining: int


class AccountCreatedOut(Model):
    user: UserOut
    recovery_codes: list[str]


class RecoveryCodesOut(Model):
    recovery_codes: list[str]


class SessionOut(Model):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    client_label: str | None = None
    current: bool = False


# --- images / catalog / products ----------------------------------------------------------


class ImageRef(Model):
    id: uuid.UUID
    url: str
    alt_text: str | None = None
    source: str
    attribution: str | None = None
    license: str | None = None


class CatalogItemOut(Model):
    id: uuid.UUID
    slug: str
    name: str
    category: str
    description: str | None = None
    sold_by: SoldBy
    package_quantity: Decimal | None = None
    package_unit: str | None = None
    default_quantity: Decimal
    default_unit: str
    brand: str | None = None
    match_spec: dict[str, Any]
    image: ImageRef | None = None
    is_active: bool
    in_my_products: bool = False
    my_product_id: uuid.UUID | None = None


class CatalogItemIn(Model):
    slug: str = Field(pattern=r"^[a-z0-9-]{3,80}$")
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=40)
    description: str | None = Field(default=None, max_length=300)
    sold_by: SoldBy
    package_quantity: Decimal | None = Field(default=None, gt=0)
    package_unit: Unit | None = None
    default_quantity: Decimal = Field(default=Decimal("1"), gt=0)
    default_unit: Unit = Unit.UN
    brand: str | None = Field(default=None, max_length=80)
    match_spec: dict[str, Any]
    is_active: bool = True


class CatalogOut(Model):
    categories: list[str]
    items: list[CatalogItemOut]


class ProductOut(Model):
    id: uuid.UUID
    catalog_item_id: uuid.UUID | None = None
    name: str
    category: str
    sold_by: SoldBy
    package_quantity: Decimal | None = None
    package_unit: str | None = None
    preferred_brand: str | None = None
    strict_brand: bool
    size_tolerance_pct: Decimal
    substitutions: dict[str, Any]
    match_spec: dict[str, Any]
    image: ImageRef | None = None
    is_active: bool
    is_favorite: bool
    is_custom: bool
    allowed_units: list[str]
    default_unit: str
    created_at: datetime
    updated_at: datetime


class ProductIn(Model):
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=40)
    sold_by: SoldBy
    package_quantity: Decimal | None = Field(default=None, gt=0, le=100000)
    package_unit: Unit | None = None
    preferred_brand: str | None = Field(default=None, max_length=80)
    strict_brand: bool = False
    size_tolerance_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    substitutions: dict[str, Any] = Field(default_factory=dict)
    match_spec: dict[str, Any] | None = None
    is_favorite: bool = False


class ProductPatch(Model):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    category: str | None = Field(default=None, min_length=2, max_length=40)
    sold_by: SoldBy | None = None
    package_quantity: Decimal | None = Field(default=None, gt=0, le=100000)
    package_unit: Unit | None = None
    preferred_brand: str | None = Field(default=None, max_length=80)
    strict_brand: bool | None = None
    size_tolerance_pct: Decimal | None = Field(default=None, ge=0, le=100)
    substitutions: dict[str, Any] | None = None
    match_spec: dict[str, Any] | None = None
    is_active: bool | None = None
    is_favorite: bool | None = None


class ImageUrlIn(Model):
    url: str = Field(min_length=8, max_length=1000)
    attribution: str | None = Field(default=None, max_length=300)


class PinIn(Model):
    candidate_id: uuid.UUID
    decision: Literal["accept", "reject"]


# --- lists -------------------------------------------------------------------------------


class ListItemOut(Model):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    category: str
    image: ImageRef | None = None
    quantity: Decimal
    unit: str
    allowed_units: list[str]
    notes: str | None = None
    position: int
    checked: bool


class ShoppingListOut(Model):
    id: uuid.UUID
    name: str
    is_default: bool
    archived: bool
    item_count: int
    items: list[ListItemOut]
    updated_at: datetime


class ListIn(Model):
    name: str = Field(min_length=1, max_length=80)
    copy_from: uuid.UUID | None = None


class ListPatch(Model):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    is_default: bool | None = None
    archived: bool | None = None


class ListItemIn(Model):
    product_id: uuid.UUID | None = None
    catalog_item_id: uuid.UUID | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0, le=1000)
    unit: Unit | None = None
    notes: str | None = Field(default=None, max_length=200)


class ListItemPatch(Model):
    quantity: Decimal | None = Field(default=None, gt=0, le=1000)
    unit: Unit | None = None
    notes: str | None = Field(default=None, max_length=200)
    checked: bool | None = None
    position: int | None = Field(default=None, ge=0)


# --- markets & stores ------------------------------------------------------------------------


class StoreOut(Model):
    id: uuid.UUID
    slug: str
    name: str
    street: str | None = None
    number: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    price_scope_note: str | None = None
    selected: bool = False
    toll_round_trip: Decimal = Decimal("0")
    last_observed_at: datetime | None = None
    distance_km: Decimal | None = None


class MarketOut(Model):
    id: uuid.UUID
    slug: str
    name: str
    website: str
    brand_color: str | None = None
    enabled: bool
    notes: str | None = None
    health: str
    last_success_at: datetime | None = None
    stores: list[StoreOut]


class StoreSelectionIn(Model):
    store_id: uuid.UUID
    toll_round_trip: Decimal = Field(default=Decimal("0"), ge=0, le=1000)


class StoreSelectionsIn(Model):
    selections: list[StoreSelectionIn] = Field(max_length=40)


# --- profile ----------------------------------------------------------------------------------


class ProfileOut(Model):
    display_name: str
    timezone: str
    freshness_days: int
    include_travel_cost: bool
    max_stops: int
    use_club_prices: list[str]
    onboarding_completed_at: datetime | None = None


class ProfilePatch(Model):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    freshness_days: int | None = Field(default=None, ge=1, le=90)
    include_travel_cost: bool | None = None
    max_stops: int | None = Field(default=None, ge=1, le=3)
    use_club_prices: list[str] | None = None
    complete_onboarding: bool = False


class AddressIn(Model):
    label: str = Field(default="Casa", max_length=60)
    postal_code: str | None = Field(default=None, max_length=9)
    street: str | None = Field(default=None, max_length=200)
    number: str | None = Field(default=None, max_length=20)
    complement: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=2)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    is_primary: bool = True


class AddressOut(AddressIn):
    id: uuid.UUID
    geocode_source: str | None = None
    geocoded_at: datetime | None = None


class VehicleIn(Model):
    name: str = Field(min_length=1, max_length=80)
    fuel_type: Literal["gasolina", "etanol", "diesel", "gnv", "flex"] = "gasolina"
    km_per_liter: Decimal = Field(gt=0, le=100)
    fuel_price_per_liter: Decimal = Field(ge=0, le=100)
    is_primary: bool = True


class VehicleOut(VehicleIn):
    id: uuid.UUID


# --- runs -------------------------------------------------------------------------------------


class RunCreateIn(Model):
    list_id: uuid.UUID | None = None
    store_ids: list[uuid.UUID] | None = Field(default=None, max_length=40)
    product_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)
    allow_llm: bool = True


class RunTargetOut(Model):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    store_id: uuid.UUID
    store_name: str
    market_slug: str
    market_name: str
    status: TargetStatus
    method: str | None = None
    error_type: str | None = None
    error_detail: str | None = None
    duration_ms: int | None = None
    candidate_count: int
    llm_needed: bool
    llm_used: bool
    started_at: datetime | None = None
    finished_at: datetime | None = None
    observation: dict[str, Any] | None = None


class RunEventOut(Model):
    id: int
    level: str
    event: str
    message: str
    created_at: datetime


class RunOut(Model):
    id: uuid.UUID
    status: RunStatus
    trigger: RunTrigger
    list_id: uuid.UUID | None = None
    parent_run_id: uuid.UUID | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    cancel_requested: bool
    total_targets: int
    done_targets: int
    counts: dict[str, int]
    llm_calls: int
    error_summary: str | None = None


class RunDetailOut(RunOut):
    targets: list[RunTargetOut]
    events: list[RunEventOut]
    retryable: int


class CandidateOut(Model):
    id: uuid.UUID
    rank: int
    title: str
    brand: str | None = None
    url: str | None = None
    image_url: str | None = None
    regular_price: Decimal | None = None
    promo_price: Decimal | None = None
    club_price: Decimal | None = None
    unit_price: Decimal | None = None
    unit_price_unit: str | None = None
    availability: str
    method: str
    match_score: Decimal
    accepted: bool
    chosen: bool
    reasons: list[str]


# --- schedules / admin ------------------------------------------------------------------------


class ScheduleIn(Model):
    name: str = Field(min_length=1, max_length=80)
    list_id: uuid.UUID | None = None
    frequency: Literal["daily", "weekly"] = "weekly"
    weekday: int | None = Field(default=None, ge=0, le=6)
    time_local: str = Field(default="07:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    store_ids: list[uuid.UUID] = Field(default_factory=list, max_length=40)
    enabled: bool = True


class ScheduleOut(Model):
    id: uuid.UUID
    name: str
    list_id: uuid.UUID
    frequency: str
    weekday: int | None = None
    time_local: str
    timezone: str
    store_ids: list[uuid.UUID]
    enabled: bool
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_run_id: uuid.UUID | None = None


class AdminSettingsOut(Model):
    registration_enabled: bool
    default_freshness_days: int
    llm_enabled: bool
    llm_max_calls_per_run: int


class AdminSettingsPatch(Model):
    registration_enabled: bool | None = None
    default_freshness_days: int | None = Field(default=None, ge=1, le=90)
    llm_enabled: bool | None = None
    llm_max_calls_per_run: int | None = Field(default=None, ge=0, le=100)


class AdminUserIn(Model):
    username: str = Field(min_length=3, max_length=32)
    display_name: str = Field(min_length=1, max_length=120)
    temporary_password: str = Field(min_length=1, max_length=256)
    role: Role = Role.USER


class AdminUserPatch(Model):
    is_active: bool | None = None
    role: Role | None = None


class AdminResetPasswordIn(Model):
    temporary_password: str = Field(min_length=1, max_length=256)


class LlmProviderOut(Model):
    id: uuid.UUID
    name: str
    kind: str
    base_url: str
    model: str
    structured_output: str
    enabled: bool
    is_default: bool
    key_configured: bool
    key_source: str
    key_env: str | None = None
    last_check_status: str | None = None
    last_check_at: datetime | None = None
    last_check_detail: str | None = None


class LlmProviderIn(Model):
    name: str | None = Field(default=None, min_length=2, max_length=60)
    kind: Literal["groq", "openai", "openai_compatible"] | None = None
    base_url: str | None = Field(default=None, max_length=300)
    model: str | None = Field(default=None, min_length=2, max_length=120)
    structured_output: Literal["json_schema", "json_object"] | None = None
    api_key_env: str | None = Field(default=None, max_length=64)
    api_key: str | None = Field(
        default=None, max_length=400, description="Write-only; stored encrypted"
    )
    clear_stored_key: bool = False
    enabled: bool | None = None
    is_default: bool | None = None


class LlmTestOut(Model):
    ok: bool
    provider: str | None = None
    model: str | None = None
    key_configured: bool = False
    error_type: str | None = None
    message: str
    latency_ms: int | None = None
    available_models: list[str] | None = None


# --- comparison & history (typed contract for the web client) ---------------------------------


class TravelOut(Model):
    distance_km: Decimal
    liters: Decimal
    fuel_cost: Decimal
    tolls: Decimal
    total: Decimal
    method: str
    route: list[str]
    formula: str


class LineOut(Model):
    cost: Decimal
    sale_units: Decimal
    sale_unit_label: str
    price_kind: str
    unit_price: Decimal | None = None
    unit_price_unit: str | None = None
    approximate: bool
    notes: list[str]


class OfferOut(Model):
    observation_id: uuid.UUID
    title: str
    brand: str | None = None
    url: str | None = None
    image_url: str | None = None
    observed_at: datetime
    regular_price: Decimal | None = None
    promo_price: Decimal | None = None
    club_price: Decimal | None = None
    club_label: str | None = None
    quantity_min: int | None = None
    quantity_price: Decimal | None = None
    quantity_mode: str | None = None
    extra_prices: list[dict[str, Any]]
    unit_price: Decimal | None = None
    unit_price_unit: str | None = None
    availability: str
    method: str
    confidence: Decimal
    review_status: str
    outlier_reason: str | None = None


class LastSearchOut(Model):
    status: TargetStatus
    finished_at: datetime | None = None


class CellOut(Model):
    status: Literal["ok", "stale", "flagged", "unavailable", "missing", "incompatible"]
    usable: bool
    reason: str | None = None
    age_days: Decimal | None = None
    last_search: LastSearchOut | None = None
    line: LineOut | None = None
    offer: OfferOut | None = None


class ComparisonItemOut(Model):
    item_id: str
    product_id: str
    name: str
    quantity: Decimal
    unit: str
    image_id: uuid.UUID | None = None
    category: str | None = None
    best_store_id: str | None = None
    best_cost: Decimal | None = None
    worst_cost: Decimal | None = None
    cells: dict[str, CellOut]


class ComparisonStoreOut(Model):
    store_id: str
    market_slug: str
    market_name: str
    store_name: str
    use_club: bool
    tolls: Decimal
    has_location: bool
    price_scope_note: str | None = None
    travel: TravelOut | None = None


class StoreTotalsOut(Model):
    store_id: str
    covered: int
    total_items: int
    products_total: Decimal
    missing_item_ids: list[str]
    stale_used: int
    oldest_age_days: Decimal | None = None
    travel: TravelOut | None = None
    effective_total: Decimal
    travel_known: bool
    complete: bool


class CommonBasketOut(Model):
    item_ids: list[str]
    excluded_item_ids: list[str]
    stores: list[StoreTotalsOut]
    winner_store_id: str | None = None
    savings_vs_runner_up: Decimal | None = None
    savings_vs_most_expensive: Decimal | None = None
    comparable: bool
    note: str


class CoverageOut(Model):
    stores: list[StoreTotalsOut]
    max_coverage: int
    best_store_id: str | None = None
    note: str


class PlanStopOut(Model):
    store_id: str
    item_ids: list[str]
    products_total: Decimal


class PlanOut(Model):
    kind: Literal["single", "split"]
    stops: list[PlanStopOut]
    covered: int
    missing_item_ids: list[str]
    products_total: Decimal
    travel: TravelOut | None = None
    effective_total: Decimal
    travel_known: bool


class EconomicPlanOut(Model):
    best: PlanOut | None = None
    best_single: PlanOut | None = None
    alternatives: list[PlanOut]
    split_savings: Decimal | None = None
    assumptions: list[str]


class RecommendationOut(Model):
    kind: Literal["single", "split", "none"]
    store_ids: list[str]
    headline: str
    explanation: list[str]
    products_total: Decimal | None = None
    travel_total: Decimal | None = None
    effective_total: Decimal | None = None
    savings: Decimal | None = None
    savings_reference_store_id: str | None = None
    covered: int
    total_items: int
    newest_observed_at: datetime | None = None
    oldest_observed_at: datetime | None = None
    confidence: Literal["alta", "media", "baixa"]
    confidence_reasons: list[str]
    warnings: list[str]


class ComparisonOut(Model):
    generated_at: datetime
    freshness_days: int
    allow_stale: bool
    include_travel: bool
    max_stops: int
    home_located: bool
    vehicle_configured: bool
    distance_method: str | None = None
    stores: list[ComparisonStoreOut]
    items: list[ComparisonItemOut]
    common: CommonBasketOut
    coverage: CoverageOut
    plan: EconomicPlanOut
    recommendation: RecommendationOut


class HistoryPointOut(Model):
    observation_id: uuid.UUID
    observed_at: datetime
    price: Decimal | None = None
    regular_price: Decimal | None = None
    promo_price: Decimal | None = None
    club_price: Decimal | None = None
    unit_price: Decimal | None = None
    unit_price_unit: str | None = None
    title: str
    url: str | None = None
    availability: str
    stale: bool
    flagged: bool
    review_status: str
    outlier_reason: str | None = None
    method: str


class HistoryStatsOut(Model):
    min: Decimal | None = None
    max: Decimal | None = None
    median: Decimal | None = None
    last: Decimal | None = None
    count: int


class HistorySeriesOut(Model):
    store_id: uuid.UUID
    store_name: str
    market_slug: str
    market_name: str
    points: list[HistoryPointOut]
    stats: HistoryStatsOut


class HistoryOut(Model):
    product_id: uuid.UUID
    product_name: str
    freshness_days: int
    days: int
    series: list[HistorySeriesOut]


class MarketHealthOut(Model):
    market_id: uuid.UUID
    slug: str
    name: str
    enabled: bool
    adapter_version: str | None = None
    strategy: str | None = None
    state: str
    targets: int
    success_rate: float | None = None
    statuses: dict[str, int]
    methods: dict[str, int]
    errors: dict[str, int]
    llm_used: int
    llm_needed: int
    median_duration_ms: int | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    notes: str | None = None


class LlmUsageOut(Model):
    days: int
    calls: int
    cache_hits: int
    errors: int


class AdminHealthOut(Model):
    markets: list[MarketHealthOut]
    llm: LlmUsageOut
