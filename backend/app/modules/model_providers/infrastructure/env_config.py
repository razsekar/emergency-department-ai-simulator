"""Reads provider configuration from environment variables. Values of secrets are never returned."""
import os

from app.modules.model_providers.domain.providers import SPECS, Provider, ProviderSpec

DEFAULT_OLLAMA_URL = "http://host.docker.internal:11434"


def is_configured(spec: ProviderSpec) -> bool:
    if spec.api_key_env:
        return bool(os.environ.get(spec.api_key_env, "").strip())
    return True  # Ollama needs no key; reachability is probed separately


def api_key(spec: ProviderSpec) -> str | None:
    """Server-side use only (passed to LiteLLM). Must never be serialized into a response."""
    return os.environ.get(spec.api_key_env, "").strip() or None if spec.api_key_env else None


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "").strip() or DEFAULT_OLLAMA_URL


def env_models(provider: Provider) -> list[str]:
    spec = SPECS[provider]
    if not spec.models_env:
        return []
    raw = os.environ.get(spec.models_env, "")
    return [m.strip() for m in raw.split(",") if m.strip()]
