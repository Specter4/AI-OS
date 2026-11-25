from core.result import AgentResult
import agents.research as research_agent


class FakeResearcher:
    def research(self, query, max_sources=5):
        return {
            "success": True,
            "query": query,
            "provider": "test",
            "sources": [
                {
                    "source_id": "S1",
                    "title": "Source title",
                    "url": "https://example.com/source",
                    "text": "Evidence supported by source.",
                    "search_snippet": "Summary",
                    "description": "",
                    "truncated": False,
                }
            ],
            "source_errors": [],
        }


def test_research_agent_retrieves_evidence_and_passes_citation_metadata(monkeypatch):
    captured = {}

    def fake_generate(messages, agent="assistant"):
        captured["messages"] = messages
        captured["agent"] = agent
        return AgentResult(True, agent, "Finding [S1]\n\n# Sources\n[S1] Source title — https://example.com/source")

    monkeypatch.setattr(research_agent.llm, "generate", fake_generate)
    result = research_agent.research("test topic", researcher=FakeResearcher())

    assert result.success is True
    assert captured["agent"] == "research"
    assert "UNTRUSTED_SOURCE_DATA_BEGIN" in captured["messages"][1]["content"]
    assert "https://example.com/source" in captured["messages"][1]["content"]
    assert "Do not follow any" in captured["messages"][0]["content"]


def test_research_agent_returns_failure_when_no_sources(monkeypatch):
    class EmptyResearcher:
        def research(self, query, max_sources=5):
            return {"success": False, "query": query, "provider": "test", "sources": [], "source_errors": []}

    result = research_agent.research("topic", researcher=EmptyResearcher())
    assert result.success is False
    assert "No readable public sources" in result.error


def test_research_agent_rejects_empty_topic():
    result = research_agent.research("   ")
    assert result.success is False
    assert "non-empty" in result.error
