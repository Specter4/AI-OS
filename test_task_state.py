from core.tasks import Task
from workflow.task_state import TaskState


def make_tasks():
    return [
        Task(id=1, title="Research", agent="research"),
        Task(id=2, title="Compare", agent="research", depends_on=[1]),
        Task(id=3, title="Recommend", agent="assistant", depends_on=[2]),
    ]


def test_state_tracks_current_task_and_progress():
    state = TaskState("Research and recommend.", make_tasks())
    assert state.snapshot().current_task_id is None
    assert state.snapshot().progress == 0

    state.start(1)
    assert state.snapshot().current_task_id == 1
    state.complete(1, "research done")
    assert state.snapshot().completed == 1
    assert state.snapshot().progress == 1 / 3
    assert state.snapshot().next_task.id == 2


def test_dependencies_prevent_out_of_order_execution():
    state = TaskState("Research, compare, recommend.", make_tasks())
    try:
        state.start(2)
    except ValueError as exc:
        assert "dependencies" in str(exc)
    else:
        raise AssertionError("dependent task started before its dependency")


def test_terminal_states_and_results_are_visible():
    state = TaskState("Research and recommend.", make_tasks()[:2])
    state.start(1)
    state.fail(1, "research unavailable")
    snapshot = state.snapshot()
    assert snapshot.tasks[0].status == "failed"
    assert snapshot.tasks[0].result == "research unavailable"
    assert snapshot.next_task is None
