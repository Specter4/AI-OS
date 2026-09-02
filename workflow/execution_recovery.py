"""Execution feedback, retry, and recovery policy for AI-OS actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from workflow.action_executor import ActionExecutionEngine, ExecutionResult


@dataclass(frozen=True)
class ExecutionAttempt:
    attempt: int
    status: str
    output: Any = None
    error: str | None = None


@dataclass(frozen=True)
class RecoveryResult:
    success: bool
    action: str
    status: str
    output: Any = None
    error: str | None = None
    attempts: tuple[ExecutionAttempt, ...] = ()
    approval_request_id: str | None = None
    recovery_action: str | None = None


class ExecutionRecovery:
    """Turn raw execution outcomes into observable, recoverable results.

    Retries are opt-in. A retry policy decides whether a failed attempt is
    transient and safe to repeat; the engine never retries denied, rejected,
    awaiting-approval, or otherwise successful actions automatically.
    """

    def __init__(
        self,
        engine: ActionExecutionEngine,
        *,
        retry_policy: Callable[[ExecutionResult, int], bool] | None = None,
        max_retries: int = 0,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self.engine = engine
        self.retry_policy = retry_policy or (lambda result, attempt: False)
        self.max_retries = max_retries

    def execute(
        self,
        action_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        identity=None,
        goal: str | None = None,
        task: str | None = None,
        approval_request_id: str | None = None,
    ) -> RecoveryResult:
        attempts: list[ExecutionAttempt] = []
        current_approval = approval_request_id

        for attempt_number in range(1, self.max_retries + 2):
            result = self.engine.execute(
                action_name,
                arguments,
                identity=identity if identity is not None else self._default_identity(),
                goal=goal,
                task=task,
                approval_request_id=current_approval,
            )
            attempts.append(
                ExecutionAttempt(
                    attempt=attempt_number,
                    status=result.status,
                    output=result.output,
                    error=result.error,
                )
            )

            if result.success:
                return RecoveryResult(
                    True, result.action, "completed", output=result.output,
                    attempts=tuple(attempts),
                )

            if result.status == "awaiting_approval":
                return RecoveryResult(
                    False, result.action, result.status, error=result.error,
                    attempts=tuple(attempts),
                    approval_request_id=result.approval_request_id,
                )

            if result.status != "failed" or attempt_number > self.max_retries:
                return RecoveryResult(
                    False, result.action, result.status, error=result.error,
                    attempts=tuple(attempts),
                    approval_request_id=result.approval_request_id,
                    recovery_action="retry_available" if result.status == "failed" and self.max_retries == 0 else None,
                )

            if not self.retry_policy(result, attempt_number):
                return RecoveryResult(
                    False, result.action, "failed", error=result.error,
                    attempts=tuple(attempts),
                    recovery_action="retry_not_recommended",
                )

            # Approval is deliberately not carried into a retry. The action
            # engine must re-check authorization and approval for each attempt.
            current_approval = None

        raise RuntimeError("Execution recovery loop terminated unexpectedly")

    @staticmethod
    def _default_identity():
        from core.authorization import IdentityLevel
        return IdentityLevel.UNKNOWN


__all__ = ["ExecutionAttempt", "ExecutionRecovery", "RecoveryResult"]
