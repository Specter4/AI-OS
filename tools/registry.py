"""Built-in tool registrations for AI-OS."""

from core.tool_registry import Permission, registry
from tools.computer import computer
from tools.applications import applications
from tools.filesystem import filesystem


def _list_tools():
    """Return a compact capability description for agent/tool selection."""
    return registry.describe()


def _register_builtin_tools() -> None:
    builtins = [
        ("system.list_tools", "List capabilities currently available to AI-OS agents.", _list_tools, Permission.READ),
        ("filesystem.read_file", "Read a UTF-8 text file inside configured local access roots.", filesystem.read_file, Permission.READ),
        ("filesystem.read_file_base64", "Read arbitrary binary file contents as base64 inside configured local access roots.", filesystem.read_file_base64, Permission.READ),
        ("filesystem.list_directory", "List files and directories inside configured local access roots.", filesystem.list_directory, Permission.READ),
        ("filesystem.search_files", "Search for files by filename pattern inside configured local access roots.", filesystem.search_files, Permission.READ),
        ("filesystem.get_file_info", "Read metadata for a file or directory inside configured local access roots.", filesystem.get_file_info, Permission.READ),
        ("filesystem.write_file", "Create a UTF-8 text file; replacing an existing file requires explicit overwrite=true.", filesystem.write_file, Permission.WRITE),
        ("filesystem.write_file_base64", "Create a binary file from base64 content; replacing an existing file requires explicit overwrite=true.", filesystem.write_file_base64, Permission.WRITE),
        ("filesystem.create_directory", "Create a directory inside configured local access roots.", filesystem.create_directory, Permission.WRITE),
        ("filesystem.copy_file", "Copy a file to another configured local path without overwriting by default.", filesystem.copy_file, Permission.WRITE),
        ("filesystem.move_file", "Move a file to another configured local path without overwriting by default.", filesystem.move_file, Permission.WRITE),
        ("filesystem.rename_file", "Rename a file without overwriting an existing destination.", filesystem.rename_file, Permission.WRITE),
        ("filesystem.delete_file", "Permanently delete a file; requires destructive permission.", filesystem.delete_file, Permission.DESTRUCTIVE),
        ("filesystem.delete_directory", "Delete an empty directory, or recursively delete it when explicitly requested; requires destructive permission.", filesystem.delete_directory, Permission.DESTRUCTIVE),
        ("desktop.screen_size", "Read the current desktop screen dimensions.", computer.screen_size, Permission.READ),
        ("desktop.click", "Click a validated on-screen coordinate; requires write permission.", computer.click, Permission.WRITE),
        ("desktop.move_mouse", "Move the pointer to a validated on-screen coordinate; requires write permission.", computer.move_mouse, Permission.WRITE),
        ("desktop.type_text", "Type bounded text into the currently focused control; requires write permission.", computer.type_text, Permission.WRITE),
        ("desktop.press_key", "Press one allowlisted key without key-chord execution; requires write permission.", computer.press_key, Permission.WRITE),
        ("desktop.screenshot", "Save a desktop screenshot without overwriting an existing file unless explicitly allowed.", computer.screenshot, Permission.WRITE),
        ("applications.list_installed", "Discover installed applications and Start Menu shortcuts without launching them.", applications.list_installed_applications, Permission.READ),
        ("applications.list_running", "List running processes with process IDs and available metadata.", applications.list_running_applications, Permission.READ),
        ("applications.list_windows", "List visible top-level application windows and their handles.", applications.list_application_windows, Permission.READ),
        ("applications.launch", "Launch an executable or named Start Menu shortcut without a command shell; requires write permission.", applications.launch_application, Permission.WRITE),
        ("applications.focus_window", "Bring a validated application window to the foreground; requires write permission.", applications.focus_window, Permission.WRITE),
        ("applications.minimize_window", "Minimize a validated application window; requires write permission.", applications.minimize_window, Permission.WRITE),
        ("applications.maximize_window", "Maximize a validated application window; requires write permission.", applications.maximize_window, Permission.WRITE),
        ("applications.restore_window", "Restore a validated application window; requires write permission.", applications.restore_window, Permission.WRITE),
        ("applications.close_window", "Request graceful window closure with WM_CLOSE; requires destructive permission because unsaved work may be affected.", applications.close_window, Permission.DESTRUCTIVE),
        ("applications.terminate", "Terminate a process only after its PID and expected process name match; force termination requires destructive permission.", applications.terminate_application, Permission.DESTRUCTIVE),
    ]

    existing = {tool.name for tool in registry.list()}
    for name, description, handler, permission in builtins:
        if name not in existing:
            registry.register(name=name, description=description, handler=handler, permission=permission)


_register_builtin_tools()
