from core.result import AgentResult
from core.tasks import Task
from workflow.autonomous_executor import ProjectTaskAgent
from workflow.autonomy import AutonomyLoop


class FakeLLM:
    pass


def make_project():
    class Context:
        def __init__(self):
            self.data = {"research": "dentist trends"}

        def all(self):
            return dict(self.data)

        def save(self, key, value):
            self.data[key] = value

        def get(self, key):
            return self.data.get(key)

    class Project:
        goal = "Build dentist website"
        status = "running"
        notes = ["Initial research completed"]
        context = Context()
        tasks = [
            Task(1, "Research dentist trends", "research", status="completed", result="Mobile-first trends"),
            Task(2, "Build dentist website", "coding", status="failed", result="Missing booking form"),
        ]

        def progress(self):
            return 50

        def context_data(self):
            return self.context.all()

        def save(self, key, value):
            self.context.save(key, value)

    return Project()


def test_context_snapshot_contains_task_results_and_shared_context():
    project = make_project()
    adapter = ProjectTaskAgent(project)

    snapshot = adapter.context_snapshot()

    assert snapshot["goal"] == "Build dentist website"
    assert snapshot["progress"] == 50
    assert snapshot["tasks"][0]["result"] == "Mobile-first trends"
    assert snapshot["tasks"][1]["result"] == "Missing booking form"
    assert snapshot["shared_context"]["research"] == "dentist trends"
    assert snapshot["notes"] == ["Initial research completed"]


def test_evaluator_receives_project_context():
    class FakeAgent:
        def run_task(self, task, *, approved_permissions=None):
            return {"success": True, "tool": "agent.coding", "result": "fixed"}

    class Loop(AutonomyLoop):
        def __init__(self):
            super().__init__(agent=FakeAgent(), max_steps=1, context_provider=lambda: {"failed": "booking form"})
            self.seen_context = None

        def evaluate(self, goal, observations, context=None):
            self.seen_context = context
            return {"complete": True, "next_task": None}

    loop = Loop()
    result = loop.run("Build dentist website")

    assert result.success is True
    assert loop.seen_context == {"failed": "booking form"}
