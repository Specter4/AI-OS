"""
AI-OS Filesystem Tool

Provides bounded filesystem operations for agents. All paths are resolved
relative to the configured AI-OS workspace and cannot escape that workspace.
"""

from __future__ import annotations

import os
from pathlib import Path

from core.logger import log


class FileSystem:
    """Safe filesystem operations scoped to an AI-OS workspace."""

    def __init__(self, workspace: str | Path | None = None) -> None:
        configured = workspace or os.getenv("AI_OS_WORKSPACE") or os.getcwd()
        self.workspace = Path(configured).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.workspace / candidate).resolve()

        try:
            resolved.relative_to(self.workspace)
        except ValueError as exc:
            raise PermissionError(
                f"Path escapes AI-OS workspace: {path}"
            ) from exc

        return resolved

    def read_file(self, path: str | Path, encoding: str = "utf-8") -> str:
        target = self._resolve(path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        log(f"Reading file: {target.relative_to(self.workspace)}")
        return target.read_text(encoding=encoding)

    def write_file(
        self,
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
    ) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)

        log(f"Wrote file: {target.relative_to(self.workspace)}")
        return str(target)

    def list_directory(self, path: str | Path = ".") -> list[dict[str, str | int]]:
        target = self._resolve(path)
        if not target.is_dir():
            raise NotADirectoryError(f"Directory not found: {path}")

        log(f"Listing directory: {target.relative_to(self.workspace)}")
        entries = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            entries.append(
                {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                }
            )
        return entries

    def create_directory(self, path: str | Path) -> str:
        target = self._resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        log(f"Created directory: {target.relative_to(self.workspace)}")
        return str(target)


filesystem = FileSystem()
