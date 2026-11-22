"""Use cases for managing DB-registered model ids (admin only). Persistence is an injected port."""
from typing import Protocol

from app.modules.model_providers.application.contracts import RegisterModelRequest
from app.modules.model_providers.domain.errors import InvalidModelError


class ModelRepository(Protocol):
    def upsert(self, provider: str, model_id: str, display_name: str | None) -> None: ...

    def disable(self, provider: str, model_id: str) -> bool: ...


class ModelRegistry:
    def __init__(self, repo: ModelRepository) -> None:
        self._repo = repo

    def register(self, req: RegisterModelRequest) -> None:
        self._repo.upsert(req.provider, req.model_id, req.display_name)

    def unregister(self, provider: str, model_id: str) -> None:
        if not self._repo.disable(provider, model_id):
            raise InvalidModelError("No such registered model")
