"""Reason-based recovery policy for autonomous AI-OS execution.

The policy is deliberately deterministic. LLM output may suggest a next task,
but it never decides whether a failure is safe to retry or requires approval.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    reason: str
    retry: bool = False
    requires_approval: bool = False


_TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "connection reset",
    "temporarily unavailable",
    "temporary failure",
    "rate limit",
    "429",
)

_APPROVAL_MARKERS = (
    "permission denied",
    "requires approval",
    "approval required",
    "destructive",
    "not approved",
)


def classify_failure(error: str | None) -> RecoveryDecision:
    """Classify a failure into a bounded, policy-controlled recovery action."""
    message = (error or "unknown failure").strip().lower()

    if any(marker in message for marker in _APPROVAL_MARKERS):
        return RecoveryDecision(
            action="request_approval",
            reason="The failure indicates an action requiring explicit permission.",
            requires_approval=True,
        )

    if any(marker in message for marker in _TRANSIENT_MARKERS):
        return RecoveryDecision(
            action="retry",
            reason="The failure looks transient and is safe to retry within a bound.",
            retry=True,
        )

    if "dependency" in message or "blocked" in message or "validation" in message:
        return RecoveryDecision(
            action="replan",
            reason="The failure suggests the current task needs a different prerequisite or approach.",
        )

    return RecoveryDecision(
        action="replan",
        reason="The failure is not safely classifiable as transient; replan instead of blind retry.",
    )
