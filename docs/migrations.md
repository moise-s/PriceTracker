# Schema migrations

[Português](migrations.pt-BR.md)

v1 has a **new schema**: it starts from an empty database and does not import, migrate or read the
prototype's SQLite database (`pricetracker.db`, left intact locally as historical reference).

## Current revisions

| Revision | File | Contents |
| --- | --- | --- |
| `0001` | `backend/migrations/versions/20260927_0001_initial_v1_schema.py` | Initial schema: 31 tables, 23 check constraints, unique constraints and indexes |
| `0002` (head) | `backend/migrations/versions/20261002_0002_length_units.py` | Allow `m` in catalog/list unit checks while preserving existing data |

Migrations are self-contained rather than importing application types. `UTCDateTime` becomes
`sa.DateTime(timezone=True)` through `render_item`. SQLite uses `render_as_batch` so future
alterations work on both databases.

## Tables by area

- **Accounts and sessions:** `users`, `user_sessions` (unique token hash), `recovery_codes`,
  `login_attempts`, `profiles` (freshness 1–90 days, stops 1–4, enabled loyalty clubs, onboarding).
- **Address and vehicle:** `addresses`, `vehicles` (km/l > 0, fuel price ≥ 0).
- **Catalog and products:** global `catalog_items` (unique slug), user-owned `products` with matching
  rules, `images` (unique storage key, indexed SHA-256, seed/upload/URL origin),
  `product_market_pins` (accepted/rejected market listings).
- **Lists:** `shopping_lists`, `list_items` (positive quantity, unique product within a list).
- **Markets:** `markets` (unique slug), `stores` (unique market + slug, coordinates and price context),
  `user_store_selections` (non-negative tolls), `adapter_versions`.
- **Collection:** `runs` (unique idempotency key; status/creation/user indexes), `run_targets`,
  `run_events`, `candidates` (evaluated listings and reasons), `observations` (one per target,
  unique idempotency key; user/product/store/time index for comparison and history).
- **Schedules and notifications:** `schedules` (daily/weekly), `price_alerts` (positive target,
  one per product), `notifications`.
- **Infrastructure:** `app_settings`, `llm_providers`, `llm_calls`, `llm_cache`, `http_cache`,
  `geo_cache` (caches with indexed expiry).

## Conventions

- Money uses `NUMERIC(12,2)`, unit prices `NUMERIC(14,4)`, quantities `NUMERIC(12,3)` and
  coordinates `NUMERIC(9,6)`.
- Timestamps use UTC with timezone (`timestamptz`); local formatting belongs to the UI.
- JSON uses `JSONB` on PostgreSQL and `JSON` on SQLite.
- User-owned records have `user_id` with `ON DELETE CASCADE`.
- Deterministic names for constraints and indexes (`ix_`, `uq_`, `ck_`, `fk_`, `pk_`) make
  `alembic check` reliable.

## Verification on 2026-09-27

These results describe revision `0001`, before the metre support added in `0002`.

| Check | PostgreSQL 17.10 | SQLite |
| --- | --- | --- |
| `alembic upgrade head` on an empty database | Passed, 31 tables | Passed |
| `alembic check` (models vs database) | No new upgrade operations detected | Same |
| `alembic downgrade base` | Passed, 0 tables | — |
| New `upgrade head` + `check` | Passed, no differences | — |
| Docker stack (`migrate` → `db-init`) | Migration and idempotent seed at startup | — |
| Test suite | 135 PostgreSQL tests (`make test-pg`) | 133 SQLite tests |

To reproduce against a disposable development database:

```bash
make dev-db
cd backend
export PRICETRACKER_DATABASE_URL=postgresql+psycopg://pricetracker:pricetracker_local@127.0.0.1:55433/pricetracker
uv run alembic upgrade head && uv run alembic check
```

## Evolving the schema

1. Update models in `backend/src/pricetracker/models/`.
2. Run `uv run alembic revision --autogenerate -m "description"` with the development database at head.
3. Review generated types, defaults for required columns in populated tables and indexes. Test
   upgrade/downgrade on PostgreSQL and SQLite, then run `alembic check`.
4. Back up before applying to real data (`make backup`). Compose's `migrate` job applies pending
   migrations before the API starts.

## Length support — revision 0002, 2026-10-02

Existing v1 installations need `upgrade head` before using quantities in metres. Compose's
`migrate` job applies it when starting the updated version. Per-metre comparison lives in the
product's JSON rules and needs no extra column. Observed unit prices retain four decimal places.

The disposable SQLite check started from `0001` with data: upgrade preserved the catalog record
and allowed `m`; invalid units were rejected; downgrade with metre-based data was blocked. After
removing/converting that data, downgrade and another upgrade passed. This revision was not applied
to a real database or verified on PostgreSQL in that round.

Do not downgrade while metre-based data exists: the migration fails explicitly to preserve it.
