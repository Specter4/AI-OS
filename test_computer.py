from pathlib import Path

import pytest

from workflow.action_registry import ActionRegistry
from workflow.computer import ComputerController, register_computer_actions


def test_controller_creates_and_lists_workspace(tmp_path: Path):
    controller = ComputerController(tmp_path)
    assert controller.create_directory("projects/demo") == "projects/demo"
    controller.write_file("projects/demo/hello.txt", "hello")
    assert controller.read_file("projects/demo/hello.txt") == "hello"
    entries = controller.list_directory("projects/demo")
    assert entries == [{"name": "hello.txt", "path": "projects/demo/hello.txt", "is_dir": False}]


def test_controller_blocks_workspace_escape(tmp_path: Path):
    controller = ComputerController(tmp_path)
    with pytest.raises(PermissionError):
        controller.read_file("../outside.txt")
    with pytest.raises(PermissionError):
        controller.write_file("../../outside.txt", "no")


def test_delete_file_is_explicit_and_scoped(tmp_path: Path):
    controller = ComputerController(tmp_path)
    controller.write_file("remove.txt", "temporary")
    assert controller.delete_file("remove.txt") == "remove.txt"
    with pytest.raises(FileNotFoundError):
        controller.read_file("remove.txt")


def test_computer_actions_are_registered_with_risk_metadata(tmp_path: Path):
    controller = ComputerController(tmp_path)
    registry = ActionRegistry()
    register_computer_actions(registry, controller)

    assert registry.names() == (
        "list_directory",
        "read_file",
        "write_file",
        "create_directory",
        "delete_file",
    )
    assert registry.require("list_directory").metadata["permission"].value == "read"
    assert registry.require("write_file").requires_approval is True
    assert registry.require("delete_file").metadata["permission"].value == "destructive"


def test_nested_write_creates_parent_directories(tmp_path: Path):
    controller = ComputerController(tmp_path)
    assert controller.write_file("a/b/c.txt", "data") == "a/b/c.txt"
    assert (tmp_path / "a" / "b" / "c.txt").read_text() == "data"
