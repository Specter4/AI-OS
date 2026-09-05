"""Deterministic autonomous tool selection and execution for JARVIS."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from core.authorization import IdentityLevel
from workflow.action_executor import ActionExecutionEngine, ExecutionResult
from workflow.action_registry import ActionRegistry, ActionSpec
from workflow.capabilities import CapabilityRegistry
from workflow.execution_recovery import ExecutionRecovery, RecoveryResult


_STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from", "get", "has", "have", "i", "in", "into", "it", "me", "my", "of", "on", "or", "please", "the", "to", "use", "want", "with", "would"}


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if token not in _STOPWORDS}


@dataclass(frozen=True)
class ToolCandidate:
    action: str
    description: str
    score: float
    capability: str | None = None
    requires_approval: bool = False


@dataclass(frozen=True)
class ToolSelection:
    goal: str
    selected: ToolCandidate | None
    candidates: tuple[ToolCandidate, ...] = ()
    status: str = "selected"
    rationale: str = ""


@dataclass(frozen=True)
class AutonomousExecutionResult:
    selection: ToolSelection
    execution: ExecutionResult | RecoveryResult | None


class ToolSelector:
    """Select only registered executable actions using explainable scoring."""

    def __init__(self, actions: ActionRegistry, capabilities: CapabilityRegistry | None = None) -> None:
        self.actions = actions
        self.capabilities = capabilities

    def discover(self, goal: str, *, limit: int = 10) -> tuple[ToolCandidate, ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        query = _tokens(goal)
        if not query:
            return ()

        capability_by_action: dict[str, str] = {}
        if self.capabilities is not None:
            for capability in self.capabilities.list(enabled_only=True):
                for action in capability.actions:
                    capability_by_action.setdefault(action.strip().lower(), capability.name)

        candidates: list[ToolCandidate] = []
        for action in self.actions.list():
            if not action.can_execute():
                continue
            score = self._score(action, query, capability_by_action)
            if score <= 0:
                continue
            candidates.append(ToolCandidate(action.name, action.description, score, capability_by_action.get(action.name.lower()), action.requires_approval))

        candidates.sort(key=lambda item: (-item.score, item.action.lower()))
        return tuple(candidates[:limit])

    def select(self, goal: str) -> ToolSelection:
        candidates = self.discover(goal)
        if not candidates:
            return ToolSelection(goal, None, (), "no_match", "No executable registered action matched the goal.")
        selected = candidates[0]
        approval = " Approval will still be required." if selected.requires_approval else ""
        return ToolSelection(goal, selected, candidates, "selected", f"Selected '{selected.action}' as the highest-scoring registered action.{approval}")

    @staticmethod
    def _score(action: ActionSpec, query: set[str], capability_by_action: dict[str, str]) -> float:
        name_tokens = _tokens(action.name.replace(".", " ").replace("_", " "))
        description_tokens = _tokens(action.description)
        metadata_tokens = _tokens(" ".join(str(value) for value in action.metadata.values()))
        capability_tokens = _tokens(capability_by_action.get(action.name.lower(), ""))
        score = 5.0 * len(query & name_tokens)
        score += 2.0 * len(query & capability_tokens)
        score += 1.0 * len(query & description_tokens)
        score += 0.5 * len(query & metadata_tokens)
        if query == name_tokens:
            score += 10.0
        return score


class AutonomousToolExecutor:
    """Select a tool, then delegate execution to the existing safety gates."""

    def __init__(self, selector: ToolSelector, engine: ActionExecutionEngine, recovery: ExecutionRecovery | None = None) -> None:
        self.selector = selector
        self.engine = engine
        self.recovery = recovery

    def execute(self, goal: str, arguments: dict[str, Any] | None = None, *, identity: IdentityLevel = IdentityLevel.UNKNOWN, approval_request_id: str | None = None) -> AutonomousExecutionResult:
        selection = self.selector.select(goal)
        if selection.selected is None:
            return AutonomousExecutionResult(selection, None)
        action = selection.selected.action
        if self.recovery is not None:
            result = self.recovery.execute(action, arguments, identity=identity, goal=goal, approval_request_id=approval_request_id)
        else:
            result = self.engine.execute(action, arguments, identity=identity, goal=goal, approval_request_id=approval_request_id)
        return AutonomousExecutionResult(selection, result)


__all__ = ["AutonomousExecutionResult", "AutonomousToolExecutor", "ToolCandidate", "ToolSelection", "ToolSelector"]
