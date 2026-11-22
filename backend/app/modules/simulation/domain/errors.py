from app.platform.errors import AppError, NotFoundError


class ScenarioValidationError(AppError):
    """Scenario parameters are invalid, or generated data did not match the requested scenario."""

    status_code = 422
    code = "scenario_validation_failed"


class ScenarioNotFoundError(NotFoundError):
    code = "scenario_not_found"
