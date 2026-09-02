from core.tool_registry import Permission, ToolSpec
from workflow.approval import ApprovalController


def make_spec(permission=Permission.WRITE):
    return ToolSpec(name="deploy", description="Deploy the service", permission=permission, handler=lambda **_: None)


def test_elevated_action_creates_pending_approval():
    controller = ApprovalController()
    request = controller.create(make_spec(), {"environment": "production"}, goal="Deploy", task="Deploy service")
    assert request.status == "pending"
    assert request.tool == "deploy"
    assert controller.pending() == [request]


def test_approval_is_explicit_and_resolvable():
    controller = ApprovalController()
    request = controller.create(make_spec(), {})
    approved = controller.approve(request.id)
    assert approved.status == "approved"
    assert controller.pending() == []


def test_denial_is_explicit():
    controller = ApprovalController()
    request = controller.create(make_spec(), {})
    denied = controller.deny(request.id)
    assert denied.status == "denied"
    assert controller.pending() == []


def test_resolved_request_cannot_be_resolved_again():
    controller = ApprovalController()
    request = controller.create(make_spec(), {})
    controller.approve(request.id)
    try:
        controller.deny(request.id)
    except ValueError:
        pass
    else:
        raise AssertionError("resolved approval should not be changed")
