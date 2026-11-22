"""HTTP layer: validation and RBAC only. All logic lives in the module's public interface."""
import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.modules.identity.public import Permission, require_permission
from app.platform.ratelimit import rate_limit
from app.modules.model_providers import public as providers
from app.modules.model_providers.application.contracts import (
    ChatRequest,
    ChatResponse,
    ModelInfo,
    ProviderStatus,
    RegisterModelRequest,
    StreamEvent,
)

router = APIRouter(prefix="/api/providers", tags=["model-providers"])


@router.get("/status", response_model=list[ProviderStatus], dependencies=[Depends(require_permission(Permission.MODELS_READ))])
def status(probe: bool = Query(False, description="Also check that Ollama is reachable")) -> list[ProviderStatus]:
    return providers.provider_status(probe=probe)


@router.get("/models", response_model=list[ModelInfo], dependencies=[Depends(require_permission(Permission.MODELS_READ))])
def models() -> list[ModelInfo]:
    return providers.list_models()


@router.post("/chat", response_model=ChatResponse,
             dependencies=[Depends(require_permission(Permission.AI_CHAT)), Depends(rate_limit("chat"))])
def chat(request: ChatRequest) -> ChatResponse:
    return providers.complete(request)


def _frame(event: StreamEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.model_dump(mode='json'))}\n\n"


@router.post("/chat/stream",
             dependencies=[Depends(require_permission(Permission.AI_CHAT)), Depends(rate_limit("chat"))])
def chat_stream(request: ChatRequest) -> StreamingResponse:
    events = providers.stream(request)
    # Pull the first event now: configuration/validation errors then surface as real HTTP errors
    # (409/422) instead of appearing mid-stream after a 200 has been sent.
    head = next(events, None)

    def frames() -> Iterator[str]:
        if head is not None:
            yield _frame(head)
        for event in events:
            yield _frame(event)

    return StreamingResponse(frames(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/models", status_code=204, dependencies=[Depends(require_permission(Permission.MODELS_CONFIGURE))])
def register_model(request: RegisterModelRequest) -> None:
    providers.register_model(request)


@router.delete("/models/{provider}/{model_id:path}", status_code=204, dependencies=[Depends(require_permission(Permission.MODELS_CONFIGURE))])
def unregister_model(provider: str, model_id: str) -> None:
    providers.unregister_model(provider, model_id)
