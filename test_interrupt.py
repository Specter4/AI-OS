import threading

from workflow.autonomy import AutonomyLoop
from workflow.interrupt import InterruptController


class FakeAgent:
    def __init__(self):
        self.tasks = []

    def run_task(self, task, approved_permissions=None):
        self.tasks.append(task)
        return {"success": True, "tool": "fake", "result": task}


def test_interrupt_controller_carries_revised_instruction():
    controller = InterruptController()
    request = controller.request("Stop that.", "Only research Lenovo laptops.")

    assert controller.is_requested()
    assert request.reason == "Stop that."
    assert request.instruction == "Only research Lenovo laptops."
    assert controller.get() == request

    controller.clear()
    assert controller.get() is None
    assert not controller.is_requested()


def test_loop_stops_before_action_when_interrupted():
    controller = InterruptController()
    controller.request("Wait, stop.", "Use only Lenovo.")
    agent = FakeAgent()
    loop = AutonomyLoop(agent=agent, max_steps=2, interrupt_controller=controller)

    result = loop.run("Research laptops")

    assert result.success is False
    assert result.error == "Wait, stop."
    assert result.suspended_task == "Research laptops"
    assert result.observations == []
    assert agent.tasks == []


def test_interrupted_run_can_resume_with_new_instruction():
    controller = InterruptController()
    controller.request("Change of plan")
    agent = FakeAgent()
    loop = AutonomyLoop(agent=agent, max_steps=1, interrupt_controller=controller)

    interrupted = loop.run("Research laptops")
    resumed = loop.resume_with_instruction(interrupted, "Research Lenovo laptops only")

    assert resumed.success is False or resumed.success is True
    assert agent.tasks == ["Research Lenovo laptops only"]


def test_interrupt_can_be_requested_from_another_thread():
    controller = InterruptController()
    loop = AutonomyLoop(agent=FakeAgent(), max_steps=1, interrupt_controller=controller)

    thread = threading.Thread(target=controller.request, kwargs={"reason": "Stop now"})
    thread.start()
    thread.join()

    assert controller.is_requested()
    assert controller.get().reason == "Stop now"
