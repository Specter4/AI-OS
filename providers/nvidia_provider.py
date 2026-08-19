"""
NVIDIA Provider

Cloud AI provider for AI-OS.
"""

from providers.base import BaseProvider
from core.config import NVIDIA_API_KEY


class NvidiaProvider(BaseProvider):

    @property
    def name(self):
        return "nvidia"

    @property
    def capabilities(self):

        return {
            "chat": True,
            "coding": True,
            "reasoning": 9,
            "vision": True,
            "tools": True,
            "cost": "free-tier",
            "speed": 8,
            "priority": 2,
        }

    def is_available(self):

        return bool(NVIDIA_API_KEY)

    def generate(self, messages):

        raise NotImplementedError(
            "NVIDIA provider has not been connected yet."
        )