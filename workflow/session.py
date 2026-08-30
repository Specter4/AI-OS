"""Shared conversation/autonomy session state for natural follow-up control."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from conversation.context import ConversationContext
from workflow.autonomy import AutonomyLoop, AutonomyResult
from workflow.interrupt import InterruptController, Interruption


@dataclass
class SessionState:
    """Owns the live conversation and autonomous task state for one user session."""

    conversation: ConversationContext = field(default_factory=ConversationContext)
    interrupt_controller: InterruptController = field(default_factory=InterruptController)
    active_goal: str | None = None
    last_result: AutonomyResult | None = None
    _lock: RLock = field(default_factory=RLock, repr=False)

    def start(self, goal: str, *, agent=None, max_steps: int = 8) -> AutonomyLoop:
        text = goal.strip()
        if not text:
            raise ValueError("goal cannot be empty")
        with self._lock:
            self.active_goal = text
            self.conversation.observe(text, goal=True)
            return AutonomyLoop(
                agent=agent,
                max_steps=max_steps,
                context_provider=self.conversation.prompt_context,
                interrupt_controller=self.interrupt_controller,
            )

    def interrupt(self, reason: str = "Interrupted by the user.", instruction: str | None = None) -> Interruption:
        return self.interrupt_controller.request(reason, instruction)

    def record_result(self, result: AutonomyResult) -> None:
        with self._lock:
            self.last_result = result
            if result.success:
                self.conversation.complete_goal(result.goal)
                self.active_goal = None
            elif result.suspended_task:
                self.active_goal = result.goal

    def resume_with_instruction(self, instruction: str, *, agent=None, max_steps: int = 8) -> AutonomyResult:
        with self._lock:
            previous = self.last_result
            if previous is None:
                raise ValueError("No interrupted run is available to resume")
            loop = AutonomyLoop(
                agent=agent,
                max_steps=max_steps,
                context_provider=self.conversation.prompt_context,
                interrupt_controller=self.interrupt_controller,
            )
        result = loop.resume_with_instruction(previous, instruction)
        self.record_result(result)
        return result

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active_goal": self.active_goal,
                "conversation": self.conversation.prompt_context(),
                "interrupted": self.interrupt_controller.is_requested(),
                "suspended_task": self.last_result.suspended_task if self.last_result else None,
            }


session = SessionState()

__all__ = ["SessionState", "session"]
