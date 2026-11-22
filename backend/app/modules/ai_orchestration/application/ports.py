"""Ports the orchestration logic depends on. Real adapters live in infrastructure; tests inject fakes."""
from collections.abc import Iterator
from typing import Protocol

from app.modules.model_providers.public import ChatRequest, ChatResponse, StreamEvent


class LlmPort(Protocol):
    def ensure_configured(self, provider: str, model: str) -> None:
        """Raise a safe, actionable error when the provider cannot be used (before any work is done)."""

    def supports_tools(self, provider: str, model: str) -> bool | None:
        """True / False when known, None when unknown (never assumed)."""

    def complete(self, request: ChatRequest) -> ChatResponse: ...

    def stream(self, request: ChatRequest) -> Iterator[StreamEvent]: ...
