"""Tool-aware agent execution.

Provides a small, controlled loop for agents that need registered tools:
1. discover available tools
2. ask the LLM to select one
3. validate the requested tool and arguments
4. invoke it through the permission-aware registry

The LLM never receives direct access to Python callables.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.logger import log
from core.tool_registry import Permission, registry
from services.llm import llm


@dataclass(frozen=True)
class ToolRequest:
    """Validated request produced by the tool-selection step."""

    tool: str
    arguments: dict[str, Any]


class ToolAgent:
    """Execution gateway used by agents that need registered tools."""

    def available_tools(self) -> list[dict[str, str]]:
        return registry.describe()

    def select_tool(self, task: str) -> ToolRequest | None:
        """Ask the LLM to select one registered tool for *task*.

        Returning ``None`` is a valid outcome when no registered tool is
        appropriate. The model is constrained to the current registry catalog.
        """
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

        result = llm.generate(
            [
                {
                    "role": "system",
                    "content": "You select tools but never execute them directly.",
                },
                {"role": "user", "content": prompt},
            ],
            agent="tool_selector",
        )

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

        # Validate against the registry before execution.
        registry.get(tool_name)
        return ToolRequest(tool=tool_name, arguments=arguments)

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

    def run_task(
        self,
        task: str,
        *,
        approved_permissions: set[Permission] | None = None,
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
            **request.arguments,
        )

        return {
            "success": True,
            "tool": request.tool,
            "result": result,
        }


# Shared execution gateway for agents.
tool_agent = ToolAgent()
