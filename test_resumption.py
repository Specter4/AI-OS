from core.tasks import Task
from workflow.interrupt import InterruptController
from workflow.resumption import TaskSession
from workflow.task_state import TaskState


def make_state():
    tasks = [
        Task(id=1, title="Research", agent="research"),
        Task(id=2, title="Compare", agent="research", depends_on=[1]),
    ]
    return TaskState("Research and compare.", tasks)


def test_stop_interrupts_active_task():
    session = TaskSession(make_state())
    session.state.start(1)
    decision = session.handle_message("Wait, stop that.")
    assert decision.action == "interrupt"
    assert decision.interrupted_task_id == 1
    assert session.snapshot().current_task_id is None
    assert session.snapshot().tasks[0].status == "cancelled"


def test_resume_reactivates_interrupted_task():
    session = TaskSession(make_state())
    session.state.start(1)
    session.handle_message("Stop that.")
    decision = session.handle_message("Continue, but do it carefully.")
    assert decision.action == "resume"
    assert decision.instruction == "but do it carefully."
    assert session.snapshot().current_task_id == 1
    assert session.snapshot().tasks[0].status == "running"


def test_controller_signal_is_cleared_on_resume():
    controller = InterruptController()
    session = TaskSession(make_state(), controller)
    session.state.start(1)
    session.handle_message("Stop.")
    assert controller.is_requested()
    session.handle_message("Continue")
    assert not controller.is_requested()


def test_replace_instruction_does_not_restart_task_implicitly():
    session = TaskSession(make_state())
    session.state.start(1)
    decision = session.handle_message("Actually, do it this way instead.")
    assert decision.action == "replace"
    assert decision.interrupted_task_id == 1
    assert session.snapshot().current_task_id == 1
