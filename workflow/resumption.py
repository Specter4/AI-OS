"""JARVIS task interruption and resumption coordination."""

from __future__ import annotations

from dataclasses import dataclass

from conversation.control import ControlIntent, interpret_control
from workflow.interrupt import InterruptController
from workflow.task_state import TaskState, TaskStateSnapshot


@dataclass(frozen=True)
class ResumeDecision:
    action: str
    instruction: str | None = None
    interrupted_task_id: int | None = None


class TaskSession:
    """Coordinates natural-language control with live task state."""

    def __init__(self, state: TaskState, interrupt_controller: InterruptController | None = None) -> None:
        self.state = state
        self.interrupt_controller = interrupt_controller or InterruptController()
        self._interrupted_task_id: int | None = None

    def handle_message(self, message: str) -> ResumeDecision:
        snapshot = self.state.snapshot()
        # An interrupted session is still an active conversational task even
        # though the live task itself is temporarily cancelled.
        active = snapshot.current_task_id is not None or self._interrupted_task_id is not None
        intent: ControlIntent = interpret_control(message, active=active)

        if intent.action == "interrupt":
            self._interrupted_task_id = snapshot.current_task_id
            if snapshot.current_task_id is not None:
                self.state.cancel(snapshot.current_task_id, intent.instruction or intent.action)
            self.interrupt_controller.request(reason=message.strip(), instruction=intent.instruction)
            return ResumeDecision("interrupt", intent.instruction, self._interrupted_task_id)

        if intent.action == "resume":
            task_id = self._interrupted_task_id
            self.interrupt_controller.clear()
            if task_id is not None:
                task = next((task for task in self.state.snapshot().tasks if task.id == task_id), None)
                if task is not None and task.status == "cancelled":
                    task.status = "pending"
                    task.result = None
                try:
                    self.state.start(task_id)
                except ValueError:
                    pass
                self._interrupted_task_id = None
            return ResumeDecision("resume", intent.instruction, task_id)

        if intent.action == "replace":
            return ResumeDecision("replace", intent.instruction, snapshot.current_task_id or self._interrupted_task_id)

        return ResumeDecision("none")

    def snapshot(self) -> TaskStateSnapshot:
        return self.state.snapshot()


__all__ = ["ResumeDecision", "TaskSession"]
