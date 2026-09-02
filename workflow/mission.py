"""End-to-end autonomous mission lifecycle for AI-OS."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.project import Project
from workflow.executor import execute, resume_project
from workflow.planner import GoalPlanner, planner as default_planner
from workflow.orchestrator import TaskOrchestrator


@dataclass(frozen=True)
class MissionReport:
    mission_id: str
    goal: str
    status: str
    progress: int
    completed: int
    failed: int
    total: int
    generated_at: str
    tasks: tuple[dict[str, object], ...]


class AutonomousMission:
    """Own the durable lifecycle of a user objective from plan to report."""

    def __init__(
        self,
        *,
        orchestrator: TaskOrchestrator | None = None,
        planner: GoalPlanner | None = None,
        project_root: str = "data/projects",
    ) -> None:
        self.planner = planner or default_planner
        self.orchestrator = orchestrator or TaskOrchestrator(self.planner)
        self.project_root = project_root

    def start(self, mission_id: str, goal: str) -> Project:
        """Plan, execute, checkpoint, and return the durable mission project."""
        if not mission_id.strip():
            raise ValueError("mission_id cannot be empty")
        if not goal.strip():
            raise ValueError("goal cannot be empty")

        tasks = self.orchestrator.build(goal)
        return execute(
            goal,
            tasks,
            project_id=mission_id,
            project_root=self.project_root,
        )

    def resume(self, mission_id: str) -> Project:
        """Resume a previously checkpointed mission."""
        return resume_project(mission_id, project_root=self.project_root)

    def status(self, mission_id: str) -> MissionReport:
        """Return a current, inspectable report without executing work."""
        project = Project.resume(mission_id, self.project_root)
        return self._report(mission_id, project)

    def report(self, mission_id: str) -> MissionReport:
        """Generate a stable report suitable for chat, Discord, or notifications."""
        return self.status(mission_id)

    @staticmethod
    def _report(mission_id: str, project: Project) -> MissionReport:
        return MissionReport(
            mission_id=mission_id,
            goal=project.goal,
            status=project.status,
            progress=project.progress(),
            completed=project.completed_tasks(),
            failed=project.failed_tasks(),
            total=len(project.tasks),
            generated_at=datetime.now(timezone.utc).isoformat(),
            tasks=tuple(
                {
                    "id": task.id,
                    "title": task.title,
                    "agent": task.agent,
                    "status": task.status,
                    "result": task.result,
                    "error": task.error,
                }
                for task in project.tasks
            ),
        )


mission = AutonomousMission()

__all__ = ["AutonomousMission", "MissionReport", "mission"]
