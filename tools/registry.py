"""Built-in tool registrations for AI-OS."""

from core.tool_registry import Permission, registry
from tools.filesystem import filesystem


def _list_tools():
    """Return a compact capability description for agent/tool selection."""
    return registry.describe()


def _register_builtin_tools() -> None:
    builtins = [
        (
            "system.list_tools",
            "List capabilities currently available to AI-OS agents.",
            _list_tools,
            Permission.READ,
        ),
        (
            "filesystem.read_file",
            "Read a UTF-8 text file inside the AI-OS workspace.",
            filesystem.read_file,
            Permission.READ,
        ),
        (
            "filesystem.list_directory",
            "List files and directories inside the AI-OS workspace.",
            filesystem.list_directory,
            Permission.READ,
        ),
        (
            "filesystem.write_file",
            "Create or replace a UTF-8 text file inside the AI-OS workspace.",
            filesystem.write_file,
            Permission.WRITE,
        ),
        (
            "filesystem.create_directory",
            "Create a directory inside the AI-OS workspace.",
            filesystem.create_directory,
            Permission.WRITE,
        ),
    ]

    existing = {tool.name for tool in registry.list()}
    for name, description, handler, permission in builtins:
        if name not in existing:
            registry.register(
                name=name,
                description=description,
                handler=handler,
                permission=permission,
            )


_register_builtin_tools()
