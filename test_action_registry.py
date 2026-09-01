import pytest

from workflow.action_registry import ActionRegistry, ActionSpec


def test_register_and_lookup_action_case_insensitively():
    registry = ActionRegistry()
    action = ActionSpec("deploy", "Deploy the application", handler=lambda: "ok")
    assert registry.register(action) is action
    assert registry.get("DEPLOY") is action
    assert registry.require(" deploy ").can_execute()


def test_registry_exposes_registered_actions():
    registry = ActionRegistry()
    registry.register(ActionSpec("research", "Research a topic"))
    registry.register(ActionSpec("deploy", "Deploy an application", requires_approval=True))
    assert registry.names() == ("research", "deploy")
    assert [a.name for a in registry.list()] == ["research", "deploy"]
    assert registry.require("deploy").requires_approval is True


def test_duplicate_or_empty_action_names_are_rejected():
    registry = ActionRegistry()
    registry.register(ActionSpec("deploy", "Deploy"))
    with pytest.raises(ValueError):
        registry.register(ActionSpec(" DEPLOY ", "Duplicate"))
    with pytest.raises(ValueError):
        registry.register(ActionSpec("   ", "Invalid"))


def test_unknown_action_is_explicitly_rejected():
    registry = ActionRegistry()
    assert registry.get("missing") is None
    with pytest.raises(KeyError):
        registry.require("missing")


def test_clear_removes_registered_actions():
    registry = ActionRegistry()
    registry.register(ActionSpec("research", "Research"))
    registry.clear()
    assert registry.names() == ()
