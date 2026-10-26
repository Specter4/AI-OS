"""Built-in tool registrations for AI-OS."""

from core.tool_registry import Permission, registry
from tools.computer import computer
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
        (
            "desktop.screen_size",
            "Read the current desktop screen dimensions.",
            computer.screen_size,
            Permission.READ,
        ),
        (
            "desktop.click",
            "Click a validated on-screen coordinate; requires write permission.",
            computer.click,
            Permission.WRITE,
        ),
        (
            "desktop.move_mouse",
            "Move the pointer to a validated on-screen coordinate; requires write permission.",
            computer.move_mouse,
            Permission.WRITE,
        ),
        (
            "desktop.type_text",
            "Type bounded text into the currently focused control; requires write permission.",
            computer.type_text,
            Permission.WRITE,
        ),
        (
            "desktop.press_key",
            "Press one allowlisted key without key-chord execution; requires write permission.",
            computer.press_key,
            Permission.WRITE,
        ),
        (
            "desktop.screenshot",
            "Save a desktop screenshot without overwriting an existing file unless explicitly allowed.",
            computer.screenshot,
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
