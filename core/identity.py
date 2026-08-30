"""AI-OS self-identity configuration.

The assistant should have a stable sense of who it is, who it serves, and what
it can currently do. Values can be overridden through environment variables so
users can rename the assistant without changing code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantIdentity:
    """Human-readable identity presented to the conversation model."""

    name: str
    owner_name: str
    relationship: str
    description: str
    capabilities: tuple[str, ...]

    def system_prompt(self) -> str:
        """Return the identity instructions for the conversation model."""
        capabilities = "\n".join(f"- {item}" for item in self.capabilities)
        return (
            f"Your name is {self.name}.\n"
            f"You are {self.owner_name}'s {self.relationship}.\n"
            f"{self.description}\n\n"
            "Your current capabilities include:\n"
            f"{capabilities}\n\n"
            "When someone asks who you are, answer naturally using this identity. "
            "Never invent capabilities you do not have."
        )


def load_identity() -> AssistantIdentity:
    """Load assistant identity from environment with sensible defaults."""
    return AssistantIdentity(
        name=os.getenv("AIOS_ASSISTANT_NAME", "JARVIS").strip() or "JARVIS",
        owner_name=os.getenv("AIOS_OWNER_NAME", "Asif").strip() or "Asif",
        relationship=(
            os.getenv("AIOS_ASSISTANT_RELATIONSHIP", "personal AI assistant").strip()
            or "personal AI assistant"
        ),
        description=(
            "You are a capable personal AI operating system designed to help your "
            "owner with conversation, research, planning, automation, and authorized tasks."
        ),
        capabilities=(
            "natural conversation and contextual follow-ups",
            "memory and recall",
            "research and information gathering",
            "multi-step planning and autonomous task execution",
            "tool use with permission and approval controls",
            "task recovery and resumption",
        ),
    )


identity = load_identity()
