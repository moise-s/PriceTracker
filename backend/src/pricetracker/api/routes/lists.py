from __future__ import annotations

import uuid

from fastapi import APIRouter

from pricetracker.api import schemas
from pricetracker.api.deps import CsrfProtected, CurrentUser, DbSession
from pricetracker.api.serializers import list_item_out, list_out
from pricetracker.services import catalog
from pricetracker.services.errors import ValidationFailed

router = APIRouter(tags=["lists"])


@router.get("/lists", response_model=list[schemas.ShoppingListOut])
def get_lists(
    user: CurrentUser, db: DbSession, include_archived: bool = False
) -> list[schemas.ShoppingListOut]:
    catalog.default_list(db, user)
    return [list_out(sl) for sl in catalog.list_lists(db, user, include_archived)]


@router.post(
    "/lists", response_model=schemas.ShoppingListOut, status_code=201, dependencies=[CsrfProtected]
)
def create_list(body: schemas.ListIn, user: CurrentUser, db: DbSession) -> schemas.ShoppingListOut:
    shopping_list = catalog.create_list(db, user, body.name, body.copy_from)
    db.refresh(shopping_list)
    return list_out(shopping_list)


@router.get("/lists/{list_id}", response_model=schemas.ShoppingListOut)
def get_list(list_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.ShoppingListOut:
    return list_out(catalog.get_list(db, user, list_id))


@router.patch(
    "/lists/{list_id}", response_model=schemas.ShoppingListOut, dependencies=[CsrfProtected]
)
def update_list(
    list_id: uuid.UUID, body: schemas.ListPatch, user: CurrentUser, db: DbSession
) -> schemas.ShoppingListOut:
    shopping_list = catalog.update_list(
        db, user, list_id, name=body.name, is_default=body.is_default, archived=body.archived
    )
    return list_out(shopping_list)


@router.delete("/lists/{list_id}", response_model=schemas.Ok, dependencies=[CsrfProtected])
def delete_list(list_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.Ok:
    catalog.delete_list(db, user, list_id)
    return schemas.Ok()


@router.post(
    "/lists/{list_id}/items",
    response_model=schemas.ListItemOut,
    status_code=201,
    dependencies=[CsrfProtected],
)
def add_item(
    list_id: uuid.UUID, body: schemas.ListItemIn, user: CurrentUser, db: DbSession
) -> schemas.ListItemOut:
    if body.product_id is None and body.catalog_item_id is None:
        raise ValidationFailed(
            "Informe um produto ou um item do catálogo.", code="product_required"
        )
    product_id = body.product_id
    quantity = body.quantity
    if product_id is None:
        assert body.catalog_item_id is not None
        catalog_item = catalog.get_catalog_item(db, body.catalog_item_id)
        # A catalog card omits quantity; use its starting amount in the same unit.
        # An explicitly chosen different unit keeps the request's default of one.
        if "quantity" not in body.model_fields_set and (
            body.unit is None or body.unit.value == catalog_item.default_unit
        ):
            quantity = catalog_item.default_quantity
        product_id = catalog.product_from_catalog(db, user, body.catalog_item_id).id
    item = catalog.upsert_list_item(
        db,
        user,
        list_id,
        product_id=product_id,
        quantity=quantity,
        unit=body.unit.value if body.unit else None,
        notes=body.notes,
    )
    db.refresh(item)
    return list_item_out(item)


@router.patch(
    "/lists/{list_id}/items/{item_id}",
    response_model=schemas.ListItemOut,
    dependencies=[CsrfProtected],
)
def update_item(
    list_id: uuid.UUID,
    item_id: uuid.UUID,
    body: schemas.ListItemPatch,
    user: CurrentUser,
    db: DbSession,
) -> schemas.ListItemOut:
    data = body.model_dump(mode="python", exclude_unset=True)
    if data.get("unit") is not None:
        data["unit"] = data["unit"].value
    return list_item_out(catalog.update_list_item(db, user, list_id, item_id, data))


@router.delete(
    "/lists/{list_id}/items/{item_id}", response_model=schemas.Ok, dependencies=[CsrfProtected]
)
def delete_item(
    list_id: uuid.UUID, item_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> schemas.Ok:
    catalog.delete_list_item(db, user, list_id, item_id)
    return schemas.Ok()
