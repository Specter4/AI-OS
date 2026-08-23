from pathlib import Path

import pytest

from core.tool_registry import Permission, registry
from tools.filesystem import FileSystem
import tools.registry  # noqa: F401 - registers built-in tools


def test_write_and_read_file(tmp_path: Path):
    fs = FileSystem(tmp_path)

    written = fs.write_file("notes/test.txt", "hello AI-OS")

    assert Path(written).read_text(encoding="utf-8") == "hello AI-OS"
    assert fs.read_file("notes/test.txt") == "hello AI-OS"


def test_list_directory(tmp_path: Path):
    fs = FileSystem(tmp_path)
    fs.write_file("a.txt", "a")
    fs.create_directory("folder")

    entries = fs.list_directory()

    assert [entry["name"] for entry in entries] == ["folder", "a.txt"]
    assert entries[0]["type"] == "directory"
    assert entries[1]["type"] == "file"


def test_workspace_escape_is_blocked(tmp_path: Path):
    fs = FileSystem(tmp_path)

    with pytest.raises(PermissionError):
        fs.read_file("../outside.txt")


def test_registry_exposes_filesystem_tools():
    descriptions = {item["name"]: item for item in registry.describe()}

    assert descriptions["filesystem.read_file"]["permission"] == Permission.READ.value
    assert descriptions["filesystem.write_file"]["permission"] == Permission.WRITE.value


def test_registry_enforces_write_permission(tmp_path: Path):
    fs = FileSystem(tmp_path)
    local_name = "test.write"

    registry.register(local_name, "test write", fs.write_file, Permission.WRITE)

    try:
        with pytest.raises(PermissionError):
            registry.invoke(local_name, "blocked.txt", "blocked")

        result = registry.invoke(
            local_name,
            "allowed.txt",
            "allowed",
            approved_permissions={Permission.READ, Permission.WRITE},
        )
        assert Path(result).read_text(encoding="utf-8") == "allowed"
    finally:
        registry.unregister(local_name)
