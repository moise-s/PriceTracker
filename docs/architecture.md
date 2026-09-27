# PriceTracker v1 — architecture

PriceTracker helps a household decide **where the weekly shopping is cheapest
once travel is included**, with honest coverage, freshness and confidence. v1 is
a full rebuild; the v0 prototype is archived under `legacy/v0/` (see
`legacy/README.md`). The v0 SQLite database is discontinued and never imported.

## Shape: a modular monolith with a dedicated worker

```
Browser (pt-BR PWA, React + TypeScript + Vite)
   │  HTTPS via Tailscale Serve (tailnet only)
   ▼
web  (Caddy: static SPA + reverse proxy /api → api)       127.0.0.1:8090 on the host
   │
   ▼
api  (FastAPI, Pydantic, SQLAlchemy)  ──┐
worker (async collection runs)  ────────┼──► db (PostgreSQL 17, durable queue + data)
scheduler (recurring runs → queue) ─────┘      uploads volume (images)
   │
   └─► market adapters ──► supermarket sites (robots-checked, rate-limited, allowlisted)
       └─► LLM provider (optional fallback, strict JSON schema, never required)
```

| Layer | Package | Responsibility |
| --- | --- | --- |
| API | `pricetracker.api` | Versioned REST (`/api/v1`), OpenAPI, auth/CSRF, per-user authorization |
| Services | `pricetracker.services` | Use cases: accounts, catalog, lists, runs, comparison, history, admin |
| Domain | `pricetracker.domain` | Pure logic: money, units, matching, basket comparison, travel cost, freshness, outliers |
| Adapters | `pricetracker.adapters` | One adapter per market behind a common contract; polite HTTP client |
| LLM | `pricetracker.llm` | Swappable providers (Groq, OpenAI, OpenAI-compatible) used only as fallback |
| Geo | `pricetracker.geo` | Swappable geocoding/routing (manual, Nominatim, OSRM, straight-line estimate) + cache |
| Jobs | `pricetracker.worker`, `pricetracker.scheduler` | PostgreSQL queue with transactional claiming (`FOR UPDATE SKIP LOCKED`) |
| Persistence | `pricetracker.db`, `pricetracker.models`, `migrations/` | SQLAlchemy 2 models and Alembic migrations (new schema only) |
| Web | `web/` | React SPA consuming a typed client generated from OpenAPI |

## Key decisions (details in `docs/decisions/`)

1. **Deterministic first.** Each adapter prefers the site's public structured data
   (JSON APIs, JSON-LD, embedded state), then deterministic DOM parsing. The LLM
   only extracts from or ranks a small, sanitized snippet of data that was already
   collected. Every value it returns must be traceable to that snippet, and hard
   matching rules (size, brand, exclusions) are always re-applied afterwards.
2. **Robots, allowlists and politeness are enforced in code.** The shared HTTP client
   refuses URLs disallowed by the host's `robots.txt` (RFC 9309 matching), validates
   every redirect against the market's domain allowlist, limits concurrency per
   domain, and applies timeouts, retries with backoff and jitter, and a circuit
   breaker. When a source blocks legitimate automation, the target fails with a
   typed status (`blocked`) and no data is fabricated.
3. **Money is `Decimal`/`NUMERIC`.** Prices are stored as `NUMERIC(12,2)` and unit
   prices as `NUMERIC(14,4)`. Floats never touch money.
4. **Honest runs.** Each run target ends in exactly one state: `found`,
   `not_found`, `unavailable`, `no_price`, `blocked`, `timeout`, `adapter_error`,
   `needs_llm` or `cancelled`. A run is `success` only when no target failed,
   `partial` when some failed, `failed` when none produced a legitimate outcome,
   and `cancelled` on request.
5. **Three comparison views.** *Common basket* compares only the items found in
   every selected store. *Coverage* shows totals per store with explicit X-of-Y
   coverage and declares no unfair winner. *Economic plan* considers one store or
   a split across at most N stops, including travel cost. Stale prices (older than
   7 days by default, configurable) and flagged outliers never win silently.
6. **Multi-tenant by construction.** Every user-owned row carries `user_id`, and
   services always filter by the authenticated user. The global catalog, markets
   and stores are curated by administrators.
7. **Local accounts only.** Passwords are hashed with Argon2id. Sessions are opaque
   tokens stored hashed, sent in `HttpOnly`, `Secure`, `SameSite=Lax` cookies. CSRF
   uses a double-submit token plus an Origin check. Logins are rate-limited.
   Recovery codes and admin password resets replace e-mail. First-run admin
   creation requires a one-time setup code generated on the server via the CLI.
8. **PostgreSQL in production.** SQLite is supported only for simple
   development and tests. The job queue is the `runs`/`run_targets` tables: no Redis
   and no `BackgroundTasks`.
9. **Private homeserver deployment.** Docker Compose runs `web`, `api`, `worker`,
   `scheduler`, `db` and a one-shot `migrate` service, with pinned images, health
   checks, resource limits and named volumes. `web` binds to loopback only and is
   published on the tailnet with Tailscale Serve (HTTPS). Nothing is exposed to the
   public internet.

## Incremental implementation sequence

1. Foundation: settings validated at startup, structured logging with redaction,
   database, models and the first migration, auth (setup, login, sessions, CSRF),
   seed catalog, markets and stores.
2. Catalog, personal products, images (upload and validated URL), lists.
3. Collection core: polite HTTP client, robots, allowlist, adapter contract,
   deterministic matcher, run queue, worker, CLI with JSON output and exit codes.
4. The four market adapters with sanitized fixtures and contract tests, live
   smoke tests (opt-in) and a readiness matrix.
5. Comparison engine (three views), travel cost, freshness, outliers, history.
6. Web UI for the main flow: onboarding, list, markets, run progress,
   recommendation, history, profile (address and vehicle).
7. Deployment: Dockerfiles, Compose, backup/restore scripts, Tailscale Serve docs,
   restart and restore drills; E2E scenarios with screenshots.
8. P1: schedules, alerts, admin health, LLM provider management and testing, PWA,
   in-store mode.
