"""Autonomous execution bridge for the main AI-OS executor."""

from __future__ import annotations

import inspect
from typing import Any

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
        generated_task = Task(id=self._next_id, title=task, agent=agent)
        self._next_id += 1
        log(f"Autonomy generated Task {generated_task.id}: {task} -> {agent}")
        try:
            result = dispatch(generated_task, project=self.project)
            if isinstance(result, AgentResult):
                success, output, error = result.success, result.output, result.error
            elif isinstance(result, dict) and "success" in result:
                success, output, error = bool(result["success"]), result, result.get("error")
            else:
                success, output, error = True, result, None
            generated_task.result = result
            generated_task.status = "completed" if success else "failed"
            self.project.tasks.append(generated_task)
            self.project.save(f"task_{generated_task.id}", result)
            return {"success": success, "tool": f"agent.{agent}", "result": output, "error": error}
        except Exception as exc:
            generated_task.status = "failed"
            generated_task.result = str(exc)
            self.project.tasks.append(generated_task)
            return {"success": False, "tool": f"agent.{agent}", "error": str(exc)}

    def context_snapshot(self) -> dict[str, Any]:
        tasks = [
            {"id": t.id, "title": t.title, "agent": t.agent, "status": t.status,
             "depends_on": list(t.depends_on), "result": t.result}
            for t in self.project.tasks
        ]
        return {
            "goal": self.project.goal,
            "status": self.project.status,
            "progress": self.project.progress(),
            "tasks": tasks,
            "shared_context": self.project.context_data(),
            "notes": list(self.project.notes),
        }


def execute_autonomous(goal: str, tasks, *, max_steps: int = 4, approved_permissions=None) -> tuple[Any, AutonomyResult | None]:
    """Run normal execution, then bounded policy-controlled autonomous recovery."""
    project = execute(goal, tasks)
    failed_or_blocked = [t for t in project.tasks if t.status in {"failed", "blocked"}]
    if not failed_or_blocked:
        log("Autonomous recovery not needed; project completed cleanly.")
        return project, None

    log(f"Autonomous recovery starting for {len(failed_or_blocked)} failed/blocked tasks.")
    adapter = ProjectTaskAgent(project)
    try:
        accepts_context_provider = "context_provider" in inspect.signature(AutonomyLoop).parameters
    except (TypeError, ValueError):
        accepts_context_provider = True

    kwargs = {"agent": adapter, "max_steps": max_steps}
    if accepts_context_provider:
        kwargs["context_provider"] = adapter.context_snapshot
    loop = AutonomyLoop(**kwargs)
    if not accepts_context_provider and hasattr(loop, "context_provider"):
        loop.context_provider = adapter.context_snapshot

    recovery = loop.run(goal, approved_permissions=approved_permissions)
    for decision in getattr(recovery, "recovery_decisions", []):
        log(f"Recovery policy: {decision.action} - {decision.reason}")

    if recovery.success:
        log("Autonomous recovery completed successfully.")
    else:
        log(f"Autonomous recovery stopped: {recovery.error}")
    return project, recovery
