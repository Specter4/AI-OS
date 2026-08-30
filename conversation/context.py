"""Lightweight state for maintaining a human-like conversational thread."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationContext:
    """Tracks the active topic and recently completed goals for follow-ups."""

    active_topic: str | None = None
    active_goal: str | None = None
    completed_goals: list[str] = field(default_factory=list)

    def observe(self, message: str, *, goal: bool = False) -> None:
        text = message.strip()
        if not text:
            return
        if goal:
            self.active_goal = text
            self.active_topic = text

    def complete_goal(self, goal: str) -> None:
        text = goal.strip()
        if text:
            self.active_goal = None
            self.active_topic = text
            self.completed_goals.append(text)
            self.completed_goals = self.completed_goals[-5:]

    def prompt_context(self) -> str:
        lines = []
        if self.active_topic:
            lines.append(f"Current conversational topic: {self.active_topic}")
        if self.active_goal:
            lines.append(f"Active goal: {self.active_goal}")
        if self.completed_goals:
            lines.append("Recently completed goals:")
            lines.extend(f"- {goal}" for goal in self.completed_goals[-3:])
        return "\n".join(lines)


context = ConversationContext()


def clear_context() -> None:
    """Reset conversational state without changing persistent memory."""
    context.active_topic = None
    context.active_goal = None
    context.completed_goals.clear()
