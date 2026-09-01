"""Live state tracking for multi-step AI-OS goals."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Iterable

from core.tasks import Task


TERMINAL_STATES = frozenset({"completed", "failed", "blocked", "cancelled"})


@dataclass(frozen=True)
class TaskStateSnapshot:
    goal: str
    tasks: tuple[Task, ...]
    current_task_id: int | None
    completed: int
    total: int
    progress: float

    @property
    def current_task(self) -> Task | None:
        if self.current_task_id is None:
            return None
        return next((task for task in self.tasks if task.id == self.current_task_id), None)

    @property
    def next_task(self) -> Task | None:
        for task in self.tasks:
            if task.status == "pending" and all(
                next((dependency for dependency in self.tasks if dependency.id == dep_id), None)
                and next(dependency for dependency in self.tasks if dependency.id == dep_id).status == "completed"
                for dep_id in task.depends_on
            ):
                return task
        return None


class TaskState:
    """Thread-safe live execution state for one or more planned tasks."""

    def __init__(self, goal: str, tasks: Iterable[Task]) -> None:
        self.goal = goal.rstrip(".!? ")
        self._tasks = {task.id: task for task in tasks}
        self._lock = RLock()

    def start(self, task_id: int) -> Task:
        with self._lock:
            task = self._get(task_id)
            if task.status != "pending":
                raise ValueError(f"Task {task_id} cannot start from status {task.status}")
            if not self._dependencies_complete(task):
                raise ValueError(f"Task {task_id} has incomplete dependencies")
            task.status = "running"
            return task

    def complete(self, task_id: int, result: str | None = None) -> Task:
        return self._finish(task_id, "completed", result)

    def fail(self, task_id: int, result: str | None = None) -> Task:
        return self._finish(task_id, "failed", result)

    def block(self, task_id: int, result: str | None = None) -> Task:
        return self._finish(task_id, "blocked", result)

    def cancel(self, task_id: int, result: str | None = None) -> Task:
        return self._finish(task_id, "cancelled", result)

    def snapshot(self) -> TaskStateSnapshot:
        with self._lock:
            tasks = tuple(self._tasks.values())
            completed = sum(task.status == "completed" for task in tasks)
            current = next((task.id for task in tasks if task.status == "running"), None)
            total = len(tasks)
            return TaskStateSnapshot(
                goal=self.goal,
                tasks=tasks,
                current_task_id=current,
                completed=completed,
                total=total,
                progress=(completed / total if total else 1.0),
            )

    def _finish(self, task_id: int, status: str, result: str | None) -> Task:
        with self._lock:
            task = self._get(task_id)
            if task.status not in {"pending", "running"}:
                raise ValueError(f"Task {task_id} cannot become {status} from status {task.status}")
            task.status = status
            task.result = result
            return task

    def _dependencies_complete(self, task: Task) -> bool:
        return all(self._get(dep_id).status == "completed" for dep_id in task.depends_on)

    def _get(self, task_id: int) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"Unknown task: {task_id}") from exc


__all__ = ["TaskState", "TaskStateSnapshot", "TERMINAL_STATES"]
