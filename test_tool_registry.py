import pytest

from core.tool_registry import Permission, ToolRegistry


def test_register_list_and_invoke():
    registry = ToolRegistry()

    registry.register(
        "math.add",
        "Add two numbers",
        lambda a, b: a + b,
    )

    assert [tool["name"] for tool in registry.describe()] == ["math.add"]
    assert registry.invoke("math.add", 2, 3) == 5


def test_permission_boundary():
    registry = ToolRegistry()
    registry.register(
        "file.delete",
        "Delete a file",
        lambda: "deleted",
        permission=Permission.DESTRUCTIVE,
    )

    with pytest.raises(PermissionError):
        registry.invoke("file.delete")

    assert registry.invoke(
        "file.delete",
        approved_permissions={Permission.DESTRUCTIVE},
    ) == "deleted"


def test_unknown_tool_fails_clearly():
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="Unknown tool"):
        registry.invoke("does.not.exist")
