"""Deterministic execution engine for registered AI-OS actions.

Authorization and approval remain outside the LLM. An action is executed only
after registration, identity policy, and any required approval are satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.authorization import IdentityLevel, AuthorizationPolicy, policy
from core.tool_registry import Permission, ToolSpec
from workflow.action_registry import ActionRegistry, ActionSpec
from workflow.approval import ApprovalController, ApprovalRequest, approval_controller


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    action: str
    status: str
    output: Any = None
    error: str | None = None
    approval_request_id: str | None = None


class ActionExecutionEngine:
    """Execute registered actions through authorization and approval gates."""

    def __init__(
        self,
        registry: ActionRegistry,
        *,
        authorization: AuthorizationPolicy = policy,
        approvals: ApprovalController = approval_controller,
    ) -> None:
        self.registry = registry
        self.authorization = authorization
        self.approvals = approvals

    def execute(
        self,
        action_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        identity: IdentityLevel = IdentityLevel.UNKNOWN,
        goal: str | None = None,
        task: str | None = None,
        approval_request_id: str | None = None,
    ) -> ExecutionResult:
        arguments = dict(arguments or {})
        try:
            action = self.registry.require(action_name)
        except KeyError as exc:
            return ExecutionResult(False, action_name, "rejected", error=str(exc))

        if not action.can_execute():
            return ExecutionResult(
                False, action.name, "rejected",
                error=f"Action '{action.name}' has no executable handler",
            )

        permission = self._permission_for(action)
        decision = self.authorization.decide(identity, permission)
        needs_approval = action.requires_approval or decision.requires_approval

        if not decision.allowed and not decision.requires_approval:
            return ExecutionResult(False, action.name, "denied", error=decision.reason)

        if needs_approval:
            if approval_request_id is None:
                request = self.approvals.create(
                    self._tool_spec(action, permission), arguments,
                    goal=goal, task=task,
                )
                return ExecutionResult(
                    False, action.name, "awaiting_approval",
                    error=decision.reason or "Explicit approval is required.",
                    approval_request_id=request.id,
                )
            try:
                request = self.approvals.get(approval_request_id)
            except KeyError as exc:
                return ExecutionResult(False, action.name, "rejected", error=str(exc))
            if request.tool != action.name or request.arguments != arguments:
                return ExecutionResult(False, action.name, "rejected", error="Approval request does not match the requested execution")
            if request.status != "approved":
                return ExecutionResult(False, action.name, "denied", error="Approval was not granted", approval_request_id=request.id)

        try:
            output = action.handler(**arguments)  # type: ignore[misc]
        except Exception as exc:
            return ExecutionResult(False, action.name, "failed", error=str(exc))

        return ExecutionResult(True, action.name, "completed", output=output)

    @staticmethod
    def _permission_for(action: ActionSpec) -> Permission:
        value = action.metadata.get("permission", Permission.READ)
        if isinstance(value, Permission):
            return value
        try:
            return Permission(str(value).lower())
        except ValueError as exc:
            raise ValueError(f"Unknown action permission: {value}") from exc

    @staticmethod
    def _tool_spec(action: ActionSpec, permission: Permission) -> ToolSpec:
        assert action.handler is not None
        return ToolSpec(action.name, action.description, action.handler, permission)


__all__ = ["ActionExecutionEngine", "ExecutionResult"]
