"""Observe/action/replan loop for autonomous AI-OS execution.

The loop is deliberately policy-first: a selected tool may execute only when
its permission is already approved. The loop never grants permissions based on
LLM output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agents.tool_agent import ToolAgent, tool_agent
from core.logger import log
from core.tool_registry import Permission
from services.llm import llm


@dataclass
class Observation:
    step: int
    task: str
    tool: str | None
    success: bool
    result: Any = None
    error: str | None = None


@dataclass
class AutonomyResult:
    success: bool
    goal: str
    observations: list[Observation] = field(default_factory=list)
    error: str | None = None


class AutonomyLoop:
    """Execute a goal through repeated plan/action/observation decisions."""

    def __init__(self, agent: ToolAgent | None = None, max_steps: int = 8):
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self.agent = agent or tool_agent
        self.max_steps = max_steps

    def evaluate(self, goal: str, observations: list[Observation]) -> dict[str, Any]:
        """Ask the LLM whether the goal is complete and what to do next."""
        history = [
            {
                "step": item.step,
                "task": item.task,
                "tool": item.tool,
                "success": item.success,
                "result": item.result,
                "error": item.error,
            }
            for item in observations
        ]

        prompt = (
            "You are the evaluation layer of AI-OS.\n"
            "Evaluate the current goal using the execution history.\n"
            "Return ONLY JSON in this exact shape:\n"
            '{"complete": true, "next_task": null}\n'
            "or:\n"
            '{"complete": false, "next_task": "a concrete next action"}\n\n'
            f"GOAL:\n{goal}\n\n"
            f"EXECUTION HISTORY:\n{json.dumps(history, indent=2, default=str)}"
        )

        result = llm.generate(
            [
                {"role": "system", "content": "Evaluate progress; do not execute tools."},
                {"role": "user", "content": prompt},
            ],
            agent="autonomy_evaluator",
        )

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

    def run(
        self,
        goal: str,
        *,
        approved_permissions: set[Permission] | None = None,
    ) -> AutonomyResult:
        """Run observe/action/replan until completion or the step limit."""
        observations: list[Observation] = []
        next_task = goal

        for step in range(1, self.max_steps + 1):
            log(f"Autonomy step {step}: {next_task}")

            try:
                action = self.agent.run_task(
                    next_task,
                    approved_permissions=approved_permissions,
                )
            except Exception as exc:
                observation = Observation(
                    step=step,
                    task=next_task,
                    tool=None,
                    success=False,
                    error=str(exc),
                )
                observations.append(observation)
                return AutonomyResult(False, goal, observations, str(exc))

            observation = Observation(
                step=step,
                task=next_task,
                tool=action.get("tool"),
                success=bool(action.get("success")),
                result=action.get("result"),
                error=action.get("error"),
            )
            observations.append(observation)

            try:
                decision = self.evaluate(goal, observations)
            except Exception as exc:
                return AutonomyResult(False, goal, observations, str(exc))

            if decision["complete"]:
                return AutonomyResult(True, goal, observations)

            next_task = decision["next_task"]

        return AutonomyResult(
            False,
            goal,
            observations,
            f"Autonomy step limit ({self.max_steps}) reached before completion.",
        )


# Shared autonomous execution loop.
autonomy = AutonomyLoop()
