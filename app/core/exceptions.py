from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FORBIDDEN = "FORBIDDEN"

    def __str__(self) -> str:
        return self.value


class AppError(Exception):
    status_code: int = 500
    error_code: str = ErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        extra: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.extra = extra or {}


class UnauthorizedError(AppError):
    status_code = 401
    error_code = ErrorCode.UNAUTHORIZED


class NotFoundError(AppError):
    status_code = 404
    error_code = ErrorCode.NOT_FOUND


class ConflictError(AppError):
    status_code = 409
    error_code = ErrorCode.CONFLICT


class AppValidationError(AppError):
    status_code = 422
    error_code = ErrorCode.VALIDATION_ERROR


class ForbiddenError(AppError):
    status_code = 403
    error_code = ErrorCode.FORBIDDEN
