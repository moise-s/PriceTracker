from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from pricetracker.api import schemas
from pricetracker.api.deps import AdminUser, CsrfProtected, CurrentUser, DbSession
from pricetracker.api.serializers import schedule_out, user_out
from pricetracker.models.enums import Role
from pricetracker.services import accounts, admin, app_settings, llm_admin, schedules

router = APIRouter()


# --- schedules (per user) -----------------------------------------------------------------------


@router.get("/schedules", response_model=list[schemas.ScheduleOut], tags=["schedules"])
def list_schedules(user: CurrentUser, db: DbSession) -> list[schemas.ScheduleOut]:
    return [schedule_out(s) for s in schedules.list_schedules(db, user)]


@router.post(
    "/schedules",
    response_model=schemas.ScheduleOut,
    status_code=201,
    tags=["schedules"],
    dependencies=[CsrfProtected],
)
def create_schedule(
    body: schemas.ScheduleIn, user: CurrentUser, db: DbSession
) -> schemas.ScheduleOut:
    data = body.model_dump()
    data["timezone"] = "America/Sao_Paulo"
    return schedule_out(schedules.save_schedule(db, user, None, data))


@router.put(
    "/schedules/{schedule_id}",
    response_model=schemas.ScheduleOut,
    tags=["schedules"],
    dependencies=[CsrfProtected],
)
def update_schedule(
    schedule_id: uuid.UUID, body: schemas.ScheduleIn, user: CurrentUser, db: DbSession
) -> schemas.ScheduleOut:
    return schedule_out(schedules.save_schedule(db, user, schedule_id, body.model_dump()))


@router.delete(
    "/schedules/{schedule_id}",
    response_model=schemas.Ok,
    tags=["schedules"],
    dependencies=[CsrfProtected],
)
def delete_schedule(schedule_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.Ok:
    schedules.delete_schedule(db, user, schedule_id)
    return schemas.Ok()


# --- admin ----------------------------------------------------------------------------------------


def _settings_out(db: DbSession) -> schemas.AdminSettingsOut:
    values = app_settings.public_settings(db)
    return schemas.AdminSettingsOut(
        registration_enabled=bool(values["registration_enabled"]),
        default_freshness_days=int(values["default_freshness_days"]),
        llm_enabled=bool(values["llm_enabled"]),
        llm_max_calls_per_run=int(values["llm_max_calls_per_run"]),
    )


@router.get("/admin/settings", response_model=schemas.AdminSettingsOut, tags=["admin"])
def get_settings_admin(admin_user: AdminUser, db: DbSession) -> schemas.AdminSettingsOut:
    return _settings_out(db)


@router.patch(
    "/admin/settings",
    response_model=schemas.AdminSettingsOut,
    tags=["admin"],
    dependencies=[CsrfProtected],
)
def update_settings(
    body: schemas.AdminSettingsPatch, admin_user: AdminUser, db: DbSession
) -> schemas.AdminSettingsOut:
    for key, value in body.model_dump(exclude_unset=True).items():
        app_settings.set_value(db, key, value, admin_user.id)
    db.commit()
    return _settings_out(db)


@router.get("/admin/users", response_model=list[schemas.UserOut], tags=["admin"])
def list_users(admin_user: AdminUser, db: DbSession) -> list[schemas.UserOut]:
    return [user_out(u) for u in admin.list_users(db)]


@router.post(
    "/admin/users",
    response_model=schemas.AccountCreatedOut,
    status_code=201,
    tags=["admin"],
    dependencies=[CsrfProtected],
)
def create_user(
    body: schemas.AdminUserIn, admin_user: AdminUser, db: DbSession
) -> schemas.AccountCreatedOut:
    account = accounts.admin_create_user(
        db,
        username=body.username,
        display_name=body.display_name,
        temporary_password=body.temporary_password,
        role=body.role,
    )
    return schemas.AccountCreatedOut(
        user=user_out(account.user), recovery_codes=account.recovery_codes
    )


@router.patch(
    "/admin/users/{user_id}",
    response_model=schemas.UserOut,
    tags=["admin"],
    dependencies=[CsrfProtected],
)
def update_user(
    user_id: uuid.UUID, body: schemas.AdminUserPatch, admin_user: AdminUser, db: DbSession
) -> schemas.UserOut:
    user = accounts.admin_update_user(
        db, admin_user, user_id=user_id, is_active=body.is_active, role=body.role
    )
    return user_out(user)


@router.post(
    "/admin/users/{user_id}/reset-password",
    response_model=schemas.Ok,
    tags=["admin"],
    dependencies=[CsrfProtected],
)
def reset_password(
    user_id: uuid.UUID, body: schemas.AdminResetPasswordIn, admin_user: AdminUser, db: DbSession
) -> schemas.Ok:
    accounts.admin_reset_password(db, user_id=user_id, temporary_password=body.temporary_password)
    return schemas.Ok()


@router.get("/admin/health", response_model=schemas.AdminHealthOut, tags=["admin"])
def adapter_health(admin_user: AdminUser, db: DbSession, days: int = 14) -> dict[str, Any]:
    return {
        "markets": admin.adapter_health(db, days=min(max(days, 1), 90)),
        "llm": llm_admin.usage_summary(db),
    }


@router.get("/admin/llm-providers", response_model=list[schemas.LlmProviderOut], tags=["admin"])
def list_providers(admin_user: AdminUser, db: DbSession) -> list[schemas.LlmProviderOut]:
    return [
        schemas.LlmProviderOut(**llm_admin.provider_view(p)) for p in llm_admin.list_providers(db)
    ]


@router.post(
    "/admin/llm-providers",
    response_model=schemas.LlmProviderOut,
    status_code=201,
    tags=["admin"],
    dependencies=[CsrfProtected],
)
def create_provider(
    body: schemas.LlmProviderIn, admin_user: AdminUser, db: DbSession
) -> schemas.LlmProviderOut:
    data = body.model_dump(exclude_unset=True)
    for required in ("name", "kind", "base_url", "model"):
        if not data.get(required):
            from pricetracker.services.errors import ValidationFailed

            raise ValidationFailed(f"Campo obrigatório: {required}.", code="missing_field")
    return schemas.LlmProviderOut(
        **llm_admin.provider_view(llm_admin.save_provider(db, None, data))
    )


@router.patch(
    "/admin/llm-providers/{provider_id}",
    response_model=schemas.LlmProviderOut,
    tags=["admin"],
    dependencies=[CsrfProtected],
)
def update_provider(
    provider_id: uuid.UUID, body: schemas.LlmProviderIn, admin_user: AdminUser, db: DbSession
) -> schemas.LlmProviderOut:
    row = llm_admin.save_provider(db, provider_id, body.model_dump(exclude_unset=True))
    return schemas.LlmProviderOut(**llm_admin.provider_view(row))


@router.post(
    "/admin/llm-providers/{provider_id}/test",
    response_model=schemas.LlmTestOut,
    tags=["admin"],
    dependencies=[CsrfProtected],
)
def test_provider(
    provider_id: uuid.UUID, admin_user: AdminUser, db: DbSession
) -> schemas.LlmTestOut:
    return schemas.LlmTestOut(**llm_admin.test_provider(db, provider_id))


# keep Role imported for OpenAPI enum generation in some generators
_ = Role
