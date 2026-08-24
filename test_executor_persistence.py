from core.tasks import Task
from workflow.executor import execute


def test_executor_checkpoints_project_state(tmp_path):
    tasks = [Task(1, "Simple task", "assistant")]

    project = execute(
        "Checkpoint test",
        tasks,
        project_id="checkpoint-test",
        project_root=tmp_path,
    )

    restored = project.resume("checkpoint-test", tmp_path)

    assert restored.goal == "Checkpoint test"
    assert restored.tasks[0].status == "completed"
    assert restored.tasks[0].result is not None


def test_executor_without_project_id_remains_ephemeral(tmp_path):
    project = execute(
        "Ephemeral test",
        [Task(1, "Simple task", "assistant")],
        project_root=tmp_path,
    )

    assert project.status == "completed"
    assert list(tmp_path.iterdir()) == []
