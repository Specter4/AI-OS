"""Structured registry of actions JARVIS may discover and execute."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Any


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    handler: Callable[..., Any] | None = None
    requires_approval: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def can_execute(self) -> bool:
        return self.handler is not None


class ActionRegistry:
    """Small, deterministic registry used by planning/execution layers."""

    def __init__(self) -> None:
        self._actions: dict[str, ActionSpec] = {}

    def register(self, action: ActionSpec) -> ActionSpec:
        key = action.name.strip().lower()
        if not key:
            raise ValueError("Action name cannot be empty")
        if key in self._actions:
            raise ValueError(f"Action already registered: {key}")
        self._actions[key] = action
        return action

    def get(self, name: str) -> ActionSpec | None:
        return self._actions.get(name.strip().lower())

    def require(self, name: str) -> ActionSpec:
        action = self.get(name)
        if action is None:
            raise KeyError(f"Unknown action: {name}")
        return action

    def list(self) -> tuple[ActionSpec, ...]:
        return tuple(self._actions.values())

    def names(self) -> tuple[str, ...]:
        return tuple(self._actions)

    def clear(self) -> None:
        self._actions.clear()


__all__ = ["ActionSpec", "ActionRegistry"]
