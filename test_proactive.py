from workflow.proactive import ProactiveKind, suggest


def test_dependency_has_highest_priority():
    result = suggest(dependency="The deployment still needs credentials.", next_step="Run tests.")
    assert result.kind is ProactiveKind.DEPENDENCY
    assert result.should_surface


def test_next_step_is_selected_when_no_dependency_exists():
    result = suggest(next_step="Run the integration tests.", opportunity="Add monitoring.")
    assert result.kind is ProactiveKind.NEXT_STEP


def test_only_one_suggestion_is_selected():
    result = suggest(
        dependency="Missing credentials.",
        next_step="Run tests.",
        trade_off="This increases latency.",
        follow_up="Which region?",
        opportunity="Add monitoring.",
    )
    assert result.kind is ProactiveKind.DEPENDENCY
    assert result.message == "Missing credentials."


def test_no_useful_observation_means_no_suggestion():
    result = suggest()
    assert result.kind is ProactiveKind.NONE
    assert not result.should_surface
