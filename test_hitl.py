from core.authorization import IdentityLevel
from core.tool_registry import Permission
from workflow.action_executor import ActionExecutionEngine
from workflow.action_registry import ActionRegistry, ActionSpec
from workflow.approval import ApprovalController
from workflow.hitl import HumanControl


def make_control():
    registry = ActionRegistry()
    calls = []
    registry.register(ActionSpec("write", "write something", lambda value: calls.append(value) or "done", metadata={"permission": Permission.WRITE}))
    approvals = ApprovalController()
    engine = ActionExecutionEngine(registry, approvals=approvals)
    return HumanControl(engine, approvals=approvals), calls


def test_pending_requests_are_visible():
    control, _ = make_control()
    result = control.engine.execute("write", {"value": "x"}, identity=IdentityLevel.OWNER)
    assert result.status == "awaiting_approval"
    pending = control.pending()
    assert len(pending) == 1
    assert pending[0].id == result.approval_request_id


def test_approve_executes_exact_requested_action():
    control, calls = make_control()
    result = control.engine.execute("write", {"value": "x"}, identity=IdentityLevel.OWNER)
    controlled = control.approve(result.approval_request_id)
    assert controlled.status == "completed"
    assert controlled.execution is not None
    assert controlled.execution.success is True
    assert calls == ["x"]


def test_deny_never_executes():
    control, calls = make_control()
    result = control.engine.execute("write", {"value": "x"}, identity=IdentityLevel.OWNER)
    controlled = control.deny(result.approval_request_id)
    assert controlled.status == "denied"
    assert controlled.execution is None
    assert calls == []


def test_cancel_never_executes_and_removes_from_pending():
    control, calls = make_control()
    result = control.engine.execute("write", {"value": "x"}, identity=IdentityLevel.OWNER)
    controlled = control.cancel(result.approval_request_id)
    assert controlled.status == "cancelled"
    assert controlled.execution is None
    assert control.pending() == []
    assert calls == []


def test_approval_is_bound_to_original_arguments():
    control, calls = make_control()
    result = control.engine.execute("write", {"value": "x"}, identity=IdentityLevel.OWNER)
    request_id = result.approval_request_id
    control.approvals.approve(request_id)
    mismatched = control.engine.execute(
        "write", {"value": "different"}, identity=IdentityLevel.OWNER, approval_request_id=request_id
    )
    assert mismatched.status == "rejected"
    assert calls == []
