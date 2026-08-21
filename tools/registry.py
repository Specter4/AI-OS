"""Built-in tool registrations for AI-OS."""

from core.tool_registry import Permission, registry


def _list_tools():
    """Return a compact capability description for agent/tool selection."""
    return registry.describe()


def _register_builtin_tools() -> None:
    if not any(tool.name == "system.list_tools" for tool in registry.list()):
        registry.register(
            name="system.list_tools",
            description="List capabilities currently available to AI-OS agents.",
            handler=_list_tools,
            permission=Permission.READ,
        )


_register_builtin_tools()
