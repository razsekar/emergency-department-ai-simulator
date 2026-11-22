import json

import pytest

from app.modules.identity.public import Permission
from app.modules.model_providers.application.contracts import ToolCall
from app.modules.model_providers.application.registry import ModelRegistry
from app.modules.model_providers.domain.errors import ProviderCallError
from app.modules.model_providers.domain.providers import Provider
from tests.model_providers.conftest import FakeConfig, FakeGateway

CHAT = {"provider": "openai", "model": "some-model", "messages": [{"role": "user", "content": "hi"}]}


def test_status_lists_all_four_providers_without_secrets(make_client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-SECRET-do-not-leak-123456")
    client = make_client(FakeConfig(configured={Provider.ANTHROPIC}))
    body = client.get("/api/providers/status")
    assert body.status_code == 200
    by = {p["provider"]: p for p in body.json()}
    assert set(by) == {"anthropic", "openai", "gemini", "ollama"}
    assert by["anthropic"]["configured"] is True and by["openai"]["configured"] is False
    assert "OPENAI_API_KEY" in by["openai"]["detail"]  # actionable, names the env var, not a value
    assert "sk-test-SECRET" not in body.text
    assert by["anthropic"]["cloud"] and by["anthropic"]["data_disclosure"]
    assert by["ollama"]["cloud"] is False and by["ollama"]["data_disclosure"] is None


def test_chat_not_configured_is_409_with_helpful_message(make_client):
    client = make_client(FakeConfig())
    r = client.post("/api/providers/chat", json=CHAT)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "provider_not_configured" and "OPENAI_API_KEY" in err["message"]


def test_chat_returns_usage_latency_disclosure_and_tool_flag(make_client):
    gw = FakeGateway()
    client = make_client(FakeConfig(configured={Provider.OPENAI}), gw)
    r = client.post("/api/providers/chat", json={**CHAT, "model": "tool-model", "temperature": 0.2})
    assert r.status_code == 200
    b = r.json()
    assert b["content"] == "hello" and b["usage"]["total_tokens"] == 5 and b["latency_ms"] == 7
    assert b["tool_calling_supported"] is True and b["cloud"] is True and b["data_disclosure"]
    assert gw.requests[0].temperature == 0.2


def test_tool_calls_pass_through_unvalidated_for_the_agent_loop(make_client):
    tc = ToolCall(id="c1", name="get_bed_availability", arguments='{"department": "ED"}')
    client = make_client(FakeConfig(configured={Provider.OPENAI}), FakeGateway(tool_calls=[tc]))
    tools = [{"type": "function", "function": {"name": "get_bed_availability", "parameters": {"type": "object"}}}]
    r = client.post("/api/providers/chat", json={**CHAT, "tools": tools})
    assert r.json()["tool_calls"] == [{"id": "c1", "name": "get_bed_availability", "arguments": '{"department": "ED"}'}]


def test_provider_failure_is_502_and_hides_internals(make_client):
    client = make_client(FakeConfig(configured={Provider.OPENAI}), FakeGateway(fail=RuntimeError("boom sk-test-SECRET")))
    r = client.post("/api/providers/chat", json=CHAT)
    assert r.status_code == 502 and r.json()["error"]["code"] == "provider_error"
    assert "boom" not in r.text and "SECRET" not in r.text


@pytest.mark.parametrize("bad", [{"model": "bad model!;"}, {"temperature": 3}, {"messages": []}, {"provider": "mistral"}])
def test_request_validation(make_client, bad):
    client = make_client(FakeConfig(configured={Provider.OPENAI}))
    assert client.post("/api/providers/chat", json={**CHAT, **bad}).status_code == 422


def test_sse_stream_emits_start_delta_done(make_client):
    client = make_client(FakeConfig(configured={Provider.OPENAI}))
    r = client.post("/api/providers/chat/stream", json=CHAT)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = [(blk.split("\n")[0][7:], json.loads(blk.split("\n")[1][6:])) for blk in r.text.strip().split("\n\n")]
    assert [e[0] for e in events] == ["start", "delta", "delta", "done"]
    assert "".join(e[1]["content"] or "" for e in events if e[0] == "delta") == "hello"
    assert events[-1][1]["response"]["usage"]["total_tokens"] == 5


def test_sse_stream_not_configured_is_http_error_not_a_stream(make_client):
    client = make_client(FakeConfig())
    r = client.post("/api/providers/chat/stream", json=CHAT)
    assert r.status_code == 409 and not r.headers["content-type"].startswith("text/event-stream")


def test_sse_stream_midway_failure_emits_error_event(make_client):
    client = make_client(FakeConfig(configured={Provider.OPENAI}), FakeGateway(fail=ProviderCallError("x")))
    r = client.post("/api/providers/chat/stream", json=CHAT)
    assert "event: error" in r.text and "SECRET" not in r.text


def test_rbac_enforced_server_side(make_client):
    client = make_client(FakeConfig(configured={Provider.OPENAI}), perms=(Permission.MODELS_READ,))
    assert client.get("/api/providers/models").status_code == 200
    assert client.post("/api/providers/chat", json=CHAT).status_code == 403
    assert client.post("/api/providers/chat/stream", json=CHAT).status_code == 403
    assert client.post("/api/providers/models", json={"provider": "openai", "model_id": "m"}).status_code == 403


def test_unauthenticated_is_401():
    from fastapi.testclient import TestClient
    from tests.model_providers.conftest import build_app
    assert TestClient(build_app()).get("/api/providers/status").status_code == 401


class FakeRepo:
    def __init__(self):
        self.rows: set[tuple[str, str]] = set()

    def upsert(self, provider, model_id, display_name):
        self.rows.add((provider, model_id))

    def disable(self, provider, model_id):
        return (provider, model_id) in self.rows and not self.rows.remove((provider, model_id))


def test_register_and_unregister_models_admin(make_client):
    repo = FakeRepo()
    client = make_client(FakeConfig(), registry=ModelRegistry(repo))
    assert client.post("/api/providers/models", json={"provider": "gemini", "model_id": "my/model:1"}).status_code == 204
    assert ("gemini", "my/model:1") in repo.rows
    assert client.delete("/api/providers/models/gemini/my/model:1").status_code == 204
    assert client.delete("/api/providers/models/gemini/missing").status_code == 422
    assert client.post("/api/providers/models", json={"provider": "gemini", "model_id": "bad id"}).status_code == 422
