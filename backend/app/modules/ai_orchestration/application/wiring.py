"""Composition of services with their real adapters. Routers depend on these functions (overridable in tests)."""
from functools import lru_cache

from app.modules.ai_orchestration.application.chat import ChatService
from app.modules.ai_orchestration.application.service import AgentService
from app.modules.ai_orchestration.infrastructure.llm import ProvidersLlm


@lru_cache
def _llm() -> ProvidersLlm:
    return ProvidersLlm()


def get_agent_service() -> AgentService:
    return AgentService(_llm())


def get_chat_service() -> ChatService:
    return ChatService(_llm())
