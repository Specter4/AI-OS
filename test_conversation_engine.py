from core.conversation import clear, get_history
from core.result import AgentResult
from conversation.engine import respond
import conversation.engine as engine


def test_conversation_engine_preserves_context(monkeypatch):
    clear()
    seen = []

    def fake_generate(messages, agent="conversation"):
        seen.append(messages)
        return AgentResult(True, agent, "The project is AI-OS.")

    monkeypatch.setattr(engine.llm, "generate", fake_generate)

    first = respond("The project is called AI-OS.")
    second = respond("What is the project called?")

    assert first.success is True
    assert second.success is True
    assert any(m["content"] == "The project is called AI-OS." for m in seen[-1])
    assert any(m["content"] == "The project is called AI-OS?" for m in seen[-1])
    history = get_history()
    assert len(history) == 4
    assert history[-1]["content"] == "The project is AI-OS."


def test_conversation_history_can_be_cleared(monkeypatch):
    clear()
    monkeypatch.setattr(
        engine.llm,
        "generate",
        lambda messages, agent="conversation": AgentResult(True, agent, "Hi"),
    )
    respond("Hello")
    clear()
    assert get_history() == []
