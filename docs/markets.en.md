# Markets, branches and how onboarding works

[Português](markets.md) · [README](../README.md)

A **market chain** owns a collection integration (adapter). A **branch** belongs to that chain and
carries its price context. A **personal selection** determines which stores enter one account's
search and comparison. Administrators manage chains/branches; users choose their own stores.
English UI support does not change BRL currency, Brazilian CEP/UF fields or source coverage.

## Registering an unrelated chain, such as Pradão

1. Open **Administration → Markets → Add new market**.
2. Enter the actual shopping website and a product page you can open without login and see a price.
   Use the product's final domain; corporate homepages and category/search pages are insufficient.
3. Click **Test website**. If the index is not found automatically, supply the XML product sitemap
   on that same domain. It may be listed in the website's `robots.txt`.
4. Review the returned sample name, price, number of indexed pages and price scope. Enter the chain
   name/color and first store's name, city and state. Confirm you checked the sample price on site.
5. **Register and enable market** runs validation again and saves the chain plus its first branch.
   It then appears in Home and Markets. Each user must select the branch for their price checks.

A successful sample is evidence for that page, not a promise that every product exists, has a price
or is discoverable. The generic integration uses a public online reference shared by the chain's
branches. Adding a city does not select a delivery region or confirm a physical store's shelf price.

## What happens behind the scenes

**No LLM is used during onboarding. No new scraper code is generated.** Compatible chains reuse the
existing `StructuredAdapter` registered as `public_jsonld`.

The browser sends the website, sample product URL and optional sitemap to
`POST /api/v1/admin/markets/probe`. Administrator authentication and CSRF protection are required.
The backend then:

1. Validates public HTTPS URLs, the same hostname and acceptable destinations at connection time.
   Private/local IPs, unsafe redirects and oversized documents are refused. Requests respect
   `robots.txt`, website pacing and the configured timeout. The probe has a 35-second time budget.
2. Reads the sample HTML without browser JavaScript or login. It parses a single JSON-LD **Product**
   (including an `@graph`) and a single **Offer**: product name, numeric positive price, `BRL`
   currency, availability and optional brand/SKU/barcode. It rejects expired, conditional,
   aggregate or multiple offers, rather than guessing which price applies.
3. Finds a same-host sitemap from `robots.txt`, falls back to `/sitemap.xml`, or uses the supplied
   index. It reads at most **6 sitemap documents and 5,000 pages**, with bounded document sizes.
4. Confirms the sample URL actually appears in that index. It returns the parsed example and
   explicit online-reference scope. Failures include their reason and do not register a market.

When you confirm, `POST /api/v1/admin/markets` repeats these checks before creating database rows:

```json
{
  "market": {
    "name": "Pradão",
    "adapter_key": "public_jsonld",
    "website": "https://<actual-shopping-host>",
    "allowed_domains": ["<actual-shopping-host>"],
    "enabled": true
  },
  "store_price_context": {
    "website": "https://<actual-shopping-host>",
    "sitemap_url": "https://<actual-shopping-host>/sitemap.xml",
    "scope": "public-online-reference"
  }
}
```

This is an illustrative stored configuration, not an API request to copy. Use the real URLs returned
by validation. The adapter registry binds the generic adapter to that market's validated hostname;
the source is now a saved configuration of working extraction code.

## How later searches find prices

A worker reads the selected stores and product matching rules. For a `public_jsonld` market it loads
the validated sitemap (cached for up to 24 hours), ranks its URL slugs using the product's search
terms/required words and visits a bounded set of candidate product pages (up to six sitemap-ranked
candidates, within the search candidate limit). It also considers previously preferred same-host
listing URLs. It parses the same Product/Offer format, normalizes package measures and prices, then
applies required words, exclusions, brand and size/unit rules.

Only equivalent, priced, available listings compete for the best comparable unit price. Observations
record the source, extraction method, package size and timestamp; list totals and price history use
these observations. Nothing is fabricated when a source cannot be read. Product URL slugs must be
informative enough for discovery: a sitemap containing only opaque numeric URLs may validate the
sample but still fail to find other products by name.

## Is AI ever involved?

The **application's worker** has an optional extraction fallback when an adapter explicitly requests it and provides a page excerpt,
the run permits AI and an enabled provider is configured. This is separate from onboarding. It reads
only the candidate page content, validates extracted products/prices against that content and still
applies deterministic equivalence rules. It cannot make an incompatible site's onboarding pass,
discover an arbitrary private catalog, choose a delivery region or replace a dedicated adapter.
The generic adapter does not request this fallback: incompatible pages produce a source error. Normal generic collection from valid JSON-LD uses no LLM. You can use the app without an AI key.

## Maintaining a generic source

Use **Revalidate source** on its market card to test a product again and update its sitemap. The
validated change propagates to all of that chain's stores. The hostname is kept to preserve the
history's source; a different hostname requires registering another chain. Failed validation keeps
the previous configuration. Source health reports later parsing/access errors.

## When a dedicated integration is needed

Sites requiring login, CEP-based sellers, browser-only JavaScript prices, custom APIs, price ranges,
multiple/conditional offers or non-BRL prices are outside generic onboarding. A failed probe should
not be overridden. A developer must implement a `MarketAdapter`, define domain and store-context
rules, normalize its offers and add fixture-based contract tests plus an integration test. Register
that adapter in `backend/src/pricetracker/adapters/registry.py` and expose its store configuration to
Administration. See [CONTRIBUTING](../CONTRIBUTING.md). An LLM does not perform these steps automatically.

## Built-in source contexts

| Chain | New branch configuration | Price meaning |
| --- | --- | --- |
| Angeloni | City/state and covered CEP; optional region seller | Online region resolved from CEP; invalid coverage/seller gives a context error |
| Fort Atacadista | Official numeric online store ID | The online store identified by that ID |
| Bistek | City/state; optional address/coordinates | Shared Florianópolis/SC online reference, even for a branch in another state |
| Imperatriz | Official numeric Super Clube store ID | Current Super Clube offers only; regular/loyalty prices separated |
| Generic public source | Validated website/sitemap and branch details | One shared anonymous online reference; not confirmed branch or delivery pricing |

Implementation: `backend/src/pricetracker/services/markets.py` (validation/persistence),
`adapters/structured.py` (JSON-LD/sitemap collection), `adapters/public_http.py` (public connection
validation) and `worker/executor.py` (collection, matching and observations). Contract and integration
tests exercise the generic source with simulated public pages; they do not claim live Pradão coverage.
