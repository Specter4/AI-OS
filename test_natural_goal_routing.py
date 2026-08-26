from conversation.intent import detect_intent


def test_normal_question_stays_conversation():
    result = detect_intent("What is Python?")
    assert result["intent"] == "conversation"


def test_actionable_request_becomes_autonomous_goal():
    result = detect_intent("Find me three good laptops under $800")
    assert result["intent"] == "autonomous_goal"
    assert result["content"] == "Find me three good laptops under $800"


def test_multi_step_goal_becomes_autonomous_goal():
    result = detect_intent(
        "Research the best laptop for me, compare the options, and recommend one."
    )
    assert result["intent"] == "autonomous_goal"


def test_explanation_question_with_action_word_stays_conversation():
    result = detect_intent("How do I build a website?")
    assert result["intent"] == "conversation"


def test_explicit_research_command_keeps_research_intent():
    result = detect_intent("research the best local LLMs")
    assert result["intent"] == "research"
