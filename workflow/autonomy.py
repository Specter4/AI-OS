"""Observe/action/replan loop for autonomous AI-OS execution.

The loop is policy-first: the LLM can select a registered tool, but it cannot
approve permissions. Elevated actions can pause for an application-supplied
approval provider, while failures remain bounded by the recovery policy.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from agents.tool_agent import ApprovalProvider, ToolAgent, tool_agent
from core.logger import log
from core.tool_registry import Permission
from services.llm import llm
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


class AutonomyLoop:
    """Execute a goal through repeated plan/action/observation decisions."""

    def __init__(
        self,
        agent: ToolAgent | None = None,
        max_steps: int = 8,
        context_provider: Callable[[], Any] | None = None,
        approval_provider: ApprovalProvider | None = None,
    ):
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self.agent = agent or tool_agent
        self.max_steps = max_steps
        self.context_provider = context_provider
        self.approval_provider = approval_provider

    def _context(self) -> Any:
        if self.context_provider is None:
            return None
        return self.context_provider()

    def evaluate(self, goal: str, observations: list[Observation], context: Any = None) -> dict[str, Any]:
        history = [
            {
                "step": item.step, "task": item.task, "tool": item.tool,
                "success": item.success, "result": item.result, "error": item.error,
                "recovery_action": item.recovery_action,
                "recovery_reason": item.recovery_reason,
            }
            for item in observations
        ]
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

    def _evaluate_compatibly(self, goal: str, observations: list[Observation], context: Any) -> dict[str, Any]:
        evaluator = self.evaluate
        try:
            accepts_context = len(inspect.signature(evaluator).parameters) >= 3
        except (TypeError, ValueError):
            accepts_context = True
        return evaluator(goal, observations, context) if accepts_context else evaluator(goal, observations)

    @staticmethod
    def _recovery(error: str | None) -> RecoveryDecision:
        return classify_failure(error)

    def _run_task(self, task: str, approved_permissions: set[Permission] | None) -> Any:
        """Invoke agents with approval support while preserving older adapters."""
        kwargs: dict[str, Any] = {"approved_permissions": approved_permissions}
        if self.approval_provider is not None:
            try:
                if "approval_provider" in inspect.signature(self.agent.run_task).parameters:
                    kwargs["approval_provider"] = self.approval_provider
            except (TypeError, ValueError):
                kwargs["approval_provider"] = self.approval_provider
        return self.agent.run_task(task, **kwargs)

    def run(self, goal: str, *, approved_permissions: set[Permission] | None = None) -> AutonomyResult:
        """Run observe/action/replan with bounded recovery and approval gates."""
        observations: list[Observation] = []
        next_task = goal

        for step in range(1, self.max_steps + 1):
            log(f"Autonomy step {step}: {next_task}")
            try:
                action = self._run_task(next_task, approved_permissions)
            except Exception as exc:
                action = {"success": False, "tool": None, "error": str(exc)}

            success = bool(action.get("success"))
            recovery = None if success else self._recovery(action.get("error"))
            observation = Observation(
                step=step, task=next_task, tool=action.get("tool"), success=success,
                result=action.get("result"), error=action.get("error"),
                recovery_action=recovery.action if recovery else None,
                recovery_reason=recovery.reason if recovery else None,
            )
            observations.append(observation)

            if not success and recovery is not None:
                log(f"Autonomy recovery decision: {recovery.action} — {recovery.reason}")
                if recovery.requires_approval:
                    return AutonomyResult(
                        False, goal, observations,
                        "Explicit approval is required before this action can continue.",
                    )
                if recovery.retry:
                    continue

            try:
                decision = self._evaluate_compatibly(goal, observations, self._context())
            except Exception as exc:
                return AutonomyResult(False, goal, observations, str(exc))
            if decision["complete"]:
                return AutonomyResult(True, goal, observations)
            next_task = decision["next_task"]

        return AutonomyResult(
            False, goal, observations,
            f"Autonomy step limit ({self.max_steps}) reached before completion.",
        )


# Shared autonomous execution loop. No approval provider is configured by
# default, so elevated actions fail closed until the host application supplies
# an explicit approval boundary.
autonomy = AutonomyLoop()
