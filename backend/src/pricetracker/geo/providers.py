"""Swappable geocoding and routing with a hashed cache.

* Geocoding: ``manual`` (coordinates typed/picked by the user; always available)
  or ``nominatim`` (self-hosted URL recommended; the public instance is only used
  for explicit one-off lookups when the user saves an address, never for
  autocomplete or recurring load, with caching and an identifying User-Agent, as
  its usage policy requires).
* Routing: ``osrm`` (self-hosted road distances) or ``estimate`` (straight line x
  detour factor, always labelled as an estimate).

Cache keys are SHA-256 hashes, so addresses never appear in plaintext in the cache
and they are never logged.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.orm import Session

from pricetracker.db.base import utcnow
from pricetracker.domain.comparison import DistanceModel
from pricetracker.domain.travel import GeoPoint, haversine_km
from pricetracker.models import GeoCache
from pricetracker.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class GeoError(Exception):
    pass


@dataclass(frozen=True)
class GeocodeResult:
    latitude: Decimal
    longitude: Decimal
    provider: str
    precision: str


def _cache_key(kind: str, provider: str, payload: Any) -> str:
    return hashlib.sha256(
        json.dumps([kind, provider, payload], sort_keys=True, default=str).encode()
    ).hexdigest()


def _cache_get(db: Session, key: str) -> dict[str, Any] | None:
    row = db.get(GeoCache, key)
    if row is None or row.expires_at < utcnow():
        return None
    return row.result


def _cache_put(db: Session, key: str, kind: str, provider: str, result: dict[str, Any]) -> None:
    settings = get_settings()
    row = db.get(GeoCache, key)
    expires = utcnow() + timedelta(days=settings.geo_cache_days)
    if row is None:
        db.add(GeoCache(key=key, kind=kind, provider=provider, result=result, expires_at=expires))
    else:
        row.result, row.expires_at = result, expires
    db.flush()


def geocode_address(
    db: Session, *, street: str | None, number: str | None, district: str | None,
    city: str | None, state: str | None, postal_code: str | None,
    settings: Settings | None = None, transport: httpx.BaseTransport | None = None,
) -> GeocodeResult:  # fmt: skip
    settings = settings or get_settings()
    if settings.geocoder != "nominatim":
        raise GeoError(
            "Geocodificação automática desativada. Informe a localização no mapa ou as coordenadas."
        )
    query = {
        "street": " ".join(filter(None, [number, street])) or None,
        "city": city,
        "state": state,
        "postalcode": postal_code,
        "country": "Brasil",
    }
    query = {k: v for k, v in query.items() if v}
    key = _cache_key("geocode", "nominatim", query)
    cached = _cache_get(db, key)
    if cached:
        return GeocodeResult(
            Decimal(cached["lat"]), Decimal(cached["lon"]), "nominatim", cached["precision"]
        )
    headers = {"User-Agent": settings.http_user_agent, "Accept-Language": "pt-BR"}
    params: dict[str, str] = {k: str(v) for k, v in query.items() if v}
    params.update({"format": "jsonv2", "limit": "1", "countrycodes": "br"})
    if settings.nominatim_contact:
        params["email"] = settings.nominatim_contact
    try:
        with httpx.Client(timeout=10.0, transport=transport) as client:
            response = client.get(
                f"{settings.nominatim_url.rstrip('/')}/search", params=params, headers=headers
            )
    except httpx.HTTPError as exc:
        raise GeoError("Serviço de geocodificação indisponível.") from exc
    if response.status_code != 200:
        raise GeoError(f"Geocodificação falhou (HTTP {response.status_code}).")
    data = response.json()
    if not data:
        raise GeoError("Endereço não encontrado. Ajuste o endereço ou marque no mapa.")
    first = data[0]
    precision = first.get("addresstype") or first.get("type") or "unknown"
    result = {"lat": str(first["lat"]), "lon": str(first["lon"]), "precision": precision}
    _cache_put(db, key, "geocode", "nominatim", result)
    return GeocodeResult(Decimal(result["lat"]), Decimal(result["lon"]), "nominatim", precision)


class DistanceService:
    """Builds a ``DistanceModel`` for home + stores using OSRM or an estimate."""

    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.db = db
        self.settings = settings or get_settings()
        self.transport = transport

    def model(self, home: GeoPoint, stores: dict[str, GeoPoint]) -> DistanceModel:
        points: dict[str, GeoPoint] = {"home": home, **stores}
        if self.settings.router == "osrm" and self.settings.osrm_url:
            try:
                matrix = self._osrm_matrix(points)
                return DistanceModel(
                    distance=lambda a, b: matrix[(a, b)],
                    method="osrm",
                    description=(
                        "Distâncias rodoviárias calculadas com OSRM (OpenStreetMap), "
                        "com a melhor ordem de paradas."
                    ),
                )
            except GeoError as exc:
                logger.warning("osrm unavailable, falling back to estimate: %s", exc)
        factor = Decimal(str(self.settings.route_detour_factor))

        def estimate(a: str, b: str) -> Decimal:
            return (haversine_km(points[a], points[b]) * factor).quantize(Decimal("0.01"))

        return DistanceModel(
            distance=estimate,
            method="estimate",
            description=(
                f"Distâncias estimadas: linha reta × {str(factor).replace('.', ',')} "
                "(aproximação; configure OSRM para distâncias rodoviárias)."
            ),
        )

    def _osrm_matrix(self, points: dict[str, GeoPoint]) -> dict[tuple[str, str], Decimal]:
        ids = list(points)
        coords = [(str(points[i].longitude), str(points[i].latitude)) for i in ids]
        key = _cache_key("route", "osrm", coords)
        cached = _cache_get(self.db, key)
        if cached is None:
            path = ";".join(f"{lon},{lat}" for lon, lat in coords)
            url = f"{self.settings.osrm_url.rstrip('/')}/table/v1/driving/{path}"  # type: ignore[union-attr]
            try:
                with httpx.Client(timeout=15.0, transport=self.transport) as client:
                    response = client.get(url, params={"annotations": "distance"})
            except httpx.HTTPError as exc:
                raise GeoError("OSRM indisponível") from exc
            if response.status_code != 200 or response.json().get("code") != "Ok":
                raise GeoError(f"OSRM respondeu {response.status_code}")
            cached = {"distances": response.json()["distances"]}
            _cache_put(self.db, key, "route", "osrm", cached)
        distances = cached["distances"]
        matrix: dict[tuple[str, str], Decimal] = {}
        for i, a in enumerate(ids):
            for j, b in enumerate(ids):
                meters = distances[i][j]
                if meters is None:
                    raise GeoError("rota não encontrada entre dois pontos")
                matrix[(a, b)] = (Decimal(str(meters)) / Decimal(1000)).quantize(Decimal("0.01"))
        return matrix
