# Source-readiness matrix

[Português](readiness-matrix.pt-BR.md)

Last live verification: **2026-09-27**, using the local Docker/PostgreSQL stack and opt-in smoke
tests (`make test-live`). Table times use America/Sao_Paulo (BRT, UTC−3). These are historical
results, not a claim of current live availability.

An adapter is ready only after finding priced real products with different sale types (package,
weight and item) in an identified branch. Reaching the homepage is insufficient.

| Source | Final domain | Tested branch | Deterministic method | Smoke products | Date/time | Result | LLM | Limits | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Angeloni** | `super.angeloni.com.br` | Beira Mar, Florianópolis (CEP 88025-202, seller `superangeloni14`) | Public VTEX Intelligent Search API with `region-id` from `/api/checkout/pub/regions`, verified seller; Master Data (`PR`) quantity offers | White rice 1 kg (pack), Alcatra/kg (weight), eggs 30 (items); 10-item basket | 2026-09-27 19:27–19:29 smoke; 19:19–19:21 basket | Smoke 3/3 found. Basket: 9 found, 1 **unavailable** (Café Três Corações Gourmet Sul de Minas, out of stock) | Not used | Online branch prices may differ from shelves. Depends on postal-code → VTEX-region mapping; seller changes fail with `adapter_error` rather than silently switching stores | **Ready** |
| **Bistek** | `www.bistek.com.br` | Costeira do Pirajubaé, Florianópolis (website reference price) | `/sitemap/product-{n}.xml` discovers URLs; `/<slug>/p` exposes embedded `__STATE__`; ETag revalidation. Robots forbids `/busca` and `/api`, so search endpoints are unused | Rice 1 kg, Alcatra/kg, eggs 30; 10-item basket | 2026-09-27 19:27–19:29 smoke; 19:19–19:21 basket | Smoke 3/3. Basket: **10/10 found** | Not used | No branch selection on site: all branches share the Florianópolis/SC reference, explicitly shown in the UI. Discovery depends on current sitemaps | **Ready**, shared-price limitation |
| **Fort Atacadista** | `fortatacadista.com.br` | Kobrasol, São José (store `1638`) | Sitemap + `/produtos/<id>/<slug>`; selected-store cookie `st_334` (`userSelected=true`); reads `APOLLO_STATE` and verifies the returned store matches the requested store | Rice 1 kg, Alcatra/kg, eggs 30; 10-item basket | 2026-09-27 19:27–19:29 smoke; 19:19–19:21 basket | Smoke 3/3. Basket: 9 found, 1 **not found** (Fuji apple, not sold online in that store) | Not used | Online store prices. Quantity offers apply only when the list meets the minimum. Robots blocks URLs containing `?`; no query strings are used | **Ready** |
| **Imperatriz** | `clube.superimperatriz.com.br` (official Super Clube site), public API at `api.zoombox.com.br` / `…execute-api.us-east-1.amazonaws.com` | Mauro Ramos, Florianópolis (store `9`); Presidente Kennedy, São José (store `16`) | Super Clube JSON offers API; public bootstrap token kept in memory. Regular/loyalty prices stored separately | 10-item basket; promotional item: Leite condensado Tirol 395 g | 2026-09-27 19:27–19:29 smoke; 19:19–19:21 basket; 19:33 promotional item | API accessible: **282 current offers**, Mauro Ramos (2 requests). Basket: **10 not found**, none on promotion. Promotional item found, regular R$5.79 / loyalty R$5.49 | Not used | **Partial coverage by source design:** current club promotions only. Full iFood catalog is deliberately excluded because of anti-bot protection/terms. Loyalty prices require profile consent | **Degraded; user decision pending** |

## Reproducible evidence

- **Complete basket, four markets/40 targets:** run `8c3fe775`, `success`, 28 found, 11 not found,
  1 unavailable, 100 s, 0 LLM calls. Reproduce with
  `make smoke CREDENTIALS=secrets/local-admin-credentials.txt` on the running stack.
- **Imperatriz promotional item, four markets:** run `5365b85b`; Imperatriz found (R$5.79,
  loyalty R$5.49), Bistek found (R$6.49), Fort unavailable (regular R$5.39, promo R$4.98,
  out of stock), Angeloni not found. Distinct outcomes coexist within one run.
- **Live smoke:** `make test-live`, 4 passed on 2026-09-27, 22:27:38–22:29:17 UTC. Covers three sale
  types at Angeloni/Bistek/Fort and availability of Imperatriz offers.
- **Restart during collection:** run `5f7acf67` stopped at 19/40 targets using `docker compose down`.
  Restart resumed attempt 2 with 21 pending targets; finished `success` with 29 observations and
  no duplicates.
- Sanitized fixtures captured on 2026-09-27 support deterministic contract tests under
  `backend/tests/fixtures/`.

## Polite access for every source

RFC 9309 robots matching (longest rule wins), allowed domains checked on redirects, at most two
connections per host, minimum request intervals, timeouts, retry backoff/jitter, per-host circuit
breakers and an identifiable User-Agent. No CAPTCHA, required-login or anti-bot bypass.
Cloudflare/Incapsula/PerimeterX challenges become `blocked`, never fabricated data.

## Pending Imperatriz decision

Live collection works, but only covers current Super Clube promotions. Options:

1. **Retain the official source:** recommended within its declared partial coverage. Missing items
   remain missing; incomplete baskets do not receive an unfair win.
2. **Disable Imperatriz** for weekly comparisons and use it only for promotional alerts.
3. **Seek an additional authorized feed/API**, for example from the chain. Anti-bot-protected
   iFood/aggregators remain excluded.

Proven live collection is complete for Angeloni, Bistek and Fort, and partial for Imperatriz.
Generic new-chain onboarding is documented in [market sources](../markets.en.md); this historical
matrix does not assert live compatibility for Pradão or other wizard-added chains.
