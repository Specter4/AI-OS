"""Human approval controller for autonomous AI-OS execution.

Approval decisions live outside the LLM. The controller creates explicit,
inspectable requests and supports approve/deny operations that a CLI, Discord
bot, API, or UI can expose later.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any
from uuid import uuid4

from core.tool_registry import Permission, ToolSpec


@dataclass(frozen=True)
class ApprovalRequest:
    id: str
    tool: str
    description: str
    permission: Permission
    arguments: dict[str, Any]
    goal: str | None = None
    task: str | None = None
    status: str = "pending"


class ApprovalController:
    """Thread-safe approval queue for elevated autonomous actions."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._lock = RLock()

    def create(
        self,
        spec: ToolSpec,
        arguments: dict[str, Any],
        *,
        goal: str | None = None,
        task: str | None = None,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            id=uuid4().hex,
            tool=spec.name,
            description=spec.description,
            permission=spec.permission,
            arguments=dict(arguments),
            goal=goal,
            task=task,
        )
        with self._lock:
            self._requests[request.id] = request
        return request

    def get(self, request_id: str) -> ApprovalRequest:
        with self._lock:
            try:
                return self._requests[request_id]
            except KeyError as exc:
                raise KeyError(f"Unknown approval request: {request_id}") from exc

    def pending(self) -> list[ApprovalRequest]:
        with self._lock:
            return [request for request in self._requests.values() if request.status == "pending"]

    def approve(self, request_id: str) -> ApprovalRequest:
        return self._resolve(request_id, "approved")

    def deny(self, request_id: str) -> ApprovalRequest:
        return self._resolve(request_id, "denied")

    def _resolve(self, request_id: str, status: str) -> ApprovalRequest:
        with self._lock:
            request = self.get(request_id)
            if request.status != "pending":
                raise ValueError(f"Approval request already resolved: {request_id}")
            resolved = ApprovalRequest(
                id=request.id,
                tool=request.tool,
                description=request.description,
                permission=request.permission,
                arguments=request.arguments,
                goal=request.goal,
                task=request.task,
                status=status,
            )
            self._requests[request_id] = resolved
            return resolved


approval_controller = ApprovalController()
