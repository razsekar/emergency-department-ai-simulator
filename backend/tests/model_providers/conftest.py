import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from fastapi import FastAPI
from app.modules.identity.public import Permission, get_current_user
from app.modules.identity.application.contracts import CurrentUser
from app.modules.model_providers import public as providers_public
from app.modules.model_providers.api.router import router
from app.platform.errors import install_error_handlers
from app.modules.model_providers.application.contracts import ChatRequest, ChatResponse, StreamEvent, ToolCall, Usage
from app.modules.model_providers.application.registry import ModelRegistry
from app.modules.model_providers.application.service import ProviderService
from app.modules.model_providers.domain.providers import Provider

SECRET = "sk-test-SECRET-do-not-leak-123456"


class FakeConfig:
    def __init__(self, configured=(), env_models=None, db_models=None, ollama=None, ollama_url="http://localhost:11434"):
        self.configured = set(configured)
        self._env_models = env_models or {}
        self._db_models = db_models or []
        self._ollama = ollama  # list of names, or an Exception instance to raise
        self._url = ollama_url

    def is_configured(self, provider: Provider) -> bool:
        return provider in self.configured

    def ollama_base_url(self) -> str:
        return self._url

    def env_models(self, provider: Provider) -> list[str]:
        return self._env_models.get(provider, [])

    def db_models(self) -> list[dict]:
        return self._db_models

    def ollama_models(self) -> list[str]:
        if isinstance(self._ollama, Exception):
            raise self._ollama
        return self._ollama or []


class FakeGateway:
    """Records calls; returns a canned response, optionally with tool calls."""

    def __init__(self, tool_calls=None, fail: Exception | None = None):
        self.requests: list[ChatRequest] = []
        self._tool_calls = tool_calls or []
        self._fail = fail

    def supports_tools(self, provider: str, model: str):
        return True if model == "tool-model" else None

    def _resp(self, req: ChatRequest) -> ChatResponse:
        return ChatResponse(
            provider=req.provider, model=req.model, content="hello", tool_calls=self._tool_calls,
            finish_reason="stop", usage=Usage(prompt_tokens=3, completion_tokens=2, total_tokens=5),
            latency_ms=7, tool_calling_supported=self.supports_tools(req.provider, req.model),
            cloud=req.provider != "ollama",
        )

    def complete(self, req: ChatRequest) -> ChatResponse:
        self.requests.append(req)
        if self._fail:
            raise self._fail
        return self._resp(req)

    def stream(self, req: ChatRequest) -> Iterator[StreamEvent]:
        self.requests.append(req)
        yield StreamEvent(type="start")
        if self._fail:
            raise self._fail
        yield StreamEvent(type="delta", content="hel")
        yield StreamEvent(type="delta", content="lo")
        yield StreamEvent(type="done", response=self._resp(req))


def make_user(*perms: Permission) -> CurrentUser:
    return CurrentUser(id=uuid.uuid4(), username="tester", display_name="Tester", roles=("test",),
                       permissions=frozenset(str(p) for p in perms))


ALL = (Permission.MODELS_READ, Permission.AI_CHAT, Permission.MODELS_CONFIGURE)


def build_app() -> FastAPI:
    """Isolated app: only this module's router (+ shared error handlers), so tests don't depend on other modules."""
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router)
    return app


@pytest.fixture
def make_client(monkeypatch):
    """Factory: build a TestClient with a fake service and a user holding the given permissions."""
    def _make(config: FakeConfig | None = None, gateway: FakeGateway | None = None,
              perms=ALL, registry: ModelRegistry | None = None) -> TestClient:
        service = ProviderService(gateway or FakeGateway(), config or FakeConfig())
        monkeypatch.setattr(providers_public, "get_service", lambda: service)
        if registry is not None:
            monkeypatch.setattr(providers_public, "get_registry", lambda: registry)
        app = build_app()
        app.dependency_overrides[get_current_user] = lambda: make_user(*perms)
        return TestClient(app, raise_server_exceptions=False)

    yield _make
