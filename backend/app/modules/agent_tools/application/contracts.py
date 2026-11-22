"""Typed contracts exposed by the agent_tools module."""
from typing import Any, Literal

from pydantic import BaseModel

ToolStatus = Literal["ok", "invalid_arguments", "unknown_tool", "error", "refused"]


class ToolError(BaseModel):
    code: str
    message: str


class ToolResult(BaseModel):
    """Outcome of one tool interaction. Never raises: failures are data the agent can inspect."""

    tool_name: str
    status: ToolStatus
    arguments: dict[str, Any]
    output: dict[str, Any] | None = None
    error: ToolError | None = None
    duration_ms: int
    data_version: int | None = None
    sequence: int = 0


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]  # simplified JSON schema


class ToolExecutionRecord(BaseModel):
    id: str
    run_id: str | None
    sequence: int
    tool_name: str
    status: str
    arguments: dict[str, Any]
    result_summary: dict[str, Any]
    error: str | None
    duration_ms: int
    data_version: int | None
    created_at: str
