"""Idempotent seed: markets, stores, the initial catalog (with images) and LLM providers."""

from __future__ import annotations

import json
from decimal import Decimal
from importlib import resources
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pricetracker.models import CatalogItem, Image, LlmProvider, Market, Store
from pricetracker.models.enums import LlmKind
from pricetracker.seed.catalog import CATALOG, SEED_IMAGE_LICENSE
from pricetracker.services import images as image_service
from pricetracker.settings import get_settings

MARKETS: list[dict[str, Any]] = [
    {
        "slug": "angeloni",
        "name": "Angeloni",
        "website": "https://super.angeloni.com.br",
        "adapter_key": "angeloni",
        "allowed_domains": ["super.angeloni.com.br"],
        "brand_color": "#0E7C66",
        "notes": (
            "API pública de busca do VTEX (Intelligent Search) por filial (region-id resolvido pelo CEP da "
            "loja). Promoções por quantidade via Master Data público. Preço de clube/app exige CPF e não é coletado."
        ),
    },
    {
        "slug": "bistek",
        "name": "Bistek",
        "website": "https://www.bistek.com.br",
        "adapter_key": "bistek",
        "allowed_domains": ["bistek.com.br"],
        "brand_color": "#C8372D",
        "notes": (
            "robots.txt proíbe /api/ e a busca: produtos descobertos pelo sitemap e lidos na página do "
            "produto. Não é possível escolher a filial dentro do robots.txt: o preço é o online de referência "
            "(Florianópolis/SC). Sem preço de clube nem promoções de carrinho."
        ),
    },
    {
        "slug": "fort",
        "name": "Fort Atacadista",
        "website": "https://www.fortatacadista.com.br",
        "adapter_key": "fort",
        "allowed_domains": ["fortatacadista.com.br"],
        "brand_color": "#E0701B",
        "notes": (
            "robots.txt proíbe a busca e URLs com query string: produtos descobertos pelo sitemap e lidos em "
            "/produtos/ com o cookie de loja do próprio site. Preços normal, promocional, 'Mais por Menos', "
            "Clube Mais e cartão."
        ),
    },
    {
        "slug": "imperatriz",
        "name": "Imperatriz",
        "website": "https://superimperatriz.com.br",
        "adapter_key": "imperatriz",
        "allowed_domains": ["api.zoombox.com.br", "9zli2drdqe.execute-api.us-east-1.amazonaws.com"],
        "brand_color": "#2457A6",
        "notes": (
            "O site não tem mais catálogo nem preços. Fonte oficial disponível: ofertas vigentes do Super "
            "Clube por loja (cobertura parcial). O catálogo completo só existe no iFood, protegido por "
            "anti-bot, e não é usado."
        ),
    },
]


def _load_stores() -> list[dict[str, Any]]:
    text = resources.files("pricetracker.seed").joinpath("stores.json").read_text(encoding="utf-8")
    return list(json.loads(text)["stores"])


def seed_markets(db: Session) -> dict[str, Market]:
    markets: dict[str, Market] = {}
    for data in MARKETS:
        market = db.scalar(select(Market).where(Market.slug == data["slug"]))
        if market is None:
            market = Market(**data)
            db.add(market)
        else:
            for key in ("name", "website", "adapter_key", "allowed_domains", "notes"):
                setattr(market, key, data[key])
        markets[data["slug"]] = market
    db.flush()
    for row in _load_stores():
        market = markets[row["market"]]
        store = db.scalar(
            select(Store).where(Store.market_id == market.id, Store.slug == row["slug"])
        )
        values = {
            "name": row["name"],
            "external_id": row.get("external_id"),
            "street": row.get("street"),
            "number": row.get("number"),
            "district": row.get("district"),
            "city": row.get("city"),
            "state": row.get("state"),
            "postal_code": row.get("postal_code"),
            "latitude": Decimal(str(row["latitude"])).quantize(Decimal("0.000001"))
            if row.get("latitude")
            else None,
            "longitude": Decimal(str(row["longitude"])).quantize(Decimal("0.000001"))
            if row.get("longitude")
            else None,
            "price_context": row.get("price_context") or {},
            "price_scope_note": row.get("price_scope_note"),
        }
        if store is None:
            db.add(Store(market_id=market.id, slug=row["slug"], source="seed", **values))
        elif store.source == "seed":
            for key, value in values.items():
                setattr(store, key, value)
    db.flush()
    return markets


def seed_catalog(db: Session) -> int:
    count = 0
    images_dir = resources.files("pricetracker.seed").joinpath("images")
    uploads = get_settings().uploads_dir
    for order, data in enumerate(CATALOG):
        item = db.scalar(select(CatalogItem).where(CatalogItem.slug == data["slug"]))
        values = {
            k: (v.value if hasattr(v, "value") else v) for k, v in data.items() if k != "slug"
        }
        values["sort_order"] = order
        if item is None:
            item = CatalogItem(slug=data["slug"], **values)
            db.add(item)
            count += 1
        else:
            for key, value in values.items():
                setattr(item, key, value)
        svg = images_dir.joinpath(f"{data['slug']}.svg")
        if svg.is_file():
            storage_name = f"catalog-{data['slug']}.svg"
            image = db.scalar(select(Image).where(Image.storage_key == f"global/{storage_name}"))
            payload = svg.read_bytes()
            if image is None:
                image = image_service.store_trusted_svg(
                    db,
                    data=payload,
                    storage_name=storage_name,
                    alt_text=data["name"],
                    license=SEED_IMAGE_LICENSE,
                )
            elif not (uploads / image.storage_key).is_file():
                (uploads / image.storage_key).parent.mkdir(parents=True, exist_ok=True)
                (uploads / image.storage_key).write_bytes(payload)
            item.image_id = image.id
    db.flush()
    return count


def seed_llm_providers(db: Session) -> None:
    settings = get_settings()
    defaults = [
        {
            "name": "Groq",
            "kind": LlmKind.GROQ.value,
            "base_url": settings.groq_base_url,
            "model": settings.groq_model,
            "api_key_env": "GROQ_API_KEY",
            "structured_output": "json_object",
            "enabled": True,
            "is_default": True,
        },
        {
            "name": "OpenAI",
            "kind": LlmKind.OPENAI.value,
            "base_url": settings.openai_base_url,
            "model": settings.openai_model,
            "api_key_env": "OPENAI_API_KEY",
            "structured_output": "json_schema",
            "enabled": False,
            "is_default": False,
        },
    ]
    for data in defaults:
        if db.scalar(select(LlmProvider).where(LlmProvider.name == data["name"])) is None:
            db.add(LlmProvider(**data))
    db.flush()


def seed_all(db: Session) -> dict[str, int]:
    markets = seed_markets(db)
    created = seed_catalog(db)
    seed_llm_providers(db)
    db.commit()
    return {"markets": len(markets), "stores": len(_load_stores()), "catalog_created": created}
