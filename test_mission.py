from pathlib import Path

import pytest

from core.project import Project
from core.tasks import Task
from workflow.mission import AutonomousMission


class FakeOrchestrator:
    def build(self, goal):
        return [Task(id=1, title="Do the work", agent="assistant")]


def test_start_builds_executes_and_persists_mission(tmp_path, monkeypatch):
    mission = AutonomousMission(orchestrator=FakeOrchestrator(), project_root=str(tmp_path))

    def fake_execute(goal, tasks, *, project_id, project_root):
        project = Project(goal=goal, status="completed", tasks=tasks)
        tasks[0].status = "completed"
        tasks[0].result = "done"
        project.persist(project_id, project_root)
        return project

    monkeypatch.setattr("workflow.mission.execute", fake_execute)

    project = mission.start("fb-page", "Handle my Facebook page")

    assert project.status == "completed"
    assert Path(tmp_path, "fb-page.json").exists()


def test_status_and_report_are_read_only_and_structured(tmp_path):
    project = Project(
        goal="Monitor my page",
        status="running",
        tasks=[Task(id=1, title="Check metrics", agent="research", status="completed", result="stable")],
    )
    project.persist("page", tmp_path)

    mission = AutonomousMission(project_root=str(tmp_path))
    report = mission.status("page")

    assert report.mission_id == "page"
    assert report.goal == "Monitor my page"
    assert report.status == "running"
    assert report.progress == 100
    assert report.completed == 1
    assert report.total == 1
    assert report.tasks[0]["result"] == "stable"
    assert report.generated_at

    second = mission.report("page")
    assert second.goal == report.goal
    assert second.progress == report.progress


def test_start_rejects_empty_identifiers(tmp_path):
    mission = AutonomousMission(orchestrator=FakeOrchestrator(), project_root=str(tmp_path))

    with pytest.raises(ValueError):
        mission.start("", "Do something")

    with pytest.raises(ValueError):
        mission.start("id", "")


def test_resume_delegates_to_persistent_executor(tmp_path, monkeypatch):
    mission = AutonomousMission(project_root=str(tmp_path))
    calls = []

    def fake_resume(project_id, *, project_root):
        calls.append((project_id, project_root))
        return Project(goal="Resume this", status="completed")

    monkeypatch.setattr("workflow.mission.resume_project", fake_resume)

    result = mission.resume("mission-1")

    assert result.status == "completed"
    assert calls == [("mission-1", str(tmp_path))]
