"""Capability discovery primitives for JARVIS tool expansion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class CapabilitySpec:
    """Describes a capability without coupling discovery to its implementation."""

    name: str
    description: str
    category: str
    actions: tuple[str, ...] = ()
    requires_approval: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def matches(self, query: str) -> bool:
        text = query.strip().lower()
        if not text:
            return True
        haystack = " ".join((self.name, self.description, self.category, *self.actions)).lower()
        return text in haystack


class CapabilityRegistry:
    """Deterministic catalog JARVIS can inspect before selecting a tool."""

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilitySpec] = {}

    def register(self, capability: CapabilitySpec) -> CapabilitySpec:
        key = capability.name.strip().lower()
        if not key:
            raise ValueError("Capability name cannot be empty")
        if key in self._capabilities:
            raise ValueError(f"Capability already registered: {key}")
        self._capabilities[key] = capability
        return capability

    def get(self, name: str) -> CapabilitySpec | None:
        return self._capabilities.get(name.strip().lower())

    def require(self, name: str) -> CapabilitySpec:
        capability = self.get(name)
        if capability is None:
            raise KeyError(f"Unknown capability: {name}")
        return capability

    def list(self, *, enabled_only: bool = False, category: str | None = None) -> tuple[CapabilitySpec, ...]:
        capabilities = tuple(self._capabilities.values())
        if enabled_only:
            capabilities = tuple(item for item in capabilities if item.enabled)
        if category is not None:
            key = category.strip().lower()
            capabilities = tuple(item for item in capabilities if item.category.lower() == key)
        return capabilities

    def discover(self, query: str = "", *, category: str | None = None) -> tuple[CapabilitySpec, ...]:
        return tuple(
            item
            for item in self.list(enabled_only=True, category=category)
            if item.matches(query)
        )

    def names(self) -> tuple[str, ...]:
        return tuple(self._capabilities)

    def clear(self) -> None:
        self._capabilities.clear()


__all__ = ["CapabilitySpec", "CapabilityRegistry"]
