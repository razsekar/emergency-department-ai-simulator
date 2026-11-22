"""Typed request/response contracts of the model_providers module (also used by the API layer)."""
from typing import Any, Literal

from pydantic import BaseModel, Field

ProviderName = Literal["anthropic", "openai", "gemini", "ollama"]


class ProviderStatus(BaseModel):
    provider: ProviderName
    label: str
    configured: bool
    reachable: bool | None = None  # only populated when probed (Ollama)
    cloud: bool
    data_disclosure: str | None = None
    detail: str  # human-readable, never contains secrets


class ModelInfo(BaseModel):
    provider: ProviderName
    model_id: str
    display_name: str
    source: Literal["env", "database", "discovered"]
    supports_tools: bool | None = None  # None = unknown (never assumed true)
    cloud: bool


class ToolCall(BaseModel):
    id: str | None = None
    name: str
    arguments: str  # raw JSON string as returned by the model; validated by the caller


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatRequest(BaseModel):
    provider: ProviderName
    model: str = Field(min_length=1, max_length=255)
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None


class Usage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponse(BaseModel):
    provider: ProviderName
    model: str
    content: str | None
    tool_calls: list[ToolCall] = []
    finish_reason: str | None = None
    usage: Usage = Usage()
    estimated_cost_usd: float | None = None
    latency_ms: int
    tool_calling_supported: bool | None = None
    cloud: bool
    data_disclosure: str | None = None
    temperature_applied: bool = True


class StreamEvent(BaseModel):
    type: Literal["start", "delta", "done", "error"]
    content: str | None = None
    response: ChatResponse | None = None
    message: str | None = None


class RegisterModelRequest(BaseModel):
    provider: ProviderName
    model_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9._:/\-]+$")
    display_name: str | None = Field(default=None, max_length=255)
