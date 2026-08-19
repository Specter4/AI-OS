"""
Provider Selector

Chooses the best provider
for a given task.
"""

from providers.manager import provider

from core.logger import log


class ProviderSelector:

    def choose(self, task):

        text = task.title.lower()

        # ------------------------
        # Coding
        # ------------------------

        if any(word in text for word in [

            "frontend",
            "backend",
            "code",
            "program",
            "develop"

        ]):

            log("Selecting Coding Provider")

            return provider.get_provider()

        # ------------------------
        # Research
        # ------------------------

        if "research" in text:

            log("Selecting Research Provider")

            return provider.get_provider()

        # ------------------------
        # Design
        # ------------------------

        if any(word in text for word in [

            "design",
            "ui",
            "ux"

        ]):

            log("Selecting Design Provider")

            return provider.get_provider()

        # Default

        return provider.get_provider()


selector = ProviderSelector()