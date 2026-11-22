"""Shared fixtures for agent_tools / ai_orchestration tests.

Builds on tests.simdb (isolated, migrated database per pytest process) and adds the `agent` migration branch.
Includes a scripted fake LLM: no network, no paid provider calls.

Import into a conftest:  from tests.agentdb import *  # noqa
"""
import json
from collections.abc import Callable, Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.modules.model_providers.public import (
    ChatRequest,
    ChatResponse,
    ProviderCallError,
    StreamEvent,
    ToolCall,
    Usage,
)
from app.modules.rag.public import RetrievedChunk
from tests.simdb import clean_state, session, sim_db_url, sim_env  # noqa: F401  (re-exported fixtures)

AGENT_TABLES = (
    "agent_tools.agent_execution_logs, ai_orchestration.chat_messages, ai_orchestration.chat_sessions, "
    "ai_orchestration.analysis_runs"
)


@pytest.fixture(scope="session")
def agent_schema(sim_db_url):  # noqa: F811
    """Apply the `agent` migration branch to the isolated database (ALEMBIC_DATABASE_URL is set by sim_db_url)."""
    command.upgrade(Config("alembic.ini"), "agent@head")
    yield


@pytest.fixture()
def agent_state(agent_schema, clean_state):  # noqa: F811
    """Empty simulation data and empty agent tables before each test."""
    with create_engine(clean_state).begin() as c:
        c.execute(text(f"TRUNCATE {AGENT_TABLES} CASCADE"))
    yield clean_state


# ------------------------------------------------------------------ scripted fake LLM
def reply(content: str | None = None, tool_calls: list[tuple[str, dict | str]] | None = None,
          prompt_tokens: int = 100, completion_tokens: int = 50, cost: float | None = 0.001) -> ChatResponse:
    calls = [
        ToolCall(id=f"call_{i}", name=name, arguments=args if isinstance(args, str) else json.dumps(args))
        for i, (name, args) in enumerate(tool_calls or [])
    ]
    return ChatResponse(
        provider="ollama", model="fake", content=content, tool_calls=calls,
        finish_reason="tool_calls" if calls else "stop",
        usage=Usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens),
        estimated_cost_usd=cost, latency_ms=5, tool_calling_supported=True, cloud=False,
    )


class ScriptedLlm:
    """Plays a script: each item is a ChatResponse, an Exception to raise, or a callable(request) -> either."""

    def __init__(self, script: list, supports_tools: bool | None = True, configured: bool = True,
                 repeat_last: bool = False) -> None:
        self.script = list(script)
        self.supports = supports_tools
        self.configured = configured
        self.repeat_last = repeat_last
        self.requests: list[ChatRequest] = []
        self.stream_requests: list[ChatRequest] = []
        self.stream_text = ["Hello", " world"]

    def ensure_configured(self, provider: str, model: str) -> None:
        if not self.configured:
            from app.modules.model_providers.public import ProviderNotConfiguredError

            raise ProviderNotConfiguredError("Fake provider is not configured. Set FAKE_API_KEY.")

    def supports_tools(self, provider: str, model: str) -> bool | None:
        return self.supports

    def complete(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        index = len(self.requests) - 1
        if index >= len(self.script):
            if not self.repeat_last:
                raise AssertionError("LLM called more times than scripted")
            index = len(self.script) - 1
        item = self.script[index]
        if callable(item):
            item = item(request)
        if isinstance(item, Exception):
            raise item
        return item

    def stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        self.stream_requests.append(request)
        yield StreamEvent(type="start")
        for piece in self.stream_text:
            yield StreamEvent(type="delta", content=piece)
        yield StreamEvent(type="done", response=reply("".join(self.stream_text)))


def tool_messages(request: ChatRequest) -> list[dict]:
    """Decoded JSON payloads of the tool-role messages the model was shown."""
    out = []
    for m in request.messages:
        if m.role == "tool" and m.content:
            try:
                out.append(json.loads(m.content))
            except json.JSONDecodeError:
                out.append({"_raw": m.content})
    return out


def all_text(request: ChatRequest) -> str:
    return "\n".join((m.content or "") for m in request.messages)


def policy_chunk(document: str = "Hospital Escalation Procedures", page: int = 2, score: float = 0.8,
                 text_: str = "If average wait exceeds the amber threshold the duty manager escalates.",
                 flagged: bool = False) -> RetrievedChunk:
    import uuid

    return RetrievedChunk(
        chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), document_name=document, page_number=page, chunk_index=0,
        excerpt=text_, score=score, injection_flagged=flagged,
        injection_signals=("instruction_override",) if flagged else (),
    )


def make_fake_search(chunks: list[RetrievedChunk] | Callable[[str, int], list[RetrievedChunk]]):
    calls: list[tuple[str, int]] = []

    def fake(query: str, k: int = 5):
        calls.append((query, k))
        return chunks(query, k) if callable(chunks) else list(chunks)

    fake.calls = calls  # type: ignore[attr-defined]
    return fake


__all__ = [
    "ProviderCallError", "ScriptedLlm", "agent_schema", "agent_state", "all_text", "clean_state", "make_fake_search",
    "policy_chunk", "reply", "session", "sim_db_url", "sim_env", "tool_messages",
]
