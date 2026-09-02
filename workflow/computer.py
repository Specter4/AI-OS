"""Safe local computer/filesystem actions for the JARVIS execution layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.tool_registry import Permission
from workflow.action_registry import ActionRegistry, ActionSpec


class ComputerController:
    """Filesystem-focused controller with explicit workspace boundaries."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, path: str | Path) -> Path:
        candidate = (self.workspace / Path(path)).resolve()
        if candidate != self.workspace and self.workspace not in candidate.parents:
            raise PermissionError("Path is outside the configured workspace")
        return candidate

    def _relative_path(self, path: Path) -> str:
        return path.relative_to(self.workspace).as_posix()

    def list_directory(self, path: str = ".") -> list[dict[str, Any]]:
        directory = self._safe_path(path)
        if not directory.is_dir():
            raise NotADirectoryError(str(directory))
        return [
            {"name": item.name, "path": self._relative_path(item), "is_dir": item.is_dir()}
            for item in sorted(directory.iterdir(), key=lambda item: item.name.lower())
        ]

    def read_file(self, path: str) -> str:
        file_path = self._safe_path(path)
        if not file_path.is_file():
            raise FileNotFoundError(str(file_path))
        return file_path.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        file_path = self._safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return self._relative_path(file_path)

    def create_directory(self, path: str) -> str:
        directory = self._safe_path(path)
        directory.mkdir(parents=True, exist_ok=True)
        return self._relative_path(directory)

    def delete_file(self, path: str) -> str:
        file_path = self._safe_path(path)
        if not file_path.is_file():
            raise FileNotFoundError(str(file_path))
        file_path.unlink()
        return self._relative_path(file_path)


def register_computer_actions(registry: ActionRegistry, controller: ComputerController) -> None:
    """Register filesystem actions without executing anything during registration."""
    registry.register(ActionSpec(
        "list_directory", "List files and directories in the JARVIS workspace.",
        handler=controller.list_directory, metadata={"permission": Permission.READ, "capability": "computer"},
    ))
    registry.register(ActionSpec(
        "read_file", "Read a UTF-8 text file in the JARVIS workspace.",
        handler=controller.read_file, metadata={"permission": Permission.READ, "capability": "computer"},
    ))
    registry.register(ActionSpec(
        "write_file", "Create or replace a UTF-8 text file in the JARVIS workspace.",
        handler=controller.write_file, requires_approval=True,
        metadata={"permission": Permission.WRITE, "capability": "computer"},
    ))
    registry.register(ActionSpec(
        "create_directory", "Create a directory in the JARVIS workspace.",
        handler=controller.create_directory, requires_approval=True,
        metadata={"permission": Permission.WRITE, "capability": "computer"},
    ))
    registry.register(ActionSpec(
        "delete_file", "Delete a file in the JARVIS workspace.",
        handler=controller.delete_file, requires_approval=True,
        metadata={"permission": Permission.DESTRUCTIVE, "capability": "computer"},
    ))


__all__ = ["ComputerController", "register_computer_actions"]
