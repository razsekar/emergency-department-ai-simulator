import httpx

from app.modules.model_providers.application.service import ProviderService
from app.modules.model_providers.domain.providers import Provider, ollama_leaves_machine
from app.modules.model_providers.infrastructure import env_config, ollama_client
from tests.model_providers.conftest import FakeConfig, FakeGateway


def _svc(cfg):
    return ProviderService(FakeGateway(), cfg)


def test_models_merge_env_database_and_ollama_without_duplicates():
    cfg = FakeConfig(
        env_models={Provider.OPENAI: ["m-a", "m-b"]},
        db_models=[{"provider": "openai", "model_id": "m-a", "display_name": "dup"},
                   {"provider": "anthropic", "model_id": "c-1", "display_name": "Claude one"}],
        ollama=["llama-x:latest"],
    )
    got = {(m.provider, m.model_id): m for m in _svc(cfg).list_models()}
    assert set(got) == {("openai", "m-a"), ("openai", "m-b"), ("anthropic", "c-1"), ("ollama", "llama-x:latest")}
    assert got[("openai", "m-a")].source == "env"  # first source wins
    assert got[("ollama", "llama-x:latest")].source == "discovered" and not got[("ollama", "llama-x:latest")].cloud
    assert got[("anthropic", "c-1")].supports_tools is None  # unknown is reported as unknown, not assumed


def test_no_models_are_hardcoded():
    assert _svc(FakeConfig(ollama=[])).list_models() == []


def test_ollama_down_does_not_break_listing():
    cfg = FakeConfig(env_models={Provider.GEMINI: ["g-1"]}, ollama=httpx.ConnectError("refused"))
    assert [m.model_id for m in _svc(cfg).list_models()] == ["g-1"]


def test_ollama_probe_reports_reachability():
    assert _svc(FakeConfig(ollama=["x"])).provider_status(probe=True)[-1].reachable is True
    down = _svc(FakeConfig(ollama=httpx.ConnectError("refused"))).provider_status(probe=True)[-1]
    assert down.provider == "ollama" and down.reachable is False and "pull a model yourself" in down.detail
    assert _svc(FakeConfig()).provider_status(probe=False)[-1].reachable is None


def test_ollama_client_reads_api_tags(monkeypatch):
    seen = {}

    def fake_get(url, timeout):
        seen["url"] = url
        return httpx.Response(200, json={"models": [{"name": "a:1"}, {"name": "b:2"}, {"bad": 1}]},
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(ollama_client.httpx, "get", fake_get)
    assert ollama_client.list_models("http://ollama:11434/") == ["a:1", "b:2"]
    assert seen["url"] == "http://ollama:11434/api/tags"


def test_env_models_parsing(monkeypatch):
    monkeypatch.setenv("OPENAI_MODELS", " a , b,,c ")
    assert env_config.env_models(Provider.OPENAI) == ["a", "b", "c"]
    monkeypatch.delenv("GEMINI_MODELS", raising=False)
    assert env_config.env_models(Provider.GEMINI) == []


def test_configured_only_when_key_non_empty(monkeypatch):
    from app.modules.model_providers.domain.providers import SPECS
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    assert env_config.is_configured(SPECS[Provider.OPENAI]) is False
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert env_config.is_configured(SPECS[Provider.OPENAI]) is True
    assert env_config.is_configured(SPECS[Provider.OLLAMA]) is True


def test_remote_ollama_gets_disclosure():
    assert not ollama_leaves_machine("http://host.docker.internal:11434")
    assert not ollama_leaves_machine("http://localhost:11434")
    assert ollama_leaves_machine("https://gpu.example.org:11434")
    st = _svc(FakeConfig(ollama_url="https://gpu.example.org:11434")).provider_status()[-1]
    assert st.data_disclosure and "leave" in st.data_disclosure
