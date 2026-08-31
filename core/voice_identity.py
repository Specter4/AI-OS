"""Voice identity abstraction for AI-OS.

This layer deliberately separates speaker identification from audio recognition
providers. A future microphone/model adapter can submit a speaker embedding or
provider identity here without changing authorization or people memory.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceIdentity:
    """A recognized speaker identity and confidence supplied by a provider."""

    person_id: str | None
    confidence: float
    provider: str = "unknown"

    @property
    def recognized(self) -> bool:
        return self.person_id is not None and 0.0 <= self.confidence <= 1.0

    @property
    def trusted(self) -> bool:
        """Conservative threshold for identity-sensitive decisions."""
        return self.recognized and self.confidence >= 0.85


class VoiceIdentityService:
    """Provider-neutral voice identity service.

    The service does not guess a speaker from text. Callers must provide a
    recognition result from an actual audio/speaker-verification provider.
    """

    def __init__(self, *, threshold: float = 0.85):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self.threshold = threshold

    def identify(self, person_id: str | None, confidence: float, *, provider: str = "unknown") -> VoiceIdentity:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        identity = VoiceIdentity(person_id=person_id, confidence=confidence, provider=provider)
        return identity

    def is_owner(self, identity: VoiceIdentity, owner_id: str) -> bool:
        return identity.person_id == owner_id and identity.confidence >= self.threshold


__all__ = ["VoiceIdentity", "VoiceIdentityService"]
