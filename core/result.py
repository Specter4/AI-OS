"""
Agent Result

Standard result returned by every agent.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentResult:

    success: bool

    agent: str

    output: str

    provider: Optional[str] = None

    duration: Optional[float] = None

    error: Optional[str] = None