from workflow.autonomy import AutonomyLoop


class SequenceAgent:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.calls = []

    def run_task(self, task, *, approved_permissions=None):
        self.calls.append(task)
        return next(self.actions)


def test_transient_failure_retries_same_task_without_replanning():
    agent = SequenceAgent([
        {"success": False, "tool": "network", "error": "connection reset"},
        {"success": True, "tool": "network", "result": "ok"},
    ])
    loop = AutonomyLoop(agent=agent, max_steps=3)
    evaluations = []
    loop.evaluate = lambda goal, observations: evaluations.append(observations[-1].task) or {
        "complete": True,
        "next_task": None,
    }

    result = loop.run("fetch data")

    assert result.success is True
    assert agent.calls == ["fetch data", "fetch data"]
    assert evaluations == ["fetch data"]
    assert result.observations[0].recovery_action == "retry"


def test_approval_failure_stops_without_llm_replan():
    agent = SequenceAgent([
        {"success": False, "tool": "file.delete", "error": "permission denied"},
    ])
    loop = AutonomyLoop(agent=agent, max_steps=3)
    loop.evaluate = lambda *args: (_ for _ in ()).throw(AssertionError("must not replan"))

    result = loop.run("delete the file")

    assert result.success is False
    assert "approval" in result.error.lower()
    assert result.observations[0].recovery_action == "request_approval"
    assert len(agent.calls) == 1


def test_non_transient_failure_enters_replan_path():
    agent = SequenceAgent([
        {"success": False, "tool": "builder", "error": "validation failed"},
        {"success": True, "tool": "builder", "result": "fixed"},
    ])
    loop = AutonomyLoop(agent=agent, max_steps=3)
    decisions = iter([
        {"complete": False, "next_task": "fix validation issue"},
        {"complete": True, "next_task": None},
    ])
    loop.evaluate = lambda *args: next(decisions)

    result = loop.run("build project")

    assert result.success is True
    assert agent.calls == ["build project", "fix validation issue"]
    assert result.observations[0].recovery_action == "replan"
