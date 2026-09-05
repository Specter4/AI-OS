"""Post-execution verification for AI-OS actions.

Execution success means a handler completed without raising. Verification is a
separate concern: it checks whether the requested outcome actually occurred.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class VerificationEvidence:
    source: str
    detail: str


@dataclass(frozen=True)
class VerificationRequest:
    action: str
    expected: Any = None
    actual: Any = None
    check: Callable[[Any], bool] | None = None
    description: str = ""


@dataclass(frozen=True)
class VerificationResult:
    status: VerificationStatus
    verified: bool
    evidence: tuple[VerificationEvidence, ...] = ()
    reason: str = ""


class Verifier:
    """Perform deterministic postconditions without granting execution authority."""

    def verify(self, request: VerificationRequest) -> VerificationResult:
        if not request.action.strip():
            raise ValueError("action cannot be empty")

        if request.check is not None:
            try:
                passed = bool(request.check(request.actual))
            except Exception as exc:
                return VerificationResult(
                    VerificationStatus.UNCERTAIN,
                    False,
                    (VerificationEvidence("check", f"Verification raised: {exc}"),),
                    "The verification check could not be completed.",
                )
            return VerificationResult(
                VerificationStatus.VERIFIED if passed else VerificationStatus.FAILED,
                passed,
                (VerificationEvidence("check", "Custom postcondition passed." if passed else "Custom postcondition failed."),),
                "Verified by custom postcondition." if passed else "The expected postcondition was not satisfied.",
            )

        if request.expected is None:
            return VerificationResult(
                VerificationStatus.SKIPPED,
                False,
                (VerificationEvidence("policy", "No postcondition was supplied."),),
                "No outcome check was supplied; execution success alone is not treated as verification.",
            )

        try:
            passed = request.actual == request.expected
        except Exception as exc:
            return VerificationResult(
                VerificationStatus.UNCERTAIN,
                False,
                (VerificationEvidence("comparison", f"Comparison raised: {exc}"),),
                "Expected and actual values could not be compared safely.",
            )

        return VerificationResult(
            VerificationStatus.VERIFIED if passed else VerificationStatus.FAILED,
            passed,
            (VerificationEvidence("comparison", "Actual outcome matched the expected outcome." if passed else "Actual outcome did not match the expected outcome."),),
            "Expected outcome confirmed." if passed else "Expected outcome was not confirmed.",
        )


verifier = Verifier()

__all__ = [
    "VerificationEvidence",
    "VerificationRequest",
    "VerificationResult",
    "VerificationStatus",
    "Verifier",
    "verifier",
]
