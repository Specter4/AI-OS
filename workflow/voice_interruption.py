"""Natural-language interruption commands for live voice interaction.

This parser is intentionally deterministic: it recognizes concise stop/pause
requests and replacement instructions without asking an LLM to interpret an
urgent interruption.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceInterruptionIntent:
    action: str
    instruction: str | None = None
    matched_phrase: str | None = None


_STOP_PHRASES = (
    "stop talking",
    "stop speaking",
    "be quiet",
    "quiet",
    "silence",
    "stop",
    "cancel",
    "wait",
    "hold on",
    "pause",
)
_RESUME_PHRASES = ("resume", "continue", "keep talking", "go on", "carry on")
_REPLACE_PREFIXES = (
    "actually",
    "instead",
    "no,",
    "no ",
    "change that",
    "change it",
    "do this instead",
)


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split()).rstrip(".!?,")


def interpret_voice_interruption(text: str) -> VoiceInterruptionIntent:
    """Classify a recognized utterance as interrupt, resume, replace, or none."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    original = text.strip()
    normalized = _normalize(original)
    if not normalized:
        return VoiceInterruptionIntent("none")

    for phrase in _STOP_PHRASES:
        if normalized == phrase or normalized.startswith(phrase + " "):
            remainder = original[len(phrase):].lstrip(" ,.!?:;")
            return VoiceInterruptionIntent("interrupt", remainder or None, phrase)

    for phrase in _RESUME_PHRASES:
        if normalized == phrase or normalized.startswith(phrase + " "):
            remainder = original[len(phrase):].lstrip(" ,.!?:;")
            return VoiceInterruptionIntent("resume", remainder or None, phrase)

    for phrase in _REPLACE_PREFIXES:
        if normalized.startswith(phrase):
            return VoiceInterruptionIntent("replace", original, phrase)

    return VoiceInterruptionIntent("none")


__all__ = ["VoiceInterruptionIntent", "interpret_voice_interruption"]
