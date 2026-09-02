from core.authorization import IdentityLevel
from core.tool_registry import Permission
from workflow.action_executor import ActionExecutionEngine
from workflow.action_registry import ActionRegistry, ActionSpec
from workflow.approval import ApprovalController


def make_engine(handler, *, approval=False, permission=Permission.READ):
    registry = ActionRegistry()
    registry.register(
        ActionSpec(
            name="test_action",
            description="A test action",
            handler=handler,
            requires_approval=approval,
            metadata={"permission": permission},
        )
    )
    return ActionExecutionEngine(registry, approvals=ApprovalController())


def test_read_action_executes_for_unknown_speaker():
    engine = make_engine(lambda value: value * 2)
    result = engine.execute("test_action", {"value": 3}, identity=IdentityLevel.UNKNOWN)
    assert result.success is True
    assert result.status == "completed"
    assert result.output == 6


def test_elevated_action_creates_approval_request():
    engine = make_engine(lambda: "done", permission=Permission.WRITE)
    result = engine.execute("test_action", identity=IdentityLevel.OWNER)
    assert result.success is False
    assert result.status == "awaiting_approval"
    assert result.approval_request_id


def test_approved_elevated_action_executes():
    calls = []
    engine = make_engine(lambda value: calls.append(value) or "done", permission=Permission.WRITE)
    pending = engine.execute("test_action", {"value": "ok"}, identity=IdentityLevel.OWNER)
    engine.approvals.approve(pending.approval_request_id)
    result = engine.execute(
        "test_action", {"value": "ok"}, identity=IdentityLevel.OWNER,
        approval_request_id=pending.approval_request_id,
    )
    assert result.success is True
    assert result.output == "done"
    assert calls == ["ok"]


def test_denied_approval_does_not_execute():
    calls = []
    engine = make_engine(lambda: calls.append(True), permission=Permission.WRITE)
    pending = engine.execute("test_action", identity=IdentityLevel.OWNER)
    engine.approvals.deny(pending.approval_request_id)
    result = engine.execute(
        "test_action", identity=IdentityLevel.OWNER,
        approval_request_id=pending.approval_request_id,
    )
    assert result.success is False
    assert result.status == "denied"
    assert calls == []


def test_mismatched_approval_cannot_execute_different_arguments():
    calls = []
    engine = make_engine(lambda value: calls.append(value), permission=Permission.WRITE)
    pending = engine.execute("test_action", {"value": "approved"}, identity=IdentityLevel.OWNER)
    engine.approvals.approve(pending.approval_request_id)
    result = engine.execute(
        "test_action", {"value": "changed"}, identity=IdentityLevel.OWNER,
        approval_request_id=pending.approval_request_id,
    )
    assert result.success is False
    assert result.status == "rejected"
    assert calls == []


def test_handler_failure_is_structured():
    engine = make_engine(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    result = engine.execute("test_action", identity=IdentityLevel.UNKNOWN)
    assert result.success is False
    assert result.status == "failed"
    assert result.error == "boom"


def test_unknown_action_is_rejected():
    engine = ActionExecutionEngine(ActionRegistry(), approvals=ApprovalController())
    result = engine.execute("missing")
    assert result.success is False
    assert result.status == "rejected"
