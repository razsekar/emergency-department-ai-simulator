"""ORM models for comparison runs in the `ai_orchestration` schema. Private to this module."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.ai_orchestration.infrastructure.models import Base


class ComparisonRunRow(Base):
    __tablename__ = "ai_comparison_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text)
    scenario_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scenario_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    data_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_version_consistent: Mapped[bool] = mapped_column(Boolean, default=True)
    snapshot_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    shared_tools: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    shared_policies: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    context_sha256: Mapped[str] = mapped_column(String(64))
    selections: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(16))
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComparisonResultRow(Base):
    __tablename__ = "ai_comparison_results"
    __table_args__ = (UniqueConstraint("comparison_id", "position", name="uq_ai_comparison_result_position"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_orchestration.ai_comparison_runs.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(255))
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_calling_supported: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    data_disclosure: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    citation_check: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
