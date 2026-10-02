"""Model -> response helpers shared by routers."""

from __future__ import annotations

import uuid
from typing import Any

from pricetracker.api import schemas
from pricetracker.models import CatalogItem, Image, ListItem, Product, Schedule, ShoppingList, User
from pricetracker.models.enums import SoldBy
from pricetracker.services import catalog


def image_ref(image: Image | None) -> schemas.ImageRef | None:
    if image is None:
        return None
    return schemas.ImageRef(
        id=image.id,
        url=f"/api/v1/images/{image.id}",
        alt_text=image.alt_text,
        source=image.source,
        attribution=image.attribution,
        license=image.license,
    )


def user_out(user: User) -> schemas.UserOut:
    return schemas.UserOut.model_validate(user)


def catalog_item_out(
    item: CatalogItem, my_products: dict[uuid.UUID, uuid.UUID]
) -> schemas.CatalogItemOut:
    return schemas.CatalogItemOut(
        id=item.id,
        slug=item.slug,
        name=item.name,
        category=item.category,
        description=item.description,
        sold_by=SoldBy(item.sold_by),
        package_quantity=item.package_quantity,
        package_unit=item.package_unit,
        default_quantity=item.default_quantity,
        default_unit=item.default_unit,
        brand=item.brand,
        match_spec=item.match_spec or {},
        image=image_ref(item.image),
        is_active=item.is_active,
        in_my_products=item.id in my_products,
        my_product_id=my_products.get(item.id),
    )


def product_out(product: Product) -> schemas.ProductOut:
    return schemas.ProductOut(
        id=product.id,
        catalog_item_id=product.catalog_item_id,
        name=product.name,
        category=product.category,
        sold_by=SoldBy(product.sold_by),
        package_quantity=product.package_quantity,
        package_unit=product.package_unit,
        preferred_brand=product.preferred_brand,
        strict_brand=product.strict_brand,
        size_tolerance_pct=product.size_tolerance_pct,
        substitutions=product.substitutions or {},
        match_spec=product.match_spec or {},
        image=image_ref(product.image),
        is_active=product.is_active,
        is_favorite=product.is_favorite,
        is_custom=product.catalog_item_id is None,
        allowed_units=catalog.allowed_units(product),
        default_unit=catalog.default_unit_for(product),
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def list_item_out(item: ListItem) -> schemas.ListItemOut:
    product = item.product
    return schemas.ListItemOut(
        id=item.id,
        product_id=product.id,
        product_name=product.name,
        category=product.category,
        image=image_ref(product.image),
        quantity=item.quantity,
        unit=item.unit,
        allowed_units=catalog.allowed_units(product),
        notes=item.notes,
        position=item.position,
        checked=item.checked_at is not None,
    )


def list_out(shopping_list: ShoppingList) -> schemas.ShoppingListOut:
    items = [list_item_out(i) for i in shopping_list.items]
    return schemas.ShoppingListOut(
        id=shopping_list.id,
        name=shopping_list.name,
        is_default=shopping_list.is_default,
        archived=shopping_list.archived_at is not None,
        item_count=len(items),
        items=items,
        updated_at=shopping_list.updated_at,
    )


def schedule_out(schedule: Schedule) -> schemas.ScheduleOut:
    return schemas.ScheduleOut(
        id=schedule.id,
        name=schedule.name,
        list_id=schedule.list_id,
        frequency=schedule.frequency,
        weekday=schedule.weekday,
        time_local=schedule.time_local,
        timezone=schedule.timezone,
        store_ids=[uuid.UUID(s) for s in schedule.store_ids or []],
        enabled=schedule.enabled,
        next_run_at=schedule.next_run_at,
        last_run_at=schedule.last_run_at,
        last_run_id=schedule.last_run_id,
    )


def jsonable(value: Any) -> Any:
    return value
