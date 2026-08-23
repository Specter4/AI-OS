import pytest

from core.tool_registry import Permission, ToolRegistry
from workflow.autonomy import AutonomyLoop


class FakeToolAgent:
    def __init__(self):
        self.calls = []

    def run_task(self, task, *, approved_permissions=None):
        self.calls.append((task, approved_permissions))
        return {"success": True, "tool": "math.add", "result": 5}


class FakeAutonomy(AutonomyLoop):
    def __init__(self):
        super().__init__(agent=FakeToolAgent(), max_steps=3)
        self.evaluations = 0

    def evaluate(self, goal, observations):
        self.evaluations += 1
        if self.evaluations == 1:
            return {"complete": False, "next_task": "verify the result"}
        return {"complete": True, "next_task": None}


def test_observe_action_replan_loop_reaches_completion():
    loop = FakeAutonomy()
    result = loop.run("Add two numbers")

    assert result.success is True
    assert len(result.observations) == 2
    assert result.observations[0].task == "Add two numbers"
    assert result.observations[1].task == "verify the result"


def test_step_limit_prevents_infinite_loop():
    loop = AutonomyLoop(agent=FakeToolAgent(), max_steps=1)
    loop.evaluate = lambda goal, observations: {
        "complete": False,
        "next_task": "keep going",
    }

    result = loop.run("Never finish")

    assert result.success is False
    assert "step limit" in result.error
    assert len(result.observations) == 1


def test_permission_is_not_escalated_by_autonomy():
    registry = ToolRegistry()
    registry.register(
        "dangerous.delete",
        "Delete something",
        lambda: "deleted",
        permission=Permission.DESTRUCTIVE,
    )

    with pytest.raises(PermissionError):
        registry.invoke("dangerous.delete")
