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


def _starts_with_control(text: str, phrase: str) -> bool:
    """Match control phrases even when natural punctuation follows them."""
    return text == phrase or text.startswith(phrase + " ") or text.startswith(phrase + ",") or text.startswith(phrase + ".") or text.startswith(phrase + "!")


def interpret_control(message: str, *, active: bool = False) -> ControlIntent:
    """Interpret human-style interruption/follow-up language deterministically."""
    original = message.strip()
    text = " ".join(original.lower().split())
    if not active:
        return ControlIntent("none")

    if any(_starts_with_control(text, phrase) for phrase in _STOP):
        return ControlIntent("interrupt", original)

    for phrase in _RESUME:
        if _starts_with_control(text, phrase):
            remainder = original[len(phrase):].lstrip(" ,.!?:;")
            return ControlIntent("resume", remainder or None)

    if any(phrase in text for phrase in _REPLACE):
        return ControlIntent("replace", original)

    return ControlIntent("none")
