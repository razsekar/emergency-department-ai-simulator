"""Use cases of the model_providers module. No framework or SDK code here: the LLM gateway is a port."""
import logging
import re
from collections.abc import Iterator
from typing import Protocol

from app.modules.model_providers.application.contracts import (
    ChatRequest,
    ChatResponse,
    ModelInfo,
    ProviderStatus,
    StreamEvent,
)
from app.modules.model_providers.domain.errors import (
    InvalidModelError,
    ProviderCallError,
    ProviderNotConfiguredError,
)
from app.modules.model_providers.domain.providers import SPECS, Provider, ollama_leaves_machine

log = logging.getLogger("app.model_providers")

_MODEL_ID = re.compile(r"^[A-Za-z0-9._:/\-]{1,255}$")
CLOUD_DISCLOSURE = (
    "Prompts and any attached operational/document context are sent to a third-party cloud provider."
)
REMOTE_OLLAMA_DISCLOSURE = "The configured Ollama endpoint is not local; prompts leave this machine."


class LlmGateway(Protocol):
    """Port implemented by the LiteLLM adapter (and by fakes in tests)."""

    def complete(self, req: ChatRequest) -> ChatResponse: ...

    def stream(self, req: ChatRequest) -> Iterator[StreamEvent]: ...

    def supports_tools(self, provider: str, model: str) -> bool | None: ...


class ConfigPort(Protocol):
    def is_configured(self, provider: Provider) -> bool: ...

    def ollama_base_url(self) -> str: ...

    def env_models(self, provider: Provider) -> list[str]: ...

    def db_models(self) -> list[dict]: ...

    def ollama_models(self) -> list[str]: ...


def disclosure_for(provider: Provider, ollama_url: str) -> str | None:
    if SPECS[provider].is_cloud:
        return CLOUD_DISCLOSURE
    return REMOTE_OLLAMA_DISCLOSURE if ollama_leaves_machine(ollama_url) else None


class ProviderService:
    def __init__(self, gateway: LlmGateway, config: ConfigPort) -> None:
        self._gw = gateway
        self._cfg = config

    # ---- status -------------------------------------------------------------------------
    def provider_status(self, probe: bool = False) -> list[ProviderStatus]:
        out: list[ProviderStatus] = []
        for provider, spec in SPECS.items():
            configured = self._cfg.is_configured(provider)
            reachable: bool | None = None
            if provider is Provider.OLLAMA:
                detail = f"Local Ollama endpoint: {self._cfg.ollama_base_url()}"
                if probe:
                    try:
                        self._cfg.ollama_models()
                        reachable = True
                    except Exception:  # noqa: BLE001 - any connectivity failure means unreachable
                        reachable = False
                        detail += " (not reachable; start Ollama and pull a model yourself)"
            else:
                detail = (
                    f"{spec.api_key_env} is set" if configured else f"Set {spec.api_key_env} in the backend environment"
                )
            out.append(
                ProviderStatus(
                    provider=provider.value,
                    label=spec.label,
                    configured=configured,
                    reachable=reachable,
                    cloud=spec.is_cloud,
                    data_disclosure=disclosure_for(provider, self._cfg.ollama_base_url()),
                    detail=detail,
                )
            )
        return out

    # ---- models -------------------------------------------------------------------------
    def list_models(self) -> list[ModelInfo]:
        seen: set[tuple[str, str]] = set()
        models: list[ModelInfo] = []

        def add(provider: Provider, model_id: str, display: str, source: str) -> None:
            key = (provider.value, model_id)
            if key in seen:
                return
            seen.add(key)
            models.append(
                ModelInfo(
                    provider=provider.value,
                    model_id=model_id,
                    display_name=display,
                    source=source,
                    supports_tools=self._gw.supports_tools(provider.value, model_id),
                    cloud=SPECS[provider].is_cloud,
                )
            )

        for provider in Provider:
            for m in self._cfg.env_models(provider):
                add(provider, m, m, "env")
        for row in self._cfg.db_models():
            add(Provider(row["provider"]), row["model_id"], row["display_name"], "database")
        try:
            for m in self._cfg.ollama_models():
                add(Provider.OLLAMA, m, m, "discovered")
        except Exception as exc:  # noqa: BLE001 - Ollama being down is normal
            log.info("Ollama model discovery unavailable: %s", type(exc).__name__)
        return models

    # ---- completion ---------------------------------------------------------------------
    def _prepare(self, req: ChatRequest) -> Provider:
        provider = Provider(req.provider)
        if not _MODEL_ID.match(req.model):
            raise InvalidModelError("Model id contains unsupported characters")
        if not self._cfg.is_configured(provider):
            spec = SPECS[provider]
            raise ProviderNotConfiguredError(
                f"{spec.label} is not configured. Set {spec.api_key_env} in the backend environment and restart."
            )
        return provider

    def complete(self, req: ChatRequest) -> ChatResponse:
        self._prepare(req)
        try:
            resp = self._gw.complete(req)
        except (ProviderNotConfiguredError, InvalidModelError, ProviderCallError):
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("Provider call failed: %s", type(exc).__name__)
            raise ProviderCallError(f"The provider call failed ({type(exc).__name__}). Check model id and provider status.") from exc
        return resp.model_copy(update={"data_disclosure": disclosure_for(Provider(req.provider), self._cfg.ollama_base_url())})

    def stream(self, req: ChatRequest) -> Iterator[StreamEvent]:
        self._prepare(req)  # raises before any bytes are streamed
        disclosure = disclosure_for(Provider(req.provider), self._cfg.ollama_base_url())
        try:
            for ev in self._gw.stream(req):
                if ev.type == "done" and ev.response is not None:
                    ev = ev.model_copy(update={"response": ev.response.model_copy(update={"data_disclosure": disclosure})})
                yield ev
        except Exception as exc:  # noqa: BLE001
            log.warning("Provider stream failed: %s", type(exc).__name__)
            yield StreamEvent(type="error", message=f"The provider stream failed ({type(exc).__name__}).")
