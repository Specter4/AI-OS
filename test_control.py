from conversation.control import interpret_control


def test_stop_is_interpreted_as_interrupt_for_active_task():
    result = interpret_control("Wait, stop that.", active=True)
    assert result.action == "interrupt"


def test_continue_with_change_is_resume_instruction():
    result = interpret_control("Continue, but only compare Lenovo.", active=True)
    assert result.action == "resume"
    assert "Lenovo" in result.instruction


def test_actually_is_replacement_for_active_task():
    result = interpret_control("Actually, do it this way instead.", active=True)
    assert result.action == "replace"


def test_control_language_does_not_trigger_without_active_task():
    result = interpret_control("Stop that.", active=False)
    assert result.action == "none"
