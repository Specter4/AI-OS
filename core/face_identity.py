"""Provider-neutral facial identity layer for AI-OS.

Camera/frame acquisition and face-recognition models remain adapters outside this
module. This layer turns a verified recognition result into the same identity
primitive used by authorization and the people registry.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FaceIdentity:
    person_id: str | None
    confidence: float
    provider: str = "unknown"

    @property
    def recognized(self) -> bool:
        return self.person_id is not None and 0.0 <= self.confidence <= 1.0

    @property
    def trusted(self) -> bool:
        return self.recognized and self.confidence >= 0.85


class FaceIdentityService:
    """Normalize face-recognition results without guessing unknown identities."""

    def __init__(self, *, threshold: float = 0.85):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self.threshold = threshold

    def identify(
        self,
        person_id: str | None,
        confidence: float,
        *,
        provider: str = "unknown",
    ) -> FaceIdentity:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return FaceIdentity(person_id=person_id, confidence=confidence, provider=provider)

    def is_owner(self, identity: FaceIdentity, owner_id: str) -> bool:
        return identity.person_id == owner_id and identity.confidence >= self.threshold


__all__ = ["FaceIdentity", "FaceIdentityService"]
