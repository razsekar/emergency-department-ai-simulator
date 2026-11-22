"""Adapter from the LlmPort to the model_providers public interface."""
import logging
from collections.abc import Iterator

from app.modules.model_providers import public as providers
from app.modules.model_providers.public import ChatRequest, ChatResponse, ProviderNotConfiguredError, StreamEvent

log = logging.getLogger("app.ai_orchestration")


class ProvidersLlm:
    def ensure_configured(self, provider: str, model: str) -> None:
        for status in providers.provider_status():
            if status.provider == provider:
                if not status.configured:
                    raise ProviderNotConfiguredError(f"{status.label} is not configured. {status.detail}.")
                return

    def supports_tools(self, provider: str, model: str) -> bool | None:
        try:
            for info in providers.list_models():
                if info.provider == provider and info.model_id == model:
                    return info.supports_tools
        except Exception as exc:  # noqa: BLE001 - discovery trouble means "unknown", never "supported"
            log.info("Tool-capability lookup failed: %s", type(exc).__name__)
        return None

    def complete(self, request: ChatRequest) -> ChatResponse:
        return providers.complete(request)

    def stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        return providers.stream(request)
