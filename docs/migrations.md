# Relatório de migrations

O schema da v1 é **novo**: começa de um banco vazio e não importa, migra nem lê o SQLite do
protótipo (`pricetracker.db`, mantido intacto na raiz só como referência histórica).

## Estado atual

| Revisão | Arquivo | Conteúdo |
| --- | --- | --- |
| `0001` (head) | `backend/migrations/versions/20260927_0001_initial_v1_schema.py` | Schema inicial completo: 31 tabelas, 23 check constraints, uniques e índices |

A migration é autocontida (não importa tipos da aplicação: o tipo `UTCDateTime` vira
`sa.DateTime(timezone=True)` via `render_item`) e usa `render_as_batch` no SQLite, para que ALTERs
futuros funcionem nos dois bancos.

## Tabelas por área

- **Contas e sessões:** `users`, `user_sessions` (hash do token, único), `recovery_codes`,
  `login_attempts`, `profiles` (frescor 1–90 dias, paradas 1–4, clubes ativados, onboarding).
- **Endereço e veículo:** `addresses`, `vehicles` (km/l > 0, preço do combustível ≥ 0).
- **Catálogo e produtos:** `catalog_items` (global, slug único), `products` (do usuário, com regras
  de matching), `images` (chave de armazenamento única, sha256 indexado, origem seed/upload/url),
  `product_market_pins` (aceitar/rejeitar anúncio por mercado).
- **Listas:** `shopping_lists`, `list_items` (quantidade > 0, produto único por lista).
- **Mercados:** `markets` (slug único), `stores` (único por mercado + slug, coordenadas e contexto de
  preço), `user_store_selections` (pedágio ≥ 0), `adapter_versions`.
- **Coleta:** `runs` (chave de idempotência única; índices por status/criação e por usuário),
  `run_targets`, `run_events`, `candidates` (todos os anúncios avaliados, com o motivo),
  `observations` (uma por alvo, chave de idempotência única; índice usuário + produto + loja +
  horário para a comparação e o histórico).
- **Agenda e avisos:** `schedules` (diária/semanal), `price_alerts` (alvo > 0, um por produto),
  `notifications`.
- **Infraestrutura:** `app_settings`, `llm_providers`, `llm_calls`, `llm_cache`, `http_cache`,
  `geo_cache` (caches com expiração indexada).

## Convenções

- Dinheiro em `NUMERIC(12,2)`, preço unitário em `NUMERIC(14,4)`, quantidade em `NUMERIC(12,3)`,
  coordenadas em `NUMERIC(9,6)`.
- Timestamps sempre em UTC com fuso (`timestamptz`); formatação local só na interface.
- JSON vira `JSONB` no PostgreSQL (e `JSON` no SQLite).
- Toda linha pertencente a um usuário tem `user_id` com `ON DELETE CASCADE`.
- Nomes de constraints e índices determinísticos (`ix_`, `uq_`, `ck_`, `fk_`, `pk_`), o que torna
  `alembic check` confiável.

## Verificação (27/09/2026)

| Verificação | PostgreSQL 17.10 | SQLite |
| --- | --- | --- |
| `alembic upgrade head` num banco vazio | ok, 31 tabelas | ok |
| `alembic check` (modelos × banco) | "No new upgrade operations detected" | idem |
| `alembic downgrade base` | ok, 0 tabelas | — |
| novo `upgrade head` + `check` | ok, sem diferenças | — |
| stack Docker (`migrate` → `db-init`) | migração + seed idempotente a cada subida | — |
| suíte de testes | 135 testes em PostgreSQL (`make test-pg`) | 133 em SQLite |

Reproduzir:

```bash
make dev-db
cd backend
export PRICETRACKER_DATABASE_URL=postgresql+psycopg://pricetracker:pricetracker_local@127.0.0.1:55433/pricetracker
uv run alembic upgrade head && uv run alembic check
```

## Como evoluir o schema

1. Altere os modelos em `backend/src/pricetracker/models/`.
2. `uv run alembic revision --autogenerate -m "descrição"` com o banco de desenvolvimento em `head`.
3. Revise o arquivo gerado (tipos, `server_default` para colunas obrigatórias em tabelas com dados,
   índices), teste `upgrade` e `downgrade` em PostgreSQL e SQLite e rode `alembic check`.
4. Faça um backup antes de aplicar em dados reais (`make backup`). Na stack, o job `migrate` aplica
   as migrations pendentes antes de a API subir.
