#!/usr/bin/env python3
"""End-to-end smoke check against a running PriceTracker stack (standard library only).

It signs in with an existing account, prepares a dedicated shopping list with every catalog item,
selects the nearest store of each market to a reference address, starts a collection run, waits
for it and prints a JSON summary (per-market statuses and the recommendation).

    scripts/stack_smoke.py prepare --credentials secrets/local-admin-credentials.txt
    scripts/stack_smoke.py run     --credentials secrets/local-admin-credentials.txt [--no-wait]
    scripts/stack_smoke.py wait    --credentials ... RUN_ID
    scripts/stack_smoke.py summary --credentials ...

The credentials file holds `username=` and `password=` lines; its values are never printed.
Session cookies are handled manually because the stack issues `Secure` cookies, which Python's
cookie jar refuses to send to http://localhost even though browsers accept them there.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

SMOKE_LIST = "Compra da semana (smoke)"
# Public reference point (Praça XV de Novembro, Florianópolis) — not a personal address.
REFERENCE = {"label": "Referência (Centro)", "city": "Florianópolis", "state": "SC",
             "latitude": "-27.596900", "longitude": "-48.549500"}  # fmt: skip
VEHICLE = {"name": "Carro de teste", "fuel_type": "gasolina", "km_per_liter": "11",
           "fuel_price_per_liter": "6.29"}  # fmt: skip
FINISHED = {"success", "partial", "failed", "cancelled"}


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.cookies: dict[str, str] = {}

    def request(self, method: str, path: str, body: Any = None) -> Any:
        headers = {"Accept": "application/json", "Origin": self.base}
        if self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        if method not in ("GET", "HEAD") and "pt_csrf" in self.cookies:
            headers["X-CSRF-Token"] = self.cookies["pt_csrf"]
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.base}/api/v1{path}", data, headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310 (local stack)
                self._store_cookies(response.headers.get_all("Set-Cookie") or [])
                raw = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:300]
            raise SystemExit(f"{method} {path} -> HTTP {error.code}: {detail}") from None
        return json.loads(raw) if raw else None

    def _store_cookies(self, headers: list[str]) -> None:
        for header in headers:
            jar: SimpleCookie = SimpleCookie()
            jar.load(header)
            for name, morsel in jar.items():
                self.cookies[name] = morsel.value

    def login(self, credentials: Path) -> None:
        values = dict(
            line.split("=", 1) for line in credentials.read_text().splitlines() if "=" in line
        )
        self.request("GET", "/auth/csrf")
        self.request(
            "POST", "/auth/login",
            {"username": values["username"].strip(), "password": values["password"].strip()},
        )  # fmt: skip


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(
        (lon2 - lon1) / 2
    ) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def smoke_list(api: Api) -> dict[str, Any] | None:
    return next((item for item in api.request("GET", "/lists") if item["name"] == SMOKE_LIST), None)


def prepare(api: Api) -> dict[str, Any]:
    existing = smoke_list(api)
    shopping = existing or api.request("POST", "/lists", {"name": SMOKE_LIST})
    detail = api.request("GET", f"/lists/{shopping['id']}")
    have = {item["product_id"] for item in detail["items"]}
    catalog = api.request("GET", "/catalog")["items"]
    for entry in catalog:
        if entry.get("my_product_id") not in have:
            api.request("POST", f"/lists/{shopping['id']}/items", {"catalog_item_id": entry["id"]})

    if not api.request("GET", "/me/addresses"):
        api.request("POST", "/me/addresses", REFERENCE)
    if not api.request("GET", "/me/vehicles"):
        api.request("POST", "/me/vehicles", VEHICLE)

    home = (float(REFERENCE["latitude"]), float(REFERENCE["longitude"]))
    chosen = []
    for market in api.request("GET", "/markets"):
        located = [s for s in market["stores"] if s.get("latitude") and s.get("longitude")]
        if not market["enabled"] or not located:
            continue
        nearest = min(
            located, key=lambda s: haversine_km(home, (float(s["latitude"]), float(s["longitude"])))
        )
        chosen.append({"store_id": nearest["id"], "market": market["name"], "store": nearest["name"]})
    api.request("PUT", "/me/stores", {"selections": [{"store_id": c["store_id"]} for c in chosen]})
    return {"list_id": shopping["id"], "items": len(catalog), "stores": chosen}


def wait(api: Api, run_id: str, timeout: float = 900) -> dict[str, Any]:
    started = time.monotonic()
    last = None
    while True:
        run = api.request("GET", f"/runs/{run_id}")
        progress = (run["status"], run["done_targets"], run["total_targets"])
        if progress != last:
            print(f"[{datetime.now():%H:%M:%S}] {run['status']} {run['done_targets']}/"
                  f"{run['total_targets']}", file=sys.stderr, flush=True)  # fmt: skip
            last = progress
        if run["status"] in FINISHED:
            return run
        if time.monotonic() - started > timeout:
            raise SystemExit(f"run {run_id} did not finish within {timeout:.0f}s")
        time.sleep(3)


def run_summary(run: dict[str, Any]) -> dict[str, Any]:
    by_market: dict[str, Counter[str]] = {}
    for target in run["targets"]:
        by_market.setdefault(target["market_name"], Counter())[target["status"]] += 1
    duration = None
    if run.get("started_at") and run.get("finished_at"):
        duration = round(
            (datetime.fromisoformat(run["finished_at"]) - datetime.fromisoformat(run["started_at"]))
            .total_seconds(), 1,
        )  # fmt: skip
    return {
        "run_id": run["id"], "status": run["status"], "targets": run["total_targets"],
        "counts": run["counts"], "llm_calls": run["llm_calls"], "duration_s": duration,
        "by_market": {name: dict(counts) for name, counts in sorted(by_market.items())},
        "retryable": run.get("retryable"),
    }  # fmt: skip


def comparison_summary(api: Api, list_id: str) -> dict[str, Any]:
    data = api.request("GET", f"/comparison?list_id={list_id}")
    rec = data["recommendation"]
    return {
        "headline": rec["headline"], "kind": rec["kind"], "covered": f"{rec['covered']}/{rec['total_items']}",
        "products_total": rec["products_total"], "travel_total": rec["travel_total"],
        "effective_total": rec["effective_total"], "savings": rec["savings"],
        "confidence": rec["confidence"], "warnings": rec["warnings"],
        "distance_method": data.get("distance_method"),
    }  # fmt: skip


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["prepare", "run", "wait", "summary"])
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--base", default="http://localhost:8090")
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    api = Api(args.base)
    api.login(args.credentials)
    output: dict[str, Any]
    if args.command == "prepare":
        output = prepare(api)
    elif args.command == "summary":
        shopping = smoke_list(api) or {}
        output = comparison_summary(api, shopping["id"]) if shopping else {"error": "run prepare first"}
    elif args.command == "wait":
        if not args.run_id:
            parser.error("wait needs RUN_ID")
        run = wait(api, args.run_id)
        output = {"run": run_summary(run), "comparison": comparison_summary(api, run["list_id"])}
    else:
        prepared = prepare(api)
        run = api.request("POST", "/runs", {"list_id": prepared["list_id"], "allow_llm": not args.no_llm})
        if args.no_wait:
            output = {"run_id": run["id"], "targets": run["total_targets"]}
        else:
            run = wait(api, run["id"])
            output = {"run": run_summary(run), "comparison": comparison_summary(api, prepared["list_id"])}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
