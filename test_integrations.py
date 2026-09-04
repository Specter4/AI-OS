from __future__ import annotations

import pytest

from core.authorization import IdentityLevel
from core.tool_registry import Permission
from workflow.action_executor import ActionExecutionEngine
from workflow.action_registry import ActionRegistry
from workflow.integrations import (
    ExternalService,
    IntegrationActionBinder,
    IntegrationRegistry,
    SMTPEmailAdapter,
    ServiceSpec,
    WebhookAdapter,
)


class FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, action: str, arguments: dict):
        self.calls.append((action, dict(arguments)))
        return {"ok": True, "action": action, "arguments": dict(arguments)}


def make_service(name="calendar", adapter=None):
    return ExternalService(
        ServiceSpec(name, "Calendar service", "productivity", credential_env=("CALENDAR_TOKEN",)),
        adapter or FakeAdapter(),
    )


def test_registry_is_case_insensitive_and_discovers_enabled_services():
    registry = IntegrationRegistry()
    registry.register(make_service())
    assert registry.get("CALENDAR") is not None
    assert registry.discover("productivity")[0].spec.name == "calendar"


def test_registry_rejects_duplicate_services():
    registry = IntegrationRegistry()
    registry.register(make_service())
    with pytest.raises(ValueError):
        registry.register(make_service())


def test_disabled_service_cannot_execute():
    service = ExternalService(ServiceSpec("x", "X", "test", enabled=False), FakeAdapter())
    with pytest.raises(RuntimeError, match="disabled"):
        service.execute("run")


def test_binder_namespaces_external_action_and_defaults_to_approval():
    services = IntegrationRegistry()
    actions = ActionRegistry()
    adapter = FakeAdapter()
    services.register(make_service(adapter=adapter))
    spec = IntegrationActionBinder(services, actions).bind("calendar", "create", "Create calendar event")
    assert spec.name == "calendar.create"
    assert spec.requires_approval is True
    assert spec.metadata["permission"] == Permission.EXTERNAL.value
    assert spec.metadata["service"] == "calendar"


def test_bound_external_action_executes_only_after_owner_approval():
    services = IntegrationRegistry()
    actions = ActionRegistry()
    adapter = FakeAdapter()
    services.register(make_service(adapter=adapter))
    IntegrationActionBinder(services, actions).bind("calendar", "create", "Create calendar event")
    engine = ActionExecutionEngine(actions)

    pending = engine.execute("calendar.create", {"title": "Exam"}, identity=IdentityLevel.OWNER)
    assert pending.status == "awaiting_approval"
    assert adapter.calls == []

    approved = engine.approvals.approve(pending.approval_request_id)
    assert approved.status == "approved"
    completed = engine.execute(
        "calendar.create", {"title": "Exam"}, identity=IdentityLevel.OWNER,
        approval_request_id=pending.approval_request_id,
    )
    assert completed.success is True
    assert adapter.calls == [("create", {"title": "Exam"})]


def test_unknown_speaker_cannot_execute_external_action():
    services = IntegrationRegistry()
    actions = ActionRegistry()
    services.register(make_service())
    IntegrationActionBinder(services, actions).bind("calendar", "create", "Create calendar event")
    result = ActionExecutionEngine(actions).execute("calendar.create", {"title": "Exam"})
    assert result.status == "denied"


def test_webhook_rejects_local_or_invalid_endpoints():
    with pytest.raises(ValueError):
        WebhookAdapter("file:///tmp/test")
    with pytest.raises(ValueError):
        WebhookAdapter("http://127.0.0.1/hook")
    with pytest.raises(ValueError):
        WebhookAdapter("http://localhost/hook")


def test_webhook_requires_token_when_configured(monkeypatch):
    adapter = WebhookAdapter("https://example.com/hook", token_env="JARVIS_TEST_TOKEN")
    monkeypatch.delenv("JARVIS_TEST_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="JARVIS_TEST_TOKEN"):
        adapter.execute("send", {"message": "hello"})


def test_webhook_uses_configured_token(monkeypatch):
    adapter = WebhookAdapter("https://example.com/hook", token_env="JARVIS_TEST_TOKEN")
    monkeypatch.setenv("JARVIS_TEST_TOKEN", "secret")
    captured = {}

    class Response:
        status = 200
        def read(self):
            return b'{"ok":true}'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("workflow.integrations.urlopen", fake_urlopen)
    result = adapter.execute("send", {"message": "hello"})
    assert result["status_code"] == 200
    assert captured == {"url": "https://example.com/hook", "auth": "Bearer secret", "timeout": 15.0}


def test_smtp_validates_arguments_and_uses_environment(monkeypatch):
    adapter = SMTPEmailAdapter()
    monkeypatch.setenv("JARVIS_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("JARVIS_SMTP_USER", "jarvis@example.com")
    monkeypatch.setenv("JARVIS_SMTP_PASSWORD", "secret")
    captured = {}

    class Server:
        def __init__(self, host, port, timeout):
            captured["connection"] = (host, port, timeout)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def starttls(self, context):
            captured["tls"] = True
        def login(self, user, password):
            captured["login"] = (user, password)
        def sendmail(self, sender, recipients, message):
            captured["mail"] = (sender, recipients, message)

    monkeypatch.setattr("workflow.integrations.smtplib.SMTP", Server)
    result = adapter.execute("send_email", {"to": "asif@example.com", "subject": "Hi", "body": "Hello"})
    assert result["sent"] is True
    assert captured["connection"] == ("smtp.example.com", 587, 20)
    assert captured["login"] == ("jarvis@example.com", "secret")
    assert captured["mail"][0] == "jarvis@example.com"
    assert captured["mail"][1] == ["asif@example.com"]


def test_smtp_rejects_missing_required_arguments():
    with pytest.raises(ValueError, match="Missing email arguments"):
        SMTPEmailAdapter().execute("send_email", {"to": "asif@example.com"})
