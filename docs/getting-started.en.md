# Getting started

[Português](getting-started.md) · [README](../README.md)

You can join an existing installation or host your own. Accounts, lists and price history are
local to that installation. There is no email sign-in and no default administrator password.

## Joining an existing installation

1. Ask the administrator for the installation's address and an account. If given a temporary
   password, choose a new password at first sign-in.
2. Choose **English** in the language selector. It is available on sign-in screens, in the desktop
   sidebar and in the phone header. The preference stays in this browser.
3. Save your recovery codes somewhere safe. Each code can reset your password once. Without a code,
   ask the administrator to reset it.
4. On **Home**, choose your markets, then select **Update prices**. Review your list, confirm the
   stores on the next page and select **Check prices now**.
5. Watch the search progress. Once finished, open **Best value**. Review missing items and the
   source notes before relying on a total.

## Hosting locally with Docker

Use the v1 branch `feat/rebuild-v1`, not the older local `main`. Requirements: Git, Docker with
Compose v2, Python 3 and a POSIX shell (WSL2 on Windows). Clone/check out the v1 source and run:

```bash
cd PriceTracker
./scripts/init-secrets.sh
docker compose up -d --build
docker compose ps
# Once persistent services are healthy:
docker compose exec api pricetracker setup-code
```

Visit **http://localhost:8090**. Create your administrator using the one-time setup code and save
the recovery codes. Configure markets in **Administration → Markets**, and create other accounts
in **Administration → Users**. AI keys are optional; onboarding compatible public markets uses no AI.

`localhost` is the computer running Docker. The same address on a phone refers to that phone.
Remote access needs its own setup; this guide does not configure it.

To stop, use `docker compose down`; data remains in named volumes. Restart with
`docker compose up -d`. Avoid `down -v`, which deletes those volumes. To update an existing v1
installation, rebuild and start Compose; the migration service applies schema updates before the
API and worker start. A development setup uses `make dev-init` to apply migrations.

## First useful comparison

Add products with quantities you actually need. Choose stores you would shop at. A new chain needs
administrator onboarding; a new physical branch of an existing chain uses that chain's integration.
Both become selectable on Home and Markets once enabled.

With a located address and vehicle in **Profile**, travel cost uses round-trip distance, fuel
consumption, fuel price and tolls. Without these details, disable travel costs to compare products
alone. The UI language can be English, while currency remains BRL and addresses use Brazil's CEP/UF.

[User guide](user-guide.en.md) · [Market onboarding and source behavior](markets.en.md)
