"""Primary-owner identity and authorization policy for AI-OS."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OwnerIdentity:
    """Stable owner identity used by higher-level authentication adapters."""

    name: str
    owner_id: str
    role: str = "owner"

    def matches(self, identity: str | None) -> bool:
        """Return whether a supplied identity matches the configured owner id."""
        if not identity:
            return False
        return identity.strip().casefold() == self.owner_id.casefold()

    def authorization_context(self) -> dict[str, str]:
        return {"owner_name": self.name, "owner_id": self.owner_id, "role": self.role}


def load_owner() -> OwnerIdentity:
    """Load the primary owner from configuration.

    The default owner name is Asif to match the existing assistant identity. The
    owner_id is intentionally configurable so a future voice/face authenticator
    can bind a stable biometric identity without changing authorization logic.
    """
    name = os.getenv("AIOS_OWNER_NAME", "Asif").strip() or "Asif"
    owner_id = os.getenv("AIOS_OWNER_ID", "owner:asif").strip() or "owner:asif"
    return OwnerIdentity(name=name, owner_id=owner_id)


owner = load_owner()

__all__ = ["OwnerIdentity", "load_owner", "owner"]
