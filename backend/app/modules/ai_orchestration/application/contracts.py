"""Typed request/response contracts of the ai_orchestration module (also used by the API layer)."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.model_providers.public import Usage

ProviderName = Literal["anthropic", "openai", "gemini", "ollama"]  # mirrors the provider contract
AgentMode = Literal["auto", "native", "fallback"]


class AgentRunRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    provider: ProviderName
    model: str = Field(min_length=1, max_length=255)
    temperature: float | None = Field(default=None, ge=0, le=2)
    mode: AgentMode = Field(default="auto", description="auto: native tool calling when the model is known to support it")


class DemoRunRequest(BaseModel):
    """The question is fixed by the backend; only the model settings can vary."""

    provider: ProviderName
    model: str = Field(min_length=1, max_length=255)
    temperature: float | None = Field(default=None, ge=0, le=2)
    mode: AgentMode = "auto"


class ToolExecutionView(BaseModel):
    sequence: int
    tool_name: str
    status: str
    arguments: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int
    data_version: int | None = None


class RetrievedPolicyView(BaseModel):
    document_name: str
    page: int
    score: float
    excerpt: str
    matched_query: str
    flagged: bool = False


class AgentRunResponse(BaseModel):
    id: UUID
    run_type: Literal["agent", "demo"]
    question: str
    status: Literal["completed", "failed"]
    error: str | None = None
    answer: str | None
    mode: Literal["native", "fallback"]
    fallback_reason: str | None = None
    scenario_key: str | None
    scenario_name: str | None
    data_version: int | None
    data_version_consistent: bool
    snapshot_metrics: dict[str, Any]
    tools_executed: list[ToolExecutionView]
    retrieved_policies: list[RetrievedPolicyView]
    citation_check: dict[str, Any]
    provider: str
    model: str
    temperature: float | None
    llm_calls: int
    latency_ms: int
    usage: Usage
    estimated_cost_usd: float | None
    data_disclosure: str | None
    created_by: str
    created_at: datetime


class RunSummary(BaseModel):
    id: UUID
    run_type: str
    question: str
    scenario_name: str | None
    data_version: int | None
    provider: str
    model: str
    mode: str
    status: str
    tool_names: list[str]
    latency_ms: int
    total_tokens: int | None
    created_at: datetime


class RunPage(BaseModel):
    items: list[RunSummary]
    total: int
    limit: int
    offset: int


# ---- chat ----
class CreateSessionRequest(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=200)


class ChatMessageView(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    sources: list[RetrievedPolicyView] = []
    citation_check: dict[str, Any] = {}
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    data_disclosure: str | None = None
    created_at: datetime


class ChatSessionView(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ChatSessionDetail(ChatSessionView):
    messages: list[ChatMessageView]


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    provider: ProviderName
    model: str = Field(min_length=1, max_length=255)
    temperature: float | None = Field(default=None, ge=0, le=2)
    use_rag: bool = True
    include_live_data: bool = Field(default=True, description="Add a fresh snapshot of the simulation to the prompt")


class SendMessageResponse(BaseModel):
    user_message: ChatMessageView
    assistant_message: ChatMessageView
    usage: Usage
    estimated_cost_usd: float | None = None
