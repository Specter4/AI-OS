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

    _SEPARATORS = re.compile(
        r"\s*(?:"
        r",\s*(?=(?:and|then|also)\b)"
        r"|\bthen\b"
        r"|\balso\b"
        r"|\band\s+(?=(?:compare|research|find|check|draft|write|send|build|recommend|summarize|analyze|deploy)\b)"
        r")\s*",
        re.I,
    )

    def plan(self, goal: str) -> GoalPlan:
        if not goal or not goal.strip():
            raise ValueError("goal cannot be empty")

        clean = " ".join(goal.split())
        parts = [part.strip(" ,.") for part in self._SEPARATORS.split(clean) if part.strip(" ,.")]

        expanded: list[str] = []
        for part in parts:
            fragments = re.split(
                r"\s*,?\s+and\s+(?=(?:compare|research|find|check|draft|write|send|build|recommend|summarize|analyze|deploy)\b)",
                part,
                flags=re.I,
            )
            expanded.extend(fragment.strip(" ,.") for fragment in fragments if fragment.strip(" ,."))
        parts = expanded or [clean]

        tasks = tuple(
            PlannedTask(
                task_id=index,
                description=part,
                depends_on=((index - 1,) if index > 1 else ()),
            )
            for index, part in enumerate(parts, start=1)
        )
        return GoalPlan(goal=clean, tasks=tasks)


planner = GoalPlanner()

__all__ = ["GoalPlanner", "GoalPlan", "PlannedTask", "planner"]
