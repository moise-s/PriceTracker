# Contributing to PriceTracker

[Português](CONTRIBUTING.pt-BR.md)

PriceTracker is licensed under MIT. Contributions to usability, documentation, accessibility
and integrations for other regions are welcome. Read the [architecture](docs/architecture.md),
[decisions](docs/decisions.md) and [source coverage](docs/markets.en.md) before changing price behavior.

## Local development

Install Python 3.13+, uv, Node 22.12+ (or a later version supported by the installed Vite), npm,
Docker with Compose v2 and make. Run from the repository root:

```bash
make bootstrap
make dev-db
make dev-init
make dev-setup-code
```

Then run `make api`, `make worker` and `make web` in separate terminals. Optionally run
`make scheduler` for recurring checks. Open **http://localhost:5173** and create the administrator
with the generated setup code. Development targets explicitly set the database, environment and
origin so they do not accidentally inherit production settings from `.env`.

`make dev-db` creates a disposable PostgreSQL container named `pricetracker-dev-pg` on port 55433.
If it already exists, start it with `docker start pricetracker-dev-pg` instead of creating it again.
Do not run tests against your personal database: the PostgreSQL suite recreates the schema.

```bash
make lint
make typecheck
make test
make openapi       # When the API contract changes; updates both generated files
make e2e           # Installed Chrome; fixture-backed backend, no live market traffic
```

`make check` also requires gitleaks. Live tests are opt-in: `make test-live` makes requests to real
websites. See [tests and fixtures](docs/testing.md). Include check results and reproduction steps
with your change. Never include `.env`, databases, dumps, personal images, cookies, tokens or
credentials in a contribution.

## Adding a market integration

Before writing an adapter, try **Administration → Markets → Add new market**. If the chain publishes
a product with a single public BRL offer and a usable sitemap, the generic collector may support it
without dedicated code. See the [contract, coverage and limits](docs/markets.en.md). Follow the steps
below when the source needs a region, specific promotions or another format.

A dedicated integration needs implementation and evidence before it is offered in the UI. Do not
copy another chain's adapter assuming it uses the same platform or identifiers.

1. Identify the official public source, access rules and `robots.txt`. Document how prices depend
   on postal code, branch or seller, whether coverage is partial and which promotions are usable.
   Do not bypass access blocks, required login or CAPTCHAs.
2. Implement `MarketAdapter` in `backend/src/pricetracker/adapters/<chain>.py`. It receives
   `AdapterContext` and `SearchQuery`, and returns `SearchOutcome` containing `Listing` objects.
   Use `PoliteClient`, `DocumentCache`, explicit allowed domains and `Decimal` for money.
3. Keep extraction separate from equivalence: adapters return candidates; the domain decides
   whether they match the product. Preserve regular, promotional and loyalty prices, package/unit
   measures, stock, URL and identifier. Never fabricate prices, regions or missing products.
4. Register it in `adapters/registry.py`; add the chain to `MARKETS` in `seed/__init__.py` and
   verified branches to `seed/stores.json`. Use a stable slug; technical domains/URLs for built-in
   integrations remain owned by code.
5. Define region fields and coverage notes in `services/markets.py` (`CONTEXTS`, `PRICE_NOTES`,
   `save_store`). The administrator UI supports postal code/seller, numeric identifiers and shared
   prices. For a different context, extend schemas, forms and validation together; do not expose
   arbitrary HTTP configuration or URLs in the branch form.
6. Capture sanitized fixtures in `tests/fixtures/<chain>/`. Add contract tests for found/missing
   products, out-of-stock/no-price cases, package/weight measures, promotions, invalid contexts
   and two regions with different prices where applicable. Use fake transports to check domains,
   limits and robots compliance without external traffic.
7. Test the worker, account isolation, comparison and administration. Update the API contract with
   `make openapi` if needed. Names/colors and loyalty prices come from API data; check the new
   identity in charts and dark mode.
8. Update `docs/markets.en.md` and its Portuguese companion, in-app help, the
   [readiness matrix](docs/sources/readiness-matrix.md) and E2E scenarios/fakes. State limitations
   and distinguish deterministic tests from authorized live checks.

A branch can be configured without changing code when its chain is integrated and its price
context is supported. To change the region of a branch with recorded runs, create another branch
and preserve the old one.

## Language conventions

- Use English for new identifiers, comments, docstrings and primary contributor/technical docs.
- Keep Portuguese documentation available through linked `.pt-BR.md` companions. User guides
  currently use `.en.md` for English and the unsuffixed file for Portuguese; maintain both when
  changing their instructions.
- Translate user-facing UI text through `web/src/lib/i18n.ts` and `translations.ts`. Existing
  Portuguese message IDs are stable keys; preserve them and add the English translation.
- Keep store names, listing titles and Brazilian product search/matching terms in their source
  language. Translating those terms changes search behavior. Preserve established API fields,
  routes and status codes rather than renaming them as part of a documentation translation.
- Keep test dates, results and coverage limitations accurate in both languages. Translating a
  report does not mean its tests were rerun.

## Future work

See the [backlog](docs/backlog.md). Priorities for a wider audience include manual prices for
unsupported chains, import/export, regional branch packages and configurable currency/timezones.
These are future improvements. The UI already supports Portuguese and English; keep its
translation catalog up to date.
