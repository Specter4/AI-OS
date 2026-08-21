import pytest

from core.router import route_message


def test_ai_router_smoke(monkeypatch):
    """Router tests must not require a running Ollama server."""
    seen = []

    def fake_classify(message):
        seen.append(message)
        return {"intent": "conversation", "content": message}

    monkeypatch.setattr("core.router.classify", fake_classify)

    assert route_message("My company is Nova Studio") == {
        "intent": "conversation",
        "content": "My company is Nova Studio",
    }
    assert route_message("Research AI website ideas")["content"] == "Research AI website ideas"
    assert len(seen) == 2
