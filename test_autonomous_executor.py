from core.tasks import Task
from workflow.autonomous_executor import ProjectTaskAgent, execute_autonomous


class FakeProject:
    def __init__(self, tasks):
        self.tasks = tasks
        self.saved = {}

    def save(self, key, value):
        self.saved[key] = value


def test_project_task_agent_routes_natural_language_to_agent(monkeypatch):
    project = FakeProject([])
    adapter = ProjectTaskAgent(project)

    monkeypatch.setattr(
        "workflow.autonomous_executor.dispatch",
        lambda task, project=None: {"success": True, "output": "researched"},
    )

    result = adapter.run_task("Research dentist competitors")

    assert result["success"] is True
    assert result["tool"] == "agent.research"
    assert project.tasks[0].agent == "research"
    assert project.tasks[0].status == "completed"


def test_clean_project_does_not_start_recovery(monkeypatch):
    clean_project = FakeProject([
        Task(1, "Done", "assistant", status="completed")
    ])

    monkeypatch.setattr(
        "workflow.autonomous_executor.execute",
        lambda goal, tasks: clean_project,
    )

    project, recovery = execute_autonomous("Finished goal", [])

    assert project is clean_project
    assert recovery is None


def test_failed_project_enters_bounded_recovery(monkeypatch):
    failed_project = FakeProject([
        Task(1, "Failed task", "research", status="failed")
    ])

    monkeypatch.setattr(
        "workflow.autonomous_executor.execute",
        lambda goal, tasks: failed_project,
    )

    class FakeLoop:
        def __init__(self, agent, max_steps):
            self.agent = agent
            self.max_steps = max_steps

        def run(self, goal, *, approved_permissions=None):
            assert goal == "Recover this goal"
            assert self.max_steps == 2
            return type("Recovery", (), {"success": True, "error": None})()

    monkeypatch.setattr("workflow.autonomous_executor.AutonomyLoop", FakeLoop)

    project, recovery = execute_autonomous(
        "Recover this goal",
        [],
        max_steps=2,
    )

    assert project is failed_project
    assert recovery.success is True
