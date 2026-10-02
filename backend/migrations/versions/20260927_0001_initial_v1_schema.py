"""initial v1 schema

Revision ID: 0001
Revises:
Create Date: 2026-09-27 20:11:12.051076+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "geo_cache",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column(
            "result",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_geo_cache")),
    )
    op.create_index(op.f("ix_geo_cache_expires_at"), "geo_cache", ["expires_at"], unique=False)
    op.create_table(
        "http_cache",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_http_cache")),
    )
    op.create_index(op.f("ix_http_cache_expires_at"), "http_cache", ["expires_at"], unique=False)
    op.create_table(
        "llm_cache",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column(
            "response",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_llm_cache")),
    )
    op.create_index(op.f("ix_llm_cache_expires_at"), "llm_cache", ["expires_at"], unique=False)
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("base_url", sa.String(length=300), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("api_key_env", sa.String(length=64), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("structured_output", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("last_check_status", sa.String(length=24), nullable=True),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_detail", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('groq', 'openai', 'openai_compatible')", name=op.f("ck_llm_providers_kind")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_providers")),
        sa.UniqueConstraint("name", name=op.f("uq_llm_providers_name")),
    )
    op.create_table(
        "login_attempts",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("username_key", sa.String(length=64), nullable=False),
        sa.Column("client_key", sa.String(length=64), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempts")),
    )
    op.create_index(
        "ix_login_attempts_client_key_created_at",
        "login_attempts",
        ["client_key", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_login_attempts_username_key_created_at",
        "login_attempts",
        ["username_key", "created_at"],
        unique=False,
    )
    op.create_table(
        "markets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("website", sa.String(length=200), nullable=False),
        sa.Column("adapter_key", sa.String(length=40), nullable=False),
        sa.Column(
            "allowed_domains",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("brand_color", sa.String(length=9), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_markets")),
        sa.UniqueConstraint("slug", name=op.f("uq_markets_slug")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'user')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "adapter_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("market_id", sa.Uuid(), nullable=False),
        sa.Column("adapter_key", sa.String(length=40), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("strategy", sa.String(length=80), nullable=False),
        sa.Column(
            "config",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["market_id"],
            ["markets.id"],
            name=op.f("fk_adapter_versions_market_id_markets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_adapter_versions")),
        sa.UniqueConstraint(
            "market_id", "version", name=op.f("uq_adapter_versions_market_id_version")
        ),
    )
    op.create_table(
        "addresses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("postal_code", sa.String(length=9), nullable=True),
        sa.Column("street", sa.String(length=200), nullable=True),
        sa.Column("number", sa.String(length=20), nullable=True),
        sa.Column("complement", sa.String(length=100), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("geocode_source", sa.String(length=32), nullable=True),
        sa.Column("geocoded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_addresses_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_addresses")),
    )
    op.create_index(op.f("ix_addresses_user_id"), "addresses", ["user_id"], unique=False)
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column(
            "value",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_app_settings_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_settings")),
    )
    op.create_table(
        "images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("storage_key", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("attribution", sa.String(length=300), nullable=True),
        sa.Column("license", sa.String(length=80), nullable=True),
        sa.Column("alt_text", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('seed', 'upload', 'url')", name=op.f("ck_images_source")),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_images_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_images")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_images_storage_key")),
    )
    op.create_index(op.f("ix_images_owner_user_id"), "images", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_images_sha256"), "images", ["sha256"], unique=False)
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.String(length=600), nullable=False),
        sa.Column(
            "data",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        "ix_notifications_user_id_created_at",
        "notifications",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("freshness_days", sa.Integer(), nullable=False),
        sa.Column("include_travel_cost", sa.Boolean(), nullable=False),
        sa.Column("max_stops", sa.Integer(), nullable=False),
        sa.Column(
            "use_club_prices",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "freshness_days BETWEEN 1 AND 90", name=op.f("ck_profiles_freshness_days")
        ),
        sa.CheckConstraint("max_stops BETWEEN 1 AND 4", name=op.f("ck_profiles_max_stops")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_profiles")),
    )
    op.create_table(
        "recovery_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_recovery_codes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recovery_codes")),
        sa.UniqueConstraint(
            "user_id", "code_hash", name=op.f("uq_recovery_codes_user_id_code_hash")
        ),
    )
    op.create_index(op.f("ix_recovery_codes_user_id"), "recovery_codes", ["user_id"], unique=False)
    op.create_table(
        "shopping_lists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_shopping_lists_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shopping_lists")),
    )
    op.create_index(op.f("ix_shopping_lists_user_id"), "shopping_lists", ["user_id"], unique=False)
    op.create_table(
        "stores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("market_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=80), nullable=True),
        sa.Column("street", sa.String(length=200), nullable=True),
        sa.Column("number", sa.String(length=20), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("postal_code", sa.String(length=9), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column(
            "price_context",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("price_scope_note", sa.String(length=300), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["market_id"],
            ["markets.id"],
            name=op.f("fk_stores_market_id_markets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stores")),
        sa.UniqueConstraint("market_id", "slug", name=op.f("uq_stores_market_id_slug")),
    )
    op.create_index(op.f("ix_stores_market_id"), "stores", ["market_id"], unique=False)
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_label", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_sessions_token_hash")),
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("fuel_type", sa.String(length=16), nullable=False),
        sa.Column("km_per_liter", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("fuel_price_per_liter", sa.Numeric(precision=8, scale=3), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "fuel_price_per_liter >= 0", name=op.f("ck_vehicles_fuel_price_non_negative")
        ),
        sa.CheckConstraint("km_per_liter > 0", name=op.f("ck_vehicles_km_per_liter_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_vehicles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicles")),
    )
    op.create_index(op.f("ix_vehicles_user_id"), "vehicles", ["user_id"], unique=False)
    op.create_table(
        "catalog_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("sold_by", sa.String(length=16), nullable=False),
        sa.Column("package_quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("package_unit", sa.String(length=8), nullable=True),
        sa.Column("default_quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("default_unit", sa.String(length=8), nullable=False),
        sa.Column("brand", sa.String(length=80), nullable=True),
        sa.Column(
            "match_spec",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("image_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "default_unit IN ('g', 'kg', 'ml', 'l', 'un', 'pct')",
            name=op.f("ck_catalog_items_default_unit"),
        ),
        sa.CheckConstraint(
            "sold_by IN ('package', 'weight', 'unit')", name=op.f("ck_catalog_items_sold_by")
        ),
        sa.CheckConstraint(
            "default_quantity > 0", name=op.f("ck_catalog_items_default_quantity_positive")
        ),
        sa.ForeignKeyConstraint(
            ["image_id"],
            ["images.id"],
            name=op.f("fk_catalog_items_image_id_images"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_items")),
        sa.UniqueConstraint("slug", name=op.f("uq_catalog_items_slug")),
    )
    op.create_index(op.f("ix_catalog_items_category"), "catalog_items", ["category"], unique=False)
    op.create_table(
        "schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("list_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("frequency", sa.String(length=16), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("time_local", sa.String(length=5), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column(
            "store_ids",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("frequency IN ('daily', 'weekly')", name=op.f("ck_schedules_frequency")),
        sa.CheckConstraint(
            "weekday IS NULL OR (weekday BETWEEN 0 AND 6)", name=op.f("ck_schedules_weekday")
        ),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["shopping_lists.id"],
            name=op.f("fk_schedules_list_id_shopping_lists"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_schedules_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedules")),
    )
    op.create_index(
        "ix_schedules_enabled_next_run_at", "schedules", ["enabled", "next_run_at"], unique=False
    )
    op.create_index(op.f("ix_schedules_user_id"), "schedules", ["user_id"], unique=False)
    op.create_table(
        "user_store_selections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("toll_round_trip", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "toll_round_trip >= 0", name=op.f("ck_user_store_selections_toll_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name=op.f("fk_user_store_selections_store_id_stores"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_store_selections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_store_selections")),
        sa.UniqueConstraint(
            "user_id", "store_id", name=op.f("uq_user_store_selections_user_id_store_id")
        ),
    )
    op.create_index(
        op.f("ix_user_store_selections_user_id"), "user_store_selections", ["user_id"], unique=False
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_item_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("sold_by", sa.String(length=16), nullable=False),
        sa.Column("package_quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("package_unit", sa.String(length=8), nullable=True),
        sa.Column("preferred_brand", sa.String(length=80), nullable=True),
        sa.Column("strict_brand", sa.Boolean(), nullable=False),
        sa.Column("size_tolerance_pct", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column(
            "substitutions",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "match_spec",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("image_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "sold_by IN ('package', 'weight', 'unit')", name=op.f("ck_products_sold_by")
        ),
        sa.CheckConstraint(
            "size_tolerance_pct >= 0 AND size_tolerance_pct <= 100",
            name=op.f("ck_products_tolerance"),
        ),
        sa.ForeignKeyConstraint(
            ["catalog_item_id"],
            ["catalog_items.id"],
            name=op.f("fk_products_catalog_item_id_catalog_items"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["image_id"],
            ["images.id"],
            name=op.f("fk_products_image_id_images"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_products_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint(
            "user_id", "catalog_item_id", name=op.f("uq_products_user_id_catalog_item_id")
        ),
    )
    op.create_index(op.f("ix_products_user_id"), "products", ["user_id"], unique=False)
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("list_id", sa.Uuid(), nullable=True),
        sa.Column("schedule_id", sa.Uuid(), nullable=True),
        sa.Column("parent_run_id", sa.Uuid(), nullable=True),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "params",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=80), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("total_targets", sa.Integer(), nullable=False),
        sa.Column("done_targets", sa.Integer(), nullable=False),
        sa.Column(
            "counts",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("llm_calls", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'success', 'partial', 'failed', 'cancelled')",
            name=op.f("ck_runs_status"),
        ),
        sa.CheckConstraint(
            "trigger IN ('manual', 'schedule', 'cli', 'retry')", name=op.f("ck_runs_trigger")
        ),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["shopping_lists.id"],
            name=op.f("fk_runs_list_id_shopping_lists"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_run_id"],
            ["runs.id"],
            name=op.f("fk_runs_parent_run_id_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.id"],
            name=op.f("fk_runs_schedule_id_schedules"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_runs_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_runs_idempotency_key")),
    )
    op.create_index("ix_runs_status_created_at", "runs", ["status", "created_at"], unique=False)
    op.create_index("ix_runs_user_id_created_at", "runs", ["user_id", "created_at"], unique=False)
    op.create_table(
        "list_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("list_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=8), nullable=False),
        sa.Column("notes", sa.String(length=200), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "unit IN ('g', 'kg', 'ml', 'l', 'un', 'pct')", name=op.f("ck_list_items_unit")
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_list_items_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["shopping_lists.id"],
            name=op.f("fk_list_items_list_id_shopping_lists"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_list_items_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_list_items")),
        sa.UniqueConstraint("list_id", "product_id", name=op.f("uq_list_items_list_id_product_id")),
    )
    op.create_index(op.f("ix_list_items_list_id"), "list_items", ["list_id"], unique=False)
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("target_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("target_price > 0", name=op.f("ck_price_alerts_target_price_positive")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_price_alerts_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_price_alerts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_alerts")),
        sa.UniqueConstraint(
            "user_id", "product_id", name=op.f("uq_price_alerts_user_id_product_id")
        ),
    )
    op.create_index(op.f("ix_price_alerts_user_id"), "price_alerts", ["user_id"], unique=False)
    op.create_table(
        "product_market_pins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("market_id", sa.Uuid(), nullable=False),
        sa.Column("listing_key", sa.String(length=200), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("gtin", sa.String(length=20), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("decision", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('accept', 'reject')", name=op.f("ck_product_market_pins_decision")
        ),
        sa.ForeignKeyConstraint(
            ["market_id"],
            ["markets.id"],
            name=op.f("fk_product_market_pins_market_id_markets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_market_pins_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_product_market_pins_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_market_pins")),
        sa.UniqueConstraint(
            "product_id",
            "market_id",
            "listing_key",
            name=op.f("uq_product_market_pins_product_id_market_id_listing_key"),
        ),
    )
    op.create_index(
        op.f("ix_product_market_pins_user_id"), "product_market_pins", ["user_id"], unique=False
    )
    op.create_table(
        "run_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("market_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=True),
        sa.Column("adapter_version", sa.String(length=40), nullable=True),
        sa.Column("search_query", sa.String(length=200), nullable=True),
        sa.Column("error_type", sa.String(length=40), nullable=True),
        sa.Column("error_detail", sa.String(length=500), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("llm_needed", sa.Boolean(), nullable=False),
        sa.Column("llm_used", sa.Boolean(), nullable=False),
        sa.Column(
            "diagnostics",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'found', 'not_found', 'unavailable', 'no_price', 'blocked', 'timeout', 'adapter_error', 'needs_llm', 'cancelled')",
            name=op.f("ck_run_targets_status"),
        ),
        sa.ForeignKeyConstraint(
            ["market_id"],
            ["markets.id"],
            name=op.f("fk_run_targets_market_id_markets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_run_targets_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_run_targets_run_id_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name=op.f("fk_run_targets_store_id_stores"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_run_targets_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_targets")),
        sa.UniqueConstraint(
            "run_id",
            "product_id",
            "store_id",
            name=op.f("uq_run_targets_run_id_product_id_store_id"),
        ),
    )
    op.create_index(
        "ix_run_targets_run_id_status", "run_targets", ["run_id", "status"], unique=False
    )
    op.create_index(op.f("ix_run_targets_user_id"), "run_targets", ["user_id"], unique=False)
    op.create_table(
        "candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("match_score", sa.Numeric(precision=5, scale=3), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("chosen", sa.Boolean(), nullable=False),
        sa.Column(
            "reasons",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "raw",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("sku", sa.String(length=120), nullable=True),
        sa.Column("gtin", sa.String(length=20), nullable=True),
        sa.Column("package_quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("package_unit", sa.String(length=8), nullable=True),
        sa.Column("sold_by", sa.String(length=16), nullable=True),
        sa.Column("unit_multiplier", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("regular_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("promo_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("club_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("club_label", sa.String(length=80), nullable=True),
        sa.Column("quantity_min", sa.Integer(), nullable=True),
        sa.Column("quantity_price", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("quantity_mode", sa.String(length=16), nullable=True),
        sa.Column(
            "extra_prices",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("unit_price_unit", sa.String(length=8), nullable=True),
        sa.Column("availability", sa.String(length=16), nullable=False),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["run_targets.id"],
            name=op.f("fk_candidates_target_id_run_targets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidates")),
    )
    op.create_index(op.f("ix_candidates_target_id"), "candidates", ["target_id"], unique=False)
    op.create_table(
        "llm_calls",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_type", sa.String(length=40), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_llm_calls_run_id_runs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["run_targets.id"],
            name=op.f("fk_llm_calls_target_id_run_targets"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_calls")),
    )
    op.create_index(op.f("ix_llm_calls_created_at"), "llm_calls", ["created_at"], unique=False)
    op.create_index(op.f("ix_llm_calls_run_id"), "llm_calls", ["run_id"], unique=False)
    op.create_table(
        "observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("market_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("adapter_version", sa.String(length=40), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("match_score", sa.Numeric(precision=5, scale=3), nullable=False),
        sa.Column(
            "raw_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("raw_sha256", sa.String(length=64), nullable=True),
        sa.Column("is_outlier", sa.Boolean(), nullable=False),
        sa.Column("outlier_reason", sa.String(length=300), nullable=True),
        sa.Column("review_status", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("sku", sa.String(length=120), nullable=True),
        sa.Column("gtin", sa.String(length=20), nullable=True),
        sa.Column("package_quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("package_unit", sa.String(length=8), nullable=True),
        sa.Column("sold_by", sa.String(length=16), nullable=True),
        sa.Column("unit_multiplier", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("regular_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("promo_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("club_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("club_label", sa.String(length=80), nullable=True),
        sa.Column("quantity_min", sa.Integer(), nullable=True),
        sa.Column("quantity_price", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("quantity_mode", sa.String(length=16), nullable=True),
        sa.Column(
            "extra_prices",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("unit_price_unit", sa.String(length=8), nullable=True),
        sa.Column("availability", sa.String(length=16), nullable=False),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.CheckConstraint(
            "review_status IN ('ok', 'flagged', 'confirmed', 'rejected')",
            name=op.f("ck_observations_review_status"),
        ),
        sa.ForeignKeyConstraint(
            ["market_id"],
            ["markets.id"],
            name=op.f("fk_observations_market_id_markets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_observations_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_observations_run_id_runs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name=op.f("fk_observations_store_id_stores"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["run_targets.id"],
            name=op.f("fk_observations_target_id_run_targets"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_observations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_observations")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_observations_idempotency_key")),
        sa.UniqueConstraint("target_id", name=op.f("uq_observations_target_id")),
    )
    op.create_index(
        op.f("ix_observations_observed_at"), "observations", ["observed_at"], unique=False
    )
    op.create_index(op.f("ix_observations_run_id"), "observations", ["run_id"], unique=False)
    op.create_index(
        "ix_observations_user_product_store_observed",
        "observations",
        ["user_id", "product_id", "store_id", "observed_at"],
        unique=False,
    )
    op.create_table(
        "run_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("level", sa.String(length=8), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("message", sa.String(length=300), nullable=False),
        sa.Column(
            "data",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_run_events_run_id_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["run_targets.id"],
            name=op.f("fk_run_events_target_id_run_targets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_events")),
    )
    op.create_index(op.f("ix_run_events_run_id"), "run_events", ["run_id"], unique=False)


def downgrade() -> None:

    op.drop_index(op.f("ix_run_events_run_id"), table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ix_observations_user_product_store_observed", table_name="observations")
    op.drop_index(op.f("ix_observations_run_id"), table_name="observations")
    op.drop_index(op.f("ix_observations_observed_at"), table_name="observations")
    op.drop_table("observations")
    op.drop_index(op.f("ix_llm_calls_run_id"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_created_at"), table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_index(op.f("ix_candidates_target_id"), table_name="candidates")
    op.drop_table("candidates")
    op.drop_index(op.f("ix_run_targets_user_id"), table_name="run_targets")
    op.drop_index("ix_run_targets_run_id_status", table_name="run_targets")
    op.drop_table("run_targets")
    op.drop_index(op.f("ix_product_market_pins_user_id"), table_name="product_market_pins")
    op.drop_table("product_market_pins")
    op.drop_index(op.f("ix_price_alerts_user_id"), table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_index(op.f("ix_list_items_list_id"), table_name="list_items")
    op.drop_table("list_items")
    op.drop_index("ix_runs_user_id_created_at", table_name="runs")
    op.drop_index("ix_runs_status_created_at", table_name="runs")
    op.drop_table("runs")
    op.drop_index(op.f("ix_products_user_id"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_user_store_selections_user_id"), table_name="user_store_selections")
    op.drop_table("user_store_selections")
    op.drop_index(op.f("ix_schedules_user_id"), table_name="schedules")
    op.drop_index("ix_schedules_enabled_next_run_at", table_name="schedules")
    op.drop_table("schedules")
    op.drop_index(op.f("ix_catalog_items_category"), table_name="catalog_items")
    op.drop_table("catalog_items")
    op.drop_index(op.f("ix_vehicles_user_id"), table_name="vehicles")
    op.drop_table("vehicles")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index(op.f("ix_stores_market_id"), table_name="stores")
    op.drop_table("stores")
    op.drop_index(op.f("ix_shopping_lists_user_id"), table_name="shopping_lists")
    op.drop_table("shopping_lists")
    op.drop_index(op.f("ix_recovery_codes_user_id"), table_name="recovery_codes")
    op.drop_table("recovery_codes")
    op.drop_table("profiles")
    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_images_sha256"), table_name="images")
    op.drop_index(op.f("ix_images_owner_user_id"), table_name="images")
    op.drop_table("images")
    op.drop_table("app_settings")
    op.drop_index(op.f("ix_addresses_user_id"), table_name="addresses")
    op.drop_table("addresses")
    op.drop_table("adapter_versions")
    op.drop_table("users")
    op.drop_table("markets")
    op.drop_index("ix_login_attempts_username_key_created_at", table_name="login_attempts")
    op.drop_index("ix_login_attempts_client_key_created_at", table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_table("llm_providers")
    op.drop_index(op.f("ix_llm_cache_expires_at"), table_name="llm_cache")
    op.drop_table("llm_cache")
    op.drop_index(op.f("ix_http_cache_expires_at"), table_name="http_cache")
    op.drop_table("http_cache")
    op.drop_index(op.f("ix_geo_cache_expires_at"), table_name="geo_cache")
    op.drop_table("geo_cache")
