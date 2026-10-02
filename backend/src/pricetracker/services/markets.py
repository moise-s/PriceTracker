"""Administrator-owned market availability and branches of installed integrations."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pricetracker.adapters.base import DocumentCache
from pricetracker.adapters.errors import ParseError
from pricetracker.adapters.http import FetchError, PoliteClient
from pricetracker.adapters.public_http import PublicHttpsTransport, public_url
from pricetracker.adapters.structured import (
    PRICE_SCOPE,
    load_public_index,
    parse_product,
    same_site,
)
from pricetracker.domain.text import slugify
from pricetracker.models import Market, Observation, RunTarget, Store
from pricetracker.services.errors import Conflict, NotFound, ValidationFailed
from pricetracker.settings import get_settings

CONTEXTS = {
    "public_jsonld": (
        "shared",
        PRICE_SCOPE + " Todas as filiais compartilham a fonte online validada no cadastro.",
    ),
    "angeloni": (
        "postal_code",
        "Informe o CEP atendido pela loja. O vendedor é opcional; quando informado, "
        "a busca confirma se o CEP pertence a ele. Não use o CEP de outra filial.",
    ),
    "bistek": (
        "shared",
        "Todas as filiais usam o preço online de referência de Florianópolis/SC. "
        "Cadastrar uma filial em outra cidade não muda a região dos preços.",
    ),
    "fort": (
        "store_id",
        "Informe o identificador oficial da loja online (store_id), obtido no site da rede. "
        "O endereço físico sozinho não identifica a região de preços.",
    ),
    "imperatriz": (
        "store_id",
        "Informe o identificador oficial da loja no Super Clube. "
        "Só as ofertas vigentes são coletadas; não há cobertura do catálogo completo.",
    ),
}

PRICE_NOTES = {
    "public_jsonld": PRICE_SCOPE,
    "angeloni": "Preço online da região atendida pelo CEP (pode variar na gôndola).",
    "bistek": "Preço online de referência (Florianópolis/SC), compartilhado entre filiais.",
    "fort": "Preço online de cada loja (pode variar na gôndola).",
    "imperatriz": "Somente ofertas vigentes do Super Clube de cada loja (cobertura parcial).",
}


def get_market(db: Session, market_id: uuid.UUID) -> Market:
    market = db.get(Market, market_id)
    if market is None:
        raise NotFound("Mercado não encontrado.")
    return market


def market_view(market: Market) -> dict[str, Any]:
    kind, help_text = CONTEXTS.get(
        market.adapter_key, ("unsupported", "Esta integração ainda não tem formulário de filiais.")
    )
    return {
        "id": market.id,
        "slug": market.slug,
        "name": market.name,
        "website": market.website,
        "enabled": market.enabled,
        "brand_color": market.brand_color,
        "notes": market.notes,
        "adapter_key": market.adapter_key,
        "context_kind": kind,
        "context_help": help_text,
        "sitemap_url": next(
            (
                s.price_context.get("sitemap_url")
                for s in market.stores
                if s.price_context and s.price_context.get("sitemap_url")
            ),
            None,
        ),
        "stores": [
            {
                **{
                    key: getattr(s, key)
                    for key in (
                        "id",
                        "slug",
                        "name",
                        "external_id",
                        "street",
                        "number",
                        "district",
                        "city",
                        "state",
                        "postal_code",
                        "latitude",
                        "longitude",
                        "is_active",
                        "source",
                        "price_scope_note",
                    )
                },
                # Imported branches may have incomplete addresses; keep them editable.
                "city": s.city or "",
                "state": s.state or "",
                "seller": (s.price_context or {}).get("seller"),
            }
            for s in market.stores
        ],
    }


def update_market(db: Session, market_id: uuid.UUID, data: dict[str, Any]) -> Market:
    market = get_market(db, market_id)
    for key, value in data.items():
        if key in {"name", "enabled"} and value is None:
            raise ValidationFailed("Nome e disponibilidade não podem ser vazios.")
        if key == "name":
            value = value.strip()
            if len(value) < 2:
                raise ValidationFailed("Informe o nome do mercado.")
        setattr(market, key, value)
    db.commit()
    return market


def save_store(
    db: Session,
    market_id: uuid.UUID,
    store_id: uuid.UUID | None,
    data: dict[str, Any],
    *,
    public_source: dict[str, str] | None = None,
) -> Store:
    market = get_market(db, market_id)
    if market.adapter_key not in CONTEXTS:
        raise ValidationFailed("Integração sem suporte à configuração de filiais.")
    if (data.get("latitude") is None) != (data.get("longitude") is None):
        raise ValidationFailed("Informe latitude e longitude juntas.", code="invalid_coordinates")
    seller = data.pop("seller", None) or None
    external_id = data.get("external_id") or None
    postal_code = data.get("postal_code") or None
    if market.adapter_key == "angeloni":
        if not postal_code:
            raise ValidationFailed(
                "Informe o CEP atendido pelo Angeloni.", code="missing_price_context"
            )
        if seller and not seller.replace("-", "").isalnum():
            raise ValidationFailed("Identificador de vendedor inválido.")
        context = {"postal_code": postal_code.replace("-", "")}
        if seller:
            context["seller"] = seller
    elif market.adapter_key in {"fort", "imperatriz"}:
        if not external_id or not external_id.isascii() or not external_id.isdigit():
            raise ValidationFailed(
                "Informe o identificador numérico oficial da loja.", code="missing_price_context"
            )
        context = {"store_id": external_id}
        duplicate_query = select(Store).where(
            Store.market_id == market.id, Store.external_id == external_id
        )
        if store_id is not None:
            duplicate_query = duplicate_query.where(Store.id != store_id)
        duplicate = db.scalar(duplicate_query)
        if duplicate:
            raise Conflict("Este identificador já pertence a uma filial. Edite a loja existente.")
    elif market.adapter_key == "public_jsonld":
        context = public_source or next(
            (
                dict(s.price_context)
                for s in market.stores
                if s.price_context and s.price_context.get("sitemap_url")
            ),
            {},
        )
        if not context:
            raise ValidationFailed("Cadastre a fonte pública pelo assistente de novo mercado.")
    else:
        context = {"scope": "online-reference"}
    data["external_id"] = external_id
    data["price_context"] = context
    data["price_scope_note"] = PRICE_NOTES[market.adapter_key]
    data["source"] = "admin"
    if store_id is None:
        slug = slugify(f"{data['name']} {data['city']}")[:70] or "loja"
        if db.scalar(select(Store.id).where(Store.market_id == market.id, Store.slug == slug)):
            slug = f"{slug}-{uuid.uuid4().hex[:8]}"
        store = Store(market_id=market.id, slug=slug, **data)
        db.add(store)
    else:
        existing = db.get(Store, store_id)
        if existing is None or existing.market_id != market.id:
            raise NotFound("Filial não encontrada neste mercado.")
        store = existing
        previous = store.price_context or {}
        if market.adapter_key == "angeloni":
            previous = {
                "postal_code": str(previous.get("postal_code") or store.postal_code or "").replace(
                    "-", ""
                )
            }
            if (store.price_context or {}).get("seller"):
                previous["seller"] = store.price_context["seller"]
        elif market.adapter_key in {"fort", "imperatriz"}:
            previous = {"store_id": str(previous.get("store_id") or store.external_id or "")}
        else:
            previous = context
        if previous != context and (
            db.scalar(select(Observation.id).where(Observation.store_id == store.id).limit(1))
            or db.scalar(select(RunTarget.id).where(RunTarget.store_id == store.id).limit(1))
        ):
            raise Conflict(
                "Esta filial já tem buscas registradas. Para trocar a região de preços, "
                "desative a filial e cadastre outra; o histórico deve continuar ligado à região original.",
                code="price_context_in_use",
            )
        for key, value in data.items():
            setattr(store, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("Já existe uma filial com esse identificador.") from exc
    return store


async def probe_market(data: dict[str, Any]) -> dict[str, Any]:
    """Check the actual public source; client-supplied test results are never trusted."""
    try:
        website_parts = urlsplit(public_url(data["website"]))
        website = urlunsplit(("https", website_parts.netloc, "", "", ""))
        sample_url = public_url(data["sample_url"])
        sitemap_url = public_url(data["sitemap_url"]) if data.get("sitemap_url") else None
    except FetchError as exc:
        raise ValidationFailed(str(exc), code="invalid_market_url") from exc
    if not same_site(sample_url, website) or (sitemap_url and not same_site(sitemap_url, website)):
        raise ValidationFailed(
            "Produto e índice precisam estar no mesmo domínio do site.", code="invalid_market_url"
        )
    result: dict[str, Any] = {
        "supported": False,
        "reason": "",
        "website": website,
        "sitemap_url": sitemap_url,
        "sample_name": None,
        "sample_price": None,
        "indexed_pages": 0,
        "price_scope_note": PRICE_SCOPE,
    }
    settings = get_settings().model_copy(
        update={"http_max_retries": 0, "http_timeout_seconds": 8.0}
    )
    try:
        async with (
            asyncio.timeout(35),
            PoliteClient(
                allowed_domains=[website_parts.hostname or ""],
                settings=settings,
                transport=PublicHttpsTransport(),
            ) as client,
        ):
            sample = await client.get(sample_url)
            if sample.status != 200:
                raise ParseError("A página de exemplo não está disponível publicamente.")
            if not same_site(sample.url, website):
                raise ParseError(
                    "O produto redireciona para outro domínio. "
                    "Use o domínio final do produto no site e teste novamente."
                )
            listing = parse_product(sample.text, sample.url)
            result.update(sample_name=listing.title, sample_price=listing.price)
            if not sitemap_url:
                robots = await client.get(website + "/robots.txt")
                candidates = [
                    line.split(":", 1)[1].strip()
                    for line in robots.text.splitlines()
                    if line.lower().startswith("sitemap:")
                ]
                sitemap_url = next(
                    (public_url(url) for url in candidates if same_site(url, website)),
                    website + "/sitemap.xml",
                )
            result["sitemap_url"] = sitemap_url
            index = await load_public_index(client, DocumentCache(), website, sitemap_url)
            result["indexed_pages"] = len(index)
            if not any(e.url in {public_url(sample.url), sample_url} for e in index.entries):
                raise ParseError(
                    "O produto de exemplo não foi encontrado no índice lido. Informe o sitemap de produtos; "
                    "a leitura é limitada a 6 mapas e 5.000 páginas."
                )
            result.update(
                supported=True,
                reason="Produto e preço em BRL reconhecidos. A descoberta de páginas pelo índice também funciona.",
            )
    except (FetchError, ParseError) as exc:
        result["reason"] = str(exc)
    except TimeoutError:
        result["reason"] = (
            "O teste excedeu 35 segundos. Tente o índice de produtos diretamente ou verifique o site mais tarde."
        )
    return result


async def create_market(db: Session, data: dict[str, Any]) -> Market:
    result = await probe_market(data)
    if not result["supported"]:
        raise ValidationFailed(result["reason"], code="market_not_supported")
    slug = slugify(data["name"])[:40]
    if not slug:
        raise ValidationFailed("Informe um nome com letras ou números.")
    if db.scalar(
        select(Market.id).where(
            or_(
                Market.slug == slug,
                Market.website.in_([result["website"], result["website"] + "/"]),
            )
        )
    ):
        raise Conflict("Este nome ou site já pertence a um mercado. Edite o cadastro existente.")
    market = Market(
        slug=slug,
        name=data["name"],
        website=result["website"],
        adapter_key="public_jsonld",
        allowed_domains=[urlsplit(result["website"]).hostname],
        enabled=True,
        brand_color=data["brand_color"],
        notes=PRICE_SCOPE,
    )
    db.add(market)
    try:
        db.flush()
        save_store(
            db,
            market.id,
            None,
            data["first_store"],
            public_source={
                "website": result["website"],
                "sitemap_url": result["sitemap_url"],
                "scope": "public-online-reference",
            },
        )
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("Já existe um mercado com esse nome.") from exc
    db.expire_all()
    return market


async def update_public_source(db: Session, market_id: uuid.UUID, data: dict[str, Any]) -> Market:
    market = get_market(db, market_id)
    if market.adapter_key != "public_jsonld":
        raise ValidationFailed(
            "Esta rede usa uma integração específica; sua fonte é definida em código."
        )
    try:
        requested_host = urlsplit(public_url(data["website"])).hostname
    except FetchError as exc:
        raise ValidationFailed(str(exc), code="invalid_market_url") from exc
    if requested_host != urlsplit(market.website).hostname:
        raise ValidationFailed(
            "Trocar o domínio exige cadastrar outra rede para preservar a origem do histórico."
        )
    result = await probe_market(data)
    if not result["supported"]:
        raise ValidationFailed(result["reason"], code="market_not_supported")
    for store in market.stores:
        store.price_context = {
            **(store.price_context or {}),
            "website": result["website"],
            "sitemap_url": result["sitemap_url"],
        }
    db.commit()
    return market
