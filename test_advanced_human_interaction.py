from core.result import AgentResult
from conversation.context import clear_context, context
import conversation.engine as engine


def test_context_tracks_latest_turn_and_signals(monkeypatch):
    clear_context()
    monkeypatch.setattr(
        engine.llm,
        "generate",
        lambda messages, agent="conversation": AgentResult(True, agent, "Understood."),
    )

    engine.respond("Research laptops")
    engine.respond("No, actually compare the cheaper ones")

    assert context.turn_count == 2
    assert context.last_user_message == "No, actually compare the cheaper ones"
    assert context.last_assistant_message == "Understood."
    assert context.last_signals.is_correction is True
    assert context.last_signals.is_follow_up is True


def test_engine_adds_correction_and_reference_guidance(monkeypatch):
    clear_context()
    seen = []

    def fake_generate(messages, agent="conversation"):
        seen.append(messages)
        return AgentResult(True, agent, "Got it.")

    monkeypatch.setattr(engine.llm, "generate", fake_generate)
    engine.respond("Research laptops")
    engine.respond("Actually, compare that with the budget option")

    system = seen[-1][0]["content"]
    assert "ADVANCED HUMAN INTERACTION" in system
    assert "newest instruction supersedes" in system
    assert "follow-up" in system.lower()
    assert "resolve references naturally" in system.lower()


def test_empty_message_does_not_corrupt_interaction_state(monkeypatch):
    clear_context()
    monkeypatch.setattr(
        engine.llm,
        "generate",
        lambda messages, agent="conversation": AgentResult(True, agent, "Ready."),
    )

    engine.respond("First turn")
    before = context.turn_count
    engine.respond("   ")
    assert context.turn_count == before
