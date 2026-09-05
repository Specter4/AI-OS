"""Unified safety-aware control loop for JARVIS.

This module coordinates the existing AI-OS layers without replacing them:
interpretation/context stays conversational, authorization and approval remain
outside the LLM, judgment decides whether an action should proceed, tool
selection chooses only registered actions, execution performs the action,
verification checks the outcome, and bounded self-correction may retry with
new arguments. Mission and memory updates are explicit and durable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable

from agents.memory import MemoryStore, memory_store
from core.authorization import IdentityLevel
from core.tool_registry import Permission
from workflow.action_executor import ActionExecutionEngine, ExecutionResult
from workflow.action_registry import ActionRegistry
from workflow.judgment import JudgmentAction, JudgmentInput, JudgmentPolicy, JudgmentResult, policy
from workflow.long_running import LongRunningMission, MissionStore
from workflow.self_correction import SelfCorrectionEngine, SelfCorrectionResult
from workflow.tool_selection import AutonomousToolExecutor, ToolSelection, ToolSelector
from workflow.verification import VerificationResult, VerificationStatus, Verifier, verifier


class ControlLoopState(str, Enum):
    RECEIVED = "received"
    JUDGING = "judging"
    SELECTING = "selecting"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    CORRECTING = "correcting"
    COMPLETED = "completed"
    COMPLETED_UNVERIFIED = "completed_unverified"
    INFORMED = "informed"
    ASKING = "asking"
    STOPPED = "stopped"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    NO_TOOL = "no_tool"


@dataclass(frozen=True)
class ControlLoopInput:
    goal: str
    arguments: dict[str, Any] = field(default_factory=dict)
    identity: IdentityLevel = IdentityLevel.UNKNOWN
    permission: Permission | None = None
    irreversible: bool = False
    affects_privacy: bool = False
    affects_security: bool = False
    material_impact: bool = False
    external_side_effect: bool = False
    uncertain: bool = False
    explicit_owner_direction: bool = False
    potentially_illegal: bool = False
    clearly_harmful: bool = False
    expected: Any = None
    check: Callable[[Any], bool] | None = None
    verification_description: str = ""
    correction: Callable[[ExecutionResult, VerificationResult, int], dict[str, Any] | None] | None = None
    max_corrections: int = 0
    approval_request_id: str | None = None
    mission_id: str | None = None
    memory_updates: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class ControlLoopResult:
    goal: str
    state: ControlLoopState
    selection: ToolSelection | None = None
    judgment: JudgmentResult | None = None
    execution: ExecutionResult | SelfCorrectionResult | None = None
    verification: VerificationResult | None = None
    owner_needs_to_know: bool = False
    message: str = ""
    mission_id: str | None = None
    memory_written: tuple[str, ...] = ()


class JarvisControlLoop:
    """Run one controlled JARVIS objective through all existing safety layers."""

    def __init__(
        self,
        actions: ActionRegistry,
        *,
        judgment: JudgmentPolicy = policy,
        verifier: Verifier = verifier,
        mission_store: MissionStore | None = None,
        memory: MemoryStore = memory_store,
        interrupt: Callable[[], bool] | None = None,
    ) -> None:
        self.actions = actions
        self.judgment = judgment
        self.verifier = verifier
        self.mission_store = mission_store
        self.memory = memory
        self.interrupt = interrupt
        self.selector = ToolSelector(actions)
        self.engine = ActionExecutionEngine(actions)

    def run(self, request: ControlLoopInput) -> ControlLoopResult:
        """Execute one objective as a deterministic control-loop slice."""
        goal = request.goal.strip()
        if not goal:
            raise ValueError("goal cannot be empty")

        if self._interrupted():
            return ControlLoopResult(goal, ControlLoopState.PAUSED, message="Execution paused by interruption.")

        selection = self.selector.select(goal)
        if selection.selected is None:
            return ControlLoopResult(
                goal, ControlLoopState.NO_TOOL, selection=selection,
                message=selection.rationale,
            )

        action_spec = self.actions.require(selection.selected.action)
        permission = request.permission or self._permission_for(action_spec)
        judgment = self.judgment.judge(
            JudgmentInput(
                identity=request.identity,
                permission=permission,
                irreversible=request.irreversible or bool(action_spec.metadata.get("irreversible", False)),
                affects_privacy=request.affects_privacy or bool(action_spec.metadata.get("affects_privacy", False)),
                affects_security=request.affects_security or bool(action_spec.metadata.get("affects_security", False)),
                material_impact=request.material_impact or bool(action_spec.metadata.get("material_impact", False)),
                external_side_effect=request.external_side_effect or bool(action_spec.metadata.get("external_side_effect", False)),
                uncertain=request.uncertain,
                explicit_owner_direction=request.explicit_owner_direction,
                potentially_illegal=request.potentially_illegal or bool(action_spec.metadata.get("potentially_illegal", False)),
                clearly_harmful=request.clearly_harmful or bool(action_spec.metadata.get("clearly_harmful", False)),
            )
        )

        if judgment.action is JudgmentAction.STOP:
            self._checkpoint(request, "stopped", error=judgment.reason)
            return ControlLoopResult(
                goal, ControlLoopState.STOPPED, selection, judgment,
                owner_needs_to_know=judgment.owner_needs_to_know,
                message=judgment.reason,
                mission_id=request.mission_id,
            )

        if judgment.action is JudgmentAction.ASK:
            self._checkpoint(request, "paused", error=judgment.reason)
            return ControlLoopResult(
                goal, ControlLoopState.ASKING, selection, judgment,
                owner_needs_to_know=judgment.owner_needs_to_know,
                message=judgment.reason,
                mission_id=request.mission_id,
            )

        if self._interrupted():
            self._checkpoint(request, "paused", error="Execution paused by interruption.")
            return ControlLoopResult(
                goal, ControlLoopState.PAUSED, selection, judgment,
                owner_needs_to_know=judgment.owner_needs_to_know,
                message="Execution paused by interruption.",
                mission_id=request.mission_id,
            )

        executor = SelfCorrectionEngine(
            self.engine,
            verifier=self.verifier,
            correction=request.correction,
            max_corrections=request.max_corrections,
        )

        execution = executor.execute(
            selection.selected.action,
            request.arguments,
            identity=request.identity,
            goal=goal,
            approval_request_id=request.approval_request_id,
            expected=request.expected,
            check=request.check,
            verification_description=request.verification_description,
        )

        if isinstance(execution, SelfCorrectionResult):
            if execution.status == "awaiting_approval":
                state = ControlLoopState.AWAITING_APPROVAL
            elif execution.success:
                state = ControlLoopState.COMPLETED
            elif execution.status == "uncertain":
                state = ControlLoopState.INFORMED
            elif execution.status == "verification_failed" and execution.correction_action == "correction_exhausted":
                state = ControlLoopState.FAILED
            else:
                state = ControlLoopState.FAILED

            verification = execution.attempts[-1].verification if execution.attempts else None
            if state is ControlLoopState.COMPLETED and verification is not None and verification.status is VerificationStatus.SKIPPED:
                state = ControlLoopState.COMPLETED_UNVERIFIED

            memory_written = self._write_memory(request, execution, state)
            self._checkpoint(
                request,
                "completed" if state in {ControlLoopState.COMPLETED, ControlLoopState.COMPLETED_UNVERIFIED} else state.value,
                result=execution.output,
                error=execution.error,
            )
            return ControlLoopResult(
                goal, state, selection, judgment, execution, verification,
                owner_needs_to_know=judgment.owner_needs_to_know or state in {
                    ControlLoopState.AWAITING_APPROVAL,
                    ControlLoopState.INFORMED,
                    ControlLoopState.COMPLETED_UNVERIFIED,
                    ControlLoopState.FAILED,
                },
                message=self._message(state, execution, judgment),
                mission_id=request.mission_id,
                memory_written=memory_written,
            )

        raise RuntimeError("Unexpected control-loop execution result")

    def _interrupted(self) -> bool:
        return bool(self.interrupt and self.interrupt())

    @staticmethod
    def _permission_for(action) -> Permission:
        value = action.metadata.get("permission", Permission.READ)
        if isinstance(value, Permission):
            return value
        try:
            return Permission(str(value).lower())
        except ValueError as exc:
            raise ValueError(f"Unknown action permission: {value}") from exc

    def _checkpoint(self, request: ControlLoopInput, state: str, *, result: Any = None, error: str | None = None) -> None:
        if not request.mission_id:
            return
        try:
            mission = LongRunningMission(request.mission_id, request.goal, store=self.mission_store)
            if state == "paused":
                if mission.record.state == "running":
                    mission.pause()
                else:
                    mission.checkpoint(error=error)
            elif state == "completed":
                if mission.record.state == "queued":
                    mission.start()
                if mission.record.state in {"running", "paused"}:
                    mission.complete(result)
                else:
                    mission.checkpoint(result=result, error=error)
            elif state in {"stopped", "cancelled"}:
                if state == "cancelled":
                    mission.cancel()
                else:
                    mission.checkpoint(error=error)
            else:
                mission.checkpoint(error=error, result=result)
        except (FileNotFoundError, RuntimeError, ValueError):
            # Mission persistence must never bypass the action safety path.
            return

    def _write_memory(self, request: ControlLoopInput, execution: SelfCorrectionResult, state: ControlLoopState) -> tuple[str, ...]:
        if state not in {ControlLoopState.COMPLETED, ControlLoopState.COMPLETED_UNVERIFIED}:
            return ()
        written: list[str] = []
        for key, value, category in request.memory_updates:
            self.memory.remember(key, value, category=category, source="control_loop")
            written.append(key.strip().lower())
        return tuple(written)

    @staticmethod
    def _message(state: ControlLoopState, execution: SelfCorrectionResult, judgment: JudgmentResult) -> str:
        if state is ControlLoopState.AWAITING_APPROVAL:
            return execution.error or "Explicit approval is required before execution can continue."
        if state is ControlLoopState.COMPLETED:
            return "The action executed and its outcome was verified."
        if state is ControlLoopState.COMPLETED_UNVERIFIED:
            return "The action executed, but no postcondition was supplied, so the outcome remains unverified."
        if state is ControlLoopState.INFORMED:
            return execution.error or judgment.reason
        return execution.error or "The control loop could not complete the requested objective."


__all__ = ["ControlLoopInput", "ControlLoopResult", "ControlLoopState", "JarvisControlLoop"]
