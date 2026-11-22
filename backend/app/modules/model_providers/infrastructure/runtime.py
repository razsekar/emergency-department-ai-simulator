"""Wires the real adapters (env, DB, Ollama, LiteLLM) into a ProviderService."""
import logging
from functools import lru_cache

from app.modules.model_providers.application.registry import ModelRegistry
from app.modules.model_providers.application.service import ProviderService
from app.modules.model_providers.domain.providers import SPECS, Provider
from app.modules.model_providers.infrastructure import env_config, ollama_client, repository
from app.modules.model_providers.infrastructure.litellm_gateway import LiteLlmGateway
from app.platform.db import unit_of_work

log = logging.getLogger("app.model_providers")


class RuntimeConfig:
    def is_configured(self, provider: Provider) -> bool:
        return env_config.is_configured(SPECS[provider])

    def ollama_base_url(self) -> str:
        return env_config.ollama_base_url()

    def env_models(self, provider: Provider) -> list[str]:
        return env_config.env_models(provider)

    def db_models(self) -> list[dict]:
        try:
            with unit_of_work() as session:
                return repository.list_enabled(session)
        except Exception as exc:  # noqa: BLE001 - DB problems must not break env/Ollama discovery
            log.warning("Could not read model_configurations: %s", type(exc).__name__)
            return []

    def ollama_models(self) -> list[str]:
        return ollama_client.list_models(env_config.ollama_base_url())


class DbModelRepository:
    """Each call is its own transaction (commit on success, roll back on error)."""

    def upsert(self, provider: str, model_id: str, display_name: str | None) -> None:
        with unit_of_work() as session:
            repository.upsert(session, provider, model_id, display_name)

    def disable(self, provider: str, model_id: str) -> bool:
        with unit_of_work() as session:
            return repository.disable(session, provider, model_id)


@lru_cache
def get_service() -> ProviderService:
    return ProviderService(LiteLlmGateway(), RuntimeConfig())


@lru_cache
def get_registry() -> ModelRegistry:
    return ModelRegistry(DbModelRepository())
