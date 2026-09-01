"""Device-independent reach-out requests for AI-OS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReachOutPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass(frozen=True)
class ReachOutRequest:
    message: str
    reason: str
    priority: ReachOutPriority = ReachOutPriority.NORMAL
    requires_approval: bool = False
    task_id: int | None = None

    @property
    def should_interrupt_user(self) -> bool:
        return self.priority in {ReachOutPriority.HIGH, ReachOutPriority.URGENT}


def create_reach_out(*, message: str, reason: str,
                     priority: ReachOutPriority = ReachOutPriority.NORMAL,
                     requires_approval: bool = False,
                     task_id: int | None = None) -> ReachOutRequest:
    """Create a channel-neutral request that a delivery adapter can send later."""
    message = message.strip()
    reason = reason.strip()
    if not message:
        raise ValueError("Reach-out message cannot be empty")
    if not reason:
        raise ValueError("Reach-out reason cannot be empty")
    return ReachOutRequest(message, reason, priority, requires_approval, task_id)


__all__ = ["ReachOutPriority", "ReachOutRequest", "create_reach_out"]
