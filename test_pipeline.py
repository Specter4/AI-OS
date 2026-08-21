from agents.manager import handle_request
from core.router import route_message


def test_pipeline_memory_flow(monkeypatch):
    """Exercise router -> manager without requiring Ollama."""

    def fake_classify(message):
        if message.startswith("remember "):
            return {"intent": "memory_store", "content": message[len("remember "):]} 
        if message.startswith("recall "):
            return {"intent": "memory_recall", "content": message[len("recall "):]} 
        return {"intent": "conversation", "content": message}

    monkeypatch.setattr("core.router.classify", fake_classify)

    request = route_message("remember pipeline_company = AI-OS")
    assert "I will remember" in handle_request(request)

    request = route_message("recall pipeline_company")
    assert "AI-OS" in handle_request(request)
