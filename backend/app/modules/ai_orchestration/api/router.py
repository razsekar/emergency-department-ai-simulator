"""HTTP layer: validation, RBAC and serialisation only. All logic lives in the application layer."""
import json
import uuid
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.modules.ai_orchestration.application import contracts as c
from app.modules.ai_orchestration.application import service
from app.modules.ai_orchestration.application.chat import ChatService
from app.modules.ai_orchestration.application.service import AgentService
from app.modules.ai_orchestration.application.wiring import get_agent_service, get_chat_service
from app.modules.identity.public import CurrentUser, Permission, require_permission

router = APIRouter(tags=["ai-orchestration"])

agent_user = require_permission(Permission.AGENT_RUN)
chat_user = require_permission(Permission.AI_CHAT)


# ------------------------------------------------------------------ agent
@router.post("/api/agent/run", response_model=c.AgentRunResponse)
def run_agent(body: c.AgentRunRequest, user: CurrentUser = Depends(agent_user),
              svc: AgentService = Depends(get_agent_service)) -> c.AgentRunResponse:
    return svc.run(question=body.question, provider=body.provider, model=body.model, temperature=body.temperature,
                   mode=body.mode, run_type="agent", actor=user.username)


@router.get("/api/agent/demo-question")
def demo_question(_: CurrentUser = Depends(agent_user)) -> dict[str, str]:
    return {"question": service.demo_question()}


@router.post("/api/agent/demo-run", response_model=c.AgentRunResponse)
def demo_run(body: c.DemoRunRequest, user: CurrentUser = Depends(agent_user),
             svc: AgentService = Depends(get_agent_service)) -> c.AgentRunResponse:
    return svc.demo_run(provider=body.provider, model=body.model, temperature=body.temperature, mode=body.mode,
                        actor=user.username)


@router.get("/api/agent/runs", response_model=c.RunPage, dependencies=[Depends(agent_user)])
def list_runs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
              run_type: str | None = Query(None, pattern="^(agent|demo)$"),
              scenario_key: str | None = Query(None, max_length=64),
              data_version: int | None = Query(None, ge=0)) -> c.RunPage:
    return service.list_runs(limit, offset, run_type, scenario_key, data_version)


@router.get("/api/agent/runs/{run_id}", response_model=c.AgentRunResponse, dependencies=[Depends(agent_user)])
def get_run(run_id: uuid.UUID) -> c.AgentRunResponse:
    return service.get_run(run_id)


# ------------------------------------------------------------------ chat
@router.post("/api/chat/sessions", response_model=c.ChatSessionView, status_code=201)
def create_session(body: c.CreateSessionRequest, user: CurrentUser = Depends(chat_user),
                   svc: ChatService = Depends(get_chat_service)) -> c.ChatSessionView:
    return svc.create_session(body.title, user.username)


@router.get("/api/chat/sessions", response_model=list[c.ChatSessionView])
def list_sessions(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                  user: CurrentUser = Depends(chat_user),
                  svc: ChatService = Depends(get_chat_service)) -> list[c.ChatSessionView]:
    return svc.list_sessions(user.username, limit, offset)


@router.get("/api/chat/sessions/{session_id}", response_model=c.ChatSessionDetail)
def get_session(session_id: uuid.UUID, user: CurrentUser = Depends(chat_user),
                svc: ChatService = Depends(get_chat_service)) -> c.ChatSessionDetail:
    return svc.get_session(session_id, user.username)


@router.post("/api/chat/sessions/{session_id}/messages", response_model=c.SendMessageResponse)
def send_message(session_id: uuid.UUID, body: c.SendMessageRequest, user: CurrentUser = Depends(chat_user),
                 svc: ChatService = Depends(get_chat_service)) -> c.SendMessageResponse:
    return svc.send_message(session_id, body, user.username)


def _frame(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"


@router.post("/api/chat/sessions/{session_id}/messages/stream")
def stream_message(session_id: uuid.UUID, body: c.SendMessageRequest, user: CurrentUser = Depends(chat_user),
                   svc: ChatService = Depends(get_chat_service)) -> StreamingResponse:
    prepared = svc.prepare_stream(session_id, body, user.username)  # failures here are real HTTP errors
    events = svc.stream_events(prepared)

    def frames() -> Iterator[str]:
        for event in events:
            yield _frame(event)

    return StreamingResponse(frames(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
