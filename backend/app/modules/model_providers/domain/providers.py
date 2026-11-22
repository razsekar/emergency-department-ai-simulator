"""Domain facts about the supported providers (pure data, no I/O)."""
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"


@dataclass(frozen=True)
class ProviderSpec:
    provider: Provider
    label: str
    api_key_env: str | None  # None => no key needed (Ollama)
    base_url_env: str | None
    models_env: str | None  # comma-separated model ids the operator wants offered
    litellm_prefix: str
    is_cloud: bool


SPECS: dict[Provider, ProviderSpec] = {
    Provider.ANTHROPIC: ProviderSpec(Provider.ANTHROPIC, "Anthropic Claude", "ANTHROPIC_API_KEY", None, "ANTHROPIC_MODELS", "anthropic", True),
    Provider.OPENAI: ProviderSpec(Provider.OPENAI, "OpenAI", "OPENAI_API_KEY", None, "OPENAI_MODELS", "openai", True),
    Provider.GEMINI: ProviderSpec(Provider.GEMINI, "Google Gemini", "GEMINI_API_KEY", None, "GEMINI_MODELS", "gemini", True),
    Provider.OLLAMA: ProviderSpec(Provider.OLLAMA, "Ollama (local)", None, "OLLAMA_BASE_URL", None, "ollama_chat", False),
}

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"}


def ollama_leaves_machine(base_url: str) -> bool:
    """True if the configured Ollama endpoint is not obviously local (data would leave the machine)."""
    host = urlparse(base_url).hostname or ""
    return host not in _LOCAL_HOSTS
