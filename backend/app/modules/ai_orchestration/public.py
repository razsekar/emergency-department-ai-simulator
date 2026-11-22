"""Public interface of the ai_orchestration module. Other modules may import ONLY this file.

Owns conversations, analysis runs and LLM request coordination (the bounded agent loop).

Contracts:

  FIXED_DEMO_QUESTION                            -> the one question used for the same-question / different-data demo
  run_agent(question, provider, model, ...)      -> AgentRunResponse   (fresh snapshot + live tools; persisted with
                                                                        the simulation data_version; never cached)
  run_demo(provider, model, ...)                 -> AgentRunResponse   (always the fixed demonstration question)
  list_runs(limit, offset, run_type, scenario_key, data_version) -> RunPage
  get_run(run_id)                                -> AgentRunResponse

Each AgentRunResponse carries the scenario name, data_version, snapshot_metrics (the known-correct numbers to
check an answer against), tools executed, retrieved policies, citation_check, provider/model, latency and tokens.
"""
from app.modules.ai_orchestration.application.contracts import (
    AgentRunRequest,
    AgentRunResponse,
    DemoRunRequest,
    RetrievedPolicyView,
    RunPage,
    RunSummary,
    ToolExecutionView,
)
from app.modules.ai_orchestration.application.service import demo_question, get_run, list_runs
from app.modules.ai_orchestration.application.wiring import get_agent_service
from app.modules.ai_orchestration.domain.prompts import FIXED_DEMO_QUESTION


def run_agent(question: str, provider: str, model: str, temperature: float | None = None, mode: str = "auto",
              actor: str = "system") -> AgentRunResponse:
    return get_agent_service().run(question=question, provider=provider, model=model, temperature=temperature,
                                   mode=mode, run_type="agent", actor=actor)


def run_demo(provider: str, model: str, temperature: float | None = None, mode: str = "auto",
             actor: str = "system") -> AgentRunResponse:
    return get_agent_service().demo_run(provider=provider, model=model, temperature=temperature, mode=mode,
                                        actor=actor)


__all__ = [
    "FIXED_DEMO_QUESTION", "AgentRunRequest", "AgentRunResponse", "DemoRunRequest", "RetrievedPolicyView", "RunPage",
    "RunSummary", "ToolExecutionView", "demo_question", "get_run", "list_runs", "run_agent", "run_demo",
]
