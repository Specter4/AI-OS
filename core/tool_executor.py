"""
AI-OS Tool Executor

Controlled execution boundary between agents and registered tools.

The executor deliberately does not let an agent call arbitrary Python
functions. A tool must first exist in the ToolRegistry, and its permission
must be explicitly approved for the current execution.
"""

from dataclasses import dataclass
from typing import Any

from core.tool_registry import Permission, ToolRegistry, registry


@dataclass(frozen=True)
class ToolExecutionResult:
    """Structured result from a tool execution attempt."""

    success: bool
    tool: str
    output: Any = None
    error: str | None = None


class ToolExecutor:
    """Safely execute tools registered with AI-OS."""

    def __init__(self, tool_registry: ToolRegistry | None = None) -> None:
        self.registry = tool_registry or registry

    def execute(
        self,
        tool_name: str,
        *args: Any,
        approved_permissions: set[Permission] | None = None,
        **kwargs: Any,
    ) -> ToolExecutionResult:
        try:
            output = self.registry.invoke(
                tool_name,
                *args,
                approved_permissions=approved_permissions,
                **kwargs,
            )
            return ToolExecutionResult(
                success=True,
                tool=tool_name,
                output=output,
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                tool=tool_name,
                error=str(exc),
            )


executor = ToolExecutor()
