"""External service integration primitives for JARVIS.

Integrations expose typed, namespaced actions to the existing action registry.
Credentials are resolved from environment variables at execution time and are
never stored in action metadata or source control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import os
import smtplib
import ssl
from threading import RLock
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json

from core.tool_registry import Permission
from workflow.action_registry import ActionRegistry, ActionSpec


class IntegrationAdapter(Protocol):
    def execute(self, action: str, arguments: Mapping[str, Any]) -> Any: ...


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    description: str
    category: str
    credential_env: tuple[str, ...] = ()
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ExternalService:
    """A configured external service with a deterministic action surface."""

    def __init__(self, spec: ServiceSpec, adapter: IntegrationAdapter) -> None:
        if not spec.name.strip():
            raise ValueError("Service name cannot be empty")
        self.spec = spec
        self.adapter = adapter

    def execute(self, action: str, arguments: Mapping[str, Any] | None = None) -> Any:
        if not self.spec.enabled:
            raise RuntimeError(f"Service is disabled: {self.spec.name}")
        return self.adapter.execute(action, dict(arguments or {}))


class IntegrationRegistry:
    """Thread-safe registry for configured external services."""

    def __init__(self) -> None:
        self._services: dict[str, ExternalService] = {}
        self._lock = RLock()

    def register(self, service: ExternalService) -> ExternalService:
        key = service.spec.name.strip().lower()
        with self._lock:
            if key in self._services:
                raise ValueError(f"Service already registered: {key}")
            self._services[key] = service
        return service

    def get(self, name: str) -> ExternalService | None:
        with self._lock:
            return self._services.get(name.strip().lower())

    def require(self, name: str) -> ExternalService:
        service = self.get(name)
        if service is None:
            raise KeyError(f"Unknown service: {name}")
        return service

    def list(self, *, enabled_only: bool = False, category: str | None = None) -> tuple[ExternalService, ...]:
        with self._lock:
            services = tuple(self._services.values())
        if enabled_only:
            services = tuple(item for item in services if item.spec.enabled)
        if category is not None:
            key = category.strip().lower()
            services = tuple(item for item in services if item.spec.category.lower() == key)
        return services

    def discover(self, query: str = "") -> tuple[ExternalService, ...]:
        text = query.strip().lower()
        return tuple(
            item for item in self.list(enabled_only=True)
            if not text or text in " ".join((item.spec.name, item.spec.description, item.spec.category)).lower()
        )

    def clear(self) -> None:
        with self._lock:
            self._services.clear()


class IntegrationActionBinder:
    """Expose service actions through the existing approval-aware executor."""

    def __init__(self, services: IntegrationRegistry, actions: ActionRegistry) -> None:
        self.services = services
        self.actions = actions

    def bind(
        self,
        service_name: str,
        action_name: str,
        description: str,
        *,
        permission: Permission = Permission.EXTERNAL,
        requires_approval: bool = True,
    ) -> ActionSpec:
        service = self.services.require(service_name)
        if not action_name.strip():
            raise ValueError("Action name cannot be empty")
        namespaced = f"{service.spec.name}.{action_name.strip()}"

        def handler(**arguments: Any) -> Any:
            return service.execute(action_name, arguments)

        return self.actions.register(
            ActionSpec(
                namespaced,
                description.strip(),
                handler=handler,
                requires_approval=requires_approval,
                metadata={
                    "permission": permission.value,
                    "service": service.spec.name,
                    "service_action": action_name.strip(),
                },
            )
        )


def _validate_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP(S) URLs with a hostname are supported")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"}:
        raise ValueError("Localhost URLs are not allowed for external integrations")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        raise ValueError("Private or local network URLs are not allowed for external integrations")


class WebhookAdapter:
    """Small dependency-free JSON webhook client."""

    def __init__(self, endpoint: str, *, token_env: str | None = None, timeout: float = 15.0) -> None:
        _validate_public_http_url(endpoint)
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        self.endpoint = endpoint
        self.token_env = token_env
        self.timeout = timeout

    def execute(self, action: str, arguments: Mapping[str, Any]) -> Any:
        if action.lower() not in {"send", "post"}:
            raise KeyError(f"Unknown webhook action: {action}")
        payload = json.dumps(dict(arguments)).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token_env:
            token = os.getenv(self.token_env)
            if not token:
                raise RuntimeError(f"Missing integration credential: {self.token_env}")
            headers["Authorization"] = f"Bearer {token}"
        request = Request(self.endpoint, data=payload, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return {"status_code": response.status, "body": body}
        except HTTPError as exc:
            raise RuntimeError(f"Webhook request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Webhook request failed: {exc.reason}") from exc


class SMTPEmailAdapter:
    """SMTP email adapter using credentials supplied through environment variables."""

    def __init__(self, host_env: str = "JARVIS_SMTP_HOST", port_env: str = "JARVIS_SMTP_PORT", user_env: str = "JARVIS_SMTP_USER", password_env: str = "JARVIS_SMTP_PASSWORD", *, use_tls: bool = True) -> None:
        self.host_env = host_env
        self.port_env = port_env
        self.user_env = user_env
        self.password_env = password_env
        self.use_tls = use_tls

    def execute(self, action: str, arguments: Mapping[str, Any]) -> Any:
        if action.lower() != "send_email":
            raise KeyError(f"Unknown email action: {action}")
        required = ("to", "subject", "body")
        missing = [key for key in required if not arguments.get(key)]
        if missing:
            raise ValueError(f"Missing email arguments: {', '.join(missing)}")
        host = os.getenv(self.host_env)
        if not host:
            raise RuntimeError(f"Missing integration credential: {self.host_env}")
        port = int(os.getenv(self.port_env, "587"))
        user = os.getenv(self.user_env)
        password = os.getenv(self.password_env)
        sender = str(arguments.get("from") or user or "")
        if not sender:
            raise RuntimeError(f"Missing integration credential: {self.user_env}")
        recipients = arguments["to"] if isinstance(arguments["to"], list) else [arguments["to"]]
        message = f"From: {sender}\nTo: {', '.join(map(str, recipients))}\nSubject: {arguments['subject']}\n\n{arguments['body']}"
        if self.use_tls:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls(context=ssl.create_default_context())
                if user and password:
                    server.login(user, password)
                server.sendmail(sender, list(map(str, recipients)), message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                if user and password:
                    server.login(user, password)
                server.sendmail(sender, list(map(str, recipients)), message)
        return {"sent": True, "to": list(map(str, recipients)), "subject": str(arguments["subject"])}


integration_registry = IntegrationRegistry()

__all__ = [
    "ExternalService",
    "IntegrationActionBinder",
    "IntegrationAdapter",
    "IntegrationRegistry",
    "ServiceSpec",
    "SMTPEmailAdapter",
    "WebhookAdapter",
    "integration_registry",
]
