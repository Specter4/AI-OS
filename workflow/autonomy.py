"""Observe/action/replan loop for autonomous AI-OS execution."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from agents.tool_agent import ApprovalProvider, ToolAgent, tool_agent
from core.logger import log
from core.tool_registry import Permission, ToolSpec
from services.llm import llm
from workflow.approval import ApprovalRequest, approval_controller
from workflow.interrupt import InterruptController
from workflow.recovery import RecoveryDecision, classify_failure


@dataclass
class Observation:
    step: int
    task: str
    tool: str | None
    success: bool
    result: Any = None
    error: str | None = None
    recovery_action: str | None = None
    recovery_reason: str | None = None


@dataclass
class AutonomyResult:
    success: bool
    goal: str
    observations: list[Observation] = field(default_factory=list)
    error: str | None = None
    approval_request: ApprovalRequest | None = None
    suspended_task: str | None = None


class AutonomyLoop:
    """Execute a goal through repeated plan/action/observation decisions."""

    def __init__(self, agent: ToolAgent | None = None, max_steps: int = 8,
                 context_provider: Callable[[], Any] | None = None,
                 approval_provider: ApprovalProvider | None = None,
                 interrupt_controller: InterruptController | None = None):
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self.agent = agent or tool_agent
        self.max_steps = max_steps
        self.context_provider = context_provider
        self.approval_provider = approval_provider
        self.interrupt_controller = interrupt_controller or InterruptController()

    def interrupt(self, reason: str = "Interrupted by the user.", instruction: str | None = None):
        """Request cooperative interruption of the current run."""
        return self.interrupt_controller.request(reason, instruction)

    def _context(self) -> Any:
        if self.context_provider is None:
            return None
        return self.context_provider()

    def evaluate(self, goal: str, observations: list[Observation], context: Any = None) -> dict[str, Any]:
        history = [{"step": i.step, "task": i.task, "tool": i.tool, "success": i.success,
                    "result": i.result, "error": i.error, "recovery_action": i.recovery_action,
                    "recovery_reason": i.recovery_reason} for i in observations]
        prompt = (
            "You are the evaluation and recovery-planning layer of AI-OS.\n"
            "Evaluate the current goal using project state and execution history.\n"
            "Prefer reusing successful work. Do not repeat completed tasks unless the evidence shows they are invalid or insufficient.\n"
            "If a task failed and the recovery policy says replan, identify the smallest concrete recovery action.\n"
            "Return ONLY JSON in this exact shape:\n"
            '{"complete": true, "next_task": null}\n'
            "or:\n"
            '{"complete": false, "next_task": "a concrete next action"}\n\n'
            f"GOAL:\n{goal}\n\nPROJECT STATE:\n{json.dumps(context, indent=2, default=str)}\n\n"
            f"EXECUTION HISTORY:\n{json.dumps(history, indent=2, default=str)}"
        )
        result = llm.generate([
            {"role": "system", "content": "Evaluate progress and plan recovery; do not execute tools."},
            {"role": "user", "content": prompt},
        ], agent="autonomy_evaluator")
        if not result.success:
            raise RuntimeError(result.error)
        try:
            decision = json.loads(result.output.strip())
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Autonomy evaluator returned invalid JSON") from exc
        if not isinstance(decision.get("complete"), bool):
            raise ValueError("Autonomy evaluator returned invalid completion state")
        if decision["complete"]:
            return {"complete": True, "next_task": None}
        next_task = decision.get("next_task")
        if not isinstance(next_task, str) or not next_task.strip():
            raise ValueError("Autonomy evaluator returned no next task")
        return {"complete": False, "next_task": next_task.strip()}

    def _evaluate_compatibly(self, goal, observations, context):
        evaluator = self.evaluate
        try:
            accepts_context = len(inspect.signature(evaluator).parameters) >= 3
        except (TypeError, ValueError):
            accepts_context = True
        return evaluator(goal, observations, context) if accepts_context else evaluator(goal, observations)

    @staticmethod
    def _recovery(error: str | None) -> RecoveryDecision:
        return classify_failure(error)

    def _approval_callback(self, goal: str, task: str) -> ApprovalProvider:
        def request(spec: ToolSpec, arguments: dict[str, Any]) -> bool:
            self._last_approval_request = approval_controller.create(spec, arguments, goal=goal, task=task)
            return False
        return request

    def _run_task(self, task, approved_permissions, *, goal):
        kwargs = {"approved_permissions": approved_permissions}
        provider = self.approval_provider or self._approval_callback(goal, task)
        try:
            if "approval_provider" in inspect.signature(self.agent.run_task).parameters:
                kwargs["approval_provider"] = provider
        except (TypeError, ValueError):
            kwargs["approval_provider"] = provider
        return self.agent.run_task(task, **kwargs)

    def _interrupted_result(self, goal, observations, task):
        request = self.interrupt_controller.get()
        if request is None:
            return None
        self.interrupt_controller.clear()
        log(f"Autonomy interrupted: {request.reason}")
        return AutonomyResult(False, goal, observations, request.reason, suspended_task=task)

    def _run_loop(self, goal, next_task, observations, *, approved_permissions=None):
        for step in range(len(observations) + 1, self.max_steps + 1):
            interrupted = self._interrupted_result(goal, observations, next_task)
            if interrupted:
                return interrupted
            self._last_approval_request = None
            log(f"Autonomy step {step}: {next_task}")
            try:
                action = self._run_task(next_task, approved_permissions, goal=goal)
            except Exception as exc:
                action = {"success": False, "tool": None, "error": str(exc)}
            interrupted = self._interrupted_result(goal, observations, next_task)
            if interrupted:
                return interrupted
            success = bool(action.get("success"))
            recovery = None if success else self._recovery(action.get("error"))
            observations.append(Observation(step, next_task, action.get("tool"), success,
                                             action.get("result"), action.get("error"),
                                             recovery.action if recovery else None,
                                             recovery.reason if recovery else None))
            if not success and recovery is not None:
                log(f"Autonomy recovery decision: {recovery.action} — {recovery.reason}")
                if recovery.requires_approval:
                    return AutonomyResult(False, goal, observations,
                                          "Explicit approval is required before this action can continue.",
                                          approval_request=getattr(self, "_last_approval_request", None),
                                          suspended_task=next_task)
                if recovery.retry:
                    continue
            try:
                decision = self._evaluate_compatibly(goal, observations, self._context())
            except Exception as exc:
                return AutonomyResult(False, goal, observations, str(exc))
            if decision["complete"]:
                return AutonomyResult(True, goal, observations)
            next_task = decision["next_task"]
        return AutonomyResult(False, goal, observations,
                              f"Autonomy step limit ({self.max_steps}) reached before completion.")

    def run(self, goal: str, *, approved_permissions=None):
        return self._run_loop(goal, goal, [], approved_permissions=approved_permissions)

    def resume(self, result: AutonomyResult, approval_request_id: str):
        if result.success:
            raise ValueError("Cannot resume a completed autonomous run")
        request = approval_controller.get(approval_request_id)
        if request.status != "approved":
            raise PermissionError(f"Approval request is not approved: {approval_request_id}")
        if result.approval_request is None or result.approval_request.id != approval_request_id:
            raise ValueError("Approval request does not belong to this autonomous run")
        return self._run_loop(result.goal, result.suspended_task or request.task or request.tool,
                              list(result.observations), approved_permissions={request.permission})

    def resume_with_instruction(self, result: AutonomyResult, instruction: str):
        """Resume an interrupted run using the user's revised instruction."""
        if result.success:
            raise ValueError("Cannot resume a completed autonomous run")
        instruction = instruction.strip()
        if not instruction:
            raise ValueError("instruction cannot be empty")
        return self._run_loop(result.goal, instruction, list(result.observations))


autonomy = AutonomyLoop()
