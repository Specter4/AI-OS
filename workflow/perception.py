"""Provider-neutral perception and environment awareness for JARVIS.

Perception providers (camera, microphone, screen capture, sensors) submit
observations here. This layer normalizes observations, tracks the latest
snapshot, detects meaningful changes, and never invents observations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Iterable, Mapping, Protocol


@dataclass(frozen=True)
class Observation:
    source: str
    kind: str
    value: Any
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("Observation source cannot be empty")
        if not self.kind.strip():
            raise ValueError("Observation kind cannot be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Observation confidence must be between 0 and 1")
        if self.timestamp.tzinfo is None:
            raise ValueError("Observation timestamp must be timezone-aware")


@dataclass(frozen=True)
class EnvironmentSnapshot:
    observations: tuple[Observation, ...]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def latest(self, kind: str) -> Observation | None:
        key = kind.strip().lower()
        matches = [item for item in self.observations if item.kind.casefold() == key]
        return max(matches, key=lambda item: item.timestamp, default=None)

    def by_source(self, source: str) -> tuple[Observation, ...]:
        key = source.strip().casefold()
        return tuple(item for item in self.observations if item.source.casefold() == key)


class PerceptionProvider(Protocol):
    def observe(self) -> Iterable[Observation]: ...


class EnvironmentAwareness:
    """Thread-safe observation store with explicit change detection."""

    def __init__(self, *, history_limit: int = 500) -> None:
        if history_limit < 1:
            raise ValueError("history_limit must be positive")
        self.history_limit = history_limit
        self._history: list[Observation] = []
        self._lock = RLock()

    def ingest(self, observations: Iterable[Observation]) -> EnvironmentSnapshot:
        items = tuple(observations)
        with self._lock:
            self._history.extend(items)
            self._history.sort(key=lambda item: item.timestamp)
            if len(self._history) > self.history_limit:
                self._history = self._history[-self.history_limit :]
            return EnvironmentSnapshot(tuple(self._history))

    def observe(self, provider: PerceptionProvider) -> EnvironmentSnapshot:
        return self.ingest(provider.observe())

    def snapshot(self) -> EnvironmentSnapshot:
        with self._lock:
            return EnvironmentSnapshot(tuple(self._history))

    def latest(self, kind: str) -> Observation | None:
        return self.snapshot().latest(kind)

    def changed_since(self, timestamp: datetime, *, kind: str | None = None) -> tuple[Observation, ...]:
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        with self._lock:
            return tuple(
                item for item in self._history
                if item.timestamp > timestamp
                and (kind is None or item.kind.casefold() == kind.strip().casefold())
            )

    def clear(self) -> None:
        with self._lock:
            self._history.clear()


environment = EnvironmentAwareness()

__all__ = [
    "EnvironmentAwareness",
    "EnvironmentSnapshot",
    "Observation",
    "PerceptionProvider",
    "environment",
]
