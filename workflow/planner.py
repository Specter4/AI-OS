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
    """Turn a natural request into an explicit, inspectable task plan.

    This first planning layer is intentionally deterministic. LLM-based
    decomposition can later replace the splitter while preserving this plan
    contract for orchestration, interruption, recovery, and UI layers.
    """

    _SEPARATORS = re.compile(r"\s*(?:,\s*(?=(?:and|then|also)\b)|\bthen\b|\balso\b|\band\s+(?=(?:compare|research|find|check|draft|write|send|build|recommend|summarize|analyze|deploy)\b))\s*", re.I)

    def plan(self, goal: str) -> GoalPlan:
        if not goal or not goal.strip():
            raise ValueError("goal cannot be empty")

        clean = " ".join(goal.split())
        parts = [part.strip(" ,.") for part in self._SEPARATORS.split(clean) if part.strip(" ,.")]

        # Preserve the complete request when no reliable task boundary exists.
        if not parts:
            parts = [clean]

        tasks = tuple(
            PlannedTask(task_id=index, description=part, depends_on=((index - 1,) if index > 1 else ()))
            for index, part in enumerate(parts, start=1)
        )
        return GoalPlan(goal=clean, tasks=tasks)


planner = GoalPlanner()

__all__ = ["GoalPlanner", "GoalPlan", "PlannedTask", "planner"]
