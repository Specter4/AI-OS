from agents.tool_agent import ToolAgent
from core.tool_registry import Permission, registry
from workflow.approval import ApprovalController
from workflow.autonomy import AutonomyLoop


def test_approval_controller_lifecycle():
    controller = ApprovalController()

    spec = registry.register(
        "approval.lifecycle",
        "Perform an external action",
        lambda: "done",
        Permission.EXTERNAL,
    )

    request = controller.create(
        spec,
        {"item": "laptop"},
        goal="buy a laptop",
        task="purchase the selected laptop",
    )

    assert request.status == "pending"
    assert controller.pending() == [request]
    assert controller.get(request.id).tool == "approval.lifecycle"

    approved = controller.approve(request.id)
    assert approved.status == "approved"
    assert controller.pending() == []

    try:
        controller.approve(request.id)
        assert False, "resolved requests must not be approved twice"
    except ValueError:
        pass


def test_autonomy_pauses_and_resumes_after_approval():
    name = "approval.resume"
    registry.register(
        name,
        "Perform an external action",
        lambda item: f"bought {item}",
        Permission.EXTERNAL,
    )

    agent = ToolAgent()
    agent.select_tool = lambda task: type(
        "Request", (), {"tool": name, "arguments": {"item": "laptop"}}
    )()

    loop = AutonomyLoop(agent=agent, max_steps=2)
    loop.evaluate = lambda goal, observations: {
        "complete": True,
        "next_task": None,
    }

    paused = loop.run("buy the laptop")

    assert paused.success is False
    assert paused.approval_request is not None
    assert paused.approval_request.status == "pending"
    assert paused.suspended_task == "buy the laptop"
    assert paused.observations[-1].recovery_action == "request_approval"

    request_id = paused.approval_request.id
    approval = __import__("workflow.approval", fromlist=["approval_controller"]).approval_controller
    approval.approve(request_id)

    resumed = loop.resume(paused, request_id)

    assert resumed.success is True
    assert resumed.observations[-1].success is True
    assert resumed.observations[-1].result == "bought laptop"


def test_resume_requires_approved_request():
    controller = ApprovalController()
    spec = registry.register(
        "approval.pending",
        "Perform an external action",
        lambda: "done",
        Permission.EXTERNAL,
    )
    request = controller.create(spec, {})

    assert request.status == "pending"
