"""Public interface of the simulation module. Other modules may import ONLY this file.

Contracts:

  get_data_state(session)  -> DataState   (data_version, scenario key/name, applied_at, last_run_id)
  current_state()          -> DataState   (opens its own transaction)
  list_scenarios()         -> list[ScenarioInfo]
  apply_scenario(key, overrides=None) -> ApplyResponse   (atomic; own transaction)
  reset_database()         -> ApplyResponse              (reapplies the baseline scenario)
  randomize_scenario(seed=None) -> ApplyResponse

``data_version`` increases by one on every successful apply/reset/randomize. Analyses store it so
results can be traced to the exact data state. This module owns schema ``simulation``.
"""
from app.modules.simulation.application.schemas import (
    ApplyRequest,
    ApplyResponse,
    DataState,
    RunPage,
    ScenarioInfo,
    ScenarioOverrides,
    ScenarioParams,
    ScenarioRunInfo,
)
from app.modules.simulation.application.service import (
    apply_scenario,
    current_state,
    get_data_state,
    get_history,
    list_scenarios,
    randomize_scenario,
    reset_database,
)

__all__ = [
    "ApplyRequest", "ApplyResponse", "DataState", "RunPage", "ScenarioInfo", "ScenarioOverrides",
    "ScenarioParams", "ScenarioRunInfo", "apply_scenario", "current_state", "get_data_state",
    "get_history", "list_scenarios", "randomize_scenario", "reset_database",
]
