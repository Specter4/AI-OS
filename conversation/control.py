"""Natural-language control interpretation for active JARVIS tasks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ControlIntent:
    action: str
    instruction: str | None = None


_STOP = ("stop", "wait", "cancel", "halt", "don't do that", "do not do that")
_RESUME = ("continue", "resume", "carry on", "keep going", "go on")
_REPLACE = ("actually", "instead", "change that", "change it", "do it this way")


def interpret_control(message: str, *, active: bool = False) -> ControlIntent:
    """Interpret human-style interruption/follow-up language deterministically."""
    text = " ".join(message.lower().strip().split())
    if not active:
        return ControlIntent("none")

    if any(text == phrase or text.startswith(phrase + " ") for phrase in _STOP):
        return ControlIntent("interrupt", message)

    if any(text == phrase or text.startswith(phrase + " ") for phrase in _RESUME):
        remainder = text
        for phrase in _RESUME:
            if remainder == phrase:
                return ControlIntent("resume")
            if remainder.startswith(phrase + " "):
                return ControlIntent("resume", message[len(phrase):].strip())

    if any(phrase in text for phrase in _REPLACE):
        return ControlIntent("replace", message)

    return ControlIntent("none")
