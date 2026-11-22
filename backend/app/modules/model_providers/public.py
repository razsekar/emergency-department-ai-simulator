"""Public interface of the model_providers module. Other modules may import ONLY this file.

Typical use by ai_orchestration / agent_tools:

    from app.modules.model_providers.public import ChatRequest, ChatMessage, complete

    resp = complete(ChatRequest(provider="ollama", model="...", messages=[ChatMessage(role="user", content="hi")],
                                tools=[...]))          # resp.tool_calls passes tool calls through
"""
from collections.abc import Iterator

from app.modules.model_providers.application.contracts import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ModelInfo,
    ProviderStatus,
    RegisterModelRequest,
    StreamEvent,
    ToolCall,
    Usage,
)
from app.modules.model_providers.domain.errors import (
    InvalidModelError,
    ProviderCallError,
    ProviderNotConfiguredError,
)
from app.modules.model_providers.infrastructure.runtime import get_registry, get_service


def list_models() -> list[ModelInfo]:
    return get_service().list_models()


def provider_status(probe: bool = False) -> list[ProviderStatus]:
    return get_service().provider_status(probe=probe)


def complete(request: ChatRequest) -> ChatResponse:
    return get_service().complete(request)


def stream(request: ChatRequest) -> Iterator[StreamEvent]:
    return get_service().stream(request)


def register_model(request: RegisterModelRequest) -> None:
    get_registry().register(request)


def unregister_model(provider: str, model_id: str) -> None:
    get_registry().unregister(provider, model_id)


__all__ = [
    "ChatMessage", "ChatRequest", "ChatResponse", "ModelInfo", "ProviderStatus", "RegisterModelRequest",
    "StreamEvent", "ToolCall", "Usage", "InvalidModelError", "ProviderCallError", "ProviderNotConfiguredError",
    "list_models", "provider_status", "complete", "stream", "register_model", "unregister_model",
]
