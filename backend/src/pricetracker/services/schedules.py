"""Recurring searches (per user)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pricetracker.db.base import utcnow
from pricetracker.models import Schedule, Store, User
from pricetracker.models.enums import ScheduleFrequency
from pricetracker.scheduler.main import next_occurrence
from pricetracker.services import catalog
from pricetracker.services.errors import NotFound, ValidationFailed

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def list_schedules(db: Session, user: User) -> list[Schedule]:
    return list(
        db.scalars(
            select(Schedule).where(Schedule.user_id == user.id).order_by(Schedule.created_at)
        )
    )


def get_schedule(db: Session, user: User, schedule_id: uuid.UUID) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None or schedule.user_id != user.id:
        raise NotFound("Agendamento não encontrado.")
    return schedule


def save_schedule(
    db: Session, user: User, schedule_id: uuid.UUID | None, data: dict[str, Any]
) -> Schedule:
    if data.get("list_id") is not None:
        catalog.get_list(db, user, data["list_id"])
    if data.get("time_local") is not None and not TIME_RE.match(data["time_local"]):
        raise ValidationFailed("Horário inválido (use HH:MM).", code="invalid_time")
    frequency = data.get("frequency")
    if frequency is not None and frequency not in {f.value for f in ScheduleFrequency}:
        raise ValidationFailed("Frequência inválida.", code="invalid_frequency")
    if data.get("store_ids") is not None:
        ids = [uuid.UUID(str(s)) for s in data["store_ids"]]
        found = set(
            db.scalars(select(Store.id).where(Store.id.in_(ids), Store.is_active.is_(True)))
        )
        if found != set(ids):
            raise ValidationFailed("Loja inválida no agendamento.", code="invalid_store")
        data["store_ids"] = [str(i) for i in ids]
    if schedule_id is None:
        if data.get("list_id") is None:
            data["list_id"] = catalog.default_list(db, user).id
        schedule = Schedule(user_id=user.id, **data)
        db.add(schedule)
    else:
        schedule = get_schedule(db, user, schedule_id)
        for key, value in data.items():
            if value is not None:
                setattr(schedule, key, value)
    if schedule.frequency == ScheduleFrequency.WEEKLY.value and schedule.weekday is None:
        raise ValidationFailed("Escolha o dia da semana.", code="weekday_required")
    schedule.next_run_at = next_occurrence(schedule, utcnow()) if schedule.enabled else None
    db.commit()
    return schedule


def delete_schedule(db: Session, user: User, schedule_id: uuid.UUID) -> None:
    db.delete(get_schedule(db, user, schedule_id))
    db.commit()
