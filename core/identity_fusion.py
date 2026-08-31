"""Identity fusion and unknown-person onboarding for AI-OS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.authorization import IdentityLevel


@dataclass(frozen=True)
class IdentityEvidence:
    """Independent evidence supplied by voice, face, or an explicit identity."""

    source: str
    person_id: str | None
    confidence: float


@dataclass(frozen=True)
class FusedIdentity:
    """Resolved identity used by the conversation and authorization layers."""

    person_id: str | None
    level: IdentityLevel
    confidence: float
    sources: tuple[str, ...] = ()
    needs_identification: bool = False


class IdentityFusion:
    """Conservatively combine independent identity evidence.

    Conflicting evidence never silently selects one person. A conflict becomes
    unknown and requires clarification instead of granting authority.
    """

    def __init__(self, *, threshold: float = 0.85):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self.threshold = threshold

    def resolve(
        self,
        evidence: Iterable[IdentityEvidence],
        *,
        known_person_ids: set[str] | None = None,
        owner_id: str | None = None,
    ) -> FusedIdentity:
        items = tuple(evidence)
        trusted = tuple(
            item for item in items
            if item.person_id and 0.0 <= item.confidence <= 1.0 and item.confidence >= self.threshold
        )
        person_ids = {item.person_id for item in trusted}

        if len(person_ids) != 1:
            return FusedIdentity(
                person_id=None,
                level=IdentityLevel.UNKNOWN,
                confidence=max((item.confidence for item in trusted), default=0.0),
                sources=tuple(item.source for item in items),
                needs_identification=True,
            )

        person_id = next(iter(person_ids))
        if owner_id and person_id == owner_id:
            level = IdentityLevel.OWNER
        elif known_person_ids and person_id in known_person_ids:
            level = IdentityLevel.KNOWN
        else:
            level = IdentityLevel.UNKNOWN

        confidence = max(item.confidence for item in trusted if item.person_id == person_id)
        return FusedIdentity(
            person_id=person_id,
            level=level,
            confidence=confidence,
            sources=tuple(item.source for item in items if item.person_id == person_id),
            needs_identification=level is IdentityLevel.UNKNOWN,
        )


fusion = IdentityFusion()

__all__ = ["IdentityEvidence", "FusedIdentity", "IdentityFusion", "fusion"]
