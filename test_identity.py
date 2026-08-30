import importlib

import core.identity as identity_module
import conversation.engine as engine


def test_default_identity_is_jarvis_for_asif():
    identity = identity_module.load_identity()

    assert identity.name == "JARVIS"
    assert identity.owner_name == "Asif"
    assert identity.relationship == "personal AI assistant"
    assert "natural conversation" in identity.capabilities[0]


def test_identity_can_be_renamed_with_environment(monkeypatch):
    monkeypatch.setenv("AIOS_ASSISTANT_NAME", "Friday")
    monkeypatch.setenv("AIOS_OWNER_NAME", "Alex")
    monkeypatch.setenv("AIOS_ASSISTANT_RELATIONSHIP", "digital chief of staff")

    identity = identity_module.load_identity()
    prompt = identity.system_prompt()

    assert identity.name == "Friday"
    assert identity.owner_name == "Alex"
    assert identity.relationship == "digital chief of staff"
    assert "Your name is Friday." in prompt
    assert "You are Alex's digital chief of staff." in prompt


def test_conversation_prompt_contains_identity_and_human_style_rules():
    assert "Your name is JARVIS." in engine.SYSTEM_PROMPT
    assert "You are Asif's personal AI assistant." in engine.SYSTEM_PROMPT
    assert "Speak like a highly capable human personal assistant" in engine.SYSTEM_PROMPT
    assert "several questions or requests in one message" in engine.SYSTEM_PROMPT
    assert "useful observation" in engine.SYSTEM_PROMPT
    assert "Never claim an action was completed" in engine.SYSTEM_PROMPT


def test_identity_module_remains_reload_safe(monkeypatch):
    monkeypatch.setenv("AIOS_ASSISTANT_NAME", "JARVIS")
    reloaded = importlib.reload(identity_module)
    assert reloaded.identity.name == "JARVIS"
