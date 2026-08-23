import pytest

from agents import tool_agent as tool_agent_module
from agents.tool_agent import ToolAgent
from core.tool_registry import Permission, ToolRegistry


def test_select_tool_validates_llm_selection(monkeypatch):
    agent = ToolAgent()
    registry = tool_agent_module.registry
    registry.register("math.add", "Add two numbers", lambda a, b: a + b)

    class FakeResult:
        success = True
        output = '{"tool":"math.add","arguments":{"a":2,"b":3}}'
        error = None

    monkeypatch.setattr(tool_agent_module.llm, "generate", lambda *args, **kwargs: FakeResult())

    request = agent.select_tool("add 2 and 3")

    assert request is not None
    assert request.tool == "math.add"
    assert request.arguments == {"a": 2, "b": 3}


def test_run_task_enforces_permission(monkeypatch):
    agent = ToolAgent()
    registry = tool_agent_module.registry
    registry.register(
        "file.delete",
        "Delete a file",
        lambda path: f"deleted {path}",
        permission=Permission.DESTRUCTIVE,
    )

    class FakeResult:
        success = True
        output = '{"tool":"file.delete","arguments":{"path":"x.txt"}}'
        error = None

    monkeypatch.setattr(tool_agent_module.llm, "generate", lambda *args, **kwargs: FakeResult())

    with pytest.raises(PermissionError):
        agent.run_task("delete x.txt")

    assert agent.run_task(
        "delete x.txt",
        approved_permissions={Permission.DESTRUCTIVE},
    )["result"] == "deleted x.txt"


def test_no_registered_tool_returns_safe_result(monkeypatch):
    agent = ToolAgent()
    monkeypatch.setattr(agent, "available_tools", lambda: [])

    result = agent.run_task("do something")

    assert result["success"] is False
    assert result["tool"] is None
