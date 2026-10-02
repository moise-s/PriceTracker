# PriceTracker — web

[English](README.md)

PWA em React 19 + TypeScript + Vite, em português/inglês, consumindo o contrato OpenAPI tipado do backend.

```bash
npm ci
npm run dev          # http://localhost:5173, proxy /api → http://127.0.0.1:8000 (PRICETRACKER_API_URL)
npm run build        # tsc -b + vite build (gera o service worker)
npm run typecheck && npm run lint
npm test             # Vitest (unitários e componentes)
npm run e2e          # Playwright (sobe backend/tests/e2e_harness.py + vite preview)
npm run api:generate # regenera src/api/schema.d.ts a partir de openapi.json
```

- `src/api/` — cliente `openapi-fetch` com CSRF, hooks TanStack Query e tipos gerados.
- `src/app/` — shell (navegação lateral/inferior), guardas de rota, rotas com code splitting.
- `src/pages/` — telas: primeiro acesso, lista, mercados, busca, onde compensa, histórico, produto,
  avisos, agendamentos, perfil, administração.
- `src/components/` — kit de UI (Radix + Tailwind) e componentes de domínio (recomendação,
  cobertura, frescor).
- `e2e/` — cenários obrigatórios e matriz de telas; screenshots em `../docs/screenshots/`.

Tokens de cor, tipografia e modo escuro ficam em `src/styles.css`; as cores dos mercados vêm de uma
paleta validada para daltonismo e contraste, e o nome do mercado sempre acompanha a cor.
Administradores podem personalizar a cor; nesse caso, confira contraste nos dois temas.

`pages/admin-markets.tsx` gerencia filiais e redes integradas. `pages/markets.tsx` filtra por região
sem remover lojas selecionadas fora do filtro. `pages/help.tsx` oferece o guia de uso em `/ajuda`.
