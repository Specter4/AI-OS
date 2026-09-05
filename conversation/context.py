"""Conversation state for maintaining a human-like conversational thread."""

from __future__ import annotations

from dataclasses import dataclass, field

from conversation.human_interaction import InteractionSignals, analyze


@dataclass
class ConversationContext:
    """Tracks active threads, turns, and deterministic interaction signals."""

    active_topic: str | None = None
    active_goal: str | None = None
    completed_goals: list[str] = field(default_factory=list)
    last_user_message: str | None = None
    last_assistant_message: str | None = None
    turn_count: int = 0
    last_signals: InteractionSignals = field(default_factory=InteractionSignals)

    def observe(self, message: str, *, goal: bool = False) -> None:
        text = message.strip()
        if not text:
            return
        self.last_signals = analyze(text, has_previous_turn=self.last_user_message is not None)
        self.last_user_message = text
        self.turn_count += 1
        if goal:
            self.active_goal = text
            self.active_topic = text
        elif self.last_signals.is_correction and self.last_signals.correction_text:
            self.active_topic = self.active_topic or self.last_signals.correction_text

    def observe_assistant(self, message: str) -> None:
        text = message.strip()
        if text:
            self.last_assistant_message = text

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
        if self.last_user_message:
            lines.append(f"Last user turn: {self.last_user_message}")
        if self.last_signals.is_correction:
            lines.append("The latest user turn appears to correct or revise something said earlier; treat the newest instruction as authoritative.")
        if self.last_signals.is_follow_up:
            lines.append("The latest user turn appears connected to the existing conversation; resolve references using the available conversation history rather than asking unnecessarily.")
        if self.last_signals.is_urgent:
            lines.append("The latest user turn contains urgency language; respond promptly and prioritize the requested matter without inventing urgency beyond the user's words.")
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
    context.last_user_message = None
    context.last_assistant_message = None
    context.turn_count = 0
    context.last_signals = InteractionSignals()
