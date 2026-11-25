"""The bounded, hand-written agent loop.

Native mode: the model decides which tools to call (OpenAI-style tool calling through the provider layer).
Fallback mode (models without tool calling, or when native calling fails on the first request): a deterministic,
data-driven plan runs the tools, then the model writes the answer from the verified results. The mode is always
reported. In both modes at most MAX_TOOL_INTERACTIONS tool executions happen per request; further calls are refused
and recorded as refused.
"""
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.modules.agent_tools import public as tools
from app.modules.agent_tools.public import ToolResult
from app.modules.ai_orchestration.application.ports import LlmPort
from app.modules.ai_orchestration.domain import prompts
from app.modules.ai_orchestration.domain.plan import PLAN_HEAD, policy_topics
from app.modules.model_providers.public import ChatMessage, ChatRequest, ChatResponse, ProviderCallError
from app.platform.config import get_settings

log = logging.getLogger("app.ai_orchestration")

MAX_TOOL_MESSAGE_CHARS = 24000
EXTRA_LLM_CALLS = 3  # headroom for the nudge and the final answer after the tool budget is spent


class AgentIncomplete(Exception):
    """The model never produced a usable final answer."""


class _NeedFallback(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AgentFailure(Exception):
    """A run that could not finish. Carries what DID happen (tools executed, tokens spent) so it is still recorded."""

    def __init__(self, cause: Exception, outcome: "AgentOutcome") -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.outcome = outcome


@dataclass
class AgentOutcome:
    answer: str | None = None
    mode: str = "native"
    fallback_reason: str | None = None
    results: list[ToolResult] = field(default_factory=list)
    llm_calls: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    data_disclosure: str | None = None
    executed: int = 0

    def add_response(self, resp: ChatResponse) -> None:
        self.llm_calls += 1
        self.prompt_tokens = _add(self.prompt_tokens, resp.usage.prompt_tokens)
        self.completion_tokens = _add(self.completion_tokens, resp.usage.completion_tokens)
        self.total_tokens = _add(self.total_tokens, resp.usage.total_tokens)
        self.cost_usd = _add(self.cost_usd, resp.estimated_cost_usd)
        self.data_disclosure = resp.data_disclosure or self.data_disclosure


def _add(total, value):
    if value is None:
        return total
    return value if total is None else total + value


def llm_payload(result: ToolResult) -> str:
    """What the LLM sees for one tool result: valid data, or a structured error it can reason about."""
    if result.status != "ok" or result.output is None:
        err = result.error.model_dump() if result.error else {}
        return json.dumps({"status": result.status, "error": err})
    out = dict(result.output)
    if result.tool_name == "retrieve_hospital_protocol":  # excerpts already live inside the delimited `context`
        out["chunks"] = [{k: v for k, v in c.items() if k != "excerpt"} for c in out.get("chunks", [])]
    return json.dumps(out, default=str)[:MAX_TOOL_MESSAGE_CHARS]


def _render_for_fallback(result: ToolResult) -> str:
    header = f"### {result.tool_name} [{result.status}]"
    if result.status != "ok" or result.output is None:
        return f"{header}\n{llm_payload(result)}"
    if result.tool_name == "retrieve_hospital_protocol":
        context = result.output.get("context", "")
        meta = {k: v for k, v in result.output.items() if k not in ("context", "chunks")}
        sources = [{k: v for k, v in c.items() if k != "excerpt"} for c in result.output.get("chunks", [])]
        return f"{header}\n{json.dumps({**meta, 'sources': sources}, default=str)}\n{context}"
    return f"{header}\n{llm_payload(result)}"


class AgentRunner:
    def __init__(self, llm: LlmPort) -> None:
        self._llm = llm

    # ------------------------------------------------------------------ entry point
    def run(self, *, question: str, provider: str, model: str, temperature: float | None, mode: str,
            run_id: uuid.UUID, briefing: str | None = None) -> AgentOutcome:
        # `briefing` (verified, application-computed facts for THIS run) is passed down as an argument, never
        # stored on the runner: the runner is shared between concurrent requests.
        reason: str | None = None
        if mode == "fallback":
            reason = "Fallback mode requested"
        elif mode == "auto":
            support = self._llm.supports_tools(provider, model)
            if support is not True:
                state = "not supported" if support is False else "unknown"
                reason = f"Tool calling is {state} for this model; used the deterministic tool plan"

        out = AgentOutcome(mode="fallback", fallback_reason=reason) if reason else AgentOutcome(mode="native")
        try:
            if reason is None:
                try:
                    return self._native(out, question, provider, model, temperature, run_id, briefing)
                except _NeedFallback as fb:
                    out.mode, out.fallback_reason = "fallback", fb.reason  # usage so far stays on `out`
            return self._fallback(out, question, provider, model, temperature, run_id, briefing)
        except (AgentIncomplete, ProviderCallError) as exc:
            raise AgentFailure(exc, out) from exc

    # ------------------------------------------------------------------ native tool calling
    def _native(self, out: AgentOutcome, question, provider, model, temperature, run_id,
                briefing: str | None = None) -> AgentOutcome:
        max_tools = tools.MAX_TOOL_INTERACTIONS
        messages = [
            ChatMessage(role="system", content=prompts.AGENT_SYSTEM_PROMPT.format(max_tools=max_tools)),
            ChatMessage(role="user", content=f"{briefing}\n\nQuestion: {question}" if briefing else question),
        ]
        offered = tools.openai_tools()
        nudged = False

        while out.llm_calls < max_tools + EXTRA_LLM_CALLS:
            allow = out.executed < max_tools
            request = ChatRequest(provider=provider, model=model, messages=messages, temperature=temperature,
                                  max_tokens=get_settings().agent_max_output_tokens,
                                  tools=offered if allow else None)
            try:
                resp = self._llm.complete(request)
            except ProviderCallError as exc:
                if out.llm_calls == 0:
                    raise _NeedFallback("Native tool calling failed on the first request; used the deterministic tool plan") from exc
                raise
            out.add_response(resp)

            if not resp.tool_calls:
                if out.executed == 0:
                    if not nudged:
                        nudged = True
                        messages += [ChatMessage(role="assistant", content=resp.content or ""),
                                     ChatMessage(role="user", content=prompts.NUDGE_TO_USE_TOOLS)]
                        continue
                    raise _NeedFallback("The model answered without calling any tool; used the deterministic tool plan")
                if not (resp.content or "").strip():
                    raise AgentIncomplete("The model returned an empty answer.")
                out.answer = resp.content
                return out

            calls = [
                {"id": tc.id or f"call_{out.llm_calls}_{i}", "type": "function",
                 "function": {"name": tc.name, "arguments": tc.arguments}}
                for i, tc in enumerate(resp.tool_calls)
            ]
            messages.append(ChatMessage(role="assistant", content=resp.content, tool_calls=calls))
            for call, tc in zip(calls, resp.tool_calls):
                sequence = len(out.results) + 1
                if out.executed >= max_tools:
                    result = tools.refuse_tool(tc.name, tc.arguments, prompts.TOOL_BUDGET_EXHAUSTED.format(max_tools=max_tools),
                                               run_id=run_id, sequence=sequence)
                else:
                    out.executed += 1
                    result = tools.execute_tool(tc.name, tc.arguments, run_id=run_id, sequence=sequence)
                out.results.append(result)
                messages.append(ChatMessage(role="tool", tool_call_id=call["id"], name=tc.name, content=llm_payload(result)))

        raise AgentIncomplete("The model did not produce a final answer within the allowed number of steps.")

    # ------------------------------------------------------------------ deterministic plan + synthesis
    def _fallback(self, out: AgentOutcome, question, provider, model, temperature, run_id,
                  briefing: str | None = None) -> AgentOutcome:
        outputs: dict[str, dict[str, Any] | None] = {}
        for name, args in PLAN_HEAD:
            outputs[name] = self._run_planned(out, name, args, run_id)
        topics = policy_topics(outputs)
        if topics:
            self._run_planned(out, "retrieve_hospital_protocol", {"topics": topics, "k": 2}, run_id)

        body = "\n\n".join(_render_for_fallback(r) for r in out.results)
        lead = f"{briefing}\n\n" if briefing else ""
        user = (f"{lead}Question: {question}\n\n"
                f"Verified tool results (fetched just now from the live simulation):\n\n{body}")
        request = ChatRequest(
            provider=provider, model=model, temperature=temperature,
            max_tokens=get_settings().agent_max_output_tokens,
            messages=[ChatMessage(role="system", content=prompts.FALLBACK_SYSTEM_PROMPT),
                      ChatMessage(role="user", content=user)],
        )
        resp = self._llm.complete(request)
        out.add_response(resp)
        if not (resp.content or "").strip():
            raise AgentIncomplete("The model returned an empty answer.")
        out.answer = resp.content
        return out

    def _run_planned(self, out: AgentOutcome, name: str, args: dict[str, Any], run_id) -> dict[str, Any] | None:
        sequence = len(out.results) + 1
        if out.executed >= tools.MAX_TOOL_INTERACTIONS:
            result = tools.refuse_tool(name, args, prompts.TOOL_BUDGET_EXHAUSTED.format(max_tools=tools.MAX_TOOL_INTERACTIONS),
                                       run_id=run_id, sequence=sequence)
        else:
            out.executed += 1
            result = tools.execute_tool(name, args, run_id=run_id, sequence=sequence)
        out.results.append(result)
        return result.output if result.status == "ok" else None
