from core.result import AgentResult
from conversation.context import clear_context, context
import conversation.engine as engine


def test_proactive_instruction_is_present(monkeypatch):
    clear_context()
    seen = []

    def fake_generate(messages, agent="conversation"):
        seen.append(messages)
        return AgentResult(True, agent, "Done. Also, check the deployment health.")

    monkeypatch.setattr(engine.llm, "generate", fake_generate)
    result = engine.respond("Deploy the project")

    assert result.success is True
    system = seen[-1][0]["content"]
    assert "PROACTIVE FOLLOW-THROUGH" in system
    assert "exactly one genuinely useful next thing" in system


def test_context_tracks_goal_for_proactive_followup(monkeypatch):
    clear_context()
    monkeypatch.setattr(
        engine.llm,
        "generate",
        lambda messages, agent="conversation": AgentResult(True, agent, "I'll handle it."),
    )

    engine.respond("Research the best laptop for programming", goal=True)
    assert context.active_goal == "Research the best laptop for programming"
    assert context.active_topic == "Research the best laptop for programming"
