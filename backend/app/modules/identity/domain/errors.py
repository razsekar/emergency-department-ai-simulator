from app.platform.errors import AppError


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthenticated"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"


class AuthNotConfiguredError(AppError):
    status_code = 500
    code = "auth_not_configured"
