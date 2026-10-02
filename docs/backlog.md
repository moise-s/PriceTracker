# Remaining risks and prioritized backlog

[Português](backlog.pt-BR.md)

## Risks

| Risk | Impact | Current mitigation | Next step |
| --- | --- | --- | --- |
| **Partial Imperatriz coverage** (Super Clube offers only) | Non-promotional items do not appear | Missing status and explicit coverage note; no incomplete-basket winner | User decision; see [readiness matrix](sources/readiness-matrix.md) |
| **One Bistek reference price** | Shelf prices may differ by branch | Explicit source note; one shared online query | Reassess if the site exposes per-store prices |
| **Website changes** (layout, APIs, store cookies) | Adapter stops finding products | Typed errors (`adapter_error`, `store_context_error`, `no_prices_extracted`), health panel, fixtures/contract tests and live smoke tests | Weekly opt-in live checks; scheduled canary is future work |
| **Estimated distance** (`haversine × 1.35`) | Bridges/mountains can alter costs and a close result | Visible method/formula; optional OSRM | Document/automate a local SC routing service |
| **Manual geocoding** | Users enter coordinates or use browser location | Location button; optional cached Nominatim | Authorized postal-code lookup is future work |
| **LLM limits/model changes** | Optional fallback becomes unavailable | Deterministic extraction first; `llm check`; only affected targets fail | No urgent change |
| **Manual backups** | Disk failure can lose data | `make backup` and tested restore drill | Scheduled backups and retention |
| **Embedded-browser service workers** | Offline shell cache may be unavailable | App works without SW; normal browsers support registration | — |
| **Localhost-only access** | A phone cannot reach the host by its own localhost URL | Intentional local scope | HTTPS proxy/network access when requested |

## Priorities

### P1 — next

1. **Regions without an integrated source:** manual prices with date, branch and provenance,
   followed by CSV import/export. Apply the same freshness, units, isolation and equivalence rules.
2. **Imperatriz decision:** retain partial coverage, disable it or add an authorized source.
3. **Scheduled backups:** retention (for example, daily with seven copies) and failure alerts.
4. **Weekly source canary:** one product per market through the scheduler, feeding source health.
5. **Store-switch savings alert:** notify when the plan beats the usual store by a user-defined
   amount. Individual price-target alerts already exist.
6. **List duplication/recurring lists in the UI:** the API already supports `copy_from`.
7. **In-store mode:** mark purchased items on a phone; the API already exposes `checked`.

### P2 — later

- **Regional branch packages:** import validated branch data with preview, deduplication, context
  validation and preservation of local edits.
- **International expansion:** currency/address formats per installation and timezone per user,
  including schedules. The UI already supports Portuguese/English; sources currently use BRL and
  Brazilian contexts. Geocoding, matching and monetary comparison need review, beyond text translation.
- **Backend message localization:** some API-generated explanations, travel formulas and errors
  still originate in Portuguese. Keep their stable API fields/codes; extend localization separately
  from translating contributor documentation.
- **Shared households** with explicit member permissions.
- **CSV/JSON export** for lists, comparisons and history; shopping links per market.
- **Optional time cost** in R$/hour, visible in the plan.
- **Road routing by default** with local OSRM and more than three stops where useful.
- **History-based suggestions:** frequent items and accepted alternatives.
- **Server installation:** household server Compose, HTTPS access and remote backups.
- **Smaller backend image:** leaner multi-stage wheels; the historical image measured 432 MB.

## Delivered beyond P0

Schedules, common basket/coverage/budget-plan comparison, in-app price alerts, source health,
retry failed targets, safe provider checks, PWA, optimal splitting across up to three stores with
an exact route, historical median/minimum, outlier flags and per-store tolls.

Delivered on 2026-10-02: administrator chain/branch management, region/name filters, seed
preservation, in-app help and installation/usage/contribution guides; public JSON-LD/BRL + sitemap
onboarding, first-branch registration, private copies of every catalog product, direct start from
Markets and guided review from Home; Portuguese/English UI, sortable history and per-metre
comparison for double-ply toilet paper, including a standard catalog item.

Sources needing login, postal-code regions or different contracts still need dedicated adapters.
Manual price entry and full international coverage remain future work.
