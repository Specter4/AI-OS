from core.project import Project
from core.tasks import Task
from workflow.executor import resume_project


def test_resume_project_skips_completed_and_retries_failed(monkeypatch, tmp_path):
    project = Project(
        "Resume dentist project",
        status="paused",
        tasks=[
            Task(1, "Research", "research", status="completed", result="done"),
            Task(2, "Write homepage", "content", status="failed", depends_on=[1]),
            Task(3, "Build site", "coding", depends_on=[2]),
        ],
    )
    project.persist("resume-demo", tmp_path)

    calls = []

    def fake_dispatch(task, project):
        calls.append(task.id)
        return {"success": True, "output": f"completed {task.id}"}

    monkeypatch.setattr("workflow.executor.dispatch", fake_dispatch)

    resumed = resume_project("resume-demo", project_root=tmp_path)

    assert calls == [2, 3]
    assert resumed.tasks[0].status == "completed"
    assert resumed.tasks[1].status == "completed"
    assert resumed.tasks[2].status == "completed"


def test_resume_project_can_unblock_tasks_after_failed_dependency_is_retried(monkeypatch, tmp_path):
    project = Project(
        "Resume blocked project",
        status="paused",
        tasks=[
            Task(1, "Research", "research", status="failed", result="temporary error"),
            Task(2, "Write", "content", status="blocked", depends_on=[1]),
        ],
    )
    project.persist("blocked-demo", tmp_path)

    calls = []

    def fake_dispatch(task, project):
        calls.append(task.id)
        return {"success": True, "output": "ok"}

    monkeypatch.setattr("workflow.executor.dispatch", fake_dispatch)

    resumed = resume_project("blocked-demo", project_root=tmp_path)

    assert calls == [1, 2]
    assert all(task.status == "completed" for task in resumed.tasks)
