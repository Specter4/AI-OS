"""Bridge natural-language goal plans into executable AI-OS tasks."""

from __future__ import annotations

from core.tasks import Task
from workflow.planner import GoalPlan, GoalPlanner, planner as default_planner


class TaskOrchestrator:
    """Convert a GoalPlan into dependency-aware executable Task objects."""

    def __init__(self, planner: GoalPlanner | None = None):
        self.planner = planner or default_planner

    @staticmethod
    def _agent_for(description: str) -> str:
        text = description.lower()
        if any(word in text for word in ("research", "find", "analyze", "compare")):
            return "research"
        if any(word in text for word in ("write", "draft", "summarize")):
            return "content"
        return "assistant"

    def build(self, goal: str) -> list[Task]:
        plan = self.planner.plan(goal)
        return self.tasks_from_plan(plan)

    def tasks_from_plan(self, plan: GoalPlan) -> list[Task]:
        return [
            Task(
                id=item.task_id,
                title=item.description,
                agent=self._agent_for(item.description),
                depends_on=list(item.depends_on),
                metadata={"goal": plan.goal, "planned": True},
            )
            for item in plan.tasks
        ]


orchestrator = TaskOrchestrator()

__all__ = ["TaskOrchestrator", "orchestrator"]
