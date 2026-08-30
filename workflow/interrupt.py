"""Cooperative interruption primitives for interactive AI-OS execution."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, RLock


@dataclass(frozen=True)
class Interruption:
    """A user interruption request for a running task."""

    reason: str = "Interrupted by the user."
    instruction: str | None = None


class InterruptController:
    """Thread-safe cooperative interruption signal."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = RLock()
        self._request: Interruption | None = None

    def request(self, reason: str = "Interrupted by the user.", instruction: str | None = None) -> Interruption:
        request = Interruption(reason=reason.strip() or "Interrupted by the user.", instruction=instruction.strip() if instruction else None)
        with self._lock:
            self._request = request
            self._event.set()
        return request

    def is_requested(self) -> bool:
        return self._event.is_set()

    def get(self) -> Interruption | None:
        with self._lock:
            return self._request

    def clear(self) -> None:
        with self._lock:
            self._request = None
            self._event.clear()


__all__ = ["InterruptController", "Interruption"]
