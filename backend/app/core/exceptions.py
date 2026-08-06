# app/core/exceptions.py


class AppError(Exception):
    status_code = 400
    code = "APP_ERROR"

    def __init__(
        self,
        detail: str,
        field_errors: dict[str, str] | None = None,
    ):
        self.detail = detail
        self.field_errors = field_errors or {}

        super().__init__(detail)


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class BusinessRuleError(AppError):
    status_code = 422
    code = "BUSINESS_RULE_ERROR"
