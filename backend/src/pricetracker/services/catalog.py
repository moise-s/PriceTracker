"""Global catalog (admin-curated), personal products and shopping lists.

Every function that touches user data takes the acting user and filters by
``user_id``; nothing here trusts identifiers coming from the client.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from pricetracker.db.base import utcnow
from pricetracker.domain.matching import MatchSpec
from pricetracker.models import (
    CatalogItem,
    Image,
    ListItem,
    Observation,
    Product,
    ProductMarketPin,
    ShoppingList,
    User,
)
from pricetracker.models.enums import PinDecision, SoldBy, Unit
from pricetracker.services import images as image_service
from pricetracker.services.errors import Conflict, NotFound, ValidationFailed

# --- match spec helpers -------------------------------------------------------------


def validate_match_spec(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        spec = MatchSpec.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailed(
            "Regra de busca inválida.",
            code="invalid_match_spec",
            details=exc.errors(include_url=False),
        ) from exc
    return spec.model_dump(mode="json", exclude_none=True)


def product_match_spec(product: Product) -> MatchSpec:
    """Effective rules: the product's own spec plus its preferences."""
    base: dict[str, Any] = dict(product.match_spec or {})
    if not base.get("search_terms"):
        base["search_terms"] = [product.name]
    base["sold_by"] = product.sold_by
    if (
        product.sold_by == SoldBy.PACKAGE.value
        and product.package_quantity
        and product.package_unit
    ):
        size = dict(base.get("size") or {})
        size["quantity"] = str(product.package_quantity)
        size["unit"] = product.package_unit
        size["tolerance_pct"] = str(product.size_tolerance_pct or Decimal("0"))
        base["size"] = size
    brands = list(base.get("brands") or [])
    if product.preferred_brand and product.preferred_brand not in brands:
        brands.insert(0, product.preferred_brand)
    extra = (product.substitutions or {}).get("brands") or []
    for brand in extra:
        if brand not in brands:
            brands.append(brand)
    base["brands"] = brands
    base["strict_brand"] = bool(product.strict_brand and brands)
    excluded = list(base.get("excluded") or [])
    for word in (product.substitutions or {}).get("excluded_words") or []:
        if word not in excluded:
            excluded.append(word)
    base["excluded"] = excluded
    if base.get("comparison_unit") == "m" and (
        product.sold_by != SoldBy.PACKAGE.value or product.package_unit != Unit.M.value
    ):
        raise ValidationFailed(
            "Comparação por metro exige uma embalagem medida em metros.", code="invalid_unit"
        )
    return MatchSpec.model_validate(base)


# --- catalog -----------------------------------------------------------------------


def list_catalog(db: Session, include_inactive: bool = False) -> list[CatalogItem]:
    stmt = select(CatalogItem).options(selectinload(CatalogItem.image))
    if not include_inactive:
        stmt = stmt.where(CatalogItem.is_active.is_(True))
    return list(
        db.scalars(stmt.order_by(CatalogItem.category, CatalogItem.sort_order, CatalogItem.name))
    )


def get_catalog_item(db: Session, item_id: uuid.UUID) -> CatalogItem:
    item = db.get(CatalogItem, item_id)
    if item is None:
        raise NotFound("Item do catálogo não encontrado.")
    return item


def upsert_catalog_item(db: Session, item: CatalogItem | None, data: dict[str, Any]) -> CatalogItem:
    if "match_spec" in data and data["match_spec"] is not None:
        data["match_spec"] = validate_match_spec(data["match_spec"])
    if item is None:
        if db.scalar(select(func.count()).where(CatalogItem.slug == data["slug"])):
            raise Conflict("Já existe um item com este identificador.", code="slug_taken")
        item = CatalogItem(**data)
        db.add(item)
    else:
        for key, value in data.items():
            setattr(item, key, value)
    db.commit()
    return item


# --- products ------------------------------------------------------------------------


def list_products(db: Session, user: User, include_inactive: bool = True) -> list[Product]:
    stmt = (
        select(Product)
        .where(Product.user_id == user.id)
        .options(
            selectinload(Product.image),
            selectinload(Product.catalog_item).selectinload(CatalogItem.image),
        )
    )
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    return list(db.scalars(stmt.order_by(Product.category, Product.name)))


def get_product(db: Session, user: User, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.user_id != user.id:
        raise NotFound("Produto não encontrado.")
    return product


def product_from_catalog(db: Session, user: User, catalog_item_id: uuid.UUID) -> Product:
    item = get_catalog_item(db, catalog_item_id)
    existing = db.scalar(
        select(Product).where(Product.user_id == user.id, Product.catalog_item_id == item.id)
    )
    if existing is not None:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
        return existing
    spec = dict(item.match_spec or {})
    size = spec.get("size") or {}
    product = Product(
        user_id=user.id,
        catalog_item_id=item.id,
        name=item.name,
        category=item.category,
        sold_by=item.sold_by,
        package_quantity=item.package_quantity,
        package_unit=item.package_unit,
        preferred_brand=item.brand,
        strict_brand=bool(spec.get("strict_brand")),
        size_tolerance_pct=Decimal(str(size.get("tolerance_pct", "0"))),
        match_spec=spec,
        image_id=item.image_id,
    )
    db.add(product)
    db.commit()
    return product


def _validate_product_fields(data: dict[str, Any]) -> None:
    sold_by = data.get("sold_by")
    if sold_by == SoldBy.PACKAGE.value:
        if not data.get("package_quantity") or not data.get("package_unit"):
            raise ValidationFailed(
                "Informe o tamanho da embalagem (ex.: 1 kg, 400 g, 30 unidades).",
                code="package_required",
            )
    if data.get("package_unit") and data["package_unit"] not in {u.value for u in Unit}:
        raise ValidationFailed("Unidade de embalagem inválida.", code="invalid_unit")


def create_custom_product(db: Session, user: User, data: dict[str, Any]) -> Product:
    _validate_product_fields(data)
    spec = data.pop("match_spec", None) or {}
    if not spec.get("search_terms"):
        spec["search_terms"] = [data["name"]]
    spec.setdefault("sold_by", data["sold_by"])
    product = Product(user_id=user.id, match_spec=validate_match_spec(spec), **data)
    product_match_spec(product)
    db.add(product)
    db.commit()
    return product


def update_product(db: Session, user: User, product_id: uuid.UUID, data: dict[str, Any]) -> Product:
    product = get_product(db, user, product_id)
    merged = {
        "sold_by": data.get("sold_by", product.sold_by),
        "package_quantity": data.get("package_quantity", product.package_quantity),
        "package_unit": data.get("package_unit", product.package_unit),
    }
    _validate_product_fields(merged)
    if "match_spec" in data and data["match_spec"] is not None:
        spec = data["match_spec"]
        spec.setdefault("sold_by", merged["sold_by"])
        data["match_spec"] = validate_match_spec(spec)
    for key, value in data.items():
        setattr(product, key, value)
    product_match_spec(product)  # raises if the combination is invalid
    db.commit()
    return product


def delete_product(db: Session, user: User, product_id: uuid.UUID) -> None:
    product = get_product(db, user, product_id)
    image = product.image
    db.delete(product)
    db.flush()
    if image is not None and image.owner_user_id == user.id:
        still_used = db.scalar(select(func.count()).where(Product.image_id == image.id))
        if not still_used:
            image_service.delete_image_file(image)
            db.delete(image)
    db.commit()


def set_product_image(db: Session, user: User, product_id: uuid.UUID, image: Image) -> Product:
    product = get_product(db, user, product_id)
    previous = product.image
    # Assign the relationship (not just the FK) so the returned object reflects the new image;
    # sessions use expire_on_commit=False, so a stale loaded relationship would survive commit.
    product.image = image
    db.flush()
    if previous is not None and previous.owner_user_id == user.id and previous.id != image.id:
        still_used = db.scalar(select(func.count()).where(Product.image_id == previous.id))
        if not still_used:
            image_service.delete_image_file(previous)
            db.delete(previous)
    db.commit()
    return product


def product_observation_count(db: Session, user: User, product_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count()).where(
                Observation.user_id == user.id, Observation.product_id == product_id
            )
        )
        or 0
    )


def pin_listing(
    db: Session,
    user: User,
    product_id: uuid.UUID,
    *,
    market_id: uuid.UUID,
    listing_key: str,
    title: str,
    decision: PinDecision,
    external_id: str | None,
    gtin: str | None,
    url: str | None,
) -> ProductMarketPin:
    get_product(db, user, product_id)
    pin = db.scalar(
        select(ProductMarketPin).where(
            ProductMarketPin.product_id == product_id,
            ProductMarketPin.market_id == market_id,
            ProductMarketPin.listing_key == listing_key,
        )
    )
    if pin is None:
        pin = ProductMarketPin(
            user_id=user.id,
            product_id=product_id,
            market_id=market_id,
            listing_key=listing_key,
            title=title[:300],
            external_id=external_id,
            gtin=gtin,
            url=url,
            decision=decision.value,
        )
        db.add(pin)
    else:
        pin.decision = decision.value
    db.commit()
    return pin


def pins_for(
    db: Session, user_id: uuid.UUID, product_id: uuid.UUID, market_id: uuid.UUID
) -> list[ProductMarketPin]:
    return list(
        db.scalars(
            select(ProductMarketPin).where(
                ProductMarketPin.user_id == user_id,
                ProductMarketPin.product_id == product_id,
                ProductMarketPin.market_id == market_id,
            )
        )
    )


# --- lists --------------------------------------------------------------------------------


def list_lists(db: Session, user: User, include_archived: bool = False) -> list[ShoppingList]:
    stmt = (
        select(ShoppingList)
        .where(ShoppingList.user_id == user.id)
        .options(selectinload(ShoppingList.items).selectinload(ListItem.product))
    )
    if not include_archived:
        stmt = stmt.where(ShoppingList.archived_at.is_(None))
    return list(db.scalars(stmt.order_by(ShoppingList.is_default.desc(), ShoppingList.created_at)))


def get_list(db: Session, user: User, list_id: uuid.UUID) -> ShoppingList:
    shopping_list = db.get(ShoppingList, list_id)
    if shopping_list is None or shopping_list.user_id != user.id:
        raise NotFound("Lista não encontrada.")
    return shopping_list


def default_list(db: Session, user: User) -> ShoppingList:
    found = db.scalar(
        select(ShoppingList).where(
            ShoppingList.user_id == user.id,
            ShoppingList.is_default.is_(True),
            ShoppingList.archived_at.is_(None),
        )
    )
    if found is None:
        found = ShoppingList(user_id=user.id, name="Minha lista", is_default=True)
        db.add(found)
        db.commit()
    return found


def create_list(
    db: Session, user: User, name: str, copy_from: uuid.UUID | None = None
) -> ShoppingList:
    shopping_list = ShoppingList(user_id=user.id, name=name.strip()[:80] or "Nova lista")
    db.add(shopping_list)
    db.flush()
    if copy_from is not None:
        source = get_list(db, user, copy_from)
        for item in source.items:
            db.add(
                ListItem(
                    list_id=shopping_list.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit=item.unit,
                    notes=item.notes,
                    position=item.position,
                )
            )
    db.commit()
    return shopping_list


def update_list(
    db: Session,
    user: User,
    list_id: uuid.UUID,
    *,
    name: str | None,
    is_default: bool | None,
    archived: bool | None,
) -> ShoppingList:
    shopping_list = get_list(db, user, list_id)
    if name is not None:
        shopping_list.name = name.strip()[:80] or shopping_list.name
    if is_default:
        for other in db.scalars(select(ShoppingList).where(ShoppingList.user_id == user.id)):
            other.is_default = other.id == shopping_list.id
    if archived is not None:
        shopping_list.archived_at = utcnow() if archived else None
    db.commit()
    return shopping_list


def delete_list(db: Session, user: User, list_id: uuid.UUID) -> None:
    shopping_list = get_list(db, user, list_id)
    if shopping_list.is_default:
        raise Conflict("A lista principal não pode ser excluída.", code="default_list")
    db.delete(shopping_list)
    db.commit()


def _allowed_units(product: Product) -> set[str]:
    if product.sold_by == SoldBy.WEIGHT.value:
        units = {Unit.KG.value, Unit.G.value}
        spec = product.match_spec or {}
        if spec.get("approx_unit_weight_kg"):
            units.add(Unit.UN.value)
        return units
    if product.sold_by == SoldBy.UNIT.value:
        return {Unit.UN.value}
    units = {Unit.PCT.value}
    if product.package_unit in (Unit.KG.value, Unit.G.value):
        units |= {Unit.KG.value, Unit.G.value}
    elif product.package_unit in (Unit.L.value, Unit.ML.value):
        units |= {Unit.L.value, Unit.ML.value}
    elif product.package_unit == Unit.M.value:
        units.add(Unit.M.value)
    elif product.package_unit == Unit.UN.value:
        units.add(Unit.UN.value)
    return units


def default_unit_for(product: Product) -> str:
    if (
        product.sold_by == SoldBy.PACKAGE.value
        and product.package_unit == Unit.M.value
        and (product.match_spec or {}).get("comparison_unit") == "m"
    ):
        return Unit.M.value
    if product.sold_by == SoldBy.WEIGHT.value:
        return Unit.KG.value
    if product.sold_by == SoldBy.UNIT.value:
        return Unit.UN.value
    return Unit.PCT.value


def upsert_list_item(
    db: Session,
    user: User,
    list_id: uuid.UUID,
    *,
    product_id: uuid.UUID,
    quantity: Decimal,
    unit: str | None,
    notes: str | None = None,
) -> ListItem:
    shopping_list = get_list(db, user, list_id)
    product = get_product(db, user, product_id)
    unit = unit or default_unit_for(product)
    if unit not in _allowed_units(product):
        raise ValidationFailed(
            f"Unidade '{unit}' não combina com este produto.",
            code="invalid_unit",
            details={"allowed": sorted(_allowed_units(product))},
        )
    if quantity <= 0 or quantity > 1000:
        raise ValidationFailed("Quantidade deve estar entre 0 e 1000.", code="invalid_quantity")
    item = db.scalar(
        select(ListItem).where(
            ListItem.list_id == shopping_list.id, ListItem.product_id == product.id
        )
    )
    if item is None:
        position = db.scalar(
            select(func.coalesce(func.max(ListItem.position), -1)).where(
                ListItem.list_id == shopping_list.id
            )
        )
        item = ListItem(
            list_id=shopping_list.id,
            product_id=product.id,
            quantity=quantity,
            unit=unit,
            notes=notes,
            position=int(position or 0) + 1,
        )
        db.add(item)
    else:
        item.quantity = quantity
        item.unit = unit
        if notes is not None:
            item.notes = notes
    db.commit()
    return item


def get_list_item(db: Session, user: User, list_id: uuid.UUID, item_id: uuid.UUID) -> ListItem:
    shopping_list = get_list(db, user, list_id)
    item = db.get(ListItem, item_id)
    if item is None or item.list_id != shopping_list.id:
        raise NotFound("Item não encontrado.")
    return item


def update_list_item(
    db: Session, user: User, list_id: uuid.UUID, item_id: uuid.UUID, data: dict[str, Any]
) -> ListItem:
    item = get_list_item(db, user, list_id, item_id)
    if (
        "unit" in data
        and data["unit"] is not None
        and data["unit"] not in _allowed_units(item.product)
    ):
        raise ValidationFailed("Unidade não combina com este produto.", code="invalid_unit")
    if (
        "quantity" in data
        and data["quantity"] is not None
        and not (Decimal("0") < data["quantity"] <= Decimal("1000"))
    ):
        raise ValidationFailed("Quantidade deve estar entre 0 e 1000.", code="invalid_quantity")
    if "checked" in data:
        item.checked_at = utcnow() if data.pop("checked") else None
    for key, value in data.items():
        if value is not None or key == "notes":
            setattr(item, key, value)
    db.commit()
    return item


def delete_list_item(db: Session, user: User, list_id: uuid.UUID, item_id: uuid.UUID) -> None:
    item = get_list_item(db, user, list_id, item_id)
    db.delete(item)
    db.commit()


def allowed_units(product: Product) -> list[str]:
    order = [u.value for u in (Unit.PCT, Unit.UN, Unit.KG, Unit.G, Unit.L, Unit.ML, Unit.M)]
    return [u for u in order if u in _allowed_units(product)]
