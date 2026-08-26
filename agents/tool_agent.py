"""Tool-aware agent execution with explicit safety gates.

The LLM can select a registered tool, but it cannot grant itself permissions.
External and destructive actions require an explicit approval callback before
execution. The approval decision is made outside the LLM and is therefore
safe to replace with a UI, Discord prompt, CLI prompt, or future API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from core.logger import log
from core.tool_registry import Permission, ToolSpec, ToolRegistry, registry
from services.llm import llm


@dataclass(frozen=True)
class ToolRequest:
    """Validated request produced by the tool-selection step."""

    tool: str
    arguments: dict[str, Any]


ApprovalProvider = Callable[[ToolSpec, dict[str, Any]], bool]


class ToolAgent:
    """Execution gateway used by agents that need registered tools."""

    def __init__(
        self,
        approval_provider: ApprovalProvider | None = None,
        registry: ToolRegistry | None = None,
    ):
        self.approval_provider = approval_provider
        # Dependency injection keeps tests and isolated interaction sessions
        # independent from the process-wide registry.
        self.registry = registry or globals()["registry"]

    def available_tools(self) -> list[dict[str, str]]:
        return self.registry.describe()

    def select_tool(self, task: str) -> ToolRequest | None:
        """Ask the LLM to select one registered tool for *task*."""
        tools = self.available_tools()
        if not tools:
            return None

        prompt = (
            "You are the tool-selection layer of AI-OS.\n"
            "Choose a tool only when one in the catalog can perform the task.\n"
            "Return ONLY valid JSON in this exact shape:\n"
            '{"tool": "tool.name", "arguments": {}}\n'
            "If no tool is appropriate, return:\n"
            '{"tool": null, "arguments": {}}\n\n'
            f"Available tools:\n{json.dumps(tools, indent=2)}\n\n"
            f"Task:\n{task}"
        )
        result = llm.generate([
            {"role": "system", "content": "You select tools but never execute them directly."},
            {"role": "user", "content": prompt},
        ], agent="tool_selector")
        if not result.success:
            raise RuntimeError(result.error)
        try:
            data = json.loads(result.output.strip())
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Tool selector returned invalid JSON") from exc

        tool_name = data.get("tool")
        arguments = data.get("arguments", {})
        if tool_name is None:
            return None
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ValueError("Tool selector returned an invalid tool name")
        if not isinstance(arguments, dict):
            raise ValueError("Tool selector arguments must be a JSON object")
        self.registry.get(tool_name)
        return ToolRequest(tool=tool_name, arguments=arguments)

    def _ensure_approved(
        self,
        spec: ToolSpec,
        arguments: dict[str, Any],
        approved_permissions: set[Permission] | None,
        approval_provider: ApprovalProvider | None = None,
    ) -> set[Permission]:
        approved = set(approved_permissions or {Permission.READ})
        if spec.permission in approved:
            return approved

        provider = approval_provider or self.approval_provider
        if provider is None:
            raise PermissionError(
                f"Tool '{spec.name}' requires explicit approval for "
                f"'{spec.permission.value}' permission"
            )

        if not bool(provider(spec, arguments)):
            raise PermissionError(
                f"Tool '{spec.name}' requires explicit approval for "
                f"'{spec.permission.value}' permission"
            )

        approved.add(spec.permission)
        return approved

    def run(
        self,
        tool_name: str,
        *args,
        approved_permissions: set[Permission] | None = None,
        approval_provider: ApprovalProvider | None = None,
        **kwargs,
    ):
        log(f"ToolAgent invoking: {tool_name}")
        spec = self.registry.get(tool_name)
        approved = self._ensure_approved(spec, kwargs, approved_permissions, approval_provider)
        return self.registry.invoke(tool_name, *args, approved_permissions=approved, **kwargs)

    def run_task(
        self,
        task: str,
        *,
        approved_permissions: set[Permission] | None = None,
        approval_provider: ApprovalProvider | None = None,
    ) -> Any:
        """Select and execute a tool for a natural-language task."""
        request = self.select_tool(task)
        if request is None:
            return {
                "success": False,
                "tool": None,
                "error": "No registered tool is appropriate for this task.",
            }

        result = self.run(
            request.tool,
            approved_permissions=approved_permissions,
            approval_provider=approval_provider,
            **request.arguments,
        )
        return {"success": True, "tool": request.tool, "result": result}


# Shared execution gateway for agents. Applications should inject an explicit
# user-approval boundary when autonomous actions need elevated permissions.
tool_agent = ToolAgent()
