import pytest

from workflow.reachout import ReachOutPriority, create_reach_out


def test_reach_out_preserves_reason_and_approval():
    request = create_reach_out(
        message="JARVIS needs your approval before deployment.",
        reason="A protected action requires owner approval.",
        priority=ReachOutPriority.HIGH,
        requires_approval=True,
        task_id=3,
    )
    assert request.message.startswith("JARVIS")
    assert request.requires_approval is True
    assert request.task_id == 3
    assert request.should_interrupt_user is True


def test_normal_reach_out_does_not_interrupt():
    request = create_reach_out(
        message="Your report is ready.",
        reason="The requested research finished.",
    )
    assert request.priority is ReachOutPriority.NORMAL
    assert request.should_interrupt_user is False


@pytest.mark.parametrize("field", ["message", "reason"])
def test_reach_out_requires_context(field):
    values = {
        "message": "A valid message.",
        "reason": "A valid reason.",
    }
    values[field] = "   "
    with pytest.raises(ValueError):
        create_reach_out(**values)
