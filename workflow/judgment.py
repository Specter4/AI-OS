"""Deterministic judgment and disclosure policy for AI-OS.

This layer answers three separate questions before execution:
1. Is the proposed action acceptable?
2. What should JARVIS do about it?
3. Does the owner need to be informed or asked?

It does not execute actions and does not replace authorization/approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.authorization import IdentityLevel
from core.tool_registry import Permission


class JudgmentLevel(str, Enum):
    SAFE = "safe"
    QUESTIONABLE = "questionable"
    RISKY = "risky"
    HARMFUL = "harmful"
    ILLEGAL = "illegal"


class JudgmentAction(str, Enum):
    PROCEED = "proceed"
    INFORM = "inform"
    ASK = "ask"
    STOP = "stop"


@dataclass(frozen=True)
class JudgmentInput:
    """Facts available to the policy without asking an LLM to make the decision."""

    identity: IdentityLevel = IdentityLevel.UNKNOWN
    permission: Permission = Permission.READ
    irreversible: bool = False
    affects_privacy: bool = False
    affects_security: bool = False
    material_impact: bool = False
    external_side_effect: bool = False
    uncertain: bool = False
    explicit_owner_direction: bool = False
    potentially_illegal: bool = False
    clearly_harmful: bool = False


@dataclass(frozen=True)
class JudgmentResult:
    level: JudgmentLevel
    action: JudgmentAction
    owner_needs_to_know: bool
    reason: str


class JudgmentPolicy:
    """Conservative policy for deciding whether to proceed, inform, ask, or stop."""

    def judge(self, request: JudgmentInput) -> JudgmentResult:
        if request.potentially_illegal:
            return JudgmentResult(
                JudgmentLevel.ILLEGAL,
                JudgmentAction.STOP,
                True,
                "The requested action may be illegal, so JARVIS must stop rather than execute it.",
            )

        if request.clearly_harmful:
            return JudgmentResult(
                JudgmentLevel.HARMFUL,
                JudgmentAction.STOP,
                True,
                "The requested action is clearly harmful, so JARVIS must stop.",
            )

        elevated = request.permission is not Permission.READ
        high_impact = request.irreversible or request.affects_security or request.material_impact
        private_or_external = request.affects_privacy or request.external_side_effect

        if request.identity is IdentityLevel.UNKNOWN and elevated:
            return JudgmentResult(
                JudgmentLevel.RISKY,
                JudgmentAction.STOP,
                True,
                "An unknown speaker cannot authorize an elevated action.",
            )

        if high_impact and not request.explicit_owner_direction:
            return JudgmentResult(
                JudgmentLevel.RISKY,
                JudgmentAction.ASK,
                True,
                "The action could have a material, irreversible, or security-sensitive consequence and needs owner direction.",
            )

        if request.uncertain:
            return JudgmentResult(
                JudgmentLevel.QUESTIONABLE,
                JudgmentAction.ASK,
                True,
                "Important context is uncertain, so JARVIS should ask instead of guessing.",
            )

        if private_or_external:
            return JudgmentResult(
                JudgmentLevel.QUESTIONABLE,
                JudgmentAction.INFORM,
                True,
                "The action affects privacy or an external system, so the owner should be informed.",
            )

        if elevated:
            return JudgmentResult(
                JudgmentLevel.QUESTIONABLE,
                JudgmentAction.INFORM,
                True,
                "The action has elevated authority or side-effect potential and should be disclosed to the owner.",
            )

        return JudgmentResult(
            JudgmentLevel.SAFE,
            JudgmentAction.PROCEED,
            False,
            "The action is low-risk and does not require owner disclosure.",
        )


policy = JudgmentPolicy()

__all__ = [
    "JudgmentAction",
    "JudgmentInput",
    "JudgmentLevel",
    "JudgmentPolicy",
    "JudgmentResult",
    "policy",
]
