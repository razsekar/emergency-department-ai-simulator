"""The LiteLLM call carries an explicit, configurable timeout (the default of 600 s was too short for CPU Ollama)."""
import pytest

from app.modules.model_providers.application.contracts import ChatMessage, ChatRequest
from app.modules.model_providers.infrastructure.litellm_gateway import LiteLlmGateway
from app.platform.config import Settings, get_settings


def _req():
    return ChatRequest(provider="ollama", model="x", messages=[ChatMessage(role="user", content="hi")])


def test_default_timeout_is_explicit_and_generous():
    get_settings.cache_clear()
    kw, _ = LiteLlmGateway()._kwargs(_req())
    assert kw["timeout"] == 1200


def test_timeout_is_configurable_by_env(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    get_settings.cache_clear()
    try:
        kw, _ = LiteLlmGateway()._kwargs(_req())
        assert kw["timeout"] == 45
    finally:
        monkeypatch.delenv("LLM_TIMEOUT_SECONDS")
        get_settings.cache_clear()


def test_ollama_calls_request_a_context_window_large_enough_for_the_agent_prompt():
    """Ollama silently truncates the START of a prompt above its default 4096-token window (observed in the real demo:
    the question, rules and briefing were dropped). The agent prompt is ~4-5k tokens, so a bigger window is required."""
    get_settings.cache_clear()
    kw, _ = LiteLlmGateway()._kwargs(_req())
    assert kw["num_ctx"] == 8192 and kw["num_ctx"] > 4096


def test_context_window_is_configurable_by_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_NUM_CTX", "16384")
    get_settings.cache_clear()
    try:
        kw, _ = LiteLlmGateway()._kwargs(_req())
        assert kw["num_ctx"] == 16384
    finally:
        monkeypatch.delenv("OLLAMA_NUM_CTX")
        get_settings.cache_clear()


def test_cloud_providers_never_receive_the_ollama_only_option():
    get_settings.cache_clear()
    for provider in ("openai", "anthropic", "gemini"):
        req = ChatRequest(provider=provider, model="m", messages=[ChatMessage(role="user", content="hi")])
        kw, _ = LiteLlmGateway()._kwargs(req)
        assert "num_ctx" not in kw, provider


def test_limits_reject_nonsense_values():
    with pytest.raises(ValueError):
        Settings(llm_timeout_seconds=0)
    with pytest.raises(ValueError):
        Settings(agent_max_output_tokens=10)
    with pytest.raises(ValueError):
        Settings(ollama_num_ctx=100)
