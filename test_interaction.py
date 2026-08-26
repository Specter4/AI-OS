from agents.tool_agent import ToolAgent
from core.tool_registry import Permission, ToolRegistry
from workflow.approval import ApprovalController
from workflow.autonomy import AutonomyLoop
from workflow.interaction import AutonomyInteraction


def test_interaction_formats_approval_and_resumes():
    registry = ToolRegistry()
    registry.register(
        "purchase.laptop",
        "Purchase a laptop",
        lambda item: f"bought {item}",
        Permission.EXTERNAL,
    )

    agent = ToolAgent(registry=registry)
    agent.select_tool = lambda task: type(
        "Request", (), {"tool": "purchase.laptop", "arguments": {"item": "laptop"}}
    )()

    loop = AutonomyLoop(agent=agent, max_steps=1)
    controller = AutonomyInteraction(loop)

    run = controller.start("buy a laptop")

    assert run.result.success is False
    assert run.result.approval_request is not None
    request = run.result.approval_request
    text = controller.format_result(run)
    assert "APPROVAL REQUIRED" in text
    assert request.id in text
    assert request.tool == "purchase.laptop"


def test_interaction_denial_stops_run():
    registry = ToolRegistry()
    registry.register(
        "external.denied",
        "External action",
        lambda: "done",
        Permission.EXTERNAL,
    )

    agent = ToolAgent(registry=registry)
    agent.select_tool = lambda task: type(
        "Request", (), {"tool": "external.denied", "arguments": {}}
    )()

    loop = AutonomyLoop(agent=agent, max_steps=1)
    controller = AutonomyInteraction(loop)
    run = controller.start("do external action")
    request = run.result.approval_request

    updated = controller.deny(run.id, request.id)
    assert updated.result.success is False
    assert "denied" in updated.result.error.lower()
