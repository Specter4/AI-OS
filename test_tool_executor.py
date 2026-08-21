from core.tool_executor import ToolExecutor
from core.tool_registry import Permission, ToolRegistry


def test_read_tool_executes():
    registry = ToolRegistry()
    registry.register(
        "add",
        "Add two numbers",
        lambda a, b: a + b,
        Permission.READ,
    )

    result = ToolExecutor(registry).execute("add", 2, 3)

    assert result.success is True
    assert result.output == 5
    assert result.error is None


def test_write_tool_requires_approval():
    registry = ToolRegistry()
    registry.register(
        "write_file",
        "Write a file",
        lambda: "written",
        Permission.WRITE,
    )

    executor = ToolExecutor(registry)

    denied = executor.execute("write_file")
    assert denied.success is False
    assert "requires 'write' permission" in denied.error

    approved = executor.execute(
        "write_file",
        approved_permissions={Permission.WRITE},
    )
    assert approved.success is True
    assert approved.output == "written"


def test_unknown_tool_returns_failure():
    result = ToolExecutor(ToolRegistry()).execute("missing")

    assert result.success is False
    assert result.tool == "missing"
    assert "Unknown tool" in result.error
