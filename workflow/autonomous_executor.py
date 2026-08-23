"""Autonomous execution bridge for the main AI-OS executor.

The normal dependency-aware executor remains the deterministic execution path.
This module adds a bounded recovery layer: when a planned project does not
finish cleanly, AI-OS can use the observe/action/re-plan loop to attempt
concrete recovery actions through the existing dispatcher.
"""

from __future__ import annotations

from typing import Any

from agents.tool_agent import ToolAgent
from core.logger import log
from core.result import AgentResult
from core.tasks import Task
from workflow.autonomy import AutonomyLoop, AutonomyResult
from workflow.dispatcher import dispatch
from workflow.executor import execute
from workflow.parser import detect_agent


class ProjectTaskAgent:
    """Adapter that lets the autonomy loop execute normal AI-OS agents."""

    def __init__(self, project):
        self.project = project
        self._next_id = max((task.id for task in project.tasks), default=0) + 1

    def run_task(self, task: str, *, approved_permissions=None) -> dict[str, Any]:
        agent = detect_agent(task)
        generated_task = Task(
            id=self._next_id,
            title=task,
            agent=agent,
        )
        self._next_id += 1

        log(
            f"Autonomy generated Task {generated_task.id}: "
            f"{task} -> {agent}"
        )

        try:
            result = dispatch(generated_task, project=self.project)

            if isinstance(result, AgentResult):
                success = result.success
                output = result.output
                error = result.error
            elif isinstance(result, dict) and "success" in result:
                success = bool(result["success"])
                output = result
                error = result.get("error")
            else:
                success = True
                output = result
                error = None

            generated_task.result = result
            generated_task.status = "completed" if success else "failed"
            self.project.tasks.append(generated_task)
            self.project.save(f"task_{generated_task.id}", result)

            return {
                "success": success,
                "tool": f"agent.{agent}",
                "result": output,
                "error": error,
            }

        except Exception as exc:
            generated_task.status = "failed"
            generated_task.result = str(exc)
            self.project.tasks.append(generated_task)
            return {
                "success": False,
                "tool": f"agent.{agent}",
                "error": str(exc),
            }


def execute_autonomous(
    goal: str,
    tasks,
    *,
    max_steps: int = 4,
    approved_permissions=None,
) -> tuple[Any, AutonomyResult | None]:
    """Run the normal executor, then bounded autonomous recovery if needed.

    This intentionally does not replace deterministic planning/execution.
    Autonomous recovery activates only when the initial project contains
    failed or blocked tasks, preventing unnecessary LLM replanning on clean
    runs.
    """
    project = execute(goal, tasks)

    failed_or_blocked = [
        task
        for task in project.tasks
        if task.status in {"failed", "blocked"}
    ]

    if not failed_or_blocked:
        log("Autonomous recovery not needed; project completed cleanly.")
        return project, None

    log(
        f"Autonomous recovery starting for {len(failed_or_blocked)} "
        "failed/blocked tasks."
    )

    adapter = ProjectTaskAgent(project)
    loop = AutonomyLoop(
        agent=adapter,
        max_steps=max_steps,
    )
    recovery = loop.run(
        goal,
        approved_permissions=approved_permissions,
    )

    if recovery.success:
        log("Autonomous recovery completed successfully.")
    else:
        log(f"Autonomous recovery stopped: {recovery.error}")

    return project, recovery
