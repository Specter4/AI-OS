"""
Base Provider

Every AI provider implements this interface.
"""

from abc import ABC, abstractmethod


class BaseProvider(ABC):

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def capabilities(self):
        """
        Returns provider capabilities.
        """
        pass

    @abstractmethod
    def is_available(self):
        pass

    @abstractmethod
    def generate(self, messages):
        pass