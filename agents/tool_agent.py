"""Tool-aware agent execution.

Keeps tool selection separate from tool implementation and enforces registry
permissions before invoking a capability.
"""

from __future__ import annotations

from core.logger import log
from core.tool_registry import Permission, registry


class ToolAgent:
    """Execution gateway used by agents that need registered tools."""

    def available_tools(self) -> list[dict[str, str]]:
        return registry.describe()

    def run(
        self,
        tool_name: str,
        *args,
        approved_permissions: set[Permission] | None = None,
        **kwargs,
    ):
        log(f"ToolAgent invoking: {tool_name}")
        return registry.invoke(
            tool_name,
            *args,
            approved_permissions=approved_permissions,
            **kwargs,
        )


# Shared execution gateway for agents.
tool_agent = ToolAgent()
