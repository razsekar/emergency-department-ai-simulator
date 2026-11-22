"""HTTP layer for tool metadata. Execution happens only inside the agent loop, never directly over HTTP."""
from fastapi import APIRouter, Depends

from app.modules.agent_tools.application.contracts import ToolDefinition
from app.modules.agent_tools.application.registry import tool_definitions
from app.modules.identity.public import Permission, require_permission

router = APIRouter(prefix="/api/agent", tags=["agent-tools"])


@router.get("/tools", response_model=list[ToolDefinition], dependencies=[Depends(require_permission(Permission.AGENT_RUN))])
def list_tools() -> list[ToolDefinition]:
    return tool_definitions()
