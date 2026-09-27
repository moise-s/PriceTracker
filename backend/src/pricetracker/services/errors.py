"""Service-level errors translated to HTTP problem responses by the API layer."""

from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details


class NotFound(ServiceError):
    status_code = 404
    code = "not_found"


class Forbidden(ServiceError):
    status_code = 403
    code = "forbidden"


class Unauthorized(ServiceError):
    status_code = 401
    code = "unauthorized"


class Conflict(ServiceError):
    status_code = 409
    code = "conflict"


class TooManyRequests(ServiceError):
    status_code = 429
    code = "rate_limited"


class ValidationFailed(ServiceError):
    status_code = 422
    code = "validation_failed"
