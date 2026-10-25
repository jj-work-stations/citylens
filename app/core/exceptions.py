# app/core/exceptions.py
import uuid as _uuid
from fastapi import HTTPException


class AppError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

    def to_http(self) -> HTTPException:
        return HTTPException(
            status_code=self.status_code,
            detail=self.detail,
        )

    @classmethod
    def internal(cls, message: str, details: dict | None = None) -> "AppError":
        err = cls()
        err.detail = message
        if details:
            err.detail += f" | {details}"
        return err


class NotFoundError(AppError):
    status_code = 404

    def __init__(self, resource: str, id=None):
        self.detail = (
            f"{resource} not found"
            if id is None
            else f"{resource} '{id}' not found"
        )


class ConflictError(AppError):
    status_code = 409

    def __init__(self, detail: str):
        self.detail = detail


class PermissionDeniedError(AppError):
    status_code = 403

    def __init__(self, detail: str = "Permission denied"):
        self.detail = detail


class InvalidCredentialsError(AppError):
    status_code = 401
    detail = "Invalid credentials"


class InactiveAccountError(AppError):
    status_code = 403
    detail = "Account is not active"


class InvalidTokenError(AppError):
    status_code = 401

    def __init__(self, detail: str = "Invalid or expired token"):
        self.detail = detail


class ExternalServiceError(AppError):
    status_code = 502

    def __init__(self, service_name: str, reason: str = ""):
        self.detail = f"Service '{service_name}' error: {reason}"


class QueryTooExpensiveError(AppError):
    status_code = 422

    def __init__(self, detail: str = "Query took too long"):
        self.detail = detail