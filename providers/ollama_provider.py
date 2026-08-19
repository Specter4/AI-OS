"""
Ollama Provider
"""

import ollama

from providers.base import BaseProvider
from core.config import DEFAULT_MODEL


class OllamaProvider(BaseProvider):

    @property
    def name(self):
        return "ollama"

    @property
    def capabilities(self):

        return {
            "chat": True,
            "coding": True,
            "reasoning": 6,
            "vision": False,
            "tools": True,
            "cost": "free",
            "speed": 9,
            "priority": 1,
        }

    def is_available(self):

        try:
            ollama.list()
            return True

        except Exception:
            return False

    def generate(self, messages):

        response = ollama.chat(
            model=DEFAULT_MODEL,
            messages=messages
        )

        return response["message"]["content"]