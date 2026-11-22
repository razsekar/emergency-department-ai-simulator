"""Liveness and readiness endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.db import get_session

router = APIRouter(prefix="/api/health", tags=["health"])


class LiveResponse(BaseModel):
    status: str


class DbHealthResponse(BaseModel):
    status: str
    pgvector: bool


@router.get("", response_model=LiveResponse)
def live() -> LiveResponse:
    return LiveResponse(status="ok")


@router.get("/db", response_model=DbHealthResponse)
def db_health(session: Session = Depends(get_session)) -> DbHealthResponse:
    session.execute(text("SELECT 1"))
    has_vector = session.execute(
        text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
    ).scalar_one()
    return DbHealthResponse(status="ok", pgvector=bool(has_vector))
