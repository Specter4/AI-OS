"""
AI-OS Tool Registry

Central registry for capabilities exposed to agents.

The registry deliberately keeps tool discovery separate from tool execution.
Agents can discover capabilities without receiving unrestricted access to the
whole Python process.
"""

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Any, Callable, List


class Permission(str, Enum):
    """Risk level required to invoke a tool."""

    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    permission: Permission = Permission.READ


class ToolRegistry:
    """Thread-safe registry of AI-OS tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._lock = RLock()

    def register(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        permission: Permission = Permission.READ,
    ) -> ToolSpec:
        if not name or not name.strip():
            raise ValueError("Tool name cannot be empty")
        if not callable(handler):
            raise TypeError("Tool handler must be callable")

        spec = ToolSpec(
            name=name.strip(),
            description=description.strip(),
            handler=handler,
            permission=permission,
        )

        with self._lock:
            if spec.name in self._tools:
                raise ValueError(f"Tool already registered: {spec.name}")
            self._tools[spec.name] = spec

        return spec

    def unregister(self, name: str) -> None:
        with self._lock:
            self._tools.pop(name, None)

    def get(self, name: str) -> ToolSpec:
        with self._lock:
            try:
                return self._tools[name]
            except KeyError as exc:
                raise KeyError(f"Unknown tool: {name}") from exc

    def list(self) -> list[ToolSpec]:
        with self._lock:
            return sorted(self._tools.values(), key=lambda tool: tool.name)

    def describe(self) -> List[dict[str, str]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "permission": tool.permission.value,
            }
            for tool in self.list()
        ]

    def invoke(
        self,
        name: str,
        *args: Any,
        approved_permissions: set[Permission] | None = None,
        **kwargs: Any,
    ) -> Any:
        tool = self.get(name)
        approved = approved_permissions or {Permission.READ}

        if tool.permission not in approved:
            raise PermissionError(
                f"Tool '{name}' requires '{tool.permission.value}' permission"
            )

        return tool.handler(*args, **kwargs)


registry = ToolRegistry()
