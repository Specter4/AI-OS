import json

import pytest

from core.project import Project
from core.tasks import Task


def test_project_persists_and_resumes_complete_state(tmp_path):
    project = Project("Build dentist website")
    project.status = "paused"
    project.notes.append("Use appointment-focused homepage")
    project.save("audience", "private dental clinics")
    project.tasks = [
        Task(1, "Research dentists", "research", status="completed", result="Research done"),
        Task(2, "Write homepage", "content", depends_on=[1]),
    ]

    path = project.persist("dentist-demo", tmp_path)
    assert path.exists()

    restored = Project.resume("dentist-demo", tmp_path)

    assert restored.goal == project.goal
    assert restored.status == "paused"
    assert restored.notes == project.notes
    assert restored.load("audience") == "private dental clinics"
    assert restored.tasks[0].status == "completed"
    assert restored.tasks[0].result == "Research done"
    assert restored.tasks[1].depends_on == [1]


def test_persistence_uses_atomic_temp_replacement(tmp_path):
    project = Project("Atomic project")
    path = project.persist("atomic", tmp_path)

    assert path.name == "atomic.json"
    assert not (tmp_path / "atomic.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["goal"] == "Atomic project"


def test_resume_missing_project_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Project.resume("missing", tmp_path)


def test_invalid_project_id_is_rejected(tmp_path):
    project = Project("Test")
    with pytest.raises(ValueError):
        project.persist("***", tmp_path)
    with pytest.raises(ValueError):
        Project.resume("***", tmp_path)
