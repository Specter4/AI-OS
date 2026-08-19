"""
Provider Manager

Handles all AI providers and selects the best one.
"""

from core.config import DEFAULT_PROVIDER
from core.logger import log

from providers.ollama_provider import OllamaProvider
from providers.nvidia_provider import NvidiaProvider


class ProviderManager:

    def __init__(self):

        self.providers = {}

        # Register all providers here
        self.register(OllamaProvider())
        self.register(NvidiaProvider())
    def register(self, provider):
        """
        Register a provider with the manager.
        """

        self.providers[provider.name] = provider

        log(f"Registered provider: {provider.name}")

    def get_provider(self):
        """
        Returns the best available provider.
        """

        available = []

        # Check which providers are available
        for provider in self.providers.values():

            if provider.is_available():
                available.append(provider)

        if not available:
            raise RuntimeError("No AI providers are available.")

        # If a specific provider is requested
        if DEFAULT_PROVIDER != "auto":

            for provider in available:

                if provider.name == DEFAULT_PROVIDER:

                    log(f"Using provider: {provider.name}")

                    return provider

        # Otherwise choose the provider with the highest priority
        available.sort(
            key=lambda p: p.capabilities["priority"]
        )

        selected = available[0]

        log(f"Automatically selected provider: {selected.name}")

        return selected

    def generate(self, messages):
        """
        Generate a response using the selected provider.
        """

        provider = self.get_provider()

        return provider.generate(messages)


# Global provider instance
provider = ProviderManager()