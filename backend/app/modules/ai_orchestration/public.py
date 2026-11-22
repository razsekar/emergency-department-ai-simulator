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


# ---- demonstration mode (worker H) -------------------------------------------------------------------------
# demo_step(request, actor)  -> DemoStepResponse   apply scenario, verify data changed, ask the FIXED question,
#                                                   save as the next "Run N"
# demo_session()             -> DemoSessionView    saved runs + derived metric comparison
# demo_reset(actor)          -> DemoResetResponse  clear saved runs and reload the Normal baseline
from app.modules.ai_orchestration.application.demo_contracts import (  # noqa: E402
    DemoResetResponse,
    DemoRunView,
    DemoSessionView,
    DemoStepRequest,
    DemoStepResponse,
)
from app.modules.ai_orchestration.application.demo_wiring import get_demo_service  # noqa: E402


def demo_step(request: DemoStepRequest, actor: str = "system") -> DemoStepResponse:
    return get_demo_service().step(request, actor=actor)


def demo_session() -> DemoSessionView:
    return get_demo_service().session()


def demo_reset(actor: str = "system") -> DemoResetResponse:
    return get_demo_service().reset(actor=actor)


__all__ = [
    "FIXED_DEMO_QUESTION", "AgentRunRequest", "AgentRunResponse", "DemoRunRequest", "RetrievedPolicyView", "RunPage",
    "RunSummary", "ToolExecutionView", "demo_question", "get_run", "list_runs", "run_agent", "run_demo",
    "DemoResetResponse", "DemoRunView", "DemoSessionView", "DemoStepRequest", "DemoStepResponse",
    "demo_reset", "demo_session", "demo_step",
]


# ---- model comparison (Phase 7) ----
# run_comparison(question, selections, actor) -> ComparisonRunResponse
#     ONE snapshot + ONE shared tool/policy context; each model answers from the identical frozen prompt.
#     Labelled "demonstration comparison, not a formal benchmark". list_comparisons / get_comparison read history.
from app.modules.ai_orchestration.application.comparison_contracts import (  # noqa: E402
    ComparisonPage,
    ComparisonRunRequest,
    ComparisonRunResponse,
    ModelResultView,
    ModelSelection,
    SharedContextView,
)
from app.modules.ai_orchestration.application.comparison_service import (  # noqa: E402
    get_comparison,
    list_comparisons,
)
from app.modules.ai_orchestration.application.comparison_wiring import get_comparison_service  # noqa: E402


def run_comparison(question: str, selections: list[ModelSelection], actor: str = "system") -> ComparisonRunResponse:
    return get_comparison_service().run(question=question, selections=selections, actor=actor)


__all__ += [
    "ComparisonPage", "ComparisonRunRequest", "ComparisonRunResponse", "ModelResultView", "ModelSelection",
    "SharedContextView", "get_comparison", "list_comparisons", "run_comparison",
]
