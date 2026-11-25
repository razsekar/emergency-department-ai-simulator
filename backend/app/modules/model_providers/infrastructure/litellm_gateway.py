"""LiteLLM adapter: the only place in the module that imports litellm."""
import logging
import os
import time
from collections.abc import Iterator
from typing import Any

# Use LiteLLM's bundled price/capability map instead of fetching it from GitHub at import time:
# reliable on slow or offline networks (important for a live demo).
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm  # noqa: E402

from app.modules.model_providers.application.contracts import (
    ChatRequest,
    ChatResponse,
    StreamEvent,
    ToolCall,
    Usage,
)
from app.modules.model_providers.domain.providers import SPECS, Provider
from app.modules.model_providers.infrastructure import env_config
from app.platform.config import get_settings

log = logging.getLogger("app.model_providers.litellm")

litellm.suppress_debug_info = True


def _full_model(provider: str, model: str) -> str:
    return f"{SPECS[Provider(provider)].litellm_prefix}/{model}"


def _supports_temperature(provider: str, model: str) -> bool:
    """False only when LiteLLM positively reports that `temperature` is unsupported for this model."""
    try:
        params = litellm.get_supported_openai_params(
            model=model, custom_llm_provider=SPECS[Provider(provider)].litellm_prefix
        )
    except Exception:  # noqa: BLE001 - unknown model => don't block, let the provider decide
        return True
    return True if params is None else "temperature" in params


def _usage(resp: Any) -> Usage:
    u = getattr(resp, "usage", None)
    if u is None:
        return Usage()
    return Usage(
        prompt_tokens=getattr(u, "prompt_tokens", None),
        completion_tokens=getattr(u, "completion_tokens", None),
        total_tokens=getattr(u, "total_tokens", None),
    )


def _cost(resp: Any) -> float | None:
    """Estimated cost only when LiteLLM can price the model; None otherwise (never guessed)."""
    try:
        cost = litellm.completion_cost(completion_response=resp)
        return float(cost) if cost else None
    except Exception:  # noqa: BLE001 - model not in LiteLLM's price map
        return None


def _tool_calls(message: Any) -> list[ToolCall]:
    calls = getattr(message, "tool_calls", None) or []
    return [
        ToolCall(id=getattr(c, "id", None), name=c.function.name, arguments=c.function.arguments or "{}")
        for c in calls
    ]


class LiteLlmGateway:
    def __init__(self, extra_litellm_kwargs: dict[str, Any] | None = None) -> None:
        """`extra_litellm_kwargs` is for tests (LiteLLM's mock_response / mock_tool_calls)."""
        self._extra = extra_litellm_kwargs or {}

    def supports_tools(self, provider: str, model: str) -> bool | None:
        """True/False when LiteLLM knows the model; None when unknown (never assumed)."""
        full = _full_model(provider, model)
        try:
            if full not in litellm.model_cost and model not in litellm.model_cost:
                return None
            return bool(litellm.supports_function_calling(model=full))
        except Exception:  # noqa: BLE001
            return None

    def _kwargs(self, req: ChatRequest) -> tuple[dict[str, Any], bool]:
        spec = SPECS[Provider(req.provider)]
        kw: dict[str, Any] = {
            "model": _full_model(req.provider, req.model),
            "messages": [m.model_dump(exclude_none=True) for m in req.messages],
        }
        key = env_config.api_key(spec)
        if key:
            kw["api_key"] = key
        if spec.provider is Provider.OLLAMA:
            kw["api_base"] = env_config.ollama_base_url()
            kw["num_ctx"] = get_settings().ollama_num_ctx  # else Ollama truncates long prompts at 4096 without an error
        temp_applied = True
        if req.temperature is not None:
            if _supports_temperature(req.provider, req.model):
                kw["temperature"] = req.temperature
            else:
                temp_applied = False
        if req.max_tokens:
            kw["max_tokens"] = req.max_tokens
        kw["timeout"] = get_settings().llm_timeout_seconds
        if req.tools:
            kw["tools"] = req.tools
            if req.tool_choice:
                kw["tool_choice"] = req.tool_choice
        kw.update(self._extra)  # test-only LiteLLM options (e.g. mock_response); never from HTTP input
        return kw, temp_applied

    def _response(self, req: ChatRequest, resp: Any, started: float, temp_applied: bool) -> ChatResponse:
        choice = resp.choices[0]
        spec = SPECS[Provider(req.provider)]
        return ChatResponse(
            provider=req.provider,
            model=req.model,
            content=choice.message.content,
            tool_calls=_tool_calls(choice.message),
            finish_reason=choice.finish_reason,
            usage=_usage(resp),
            estimated_cost_usd=_cost(resp),
            latency_ms=int((time.perf_counter() - started) * 1000),
            tool_calling_supported=self.supports_tools(req.provider, req.model),
            cloud=spec.is_cloud,
            temperature_applied=temp_applied,
        )

    def complete(self, req: ChatRequest) -> ChatResponse:
        kw, temp_applied = self._kwargs(req)
        started = time.perf_counter()
        resp = litellm.completion(**kw)
        return self._response(req, resp, started, temp_applied)

    def stream(self, req: ChatRequest) -> Iterator[StreamEvent]:
        kw, temp_applied = self._kwargs(req)
        kw["stream"] = True
        kw["stream_options"] = {"include_usage": True}
        started = time.perf_counter()
        yield StreamEvent(type="start")
        chunks: list[Any] = []
        for chunk in litellm.completion(**kw):
            chunks.append(chunk)
            if chunk.choices:
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    yield StreamEvent(type="delta", content=delta.content)
        full = litellm.stream_chunk_builder(chunks, messages=kw["messages"])
        yield StreamEvent(type="done", response=self._response(req, full, started, temp_applied))
