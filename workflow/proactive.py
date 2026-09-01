"""Proactive follow-through decisions for the conversational manager."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProactiveKind(str, Enum):
    NONE = "none"
    NEXT_STEP = "next_step"
    DEPENDENCY = "dependency"
    TRADE_OFF = "trade_off"
    FOLLOW_UP = "follow_up"
    OPPORTUNITY = "opportunity"


@dataclass(frozen=True)
class ProactiveSuggestion:
    kind: ProactiveKind
    message: str
    priority: int = 0

    @property
    def should_surface(self) -> bool:
        return self.kind is not ProactiveKind.NONE and bool(self.message.strip())


def suggest(*, dependency: str | None = None, next_step: str | None = None,
            trade_off: str | None = None, follow_up: str | None = None,
            opportunity: str | None = None) -> ProactiveSuggestion:
    """Select the single highest-priority useful proactive observation."""
    candidates = (
        (ProactiveKind.DEPENDENCY, dependency, 5),
        (ProactiveKind.NEXT_STEP, next_step, 4),
        (ProactiveKind.TRADE_OFF, trade_off, 3),
        (ProactiveKind.FOLLOW_UP, follow_up, 2),
        (ProactiveKind.OPPORTUNITY, opportunity, 1),
    )
    for kind, message, priority in candidates:
        if message and message.strip():
            return ProactiveSuggestion(kind, message.strip(), priority)
    return ProactiveSuggestion(ProactiveKind.NONE, "", 0)


__all__ = ["ProactiveKind", "ProactiveSuggestion", "suggest"]
