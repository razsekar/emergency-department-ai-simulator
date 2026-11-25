"""The model is handed a verified briefing (scenario name, data version, computed GREEN/AMBER/RED level)
instead of being left to work the level out itself. Scripted fake LLM; no network."""
import pytest

from app.modules.agent_tools.application import handlers
from app.modules.ai_orchestration.application.service import AgentService
from app.modules.ai_orchestration.domain import prompts
from app.modules.simulation import public as simulation
from tests.agentdb import ScriptedLlm, all_text, make_fake_search, policy_chunk, reply
from tests.ai_orchestration.test_agent import FOUR_FACTS, POLICY, fallback_answer, grounded_answer

EXPECTED = {"normal": ("Normal Operations", "GREEN"),
            "surge": ("Emergency Surge", "RED"),
            "recovery": ("Recovery Operations", "GREEN")}


@pytest.fixture(autouse=True)
def fake_policy_search(monkeypatch):
    monkeypatch.setattr(handlers.rag, "search", make_fake_search([policy_chunk()]))


def run_fallback(llm):
    return AgentService(llm).run(question="How is the ED doing?", provider="ollama", model="fake", mode="fallback")


def run_native(llm):
    return AgentService(llm).run(question="How is the ED doing?", provider="ollama", model="fake", mode="native")


def native_script():
    return [reply(tool_calls=FOUR_FACTS), reply(tool_calls=[POLICY]), grounded_answer]


@pytest.mark.parametrize("scenario", ["normal", "surge", "recovery"])
def test_fallback_prompt_carries_the_computed_level_and_scenario_name(agent_state, scenario):
    name, level = EXPECTED[scenario]
    simulation.apply_scenario(scenario)
    llm = ScriptedLlm([fallback_answer])
    res = run_fallback(llm)

    text = all_text(llm.requests[0])
    assert "VERIFIED BRIEFING" in text
    assert f"Scenario: {name}" in text
    assert f"Operating level: {level}" in text
    assert f"Data version: {res.data_version}" in text
    others = {"GREEN", "AMBER", "RED"} - {level}
    assert not any(f"Operating level: {o}" in text for o in others)


@pytest.mark.parametrize("scenario", ["normal", "surge", "recovery"])
def test_native_first_message_carries_the_briefing_before_the_question(agent_state, scenario):
    name, level = EXPECTED[scenario]
    simulation.apply_scenario(scenario)
    llm = ScriptedLlm(native_script())
    run_native(llm)

    user = llm.requests[0].messages[1].content
    assert user.startswith("VERIFIED BRIEFING")
    assert f"Scenario: {name}" in user and f"Operating level: {level}" in user
    assert user.rstrip().endswith("Question: How is the ED doing?")


def test_indicator_table_shows_values_bands_and_policy_bands(agent_state):
    simulation.apply_scenario("surge")
    llm = ScriptedLlm([fallback_answer])
    run_fallback(llm)
    text = all_text(llm.requests[0])
    assert "Average waiting time: 75 min -> RED (bands: GREEN <=30; AMBER 31-60; RED >60)" in text
    assert "Available beds: 1 beds -> RED" in text
    assert "Pending investigation requests: 28 requests -> RED" in text
    assert "6 indicator(s) RED" in text


def test_briefing_is_rebuilt_every_run_and_never_leaks_between_runs(agent_state):
    svc = AgentService(ScriptedLlm([]))  # same service object, like the real singleton
    seen = []
    for scenario in ("surge", "normal", "recovery", "surge"):
        simulation.apply_scenario(scenario)
        llm = ScriptedLlm([fallback_answer])
        svc._llm = llm
        svc._runner._llm = llm
        svc.run(question="How is the ED doing?", provider="ollama", model="fake", mode="fallback")
        seen.append(llm.requests[0].messages[1].content)  # the user message only (the system prompt also names the rule)
    levels = [next(l for l in ("RED", "AMBER", "GREEN") if f"Operating level: {l}" in t) for t in seen]
    assert levels == ["RED", "GREEN", "GREEN", "RED"]
    assert [t.count("VERIFIED BRIEFING") for t in seen] == [1, 1, 1, 1]


def test_system_prompts_require_the_briefing_level_and_mandatory_actions():
    for prompt in (prompts.AGENT_SYSTEM_PROMPT, prompts.FALLBACK_SYSTEM_PROMPT):
        assert "VERIFIED BRIEFING" in prompt
        assert "exactly as given" in prompt and "never invent thresholds" in prompt.replace("Never recompute, soften or contradict the level, and ", "")
        assert "mandatory" in prompt and "Recommended administrative actions" in prompt
        assert 'such as "UNTRUSTED"' in prompt  # do not echo internal delimiters


def test_budget_and_grounding_rules_are_unchanged():
    assert "At most {max_tools} tool calls" in prompts.AGENT_SYSTEM_PROMPT
    assert "Never invent a citation" in prompts.AGENT_SYSTEM_PROMPT
