"""
Project State

Represents one AI-OS project.
"""

from dataclasses import dataclass, field
from typing import List

from core.tasks import Task
from core.context import ProjectContext


@dataclass
class Project:

    # Required
    goal: str

    # Optional
    status: str = "running"

    tasks: List[Task] = field(default_factory=list)

    notes: List[str] = field(default_factory=list)

    context: ProjectContext = field(
        default_factory=ProjectContext
    )

    def completed_tasks(self):

        return len(
            [
                t for t in self.tasks
                if t.status == "completed"
            ]
        )

    def failed_tasks(self):

        return len(
            [
                t for t in self.tasks
                if t.status == "failed"
            ]
        )

    def progress(self):

        if not self.tasks:
            return 0

        return int(
            self.completed_tasks()
            / len(self.tasks)
            * 100
        )

    def summary(self):

        return {
            "goal": self.goal,
            "status": self.status,
            "progress": self.progress(),
            "completed": self.completed_tasks(),
            "failed": self.failed_tasks(),
            "total": len(self.tasks),
        }

    # -------------------------
    # Shared Project Context
    # -------------------------

    def save(self, key, value):

        self.context.save(key, value)

    def load(self, key):

        return self.context.get(key)

    def context_data(self):

        return self.context.all() 