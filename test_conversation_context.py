from conversation.context import ConversationContext, clear_context


def test_context_tracks_active_goal_and_completed_goals():
    ctx = ConversationContext()
    ctx.observe("Find three laptops", goal=True)
    assert ctx.active_goal == "Find three laptops"
    assert "Find three laptops" in ctx.prompt_context()

    ctx.complete_goal("Find three laptops")
    assert ctx.active_goal is None
    assert ctx.active_topic == "Find three laptops"
    assert "Find three laptops" in ctx.prompt_context()


def test_context_keeps_only_recent_completed_goals():
    ctx = ConversationContext()
    for i in range(7):
        ctx.complete_goal(f"goal {i}")
    assert ctx.completed_goals == ["goal 2", "goal 3", "goal 4", "goal 5", "goal 6"]


def test_clear_context_resets_global_state():
    from conversation.context import context
    context.observe("build something", goal=True)
    context.complete_goal("build something")
    clear_context()
    assert context.active_goal is None
    assert context.active_topic is None
    assert context.completed_goals == []
