# Legacy v0 prototype (discontinued)

`legacy/v0/` is the original Streamlit + YAML + SQLite prototype, archived on
2026-09-27 when PriceTracker v1 was rebuilt. It is kept only as reference for
requirements and lessons learned; nothing in the v1 runtime imports it, and it is
excluded from the v1 lint and test suites.

- Last v0 commit: `bdb478c` (local tag `v0-prototype`).
- The archive includes the work that was uncommitted when the rebuild started:
  the `headless=False` change in `pricetracker/core/runner.py` and the untracked
  Alembic chain (`alembic.ini`, `alembic/script.py.mako`, `alembic/versions/`).
- The old local files `config.yaml`, `pricetracker.db` and `.env` at the
  repository root are git-ignored and were left untouched. The v1 application does
  not read `config.yaml` or `pricetracker.db`; the old database is discontinued and
  is not migrated or imported.

Why it was replaced (observed problems): money stored as `float`; overly
permissive matching; suspicious historical values; per-product errors swallowed
so a run could end as `success` with failures; no JSON summary or useful exit
codes; a browser forced into visible mode; no authentication, per-user isolation,
images, addresses, stores or travel cost; site selectors that broke silently.
