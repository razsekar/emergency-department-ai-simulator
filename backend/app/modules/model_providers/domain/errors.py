"""Errors raised by the model_providers module. Messages never contain secrets."""
from app.platform.errors import AppError


class ProviderNotConfiguredError(AppError):
    status_code = 409
    code = "provider_not_configured"


class ProviderCallError(AppError):
    status_code = 502
    code = "provider_error"


class InvalidModelError(AppError):
    status_code = 422
    code = "invalid_model"
