"""User-facing control layer for autonomous AI-OS runs.

This module keeps interactive state outside the LLM. Hosts such as Discord,
CLI, or a future web app can start runs, inspect approval requests, and
approve/deny suspended runs without knowing the autonomy internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from workflow.approval import ApprovalRequest, approval_controller
from workflow.autonomy import AutonomyLoop, AutonomyResult, autonomy


@dataclass
class InteractiveRun:
    id: str
    loop: AutonomyLoop
    result: AutonomyResult


class AutonomyInteraction:
    """Thread-safe session manager for interactive autonomous execution."""

    def __init__(self, default_loop: AutonomyLoop | None = None) -> None:
        self.default_loop = default_loop or autonomy
        self._runs: dict[str, InteractiveRun] = {}
        self._lock = RLock()
        self._counter = 0

    def start(self, goal: str, *, max_steps: int | None = None) -> InteractiveRun:
        loop = self.default_loop
        if max_steps is not None:
            loop = AutonomyLoop(
                agent=loop.agent,
                max_steps=max_steps,
                context_provider=loop.context_provider,
                approval_provider=loop.approval_provider,
            )
        result = loop.run(goal)
        with self._lock:
            self._counter += 1
            run_id = f"run-{self._counter:04d}"
            run = InteractiveRun(run_id, loop, result)
            self._runs[run_id] = run
            return run

    def get(self, run_id: str) -> InteractiveRun:
        with self._lock:
            try:
                return self._runs[run_id]
            except KeyError as exc:
                raise KeyError(f"Unknown autonomous run: {run_id}") from exc

    def pending_approvals(self) -> list[ApprovalRequest]:
        return approval_controller.pending()

    def approve(self, run_id: str, request_id: str) -> InteractiveRun:
        run = self.get(run_id)
        approval_controller.approve(request_id)
        run.result = run.loop.resume(run.result, request_id)
        return run

    def deny(self, run_id: str, request_id: str) -> InteractiveRun:
        run = self.get(run_id)
        approval_controller.deny(request_id)
        run.result = AutonomyResult(
            success=False,
            goal=run.result.goal,
            observations=run.result.observations,
            error="Approval denied by the user.",
            approval_request=run.result.approval_request,
            suspended_task=run.result.suspended_task,
        )
        return run

    @staticmethod
    def format_result(run: InteractiveRun) -> str:
        result = run.result
        if result.success:
            return f"Run {run.id} completed successfully."
        if result.approval_request is not None:
            request = result.approval_request
            return (
                f"APPROVAL REQUIRED\n"
                f"Run: {run.id}\n"
                f"Request: {request.id}\n"
                f"Action: {request.tool}\n"
                f"Permission: {request.permission.value}\n"
                f"Description: {request.description}\n"
                f"Arguments: {request.arguments}"
            )
        return f"Run {run.id} stopped: {result.error or 'unknown error'}"


interaction = AutonomyInteraction()
