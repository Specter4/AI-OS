"""Bounded self-correction for autonomous AI-OS execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from workflow.action_executor import ActionExecutionEngine, ExecutionResult
from workflow.execution_recovery import ExecutionRecovery
from workflow.verification import VerificationRequest, VerificationResult, VerificationStatus, Verifier, verifier


@dataclass(frozen=True)
class CorrectionAttempt:
    attempt: int
    execution: ExecutionResult | Any
    verification: VerificationResult
    correction: str | None = None


@dataclass(frozen=True)
class SelfCorrectionResult:
    success: bool
    action: str
    status: str
    output: Any = None
    error: str | None = None
    attempts: tuple[CorrectionAttempt, ...] = ()
    correction_action: str | None = None
    approval_request_id: str | None = None


class SelfCorrectionEngine:
    """Execute, verify, and make bounded corrections without bypassing safety gates."""

    def __init__(
        self,
        engine: ActionExecutionEngine,
        *,
        verifier: Verifier = verifier,
        correction: Callable[[ExecutionResult, VerificationResult, int], dict[str, Any] | None] | None = None,
        max_corrections: int = 0,
        recovery: ExecutionRecovery | None = None,
    ) -> None:
        if max_corrections < 0:
            raise ValueError("max_corrections cannot be negative")
        self.engine = engine
        self.verifier = verifier
        self.correction = correction
        self.max_corrections = max_corrections
        self.recovery = recovery

    def execute(
        self,
        action_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        identity=None,
        goal: str | None = None,
        task: str | None = None,
        approval_request_id: str | None = None,
        expected: Any = None,
        check: Callable[[Any], bool] | None = None,
        verification_description: str = "",
    ) -> SelfCorrectionResult:
        current_arguments = dict(arguments or {})
        current_approval = approval_request_id
        attempts: list[CorrectionAttempt] = []

        for attempt_number in range(1, self.max_corrections + 2):
            if self.recovery is not None:
                execution = self.recovery.execute(
                    action_name,
                    current_arguments,
                    identity=identity,
                    goal=goal,
                    task=task,
                    approval_request_id=current_approval,
                )
                actual = execution.output
                execution_success = execution.success
                execution_status = execution.status
                execution_error = execution.error
                execution_action = execution.action
                execution_approval_id = getattr(execution, "approval_request_id", None)
            else:
                execution = self.engine.execute(
                    action_name,
                    current_arguments,
                    identity=identity if identity is not None else self._default_identity(),
                    goal=goal,
                    task=task,
                    approval_request_id=current_approval,
                )
                actual = execution.output
                execution_success = execution.success
                execution_status = execution.status
                execution_error = execution.error
                execution_action = execution.action
                execution_approval_id = execution.approval_request_id

            if execution_status == "awaiting_approval":
                return SelfCorrectionResult(
                    False, execution_action, execution_status, error=execution_error,
                    attempts=tuple(attempts),
                    correction_action="awaiting_approval",
                    approval_request_id=execution_approval_id,
                )
            if not execution_success:
                verification = VerificationResult(
                    VerificationStatus.FAILED,
                    False,
                    reason="Execution failed before the requested outcome could be verified.",
                )
            else:
                verification = self.verifier.verify(
                    VerificationRequest(
                        action=execution_action,
                        expected=expected,
                        actual=actual,
                        check=check,
                        description=verification_description,
                    )
                )

            correction_note: str | None = None
            if execution_success and verification.status == VerificationStatus.VERIFIED:
                attempts.append(CorrectionAttempt(attempt_number, execution, verification))
                return SelfCorrectionResult(
                    True, execution_action, "verified", output=actual,
                    attempts=tuple(attempts),
                )

            if not execution_success and self.correction is None:
                attempts.append(CorrectionAttempt(attempt_number, execution, verification))
                return SelfCorrectionResult(
                    False, execution_action, execution_status, error=execution_error,
                    output=actual, attempts=tuple(attempts),
                    correction_action="correction_not_available",
                )

            if verification.status in {VerificationStatus.SKIPPED, VerificationStatus.UNCERTAIN}:
                attempts.append(CorrectionAttempt(attempt_number, execution, verification))
                return SelfCorrectionResult(
                    False, execution_action, "uncertain", error=verification.reason,
                    output=actual, attempts=tuple(attempts),
                    correction_action="needs_review",
                )

            if attempt_number > self.max_corrections or self.correction is None:
                attempts.append(CorrectionAttempt(attempt_number, execution, verification))
                return SelfCorrectionResult(
                    False, execution_action, "verification_failed", error=verification.reason,
                    output=actual, attempts=tuple(attempts),
                    correction_action="correction_exhausted" if self.max_corrections else "correction_not_configured",
                )

            next_arguments = self.correction(execution, verification, attempt_number)
            if next_arguments is None:
                attempts.append(CorrectionAttempt(attempt_number, execution, verification))
                return SelfCorrectionResult(
                    False, execution_action, "verification_failed", error=verification.reason,
                    output=actual, attempts=tuple(attempts),
                    correction_action="correction_declined",
                )
            if not isinstance(next_arguments, dict):
                raise TypeError("correction must return a dict of action arguments or None")

            correction_note = "Correction strategy supplied revised action arguments."
            attempts.append(CorrectionAttempt(attempt_number, execution, verification, correction_note))
            current_arguments = dict(next_arguments)
            current_approval = None

        raise RuntimeError("Self-correction loop terminated unexpectedly")

    @staticmethod
    def _default_identity():
        from core.authorization import IdentityLevel
        return IdentityLevel.UNKNOWN


__all__ = ["CorrectionAttempt", "SelfCorrectionEngine", "SelfCorrectionResult"]
