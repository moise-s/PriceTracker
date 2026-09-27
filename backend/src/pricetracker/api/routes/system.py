from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from pricetracker import __version__
from pricetracker.api import schemas
from pricetracker.api.deps import DbSession
from pricetracker.services import accounts, app_settings
from pricetracker.settings import get_settings

router = APIRouter(tags=["system"])


@router.get("/health/live", response_model=schemas.Ok)
def live() -> schemas.Ok:
    return schemas.Ok()


@router.get("/health/ready", response_model=schemas.HealthOut)
def ready(db: DbSession) -> schemas.HealthOut:
    try:
        db.execute(text("SELECT 1"))
        version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        return schemas.HealthOut(status="ok", database=True, schema_version=version)
    except Exception:
        return schemas.HealthOut(status="degraded", database=False)


@router.get("/meta", response_model=schemas.MetaOut)
def meta(db: DbSession) -> schemas.MetaOut:
    settings = get_settings()
    status = accounts.setup_status(db)
    return schemas.MetaOut(
        version=__version__,
        environment=settings.environment,
        timezone=settings.timezone,
        default_freshness_days=int(app_settings.get_value(db, "default_freshness_days")),
        registration_enabled=bool(app_settings.get_value(db, "registration_enabled")),
        needs_setup=status["needs_setup"],
        requires_setup_code=status["requires_code"],
        geocoder=settings.geocoder,
        router=settings.router,
    )
