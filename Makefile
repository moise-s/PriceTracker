.PHONY: help bootstrap dev-db api worker scheduler web test test-live lint typecheck check openapi build up down logs backup restore-drill smoke e2e secrets-scan

help: ## List targets
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*## / — /'

bootstrap: ## Install backend and web dependencies
	cd backend && uv sync
	cd web && npm ci

dev-db: ## Start a throwaway PostgreSQL for development on 127.0.0.1:55433
	docker run -d --name pricetracker-dev-pg -e POSTGRES_USER=pricetracker -e POSTGRES_PASSWORD=pricetracker_local -e POSTGRES_DB=pricetracker -p 127.0.0.1:55433:5432 postgres:17.10-alpine@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193

api: ## Run the API against the dev database
	cd backend && PRICETRACKER_DATABASE_URL=postgresql+psycopg://pricetracker:pricetracker_local@127.0.0.1:55433/pricetracker PRICETRACKER_COOKIE_SECURE=false uv run pricetracker serve

worker: ## Run the worker against the dev database
	cd backend && PRICETRACKER_DATABASE_URL=postgresql+psycopg://pricetracker:pricetracker_local@127.0.0.1:55433/pricetracker uv run pricetracker worker

scheduler: ## Run the scheduler against the dev database
	cd backend && PRICETRACKER_DATABASE_URL=postgresql+psycopg://pricetracker:pricetracker_local@127.0.0.1:55433/pricetracker uv run pricetracker scheduler

web: ## Run the Vite dev server (proxies /api to :8000)
	cd web && npm run dev

test: ## Deterministic backend tests + web unit tests
	cd backend && uv run pytest -q
	cd web && npm test

test-live: ## Opt-in live smoke tests against the real supermarket sites
	cd backend && uv run pytest tests/live --live -q

lint: ## Ruff + oxlint
	cd backend && uv run ruff check src tests && uv run ruff format --check src tests
	cd web && npm run lint

typecheck: ## mypy (strict) + tsc
	cd backend && uv run mypy src
	cd web && npm run typecheck

check: lint typecheck test secrets-scan ## Everything that must pass before a commit

openapi: ## Export the API contract and regenerate the typed web client
	cd backend && uv run pricetracker openapi --output ../web/openapi.json
	cd web && npm run api:generate

build: ## Build the Docker images
	docker compose build

up: ## Start the local stack (http://localhost:8090)
	docker compose up -d --build

down: ## Stop the local stack (data volumes are kept)
	docker compose down

logs: ## Follow logs
	docker compose logs -f --tail=100

backup: ## Backup database + uploads to ./backups
	./scripts/backup.sh

restore-drill: ## Verify a backup in a throwaway database: make restore-drill BACKUP=backups/pricetracker-...
	./scripts/restore-drill.sh $(BACKUP)

smoke: ## Real collection against the running stack: make smoke CREDENTIALS=secrets/local-admin-credentials.txt
	python3 scripts/stack_smoke.py run --credentials $(CREDENTIALS)

e2e: ## Playwright end-to-end scenarios (starts its own isolated backend)
	cd web && npm run e2e

secrets-scan: ## Scan the working tree and history for secrets
	gitleaks git --no-banner --redact --config .gitleaks.toml .
