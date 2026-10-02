# PriceTracker — web

[Português](README.pt-BR.md)

React 19 + TypeScript + Vite PWA with Portuguese/English UI, consuming the backend's typed
OpenAPI contract.

```bash
npm ci
npm run dev          # http://localhost:5173, /api proxy → http://127.0.0.1:8000 (PRICETRACKER_API_URL)
npm run build        # tsc -b + vite build, including the service worker
npm run typecheck && npm run lint
npm test             # Vitest unit and component tests
npm run e2e          # Playwright; starts backend/tests/e2e_harness.py and vite preview
npm run api:generate # Regenerate src/api/schema.d.ts from openapi.json
```

- `src/api/`: `openapi-fetch` client with CSRF, TanStack Query hooks and generated types.
- `src/app/`: navigation shell, route guards and routes with code splitting.
- `src/pages/`: first access, list, markets, search, comparison, history, product editor,
  notifications, schedules, profile and administration.
- `src/components/`: UI kit (Radix + Tailwind) and domain components for recommendations,
  coverage and price freshness.
- `src/lib/i18n.ts`, `translations.ts`: browser-local language choice and English translations of
  Portuguese message IDs. Formatting uses the selected locale; currency remains BRL.
- `e2e/`: usage scenarios and screen matrix; screenshots live in `../docs/screenshots/`.

Color tokens, typography and dark mode live in `src/styles.css`. Default market colors use a
palette checked for color blindness and contrast; market names always accompany colors.
Administrators can customize colors, so check contrast in both themes after changing them.

`pages/admin-markets.tsx` manages chains and branches. `pages/market-onboarding.tsx` validates
public sources for new chains. `pages/markets.tsx` filters regions while keeping selections outside
the filter. `pages/help.tsx` provides in-app help at `/ajuda`.

Use English identifiers and new code comments, but keep source names and product search terms
unchanged. Translate UI text through the existing catalog rather than replacing its message IDs.
See [language conventions](../CONTRIBUTING.md#language-conventions).
