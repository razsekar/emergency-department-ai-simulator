"""Application settings, loaded from environment variables (never from frontend code)."""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ED Patient Flow Simulator"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://edsim:edsim@db:5432/edsim"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4200"])
    log_level: str = "INFO"

    # LLM call limits. A small local model on CPU (Ollama) can take many minutes per answer, so the
    # timeout is generous; the output cap bounds the final answer so one call cannot run away.
    # Ollama silently TRUNCATES the start of a prompt that exceeds its context window (default 4096), which
    # drops the system rules, briefing and question. The agent prompt is ~4-5k tokens, so ask for more.
    ollama_num_ctx: int = Field(default=8192, ge=2048, le=131072)
    llm_timeout_seconds: int = Field(default=1200, ge=10, le=7200)
    agent_max_output_tokens: int = Field(default=1200, ge=64, le=32000)

    # Request body cap (MB), enforced from Content-Length before the body is read. It must stay a
    # little above KB_MAX_UPLOAD_MB (default 10) to leave room for multipart overhead.
    max_request_body_mb: int = Field(default=12, ge=1, le=1024)

    # Rate limits. Defaults are generous so a live demo is never blocked; set a value to 0 to disable
    # one bucket, or RATE_LIMIT_ENABLED=false to disable everything.
    rate_limit_enabled: bool = True
    rate_limit_agent_per_minute: int = Field(default=30, ge=0)  # agent run, demo step, comparison
    rate_limit_chat_per_minute: int = Field(default=60, ge=0)
    rate_limit_upload_per_minute: int = Field(default=20, ge=0)  # document upload, load-samples
    # Login back-off: after N consecutive failures for a (client, username) the pair is locked out
    # for base * 2^(failures-N) seconds, capped at the maximum. A success clears the counter.
    login_max_failures: int = Field(default=5, ge=1)
    login_failure_window_seconds: int = Field(default=300, ge=1)
    login_lockout_base_seconds: int = Field(default=15, ge=1)
    login_lockout_max_seconds: int = Field(default=300, ge=1)

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard_origin(cls, origins: list[str]) -> list[str]:
        if any(o.strip() == "*" for o in origins):
            raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed")
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
