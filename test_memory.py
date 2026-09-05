from agents.memory import MemoryStore


def test_memory_persists_across_store_instances(tmp_path):
    path = tmp_path / "memory.db"

    first = MemoryStore(path)
    record = first.remember(
        "favorite editor",
        "VS Code",
        category="preference",
        importance=8,
        confidence=0.95,
    )

    second = MemoryStore(path)
    recalled = second.recall("favorite editor", category="preference")

    assert record.id == 1
    assert recalled is not None
    assert recalled.value == "VS Code"
    assert recalled.category == "preference"
    assert recalled.importance == 8
    assert recalled.confidence == 0.95


def test_memory_update_preserves_history(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.remember("goal", "Build AI-OS", category="goal")
    updated = store.remember("goal", "Finish Phase 7", category="goal", reason="owner_update")

    history = store.history("goal", category="goal")

    assert updated.value == "Finish Phase 7"
    assert len(history) == 1
    assert history[0]["old_value"] == "Build AI-OS"
    assert history[0]["new_value"] == "Finish Phase 7"
    assert history[0]["reason"] == "owner_update"


def test_memory_search_and_category_filter(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.remember("laptop", "Prefers lightweight laptops", category="preference", importance=7)
    store.remember("laptop_model", "ThinkPad", category="fact", importance=5)
    store.remember("college", "HSC student", category="context", importance=6)

    results = store.search("laptop")
    preferences = store.search("laptop", category="preference")

    assert [item.key for item in results] == ["laptop", "laptop_model"]
    assert [item.key for item in preferences] == ["laptop"]


def test_memory_supports_required_categories(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")

    for category in ("fact", "preference", "person", "event", "goal", "context"):
        store.remember(category, f"value-{category}", category=category)

    assert {item.category for item in store.list()} == {
        "fact",
        "preference",
        "person",
        "event",
        "goal",
        "context",
    }


def test_memory_validates_quality_fields(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")

    try:
        store.remember("bad", "value", importance=11)
        assert False, "importance validation should fail"
    except ValueError as exc:
        assert "importance" in str(exc)

    try:
        store.remember("bad", "value", confidence=1.1)
        assert False, "confidence validation should fail"
    except ValueError as exc:
        assert "confidence" in str(exc)

    try:
        store.remember("bad", "value", category="unknown")
        assert False, "category validation should fail"
    except ValueError as exc:
        assert "category" in str(exc)


def test_memory_forget_and_clear(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.remember("one", "1")
    store.remember("two", "2")

    assert store.forget("one") == 1
    assert store.recall("one") is None
    assert store.recall("two") is not None

    store.clear()
    assert store.list() == []
    assert store.history("two") == []
