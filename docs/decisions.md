# Decisions and trade-offs

[Português](decisions.pt-BR.md)

Short architecture decision records: context → decision → consequences. ADR-01 through ADR-10
were recorded on 2026-09-27; regional onboarding and language/length support were added on 2026-10-02.

## ADR-01 — Modular monolith with a worker and PostgreSQL queue

- **Context:** collection takes minutes, must survive restarts and must not duplicate results.
  A household installation should remain lightweight.
- **Decision:** FastAPI, services and a pure domain in one package; separate worker/scheduler
  processes. `runs`/`run_targets` provide a queue with `FOR UPDATE SKIP LOCKED` claims, heartbeats,
  orphan-run recovery and return to the queue at shutdown. Recurrences have one idempotency key
  per occurrence.
- **Consequences:** no Redis/Celery; one database to back up. Limited throughput suits a household.
  SQLite serializes writes and serves development/tests only.

## ADR-02 — Deterministic collection first, validated LLM fallback

- **Context:** the prototype depended on an LLM and a discontinued model. Models can fabricate prices.
- **Decision:** adapters prefer public structured data (JSON APIs, JSON-LD, embedded page state),
  then deterministic DOM extraction. An LLM receives only a small sanitized excerpt treated as
  untrusted data, with a strict JSON schema. Every returned value must occur in that excerpt;
  matching rules run again. Groq `qwen/qwen3.8-27b` was the configured default, verified with
  `pricetracker llm check`. OpenAI requires a platform `OPENAI_API_KEY`; a ChatGPT subscription
  does not supply API credits. Calls have a per-run budget and a content-hash cache.
- **Consequences:** live runs on 2026-09-27 used **0 LLM calls**. Without a key, only targets needing
  AI become `needs_llm`; the rest of the run continues.

## ADR-03 — Respect sources without bypassing protections

- **Decision:** a shared HTTP client implements `robots.txt` (RFC 9309), allowed-domain checks on
  redirects, per-host concurrency/pacing, retries with backoff/jitter, circuit breakers, an
  identifiable User-Agent and anti-bot challenge detection that produces `blocked`.
- **Consequences:** Bistek uses sitemaps because robots forbids search/API access; Fort avoids query
  strings. Imperatriz's full iFood catalog stays excluded (ADR-07).

## ADR-04 — Decimal/NUMERIC money; list quantity differs from package size

- **Decision:** prices use `NUMERIC(12,2)`, unit prices `NUMERIC(14,4)` and quantities
  `NUMERIC(12,3)`. The API sends money as decimal strings. Lists record how much to buy (2 packs,
  1.5 kg, 12 items); package size belongs to the offer. Weight-based items convert estimated packs
  to price per kg. Quantity discounts apply only when the minimum is met; loyalty prices apply
  only when the user enables that club.
- **Consequences:** money calculations do not use floats. Line costs are explainable, for example
  2 × R$6.79.

## ADR-05 — Three comparison views and honest recommendations

- **Decision:** common basket (intersection), per-store coverage and a budget plan prioritizing
  coverage, including travel and limiting stops. Splitting requires at least R$5 savings. Stale
  prices (default 7 days) require consent and reduce confidence; confidence is low when all used
  prices are stale. Outliers remain under review. Empty cells show the latest search outcome.
- **Consequences:** the recommendation may say there are insufficient prices rather than offer
  an unsupported winner.

## ADR-06 — Local accounts without email

- **Decision:** Argon2id, opaque sessions hashed in the database, `HttpOnly`/`Secure`/`Lax` cookies,
  double-submit CSRF plus Origin checks, HMAC-based user/client rate limits, 10 single-use recovery
  codes and administrator resets requiring a password change. The first administrator needs a
  one-time server-generated code (`pricetracker setup-code`). Self-registration is disabled after
  bootstrap; an administrator can enable it.
- **Consequences:** no SMTP dependency. Losing both password and recovery codes requires an admin.

## ADR-07 — Imperatriz uses only the official Super Clube source

- **Context:** Imperatriz's website does not publish catalog prices. Its full catalog is on iFood,
  protected by PerimeterX and terms of use.
- **Decision:** use only the official public Super Clube offers API, keep regular/loyalty prices
  separate and declare partial coverage in the UI.
- **Consequences:** items outside current offers appear as not found. **A user decision remains
  pending**; see the [source-readiness matrix](sources/readiness-matrix.md).

## ADR-08 — Geography without recurring public-service dependencies

- **Decision:** user-provided coordinates or browser geolocation. Nominatim is an explicit opt-in
  with configured contact and cache, never autocomplete. Routing uses optional self-hosted OSRM
  or `haversine × 1.35`, with the formula visible.
- **Consequences:** no external dependency by default. Estimates can be wrong around bridges or
  mountains, so the UI identifies the method; OSRM provides the optional more precise route.

## ADR-09 — Local installation only

- **Context:** server deployment was explicitly excluded from this delivery.
- **Decision:** local Docker Compose exposed only at `127.0.0.1:8090`, file-based secrets, tested
  backups/restoration. Tailscale Serve, systemd and server deployment remain outside scope.
- **Consequences:** another household device needs additional HTTPS/proxy configuration, tracked
  in the backlog.

## ADR-10 — E2E tests against a deterministic backend

- **Decision:** `backend/tests/e2e_harness.py` runs the real API with disposable SQLite and an
  in-process worker replaying sanitized fixtures. A control API, mounted only in the harness,
  resets state and injects market failures. Playwright uses the production build (`vite preview`).
- **Consequences:** the initial eight desktop/mobile scenarios ran in about a minute without
  external traffic or live-site instability. Real-source validation uses opt-in live smoke tests
  and stack runs.

## ADR-11 — Regional management with explicit integrations

- **Context:** users in other cities needed to change the initial branch data and lacked UI branch
  management. A street address and an online pricing region are different concepts.
- **Decision:** administrators manage integrated chains and branches; users filter by region and
  maintain personal selections. Adapter-specific contexts validate postal code/seller, official
  IDs or shared reference prices. Built-in integration domains, sites and collection code remain
  code-owned. New sources follow ADR-12 validation.
- **Persistence:** seed preserves administrator-editable market fields and branches with `admin`
  origin. Deactivation preserves history and excludes new selections/comparisons. Explicit
  unavailable IDs are rejected in retries and new schedules. Existing runs may finish.
- **History:** changing a pricing region after a recorded run requires another branch. Old
  observations are not reinterpreted as prices from the new region.
- **Limits:** Portuguese/English UI, BRL and Brazilian addresses. Sources outside ADR-12 need
  adapters with fixtures and verifiable context. Manual/imported prices, other currencies and
  international address formats remain future work.

## ADR-12 — New-chain wizard with a verified public source

- **Context:** managing branches of four chains does not serve regions where none exists. A name
  and website alone do not establish a usable price source.
- **Decision:** administrators test HTTPS site, public product and sitemap. A source with JSON-LD
  `Product` and a single explicit BRL `Offer` can be registered with its first store in one
  transaction. Validation runs again at registration; client-supplied previews are not evidence.
  The UI can revalidate/update the same-host index for all branches without changing availability.
  Another hostname requires another chain to preserve historical origin. Built-in integrations
  retain their region/promotion contracts.
- **Coverage:** anonymous online reference shared across branches, with explicit notice and
  confirmation. City/address does not configure the site's delivery region. Price ranges, multiple
  offers, quantity/customer conditions, expired offers and other currencies are refused.
- **Collection:** up to 6 sitemap documents/5,000 pages, 24-hour cache and up to 6 discovered
  candidates per product. Each listing still passes equivalence rules. This adapter uses no
  JavaScript, login, postal-code setup or AI fallback.
- **Network:** HTTPS, configured same origin, robots and pacing. Every connection checks all DNS
  addresses are public and pins the validated IP with original Host/SNI. Private addresses,
  credentials and alternative ports are refused. Documents are limited to 4 MB; probes to 35 s.
- **UX:** any catalog product can become a private editable copy. Markets shows product/store
  counts and an action that saves the selection and starts a run. Advanced options/history remain
  separately available.

## ADR-13 — Browser language and per-metre comparison, 2026-10-02

- **Context:** product creation left users unsure whether they were still editing. Toilet-paper
  packs of different sizes needed an equivalent comparison.
- **Decision:** saving a new product returns to the list, where the user adds it. UI language is
  chosen per browser without translating user/source names or search terms. README, onboarding,
  usage and source guides have English versions. Currency remains BRL and the installation's
  timezone is unchanged.
- **Length:** `m` means total metres. Double-ply rules require that characteristic and allow
  different pack sizes; unverifiable length is refused. Selection uses price per metre with four
  decimal places. The basket buys enough whole packs and explains excess quantity; alerts still
  use price per pack.
- **Flow:** Home provides store selection. Update prices saves it, then opens list review → market
  confirmation → start search. History sorts every column both ways, with missing values last.
- **Persistence:** migration `0002` expands allowed units; downgrade refuses metre-based data to
  avoid silent loss. English UI does not automatically expand source coverage.
