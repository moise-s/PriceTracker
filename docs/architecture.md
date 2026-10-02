# PriceTracker v1 architecture

[Português](architecture.pt-BR.md)

PriceTracker answers a household question: **where does the weekly grocery shop cost less when
travel is included?** Coverage, freshness and confidence remain explicit. v1 is a complete rebuild;
the v0 prototype is archived under `legacy/v0/`, and its old SQLite database is not imported or
supported by v1.

## Modular monolith with a dedicated worker

```text
Browser (Portuguese/English PWA: React + TypeScript + Vite)
   │  http://localhost:8090 (loopback only)
   ▼
web  (Caddy: static SPA + /api proxy → api, CSP and security headers)
   │
   ▼
api  (FastAPI, Pydantic, SQLAlchemy) ───┐
worker (asynchronous collection) ──────┼──► db (PostgreSQL 17: data + durable queue)
scheduler (recurrences → queue) ───────┘     app_data volume (uploaded images)
   │
   └─► market adapters ──► supermarket websites (robots, allowed domains, polite pacing)
       └─► LLM provider (optional fallback; strict JSON schema; never required)
```

| Layer | Package | Responsibility |
| --- | --- | --- |
| API | `pricetracker.api` | Versioned REST (`/api/v1`), OpenAPI, authentication/CSRF and user authorization |
| Services | `pricetracker.services` | Use cases: accounts, catalog, lists, runs, comparison, history, alerts and administration |
| Domain | `pricetracker.domain` | Pure logic: money, units, matching, baskets, travel, freshness and outliers |
| Adapters | `pricetracker.adapters` | Source-specific adapters and a generic public adapter behind one contract; polite HTTP client |
| LLM | `pricetracker.llm` | Interchangeable providers (Groq, OpenAI, OpenAI-compatible), used only as fallback |
| Geography | `pricetracker.geo` | Interchangeable geocoding/routing (manual, optional Nominatim/OSRM, estimate) and cache |
| Jobs | `pricetracker.worker`, `pricetracker.scheduler` | PostgreSQL queue with transactional claims (`FOR UPDATE SKIP LOCKED`) |
| Persistence | `pricetracker.db`, `pricetracker.models`, `migrations/` | SQLAlchemy 2 models and Alembic migrations for the new schema |
| Web | `web/` | React SPA consuming an OpenAPI-generated typed client |

## Price-check flow

1. A user requests a check, or the scheduler queues a recurrence with an idempotency key
   `schedule:<id>:<occurrence>`. The API creates a `run` and one target per product × store.
2. The worker claims the run (`UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED)`), maintains
   a heartbeat and processes targets with bounded concurrency. Targets sharing a price context
   (for example, Bistek stores with one reference price) share a single query.
3. Each target goes through adapter → deterministic listings → `MatchSpec` → best comparable
   unit price. Rules include search terms, required groups, exclusions, brand, size tolerance
   and whether the main product appears in the first three title words. An optional LLM may
   extract items from a sanitized excerpt when the adapter requests it; every returned value
   must occur in that excerpt. The generic `public_jsonld` adapter does not request this fallback.
4. Each target ends with one status: `found`, `not_found`, `unavailable`, `no_price`, `blocked`,
   `timeout`, `adapter_error`, `needs_llm` or `cancelled`. A run is `success` without failures,
   `partial` with some failures, `failed` without legitimate results, or `cancelled` on request.
5. Observations record extraction method (`api`, `json_ld`, `embedded_state`, `dom`, `llm`),
   confidence, adapter version, URL, branch, timestamp, sanitized raw payload and outlier review.
6. When the run finishes, the user's price alerts are checked against its observations.
7. A stopped worker returns the run to the queue without losing completed targets. If it dies,
   the scheduler/worker recovers runs whose heartbeat has expired.

Generic market onboarding validates a public Product/Offer and sitemap again before saving the
source configuration. It does not generate code or use an LLM. See [market sources](markets.en.md).

## Comparison

Three views use the latest observation for each product × store:

- **Common basket:** items found in every store; the lowest basket total wins.
- **By market (coverage):** each store total includes its item count. Incomplete baskets are marked
  as non-comparable and do not win simply because they omit products.
- **Budget plan:** prioritize coverage, then effective cost (products + travel), with up to N stops
  (default 2, maximum 3) and an exact home → stores → home route. Splitting requires savings of
  at least R$5.

Travel cost is `distance ÷ km/l × R$/l + tolls`, with values and formula shown in the UI. Distance
uses optional self-hosted OSRM or the estimate `haversine × 1.35`. Prices older than N days
(default 7) stay in history but require explicit consent to enter the recommendation. Outliers
are flagged for review and excluded. Empty cells explain the last check's result. Confidence
(high/medium/low) considers coverage, authorized stale prices, AI use, estimated weights and travel.

For double-ply toilet paper, `comparison_unit=m` permits different pack sizes with verified total
length. Selection uses price per metre; basket costs round up to whole packs. Unknown total lengths
are excluded. See the [user guide](user-guide.en.md#double-ply-toilet-paper-lowest-price-per-metre).

## Security and privacy

- Local accounts: Argon2id, opaque sessions stored as hashes, `HttpOnly`/`Secure`/`SameSite=Lax`
  cookies, double-submit CSRF and `Origin` checks, login rate limits and recovery codes instead of
  email. The first administrator needs a server-generated setup code.
- User isolation: user-owned records include `user_id`, and services filter by it. Administrators
  curate the global catalog, markets and branches.
- Secrets come from files (`./secrets`, Docker secrets or `*_FILE`), not the frontend, logs or Git.
  Structured JSON logs redact keys, tokens, cookies and passwords. Administrator-configured API
  keys are stored encrypted; environment/file-backed provider secrets remain outside the database.
- Uploaded images are validated and re-encoded as WebP; user-uploaded SVG is refused. URL imports
  accept public IP destinations only and revalidate redirects against SSRF.
- Administrator-supplied market sources require public HTTPS destinations. Each connection
  validates DNS results and pins the allowed IP while keeping the original Host/SNI.

## Local installation

Docker Compose runs `db`, one-shot `migrate`, `api`, `worker`, `scheduler` and `web`. Images are
version-pinned (PostgreSQL by digest), with non-root users, read-only filesystems,
`no-new-privileges`, health checks, CPU/memory limits and named volumes. Only `127.0.0.1:8090`
is published. Server deployment and Tailscale Serve are outside this delivery's scope; see
[local operations](operations.md).

## Quality

- Backend unit, contract (sanitized fixtures) and integration tests run on SQLite and optionally
  PostgreSQL (`make test-pg`), including concurrent queue tests. Live smoke tests are opt-in
  (`make test-live`).
- Vitest and Playwright test the web against a deterministic backend (`backend/tests/e2e_harness.py`)
  that replays fixtures without external market traffic.
- See [test evidence](testing.md) and [architecture decisions](decisions.md).
