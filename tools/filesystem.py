"""
AI-OS Filesystem Tool

Provides configurable local filesystem access for JARVIS. Relative paths resolve
from the AI-OS workspace; absolute paths are accepted only inside configured
allowed roots. The default local root is the current user's home directory, so
JARVIS can work with ordinary PC files as well as its own workspace.

Destructive operations are deliberately separate from ordinary writes and must
be authorized by the existing permission gateway.
"""
from __future__ import annotations

import base64
import binascii
import fnmatch
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from core.logger import log


class FileSystem:
    """Filesystem operations constrained to explicitly configured root folders."""

    def __init__(
        self,
        workspace: str | Path | None = None,
        allowed_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
    ) -> None:
        configured_workspace = workspace or os.getenv("AI_OS_WORKSPACE") or os.getcwd()
        self.workspace = Path(configured_workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

        if allowed_roots is None:
            configured_roots = os.getenv("AI_OS_ALLOWED_ROOTS")
            if configured_roots:
                roots = [Path(item.strip()).expanduser() for item in configured_roots.split(os.pathsep) if item.strip()]
            else:
                # Broad local access for the signed-in user, without granting
                # access to other users' profiles or unrelated mounted volumes.
                roots = [Path.home()]
        else:
            roots = [Path(item).expanduser() for item in allowed_roots]

        roots.append(self.workspace)
        self.allowed_roots = tuple(dict.fromkeys(root.resolve() for root in roots))
        for root in self.allowed_roots:
            root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_path(path: str | Path) -> Path:
        if not isinstance(path, (str, Path)):
            raise TypeError("path must be a string or Path")
        value = str(path)
        if not value.strip() or "\x00" in value:
            raise ValueError("A non-empty valid path is required")
        return Path(value).expanduser()

    def _resolve(self, path: str | Path, *, must_exist: bool = False) -> Path:
        candidate = self._validate_path(path)
        resolved = (candidate if candidate.is_absolute() else self.workspace / candidate).resolve()
        if not any(resolved == root or root in resolved.parents for root in self.allowed_roots):
            raise PermissionError(f"Path is outside configured AI-OS access roots: {path}")
        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        return resolved

    def _relative_label(self, path: Path) -> str:
        for root in self.allowed_roots:
            try:
                return str(path.relative_to(root))
            except ValueError:
                continue
        return str(path)

    def read_file(self, path: str | Path, encoding: str = "utf-8", max_bytes: int = 10_000_000) -> str:
        target = self._resolve(path, must_exist=True)
        if not target.is_file():
            raise IsADirectoryError(f"Not a file: {path}")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        if target.stat().st_size > max_bytes:
            raise ValueError(f"File exceeds the {max_bytes}-byte read limit")
        log(f"Reading file: {self._relative_label(target)}")
        return target.read_text(encoding=encoding)

    def read_file_base64(self, path: str | Path, max_bytes: int = 10_000_000) -> str:
        """Read arbitrary binary files as base64 for safe tool/JSON transport."""
        target = self._resolve(path, must_exist=True)
        if not target.is_file():
            raise IsADirectoryError(f"Not a file: {path}")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        if target.stat().st_size > max_bytes:
            raise ValueError(f"File exceeds the {max_bytes}-byte read limit")
        log(f"Reading binary file: {self._relative_label(target)}")
        return base64.b64encode(target.read_bytes()).decode("ascii")

    def write_file_base64(
        self,
        path: str | Path,
        content_base64: str,
        overwrite: bool = False,
    ) -> str:
        """Write arbitrary binary content supplied as validated base64."""
        if not isinstance(content_base64, str):
            raise TypeError("content_base64 must be a string")
        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean")
        try:
            data = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("content_base64 must contain valid base64 data") from exc
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {target}")
        fd, temporary = tempfile.mkstemp(prefix=".aios-write-", dir=str(target.parent))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if target.exists() and not overwrite:
                raise FileExistsError(f"File already exists: {target}")
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        log(f"Wrote binary file: {self._relative_label(target)}")
        return str(target)

    def write_file(
        self,
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
        overwrite: bool = False,
    ) -> str:
        if not isinstance(content, str):
            raise TypeError("content must be a string")
        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean")
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {target}")
        # Write beside the destination and atomically replace it only after
        # the complete content has been flushed.
        fd, temporary = tempfile.mkstemp(prefix=".aios-write-", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding=encoding) as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if target.exists() and not overwrite:
                raise FileExistsError(f"File already exists: {target}")
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        log(f"Wrote file: {self._relative_label(target)}")
        return str(target)

    def list_directory(self, path: str | Path = ".") -> list[dict[str, Any]]:
        target = self._resolve(path, must_exist=True)
        if not target.is_dir():
            raise NotADirectoryError(f"Directory not found: {path}")
        entries: list[dict[str, Any]] = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            # Resolve every child before exposing it; do not follow symlinks
            # that point outside the configured roots.
            try:
                safe_item = self._resolve(item)
            except PermissionError:
                continue
            entries.append({
                "name": item.name,
                "type": "directory" if safe_item.is_dir() else "file",
                "size": safe_item.stat().st_size if safe_item.is_file() else 0,
                "path": str(safe_item),
            })
        log(f"Listed directory: {self._relative_label(target)}")
        return entries

    def create_directory(self, path: str | Path) -> str:
        target = self._resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        log(f"Created directory: {self._relative_label(target)}")
        return str(target)

    def search_files(
        self,
        pattern: str = "*",
        path: str | Path = ".",
        recursive: bool = True,
        max_results: int = 200,
    ) -> list[dict[str, Any]]:
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError("A non-empty search pattern is required")
        if not isinstance(recursive, bool):
            raise TypeError("recursive must be a boolean")
        if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 5000:
            raise ValueError("max_results must be between 1 and 5000")
        root = self._resolve(path, must_exist=True)
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        iterator = root.rglob("*") if recursive else root.glob("*")
        matches = []
        for item in iterator:
            if not fnmatch.fnmatch(item.name.lower(), pattern.lower()):
                continue
            try:
                safe_item = self._resolve(item, must_exist=True)
            except (PermissionError, FileNotFoundError):
                continue
            matches.append({
                "name": item.name,
                "path": str(safe_item),
                "type": "directory" if safe_item.is_dir() else "file",
                "size": safe_item.stat().st_size if safe_item.is_file() else 0,
            })
            if len(matches) >= max_results:
                break
        return matches

    def get_file_info(self, path: str | Path) -> dict[str, Any]:
        target = self._resolve(path, must_exist=True)
        stat = target.stat()
        return {
            "name": target.name,
            "path": str(target),
            "type": "directory" if target.is_dir() else "file",
            "size": stat.st_size if target.is_file() else 0,
            "modified_at": stat.st_mtime,
            "created_at": stat.st_ctime,
        }

    def copy_file(self, source: str | Path, destination: str | Path, overwrite: bool = False) -> str:
        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean")
        src = self._resolve(source, must_exist=True)
        dst = self._resolve(destination)
        if not src.is_file():
            raise IsADirectoryError(f"Source is not a file: {source}")
        if src == dst:
            raise ValueError("Source and destination must be different paths")
        if dst.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log(f"Copied file: {self._relative_label(src)} -> {self._relative_label(dst)}")
        return str(dst)

    def move_file(self, source: str | Path, destination: str | Path, overwrite: bool = False) -> str:
        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean")
        src = self._resolve(source, must_exist=True)
        dst = self._resolve(destination)
        if not src.is_file():
            raise IsADirectoryError(f"Source is not a file: {source}")
        if src == dst:
            raise ValueError("Source and destination must be different paths")
        if dst.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if overwrite and dst.exists():
            dst.unlink()
        shutil.move(str(src), str(dst))
        log(f"Moved file: {self._relative_label(src)} -> {self._relative_label(dst)}")
        return str(dst)

    def rename_file(self, path: str | Path, new_name: str) -> str:
        if not isinstance(new_name, str) or not new_name.strip():
            raise ValueError("A non-empty new filename is required")
        if Path(new_name).name != new_name or new_name in {".", ".."}:
            raise ValueError("new_name must be a filename, not a path")
        source = self._resolve(path, must_exist=True)
        if not source.is_file():
            raise IsADirectoryError(f"Not a file: {path}")
        destination = self._resolve(source.parent / new_name)
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        source.rename(destination)
        log(f"Renamed file: {self._relative_label(source)} -> {new_name}")
        return str(destination)

    def delete_file(self, path: str | Path) -> dict[str, Any]:
        target = self._resolve(path, must_exist=True)
        if not target.is_file():
            raise IsADirectoryError(f"Not a file: {path}")
        target.unlink()
        log(f"Deleted file: {self._relative_label(target)}")
        return {"success": True, "deleted": str(target)}

    def delete_directory(self, path: str | Path, recursive: bool = False) -> dict[str, Any]:
        if not isinstance(recursive, bool):
            raise TypeError("recursive must be a boolean")
        target = self._resolve(path, must_exist=True)
        if not target.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        if target in self.allowed_roots or target == self.workspace:
            raise PermissionError("Configured access roots cannot be deleted")
        if recursive:
            shutil.rmtree(target)
        else:
            target.rmdir()
        log(f"Deleted directory: {self._relative_label(target)}")
        return {"success": True, "deleted": str(target), "recursive": recursive}


filesystem = FileSystem()

__all__ = ["FileSystem", "filesystem"]
