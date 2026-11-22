"""Composition of the demo service with the real agent service (overridable in tests)."""
from app.modules.ai_orchestration.application.demo_service import DemoService
from app.modules.ai_orchestration.application.wiring import get_agent_service


def get_demo_service() -> DemoService:
    return DemoService(get_agent_service())
