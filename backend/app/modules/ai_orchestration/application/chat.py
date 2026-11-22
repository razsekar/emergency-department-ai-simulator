"""RAG-grounded chat. Policy excerpts and (optionally) a fresh simulation snapshot are put in the prompt;
retrieved text is delimited as untrusted data, flagged chunks are withheld, citations are verified afterwards."""
import json
import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any

from app.modules.ai_orchestration.application import contracts as c
from app.modules.ai_orchestration.application.ports import LlmPort
from app.modules.ai_orchestration.application.snapshot import take_snapshot
from app.modules.ai_orchestration.domain.citations import RetrievedRef, check_citations
from app.modules.ai_orchestration.domain.prompts import CHAT_SYSTEM_PROMPT
from app.modules.ai_orchestration.infrastructure.models import ChatMessageRow
from app.modules.ai_orchestration.infrastructure.repository import ChatRepository
from app.modules.model_providers.public import ChatMessage, ChatRequest, ChatResponse, Usage
from app.modules.rag import public as rag
from app.platform.db import unit_of_work
from app.platform.errors import NotFoundError

log = logging.getLogger("app.ai_orchestration")

HISTORY_MESSAGES = 10
RAG_K = 4
EXCERPT_CHARS = 700


def _message_view(row: ChatMessageRow) -> c.ChatMessageView:
    return c.ChatMessageView(
        id=row.id, role=row.role, content=row.content, sources=row.sources, citation_check=row.citation_check,
        provider=row.provider, model=row.model, latency_ms=row.latency_ms, prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens, data_disclosure=row.data_disclosure, created_at=row.created_at,
    )


def _live_block() -> str:
    snap = take_snapshot()
    return (
        f"Verified live simulation data (scenario: {snap.scenario_name}, data version {snap.data_version}):\n"
        + json.dumps(snap.metrics)
    )


class _Prepared:
    """Everything needed to call the model, built (and the user message stored) before any bytes are streamed."""

    def __init__(self, session_id, request: ChatRequest, sources: list[dict[str, Any]], user_view: c.ChatMessageView,
                 provider: str, model: str) -> None:
        self.session_id, self.request, self.sources, self.user_view = session_id, request, sources, user_view
        self.provider, self.model = provider, model


class ChatService:
    def __init__(self, llm: LlmPort) -> None:
        self._llm = llm

    # ------------------------------------------------------------------ sessions
    def create_session(self, title: str, owner: str) -> c.ChatSessionView:
        with unit_of_work() as session:
            row = ChatRepository(session).create_session(title, owner)
            return c.ChatSessionView(id=row.id, title=row.title, created_at=row.created_at, updated_at=row.updated_at)

    def list_sessions(self, owner: str, limit: int = 50, offset: int = 0) -> list[c.ChatSessionView]:
        with unit_of_work() as session:
            return [c.ChatSessionView(id=r.id, title=r.title, created_at=r.created_at, updated_at=r.updated_at)
                    for r in ChatRepository(session).list_sessions(owner, limit, offset)]

    def get_session(self, session_id: uuid.UUID, owner: str) -> c.ChatSessionDetail:
        with unit_of_work() as session:
            repo = ChatRepository(session)
            row = repo.get_session(session_id, owner)
            if row is None:
                raise NotFoundError("Conversation not found")
            return c.ChatSessionDetail(
                id=row.id, title=row.title, created_at=row.created_at, updated_at=row.updated_at,
                messages=[_message_view(m) for m in repo.messages(session_id)],
            )

    # ------------------------------------------------------------------ messaging
    def _prepare(self, session_id: uuid.UUID, req: c.SendMessageRequest, owner: str) -> _Prepared:
        self._llm.ensure_configured(req.provider, req.model)
        with unit_of_work() as session:  # ownership check first, so strangers learn nothing
            if ChatRepository(session).get_session(session_id, owner) is None:
                raise NotFoundError("Conversation not found")

        chunks = []
        if req.use_rag:
            try:
                chunks = rag.search(req.content, RAG_K)
            except Exception as exc:  # noqa: BLE001 - answer without policy rather than fail the chat
                log.warning("Policy search unavailable: %s", type(exc).__name__)
        sources = [
            c.RetrievedPolicyView(
                document_name=h.document_name, page=h.page_number, score=h.score, matched_query=req.content,
                excerpt="[withheld: possible prompt injection in source text]" if h.injection_flagged
                else h.excerpt[:EXCERPT_CHARS],
                flagged=h.injection_flagged,
            ).model_dump(mode="json")
            for h in chunks
        ]

        system = CHAT_SYSTEM_PROMPT
        if req.include_live_data:
            system += "\n" + _live_block()
        system += "\n\nRetrieved policy excerpts:\n" + (rag.format_context(chunks) if chunks else "(none retrieved)")

        with unit_of_work() as session:
            repo = ChatRepository(session)
            history = [ChatMessage(role=m.role, content=m.content) for m in repo.messages(session_id, HISTORY_MESSAGES)]
            user_row = repo.add_message(session_id=session_id, role="user", content=req.content)
            user_view = _message_view(user_row)

        request = ChatRequest(
            provider=req.provider, model=req.model, temperature=req.temperature,
            messages=[ChatMessage(role="system", content=system), *history,
                      ChatMessage(role="user", content=req.content)],
        )
        return _Prepared(session_id, request, sources, user_view, req.provider, req.model)

    def _store_reply(self, prep: _Prepared, text: str, resp: ChatResponse | None, latency_ms: int) -> c.ChatMessageView:
        citation = check_citations(
            text, [RetrievedRef(s["document_name"], s["page"]) for s in prep.sources if not s["flagged"]]
        )
        usage = resp.usage if resp else Usage()
        with unit_of_work() as session:
            row = ChatRepository(session).add_message(
                session_id=prep.session_id, role="assistant", content=text, sources=prep.sources,
                citation_check=citation, provider=prep.provider, model=prep.model, latency_ms=latency_ms,
                prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
                data_disclosure=resp.data_disclosure if resp else None,
            )
            return _message_view(row)

    def send_message(self, session_id: uuid.UUID, req: c.SendMessageRequest, owner: str) -> c.SendMessageResponse:
        prep = self._prepare(session_id, req, owner)
        started = time.perf_counter()
        resp = self._llm.complete(prep.request)  # provider errors propagate as safe HTTP errors
        latency = int((time.perf_counter() - started) * 1000)
        reply = self._store_reply(prep, resp.content or "", resp, latency)
        return c.SendMessageResponse(user_message=prep.user_view, assistant_message=reply, usage=resp.usage,
                                     estimated_cost_usd=resp.estimated_cost_usd)

    def prepare_stream(self, session_id: uuid.UUID, req: c.SendMessageRequest, owner: str) -> _Prepared:
        """Validate, retrieve and store the user message BEFORE streaming so failures are real HTTP errors."""
        return self._prepare(session_id, req, owner)

    def stream_events(self, prep: _Prepared) -> Iterator[dict[str, Any]]:
        yield {"type": "sources", "sources": prep.sources, "user_message": prep.user_view.model_dump(mode="json")}
        started = time.perf_counter()
        text: list[str] = []
        final: ChatResponse | None = None
        for event in self._llm.stream(prep.request):
            if event.type == "delta" and event.content:
                text.append(event.content)
                yield {"type": "delta", "content": event.content}
            elif event.type == "done":
                final = event.response
            elif event.type == "error":
                yield {"type": "error", "message": event.message or "The provider stream failed."}
                return
        latency = int((time.perf_counter() - started) * 1000)
        reply = self._store_reply(prep, "".join(text), final, latency)
        yield {"type": "done", "assistant_message": reply.model_dump(mode="json"),
               "usage": final.usage.model_dump() if final else None,
               "estimated_cost_usd": final.estimated_cost_usd if final else None}
