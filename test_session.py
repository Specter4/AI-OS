from core.tool_registry import Permission, ToolRegistry
from agents.tool_agent import ToolAgent
from workflow.session import SessionState


def test_session_shares_interrupt_controller_with_autonomy():
    session = SessionState()
    loop = session.start("Research laptops", agent=ToolAgent(registry=ToolRegistry()), max_steps=1)

    assert session.active_goal == "Research laptops"
    assert loop.interrupt_controller is session.interrupt_controller
    assert "Active goal: Research laptops" in session.snapshot()["conversation"]


def test_session_interrupt_and_resume_updates_shared_state():
    registry = ToolRegistry()
    registry.register("research", "Research", lambda task: task, Permission.READ)
    agent = ToolAgent(registry=registry)
    session = SessionState()
    loop = session.start("Research laptops", agent=agent, max_steps=1)

    loop.interrupt("Wait, stop.", "Research Lenovo laptops only")
    result = loop.run("Research laptops")
    session.record_result(result)

    assert session.last_result is result
    assert result.suspended_task == "Research laptops"
    assert session.active_goal == "Research laptops"

    resumed = session.resume_with_instruction("Research Lenovo laptops only", agent=agent, max_steps=1)
    assert session.last_result is resumed
    assert resumed.observations[0].task == "Research Lenovo laptops only"
