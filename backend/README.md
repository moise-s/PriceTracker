# PriceTracker — backend

[Português](README.pt-BR.md)

The FastAPI API, worker, scheduler and CLI share one Python package (`pricetracker`), managed with uv.

```bash
uv sync
uv run pricetracker --help            # serve, worker, scheduler, run, db upgrade, db-init, seed,
                                      # setup-code, user, llm check, health, openapi
uv run pytest -q                      # Deterministic suite (SQLite)
PRICETRACKER_TEST_DATABASE_URL=postgresql+psycopg://… uv run pytest -q   # Same suite on PostgreSQL
uv run pytest tests/live --live -q    # Live website smoke tests (opt-in)
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

## Structure

| Path | Contents |
| --- | --- |
| `src/pricetracker/api/` | `/api/v1` routes, Pydantic schemas and dependencies (sessions, CSRF, roles) |
| `src/pricetracker/services/` | Use cases: accounts, catalog, lists, runs, comparison, history, alerts and administration |
| `src/pricetracker/domain/` | Pure logic: money, units, text, matching, pricing, travel, quality and comparison |
| `src/pricetracker/adapters/` | Polite HTTP client, robots, sitemaps, four built-in adapters and the generic `public_jsonld` adapter |
| `src/pricetracker/llm/` | Providers (Groq, OpenAI, compatible APIs) and extraction validation against source content |
| `src/pricetracker/worker/`, `scheduler/` | PostgreSQL queue, run executor and recurring checks |
| `src/pricetracker/seed/` | Markets, initial branches and catalog with original illustrations |
| `migrations/` | Alembic: initial v1 schema (`0001`) and metre-based quantities (`0002`) |
| `tests/` | `unit/`, `contract/` (sanitized fixtures), `integration/`, `live/` and `e2e_harness.py` |

Configure `PRICETRACKER_*` environment variables (or `*_FILE` for secrets); see
`src/pricetracker/settings.py` and `../.env.example`.

Market/branch management lives in `services/markets.py`, schemas `MarketPatch`/`StoreAdminIn`
and administrator routes: `GET /api/v1/admin/markets`, `PATCH .../{market_id}`,
`POST .../{market_id}/stores` and `PUT .../{market_id}/stores/{store_id}`. New generic chains use
`POST /api/v1/admin/markets/probe` followed by `POST /api/v1/admin/markets`. All require an
administrator; mutations require CSRF protection. Deactivation preserves history. Price regions
already used in runs cannot be reassigned.

See [market sources](../docs/markets.en.md), [architecture](../docs/architecture.md) and
[contributing a new adapter](../CONTRIBUTING.md).
