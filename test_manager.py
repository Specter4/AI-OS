from agents.manager import handle_request


def test_manager_memory_store_and_recall():
    assert handle_request({
        "intent": "memory_store",
        "content": "test_company = AI-OS",
    }) == "✅ I will remember **test_company** = **AI-OS**"

    assert handle_request({
        "intent": "memory_recall",
        "content": "test_company",
    }) == "🧠 **test_company** = **AI-OS**"


def test_manager_unknown_intent():
    result = handle_request({
        "intent": "unknown",
        "content": "test",
    })

    assert "don't know how to handle" in result
