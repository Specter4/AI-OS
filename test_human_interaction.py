from conversation.human_interaction import analyze


def test_detects_correction_and_extracts_new_instruction():
    signals = analyze("No, actually use the cheaper option", has_previous_turn=True)
    assert signals.is_correction is True
    assert signals.correction_text == "use the cheaper option"


def test_detects_reference_as_follow_up():
    signals = analyze("Can you change that and send it again?", has_previous_turn=True)
    assert signals.is_follow_up is True
    assert signals.refers_to_previous is True


def test_does_not_invent_follow_up_without_history():
    signals = analyze("Do it", has_previous_turn=False)
    assert signals.is_follow_up is False
    assert signals.refers_to_previous is False


def test_detects_urgency():
    signals = analyze("Handle this ASAP")
    assert signals.is_urgent is True
