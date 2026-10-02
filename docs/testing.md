# Tests and evidence

[Português](testing.pt-BR.md)

This document records checks by date. Historical live/PostgreSQL results do not imply those
checks were rerun with later changes. Documentation translations do not rerun application tests.

## Running checks

| Command | What it runs |
| --- | --- |
| `make test` | Backend pytest on SQLite and web Vitest |
| `make test-pg` | Backend suite on PostgreSQL, including concurrent queue tests; requires the disposable development database |
| `make test-live` | Opt-in live website smoke tests with polite, limited traffic |
| `make e2e` | Deterministic harness, production web build and Playwright scenarios |
| `make lint` / `make typecheck` | Ruff/oxlint and strict mypy/TypeScript |
| `make secrets-scan` | Gitleaks over Git history |
| `make smoke CREDENTIALS=…` | Complete live collection on the running Docker stack (`scripts/stack_smoke.py`) |

E2E uses installed Google Chrome without downloading a browser. To use Playwright Chromium,
run `npx playwright install chromium`, then `PLAYWRIGHT_CHANNEL=bundled make e2e`.

## Results on 2026-09-27

| Suite | Result |
| --- | --- |
| Backend SQLite | **133 passed**, 6 skipped (4 live, 2 PostgreSQL-only) |
| Backend PostgreSQL 17.10 | **135 passed**, 4 skipped (live) |
| Live smoke (`--live`) | **4 passed**, 22:27–22:29 UTC: package/weight/unit products at Angeloni, Bistek and Fort; Imperatriz offers |
| Web Vitest | **26 passed** |
| Playwright | **17 passed**: 8 scenarios × desktop (1280×900)/phone (390×844), plus the screen matrix |
| Lint/types | Ruff, strict mypy, oxlint and TypeScript passed |
| AI provider | Stack `pricetracker llm check`: Groq `qwen/qwen3.8-27b`, connection passed in 259 ms |
| Secrets | Gitleaks found no leaks in history |

## E2E scenarios

Tests use `backend/tests/e2e_harness.py`: real API, disposable SQLite, in-process worker and
sanitized fixtures, with no external source traffic. Step screenshots are attached to the
Playwright HTML report (`web/playwright-report/`).

| # | Scenario | Verified behavior |
| --- | --- | --- |
| 1 | Weekly shop | Setup code → recovery codes → onboarding → catalog list → store selection → completed run → recommendation with 4/4 coverage and a missing-travel-configuration notice |
| 2 | Missing item | Fuji apple unavailable in Fort's catalog; complete Angeloni basket wins, common basket excludes the missing item, Fort's 2/3 total is non-comparable |
| 3 | Travel changes the winner | Fort wins without travel (R$26.46 vs R$29.77); Angeloni wins with home near Beira Mar and Fort ~12 km away; fuel formula is visible |
| 4 | AI unavailable | Simulated Bistek layout failure without a key affects only its targets (`needs_llm`); Fort prices/comparison still work |
| 5 | Partial failure | Angeloni anti-bot challenge → partial run and blocked targets; retry after recovery preserves existing results and completes comparison |
| 6 | Isolation | A second account cannot access the first account's products, list, run or address; API/UI return 404 or empty results |
| 7 | Freshness | Ten-day-old prices are excluded until explicitly authorized; using them shows low confidence and a notice |
| 8 | Price alert | Product target → collection → R$6.79/pack notification, target badge and bell counter; marking read clears the counter |

## Screen matrix

`web/e2e/screens.spec.ts` opens 10 screens (Home, list, markets, run, comparison, history, product,
notifications, profile, administration) at **360, 390, 1280 and 1440 px**, plus three screens in
dark mode at 390/1280 px. It fails on horizontal overflow, content clipped at the screen edge or
serious/critical axe violations on the tested accessibility viewports (WCAG 2.1 A/AA).
Screenshots are stored under `docs/screenshots/`:

- `<width>/<screen>.jpg`, for example `390/onde-compensa.jpg` or `1280/inicio.jpg`.
- `dark/<screen>-<width>.jpg`.
- `readme/<preview>.<locale>.jpg`: compact English/Portuguese viewport captures.

## Live Docker stack evidence on 2026-09-27

| Evidence | Result |
| --- | --- |
| Complete collection, 10 items × 4 markets | `success`, 28 found, 11 not found, 1 unavailable, 100 s, 0 AI calls |
| Imperatriz promotional item | Found at Imperatriz (R$5.79) and Bistek (R$6.49), unavailable at Fort, not found at Angeloni |
| Restart during collection | Resumed without duplicate observations |
| Backup/restoration | Drill PASS and real restoration checked |

See the [per-source readiness matrix](sources/readiness-matrix.md).

## Regional management verification — 2026-10-02

The deterministic backend suite on `feat/rebuild-v1` passed **146 tests**, with **6 skipped**
(2 PostgreSQL-only, 4 live). Vitest passed **26**. Ruff, mypy, oxlint and TypeScript passed;
OpenAPI and generated types were refreshed.

The 16 original browser scenarios and 4 new regional scenarios passed on desktop/phone.
`web/e2e/market-management.spec.ts` covers branch creation/editing/deactivation in another state,
source-specific contexts, selection persistence across filters, help at 320 px, clipping/overflow
and axe. Reduced motion avoids measuring a partially transparent entry-animation frame.

Tests use real API endpoints with a disposable database and simulated sources. They do not prove
new postal-code/store-ID coverage on live websites. A fresh Docker installation was not tested.

## Product editing, direct start and new chains — 2026-10-02

- Backend: **177 passed**, 6 skipped (4 live, 2 PostgreSQL-only).
- Vitest: **26 passed**. Ruff/formatting, mypy, oxlint and TypeScript passed.
- Playwright: the preceding 20 scenarios and 6 new editing/direct-start/onboarding scenarios
  passed on desktop/phone. New flows were rechecked after source revalidation, including 320 px
  and dialog accessibility checks.
- Backend integration covers independent-chain registration and worker collection through
  comparison with mocked HTTP. It checks invalid origin/index, changed sources between preview
  and confirmation, permissions/CSRF, confirmation, duplicates and index updates across branches
  without changing domain/availability.
- Public transport checks cover private IPs, mixed/rebinding DNS, pinned IP with Host/SNI, document
  size and robots redirects. Sitemap tests cover document/page limits and caching; incompatible
  currencies, aggregate/multiple offers and conditions are refused.

The browser wizard mocks probe/registration responses. Backend integration exercises real
endpoints/transport with simulated public pages. It does not guarantee a specific real market's
compatibility or perform live collection/deployment.

## Language, metres and guided review — 2026-10-02

- Backend: **193 passed**, 6 skipped. Coverage includes roll/total-length parsing, per-metre
  matching, whole-pack costs, generic collection through comparison and data-preserving migrations.
- Vitest: **33 passed**, including language persistence, translation, formatting and history
  sorting. Ruff/formatting, strict mypy, oxlint and TypeScript passed.
- Playwright: **32 passed** (16 × desktop/phone), covering the preceding 26 plus language/creation,
  Home selection/guided review and every history column's ordering. Includes English help/wizard
  at 320 px and accessibility/overflow checks.
- Disposable databases and simulated sources. No live Pradão collection, new installation or
  PostgreSQL check in this round. Real prices/delivery coverage need source validation. The older
  screenshot matrix had not yet been regenerated at this stage.

### Toilet paper in the standard catalog

Added to Hygiene with a local illustration, per-metre comparison and a starting quantity of
120 m. Adding a catalog item respects its starting amount unless the user supplies another.
Integration covers both custom and standard-catalog products from list insertion through
collection/comparison without real HTTP traffic. Backend: **194 passed**, 6 skipped; changed-file
lint, formatting and types passed.

### Visual README update

Regenerated **46 full screenshots** (10 screens × four widths plus 6 dark-mode captures) with demo
data. The matrix passed at 360/390/1280/1440 px, including overflow, clipping and accessibility
checks on the covered viewports. Also generated 12 viewport previews (six per language) without
editing the full images. The gallery identifies prices as demonstration data.
The 32 usage scenarios and 33 Vitest tests passed again before publication.
