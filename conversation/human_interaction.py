"""Advanced human-interaction signals for natural JARVIS conversation.

This layer does not replace the LLM. It supplies deterministic conversational
signals so the model can handle corrections, references, urgency, and social
context without losing the active thread.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class InteractionSignals:
    """Deterministic signals extracted from the user's latest utterance."""

    is_correction: bool = False
    is_follow_up: bool = False
    is_urgent: bool = False
    refers_to_previous: bool = False
    correction_text: str | None = None


_CORRECTION_PREFIXES = (
    "no,",
    "no ",
    "actually,",
    "actually ",
    "wait,",
    "wait ",
    "i meant",
    "what i meant",
    "correction:",
)
_FOLLOW_UP_WORDS = {
    "also", "and", "then", "that", "this", "it", "them", "those", "instead",
    "what about", "how about", "why", "what if", "can you also",
}
_URGENT_WORDS = {"urgent", "urgently", "asap", "immediately", "emergency", "critical"}
_REFERENCE_RE = re.compile(r"\b(it|that|this|them|those|he|she|they|there|again)\b", re.I)


def analyze(message: str, *, has_previous_turn: bool = False) -> InteractionSignals:
    """Extract human conversational signals without guessing hidden intent."""
    text = " ".join(message.strip().split())
    lowered = text.lower()
    correction = any(lowered.startswith(prefix) for prefix in _CORRECTION_PREFIXES)
    correction_text = None
    if correction:
        for prefix in _CORRECTION_PREFIXES:
            if lowered.startswith(prefix):
                correction_text = text[len(prefix):].lstrip(" ,.!?:;") or None
                if correction_text and correction_text.lower().startswith("actually "):
                    correction_text = correction_text[len("actually "):].lstrip()
                break

    follow_up = has_previous_turn and (
        bool(_REFERENCE_RE.search(text))
        or correction
        or any(lowered.startswith(word + " ") or lowered == word for word in _FOLLOW_UP_WORDS)
    )
    urgent = any(word in lowered for word in _URGENT_WORDS)

    return InteractionSignals(
        is_correction=correction,
        is_follow_up=follow_up,
        is_urgent=urgent,
        refers_to_previous=has_previous_turn and bool(_REFERENCE_RE.search(text)),
        correction_text=correction_text,
    )


__all__ = ["InteractionSignals", "analyze"]
