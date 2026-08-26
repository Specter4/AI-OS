import pytest

from agents.tool_agent import ToolAgent
from core.tool_registry import Permission, registry
from workflow.autonomy import AutonomyLoop


def test_elevated_tool_fails_closed_without_approval(monkeypatch):
    name = "purchase.test"
    registry.register(name, "Purchase an item", lambda item: f"bought {item}", Permission.EXTERNAL)

    agent = ToolAgent()
    monkeypatch.setattr(
        agent,
        "select_tool",
        lambda task: type("Request", (), {"tool": name, "arguments": {"item": "laptop"}})(),
    )

    with pytest.raises(PermissionError, match="explicit approval"):
        agent.run_task("buy the laptop")


def test_elevated_tool_runs_only_after_explicit_approval():
    name = "purchase.approved"
    registry.register(name, "Purchase an item", lambda item: f"bought {item}", Permission.EXTERNAL)

    approvals = []

    def approve(spec, arguments):
        approvals.append((spec.name, arguments))
        return True

    agent = ToolAgent(approval_provider=approve)
    agent.select_tool = lambda task: type(
        "Request", (), {"tool": name, "arguments": {"item": "laptop"}}
    )()

    result = agent.run_task("buy the laptop")

    assert result["result"] == "bought laptop"
    assert approvals == [(name, {"item": "laptop"})]


def test_autonomy_passes_approval_boundary_to_agent():
    seen = []

    class Agent:
        def run_task(self, task, *, approved_permissions=None, approval_provider=None):
            seen.append(approval_provider)
            return {"success": True, "tool": "read.test", "result": "ok"}

    approval = lambda spec, arguments: True
    loop = AutonomyLoop(agent=Agent(), max_steps=1, approval_provider=approval)
    loop.evaluate = lambda goal, observations: {"complete": True, "next_task": None}

    result = loop.run("inspect")

    assert result.success is True
    assert seen == [approval]


def test_autonomy_stops_when_approval_is_denied():
    name = "purchase.denied"
    registry.register(name, "Purchase an item", lambda item: f"bought {item}", Permission.EXTERNAL)

    agent = ToolAgent(approval_provider=lambda spec, arguments: False)
    agent.select_tool = lambda task: type(
        "Request", (), {"tool": name, "arguments": {"item": "laptop"}}
    )()

    loop = AutonomyLoop(agent=agent, max_steps=3)
    result = loop.run("buy the laptop")

    assert result.success is False
    assert "approval" in result.error.lower()
    assert len(result.observations) == 1
    assert result.observations[0].recovery_action == "request_approval"
