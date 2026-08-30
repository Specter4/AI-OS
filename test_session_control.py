from conversation.control import ControlIntent
from workflow.session import SessionState


def test_session_interprets_stop_against_active_goal():
    session = SessionState(active_goal="Research laptops")
    intent = session.interpret("Wait, stop that.")
    assert intent == ControlIntent("interrupt", "Wait, stop that.")


def test_session_control_requests_interrupt_with_revised_instruction():
    session = SessionState(active_goal="Research laptops")
    intent = session.handle_control("Actually, do it this way instead.")
    assert intent.action == "replace"
    request = session.interrupt_controller.get()
    assert request is not None
    assert request.instruction == "Actually, do it this way instead."


def test_session_control_ignores_stop_when_idle():
    session = SessionState()
    intent = session.handle_control("Stop that.")
    assert intent.action == "none"
    assert session.interrupt_controller.get() is None
