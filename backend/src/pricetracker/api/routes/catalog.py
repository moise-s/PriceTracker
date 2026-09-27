from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from pricetracker.api import schemas
from pricetracker.api.deps import AdminUser, CsrfProtected, CurrentUser, DbSession
from pricetracker.api.serializers import catalog_item_out, product_out
from pricetracker.models import Candidate, Product, RunTarget
from pricetracker.models.enums import ImageSource, PinDecision
from pricetracker.seed.catalog import CATEGORIES
from pricetracker.services import catalog, images
from pricetracker.services.errors import NotFound, ValidationFailed
from pricetracker.settings import get_settings

router = APIRouter()


def _my_products(db: DbSession, user_id: uuid.UUID) -> dict[uuid.UUID, uuid.UUID]:
    rows = db.execute(
        select(Product.catalog_item_id, Product.id).where(
            Product.user_id == user_id,
            Product.catalog_item_id.is_not(None),
            Product.is_active.is_(True),
        )
    ).all()
    return {row[0]: row[1] for row in rows if row[0] is not None}


@router.get("/catalog", response_model=schemas.CatalogOut, tags=["catalog"])
def get_catalog(user: CurrentUser, db: DbSession) -> schemas.CatalogOut:
    mine = _my_products(db, user.id)
    items = [catalog_item_out(item, mine) for item in catalog.list_catalog(db)]
    return schemas.CatalogOut(categories=CATEGORIES, items=items)


@router.post(
    "/admin/catalog",
    response_model=schemas.CatalogItemOut,
    status_code=201,
    tags=["admin"],
    dependencies=[CsrfProtected],
)
def create_catalog_item(
    body: schemas.CatalogItemIn, admin: AdminUser, db: DbSession
) -> schemas.CatalogItemOut:
    data = body.model_dump(mode="python")
    for key in ("sold_by", "package_unit", "default_unit"):
        if data.get(key) is not None:
            data[key] = data[key].value if hasattr(data[key], "value") else data[key]
    item = catalog.upsert_catalog_item(db, None, data)
    return catalog_item_out(item, {})


@router.put(
    "/admin/catalog/{item_id}",
    response_model=schemas.CatalogItemOut,
    tags=["admin"],
    dependencies=[CsrfProtected],
)
def update_catalog_item(
    item_id: uuid.UUID, body: schemas.CatalogItemIn, admin: AdminUser, db: DbSession
) -> schemas.CatalogItemOut:
    item = catalog.get_catalog_item(db, item_id)
    data = body.model_dump(mode="python", exclude={"slug"})
    for key in ("sold_by", "package_unit", "default_unit"):
        if data.get(key) is not None:
            data[key] = data[key].value if hasattr(data[key], "value") else data[key]
    return catalog_item_out(catalog.upsert_catalog_item(db, item, data), {})


@router.post(
    "/admin/catalog/{item_id}/image",
    response_model=schemas.CatalogItemOut,
    tags=["admin"],
    dependencies=[CsrfProtected],
)
async def upload_catalog_image(
    item_id: uuid.UUID, admin: AdminUser, db: DbSession, file: UploadFile = File(...)
) -> schemas.CatalogItemOut:
    item = catalog.get_catalog_item(db, item_id)
    data = await _read_upload(file)
    image = images.store_image(
        db, data=data, owner_user_id=None, source=ImageSource.UPLOAD, alt_text=item.name
    )
    item.image_id = image.id
    db.commit()
    return catalog_item_out(item, {})


# --- products --------------------------------------------------------------------------------


@router.get("/products", response_model=list[schemas.ProductOut], tags=["products"])
def list_products(user: CurrentUser, db: DbSession) -> list[schemas.ProductOut]:
    return [product_out(p) for p in catalog.list_products(db, user)]


@router.post(
    "/products",
    response_model=schemas.ProductOut,
    status_code=201,
    tags=["products"],
    dependencies=[CsrfProtected],
)
def create_product(body: schemas.ProductIn, user: CurrentUser, db: DbSession) -> schemas.ProductOut:
    data = body.model_dump(mode="python")
    data["sold_by"] = data["sold_by"].value
    if data.get("package_unit") is not None:
        data["package_unit"] = data["package_unit"].value
    return product_out(catalog.create_custom_product(db, user, data))


@router.post(
    "/products/from-catalog/{catalog_item_id}",
    response_model=schemas.ProductOut,
    tags=["products"],
    dependencies=[CsrfProtected],
)
def product_from_catalog(
    catalog_item_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> schemas.ProductOut:
    return product_out(catalog.product_from_catalog(db, user, catalog_item_id))


@router.get("/products/{product_id}", response_model=schemas.ProductOut, tags=["products"])
def get_product(product_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.ProductOut:
    return product_out(catalog.get_product(db, user, product_id))


@router.patch(
    "/products/{product_id}",
    response_model=schemas.ProductOut,
    tags=["products"],
    dependencies=[CsrfProtected],
)
def update_product(
    product_id: uuid.UUID, body: schemas.ProductPatch, user: CurrentUser, db: DbSession
) -> schemas.ProductOut:
    data = body.model_dump(mode="python", exclude_unset=True)
    for key in ("sold_by", "package_unit"):
        if data.get(key) is not None:
            data[key] = data[key].value
    return product_out(catalog.update_product(db, user, product_id, data))


@router.delete(
    "/products/{product_id}",
    response_model=schemas.Ok,
    tags=["products"],
    dependencies=[CsrfProtected],
)
def delete_product(product_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.Ok:
    catalog.delete_product(db, user, product_id)
    return schemas.Ok()


async def _read_upload(file: UploadFile) -> bytes:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise ValidationFailed(
            f"A imagem excede {get_settings().max_upload_mb} MB.", code="image_too_large"
        )
    return data


@router.post(
    "/products/{product_id}/image",
    response_model=schemas.ProductOut,
    tags=["products"],
    dependencies=[CsrfProtected],
)
async def upload_product_image(
    product_id: uuid.UUID, user: CurrentUser, db: DbSession, file: UploadFile = File(...)
) -> schemas.ProductOut:
    product = catalog.get_product(db, user, product_id)
    data = await _read_upload(file)
    image = images.store_image(
        db, data=data, owner_user_id=user.id, source=ImageSource.UPLOAD, alt_text=product.name
    )
    return product_out(catalog.set_product_image(db, user, product_id, image))


@router.post(
    "/products/{product_id}/image-url",
    response_model=schemas.ProductOut,
    tags=["products"],
    dependencies=[CsrfProtected],
)
def import_product_image(
    product_id: uuid.UUID, body: schemas.ImageUrlIn, user: CurrentUser, db: DbSession
) -> schemas.ProductOut:
    product = catalog.get_product(db, user, product_id)
    data, final_url = images.fetch_image_bytes(body.url)
    image = images.store_image(
        db,
        data=data,
        owner_user_id=user.id,
        source=ImageSource.URL,
        source_url=final_url,
        attribution=body.attribution,
        alt_text=product.name,
    )
    return product_out(catalog.set_product_image(db, user, product_id, image))


@router.get(
    "/products/{product_id}/candidates",
    response_model=list[schemas.CandidateOut],
    tags=["products"],
)
def recent_candidates(
    product_id: uuid.UUID, user: CurrentUser, db: DbSession, store_id: uuid.UUID | None = None
) -> list[schemas.CandidateOut]:
    catalog.get_product(db, user, product_id)
    stmt = (
        select(RunTarget)
        .where(
            RunTarget.user_id == user.id,
            RunTarget.product_id == product_id,
            RunTarget.finished_at.is_not(None),
        )
        .order_by(RunTarget.finished_at.desc())
    )
    if store_id is not None:
        stmt = stmt.where(RunTarget.store_id == store_id)
    target = db.scalars(stmt.limit(1)).first()
    if target is None:
        return []
    rows = db.scalars(
        select(Candidate).where(Candidate.target_id == target.id).order_by(Candidate.rank)
    )
    return [schemas.CandidateOut.model_validate(c) for c in rows]


@router.post(
    "/products/{product_id}/pins",
    response_model=schemas.Ok,
    tags=["products"],
    dependencies=[CsrfProtected],
)
def pin_candidate(
    product_id: uuid.UUID, body: schemas.PinIn, user: CurrentUser, db: DbSession
) -> schemas.Ok:
    candidate = db.get(Candidate, body.candidate_id)
    target = db.get(RunTarget, candidate.target_id) if candidate else None
    if (
        candidate is None
        or target is None
        or target.user_id != user.id
        or target.product_id != product_id
    ):
        raise NotFound("Candidato não encontrado.")
    from pricetracker.domain.listing import Listing
    from pricetracker.models.enums import ExtractionMethod

    key = Listing(title=candidate.title, method=ExtractionMethod(candidate.method), url=candidate.url,
                  external_id=candidate.external_id, sku=candidate.sku).listing_key  # fmt: skip
    catalog.pin_listing(
        db,
        user,
        product_id,
        market_id=target.market_id,
        listing_key=key,
        title=candidate.title,
        decision=PinDecision(body.decision),
        external_id=candidate.external_id,
        gtin=candidate.gtin,
        url=candidate.url,
    )
    return schemas.Ok()


# --- images ------------------------------------------------------------------------------------


@router.get("/images/{image_id}", tags=["images"], response_class=FileResponse)
def get_image(image_id: uuid.UUID, user: CurrentUser, db: DbSession) -> FileResponse:
    image = images.get_visible_image(db, image_id, user.id)
    path = images.image_path(image)
    if not path.is_file():
        raise NotFound("Arquivo da imagem não encontrado.")
    headers = {
        "Cache-Control": "private, max-age=86400",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    }
    return FileResponse(path, media_type=image.content_type, headers=headers)
