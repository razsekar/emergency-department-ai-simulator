"""ORM model for ai_orchestration.demo_runs. Private to this module."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.ai_orchestration.infrastructure.models import Base


class DemoRunRow(Base):
    __tablename__ = "demo_runs"
    __table_args__ = (UniqueConstraint("session_id", "run_number", name="uq_demo_runs_session_number"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    run_number: Mapped[int] = mapped_column(Integer)
    run_label: Mapped[str] = mapped_column(String(16))
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    scenario_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scenario_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    data_version: Mapped[int] = mapped_column(Integer)
    patient_record_count: Mapped[int] = mapped_column(Integer)
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    verification: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    tools_executed: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    retrieved_policies: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    question: Mapped[str] = mapped_column(Text)
    question_sha256: Mapped[str] = mapped_column(String(64))
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(255))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
