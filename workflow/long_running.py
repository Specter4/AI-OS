"""Durable runtime primitives for long-running autonomous missions."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


MISSION_STATES = {"queued", "running", "paused", "completed", "failed", "cancelled"}
TERMINAL_STATES = {"completed", "failed", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MissionCheckpoint:
    sequence: int = 0
    state: str = "queued"
    progress: int = 0
    current_task: str | None = None
    completed_tasks: list[str] = field(default_factory=list)
    failed_tasks: list[str] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    updated_at: str = field(default_factory=_now)


@dataclass
class MissionRecord:
    mission_id: str
    goal: str
    state: str = "queued"
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    completed_at: str | None = None
    heartbeat_at: str | None = None
    checkpoint: MissionCheckpoint = field(default_factory=MissionCheckpoint)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def progress(self) -> int:
        return max(0, min(100, int(self.checkpoint.progress)))


class MissionStore:
    """Small atomic JSON store for mission lifecycle state."""

    def __init__(self, root: str | Path = "data/missions") -> None:
        self.root = Path(root)
        self._lock = threading.RLock()

    def _path(self, mission_id: str) -> Path:
        safe = "".join(c for c in mission_id if c.isalnum() or c in "-_ ").strip()
        if not safe:
            raise ValueError("mission_id cannot be empty")
        return self.root / f"{safe}.json"

    def save(self, record: MissionRecord) -> MissionRecord:
        if record.state not in MISSION_STATES:
            raise ValueError(f"Invalid mission state: {record.state}")
        record.checkpoint.updated_at = _now()
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            target = self._path(record.mission_id)
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps(asdict(record), indent=2, default=str), encoding="utf-8")
            temporary.replace(target)
        return record

    def load(self, mission_id: str) -> MissionRecord:
        with self._lock:
            path = self._path(mission_id)
            if not path.exists():
                raise FileNotFoundError(f"Mission not found: {mission_id}")
            raw = json.loads(path.read_text(encoding="utf-8"))
        checkpoint = MissionCheckpoint(**raw.pop("checkpoint", {}))
        return MissionRecord(checkpoint=checkpoint, **raw)

    def list(self, *, states: set[str] | None = None) -> list[MissionRecord]:
        with self._lock:
            if not self.root.exists():
                return []
            records = [self.load(path.stem) for path in self.root.glob("*.json")]
        if states is not None:
            records = [record for record in records if record.state in states]
        return sorted(records, key=lambda record: record.created_at)


class LongRunningMission:
    """Lifecycle controller that makes mission progress durable and resumable."""

    def __init__(self, mission_id: str, goal: str, *, store: MissionStore | None = None) -> None:
        if not mission_id.strip() or not goal.strip():
            raise ValueError("mission_id and goal cannot be empty")
        self.store = store or MissionStore()
        try:
            self.record = self.store.load(mission_id)
            if self.record.goal != goal:
                raise ValueError("Mission ID already belongs to a different goal")
        except FileNotFoundError:
            self.record = MissionRecord(mission_id=mission_id, goal=goal)
            self.store.save(self.record)

    def start(self) -> MissionRecord:
        if self.record.state in TERMINAL_STATES:
            raise RuntimeError("Terminal missions cannot be started")
        self.record.state = "running"
        self.record.started_at = self.record.started_at or _now()
        self.heartbeat()
        return self.checkpoint()

    def pause(self) -> MissionRecord:
        if self.record.state != "running":
            raise RuntimeError("Only running missions can be paused")
        self.record.state = "paused"
        return self.checkpoint()

    def resume(self) -> MissionRecord:
        if self.record.state not in {"paused", "failed", "queued"}:
            raise RuntimeError("Mission is not resumable")
        self.record.state = "running"
        self.record.checkpoint.error = None
        self.heartbeat()
        return self.checkpoint()

    def cancel(self) -> MissionRecord:
        if self.record.state in TERMINAL_STATES:
            return self.record
        self.record.state = "cancelled"
        self.record.completed_at = _now()
        return self.checkpoint()

    def heartbeat(self) -> MissionRecord:
        if self.record.state == "running":
            self.record.heartbeat_at = _now()
        return self.store.save(self.record)

    def checkpoint(
        self,
        *,
        progress: int | None = None,
        current_task: str | None = None,
        completed_tasks: list[str] | None = None,
        failed_tasks: list[str] | None = None,
        result: Any = None,
        error: str | None = None,
    ) -> MissionRecord:
        if progress is not None:
            self.record.checkpoint.progress = max(0, min(100, int(progress)))
        if current_task is not None:
            self.record.checkpoint.current_task = current_task
        if completed_tasks is not None:
            self.record.checkpoint.completed_tasks = list(completed_tasks)
        if failed_tasks is not None:
            self.record.checkpoint.failed_tasks = list(failed_tasks)
        if result is not None:
            self.record.checkpoint.result = result
        self.record.checkpoint.error = error
        self.record.checkpoint.sequence += 1
        self.record.checkpoint.state = self.record.state
        if self.record.state in TERMINAL_STATES:
            self.record.completed_at = self.record.completed_at or _now()
        return self.store.save(self.record)

    def complete(self, result: Any = None) -> MissionRecord:
        if self.record.state not in {"running", "paused"}:
            raise RuntimeError("Only active missions can complete")
        self.record.state = "completed"
        self.record.checkpoint.progress = 100
        return self.checkpoint(result=result, current_task=None)

    def fail(self, error: str) -> MissionRecord:
        if self.record.state in TERMINAL_STATES:
            return self.record
        self.record.state = "failed"
        return self.checkpoint(error=str(error))

    def run_step(self, step: Callable[[MissionCheckpoint], Any]) -> MissionRecord:
        """Execute one bounded slice of work, then checkpoint it.

        The callback receives the last durable checkpoint. A callback may return a
        dict containing progress/current_task/completed_tasks/failed_tasks/result.
        Exceptions become durable failed state rather than disappearing.
        """
        if self.record.state != "running":
            raise RuntimeError("Mission must be running to execute a step")
        self.heartbeat()
        try:
            value = step(self.record.checkpoint)
            updates = value if isinstance(value, dict) else {"result": value}
            return self.checkpoint(**{key: updates[key] for key in updates if key in {
                "progress", "current_task", "completed_tasks", "failed_tasks", "result", "error"
            }})
        except Exception as exc:
            return self.fail(str(exc))

    def is_stale(self, timeout_seconds: int = 300) -> bool:
        if self.record.state != "running" or not self.record.heartbeat_at:
            return False
        heartbeat = datetime.fromisoformat(self.record.heartbeat_at)
        return datetime.now(timezone.utc) - heartbeat > timedelta(seconds=max(1, timeout_seconds))


__all__ = ["LongRunningMission", "MissionCheckpoint", "MissionRecord", "MissionStore", "MISSION_STATES"]
