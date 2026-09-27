# PriceTracker — backend

API (FastAPI), worker, scheduler e CLI em um pacote Python (`pricetracker`), gerenciado com `uv`.

```bash
uv sync
uv run pricetracker --help            # serve, worker, scheduler, run, db upgrade, db-init, seed,
                                      # setup-code, user, llm check, health, openapi
uv run pytest -q                      # suíte determinística (SQLite)
PRICETRACKER_TEST_DATABASE_URL=postgresql+psycopg://… uv run pytest -q   # mesma suíte em PostgreSQL
uv run pytest tests/live --live -q    # smoke tests nos sites reais (opt-in)
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

## Estrutura

| Caminho | Conteúdo |
| --- | --- |
| `src/pricetracker/api/` | Rotas `/api/v1`, schemas Pydantic, dependências (sessão, CSRF, papéis) |
| `src/pricetracker/services/` | Casos de uso (contas, catálogo, listas, buscas, comparação, histórico, alertas, admin) |
| `src/pricetracker/domain/` | Lógica pura: dinheiro, unidades, texto, matching, preços, deslocamento, qualidade, comparação |
| `src/pricetracker/adapters/` | Cliente HTTP educado, robots, sitemaps e os adaptadores `angeloni`, `bistek`, `fort`, `imperatriz` |
| `src/pricetracker/llm/` | Provedores (Groq, OpenAI, compatível) e serviço com verificação anti-fabricação |
| `src/pricetracker/worker/`, `scheduler/` | Fila no PostgreSQL, executor de buscas, recorrências |
| `src/pricetracker/seed/` | Mercados, 85 filiais, catálogo inicial com ilustrações originais |
| `migrations/` | Alembic (schema novo, revisão `0001`) |
| `tests/` | `unit/`, `contract/` (fixtures sanitizadas), `integration/`, `live/`, `e2e_harness.py` |

Configuração por variáveis `PRICETRACKER_*` (ou `*_FILE` para segredos); ver
`src/pricetracker/settings.py` e `../.env.example`.
