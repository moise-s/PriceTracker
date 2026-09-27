from __future__ import annotations

import uuid

from fastapi import APIRouter

from pricetracker.api import schemas
from pricetracker.api.deps import CsrfProtected, CurrentUser, DbSession
from pricetracker.services import alerts, profile

router = APIRouter(tags=["alerts"])


def _alert_out(view: alerts.AlertView) -> schemas.AlertOut:
    return schemas.AlertOut(
        product_id=view.product.id,
        product_name=view.product.name,
        unit_label=alerts.unit_label(view.product),
        target_price=view.alert.target_price,
        enabled=view.alert.enabled,
        last_triggered_at=view.alert.last_triggered_at,
        best_price=view.best_price,
        best_store=view.best_store,
        best_observed_at=view.best_observed_at,
    )


def _views(db: DbSession, user: CurrentUser) -> list[alerts.AlertView]:
    return alerts.list_alerts(db, user, profile.get_profile(db, user).freshness_days)


@router.get("/alerts", response_model=list[schemas.AlertOut])
def list_alerts(user: CurrentUser, db: DbSession) -> list[schemas.AlertOut]:
    """Price alerts with the best fresh price seen for each product."""
    return [_alert_out(view) for view in _views(db, user)]


@router.put(
    "/products/{product_id}/alert", response_model=schemas.AlertOut, dependencies=[CsrfProtected]
)
def set_alert(
    product_id: uuid.UUID, body: schemas.AlertIn, user: CurrentUser, db: DbSession
) -> schemas.AlertOut:
    alerts.upsert_alert(db, user, product_id, body.target_price, body.enabled)
    return next(_alert_out(v) for v in _views(db, user) if v.product.id == product_id)


@router.delete(
    "/products/{product_id}/alert", response_model=schemas.Ok, dependencies=[CsrfProtected]
)
def delete_alert(product_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.Ok:
    alerts.delete_alert(db, user, product_id)
    return schemas.Ok()


@router.get("/notifications", response_model=schemas.NotificationsOut)
def notifications(user: CurrentUser, db: DbSession) -> schemas.NotificationsOut:
    return schemas.NotificationsOut(
        unread=alerts.unread_count(db, user),
        items=[
            schemas.NotificationOut.model_validate(n) for n in alerts.list_notifications(db, user)
        ],
    )


@router.post("/notifications/read", response_model=schemas.MarkedOut, dependencies=[CsrfProtected])
def mark_read(body: schemas.MarkReadIn, user: CurrentUser, db: DbSession) -> schemas.MarkedOut:
    return schemas.MarkedOut(marked=alerts.mark_read(db, user, body.ids))
