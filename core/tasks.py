"""
Task System

Represents executable tasks inside AI-OS.
"""

from dataclasses import dataclass, field


@dataclass
class Task:

    id: int

    title: str

    agent: str

    priority: int = 1

    status: str = "pending"

    result: str | None = None

    metadata: dict = field(
        default_factory=dict
    )

    # Task IDs that must complete before this task can run.
    depends_on: list[int] = field(
        default_factory=list
    )