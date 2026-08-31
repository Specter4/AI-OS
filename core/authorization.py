"""Identity-aware authorization policy for AI-OS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.tool_registry import Permission


class IdentityLevel(str, Enum):
    OWNER = "owner"
    KNOWN = "known"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    requires_approval: bool = False
    reason: str = ""


class AuthorizationPolicy:
    """Conservative policy combining speaker/face identity with tool risk."""

    def decide(self, identity: IdentityLevel, permission: Permission) -> AuthorizationDecision:
        if identity is IdentityLevel.UNKNOWN:
            if permission is Permission.READ:
                return AuthorizationDecision(True, reason="Read action allowed for an unknown speaker.")
            return AuthorizationDecision(False, reason="Unknown speaker cannot authorize this action.")

        if identity is IdentityLevel.KNOWN:
            if permission is Permission.READ:
                return AuthorizationDecision(True, reason="Known person may use read-only capabilities.")
            return AuthorizationDecision(False, requires_approval=True, reason="This action requires owner approval.")

        # Owner may use normal capabilities, while elevated actions still pass
        # through an explicit approval gate rather than being silently trusted.
        if permission is Permission.READ:
            return AuthorizationDecision(True, reason="Owner read action allowed.")
        return AuthorizationDecision(False, requires_approval=True, reason="Owner approval is required for this elevated action.")


policy = AuthorizationPolicy()

__all__ = ["AuthorizationDecision", "AuthorizationPolicy", "IdentityLevel", "policy"]
