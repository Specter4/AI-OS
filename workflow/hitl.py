"""Human-in-the-loop control for approval-gated autonomous execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from workflow.action_executor import ActionExecutionEngine, ExecutionResult
from workflow.approval import ApprovalController, ApprovalRequest, approval_controller


@dataclass(frozen=True)
class HumanControlResult:
    action: str
    status: str
    request_id: str
    message: str
    execution: ExecutionResult | None = None


class HumanControl:
    """Expose explicit approve/deny/cancel controls without involving the LLM."""

    def __init__(
        self,
        engine: ActionExecutionEngine,
        *,
        approvals: ApprovalController = approval_controller,
    ) -> None:
        self.engine = engine
        self.approvals = approvals

    def pending(self) -> list[ApprovalRequest]:
        return self.approvals.pending()

    def approve(self, request_id: str) -> HumanControlResult:
        request = self.approvals.approve(request_id)
        execution = self.engine.execute(
            request.tool,
            request.arguments,
            identity=self._owner_identity(),
            goal=request.goal,
            task=request.task,
            approval_request_id=request.id,
        )
        return HumanControlResult(
            request.tool,
            execution.status,
            request.id,
            "Approval granted and action execution attempted.",
            execution,
        )

    def deny(self, request_id: str) -> HumanControlResult:
        request = self.approvals.deny(request_id)
        return HumanControlResult(
            request.tool,
            "denied",
            request.id,
            "Approval denied; the action was not executed.",
        )

    def cancel(self, request_id: str) -> HumanControlResult:
        request = self.approvals.cancel(request_id)
        return HumanControlResult(
            request.tool,
            "cancelled",
            request.id,
            "Approval cancelled; the action was not executed.",
        )

    @staticmethod
    def _owner_identity():
        from core.authorization import IdentityLevel
        return IdentityLevel.OWNER


__all__ = ["HumanControl", "HumanControlResult"]
