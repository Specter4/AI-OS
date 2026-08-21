from core.router import route_message


def test_router_uses_classifier(monkeypatch):
    def fake_classify(message):
        return {"intent": "memory_store", "content": message}

    monkeypatch.setattr("core.router.classify", fake_classify)

    result = route_message("remember company = AI-OS")

    assert result == {
        "intent": "memory_store",
        "content": "remember company = AI-OS",
    }
