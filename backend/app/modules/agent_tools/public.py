"""Public interface of the agent_tools module. Other modules may import ONLY this file.

Owns the approved, executable LLM tools. Tools read data exclusively through other modules' public
interfaces; the LLM never receives database, SQL or shell access.

Contracts:

  tool_definitions()                       -> list[ToolDefinition]  (name, description, simplified JSON schema)
  openai_tools()                           -> list[dict]            (OpenAI/LiteLLM function-calling format)
  execute_tool(name, arguments, run_id=, sequence=) -> ToolResult   (never raises; validates input AND output;
                                                                     writes agent_execution_logs)
  refuse_tool(name, arguments, reason, ...)-> ToolResult            (records a call that was not executed)
  list_executions(run_id)                  -> list[ToolExecutionRecord]
  MAX_TOOL_INTERACTIONS                    -> 5 (the bound on tool interactions per user request)
  TOOL_NAMES                               -> tuple of the seven approved tool names
"""
from typing import Any

from app.modules.agent_tools.application.contracts import (
    ToolDefinition,
    ToolError,
    ToolExecutionRecord,
    ToolResult,
    ToolStatus,
)
from app.modules.agent_tools.application.executor import execute_tool, list_executions, refuse_tool
from app.modules.agent_tools.application.registry import TOOLS, tool_definitions
from app.modules.agent_tools.domain.tool_models import MAX_TOOL_INTERACTIONS

TOOL_NAMES: tuple[str, ...] = tuple(TOOLS)


def openai_tools() -> list[dict[str, Any]]:
    return [
        {"type": "function", "function": {"name": d.name, "description": d.description, "parameters": d.parameters}}
        for d in tool_definitions()
    ]


__all__ = [
    "MAX_TOOL_INTERACTIONS", "TOOL_NAMES", "ToolDefinition", "ToolError", "ToolExecutionRecord", "ToolResult",
    "ToolStatus", "execute_tool", "list_executions", "openai_tools", "refuse_tool", "tool_definitions",
]
