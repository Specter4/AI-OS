"""Natural-language goal planning for AI-OS."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class PlannedTask:
    task_id: int
    description: str
    depends_on: tuple[int, ...] = ()


@dataclass(frozen=True)
class GoalPlan:
    goal: str
    tasks: tuple[PlannedTask, ...]

    @property
    def is_multi_task(self) -> bool:
        return len(self.tasks) > 1


class GoalPlanner:
    """Turn a natural request into an explicit, inspectable task plan."""

    _ACTION_VERBS = r"compare|research|find|check|draft|write|send|build|recommend|summarize|analyze|deploy"

    def plan(self, goal: str) -> GoalPlan:
        if not goal or not goal.strip():
            raise ValueError("goal cannot be empty")

        clean = " ".join(goal.split())
        parts = self._split_tasks(clean)

        tasks = tuple(
            PlannedTask(
                task_id=index,
                description=part.strip(" ,."),
                depends_on=((index - 1,) if index > 1 else ()),
            )
            for index, part in enumerate(parts, start=1)
            if part.strip(" ,.")
        )
        return GoalPlan(goal=clean, tasks=tasks)

    def _split_tasks(self, text: str) -> list[str]:
        """Split only at natural action boundaries, while retaining task text."""
        boundary = re.compile(
            rf"(?:,\s*)?\b(?:then|also)\b\s+|"
            rf",\s*and\s+(?=(?:{self._ACTION_VERBS})\b)|"
            rf"\s+and\s+(?=(?:{self._ACTION_VERBS})\b)",
            re.I,
        )
        parts = boundary.split(text)
        return [part for part in parts if part.strip(" ,.")]


planner = GoalPlanner()

__all__ = ["GoalPlanner", "GoalPlan", "PlannedTask", "planner"]
