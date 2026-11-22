"""Composition of the comparison service with its real LLM adapter (overridable in tests via FastAPI dependencies)."""
from app.modules.ai_orchestration.application.comparison_service import ComparisonService
from app.modules.ai_orchestration.infrastructure.llm import ProvidersLlm


def get_comparison_service() -> ComparisonService:
    return ComparisonService(ProvidersLlm())
