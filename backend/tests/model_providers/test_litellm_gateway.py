"""Exercises the real LiteLLM adapter with LiteLLM's own mock_response (no network, no paid calls)."""
import pytest

from app.modules.model_providers.application.contracts import ChatMessage, ChatRequest
from app.modules.model_providers.application.service import ProviderService
from app.modules.model_providers.domain.providers import Provider
from app.modules.model_providers.infrastructure import litellm_gateway as lg
from tests.model_providers.conftest import FakeConfig

MSGS = [ChatMessage(role="user", content="hi")]


def req(provider="openai", model="zzz-unmapped-model", **kw):
    return ChatRequest(provider=provider, model=model, messages=MSGS, **kw)


def svc(mock: dict, configured=(Provider.OPENAI, Provider.ANTHROPIC, Provider.OLLAMA)):
    return ProviderService(lg.LiteLlmGateway(mock), FakeConfig(configured=set(configured)))


def test_complete_maps_content_usage_latency_and_disclosure():
    r = svc({"mock_response": "hello there"}).complete(req(temperature=0.3, max_tokens=50))
    assert r.content == "hello there" and r.finish_reason == "stop"
    assert r.usage.total_tokens and r.usage.total_tokens == (r.usage.prompt_tokens or 0) + (r.usage.completion_tokens or 0)
    assert r.latency_ms >= 0 and r.cloud is True and "cloud" in (r.data_disclosure or "")
    assert r.temperature_applied is True


def test_cost_is_none_for_unmapped_models_and_a_number_for_mapped_ones():
    assert svc({"mock_response": "x"}).complete(req()).estimated_cost_usd is None  # never guessed
    priced = svc({"mock_response": "x"}).complete(req(model="gpt-4o-mini"))
    assert priced.estimated_cost_usd is not None and priced.estimated_cost_usd > 0


def test_tool_support_is_unknown_for_unmapped_and_known_for_mapped_models():
    gw = lg.LiteLlmGateway()
    assert gw.supports_tools("openai", "zzz-unmapped-model") is None
    assert gw.supports_tools("openai", "gpt-4o-mini") is True


def test_tool_calls_pass_through():
    tools = [{"type": "function", "function": {"name": "f", "parameters": {"type": "object", "properties": {}}}}]
    mock = {"mock_tool_calls": [{"id": "c1", "type": "function", "function": {"name": "f", "arguments": '{"a": 1}'}}]}
    r = svc(mock).complete(req(tools=tools, tool_choice="auto"))
    assert [(t.id, t.name, t.arguments) for t in r.tool_calls] == [("c1", "f", '{"a": 1}')]


def test_temperature_dropped_when_litellm_says_unsupported(monkeypatch):
    monkeypatch.setattr(lg.litellm, "get_supported_openai_params", lambda **k: ["max_tokens"])
    seen = {}
    real = lg.litellm.completion

    def spy(**kw):
        seen.update(kw)
        return real(**kw)

    monkeypatch.setattr(lg.litellm, "completion", spy)
    r = svc({"mock_response": "x"}).complete(req(temperature=0.9))
    assert "temperature" not in seen and r.temperature_applied is False


def test_temperature_sent_when_supported_or_unknown(monkeypatch):
    seen = {}
    real = lg.litellm.completion
    monkeypatch.setattr(lg.litellm, "completion", lambda **kw: (seen.update(kw), real(**kw))[1])
    svc({"mock_response": "x"}).complete(req(temperature=0.9))
    assert seen["temperature"] == 0.9
    monkeypatch.setattr(lg.litellm, "get_supported_openai_params", lambda **k: None)
    seen.clear()
    svc({"mock_response": "x"}).complete(req(temperature=0.5))
    assert seen["temperature"] == 0.5


def test_model_prefix_and_ollama_base_url(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    seen = {}
    real = lg.litellm.completion
    monkeypatch.setattr(lg.litellm, "completion", lambda **kw: (seen.update(kw), real(**kw))[1])
    svc({"mock_response": "x"}).complete(req(provider="ollama", model="llama-x:latest"))
    assert seen["model"] == "ollama_chat/llama-x:latest" and seen["api_base"] == "http://localhost:11434"
    assert "api_key" not in seen
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret")
    seen.clear()
    svc({"mock_response": "x"}).complete(req(provider="anthropic", model="some-claude"))
    assert seen["model"] == "anthropic/some-claude" and "api_base" not in seen


def test_streaming_yields_deltas_then_done_with_usage():
    events = list(svc({"mock_response": "hello there friend"}).stream(req()))
    assert events[0].type == "start" and events[-1].type == "done"
    assert "".join(e.content or "" for e in events if e.type == "delta") == "hello there friend"
    done = events[-1].response
    assert done.content == "hello there friend" and done.usage.total_tokens and done.data_disclosure


def test_unconfigured_provider_never_reaches_litellm(monkeypatch):
    monkeypatch.setattr(lg.litellm, "completion", lambda **kw: pytest.fail("must not call provider"))
    from app.modules.model_providers.domain.errors import ProviderNotConfiguredError
    with pytest.raises(ProviderNotConfiguredError) as e:
        svc({"mock_response": "x"}, configured=()).complete(req(provider="gemini", model="m"))
    assert "GEMINI_API_KEY" in str(e.value)
    with pytest.raises(ProviderNotConfiguredError):
        list(svc({"mock_response": "x"}, configured=()).stream(req(provider="gemini", model="m")))


def test_api_key_is_passed_to_litellm_but_never_returned(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-SECRET-do-not-leak-123456")
    seen = {}
    real = lg.litellm.completion
    monkeypatch.setattr(lg.litellm, "completion", lambda **kw: (seen.update(kw), real(**kw))[1])
    r = svc({"mock_response": "x"}).complete(req())
    assert seen["api_key"].startswith("sk-test-SECRET")
    assert "SECRET" not in r.model_dump_json()
