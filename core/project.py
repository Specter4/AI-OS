"""
Project State

Represents one AI-OS project and supports persistence/resume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

from core.tasks import Task
from core.context import ProjectContext


@dataclass
class Project:
    goal: str
    status: str = "running"
    tasks: List[Task] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    context: ProjectContext = field(default_factory=ProjectContext)

    def completed_tasks(self):
        return len([t for t in self.tasks if t.status == "completed"])

    def failed_tasks(self):
        return len([t for t in self.tasks if t.status == "failed"])

    def progress(self):
        if not self.tasks:
            return 0
        return int(self.completed_tasks() / len(self.tasks) * 100)

    def summary(self):
        return {
            "goal": self.goal,
            "status": self.status,
            "progress": self.progress(),
            "completed": self.completed_tasks(),
            "failed": self.failed_tasks(),
            "total": len(self.tasks),
        }

    def save(self, key, value):
        self.context.save(key, value)

    def load(self, key):
        return self.context.get(key)

    def context_data(self):
        return self.context.all()

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "status": self.status,
            "notes": list(self.notes),
            "context": self.context_data(),
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "agent": task.agent,
                    "priority": task.priority,
                    "status": task.status,
                    "result": task.result,
                    "metadata": dict(task.metadata),
                    "depends_on": list(task.depends_on),
                }
                for task in self.tasks
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        project = cls(
            goal=str(data["goal"]),
            status=str(data.get("status", "running")),
            notes=list(data.get("notes", [])),
        )
        for key, value in data.get("context", {}).items():
            project.save(key, value)
        for raw in data.get("tasks", []):
            project.tasks.append(Task(**raw))
        return project

    def persist(self, project_id: str, root: str | Path = "data/projects") -> Path:
        """Persist this project atomically so it can be resumed later."""
        directory = Path(root)
        directory.mkdir(parents=True, exist_ok=True)
        safe_id = "".join(c for c in project_id if c.isalnum() or c in "-_ ").strip()
        if not safe_id:
            raise ValueError("project_id cannot be empty")
        target = directory / f"{safe_id}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        temporary.replace(target)
        return target

    @classmethod
    def resume(cls, project_id: str, root: str | Path = "data/projects") -> "Project":
        """Load a previously persisted project without losing task state."""
        safe_id = "".join(c for c in project_id if c.isalnum() or c in "-_ ").strip()
        if not safe_id:
            raise ValueError("project_id cannot be empty")
        path = Path(root) / f"{safe_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Project not found: {project_id}")
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
