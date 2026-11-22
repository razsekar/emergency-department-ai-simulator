"""Validated, logged tool execution. `execute_tool` never raises: every failure becomes a ToolResult."""
import json
import logging
import time
import uuid
from typing import Any

from pydantic import ValidationError

from app.modules.agent_tools.application.contracts import ToolError, ToolExecutionRecord, ToolResult
from app.modules.agent_tools.application.registry import TOOLS
from app.modules.agent_tools.domain.errors import ToolInputError
from app.modules.agent_tools.infrastructure.repository import ExecutionLogRepository
from app.platform.db import unit_of_work

log = logging.getLogger("app.agent_tools")

MAX_ARGUMENT_CHARS = 4000


def _summarize(output: dict[str, Any] | None) -> dict[str, Any]:
    """Compact, log-friendly summary: scalars verbatim, collections as sizes."""
    if not output:
        return {}
    summary: dict[str, Any] = {}
    for key, value in output.items():
        if isinstance(value, (list, tuple)):
            summary[key] = f"list[{len(value)}]"
        elif isinstance(value, dict):
            summary[key] = f"object[{len(value)} keys]"
        elif isinstance(value, str):
            summary[key] = value[:80]
        else:
            summary[key] = value
    return summary


def _persist(result: ToolResult, run_id: uuid.UUID | None) -> None:
    """Audit log of every tool interaction. A logging failure must never break the tool call."""
    try:
        with unit_of_work() as session:
            ExecutionLogRepository(session).add(
                run_id=run_id, sequence=result.sequence, tool_name=result.tool_name, status=result.status,
                arguments=result.arguments, result_summary=_summarize(result.output),
                error=result.error.message if result.error else None, duration_ms=result.duration_ms,
                data_version=result.data_version,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not persist tool execution log: %s", type(exc).__name__)


def _parse_arguments(arguments: str | dict[str, Any] | None) -> dict[str, Any]:
    if arguments is None or arguments == "":
        return {}
    if isinstance(arguments, str):
        if len(arguments) > MAX_ARGUMENT_CHARS:
            raise ValueError("Arguments are too large")
        parsed = json.loads(arguments)
    else:
        parsed = arguments
    if not isinstance(parsed, dict):
        raise ValueError("Arguments must be a JSON object")
    return parsed


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def execute_tool(
    name: str, arguments: str | dict[str, Any] | None, *, run_id: uuid.UUID | None = None, sequence: int = 0
) -> ToolResult:
    started = time.perf_counter()

    def finish(status: str, args: dict[str, Any], output=None, error: ToolError | None = None) -> ToolResult:
        version = output.get("data_version") if isinstance(output, dict) else None
        result = ToolResult(
            tool_name=name, status=status, arguments=args, output=output, error=error,
            duration_ms=int((time.perf_counter() - started) * 1000), data_version=version, sequence=sequence,
        )
        _persist(result, run_id)
        return result

    spec = TOOLS.get(name)
    if spec is None:
        return finish("unknown_tool", {}, error=ToolError(code="unknown_tool", message=f"'{name[:64]}' is not an approved tool"))

    try:
        raw = _parse_arguments(arguments)
    except (ValueError, TypeError) as exc:
        return finish("invalid_arguments", {}, error=ToolError(code="invalid_arguments", message=f"Arguments are not valid JSON: {exc}"[:300]))

    try:
        validated = spec.input_model.model_validate(raw)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors())[:500]
        return finish("invalid_arguments", _jsonable(raw), error=ToolError(code="invalid_arguments", message=problems))
    args = _jsonable(validated.model_dump())

    try:
        produced = spec.handler(validated)
    except ToolInputError as exc:
        return finish("invalid_arguments", args, error=ToolError(code="invalid_arguments", message=str(exc)[:300]))
    except Exception as exc:  # noqa: BLE001 - tool failures are reported to the agent, not raised
        log.warning("Tool %s failed: %s", name, type(exc).__name__)
        return finish("error", args, error=ToolError(code="tool_failed", message=f"The tool failed ({type(exc).__name__})."))

    try:
        output = _jsonable(spec.output_model.model_validate(produced).model_dump())
    except ValidationError:
        log.warning("Tool %s produced output that failed validation", name)
        return finish("error", args, error=ToolError(code="invalid_tool_output", message="The tool returned malformed data."))
    return finish("ok", args, output=output)


def refuse_tool(
    name: str, arguments: str | dict[str, Any] | None, reason: str, *, run_id: uuid.UUID | None = None, sequence: int = 0
) -> ToolResult:
    """Record a call that was not executed (for example the tool budget is exhausted)."""
    try:
        args = _jsonable(_parse_arguments(arguments))
    except (ValueError, TypeError):
        args = {}
    result = ToolResult(
        tool_name=name, status="refused", arguments=args, error=ToolError(code="refused", message=reason),
        duration_ms=0, sequence=sequence,
    )
    _persist(result, run_id)
    return result


def list_executions(run_id: uuid.UUID) -> list[ToolExecutionRecord]:
    with unit_of_work() as session:
        rows = ExecutionLogRepository(session).list_for_run(run_id)
        return [
            ToolExecutionRecord(
                id=str(r.id), run_id=str(r.run_id) if r.run_id else None, sequence=r.sequence, tool_name=r.tool_name,
                status=r.status, arguments=r.arguments, result_summary=r.result_summary, error=r.error,
                duration_ms=r.duration_ms, data_version=r.data_version, created_at=r.created_at.isoformat(),
            )
            for r in rows
        ]
