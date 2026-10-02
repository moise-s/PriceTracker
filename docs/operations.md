# Local operations

[Português](operations.pt-BR.md)

Everything runs on your computer with Docker Compose. Only the web UI is published, on loopback
(`http://localhost:8090`). Server deployment and Tailscale Serve are outside this version's scope.

## 1. First installation

```bash
./scripts/init-secrets.sh                    # Create ./secrets (database password and app key)
./scripts/init-secrets.sh --import-groq .env # Optional: import GROQ_API_KEY without displaying it
docker compose up -d --build                 # db → migrate (schema + seed) → api/worker/scheduler/web
docker compose ps                            # Persistent services should become healthy
```

- `./secrets/` is excluded from Git, with file permissions `0600`. Files: `postgres_password`,
  `app_secret_key`, `groq_api_key`, `openai_api_key`. The last two may be empty; AI fallback is
  disabled without a key and normal collection still works.
- Optional configuration: copy `.env.example` to `.env`, or use `--env-file`. Defaults support
  local operation. An existing root `.env` from the prototype is read by Compose if present;
  only variables listed in `compose.yaml` are used.

## 2. First access: create the administrator

There is no default password. Generate a single-use setup code valid for 30 minutes:

```bash
docker compose exec api pricetracker setup-code
```

Open `http://localhost:8090`, enter the code, name, username and a password of at least 10
characters. The next screen displays **10 recovery codes once**; save them because there is no
email recovery. After bootstrap, self-registration is disabled. Administrators can create users
with temporary passwords requiring a change, or enable self-registration.

CLI alternative, with a password read without terminal echo and a required change at first login:
`docker compose exec api pricetracker user create --username <username> --display-name "<name>" --admin`.

## 3. Daily use

- **Administration → Markets** manages integrated branches and availability and offers onboarding
  for compatible new chains. **Markets** filters by Brazilian state/city and saves each user's
  selection. See [coverage and price contexts](markets.en.md).
- New-user guides: [getting started](getting-started.en.md), [daily use](user-guide.en.md) and
  **More → How to use** in the app.
- Build a list, choose stores, configure address/coordinates and vehicle, then check prices.
  Home's **Refresh prices** opens list review → store confirmation → search. Collection continues
  in the background after you close the page.
- **Schedules** refresh prices regularly, for example every Friday at 07:00.
- **Notifications** displays price alerts triggered by runs.
- CLI output is JSON; exit codes are 0 success, 4 partial, 5 failed, 6 cancelled:
  `docker compose exec api pricetracker run --user <username> --store angeloni:beira-mar --product arroz`.
  `--enqueue` only queues for the worker; `--no-llm` disables the AI fallback.

## 4. Health and logs

```bash
docker compose ps
docker compose logs -f --tail=100 api worker   # JSON logs with request_id/run_id; secrets redacted
curl -s localhost:8090/api/v1/health/ready      # {"status":"ok","database":true,"schema_version":"0002"}
docker compose exec api pricetracker llm check  # Check the AI provider without displaying its key
```

Administration shows per-market success rate, duration, extraction methods and failures over the
last 14 days, plus AI usage.

## 5. Backup and restoration

```bash
make backup                                           # ./backups/pricetracker-<UTC>/
make restore-drill BACKUP=backups/pricetracker-<UTC>    # Restore/check a disposable PostgreSQL
./scripts/restore.sh backups/pricetracker-<UTC> --yes   # DESTRUCTIVE: replace stack database/images
```

- Backups contain `db.dump` (`pg_dump` custom format), `uploads.tar.gz` and `manifest.json`
  (SHA-256 checksums, schema version and row counts).
- The drill validates checksums, restores, compares schema/row counts and checks image files without
  touching the running stack. `restore.sh` performs the drill before removing existing data.
- Evidence from 2026-09-27: backup `20260927T213829Z` (1.1 MB dump, 11 images), drill **PASS** in
  3.8 s. A real restore removed a subsequently created list and retained the uploaded image.
- Local backups are manual by default. Scheduling `make backup` and retention is separate setup.

## 6. Restart and persistence

`docker compose down` followed by `docker compose up -d` preserves the `pg_data` and `app_data`
volumes. An interrupted run returns to the queue and resumes from its completed targets.
Seed preserves market names, colors, notes and availability. Administrator-edited branches have
`admin` origin and are not overwritten. Built-in source domains/adapters remain code-owned.
Wizard-added chains preserve validated domains/source configuration in the database;
see [sources](markets.en.md).

The 2026-09-27 restart test interrupted a run at 19/40 targets. After restart, attempt 2 processed
the 21 pending targets and finished `success`, with 29 observations and no duplicates.
`docker compose down -v` deletes **all volume data**; do not use it for normal shutdown.

## 7. Updates and migrations

```bash
git pull                       # When a new version is available
docker compose up -d --build   # migrate applies pending revisions and idempotent seed
```

Revision `0002` allows metre-based quantities without deleting existing data. v1 installations
need it before using per-metre comparison; `migrate` applies it at startup. See
[migrations and downgrade limits](migrations.md).

## 8. Resource usage

Measured on 2026-09-27 using Docker Desktop on Apple Silicon; these are historical measurements.

| Service | Idle | During collection (40 targets) | Configured limit |
| --- | --- | --- | --- |
| api | ~90 MiB, ~0% CPU | ~91 MiB, peaks ~14% CPU | 1 CPU / 512 MiB |
| worker | ~70 MiB | 95–130 MiB, peaks ~23% CPU | 1 CPU / 768 MiB |
| scheduler | ~67 MiB | ~67 MiB | 0.25 CPU / 256 MiB |
| db | ~45–50 MiB | ~49 MiB | 1 CPU / 512 MiB |
| web | ~14 MiB | ~14 MiB | 0.5 CPU / 128 MiB |
| **Total** | **~290 MiB** | **~350 MiB** | |

Collection uses HTTP rather than a headless browser. Measured images were 432 MB backend and
82 MB web. `PRICETRACKER_WORKER_CONCURRENCY` defaults to 3; each host allows at most 2 connections.

## 9. Known issues

- **Embedded-browser service workers:** some Electron-based browsers reject registration on
  `http://localhost` with an unknown script-fetch error. The app still works without its offline
  shell cache. Chrome registration was verified with Playwright; check normal browsers before
  diagnosing an embedded-browser failure.
- **Secure cookies over HTTP:** current browsers accept `Secure` cookies on `http://localhost`.
  Access through another name/IP without HTTPS can break session persistence. Use localhost or
  configure an HTTPS proxy.
- **Other devices:** the published port is bound to `127.0.0.1`. Network access needs an HTTPS proxy
  and a matching `PRICETRACKER_PUBLIC_ORIGIN`, outside this version's installation scope.

## 10. Development without application containers

A disposable database still uses Docker; API, worker and web run directly on the host:

```bash
make bootstrap       # uv sync + npm ci
make dev-db          # Disposable PostgreSQL at 127.0.0.1:55433 and pricetracker_test database
make dev-init        # Apply schema and seed before starting the API
make dev-setup-code  # Generate the first administrator's setup code
make api             # :8000, development cookies for http://localhost:5173
make worker
make web             # Vite :5173 with /api proxy → :8000
```
