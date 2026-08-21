"""
AI-OS Tool Gateway

Single execution boundary between agents and registered tools.

Agents should call this gateway instead of importing arbitrary tool modules.
This gives AI-OS one place to add logging, approvals, quotas, and auditing.
"""

from typing import Any

from core.logger import log
from core.tool_registry import Permission, registry

# Import registrations once when the gateway is loaded.
import tools.registry  # noqa: F401,E402


def available_tools() -> list[dict[str, str]]:
    """Return discoverable tools without exposing Python callables."""
    return registry.describe()


def invoke_tool(
    name: str,
    *args: Any,
    approved_permissions: set[Permission] | None = None,
    **kwargs: Any,
) -> Any:
    """Invoke one registered tool through the centralized safety boundary."""
    log(f"Tool requested: {name}")

    result = registry.invoke(
        name,
        *args,
        approved_permissions=approved_permissions,
        **kwargs,
    )

    log(f"Tool completed: {name}")
    return result
